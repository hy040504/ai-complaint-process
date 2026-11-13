/** llm 브랜치 응대 검사기의 질의 합성과 화면 경계를 검증합니다. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { labQuery, labShell } from "../src/lab.js";
import {
  initLlmSelector,
  streamComplaint,
  updateLlmAvailability,
} from "../../src/lab_web/static/app.js";

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
