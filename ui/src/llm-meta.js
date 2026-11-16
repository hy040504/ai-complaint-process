/**
 * 응대 검사기(`/#/lab`)와 담당자 콘솔이 함께 쓰는 LLM·판정·지역 표시 도우미입니다.
 */

const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (ch) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        ch
      ],
  );

export const LAB_STORAGE_KEY = "cheongju_lab_llm_provider";

export const PROVIDER_SHORT_LABELS = {
  "": ".env 기본",
  exaone_api: "엑사온 API",
  codex_cli: "Codex CLI",
  openai_api: "GPT API",
  legacy: "외부 LLM",
};

export const LLM_DISPLAY_META = {
  "": {
    subject: "선택한 LLM",
    shortName: "기본 설정",
    chip: "기본 LLM",
    dataNote:
      "아래 JSON은 검색 근거와 질의가 LLM 호출로 어떻게 구성됐는지 호출별로 보여 줍니다.",
    promptNote:
      "각 단계가 실제로 사용한 [시스템 지시]와 [사용자 입력] 전문입니다.",
    emptyPromptNote: "프롬프트를 만들지 못했습니다.",
  },
  exaone_api: {
    subject: "엑사온 API (K-EXAONE 2.5)",
    shortName: "엑사온 API",
    chip: "EXAONE API · K-EXAONE 2.5",
    dataNote:
      "아래 JSON은 검색 결과를 바탕으로 K-EXAONE 2.5 API에 전달한 호출별 입력 데이터입니다.",
    promptNote:
      "K-EXAONE 2.5 API 호출마다 전달한 [시스템 지시]와 [사용자 입력] 전문입니다.",
    emptyPromptNote: "엑사온 API에 전달한 프롬프트가 없습니다.",
  },
  codex_cli: {
    subject: "Codex CLI",
    shortName: "Codex CLI",
    chip: "Codex CLI",
    dataNote:
      "아래 JSON은 Codex CLI에 전달한 호출별 입력 데이터입니다. 먼저 데이터 구조를 확인한 뒤 아래 프롬프트 전문을 보세요.",
    promptNote:
      "Codex CLI 호출마다 실제로 넘긴 [시스템 지시]와 [사용자 입력] 전문입니다.",
    emptyPromptNote: "Codex CLI에 전달한 프롬프트가 없습니다.",
  },
  openai_api: {
    subject: "GPT API (GPT-6 Luna)",
    shortName: "GPT API",
    chip: "OpenAI GPT API · GPT-6 Luna",
    dataNote:
      "아래 JSON은 OpenAI 호환 GPT API에 전달한 호출별 입력 데이터입니다.",
    promptNote:
      "GPT API 호출마다 실제로 보낸 [시스템 지시]와 [사용자 입력] 전문입니다.",
    emptyPromptNote: "GPT API에 전달한 프롬프트가 없습니다.",
  },
  legacy: {
    subject: "외부 LLM",
    shortName: "외부 LLM",
    chip: "외부 호환 LLM",
    dataNote: "아래 JSON은 외부 호환 LLM API에 전달한 호출별 입력 데이터입니다.",
    promptNote:
      "외부 호환 LLM 호출마다 전달한 [시스템 지시]와 [사용자 입력] 전문입니다.",
    emptyPromptNote: "외부 LLM에 전달한 프롬프트가 없습니다.",
  },
};

export const LLM_ENGINE_CHOICES = [
  {
    value: "",
    badge: "DEFAULT",
    badgeClass: "badge-default",
    title: ".env 기본 설정",
    defaultDesc: "환경설정 기본 엔진 사용",
  },
  {
    value: "exaone_api",
    badge: "FREE API",
    badgeClass: "badge-exaone",
    title: "K-EXAONE 2.5",
    defaultDesc: "무료 API · LG AI EXAONE",
  },
  {
    value: "codex_cli",
    badge: "CODEX CLI",
    badgeClass: "badge-codex",
    title: "Codex CLI (gpt-6-luna)",
    defaultDesc: "로컬 Codex CLI 실행",
  },
  {
    value: "openai_api",
    badge: "GPT API",
    badgeClass: "badge-openai",
    title: "GPT-6 Luna API",
    defaultDesc: "OPENAI_API_KEY 필요",
  },
];

