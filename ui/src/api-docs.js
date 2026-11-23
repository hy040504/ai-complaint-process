/**
 * 담당자 콘솔(#/staff/api)에서 백엔드 Swagger UI와 OpenAPI 3.1 명세 요약을 렌더링합니다.
 */
import { escapeHTML as e } from "./citizen.js";
import { icon } from "./icons.js";

const METHOD_ORDER = ["GET", "POST", "PUT", "PATCH", "DELETE"];

/**
 * flask-openapi3가 만든 HTML 줄바꿈(`<br/>`)·태그를 읽기 쉬운 일반 문장으로 정리합니다.
 *
 * @param {unknown} value OpenAPI summary 또는 description 원문입니다.
 * @returns {string} HTML 태그가 제거된 요약 문자열입니다.
 */
function cleanDocText(value) {
  return String(value ?? "")
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/\b(Args|Returns|Raises):/g, " · $1:")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * `/openapi/openapi.json` 명세에서 태그별 엔드포인트 수와 목록을 추출합니다.
 *
 * @param {object|null|undefined} spec OpenAPI JSON 객체입니다.
 * @returns {{title: string, version: string, openapiVersion: string, endpointCount: number, tags: Array<{name: string, description: string, count: number}>, endpoints: Array<{method: string, path: string, tag: string, summary: string, description: string, operationId: string, searchText: string}>}} 요약된 API 명세 객체입니다.
 */
export function summarizeOpenApiSpec(spec) {
  const info = spec && typeof spec === "object" ? spec.info || {} : {};
  const paths = spec && typeof spec === "object" && spec.paths ? spec.paths : {};
  const tagDescriptions = new Map();
  const tagOrder = [];

  for (const tagItem of Array.isArray(spec?.tags) ? spec.tags : []) {
    if (!tagItem || typeof tagItem.name !== "string") continue;
    const name = tagItem.name.trim();
    if (!name) continue;
    if (!tagDescriptions.has(name)) tagOrder.push(name);
    tagDescriptions.set(name, String(tagItem.description || "").trim());
  }

  const tagCounts = new Map();
  const endpoints = [];

  for (const [path, methods] of Object.entries(paths)) {
    if (!methods || typeof methods !== "object") continue;
    for (const [rawMethod, op] of Object.entries(methods)) {
      const method = rawMethod.toUpperCase();
      if (!METHOD_ORDER.includes(method) || !op || typeof op !== "object") {
        continue;
      }
      const tag =
        Array.isArray(op.tags) && op.tags.length
          ? String(op.tags[0])
          : "기타";
      if (!tagDescriptions.has(tag)) {
        tagDescriptions.set(tag, "");
        tagOrder.push(tag);
      }
      tagCounts.set(tag, (tagCounts.get(tag) || 0) + 1);
      const summaryText = cleanDocText(op.summary || op.operationId || path);
      const descriptionText = cleanDocText(op.description || "");
      endpoints.push({
        method,
        path,
        tag,
        summary: summaryText,
        description: descriptionText,
        operationId: String(op.operationId || "").trim(),
        searchText: [method, path, tag, summaryText, descriptionText]
          .join(" ")
          .toLowerCase(),
      });
    }
  }

  endpoints.sort((a, b) => {
    const pathCmp = a.path.localeCompare(b.path);
    if (pathCmp !== 0) return pathCmp;
    return METHOD_ORDER.indexOf(a.method) - METHOD_ORDER.indexOf(b.method);
  });

  const tags = tagOrder
    .map((name) => ({
      name,
      description: tagDescriptions.get(name) || "",
      count: tagCounts.get(name) || 0,
    }))
    .filter((item) => item.count > 0);

  return {
    title: String(info.title || "청주톡톡 민원 업무 API"),
    version: String(info.version || "0.1.0"),
    openapiVersion: String(spec?.openapi || "3.1.0"),
    endpointCount: endpoints.length,
    tags,
    endpoints,
  };
}

