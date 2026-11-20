/**
 * 운영용 시민 2단계 본인확인 가입·비밀번호 로그인 및 담당자 부서별 계정 로그인 모달 UI입니다.
 *
 * 실제 외부 이동통신사 PASS·행정 SSO 연동과 구분되는 로컬 서버 인증(`scrypt` 해시·
 * 6자리 OTP 챌린지·5회 실패 잠금·부서 권한) 화면을 제공합니다.
 */

import { escapeHTML as esc } from "./citizen.js";
import { icon } from "./icons.js";

/**
 * 사용자의 인증 방식에 맞는 짧은 상태 배지 HTML을 만듭니다.
 *
 * @param {object|null} actor 현재 서버 세션의 `Actor` 객체입니다.
 * @returns {string} 상태 배지 HTML 문자열입니다.
 */
export function renderAuthBadge(actor) {
  if (!actor) return '<span class="auth-badge demo">미인증</span>';
  if (!actor.demo && actor.role === "citizen" && actor.verified) {
    return '<span class="auth-badge verified">본인확인 완료</span>';
  }
  if (!actor.demo && actor.role === "staff") {
    return '<span class="auth-badge staff-auth">담당자 인증</span>';
  }
  return '<span class="auth-badge demo">시연 계정</span>';
}

/**
 * 시민 로그인·본인확인 회원가입·담당자 로그인 탭 모달의 내부 HTML을 생성합니다.
 *
 * @param {object} [options] 모달 렌더링 상태입니다.
 * @param {string} [options.tab="citizen-login"] 활성 탭(`citizen-login`·`citizen-register`·`staff-login`)입니다.
 * @param {object|null} [options.verifyChallenge=null] 1단계 본인확인 발급 결과입니다.
 * @param {object|null} [options.actor=null] 현재 로그인된 사용자 정보입니다.
 * @param {string} [options.error=""] 직전 인증 시도 오류 안내 문구입니다.
 * @returns {string} 모달 본문 HTML 문자열입니다.
 */
