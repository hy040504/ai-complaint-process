/**
 * 민원인·담당자 아이디·비밀번호 로그인 및 민원인 간단 가입 모달 UI입니다.
 *
 * 외부 이동통신사 PASS·행정 SSO 연동은 별도 인프라 범위이며,
 * 로컬 서버 `scrypt` 비밀번호 검증 기반의 단순한 로그인 화면을 제공합니다.
 */

import { escapeHTML as esc } from "./citizen.js";
import { icon } from "./icons.js";
import { SITE } from "./site.js";

/**
 * 현재 로그인된 계정 유형에 맞는 짧은 배지 HTML을 만듭니다.
 *
 * @param {object|null} actor 현재 서버 세션의 `Actor` 객체입니다.
 * @returns {string} 상태 배지 HTML 문자열입니다.
 */
export function renderAuthBadge(actor) {
  if (!actor) return '<span class="auth-badge demo">미로그인</span>';
  if (!actor.demo && actor.role === "citizen") {
    return '<span class="auth-badge verified">민원인</span>';
  }
  if (!actor.demo && actor.role === "staff") {
    return '<span class="auth-badge staff-auth">담당자</span>';
  }
  return '<span class="auth-badge demo">시연</span>';
}

/**
 * 민원인·담당자 아이디/비밀번호 로그인 모달의 내부 HTML을 생성합니다.
 *
 * @param {object} [options] 모달 렌더링 상태입니다.
 * @param {string} [options.tab="citizen-login"] 활성 화면(`citizen-login`·`citizen-register`·`staff-login`)입니다.
 * @param {object|null} [options.actor=null] 현재 로그인된 사용자 정보입니다.
 * @param {string} [options.error=""] 직전 로그인·가입 오류 안내 문구입니다.
 * @param {"citizen"|"staff"} [options.site] 로그인 화면을 보여 줄 사이트입니다. 기본은 현재 사이트입니다.
 * @returns {string} 모달 본문 HTML 문자열입니다.
 */
export function renderAuthModalHtml({
  tab = "citizen-login",
  actor = null,
  error = "",
  site = SITE,
} = {}) {
  // 사이트별로 허용하는 로그인 화면만 노출합니다(시민은 민원인, 담당자는 담당자 전용).
  const tabs =
    site === "staff"
      ? [["staff-login", "담당자 로그인"]]
      : [["citizen-login", "민원인 로그인"]];
  if (site === "staff") tab = "staff-login";
  else if (tab === "staff-login") tab = "citizen-login";
  const isStaffTab = tab === "staff-login";
  const currentBar = actor
    ? `<div class="auth-current-bar"><div><b>${esc(actor.displayName || actor.id)}</b>${actor.department ? ` · <span>${esc(actor.department)}</span>` : ""} ${renderAuthBadge(actor)}</div>${!actor.demo ? '<button type="button" class="btn subtle" data-action="auth-logout">로그아웃</button>' : ""}</div>`
    : "";
  const errorBox = error
    ? `<div class="auth-error-box" role="alert">${icon("help", 15)} <span>${esc(error)}</span></div>`
    : "";

  let bodyHtml = "";
  if (tab === "citizen-login") {
    bodyHtml = `<form id="auth-citizen-login-form" class="auth-form">
      <p class="auth-desc">민원인 아이디와 비밀번호로 로그인하면 본인 민원만 안전하게 조회·관리할 수 있습니다.</p>
      <label for="auth-cit-id">아이디</label>
      <input id="auth-cit-id" name="loginId" required minlength="3" maxlength="32" autocomplete="username" placeholder="아이디 입력">
      <label for="auth-cit-pw">비밀번호</label>
      <input id="auth-cit-pw" name="password" type="password" required minlength="4" maxlength="100" autocomplete="current-password" placeholder="비밀번호 입력">
      <div class="auth-switch-row">
        <span>민원인 계정이 없으신가요?</span>
        <button type="button" class="auth-inline-link" data-action="auth-tab" data-tab="citizen-register">새 민원인 계정 만들기</button>
      </div>
      <div class="form-footer"><button type="button" class="btn" data-action="close-modal">닫기</button><button type="submit" class="btn primary">민원인 로그인</button></div>
    </form>`;
  } else if (tab === "citizen-register") {
    bodyHtml = `<form id="auth-citizen-register-form" class="auth-form">
      <p class="auth-desc">아이디·비밀번호·이름만 입력해 간단히 민원인 계정을 만들고 바로 로그인합니다.</p>
      <label for="auth-reg-name">이름 (2~30자)</label>
      <input id="auth-reg-name" name="displayName" required minlength="2" maxlength="30" placeholder="예: 홍길동">
      <label for="auth-reg-id">아이디 (영문·숫자 3~32자)</label>
      <input id="auth-reg-id" name="loginId" required pattern="[A-Za-z0-9_.-]{3,32}" maxlength="32" autocomplete="username" placeholder="영문·숫자 3~32자">
      <label for="auth-reg-pw">비밀번호 (6자 이상)</label>
      <input id="auth-reg-pw" name="password" type="password" required minlength="6" maxlength="100" autocomplete="new-password" placeholder="6자 이상 입력">
      <div class="form-footer"><button type="button" class="btn" data-action="auth-tab" data-tab="citizen-login">로그인으로 돌아가기</button><button type="submit" class="btn primary">민원인 가입 및 로그인</button></div>
    </form>`;
  } else {
    bodyHtml = `<form id="auth-staff-login-form" class="auth-form">
      <p class="auth-desc">담당자 아이디와 비밀번호로 로그인하면 소속 부서 권한과 처리자 이름이 이력에 기록됩니다.</p>
      <label for="auth-staff-id">담당자 아이디</label>
      <input id="auth-staff-id" name="loginId" required minlength="3" maxlength="32" autocomplete="username" placeholder="담당자 아이디 입력">
      <label for="auth-staff-pw">비밀번호</label>
      <input id="auth-staff-pw" name="password" type="password" required minlength="4" maxlength="100" autocomplete="current-password" placeholder="담당자 비밀번호">
      <div class="form-footer"><button type="button" class="btn" data-action="close-modal">닫기</button><button type="submit" class="btn primary">담당자 로그인</button></div>
    </form>`;
  }

  return `<div class="modal-content auth-modal">
    ${currentBar}
    <div class="auth-tabs" role="tablist">${tabs
      .map(([key, label]) => {
        const active =
          (key === "staff-login" && isStaffTab) ||
          (key === "citizen-login" && !isStaffTab);
        return `<button type="button" role="tab" aria-selected="${active ? "true" : "false"}" class="auth-tab ${active ? "active" : ""}" data-action="auth-tab" data-tab="${key}">${label}</button>`;
      })
      .join("")}</div>
    ${errorBox}
    ${bodyHtml}
  </div>`;
}
