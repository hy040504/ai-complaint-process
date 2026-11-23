/**
 * 담당자 실시간 AI 작업 모니터용 SSE(`EventSource`) 클라이언트입니다.
 *
 * `Last-Event-ID` 기반 중복 제거·순서 보장, `resync_required` 스냅샷 재동기화,
 * 연결 장애 시 3초 폴링 대체 전환과 복구 시 자동 원복을 담당합니다.
 */

import { escapeHTML as esc } from "./citizen.js";

/** 담당자 SSE 스트림에서 수신하는 업무·작업 이벤트 이름 목록입니다. */
export const STAFF_SSE_EVENT_TYPES = [
  "ai_job.stage_changed",
  "ai_job.completed",
  "ai_job.failed",
  "ai_job.cancelled",
  "complaint.created",
  "complaint.updated",
  "complaint.deleted",
];

/** SSE 연결 상태별 화면 표기와 시각 톤 매핑입니다. */
export const SSE_STATE_META = {
  idle: { label: "연결 대기", tone: "idle" },
  connecting: { label: "실시간 연결 중…", tone: "warn" },
  connected: { label: "실시간 연결됨", tone: "live" },
  reconnecting: { label: "다시 연결 중…", tone: "warn" },
  fallback: { label: "3초마다 확인 중", tone: "fallback" },
};

/**
 * 안전하게 JSON 문자열을 객체로 파싱합니다.
 *
 * @param {string} raw SSE `data` 원문 문자열입니다.
 * @returns {object|null} 파싱된 객체 또는 실패 시 null입니다.
 */