export function renderAuthModalHtml({
  tab = "citizen-login",
  verifyChallenge = null,
  actor = null,
  error = "",
} = {}) {
  const tabs = [
    ["citizen-login", "시민 로그인"],
    ["citizen-register", "시민 본인확인·가입"],
    ["staff-login", "담당자 로그인"],
  ];
  const currentBar = actor
    ? `<div class="auth-current-bar"><div><b>${esc(actor.displayName || actor.id)}</b>${actor.department ? ` · <span>${esc(actor.department)}</span>` : ""} ${renderAuthBadge(actor)}</div>${!actor.demo ? '<button type="button" class="btn subtle" data-action="auth-logout">로그아웃</button>' : ""}</div>`
    : "";
  const errorBox = error
    ? `<div class="auth-error-box" role="alert">${icon("help", 15)} <span>${esc(error)}</span></div>`
    : "";

  let bodyHtml = "";
  if (tab === "citizen-login") {
    bodyHtml = `<form id="auth-citizen-login-form" class="auth-form">
      <p class="auth-desc">본인확인으로 가입한 시민 계정으로 로그인하면 본인 민원만 안전하게 격리·관리할 수 있습니다.</p>
      <label for="auth-cit-id">아이디</label>
      <input id="auth-cit-id" name="loginId" required minlength="3" maxlength="32" autocomplete="username" placeholder="예: cheongju_user">
      <label for="auth-cit-pw">비밀번호</label>
      <input id="auth-cit-pw" name="password" type="password" required minlength="4" maxlength="100" autocomplete="current-password" placeholder="영문+숫자 8자 이상">
      <div class="form-footer"><button type="button" class="btn" data-action="close-modal">닫기</button><button type="submit" class="btn primary">시민 로그인</button></div>
    </form>`;
  } else if (tab === "citizen-register") {
    const otpSection = verifyChallenge
      ? `<div class="auth-otp-box">
          <strong>1단계 본인확인 코드 발급 완료</strong>
          <p>대상 연락처: <b>${esc(verifyChallenge.maskedPhone)}</b> (유효 ${Math.floor((verifyChallenge.expiresInSeconds || 300) / 60)}분)</p>
          ${verifyChallenge.demoCode ? `<p class="auth-otp-code">로컬 검증용 확인 코드: <code>${esc(verifyChallenge.demoCode)}</code></p>` : ""}
        </div>
        <form id="auth-citizen-register-form" class="auth-form">
          <input type="hidden" name="challengeId" value="${esc(verifyChallenge.challengeId)}">
          <input type="hidden" name="displayName" value="${esc(verifyChallenge.name || "")}">
          <label for="auth-reg-code">6자리 본인확인 코드</label>
          <input id="auth-reg-code" name="code" required pattern="[0-9]{6}" maxlength="6" placeholder="숫자 6자리" value="${esc(verifyChallenge.demoCode || "")}">
          <label for="auth-reg-id">사용할 아이디 (영문·숫자 4~32자)</label>
          <input id="auth-reg-id" name="loginId" required pattern="[A-Za-z0-9_.-]{4,32}" maxlength="32" autocomplete="username" placeholder="예: citizen_01">
          <label for="auth-reg-pw">비밀번호 (8자 이상 · 영문+숫자 조합)</label>
          <input id="auth-reg-pw" name="password" type="password" required minlength="8" maxlength="100" autocomplete="new-password" placeholder="예: pass1234">
          <div class="form-footer"><button type="button" class="btn" data-action="auth-tab" data-tab="citizen-register">다시 인증</button><button type="submit" class="btn primary">본인확인 완료 및 가입</button></div>
        </form>`
      : `<form id="auth-citizen-verify-form" class="auth-form">
          <p class="auth-desc">1단계 휴대전화 본인확인 후 6자리 인증코드로 계정을 생성합니다. 전화번호 원문은 저장하지 않고 끝 4자리와 해시만 사용합니다.</p>
          <label for="auth-ver-name">성명 (2~30자)</label>
          <input id="auth-ver-name" name="name" required minlength="2" maxlength="30" placeholder="예: 홍길동">
          <label for="auth-ver-phone">휴대전화 번호</label>
          <input id="auth-ver-phone" name="phone" required pattern="01[016789]-?[0-9]{3,4}-?[0-9]{4}" placeholder="예: 010-1234-5678">
          <div class="form-footer"><button type="button" class="btn" data-action="close-modal">닫기</button><button type="submit" class="btn primary">본인확인 코드 발급</button></div>
        </form>`;
    bodyHtml = otpSection;
  } else {
    bodyHtml = `<form id="auth-staff-login-form" class="auth-form">
      <p class="auth-desc">공무원 계정으로 로그인하면 소속 부서 권한 범위와 실제 처리자 이름이 모든 이력·버전에 기록됩니다.</p>
      <label for="auth-staff-id">담당자 아이디</label>
      <input id="auth-staff-id" name="loginId" required minlength="3" maxlength="32" autocomplete="username" placeholder="예: staff_admin 또는 staff_seowon">
      <label for="auth-staff-pw">비밀번호</label>
      <input id="auth-staff-pw" name="password" type="password" required minlength="4" maxlength="100" autocomplete="current-password" placeholder="담당자 비밀번호">
      <div class="auth-staff-hints">
        <small>로컬 검증용 기본 담당자 계정 (초기 비밀번호는 환경변수 <code>COMPLAINT_STAFF_INIT_PASSWORD</code>):</small>
        <ul>
          <li><code>staff_admin</code> · 청주시 민원과 총괄 (전 부서 권한)</li>
          <li><code>staff_seowon</code> · 서원구 건설과 (소관 부서 범위)</li>
          <li><code>staff_heungdeok</code> · 흥덕구 환경위생과 (소관 부서 범위)</li>
        </ul>
      </div>
      <div class="form-footer"><button type="button" class="btn" data-action="close-modal">닫기</button><button type="submit" class="btn primary">담당자 로그인</button></div>
    </form>`;
  }

  return `<div class="modal-content auth-modal">
    ${currentBar}
    <div class="auth-tabs" role="tablist">${tabs
      .map(
        ([key, label]) =>
          `<button type="button" role="tab" aria-selected="${tab === key ? "true" : "false"}" class="auth-tab ${tab === key ? "active" : ""}" data-action="auth-tab" data-tab="${key}">${label}</button>`,
      )
      .join("")}</div>
    ${errorBox}
    ${bodyHtml}
  </div>`;
}
