/** 담당자 실시간 SSE 클라이언트 상태 전이·중복 제거·재동기화·폴링 대체 전환을 검증합니다. */
import assert from "node:assert/strict";
import test from "node:test";

import {
  createStaffEventStream,
  renderSseStatusBadge,
} from "../src/realtime.js";

/**
 * 단위 테스트용 모의 EventSource 구현을 만듭니다.
 *
 * @param {string} url 연결 대상 URL입니다.
 * @returns {object} 이벤트 발행과 닫기 여부를 추적하는 가짜 EventSource입니다.
 */
function makeFakeEventSource(url) {
  const listeners = new Map();
  return {
    url,
    readyState: 1,
    closed: false,
    onerror: null,
    addEventListener(type, fn) {
      if (!listeners.has(type)) listeners.set(type, []);
      listeners.get(type).push(fn);
    },
    emit(type, evt = {}) {
      for (const fn of listeners.get(type) || []) fn(evt);
    },
    triggerError(closed = false) {
      if (closed) this.readyState = 2;
      this.onerror?.(new Event("error"));
    },
    close() {
      this.closed = true;
      this.readyState = 2;
    },
  };
}

test("createStaffEventStream은 연결·중복 제거·resync_required·폴링 대체 복구를 정확히 처리한다", () => {
  const created = [];
  const received = [];
  const resyncs = [];
  const states = [];

  const stream = createStaffEventStream({
    url: "/api/v1/staff/events",
    initialCursor: 2,
    maxErrorsBeforeFallback: 2,
    createEventSource: (url) => {
      const es = makeFakeEventSource(url);
      created.push(es);
      return es;
    },
    onEvent: (type, payload) => received.push([type, payload.eventId, payload.stage]),
    onResync: (payload) => resyncs.push(payload),
    onStateChange: (state) => states.push(state),
  });

  stream.open(3);
  assert.equal(created.length, 1);
  assert.match(created[0].url, /lastEventId=3$/);
  assert.equal(stream.getState(), "connecting");

  const es = created[0];
  es.emit("connected", {
    data: JSON.stringify({
      cursor: 3,
      aiConnected: true,
      occurredAt: "2026-11-20T01:00:00Z",
    }),
  });
  assert.equal(stream.getState(), "connected");

  // 커서보다 작거나 같은 중복 이벤트는 무시하고 새 이벤트만 전달합니다.
  es.emit("ai_job.stage_changed", {
    lastEventId: "3",
    data: JSON.stringify({ eventId: 3, stage: "중복 무시" }),
  });
  es.emit("ai_job.stage_changed", {
    lastEventId: "4",
    data: JSON.stringify({ eventId: 4, stage: "검색 중" }),
  });
  assert.deepEqual(received, [["ai_job.stage_changed", 4, "검색 중"]]);
  assert.equal(stream.getLastEventId(), 4);

  // resync_required 수신 시 커서를 갱신하고 콜백을 호출합니다.
  es.emit("resync_required", {
    data: JSON.stringify({ reason: "cursor_expired", cursor: 10 }),
  });
  assert.equal(resyncs.length, 1);
  assert.equal(stream.getLastEventId(), 10);

  // 1차 오류 -> reconnecting, 2차 오류 -> fallback, 다시 connected -> connected 복구
  es.triggerError(false);
  assert.equal(stream.getState(), "reconnecting");
  es.triggerError(false);
  assert.equal(stream.getState(), "fallback");
  es.emit("connected", {
    data: JSON.stringify({ cursor: 10, aiConnected: true }),
  });
  assert.equal(stream.getState(), "connected");

  stream.close();
  assert.equal(es.closed, true);
  assert.equal(stream.getState(), "idle");
  assert.ok(states.includes("fallback"));
});

test("EventSource가 없으면 즉시 폴링 대체 상태로 전환하고 배지를 렌더링한다", () => {
  const prev = globalThis.EventSource;
  try {
    globalThis.EventSource = undefined;
    const states = [];
    const stream = createStaffEventStream({
      onStateChange: (s) => states.push(s),
    });
    stream.open();
    assert.equal(stream.getState(), "fallback");
    assert.deepEqual(states, ["fallback"]);
  } finally {
    globalThis.EventSource = prev;
  }

  const liveHtml = renderSseStatusBadge("connected", "2026-11-20T01:00:00Z");
  assert.match(liveHtml, /sse-live/);
  assert.match(liveHtml, /실시간 연결됨/);
  const fallbackHtml = renderSseStatusBadge("fallback");
  assert.match(fallbackHtml, /sse-fallback/);
  assert.match(fallbackHtml, /3초마다 확인 중/);
});
