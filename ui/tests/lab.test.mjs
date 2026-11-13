/** llm 브랜치 응대 검사기의 질의 합성과 화면 경계를 검증합니다. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { labQuery, labShell } from "../src/lab.js";
import {
  initLlmSelector,
  resolveLlmSectionMeta,
  showResult,
  streamComplaint,
  updateLlmAvailability,
} from "../../src/lab_web/static/app.js";

/**
 * 테스트용 가짜 LLM 엔진 선택 버튼을 만듭니다.
 *
 * @param {string} provider 공급자 식별자입니다.
 * @param {boolean} [active=false] 초기 활성 상태입니다.
 * @returns {object} 클릭·속성 모의 버튼 객체입니다.
 */
function makeFakeButton(provider, active = false) {
  const classes = new Set(active ? ["llm-choice-btn", "active"] : ["llm-choice-btn"]);
  const attrs = { "aria-pressed": String(active) };
  const handlers = {};
  const badge = { className: "btn-badge badge-free", textContent: "무료 API", dataset: {} };
  const desc = { textContent: "원래 설명", dataset: {} };
  return {
    dataset: { provider },
    title: `${provider} 설명`,
    offsetWidth: 0,
    classList: {
      add: (...names) => names.forEach((n) => classes.add(n)),
      remove: (...names) => names.forEach((n) => classes.delete(n)),
      toggle: (name, force) => {
        const on = force === undefined ? !classes.has(name) : Boolean(force);
        if (on) classes.add(name);
        else classes.delete(name);
        return on;
      },
      contains: (name) => classes.has(name),
    },
    setAttribute: (k, v) => { attrs[k] = String(v); },
    getAttribute: (k) => attrs[k] ?? null,
    removeAttribute: (k) => { delete attrs[k]; },
    querySelector: (sel) => (sel === ".btn-badge" ? badge : sel === "small" ? desc : null),
    addEventListener: (type, fn) => { handlers[type] = fn; },
    click: () => handlers.click?.(),
  };
}

/**
 * 테스트용 가짜 LLM 선택 루트 컨테이너를 만듭니다.
 *
 * @returns {object} 버튼 목록과 hidden 입력을 포함한 모의 DOM 루트입니다.
 */
function makeFakeRoot() {
  const buttons = [
    makeFakeButton("", true),
    makeFakeButton("exaone_api"),
    makeFakeButton("openai_api"),
    makeFakeButton("codex_cli"),
  ];
  const hiddenInput = { value: "" };
  return {
    buttons,
    hiddenInput,
    querySelectorAll: (sel) => (sel === ".llm-choice-btn" ? buttons : []),
    querySelector: (sel) => (sel === "#provider" ? hiddenInput : null),
  };
}

test("제목·분야·본문을 검색 질의로 합친다", () => {
  const query = labQuery({
    category: "청소",
    title: "대형폐기물",
    body: "배출 방법이 궁금합니다",
  });
  assert.equal(query, "분야: 청소\n\n대형폐기물\n\n배출 방법이 궁금합니다");
});

test("검사기 껍데기에 시민·담당자 화면 링크가 없다", () => {
  const html = labShell("<p>본문</p>");
  assert.match(html, /href="#\/lab"/);
  assert.doesNotMatch(html, /href="#\/citizen"/);
  assert.doesNotMatch(html, /href="#\/staff"/);
});

test("검사기 LLM 버튼 잠금 시 aria-disabled·shake와 자동 복원 방지가 동작한다", () => {
  const storageMap = new Map([["cheongju_lab_llm_provider", "openai_api"]]);
  globalThis.localStorage = {
    getItem: (k) => storageMap.get(k) ?? null,
    setItem: (k, v) => storageMap.set(k, String(v)),
  };

  try {
    const root = makeFakeRoot();
    updateLlmAvailability(root, {
      exaone_api: { available: true, reason: "" },
      openai_api: { available: false, reason: "OPENAI_API_KEY가 비어 있습니다." },
      codex_cli: { available: false, reason: "Codex CLI가 없습니다." },
    });

    const openaiBtn = root.buttons[2];
    assert.equal(openaiBtn.getAttribute("aria-disabled"), "true");
    assert.equal(openaiBtn.classList.contains("is-disabled"), true);

    // localStorage에 잠긴 openai_api가 남아 있어도 잠기지 않은 기본 단추를 선택해야 합니다.
    initLlmSelector(root);
    assert.equal(root.hiddenInput.value, "");
    assert.equal(openaiBtn.classList.contains("active"), false);

    // 잠긴 단추를 누르면 선택되지 않고 shake 효과만 켜집니다.
    openaiBtn.click();
    assert.equal(openaiBtn.classList.contains("shake"), true);
    assert.equal(root.hiddenInput.value, "");

    // 열린 단추(exaone_api)를 누르면 정상 선택됩니다.
    root.buttons[1].click();
    assert.equal(root.hiddenInput.value, "exaone_api");
    assert.equal(root.buttons[1].getAttribute("aria-pressed"), "true");
  } finally {
    delete globalThis.localStorage;
  }
});

