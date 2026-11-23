/** 담당자 통계 대시보드·드릴다운 링크·큐 통합 검색·CSV 내보내기 URL을 검증합니다. */
import assert from "node:assert/strict";
import test from "node:test";

import {
  buildStaffExportUrl,
  buildStatsDrilldownHref,
  staffStatsPage,
} from "../src/staff-stats.js";
import { matchesStaffSearch, staffQueue } from "../src/staff.js";

test("buildStaffExportUrl은 현재 필터·정렬·시연 제외 조건을 서버 CSV 쿼리로 변환한다", () => {
  const params = new URLSearchParams(
    "q=가로등&district=서원구&aiOutcome=department_suggestion&sort=oldest_open&synthetic=0",
  );
  const url = buildStaffExportUrl(params);
  assert.match(url, /^\/api\/v1\/staff\/complaints\/export\.csv\?/);
  assert.match(url, /q=%EA%B0%80%EB%A1%9C%EB%93%B1/);
  assert.match(url, /aiOutcome=department_suggestion/);
  assert.match(url, /sort=oldest_open/);
  assert.match(url, /includeSynthetic=0/);
});

test("buildStatsDrilldownHref와 staffStatsPage는 RBAC 배지·차트 드릴다운·7테이블 요약을 렌더링한다", () => {
  assert.equal(
    buildStatsDrilldownHref(
      { filterKey: "aiOutcome", filterValue: "faq_answer" },
      false,
    ),
    "#/staff/complaints?aiOutcome=faq_answer&synthetic=0",
  );

  const html = staffStatsPage(
    {
      scopeLabel: "서원구 건설과 소관 + 미배정",
      isAdminScope: false,
      includeSynthetic: false,
      totalComplaints: 12,
      realComplaints: 12,
      syntheticComplaints: 5,
      operational: {
        openCount: 4,
        submittedCount: 2,
        underReviewCount: 2,
        answeredCount: 8,
        unassignedCount: 3,
        unpublishedDrafts: 1,
        withFollowups: 2,
        aiFailed: 1,
        aiRunning: 0,
        publishedCount: 8,
        avgOpenDays: 2.5,
      },
      byStatus: [
        { key: "submitted", label: "접수 대기", count: 2, filterKey: "status", filterValue: "submitted" },
      ],
      byDistrict: [
        { key: "서원구", label: "서원구", count: 7, filterKey: "district", filterValue: "서원구" },
      ],
      byCategory: [
        { key: "도로·교통", label: "도로·교통", count: 6, filterKey: "category", filterValue: "도로·교통" },
      ],
      byAiOutcome: [
        { key: "faq_answer", label: "공식 FAQ 안내", count: 5, filterKey: "aiOutcome", filterValue: "faq_answer" },
      ],
      byDepartment: [
        { key: "서원구 건설과", label: "서원구 건설과", count: 9, filterKey: "q", filterValue: "서원구 건설과" },
      ],
      dbSummary: {
        schemaName: "complaint_app",
        storage: "postgresql",
        normalizedTables: { users: 6, complaints: 17, ai_results: 10 },
        aiOutcomes: { faq_answer: 5 },
        userRoles: { citizen: 3, staff: 3 },
      },
    },
    { includeSynthetic: false },
  );

  assert.match(html, /서원구 건설과 소관 \+ 미배정/);
  assert.match(html, /실제 민원만 보는 중/);
  assert.match(html, /includeSynthetic=0/);
  assert.match(html, /#\/staff\/complaints\?aiOutcome=faq_answer&amp;synthetic=0/);
  assert.match(html, /정규화 7테이블 저장소 요약/);
  assert.match(html, /ai_results/);
});

test("matchesStaffSearch와 staffQueue는 본문·ID·부서 통합 검색과 AI 판정·정렬·담당자 실명을 반영한다", () => {
  const sample = {
    id: "DEMO-2026-AAA111",
    title: "가로등 점멸 신고",
    body: "사창동 골목 가로등이 밤새 깜빡입니다.",
    district: "서원구",
    category: "도로·교통",
    status: "under_review",
    visibility: "private",
    date: "2026-11-18T00:00:00Z",
    department: "서원구 건설과",
    assigned: true,
    assigneeName: "박주무관",
    isSynthetic: false,
    draft: "검토 초안",
    published: null,
    messages: [{ text: "언제 수리되나요?" }],
    job: { status: "succeeded", stage: "완료", attempt: 1, events: [] },
    aiAssist: { outcome: "department_suggestion" },
  };
  const syntheticRow = {
    ...sample,
    id: "DEMO-PUB-001",
    title: "시연 데이터 예시",
    body: "시연 데이터 본문",
    isSynthetic: true,
    assigned: false,
    assigneeName: null,
    department: null,
    draft: "",
    messages: [],
    aiAssist: null,
  };

  assert.equal(matchesStaffSearch(sample, "골목"), true);
  assert.equal(matchesStaffSearch(sample, "AAA111"), true);
  assert.equal(matchesStaffSearch(sample, "서원구 건설과"), true);
  assert.equal(matchesStaffSearch(sample, "없는단어"), false);

  const html = staffQueue(
    { complaints: [sample, syntheticRow] },
    new URLSearchParams("q=골목&aiOutcome=department_suggestion&synthetic=0&sort=most_followups"),
  );
  assert.match(html, /가로등 점멸 신고/);
  assert.doesNotMatch(html, /시연 데이터 예시/);
  assert.match(html, /박주무관/);
  assert.doesNotMatch(html, /<span class="staff-tag gray">김담당<\/span>/);
  assert.match(html, /CSV 내보내기/);
  assert.match(html, /추가 문의 많은순/);
});

test("staffStatsPage는 통계 분석·민원 분류 구역과 탭·지역·집계 단위 전환을 렌더링한다", async () => {
  const { setStatsView } = await import("../src/staff-stats.js");
  const cats = ["도로·교통", "환경·청소"];
  const analytics = {
    trends: [
      {
        unit: "day",
        labels: ["11/21", "11/22", "11/23"],
        received: [4, 2, 3],
        resolved: [1, 1, 0],
        categoryReceived: { "도로·교통": [3, 1, 2], "환경·청소": [1, 1, 1] },
      },
      {
        unit: "week",
        labels: ["11/9주", "11/16주", "11/23주"],
        received: [5, 7, 3],
        resolved: [4, 5, 1],
        categoryReceived: { "도로·교통": [3, 4, 1], "환경·청소": [2, 3, 2] },
      },
      {
        unit: "month",
        labels: ["26.09", "26.10", "26.11"],
        received: [2, 6, 9],
        resolved: [1, 4, 3],
        categoryReceived: { "도로·교통": [1, 4, 5], "환경·청소": [1, 2, 4] },
      },
    ],
    monthLabels: ["26.09", "26.10", "26.11"],
    categoryTrends: [{ category: "도로·교통", counts: [1, 4, 5], total: 10, changePct: 300 }],
    categories: cats,
    districtCategory: [
      { district: "상당구", counts: [5, 1], total: 6 },
      { district: "모름", counts: [2, 4], total: 6 },
    ],
    hourWeekday: Array.from({ length: 7 }, (_, d) => Array.from({ length: 24 }, (_, h) => (h === 9 ? d + 1 : 0))),
    resolutionByCategory: [
      { category: "도로·교통", resolved: 2, avgDays: 1.5 },
      { category: "환경·청소", resolved: 0, avgDays: null },
    ],
    resolutionBuckets: [{ key: "within1", label: "1일 이내", count: 2 }],
    aiFirstResponseRate: 40,
    resolveRate: 50,
  };
  const stats = {
    scopeLabel: "청주시 전체 민원 (총괄)",
    isAdminScope: true,
    totalComplaints: 3,
    operational: {},
    dbSummary: { normalizedTables: {} },
    analytics,
  };
  const render = () => staffStatsPage(stats, {});

  let html = render();
  assert.match(html, /통계 분석/);
  assert.match(html, /민원 분류/);
  assert.match(html, /data-action="stats-tab" data-id="region"/);
  assert.match(html, /지난 일 접수<\/span><strong>2건/);
  assert.match(html, /▼ 50% 그 전 일 대비 · 이번 일 3건\(진행 중\)/);
  assert.match(html, /class="catrow"/);
  assert.match(html, /야간·주말 접수가/);
  assert.match(html, /분야별 12개월 접수 추이/);
  assert.match(html, /<svg class="stats-svg radar"/);

  setStatsView("period", "week");
  assert.match(render(), /최근 8주 접수/);
  setStatsView("period", "bogus");
  assert.match(render(), /최근 8주 접수/);

  setStatsView("tab", "region");
  html = render();
  assert.match(html, /지역 × 분야/);
  assert.match(html, /위치 미지정/);
  setStatsView("region", 1);
  assert.match(render(), /위치 미지정 — 분야 레이더/);
  setStatsView("region", 99);
  assert.match(render(), /위치 미지정 — 분야 레이더/);

  setStatsView("tab", "time");
  assert.match(render(), /요일 × 시간대/);
  setStatsView("tab", "period");
  html = render();
  assert.match(html, /분야별 평균 처리일/);
  assert.match(html, /1\.5일/);
  setStatsView("tab", "bogus");
  assert.match(render(), /분야별 평균 처리일/);

  setStatsView("tab", "overview");
  setStatsView("period", "day");
  setStatsView("region", 0);
});