/** 시민 민원 도우미 실시간 스트림 클라이언트와 안전 카드 렌더러를 검증합니다. */
import assert from "node:assert/strict";
import test from "node:test";

import {
  ANON_CHAT_STORAGE_KEY,
  buildChatHistoryPayload,
  buildCitizenDraftPayload,
  hydrateSessionMessages,
  loadAnonChatMessages,
  renderChatSessionBar,
  renderCitizenChatBubble,
  saveAnonChatMessages,
  streamCitizenChat,
} from "../src/chatbot.js";

/**
 * NDJSON 청크 배열을 ReadableStream 응답으로 감쌉니다.
 *
 * @param {string[]} chunks 순서대로 흘려보낼 문자열 조각입니다.
 * @returns {object} `fetch`와 호환되는 가짜 Response 객체입니다.
 */
function makeNdjsonResponse(chunks) {
  const encoder = new TextEncoder();
  let idx = 0;
  return {
    ok: true,
    status: 200,
    body: {
      getReader() {
        return {
          async read() {
            if (idx >= chunks.length) return { done: true, value: undefined };
            return { done: false, value: encoder.encode(chunks[idx++]) };
          },
        };
      },
    },
  };
}

test("streamCitizenChat은 분할 청크와 개행 없는 마지막 done 줄을 빠짐없이 처리한다", async () => {
  const steps = [];
  const fakeFetch = async (url) => {
    assert.equal(url, "/api/v1/citizen/chat/stream");
    return makeNdjsonResponse([
      '{"type":"progress","key":"read","label":"민원 내용을 ',
      '읽고 있어요"}\n{"type":"progress","key":"search","label":"자료를 찾고 있어요"}\n',
      '{"type":"done","result":{"outcome":"faq_answer","answer":"대형폐기물 신고필증을 부착하세요.","district":"흥덕구","automaticTransfer":false}}',
    ]);
  };
  const result = await streamCitizenChat(
    { message: "대형폐기물 방법", district: null },
    {
      onProgress: (step) => steps.push(step),
      fetchFn: fakeFetch,
    },
  );
  assert.deepEqual(steps, [
    { key: "read", label: "민원 내용을 읽고 있어요" },
    { key: "search", label: "자료를 찾고 있어요" },
  ]);
  assert.equal(result.outcome, "faq_answer");
  assert.equal(result.automaticTransfer, false);
});

test("streamCitizenChat은 스트림 404 시 /api/v1/citizen/chat으로 대체 호출한다", async () => {
  const urls = [];
  const fakeFetch = async (url) => {
    urls.push(url);
    if (url.endsWith("/stream")) {
      return { ok: false, status: 404, async json() { return null; } };
    }
    return {
      ok: true,
      status: 200,
      async json() {
        return {
          outcome: "human_handoff",
          reasonCode: "out_of_scope",
          answer: "청주시 관할 외 안내입니다.",
          district: "모름",
          automaticTransfer: false,
        };
      },
    };
  };
  const res = await streamCitizenChat(
    { message: "천안시 도로 파손" },
    { fetchFn: fakeFetch },
  );
  assert.deepEqual(urls, ["/api/v1/citizen/chat/stream", "/api/v1/citizen/chat"]);
  assert.equal(res.reasonCode, "out_of_scope");
});

