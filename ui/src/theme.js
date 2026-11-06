/**
 * 시민·담당자 화면이 공유하는 저장형 테마 선택을 관리합니다.
 */
import { icon } from "./icons.js";

export const THEME_KEY = "minwon-ui-theme";
let current = "light";

/**
 * 저장 가능 여부와 관계없이 현재 탭의 테마를 반환합니다.
 * @returns {"light"|"dark"} 현재 적용한 테마입니다.
 */
export function getTheme() {
  return current;
}

/**
 * 저장된 테마를 읽고 브라우저 저장소를 사용할 수 없으면 라이트로 설정합니다.
 *
 * @returns {string} 저장된 테마 또는 기본 테마입니다.
 */
export function readTheme() {
  try {
    return localStorage.getItem(THEME_KEY) === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

/**
 * 테마 선택·저장과 버튼의 아이콘·접근성 이름을 갱신합니다.
 *
 * @param {unknown} value 변환하거나 적용할 값입니다.
 * @param {boolean} [persist=true] 선택값을 브라우저에 저장할지 여부입니다.
 * @returns {void} 반환값 없이 화면 상태를 갱신합니다.
 */
export function setTheme(value, persist = true) {
  current = value === "dark" ? "dark" : "light";
  document.body.dataset.theme = current;
  document.documentElement.style.colorScheme = current;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta)
    meta.content =
      current === "dark"
        ? "#101827"
        : document.body.dataset.site === "staff"
          ? "#16203a"
          : "#2f6fed";
  if (persist) {
    try {
      localStorage.setItem(THEME_KEY, current);
    } catch {
      /* 저장에 실패해도 현재 탭의 테마 선택은 적용합니다. */
    }
  }
  document
    .querySelectorAll('[data-action="theme-toggle"]')
    .forEach((button) => {
      const label =
        current === "dark" ? "라이트 테마로 전환" : "다크 테마로 전환";
      button.innerHTML = icon(current === "dark" ? "sun" : "moon", 19);
      button.setAttribute("aria-label", label);
      button.setAttribute("title", label);
      button.setAttribute("aria-pressed", String(current === "dark"));
    });
}

/**
 * 다음 테마를 나타내는 아이콘과 접근 가능한 버튼 이름을 만듭니다.
 *
 * @returns {string} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
export function themeButton() {
  const label = current === "dark" ? "라이트 테마로 전환" : "다크 테마로 전환";
  return `<button class="icon-btn theme-toggle" type="button" data-action="theme-toggle" aria-label="${label}" title="${label}" aria-pressed="${current === "dark"}">${icon(current === "dark" ? "sun" : "moon", 19)}</button>`;
}
