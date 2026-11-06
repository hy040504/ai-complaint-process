/**
 * 시민 직접 작성 양식을 쓰는 RAG·LLM 응대 검사기입니다.
 */
import { citizenIdentity, escapeHTML as esc } from "./citizen.js";
import { icon } from "./icons.js";
import { themeButton } from "./theme.js";
import { api, categories, districts } from "./store.js";

const outcomeNames = {
  faq_answer: "안내를 드렸습니다",
  department_suggestion: "담당 부서 후보로 넘겼습니다",
  human_handoff: "담당자가 이어서 살펴봅니다",
};
const outcomeTone = {
  faq_answer: "answered",
  department_suggestion: "under_review",
  human_handoff: "submitted",
};
const processCopy = {
  faq_answer: {
    title: "저장된 안내로 바로 답했습니다",
    next: "이 안내는 시연 초안입니다. 공식 접수·이관이 아니며 조건이 맞는지 담당자 확인이 필요할 수 있습니다.",
  },
  department_suggestion: {
    title: "현장 조치가 필요해 담당 부서 후보를 표시했습니다",
    next: "자동으로 다른 부서에 넘기지 않았습니다. 담당자가 부서와 관할을 확인합니다.",
  },
  human_handoff: {
    title: "바로 안내하지 않고 담당자 검토로 넘겼습니다",
    next: "검색 근거는 남겨 두었고, 공식 접수·외부 이관은 하지 않았습니다.",
  },
};
const reasonCopy = {
  llm_unavailable:
    "언어 모델이 없거나 호출되지 않아 안내문을 만들지 못했습니다. 찾은 자료는 담당자가 검토합니다.",
  search_failed:
    "저장된 안내·사례를 불러오지 못했습니다. 담당자가 직접 확인합니다.",
  insufficient_evidence:
    "비슷한 안내가 충분하지 않아 바로 답하지 못했습니다.",
  out_of_scope:
    "이 화면의 안내·사례 범위에서 확정하기 어려워 담당자가 살펴봅니다.",
  action_required:
    "단속·수리처럼 현장 조치가 필요해 보여 부서 후보만 표시했습니다.",
  mixed_request:
    "안내와 조치가 섞여 있어 일부 안내만으로 끝내지 않았습니다.",
  department_unverified:
    "부서 업무분장·관할이 확인되지 않아 담당자가 검토합니다.",
  condition_unclear:
    "적용 조건이 분명하지 않아 담당자가 확인합니다.",
  faq_generation_failed:
    "안내문을 만드는 과정에서 검사를 통과하지 못했습니다.",
  invalid_model_output:
    "판정 결과를 코드에서 검증하지 못해 담당자가 확인합니다.",
  policy_rejected:
    "모델이 가리킨 근거가 검색 결과와 맞지 않아 담당자가 검토합니다.",
  ok: "검색한 안내를 바탕으로 답했습니다.",
};

/** @type {Array<{id:string,title:string,query:string,district:?string}>} */
export let labExamples = [];
/** @type {object|null} */
export let labResult = null;
/** @type {{key:string,label:string}|null} */
export let labLive = null;
export let labPending = false;
export let labError = "";

/**
 * 제목·분야·본문을 검색 질의로 합칩니다.
 *
 * @param {{title?:string,category?:string,body?:string}} values 작성 값입니다.
 * @returns {string} 1~2000자 질의입니다.
 */
export function labQuery(values) {
  const title = String(values.title || "").trim();
  const body = String(values.body || "").trim();
  const category = String(values.category || "").trim();
  const parts = [];
  if (category) parts.push(`분야: ${category}`);
  if (title) parts.push(title);
  if (body) parts.push(body);
  return parts.join("\n\n").slice(0, 2000);
}

/**
 * 응대 검사기만 여는 껍데기를 만듭니다. 시민·담당자 화면 링크는 두지 않습니다.
 *
 * @param {string} content 본문 HTML입니다.
 * @returns {string} 페이지 HTML입니다.
 */
export function labShell(content) {
  return `<div class="demo-bar citizen-demo-bar lab-demo-bar"><div><span class="demo-label">LAB</span><span>민원톡톡 <span class="demo-extra">· 응대 검사기 · RAG + LLM · 민원은 저장하지 않습니다</span></span></div></div><div class="citizen-shell citizen-reference lab-shell"><header class="citizen-header"><a class="citizen-identity" href="#/lab" aria-label="응대 검사기 홈">${citizenIdentity()}</a><div class="citizen-header-actions">${themeButton()}<button class="icon-btn" data-action="lab-help" aria-label="검사기 이용 안내">${icon("help", 18)}</button></div></header><main id="main" tabindex="-1">${content}</main><footer><span>민원톡톡 <b>찾은 자료를 확인한 뒤 안내합니다</b></span><span>llm 브랜치 · 민원 저장·공식 접수·외부 이관 없음</span></footer></div>`;
}