/**
 * 선택된 태그와 검색어로 엔드포인트 목록을 필터링합니다.
 *
 * @param {Array<{method: string, path: string, tag: string, summary: string, description: string, searchText?: string}>} endpoints 전체 엔드포인트 목록입니다.
 * @param {object} [options] 필터 옵션입니다.
 * @param {string} [options.tag=""] 필터링할 태그 이름입니다.
 * @param {string} [options.query=""] 검색할 경로·설명 키워드입니다.
 * @returns {Array<object>} 조건과 일치하는 엔드포인트 배열입니다.
 */
export function filterApiEndpoints(endpoints, { tag = "", query = "" } = {}) {
  const needle = String(query || "").trim().toLowerCase();
  return (Array.isArray(endpoints) ? endpoints : []).filter((item) => {
    if (tag && item.tag !== tag) return false;
    if (!needle) return true;
    const haystack =
      typeof item.searchText === "string"
        ? item.searchText
        : [
            item.method,
            item.path,
            item.tag,
            item.summary,
            item.description,
          ]
            .join(" ")
            .toLowerCase();
    return haystack.includes(needle);
  });
}

/**
 * 필터 조건에 맞는 엔드포인트 표 HTML을 렌더링합니다.
 *
 * @param {object} specOrSummary OpenAPI 명세 객체 또는 미리 요약된 결과 객체입니다.
 * @param {object} [options] 필터 상태입니다.
 * @param {string} [options.tag=""] 선택된 태그 이름입니다.
 * @param {string} [options.query=""] 검색어입니다.
 * @returns {{count: number, html: string}} 결과 건수와 HTML 문자열입니다.
 */
export function renderApiEndpointListHtml(
  specOrSummary,
  { tag = "", query = "" } = {},
) {
  const summary = Array.isArray(specOrSummary?.endpoints)
    ? specOrSummary
    : summarizeOpenApiSpec(specOrSummary);
  const filtered = filterApiEndpoints(summary.endpoints, { tag, query });
  if (!summary.endpointCount) {
    return {
      count: 0,
      html: `<div class="empty">${icon("code", 32)}<h3>OpenAPI 명세를 불러오는 중이거나 경로가 없습니다</h3><p>상단 새로고침 버튼으로 <code>/openapi/openapi.json</code>을 다시 불러와 주세요.</p></div>`,
    };
  }
  if (!filtered.length) {
    return {
      count: 0,
      html: `<div class="empty">${icon("search", 32)}<h3>조건과 일치하는 엔드포인트가 없습니다</h3><p>검색어나 태그 선택을 초기화해 보세요.</p><button class="btn" type="button" data-action="api-docs-reset">필터 초기화</button></div>`,
    };
  }
  const rows = filtered
    .map(
      (item) => `<tr>
        <td><span class="http-method ${e(item.method)}">${e(item.method)}</span></td>
        <td><code class="api-path-code">${e(item.path)}</code></td>
        <td><span class="staff-tag navy">${e(item.tag)}</span></td>
        <td>
          <strong>${e(item.summary)}</strong>
          ${item.description && item.description !== item.summary ? `<small class="api-op-desc">${e(item.description)}</small>` : ""}
        </td>
      </tr>`,
    )
    .join("");
  return {
    count: filtered.length,
    html: `<div class="table-wrap staff-api-table-wrap">
      <table>
        <thead>
          <tr>
            <th scope="col">메서드</th>
            <th scope="col">경로</th>
            <th scope="col">분류 태그</th>
            <th scope="col">설명</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`,
  };
}

