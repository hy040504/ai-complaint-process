/** 담당자 콘솔의 백엔드 API · Swagger UI 요약 및 화면 구성을 검증합니다. */
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  backendSwaggerPage,
  filterApiEndpoints,
  renderApiEndpointListHtml,
  summarizeOpenApiSpec,
} from "../src/api-docs.js";
import { staffShell } from "../src/staff.js";

const SAMPLE_SPEC = {
  openapi: "3.1.0",
  info: { title: "청주톡톡 민원 업무 API", version: "0.1.0" },
  tags: [
    { name: "민원", description: "민원 등록·조회" },
    { name: "서버 상태", description: "헬스 체크" },
  ],
  paths: {
    "/api/v1/health": {
      get: {
        tags: ["서버 상태"],
        summary: "서버 상태 확인",
        description: "DB와 AI 연동 상태를 반환합니다.",
        operationId: "health",
      },
    },
    "/api/v1/complaints": {
      get: {
        tags: ["민원"],
        summary: "민원 목록 조회",
        description:
          "검색·지역 조건을 적용한 민원 목록입니다.<br/>Args:<br/>  query: 조건입니다.<br/><br/>Returns:<br/>  페이지입니다.",
        operationId: "list_complaints",
      },
      post: {
        tags: ["민원"],
        summary: "민원 등록",
        operationId: "create_complaint",
      },
    },
  },
};

test("OpenAPI 3.1 명세에서 태그별 엔드포인트 수와 필터링·HTML 정리를 계산한다", () => {
  const summary = summarizeOpenApiSpec(SAMPLE_SPEC);
  assert.equal(summary.endpointCount, 3);
  assert.equal(summary.openapiVersion, "3.1.0");
  assert.ok(!summary.endpoints[0].description.includes("<br"));
  assert.match(summary.endpoints[0].description, /Args: query: 조건입니다\./);
  assert.deepEqual(
    summary.tags.map((item) => [item.name, item.count]),
    [
      ["민원", 2],
      ["서버 상태", 1],
    ],
  );
  assert.equal(summary.endpoints[0].method, "GET");
  assert.equal(summary.endpoints[1].method, "POST");

  const filteredByTag = filterApiEndpoints(summary.endpoints, { tag: "민원" });
  assert.equal(filteredByTag.length, 2);

  const filteredByQuery = filterApiEndpoints(summary.endpoints, {
    query: "POST",
  });
  assert.equal(filteredByQuery.length, 1);
  assert.equal(filteredByQuery[0].path, "/api/v1/complaints");
  assert.match(summary.endpoints[0].searchText, /\/api\/v1\/complaints/);

  const precomputedList = renderApiEndpointListHtml(summary, {
    tag: "서버 상태",
    query: "health",
  });
  assert.equal(precomputedList.count, 1);
  assert.match(precomputedList.html, /\/api\/v1\/health/);
});

test("담당자 API 문서 페이지가 Swagger iframe·색인 탭·경계 안내를 렌더링한다", () => {
  const swaggerHtml = backendSwaggerPage({
    health: {
      storage: "postgresql",
      aiConnected: true,
      assistSearch: true,
      assistLlm: true,
    },
    spec: SAMPLE_SPEC,
    tab: "swagger",
    theme: "dark",
  });
  assert.match(swaggerHtml, /PostgreSQL \(complaint_app\)/);
  assert.match(swaggerHtml, /검색 :8007 연결됨/);
  assert.match(swaggerHtml, /LLM 설정됨 · 비동기 RAG\+LLM 워커 활성/);
  assert.match(swaggerHtml, /\/swagger\?embed=1&theme=dark/);
  assert.match(swaggerHtml, /3개 엔드포인트/);
  assert.match(swaggerHtml, /automaticTransfer=false/);

  const indexHtml = backendSwaggerPage({
    health: null,
    spec: SAMPLE_SPEC,
    summary: summarizeOpenApiSpec(SAMPLE_SPEC),
    tab: "index",
    query: "health",
  });
  assert.match(indexHtml, /\/api\/v1\/health/);
  assert.match(indexHtml, /서버 상태 확인/);
});

test("담당자 사이드바 셸이 /staff/api 경로를 활성 메뉴로 표시한다", () => {
  const html = staffShell(
    "<section>API</section>",
    {
      path: "/staff/api",
      params: new URLSearchParams(),
    },
    { complaints: [] },
  );
  assert.match(html, /API 문서 · Swagger/);
  assert.match(html, /class="staff-nav-link active" href="#\/staff\/api"/);
  assert.match(html, /백엔드 API · Swagger/);
  assert.match(html, /href="\/swagger"/);
});
