/**
 * 응대 검사기 작성 화면입니다. 민원 필드를 JSON으로 서버에 보냅니다.
 * 보낸 결과는 `.rag-cache/lab-runs` 파일에 남기고 업무 DB에는 쓰지 않습니다.
 */

const outcomeNames = {
  faq_answer: "안내를 드렸습니다",
  department_suggestion: "담당 부서 후보로 넘겼습니다",
  human_handoff: "담당자가 이어서 살펴봅니다",
};

const reasonNames = {
  ok: "검색 근거로 안내합니다",
  insufficient_evidence: "검색 근거만으로 안내를 확정하기 어렵습니다",
  condition_unclear: "FAQ에 질문이 요구하는 항목이 부족합니다",
  out_of_scope: "현재 FAQ·사례 범위에서 확정하기 어렵습니다",
  action_required: "현장 조치가 필요한 요청입니다",
  mixed_request: "안내와 조치가 섞여 있습니다",
  department_unverified: "부서 업무분장·관할이 확인되지 않았습니다",
  invalid_model_output: "판정 JSON을 코드에서 검증하지 못했습니다",
  policy_rejected: "모델이 가리킨 근거가 검색 결과와 맞지 않습니다",
  llm_unavailable: "언어 모델을 호출하지 못했습니다",
  search_failed: "검색에 실패했습니다",
  faq_generation_failed: "FAQ 안내문 생성을 통과하지 못했습니다",
};

/**
 * 기록 시각을 짧게 표시합니다.
 *
 * @param {string} iso ISO 시각입니다.
 * @returns {string} 월·일·시각 문구입니다.
 */
