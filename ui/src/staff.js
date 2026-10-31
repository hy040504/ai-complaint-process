/**
 * 예시 민원과 콘솔의 구성을 실제 서버 상태에 맞춰 렌더링합니다.
 */
import { icon } from "./icons.js";
import { themeButton } from "./theme.js";
import { districts, categories, statusNames } from "./store.js";
import { escapeHTML as e } from "./citizen.js";

/** 화면 안에서 이동할 링크를 만듭니다. */
const a = (text, path, cls = "", active = false) =>
  `<a class="${cls}${active ? " active" : ""}" href="#${path}"${active ? ' aria-current="page"' : ""}>${text}</a>`;
/** 등록 시각을 표시용 날짜로 변환합니다. */
const day = (value) =>
  new Date(value).toLocaleDateString("ko-KR", {
    month: "2-digit",
    day: "2-digit",
  });
const jobLabel = {
  queued: "AI 미연동 · 대기",
  running: "단계 시연 중",
  succeeded: "시연 완료",
  failed: "시연 실패",
  cancelled: "시연 취소",
  superseded: "맥락 변경",
};
/** 화면에 필요한 값을 변환합니다. */
const live = (data) =>
  (data?.complaints || []).filter((c) => c.job && c.status !== "withdrawn");
/** 화면에 필요한 값을 변환합니다. */
const open = (c) => ["submitted", "under_review"].includes(c.status);
/** 화면에 필요한 값을 변환합니다. */
const unpublished = (c) => Boolean(c.draft && !c.published);

