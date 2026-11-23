/**
 * 시민 직접 작성 양식을 쓰는 RAG·LLM 응대 검사기입니다.
 */
import { citizenIdentity, escapeHTML as esc } from "./citizen.js";
import { icon } from "./icons.js";
import { siteHeaders } from "./site.js";
import { themeButton } from "./theme.js";
import { api, categories, districts } from "./store.js";
import {
  LAB_STORAGE_KEY,
  LLM_ENGINE_CHOICES,
  OUTCOME_NAMES,
  OUTCOME_TONE,
  PROVIDER_SHORT_LABELS,
  REASON_NAMES,
  ROLE_PROMPT_NAMES,
  buildDistrictOptionsHtml,
  formatPlaceText,
  resolveLlmMeta,
} from "./llm-meta.js";

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

/** @type {Array<{id:string,title:string,query:string,district:?string}>} */
export let labExamples = [];
/** @type {{categories:string[],districts:string[],districtAreas:Object<string,string[]>,providers:Object<string,object>}} */
export let labFields = {
  categories: [...categories],
  districts: districts.filter((d) => d !== "모름"),
  districtAreas: {},
  providers: {},
};
/** @type {string} */
export let selectedLabProvider = "";
/** @type {string|null} */
export let requestedLabProvider = null;
/** @type {object|null} */
export let labResult = null;
/** @type {{key:string,label:string}|null} */
export let labLive = null;
export let labPending = false;
export let labError = "";

/**
 * 저장된 선택과 서버 가용 상태를 기준으로 유효한 LLM 선택값을 고릅니다.
 *
 * @param {Object<string, {available?:boolean}>} providers 서버가 준 공급자 가용 맵입니다.
 * @param {string} [candidate=""] 우선 확인할 선택값입니다.
 * @returns {string} 선택 가능한 공급자 ID 또는 `""`입니다.
 */
export function resolveSelectableProvider(providers = {}, candidate = "") {
  const isOpen = (id) => providers?.[id]?.available !== false;
  if (isOpen(candidate)) return candidate;
  if (isOpen("")) return "";
  const firstOpen = Object.keys(providers || {}).find((id) => isOpen(id));
  return firstOpen ?? "";
}

/**
 * 검사기에서 선택된 LLM 공급자 값을 변경하고 브라우저 저장소에 기억합니다.
 *
 * @param {string} provider 선택할 공급자 ID(`""`는 `.env` 기본 설정)입니다.
 * @returns {void}
 */
export function setSelectedLabProvider(provider) {
  selectedLabProvider = resolveSelectableProvider(
    labFields.providers,
    String(provider || ""),
  );
  try {
    if (typeof localStorage !== "undefined") {
      localStorage.setItem(LAB_STORAGE_KEY, selectedLabProvider);
    }
  } catch {
    /* 브라우저 저장소 접근이 제한된 환경은 무시합니다. */
  }
}

/**
 * 제목과 본문을 검색 질의로 합칩니다. 민원 분야(`category`)는 검색 질의에 넣지 않습니다.
 *
 * @param {{title?:string,category?:string,body?:string}} values 작성 값입니다.
 * @returns {string} 1~2000자 질의입니다.
 */
export function labQuery(values) {
  const title = String(values.title || "").trim();
  const body = String(values.body || "").trim();
  const parts = [];
  if (title) parts.push(title);
  if (body) parts.push(body);
  return parts.join("\n\n").slice(0, 2000);
}

/**
 * 응대 검사기만 여는 껍데기를 만듭니다. 단독 페이지(`/lab/`)용이라 시민·담당자 화면 링크는 두지 않습니다.
 *
 * @param {string} content 본문 HTML입니다.
 * @returns {string} 페이지 HTML입니다.
 */
