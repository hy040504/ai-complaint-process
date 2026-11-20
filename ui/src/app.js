import { icon } from "./icons.js";
import { THEME_KEY, readTheme, getTheme, setTheme } from "./theme.js";
import {
  backendSwaggerPage,
  renderApiEndpointListHtml,
  summarizeOpenApiSpec,
} from "./api-docs.js";
import {
  staffShell,
  staffQueue,
  staffProcess,
  staffReviewInfo,
  daysSince,
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
  getActor,
  ensureRoleSession,
  loginAccount,
  logoutAccount,
  requestCitizenVerify,
  registerCitizenAccount,
  visible,
  statusNames,
  districts,
  categories,
} from "./store.js";
import { renderAuthModalHtml } from "./auth.js";
import {
  labExamples,
  labFields,
  labPage,
  labQuery,
  labResult,
  labShell,
  loadLabExamples,
  loadLabFields,
  runLabAssist,
  selectedLabProvider,
  setSelectedLabProvider,
} from "./lab.js";
import {
  PROVIDER_SHORT_LABELS,
  ROLE_PROMPT_NAMES,
  buildDepartmentOptionsHtml,
  buildProviderOptionsHtml,
  resolveLlmMeta,
} from "./llm-meta.js";
import { createStaffEventStream, renderSseStatusBadge } from "./realtime.js";
import {
  buildCitizenDraftPayload,
  renderCitizenChatBubble,
  streamCitizenChat,
} from "./chatbot.js";

const app = document.querySelector("#app");
const modal = document.querySelector("#modal");
/**
 * 지정한 범위(기본값 `document`)에서 CSS 선택자에 맞는 첫 요소를 찾습니다.
 *
 * @param {string} s CSS 선택자 문자열입니다.
 * @param {ParentNode} [parent=document] 탐색 기준 루트 노드입니다.
 * @returns {Element|null} 일치한 첫 번째 요소 또는 null입니다.
 */
const $ = (s, parent = document) => parent.querySelector(s);
/** 서버 연결 전 또는 복원 기준으로 쓰는 기본 답변 템플릿 5종입니다. */
const FALLBACK_TEMPLATES = [
  {
    id: "TPL-DEF-1",
    title: "검토 결과 인사",
    content: "안녕하십니까. 접수하신 민원의 검토 결과를 안내드립니다.",
    isDefault: true,
  },
  {
    id: "TPL-DEF-2",
    title: "불편 사과",
    content: "불편을 드려 죄송합니다.",
    isDefault: true,
  },
  {
    id: "TPL-DEF-3",
    title: "추가 조사·부서 전달",
    content: "확인 과정에서 추가 조사가 필요하여 담당 부서에 전달하였습니다.",
    isDefault: true,
  },
  {
    id: "TPL-DEF-4",
    title: "추가 문의 안내",
    content: "추가 문의가 있으시면 민원 상세 화면의 추가 문의로 남겨 주세요.",
    isDefault: true,
  },
  {
    id: "TPL-DEF-5",
    title: "맺음말 감사",
    content: "감사합니다.",
    isDefault: true,
  },
];
let staffDepartments = [];
let answerTemplates = [...FALLBACK_TEMPLATES];
let templatesLoaded = false;

/**
 * 담당자 부서 배정에 사용할 청주시 현행 부서 목록을 서버에서 불러옵니다.
 *
 * 한 번 로드한 현행 부서 목록은 메모리 캐시를 재사용해 반복 HTTP 요청을 줄입니다.
 *
 * @param {boolean} [force=false] 캐시를 무시하고 서버에서 다시 불러올지 여부입니다.
 * @returns {Promise<Array<object>>} 부서 목록입니다.
 */
async function loadStaffDepartments(force = false) {
  if (!force && staffDepartments.length) return staffDepartments;
  const res = await api("/departments");
  staffDepartments = Array.isArray(res?.departments) ? res.departments : [];
  return staffDepartments;
}

let backendHealth = null;
let openApiSpec = null;
let openApiSummary = null;
let apiDocsLoading = false;
let apiDocsError = "";
let apiDocsTab = "swagger";
let apiDocsTag = "";
let apiDocsQuery = "";

/**
 * 담당자 API 문서 화면용 헬스 상태와 OpenAPI 3.1 명세를 불러옵니다.
 *
 * @param {boolean} [force=false] 캐시된 OpenAPI 명세를 무시하고 다시 조회할지 여부입니다.
 * @returns {Promise<void>} 명세·상태 로딩 완료 프로미스입니다.
 */
async function loadBackendApiDocs(force = false) {
  apiDocsLoading = true;
  apiDocsError = "";
  try {
    const [healthRes, specRes] = await Promise.all([
      api("/health").catch(() => null),
      !force && openApiSpec
        ? Promise.resolve(openApiSpec)
        : fetch("/openapi/openapi.json", { credentials: "same-origin" }).then(
            async (res) => {
              if (!res.ok)
                throw new Error(`OpenAPI 명세 조회 실패 (${res.status})`);
              return res.json();
            },
          ),
    ]);
    if (healthRes) backendHealth = healthRes;
    if (specRes) {
      if (force || specRes !== openApiSpec || !openApiSummary) {
        openApiSummary = summarizeOpenApiSpec(specRes);
      }
      openApiSpec = specRes;
    }
  } catch (err) {
    apiDocsError = err?.message || "API 명세를 불러오지 못했습니다.";
  } finally {
    apiDocsLoading = false;
  }
}

/**
 * 담당자 답변 편집기용 템플릿 목록을 서버에서 불러옵니다.
 *
 * @param {boolean} [force=false] 캐시를 무시하고 서버에서 최신 목록을 다시 조회할지 여부입니다.
 * @returns {Promise<Array<object>>} 저장된 답변 템플릿 목록입니다.
 */
async function loadAnswerTemplates(force = false) {
  if (!force && templatesLoaded) return answerTemplates;
  const res = await api("/templates");
  if (Array.isArray(res?.templates)) {
    answerTemplates = res.templates;
    templatesLoaded = true;
  }
  return answerTemplates;
}
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
let chatLiveLabel = "";
let chatDistrict = "";
let citizenPrompt = null;
let newlyCreatedId = null;
let busy = false;
let loadSequence = 0;
let sseState = "idle";
let sseLastEventAt = null;
let sseAiConnected = true;
let staffSyncPending = false;
let staffSyncQueued = false;
let authModalTab = "citizen-login";
let authVerifyChallenge = null;
let authModalError = "";

/**
 * 계정 로그인·시민 본인확인 모달을 지정한 탭으로 엽니다.
 *
 * @param {string} [tab] 초기 활성 탭(`citizen-login`·`citizen-register`·`staff-login`)입니다.
 * @returns {void}
 */
function openAuthModal(tab) {
  authModalTab = tab || (route?.staff ? "staff-login" : "citizen-login");
  authModalError = "";
  openModal(
    "계정 로그인 · 본인확인",
    renderAuthModalHtml({
      tab: authModalTab,
      verifyChallenge: authVerifyChallenge,
      actor: getActor(),
      error: authModalError,
    }),
  );
}

/**
 * 서버의 최신 담당자 스냅샷을 조회해 안전하게 화면을 갱신합니다.
 *
 * 편집 중인 `#answer-form` 초안을 덮어쓰지 않으며, 동시 이벤트가 몰릴 때는
 * 한 번의 후속 조회로 합쳐 중복 HTTP 호출을 방지합니다.
 *
 * @returns {Promise<void>} 스냅샷 동기화 완료 프로미스입니다.
 */
async function syncStaffFromServer() {
  if (busy || !currentRoute().staff) return;
  if (staffSyncPending) {
    staffSyncQueued = true;
    return;
  }
  staffSyncPending = true;
  try {
    const editorForm = $("#answer-form");
    const snapshot = await refresh();
    const latest = editorForm
      ? snapshot.complaints.find((c) => c.id === editorForm.dataset.id)
      : null;
    if (
      editorForm &&
      latest &&
      (String(latest.contextVersion) !== editorForm.dataset.context ||
        String(latest.draftVersion) !== editorForm.dataset.draft)
    ) {
      toast(
        "다른 요청에서 내용이 바뀌었습니다. 편집 내용을 보관한 뒤 새로고침해 주세요.",
      );
      return;
    }
    if (
      !modal.open &&
      !$("#complaint-form") &&
      !$("#followup-form textarea:focus") &&
      currentRoute().path !== "/staff/api"
    ) {
      render();
    }
  } catch (error) {
    toast(error.message);
  } finally {
    staffSyncPending = false;
    if (staffSyncQueued) {
      staffSyncQueued = false;
      syncStaffFromServer();
    }
  }
}

