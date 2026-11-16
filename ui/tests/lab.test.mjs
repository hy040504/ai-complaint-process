/** llm 브랜치 응대 검사기와 민원웹 LLM UI 보조 함수의 질의 합성과 화면 경계를 검증합니다. */
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  labPage,
  labQuery,
  labShell,
  resolveSelectableProvider,
  runLabAssist,
} from "../src/lab.js";
import {
  buildDepartmentOptionsHtml,
  buildDistrictOptionsHtml,
  buildProviderOptionsHtml,
  formatPlaceText,
  resolveLlmMeta,
} from "../src/llm-meta.js";
import { staffProcess, staffQueue, staffReviewInfo } from "../src/staff.js";
import {
  fillComplaintForm,
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

test("분야를 제외하고 제목·본문만 검색 질의로 합친다", () => {
  const query = labQuery({
    category: "청소",
    title: "대형폐기물",
    body: "배출 방법이 궁금합니다",
  });
  assert.equal(query, "대형폐기물\n\n배출 방법이 궁금합니다");
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

test("사용 불가 LLM 공급자를 고르면 .env 기본값('')으로 되돌린다", () => {
  const providers = {
    "": { available: true, resolvedProvider: "codex_cli" },
    exaone_api: { available: true },
    openai_api: { available: false, reason: ".env에 OPENAI_API_KEY가 없습니다." },
  };
  assert.equal(resolveSelectableProvider(providers, "exaone_api"), "exaone_api");
  assert.equal(resolveSelectableProvider(providers, "openai_api"), "");
  assert.equal(resolveSelectableProvider(providers, ""), "");
});

test("읍·면·동 선택 옵션과 담당자 LLM 옵션 HTML을 생성한다", () => {
  const districtHtml = buildDistrictOptionsHtml(
    "오송읍",
    ["상당구", "서원구", "흥덕구", "청원구", "모름"],
    { 흥덕구: ["오송읍", "복대1동"] },
  );
  assert.match(districtHtml, /<optgroup label="청주시 4개 자치구 \(전체\)">/);
  assert.match(districtHtml, /<option value="오송읍" selected>오송읍 \(흥덕구\)<\/option>/);

  const providerHtml = buildProviderOptionsHtml(
    {
      "": { available: true, resolvedProvider: "exaone_api" },
      exaone_api: { available: true },
      codex_cli: { available: true },
      openai_api: { available: false, reason: "API 키 없음" },
    },
    "codex_cli",
  );
  assert.match(providerHtml, /\.env 기본 \(엑사온 API\)/);
  assert.match(providerHtml, /<option value="codex_cli" selected/);
  assert.match(providerHtml, /<option value="openai_api" disabled/);
});

test("공급자별 LLM 메타데이터와 장소 문자열을 일관되게 조합한다", () => {
  const meta = resolveLlmMeta("", { llmProvider: "exaone_api", llmModel: "k-exaone_v2.5" });
  assert.equal(meta.dataTitle, "엑사온 API (K-EXAONE 2.5)에 보낸 데이터");
  assert.equal(meta.promptTitle, "엑사온 API (K-EXAONE 2.5)에 보낸 프롬프트");
  assert.match(meta.badgeText, /LLM: 엑사온 API · k-exaone_v2\.5 · \.env 기본/);

  assert.equal(
    formatPlaceText({ title: "오송읍 행정복지센터", roadAddress: "충북 청주시 흥덕구 오송읍 오송가락로 123" }),
    "오송읍 행정복지센터 (충북 청주시 흥덕구 오송읍 오송가락로 123)",
  );
  assert.equal(formatPlaceText(null), "");
});

test("담당자 검토 참고 카드가 실제 aiAssist 결과를 표시한다", () => {
  const html = staffReviewInfo({
    category: "도로·교통",
    district: "모름",
    job: { status: "succeeded", stage: "완료", provider: "exaone_api" },
    aiAssist: {
      outcome: "department_suggestion",
      reasonCode: "department_candidate",
      district: "흥덕구",
      inferredPlace: { title: "오송읍행정복지센터", roadAddress: "청주시 흥덕구 오송읍" },
      llmProvider: "exaone_api",
      llmModel: "k-exaone_v2.5",
      departments: [
        {
          canonicalName: "흥덕구 건설과",
          dutyStatus: "unverified",
          jurisdictionStatus: "inferred_from_name",
          selected: true,
          automaticTransfer: false,
        },
        {
          canonicalName: "재난안전실 재난대응과",
          dutyStatus: "unverified",
          jurisdictionStatus: "inferred_from_name",
          selected: false,
          automaticTransfer: false,
        },
      ],
      faq: [{ sourceId: "12", title: "가로등 고장 신고 안내" }],
      cases: [{ sourceId: "34", title: "오송읍 가로등 점검 요청", departmentCurrent: "흥덕구 건설과" }],
      sanitize: {
        sanitizedSummary: "가로등 점등 불량 점검 요청",
        humanProtectionReviewNeeded: false,
      },
      staffDraft: {
        summaryCard: {
          coreSummary: "오송읍 도로 가로등 미점등 신고",
          missingInfo: ["정확한 전주 번호"],
        },
      },
      policyFailures: [],
      codex: [],
    },
  });
  assert.match(html, /담당 부서 후보 안내/);
  assert.match(html, /AI 감지: 흥덕구/);
  assert.match(html, /오송읍행정복지센터 \(청주시 흥덕구 오송읍\)/);
  assert.match(html, /흥덕구 건설과<\/b> <span>· AI 추천 후보/);
  assert.match(html, /재난안전실 재난대응과<\/b> <span>· 유사 사례 참고/);
  assert.doesNotMatch(html, /업무분장:|inferred_from_name|자동 이관 아님/);
  assert.match(html, /가로등 고장 신고 안내/);
  assert.match(html, /오송읍 도로 가로등 미점등 신고/);
  assert.match(html, /가로등 점등 불량 점검 요청/);
  assert.match(html, /엑사온 API/);
});

test("응대 검사기 labPage는 부서 후보에 업무분장·관할·자동 이관 아님 표기를 유지한다", async () => {
  const prevFetch = globalThis.fetch;
  const mockResult = {
    outcome: "department_suggestion",
    reasonCode: "action_required",
    district: "흥덕구",
    districtInferred: true,
    llmProvider: "codex_cli",
    llmModel: "gpt-6-luna",
    answer: "담당 부서 후보를 안내합니다.",
    departments: [
      {
        canonicalName: "흥덕구 건설과",
        dutyStatus: "unverified",
        jurisdictionStatus: "inferred_from_name",
        selected: true,
        automaticTransfer: false,
      },
    ],
    faq: [],
    cases: [],
    codex: [],
  };
  const ndjson = `${JSON.stringify({ type: "done", result: mockResult })}\n`;
  globalThis.fetch = async () =>
    new Response(ndjson, {
      status: 200,
      headers: { "Content-Type": "application/x-ndjson" },
    });
  try {
    await runLabAssist({ query: "가로등 점멸 신고", district: "흥덕구", provider: "codex_cli" });
    const html = labPage();
    assert.match(html, /흥덕구 건설과/);
    assert.match(html, /업무분장: unverified, 관할: inferred_from_name · 자동 이관 아님/);
  } finally {
    globalThis.fetch = prevFetch;
  }
});

test("buildDepartmentOptionsHtml과 담당자 화면은 배정 부서·버튼을 구분해 표시한다", () => {
  const optionsHtml = buildDepartmentOptionsHtml(
    [
      { canonicalName: "건설교통국 대중교통과", district: null },
      { canonicalName: "흥덕구 건설과", district: "흥덕구" },
      { canonicalName: "서원구 행정지원과", district: "서원구" },
    ],
    "흥덕구 건설과",
    "건설",
  );
  assert.match(optionsHtml, /<optgroup label="청주시 본청 · 사업소 \(1\)">/);
  assert.match(optionsHtml, /<optgroup label="흥덕구 \(1\)">/);
  assert.match(optionsHtml, /<option value="흥덕구 건설과" selected>흥덕구 건설과<\/option>/);
  assert.doesNotMatch(optionsHtml, /서원구 행정지원과/);

  const row = {
    id: "DEMO-2026-DEPT1",
    title: "보행로 파손 신고",
    body: "보행로 보도블록이 깨졌습니다. 점검을 부탁드립니다.",
    category: "도로·교통",
    district: "흥덕구",
    status: "under_review",
    visibility: "private",
    date: "2026-11-16T00:00:00Z",
    assigned: true,
    department: "흥덕구 건설과",
    draft: "",
    draftVersion: 0,
    published: null,
    messages: [],
    job: { status: "queued" },
  };
  const procHtml = staffProcess(row);
  assert.match(procHtml, /담당·부서 지정/);
  assert.match(procHtml, /흥덕구 건설과 · 김담당/);

  const queueHtml = staffQueue({ complaints: [row] }, new URLSearchParams());
  assert.match(queueHtml, /<span class="staff-tag dept"[^>]*>흥덕구 건설과<\/span>/);
  assert.match(queueHtml, /data-action="open-assign-dept"[^>]*>부서 변경<\/button>/);
  assert.match(queueHtml, /data-action="assign"[^>]*>담당 해제<\/button>/);
});

test("fillComplaintForm은 저장된 실행 payload를 폼 입력란·글자 수·엔진 버튼에 복원한다", () => {
  const root = makeFakeRoot();
  const titleInput = { value: "" };
  const categorySelect = { value: "" };
  const districtSelect = { value: "청원구" };
  const bodyInput = { value: "" };
  const titleCount = { textContent: "0/120" };
  const bodyCount = { textContent: "0/2,000" };
  const elements = {
    "#title": titleInput,
    "#category": categorySelect,
    "#district": districtSelect,
    "#body": bodyInput,
    "#title-count": titleCount,
    "#body-count": bodyCount,
    "#provider": root.hiddenInput,
  };
  const fakeForm = {
    querySelector: (sel) => elements[sel] || null,
    querySelectorAll: (sel) => root.querySelectorAll(sel),
  };

  fillComplaintForm(
    fakeForm,
    {
      title: "오송읍 가로등 고장 신고",
      category: "도로·교통",
      district: "흥덕구:오송읍",
      body: "오송역 앞 횡단보도 가로등이 어제부터 켜지지 않습니다.",
      provider: "codex_cli",
    },
    fakeForm,
  );
  assert.equal(titleInput.value, "오송읍 가로등 고장 신고");
  assert.equal(categorySelect.value, "도로·교통");
  assert.equal(districtSelect.value, "흥덕구:오송읍");
  assert.equal(bodyInput.value, "오송역 앞 횡단보도 가로등이 어제부터 켜지지 않습니다.");
  assert.equal(titleCount.textContent, "13/120");
  assert.equal(bodyCount.textContent, "30/2,000");
  assert.equal(root.hiddenInput.value, "codex_cli");
  assert.equal(root.buttons[3].classList.contains("active"), true);
  assert.equal(root.buttons[0].classList.contains("active"), false);

  fillComplaintForm(
    fakeForm,
    {
      title: "쓰레기 배출 방법 문의",
      category: "청소",
      district: null,
      body: "대형폐기물 스티커 인터넷 신청 절차가 궁금합니다.",
      provider: null,
    },
    fakeForm,
  );
  assert.equal(districtSelect.value, "");
  assert.equal(root.hiddenInput.value, "");
  assert.equal(root.buttons[0].classList.contains("active"), true);
  assert.equal(root.buttons[3].classList.contains("active"), false);
  assert.equal(titleCount.textContent, "12/120");
  assert.equal(bodyCount.textContent, "27/2,000");
});
