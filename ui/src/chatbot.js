/**
 * 시민 민원 도우미(`#/citizen/assistant`)의 다중 턴 RAG + LLM 챗봇 클라이언트,
 * 세션 목록·복원·삭제 API, 비로그인 임시 저장소, 시민 전용 안전 결과 카드 렌더러입니다.
 *
 * 서버의 `/api/v1/citizen/chat*` 경로만 호출하며, 미게시 담당자 초안·
 * 직원 보호 순화·내부 프롬프트는 다루지 않습니다.
 */

import { escapeHTML as esc } from "./citizen.js";
import { icon } from "./icons.js";
import { PROVIDER_SHORT_LABELS } from "./llm-meta.js";

/** 비로그인 시연 시민이 현재 탭에서 임시 대화를 이어갈 때 쓰는 sessionStorage 키입니다. */
export const ANON_CHAT_STORAGE_KEY = "citizen-anon-chat-v1";

/** 시민 챗봇 판정 갈래별 카드 제목과 시각 톤 정의입니다. */
const OUTCOME_CARD_META = {
  faq_answer: {
    title: "공식 FAQ 안내",
    chip: "바로 안내",
    tone: "faq",
    cta: "그래도 민원으로 작성하기",
    ctaClass: "",
  },
  department_suggestion: {
    title: "현장 조치 · 민원 작성 안내",
    chip: "담당자 확인 필요",
    tone: "action",
    cta: "이 내용으로 민원 작성",
    ctaClass: "primary",
  },
  human_handoff: {
    title: "담당자 검토 안내",
    chip: "검토 연결",
    tone: "handoff",
    cta: "이 내용으로 민원 작성",
    ctaClass: "primary",
  },
};

/**
 * 외부 출처 링크가 안전한 HTTP(S) 주소인지 검증합니다.
 *
 * @param {string|null|undefined} url 검증할 출처 URL입니다.
 * @returns {boolean} 안전한 http/https 주소이면 true입니다.
 */
function isSafeHttpUrl(url) {
  return typeof url === "string" && /^https?:\/\//i.test(url.trim());
}

/**
 * 현재 대화 배열에서 서버 다중 턴 문맥용 최근 `history` 배열(최대 12건)을 추출합니다.
 *
 * @param {Array<object>} messages 화면에 누적된 챗봇 메시지 목록입니다.
 * @returns {Array<{role:"user"|"assistant",content:string,district:string|null}>} API 전송용 대화 이력입니다.
 */
export function buildChatHistoryPayload(messages) {
  if (!Array.isArray(messages) || !messages.length) return [];
  const items = [];
  for (const msg of messages) {
    if (!msg || typeof msg !== "object") continue;
    const role = msg.role === "me" ? "user" : msg.role === "ai" ? "assistant" : null;
    const content = String(msg.text || msg.result?.answer || "").trim();
    if (!role || !content) continue;
    const district =
      role === "assistant" && msg.result?.district && msg.result.district !== "모름"
        ? msg.result.district
        : msg.district && msg.district !== "모름"
          ? msg.district
          : null;
    items.push({ role, content: content.slice(0, 2000), district });
  }
  return items.slice(-12);
}

/**
 * 비로그인 시연 시민의 임시 대화 목록을 브라우저 `sessionStorage`에서 불러옵니다.
 *
 * @param {Storage|null} [storage] 테스트 주입용 Storage 객체입니다.
 * @returns {Array<object>} 복원된 메시지 배열입니다.
 */