test("renderCitizenChatBubble과 buildCitizenDraftPayload는 구 자동 채움·출처 링크 안전성을 지킨다", () => {
  const draft = buildCitizenDraftPayload("서원대 후문 가로등 꺼짐", {
    district: "서원구",
  });
  assert.equal(draft.district, "서원구");
  assert.equal(draft.visibility, "private");

  const fallbackDraft = buildCitizenDraftPayload("기타 문의", {
    district: "없는구",
  });
  assert.equal(fallbackDraft.district, "모름");

  // FAQ 카드: 안전한 https 링크만 <a>로 열고 javascript: 링크는 차단합니다.
  const faqHtml = renderCitizenChatBubble({
    role: "ai",
    source: "대형폐기물 배출",
    text: "신고필증을 부착하세요.",
    result: {
      query: "대형폐기물 배출",
      outcome: "faq_answer",
      reasonCode: "ok",
      answer: "신고필증을 부착하세요.",
      district: "모름",
      faqSources: [
        {
          title: "대형폐기물 안내",
          sourceUrl: "https://toktalk.cheongju.go.kr/faq/1",
        },
        {
          title: "위험 링크 <script>",
          sourceUrl: "javascript:alert(1)",
        },
      ],
      departmentHints: [],
      llmProvider: "exaone_api",
      demoNotice: "시연 안내입니다.",
    },
  });
  assert.match(faqHtml, /tone-faq/);
  assert.match(faqHtml, /https:\/\/toktalk\.cheongju\.go\.kr\/faq\/1/);
  assert.doesNotMatch(faqHtml, /javascript:/);
  assert.doesNotMatch(faqHtml, /<script>/);

  // 현장 조치 카드: 감지 구와 참고 부서 칩, data-district 전달 확인
  const actionHtml = renderCitizenChatBubble({
    role: "ai",
    source: "서원대 후문 가로등 고장",
    text: "현장 조치가 필요합니다.",
    result: {
      query: "서원대 후문 가로등 고장",
      outcome: "department_suggestion",
      reasonCode: "department_candidate",
      answer: "현장 조치가 필요합니다.",
      district: "서원구",
      districtInferred: true,
      inferredPlaceTitle: "서원대학교",
      faqSources: [],
      departmentHints: ["서원구 건설과"],
      demoNotice: "공식 이관이 아닙니다.",
    },
  });
  assert.match(actionHtml, /tone-action/);
  assert.match(actionHtml, /서원구 · 서원대학교/);
  assert.match(actionHtml, /서원구 건설과/);
  assert.match(actionHtml, /data-district="서원구"/);
});

test("다중 턴 이력 변환·드래프트 병합·세션 바 및 비로그인 임시 저장이 안전하게 동작한다", () => {
  const turns = [
    { role: "me", text: "흥덕구 대형폐기물 배출 방법 알려주세요", district: "흥덕구" },
    {
      role: "ai",
      text: "신고필증을 부착해 주세요.",
      result: { district: "흥덕구", answer: "신고필증을 부착해 주세요." },
    },
    { role: "me", text: "그럼 수수료는 얼마인가요?", district: null },
  ];
  const history = buildChatHistoryPayload(turns);
  assert.equal(history.length, 3);
  assert.deepEqual(
    history.map((h) => h.role),
    ["user", "assistant", "user"],
  );
  assert.equal(history[1].district, "흥덕구");

  const multiDraft = buildCitizenDraftPayload(
    "그럼 수수료는 얼마인가요?",
    { district: "흥덕구" },
    ["흥덕구 대형폐기물 배출 방법 알려주세요", "그럼 수수료는 얼마인가요?"],
  );
  assert.equal(multiDraft.title, "흥덕구 대형폐기물 배출 방법 알려주세요");
  assert.match(multiDraft.body, /대형폐기물/);
  assert.match(multiDraft.body, /수수료/);
  assert.equal(multiDraft.district, "흥덕구");

  const hydrated = hydrateSessionMessages({
    messages: [
      { role: "user", content: "질문 1", district: "서원구" },
      {
        role: "assistant",
        content: "응답 1",
        payload: { outcome: "faq_answer", answer: "응답 1", district: "서원구" },
      },
    ],
  });
  assert.equal(hydrated.length, 2);
  assert.equal(hydrated[0].role, "me");
  assert.equal(hydrated[1].result.outcome, "faq_answer");

  const anonBar = renderChatSessionBar({ actor: { role: "citizen", demo: true } });
  assert.match(anonBar, /로그인하면 대화가 저장됩니다/);

  const savedBar = renderChatSessionBar({
    actor: { role: "citizen", demo: false },
    persisted: true,
    activeSessionId: "CHAT-2026-AAA",
    sessions: [
      { id: "CHAT-2026-AAA", title: "대형폐기물 문의", messageCount: 4 },
    ],
  });
  assert.match(savedBar, /내 대화 자동 저장/);
  assert.match(savedBar, /대형폐기물 문의/);
  assert.match(savedBar, /2턴/);

  const mem = new Map();
  const fakeStorage = {
    getItem: (k) => (mem.has(k) ? mem.get(k) : null),
    setItem: (k, v) => mem.set(k, v),
    removeItem: (k) => mem.delete(k),
  };
  saveAnonChatMessages(turns, fakeStorage);
  assert.ok(mem.has(ANON_CHAT_STORAGE_KEY));
  assert.equal(loadAnonChatMessages(fakeStorage).length, 3);
});
