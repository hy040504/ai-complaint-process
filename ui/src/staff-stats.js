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

/** 분석 탭 정의입니다. `통계 분석`은 추이, 나머지는 `민원 분류` 관점입니다. */
export const ANALYTICS_TABS = [
  ["trend", "접수·처리 추이"],
  ["category", "분야별 추이"],
  ["region", "지역×분야"],
  ["time", "시간대·요일"],
  ["period", "처리기간"],
];
const PERIODS = [
  ["day", "일별"],
  ["week", "주별"],
  ["month", "월별"],
];
const WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"];
const SERIES_COLORS = ["#2f6fed", "#0d9488", "#c2850c", "#4f46e5", "#d9485f", "#7a8aa5"];

/** 화면에서 고른 분석 탭·집계 단위입니다. 새로고침해도 같은 화면을 유지합니다. */
const view = { tab: "trend", period: "day" };

/**
 * 분석 탭 또는 집계 단위를 바꿉니다. 목록에 없는 값은 무시합니다.
 *
 * @param {"tab"|"period"} kind 바꿀 항목입니다.
 * @param {string} value 새 값입니다.
 */
export function setStatsView(kind, value) {
  const allowed = kind === "tab" ? ANALYTICS_TABS : PERIODS;
  if (allowed.some(([key]) => key === value)) view[kind] = value;
}

const n = (value) => Number(value) || 0;

/** 접수(옅은 막대)와 처리(진한 막대)를 나란히 그리는 SVG 이중 막대 차트입니다. */
function trendChart(series) {
  const labels = series.labels || [];
  const recv = (series.received || []).map(n);
  const done = (series.resolved || []).map(n);
  const peak = Math.max(1, ...recv, ...done);
  const W = 640;
  const H = 210;
  const padL = 28;
  const padB = 24;
  const innerH = H - padB - 18;
  const slot = (W - padL) / Math.max(1, labels.length);
  const bw = Math.min(16, slot / 2 - 2);
  const grid = [0, 0.5, 1]
    .map((f) => {
      const y = 18 + innerH * (1 - f);
      return `<line x1="${padL}" x2="${W}" y1="${y}" y2="${y}" class="chart-grid"/><text x="${padL - 4}" y="${y + 3}" text-anchor="end" class="chart-axis">${Math.round(peak * f)}</text>`;
    })
    .join("");
  const bars = labels
    .map((label, i) => {
      const cx = padL + slot * i + slot / 2;
      const hr = (recv[i] / peak) * innerH;
      const hd = (done[i] / peak) * innerH;
      const last = i === labels.length - 1;
      return `<g class="${last ? "chart-hot" : ""}"><rect x="${cx - bw - 1}" y="${18 + innerH - hr}" width="${bw}" height="${hr}" rx="3" class="bar-recv"><title>${esc(label)} 접수 ${recv[i]}건</title></rect><rect x="${cx + 1}" y="${18 + innerH - hd}" width="${bw}" height="${hd}" rx="3" class="bar-done"><title>${esc(label)} 처리 ${done[i]}건</title></rect><text x="${cx}" y="${H - 8}" text-anchor="middle" class="chart-axis">${esc(label)}</text></g>`;
    })
    .join("");
  return `<svg class="stats-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="접수와 처리 건수 막대 차트">${grid}${bars}</svg><div class="chart-legend"><span><i class="bar-recv"></i>접수</span><span><i class="bar-done"></i>처리(답변 게시)</span></div>`;
}