export function loadAnonChatMessages(storage = globalThis.sessionStorage) {
  try {
    const raw = storage?.getItem(ANON_CHAT_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.slice(-24) : [];
  } catch {
    return [];
  }
}

/**
 * 비로그인 시연 시민의 임시 대화 목록을 브라우저 `sessionStorage`에 저장합니다.
 *
 * @param {Array<object>} messages 저장할 대화 항목 배열입니다.
 * @param {Storage|null} [storage] 테스트 주입용 Storage 객체입니다.
 * @returns {void}
 */
export function saveAnonChatMessages(messages, storage = globalThis.sessionStorage) {
  try {
    if (!Array.isArray(messages) || !messages.length) {
      storage?.removeItem(ANON_CHAT_STORAGE_KEY);
      return;
    }
    storage?.setItem(ANON_CHAT_STORAGE_KEY, JSON.stringify(messages.slice(-24)));
  } catch {
    /* 탭 저장소 제한 환경은 조용히 무시합니다. */
  }
}

/**
 * 비로그인 시연 시민의 임시 대화 기록을 지웁니다.
 *
 * @param {Storage|null} [storage] 테스트 주입용 Storage 객체입니다.
 * @returns {void}
 */
export function clearAnonChatMessages(storage = globalThis.sessionStorage) {
  try {
    storage?.removeItem(ANON_CHAT_STORAGE_KEY);
  } catch {
    /* 탭 저장소 제한 환경은 조용히 무시합니다. */
  }
}

/**
 * 챗봇 단일 또는 다중 턴 대화 내용을 민원 작성 화면(`#/citizen/write`) 임시 저장 형식으로 변환합니다.
 *
 * @param {string} sourceText 시민이 챗봇에 입력한 기준 문의 문장입니다.
 * @param {object|null} [chatResult=null] 서버가 반환한 `CitizenChatResponse` 객체입니다.
 * @param {string[]} [allUserTurns=[]] 같은 대화 세션에서 시민이 입력한 전체 발화 목록입니다.
 * @returns {{title:string,body:string,district:string,visibility:string}} 작성 폼 초깃값 객체입니다.
 */
export function buildCitizenDraftPayload(
  sourceText,
  chatResult = null,
  allUserTurns = [],
) {
  const clean = String(sourceText || "").trim();
  const turns = Array.isArray(allUserTurns)
    ? allUserTurns.map((item) => String(item || "").trim()).filter(Boolean)
    : [];
  const mergedBody =
    turns.length > 1
      ? turns.join("\n").slice(0, 2000)
      : (clean || turns[0] || "").slice(0, 2000);
  const titleSeed = turns.length > 1 ? turns[0] : clean || turns[0] || "";
  const validDistricts = new Set(["상당구", "서원구", "흥덕구", "청원구"]);
  const detected =
    chatResult?.district && validDistricts.has(chatResult.district)
      ? chatResult.district
      : "모름";
  return {
    title: titleSeed.slice(0, 120),
    body: mergedBody,
    district: detected,
    visibility: "private",
  };
}

/**
 * 서버의 `ChatSessionDetail` 응답을 화면 렌더링용 `chatMessages` 배열로 복원합니다.
 *
 * @param {object|null} detail `/api/v1/citizen/chat/sessions/{id}` 응답 객체입니다.
 * @returns {Array<object>} 말풍선 렌더링용 메시지 배열입니다.
 */
export function hydrateSessionMessages(detail) {
  const list = Array.isArray(detail?.messages) ? detail.messages : [];
  const out = [];
  let lastUserText = "";
  for (const item of list) {
    if (item.role === "user") {
      lastUserText = String(item.content || "");
      out.push({
        role: "me",
        text: lastUserText,
        district: item.district || null,
      });
    } else if (item.role === "assistant") {
      out.push({
        role: "ai",
        source: lastUserText,
        text: String(item.content || item.payload?.answer || ""),
        result: item.payload || null,
      });
    }
  }
  return out;
}

/**
 * 로그인 민원인의 저장된 챗봇 세션 목록을 조회합니다.
 *
 * @param {object} [options] 테스트 주입용 `fetchFn` 설정입니다.
 * @param {typeof fetch=} options.fetchFn HTTP 요청 함수입니다.
 * @returns {Promise<{sessions:Array<object>,persisted:boolean}>} 세션 목록 응답입니다.
 */
export async function fetchChatSessions({ fetchFn = fetch } = {}) {
  const res = await fetchFn("/api/v1/citizen/chat/sessions", {
    method: "GET",
    credentials: "same-origin",
  });
  const body = await res.json().catch(() => null);
  if (!res.ok || !body) {
    throw new Error(body?.message || "대화 목록을 불러오지 못했습니다.");
  }
  return {
    sessions: Array.isArray(body.sessions) ? body.sessions : [],
    persisted: Boolean(body.persisted),
  };
}

/**
 * 로그인 민원인의 단일 챗봇 대화 세션과 전체 발화 이력을 조회합니다.
 *
 * @param {string} sessionId 조회할 챗봇 세션 ID입니다.
 * @param {object} [options] 테스트 주입용 `fetchFn` 설정입니다.
 * @param {typeof fetch=} options.fetchFn HTTP 요청 함수입니다.
 * @returns {Promise<object>} `ChatSessionDetail` 객체입니다.
 */
export async function fetchChatSessionDetail(sessionId, { fetchFn = fetch } = {}) {
  const res = await fetchFn(
    `/api/v1/citizen/chat/sessions/${encodeURIComponent(sessionId)}`,
    {
      method: "GET",
      credentials: "same-origin",
    },
  );
  const body = await res.json().catch(() => null);
  if (!res.ok || !body) {
    throw new Error(body?.message || "저장된 대화를 불러오지 못했습니다.");
  }
  return body;
}

/**
 * 로그인 민원인의 저장된 챗봇 대화 세션을 삭제합니다.
 *
 * @param {string} sessionId 삭제할 챗봇 세션 ID입니다.
 * @param {object} [options] 테스트 주입용 `fetchFn` 설정입니다.
 * @param {typeof fetch=} options.fetchFn HTTP 요청 함수입니다.
 * @returns {Promise<void>} 삭제 완료 프로미스입니다.
 */
export async function deleteChatSession(sessionId, { fetchFn = fetch } = {}) {
  const res = await fetchFn(
    `/api/v1/citizen/chat/sessions/${encodeURIComponent(sessionId)}`,
    {
      method: "DELETE",
      credentials: "same-origin",
    },
  );
  if (!res.ok && res.status !== 204) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.message || "대화를 삭제하지 못했습니다.");
  }
}