/** 담당자 실시간 AI 작업·민원 변경 SSE 구독 관리자입니다. */
const staffStream = createStaffEventStream({
  onEvent: (_type, payload) => {
    sseLastEventAt = payload?.occurredAt || new Date().toISOString();
    syncStaffFromServer();
  },
  onResync: () => {
    syncStaffFromServer();
  },
  onStateChange: (nextState, detail) => {
    sseState = nextState;
    if (detail?.lastEventAt) sseLastEventAt = detail.lastEventAt;
    if (typeof detail?.aiConnected === "boolean") {
      sseAiConnected = detail.aiConnected;
    }
    const badgeEl = $("#staff-sse-status");
    if (badgeEl) {
      badgeEl.outerHTML = renderSseStatusBadge(sseState, sseLastEventAt).replace(
        "<span ",
        '<span id="staff-sse-status" ',
      );
    }
  },
});

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
 * 검사기 응대를 실행하고 결과 영역으로 이동합니다.
 *
 * @param {{query:string,district?:string|null,limit?:number}} body 요청 본문입니다.
 * @returns {Promise<void>} 비동기 작업의 완료 결과입니다.
 */
async function completeLabAssist(body) {
  if (busy) return;
  busy = true;
  app.setAttribute("aria-busy", "true");
  try {
    await runLabAssist(body, render);
    render();
    document.getElementById("lab-result-panel")?.scrollIntoView({
      block: "start",
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "instant"
        : "smooth",
    });
  } finally {
    busy = false;
    app.removeAttribute("aria-busy");
  }
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
  if (route.path === "/lab") {
    staffStream.close();
    app.innerHTML = labShell(
      '<div class="panel empty" role="status">검사기를 준비하고 있습니다…</div>',
    );
    try {
      await Promise.all([loadLabExamples(), loadLabFields()]);
      if (sequence === loadSequence) render();
    } catch (error) {
      if (sequence === loadSequence)
        app.innerHTML = labShell(
          `<div class="panel empty"><h1>검사기를 열지 못했습니다</h1><p>${esc(error.message)}</p>${button("다시 시도", "primary", 'data-action="reload"')}</div>`,
        );
    }
    return;
  }
  if (!route.staff) {
    staffStream.close();
  }
  app.innerHTML = shell(
    '<div class="page-content"><div class="panel empty" role="status">서버에서 민원을 불러오고 있습니다…</div></div>',
  );
  try {
    await ensureRoleSession(route.staff ? "staff" : "citizen");
    await Promise.all([
      refresh(),
      route.staff
        ? Promise.all([
            loadLabFields().catch(() => null),
            loadStaffDepartments().catch(() => null),
            loadAnswerTemplates().catch(() => null),
            ...(route.path === "/staff/api"
              ? [loadBackendApiDocs().catch(() => null)]
              : []),
          ])
        : Promise.resolve(),
    ]);
    if (sequence === loadSequence) {
      if (route.staff && staffStream.getState() === "idle") {
        staffStream.open(read()?.eventCursor || 0);
      }
      render();
      if (!route.staff) showCitizenIntro();
      if (route.path === "/citizen/assistant" && citizenPrompt) {
        const prompt = citizenPrompt;
        citizenPrompt = null;
        sendChat(prompt);
      }
    }
  } catch (error) {
    if (sequence === loadSequence) {
      const needsLogin = error?.code === "demo_login_disabled" || error?.status === 401;
      app.innerHTML = shell(
        `<div class="page-content"><div class="panel empty"><h1>${needsLogin ? "계정 로그인이 필요합니다" : "서버 데이터를 불러오지 못했습니다"}</h1><p>${esc(error.message)}</p>${needsLogin ? button("로그인 · 본인확인", "primary", 'data-action="open-auth"') : button("다시 시도", "primary", 'data-action="reload"')}</div></div>`,
      );
      if (needsLogin) openAuthModal();
    }
  }
}
/**
 * shell 화면 동작을 구성합니다.
 *
 * @param {string} content 렌더링할 HTML 내용입니다.
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
function shell(content) {
  if (route.path === "/lab") {
    document.body.dataset.site = "lab";
    document.querySelector('meta[name="theme-color"]').content =
      getTheme() === "dark" ? "#101827" : "#2f6fed";
    return labShell(content);
  }
  document.body.dataset.site = route.staff ? "staff" : "citizen";
  document.querySelector('meta[name="theme-color"]').content =
    getTheme() === "dark" ? "#101827" : route.staff ? "#16203a" : "#2f6fed";
  return route.staff
    ? staffShell(content, route, data || read(), getActor())
    : citizenShell(content, route.path, getActor());
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
 * 민원 게시판 표의 본문 행(`<tr>`)을 렌더링합니다.
 *
 * @param {Array<object>} rows 현재 권한으로 조회한 민원 목록입니다.
 * @param {boolean} [staff=false] 담당자 화면인지 여부입니다.
 * @param {boolean} [mine=false] 시민 '내 민원' 화면인지 여부(본인 행 삭제 버튼 노출 기준)입니다.
 * @returns {string} 화면에 사용할 HTML 문자열입니다.
 */
