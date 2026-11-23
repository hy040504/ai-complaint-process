/**
 * 시민 사이트(`/`)와 담당자 사이트(`/staff/`)를 구분하는 공통 모듈입니다.
 *
 * 각 진입 HTML(`index.html`·`staff.html`)이 `<html data-site="...">`로 사이트를 선언하고,
 * 이 모듈은 그 값으로 요청 헤더·허용 경로·기본 경로를 결정합니다. 서버는 같은 헤더로
 * 사이트별 세션 쿠키를 분리합니다.
 */

/** 서버가 사이트별 세션 쿠키를 고를 때 읽는 요청 헤더 이름입니다. */
export const SITE_HEADER = "X-Cheongju-Site";

/**
 * 현재 페이지가 선언한 사이트를 읽습니다. 선언이 없거나 브라우저가 아니면 시민입니다.
 *
 * @returns {"citizen"|"staff"|"lab"} 현재 사이트입니다. `lab`은 응대 검사기 단독 페이지(`/lab/`)입니다.
 */
function readSite() {
  if (typeof document === "undefined") return "citizen";
  const declared = document.documentElement?.dataset?.site;
  return declared === "staff" || declared === "lab" ? declared : "citizen";
}

/** 현재 사이트(`citizen`·`staff`·`lab`)입니다. */
export const SITE = readSite();

/**
 * 모든 API 요청에 붙일 사이트 헤더를 반환합니다.
 *
 * 응대 검사기 페이지(`lab`)는 담당자 로그인 세션을 쓰므로 헤더는 `staff`로 보냅니다.
 *
 * @param {Object<string,string>} [extra] 함께 보낼 추가 헤더입니다.
 * @returns {Object<string,string>} 사이트 헤더가 포함된 헤더 객체입니다.
 */
export function siteHeaders(extra = {}) {
  return { [SITE_HEADER]: SITE === "lab" ? "staff" : SITE, ...extra };
}

/**
 * 사이트의 기본 화면 경로를 반환합니다.
 *
 * @param {"citizen"|"staff"|"lab"} [site] 대상 사이트입니다. 기본은 현재 사이트입니다.
 * @returns {string} 해시 경로(`/citizen`·`/staff`·`/lab`)입니다.
 */
export function homePath(site = SITE) {
  if (site === "lab") return "/lab";
  return site === "staff" ? "/staff" : "/citizen";
}

/**
 * 해시 경로를 현재 사이트에서 허용하는 경로로 바로잡습니다.
 *
 * 시민 사이트는 `/citizen*`만, 담당자 사이트는 `/staff*`만, 응대 검사기 페이지는 `/lab`만 허용합니다.
 * 허용하지 않는 경로는 사이트 홈으로 돌립니다.
 *
 * @param {string} path `#` 뒤 경로(쿼리 제외)입니다.
 * @param {"citizen"|"staff"|"lab"} [site] 대상 사이트입니다. 기본은 현재 사이트입니다.
 * @returns {string} 허용된 경로입니다.
 */
export function normalizePath(path, site = SITE) {
  const value = path || "";
  if (site === "lab") return "/lab";
  if (site === "staff") {
    return value.startsWith("/staff") ? value : "/staff";
  }
  return value.startsWith("/citizen") ? value : "/citizen";
}