/**
 * 시민 민원 도우미 스트림 API(`/api/v1/citizen/chat/stream`)를 호출해
 * 진행 단계와 최종 시민 안전 응답을 받아옵니다.
 *
 * 스트림 경로가 지원되지 않거나 시작 전 연결이 끊기면 `/api/v1/citizen/chat`으로
 * 안전하게 대체 호출합니다.
 *
 * @param {{message:string,district?:string|null,provider?:string|null,sessionId?:string|null,history?:Array<object>}} payload 요청 본문입니다.
 * @param {object} [options] 진행 콜백과 테스트 주입용 `fetch` 함수입니다.
 * @param {((step:{key:string,label:string}) => void)=} options.onProgress 진행 단계 수신 콜백입니다.
 * @param {typeof fetch=} options.fetchFn HTTP 요청 함수입니다.
 * @returns {Promise<object>} 서버가 투영한 `CitizenChatResponse` 객체입니다.
 */
export async function streamCitizenChat(
  payload,
  { onProgress, fetchFn = fetch } = {},
) {
  let sawProgress = false;
  let finalResult = null;
  try {
    const response = await fetchFn("/api/v1/citizen/chat/stream", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok || !response.body) {
      const value = await response.json().catch(() => null);
      const err = new Error(value?.message || "민원 도우미 응답을 받지 못했습니다.");
      if (response.status !== 404 && response.status !== 405 && value?.message) {
        err.noFallback = true;
      }
      throw err;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    const consume = (chunk) => {
      buffer += chunk;
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (!line.trim()) continue;
        const evt = JSON.parse(line);
        if (evt.type === "progress") {
          sawProgress = true;
          onProgress?.({
            key: String(evt.key || "review"),
            label: String(evt.label || "내용을 확인하고 있어요"),
          });
        } else if (evt.type === "done" && evt.result) {
          finalResult = evt.result;
        } else if (evt.type === "error") {
          const err = new Error(evt.message || "민원 도우미 처리 중 오류가 발생했습니다.");
          err.noFallback = true;
          throw err;
        }
      }
    };

    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        consume(decoder.decode());
        if (buffer.trim()) consume("\n");
        break;
      }
      consume(decoder.decode(value, { stream: true }));
    }
    if (finalResult) return finalResult;
  } catch (error) {
    if (error && typeof error === "object" && (error.noFallback || sawProgress)) {
      throw error;
    }
  }

  const fallbackRes = await fetchFn("/api/v1/citizen/chat", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const fallbackBody = await fallbackRes.json().catch(() => null);
  if (!fallbackRes.ok || !fallbackBody) {
    throw new Error(fallbackBody?.message || "민원 도우미 응답을 받지 못했습니다.");
  }
  return fallbackBody;
}