/**
 * 고정 예시 질문을 서버에서 불러옵니다.
 *
 * @returns {Promise<void>} 비동기 작업의 완료 결과입니다.
 */
export async function loadLabExamples() {
  if (labExamples.length) return;
  const value = await api("/assist/examples");
  labExamples = value.examples || [];
}

/**
 * 진행 안내 NDJSON을 읽어 화면에 반영합니다.
 *
 * @param {{query:string,district?:string,rerank?:boolean,limit?:number}} body 요청 본문입니다.
 * @param {(() => void)=} paint 진행 상태를 그릴 함수입니다.
 * @returns {Promise<void>} 비동기 작업의 완료 결과입니다.
 */
async function streamLabAssist(body, paint) {
  const response = await fetch("/api/v1/assist/stream", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok || !response.body) {
    const value = await response.json().catch(() => null);
    throw new Error(value?.message || "응대 진행 응답을 받지 못했습니다.");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (!line.trim()) continue;
      const event = JSON.parse(line);
      if (event.type === "progress") {
        labLive = { key: event.key, label: event.label };
        paint?.();
      } else if (event.type === "done") labResult = event.result;
      else if (event.type === "error") throw new Error(event.message);
    }
  }
}

/**
 * 응대를 실행하고 진행 안내를 화면에 반영합니다.
 *
 * @param {{query:string,district?:string,rerank?:boolean,limit?:number}} body 요청 본문입니다.
 * @param {(() => void)=} paint 대기 상태를 바로 그릴 함수입니다.
 * @returns {Promise<void>} 비동기 작업의 완료 결과입니다.
 */
export async function runLabAssist(body, paint) {
  labPending = true;
  labError = "";
  labResult = null;
  labLive = { key: "read", label: "민원 내용을 읽고 있어요" };
  paint?.();
  try {
    try {
      await streamLabAssist(body, paint);
    } catch {
      if (!labResult) {
        labResult = await api("/assist", { method: "POST", body });
      }
    }
    if (!labResult) throw new Error("응대 결과를 받지 못했습니다.");
  } catch (error) {
    labError = error.message;
    labResult = null;
  } finally {
    labPending = false;
    labLive = null;
  }
}

/**
 * 처리 사유와 다음 단계를 설명합니다.
 *
 * @param {object} result 응대 결과입니다.
 * @returns {{title:string,detail:string,next:string}} 화면에 쓸 설명입니다.
 */
function processNote(result) {
  const pack = processCopy[result.outcome] || processCopy.human_handoff;
  return {
    title: pack.title,
    detail:
      reasonCopy[result.reasonCode] ||
      reasonCopy.insufficient_evidence,
    next: pack.next,
  };
}

/**
 * 검사기 본문을 시민 작성 양식과 응답 영역으로 만듭니다.
 *
 * @param {object} [form] 입력 유지 값입니다.
 * @returns {string} HTML입니다.
 */
