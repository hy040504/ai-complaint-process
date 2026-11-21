/**
 * 두 사이트가 공유하는 동적 효과(카운트업·화면 진입·새 행 플래시) 도우미입니다 (CASE-120).
 *
 * 모든 효과는 사용자가 운영체제에서 "동작 줄이기"를 켜면 건너뜁니다. 화면은 실시간(SSE)
 * 이벤트마다 통째로 다시 그려지므로, 반복 재생되지 않도록 숫자는 값이 바뀔 때만,
 * 진입 효과는 경로가 바뀔 때만 실행합니다.
 */

/**
 * 사용자가 동작 줄이기를 요청했는지 확인합니다.
 *
 * @returns {boolean} 동작 줄이기가 켜져 있으면 true입니다.
 */
export function prefersReducedMotion() {
  return (
    typeof matchMedia === "function" &&
    matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

/**
 * 시작은 느리지 않고 끝에서 부드럽게 멈추는 ease-out 곡선입니다.
 *
 * @param {number} progress 0~1 진행률입니다(범위를 벗어나면 잘라냅니다).
 * @returns {number} 0~1 보정 진행률입니다.
 */
export function easeOutCubic(progress) {
  const x = Math.min(1, Math.max(0, progress));
  return 1 - Math.pow(1 - x, 3);
}

/**
 * 시작값에서 목표값까지 진행률에 맞는 정수를 계산합니다.
 *
 * @param {number} from 시작 값입니다.
 * @param {number} to 목표 값입니다.
 * @param {number} progress 0~1 진행률입니다.
 * @returns {number} 반올림한 중간 값입니다.
 */
export function countValue(from, to, progress) {
  return Math.round(from + (to - from) * easeOutCubic(progress));
}

const lastCounts = new Map();

/**
 * `data-countup="목표"` 요소의 숫자를 0(또는 이전 값)에서 목표까지 올립니다.
 *
 * `data-ck`가 같은 요소는 이전에 보여 준 값에서 이어 올라가므로, 화면이 다시 그려져도
 * 값이 바뀌지 않았다면 즉시 최종 값을 보여 줍니다.
 *
 * @param {ParentNode} [root=document] 탐색 기준 노드입니다.
 * @param {{duration?: number}} [options] 지속 시간(ms)입니다.
 * @returns {void}
 */
export function runCountUps(root = document, { duration = 900 } = {}) {
  root.querySelectorAll("[data-countup]").forEach((el) => {
    const to = Number(el.dataset.countup);
    if (!Number.isFinite(to)) return;
    const key = el.dataset.ck || "";
    const from = key && lastCounts.has(key) ? lastCounts.get(key) : 0;
    if (key) lastCounts.set(key, to);
    if (prefersReducedMotion() || from === to) {
      el.textContent = String(to);
      return;
    }
    const start = performance.now();
    el.textContent = String(from);
    const tick = (now) => {
      const progress = (now - start) / duration;
      if (progress < 1 && el.isConnected) {
        el.textContent = String(countValue(from, to, progress));
        requestAnimationFrame(tick);
      } else {
        el.textContent = String(to);
      }
    };
    requestAnimationFrame(tick);
  });
}

let lastEnterKey = "";

/**
 * 화면(경로)이 바뀐 직후 한 번만 주요 블록을 12px 올라오며 나타나게 합니다.
 *
 * @param {ParentNode} root 새로 그린 화면의 루트입니다.
 * @param {string} key 현재 경로 식별자입니다. 이전과 같으면 아무것도 하지 않습니다.
 * @returns {number} 효과를 건 요소 수입니다(동작 줄이기·미지원이면 0).
 */
export function enterAnimate(root, key) {
  if (key === lastEnterKey) return 0;
  lastEnterKey = key;
  if (prefersReducedMotion() || typeof Element.prototype.animate !== "function") {
    return 0;
  }
  const targets = [
    ...root.querySelectorAll(
      ".page-content > *:not(.staff-kpi-grid):not(.stats-kpi-grid), .citizen-home-main > *, .citizen-home-aside > *, .staff-kpi",
    ),
  ];
  const picked = targets.filter(
    (el) => !targets.some((other) => other !== el && other.contains(el)),
  );
  picked.forEach((el, index) => {
    el.animate(
      [
        { opacity: 0, transform: "translateY(12px)" },
        { opacity: 1, transform: "none" },
      ],
      {
        duration: 420,
        delay: Math.min(index, 8) * 60,
        easing: "cubic-bezier(0.2, 0.7, 0.2, 1)",
        fill: "backwards",
      },
    );
  });
  return picked.length;
}

let seenRowIds = null;
let seenRowKey = "";
const FLASH_MS = 2600;
const flashStart = new Map();

/**
 * 담당자 큐에 새로 나타난 민원 행에 `row-flash`를 붙여 눈에 띄게 합니다.
 *
 * 화면 경로·필터(키)가 바뀌면 기준을 새로 잡아, 필터 전환으로 보이게 된 행에는 반응하지
 * 않습니다. 실시간 갱신으로 같은 화면에 새 행이 생겼을 때만 플래시합니다. 새 민원이 들어올 때는
 * 이벤트가 연달아 와 화면이 여러 번 다시 그려지므로, 플래시 시작 시각을 기억해 다시 그려진
 * 행에도 남은 시간만큼 이어서 재생합니다(`animation-delay` 음수 값).
 *
 * @param {ParentNode} root 새로 그린 화면의 루트입니다.
 * @param {string} key 현재 경로+쿼리 식별자입니다.
 * @returns {string[]} 플래시한 민원 식별자 목록입니다.
 */
export function flashNewRows(root, key) {
  const links = [
    ...root.querySelectorAll('.staff-queue-item a[href^="#/staff/detail/"]'),
  ];
  const ids = links.map((a) => a.getAttribute("href").split("/").pop());
  if (key !== seenRowKey || seenRowIds === null) {
    seenRowKey = key;
    seenRowIds = new Set(ids);
    flashStart.clear();
    return [];
  }
  const now = Date.now();
  const fresh = [];
  links.forEach((a, index) => {
    const id = ids[index];
    const row = a.closest(".staff-queue-item");
    if (!row) return;
    if (!seenRowIds.has(id)) {
      seenRowIds.add(id);
      flashStart.set(id, now);
      fresh.push(id);
    }
    const started = flashStart.get(id);
    if (started === undefined) return;
    const elapsed = now - started;
    if (elapsed < FLASH_MS) {
      row.classList.add("row-flash");
      row.style.animationDelay = `-${Math.round(elapsed)}ms`;
    } else {
      flashStart.delete(id);
    }
  });
  return fresh;
}

/**
 * 화면을 새로 그린 직후 호출해 모든 동적 효과를 적용합니다.
 *
 * @param {ParentNode} root 새로 그린 화면의 루트입니다.
 * @param {string} path 현재 경로(쿼리 제외)입니다.
 * @param {string} fullKey 쿼리를 포함한 현재 해시입니다.
 * @returns {void}
 */
export function afterRender(root, path, fullKey) {
  runCountUps(root);
  enterAnimate(root, path);
  flashNewRows(root, fullKey);
}