function listRows(rows, staff = false, mine = false) {
  const myId = getActor()?.id || "citizen-demo";
  return rows
    .map(
      (c) =>
        `<tr><td class="id-cell">${c.id.split("-").at(-1)}</td><td><a class="row-title" href="#/${staff ? "staff" : "citizen"}/detail/${c.id}">${esc(c.title)} ${c.visibility === "private" ? `<span class="private-mark" title="비공개">${icon("shield", 13)}</span>` : ""}</a><span class="row-sub">${esc(c.category)} <span>·</span> ${staff ? (c.assigned ? esc(c.assigneeName || "김담당") : "담당자 미지정") : `<span class="origin-badge ${c.published?.origin || ""}">${origin(c.published)}</span>`}</span></td><td>${esc(c.district)}</td><td>${badge(c)}</td><td class="date-cell">${date(c.date)}</td><td>${!staff && mine && c.owner === myId ? `<div class="row-actions"><button type="button" class="row-delete-btn" data-action="delete-complaint" data-id="${c.id}" aria-label="${esc(c.title)} 삭제">삭제</button><a class="row-open" href="#/citizen/detail/${c.id}" aria-label="${esc(c.title)} 상세 보기">${icon("chevron", 16)}</a></div>` : `<a class="row-open" href="#/${staff ? "staff" : "citizen"}/detail/${c.id}" aria-label="${esc(c.title)} 상세 보기">${icon("chevron", 16)}</a>`}</td></tr>`,
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
  ${!staff ? `<nav class="scope-tabs" aria-label="민원 범위">${link("공개 민원", "/citizen/board", mine ? "" : "active")}${link("내 민원", "/citizen/mine", mine ? "active" : "")}</nav>` : ""}
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
    )}</div><form id="filters" class="filters"><div class="search-field">${icon("search", 18)}<input name="q" aria-label="민원 제목 검색" placeholder="어떤 민원을 찾으세요? 제목을 검색해 보세요." value="${esc(q)}"></div><select name="district" aria-label="지역 선택"><option value="">전체 지역</option>${districts.map((d) => `<option ${district === d ? "selected" : ""}>${d}</option>`).join("")}</select><select name="category" aria-label="분야 선택"><option value="">전체 분야</option>${categories.map((c) => `<option ${category === c ? "selected" : ""}>${c}</option>`).join("")}</select>${staff ? `<select name="assign" aria-label="담당 선택"><option value="">전체 담당</option><option value="mine" ${assign === "mine" ? "selected" : ""}>내 담당</option><option value="none" ${assign === "none" ? "selected" : ""}>미지정</option></select>` : ""}${button("검색", "primary", 'type="submit"')}<button class="icon-btn" type="button" data-action="reset-filters" aria-label="검색 조건 초기화">${icon("refresh", 18)}</button></form><div class="table-meta"><span>총 <b>${total}</b>건의 민원</span><span>최근 등록순 ${icon("filter", 14)}</span></div><div class="table-wrap"><table><thead><tr><th scope="col">번호</th><th scope="col">민원 제목</th><th scope="col">지역</th><th scope="col">처리 상태</th><th scope="col">등록일</th><th scope="col"><span class="sr-only">상세</span></th></tr></thead><tbody>${listRows(rows, staff, mine)}</tbody></table></div>${total === 0 ? `<div class="empty">${icon("search", 38)}<h3>검색 결과가 없습니다</h3><p>검색어나 필터를 바꾸어 다시 찾아보세요.</p>${button("검색 조건 초기화", "", 'data-action="reset-filters"')}</div>` : ""}<div class="pagination"><span>${total ? (page - 1) * 8 + 1 : 0}–${Math.min(page * 8, total)} / ${total}건</span><div>${button("‹", "", 'data-action="page" data-page="' + (page - 1) + '" ' + (page === 1 ? "disabled" : ""))}${Array.from({ length: pages }, (_, i) => button(i + 1, page === i + 1 ? "active" : "", `data-action="page" data-page="${i + 1}"`)).join("")}${button("›", "", 'data-action="page" data-page="' + (page + 1) + '" ' + (page === pages ? "disabled" : ""))}</div><span>페이지당 8건</span></div></section></div>`;
}
/**
 * writeForm 화면 동작을 구성합니다.
 *
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
function writeForm() {
  const editId = route.params.get("edit");
  const myId = getActor()?.id || "citizen-demo";
  const item = editId
    ? data.complaints.find(
        (c) =>
          c.id === editId &&
          c.owner === myId &&
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
  return `<div class="page-content narrow">${pageHeading("YOUR VOICE MATTERS", item ? "민원 수정" : "작은 목소리도 소중히 듣겠습니다", "일상에서 느낀 불편이나 궁금한 점을 편하게 남겨주세요.")}<div class="form-steps"><span class="active"><b>1</b> 민원 내용 작성</span><i></i><span><b>2</b> 담당자 검토</span><i></i><span><b>3</b> 답변 확인</span></div><div class="info-banner">${icon("help", 20)}<span>이곳은 <b>시연 서비스</b>입니다. <b>주민등록번호·전화번호·계좌번호</b>는 제목과 내용에 쓰지 마세요. 청주시 공식 접수로 연결되지 않습니다.</span></div><form id="complaint-form" class="panel complaint-form" data-id="${item?.id || ""}" data-version="${item?.version || ""}"><div class="section-title"><h2>민원 내용</h2><span><em>*</em> 필수 입력 항목</span></div><label for="title">제목 <em>*</em></label><input id="title" name="title" required minlength="2" maxlength="120" placeholder="민원 내용을 한눈에 알 수 있도록 작성해 주세요." value="${esc(value.title || "")}"><div class="field-hint"><span>이름, 연락처 등 개인정보는 제목에 적지 마세요.</span><span id="title-count">${(value.title || "").length}/120</span></div><div class="form-grid"><div><label for="category">민원 분야 <em>*</em></label><select id="category" name="category" required>${categories.map((c) => `<option ${c === (value.category || route.params.get("category")) ? "selected" : ""}>${c}</option>`).join("")}</select></div><div><label for="district">관할 구 <em>*</em></label><select id="district" name="district" required><option value="">지역을 선택해 주세요</option>${districts.map((d) => `<option ${d === value.district ? "selected" : ""}>${d}</option>`).join("")}</select></div></div><label for="body">상세 내용 <em>*</em></label><textarea id="body" name="body" rows="9" required minlength="10" maxlength="2000" placeholder="어디에서, 언제, 어떤 일이 있었나요?&#10;구체적인 상황과 요청 사항을 작성해 주시면 검토에 도움이 됩니다.">${esc(value.body || "")}</textarea><div class="field-hint"><span>최소 10자 이상 작성해 주세요. 첨부파일은 후속 지원 예정입니다.</span><span id="body-count">${(value.body || "").length}/2,000</span></div><label>공개 범위</label><div class="radio-cards"><label><input type="radio" name="visibility" value="private" ${value.visibility !== "public" ? "checked" : ""}><span><b>${icon("shield", 16)} 비공개</b><small>나와 담당자만 확인할 수 있어요.</small></span></label><label><input type="radio" name="visibility" value="public" ${value.visibility === "public" ? "checked" : ""}><span><b>${icon("user", 16)} 공개</b><small>다른 시민도 내용을 볼 수 있어요.</small></span></label></div><div class="consent"><label><input type="checkbox" name="consent" required> 시연용 데이터 저장 및 공식 민원 미접수 안내를 확인했습니다. <em>*</em></label></div><div class="form-footer">${link("취소", "/citizen/mine", "btn")}${button("임시 저장", "", 'type="button" data-action="save-form"')}${button(`${item ? "수정 내용 저장" : "민원 등록하기"} ${icon("arrow", 17)}`, "primary", 'type="submit"')}</div></form></div>`;
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
  const myId = getActor()?.id || "citizen-demo";
  const c = data.complaints.find(
    (c) =>
      c.id === id &&
      c.status !== "withdrawn" &&
      (route.staff || c.owner === myId || c.visibility === "public"),
  );
  if (!c) return missing();
  const owner = c.owner === myId;
  return `<div class="page-content">${!route.staff && newlyCreatedId === c.id ? `<div class="citizen-receipt" role="status"><span>${icon("check", 24)}</span><div><b>시연 서버에 민원이 등록되었어요</b><p>${c.id} · 청주시 공식 접수는 아닙니다.</p></div><button data-action="close-receipt" aria-label="등록 확인 닫기">${icon("close", 17)}</button></div>` : ""}<a class="back-link" href="#/${route.staff ? "staff/complaints" : "citizen/board"}">← 민원 목록으로</a>${route.staff ? staffPager(c) : ""}<div class="detail-heading"><div><div class="eyebrow">${c.id} <span>·</span> ${c.visibility === "private" ? "비공개 민원" : "공개 시연 민원"}</div><h1>${esc(c.title)}</h1><p>${esc(c.district)} <span>·</span> ${esc(c.category)} <span>·</span> ${date(c.date)} <span>·</span> 내용 버전 ${c.contextVersion}</p></div>${badge(c)}</div>${route.staff ? staffProcess(c) : ""}<div class="detail-grid ${route.staff ? "staff-detail" : ""}"><div><section class="panel detail-body"><div class="section-title"><h2>${icon("file", 20)} 민원 내용</h2>${owner && !route.staff ? `<div class="inline-actions">${!c.published ? link("수정", `/citizen/write?edit=${c.id}`) : ""}<button type="button" data-action="withdraw" data-id="${c.id}">민원 철회</button><button type="button" class="danger-link" data-action="delete-complaint" data-id="${c.id}">민원 삭제</button></div>` : ""}</div><div class="prose">${esc(c.body)}</div><div class="detail-note">${icon("shield", 16)} ${c.visibility === "private" ? "비공개로 등록된 민원입니다." : "개인정보 없는 공개 시연 민원입니다."}</div></section>${route.staff ? staffReviewInfo(c) : nextStepBox(c)}<section class="panel answer-panel"><div class="section-title"><h2>${icon("chat", 20)} ${route.staff ? "현재 게시된 답변" : "답변 확인"}</h2>${c.published ? `<span class="origin-badge ${c.published.origin || ""}">${origin(c.published)}</span>` : ""}</div>${c.published ? `<div class="answer-person"><span class="avatar">김</span><div><b>김담당 <span>민원 검토 담당자 · 시연</span></b><small>${date(c.published.date)} 게시</small></div></div>${route.staff ? `<div class="prose">${esc(c.published.text)}</div>` : foldAnswer(c.published.text)}${c.published.origin !== "staff" ? '<p class="answer-disclosure">AI가 작성한 초안을 담당자가 검토' + (c.published.origin === "ai_edited" ? "·수정" : "") + "한 답변입니다.</p>" : ""}` : `<div class="waiting-answer">${icon("clock", 30)}<h3>담당자가 민원을 살펴보고 있습니다</h3><p>검토를 마치면 이곳에서 답변을 확인할 수 있어요.<br>작성 중인 초안은 시민에게 공개되지 않습니다.</p></div>`}</section><section class="panel followup"><div class="section-title"><h2>추가 문의 <small>${c.messages.length}</small></h2></div>${c.messages.map((m) => `<div class="message"><b>${m.author === "staff" ? "김담당" : "시민님"}</b><span>${date(m.date)}</span><p>${esc(m.text)}</p></div>`).join("")}${owner && !route.staff && c.status !== "closed" ? `<form id="followup-form" data-id="${c.id}" data-version="${c.version}"><label class="sr-only" for="followup">추가 문의 내용</label><textarea id="followup" name="message" maxlength="500" required placeholder="답변을 보고 더 궁금한 점을 적어 주세요." rows="3"></textarea><p class="field-hint"><span id="followup-count">0/500</span></p><div class="form-footer">${c.published ? button("담당자 재검토 요청", "", 'type="button" data-action="review" data-id="' + c.id + '"') : ""}${button("추가 문의 등록", "primary", 'type="submit"')}</div></form>` : owner && !route.staff ? '<p class="muted">처리가 종료된 민원에는 추가 문의를 남길 수 없습니다.</p>' : '<p class="muted">민원 작성자의 추가 문의가 이곳에 표시됩니다.</p>'}</section></div><aside>${route.staff ? editor(c) : citizenProgress(c)}<details class="panel history-panel"><summary><h2>${route.staff ? "처리 이력" : "처리 이력 보기"}</h2></summary><ol class="timeline">${c.history
    .slice()
    .reverse()
    .map((h) => `<li><b>${esc(h.text)}</b><time>${date(h.date)}</time></li>`)
    .join("") || '<li class="empty-line">아직 처리 이력이 없습니다.</li>'}</ol></details></aside></div></div>`;
}
/**
 * 시민 상세 맨 위에 처리 결론·지금 상태·다음 단계를 보여 줍니다.
 *
 * 부서 정보는 데이터 모델에 없으므로 표시하지 않습니다.
 *
 * @param {object} c 서버에서 조회한 민원입니다.
 * @returns {string} 결론 상자 HTML입니다.
 */
function nextStepBox(c) {
  const [conclusion, now, next] = {
    submitted: [
      "접수 대기",
      "담당자가 아직 내용을 확인하기 전이에요",
      "담당자가 검토한 뒤 결과를 안내드려요",
    ],
    under_review: [
      "담당자 검토 중",
      "담당자가 내용과 필요한 조치를 살펴보고 있어요",
      "검토가 끝나면 답변이 게시돼요",
    ],
    answered: [
      "답변이 게시되었어요",
      "담당자 답변을 아래에서 확인할 수 있어요",
      "더 궁금하면 추가 문의를 남겨 주세요",
    ],
    closed: [
      "처리가 끝난 민원이에요",
      "처리 종료 상태입니다",
      "새로운 문의는 새 민원으로 접수해 주세요",
    ],
  }[c.status] || ["처리 상태 확인 중", "", ""];
  return `<section class="panel next-step-box" aria-label="처리 요약"><span class="badge ${c.status}"><i></i>${statusNames[c.status] || ""}</span><p class="next-step-conclusion">${conclusion}</p><dl><div><dt>지금 상태</dt><dd>${now}</dd></div><div><dt>다음 단계</dt><dd>${next}</dd></div></dl></section>`;
}
/**
 * 시민에게 보여 줄 답변을 첫 문장과 나머지로 나눕니다. 나머지는 접어 둡니다.
 *
 * @param {string} text 게시된 답변 원문입니다.
 * @returns {string} 답변 HTML입니다.
 */
function foldAnswer(text) {
  const source = String(text).trim();
  // 한글·영문 뒤의 마침표와 뒤따르는 공백에서만 나눕니다. "2026. 10. 28."처럼 숫자 뒤의 마침표는 나누지 않습니다.
  // 홀수 번째 조각은 나눈 공백입니다.
  const tokens = source.split(/((?<=[가-힣A-Za-z]\.)\s+)/);
  const greeting = /^안녕하(세요|십니까)[.!]?$/;
  const idx = tokens.findIndex(
    (t, i) => i % 2 === 0 && t && !greeting.test(t.trim()),
  );
  if (idx < 0 || tokens.length === 1)
    return `<div class="prose">${esc(source)}</div>`;
  // 결론 문장을 맨 위에 두고, 나머지(인사말 포함)는 원래 순서대로 접습니다.
  const lead = tokens[idx];
  const before = tokens.slice(0, idx).join("").trim();
  const after = tokens.slice(idx + 2).join("").trim();
  const rest = [before, after].filter(Boolean).join("\n");
  if (!rest) return `<div class="prose">${esc(source)}</div>`;
  return `<div class="prose answer-lead">${esc(lead.trim())}</div><details class="answer-more"><summary>자세한 안내 보기</summary><div class="prose answer-rest">${esc(rest)}</div></details>`;
}
/**
 * 담당자 상세에서 이전·다음 민원으로 이동하는 줄을 만듭니다.
 *
 * 전체 업무 목록의 기본 순서(최신 등록순, 철회 제외)를 따릅니다.
 *
 * @param {object} c 현재 상세 민원입니다.
 * @returns {string} 이동 줄 HTML입니다.
 */
function staffPager(c) {
  const list = data.complaints
    .filter((row) => row.status !== "withdrawn")
    .sort((x, y) => new Date(y.date) - new Date(x.date));
  const index = list.findIndex((row) => row.id === c.id);
  if (index < 0) return "";
  const prev = list[index - 1];
  const next = list[index + 1];
  return `<nav class="staff-pager" aria-label="민원 이동">${prev ? link("‹ 이전 민원", `/staff/detail/${prev.id}`) : '<span class="disabled">‹ 이전 민원</span>'}<span>${index + 1} / ${list.length}</span>${next ? link("다음 민원 ›", `/staff/detail/${next.id}`) : '<span class="disabled">다음 민원 ›</span>'}</nav>`;
}
/**
 * 시민 상세의 3단계 처리 현황 막대를 만듭니다.
 *
 * @param {object} c 서버에서 조회한 민원입니다.
 * @returns {string} 처리 현황 HTML입니다.
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
  const candidateDiffers = Boolean(
    c.aiCandidate && c.aiCandidate.trim() && c.aiCandidate.trim() !== c.draft.trim(),
  );
  const officerName = c.assigneeName || "김담당";
  const assignLabel = c.department
    ? c.assigned
      ? `${esc(c.department)} · ${esc(officerName)}`
      : esc(c.department)
    : c.assigned
      ? esc(officerName)
      : "미지정";
  const templates = Array.isArray(answerTemplates) ? answerTemplates : [];
  const existingIds = new Set(templates.map((t) => t.id));
  const hasMissingDefaults = FALLBACK_TEMPLATES.some((t) => !existingIds.has(t.id));
  const evidenceText =
    c.job?.status === "running"
      ? `RAG 검색과 LLM 판정·초안 생성을 실행하고 있습니다 (${c.job.stage || "진행 중"}).`
      : c.aiAssist
        ? "RAG+LLM 분석 결과를 좌측 참고 정보에 표시했습니다. 게시 전 FAQ 조건·부서 업무분장을 확인하세요."
        : "담당자가 직접 작성하거나 아래 엔진 선택으로 RAG+LLM 응대 분석을 실행할 수 있습니다.";
  return `<section class="panel editor-panel"><div class="section-title"><h2>${icon("spark", 19)} 답변 검토·편집</h2><span class="mini-chip">시민 비공개</span></div><div class="editor-status"><span class="badge under_review">검토 우선</span><span>접수 ${daysSince(c.date)}일째</span><span id="draft-state" class="draft-state" role="status" aria-live="polite">서버 저장본</span></div><div class="assign-row"><span>담당·부서</span><b>${assignLabel}</b><div class="assign-actions">${button(c.department ? "부서 변경" : "다른 부서 배정", "", 'type="button" data-action="open-assign-dept" data-id="' + c.id + '"')}${button(c.assigned ? "담당 해제" : "내가 담당", "", 'type="button" data-action="assign" data-id="' + c.id + '"')}</div></div><form id="answer-form" data-id="${c.id}" data-version="${c.version}" data-context="${c.contextVersion}" data-draft="${c.draftVersion}"><label for="answer">시민에게 안내할 답변</label><div class="phrase-section"><div class="phrase-header"><span class="phrase-title">자주 쓰는 답변 템플릿 <small>${templates.length}</small></span><div class="phrase-header-actions"><button type="button" class="phrase-manage-btn" data-action="open-add-template">${icon("plus", 13)} 템플릿 추가</button>${hasMissingDefaults ? '<button type="button" class="phrase-reset-btn" data-action="reset-templates">기본 복원</button>' : ""}</div></div>${templates.length ? `<div class="phrase-bar" aria-label="자주 쓰는 답변 템플릿">${templates.map((t) => `<span class="phrase-chip-wrap"><button type="button" class="phrase-chip" data-action="insert-phrase" data-phrase="${esc(t.content)}" title="${esc(t.content)}">${esc(t.title)}</button><button type="button" class="phrase-del" data-action="delete-template" data-id="${esc(t.id)}" data-title="${esc(t.title)}" aria-label="${esc(t.title)} 템플릿 삭제" title="템플릿 삭제">×</button></span>`).join("")}</div>` : '<p class="phrase-empty">저장된 답변 템플릿이 없습니다. "+ 템플릿 추가"로 자주 쓰는 안내 문구를 등록해 보세요.</p>'}</div><textarea id="answer" name="answer" required maxlength="4000" rows="13" placeholder="검토한 내용을 바탕으로 답변을 작성해 주세요.">${esc(c.draft)}</textarea><div class="field-foot"><p class="field-hint">${c.aiOriginal ? "AI 작성 기원과 원본을 보존합니다." : "담당자가 직접 작성하는 답변입니다."}</p><span class="char-count" id="answer-count">${c.draft.length}/4,000</span></div><label for="reason">수정·게시 사유 <em>*</em></label><input id="reason" name="reason" required maxlength="200" placeholder="예: 현장 확인 필요 사항을 보완함"><span class="char-count" id="reason-count">0/200</span><div class="editor-buttons">${button("초안 저장", "", 'type="submit"')}${button("미리보기·게시", "primary", 'type="button" data-action="preview-answer"')}</div><p class="shortcut-hint">Ctrl+S(또는 ⌘S)로 초안을 저장합니다.</p></form><div class="staff-ai-runner"><label for="staff-job-provider">AI 분석 엔진</label><div class="staff-ai-runner-row"><select id="staff-job-provider" aria-label="AI 분석 엔진 선택">${buildProviderOptionsHtml(labFields.providers, c.job?.provider || "")}</select>${button(`${icon("refresh", 15)} ${c.aiAssist ? "AI 재실행" : "AI 분석 실행"}`, "", 'data-action="retry" data-id="' + c.id + '" ' + (c.job.status === "running" ? "disabled" : ""))}</div></div><div class="editor-tools">${button(`${icon("book", 15)} AI 원문·추론 이력`, "", 'data-action="compare" data-id="' + c.id + '"')}${candidateDiffers ? button(`${icon("spark", 15)} AI 후보 채우기`, "", 'data-action="apply-ai-candidate" data-id="' + c.id + '"') : ""}</div><div class="evidence-note">${icon("help", 17)}<span>${esc(evidenceText)}</span></div>${c.published ? button("게시 답변 철회", "danger subtle", 'data-action="retract" data-id="' + c.id + '"') : ""}</section>`;
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
 * 담당자 콘솔에서 백엔드 API · Swagger UI 페이지를 구성합니다.
 *
 * @returns {string} 렌더링할 HTML 문자열입니다.
 */
function swaggerDocs() {
  const host = window.location.hostname || "127.0.0.1";
  const ragDocsUrl = `${window.location.protocol}//${host}:8007/docs`;
  return backendSwaggerPage({
    health: backendHealth,
    spec: openApiSpec,
    summary: openApiSummary,
    loading: apiDocsLoading,
    error: apiDocsError,
    tab: apiDocsTab,
    tag: apiDocsTag,
    query: apiDocsQuery,
    theme: getTheme(),
    ragDocsUrl,
  });
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
  const stageChecks = [
    ["읽기·접수", /읽|저장|요청|시뮬레이션/],
    ["검색", /자료|검색/],
    ["판정·검토", /살펴|판정|부서/],
    ["안내·초안", /안내|작성|초안|정리|검증|완료/],
  ];
  const sseBadgeHtml = renderSseStatusBadge(sseState, sseLastEventAt).replace(
    "<span ",
    '<span id="staff-sse-status" ',
  );
  return `<div class="page-content">${pageHeading("AI WORKSPACE", "AI 작업 모니터", "검색부터 검토 대기까지, AI 작업의 단계와 이력을 실시간으로 확인하세요.", sseBadgeHtml)}<div class="info-banner amber">${icon("help", 20)}<span><b>RAG + LLM 백그라운드 분석 · 실시간 SSE 푸시</b> (연결 단절 시 3초 폴링 자동 전환) · 민원 등록·재실행 시 실제 검색과 LLM 판정·초안을 실행하며, 미게시 초안은 시민에게 노출하지 않습니다.</span></div><div class="monitor-toolbar">${[
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
    )}<span class="muted">총 ${rows.length}건</span></div><div class="job-grid">${rows.map((c) => {
      const provKey = c.aiAssist?.llmProvider || c.job?.provider || "";
      const provLabel = provKey ? ` · ${PROVIDER_SHORT_LABELS[provKey] || provKey}` : "";
      const lastDate = c.job.events.at(-1)?.date;
      return `<section class="panel job-card"><div class="job-card-top"><span class="mono">${c.id}</span><span class="badge job-${c.job.status}">${{ queued: "실행 대기", running: "실행 중", succeeded: "완료", failed: "실패", cancelled: "취소", superseded: "입력 변경" }[c.job.status] || c.job.status}</span></div><h2>${esc(c.title)}</h2><p class="job-meta">작업 ${c.id}-A${c.job.attempt} · 입력 v${c.job.contextVersion || c.contextVersion} · 시도 ${c.job.attempt}${esc(provLabel)}</p><div class="job-stage">${icon(c.job.status === "running" ? "refresh" : "monitor", 19)}<b>${esc(c.job.stage)}</b></div><div class="stage-steps">${stageChecks.map(([label, rx]) => `<span class="${c.job.events.some((e) => rx.test(e.stage)) ? "done" : ""}">${label}</span>`).join("")}</div><p class="job-updated">${lastDate ? `마지막 이벤트 · ${new Date(lastDate).toLocaleTimeString("ko-KR")}` : "대기 중"}</p><div class="job-actions">${link("민원 열기", `/staff/detail/${c.id}`, "btn")}${button("이력", "", 'data-action="job-history" data-id="' + c.id + '"')}${button(c.job.status === "running" ? "취소" : "AI 재실행", c.job.status === "running" ? "danger" : "primary subtle", `data-action="${c.job.status === "running" ? "cancel-job" : "retry"}" data-id="${c.id}"`)}</div></section>`;
    }).join("")}</div>${!rows.length ? '<div class="panel empty"><h2>해당 상태의 작업이 없습니다</h2><p>다른 필터를 선택하거나 민원 상세에서 AI 분석을 실행하세요.</p></div>' : ""}</div>`;
}
/**
 * assistant 화면 동작을 구성합니다.
 *
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
function assistant() {
  const districtChoices = ["", ...districts.filter((d) => d !== "모름")];
  return `<div class="page-content assistant-page"><a class="back-link" href="#/citizen">← 홈으로</a><section class="panel chat-panel"><div class="chat-heading"><span class="citizen-chat-avatar">${icon("spark", 24)}</span><div><h1>민원 도우미</h1><small><i></i> 청주시 공식 FAQ · 사례 기반 실시간 AI 안내</small></div><span class="mini-chip live-chip">RAG + LLM 연동</span></div><div class="chat-messages" aria-live="polite"><div class="chat-bubble ai"><b>안녕하세요! 불편하신 점이나 궁금한 제도를<br>평소 말하듯이 물어보세요 🙂</b><p>청주시 공식 자주 묻는 민원(FAQ)을 찾아 바로 안내해 드리고,<br>현장 조치나 담당자 확인이 필요하면 민원 작성으로 바로 이어 드려요.</p><small>AI 시연 안내이며 공식 민원 접수·자동 부서 이관은 아닙니다. 미게시 담당자 초안은 노출하지 않습니다.</small></div>${chatMessages.map(renderCitizenChatBubble).join("")}${chatPending ? `<div class="chat-bubble ai citizen-typing" role="status" aria-label="AI 답변 준비 중"><i></i><i></i><i></i><span id="chat-live-label">${esc(chatLiveLabel || "민원 내용을 읽고 있어요")}</span></div>` : ""}</div>${!chatMessages.length ? `<div class="suggestions">${["대형폐기물 배출 방법이 궁금해요", "서원대 후문 가로등이 밤새 깜빡거려요", "전입신고에 필요한 서류를 문의하고 싶어요"].map((s) => button(s, "", 'data-action="chat-suggest" data-text="' + s + '"')).join("")}</div>` : ""}<div class="citizen-chat-tools"><label class="chat-district-wrap" for="chat-district"><span>지역</span><select id="chat-district" aria-label="문의 관할 구 선택" ${chatPending ? "disabled" : ""}>${districtChoices.map((d) => `<option value="${esc(d)}" ${chatDistrict === d ? "selected" : ""}>${d ? esc(d) : "자동 감지"}</option>`).join("")}</select></label><button data-action="citizen-chat-help">${icon("book", 14)} 작성 요령</button>${chatMessages.length ? `<button data-action="chat-reset" ${chatPending ? "disabled" : ""}>${icon("refresh", 14)} 새 대화</button>` : ""}<span>${icon("shield", 14)} 개인정보 입력 주의</span>${link("직접 작성하기", "/citizen/write")}</div><form id="chat-form" class="chat-input"><label class="sr-only" for="chat-input">도우미에게 보낼 내용</label><input id="chat-input" name="message" required maxlength="2000" placeholder="예) 대형폐기물 배출 방법이나 동네 불편 사항을 입력해 주세요" ${chatPending ? "disabled" : ""}>${button(icon("arrow", 20), "primary", 'type="submit" aria-label="보내기" ' + (chatPending ? "disabled" : ""))}</form></section><p class="chat-disclaimer">${icon("shield", 14)} 청주시 공식 FAQ·사례 검색 기반 AI 시연 안내 · 실제 민원은 작성 화면에서 직접 등록해야 담당자가 접수합니다.</p></div>`;
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
      "제목과 상세 내용, 관할 구를 작성해 주세요. 공개 범위는 비공개가 기본이며, 개인정보는 입력하지 마세요.",
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
      "민원과 답변은 Flask 서버의 PostgreSQL 업무 DB(`complaint_app`)에 저장되어 브라우저를 새로 열어도 유지됩니다. 작성 전 임시 입력만 이 탭에 저장합니다.",
    ],
    [
      "AI가 바로 답변하나요?",
      "민원 등록 시 백그라운드에서 RAG 검색과 LLM 분석이 실행되어 담당자에게 참고 근거·부서 후보·초안을 제공합니다. 초안은 담당자가 검토·게시하기 전까지 시민 화면에 표시하지 않습니다.",
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
  const oldProviderChoice = $("#staff-job-provider")?.value;
  route = currentRoute();
  data = read();
  let content;
  if (route.path === "/lab") {
    const form = $("#assist-form");
    content = labPage(
      form
        ? {
            title: form.elements.title.value,
            body: form.elements.body.value,
            district: form.elements.district.value,
            category: form.elements.category.value,
            provider: form.elements.provider?.value,
          }
        : {},
    );
  } else if (route.path === "/citizen") content = home();
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
  else if (route.path === "/staff/api") content = swaggerDocs();
  else if (route.path === "/citizen/assistant") content = assistant();
  else if (route.path === "/citizen/guide") content = guide();
  else if (route.path === "/citizen/services") content = citizenServicesPage();
  else if (route.path === "/citizen/news") content = citizenNewsPage();
  else if (route.path === "/citizen/updates") content = citizenUpdates(data);
  else if (route.path === "/citizen/profile")
    content = citizenProfile(data, getActor());
  else content = missing();
  app.innerHTML = shell(content);
  const newEditor = $("#answer-form");
  const newProviderSelect = $("#staff-job-provider");
  if (
    oldProviderChoice !== undefined &&
    newProviderSelect &&
    newEditor &&
    editing &&
    newEditor.dataset.id === editing.id
  ) {
    newProviderSelect.value = oldProviderChoice;
  }
  if (
    editing &&
    newEditor &&
    newEditor.dataset.id === editing.id &&
    newEditor.dataset.context === editing.context &&
    newEditor.dataset.draft === editing.draftVersion
  ) {
    newEditor.elements.answer.value = editing.text;
    newEditor.elements.reason.value = editing.reason;
    const answerCount = $("#answer-count");
    if (answerCount) {
      answerCount.textContent =
        editing.text.length.toLocaleString("ko-KR") + "/4,000";
    }
    const reasonCount = $("#reason-count");
    if (reasonCount) reasonCount.textContent = editing.reason.length + "/200";
    const draftState = $("#draft-state");
    if (draftState && editing.text !== newEditor.elements.answer.defaultValue) {
      draftState.textContent = "작성 중 · 저장 안 됨";
      draftState.classList.add("dirty");
    }
    if (editing.focus === "answer" || editing.focus === "reason") {
      const field = document.getElementById(editing.focus);
      field.focus({ preventScroll: true });
      field.setSelectionRange(editing.start, editing.end);
    }
  }
  document.title = `${route.path === "/lab" ? "응대 검사기" : route.staff ? "담당자 업무 포털" : "청주톡톡"} · 시민의 목소리에 더 가까이`;
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
 * 시민 민원 도우미 질문을 서버 RAG+LLM 스트림 API로 보내고 결과를 말풍선에 표시합니다.
 *
 * @param {string} text 사용자가 입력한 상담 내용입니다.
 * @returns {Promise<void>} 비동기 응답 반영 완료 프로미스입니다.
 */