test("updateLlmAvailability는 기본 선택 버튼에 해석된 .env 기본 엔진을 표시하고 복원한다", () => {
  const root = makeFakeRoot();
  const defaultDesc = root.buttons[0].querySelector("small");

  updateLlmAvailability(root, {
    "": { available: true, reason: "", resolvedProvider: "exaone_api" },
  });
  assert.equal(defaultDesc?.textContent, ".env 기본: 엑사온 API");

  // resolvedProvider가 없으면 원래 설명 문구로 되돌려야 합니다.
  updateLlmAvailability(root, {
    "": { available: true, reason: "" },
  });
  assert.equal(defaultDesc?.textContent, "원래 설명");

  // 기본 버튼이 잠겼다가 다시 열려도 새 resolvedProvider가 반영되어야 합니다.
  updateLlmAvailability(root, {
    "": { available: false, reason: "사용 불가", resolvedProvider: "openai_api" },
  });
  assert.equal(root.buttons[0].getAttribute("aria-disabled"), "true");
  updateLlmAvailability(root, {
    "": { available: true, reason: "", resolvedProvider: "openai_api" },
  });
  assert.equal(defaultDesc?.textContent, ".env 기본: GPT API");
});

/**
 * NDJSON 청크 배열을 스트리밍하는 모의 fetch 응답을 만듭니다.
 *
 * @param {string[]} chunks 순차 전달할 문자열 청크 배열입니다.
 * @param {{ok?:boolean,status?:number}} [options] 응답 상태 옵션입니다.
 * @returns {object} `getReader()`를 제공하는 모의 Response 객체입니다.
 */
function fakeNdjsonResponse(chunks, { ok = true, status = 200 } = {}) {
  const encoder = new TextEncoder();
  let idx = 0;
  return {
    ok,
    status,
    body: {
      getReader() {
        return {
          async read() {
            if (idx >= chunks.length) return { value: undefined, done: true };
            return { value: encoder.encode(chunks[idx++]), done: false };
          },
        };
      },
    },
    async json() {
      return null;
    },
  };
}

