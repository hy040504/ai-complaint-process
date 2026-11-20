/**
 * 구상 기능 프로토타입의 브라우저 보관 상태입니다.
 *
 * 업무 데이터(민원·답변·상태)는 여기에 저장하지 않습니다. 탭 안의 최근 본 목록,
 * 검사기에서 넘긴 임시 초안, 이 브라우저의 읽음 표시, 사용자가 추가한 문구 템플릿만
 * 보관하며, 모든 저장소 접근은 실패를 견디도록 감쌉니다.
 */

const RECENT_KEY = "proto-recent-complaints";
const SEED_KEY = "proto-staff-draft-seed";
const READ_KEY = "proto-read-answers";
const TEMPLATE_KEY = "proto-custom-templates";

/**
 * 저장소 값을 JSON으로 읽고, 실패하면 기본값을 돌려줍니다.
 *
 * @param {Storage} store sessionStorage 또는 localStorage입니다.
 * @param {string} key 저장 키입니다.
 * @param {*} fallback 읽기에 실패했을 때의 기본값입니다.
 * @returns {*} 저장된 값 또는 기본값입니다.
 */
function readJSON(store, key, fallback) {
  try {
    const value = JSON.parse(store.getItem(key) ?? "null");
    return value ?? fallback;
  } catch {
    return fallback;
  }
}

/**
 * 저장소에 JSON을 쓰고, 용량 초과·차단 등 실패는 무시합니다.
 *
 * @param {Storage} store sessionStorage 또는 localStorage입니다.
 * @param {string} key 저장 키입니다.
 * @param {*} value 저장할 값입니다.
 * @returns {boolean} 저장에 성공했는지 여부입니다.
 */
function writeJSON(store, key, value) {
  try {
    store.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

/* ── 최근 본 민원 (담당자, 이 탭에서만 유지) ── */

/**
 * 최근에 연 민원 목록을 최신순으로 돌려줍니다.
 *
 * @returns {Array<{id:string,title:string}>} 최대 5건의 민원 식별자와 제목입니다.
 */
export function recentComplaints() {
  const list = readJSON(sessionStorage, RECENT_KEY, []);
  return Array.isArray(list) ? list.slice(0, 5) : [];
}

/**
 * 민원을 연 기록을 맨 앞에 두고 5건까지만 남깁니다.
 *
 * @param {{id:string,title:string}} complaint 방금 연 민원입니다.
 * @returns {void} 반환값 없이 저장소만 갱신합니다.
 */
export function recordRecent(complaint) {
  const rest = recentComplaints().filter((item) => item.id !== complaint.id);
  writeJSON(sessionStorage, RECENT_KEY, [
    { id: complaint.id, title: complaint.title },
    ...rest,
  ].slice(0, 5));
}

/* ── 검사기 초안을 담당자 편집기로 넘기기 (이 탭에서만 유지) ── */

/**
 * 검사기 결과 초안을 편집기 전달 대기 상태로 저장합니다.
 *
 * @param {{text:string,title?:string}} draft 검사기가 만든 안내 초안입니다.
 * @returns {boolean} 저장에 성공했는지 여부입니다.
 */
export function setDraftSeed(draft) {
  return writeJSON(sessionStorage, SEED_KEY, { ...draft, at: Date.now() });
}

/**
 * 전달 대기 중인 검사기 초안을 읽습니다.
 *
 * @returns {{text:string,title?:string,at:number}|null} 대기 중인 초안 또는 null입니다.
 */
export function draftSeed() {
  const seed = readJSON(sessionStorage, SEED_KEY, null);
  return seed && typeof seed.text === "string" ? seed : null;
}

/**
 * 전달 대기 중인 초안을 지웁니다. 편집기에 넣었거나 사용자가 취소했을 때 호출합니다.
 *
 * @returns {void} 반환값 없이 저장소만 갱신합니다.
 */
export function clearDraftSeed() {
  try {
    sessionStorage.removeItem(SEED_KEY);
  } catch {
    /* 저장소를 쓸 수 없으면 대기 상태가 남지 않으므로 무시합니다. */
  }
}

/* ── 시민 답변 읽음 표시 (이 브라우저에서만 유지) ── */

/**
 * 게시 답변 하나를 구별하는 키입니다. 답변이 새로 게시되면 키가 바뀝니다.
 *
 * @param {{id:string,published?:{date:string}}} complaint 민원입니다.
 * @returns {string} 민원 번호와 게시 시각을 합친 키입니다.
 */
export function answerKey(complaint) {
  return `${complaint.id}|${complaint.published?.date ?? ""}`;
}

/**
 * 아직 읽지 않은 게시 답변 키 목록을 구합니다.
 *
 * @param {Array<object>} complaints 시민이 볼 수 있는 민원 목록입니다.
 * @returns {Set<string>} 읽지 않은 답변 키 집합입니다.
 */
export function unreadAnswerKeys(complaints) {
  const seen = new Set(readJSON(localStorage, READ_KEY, []));
  return new Set(
    complaints
      .filter((c) => c.published)
      .map(answerKey)
      .filter((key) => !seen.has(key)),
  );
}

/**
 * 민원의 게시 답변을 이 브라우저에서 읽음으로 표시합니다.
 *
 * @param {object} complaint 시민이 연 민원입니다.
 * @returns {void} 반환값 없이 저장소만 갱신합니다.
 */
export function markAnswerRead(complaint) {
  if (!complaint?.published) return;
  const seen = readJSON(localStorage, READ_KEY, []);
  const key = answerKey(complaint);
  if (seen.includes(key)) return;
  writeJSON(localStorage, READ_KEY, [...seen, key].slice(-200));
}

/* ── 사용자가 추가한 답변 템플릿 (이 브라우저에서만 유지) ── */

/**
 * 사용자가 추가한 템플릿 목록을 읽습니다.
 *
 * @returns {Array<{id:string,title:string,category:string,body:string}>} 추가 템플릿 목록입니다.
 */
export function customTemplates() {
  const list = readJSON(localStorage, TEMPLATE_KEY, []);
  return Array.isArray(list) ? list : [];
}

/**
 * 추가 템플릿을 저장합니다.
 *
 * @param {{title:string,category:string,body:string}} item 새 템플릿입니다.
 * @returns {boolean} 저장에 성공했는지 여부입니다.
 */
export function addCustomTemplate(item) {
  const id = `custom-${Date.now().toString(36)}`;
  return writeJSON(localStorage, TEMPLATE_KEY, [
    ...customTemplates(),
    { id, ...item },
  ]);
}

/**
 * 추가 템플릿 하나를 지웁니다.
 *
 * @param {string} id 지울 템플릿 식별자입니다.
 * @returns {boolean} 저장에 성공했는지 여부입니다.
 */
export function removeCustomTemplate(id) {
  return writeJSON(
    localStorage,
    TEMPLATE_KEY,
    customTemplates().filter((item) => item.id !== id),
  );
}
