/**
 * 응대 검사기 작성 화면입니다. 민원 필드를 JSON으로 서버에 보냅니다.
 * 보낸 결과는 이 브라우저의 테스트 기록에만 남기고 업무 DB에는 쓰지 않습니다.
 */

export const RUN_STORAGE_KEY = "lab-test-runs";
export const MAX_RUNS = 20;

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
 * 브라우저 저장소에서 테스트 기록을 읽습니다.
 *
 * @param {Storage} [storage=localStorage] 웹 저장소입니다.
 * @returns {object[]}
 */
export function loadRuns(storage = localStorage) {
  try {
    const parsed = JSON.parse(storage.getItem(RUN_STORAGE_KEY) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

/**
 * 테스트 기록을 브라우저 저장소에 씁니다.
 *
 * @param {object[]} runs 기록 목록입니다.
 * @param {Storage} [storage=localStorage] 웹 저장소입니다.
 * @returns {void}
 */
export function saveRuns(runs, storage = localStorage) {
  storage.setItem(RUN_STORAGE_KEY, JSON.stringify(runs.slice(0, MAX_RUNS)));
}

/**
 * 한 번의 검사 결과를 기록 항목으로 만듭니다.
 *
 * @param {ReturnType<typeof readComplaint>} payload 보낸 민원입니다.
 * @param {object} received 서버 JSON입니다.
 * @returns {{id:string,at:string,title:string,outcome:string,reasonCode:string,payload:object,received:object}}
 */
export function makeRun(payload, received) {
  const assist = received.assist || {};
  return {
    id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
    at: new Date().toISOString(),
    title: payload.title,
    outcome: assist.outcome || "",
    reasonCode: assist.reasonCode || assist.decision?.reasonCode || "",
    payload,
    received,
  };
}

/**
 * 새 기록을 맨 앞에 두고 개수 한도를 지킵니다.
 *
 * @param {object[]} runs 기존 목록입니다.
 * @param {object} run 추가할 기록입니다.
 * @returns {object[]}
 */
export function addRun(runs, run) {
  return [run, ...runs.filter((item) => item.id !== run.id)].slice(0, MAX_RUNS);
}

/**
 * 기록 시각을 짧게 표시합니다.
 *
 * @param {string} iso ISO 시각입니다.
 * @returns {string}
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

/**
 * 폼 값을 서버 계약 JSON으로 만듭니다.
 *
 * @param {HTMLFormElement} form 작성 폼입니다.
 * @returns {{title:string,category:string,district:string|null,body:string}}
 */
export function readComplaint(form) {
  const data = new FormData(form);
  const district = String(data.get("district") || "").trim();
  return {
    title: String(data.get("title") || "").trim(),
    category: String(data.get("category") || "").trim(),
    district: district || null,
    body: String(data.get("body") || "").trim(),
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
 * 분야·지역 목록을 서버에서 불러옵니다.
 *
 * @returns {Promise<void>}
 */
async function loadFields() {
  const response = await fetch("/api/v1/lab/fields");
  if (!response.ok) throw new Error("작성 항목을 불러오지 못했습니다.");
  const value = await response.json();
  fillSelect(document.querySelector("#category"), value.categories || []);
  fillSelect(document.querySelector("#district"), value.districts || [], true);
}

/**
 * 응대 결과를 화면에 채웁니다.
 *
 * @param {ReturnType<typeof readComplaint>} payload 검사기에 보낸 민원입니다.
 * @param {object} received 서버 JSON입니다. `assist.codex`는 모델 사용자 JSON입니다.
 * @param {string} [sourceText] 기록에서 다시 볼 때 안내 문구입니다.
 * @returns {void}
 */
function showResult(payload, received, sourceText = "") {
  const source = document.querySelector("#result-source");
  if (source) {
    source.textContent = sourceText;
    source.hidden = !sourceText;
  }
  const assist = received.assist || {};
  document.querySelector("#result-message").textContent = received.message;
  document.querySelector("#result-outcome").textContent =
    outcomeNames[assist.outcome] || assist.outcome || "";
  const reason = assist.reasonCode || assist.decision?.reasonCode || "";
  document.querySelector("#result-reason").textContent = reason
    ? reasonNames[reason] || reason
    : "";
  const failures = assist.policyFailures || [];
  document.querySelector("#result-failures").textContent = failures.length
    ? `정책 검사: ${failures.join(" ")}`
    : "";
  document.querySelector("#result-answer").textContent = assist.answer || "";
  const draft = assist.staffDraft;
  document.querySelector("#result-draft").textContent = draft
    ? draft.draftAnswer || ""
    : "이번 민원에는 담당자 초안을 만들지 않았습니다.";
  const cleaned = assist.sanitize;
  document.querySelector("#result-sanitize").textContent = cleaned
    ? cleaned.sanitizedSummary || ""
    : "거친 표현 힌트가 없어 순화 호출을 건너뛰었습니다.";
  const hits = document.querySelector("#result-hits");
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
  document.querySelector("#codex-json").textContent = JSON.stringify(
    assist.codex || [],
    null,
    2,
  );
  document.querySelector("#sent-json").textContent = JSON.stringify(payload, null, 2);
  document.querySelector("#received-json").textContent = JSON.stringify(
    received,
    null,
    2,
  );
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
  const value = await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(value?.message || "서버가 민원을 받지 못했습니다.");
    error.status = response.status;
    throw error;
  }
  return value;
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
  let runs = loadRuns();
  let selectedId = "";

  const count = () => {
    titleCount.textContent = `${title.value.length}/120`;
    bodyCount.textContent = `${body.value.length}/2,000`;
  };
  title.addEventListener("input", count);
  body.addEventListener("input", count);
  count();

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
      button.addEventListener("click", () => {
        selectedId = run.id;
        showResult(
          run.payload,
          run.received,
          "기록에서 다시 보는 결과입니다. 모델을 다시 호출하지 않았습니다.",
        );
        result.hidden = false;
        renderRuns();
      });
      item.append(button);
      list.append(item);
    }
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorBox.hidden = true;
    submit.disabled = true;
    const payload = readComplaint(form);
    try {
      const received = await sendComplaint(payload);
      const run = makeRun(payload, received);
      runs = addRun(runs, run);
      saveRuns(runs);
      selectedId = run.id;
      showResult(payload, received);
      result.hidden = false;
      renderRuns();
      result.scrollIntoView({ block: "start" });
    } catch (error) {
      errorBox.textContent = error.message;
      errorBox.hidden = false;
    } finally {
      submit.disabled = false;
    }
  });

  clear.addEventListener("click", () => {
    runs = [];
    selectedId = "";
    saveRuns(runs);
    result.hidden = true;
    renderRuns();
  });

  renderRuns();
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