/**
 * 담당자 업무 콘솔 내부의 백엔드 API · Swagger UI 페이지를 렌더링합니다.
 *
 * @param {object} ctx 화면 상태 컨텍스트입니다.
 * @param {object|null} ctx.health `/api/v1/health` 응답 객체입니다.
 * @param {object|null} ctx.spec `/openapi/openapi.json` 응답 객체입니다.
 * @param {boolean} [ctx.loading=false] 명세 로딩 여부입니다.
 * @param {string} [ctx.error=""] 명세 조회 오류 메시지입니다.
 * @param {"swagger"|"index"} [ctx.tab="swagger"] 활성 탭 이름입니다.
 * @param {string} [ctx.tag=""] 선택된 OpenAPI 태그입니다.
 * @param {string} [ctx.query=""] 엔드포인트 검색어입니다.
 * @param {object} [ctx.summary=null] 미리 계산된 `summarizeOpenApiSpec(spec)` 결과 객체입니다.
 * @param {"light"|"dark"} [ctx.theme="light"] 현재 UI 테마입니다.
 * @param {string} [ctx.ragDocsUrl="http://127.0.0.1:8007/docs"] RAG 검색 서버 Swagger URL입니다.
 * @returns {string} `#/staff/api` 화면 HTML 문자열입니다.
 */
