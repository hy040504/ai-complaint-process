import { icon } from "./icons.js";
import { THEME_KEY, readTheme, getTheme, setTheme } from "./theme.js";
import {
  staffShell,
  staffQueue,
  staffProcess,
  staffReviewInfo,
} from "./staff.js";
import {
  citizenShell,
  citizenHome,
  citizenServicesPage,
  citizenNewsPage,
  citizenUpdates,
  citizenProfile,
  citizenNotices,
  showCitizenIntro,
} from "./citizen.js";
import {
  read,
  refresh,
  api,
  setRole,
  visible,
  statusNames,
  districts,
  categories,
} from "./store.js";

const app = document.querySelector("#app");
const modal = document.querySelector("#modal");
const $ = (s, parent = document) => parent.querySelector(s);
/** 화면에 필요한 값을 변환합니다. */
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (ch) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        ch
      ],
  );
/** 화면에 필요한 값을 변환합니다. */
const date = (value) =>
  new Date(value).toLocaleDateString("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
/** 화면에 필요한 값을 변환합니다. */
const badge = (c) =>
  `<span class="badge ${c.status}"><i></i>${statusNames[c.status]}</span>`;
/** 화면에 필요한 값을 변환합니다. */
const origin = (answer) =>
  ({
    ai: "AI 초안·담당자 검토",
    ai_edited: "AI 초안·담당자 수정",
    staff: "담당자 답변",
  })[answer?.origin] || "답변 대기";
/** 화면에 필요한 값을 변환합니다. */
const button = (text, cls = "", attrs = "") =>
  `<button class="btn ${cls}" ${attrs}>${text}</button>`;
/** 화면에 필요한 값을 변환합니다. */
const link = (text, path, cls = "") =>
  `<a class="${cls}" href="#${path}">${text}</a>`;
let route, data, toastTimer;
let chatMessages = [];
let chatPending = false;
let citizenPrompt = null;
let newlyCreatedId = null;
let busy = false;
let loadSequence = 0;

/**
 * 현재 해시 경로와 목록 필터를 읽습니다.
 *
 * @returns {object} 현재 경로·쿼리·역할 정보입니다.
 */
function currentRoute() {
  const [path, query] = (location.hash.slice(1) || "/citizen").split("?");
  return {
    path,
    params: new URLSearchParams(query),
    staff: path.startsWith("/staff"),
  };
}
/**
 * 저장 오류를 포함한 작업 결과를 보조 기술에도 알립니다.
 *
 * @param {string} message 표시할 안내 문구입니다.
 * @returns {void} 반환값 없이 화면 상태를 갱신합니다.
 */
function toast(message) {
  clearTimeout(toastTimer);
  $("#toast").textContent = message;
  $("#toast").classList.add("show");
  toastTimer = setTimeout(() => $("#toast").classList.remove("show"), 4500);
}
/**
 * 모달 안에서 확인할 내용을 제공하고 닫힌 뒤 원래 초점으로 돌아갑니다.
 *
 * @param {string} title 화면에 표시할 제목입니다.
 * @param {string} content 렌더링할 HTML 내용입니다.
 * @returns {void} 반환값 없이 화면 상태를 갱신합니다.
 */
function openModal(title, content) {
  modal.innerHTML = `<div class="modal-head"><h2 id="modal-title">${title}</h2><button class="icon-btn" data-action="close-modal" aria-label="닫기">${icon("close")}</button></div>${content}`;
  modal.showModal();
}
/**
 * 변경 작업 실패 시 기존 입력을 보존하면서 안내합니다.
 *
 * @param {function(): (unknown|Promise<unknown>)} action 실행할 동작 또는 동작 영역 HTML입니다.
 * @param {string} message 표시할 안내 문구입니다.
 * @param {boolean} [rerender=true] 성공 후 화면을 다시 그릴지 여부입니다.
 * @returns {Promise<boolean>} 비동기 작업의 완료 결과입니다.
 */
async function perform(action, message, rerender = true) {
  if (busy) return false;
  busy = true;
  const controls = [...document.querySelectorAll("button")].map((element) => [
    element,
    element.disabled,
  ]);
  controls.forEach(([element]) => {
    element.disabled = true;
  });
  app.setAttribute("aria-busy", "true");
  try {
    await action();
    await refresh();
    if (rerender) render();
    if (message) toast(message);
    return true;
  } catch (error) {
    toast(error.message);
    return false;
  } finally {
    busy = false;
    app.removeAttribute("aria-busy");
    controls.forEach(([element, disabled]) => {
      if (element.isConnected) element.disabled = disabled;
    });
  }
}
/**
 * loadScreen 화면 동작을 구성합니다.
 *
 * @returns {Promise<void>} 비동기 작업의 완료 결과입니다.
 */
async function loadScreen() {
  const sequence = ++loadSequence;
  route = currentRoute();
  app.innerHTML = shell(
    '<div class="page-content"><div class="panel empty" role="status">서버에서 민원을 불러오고 있습니다…</div></div>',
  );
  try {
    await setRole(route.staff ? "staff" : "citizen");
    await refresh();
    if (sequence === loadSequence) {
      render();
      if (!route.staff) showCitizenIntro();
      if (route.path === "/citizen/assistant" && citizenPrompt) {
        const prompt = citizenPrompt;
        citizenPrompt = null;
        sendChat(prompt);
      }
    }
  } catch (error) {
    if (sequence === loadSequence)
      app.innerHTML = shell(
        `<div class="page-content"><div class="panel empty"><h1>서버 데이터를 불러오지 못했습니다</h1><p>${esc(error.message)}</p>${button("다시 시도", "primary", 'data-action="reload"')}</div></div>`,
      );
  }
}
/**
 * shell 화면 동작을 구성합니다.
 *
 * @param {string} content 렌더링할 HTML 내용입니다.
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
function shell(content) {
  document.body.dataset.site = route.staff ? "staff" : "citizen";
  document.querySelector('meta[name="theme-color"]').content =
    getTheme() === "dark" ? "#101827" : route.staff ? "#16203a" : "#2f6fed";
  return route.staff
    ? staffShell(content, route, data || read())
    : citizenShell(content, route.path);
}
/**
 * pageHeading 화면 동작을 구성합니다.
 *
 * @param {string} eyebrow 제목 위의 구분 문구입니다.
 * @param {string} title 화면에 표시할 제목입니다.
 * @param {string} sub 제목의 보조 설명입니다.
 * @param {string} [action=""] 실행할 동작 또는 동작 영역 HTML입니다.
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
function pageHeading(eyebrow, title, sub, action = "") {
  return `<div class="page-heading"><div><div class="eyebrow">${eyebrow}</div><h1>${title}</h1><p>${sub}</p></div>${action}</div>`;
}
/**
 * home 화면 동작을 구성합니다.
 *
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
function home() {
  return citizenHome(data);
}
/**
 * listRows 화면 동작을 구성합니다.
 *
 * @param {Array<object>} rows 현재 권한으로 조회한 민원 목록입니다.
 * @param {boolean} [staff=false] 담당자 화면인지 여부입니다.
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
function listRows(rows, staff = false) {
  return rows
    .map(
      (c) =>
        `<tr><td class="id-cell">${c.id.split("-").at(-1)}</td><td><a class="row-title" href="#/${staff ? "staff" : "citizen"}/detail/${c.id}">${esc(c.title)} ${c.visibility === "private" ? `<span class="private-mark" title="비공개">${icon("shield", 13)}</span>` : ""}</a><span class="row-sub">${esc(c.category)} <span>·</span> ${staff ? (c.assigned ? "김담당" : "담당자 미지정") : origin(c.published)}</span></td><td>${esc(c.district)}</td><td>${badge(c)}</td><td class="date-cell">${date(c.date)}</td><td><a class="row-open" href="#/${staff ? "staff" : "citizen"}/detail/${c.id}" aria-label="${esc(c.title)} 상세 보기">${icon("chevron", 16)}</a></td></tr>`,
    )
    .join("");
}
/**
 * board 화면 동작을 구성합니다.
 *
 * @param {boolean} [staff=false] 담당자 화면인지 여부입니다.
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
function board(staff = false) {
  if (staff) return staffQueue(data, route.params);
  const mine = route.path.endsWith("/mine");
  const q = route.params.get("q") || "",
    status = route.params.get("status") || "",
    district = route.params.get("district") || "",
    category = route.params.get("category") || "",
    assign = route.params.get("assign") || "";
  let rows = (
    staff
      ? data.complaints.filter((c) => c.status !== "withdrawn")
      : visible(data, mine)
  ).filter(
    (c) =>
      (!q || c.title.toLowerCase().includes(q.toLowerCase())) &&
      (!status || c.status === status) &&
      (!district || c.district === district) &&
      (!category || c.category === category) &&
      (!assign || (assign === "mine" ? c.assigned : !c.assigned)),
  );
  const total = rows.length,
    pages = Math.max(1, Math.ceil(total / 8));
  const page = Math.max(
    1,
    Math.min(Number(route.params.get("page")) || 1, pages),
  );
  rows = rows.slice((page - 1) * 8, page * 8);
  return `<div class="page-content">${pageHeading(staff ? "COMPLAINT MANAGEMENT" : "CITIZEN VOICE", mine ? "내 민원" : staff ? "민원 관리" : "민원 게시판", mine ? "내가 남긴 목소리와 답변을 한곳에서 확인하세요." : staff ? "접수된 민원을 확인하고 담당자 검토와 답변을 이어가세요." : "우리 동네의 목소리를 살펴보고, 여러분의 의견도 들려주세요.", staff ? "" : link(`${icon("plus", 17)} 민원 작성`, "/citizen/write", "btn primary"))}
  ${!staff ? `<div class="info-banner">${icon("shield", 19)}<span>개인정보 없는 합성 시연 데이터입니다. 비공개 민원은 내 글만 표시됩니다.</span></div>` : ""}<section class="panel list-panel"><div class="list-tabs">${(staff
    ? [
        ["", "전체 민원"],
        ["under_review", "검토 중"],
        ["submitted", "접수 대기"],
        ["answered", "답변 완료"],
      ]
    : [
        ["", "전체"],
        ["submitted", "접수 대기"],
        ["under_review", "검토 중"],
        ["answered", "답변 완료"],
        ["closed", "처리 종료"],
      ]
  )
    .map(
      ([value, label]) =>
        `<button class="${status === value ? "active" : ""}" data-action="filter-status" data-value="${value}">${label}</button>`,
    )
    .join(
      "",
    )}</div><form id="filters" class="filters"><div class="search-field">${icon("search", 18)}<input name="q" aria-label="민원 제목 검색" placeholder="어떤 민원을 찾으세요? 제목을 검색해 보세요." value="${esc(q)}"></div><select name="district" aria-label="지역 선택"><option value="">전체 지역</option>${districts.map((d) => `<option ${district === d ? "selected" : ""}>${d}</option>`).join("")}</select><select name="category" aria-label="분야 선택"><option value="">전체 분야</option>${categories.map((c) => `<option ${category === c ? "selected" : ""}>${c}</option>`).join("")}</select>${staff ? `<select name="assign" aria-label="담당 선택"><option value="">전체 담당</option><option value="mine" ${assign === "mine" ? "selected" : ""}>내 담당</option><option value="none" ${assign === "none" ? "selected" : ""}>미지정</option></select>` : ""}${button("검색", "primary", 'type="submit"')}<button class="icon-btn" type="button" data-action="reset-filters" aria-label="검색 조건 초기화">${icon("refresh", 18)}</button></form><div class="table-meta"><span>총 <b>${total}</b>건의 민원</span><span>최근 등록순 ${icon("filter", 14)}</span></div><div class="table-wrap"><table><thead><tr><th scope="col">번호</th><th scope="col">민원 제목</th><th scope="col">지역</th><th scope="col">처리 상태</th><th scope="col">등록일</th><th scope="col"><span class="sr-only">상세</span></th></tr></thead><tbody>${listRows(rows, staff)}</tbody></table></div>${total === 0 ? `<div class="empty">${icon("search", 38)}<h3>검색 결과가 없습니다</h3><p>검색어나 필터를 바꾸어 다시 찾아보세요.</p>${button("검색 조건 초기화", "", 'data-action="reset-filters"')}</div>` : ""}<div class="pagination"><span>${total ? (page - 1) * 8 + 1 : 0}–${Math.min(page * 8, total)} / ${total}건</span><div>${button("‹", "", 'data-action="page" data-page="' + (page - 1) + '" ' + (page === 1 ? "disabled" : ""))}${Array.from({ length: pages }, (_, i) => button(i + 1, page === i + 1 ? "active" : "", `data-action="page" data-page="${i + 1}"`)).join("")}${button("›", "", 'data-action="page" data-page="' + (page + 1) + '" ' + (page === pages ? "disabled" : ""))}</div><span>페이지당 8건</span></div></section></div>`;
}
/**
 * writeForm 화면 동작을 구성합니다.
 *
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
function writeForm() {
  const editId = route.params.get("edit");
  const item = editId
    ? data.complaints.find(
        (c) =>
          c.id === editId &&
          c.owner === "citizen-demo" &&
          !c.published &&
          c.status !== "withdrawn",
      )
    : null;
  if (editId && !item) return missing();
  let draft = {};
  try {
    draft = JSON.parse(sessionStorage.getItem("complaint-form") || "{}");
  } catch {
    /* 손상된 임시 입력 대신 빈 양식을 제공합니다. */
  }
  const value = item || draft;
  return `<div class="page-content narrow">${pageHeading("YOUR VOICE MATTERS", item ? "민원 수정" : "작은 목소리도 소중히 듣겠습니다", "일상에서 느낀 불편이나 궁금한 점을 편하게 남겨주세요.")}<div class="form-steps"><span class="active"><b>1</b> 민원 내용 작성</span><i></i><span><b>2</b> 담당자 검토</span><i></i><span><b>3</b> 답변 확인</span></div><div class="info-banner">${icon("help", 20)}<span>이곳은 <b>시연 서비스</b>입니다. 실제 개인정보를 입력하지 마세요. 청주시 공식 접수로 연결되지 않습니다.</span></div><form id="complaint-form" class="panel complaint-form" data-id="${item?.id || ""}" data-version="${item?.version || ""}"><div class="section-title"><h2>민원 내용</h2><span><em>*</em> 필수 입력 항목</span></div><label for="title">제목 <em>*</em></label><input id="title" name="title" required maxlength="120" placeholder="민원 내용을 한눈에 알 수 있도록 작성해 주세요." value="${esc(value.title || "")}"><div class="field-hint"><span>이름, 연락처 등 개인정보는 제목에 적지 마세요.</span><span id="title-count">${(value.title || "").length}/120</span></div><div class="form-grid"><div><label for="category">민원 분야 <em>*</em></label><select id="category" name="category" required>${categories.map((c) => `<option ${c === (value.category || route.params.get("category")) ? "selected" : ""}>${c}</option>`).join("")}</select></div><div><label for="district">발생 지역 <em>*</em></label><select id="district" name="district" required><option value="">지역을 선택해 주세요</option>${districts.map((d) => `<option ${d === value.district ? "selected" : ""}>${d}</option>`).join("")}</select></div></div><label for="body">상세 내용 <em>*</em></label><textarea id="body" name="body" rows="9" required minlength="10" maxlength="2000" placeholder="어디에서, 언제, 어떤 일이 있었나요?&#10;구체적인 상황과 요청 사항을 작성해 주시면 검토에 도움이 됩니다.">${esc(value.body || "")}</textarea><div class="field-hint"><span>최소 10자 이상 작성해 주세요. 첨부파일은 후속 지원 예정입니다.</span><span id="body-count">${(value.body || "").length}/2,000</span></div><label>공개 범위</label><div class="radio-cards"><label><input type="radio" name="visibility" value="private" ${value.visibility !== "public" ? "checked" : ""}><span><b>${icon("shield", 16)} 비공개</b><small>나와 담당자만 확인할 수 있어요.</small></span></label><label><input type="radio" name="visibility" value="public" ${value.visibility === "public" ? "checked" : ""}><span><b>${icon("user", 16)} 공개</b><small>다른 시민도 내용을 볼 수 있어요.</small></span></label></div><div class="consent"><label><input type="checkbox" name="consent" required> 시연용 데이터 저장 및 공식 민원 미접수 안내를 확인했습니다. <em>*</em></label></div><div class="form-footer">${link("취소", "/citizen/mine", "btn")}${button("임시 저장", "", 'type="button" data-action="save-form"')}${button(`${item ? "수정 내용 저장" : "민원 등록하기"} ${icon("arrow", 17)}`, "primary", 'type="submit"')}</div></form></div>`;
}
/**
 * missing 화면 동작을 구성합니다.
 *
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
function missing() {
  return `<div class="page-content"><div class="empty panel">${icon("file", 40)}<h1>민원을 찾을 수 없습니다</h1><p>삭제된 민원이거나 현재 계정으로 열람할 수 없습니다.</p>${link("목록으로 돌아가기", route.staff ? "/staff/complaints" : "/citizen/board", "btn primary")}</div></div>`;
}
/**
 * detail 화면 동작을 구성합니다.
 *
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
function detail() {
  const id = route.path.split("/").at(-1);
  const c = data.complaints.find(
    (c) =>
      c.id === id &&
      c.status !== "withdrawn" &&
      (route.staff || c.owner === "citizen-demo" || c.visibility === "public"),
  );
  if (!c) return missing();
  const owner = c.owner === "citizen-demo";
  return `<div class="page-content">${!route.staff && newlyCreatedId === c.id ? `<div class="citizen-receipt" role="status"><span>${icon("check", 24)}</span><div><b>시연 서버에 민원이 등록되었어요</b><p>${c.id} · 청주시 공식 접수는 아닙니다.</p></div><button data-action="close-receipt" aria-label="등록 확인 닫기">${icon("close", 17)}</button></div>` : ""}<a class="back-link" href="#/${route.staff ? "staff/complaints" : "citizen/board"}">← 민원 목록으로</a><div class="detail-heading"><div><div class="eyebrow">${c.id} <span>·</span> ${c.visibility === "private" ? "비공개 민원" : "공개 시연 민원"}</div><h1>${esc(c.title)}</h1><p>${esc(c.district)} <span>·</span> ${esc(c.category)} <span>·</span> ${date(c.date)} <span>·</span> 내용 버전 ${c.contextVersion}</p></div>${badge(c)}</div>${route.staff ? staffProcess(c) : ""}<div class="detail-grid ${route.staff ? "staff-detail" : ""}"><div>${route.staff ? staffReviewInfo(c) : ""}<section class="panel detail-body"><div class="section-title"><h2>${icon("file", 20)} 민원 내용</h2>${owner && !route.staff ? `<div class="inline-actions">${!c.published ? link("수정", `/citizen/write?edit=${c.id}`) : ""}<button data-action="withdraw" data-id="${c.id}">민원 철회</button></div>` : ""}</div><div class="prose">${esc(c.body)}</div><div class="detail-note">${icon("shield", 16)} ${c.visibility === "private" ? "비공개로 등록된 민원입니다." : "개인정보 없는 공개 시연 민원입니다."}</div></section><section class="panel answer-panel"><div class="section-title"><h2>${icon("chat", 20)} ${route.staff ? "현재 게시된 답변" : "답변 확인"}</h2>${c.published ? `<span class="origin-badge">${origin(c.published)}</span>` : ""}</div>${c.published ? `<div class="answer-person"><span class="avatar">김</span><div><b>김담당 <span>민원 검토 담당자 · 시연</span></b><small>${date(c.published.date)} 게시</small></div></div><div class="prose">${esc(c.published.text)}</div>${c.published.origin !== "staff" ? '<p class="answer-disclosure">AI가 작성한 초안을 담당자가 검토' + (c.published.origin === "ai_edited" ? "·수정" : "") + "한 답변입니다.</p>" : ""}` : `<div class="waiting-answer">${icon("clock", 30)}<h3>담당자가 민원을 살펴보고 있습니다</h3><p>검토를 마치면 이곳에서 답변을 확인할 수 있어요.<br>작성 중인 초안은 시민에게 공개되지 않습니다.</p></div>`}</section><section class="panel followup"><div class="section-title"><h2>추가 문의 <small>${c.messages.length}</small></h2></div>${c.messages.map((m) => `<div class="message"><b>${m.author === "staff" ? "김담당" : "시민님"}</b><span>${date(m.date)}</span><p>${esc(m.text)}</p></div>`).join("")}${owner && !route.staff ? `<form id="followup-form" data-id="${c.id}" data-version="${c.version}"><label class="sr-only" for="followup">추가 문의 내용</label><textarea id="followup" name="message" maxlength="2000" required placeholder="추가로 전하고 싶은 내용을 남겨주세요." rows="3"></textarea><div class="form-footer">${c.published ? button("담당자 재검토 요청", "", 'type="button" data-action="review" data-id="' + c.id + '"') : ""}${button("추가 문의 등록", "primary", 'type="submit"')}</div></form>` : '<p class="muted">민원 작성자의 추가 문의가 이곳에 표시됩니다.</p>'}</section></div><aside>${route.staff ? editor(c) : citizenProgress(c)}<section class="panel history-panel"><h2>처리 이력</h2><ol class="timeline">${c.history
    .slice()
    .reverse()
    .map((h) => `<li><b>${esc(h.text)}</b><time>${date(h.date)}</time></li>`)
    .join("")}</ol></section></aside></div></div>`;
}
/**
 * citizenProgress 화면 동작을 구성합니다.
 *
 * @param {object} c 서버에서 조회한 민원입니다.
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
function citizenProgress(c) {
  const step =
    c.status === "submitted" ? 0 : c.status === "under_review" ? 1 : 2;
  return `<section class="panel progress-panel"><h2>민원 처리 현황</h2><ol class="progress-list">${[
    ["민원 등록", "시연 서비스에 저장되었어요"],
    ["담당자 검토", "내용과 필요한 조치를 살펴봐요"],
    ["답변 확인", "게시된 답변을 확인해 주세요"],
  ]
    .map(
      ([title, sub], i) =>
        `<li class="${i < step || c.status === "closed" ? "done complete" : i === step ? "done current" : ""}"><span>${i < step ? icon("check", 14) : i + 1}</span><div><b>${title}</b><small>${sub}</small></div></li>`,
    )
    .join(
      "",
    )}</ol><p class="muted">공식 행정 접수·배정과 구분되는<br>시연 서비스 내 처리 상태입니다.</p></section>`;
}
/**
 * editor 화면 동작을 구성합니다.
 *
 * @param {object} c 서버에서 조회한 민원입니다.
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
function editor(c) {
  return `<section class="panel editor-panel"><div class="section-title"><h2>${icon("spark", 19)} 답변 검토·편집</h2><span class="mini-chip">시민 비공개</span></div><div class="editor-status"><span class="badge under_review">검토 우선</span><span>초안 v${c.draftVersion}</span></div><div class="assign-row"><span>담당자</span><b>${c.assigned ? "김담당" : "미지정"}</b>${button(c.assigned ? "담당 해제" : "내가 담당", "", 'data-action="assign" data-id="' + c.id + '"')}</div><form id="answer-form" data-id="${c.id}" data-version="${c.version}" data-context="${c.contextVersion}" data-draft="${c.draftVersion}"><label for="answer">시민에게 안내할 답변</label><textarea id="answer" name="answer" required maxlength="4000" rows="13" placeholder="검토한 내용을 바탕으로 답변을 작성해 주세요.">${esc(c.draft)}</textarea><p class="field-hint">${c.aiOriginal ? "AI 작성 기원과 원본을 보존합니다." : "담당자가 직접 작성하는 답변입니다."}</p><label for="reason">수정·게시 사유 <em>*</em></label><input id="reason" name="reason" required maxlength="200" placeholder="예: 현장 확인 필요 사항을 보완함"><div class="editor-buttons">${button("초안 저장", "", 'type="submit"')}${button("미리보기·게시", "primary", 'type="button" data-action="preview-answer"')}</div></form><div class="editor-tools">${button(`${icon("book", 15)} AI 원문·이력`, "", 'data-action="compare" data-id="' + c.id + '"')}${button(`${icon("refresh", 15)} AI 시연 재실행`, "", 'data-action="retry" data-id="' + c.id + '" ' + (c.job.status === "running" ? "disabled" : ""))}</div><div class="evidence-note">${icon("help", 17)}<span>검색·LLM 미연동 상태입니다. 공식 FAQ 근거와 부서 후보는 생성하지 않습니다.</span></div>${c.published ? button("게시 답변 철회", "danger subtle", 'data-action="retract" data-id="' + c.id + '"') : ""}</section>`;
}
/**
 * dashboard 화면 동작을 구성합니다.
 *
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
function dashboard() {
  return staffQueue(data, route.params, { landing: true });
}
/**
 * monitor 화면 동작을 구성합니다.
 *
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
function monitor() {
  const filter = route.params.get("job") || "";
  const rows = data.complaints.filter(
    (c) => c.status !== "withdrawn" && (!filter || c.job.status === filter),
  );
  return `<div class="page-content">${pageHeading("AI WORKSPACE", "AI 작업 모니터", "검색부터 검토 대기까지, AI 작업의 단계와 이력을 확인하세요.", `<span class="connection"><i></i> 서버 단계 시연</span>`)}<div class="info-banner amber">${icon("help", 20)}<span><b>실제 AI·SSE 미연동 · 서버 폴링</b> · 재실행 단계와 이벤트는 서버에 저장됩니다. 진행률과 검색 근거를 생성하지 않습니다.</span></div><div class="monitor-toolbar">${[
    ["", "전체 작업"],
    ["queued", "실행 대기"],
    ["running", "실행 중"],
    ["succeeded", "완료"],
    ["failed", "실패"],
    ["cancelled", "취소"],
    ["superseded", "입력 변경"],
  ]
    .map(([value, label]) =>
      link(
        label,
        `/staff/monitor${value ? "?job=" + value : ""}`,
        `btn ${value === filter ? "primary" : ""}`,
      ),
    )
    .join(
      "",
    )}<span class="muted">총 ${rows.length}건</span></div><div class="job-grid">${rows.map((c) => `<section class="panel job-card"><div class="job-card-top"><span class="mono">${c.id}</span><span class="badge job-${c.job.status}">${{ queued: "실행 대기", running: "실행 중", succeeded: "완료", failed: "실패", cancelled: "취소", superseded: "입력 변경" }[c.job.status] || c.job.status}</span></div><h2>${esc(c.title)}</h2><p class="job-meta">작업 ${c.id}-A${c.job.attempt} · 입력 v${c.job.contextVersion || c.contextVersion} · 시도 ${c.job.attempt}</p><div class="job-stage">${icon(c.job.status === "running" ? "refresh" : "monitor", 19)}<b>${esc(c.job.stage)}</b></div><div class="stage-steps">${["검색", "판정", "작성", "검증"].map((s) => `<span class="${c.job.events.some((e) => e.stage.includes(s)) ? "done" : ""}">${s}</span>`).join("")}</div><p class="job-updated">마지막 이벤트 · ${new Date(c.job.events.at(-1).date).toLocaleTimeString("ko-KR")}</p><div class="job-actions">${link("민원 열기", `/staff/detail/${c.id}`, "btn")}${button("이력", "", 'data-action="job-history" data-id="' + c.id + '"')}${button(c.job.status === "running" ? "취소" : "시연 재실행", c.job.status === "running" ? "danger" : "primary subtle", `data-action="${c.job.status === "running" ? "cancel-job" : "retry"}" data-id="${c.id}"`)}</div></section>`).join("")}</div>${!rows.length ? '<div class="panel empty"><h2>해당 상태의 작업이 없습니다</h2><p>다른 필터를 선택하거나 민원에서 시연 작업을 실행하세요.</p></div>' : ""}</div>`;
}
/**
 * assistant 화면 동작을 구성합니다.
 *
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
function assistant() {
  return `<div class="page-content assistant-page"><a class="back-link" href="#/citizen">← 홈으로</a><section class="panel chat-panel"><div class="chat-heading"><span class="citizen-chat-avatar">${icon("spark", 24)}</span><div><h1>민원 도우미</h1><small><i></i> 편하게 이야기해 주세요 · 상담 흐름 시연</small></div><span class="mini-chip">AI 미연동</span></div><div class="chat-messages" aria-live="polite"><div class="chat-bubble ai"><b>안녕하세요! 불편하신 점을<br>평소 말하듯이 알려주세요 🙂</b><p>어느 부서에 문의할지 몰라도 괜찮아요.<br>일상에서 겪은 일을 편하게 들려주세요.</p><small>현재는 고정 응답으로 상담 흐름을 체험하는 시연입니다. 정책 판단과 부서 배정은 담당자 확인이 필요합니다.</small></div>${chatMessages.map((m) => `<div class="chat-bubble ${m.role}">${esc(m.text)}${m.role === "ai" ? `<section class="citizen-ai-card"><header>${icon("spark", 15)} 민원 작성 안내 <span>시연</span></header><dl><div><dt>접수 내용</dt><dd>${esc(m.source || "말씀하신 내용")}</dd></div><div><dt>다음 단계</dt><dd>발생 위치와 요청 사항을 보완해 주세요.</dd></div><div><dt>검토 안내</dt><dd>정책·담당 부서는 담당자 확인이 필요해요.</dd></div></dl><button class="btn primary" data-action="citizen-use-draft" data-text="${esc(m.source || "")}">이 내용으로 민원 작성 ${icon("arrow", 16)}</button></section>` : ""}</div>`).join("")}${chatPending ? '<div class="chat-bubble ai citizen-typing" role="status" aria-label="시연 답변 준비 중"><i></i><i></i><i></i><span>내용을 정리하고 있어요</span></div>' : ""}</div>${!chatMessages.length ? `<div class="suggestions">${["전입신고에 필요한 서류를 문의하고 싶어요", "우리집 앞 가로등이 밤새 깜빡거려요", "놀이터 그네가 부서졌어요"].map((s) => button(s, "", 'data-action="chat-suggest" data-text="' + s + '"')).join("")}</div>` : ""}<div class="citizen-chat-tools"><button data-action="citizen-chat-help">${icon("book", 14)} 작성 요령</button><span>${icon("shield", 14)} 개인정보 입력 주의</span>${link("직접 작성하기", "/citizen/write")}</div><form id="chat-form" class="chat-input"><label class="sr-only" for="chat-input">도우미에게 보낼 내용</label><input id="chat-input" name="message" required maxlength="2000" placeholder="예) 우리집 앞 가로등이 깜빡거려요" ${chatPending ? "disabled" : ""}>${button(icon("arrow", 20), "primary", 'type="submit" aria-label="보내기" ' + (chatPending ? "disabled" : ""))}</form></section><p class="chat-disclaimer">${icon("shield", 14)} 실제 AI 미연동 · 민원 작성 후 확인해야 시연 서버에 등록돼요.</p></div>`;
}
/**
 * guide 화면 동작을 구성합니다.
 *
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
function guide() {
  return `<div class="page-content narrow">${pageHeading("HOW TO USE", "청주톡톡, 이렇게 이용하세요", "목소리를 남기고, 답변을 확인하는 세 가지 단계.")}<div class="guide-steps">${[
    [
      "file",
      "01",
      "민원을 작성해 주세요",
      "제목과 상세 내용, 발생 지역을 작성해 주세요. 공개 범위는 비공개가 기본이며, 개인정보는 입력하지 마세요.",
    ],
    [
      "shield",
      "02",
      "담당자가 꼼꼼히 살펴봐요",
      "AI 초안은 담당자 검토를 거쳐 게시됩니다. 업무 데이터는 서버에 저장되며 AI는 단계 시연으로 확인할 수 있습니다.",
    ],
    [
      "chat",
      "03",
      "답변을 확인하고 이어가세요",
      "내 민원에서 게시된 답변을 확인하세요. 궁금한 내용은 추가 문의로 남기거나 담당자 재검토를 요청할 수 있습니다.",
    ],
  ]
    .map(
      ([ic, n, title, body]) =>
        `<section class="panel guide-step"><span class="quick-icon">${icon(ic, 28)}</span><div class="eyebrow">STEP ${n}</div><h2>${title}</h2><p>${body}</p></section>`,
    )
    .join(
      "",
    )}</div><section class="panel faq-panel"><h2>자주 묻는 이용 질문</h2>${[
    [
      "실제 청주시 민원으로 접수되나요?",
      "아니요. 이 서비스는 Flask 서버 기반 시연이며, 청주시 공식 접수·외부 행정 이관과 연결되어 있지 않습니다.",
    ],
    [
      "등록한 내용은 어디에 저장되나요?",
      "민원과 답변은 Flask 서버의 별도 SQLite DB에 저장되어 브라우저를 새로 열어도 유지됩니다. 작성 전 임시 입력만 이 탭에 저장합니다. 기존 localStorage 자료는 자동 업로드하지 않습니다.",
    ],
    [
      "AI가 바로 답변하나요?",
      "현재 실제 LLM과 검색 API는 연결되어 있지 않습니다. 작업 재실행은 서버 단계 시뮬레이션이며, 초안은 담당자가 명시적으로 게시하기 전까지 시민 화면에 표시하지 않습니다.",
    ],
    [
      "민원을 수정하거나 철회할 수 있나요?",
      "본인 민원은 답변 게시 전 수정할 수 있습니다. 답변 후에는 추가 문의로 정정해 주세요. 철회하면 목록에서 숨겨지고 이력은 서버 DB에 보존됩니다.",
    ],
    [
      "시민·담당자 전환은 로그인인가요?",
      "로컬 시연 계정을 선택해 서명된 세션 쿠키를 설정합니다. 서버가 역할·작성자를 검사하지만, 실제 본인인증이나 운영용 담당자 로그인은 아닙니다.",
    ],
  ]
    .map(
      ([q, a]) =>
        `<details><summary>${q}${icon("plus", 17)}</summary><p>${a}</p></details>`,
    )
    .join(
      "",
    )}</section><div class="center-action">${link(`첫 민원 작성하기 ${icon("arrow", 17)}`, "/citizen/write", "btn primary")}</div></div>`;
}
/**
 * 경로별 화면을 생성하고 잘못된 저장 데이터는 초기화 없이 오류로 표시합니다.
 *
 * @returns {void} 반환값 없이 화면 상태를 갱신합니다.
 */