/**
 * 챗봇 상단의 저장 세션 전환 바 또는 비로그인 안내 배너를 렌더링합니다.
 *
 * @param {object} options 세션 바 표시 상태입니다.
 * @param {object|null} [options.actor=null] 현재 세션 사용자 객체입니다.
 * @param {Array<object>} [options.sessions=[]] 저장된 세션 요약 배열입니다.
 * @param {string|null} [options.activeSessionId=null] 현재 활성 세션 ID입니다.
 * @param {boolean} [options.persisted=false] DB 저장이 활성화된 로그인 민원인인지 여부입니다.
 * @param {boolean} [options.loading=false] 세션 목록을 불러오는 중인지 여부입니다.
 * @param {boolean} [options.pending=false] AI 응답 대기 중인지 여부입니다.
 * @returns {string} 렌더링된 세션 바 HTML입니다.
 */
export function renderChatSessionBar({
  actor = null,
  sessions = [],
  activeSessionId = null,
  persisted = false,
  loading = false,
  pending = false,
} = {}) {
  const isLoggedInCitizen = Boolean(
    persisted || (actor && actor.role === "citizen" && !actor.demo && !actor.guest),
  );
  if (!isLoggedInCitizen) {
    return `<div class="chat-session-bar anon"><div class="chat-session-notice">${icon("shield", 14)}<span><b>로그인하면 대화가 저장됩니다</b> · 지금 대화는 이 탭을 닫으면 사라져요.</span></div><button type="button" class="btn subtle chat-login-cta" data-action="open-auth" data-tab="citizen-login">${icon("user", 13)} 로그인</button></div>`;
  }
  const pills = (Array.isArray(sessions) ? sessions : [])
    .slice(0, 8)
    .map((s) => {
      const isActive = s.id === activeSessionId;
      const countText = s.messageCount ? `${Math.max(1, Math.floor(s.messageCount / 2))}턴` : "";
      return `<div class="chat-session-pill ${isActive ? "active" : ""}"><button type="button" class="chat-session-pick" data-action="chat-select-session" data-id="${esc(s.id)}" ${pending ? "disabled" : ""} title="${esc(s.title)}"><span>${esc(s.title)}</span>${countText ? `<small>${esc(countText)}</small>` : ""}</button><button type="button" class="chat-session-del" data-action="chat-delete-session" data-id="${esc(s.id)}" data-title="${esc(s.title)}" aria-label="${esc(s.title)} 대화 삭제" title="대화 삭제" ${pending ? "disabled" : ""}>×</button></div>`;
    })
    .join("");
  return `<div class="chat-session-bar saved"><div class="chat-session-head"><span class="chat-saved-badge">${icon("check", 13)} 내 대화 자동 저장</span><button type="button" class="chat-new-btn" data-action="chat-reset" ${pending ? "disabled" : ""}>${icon("plus", 13)} 새 대화</button></div>${loading ? '<p class="chat-session-empty">저장된 대화를 불러오는 중…</p>' : pills ? `<div class="chat-session-rail" role="list" aria-label="저장된 내 대화 목록">${pills}</div>` : '<p class="chat-session-empty">질문을 보내면 대화가 계정에 안전하게 저장돼요.</p>'}</div>`;
}

/**
 * 시민 챗봇의 단일 대화 말풍선과 결과 카드를 HTML로 렌더링합니다.
 *
 * @param {object} message 대화 항목(`role`, `text`, `source`, `result`, `error`)입니다.
 * @param {object} [options] 다중 턴 드래프트 결합 옵션입니다.
 * @param {string[]} [options.allUserTurns=[]] 현재 세션에서 시민이 입력한 전체 발화 목록입니다.
 * @returns {string} 안전하게 이스케이프된 말풍선 HTML입니다.
 */