export function formatRunTime(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

/** 마지막으로 고른 LLM 엔진을 남기는 `localStorage` 키입니다. */
const LLM_STORAGE_KEY = "cheongju_lab_llm_provider";

/** 결과 화면의 `🤖 LLM 엔진` 배지 문구입니다. 빈 키는 `.env` 기본 설정입니다. */
const PROVIDER_LABELS = {
  "": "기본 설정 (.env)",
  exaone_api: "엑사온 API (K-EXAONE 2.5)",
  codex_cli: "Codex CLI (GPT-6 Luna)",
  openai_api: "GPT API (GPT-6 Luna)",
  legacy: "기타 호환 LLM API",
};

/** `/api/v1/lab/fields`의 `""` 기본 설정이 실제로 가리키는 공급자입니다. */
let defaultResolvedProvider = "";

/**
 * 결과 화면의 LLM 데이터·프롬프트 영역에 쓸 엔진별 문구·배지 정보입니다.
 * 엑사온 API·Codex CLI·GPT API를 한눈에 구별해 보여 줍니다.
 */
const LLM_DISPLAY_META = {
  exaone_api: {
    defaultModel: "k-exaone_v2.5",
    subject: "엑사온 API (K-EXAONE 2.5)",
    shortName: "엑사온 API",
    chip: "EXAONE API · K-EXAONE 2.5",
    dataNote:
      "엑사온 API(K-EXAONE 2.5)로 보낸 단계별 사용자 JSON입니다. 1차 판정은 PREFIX-00+01, FAQ 안내는 PREFIX-00+02, 담당자 초안은 PREFIX-00+03, 순화는 PREFIX-00+04가 이어집니다.",
    promptNote:
      "엑사온 API(Chat Completions) 호출 시 system·user 메시지로 전달하는 전체 프롬프트(PREFIX + 사용자 JSON)를 호출마다 그대로 보여 줍니다.",
    emptyPromptNote:
      "이 기록에는 엑사온 API(K-EXAONE 2.5) 프롬프트 전문이 없습니다. 새로 민원을 보내면 호출마다 표시됩니다.",
  },
  codex_cli: {
    defaultModel: "gpt-6-luna",
    subject: "Codex CLI",
    shortName: "Codex CLI",
    chip: "Codex CLI · GPT-6 Luna (MCP)",
    dataNote:
      "Codex CLI로 보낸 단계별 사용자 JSON입니다. 1차 판정은 PREFIX-00+01, FAQ 안내는 PREFIX-00+02, 담당자 초안은 PREFIX-00+03, 순화는 PREFIX-00+04가 이어집니다.",
    promptNote:
      "`codex exec -` 표준 입력(stdin) 전문입니다. 실행 래퍼, PREFIX 본문, 사용자 JSON을 호출마다 그대로 보여 줍니다.",
    emptyPromptNote:
      "이 기록에는 Codex CLI 표준 입력 전문이 없습니다. 새로 민원을 보내면 호출마다 표시됩니다.",
  },
  openai_api: {
    defaultModel: "gpt-6-luna",
    subject: "GPT API (GPT-6 Luna)",
    shortName: "GPT API",
    chip: "OpenAI GPT API · GPT-6 Luna",
    dataNote:
      "OpenAI GPT API(Responses API · GPT-6 Luna)로 보낸 단계별 사용자 JSON입니다. 1차 판정은 PREFIX-00+01, FAQ 안내는 PREFIX-00+02, 담당자 초안은 PREFIX-00+03, 순화는 PREFIX-00+04가 이어집니다.",
    promptNote:
      "OpenAI GPT API(Responses API) 호출 시 instructions(시스템)·input(사용자) 필드로 보낸 전체 프롬프트 본문을 호출마다 그대로 보여 줍니다.",
    emptyPromptNote:
      "이 기록에는 GPT API 프롬프트 전문이 없습니다. 새로 민원을 보내면 호출마다 표시됩니다.",
  },
  legacy: {
    subject: "기타 LLM API",
    shortName: "기타 LLM API",
    chip: "Legacy LLM API",
    dataNote:
      "호환 LLM API로 보낸 단계별 사용자 JSON입니다. PREFIX-00+01~04 조합을 그대로 전달합니다.",
    promptNote:
      "호환 LLM API 호출 시 system·user 메시지로 보낸 전체 프롬프트 본문을 보여 줍니다.",
    emptyPromptNote:
      "이 기록에는 LLM 프롬프트 전문이 없습니다. 새로 민원을 보내면 호출마다 표시됩니다.",
  },
  "": {
    subject: "선택한 LLM",
    shortName: "기본 설정",
    chip: "기본 설정 (.env)",
    dataNote:
      "LLM에 전달한 단계별 사용자 JSON입니다. 시스템 지시는 PREFIX-00+01이며, FAQ 안내는 PREFIX-00+02, 담당자 초안은 PREFIX-00+03, 순화는 PREFIX-00+04가 이어집니다.",
    promptNote:
      "실행한 LLM에 전달한 호출별 전체 프롬프트(시스템 지시 PREFIX + 사용자 JSON)를 보여 줍니다. 예전 기록에는 이 칸이 없을 수 있습니다.",
    emptyPromptNote:
      "이 기록에는 LLM 프롬프트 전문이 없습니다. 새로 민원을 보내면 호출마다 표시됩니다.",
  },
};

/** 잠긴 단추에 보일 배지·설명 문구입니다. Codex는 키가 아니라 실행 파일이 필요합니다. */
const LOCKED_TEXT = {
  codex_cli: { badge: "미설치", desc: "Codex CLI 없음 (PATH)" },
  default: { badge: "키 미설정", desc: "API 키 미설정 (.env)" },
};

/**
 * 브라우저 저장소를 읽습니다. 사생활 보호 모드처럼 막혀 있으면 빈 값입니다.
 *
 * @returns {string} 저장된 공급자 이름입니다.
 */
function readSavedProvider() {
  try {
    return localStorage.getItem(LLM_STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

/**
 * 고른 공급자를 브라우저 저장소에 남깁니다. 저장이 막혀도 선택은 유지합니다.
 *
 * @param {string} provider 공급자 이름입니다.
 * @returns {void}
 */
function saveProvider(provider) {
  try {
    localStorage.setItem(LLM_STORAGE_KEY, provider);
  } catch {
    // 저장소가 막힌 환경에서는 이번 화면에서만 선택을 유지합니다.
  }
}

/**
 * 단추가 잠겼는지 봅니다. 클릭 안내를 위해 `disabled` 대신 `aria-disabled`를 씁니다.
 *
 * @param {HTMLElement} button 엔진 단추입니다.
 * @returns {boolean} 잠겼으면 true입니다.
 */
function isLocked(button) {
  return button.getAttribute("aria-disabled") === "true";
}

/**
 * 한 단추를 활성으로 표시하고 숨은 입력에 공급자를 넣습니다.
 *
 * @param {NodeListOf<HTMLElement>} buttons 엔진 단추 목록입니다.
 * @param {HTMLElement} button 고를 단추입니다.
 * @param {HTMLInputElement} hiddenInput 폼의 `provider` 입력입니다.
 * @returns {void}
 */
function activateProvider(buttons, button, hiddenInput) {
  buttons.forEach((item) => {
    const on = item === button;
    item.classList.toggle("active", on);
    item.setAttribute("aria-pressed", String(on));
  });
  hiddenInput.value = button.dataset.provider || "";
}

/**
 * LLM 엔진 선택 단추를 연결하고 이전 선택을 복원합니다.
 *
 * 잠긴 단추를 누르면 고르지 않고 흔들림으로 알립니다. 여러 번 불러도
 * 클릭 처리기는 한 번만 붙습니다.
 *
 * @param {ParentNode} [root=document] 검색 범위입니다.
 * @returns {void}
 */
export function initLlmSelector(root = document) {
  const buttons = root.querySelectorAll(".llm-choice-btn");
  const hiddenInput = root.querySelector("#provider");
  if (!buttons.length || !hiddenInput) return;

  const saved = readSavedProvider();
  const buttonList = Array.from(buttons);
  const restored =
    buttonList.find((btn) => (btn.dataset.provider || "") === saved && !isLocked(btn)) ||
    buttonList.find((btn) => !isLocked(btn)) ||
    buttons[0];
  activateProvider(buttons, restored, hiddenInput);

  buttons.forEach((btn) => {
    if (btn.dataset.bound) return;
    btn.dataset.bound = "true";
    btn.addEventListener("click", () => {
      if (isLocked(btn)) {
        btn.classList.remove("shake");
        void btn.offsetWidth; // 다시 누를 때도 애니메이션을 처음부터 재생합니다.
        btn.classList.add("shake");
        return;
      }
      activateProvider(buttons, btn, hiddenInput);
      saveProvider(btn.dataset.provider || "");
    });
  });
}

/**
 * 서버가 알려 준 공급자 상태로 키·실행 파일이 없는 단추를 잠급니다.
 *
 * 잠긴 단추는 흐리게 보이고 배지·설명·툴팁이 불가 사유로 바뀝니다. 현재
 * 선택이 잠기면 처음 사용할 수 있는 단추로 옮기되, 저장된 선호는 지우지
 * 않아 키를 넣은 뒤 다시 열면 복원됩니다.
 *
 * @param {ParentNode} [root=document] 검색 범위입니다.
 * @param {Record<string, {available: boolean, reason?: string, resolvedProvider?: (string|null)}>} [providerStatus={}]
 *   `/api/v1/lab/fields`의 `providers`입니다. 없는 공급자는 사용 가능으로 봅니다.
 * @returns {void}
 */
export function updateLlmAvailability(root = document, providerStatus = {}) {
  const buttons = root.querySelectorAll(".llm-choice-btn");
  const hiddenInput = root.querySelector("#provider");
  if (!buttons.length || !hiddenInput) return;

  buttons.forEach((btn) => {
    const prov = btn.dataset.provider || "";
    const status = providerStatus[prov];
    const locked = Boolean(status) && !status.available;
    const badge = btn.querySelector(".btn-badge");
    const desc = btn.querySelector("small");
    // 처음 한 번 원래 문구를 보관해 두고, 다시 사용 가능해지면 되돌립니다.
    btn.dataset.origTitle ??= btn.title || "";
    if (badge) {
      badge.dataset.origClass ??= badge.className;
      badge.dataset.origText ??= badge.textContent;
    }
    if (desc) desc.dataset.origText ??= desc.textContent;

    btn.classList.toggle("is-disabled", locked);
    if (locked) {
      const text = LOCKED_TEXT[prov] || LOCKED_TEXT.default;
      btn.setAttribute("aria-disabled", "true");
      btn.title = `[선택 불가] ${status.reason || "현재 환경에서 사용할 수 없습니다."}`;
      if (badge) {
        badge.className = "btn-badge badge-disabled";
        badge.textContent = text.badge;
      }
      if (desc) desc.textContent = text.desc;
    } else {
      btn.removeAttribute("aria-disabled");
      btn.title = btn.dataset.origTitle;
      if (badge) {
        badge.className = badge.dataset.origClass;
        badge.textContent = badge.dataset.origText;
      }
      if (desc) {
        const resolvedShort =
          !prov && status?.resolvedProvider
            ? LLM_DISPLAY_META[status.resolvedProvider]?.shortName
            : "";
        desc.textContent = resolvedShort
          ? `.env 기본: ${resolvedShort}`
          : desc.dataset.origText;
      }
    }
  });

  const current = Array.from(buttons).find((btn) => btn.classList.contains("active"));
  if (!current || isLocked(current)) {
    const usable = Array.from(buttons).find((btn) => !isLocked(btn));
    if (usable) activateProvider(buttons, usable, hiddenInput);
  }
}

/**
 * 폼 값을 서버 계약 JSON으로 만듭니다.
 *
 * @param {HTMLFormElement} form 작성 폼입니다.
 * @returns {{title:string,category:string,district:string|null,body:string,provider:string|null}}
 */
export function readComplaint(form) {
  const data = new FormData(form);
  const district = String(data.get("district") || "").trim();
  const provider = String(data.get("provider") || "").trim();
  return {
    title: String(data.get("title") || "").trim(),
    category: String(data.get("category") || "").trim(),
    district: district || null,
    body: String(data.get("body") || "").trim(),
    provider: provider || null,
  };
}

/**
 * 선택 목록을 채웁니다.
 *
 * @param {HTMLSelectElement} select 대상 목록입니다.
 * @param {string[]} values 허용 값입니다.
 * @param {boolean} [keepEmpty=false] 빈 항목을 남길지 여부입니다.
 * @returns {void}
 */
function fillSelect(select, values, keepEmpty = false) {
  const current = select.value;
  select.querySelectorAll("option:not([value=''])").forEach((node) => node.remove());
  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.append(option);
  }
  if (keepEmpty || values.includes(current)) select.value = current;
}

/**
 * 청주시 4개 구 및 산하 읍·면·동 목록으로 발생 지역 셀렉트를 채웁니다.
 *
 * @param {HTMLSelectElement} select 대상 셀렉트 요소입니다.
 * @param {string[]} districts 자치구 목록입니다.
 * @param {Record<string, string[]>} districtAreas 구별 읍·면·동 목록입니다.
 * @returns {void}
 */
export function fillDistrictSelect(select, districts = [], districtAreas = {}) {
  if (!select) return;
  const current = select.value;
  select.innerHTML = '<option value="">지정하지 않음 (본문 자동 감지)</option>';
  for (const district of districts) {
    const group = document.createElement("optgroup");
    group.label = district;
    const allOption = document.createElement("option");
    allOption.value = district;
    allOption.textContent = `${district} (전체)`;
    group.append(allOption);

    const areas = districtAreas[district] || [];
    for (const area of areas) {
      const areaOption = document.createElement("option");
      areaOption.value = `${district}:${area}`;
      areaOption.textContent = `${district} ${area}`;
      group.append(areaOption);
    }
    select.append(group);
  }
  if (current) select.value = current;
}

/**
 * 분야·지역 목록을 서버에서 불러옵니다.
 *
 * @returns {Promise<void>}
 */
async function loadFields() {
  const response = await fetch("/api/v1/lab/fields");
  if (!response.ok) throw new Error("작성 항목을 불러오지 못했습니다.");
  const value = await response.json();
  fillSelect(document.querySelector("#category"), value.categories || []);
  fillDistrictSelect(
    document.querySelector("#district"),
    value.districts || [],
    value.districtAreas || {},
  );
  if (value.providers) {
    defaultResolvedProvider = value.providers[""]?.resolvedProvider || "";
    updateLlmAvailability(document, value.providers);
  }
}

const COPY_IDLE = "JSON 복사";
const COPY_DONE = "복사됨";
const COPY_FAIL = "복사 실패";

/**
 * 클립보드에 문자열을 넣습니다.
 *
 * 보안 문맥에서는 Clipboard API를 쓰고, 없으면 숨은 textarea로 복사합니다.
 *
 * @param {string} text 복사할 본문입니다.
 * @returns {Promise<void>}
 */
export async function copyText(text) {
  const value = String(text ?? "");
  if (navigator.clipboard?.writeText) {
    try {
      await Promise.race([
        navigator.clipboard.writeText(value),
        new Promise((_, reject) => {
          window.setTimeout(() => reject(new Error("clipboard timeout")), 1500);
        }),
      ]);
      return;
    } catch {
      // Clipboard API가 막히면 아래 textarea 경로를 씁니다.
    }
  }
  if (typeof document === "undefined") {
    throw new Error("클립보드를 쓸 수 없습니다.");
  }
  const area = document.createElement("textarea");
  area.value = value;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.left = "-9999px";
  document.body.append(area);
  area.select();
  const ok = document.execCommand("copy");
  area.remove();
  if (!ok) throw new Error("클립보드를 쓸 수 없습니다.");
}

/**
 * JSON 칸의 복사 단추를 잠시 안내 문구로 바꿉니다.
 *
 * @param {HTMLButtonElement} button 대상 단추입니다.
 * @param {string} label 표시 문구입니다.
 * @returns {void}
 */
function flashCopyButton(button, label) {
  window.clearTimeout(Number(button.dataset.copyTimer || 0));
  button.textContent = label;
  const idle = button.dataset.copyIdle || COPY_IDLE;
  button.dataset.copyTimer = String(
    window.setTimeout(() => {
      button.textContent = idle;
    }, 1600),
  );
}

/**
 * 응대 결과 JSON 칸마다 복사 단추를 연결합니다.
 *
 * @param {ParentNode} [root=document] 검색 범위입니다.
 * @returns {void}
 */
export function bindJsonCopyButtons(root = document) {
  root.querySelectorAll("[data-copy-target]").forEach((node) => {
    if (!(node instanceof HTMLButtonElement)) return;
    node.addEventListener("click", async () => {
      const targetId = node.getAttribute("data-copy-target") || "";
      const pre = targetId ? root.querySelector(`#${targetId}`) : null;
      try {
        await copyText(pre ? pre.textContent || "" : "");
        flashCopyButton(node, COPY_DONE);
      } catch {
        flashCopyButton(node, COPY_FAIL);
      }
    });
  });
}

const ROLE_PROMPT_NAMES = {
  decision: "1차 판정",
  faq_answer: "FAQ 안내",
  staff_draft: "담당자 초안",
  sanitize: "순화",
};

/**
 * 응대 결과에 실제로 사용된 LLM 엔진 표시 정보를 계산합니다.
 *
 * `assist.llmProvider`(백엔드가 실제 해석한 공급자)를 최우선으로 보고,
 * 없으면 요청한 `provider`나 (기록 조회가 아닐 때) `.env` 기본 공급자를 씁니다.
 *
 * @param {object} payload 검사기에 보낸 민원 요청 본문입니다.
 * @param {object} received 서버 응답 JSON입니다.
 * @param {{fromHistory?:boolean,defaultProvider?:string}} [options] 해석 옵션입니다.
 * @returns {{
 *   providerKey:string,
 *   subject:string,
 *   shortName:string,
 *   chipText:string,
 *   badgeText:string,
 *   dataTitle:string,
 *   promptTitle:string,
 *   copyAriaLabel:string,
 *   dataNote:string,
 *   promptNote:string,
 *   emptyPromptNote:string,
 * }} 화면 섹션·배지 렌더링용 표시 정보입니다.
 */
export function resolveLlmSectionMeta(
  payload,
  received,
  { fromHistory = false, defaultProvider = "" } = {},
) {
  const assist = received?.assist || {};
  const requested = String(
    payload?.provider || received?.complaint?.provider || "",
  )
    .trim()
    .toLowerCase();
  const actual = String(assist.llmProvider || "").trim().toLowerCase();
  const fallback = !fromHistory ? String(defaultProvider || "").trim().toLowerCase() : "";
  const providerKey = actual || requested || fallback;
  const base = LLM_DISPLAY_META[providerKey] || {
    subject: PROVIDER_LABELS[providerKey] || providerKey,
    shortName: providerKey,
    chip: providerKey,
    dataNote: LLM_DISPLAY_META[""].dataNote,
    promptNote: LLM_DISPLAY_META[""].promptNote,
    emptyPromptNote: LLM_DISPLAY_META[""].emptyPromptNote,
  };
  const model = String(assist.llmModel || "").trim();
  const isCustomModel =
    Boolean(model) && model.toLowerCase() !== (base.defaultModel || "");
  const chipText = isCustomModel ? `${base.shortName} · ${model}` : base.chip;
  const fromEnvDefault = !requested && Boolean(actual || fallback);
  const labelCore = PROVIDER_LABELS[providerKey] || base.subject;
  let badgeText = `🤖 LLM 엔진: ${labelCore}`;
  if (isCustomModel) badgeText += ` · ${model}`;
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
 * 데이터·프롬프트 제목 옆의 LLM 엔진 칩을 갱신합니다.
 *
 * @param {Element|null} chipNode 대상 칩 요소입니다.
 * @param {ReturnType<typeof resolveLlmSectionMeta>} meta 엔진 표시 정보입니다.
 * @returns {void}
 */
function applyEngineChip(chipNode, meta) {
  if (!chipNode) return;
  chipNode.textContent = meta.chipText;
  chipNode.className = meta.providerKey
    ? `engine-chip engine-chip--${meta.providerKey}`
    : "engine-chip";
  chipNode.hidden = false;
}

/**
 * LLM 입력 데이터/프롬프트 섹션의 제목, 엔진 칩, 안내 문구를 일괄 갱신합니다.
 *
 * @param {ParentNode} root - 탐색 기준 루트 노드입니다.
 * @param {{
 *   titleSel: string,
 *   chipSel: string,
 *   noteSel: string,
 *   title: string,
 *   note: string,
 *   llmMeta: ReturnType<typeof resolveLlmSectionMeta>,
 * }} opts - 섹션 선택자와 표시 문구 설정입니다.
 * @returns {void}
 */
function applyLlmSection(
  root,
  { titleSel, chipSel, noteSel, title, note, llmMeta },
) {
  const titleNode = root.querySelector(titleSel);
  if (titleNode) titleNode.textContent = title;
  applyEngineChip(root.querySelector(chipSel), llmMeta);
  const noteNode = root.querySelector(noteSel);
  if (noteNode) noteNode.textContent = note;
}

/**
 * LLM에 전달한 호출별 프롬프트 전문을 호출마다 그립니다.
 *
 * @param {Array<{role?:string,system?:string,sent?:boolean,prompt?:string}>} calls
 *   `assist.codex` 목록입니다.
 * @param {{emptyNote?:string,shortName?:string,root?:ParentNode}} [options] 표시 옵션입니다.
 * @returns {void}
 */
export function renderCodexPrompts(
  calls,
  { emptyNote = "", shortName = "", root = document } = {},
) {
  const host = root.querySelector("#codex-prompts");
  if (!host) return;
  host.replaceChildren();
  const items = (calls || []).filter(
    (call) => typeof call?.prompt === "string" && call.prompt,
  );
  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "hint-block";
    empty.textContent = emptyNote || LLM_DISPLAY_META[""].emptyPromptNote;
    host.append(empty);
    return;
  }
  const enginePart = shortName && shortName !== "기본 설정" ? ` · ${shortName}` : "";
  items.forEach((call, index) => {
    const block = document.createElement("div");
    block.className = "json-block prompt-block";
    const head = document.createElement("div");
    head.className = "json-head";
    const title = document.createElement("h4");
    const roleName = ROLE_PROMPT_NAMES[call.role] || call.role || "호출";
    const sentLabel = call.sent ? "보냄" : "보내지 않음";
    title.textContent = `${index + 1}. ${roleName}${enginePart} · ${call.system || ""} · ${sentLabel}`;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "json-copy";
    button.dataset.copyIdle = "프롬프트 복사";
    button.dataset.copyPrompt = "1";
    button.textContent = "프롬프트 복사";
    button.setAttribute("aria-label", `${roleName} 프롬프트 복사`);
    head.append(title, button);
    const pre = document.createElement("pre");
    pre.textContent = call.prompt;
    block.append(head, pre);
    host.append(block);
  });
}

/**
 * 프롬프트 칸의 복사 단추를 한 번 연결합니다.
 *
 * @param {ParentNode} [root=document] 검색 범위입니다.
 * @returns {void}
 */
export function bindPromptCopyButtons(root = document) {
  const host = root.querySelector("#codex-prompts");
  if (!host || host.dataset.copyBound === "1") return;
  host.dataset.copyBound = "1";
  host.addEventListener("click", async (event) => {
    const target = event.target instanceof Element ? event.target : null;
    const button = target ? target.closest("[data-copy-prompt]") : null;
    if (!(button instanceof HTMLButtonElement)) return;
    const pre = button.closest(".prompt-block")?.querySelector("pre");
    try {
      await copyText(pre ? pre.textContent || "" : "");
      flashCopyButton(button, COPY_DONE);
    } catch {
      flashCopyButton(button, COPY_FAIL);
    }
  });
}

/**
 * 응대 결과를 화면에 채웁니다.
 *
 * @param {ReturnType<typeof readComplaint>} payload 검사기에 보낸 민원입니다.
 * @param {object} received 서버 JSON입니다. `assist.codex`는 사용자 JSON과 프롬프트 전문입니다.
 * @param {string} [sourceText] 기록에서 다시 볼 때 안내 문구입니다.
 * @param {ParentNode} [root=document] 결과를 채울 DOM 루트입니다.
 * @returns {void}
 */
export function showResult(payload, received, sourceText = "", root = document) {
  const assist = received.assist || {};
  const llmMeta = resolveLlmSectionMeta(payload, received, {
    fromHistory: Boolean(sourceText),
    defaultProvider: defaultResolvedProvider,
  });
  const source = root.querySelector("#result-source");
  if (source) {
    source.textContent = sourceText;
    source.hidden = !sourceText;
  }
  const districtBadge = root.querySelector("#result-district");
  if (districtBadge) {
    const effDistrict = received.effectiveDistrict || assist.district;
    const inferred = Boolean(received.districtInferred ?? assist.districtInferred);
    if (effDistrict) {
      districtBadge.textContent = inferred
        ? `📍 발생 지역: ${effDistrict} (본문 지명 자동 감지)`
        : `📍 발생 지역: ${effDistrict}`;
      districtBadge.hidden = false;
    } else {
      districtBadge.textContent = "📍 발생 지역: 지정 없음 (전체 지역 검색)";
      districtBadge.hidden = false;
    }
  }
  const placeBadge = root.querySelector("#result-place");
  if (placeBadge) {
    const place = assist.inferredPlace || received.inferredPlace;
    if (place && place.title) {
      const addr =
        place.roadAddress ||
        place.road_address ||
        place.jibunAddress ||
        place.jibun_address ||
        place.address ||
        "";
      placeBadge.textContent = addr
        ? `🗺️ 장소 추적: ${place.title} (${addr})`
        : `🗺️ 장소 추적: ${place.title}`;
      placeBadge.hidden = false;
    } else {
      placeBadge.hidden = true;
    }
  }
  const llmBadge = root.querySelector("#result-llm");
  if (llmBadge) {
    llmBadge.textContent = llmMeta.badgeText;
    if (llmMeta.providerKey) llmBadge.dataset.provider = llmMeta.providerKey;
    else delete llmBadge.dataset.provider;
    llmBadge.hidden = false;
  }
  root.querySelector("#result-message").textContent = received.message;
  root.querySelector("#result-outcome").textContent =
    outcomeNames[assist.outcome] || assist.outcome || "";
  const reason = assist.reasonCode || assist.decision?.reasonCode || "";
  root.querySelector("#result-reason").textContent = reason
    ? reasonNames[reason] || reason
    : "";
  const failures = assist.policyFailures || [];
  root.querySelector("#result-failures").textContent = failures.length
    ? `정책 검사: ${failures.join(" ")}`
    : "";
  root.querySelector("#result-answer").textContent = assist.answer || "";
  const draft = assist.staffDraft;
  root.querySelector("#result-draft").textContent = draft
    ? draft.draftAnswer || ""
    : "이번 민원에는 담당자 초안을 만들지 않았습니다.";
  const cleaned = assist.sanitize;
  root.querySelector("#result-sanitize").textContent = cleaned
    ? cleaned.sanitizedSummary || ""
    : "거친 표현 힌트가 없어 순화 호출을 건너뛰었습니다.";
  const hits = root.querySelector("#result-hits");
  hits.replaceChildren();
  for (const hit of [...(assist.faq || []), ...(assist.cases || [])]) {
    const item = document.createElement("li");
    item.textContent = `${hit.corpus === "routing" ? "사례" : "FAQ"} · ${hit.title || hit.sourceId || ""}`;
    hits.append(item);
  }
  if (!hits.childElementCount) {
    const item = document.createElement("li");
    item.textContent = "표시할 자료가 없습니다.";
    hits.append(item);
  }
  applyLlmSection(root, {
    titleSel: "#codex-data-title",
    chipSel: "#codex-data-engine",
    noteSel: "#codex-note",
    title: llmMeta.dataTitle,
    note: llmMeta.dataNote,
    llmMeta,
  });
  const copyDataBtn = root.querySelector("#codex-json-copy");
  if (copyDataBtn) copyDataBtn.setAttribute("aria-label", llmMeta.copyAriaLabel);
  root.querySelector("#codex-json").textContent = JSON.stringify(
    assist.codex || [],
    null,
    2,
  );

  applyLlmSection(root, {
    titleSel: "#codex-prompt-title",
    chipSel: "#codex-prompt-engine",
    noteSel: "#codex-prompt-note",
    title: llmMeta.promptTitle,
    note: llmMeta.promptNote,
    llmMeta,
  });
  renderCodexPrompts(assist.codex || [], {
    emptyNote: llmMeta.emptyPromptNote,
    shortName: llmMeta.shortName,
    root,
  });

  root.querySelector("#sent-json").textContent = JSON.stringify(payload, null, 2);
  root.querySelector("#received-json").textContent = JSON.stringify(
    received,
    null,
    2,
  );
}

/**
 * JSON 응답을 읽고 실패면 안내 문구를 던집니다.
 *
 * @param {Response} response fetch 응답입니다.
 * @param {string} fallback 본문에 message가 없을 때 쓸 문구입니다.
 * @returns {Promise<object>} 본문 객체입니다.
 */
async function readJsonResponse(response, fallback) {
  const value = await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(value?.message || fallback);
    error.status = response.status;
    throw error;
  }
  return value;
}

/**
 * 민원 JSON을 수신 API로 보냅니다.
 *
 * @param {ReturnType<typeof readComplaint>} payload 민원 내용입니다.
 * @returns {Promise<object>} 검색·판정 결과입니다.
 */
export async function sendComplaint(payload) {
  const response = await fetch("/api/v1/lab/complaints", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJsonResponse(response, "서버가 민원을 받지 못했습니다.");
}

const PROGRESS_STEPS = [
  { key: "read", label: "민원 내용을 읽고 있어요" },
  { key: "search", label: "저장된 안내와 사례를 찾고 있어요" },
  { key: "review", label: "찾은 자료를 살펴보고 있어요" },
  { key: "write", label: "안내문을 준비하고 있어요" },
  { key: "sanitize", label: "거친 표현을 정리하고 있어요" },
  { key: "draft", label: "담당자용 초안을 준비하고 있어요" },
];

/** @type {string[]} */
let progressSeen = [];

/**
 * 진행 칸을 열고 첫 단계로 맞춥니다.
 *
 * @returns {void}
 */
export function showProgress() {
  const panel = document.querySelector("#progress");
  if (!panel) return;
  progressSeen = [];
  panel.hidden = false;
  setProgress("read", PROGRESS_STEPS[0].label);
  panel.scrollIntoView({ block: "nearest" });
}

/**
 * 진행 칸을 닫습니다.
 *
 * @returns {void}
 */
export function hideProgress() {
  const panel = document.querySelector("#progress");
  if (panel) panel.hidden = true;
  progressSeen = [];
}

/**
 * 현재 진행 단계와 목록을 갱신합니다.
 *
 * @param {string} key 진행 키입니다.
 * @param {string} label 화면에 보여줄 문구입니다.
 * @returns {void}
 */
export function setProgress(key, label) {
  const labelNode = document.querySelector("#progress-label");
  if (labelNode) labelNode.textContent = label || "";
  if (key && !progressSeen.includes(key)) progressSeen.push(key);
  const list = document.querySelector("#progress-steps");
  if (!list) return;
  list.replaceChildren();
  for (const step of PROGRESS_STEPS) {
    const item = document.createElement("li");
    item.textContent = step.label;
    if (step.key === key) item.className = "active";
    else if (progressSeen.includes(step.key)) item.className = "done";
    list.append(item);
  }
}

/**
 * 진행 안내 NDJSON을 읽어 최종 수신 결과를 돌려줍니다.
 *
 * @param {ReturnType<typeof readComplaint>} payload 민원 내용입니다.
 * @param {(key:string,label:string)=>void} [onProgress] 단계 갱신 콜백입니다.
 * @returns {Promise<object>} `done.result` 본문입니다.
 */
export async function streamComplaint(payload, onProgress) {
  const response = await fetch("/api/v1/lab/complaints/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok || !response.body) {
    const value = await response.json().catch(() => null);
    const error = new Error(value?.message || "응대 진행 응답을 받지 못했습니다.");
    error.status = response.status;
    // 404/405나 스트림 본문 부재가 아닌 검증(422) 등 명확한 오류는 /complaints 재시도를 막습니다.
    if (!response.ok && response.status && response.status !== 404 && response.status !== 405) {
      error.noFallback = true;
    }
    throw error;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result = null;
  const consumeLine = (line) => {
    if (!line.trim()) return;
    const event = JSON.parse(line);
    if (event.type === "progress") {
      onProgress?.(event.key, event.label);
    } else if (event.type === "done") {
      result = event.result;
    } else if (event.type === "error") {
      const error = new Error(event.message || "응대 진행이 실패했습니다.");
      error.noFallback = true;
      throw error;
    }
  };
  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      buffer += decoder.decode();
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) consumeLine(line);
  }
  for (const line of buffer.split("\n")) consumeLine(line);
  if (!result) {
    const error = new Error("응대 결과를 받지 못했습니다.");
    error.noFallback = true;
    throw error;
  }
  return result;
}

/**
 * 파일로 남긴 테스트 기록 목록을 불러옵니다.
 *
 * @returns {Promise<object[]>} 최신순 요약 목록입니다.
 */
export async function fetchRuns() {
  const response = await fetch("/api/v1/lab/runs");
  const value = await readJsonResponse(response, "테스트 기록을 불러오지 못했습니다.");
  return value.items || [];
}

/**
 * 파일로 남긴 검사 결과 한 건을 불러옵니다.
 *
 * @param {string} runId 기록 ID입니다.
 * @returns {Promise<object>}
 */
export async function fetchRun(runId) {
  const response = await fetch(`/api/v1/lab/runs/${encodeURIComponent(runId)}`);
  return readJsonResponse(response, "테스트 기록을 찾지 못했습니다.");
}

/**
 * 파일로 남긴 테스트 기록을 모두 지웁니다.
 *
 * @returns {Promise<number>} 삭제한 파일 수입니다.
 */
export async function clearSavedRuns() {
  const response = await fetch("/api/v1/lab/runs", { method: "DELETE" });
  const value = await readJsonResponse(response, "테스트 기록을 지우지 못했습니다.");
  return value.removed || 0;
}

/**
 * 작성 폼 제출과 테스트 기록 목록을 연결합니다.
 *
 * @returns {void}
 */
function bind() {
  const form = document.querySelector("#complaint-form");
  const title = document.querySelector("#title");
  const body = document.querySelector("#body");
  const submit = document.querySelector("#submit");
  const result = document.querySelector("#result");
  const errorBox = document.querySelector("#error");
  const titleCount = document.querySelector("#title-count");
  const bodyCount = document.querySelector("#body-count");
  const list = document.querySelector("#run-list");
  const empty = document.querySelector("#run-empty");
  const clear = document.querySelector("#run-clear");
  let runs = [];
  let selectedId = "";

  const count = () => {
    titleCount.textContent = `${title.value.length}/120`;
    bodyCount.textContent = `${body.value.length}/2,000`;
  };
  title.addEventListener("input", count);
  body.addEventListener("input", count);
  count();
  initLlmSelector();
  bindJsonCopyButtons();
  bindPromptCopyButtons();

  /**
   * 오른쪽 기록 목록을 다시 그립니다.
   *
   * @returns {void}
   */
  const renderRuns = () => {
    list.replaceChildren();
    empty.hidden = runs.length > 0;
    clear.disabled = runs.length === 0;
    for (const run of runs) {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "run-item";
      button.dataset.runId = run.id;
      if (run.id === selectedId) button.setAttribute("aria-current", "true");
      const heading = document.createElement("strong");
      heading.textContent = run.title || "(제목 없음)";
      const meta = document.createElement("span");
      const outcome = outcomeNames[run.outcome] || run.outcome || "결과 없음";
      meta.textContent = `${formatRunTime(run.at)} · ${outcome}`;
      button.append(heading, meta);
      button.addEventListener("click", async () => {
        errorBox.hidden = true;
        try {
          const record = await fetchRun(run.id);
          selectedId = run.id;
          showResult(
            record.payload,
            record.received,
            "파일 기록에서 다시 보는 결과입니다. 모델을 다시 호출하지 않았습니다.",
          );
          result.hidden = false;
          renderRuns();
        } catch (error) {
          errorBox.textContent = error.message;
          errorBox.hidden = false;
        }
      });
      item.append(button);
      list.append(item);
    }
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorBox.hidden = true;
    result.hidden = true;
    const payload = readComplaint(form);
    submit.disabled = true;
    submit.textContent = "자료를 확인하고 있어요…";
    form.querySelectorAll("input, select, textarea").forEach((node) => {
      node.disabled = true;
    });
    showProgress();
    let sawProgress = false;
    try {
      let received;
      try {
        received = await streamComplaint(payload, (key, label) => {
          sawProgress = true;
          setProgress(key, label);
        });
      } catch (streamError) {
        if (streamError?.noFallback || sawProgress) throw streamError;
        received = await sendComplaint(payload);
      }
      hideProgress();
      selectedId = received.run?.id || "";
      runs = await fetchRuns();
      showResult(payload, received);
      result.hidden = false;
      renderRuns();
      result.scrollIntoView({ block: "start" });
    } catch (error) {
      hideProgress();
      errorBox.textContent = error.message;
      errorBox.hidden = false;
    } finally {
      submit.disabled = false;
      submit.textContent = "민원 보내기";
      form.querySelectorAll("input, select, textarea").forEach((node) => {
        node.disabled = false;
      });
    }
  });

  clear.addEventListener("click", async () => {
    errorBox.hidden = true;
    try {
      await clearSavedRuns();
      runs = [];
      selectedId = "";
      result.hidden = true;
      renderRuns();
    } catch (error) {
      errorBox.textContent = error.message;
      errorBox.hidden = false;
    }
  });

  fetchRuns()
    .then((items) => {
      runs = items;
      renderRuns();
    })
    .catch((error) => {
      errorBox.textContent = error.message;
      errorBox.hidden = false;
      renderRuns();
    });
}

if (typeof document !== "undefined" && document.querySelector("#complaint-form")) {
  loadFields()
    .catch((error) => {
      const errorBox = document.querySelector("#error");
      errorBox.textContent = error.message;
      errorBox.hidden = false;
    })
    .finally(bind);
}