export const OUTCOME_NAMES = {
  faq_answer: "안내를 드렸습니다",
  department_suggestion: "담당 부서 후보로 넘겼습니다",
  human_handoff: "담당자가 이어서 살펴봅니다",
};

export const OUTCOME_SHORT_NAMES = {
  faq_answer: "FAQ 안내 가능",
  department_suggestion: "담당 부서 후보 안내",
  human_handoff: "담당자 직접 검토",
};

export const OUTCOME_TONE = {
  faq_answer: "answered",
  department_suggestion: "under_review",
  human_handoff: "submitted",
};

export const REASON_NAMES = {
  ok: "검색한 안내를 바탕으로 답했습니다.",
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
};

export const ROLE_PROMPT_NAMES = {
  decision: "1차 판정",
  faq_answer: "FAQ 안내 생성",
  department_suggestion: "부서 안내 생성",
  staff_draft: "담당자 초안 (PREFIX-03)",
  sanitize: "원문 순화 (PREFIX-04)",
};

/**
 * 실제 사용한 LLM 공급자·모델명으로 화면 표시 메타데이터를 만듭니다.
 *
 * @param {string|null|undefined} requestedProvider 사용자가 고른 공급자 ID입니다.
 * @param {object|null|undefined} assist `AssistResponse` 객체입니다.
 * @param {string|null} [defaultProvider=null] `.env` 기본 설정이 가리키는 공급자입니다.
 * @returns {{
 *   providerKey: string,
 *   subject: string,
 *   shortName: string,
 *   chipText: string,
 *   badgeText: string,
 *   dataTitle: string,
 *   promptTitle: string,
 *   copyAriaLabel: string,
 *   dataNote: string,
 *   promptNote: string,
 *   emptyPromptNote: string,
 * }} 화면 표시에 쓸 메타데이터 묶음입니다.
 */
export function resolveLlmMeta(
  requestedProvider,
  assist,
  defaultProvider = null,
) {
  const reqProv = String(requestedProvider || "").trim().toLowerCase();
  const actualProv = String(assist?.llmProvider || "").trim().toLowerCase();
  const resolvedDefault = String(defaultProvider || "").trim().toLowerCase();
  const providerKey = actualProv || reqProv || resolvedDefault || "";
  const base = LLM_DISPLAY_META[providerKey] || LLM_DISPLAY_META[""];
  const model = String(assist?.llmModel || "").trim();
  const chipText =
    providerKey === "codex_cli" && model
      ? `Codex CLI · ${model}`
      : base.chip;
  const fromEnvDefault = !reqProv && Boolean(providerKey);
  let badgeText = `LLM: ${base.shortName}`;
  if (model) badgeText += ` · ${model}`;
  if (fromEnvDefault) badgeText += " · .env 기본";

  return {
    providerKey,
    subject: base.subject,
    shortName: base.shortName,
    chipText,
    badgeText,
    dataTitle: `${base.subject}에 보낸 데이터`,
    promptTitle: `${base.subject}에 보낸 프롬프트`,
    copyAriaLabel: `${base.subject}에 보낸 데이터 JSON 복사`,
    dataNote: base.dataNote,
    promptNote: base.promptNote,
    emptyPromptNote: base.emptyPromptNote,
  };
}

/**
 * 네이버 지도 장소 추론 객체를 한 줄 안내 문자열로 변환합니다.
 *
 * @param {object|null|undefined} place `inferredPlace` 객체입니다.
 * @returns {string} 장소 문자열입니다. 제목이 없으면 빈 문자열입니다.
 */
export function formatPlaceText(place) {
  if (!place || !place.title) return "";
  const addr =
    place.roadAddress ||
    place.road_address ||
    place.jibunAddress ||
    place.jibun_address ||
    place.address ||
    "";
  return addr ? `${place.title} (${addr})` : String(place.title);
}

/**
 * 청주시 4대 구와 관할 읍·면·동 선택용 `<optgroup>` HTML을 만듭니다.
 *
 * @param {string} selected 현재 선택된 지역 문자열입니다.
 * @param {string[]} districts 4개 자치구 목록입니다.
 * @param {Object<string, string[]>} districtAreas 구별 관할 읍·면·동 목록입니다.
 * @returns {string} `<option>`/`<optgroup>` HTML 문자열입니다.
 */