export function renderCitizenChatBubble(message, { allUserTurns = [] } = {}) {
  if (message.role === "me") {
    return `<div class="chat-bubble me">${esc(message.text)}</div>`;
  }
  const res = message.result || null;
  if (!res) {
    const draftPayload = buildCitizenDraftPayload(
      message.source || "",
      null,
      allUserTurns,
    );
    return `<div class="chat-bubble ai"><p>${esc(message.text)}</p><section class="citizen-ai-card tone-handoff"><header>${icon("spark", 15)} 민원 작성 안내 <span>직접 접수</span></header><dl><div><dt>입력 내용</dt><dd>${esc(draftPayload.body || "말씀하신 내용")}</dd></div><div><dt>안내</dt><dd>일시적으로 AI 응답을 받지 못했습니다. 민원을 직접 등록하시면 담당자가 검토합니다.</dd></div></dl><button class="btn primary" data-action="citizen-use-draft" data-text="${esc(draftPayload.body)}" data-district="${esc(draftPayload.district)}">이 내용으로 민원 작성 ${icon("arrow", 16)}</button></section></div>`;
  }

  const baseMeta = OUTCOME_CARD_META[res.outcome] || OUTCOME_CARD_META.human_handoff;
  const chipLabel =
    res.reasonCode === "out_of_scope" ? "청주시 관할 외" : baseMeta.chip;
  const draftPayload = buildCitizenDraftPayload(
    message.source || res.query || "",
    res,
    allUserTurns,
  );
  const provName = res.llmProvider
    ? PROVIDER_SHORT_LABELS[res.llmProvider] || res.llmProvider
    : "";

  const metaRows = [];
  if (res.effectiveQuery) {
    metaRows.push(
      `<div><dt>대화 문맥</dt><dd>이전 질문과 이어서 확인했어요</dd></div>`,
    );
  }
  if (res.district && res.district !== "모름") {
    const loc = res.inferredPlaceTitle
      ? `${res.district} · ${res.inferredPlaceTitle}`
      : res.district;
    metaRows.push(
      `<div><dt>감지 지역</dt><dd>${esc(loc)}${res.districtInferred ? " (자동 감지)" : ""}</dd></div>`,
    );
  }
  if (Array.isArray(res.faqSources) && res.faqSources.length) {
    const items = res.faqSources
      .map((src) => {
        const title = esc(src.title);
        return isSafeHttpUrl(src.sourceUrl)
          ? `<a href="${esc(src.sourceUrl)}" target="_blank" rel="noopener noreferrer">${title} ↗</a>`
          : `<span>${title}</span>`;
      })
      .join("<br>");
    metaRows.push(`<div><dt>공식 출처</dt><dd class="chat-faq-links">${items}</dd></div>`);
  }
  if (Array.isArray(res.departmentHints) && res.departmentHints.length) {
    const chips = res.departmentHints
      .map((dept) => `<span class="chat-dept-chip">${esc(dept)}</span>`)
      .join("");
    metaRows.push(
      `<div><dt>참고 부서</dt><dd><div class="chat-dept-chips">${chips}</div><small>유사 사례 참고 후보이며 공식 배정·자동 이관이 아닙니다.</small></dd></div>`,
    );
  }
  if (!metaRows.length) {
    metaRows.push(
      `<div><dt>다음 단계</dt><dd>${res.reasonCode === "out_of_scope" ? "관할 지자체 확인 또는 청주시 관련 위치 정보를 보완해 주세요." : "발생 위치와 요청 사항을 보완해 민원으로 등록해 주세요."}</dd></div>`,
    );
  }

  const answerHtml = esc(message.text || res.answer || "").replace(/\n/g, "<br>");
  const footerNote = provName ? `${provName} · ${res.demoNotice || ""}` : res.demoNotice || "";

  return `<div class="chat-bubble ai"><div class="chat-answer-text">${answerHtml}</div><section class="citizen-ai-card tone-${esc(baseMeta.tone)}"><header>${icon("spark", 15)} ${esc(baseMeta.title)} <span>${esc(chipLabel)}</span></header><dl>${metaRows.join("")}</dl>${footerNote ? `<p class="chat-card-note">${esc(footerNote)}</p>` : ""}<button class="btn ${esc(baseMeta.ctaClass)}" data-action="citizen-use-draft" data-text="${esc(draftPayload.body)}" data-district="${esc(draftPayload.district)}">${esc(baseMeta.cta)} ${icon("arrow", 16)}</button></section></div>`;
}
