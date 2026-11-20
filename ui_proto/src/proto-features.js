/**
 * 구상 메모(UI_기능_구상.txt)의 담당자·검사기 기능을 구현합니다.
 *
 * 답변 템플릿 검색·분류, AI 원문과 편집본의 단어 단위 비교, 단축키 안내,
 * 검사기 초안을 담당자 편집기로 넘기는 동작을 담습니다. 이벤트는 모듈이 가져와질 때
 * 문서에 한 번 등록하며, app.js의 기존 흐름은 바꾸지 않습니다.
 */
import { icon } from "./icons.js";
import { diffTokens } from "./proto-diff.js";
import { categories, read } from "./store.js";
import { labResult } from "./lab.js";
import {
  addCustomTemplate,
  clearDraftSeed,
  customTemplates,
  removeCustomTemplate,
  setDraftSeed,
} from "./proto-state.js";

/** 시민 답변에 자주 쓰는 예시 문구입니다. 공식 답변 문안이 아닙니다. */
const BUILTIN = [
  { id: "base-greeting", title: "결론 안내 시작", category: "공통", body: "안녕하십니까. 접수하신 민원의 검토 결과를 안내드립니다." },
  { id: "base-apology", title: "불편 사과", category: "공통", body: "불편을 드려 죄송합니다." },
  { id: "base-referral", title: "부서 전달 안내", category: "공통", body: "확인 과정에서 추가 조사가 필요하여 담당 부서에 전달하였습니다." },
  { id: "base-followup", title: "추가 문의 안내", category: "공통", body: "추가 문의가 있으시면 민원 상세 화면의 추가 문의로 남겨 주세요." },
  { id: "base-thanks", title: "마무리 인사", category: "공통", body: "감사합니다." },
  { id: "road-repair", title: "도로 보수 검토", category: "도로·교통", body: "현장 상태를 확인한 뒤 보수 필요 여부와 일정을 검토하겠습니다." },
  { id: "env-clean", title: "청소 점검 요청", category: "환경·청소", body: "해당 구역의 청소 일정과 점검 상태를 담당 부서에 확인 요청하였습니다." },
  { id: "park-check", title: "시설 정비 검토", category: "공원·녹지", body: "시설 점검 결과를 바탕으로 정비 계획을 검토하겠습니다." },
  { id: "welfare-guide", title: "복지 제도 안내", category: "생활·복지", body: "관련 복지 제도와 신청 절차를 안내드립니다. 자격 조건은 담당 부서 확인이 필요합니다." },
  { id: "house-check", title: "건축·주택 확인", category: "주택·건축", body: "관할 구청 담당 부서와 함께 해당 사항을 확인하겠습니다." },
];

/** 템플릿 목록의 현재 분야 선택과 검색어입니다. 다시 그려도 유지합니다. */
let tplCategory = "";
let tplQuery = "";

/**
 * HTML 특수문자를 이스케이프합니다.
 *
 * @param {unknown} value 표시할 값입니다.
 * @returns {string} 안전하게 바꾼 문자열입니다.
 */
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch],
  );

/**
 * 짧은 안내 문구를 토스트 영역에 잠시 보여 줍니다.
 *
 * @param {string} message 보여 줄 문구입니다.
 * @returns {void} 반환값 없이 화면만 갱신합니다.
 */
function notify(message) {
  const box = document.getElementById("toast");
  if (!box) return;
  box.textContent = message;
  box.classList.add("show");
  clearTimeout(notify.timer);
  notify.timer = setTimeout(() => box.classList.remove("show"), 4000);
}

/**
 * 기본 문구와 사용자가 추가한 문구를 합칩니다.
 *
 * @returns {Array<object>} 템플릿 목록입니다.
 */
function allTemplates() {
  return [...BUILTIN, ...customTemplates().map((item) => ({ ...item, custom: true }))];
}

/**
 * 템플릿 한 줄을 만듭니다. 검색과 분류는 data 속성으로 판단합니다.
 *
 * @param {object} item 템플릿입니다.
 * @returns {string} 목록 항목 HTML입니다.
 */