export function buildDistrictOptionsHtml(
  selected,
  districts = [],
  districtAreas = {},
) {
  const guList = (districts || []).filter((d) => d && d !== "모름");
  const lines = ['<option value="">지정하지 않음 (본문 자동 감지·전체 검색)</option>'];
  if (guList.length) {
    lines.push(
      `<optgroup label="청주시 4개 자치구 (전체)">${guList
        .map(
          (gu) =>
            `<option value="${esc(gu)}"${selected === gu ? " selected" : ""}>${esc(gu)}</option>`,
        )
        .join("")}</optgroup>`,
    );
  }
  for (const gu of guList) {
    const areas = districtAreas?.[gu] || [];
    if (!areas.length) continue;
    lines.push(
      `<optgroup label="${esc(gu)} 관할 읍·면·동">${areas
        .map(
          (area) =>
            `<option value="${esc(area)}"${selected === area ? " selected" : ""}>${esc(area)} (${esc(gu)})</option>`,
        )
        .join("")}</optgroup>`,
    );
  }
  return lines.join("");
}

/**
 * 담당자 편집기에서 AI 실행 시 고를 수 있는 엔진 `<option>` 목록을 만듭니다.
 *
 * @param {Object<string, {available?:boolean, reason?:string, resolvedProvider?:string|null}>} providers
 *   `/api/v1/assist/fields`의 `providers` 맵입니다.
 * @param {string} [selected=""] 현재 선택된 공급자 ID입니다.
 * @returns {string} `<option>` HTML 문자열입니다.
 */
export function buildProviderOptionsHtml(providers = {}, selected = "") {
  return LLM_ENGINE_CHOICES.map((choice) => {
    const status = providers?.[choice.value];
    const available = status ? status.available !== false : true;
    let label = choice.value ? choice.title : ".env 기본 설정";
    if (!choice.value && status?.resolvedProvider) {
      const resolvedName =
        PROVIDER_SHORT_LABELS[status.resolvedProvider] || status.resolvedProvider;
      label = `.env 기본 (${resolvedName})`;
    }
    if (!available) label += " · 사용 불가";
    const isSelected = choice.value === (selected || "");
    return `<option value="${esc(choice.value)}"${isSelected ? " selected" : ""}${!available ? " disabled" : ""} title="${esc(status?.reason || choice.defaultDesc)}">${esc(label)}</option>`;
  }).join("");
}

/**
 * 담당자 부서 배정 모달용 `<optgroup>`/`<option>` HTML을 구·본청별로 생성합니다.
 *
 * @param {Array<{canonicalName?:string, district?:string|null}>} departments 청주시 현행 부서 목록입니다.
 * @param {string} [selected=""] 현재 선택된 부서 이름입니다.
 * @param {string} [filterText=""] 부서명 또는 구 이름 검색어입니다.
 * @returns {string} `<select>` 내부 HTML 문자열입니다.
 */
export function buildDepartmentOptionsHtml(
  departments = [],
  selected = "",
  filterText = "",
) {
  const needle = String(filterText || "").trim().toLowerCase();
  const list = (departments || []).filter((item) => {
    const name = String(item?.canonicalName || "").trim();
    if (!name) return false;
    if (!needle) return true;
    const gu = String(item?.district || "").toLowerCase();
    return name.toLowerCase().includes(needle) || gu.includes(needle);
  });
  if (!list.length) {
    return '<option value="" disabled>일치하는 부서가 없습니다</option>';
  }
  const order = ["청주시 본청 · 사업소", "상당구", "서원구", "흥덕구", "청원구"];
  const groups = new Map(order.map((label) => [label, []]));
  for (const item of list) {
    const key =
      item.district && groups.has(item.district)
        ? item.district
        : "청주시 본청 · 사업소";
    groups.get(key).push(item.canonicalName);
  }
  const blocks = ['<option value="">배정할 부서를 선택해 주세요</option>'];
  for (const label of order) {
    const names = groups.get(label) || [];
    if (!names.length) continue;
    blocks.push(
      `<optgroup label="${esc(label)} (${names.length})">${names
        .map(
          (name) =>
            `<option value="${esc(name)}"${name === selected ? " selected" : ""}>${esc(name)}</option>`,
        )
        .join("")}</optgroup>`,
    );
  }
  return blocks.join("");
}