test("streamComplaint는 개행 없는 마지막 NDJSON done 줄을 유실하지 않는다", async () => {
  const originalFetch = globalThis.fetch;
  const seen = [];
  globalThis.fetch = async () =>
    fakeNdjsonResponse([
      '{"type":"progress","key":"read","label":"민원 읽는 중"}\n',
      '{"type":"done","result":{"ok":true,"provider":"exaone_api"}}',
    ]);
  try {
    const result = await streamComplaint({ title: "제목", body: "본문입니다" }, (k, l) =>
      seen.push([k, l]),
    );
    assert.deepEqual(seen, [["read", "민원 읽는 중"]]);
    assert.deepEqual(result, { ok: true, provider: "exaone_api" });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("streamComplaint는 422 검증 오류와 error 이벤트에서 재시도 금지를 표시한다", async () => {
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () => ({
      ok: false,
      status: 422,
      body: null,
      async json() {
        return { message: "제목은 1자 이상이어야 합니다." };
      },
    });
    await assert.rejects(
      () => streamComplaint({}),
      (err) => err.noFallback === true && err.status === 422 && /제목/.test(err.message),
    );

    globalThis.fetch = async () =>
      fakeNdjsonResponse(['{"type":"error","message":"중단됨"}\n']);
    await assert.rejects(
      () => streamComplaint({}),
      (err) => err.noFallback === true && err.message === "중단됨",
    );

    globalThis.fetch = async () => ({
      ok: false,
      status: 404,
      body: null,
      async json() {
        return null;
      },
    });
    await assert.rejects(
      () => streamComplaint({}),
      (err) => err.noFallback === undefined && err.status === 404,
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

/**
 * 결과 화면 DOM 테스트를 위한 최소 모의 노드를 만듭니다.
 *
 * @param {string} [tagName="div"] 요소 태그 이름입니다.
 * @returns {object} 텍스트·속성·자식 노드 조작을 지원하는 모의 요소입니다.
 */
function makeFakeNode(tagName = "div") {
  const attrs = {};
  const node = {
    tagName,
    textContent: "",
    className: "",
    hidden: false,
    dataset: {},
    children: [],
    get childElementCount() {
      return this.children.length;
    },
    replaceChildren(...items) {
      this.children = items;
    },
    append(...items) {
      this.children.push(...items);
    },
    setAttribute(k, v) {
      attrs[k] = String(v);
    },
    getAttribute(k) {
      return attrs[k] ?? null;
    },
  };
  return node;
}

test("resolveLlmSectionMeta는 사용한 LLM에 따라 데이터·프롬프트 제목과 칩을 구분한다", () => {
  const exaone = resolveLlmSectionMeta(
    { provider: "exaone_api" },
    { assist: { llmProvider: "exaone_api", llmModel: "k-exaone_v2.5" } },
  );
  assert.equal(exaone.dataTitle, "엑사온 API (K-EXAONE 2.5)에 보낸 데이터");
  assert.equal(exaone.promptTitle, "엑사온 API (K-EXAONE 2.5)에 보낸 프롬프트");
  assert.equal(exaone.chipText, "EXAONE API · K-EXAONE 2.5");
  assert.match(exaone.badgeText, /엑사온 API/);

  const codex = resolveLlmSectionMeta(
    { provider: "codex_cli" },
    { assist: { llmProvider: "codex_cli", llmModel: "gpt-6-luna" } },
  );
  assert.equal(codex.dataTitle, "Codex CLI에 보낸 데이터");
  assert.equal(codex.promptTitle, "Codex CLI에 보낸 프롬프트");
  assert.match(codex.chipText, /Codex CLI/);

  const gpt = resolveLlmSectionMeta(
    { provider: "openai_api" },
    { assist: { llmProvider: "openai_api", llmModel: "gpt-6-luna" } },
  );
  assert.equal(gpt.dataTitle, "GPT API (GPT-6 Luna)에 보낸 데이터");
  assert.equal(gpt.promptTitle, "GPT API (GPT-6 Luna)에 보낸 프롬프트");
  assert.match(gpt.chipText, /GPT API/);

  // 사용자가 기본 설정(.env)을 고른 경우에도 실제 해석된 공급자를 표시합니다.
  const envDefault = resolveLlmSectionMeta(
    { provider: null },
    { assist: { llmProvider: "exaone_api", llmModel: "k-exaone_v2.5" } },
  );
  assert.equal(envDefault.dataTitle, "엑사온 API (K-EXAONE 2.5)에 보낸 데이터");
  assert.equal(envDefault.promptTitle, "엑사온 API (K-EXAONE 2.5)에 보낸 프롬프트");
  assert.match(envDefault.badgeText, /\.env 기본/);
});

test("showResult는 데이터 JSON·프롬프트 제목, 배지, 호출 카드를 사용한 LLM에 맞게 채운다", () => {
  const originalDocument = globalThis.document;
  const nodes = Object.fromEntries(
    [
      "#result-source",
      "#result-district",
      "#result-place",
      "#result-llm",
      "#result-message",
      "#result-outcome",
      "#result-reason",
      "#result-failures",
      "#result-answer",
      "#result-draft",
      "#result-sanitize",
      "#result-hits",
      "#codex-data-title",
      "#codex-data-engine",
      "#codex-json-copy",
      "#codex-note",
      "#codex-json",
      "#codex-prompt-title",
      "#codex-prompt-engine",
      "#codex-prompt-note",
      "#codex-prompts",
      "#sent-json",
      "#received-json",
    ].map((id) => [id, makeFakeNode()]),
  );
  const root = { querySelector: (sel) => nodes[sel] || null };
  globalThis.document = {
    createElement: (tag) => makeFakeNode(tag),
  };

  try {
    showResult(
      { title: "테스트 민원", provider: null },
      {
        message: "완료",
        complaint: { provider: null },
        assist: {
          llmProvider: "openai_api",
          llmModel: "gpt-6-luna",
          outcome: "human_handoff",
          reasonCode: "out_of_scope",
          policyFailures: [],
          answer: "안내",
          faq: [],
          cases: [],
          codex: [
            {
              role: "decision",
              system: "PREFIX-00 + PREFIX-01",
              sent: true,
              user: { query: "테스트" },
              prompt: "[시스템 지시]\nPREFIX\n\n[사용자 입력]\n{}",
            },
          ],
        },
      },
      "",
      root,
    );

    assert.equal(nodes["#codex-data-title"].textContent, "GPT API (GPT-6 Luna)에 보낸 데이터");
    assert.equal(
      nodes["#codex-prompt-title"].textContent,
      "GPT API (GPT-6 Luna)에 보낸 프롬프트",
    );
    assert.equal(nodes["#codex-data-engine"].className, "engine-chip engine-chip--openai_api");
    assert.equal(nodes["#codex-prompt-engine"].textContent, "OpenAI GPT API · GPT-6 Luna");
    assert.equal(
      nodes["#codex-json-copy"].getAttribute("aria-label"),
      "GPT API (GPT-6 Luna)에 보낸 데이터 JSON 복사",
    );
    assert.match(nodes["#result-llm"].textContent, /GPT API.*\.env 기본/);
    assert.equal(nodes["#codex-prompts"].children.length, 1);
    const callHeading = nodes["#codex-prompts"].children[0].children[0].children[0].textContent;
    assert.match(callHeading, /1차 판정 · GPT API · PREFIX-00 \+ PREFIX-01 · 보냄/);
  } finally {
    if (originalDocument === undefined) delete globalThis.document;
    else globalThis.document = originalDocument;
  }
});