async function sendChat(text) {
  const trimmed = String(text || "").trim();
  if (chatPending || !trimmed) return;
  chatMessages.push({ role: "me", text: trimmed });
  chatPending = true;
  chatLiveLabel = "민원 내용을 읽고 있어요";
  const scrollChatBottom = () => {
    $(".chat-messages")?.lastElementChild?.scrollIntoView({
      block: "nearest",
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "instant"
        : "smooth",
    });
  };
  render();
  scrollChatBottom();
  try {
    const result = await streamCitizenChat(
      {
        message: trimmed,
        district: chatDistrict || null,
      },
      {
        onProgress: (step) => {
          chatLiveLabel = step.label;
          const liveEl = $("#chat-live-label");
          if (liveEl) liveEl.textContent = chatLiveLabel;
        },
      },
    );
    try {
      sessionStorage.setItem(
        "complaint-form",
        JSON.stringify(buildCitizenDraftPayload(trimmed, result)),
      );
    } catch {
      /* 브라우저 탭 저장소 제한 환경은 무시합니다. */
    }
    chatMessages.push({
      role: "ai",
      source: trimmed,
      text: result.answer,
      result,
    });
  } catch (error) {
    chatMessages.push({
      role: "ai",
      source: trimmed,
      text:
        error?.message ||
        "일시적으로 AI 안내를 불러오지 못했습니다. 아래 버튼으로 민원을 직접 작성해 주세요.",
      result: null,
    });
  } finally {
    chatPending = false;
    chatLiveLabel = "";
    if (currentRoute().path === "/citizen/assistant") {
      render();
      scrollChatBottom();
    }
  }
}