function parseJsonSafe(raw) {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

/**
 * 담당자 화면용 단일 SSE 구독 관리자를 만듭니다.
 *
 * @param {object} [options] 구독 설정과 콜백입니다.
 * @param {string} [options.url="/api/v1/staff/events"] SSE 엔드포인트 경로입니다.
 * @param {number} [options.initialCursor=0] 초기 스냅샷에서 받은 마지막 이벤트 커서입니다.
 * @param {number} [options.maxErrorsBeforeFallback=2] 폴링 대체 상태로 전환할 연속 오류 횟수입니다.
 * @param {((url:string) => EventSource)=} options.createEventSource 테스트 주입용 EventSource 생성기입니다.
 * @param {((type:string, payload:object) => void)=} options.onEvent 새 이벤트 수신 콜백입니다.
 * @param {((payload:object) => void)=} options.onResync 커서 만료·버퍼 초과 시 스냅샷 재조회 콜백입니다.
 * @param {((state:string, detail:object) => void)=} options.onStateChange 연결 상태 변경 콜백입니다.
 * @returns {object} `open`, `close`, `getState`, `getLastEventId` 제어 객체입니다.
 */
export function createStaffEventStream({
  url = "/api/v1/staff/events",
  initialCursor = 0,
  maxErrorsBeforeFallback = 2,
  createEventSource,
  onEvent,
  onResync,
  onStateChange,
} = {}) {
  let source = null;
  let state = "idle";
  let lastEventId = Number.isFinite(initialCursor) ? Math.max(0, initialCursor) : 0;
  let errorCount = 0;
  let lastEventAt = null;

  /**
   * 내부 연결 상태를 갱신하고 상태 변경 콜백을 알립니다.
   *
   * @param {string} next 새 연결 상태 문자열입니다.
   * @param {object} [extra={}] 추가 상태 메타데이터입니다.
   * @returns {void}
   */
  function setState(next, extra = {}) {
    if (state === next && !extra.force) return;
    state = next;
    onStateChange?.(state, {
      lastEventId,
      lastEventAt,
      errorCount,
      ...extra,
    });
  }

  /**
   * 열려 있는 SSE 연결을 닫아 중복 구독과 유휴 소켓 점유를 막습니다.
   *
   * @param {boolean} [resetState=true] 상태를 `idle`로 되돌릴지 여부입니다.
   * @returns {void}
   */
  function close(resetState = true) {
    if (source) {
      try {
        source.close();
      } catch {
        /* 이미 닫힌 EventSource 정리 오류는 무시합니다. */
      }
      source = null;
    }
    errorCount = 0;
    if (resetState) setState("idle");
  }

  /**
   * 지정한 커서 이후부터 담당자 SSE 구독을 시작합니다.
   *
   * @param {number} [cursor] 스냅샷에서 확보한 최신 이벤트 커서입니다.
   * @returns {void}
   */
  function open(cursor) {
    close(false);
    if (Number.isFinite(cursor) && cursor >= 0) {
      lastEventId = Math.max(lastEventId, cursor);
    }
    const factory =
      createEventSource ||
      (typeof EventSource !== "undefined"
        ? (targetUrl) => new EventSource(targetUrl, { withCredentials: true })
        : null);
    if (!factory) {
      setState("fallback", { reason: "unsupported", force: true });
      return;
    }
    const targetUrl =
      lastEventId > 0
        ? `${url}${url.includes("?") ? "&" : "?"}lastEventId=${encodeURIComponent(String(lastEventId))}`
        : url;
    setState("connecting", { force: true });
    try {
      source = factory(targetUrl);
    } catch {
      setState("fallback", { reason: "init_failed", force: true });
      return;
    }

    source.addEventListener("connected", (evt) => {
      const payload = parseJsonSafe(evt?.data) || {};
      errorCount = 0;
      if (Number.isFinite(payload.cursor)) {
        lastEventId = Math.max(lastEventId, Number(payload.cursor));
      }
      lastEventAt = payload.occurredAt || new Date().toISOString();
      setState("connected", { aiConnected: Boolean(payload.aiConnected), force: true });
    });

    source.addEventListener("resync_required", (evt) => {
      const payload = parseJsonSafe(evt?.data) || {};
      errorCount = 0;
      if (Number.isFinite(payload.cursor)) {
        lastEventId = Math.max(0, Number(payload.cursor));
      }
      lastEventAt = payload.occurredAt || new Date().toISOString();
      setState("connected");
      onResync?.(payload);
    });

    for (const type of STAFF_SSE_EVENT_TYPES) {
      source.addEventListener(type, (evt) => {
        const payload = parseJsonSafe(evt?.data) || {};
        const rawId = evt?.lastEventId || payload.eventId;
        const parsedId =
          rawId !== undefined && rawId !== null && String(rawId).trim() !== ""
            ? Number(rawId)
            : NaN;
        if (Number.isFinite(parsedId)) {
          // 재연결 중 중복·역순으로 도착한 이전 커서 이벤트는 무시합니다.
          if (parsedId <= lastEventId) return;
          lastEventId = parsedId;
        }
        errorCount = 0;
        lastEventAt = payload.occurredAt || new Date().toISOString();
        setState("connected");
        onEvent?.(type, payload);
      });
    }

    source.onerror = () => {
      errorCount += 1;
      const closed = source && source.readyState === 2;
      if (closed || errorCount >= maxErrorsBeforeFallback) {
        setState("fallback", { reason: closed ? "closed" : "error" });
      } else {
        setState("reconnecting", { reason: "error" });
      }
    };
  }

  return {
    open,
    close,
    /**
     * 현재 SSE 연결 상태를 반환합니다.
     *
     * @returns {string} `idle`·`connecting`·`connected`·`reconnecting`·`fallback` 중 하나입니다.
     */
    getState: () => state,
    /**
     * 마지막으로 확인한 이벤트 커서 번호를 반환합니다.
     *
     * @returns {number} 마지막 이벤트 ID입니다.
     */
    getLastEventId: () => lastEventId,
    /**
     * 마지막 이벤트 수신 시각(ISO 문자열)을 반환합니다.
     *
     * @returns {string|null} 마지막 수신 시각 또는 null입니다.
     */
    getLastEventAt: () => lastEventAt,
  };
}

/**
 * 담당자 모니터·대시보드 헤더에 표시할 실시간 SSE 연결 배지 HTML을 생성합니다.
 *
 * @param {string} state 현재 SSE 연결 상태 문자열입니다.
 * @param {string|null} [lastEventAt=null] 마지막 이벤트 수신 시각(ISO)입니다.
 * @returns {string} 상태 점과 설명 문구가 포함된 HTML입니다.
 */
export function renderSseStatusBadge(state, lastEventAt = null) {
  const meta = SSE_STATE_META[state] || SSE_STATE_META.idle;
  const timeNote =
    lastEventAt && state === "connected"
      ? ` · ${new Date(lastEventAt).toLocaleTimeString("ko-KR")}`
      : "";
  return `<span class="connection sse-${esc(meta.tone)}" role="status" aria-live="polite"><i></i>${esc(meta.label)}${esc(timeNote)}</span>`;
}
