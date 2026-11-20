/**
 * 시민 민원 도우미(`#/citizen/assistant`)의 실시간 RAG + LLM 챗봇 클라이언트와
 * 시민 전용 안전 결과 카드 렌더러입니다.
 *
 * 서버의 `/api/v1/citizen/chat/stream`·`/api/v1/citizen/chat`만 호출하며,
 * 미게시 담당자 초안·직원 보호 순화·내부 프롬프트는 다루지 않습니다.
 */

import { escapeHTML as esc } from "./citizen.js";
import { icon } from "./icons.js";
import { PROVIDER_SHORT_LABELS } from "./llm-meta.js";

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
 * 챗봇 대화 내용을 민원 작성 화면(`#/citizen/write`) 임시 저장 형식으로 변환합니다.
 *
 * @param {string} sourceText 시민이 챗봇에 입력한 원래 문의 문장입니다.
 * @param {object|null} [chatResult=null] 서버가 반환한 `CitizenChatResponse` 객체입니다.
 * @returns {{title:string,body:string,district:string,visibility:string}} 작성 폼 초깃값 객체입니다.
 */
export function buildCitizenDraftPayload(sourceText, chatResult = null) {
  const clean = String(sourceText || "").trim();
  const validDistricts = new Set(["상당구", "서원구", "흥덕구", "청원구"]);
  const detected =
    chatResult?.district && validDistricts.has(chatResult.district)
      ? chatResult.district
      : "모름";
  return {
    title: clean.slice(0, 120),
    body: clean.slice(0, 2000),
    district: detected,
    visibility: "private",
  };
}

/**
 * 시민 민원 도우미 스트림 API(`/api/v1/citizen/chat/stream`)를 호출해
 * 진행 단계와 최종 시민 안전 응답을 받아옵니다.
 *
 * 스트림 경로가 지원되지 않거나 시작 전 연결이 끊기면 `/api/v1/citizen/chat`으로
 * 안전하게 대체 호출합니다.
 *
 * @param {{message:string,district?:string|null,provider?:string|null}} payload 요청 본문입니다.
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
 * 시민 챗봇의 단일 대화 말풍선과 결과 카드를 HTML로 렌더링합니다.
 *
 * @param {object} message 대화 항목(`role`, `text`, `source`, `result`, `error`)입니다.
 * @returns {string} 안전하게 이스케이프된 말풍선 HTML입니다.
 */
export function renderCitizenChatBubble(message) {
  if (message.role === "me") {
    return `<div class="chat-bubble me">${esc(message.text)}</div>`;
  }
  const res = message.result || null;
  if (!res) {
    const draftPayload = buildCitizenDraftPayload(message.source || "", null);
    return `<div class="chat-bubble ai"><p>${esc(message.text)}</p><section class="citizen-ai-card tone-handoff"><header>${icon("spark", 15)} 민원 작성 안내 <span>직접 접수</span></header><dl><div><dt>입력 내용</dt><dd>${esc(draftPayload.body || "말씀하신 내용")}</dd></div><div><dt>안내</dt><dd>일시적으로 AI 응답을 받지 못했습니다. 민원을 직접 등록하시면 담당자가 검토합니다.</dd></div></dl><button class="btn primary" data-action="citizen-use-draft" data-text="${esc(draftPayload.body)}" data-district="${esc(draftPayload.district)}">이 내용으로 민원 작성 ${icon("arrow", 16)}</button></section></div>`;
  }

  const baseMeta = OUTCOME_CARD_META[res.outcome] || OUTCOME_CARD_META.human_handoff;
  const chipLabel =
    res.reasonCode === "out_of_scope" ? "청주시 관할 외" : baseMeta.chip;
  const draftPayload = buildCitizenDraftPayload(message.source || res.query || "", res);
  const provName = res.llmProvider
    ? PROVIDER_SHORT_LABELS[res.llmProvider] || res.llmProvider
    : "";

  const metaRows = [];
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
