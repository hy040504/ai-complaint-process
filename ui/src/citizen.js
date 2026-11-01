/**
 * 예시 HTML의 시민 화면 구성과 시각 요소를 실제 업무 데이터에 연결합니다.
 */
import { icon } from "./icons.js";
import { serviceIcon } from "./service-icons.js";
import { themeButton } from "./theme.js";
import { visible, statusNames } from "./store.js";

export const citizenNotices = [
  {
    id: "road",
    emoji: "🚧",
    tone: "amber",
    title: "도로·시설 불편, 위치를 함께 알려주세요",
    tag: "작성 안내",
    category: "도로·교통",
    body: "도로 파손이나 가로등 고장을 남길 때 발생 위치와 불편한 상황을 구체적으로 적어 주세요. 담당자가 내용을 확인하는 데 도움이 됩니다. 이 글은 시연 사이트 이용 안내이며 공사 일정이나 실제 행정 공지가 아닙니다.",
    prompt: "우리집 앞 가로등이 밤새 깜빡거려요.",
  },
  {
    id: "environment",
    emoji: "♻️",
    tone: "green",
    title: "깨끗한 우리 동네를 위한 생활 민원 안내",
    tag: "이용 안내",
    category: "환경·청소",
    body: "쓰레기나 생활 환경으로 불편한 점이 있다면 발생 장소와 상황을 남겨 주세요. 실제 배출 방법·수거 일정은 담당자 확인이 필요합니다. 현재 AI 도우미는 상담 흐름을 보여주는 시연입니다.",
    prompt: "집 근처에 쓰레기가 쌓여 있어 확인을 요청하고 싶어요.",
  },
  {
    id: "transport",
    emoji: "🚌",
    tone: "blue",
    title: "대중교통 이용 불편, 이렇게 남겨주세요",
    tag: "작성 안내",
    category: "도로·교통",
    body: "이용한 노선과 장소, 발생 시각 등 확인에 필요한 내용을 민원에 적어 주세요. 이름·연락처 등 실제 개인정보는 입력하지 마세요. 이곳에서 등록하는 민원은 청주시 공식 접수와 연결되지 않습니다.",
    prompt: "시내버스 이용 중 겪은 불편을 남기고 싶어요.",
  },
  {
    id: "service",
    emoji: "💬",
    tone: "green",
    title: "청주톡톡에서 내 민원과 답변을 확인하세요",
    tag: "서비스 안내",
    category: "이용 안내",
    body: "등록한 글은 나의 민원에서 확인할 수 있습니다. 담당자가 게시한 답변이 있으면 상세 화면에서 볼 수 있고, 추가 문의를 남길 수 있습니다. 아래 알림 메뉴는 사이트 안의 게시 답변을 모아 보여 주며 실제 문자 발송 기능은 아닙니다.",
    prompt: "민원을 처음 작성하려는데 어떻게 시작하면 되나요?",
  },
];

export const citizenServices = [
  ["parking", "불법주정차", "불법 주정차로 통행이 불편해요."],
  ["documents", "서류 안내", "필요한 서류를 어디에서 확인해야 하나요?"],
  ["roads", "도로·시설", "우리집 앞 가로등이 밤새 깜빡거려요."],
  ["environment", "소음·환경", "밤에 공사 소음이 너무 심해요."],
  ["recycling", "폐기물", "대형폐기물 배출 방법을 문의하고 싶어요."],
  ["water", "상수도", "수돗물에서 녹물이 나와요."],
  ["parks", "공원·녹지", "놀이터 그네가 부서졌어요."],
  ["pets", "반려동물", "동네에서 유기견을 발견했어요."],
  ["housing", "주택·건축", "주택과 건축에 관해 문의하고 싶어요."],
  ["taxes", "지방세", "지방세 관련 문의를 남기고 싶어요."],
  ["welfare", "생활·복지", "복지 관련 상담이 필요해요."],
  ["transit", "대중교통", "시내버스 이용 불편을 남기고 싶어요."],
];

/**
 * 출력할 시민 입력·데이터를 HTML 문자로 이스케이프합니다.
 *
 * @param {unknown} value 변환하거나 적용할 값입니다.
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
export function escapeHTML(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (ch) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        ch
      ],
  );
}
const e = escapeHTML;
/** 화면 안에서 이동할 링크를 만듭니다. */
const a = (text, path, cls = "") =>
  `<a class="${cls}" href="#${path}"${cls.split(" ").includes("active") ? ' aria-current="page"' : ""}>${text}</a>`;
/** 화면에 필요한 값을 변환합니다. */
const date = (value) =>
  new Date(value).toLocaleDateString("ko-KR", {
    month: "2-digit",
    day: "2-digit",
  });