export function labShell(content) {
  return `<div class="demo-bar citizen-demo-bar lab-demo-bar"><div><span class="demo-label">LAB</span><span>청주톡톡 <span class="demo-extra">· 응대 검사기 · RAG + LLM · 민원은 저장하지 않습니다</span></span></div></div><div class="citizen-shell citizen-reference lab-shell"><header class="citizen-header"><a class="citizen-identity" href="#/lab" aria-label="응대 검사기 홈">${citizenIdentity()}</a><div class="citizen-header-actions"><span class="lab-header-pill">RAG + LLM 검증</span>${themeButton()}<button class="icon-btn" data-action="lab-help" aria-label="검사기 이용 안내">${icon("help", 18)}</button></div></header><main id="main" tabindex="-1">${content}</main><footer><span>청주톡톡 <b>찾은 자료를 확인한 뒤 안내합니다</b></span><span>llm 브랜치 · 민원 저장·공식 접수·외부 이관 없음</span></footer></div>`;
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
 * 허용 분야·세부 관할 지역·LLM 공급자 가용 상태를 서버에서 불러옵니다.
 *
 * @returns {Promise<void>} 비동기 작업의 완료 결과입니다.
 */
export async function loadLabFields() {
  const value = await api("/assist/fields");
  labFields = {
    categories: value.categories || [...categories],
    districts: value.districts || districts.filter((d) => d !== "모름"),
    districtAreas: value.districtAreas || {},
    providers: value.providers || {},
  };
  let saved = selectedLabProvider;
  if (!saved) {
    try {
      saved =
        typeof localStorage !== "undefined"
          ? localStorage.getItem(LAB_STORAGE_KEY) || ""
          : "";
    } catch {
      saved = "";
    }
  }
  selectedLabProvider = resolveSelectableProvider(labFields.providers, saved);
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
    headers: siteHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  if (!response.ok || !response.body) {
    const value = await response.json().catch(() => null);
    const error = new Error(value?.message || "응대 진행 응답을 받지 못했습니다.");
    if (response.status !== 404 && response.status !== 405 && value?.message) {
      error.noFallback = true;
    }
    throw error;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let sawProgress = false;
  const consumeLines = (chunkText) => {
    buffer += chunkText;
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (!line.trim()) continue;
      const event = JSON.parse(line);
      if (event.type === "progress") {
        sawProgress = true;
        labLive = { key: event.key, label: event.label };
        paint?.();
      } else if (event.type === "done") labResult = event.result;
      else if (event.type === "error") {
        const error = new Error(
          event.message || "응대 처리 중 오류가 발생했습니다.",
        );
        error.noFallback = true;
        throw error;
      }
    }
  };
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        consumeLines(decoder.decode());
        if (buffer.trim()) consumeLines("\n");
        break;
      }
      consumeLines(decoder.decode(value, { stream: true }));
    }
  } catch (error) {
    if (error && typeof error === "object" && sawProgress) {
      error.noFallback = true;
    }
    throw error;
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
  requestedLabProvider = body?.provider ?? (selectedLabProvider || null);
  labLive = { key: "read", label: "민원 내용을 읽고 있어요" };
  paint?.();
  const payload = { rerank: false, limit: 5, ...body };
  try {
    try {
      await streamLabAssist(payload, paint);
    } catch (error) {
      if (error && typeof error === "object" && error.noFallback) throw error;
      if (!labResult) {
        labResult = await api("/assist", { method: "POST", body: payload });
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
      REASON_NAMES[result.reasonCode] ||
      REASON_NAMES.insufficient_evidence,
    next: pack.next,
  };
}

/**
 * 검사기 상단의 LLM 엔진 선택 버튼 그룹 HTML을 만듭니다.
 *
 * @param {string} active 선택된 공급자 ID입니다.
 * @returns {string} 버튼 묶음 HTML입니다.
 */
function renderLlmChoices(active) {
  return `<div class="lab-llm-field"><div class="lab-llm-head"><span class="lab-llm-label">응대 LLM 엔진</span><small>사용 가능 여부는 서버 환경 설정(.env)을 따릅니다.</small></div><div class="lab-llm-grid" role="group" aria-label="LLM 엔진 선택">${LLM_ENGINE_CHOICES.map(
    (choice) => {
      const status = labFields.providers?.[choice.value];
      const available = status ? status.available !== false : true;
      const isActive = available && active === choice.value;
      let desc = choice.defaultDesc;
      if (!available) {
        desc = status?.reason || "환경 설정이 필요합니다.";
      } else if (!choice.value && status?.resolvedProvider) {
        const resolved =
          PROVIDER_SHORT_LABELS[status.resolvedProvider] ||
          status.resolvedProvider;
        desc = `.env 기본: ${resolved}`;
      }
      const badgeCls = available ? choice.badgeClass : "badge-disabled";
      const badgeText = available ? choice.badge : "KEY 없음";
      return `<button type="button" class="llm-choice-btn${isActive ? " active" : ""}${available ? "" : " is-disabled"}" data-action="lab-provider" data-provider="${esc(choice.value)}" aria-pressed="${isActive ? "true" : "false"}" ${available ? "" : `aria-disabled="true" title="${esc(desc)}"`}><span class="btn-badge ${badgeCls}">${esc(badgeText)}</span><strong>${esc(choice.title)}</strong><small>${esc(desc)}</small></button>`;
    },
  ).join("")}</div><input type="hidden" id="lab-provider" name="provider" value="${esc(active)}"></div>`;
}

/**
 * LLM에 전달한 호출별 프롬프트 카드 목록 HTML을 만듭니다.
 *
 * @param {Array<object>} calls `result.codex` 목록입니다.
 * @param {ReturnType<typeof resolveLlmMeta>} llmMeta LLM 표시 메타입니다.
 * @returns {string} 프롬프트 카드 HTML입니다.
 */
function renderPromptCards(calls, llmMeta) {
  const items = (calls || []).filter(
    (call) => typeof call?.prompt === "string" && call.prompt,
  );
  if (!items.length) {
    return `<p class="hint-block">${esc(llmMeta.emptyPromptNote)}</p>`;
  }
  const enginePart =
    llmMeta.shortName && llmMeta.shortName !== "기본 설정"
      ? ` · ${llmMeta.shortName}`
      : "";
  return items
    .map((call, index) => {
      const roleName = ROLE_PROMPT_NAMES[call.role] || call.role || "호출";
      const sentLabel = call.sent ? "보냄" : "보내지 않음";
      return `<div class="json-block prompt-block"><div class="json-head"><h4>${index + 1}. ${esc(roleName)}${esc(enginePart)} · ${esc(call.system || "")} · ${sentLabel}</h4><button type="button" class="json-copy" data-action="lab-copy-prompt" data-index="${index}">프롬프트 복사</button></div><pre>${esc(call.prompt)}</pre></div>`;
    })
    .join("");
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
  const fieldCategories = labFields.categories?.length
    ? labFields.categories
    : categories;
  const fieldDistricts = labFields.districts?.length
    ? labFields.districts
    : districts;
  const category = form.category || fieldCategories[0];
  const provider =
    form.provider !== undefined
      ? resolveSelectableProvider(labFields.providers, form.provider)
      : selectedLabProvider;
  const result = labResult;
  const step = labPending ? 1 : result ? 2 : 0;
  const note = result ? processNote(result) : null;
  const steps = ["민원 내용 작성", "자료 확인", "안내 확인"];
  const defaultResolved =
    labFields.providers?.[""]?.resolvedProvider || null;
  const llmMeta = result
    ? resolveLlmMeta(requestedLabProvider, result, defaultResolved)
    : null;
  const placeText = result ? formatPlaceText(result.inferredPlace) : "";
  return `<div class="page-content narrow"><section class="lab-hero"><div><span class="lab-hero-eyebrow">청주시 AI 응대 검사기 · ASSIST LAB</span><h1>작은 불편도, 궁금한 일도<br><em>응대 흐름을 미리 확인</em>해 보세요.</h1><p>제목과 본문으로 저장된 안내와 사례를 먼저 찾고, AI 판정과 부서 후보·프롬프트 전문을 한눈에 점검합니다.</p></div><span class="citizen-welcome-symbol" aria-hidden="true">${icon("chat", 42)}<i>AI</i></span></section><div class="form-steps">${steps
    .map(
      (label, index) =>
        `<span class="${index === step ? "active" : ""}"><b>${index + 1}</b> ${label}</span>${index < 2 ? "<i></i>" : ""}`,
    )
    .join("")}</div><div class="info-banner">${icon("help", 20)}<span>이곳은 <b>시연 검사기</b>입니다. 실제 개인정보를 입력하지 마세요. 민원은 저장되지 않으며 청주시 공식 접수로 연결되지 않습니다.</span></div><section class="panel lab-examples-panel"><div class="section-title"><h2>시험용 예시</h2><span>내용을 채운 뒤 바로 실행합니다</span></div><div class="lab-examples">${labExamples
    .map(
      (item) =>
        `<button type="button" class="lab-example" data-action="lab-example" data-id="${esc(item.id)}"><span class="lab-example-head"><b>${esc(item.title)}</b>${item.district ? `<em class="lab-example-tag">${esc(item.district)}</em>` : ""}</span><span>${esc(item.query)}</span></button>`,
    )
    .join("")}</div></section><form id="assist-form" class="panel complaint-form"><div class="section-title"><h2>민원 내용</h2><span><em>*</em> 필수 입력 항목</span></div>${renderLlmChoices(provider)}<label for="lab-title">제목 <em>*</em></label><input id="lab-title" name="title" required maxlength="120" placeholder="민원 내용을 한눈에 알 수 있도록 작성해 주세요." value="${esc(title)}"><div class="field-hint"><span>이름, 연락처 등 개인정보는 제목에 적지 마세요.</span><span id="lab-title-count">${title.length}/120</span></div><div class="form-grid"><div><label for="lab-category">민원 분야 <em>*</em></label><select id="lab-category" name="category" required>${fieldCategories
    .map(
      (name) =>
        `<option ${name === category ? "selected" : ""}>${name}</option>`,
    )
    .join("")}</select></div><div><label for="lab-district">발생 지역</label><select id="lab-district" name="district">${buildDistrictOptionsHtml(district, fieldDistricts, labFields.districtAreas)}</select></div></div><label for="lab-body">상세 내용 <em>*</em></label><textarea id="lab-body" name="body" rows="9" required minlength="10" maxlength="2000" placeholder="어디에서, 언제, 어떤 일이 있었나요?&#10;구체적인 상황과 요청 사항을 작성해 주시면 검토에 도움이 됩니다.">${esc(body)}</textarea><div class="field-hint"><span>최소 10자 이상 작성해 주세요. 민원 분야는 검색 질의에 섞지 않고 제목·본문으로 검색합니다.</span><span id="lab-body-count">${body.length}/2,000</span></div><div class="form-footer">${buttonWait()}</div></form><div id="lab-result-panel">${livePanel()}${
    labError
      ? `<div class="panel empty"><h2>실행에 실패했습니다</h2><p>${esc(labError)}</p></div>`
      : ""
  }${
    result
      ? `<article class="panel answer-panel lab-reply"><div class="section-title"><h2>${icon("chat", 20)} 안내 결과</h2><span class="badge ${OUTCOME_TONE[result.outcome] || ""}">${esc(OUTCOME_NAMES[result.outcome] || result.outcome)}</span></div><div class="lab-result-badges"><span class="lab-meta-badge badge-district" id="lab-result-district">${
          result.district
            ? `📍 발생 지역: ${esc(result.district)}${result.districtInferred ? " (본문 지명 자동 감지)" : ""}`
            : "📍 발생 지역: 지정 없음 (전체 지역 검색)"
        }</span>${
          placeText
            ? `<span class="lab-meta-badge badge-place" id="lab-result-place">🗺️ 장소 추적: ${esc(placeText)}</span>`
            : ""
        }<span class="lab-meta-badge badge-llm" id="lab-result-llm" data-provider="${esc(llmMeta?.providerKey || "")}">${esc(llmMeta?.badgeText || "")}</span></div><div class="lab-answer-box prose">${esc(result.answer || "안내 문장이 없습니다.").replace(/\n/g, "<br>")}</div>${
          result.policyFailures?.length
            ? `<p class="lab-policy-warn">정책 검사: ${esc(result.policyFailures.join(" "))}</p>`
            : ""
        }</article><section class="panel lab-process-note"><div class="section-title"><h2>${icon("shield", 18)} 이렇게 처리했습니다</h2></div><b>${esc(note.title)}</b><p>${esc(note.detail)}</p><p class="muted">${esc(note.next)}</p>${
          result.departments?.length
            ? `<ul class="lab-dept-list">${result.departments
                .map(
                  (dept) =>
                    `<li><b>${esc(dept.canonicalName || "")}</b> (업무분장: ${esc(dept.dutyStatus || "unverified")}, 관할: ${esc(dept.jurisdictionStatus || "unverified")} · 자동 이관 아님)${dept.selected ? " · 후보" : ""}</li>`,
                )
                .join("")}</ul>`
            : ""
        }</section><section class="panel lab-aux-grid"><div class="lab-aux-card"><div class="lab-aux-head"><h3>담당자 초안 (미게시)</h3><span class="mini-chip">PREFIX-03</span></div><p class="prose">${esc(result.staffDraft?.draftAnswer || "이번 민원에는 담당자 초안을 만들지 않았습니다.")}</p></div><div class="lab-aux-card"><div class="lab-aux-head"><h3>순화 요약 (담당자 참고)</h3><span class="mini-chip">PREFIX-04</span></div><p class="prose">${esc(result.sanitize?.sanitizedSummary || "거친 표현 힌트가 없어 순화 호출을 건너뛰었습니다.")}</p></div></section><section class="panel"><div class="section-title"><h2>참고한 자료</h2><span>FAQ ${result.faq?.length || 0}건 · 사례 ${result.cases?.length || 0}건</span></div><ul class="lab-evidence">${[
          ...(result.faq || []).map((hit) => ({ ...hit, kind: "FAQ" })),
          ...(result.cases || []).map((hit) => ({ ...hit, kind: "사례" })),
        ]
          .map(
            (hit) =>
              `<li><span class="mini-chip">${esc(hit.kind)}</span><b>${esc(hit.title || hit.sourceId || "")}</b></li>`,
          )
          .join("") || "<li>표시할 자료가 없습니다.</li>"}</ul></section><section class="panel lab-trace-panel"><div class="json-block" id="lab-llm-data-block"><div class="json-head"><div class="json-title-group"><h3>${esc(llmMeta?.dataTitle || "")}</h3><span class="engine-chip${llmMeta?.providerKey ? ` engine-chip--${esc(llmMeta.providerKey)}` : ""}">${esc(llmMeta?.chipText || "")}</span></div><button type="button" class="json-copy" data-action="lab-copy-data" aria-label="${esc(llmMeta?.copyAriaLabel || "JSON 복사")}">JSON 복사</button></div><p class="muted">${esc(llmMeta?.dataNote || "")}</p><pre id="lab-codex-json">${esc(JSON.stringify(result.codex || [], null, 2))}</pre></div><div class="json-block" id="lab-llm-prompt-block"><div class="json-head"><div class="json-title-group"><h3>${esc(llmMeta?.promptTitle || "")}</h3><span class="engine-chip${llmMeta?.providerKey ? ` engine-chip--${esc(llmMeta.providerKey)}` : ""}">${esc(llmMeta?.chipText || "")}</span></div></div><p class="muted">${esc(llmMeta?.promptNote || "")}</p><div id="lab-codex-prompts">${renderPromptCards(result.codex || [], llmMeta)}</div></div></section>`
      : labPending
        ? ""
        : `<div class="panel empty">${icon("spark", 32)}<h2>작성한 내용으로 안내를 확인합니다</h2><p>엔진과 예시를 고르거나 민원 내용을 작성한 뒤 응대를 요청해 주세요.</p></div>`
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