/** 분야별 최근 월별 접수 추이를 꺾은선으로 그립니다. 상위 분야 6개를 보여줍니다. */
function categoryLines(analytics) {
  const labels = analytics.monthLabels || [];
  const items = (analytics.categoryTrends || []).slice(0, SERIES_COLORS.length);
  const peak = Math.max(1, ...items.flatMap((item) => (item.counts || []).map(n)));
  const W = 640;
  const H = 220;
  const padL = 28;
  const padB = 24;
  const innerH = H - padB - 14;
  const step = (W - padL - 14) / Math.max(1, labels.length - 1);
  const px = (i) => padL + step * i;
  const py = (v) => 14 + innerH * (1 - v / peak);
  const lines = items
    .map((item, idx) => {
      const pts = (item.counts || []).map((v, i) => `${px(i)},${py(n(v))}`).join(" ");
      const color = SERIES_COLORS[idx];
      const dots = (item.counts || [])
        .map((v, i) => `<circle cx="${px(i)}" cy="${py(n(v))}" r="3" fill="${color}"><title>${esc(item.category)} ${esc(labels[i])} ${n(v)}건</title></circle>`)
        .join("");
      return `<polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2.2" stroke-linejoin="round"/>${dots}`;
    })
    .join("");
  const axis = labels
    .map((l, i) => `<text x="${px(i)}" y="${H - 8}" text-anchor="middle" class="chart-axis">${esc(l)}</text>`)
    .join("");
  const grid = [0, 0.5, 1]
    .map((f) => `<line x1="${padL}" x2="${W}" y1="${14 + innerH * (1 - f)}" y2="${14 + innerH * (1 - f)}" class="chart-grid"/><text x="${padL - 4}" y="${14 + innerH * (1 - f) + 3}" text-anchor="end" class="chart-axis">${Math.round(peak * f)}</text>`)
    .join("");
  const legend = items
    .map((item, idx) => {
      const change = item.changePct;
      const delta = change == null ? "" : `<em class="${change > 0 ? "up" : change < 0 ? "down" : ""}">${change > 0 ? "▲" : change < 0 ? "▼" : "–"} ${Math.abs(change)}%</em>`;
      return `<a href="#/staff/complaints?category=${encodeURIComponent(item.category)}" class="legend-chip"><i style="background:${SERIES_COLORS[idx]}"></i>${esc(item.category)} <b>${n(item.total)}</b>${delta}</a>`;
    })
    .join("");
  return `<svg class="stats-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="분야별 월별 접수 추이">${grid}${lines}${axis}</svg><div class="chart-legend wrap">${legend}</div><p class="chart-note">최근 6개월 접수 건수이며 증감은 진행 중인 이번 달을 빼고 지난달을 지지난달과 비교한 값입니다. 이름을 누르면 해당 분야 목록으로 이동합니다.</p>`;
}

/** 값에 비례해 진해지는 히트맵 셀 클래스를 고릅니다. */
function heatLevel(value, peak) {
  if (!value || !peak) return "h0";
  const r = value / peak;
  return r > 0.75 ? "h4" : r > 0.5 ? "h3" : r > 0.25 ? "h2" : "h1";
}

/** 지역×분야 교차표를 히트맵 형태로 그립니다. 행을 누르면 해당 지역 목록으로 이동합니다. */
function regionTable(analytics, includeSynthetic) {
  const cats = analytics.categories || [];
  const rows = analytics.districtCategory || [];
  const peak = Math.max(1, ...rows.flatMap((row) => (row.counts || []).map(n)));
  const syn = includeSynthetic ? "" : "&synthetic=0";
  const head = `<tr><th scope="col">지역</th>${cats.map((c) => `<th scope="col">${esc(c)}</th>`).join("")}<th scope="col">합계</th></tr>`;
  const body = rows
    .map(
      (row) =>
        `<tr><th scope="row"><a href="#/staff/complaints?district=${encodeURIComponent(row.district)}${syn}">${esc(row.district === "모름" ? "위치 미지정" : row.district)}</a></th>${(row.counts || []).map((v) => `<td class="heat ${heatLevel(n(v), peak)}">${n(v)}</td>`).join("")}<td class="total">${n(row.total)}</td></tr>`,
    )
    .join("");
  return `<div class="stats-db-table-wrap"><table class="stats-cross"><thead>${head}</thead><tbody>${body}</tbody></table></div><p class="chart-note">진할수록 접수가 많은 칸입니다. 지역 이름을 누르면 해당 지역 민원 목록으로 이동합니다.</p>`;
}