function templateItem(item) {
  const search = `${item.title} ${item.body}`.toLowerCase();
  return `<li class="proto-tpl-item" data-cat="${esc(item.category)}" data-search="${esc(search)}"><div class="proto-tpl-text"><b>${esc(item.title)}</b><small>${esc(item.category)}${item.custom ? " · 직접 추가" : ""}</small><p>${esc(item.body)}</p></div><div class="proto-tpl-btns"><button type="button" class="btn" data-action="tpl-insert" data-body="${esc(item.body)}">삽입</button>${item.custom ? `<button type="button" class="btn danger subtle" data-action="tpl-delete" data-tpl="${esc(item.id)}" aria-label="${esc(item.title)} 템플릿 삭제">삭제</button>` : ""}</div></li>`;
}

/**
 * 답변 편집기 아래에 두는 템플릿 패널입니다. 검색창과 분야 칩으로 찾습니다.
 *
 * @returns {string} 패널 HTML입니다.
 */
export function templatePanel() {
  const items = allTemplates();
  const chips = ["", "공통", ...categories];
  const open = document.querySelector(".proto-tpl-add")?.open ? " open" : "";
  return `<section class="proto-tpl" id="tpl-panel" aria-label="답변 템플릿"><div class="proto-tpl-head"><h3>답변 템플릿</h3><span>${items.length}개 · 예시 문구이며 공식 답변이 아닙니다</span></div><div class="proto-tpl-tools"><label class="sr-only" for="tpl-search">템플릿 검색</label><div class="search-field">${icon("search", 16)}<input id="tpl-search" type="search" placeholder="템플릿 제목이나 내용 검색" value="${esc(tplQuery)}"></div></div><div class="proto-tpl-chips" role="group" aria-label="분야별 보기">${chips
    .map((cat) => `<button type="button" class="proto-tpl-chip${tplCategory === cat ? " active" : ""}" data-action="tpl-cat" data-cat="${esc(cat)}" aria-pressed="${tplCategory === cat}">${cat || "전체"}</button>`)
    .join("")}</div><ul class="proto-tpl-list">${items.map(templateItem).join("")}</ul><p class="proto-tpl-empty" id="tpl-empty" hidden>조건에 맞는 템플릿이 없습니다.</p><details class="proto-tpl-add"${open}><summary>${icon("plus", 14)} 템플릿 추가</summary><form id="tpl-add-form" class="proto-tpl-form"><label for="tpl-title">제목 <em>*</em></label><input id="tpl-title" name="title" required maxlength="40" placeholder="예: 가로등 수리 안내"><label for="tpl-cat">분야</label><select id="tpl-cat" name="category">${categories.map((cat) => `<option>${cat}</option>`).join("")}</select><label for="tpl-body">문구 <em>*</em></label><textarea id="tpl-body" name="body" required maxlength="400" rows="3" placeholder="시민에게 안내할 문장을 입력하세요."></textarea><div class="form-footer"><button class="btn primary" type="submit">템플릿 추가</button></div></form></details></section>`;
}

/**
 * 현재 검색어와 분야 선택을 템플릿 항목에 적용합니다. 다시 그리지 않습니다.
 *
 * @returns {void} 반환값 없이 화면만 갱신합니다.
 */
function applyTemplateFilter() {
  const q = tplQuery.trim().toLowerCase();
  let shown = 0;
  document.querySelectorAll("#tpl-panel .proto-tpl-item").forEach((item) => {
    const ok =
      (!tplCategory || item.dataset.cat === tplCategory) &&
      (!q || item.dataset.search.includes(q));
    item.hidden = !ok;
    if (ok) shown += 1;
  });
  const empty = document.getElementById("tpl-empty");
  if (empty) empty.hidden = shown > 0;
}

/**
 * 템플릿 패널만 새로 그립니다. 편집기 입력은 건드리지 않습니다.
 *
 * @returns {void} 반환값 없이 화면만 갱신합니다.
 */