document.addEventListener("click", async (event) => {
  const target = event.target.closest("[data-action]");
  if (!target || busy) return;
  const action = target.dataset.action,
    id = target.dataset.id;
  if (action === "lab-help") {
    openModal(
      "응대 검사기 이용 안내",
      `<div class="modal-content"><p>민원 내용을 시민 작성 양식으로 남기면 저장된 안내와 사례를 찾아 바로 안내할 수 있는지 살펴봅니다.</p><p>진행 중에는 지금 하는 일만 짧게 보여 줍니다. 바로 안내하지 못하면 담당자 검토·부서 후보 등 처리 이유를 알려 줍니다. 자동 이관은 없습니다.</p><p>민원은 저장하지 않으며 공식 접수와 연결되지 않습니다.</p>${button("확인", "primary", 'data-action="close-modal"')}</div>`,
    );
    return;
  }
  if (action === "lab-provider") {
    if (target.getAttribute("aria-disabled") === "true") {
      target.classList.remove("shake");
      void target.offsetWidth;
      target.classList.add("shake");
      toast(target.getAttribute("title") || "현재 사용할 수 없는 LLM 엔진입니다.");
      return;
    }
    setSelectedLabProvider(target.dataset.provider || "");
    render();
    return;
  }
  if (action === "lab-copy-data") {
    try {
      await navigator.clipboard.writeText(
        JSON.stringify(labResult?.codex || [], null, 2),
      );
      toast("보낸 데이터 JSON을 복사했습니다.");
    } catch {
      toast("복사에 실패했습니다. 직접 선택해 복사해 주세요.");
    }
    return;
  }
  if (action === "lab-copy-prompt") {
    const idx = Number(target.dataset.index);
    const items = (labResult?.codex || []).filter(
      (call) => typeof call?.prompt === "string" && call.prompt,
    );
    try {
      await navigator.clipboard.writeText(items[idx]?.prompt || "");
      toast("프롬프트를 복사했습니다.");
    } catch {
      toast("복사에 실패했습니다. 직접 선택해 복사해 주세요.");
    }
    return;
  }
  if (action === "lab-example") {
    const sample = labExamples.find((item) => item.id === id);
    if (!sample) return;
    const form = $("#assist-form");
    if (form) {
      form.elements.title.value = sample.title;
      form.elements.body.value = sample.query;
      form.elements.district.value = sample.district || "";
      $("#lab-title-count").textContent = sample.title.length + "/120";
      $("#lab-body-count").textContent = sample.query.length + "/2,000";
    }
    await completeLabAssist({
      query: labQuery({
        title: sample.title,
        body: sample.query,
        category: form?.elements.category.value,
      }),
      district: sample.district || null,
      limit: 5,
      rerank: false,
      provider: form?.elements.provider?.value || selectedLabProvider || null,
    });
    return;
  }
  const c = id ? data?.complaints?.find((row) => row.id === id) : null;
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
      const payload = buildCitizenDraftPayload(target.dataset.text, {
        district: target.dataset.district || "모름",
      });
      sessionStorage.setItem("complaint-form", JSON.stringify(payload));
      location.hash = "/citizen/write";
    } catch {
      toast("작성 내용을 옮기지 못했습니다. 입력 내용을 보관해 주세요.");
    }
    return;
  }
  if (action === "chat-reset") {
    if (chatPending) return;
    chatMessages = [];
    chatLiveLabel = "";
    render();
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
    const next = getTheme() === "dark" ? "light" : "dark";
    setTheme(next);
    $("#staff-swagger-frame")?.contentWindow?.postMessage(
      { type: "minwon-theme", theme: next },
      location.origin,
    );
    return;
  }
  if (action === "api-docs-tab") {
    apiDocsTab = target.dataset.tab === "index" ? "index" : "swagger";
    render();
    return;
  }
  if (action === "api-docs-tag") {
    apiDocsTag = target.dataset.tag || "";
    render();
    return;
  }
  if (action === "api-docs-reset") {
    apiDocsTag = "";
    apiDocsQuery = "";
    render();
    return;
  }
  if (action === "api-docs-refresh") {
    await loadBackendApiDocs(true);
    render();
    toast("백엔드 OpenAPI 명세와 서버 상태를 새로고침했습니다.");
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
            .querySelector(".staff-sidebar nav a, .staff-sidebar nav button")
            ?.focus({ preventScroll: true });
      }, 220);
    else document.querySelector(".staff-menu-toggle")?.focus();
    return;
  }
  if (action === "staff-help") {
    openModal(
      "민원과 업무 이용 안내",
      `<div class="modal-content"><p>접수 대기·검토 목록에서 민원을 선택하고, 담당자 지정과 RAG+LLM 분석 근거를 확인하세요.</p><p>초안을 저장한 뒤 미리보기에서 시민에게 표시될 내용을 확인하고 게시할 수 있습니다. AI 원본과 수정 이력은 보존됩니다.</p><p>업무 상태·AI 작업·게시 여부는 구분됩니다. 자동 부서 배정·법정기한·공식 행정 이관은 연결되지 않은 로컬 시연입니다.</p>${button("확인", "primary", 'data-action="close-modal"')}</div>`,
    );
    return;
  }
  if (action === "skip-main") {
    event.preventDefault();
    $("#main")?.focus();
    return;
  }
  if (action === "open-auth") {
    authVerifyChallenge = null;
    openAuthModal(target.dataset.tab || undefined);
    return;
  }
  if (action === "auth-tab") {
    authModalTab = target.dataset.tab || "citizen-login";
    if (authModalTab === "citizen-register") authVerifyChallenge = null;
    openAuthModal(authModalTab);
    return;
  }
  if (action === "auth-logout") {
    try {
      staffStream.close();
      await logoutAccount();
      modal.close();
      toast("로그아웃되었습니다.");
      await loadScreen();
    } catch (err) {
      toast(err?.message || "로그아웃 처리 중 오류가 발생했습니다.");
    }
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
  if (action === "open-assign-dept") {
    if (!c) return;
    if (!staffDepartments.length) {
      await loadStaffDepartments().catch(() => []);
    }
    const aiDepts = [
      ...new Set(
        (c.aiAssist?.departments || [])
          .map((item) => item?.canonicalName)
          .filter(Boolean),
      ),
    ].slice(0, 6);
    const suggestHtml = aiDepts.length
      ? `<div class="dept-suggest-block"><small>AI 추천 부서 후보 (참고용 · 눌러서 선택)</small><div class="dept-suggest-chips">${aiDepts
          .map(
            (name) =>
              `<button type="button" class="dept-suggest-btn" data-action="pick-suggest-dept" data-department="${esc(name)}">${esc(name)}</button>`,
          )
          .join("")}</div></div>`
      : "";
    openModal(
      "다른 부서로 배정하기",
      `<form id="assign-dept-form" class="modal-content" data-id="${esc(c.id)}" data-version="${c.version}"><p>시연 업무 포털 내에서 담당 부서를 지정·전달합니다. 실제 청주시 공식 이관은 수행하지 않으며, 배정 전 업무분장을 확인해 주세요.</p>${suggestHtml}<label for="dept-search">부서 검색</label><input id="dept-search" type="search" placeholder="예: 건설과, 대중교통과, 흥덕구" autocomplete="off"><label for="dept-select">배정할 부서 <em>*</em></label><select id="dept-select" name="department" required>${buildDepartmentOptionsHtml(staffDepartments, c.department || "", "")}</select><label for="dept-reason">전달·배정 메모 (선택)</label><input id="dept-reason" name="reason" maxlength="200" placeholder="예: 현장 점검 구역 확인 요청"><div class="form-footer">${button("취소", "", 'type="button" data-action="close-modal"')}${c.department ? button("배정 해제", "danger subtle", 'type="button" data-action="clear-assign-dept" data-id="' + esc(c.id) + '"') : ""}${button("부서 배정 저장", "primary", 'type="submit"')}</div></form>`,
    );
    return;
  }
  if (action === "pick-suggest-dept") {
    const deptName = target.dataset.department || "";
    const searchInput = $("#dept-search");
    const select = $("#dept-select");
    if (searchInput) searchInput.value = "";
    if (select) {
      select.innerHTML = buildDepartmentOptionsHtml(
        staffDepartments,
        deptName,
        "",
      );
      select.value = deptName;
      select.focus();
    }
    return;
  }
  if (action === "clear-assign-dept") {
    if (!c) return;
    const ok = await perform(
      () => command("/assignment", { department: "" }, "PUT"),
      "담당 부서 배정을 해제했습니다.",
    );
    if (ok) modal.close();
    return;
  }
  if (action === "open-add-template") {
    const currentAnswer = ($("#answer")?.value || "").trim();
    openModal(
      "답변 템플릿 추가",
      `<form id="template-form" class="modal-content"><label for="template-title">템플릿 이름 <em>*</em></label><input id="template-title" name="title" required maxlength="60" placeholder="예: 가로등 점검 안내"><label for="template-content">안내 문구 내용 <em>*</em></label><textarea id="template-content" name="content" required maxlength="2000" rows="6" placeholder="시민 안내 답변에 넣을 문구를 입력해 주세요."></textarea>${currentAnswer ? '<div class="modal-inline-action"><button type="button" class="phrase-manage-btn" data-action="fill-template-from-answer">현재 편집 중 답변 불러오기</button></div>' : ""}<div class="form-footer">${button("취소", "", 'type="button" data-action="close-modal"')}${button("템플릿 저장", "primary", 'type="submit"')}</div></form>`,
    );
    return;
  }
  if (action === "fill-template-from-answer") {
    const src = $("#answer")?.value?.trim() || "";
    const dest = $("#template-content");
    if (dest && src) dest.value = src.slice(0, 2000);
    if ($("#template-title") && !$("#template-title").value.trim()) {
      $("#template-title").focus();
    } else if (dest) {
      dest.focus();
    }
    return;
  }
  if (action === "delete-template") {
    const tplTitle = target.dataset.title || "선택한";
    openModal(
      "템플릿을 삭제하시겠어요?",
      `<form id="confirm-form" class="modal-content" data-id="${esc(id || "")}" data-kind="delete-template"><p><strong>${esc(tplTitle)}</strong> 답변 템플릿을 삭제합니다. 작성 중인 답변 본문은 그대로 유지됩니다.</p><div class="form-footer">${button("취소", "", 'type="button" data-action="close-modal"')}${button("삭제하기", "danger", 'type="submit"')}</div></form>`,
    );
    return;
  }
  if (action === "reset-templates") {
    await perform(async () => {
      const res = await api("/templates/reset", { method: "POST" });
      if (Array.isArray(res?.templates)) {
        answerTemplates = res.templates;
        templatesLoaded = true;
      }
    }, "기본 답변 템플릿을 복원했습니다.");
    return;
  }
  if (action === "review") {
    await perform(() => command("/review"), "재검토 요청을 저장했습니다.");
    return;
  }
  if (action === "retry") {
    const provider = $("#staff-job-provider")?.value || null;
    await perform(
      () => command("/jobs", provider ? { provider } : {}),
      "AI 응대 분석을 요청했습니다. 기존 편집본은 유지됩니다.",
    );
    return;
  }
  if (action === "apply-ai-candidate") {
    const field = $("#answer");
    if (!field || !c?.aiCandidate) return;
    field.value = c.aiCandidate;
    field.dispatchEvent(new Event("input", { bubbles: true }));
    field.focus();
    toast("AI 후보 문장을 편집기에 채웠습니다. 검토 후 초안 저장 또는 게시해 주세요.");
    return;
  }
  if (action === "cancel-job") {
    await perform(
      () => command("/jobs/cancel"),
      "진행 중인 AI 분석 작업을 취소했습니다.",
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
  if (action === "delete-complaint") {
    if (!c) return;
    openModal(
      "민원을 삭제하시겠어요?",
      `<form id="confirm-form" class="modal-content" data-id="${id}" data-version="${c.version}" data-kind="delete-complaint"><p><strong>${esc(c.title)}</strong> 민원을 서버에서 완전히 삭제합니다. 삭제한 민원은 복구할 수 없으며 내 민원과 공개 목록에서 모두 사라집니다.</p><div class="form-footer">${button("취소", "", 'type="button" data-action="close-modal"')}${button("삭제하기", "danger", 'type="submit"')}</div></form>`,
    );
    return;
  }
  if (action === "insert-phrase") {
    const field = $("#answer");
    if (!field) return;
    const start = field.selectionStart ?? field.value.length;
    const end = field.selectionEnd ?? start;
    const before = field.value.slice(0, start);
    const sep = before && !before.endsWith("\n") ? "\n" : "";
    field.setRangeText(sep + target.dataset.phrase, start, end, "end");
    field.dispatchEvent(new Event("input", { bubbles: true }));
    field.focus();
    return;
  }
  if (action === "compare") {
    const llmMeta = c.aiAssist
      ? resolveLlmMeta(c.job?.provider, c.aiAssist)
      : null;
    const codexItems = (c.aiAssist?.codex || []).filter(
      (call) => typeof call?.prompt === "string" && call.prompt,
    );
    const traceHtml = c.aiAssist
      ? `<details class="staff-trace-details"><summary>${esc(llmMeta?.dataTitle || "LLM 호출 데이터")} · ${esc(llmMeta?.chipText || "")}</summary><h4>${esc(llmMeta?.dataTitle || "LLM에 보낸 데이터")}</h4><pre class="compare-box">${esc(JSON.stringify(c.aiAssist.codex || [], null, 2))}</pre><h4>${esc(llmMeta?.promptTitle || "LLM에 보낸 프롬프트")}</h4>${
          codexItems.length
            ? codexItems
                .map(
                  (call, idx) =>
                    `<details><summary>${idx + 1}. ${esc(ROLE_PROMPT_NAMES[call.role] || call.role || "호출")} · ${esc(call.system || "")} · ${call.sent ? "보냄" : "보내지 않음"}</summary><pre class="compare-box">${esc(call.prompt)}</pre></details>`,
                )
                .join("")
            : `<p class="muted">${esc(llmMeta?.emptyPromptNote || "프롬프트 없음")}</p>`
        }</details>`
      : "";
    openModal(
      "AI 원문과 추론·답변 이력",
      `<div class="modal-content"><span class="mini-chip">AI 원본 · 보존됨</span><div class="compare-box prose">${esc(c.aiOriginal || "AI 원본이 없습니다.")}</div>${c.aiCandidate ? `<h3>최신 AI 후보 · 편집본에 자동 덮어쓰기 안 함</h3><div class="compare-box prose">${esc(c.aiCandidate)}</div>` : ""}<h3>저장·게시 이력 ${c.versions.length}개</h3>${
        c.versions
          .slice()
          .reverse()
          .map(
            (v) =>
              `<details><summary>v${v.version} · ${esc(v.kind)} · ${date(v.date)}</summary><p class="prose">${esc(v.text)}</p><small>사유: ${esc(v.reason)}</small></details>`,
          )
          .join("") || "<p>아직 저장한 편집 이력이 없습니다.</p>"
      }${traceHtml}<p class="muted">재실행 후보는 현재 편집본에 자동 적용하지 않으며, 담당자 게시 전까지 시민 화면에 공개되지 않습니다.</p></div>`,
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
  if (action === "job-history") {
    const provTag = c.aiAssist?.llmProvider || c.job?.provider;
    openModal(
      "AI 작업 이벤트 이력",
      `<div class="modal-content"><p class="mono">${c.id}-A${c.job.attempt}${provTag ? ` · ${esc(PROVIDER_SHORT_LABELS[provTag] || provTag)}` : ""}</p><ol class="timeline">${c.job.events.map((e) => `<li><b>${esc(e.stage)}</b><time>${new Date(e.date).toLocaleString("ko-KR")}</time></li>`).join("")}</ol></div>`,
    );
  }
});

document.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (busy) return;
  const form = event.target,
    values = Object.fromEntries(new FormData(form));
  if (form.id === "assist-form") {
    if (!String(values.body || "").trim() || String(values.body).trim().length < 10) {
      toast("제목과 10자 이상의 상세 내용을 입력해 주세요.");
      return;
    }
    await completeLabAssist({
      query: labQuery(values),
      district: values.district || null,
      limit: 5,
      rerank: false,
      provider: values.provider || selectedLabProvider || null,
    });
    return;
  }
  if (form.id === "filters") {
    updateFilter({ ...values, page: "" });
    return;
  }
  if (form.id === "auth-citizen-login-form" || form.id === "auth-staff-login-form") {
    const isStaffLogin = form.id === "auth-staff-login-form";
    try {
      const loggedIn = await loginAccount({
        loginId: String(values.loginId || "").trim(),
        password: String(values.password || ""),
        expectedRole: isStaffLogin ? "staff" : "citizen",
      });
      modal.close();
      staffStream.close();
      toast(`${loggedIn.displayName || loggedIn.loginId} 계정으로 로그인했습니다.`);
      const targetHash = isStaffLogin ? "/staff" : "/citizen/mine";
      if ((isStaffLogin && !route.staff) || (!isStaffLogin && route.staff)) {
        location.hash = targetHash;
      } else {
        await loadScreen();
      }
    } catch (err) {
      authModalError = err?.message || "로그인에 실패했습니다.";
      openModal(
        "계정 로그인 · 본인확인",
        renderAuthModalHtml({
          tab: authModalTab,
          verifyChallenge: authVerifyChallenge,
          actor: getActor(),
          error: authModalError,
        }),
      );
    }
    return;
  }
  if (form.id === "auth-citizen-verify-form") {
    try {
      const name = String(values.name || "").trim();
      const res = await requestCitizenVerify({
        name,
        phone: String(values.phone || "").trim(),
      });
      authVerifyChallenge = { ...res, name };
      authModalError = "";
      openModal(
        "계정 로그인 · 본인확인",
        renderAuthModalHtml({
          tab: "citizen-register",
          verifyChallenge: authVerifyChallenge,
          actor: getActor(),
          error: "",
        }),
      );
    } catch (err) {
      authModalError = err?.message || "본인확인 코드 발급에 실패했습니다.";
      openModal(
        "계정 로그인 · 본인확인",
        renderAuthModalHtml({
          tab: "citizen-register",
          verifyChallenge: null,
          actor: getActor(),
          error: authModalError,
        }),
      );
    }
    return;
  }
  if (form.id === "auth-citizen-register-form") {
    try {
      const createdActor = await registerCitizenAccount({
        loginId: String(values.loginId || "").trim(),
        password: String(values.password || ""),
        displayName: String(values.displayName || authVerifyChallenge?.name || "").trim(),
        challengeId: String(values.challengeId || "").trim(),
        code: String(values.code || "").trim(),
      });
      authVerifyChallenge = null;
      modal.close();
      toast(`${createdActor.displayName} 님 본인확인 및 가입이 완료되었습니다.`);
      if (route.staff) location.hash = "/citizen/mine";
      else await loadScreen();
    } catch (err) {
      authModalError = err?.message || "회원가입에 실패했습니다.";
      openModal(
        "계정 로그인 · 본인확인",
        renderAuthModalHtml({
          tab: "citizen-register",
          verifyChallenge: authVerifyChallenge,
          actor: getActor(),
          error: authModalError,
        }),
      );
    }
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
  if (form.id === "assign-dept-form") {
    const dept = (values.department || "").trim();
    if (!dept) {
      toast("배정할 부서를 선택해 주세요.");
      return;
    }
    const reason = (values.reason || "").trim();
    const ok = await perform(
      () =>
        api("/complaints/" + form.dataset.id + "/assignment", {
          method: "PUT",
          body: {
            version: Number(form.dataset.version),
            department: dept,
            ...(reason ? { reason } : {}),
          },
        }),
      `시연 담당 부서를 "${dept}"(으)로 배정했습니다.`,
    );
    if (ok) modal.close();
    return;
  }
  if (form.id === "template-form") {
    const tplTitle = (values.title || "").trim();
    const content = (values.content || "").trim();
    if (!tplTitle || !content) {
      toast("템플릿 이름과 안내 문구를 모두 입력해 주세요.");
      return;
    }
    const ok = await perform(async () => {
      await api("/templates", {
        method: "POST",
        body: { title: tplTitle, content },
      });
      await loadAnswerTemplates(true);
    }, `"${tplTitle}" 템플릿을 추가했습니다.`);
    if (ok) modal.close();
    return;
  }
  if (form.id === "confirm-form") {
    const kind = form.dataset.kind;
    if (kind === "delete-template") {
      const targetId = form.dataset.id;
      const ok = await perform(async () => {
        await api("/templates/" + encodeURIComponent(targetId), {
          method: "DELETE",
        });
        await loadAnswerTemplates(true);
      }, "답변 템플릿을 삭제했습니다.");
      if (ok) modal.close();
      return;
    }
    if (kind === "delete-complaint") {
      const targetId = form.dataset.id;
      const ok = await perform(
        () =>
          api("/complaints/" + targetId + "/delete", {
            method: "POST",
            body: { version: Number(form.dataset.version) },
          }),
        "민원을 삭제했습니다.",
        false,
      );
      if (ok) {
        if (newlyCreatedId === targetId) newlyCreatedId = null;
        modal.close();
        if (route.path.startsWith("/citizen/detail/")) {
          location.hash = "/citizen/mine";
        } else {
          render();
        }
      }
      return;
    }
    if (!values.reason.trim()) return;
    const withdraw = kind === "withdraw";
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
  if (event.target.id === "answer") {
    $("#answer-count").textContent =
      event.target.value.length.toLocaleString("ko-KR") + "/4,000";
    const state = $("#draft-state");
    if (state) {
      state.textContent = "작성 중 · 저장 안 됨";
      state.classList.add("dirty");
    }
  }
  if (event.target.id === "reason")
    $("#reason-count").textContent = event.target.value.length + "/200";
  if (event.target.id === "dept-search") {
    const select = $("#dept-select");
    if (select) {
      const currentVal = select.value;
      select.innerHTML = buildDepartmentOptionsHtml(
        staffDepartments,
        currentVal,
        event.target.value,
      );
      if (!select.value && event.target.value.trim()) {
        // 검색 결과가 있을 때는 첫 번째 실제 부서를 바로 선택 상태로 맞춘다.
        for (const opt of select.options) {
          if (opt.value && !opt.disabled) {
            select.value = opt.value;
            break;
          }
        }
      }
    }
  }
  if (event.target.id === "title")
    $("#title-count").textContent = event.target.value.length + "/120";
  if (event.target.id === "body")
    $("#body-count").textContent = event.target.value.length + "/2,000";
  if (event.target.id === "followup")
    $("#followup-count").textContent = event.target.value.length + "/500";
  if (event.target.id === "lab-title")
    $("#lab-title-count").textContent = event.target.value.length + "/120";
  if (event.target.id === "lab-body")
    $("#lab-body-count").textContent = event.target.value.length + "/2,000";
  if (event.target.id === "api-docs-search") {
    apiDocsQuery = event.target.value;
    const list = $("#api-docs-endpoint-list");
    const count = $("#api-docs-count");
    if (list) {
      const result = renderApiEndpointListHtml(openApiSummary || openApiSpec, {
        tag: apiDocsTag,
        query: apiDocsQuery,
      });
      list.innerHTML = result.html;
      if (count) count.textContent = String(result.count);
    }
  }
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
document.addEventListener("change", (event) => {
  if (event.target.id === "chat-district") {
    chatDistrict = event.target.value || "";
  }
});
window.addEventListener("beforeunload", () => {
  staffStream.close(false);
});
setInterval(async () => {
  if (busy || document.hidden || !currentRoute().staff) return;
  // 정상 SSE 연결 중(실제 AI)에는 중복 폴링을 하지 않고, 장애 대체(fallback) 또는 단계 시연 실행 중에만 3초 조회합니다.
  const needsFallbackPoll =
    sseState === "fallback" ||
    (!sseAiConnected && data?.complaints.some((c) => c.job?.status === "running"));
  if (!needsFallbackPoll) return;
  await syncStaffFromServer();
}, 3000);
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
  // 담당자 답변 편집기에서 Ctrl+S(⌘S)는 브라우저 저장 대신 초안 저장으로 처리합니다.
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
    const form = $("#answer-form");
    if (form) {
      event.preventDefault();
      form.requestSubmit();
    }
    return;
  }
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