/**
 * 목록의 현재 필터를 보존하면서 URL 조건을 바꿉니다.
 *
 * @param {string} path 화면 경로 또는 API 상대 경로입니다.
 * @param {URLSearchParams} params 현재 URL의 검색 조건입니다.
 * @param {Object} changes 변경할 검색 조건입니다.
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
function queryLink(path, params, changes) {
  const next = new URLSearchParams(params);
  next.delete("page");
  for (const [key, value] of Object.entries(changes)) {
    if (value) next.set(key, value);
    else next.delete(key);
  }
  return path + (next.size ? "?" + next : "");
}

/**
 * 역할 전환·남색 업무 메뉴·상태바를 담당자 화면에 공통 적용합니다.
 *
 * @param {string} content 렌더링할 HTML 내용입니다.
 * @param {object} route 현재 화면 경로와 역할 정보입니다.
 * @param {object} data 현재 역할로 조회한 업무 스냅샷입니다.
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
export function staffShell(content, route, data) {
  const rows = live(data),
    pending = rows.filter(open).length;
  const mine = rows.filter((c) => c.assigned).length;
  const unassigned = rows.filter((c) => !c.assigned).length;
  const followups = rows.filter((c) => c.messages.length).length;
  const failed = rows.filter((c) => c.job.status === "failed").length;
  const view = route.params.get("view"),
    assign = route.params.get("assign");
  const menu = [
    { group: "WORK" },
    {
      icon: "grid",
      label: "접수 대기·검토",
      path: "/staff",
      count: pending,
      active: route.path === "/staff",
    },
    {
      icon: "user",
      label: "담당 업무",
      path: "/staff/complaints?assign=mine",
      count: mine,
      gold: true,
      active: route.path === "/staff/complaints" && assign === "mine",
    },
    {
      icon: "file",
      label: "전체 민원",
      path: "/staff/complaints",
      active: route.path === "/staff/complaints" && !assign && !view,
    },
    {
      icon: "building",
      label: "담당 미지정",
      path: "/staff/complaints?assign=none",
      count: unassigned,
      active: route.path === "/staff/complaints" && assign === "none",
    },
    { group: "MANAGE" },
    {
      icon: "monitor",
      label: "AI 작업 모니터",
      path: "/staff/monitor",
      count: failed,
      active: route.path === "/staff/monitor",
    },
    {
      icon: "chat",
      label: "추가 문의",
      path: "/staff/complaints?view=followup",
      count: followups,
      active: view === "followup",
    },
    {
      icon: "check",
      label: "게시 답변",
      path: "/staff/complaints?view=published",
      count: rows.filter((c) => c.published).length,
      gold: true,
      active: view === "published",
    },
  ];
  const title = route.path.includes("/detail/")
    ? "민원 상세 검토"
    : route.path.includes("/monitor")
      ? "AI 작업 모니터"
      : route.path === "/staff"
        ? "접수 대기·검토"
        : "민원 업무 목록";
  const nav = menu
    .map((item) =>
      item.group
        ? `<div class="staff-nav-group">${item.group}</div>`
        : a(
            `${icon(item.icon, 17)}<span>${item.label}</span>${item.count ? `<span class="staff-nav-count ${item.gold ? "gold" : ""}">${item.count}</span>` : ""}`,
            item.path,
            "staff-nav-link",
            item.active,
          ),
    )
    .join("");
  return `<div class="demo-bar staff-demo-bar"><div><span class="demo-label">DEMO</span><span>민원톡톡 <span class="demo-extra">· 개인정보 없는 합성 데이터로 체험하는 업무 콘솔</span></span></div><div class="role-switch">${a("시민 사이트", "/citizen")}${a("담당자 사이트", "/staff", "selected")}</div></div><button class="staff-menu-backdrop" data-action="staff-menu-close" aria-label="업무 메뉴 닫기" tabindex="-1"></button><aside class="staff-sidebar" id="staff-sidebar"><div class="staff-console-brand">${a(`<span>MINWON DESK</span><small>민원과 · 담당자 업무 콘솔</small>`, "/staff")}<button class="staff-drawer-close icon-btn" data-action="staff-menu-close" aria-label="업무 메뉴 닫기">${icon("close", 19)}</button></div><nav aria-label="담당자 업무 메뉴">${nav}</nav><div class="staff-sidebar-bottom"><div class="staff-sidebar-policy">${icon("shield", 16)}<b>검토 우선 모드</b><p>담당자가 확인한 답변만<br>시민에게 게시됩니다.</p></div><button class="staff-help-link" data-action="staff-help">${icon("help", 16)} 업무 이용 안내 ${icon("chevron", 13)}</button>${a(`${icon("exit", 16)} 시민 사이트로 이동`, "/citizen", "staff-exit-link")}<div class="staff-account"><span class="staff-account-avatar">김</span><div><b>김담당 <small>시연 계정</small></b><p>민원 검토·답변 담당자</p></div></div></div></aside><div class="staff-shell staff-workspace"><header class="staff-topbar"><button class="staff-menu-toggle icon-btn" data-action="staff-menu-toggle" aria-controls="staff-sidebar" aria-expanded="false" aria-label="업무 메뉴 열기">${icon("menu", 21)}</button><span class="staff-connection"><i></i> 로컬 시연</span><span class="staff-crumb">민원과 <i>/</i> ${title}</span><div class="staff-topbar-right"><span>${icon("shield", 13)} 미게시 초안은 시민 비공개</span>${themeButton()}<button class="icon-btn" data-action="staff-help" aria-label="업무 이용 안내">${icon("help", 18)}</button><span class="staff-mini-avatar">김</span></div></header><nav class="staff-compact-nav" aria-label="담당자 빠른 메뉴">${a("접수·검토", "/staff", "", route.path === "/staff")}${a("전체 민원", "/staff/complaints", "", route.path === "/staff/complaints" && assign !== "mine")}${a("담당 업무", "/staff/complaints?assign=mine", "", assign === "mine")}${a("AI 모니터", "/staff/monitor", "", route.path === "/staff/monitor")}</nav><main id="main" tabindex="-1">${content}</main><footer class="staff-footer"><span>민원톡톡 <b>시민의 목소리를 업무로 잇다</b></span><span>로컬 시연 · 실제 AI·공식 접수·외부 이관 미연동</span></footer></div>`;
}

/**
 * 예시의 요약 카드에 실제 접수·검토·초안·게시 건수를 표시합니다.
 *
 * @param {Array<object>} rows 현재 권한으로 조회한 민원 목록입니다.
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
function metrics(rows) {
  const items = [
    [
      "접수 대기",
      rows.filter((c) => c.status === "submitted").length,
      "등록된 민원을 확인해 주세요",
      "submitted",
      "red",
    ],
    [
      "담당자 검토",
      rows.filter((c) => c.status === "under_review").length,
      "내용·추가 문의 확인 필요",
      "under_review",
      "blue",
    ],
    [
      "미게시 초안",
      rows.filter(unpublished).length,
      "담당자 검토 후 게시",
      "drafts",
      "gold",
    ],
    [
      "게시된 답변",
      rows.filter((c) => c.published).length,
      "시민이 확인할 수 있는 답변",
      "published",
      "green",
    ],
  ];
  return `<div class="staff-kpi-grid">${items.map(([label, count, sub, key, tone]) => a(`<span class="staff-kpi-label">${label}</span><strong>${count}<small>건</small></strong><span class="staff-kpi-sub ${tone}">${sub}</span>`, `/staff/complaints?${["drafts", "published"].includes(key) ? "view" : "status"}=${key}`, "staff-kpi")).join("")}</div>`;
}

/**
 * 원문 일부와 실제 업무 상태를 보여 주는 접근 가능한 민원 행입니다.
 *
 * @param {Array<object>} rows 현재 권한으로 조회한 민원 목록입니다.
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
function queueRows(rows) {
  return rows
    .map((c) =>
      a(
        `<span class="staff-row-code" title="${e(c.id)}">#${e(c.id.split("-").at(-1))}</span><div class="staff-row-content"><div class="staff-row-heading"><h2>${e(c.title)}</h2>${c.messages.length ? `<span class="staff-tag amber">추가 문의 ${c.messages.length}</span>` : ""}${c.visibility === "private" ? `<span class="staff-row-private">${icon("shield", 12)} 비공개</span>` : ""}</div><p class="staff-row-excerpt">원문: ${e(c.body.replace(/\s+/g, " ").slice(0, 82))}${c.body.length > 82 ? "…" : ""}</p><div class="staff-row-meta"><span class="staff-tag navy">${e(c.category)}</span><span>${icon("pin", 11)} ${e(c.district)}</span><span class="staff-tag ${c.assigned ? "gray" : "amber"}">${c.assigned ? "김담당" : "담당자 미지정"}</span>${unpublished(c) ? '<span class="staff-tag gold">검토 전 초안</span>' : ""}${c.job.status === "failed" ? '<span class="staff-tag red">AI 시연 실패</span>' : ""}${c.job.status === "running" ? '<span class="staff-tag blue">단계 시연 중</span>' : ""}${c.published ? '<span class="staff-published-mark">' + icon("check", 11) + " 답변 게시됨</span>" : ""}</div></div><div class="staff-row-state"><span class="badge ${c.status}">${statusNames[c.status]}</span><time>${day(c.date)} 등록</time></div><span class="staff-row-open">${icon("chevron", 16)}</span>`,
        `/staff/detail/${c.id}`,
        "staff-queue-row",
      ),
    )
    .join("");
}

/**
 * 서버 스냅샷에서 검색·담당·문의·초안 조건과 페이지를 적용합니다.
 *
 * @param {object} data 현재 역할로 조회한 업무 스냅샷입니다.
 * @param {URLSearchParams} params 현재 URL의 검색 조건입니다.
 * @param {object} [options] 업무 큐 화면 설정입니다.
 * @param {boolean} [options.landing=false] 접수·검토 첫 화면인지 여부입니다.
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
export function staffQueue(data, params, { landing = false } = {}) {
  const all = live(data),
    path = landing ? "/staff" : "/staff/complaints";
  const scope = params.get("scope") || "all",
    q = params.get("q") || "",
    status = params.get("status") || "",
    district = params.get("district") || "",
    category = params.get("category") || "",
    assign = params.get("assign") || "",
    view = params.get("view") || "";
  let base = all.filter(
    (c) =>
      (!landing || open(c)) &&
      (scope !== "mine" || c.assigned || c.status === "submitted"),
  );
  const totals = {
    all: base.length,
    submitted: base.filter((c) => c.status === "submitted").length,
    review: base.filter((c) => c.status === "under_review").length,
    none: base.filter((c) => !c.assigned).length,
    followup: base.filter((c) => c.messages.length).length,
    drafts: base.filter(unpublished).length,
    failed: base.filter((c) => c.job.status === "failed").length,
    published: base.filter((c) => c.published).length,
  };
  let rows = base.filter(
    (c) =>
      (!q || c.title.toLocaleLowerCase().includes(q.toLocaleLowerCase())) &&
      (!status || c.status === status) &&
      (!district || c.district === district) &&
      (!category || c.category === category) &&
      (!assign || (assign === "mine" ? c.assigned : !c.assigned)) &&
      (!view ||
        (view === "followup"
          ? c.messages.length
          : view === "drafts"
            ? unpublished(c)
            : view === "failed"
              ? c.job.status === "failed"
              : view === "published"
                ? c.published
                : true)),
  );
  const total = rows.length,
    pages = Math.max(1, Math.ceil(total / 8)),
    page = Math.max(1, Math.min(Number(params.get("page")) || 1, pages));
  rows = rows.slice((page - 1) * 8, page * 8);
  const title = landing
    ? "접수 대기·검토"
    : assign === "mine"
      ? "담당 업무"
      : assign === "none"
        ? "담당 미지정 민원"
        : view === "followup"
          ? "추가 문의 검토"
          : view === "published"
            ? "게시 답변 현황"
            : "민원 업무 목록";
  const chips = [
    [
      "전체",
      totals.all,
      { status: "", assign: "", view: "" },
      !status && !assign && !view,
    ],
    [
      "접수 대기",
      totals.submitted,
      { status: "submitted", assign: "", view: "" },
      status === "submitted",
    ],
    [
      "검토 중",
      totals.review,
      { status: "under_review", assign: "", view: "" },
      status === "under_review",
    ],
    [
      "미지정",
      totals.none,
      { status: "", assign: "none", view: "" },
      assign === "none",
    ],
    [
      "미게시 초안",
      totals.drafts,
      { status: "", assign: "", view: "drafts" },
      view === "drafts",
    ],
    [
      "추가 문의",
      totals.followup,
      { status: "", assign: "", view: "followup" },
      view === "followup",
    ],
    [
      "AI 시연 실패",
      totals.failed,
      { status: "", assign: "", view: "failed" },
      view === "failed",
    ],
    [
      "게시 답변",
      totals.published,
      { status: "", assign: "", view: "published" },
      view === "published",
    ],
  ];
  return `<div class="page-content staff-queue-page"><div class="staff-page-title"><h1>${title}</h1><span>${landing ? "M-01" : "M-02"}</span><div class="staff-scope">${a("전체 업무", queryLink(path, params, { scope: "all" }), "", scope === "all")}${a("내 담당·접수 대기", queryLink(path, params, { scope: "mine" }), "", scope === "mine")}</div><small>최신 등록순</small></div>${landing ? `<div class="staff-inbox-banner"><span class="staff-banner-dot"></span><b>접수 대기 민원 ${all.filter((c) => c.status === "submitted").length}건이 있습니다</b><span>담당자 미지정 여부와 민원 내용을 확인해 주세요.</span>${a("접수 대기 보기", "/staff/complaints?status=submitted", "btn primary")}</div>${metrics(all)}` : ""}<div class="staff-section-rule"><h2>${landing ? "검토할 업무 큐" : "민원 검색·검토 목록"}</h2><span>민원·AI 작업·답변 게시 상태를 구분합니다</span></div><div class="staff-filter-chips">${chips.map(([label, count, changes, active]) => a(`${label}<span>${count}</span>`, queryLink(path, params, changes), "staff-filter-chip", active)).join("")}</div><section class="panel staff-queue-panel"><form id="filters" class="staff-filter-form"><div class="search-field">${icon("search", 17)}<input name="q" aria-label="민원 제목 검색" placeholder="민원 제목으로 검색" value="${e(q)}"></div><select name="district" aria-label="지역 선택"><option value="">전체 지역</option>${districts.map((d) => `<option ${district === d ? "selected" : ""}>${d}</option>`).join("")}</select><select name="category" aria-label="분야 선택"><option value="">전체 분야</option>${categories.map((c) => `<option ${category === c ? "selected" : ""}>${c}</option>`).join("")}</select><select name="assign" aria-label="담당 선택"><option value="">전체 담당</option><option value="mine" ${assign === "mine" ? "selected" : ""}>내 담당</option><option value="none" ${assign === "none" ? "selected" : ""}>미지정</option></select><button class="btn primary" type="submit">검색</button><button class="icon-btn" type="button" data-action="reset-filters" aria-label="검색 조건 초기화">${icon("refresh", 17)}</button></form><div class="staff-list-caption"><span>총 <b>${total}</b>건</span><span>민원을 선택하면 상세 검토로 이동합니다</span></div><div class="staff-queue-list">${rows.length ? queueRows(rows) : `<div class="empty">${icon("search", 32)}<h2>조건에 맞는 민원이 없습니다</h2><p>검색어나 필터를 변경해 주세요.</p><button class="btn" data-action="reset-filters">검색 조건 초기화</button></div>`}</div><div class="pagination"><span>${total ? (page - 1) * 8 + 1 : 0}–${Math.min(page * 8, total)} / ${total}건</span><div><button class="btn" data-action="page" data-page="${page - 1}" ${page === 1 ? "disabled" : ""}>‹</button>${Array.from({ length: pages }, (_, i) => `<button class="btn ${page === i + 1 ? "active" : ""}" data-action="page" data-page="${i + 1}" aria-label="${i + 1}페이지">${i + 1}</button>`).join("")}<button class="btn" data-action="page" data-page="${page + 1}" ${page === pages ? "disabled" : ""}>›</button></div><span>페이지당 8건</span></div></section>${landing ? categoryOverview(all) : ""}</div>`;
}

/**
 * 허위 부서 처리율 대신 민원 분야별 실제 검토 건수를 표시합니다.
 *
 * @param {Array<object>} rows 현재 권한으로 조회한 민원 목록입니다.
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
function categoryOverview(rows) {
  const active = rows.filter((c) => c.status === "under_review"),
    values = categories
      .slice(0, 4)
      .map((category) => [
        category,
        active.filter((c) => c.category === category).length,
      ]);
  return `<div class="staff-section-rule"><h2>분야별 검토 현황</h2><span>담당 부서 추천·배정과 구분되는 민원 분류입니다</span></div><section class="panel staff-category-panel">${values.map(([category, count]) => a(`<span>${category}</span><b>${count}<small>건 검토 중</small></b>`, `/staff/complaints?category=${encodeURIComponent(category)}&status=under_review`)).join("")}</section>`;
}

/**
 * 상세 화면의 네 단계는 실제로 저장된 접수·담당·초안·게시 여부입니다.
 *
 * @param {object} c 서버에서 조회한 민원입니다.
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
export function staffProcess(c) {
  const steps = [
    ["서버 접수", true, "민원 원문 저장"],
    ["담당자 지정", c.assigned, c.assigned ? "김담당" : "담당자 미지정"],
    [
      "답변 초안",
      Boolean(c.draft),
      c.draft ? `초안 v${c.draftVersion}` : "초안 작성 대기",
    ],
    [
      "답변 게시",
      Boolean(c.published),
      c.published ? "시민에게 공개됨" : "검토 후 게시",
    ],
  ];
  const first = steps.findIndex((s) => !s[1]);
  return `<section class="panel staff-process"><header><h2>처리 프로세스</h2><span>현재 업무 상태 <b>${statusNames[c.status]}</b>${c.messages.length ? ` · 추가 문의 ${c.messages.length}건` : ""}</span></header><ol>${steps.map(([title, done, sub], i) => `<li class="${done ? "done" : i === first ? "current" : "waiting"}"><span>${done ? icon("check", 16) : i + 1}</span><b>${title}</b><small>${sub}</small></li>`).join("")}</ol></section>`;
}

/**
 * 금색 참고 카드에서 실제 필드와 AI 미연결 경계를 명시합니다.
 *
 * @param {object} c 서버에서 조회한 민원입니다.
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
export function staffReviewInfo(c) {
  return `<section class="panel staff-reference-card"><header><h2>${icon("spark", 16)} 검토 참고 정보</h2><span>실제 AI 미연동</span></header><dl><div><dt>민원 분야</dt><dd>${e(c.category)} <span>· ${e(c.district)}</span></dd></div><div><dt>공개 범위</dt><dd>${c.visibility === "private" ? "비공개 · 작성자와 담당자 열람" : "공개 시연 민원"}</dd></div><div><dt>담당 정보</dt><dd>${c.assigned ? "김담당" : "담당자 미지정"}</dd></div><div><dt>AI 작업</dt><dd>${jobLabel[c.job.status] || c.job.status} <span>· 실제 추론과 구분</span></dd></div><div><dt>참고 근거</dt><dd>공식 FAQ·업무분장 근거 미연결</dd></div></dl><div class="staff-reference-note">과거 사례나 시연 초안을 현행 정책으로 안내하지 않습니다. 원문과 근거를 확인한 후 답변을 게시해 주세요.</div></section>`;
}