function refreshTemplatePanel() {
  const current = document.getElementById("tpl-panel");
  if (!current) return;
  current.insertAdjacentHTML("afterend", templatePanel());
  current.remove();
  applyTemplateFilter();
}

/**
 * 구간 목록을 HTML로 바꿉니다. 바뀐 구간만 색으로 표시합니다.
 *
 * @param {Array<[string,string]>} segments 구간 목록입니다.
 * @param {string} mark 표시할 변경 종류("del" 또는 "ins")입니다.
 * @returns {string} HTML입니다.
 */
function renderSegments(segments, mark) {
  let html = "", run = "", runType = "";
  const flush = () => {
    if (!run) return;
    html += runType === mark ? `<mark class="proto-diff-${mark}">${esc(run)}</mark>` : esc(run);
    run = "";
  };
  for (const [type, text] of segments) {
    const kind = type === "eq" ? "eq" : type;
    if (kind !== runType) flush();
    runType = kind;
    run += text;
  }
  flush();
  return html;
}

/**
 * AI 원문과 현재 편집기 내용을 나란히 보여 주는 창입니다.
 *
 * @param {object} complaint 서버 스냅샷의 민원입니다.
 * @param {string} current 지금 편집기에 있는 내용입니다. 저장 전 변경도 포함합니다.
 * @returns {void} 반환값 없이 창만 엽니다.
 */
function openCompare(complaint, current) {
  const original = complaint.aiOriginal;
  let body;
  if (!original) {
    body = `<p class="muted">AI 원문이 없습니다. 이 답변은 담당자가 직접 작성했습니다.</p>`;
  } else {
    const diff = diffTokens(original, current);
    const changed = diff
      ? diff.left.filter(([t, s]) => t === "del" && s.trim()).length +
        diff.right.filter(([t, s]) => t === "ins" && s.trim()).length
      : null;
    body = `<p class="proto-compare-summary">${changed === null ? "내용이 길어 단어 단위 표시를 생략했습니다." : `바뀐 부분 <b>${changed}</b>곳`} <span class="muted">· 빨강은 원문에서 빠진 부분, 초록은 편집본에서 새로 들어간 부분입니다.</span></p><div class="proto-compare-grid"><section><h3>AI 원문 <span class="mini-chip">보존됨</span></h3><div class="compare-box prose">${diff ? renderSegments(diff.left, "del") : esc(original)}</div></section><section><h3>담당자 편집본</h3><div class="compare-box prose">${diff ? renderSegments(diff.right, "ins") : esc(current)}</div></section></div>`;
  }
  const modal = document.getElementById("modal");
  modal.innerHTML = `<div class="modal-head"><h2 id="modal-title">AI 초안과 편집본 비교</h2><button class="icon-btn" data-action="close-modal" aria-label="닫기">${icon("close")}</button></div><div class="modal-content proto-compare">${body}<div class="form-footer"><button class="btn primary" type="button" data-action="close-modal">닫기</button></div></div>`;
  modal.showModal();
}

/**
 * 단축키 목록을 작은 창으로 보여 줍니다.
 *
 * @returns {void} 반환값 없이 창만 엽니다.
 */
function openShortcuts() {
  const modal = document.getElementById("modal");
  modal.innerHTML = `<div class="modal-head"><h2 id="modal-title">단축키</h2><button class="icon-btn" data-action="close-modal" aria-label="닫기">${icon("close")}</button></div><div class="modal-content proto-shortcuts"><dl><div><dt><kbd>Ctrl</kbd> + <kbd>S</kbd></dt><dd>편집 중인 답변 초안 저장 (민원 상세)</dd></div><div><dt><kbd>/</kbd></dt><dd>민원 검색창으로 이동</dd></div><div><dt><kbd>?</kbd></dt><dd>이 단축키 안내 열기·닫기</dd></div><div><dt><kbd>Esc</kbd></dt><dd>열린 창과 업무 메뉴 닫기</dd></div></dl></div>`;
  modal.showModal();
}