/** 요일×시각(24시간) 접수 히트맵과 시간대별 합계 막대를 그립니다. 시각은 한국 표준시입니다. */
function timeHeatmap(analytics) {
  const matrix = analytics.hourWeekday || [];
  const peak = Math.max(1, ...matrix.flat().map(n));
  const hourTotals = Array.from({ length: 24 }, (_, h) => matrix.reduce((sum, row) => sum + n(row?.[h]), 0));
  const hourPeak = Math.max(1, ...hourTotals);
  const head = `<tr><th></th>${Array.from({ length: 24 }, (_, h) => `<th scope="col">${h % 3 === 0 ? h : ""}</th>`).join("")}</tr>`;
  const body = WEEKDAYS.map(
    (day, d) =>
      `<tr><th scope="row">${day}</th>${Array.from({ length: 24 }, (_, h) => `<td class="heat ${heatLevel(n(matrix[d]?.[h]), peak)}" title="${day}요일 ${h}시 ${n(matrix[d]?.[h])}건"></td>`).join("")}</tr>`,
  ).join("");
  const bars = hourTotals
    .map((v, h) => `<i style="height:${Math.max(v ? 6 : 0, Math.round((v / hourPeak) * 100))}%" title="${h}시 ${v}건"></i>`)
    .join("");
  return `<div class="stats-heat-wrap"><table class="stats-heat"><thead>${head}</thead><tbody>${body}</tbody></table></div><h3 class="stats-sub">시간대별 접수</h3><div class="hour-bars" role="img" aria-label="시간대별 접수 건수">${bars}</div><div class="hour-axis" aria-hidden="true">${Array.from({ length: 24 }, (_, h) => `<span>${h % 6 === 0 ? `${h}시` : ""}</span>`).join("")}</div><p class="chart-note">시각은 한국 표준시 기준입니다. 진할수록 접수가 몰리는 시간입니다.</p>`;
}

/** 처리기간 구간 분포와 분야별 평균 처리일을 그립니다. */
function periodPanel(analytics, includeSynthetic) {
  const buckets = analytics.resolutionBuckets || [];
  const done = buckets.reduce((sum, b) => sum + n(b.count), 0);
  const peak = Math.max(1, ...buckets.map((b) => n(b.count)));
  const dist = buckets
    .map((b) => `<div class="stats-bar-row static"><span class="stats-bar-label">${esc(b.label)}</span><span class="stats-bar-track" aria-hidden="true"><i class="stats-bar-fill tone-teal" style="width:${n(b.count) ? Math.max(4, Math.round((n(b.count) / peak) * 100)) : 0}%"></i></span><span class="stats-bar-val"><b>${n(b.count)}</b><small>${done ? Math.round((n(b.count) / done) * 100) : 0}%</small></span></div>`)
    .join("");
  const rows = (analytics.resolutionByCategory || [])
    .map((r) => `<tr><td>${esc(r.category)}</td><td class="num">${n(r.resolved)}건</td><td class="num">${r.avgDays == null ? "–" : `${Number(r.avgDays).toFixed(1)}일`}</td></tr>`)
    .join("");
  return `<div class="stats-two-col"><div><h3 class="stats-sub">접수부터 답변 게시까지</h3><div class="stats-bar-list">${dist}</div></div><div class="stats-db-table-wrap"><table><thead><tr><th scope="col">분야</th><th scope="col" class="num">처리 건수</th><th scope="col" class="num">평균 처리일</th></tr></thead><tbody>${rows}</tbody></table></div></div><p class="chart-note">답변이 게시된 민원 ${done}건 기준입니다. 아직 답변이 없는 민원은 포함하지 않습니다.${includeSynthetic ? " 공개 시연 데이터가 포함돼 있습니다." : ""}</p>`;
}

