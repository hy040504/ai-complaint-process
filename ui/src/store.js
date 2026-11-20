/**
 * Flask API와 통신하며 업무 데이터는 브라우저 저장소에 보관하지 않습니다.
 */
export const districts = ["상당구", "서원구", "흥덕구", "청원구", "모름"];
export const categories = [
  "도로·교통",
  "환경·청소",
  "공원·녹지",
  "생활·복지",
  "주택·건축",
  "기타",
];
export const statusNames = {
  submitted: "접수 대기",
  under_review: "검토 중",
  answered: "답변 완료",
  closed: "처리 종료",
  withdrawn: "철회",
};
let cache = { revision: 0, complaints: [] };
let activeRole;
let currentActor = null;

/**
 * 현재 세션에 연결된 인증 사용자(`Actor`) 정보를 반환합니다.
 *
 * @returns {object|null} 서버 세션에서 확인한 사용자 객체 또는 null입니다.
 */
export function getActor() {
  return currentActor;
}

/**
 * 같은 출처의 API에 JSON 요청을 보내고 공통 오류를 처리합니다.
 *
 * @param {string} path 화면 경로 또는 API 상대 경로입니다.
 * @param {object} [options] 요청 설정입니다.
 * @param {string} [options.method="GET"] HTTP 메서드입니다.
 * @param {object} [options.body] JSON으로 직렬화할 요청 본문입니다.
 * @param {Object<string,string>} [options.headers] 추가 HTTP 헤더입니다.
 * @returns {Promise<unknown>} 비동기 작업의 완료 결과입니다.
 */
export async function api(path, { method = "GET", body, headers = {} } = {}) {
  let response;
  try {
    response = await fetch("/api/v1" + path, {
      method,
      credentials: "same-origin",
      headers: {
        ...(body ? { "Content-Type": "application/json" } : {}),
        ...headers,
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
  } catch {
    throw new Error(
      "Flask 서버에 연결할 수 없습니다. 서버 실행 상태를 확인해 주세요.",
    );
  }
  let value;
  try {
    value = response.status === 204 ? null : await response.json();
  } catch {
    throw new Error(
      "서버 응답을 읽지 못했습니다. Flask 서버 주소로 접속해 주세요.",
    );
  }
  if (!response.ok) {
    const error = new Error(value?.message || "서버 요청이 실패했습니다.");
    error.status = response.status;
    error.code = value?.code;
    throw error;
  }
  return value;
}

/**
 * 역할을 바꿀 때 기존 역할의 메모리 데이터를 먼저 제거합니다.
 *
 * @param {string} role 선택할 시연 사용자 역할입니다.
 * @returns {Promise<object>} 발급된 시연 사용자 `Actor` 객체입니다.
 */
export async function setRole(role) {
  if (activeRole === role) return currentActor;
  cache = { revision: 0, complaints: [] };
  activeRole = undefined;
  currentActor = null;
  const actor = await api("/session", { method: "POST", body: { role } });
  currentActor = actor || { id: role === "staff" ? "staff-demo" : "citizen-demo", role, demo: true };
  activeRole = role;
  return currentActor;
}

/**
 * 기존 실계정 인증 세션이 대상 역할과 일치하면 유지하고, 아니면 시연 세션을 선택합니다.
 *
 * @param {string} role 진입하려는 화면 역할(`citizen` 또는 `staff`)입니다.
 * @returns {Promise<object>} 현재 활성 사용자 `Actor` 객체입니다.
 */
export async function ensureRoleSession(role) {
  if (currentActor && currentActor.role === role) {
    activeRole = role;
    return currentActor;
  }
  try {
    const me = await api("/auth/me");
    if (me && me.role === role && me.demo === false) {
      cache = { revision: 0, complaints: [] };
      currentActor = me;
      activeRole = role;
      return me;
    }
  } catch {
    /* 미인증 상태면 아래 시연 전환 또는 로그인 모달 경로로 진행합니다. */
  }
  return setRole(role);
}

/**
 * 아이디·비밀번호로 실계정 로그인하고 기존 역할 캐시를 초기화합니다.
 *
 * @param {{loginId:string,password:string,expectedRole?:string}} payload 로그인 자격 증명입니다.
 * @returns {Promise<object>} 인증된 `Actor` 객체입니다.
 */
export async function loginAccount(payload) {
  cache = { revision: 0, complaints: [] };
  activeRole = undefined;
  currentActor = null;
  const actor = await api("/auth/login", { method: "POST", body: payload });
  currentActor = actor;
  activeRole = actor.role;
  return actor;
}

/**
 * 아이디·비밀번호·이름으로 새 민원인 계정을 생성하고 즉시 로그인합니다.
 *
 * @param {{loginId:string,password:string,displayName:string}} payload 가입 정보입니다.
 * @returns {Promise<object>} 가입·로그인된 민원인 `Actor` 객체입니다.
 */
export async function registerCitizenAccount(payload) {
  cache = { revision: 0, complaints: [] };
  activeRole = undefined;
  currentActor = null;
  const actor = await api("/auth/register", {
    method: "POST",
    body: payload,
  });
  currentActor = actor;
  activeRole = actor.role;
  return actor;
}

/**
 * 현재 세션을 로그아웃하고 메모리 스냅샷을 비웁니다.
 *
 * @returns {Promise<void>} 로그아웃 완료 프로미스입니다.
 */
export async function logoutAccount() {
  await api("/auth/logout", { method: "POST" });
  cache = { revision: 0, complaints: [] };
  activeRole = undefined;
  currentActor = null;
}

/**
 * 세션과 일치하는 최신 스냅샷만 메모리에 적용합니다.
 *
 * @returns {Promise<object>} 비동기 작업의 완료 결과입니다.
 */
export async function refresh() {
  const role = activeRole;
  const value = await api("/workspace");
  if (value.role && value.role !== role) {
    cache = { revision: 0, complaints: [] };
    activeRole = undefined;
    currentActor = null;
    throw new Error(
      "다른 탭에서 시연 역할이 바뀌었습니다. 현재 화면을 다시 불러와 주세요.",
    );
  }
  if (role === activeRole) cache = value;
  return cache;
}

/**
 * 렌더링 전용 메모리 스냅샷을 반환합니다. 저장은 API로만 수행합니다.
 *
 * @returns {object} 화면 렌더링용 메모리 스냅샷입니다.
 */
export function read() {
  return cache;
}

/**
 * 서버가 허용한 목록에서 화면의 내 민원 조건을 적용합니다.
 *
 * @param {object} data 현재 역할로 조회한 업무 스냅샷입니다.
 * @param {boolean} [mine=false] 본인 민원만 표시할지 여부입니다.
 * @returns {Array<object>} 화면에 사용할 민원 배열입니다.
 */
export function visible(data, mine = false) {
  const ownerId = currentActor?.id || "citizen-demo";
  return data.complaints.filter(
    (c) => c.status !== "withdrawn" && (!mine || c.owner === ownerId),
  );
}