/**
 * 입력 중인지 확인합니다. 입력 중에는 단축키를 가로채지 않습니다.
 *
 * @returns {boolean} 글을 쓰는 중이면 true입니다.
 */
function isTyping() {
  const el = document.activeElement;
  return Boolean(el && (/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || el.isContentEditable));
}

/**
 * 편집기 커서 위치에 템플릿 문구를 넣습니다.
 *
 * @param {string} text 넣을 문구입니다.
 * @returns {void} 반환값 없이 편집기만 갱신합니다.
 */
function insertTemplate(text) {
  const field = document.getElementById("answer");
  if (!field) return;
  const start = field.selectionStart ?? field.value.length;
  const end = field.selectionEnd ?? start;
  const before = field.value.slice(0, start);
  const after = field.value.slice(end);
  // 앞뒤 글과 줄이 붙지 않도록 필요한 경우에만 줄바꿈을 넣습니다.
  const lead = before && !before.endsWith("\n") ? "\n" : "";
  const tail = after && !after.startsWith("\n") ? "\n" : "";
  field.setRangeText(lead + text + tail, start, end, "end");
  field.dispatchEvent(new Event("input", { bubbles: true }));
  field.focus();
}

document.addEventListener("input", (event) => {
  if (event.target.id === "tpl-search") {
    tplQuery = event.target.value;
    applyTemplateFilter();
  }
});

document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-action]");
  if (!target) return;
  const action = target.dataset.action;
  if (action === "tpl-cat") {
    tplCategory = target.dataset.cat || "";
    document.querySelectorAll(".proto-tpl-chip").forEach((chip) => {
      const on = chip.dataset.cat === tplCategory;
      chip.classList.toggle("active", on);
      chip.setAttribute("aria-pressed", String(on));
    });
    applyTemplateFilter();
  } else if (action === "tpl-insert") {
    insertTemplate(target.dataset.body || "");
  } else if (action === "tpl-delete") {
    removeCustomTemplate(target.dataset.tpl);
    refreshTemplatePanel();
    notify("추가한 템플릿을 삭제했습니다.");
  } else if (action === "diff-compare") {
    const complaint = read().complaints.find((row) => row.id === target.dataset.id);
    if (!complaint) return;
    openCompare(complaint, document.getElementById("answer")?.value ?? complaint.draft ?? "");
  } else if (action === "lab-to-editor") {
    if (!labResult?.answer) return;
    if (!setDraftSeed({ text: labResult.answer })) {
      notify("초안을 넘기지 못했습니다. 내용을 직접 복사해 주세요.");
      return;
    }
    location.hash = "#/staff/complaints";
    notify("검사기 초안을 가져왔습니다. 민원을 열면 편집기에 채워집니다.");
  } else if (action === "seed-cancel") {
    clearDraftSeed();
    window.dispatchEvent(new HashChangeEvent("hashchange"));
    notify("가져온 검사기 초안을 취소했습니다.");
  }
});

document.addEventListener("submit", (event) => {
  if (event.target.id !== "tpl-add-form") return;
  const form = event.target;
  const title = form.elements.title.value.trim();
  const body = form.elements.body.value.trim();
  if (!title || !body) {
    notify("제목과 문구를 입력해 주세요.");
    return;
  }
  if (!addCustomTemplate({ title, category: form.elements.category.value, body })) {
    notify("템플릿을 저장하지 못했습니다. 브라우저 저장 설정을 확인해 주세요.");
    return;
  }
  refreshTemplatePanel();
  notify("템플릿을 추가했습니다. 이 브라우저에만 저장됩니다.");
});

document.addEventListener("keydown", (event) => {
  if (event.ctrlKey || event.metaKey || event.altKey) return;
  if (event.key === "?" && !isTyping()) {
    event.preventDefault();
    const modal = document.getElementById("modal");
    if (modal.open) modal.close();
    else openShortcuts();
  } else if (event.key === "/" && !isTyping()) {
    const search = document.querySelector('input[name="q"]');
    if (search) {
      event.preventDefault();
      search.focus();
    }
  }
});