/**
 * 왼쪽 청주시 CI와 민원톡톡 이름을 결합한 시민 헤더를 구성합니다.
 *
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
export function citizenIdentity() {
  return `<span class="citizen-city-logo" role="img" aria-label="청주시 로고"></span><span class="citizen-slogan">민원<span>톡톡</span><small>시민의 목소리에 더 가까이</small></span>`;
}

/**
 * 하단 다섯 메뉴와 가운데 접수 버튼을 모든 시민 화면에서 유지합니다.
 *
 * @param {string} content 렌더링할 HTML 내용입니다.
 * @param {string} path 화면 경로 또는 API 상대 경로입니다.
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
export function citizenShell(content, path) {
  const tabs = [
    ["home", "홈", "/citizen"],
    ["file", "나의 민원", "/citizen/mine"],
    ["plus", "접수", "/citizen/assistant"],
    ["bell", "알림", "/citizen/updates"],
    ["user", "내 정보", "/citizen/profile"],
  ];
  const selected = (target) =>
    path === target ||
    (target === "/citizen" &&
      ["/citizen/news", "/citizen/services"].includes(path)) ||
    (target.endsWith("/mine") && path.includes("/detail/")) ||
    (target.endsWith("/assistant") && path.endsWith("/write")) ||
    (target.endsWith("/profile") && path.endsWith("/guide"));
  return `<div class="demo-bar citizen-demo-bar"><div><span class="demo-label">DEMO</span><span>청주 민원 시연 <span class="demo-extra">· 청주시 공식 접수와 연결되지 않는 시연 서비스입니다.</span></span></div><div class="role-switch">${a("시민 사이트", "/citizen", "selected")}${a("담당자 사이트", "/staff")}${a("응대 검사기", "/lab")}</div></div><div class="citizen-shell citizen-reference"><header class="citizen-header"><a class="citizen-identity" href="#/citizen" aria-label="민원톡톡 홈">${citizenIdentity()}</a><nav class="citizen-desktop-nav" aria-label="시민 주요 메뉴">${[
    ["홈", "/citizen"],
    ["나의 민원", "/citizen/mine"],
    ["민원 게시판", "/citizen/board"],
    ["이용 안내", "/citizen/guide"],
  ]
    .map(([label, target]) =>
      a(label, target, selected(target) ? "active" : ""),
    )
    .join(
      "",
    )}</nav><div class="citizen-header-actions">${themeButton()}${a(icon("bell", 21), "/citizen/updates", "icon-btn")}${a(`${icon("plus", 17)} 직접 작성`, "/citizen/write", "btn primary")}</div></header><main id="main" tabindex="-1">${content}</main><footer><span>청주톡톡 <b>말하듯 접수하고, 눈으로 확인하세요</b></span><span>시연 서비스 · 공식 접수·행정 이관 미연동</span></footer><nav class="citizen-bottom-nav" aria-label="시민 하단 메뉴">${tabs.map(([ic, label, target], index) => a(`<span class="bottom-icon">${icon(ic, index === 2 ? 25 : 21)}</span><span>${label}</span>`, target, `${selected(target) ? "active " : ""}${index === 2 ? "citizen-fab" : ""}`)).join("")}</nav></div>`;
}

/**
 * 실제로 저장된 민원 수와 게시 답변 수를 표시합니다.
 *
 * @param {object} data 현재 역할로 조회한 업무 스냅샷입니다.
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
function summary(data) {
  const mine = visible(data, true);
  const recent =
    mine.find((c) => ["submitted", "under_review"].includes(c.status)) ||
    mine[0];
  return `<section class="citizen-status-card"><div class="citizen-section-label"><h2>나의 민원 현황</h2>${a("전체 보기 ›", "/citizen/mine")}</div><div class="citizen-counts">${[
    ["submitted", "접수 대기"],
    ["under_review", "검토 중"],
    ["answered", "답변 완료"],
  ]
    .map(([key, label]) =>
      a(
        `<strong>${mine.filter((c) => c.status === key).length}<small>건</small></strong><span>${label}</span>`,
        `/citizen/mine?status=${key}`,
      ),
    )
    .join(
      "",
    )}</div>${recent ? a(`<span class="citizen-ring">${icon(["answered", "closed"].includes(recent.status) ? "check" : "clock", 22)}</span><div><b>${e(recent.title)}</b><small>${date(recent.date)} · ${statusNames[recent.status]}</small></div>${icon("chevron", 16)}`, `/citizen/detail/${recent.id}`, "citizen-recent") : '<p class="citizen-empty-note">아직 남긴 민원이 없어요. 일상의 작은 불편부터 이야기해 주세요.</p>'}</section>`;
}

/**
 * 허위 행정 일정 없이 서비스 이용 안내를 소식 카드로 제공합니다.
 *
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
function noticeRows() {
  return `<div class="citizen-news-list">${citizenNotices.map((n, index) => `<button class="citizen-news-row ${index === 0 ? "fresh" : ""}" data-action="citizen-notice" data-id="${n.id}"><span class="citizen-news-icon ${n.tone}">${n.emoji}</span><span class="citizen-news-copy"><b>${n.title}</b><span><em>${n.tag}</em><small>${n.category}</small>${index === 0 ? "<i>시연 안내</i>" : ""}</span></span>${icon("chevron", 16)}</button>`).join("")}</div>`;
}

/**
 * 서비스 선택 시 질문을 채운 상담 화면으로 연결합니다.
 *
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
function serviceButtons() {
  return citizenServices
    .map(
      ([name, label, prompt]) =>
        `<button class="citizen-service" data-action="citizen-service" data-prompt="${e(prompt)}"><span>${serviceIcon(name)}</span><b>${label}</b></button>`,
    )
    .join("");
}

/**
 * 원본의 소식·서비스·말하듯 접수 순서를 PC와 모바일에 맞게 배치합니다.
 *
 * @param {object} data 현재 역할로 조회한 업무 스냅샷입니다.
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
export function citizenHome(data) {
  return `<div class="citizen-home-layout"><div class="citizen-home-main"><section class="citizen-welcome"><div><span>청주시 AI 스마트 민원</span><h1>작은 불편도, 궁금한 일도<br><em>청주톡톡</em>에 남겨주세요.</h1><p>부서를 몰라도 괜찮아요. 평소 말하듯 시작해 보세요.</p></div><span class="citizen-welcome-symbol" aria-hidden="true">${icon("chat", 42)}<i>톡!</i></span></section><section class="citizen-news-section citizen-reveal"><div class="citizen-section-label"><h2>우리 동네 소식 <span>시연 이용 안내</span></h2>${a("전체보기 ›", "/citizen/news")}</div>${noticeRows()}</section><section class="citizen-services-section citizen-reveal"><div class="citizen-section-label"><h2>자주 찾는 서비스</h2>${a("전체 보기 ›", "/citizen/services")}</div><div class="citizen-service-rail" aria-label="자주 찾는 서비스, 가로로 넘겨보세요" tabindex="0">${serviceButtons()}</div><p class="citizen-rail-hint">${icon("arrow", 12)} 옆으로 넘겨 더 많은 서비스를 찾아보세요</p></section><section class="citizen-ask-zone citizen-reveal"><h2>궁금한 건 <em>말하듯이</em> 물어보세요</h2><a class="citizen-askbar" href="#/citizen/assistant"><span class="citizen-ask-icon">${icon("chat", 24)}</span><span class="citizen-ask-copy"><b>여기를 눌러 대화를 시작하세요</b><span>예) 우리집 앞 가로등이 깜빡거려요</span></span><span class="citizen-ask-go">접수 시작 ${icon("arrow", 15)}</span></a><p>${icon("spark", 13)} 상담 흐름 시연 · 실제 AI는 아직 연결되지 않았어요</p></section><div class="citizen-mobile-status">${summary(data)}</div></div><aside class="citizen-home-aside"><div class="citizen-desktop-status">${summary(data)}</div><section class="citizen-how-card"><div class="citizen-section-label"><h2>이렇게 이용하세요</h2>${icon("shield", 18)}</div>${[
    [
      "01",
      "말하듯 편하게",
      "불편한 점을 알려주시면, 작성할 내용을 함께 정리해요.",
    ],
    [
      "02",
      "눈으로 확인해요",
      "나의 민원에서 등록 상태와 게시된 답변을 확인할 수 있어요.",
    ],
    [
      "03",
      "다시 이어 물어요",
      "더 궁금한 점은 추가 문의로 남기고 담당자 검토를 요청하세요.",
    ],
  ]
    .map(
      ([n, title, body]) =>
        `<div class="citizen-how-step"><span>${n}</span><div><b>${title}</b><p>${body}</p></div></div>`,
    )
    .join(
      "",
    )}${a("이용 안내 자세히 보기 →", "/citizen/guide", "text-link")}</section><div class="citizen-service-note">${icon("help", 17)}<p>이 사이트에 등록한 민원은 <b>시연용으로 저장</b>되며, 청주시 공식 민원으로 접수되지 않습니다.</p></div></aside></div>`;
}

/**
 * 원본의 서비스 전체보기와 같은 카드 메뉴입니다.
 *
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
export function citizenServicesPage() {
  return `<div class="page-content narrow citizen-utility"><a class="back-link" href="#/citizen">← 홈으로</a><div class="page-heading"><div><div class="eyebrow">QUICK SERVICE</div><h1>자주 찾는 서비스</h1><p>궁금한 분야를 고르면 질문이 입력된 채로 대화를 시작해요.</p></div></div><div class="citizen-all-services">${serviceButtons()}</div><div class="info-banner">${icon("spark", 18)} 선택한 항목으로 담당 부서를 자동 확정하지 않습니다. 상담은 시연 흐름입니다.</div></div>`;
}

/**
 * 원본과 같은 소식 목록에서 이용 안내를 바텀시트로 엽니다.
 *
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
export function citizenNewsPage() {
  return `<div class="page-content narrow citizen-utility"><a class="back-link" href="#/citizen">← 홈으로</a><div class="page-heading"><div><div class="eyebrow">OUR NEIGHBORHOOD</div><h1>우리 동네 소식</h1><p>청주톡톡 이용을 돕는 시연 안내입니다. 실제 행정 공지와 구별해 주세요.</p></div></div>${noticeRows()}</div>`;
}

/**
 * 문자 발송을 가장하지 않고 서버의 게시 답변만 알림에 모읍니다.
 *
 * @param {object} data 현재 역할로 조회한 업무 스냅샷입니다.
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
export function citizenUpdates(data) {
  const rows = visible(data, true)
    .filter((c) => c.published)
    .sort((x, y) => new Date(y.published.date) - new Date(x.published.date));
  return `<div class="page-content narrow citizen-utility"><div class="page-heading"><div><div class="eyebrow">MY UPDATES</div><h1>내 민원 알림</h1><p>새로 게시된 답변을 모아 보여드려요. 실제 문자 발송은 연결되어 있지 않습니다.</p></div></div><div class="citizen-updates">${rows.length ? rows.map((c) => a(`<span class="citizen-news-icon blue">${icon("chat", 22)}</span><div><b>민원에 답변이 도착했어요</b><p>${e(c.title)}</p><small>${date(c.published.date)} · 게시된 답변 확인</small></div>${icon("chevron", 17)}`, `/citizen/detail/${c.id}`, "citizen-update-row")).join("") : `<div class="panel empty">${icon("bell", 35)}<h2>아직 게시된 답변이 없어요</h2><p>담당자가 답변을 게시하면 이곳에서 확인할 수 있어요.</p>${a("나의 민원 확인", "/citizen/mine", "btn primary")}</div>`}</div></div>`;
}

/**
 * 시연 계정 정보와 실제로 이용 가능한 메뉴만 제공합니다.
 *
 * @param {object} data 현재 역할로 조회한 업무 스냅샷입니다.
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
export function citizenProfile(data) {
  return `<div class="page-content narrow citizen-utility"><div class="page-heading"><div><div class="eyebrow">MY PAGE</div><h1>내 정보</h1><p>나의 민원과 이용 정보를 한곳에서 확인하세요.</p></div></div><section class="citizen-profile-card"><span>${icon("user", 27)}</span><div><b>시민님 <em>시연 계정</em></b><p>현재 나의 민원 ${visible(data, true).length}건</p></div></section><div class="citizen-profile-menu">${[
    ["file", "나의 민원", "/citizen/mine"],
    ["bell", "답변 알림", "/citizen/updates"],
    ["grid", "민원 게시판", "/citizen/board"],
    ["plus", "작성 중인 민원 이어쓰기", "/citizen/write"],
    ["help", "이용 안내", "/citizen/guide"],
  ]
    .map(([ic, label, target]) =>
      a(`${icon(ic, 21)}<span>${label}</span>${icon("chevron", 17)}`, target),
    )
    .join(
      "",
    )}</div><div class="info-banner">${icon("shield", 18)} 운영용 본인인증이 아닌 로컬 시연 계정입니다. 실제 개인정보를 입력하지 마세요.</div></div>`;
}

/**
 * 모션 감소 설정을 존중하는 짧은 첫 방문 인사 효과입니다.
 *
 * @returns {void} 반환값 없이 화면 상태를 갱신합니다.
 */
export function showCitizenIntro() {
  try {
    if (sessionStorage.getItem("citizen-intro-seen")) return;
    sessionStorage.setItem("citizen-intro-seen", "1");
  } catch {
    return;
  }
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const intro = document.createElement("div");
  intro.className = "citizen-intro";
  intro.setAttribute("aria-hidden", "true");
  intro.innerHTML = `${citizenIdentity()}<hr><b>AI 스마트 민원</b><p>말하듯 접수하고, 눈으로 확인하세요</p><small>청주톡톡 · 시연 서비스</small>`;
  document.body.append(intro);
  setTimeout(() => {
    intro.classList.add("leaving");
    setTimeout(() => intro.remove(), 230);
  }, 800);
}
