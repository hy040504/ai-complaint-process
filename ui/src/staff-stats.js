/**
 * 담당자 통계 대시보드(`#/staff/stats`)와 CSV 내보내기 URL 구성을 담당합니다.
 *
 * 서버 `/api/v1/staff/stats`에서 담당자 부서 RBAC 소관 범위로 집계한
 * 운영 KPI·5종 분포 차트·정규화 7테이블 요약을 표시하며, 모든 차트 막대는
 * 해당 조건의 `#/staff/complaints?...` 목록으로 즉시 드릴다운됩니다.
 */

import { escapeHTML as esc } from "./citizen.js";
import { icon } from "./icons.js";

/** 정규화 7테이블의 한국어 설명 표입니다. */
const TABLE_LABELS = {
  users: "사용자 계정",
  complaints: "민원 원문·상태",
  messages: "답변·추가 문의",
  message_versions: "초안·게시 버전 이력",
  ai_jobs: "AI 분석 작업",
  ai_results: "AI 판정·부서 후보",
  job_events: "작업 단계 이벤트",
};

/**
 * 현재 담당자 목록 쿼리 조건을 `/api/v1/staff/complaints/export.csv` URL로 변환합니다.
 *
 * @param {URLSearchParams|null|undefined} params 현재 목록 화면의 URL 쿼리 파라미터입니다.
 * @returns {string} 서버 CSV 다운로드 상대 URL입니다.
 */
export function buildStaffExportUrl(params) {
  const out = new URLSearchParams();
  if (params) {
    for (const key of [
      "q",
      "status",
      "district",
      "category",
      "assign",
      "view",
      "aiOutcome",
      "sort",
    ]) {
      const val = params.get(key);
      if (val) out.set(key, val);
    }
    if (params.get("synthetic") === "0") {
      out.set("includeSynthetic", "0");
    }
  }
  return "/api/v1/staff/complaints/export.csv" + (out.size ? "?" + out : "");
}

/**
 * 통계 버킷 항목을 클릭 시 이동할 `#/staff/complaints?...` 드릴다운 해시로 변환합니다.
 *
 * @param {object} bucket 서버 `StaffStatsBucket` 객체입니다.
 * @param {boolean} includeSynthetic 공개 시연 데이터 포함 여부입니다.
 * @returns {string} 해시 라우트 경로입니다.
 */
export function buildStatsDrilldownHref(bucket, includeSynthetic = true) {
  const params = new URLSearchParams();
  if (bucket?.filterKey && bucket?.filterValue) {
    params.set(bucket.filterKey, bucket.filterValue);
  }
  if (!includeSynthetic) {
    params.set("synthetic", "0");
  }
  return "#/staff/complaints" + (params.size ? "?" + params : "");
}

/**
 * 단일 가로 막대 분포 차트 패널 HTML을 생성합니다.
 *
 * @param {string} title 차트 카드 제목입니다.
 * @param {string} subtitle 보조 설명 문구입니다.
 * @param {Array<object>} buckets `StaffStatsBucket` 배열입니다.
 * @param {object} options 표시 설정입니다.
 * @param {number} options.total 전체 모수 건수입니다.
 * @param {boolean} options.includeSynthetic 공개 시연 데이터 포함 여부입니다.
 * @param {string} [options.tone="blue"] 막대 색상 테마(`blue`·`teal`·`gold`·`indigo`)입니다.
 * @returns {string} 차트 섹션 HTML입니다.
 */
function renderBarChart(title, subtitle, buckets, { total, includeSynthetic, tone = "blue" }) {
  const items = Array.isArray(buckets) ? buckets : [];
  const maxVal = Math.max(1, ...items.map((item) => Number(item.count) || 0));
  const denom = Math.max(1, Number(total) || 0);
  const rows = items.length
    ? items
        .map((item) => {
          const count = Number(item.count) || 0;
          const barPct = count > 0 ? Math.max(4, Math.round((count / maxVal) * 100)) : 0;
          const sharePct = total > 0 ? Math.round((count / denom) * 100) : 0;
          const href = buildStatsDrilldownHref(item, includeSynthetic);
          return `<a class="stats-bar-row" href="${esc(href)}" title="${esc(item.label)} ${count}건 목록 보기"><span class="stats-bar-label">${esc(item.label)}</span><span class="stats-bar-track" aria-hidden="true"><i class="stats-bar-fill tone-${esc(tone)}" style="width:${barPct}%"></i></span><span class="stats-bar-val"><b>${count}</b><small>${sharePct}%</small></span></a>`;
        })
        .join("")
    : '<p class="muted">집계할 데이터가 없습니다.</p>';

  return `<section class="panel stats-chart-card"><header><h2>${esc(title)}</h2><span>${esc(subtitle)}</span></header><div class="stats-bar-list">${rows}</div></section>`;
}

