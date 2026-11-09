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
  button.dataset.copyTimer = String(
    window.setTimeout(() => {
      button.textContent = COPY_IDLE;
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
  bindJsonCopyButtons();

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
    submit.disabled = true;
    const payload = readComplaint(form);
    try {
      const received = await sendComplaint(payload);
      selectedId = received.run?.id || "";
      runs = await fetchRuns();
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