export function backendSwaggerPage({
  health = null,
  spec = null,
  summary = null,
  loading = false,
  error = "",
  tab = "swagger",
  tag = "",
  query = "",
  theme = "light",
  ragDocsUrl = "http://127.0.0.1:8007/docs",
} = {}) {
  const resolvedSummary = Array.isArray(summary?.endpoints)
    ? summary
    : summarizeOpenApiSpec(spec);
  const endpointResult = renderApiEndpointListHtml(resolvedSummary, {
    tag,
    query,
  });
  const assistSearch = Boolean(health?.assistSearch ?? health?.assist_search);
  const assistLlm = Boolean(health?.assistLlm ?? health?.assist_llm);
  const aiConnected = Boolean(health?.aiConnected ?? health?.ai_connected);
  const storageLabel = !health
    ? "확인 중"
    : health.storage === "postgresql" || health.storage === "postgres"
      ? "PostgreSQL (complaint_app)"
      : String(health.storage || "-");
  const searchLabel = !health
    ? "확인 중"
    : assistSearch
      ? "검색 :8007 연결됨"
      : "검색 :8007 미연결";
  const llmLabel = !health
    ? "확인 중"
    : assistLlm
      ? "LLM 설정됨"
      : "LLM 미설정·시뮬레이션";
  const workerLabel = !health
    ? "확인 중"
    : aiConnected
      ? "비동기 RAG+LLM 워커 활성"
      : "단계 시연 모드";

  const frameSrc = `/swagger?embed=1&theme=${theme === "dark" ? "dark" : "light"}`;
  const tagChips = [
    `<button type="button" class="staff-filter-chip ${!tag ? "active" : ""}" data-action="api-docs-tag" data-tag="">전체<span>${resolvedSummary.endpointCount}</span></button>`,
    ...resolvedSummary.tags.map(
      (item) =>
        `<button type="button" class="staff-filter-chip ${tag === item.name ? "active" : ""}" data-action="api-docs-tag" data-tag="${e(item.name)}" title="${e(item.description)}">${e(item.name)}<span>${item.count}</span></button>`,
    ),
  ].join("");

  const swaggerPanel = `<section class="panel staff-api-swagger-panel">
    <header class="staff-api-panel-head">
      <div>
        <h2>대화형 Swagger UI (:5000)</h2>
        <p>현재 담당자 시연 세션 쿠키가 적용되어 <code>/api/v1/complaints</code>·<code>/departments</code>·<code>/templates</code>를 바로 실행(Try it out)할 수 있습니다.</p>
      </div>
      <div class="staff-api-panel-links">
        <a class="btn" href="/swagger" target="_blank" rel="noopener">${icon("external", 14)} 단독 Swagger 열기</a>
      </div>
    </header>
    <div class="staff-api-frame-wrap">
      <iframe id="staff-swagger-frame" class="staff-swagger-frame" src="${frameSrc}" title="청주톡톡 백엔드 API Swagger UI" loading="lazy"></iframe>
    </div>
  </section>`;

  const indexPanel = `<section class="panel staff-api-explorer">
    <header class="staff-api-panel-head">
      <div>
        <h2>엔드포인트 빠른 색인</h2>
        <p>태그와 경로 키워드로 ${resolvedSummary.endpointCount}개 백엔드 엔드포인트를 즉시 필터링해 확인합니다.</p>
      </div>
      <span class="staff-api-count-pill">표시 중 <b id="api-docs-count">${endpointResult.count}</b> / ${resolvedSummary.endpointCount}개</span>
    </header>
    <div class="staff-api-filter-bar">
      <div class="search-field">
        ${icon("search", 17)}
        <input id="api-docs-search" type="search" aria-label="API 엔드포인트 검색" placeholder="경로(/complaints), 메서드(POST), 기능 설명 검색" value="${e(query)}">
      </div>
      <button class="btn" type="button" data-action="api-docs-reset">초기화</button>
    </div>
    <div class="staff-filter-chips staff-api-tag-chips">${tagChips}</div>
    <div id="api-docs-endpoint-list">${endpointResult.html}</div>
  </section>`;

  return `<div class="page-content staff-api-page">
    <div class="staff-page-title staff-api-title">
      <h1>백엔드 API · Swagger</h1>
      <div class="staff-api-head-actions">
        <button class="btn" type="button" data-action="api-docs-refresh" ${loading ? "disabled" : ""}>${icon("refresh", 15)} 명세 새로고침</button>
        <a class="btn primary" href="/swagger" target="_blank" rel="noopener">${icon("external", 15)} 새 탭에서 Swagger 열기</a>
        <a class="btn" href="/openapi/openapi.json" target="_blank" rel="noopener">OpenAPI JSON</a>
        <a class="btn" href="${e(ragDocsUrl)}" target="_blank" rel="noopener">RAG 검색 Swagger (:8007)</a>
      </div>
    </div>

    <div class="info-banner amber">
      ${icon("shield", 19)}
      <span><b>백엔드 API 경계 · 시연 환경</b> · 민원 CRUD·AI 워커·응대 검사기(:5000)의 OpenAPI 3.1 문서입니다. 미게시 초안은 시민 응답에서 제외되며 공식 행정 이관(<code>automaticTransfer=false</code>)은 연결되지 않습니다.</span>
    </div>

    ${error ? `<div class="info-banner">${icon("help", 19)}<span>명세 일부를 불러오지 못했습니다: ${e(error)} (하단 Swagger UI는 <code>/swagger?embed=1</code>에서 독립 동작합니다.)</span></div>` : ""}

    <div class="staff-api-summary-grid">
      <div class="staff-api-stat">
        <span class="staff-api-stat-label">업무 저장소</span>
        <strong>${e(storageLabel)}</strong>
        <small>GET /api/v1/health</small>
      </div>
      <div class="staff-api-stat">
        <span class="staff-api-stat-label">RAG · LLM 연동</span>
        <strong>${e(searchLabel)}</strong>
        <small>${e(llmLabel)} · ${e(workerLabel)}</small>
      </div>
      <div class="staff-api-stat">
        <span class="staff-api-stat-label">OpenAPI 명세</span>
        <strong>${resolvedSummary.endpointCount}개 엔드포인트</strong>
        <small>OpenAPI ${e(resolvedSummary.openapiVersion)} · ${resolvedSummary.tags.length}개 분류 태그</small>
      </div>
      <div class="staff-api-stat">
        <span class="staff-api-stat-label">고정 문서 진입점</span>
        <strong><code>/docs</code> · <code>/swagger</code></strong>
        <small>JSON: <code>/openapi/openapi.json</code></small>
      </div>
    </div>

    <div class="staff-api-tabs" role="tablist" aria-label="백엔드 API 보기 전환">
      <button type="button" role="tab" aria-selected="${tab !== "index"}" class="staff-api-tab ${tab !== "index" ? "active" : ""}" data-action="api-docs-tab" data-tab="swagger">${icon("code", 15)} 대화형 Swagger UI</button>
      <button type="button" role="tab" aria-selected="${tab === "index"}" class="staff-api-tab ${tab === "index" ? "active" : ""}" data-action="api-docs-tab" data-tab="index">${icon("file", 15)} 엔드포인트 빠른 색인 (${resolvedSummary.endpointCount})</button>
    </div>

    ${tab === "index" ? indexPanel : swaggerPanel}
  </div>`;
}
