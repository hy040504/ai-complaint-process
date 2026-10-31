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
 * @returns {Promise<void>} 비동기 작업의 완료 결과입니다.
 */
export async function setRole(role) {
  if (activeRole === role) return;
  cache = { revision: 0, complaints: [] };
  activeRole = undefined;
  await api("/session", { method: "POST", body: { role } });
  activeRole = role;
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
 * @returns {Array<object>} 화면에 사용할 HTML 또는 변환 결과입니다.
 */
export function visible(data, mine = false) {
  return data.complaints.filter(
    (c) => c.status !== "withdrawn" && (!mine || c.owner === "citizen-demo"),
  );
}