/** 분석 탭 전체(탭 막대·선택 패널)를 만듭니다. */
function analyticsSection(analytics, includeSynthetic) {
  if (!analytics || !analytics.trends?.length) return "";
  const tabs = ANALYTICS_TABS.map(
    ([key, label]) => `<button type="button" role="tab" class="stats-tab" aria-selected="${view.tab === key}" data-action="stats-tab" data-id="${key}">${esc(label)}</button>`,
  ).join("");
  let title = "";
  let panel = "";
  let extra = "";
  if (view.tab === "trend") {
    const series = analytics.trends.find((t) => t.unit === view.period) || analytics.trends[0];
    const recv = series.received.map(n);
    const done = series.resolved.map(n);
    const sum = recv.reduce((a, b) => a + b, 0);
    const doneSum = done.reduce((a, b) => a + b, 0);
    // 이번 구간은 진행 중이므로 비교에서 빼고, 끝난 직전 두 구간을 비교합니다.
    const current = recv.at(-1) ?? 0;
    const last = recv.at(-2) ?? 0;
    const prev = recv.at(-3) ?? 0;
    const chg = prev ? Math.round(((last - prev) / prev) * 1000) / 10 : null;
    const unit = { day: "일", week: "주", month: "월" }[series.unit];
    title = "접수·처리 추이";
    extra = `<div class="scope-switch" role="group" aria-label="집계 단위">${PERIODS.map(([key, label]) => `<button type="button" data-action="stats-period" data-id="${key}" aria-pressed="${view.period === key}">${label}</button>`).join("")}</div>`;
    panel = `<div class="trend-kpis"><div><span>기간 접수</span><b>${sum}건</b></div><div><span>기간 처리</span><b>${doneSum}건</b></div><div><span>지난 ${unit} 접수</span><b>${last}건</b><small class="${chg > 0 ? "up" : chg < 0 ? "down" : ""}">${chg == null ? "비교 대상 없음" : `${chg > 0 ? "▲" : chg < 0 ? "▼" : "–"} ${Math.abs(chg)}% 그 전 ${unit} 대비`} · 이번 ${unit} ${current}건(진행 중)</small></div><div><span>전체 처리율</span><b>${n(analytics.resolveRate)}%</b></div><div><span>AI 안내 완료율</span><b>${n(analytics.aiFirstResponseRate)}%</b><small>AI 결과가 FAQ 안내로 끝난 비율</small></div></div>${trendChart(series)}`;
  } else if (view.tab === "category") {
    title = "분야별 추이";
    panel = categoryLines(analytics);
  } else if (view.tab === "region") {
    title = "지역×분야 교차";
    panel = regionTable(analytics, includeSynthetic);
  } else if (view.tab === "time") {
    title = "시간대·요일 분포";
    panel = timeHeatmap(analytics);
  } else {
    title = "처리기간 분석";
    panel = periodPanel(analytics, includeSynthetic);
  }
  return `<section class="panel stats-analytics"><header><div><div class="eyebrow">통계 분석 · 민원 분류</div><h2>${esc(title)}</h2></div>${extra}</header><div class="stats-tabs" role="tablist" aria-label="분석 보기">${tabs}</div><div class="stats-analytics-body">${panel}</div></section>`;
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

  return `<div class="page-content staff-stats-page">${headerBar}<div class="info-banner">${icon("spark", 18)}<span>부서 담당자에게는 자기 부서 민원만 집계됩니다. 막대나 지표를 누르면 해당 조건의 민원 목록으로 바로 이동하며, CSV 내보내기에는 미게시 AI 초안과 순화 본문이 제외됩니다.</span></div>${kpiHtml}${analyticsSection(stats.analytics, includeSynthetic)}${chartsHtml}${dbSection}</div>`;
}