export function labPage(form = {}) {
  const title = form.title || "";
  const body = form.body || "";
  const district = form.district || "";
  const category = form.category || categories[0];
  const result = labResult;
  const step = labPending ? 1 : result ? 2 : 0;
  const note = result ? processNote(result) : null;
  const steps = ["민원 내용 작성", "자료 확인", "안내 확인"];
  return `<div class="page-content narrow"><div class="page-heading"><div><div class="eyebrow">ASSIST LAB</div><h1>작은 목소리도 소중히 듣겠습니다</h1><p>일상에서 느낀 불편이나 궁금한 점을 남겨 주세요. 저장된 안내와 사례를 찾아 바로 안내할 수 있는지 살펴봅니다.</p></div></div><div class="form-steps">${steps
    .map(
      (label, index) =>
        `<span class="${index === step ? "active" : ""}"><b>${index + 1}</b> ${label}</span>${index < 2 ? "<i></i>" : ""}`,
    )
    .join("")}</div><div class="info-banner">${icon("help", 20)}<span>이곳은 <b>시연 검사기</b>입니다. 실제 개인정보를 입력하지 마세요. 민원은 저장되지 않으며 청주시 공식 접수로 연결되지 않습니다.</span></div><section class="panel lab-examples-panel"><div class="section-title"><h2>시험용 예시</h2><span>내용을 채운 뒤 바로 실행합니다</span></div><div class="lab-examples">${labExamples
    .map(
      (item) =>
        `<button type="button" class="lab-example" data-action="lab-example" data-id="${esc(item.id)}"><b>${esc(item.title)}</b><span>${esc(item.query)}</span></button>`,
    )
    .join("")}</div></section><form id="assist-form" class="panel complaint-form"><div class="section-title"><h2>민원 내용</h2><span><em>*</em> 필수 입력 항목</span></div><label for="lab-title">제목 <em>*</em></label><input id="lab-title" name="title" required maxlength="120" placeholder="민원 내용을 한눈에 알 수 있도록 작성해 주세요." value="${esc(title)}"><div class="field-hint"><span>이름, 연락처 등 개인정보는 제목에 적지 마세요.</span><span id="lab-title-count">${title.length}/120</span></div><div class="form-grid"><div><label for="lab-category">민원 분야 <em>*</em></label><select id="lab-category" name="category" required>${categories
    .map(
      (name) =>
        `<option ${name === category ? "selected" : ""}>${name}</option>`,
    )
    .join(
      "",
    )}</select></div><div><label for="lab-district">발생 지역</label><select id="lab-district" name="district"><option value="">지정하지 않음</option>${districts
    .filter((name) => name !== "모름")
    .map(
      (name) =>
        `<option ${district === name ? "selected" : ""}>${name}</option>`,
    )
    .join(
      "",
    )}</select></div></div><label for="lab-body">상세 내용 <em>*</em></label><textarea id="lab-body" name="body" rows="9" required minlength="10" maxlength="2000" placeholder="어디에서, 언제, 어떤 일이 있었나요?&#10;구체적인 상황과 요청 사항을 작성해 주시면 검토에 도움이 됩니다.">${esc(body)}</textarea><div class="field-hint"><span>최소 10자 이상 작성해 주세요. 첨부파일은 후속 지원 예정입니다.</span><span id="lab-body-count">${body.length}/2,000</span></div><div class="form-footer">${buttonWait()}</div></form><div id="lab-result-panel">${livePanel()}${
    labError
      ? `<div class="panel empty"><h2>실행에 실패했습니다</h2><p>${esc(labError)}</p></div>`
      : ""
  }${
    result
      ? `<article class="panel answer-panel lab-reply"><div class="section-title"><h2>${icon("chat", 20)} 안내 결과</h2><span class="badge ${outcomeTone[result.outcome] || ""}">${esc(outcomeNames[result.outcome] || result.outcome)}</span></div><div class="prose">${esc(result.answer || "안내 문장이 없습니다.").replace(/\n/g, "<br>")}</div></article><section class="panel lab-process-note"><div class="section-title"><h2>${icon("shield", 18)} 이렇게 처리했습니다</h2></div><b>${esc(note.title)}</b><p>${esc(note.detail)}</p><p class="muted">${esc(note.next)}</p>${
        result.departments?.length
          ? `<ul class="lab-dept-list">${result.departments
              .map(
                (dept) =>
                  `<li>${esc(dept.canonicalName)} · ${esc(dept.dutyStatus)}${dept.selected ? " · 후보" : ""}</li>`,
              )
              .join("")}</ul>`
          : ""
      }</section><section class="panel"><div class="section-title"><h2>참고한 자료</h2><span>FAQ ${result.faq?.length || 0}건 · 사례 ${result.cases?.length || 0}건</span></div><ul class="lab-evidence">${[
        ...(result.faq || []).map((hit) => ({ ...hit, kind: "FAQ" })),
        ...(result.cases || []).map((hit) => ({ ...hit, kind: "사례" })),
      ]
        .map(
          (hit) =>
            `<li><span class="mini-chip">${esc(hit.kind)}</span><b>${esc(hit.title)}</b></li>`,
        )
        .join("") || "<li>표시할 자료가 없습니다.</li>"}</ul></section>`
      : labPending
        ? ""
        : `<div class="panel empty">${icon("spark", 32)}<h2>작성한 내용으로 안내를 확인합니다</h2><p>예시를 고르거나 민원 내용을 작성한 뒤 응대를 요청해 주세요.</p></div>`
  }</div></div>`;
}

/**
 * 진행 중 안내 카드를 만듭니다.
 *
 * @returns {string} HTML입니다.
 */
function livePanel() {
  if (!labLive) return "";
  return `<section class="panel lab-live" role="status"><span class="lab-live-dot"></span><div><b>${esc(labLive.label)}</b><p>작업 전체를 보여 주지 않고, 지금 하는 일만 짧게 표시합니다.</p></div></section>`;
}

/**
 * 실행 버튼 문구를 대기 상태에 맞춥니다.
 *
 * @returns {string} 버튼 HTML입니다.
 */
function buttonWait() {
  return `<button class="btn primary" type="submit" ${labPending ? "disabled" : ""}>${labPending ? "자료를 확인하고 있어요…" : `응대 요청하기 ${icon("arrow", 17)}`}</button>`;
}