function render() {
  const oldEditor = $("#answer-form");
  const editing = oldEditor
    ? {
        id: oldEditor.dataset.id,
        context: oldEditor.dataset.context,
        draftVersion: oldEditor.dataset.draft,
        text: oldEditor.elements.answer.value,
        reason: oldEditor.elements.reason.value,
        focus: document.activeElement?.id,
        start: document.activeElement?.selectionStart,
        end: document.activeElement?.selectionEnd,
      }
    : null;
  route = currentRoute();
  data = read();
  let content;
  if (route.path === "/citizen") content = home();
  else if (
    ["/citizen/board", "/citizen/mine", "/staff/complaints"].includes(
      route.path,
    )
  )
    content = board(route.staff);
  else if (route.path === "/citizen/write") content = writeForm();
  else if (/^\/(citizen|staff)\/detail\//.test(route.path)) content = detail();
  else if (route.path === "/staff") content = dashboard();
  else if (route.path === "/staff/monitor") content = monitor();
  else if (route.path === "/citizen/assistant") content = assistant();
  else if (route.path === "/citizen/guide") content = guide();
  else if (route.path === "/citizen/services") content = citizenServicesPage();
  else if (route.path === "/citizen/news") content = citizenNewsPage();
  else if (route.path === "/citizen/updates") content = citizenUpdates(data);
  else if (route.path === "/citizen/profile") content = citizenProfile(data);
  else content = missing();
  app.innerHTML = shell(content);
  const newEditor = $("#answer-form");
  if (
    editing &&
    newEditor &&
    newEditor.dataset.id === editing.id &&
    newEditor.dataset.context === editing.context &&
    newEditor.dataset.draft === editing.draftVersion
  ) {
    newEditor.elements.answer.value = editing.text;
    newEditor.elements.reason.value = editing.reason;
    if (editing.focus === "answer" || editing.focus === "reason") {
      const field = document.getElementById(editing.focus);
      field.focus({ preventScroll: true });
      field.setSelectionRange(editing.start, editing.end);
    }
  }
  document.title = `${route.staff ? "담당자 업무 포털" : "청주톡톡"} · 시민의 목소리에 더 가까이`;
}
/**
 * updateFilter 화면 동작을 구성합니다.
 *
 * @param {Object} changes 변경할 검색 조건입니다.
 * @returns {void} 반환값 없이 화면 상태를 갱신합니다.
 */
function updateFilter(changes) {
  const params = new URLSearchParams(route.params);
  for (const [key, value] of Object.entries(changes)) {
    if (value) params.set(key, value);
    else params.delete(key);
  }
  location.hash = route.path + (params.size ? "?" + params : "");
}
/**
 * sendChat 화면 동작을 구성합니다.
 *
 * @param {string} text 사용자가 입력한 상담 내용입니다.
 * @returns {void} 반환값 없이 화면 상태를 갱신합니다.
 */
function sendChat(text) {
  if (chatPending || !text.trim()) return;
  chatMessages.push({ role: "me", text: text.trim() });
  chatPending = true;
  render();
  setTimeout(() => {
    try {
      sessionStorage.setItem(
        "complaint-form",
        JSON.stringify({
          title: text.slice(0, 120),
          body: text,
          district: "모름",
          visibility: "private",
        }),
      );
    } catch {
      toast("임시 입력을 저장하지 못했습니다.");
    }
    chatMessages.push({
      role: "ai",
      source: text,
      text: "말씀하신 내용을 작성 화면에 옮길 수 있어요. 구체적인 위치와 요청 사항을 확인한 뒤 민원을 등록해 주세요.",
    });
    chatPending = false;
    if (currentRoute().path === "/citizen/assistant") {
      render();
      $(".chat-messages")?.lastElementChild?.scrollIntoView({
        block: "nearest",
        behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "instant"
          : "smooth",
      });
    }
  }, 850);
}

document.addEventListener("click", async (event) => {
  const target = event.target.closest("[data-action]");
  if (!target || busy) return;
  const action = target.dataset.action,
    id = target.dataset.id;
  const c = id ? data.complaints.find((row) => row.id === id) : null;
  const command = (suffix, body = {}, method = "POST") =>
    api("/complaints/" + encodeURIComponent(id) + suffix, {
      method,
      body: { version: c.version, ...body },
    });
  if (action === "citizen-service") {
    citizenPrompt = target.dataset.prompt;
    location.hash = "/citizen/assistant";
    return;
  }
  if (action === "citizen-use-draft") {
    try {
      sessionStorage.setItem(
        "complaint-form",
        JSON.stringify({
          title: target.dataset.text.slice(0, 120),
          body: target.dataset.text,
          district: "모름",
          visibility: "private",
        }),
      );
      location.hash = "/citizen/write";
    } catch {
      toast("작성 내용을 옮기지 못했습니다. 입력 내용을 보관해 주세요.");
    }
    return;
  }
  if (action === "citizen-notice") {
    const notice = citizenNotices.find((n) => n.id === id);
    if (!notice) return;
    openModal(
      esc(notice.title),
      `<div class="modal-content citizen-notice-sheet"><div class="citizen-sheet-tags"><span>${notice.tag}</span><span>${notice.category}</span><em>시연 이용 안내</em></div><p>${esc(notice.body)}</p><div class="citizen-sheet-note">이 안내는 서비스 이용을 돕기 위한 시연 콘텐츠입니다. 실제 공사·행사 일정이나 공식 정책 안내가 아닙니다.</div><div class="form-footer">${button("닫기", "", 'type="button" data-action="close-modal"')}${button("이 내용으로 문의", "primary", 'type="button" data-action="citizen-service" data-prompt="' + esc(notice.prompt) + '"')}</div></div>`,
    );
    return;
  }
  if (action === "citizen-chat-help") {
    openModal(
      "이렇게 이야기해 주세요",
      `<div class="modal-content"><p>어디에서, 언제, 어떤 불편을 겪으셨나요?<br>상황과 요청 사항을 구체적으로 적어 주시면 검토에 도움이 됩니다.</p><p>실제 이름·연락처 등 개인정보는 입력하지 마세요. 현재 시연에는 자동 마스킹·첨부파일·문자 발송 기능이 없습니다.</p>${button("확인했어요", "primary", 'data-action="close-modal"')}</div>`,
    );
    return;
  }
  if (action === "close-receipt") {
    newlyCreatedId = null;
    render();
    return;
  }
  if (action === "theme-toggle") {
    setTheme(getTheme() === "dark" ? "light" : "dark");
    return;
  }
  if (action === "staff-menu-toggle" || action === "staff-menu-close") {
    const opening =
      action === "staff-menu-toggle" &&
      !document.body.classList.contains("staff-menu-open");
    document.body.classList.toggle("staff-menu-open", opening);
    document
      .querySelector(".staff-menu-toggle")
      ?.setAttribute("aria-expanded", String(opening));
    if (opening)
      setTimeout(() => {
        if (document.body.classList.contains("staff-menu-open"))
          document
            .querySelector(".staff-sidebar nav a")
            ?.focus({ preventScroll: true });
      }, 220);
    else document.querySelector(".staff-menu-toggle")?.focus();
    return;
  }
  if (action === "staff-help") {
    openModal(
      "민원과 업무 이용 안내",
      `<div class="modal-content"><p>접수 대기·검토 목록에서 민원을 선택하고, 담당자 지정과 원문 확인을 진행하세요.</p><p>초안을 저장한 뒤 미리보기에서 시민에게 표시될 내용을 확인하고 게시할 수 있습니다. AI 원본과 수정 이력은 보존됩니다.</p><p>업무 상태·AI 작업·게시 여부는 다릅니다. 실제 AI·자동 부서 배정·법정기한·감사 로그·공식 이관은 연결되지 않은 로컬 시연입니다.</p>${button("확인", "primary", 'data-action="close-modal"')}</div>`,
    );
    return;
  }
  if (action === "skip-main") {
    event.preventDefault();
    $("#main")?.focus();
    return;
  }
  if (action === "close-modal") {
    modal.close();
    return;
  }
  if (action === "reload") {
    await loadScreen();
    return;
  }
  if (action === "notifications") {
    openModal(
      "시연 서비스 알림",
      `<div class="modal-content"><p>답변이 게시되면 내 민원에서 확인할 수 있습니다. 민원과 답변은 Flask 서버 DB에 저장됩니다. 외부 알림은 미연동입니다.</p>${link("내 민원 확인하기", "/citizen/mine", "btn primary")}</div>`,
    );
    return;
  }
  if (action === "filter-status") {
    updateFilter({ status: target.dataset.value, page: "" });
    return;
  }
  if (action === "reset-filters") {
    location.hash = route.path;
    return;
  }
  if (action === "page") {
    updateFilter({ page: target.dataset.page });
    return;
  }
  if (action === "chat-suggest") {
    sendChat(target.dataset.text);
    return;
  }
  if (action === "save-form") {
    try {
      sessionStorage.setItem(
        "complaint-form",
        JSON.stringify(Object.fromEntries(new FormData($("#complaint-form")))),
      );
      toast("이 탭에 입력 내용을 임시 저장했습니다.");
    } catch {
      toast("임시 저장에 실패했습니다. 입력 내용을 보관해 주세요.");
    }
    return;
  }
  if (action === "assign") {
    await perform(
      () => command("/assignment", { assigned: !c.assigned }, "PUT"),
      "담당자 정보를 서버에 저장했습니다.",
    );
    return;
  }
  if (action === "review") {
    await perform(() => command("/review"), "재검토 요청을 저장했습니다.");
    return;
  }
  if (action === "retry") {
    await perform(
      () => command("/jobs"),
      "서버 단계 시연을 시작했습니다. 기존 편집본은 유지됩니다.",
    );
    return;
  }
  if (action === "cancel-job") {
    await perform(
      () => command("/jobs/cancel"),
      "서버 시연 작업을 취소했습니다.",
    );
    return;
  }
  if (action === "withdraw" || action === "retract") {
    openModal(
      action === "withdraw"
        ? "민원을 철회하시겠어요?"
        : "게시 답변을 철회하시겠어요?",
      `<form id="confirm-form" class="modal-content" data-id="${id}" data-version="${c.version}" data-kind="${action}"><p>현재 목록 또는 게시 화면에서 숨겨집니다. 서버 DB의 이전 본문과 변경 이력은 보존됩니다.</p><label for="confirm-reason">철회 사유</label><input id="confirm-reason" name="reason" required maxlength="200" placeholder="철회 사유를 입력해 주세요"><div class="form-footer">${button("취소", "", 'type="button" data-action="close-modal"')}${button("철회하기", "danger", 'type="submit"')}</div></form>`,
    );
    return;
  }
  if (action === "compare") {
    openModal(
      "AI 원문과 답변 이력",
      `<div class="modal-content"><span class="mini-chip">AI 원본 · 보존됨</span><div class="compare-box prose">${esc(c.aiOriginal || "AI 원본이 없습니다.")}</div>${c.aiCandidate ? `<h3>재실행 후보 · 편집본에 미적용</h3><div class="compare-box prose">${esc(c.aiCandidate)}</div>` : ""}<h3>저장·게시 이력 ${c.versions.length}개</h3>${
        c.versions
          .slice()
          .reverse()
          .map(
            (v) =>
              `<details><summary>v${v.version} · ${esc(v.kind)} · ${date(v.date)}</summary><p class="prose">${esc(v.text)}</p><small>사유: ${esc(v.reason)}</small></details>`,
          )
          .join("") || "<p>아직 저장한 편집 이력이 없습니다.</p>"
      }<p class="muted">실제 AI는 미연동입니다. 시연 후보는 현재 편집본에 자동 적용하지 않습니다.</p></div>`,
    );
    return;
  }
  if (action === "preview-answer") {
    const form = $("#answer-form");
    if (!form.reportValidity()) return;
    const text = form.elements.answer.value.trim(),
      reason = form.elements.reason.value.trim();
    if (!text || !reason) {
      toast("답변과 사유를 입력해 주세요.");
      return;
    }
    const complaint = data.complaints.find((row) => row.id === form.dataset.id);
    const answerOrigin = complaint.aiOriginal
      ? text === complaint.aiOriginal
        ? "ai"
        : "ai_edited"
      : "staff";
    openModal(
      "시민에게 표시될 답변 미리보기",
      `<form id="publish-form" class="modal-content" data-id="${form.dataset.id}" data-version="${form.dataset.version}"><span class="origin-badge">${origin({ origin: answerOrigin })}</span><div class="prose compare-box">${esc(text)}</div><input type="hidden" name="text" value="${esc(text)}"><input type="hidden" name="reason" value="${esc(reason)}"><p class="muted">서버가 권한·버전을 다시 검사한 뒤 게시합니다. 시연 서비스 내부 게시이며 공식 행정 접수와 구별됩니다.</p><div class="form-footer">${button("돌아가기", "", 'type="button" data-action="close-modal"')}${button("검토 완료·답변 게시", "primary", 'type="submit"')}</div></form>`,
    );
    return;
  }
  if (action === "job-history")
    openModal(
      "AI 작업 이벤트 이력",
      `<div class="modal-content"><p class="mono">${c.id}-A${c.job.attempt} · 서버 단계 시연</p><ol class="timeline">${c.job.events.map((e) => `<li><b>${esc(e.stage)}</b><time>${new Date(e.date).toLocaleString("ko-KR")}</time></li>`).join("")}</ol></div>`,
    );
});

document.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (busy) return;
  const form = event.target,
    values = Object.fromEntries(new FormData(form));
  if (form.id === "filters") {
    updateFilter({ ...values, page: "" });
    return;
  }
  if (form.id === "chat-form") {
    sendChat(values.message);
    return;
  }
  if (form.id === "complaint-form") {
    if (!values.title.trim() || values.body.trim().length < 10) {
      toast("제목과 10자 이상의 상세 내용을 입력해 주세요.");
      return;
    }
    const id = form.dataset.id;
    const body = {
      title: values.title,
      body: values.body,
      district: values.district,
      category: values.category,
      visibility: values.visibility,
    };
    let saved;
    form.dataset.key ||= crypto.randomUUID();
    const ok = await perform(
      async () => {
        saved = await api(id ? "/complaints/" + id : "/complaints", {
          method: id ? "PUT" : "POST",
          body: id ? { ...body, version: Number(form.dataset.version) } : body,
          headers: id ? {} : { "Idempotency-Key": form.dataset.key },
        });
      },
      "",
      false,
    );
    if (ok) {
      if (!id) newlyCreatedId = saved.id;
      sessionStorage.removeItem("complaint-form");
      location.hash = "/citizen/detail/" + saved.id;
      toast(
        id
          ? "수정 내용을 서버에 저장했습니다."
          : "시연 서버 DB에 민원을 등록했습니다. 공식 접수는 진행하지 않습니다.",
      );
    }
    return;
  }
  if (form.id === "followup-form") {
    if (!values.message.trim()) return;
    await perform(
      () =>
        api("/complaints/" + form.dataset.id + "/messages", {
          method: "POST",
          body: {
            version: Number(form.dataset.version),
            message: values.message,
          },
        }),
      "추가 문의를 서버에 저장했습니다.",
    );
    return;
  }
  if (form.id === "answer-form" || form.id === "publish-form") {
    const publish = form.id === "publish-form",
      text = (publish ? values.text : values.answer).trim(),
      reason = values.reason.trim();
    if (!text || !reason) {
      toast("답변과 사유를 입력해 주세요.");
      return;
    }
    const ok = await perform(
      () =>
        api(
          "/complaints/" + form.dataset.id + (publish ? "/publish" : "/draft"),
          {
            method: publish ? "POST" : "PUT",
            body: { version: Number(form.dataset.version), text, reason },
          },
        ),
      publish
        ? "답변을 서버에 게시했습니다. 시민 화면에서 확인할 수 있습니다."
        : "초안을 서버에 저장했습니다. 시민 API에는 포함하지 않습니다.",
    );
    if (ok && publish) modal.close();
    return;
  }
  if (form.id === "confirm-form") {
    if (!values.reason.trim()) return;
    const withdraw = form.dataset.kind === "withdraw";
    const ok = await perform(
      () =>
        api("/complaints/" + form.dataset.id + (withdraw ? "" : "/retract"), {
          method: withdraw ? "DELETE" : "POST",
          body: {
            version: Number(form.dataset.version),
            reason: values.reason,
          },
        }),
      "서버에 철회를 반영했습니다.",
      false,
    );
    if (ok) {
      modal.close();
      if (withdraw) location.hash = "/citizen/mine";
      else render();
    }
    return;
  }
});
document.addEventListener("input", (event) => {
  if (event.target.closest("#complaint-form"))
    delete $("#complaint-form").dataset.key;
  if (event.target.id === "title")
    $("#title-count").textContent = event.target.value.length + "/120";
  if (event.target.id === "body")
    $("#body-count").textContent = event.target.value.length + "/2,000";
});
document.addEventListener("click", (event) => {
  if (event.target.closest("#modal a[href]")) modal.close();
});
window.addEventListener("storage", (event) => {
  if (event.key === THEME_KEY)
    setTheme(event.newValue === "dark" ? "dark" : "light", false);
});
window.addEventListener("hashchange", () => {
  document.body.classList.remove("staff-menu-open");
  if (modal.open) modal.close();
  loadScreen();
  window.scrollTo(0, 0);
});
setInterval(async () => {
  if (
    busy ||
    document.hidden ||
    !currentRoute().staff ||
    !data?.complaints.some((c) => c.job?.status === "running")
  )
    return;
  try {
    const editor = $("#answer-form"),
      snapshot = await refresh();
    const latest = editor
      ? snapshot.complaints.find((c) => c.id === editor.dataset.id)
      : null;
    if (
      editor &&
      latest &&
      (String(latest.contextVersion) !== editor.dataset.context ||
        String(latest.draftVersion) !== editor.dataset.draft)
    ) {
      toast(
        "다른 요청에서 내용이 바뀌었습니다. 편집 내용을 보관한 뒤 새로고침해 주세요.",
      );
      return;
    }
    if (
      !modal.open &&
      !$("#complaint-form") &&
      !$("#followup-form textarea:focus")
    )
      render();
  } catch (error) {
    toast(error.message);
  }
}, 1500);
setTheme(readTheme(), false);
loadScreen();

modal.addEventListener("click", (event) => {
  if (event.target !== modal) return;
  const rect = modal.getBoundingClientRect();
  if (
    event.clientX < rect.left ||
    event.clientX > rect.right ||
    event.clientY < rect.top ||
    event.clientY > rect.bottom
  )
    modal.close();
});

document.addEventListener("keydown", (event) => {
  if (!document.body.classList.contains("staff-menu-open")) return;
  if (event.key === "Escape") {
    document.querySelector(".staff-drawer-close")?.click();
    return;
  }
  if (event.key !== "Tab") return;
  const fields = [
    ...document.querySelectorAll(".staff-sidebar a,.staff-sidebar button"),
  ].filter(
    (el) =>
      el.getClientRects().length &&
      getComputedStyle(el).visibility !== "hidden",
  );
  const first = fields[0],
    last = fields.at(-1);
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last?.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first?.focus();
  }
});
