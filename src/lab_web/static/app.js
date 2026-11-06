/**
 * 응대 검사기 작성 화면입니다. 민원 필드를 JSON으로 서버에 보냅니다.
 */

const outcomeNames = {
  faq_answer: "안내를 드렸습니다",
  department_suggestion: "담당 부서 후보로 넘겼습니다",
  human_handoff: "담당자가 이어서 살펴봅니다",
};

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
 * 민원 JSON을 수신 API로 보냅니다.
 *
 * @param {ReturnType<typeof readComplaint>} payload 민원 내용입니다.
 * @returns {Promise<object>}
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

function bind() {
  const form = document.querySelector("#complaint-form");
  const title = document.querySelector("#title");
  const body = document.querySelector("#body");
  const submit = document.querySelector("#submit");
  const result = document.querySelector("#result");
  const errorBox = document.querySelector("#error");
  const titleCount = document.querySelector("#title-count");
  const bodyCount = document.querySelector("#body-count");

  const count = () => {
    titleCount.textContent = `${title.value.length}/120`;
    bodyCount.textContent = `${body.value.length}/2,000`;
  };
  title.addEventListener("input", count);
  body.addEventListener("input", count);
  count();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorBox.hidden = true;
    result.hidden = true;
    submit.disabled = true;
    const payload = readComplaint(form);
    try {
      const received = await sendComplaint(payload);
      const assist = received.assist || {};
      document.querySelector("#result-message").textContent = received.message;
      document.querySelector("#result-outcome").textContent =
        outcomeNames[assist.outcome] || assist.outcome || "";
      document.querySelector("#result-answer").textContent = assist.answer || "";
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
      document.querySelector("#sent-json").textContent = JSON.stringify(
        payload,
        null,
        2,
      );
      document.querySelector("#received-json").textContent = JSON.stringify(
        received,
        null,
        2,
      );
      result.hidden = false;
      result.scrollIntoView({ block: "start" });
    } catch (error) {
      errorBox.textContent = error.message;
      errorBox.hidden = false;
    } finally {
      submit.disabled = false;
    }
  });
}

loadFields()
  .catch((error) => {
    const errorBox = document.querySelector("#error");
    errorBox.textContent = error.message;
    errorBox.hidden = false;
  })
  .finally(bind);