/**
 * 담당자 전용 업무 통계 대시보드(`#/staff/stats`) 전체 HTML을 렌더링합니다.
 *
 * @param {object|null} stats `/api/v1/staff/stats` 응답 객체입니다.
 * @param {object} [options] 로딩·오류·시연 데이터 토글 상태입니다.
 * @param {boolean} [options.loading=false] 데이터를 조회 중인지 여부입니다.
 * @param {string} [options.error=""] 조회 오류 메시지입니다.
 * @param {boolean} [options.includeSynthetic=true] 공개 시연 데이터 포함 여부입니다.
 * @returns {string} 통계 대시보드 HTML입니다.
 */
export function staffStatsPage(
  stats,
  { loading = false, error = "", includeSynthetic = true } = {},
) {
  const synQuery = includeSynthetic ? "" : "&synthetic=0";
  const synOnlyQuery = includeSynthetic ? "" : "?synthetic=0";
  const exportHref = `/api/v1/staff/complaints/export.csv?includeSynthetic=${includeSynthetic ? "1" : "0"}`;
  const scopeLabel = stats?.scopeLabel || "소관 범위 확인 중";
  const scopeTone = stats?.isAdminScope ? "admin" : "dept";

  const headerBar = `<div class="staff-page-title stats-page-head"><div><div class="eyebrow">업무 현황</div><h1>업무 통계 대시보드</h1></div><div class="stats-head-actions"><span class="stats-scope-badge ${scopeTone}">${icon("shield", 14)} ${esc(scopeLabel)}</span><button type="button" class="btn ${includeSynthetic ? "" : "primary subtle"}" data-action="toggle-stats-synthetic" aria-pressed="${includeSynthetic ? "true" : "false"}">${includeSynthetic ? "공개 시연 포함 중" : "실제 민원만 보는 중"}</button><button type="button" class="btn" data-action="refresh-stats">${icon("refresh", 15)} 새로고침</button><a class="btn primary" href="${esc(exportHref)}" download>${icon("download", 15)} CSV 내보내기</a></div></div>`;

  if (loading && !stats) {
    return `<div class="page-content staff-stats-page">${headerBar}<div class="panel empty" role="status">소관 범위 민원 통계를 집계하고 있습니다…</div></div>`;
  }
  if (error && !stats) {
    return `<div class="page-content staff-stats-page">${headerBar}<div class="panel empty"><h2>통계를 불러오지 못했습니다</h2><p>${esc(error)}</p><button type="button" class="btn primary" data-action="refresh-stats">다시 시도</button></div></div>`;
  }
  if (!stats) {
    return `<div class="page-content staff-stats-page">${headerBar}<div class="panel empty"><h2>집계 데이터가 없습니다</h2></div></div>`;
  }

  const op = stats.operational || {};
  const total = Number(stats.totalComplaints) || 0;
  const kpis = [
    {
      label: "전체 소관 민원",
      value: `${total}`,
      unit: "건",
      sub: `실제 ${stats.realComplaints ?? 0}건 · 공개 시연 ${stats.syntheticComplaints ?? 0}건`,
      tone: "blue",
      href: `#/staff/complaints${synOnlyQuery}`,
    },
    {
      label: "미처리 (접수·검토)",
      value: `${op.openCount ?? 0}`,
      unit: "건",
      sub: `평균 경과 ${Number(op.avgOpenDays || 0).toFixed(1)}일`,
      tone: "red",
      href: `#/staff/complaints?status=under_review${synQuery}`,
    },
    {
      label: "담당 미지정",
      value: `${op.unassignedCount ?? 0}`,
      unit: "건",
      sub: "부서 또는 담당자 배정 필요",
      tone: "gold",
      href: `#/staff/complaints?assign=none${synQuery}`,
    },
    {
      label: "미게시 초안",
      value: `${op.unpublishedDrafts ?? 0}`,
      unit: "건",
      sub: "검토 후 시민 게시 대기",
      tone: "gold",
      href: `#/staff/complaints?view=drafts${synQuery}`,
    },
    {
      label: "추가 문의 있음",
      value: `${op.withFollowups ?? 0}`,
      unit: "건",
      sub: `답변 게시 완료 ${op.publishedCount ?? 0}건`,
      tone: "green",
      href: `#/staff/complaints?view=followup${synQuery}`,
    },
    {
      label: "AI 분석 실패",
      value: `${op.aiFailed ?? 0}`,
      unit: "건",
      sub: `현재 분석 실행 중 ${op.aiRunning ?? 0}건`,
      tone: op.aiFailed ? "red" : "blue",
      href: `#/staff/complaints?view=failed${synQuery}`,
    },
  ];

  const kpiHtml = `<div class="stats-kpi-grid">${kpis
    .map(
      (k) =>
        `<a class="staff-kpi" href="${esc(k.href)}"><span class="staff-kpi-label">${esc(k.label)}</span><strong><span data-countup="${esc(k.value)}" data-ck="stats-kpi-${esc(k.label)}">${esc(k.value)}</span><small>${esc(k.unit)}</small></strong><span class="staff-kpi-sub ${esc(k.tone)}">${esc(k.sub)}</span></a>`,
    )
    .join("")}</div>`;

  const chartsHtml = `<div class="stats-chart-grid">${renderBarChart(
    "처리 상태별 분포",
    "막대를 누르면 해당 상태 민원 목록으로 이동합니다",
    stats.byStatus,
    { total, includeSynthetic, tone: "blue" },
  )}${renderBarChart(
    "AI 판정별 분포",
    "FAQ 안내·부서 후보·담당자 검토 비율",
    stats.byAiOutcome,
    { total, includeSynthetic, tone: "teal" },
  )}${renderBarChart(
    "관할 구별 분포",
    "청주시 4개 자치구 및 위치 미지정",
    stats.byDistrict,
    { total, includeSynthetic, tone: "indigo" },
  )}${renderBarChart(
    "민원 분야별 분포",
    "시민이 선택한 민원 분류 기준",
    stats.byCategory,
    { total, includeSynthetic, tone: "gold" },
  )}${renderBarChart(
    "배정 부서별 현황",
    "상위 10개 배정 부서 및 미배정 건수",
    stats.byDepartment,
    { total, includeSynthetic, tone: "blue" },
  )}</div>`;

  const db = stats.dbSummary || {};
  const tables = db.normalizedTables || {};
  const tableRows = Object.entries(tables)
    .map(
      ([name, count]) =>
        `<tr><td><code>${esc(name)}</code></td><td>${esc(TABLE_LABELS[name] || name)}</td><td class="num">${Number(count || 0).toLocaleString("ko-KR")}건</td></tr>`,
    )
    .join("");
  const dbSection = `<section class="panel stats-db-card"><header><div><h2>정규화 7테이블 저장소 요약</h2><p>RAG 검색 색인(<code>complaint_rag</code>)과 분리된 업무 데이터베이스(<code>${esc(db.schemaName || "complaint_app")}</code> · ${esc(db.storage || "postgresql")}) 현황입니다.</p></div><span class="staff-api-count-pill">민원인 ${db.userRoles?.citizen ?? 0} · 담당자 ${db.userRoles?.staff ?? 0}</span></header><div class="stats-db-table-wrap"><table><thead><tr><th scope="col">테이블</th><th scope="col">역할</th><th scope="col" class="num">저장 행 수</th></tr></thead><tbody>${tableRows}</tbody></table></div></section>`;

  return `<div class="page-content staff-stats-page">${headerBar}<div class="info-banner">${icon("spark", 18)}<span>부서 담당자에게는 자기 부서 민원만 집계됩니다. 막대나 지표를 누르면 해당 조건의 민원 목록으로 바로 이동하며, CSV 내보내기에는 미게시 AI 초안과 순화 본문이 제외됩니다.</span></div>${kpiHtml}${chartsHtml}${dbSection}</div>`;
}
