/**
 * 담당자 통계 대시보드(`#/staff/stats`)와 CSV 내보내기 URL 구성을 담당합니다.
 *
 * 서버 `/api/v1/staff/stats`에서 담당자 부서 RBAC 소관 범위로 집계한
 * 운영 KPI·5종 분포 차트·정규화 7테이블 요약을 표시하며, 모든 차트 막대는
 * 해당 조건의 `#/staff/complaints?...` 목록으로 즉시 드릴다운됩니다.
 */

import { escapeHTML as esc } from "./citizen.js";
import { icon } from "./icons.js";
import { SERIES_COLORS, barsChart, legend, lineChart, radarChart } from "./stats-charts.js";

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

/** 민원 분류 탭 정의입니다. */
export const CLASSIFY_TABS = [
  ["overview", "종합"],
  ["region", "지역별"],
  ["time", "시간대·요일"],
  ["period", "처리기간"],
];
const PERIODS = [
  ["day", "일자별"],
  ["week", "주간별"],
  ["month", "월별"],
];
const PERIOD_META = {
  day: { label: "최근 14일", unit: "일", days: 14 },
  week: { label: "최근 8주", unit: "주", days: 56 },
  month: { label: "최근 12개월", unit: "월", days: 365 },
};
const WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"];

/** 화면에서 고른 분류 탭·집계 단위·지역입니다. 새로고침해도 같은 화면을 유지합니다. */
const view = { tab: "overview", period: "day", region: 0 };

/**
 * 분류 탭·집계 단위·선택 지역을 바꿉니다. 허용하지 않는 값은 무시합니다.
 *
 * @param {"tab"|"period"|"region"} kind 바꿀 항목입니다.
 * @param {string|number} value 새 값입니다. 지역은 표의 행 번호입니다.
 */
export function setStatsView(kind, value) {
  if (kind === "region") {
    const index = Number(value);
    if (Number.isInteger(index) && index >= 0 && index < 20) view.region = index;
    return;
  }
  const allowed = kind === "tab" ? CLASSIFY_TABS : PERIODS;
  if (allowed.some(([key]) => key === value)) view[kind] = value;
}

const n = (value) => Number(value) || 0;
const sum = (list) => (list || []).reduce((a, b) => a + n(b), 0);
const fmt = (value) => n(value).toLocaleString("ko-KR");

/** 증감률(%)을 계산합니다. 비교 대상이 0이면 null입니다. */
function changePct(last, prev) {
  return prev ? Math.round(((last - prev) / prev) * 1000) / 10 : null;
}

/** 증감률을 색 있는 작은 표지로 만듭니다. */
function deltaTag(pct) {
  if (pct == null) return '<span class="tag gray">–</span>';
  const cls = pct > 15 ? "red" : pct > 0 ? "amber" : "green";
  return `<span class="tag ${cls}">${pct > 0 ? "+" : ""}${pct.toFixed(1)}%</span>`;
}

/** 지역 이름의 표시 문구입니다. */
const districtName = (name) => (name === "모름" ? "위치 미지정" : name);

/** 값이 클수록 진한 히트맵 칸 단계(`hl0`~`hl4`)를 고릅니다. */
function heatLevel(value, peak) {
  if (!value || !peak) return "hl0";
  const r = value / peak;
  return r > 0.75 ? "hl4" : r > 0.5 ? "hl3" : r > 0.25 ? "hl2" : "hl1";
}

/** 구간 제목선(`통계 분석` 같은 큰 묶음 이름)을 만듭니다. */
function sectionTitle(text, note = "") {
  return `<div class="stats-sectitle"><span>${esc(text)}</span>${note ? `<small>${esc(note)}</small>` : ""}</div>`;
}

/** 지표 카드(통계 분석 상단 4개) 한 개를 만듭니다. */
function metricCard(label, value, sub, tone) {
  return `<div class="staff-kpi stat-metric"><span class="staff-kpi-label">${esc(label)}</span><strong>${esc(value)}</strong><span class="staff-kpi-sub ${tone}">${esc(sub)}</span></div>`;
}

/** 접수(진한 막대)와 처리(옅은 막대)를 값 라벨과 함께 보여 주는 막대 시계열입니다. */
function trendBars(series) {
  const recv = (series.received || []).map(n);
  const done = (series.resolved || []).map(n);
  const peak = Math.max(1, ...recv, ...done);
  const lastIndex = recv.length - 1;
  const cols = (series.labels || [])
    .map(
      (label, i) =>
        `<div class="tcol${i === lastIndex ? " hot" : ""}"><em>${recv[i]}</em><div class="tbars"><b style="height:${Math.max(4, Math.round((recv[i] / peak) * 130))}px" title="접수 ${recv[i]}건"></b><b class="d" style="height:${Math.max(4, Math.round((done[i] / peak) * 130))}px" title="처리 ${done[i]}건"></b></div><span>${esc(label)}</span></div>`,
    )
    .join("");
  return `<div class="tchart">${cols}</div><div class="lgd"><span class="lg-item"><i class="sw-recv"></i>접수</span><span class="lg-item"><i class="sw-done"></i>처리(답변 게시)</span><span class="lg-note">마지막 막대는 진행 중인 구간입니다</span></div>`;
}

/** 분야별 순위 표입니다. 비중 막대·건수·평균 처리일·전기 대비를 한 줄에 보여 줍니다. */
function categoryRanking(series, analytics, includeSynthetic) {
  const syn = includeSynthetic ? "" : "&synthetic=0";
  const avgDays = new Map((analytics.resolutionByCategory || []).map((r) => [r.category, r]));
  const rows = Object.entries(series.categoryReceived || {})
    .map(([name, counts]) => ({
      name,
      total: sum(counts),
      pct: changePct(n(counts.at(-2)), n(counts.at(-3))),
      info: avgDays.get(name),
    }))
    .sort((a, b) => b.total - a.total || a.name.localeCompare(b.name));
  const grand = Math.max(1, rows.reduce((a, r) => a + r.total, 0));
  const shades = ["#2f6fed", "#5a8df2", "#a9c2f0"];
  const body = rows
    .map((r, i) => {
      const share = (r.total / grand) * 100;
      const avg = r.info?.avgDays == null ? "–" : `${Number(r.info.avgDays).toFixed(1)}일`;
      return `<a class="catrow" href="#/staff/complaints?category=${encodeURIComponent(r.name)}${syn}"><span class="rk">${i + 1}</span><div class="nm"><b>${esc(r.name)}</b><span>처리 ${n(r.info?.resolved)}건</span></div><div class="bw"><div class="bar"><i style="width:${share.toFixed(1)}%;background:${shades[Math.min(i, 2)]}"></i></div></div><span class="pc">${share.toFixed(1)}</span><span class="ct">${fmt(r.total)}</span><span class="av">${avg}</span><span class="dl">${deltaTag(r.pct)}</span></a>`;
    })
    .join("");
  return `<div class="catrow-head"><span class="rk"></span><span class="nm">분야</span><span class="bw">비중</span><span class="pc">%</span><span class="ct">건수</span><span class="av">평균 처리</span><span class="dl">전기 대비</span></div>${body}`;
}

/** 요일×시각 행렬에서 시간대별 합계를 구합니다. */
function hourTotals(matrix) {
  return Array.from({ length: 24 }, (_, h) => (matrix || []).reduce((acc, row) => acc + n(row?.[h]), 0));
}

/** 시간대별 접수 막대(피크 강조)와 야간·주말 비중 안내입니다. */
function hourPanel(analytics) {
  const matrix = analytics.hourWeekday || [];
  const totals = hourTotals(matrix);
  const peak = Math.max(1, ...totals);
  const all = sum(totals);
  let offHours = 0;
  matrix.forEach((row, d) => (row || []).forEach((v, h) => {
    if (d >= 5 || h >= 22 || h < 6) offHours += n(v);
  }));
  const share = all ? Math.round((offHours / all) * 100) : 0;
  const bars = totals
    .map((v, h) => `<b class="${v >= peak * 0.85 ? "pk" : ""}" title="${h}시 ${v}건" style="height:${Math.max(3, Math.round((v / peak) * 70))}px"></b>`)
    .join("");
  return `<div class="hourbar">${bars}</div><div class="hourlab"><span>00</span><span>06</span><span>12</span><span>18</span><span>23</span></div><div class="stats-note blue"><b>야간·주말 접수가 ${share}%</b>입니다. 창구 운영 시간 밖에 들어온 민원을 AI가 먼저 안내하는 효과를 가늠하는 지표입니다.</div>`;
}

/** 일·주·월 세 기간을 한 표에서 비교합니다. 행을 누르면 위 차트의 집계 단위가 바뀝니다. */
function periodCompare(analytics) {
  const rows = analytics.trends
    .map((t) => {
      const meta = PERIOD_META[t.unit];
      const r = sum(t.received);
      const d = sum(t.resolved);
      const on = view.period === t.unit;
      return `<tr class="clickable${on ? " on" : ""}" data-action="stats-period" data-id="${t.unit}"><td><b>${esc(meta.label)}</b></td><td class="num">${fmt(r)}</td><td class="num">${fmt(d)}</td><td class="num">${r ? Math.round((d / r) * 100) : 0}%</td><td class="num">${(r / meta.days).toFixed(1)}</td><td>${on ? "현재 보는 기간" : "누르면 위 차트가 바뀝니다"}</td></tr>`;
    })
    .join("");
  return `<div class="stats-db-table-wrap"><table><thead><tr><th scope="col">구분</th><th scope="col" class="num">접수</th><th scope="col" class="num">처리 완료</th><th scope="col" class="num">처리율</th><th scope="col" class="num">일평균</th><th scope="col">비고</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

/**
 * `통계 분석` 구역: 기간 전환·지표 카드·접수·처리 추이·분야 순위·시간대/요일·기간 비교입니다.
 *
 * @param {object} analytics 서버 `analytics` 객체입니다.
 * @param {boolean} includeSynthetic 공개 시연 데이터 포함 여부입니다.
 * @returns {string} 구역 HTML입니다.
 */
function statsAnalysis(analytics, includeSynthetic) {
  const series = analytics.trends.find((t) => t.unit === view.period) || analytics.trends[0];
  const meta = PERIOD_META[series.unit];
  const recv = (series.received || []).map(n);
  const done = (series.resolved || []).map(n);
  const total = sum(recv);
  const doneTotal = sum(done);
  const current = recv.at(-1) ?? 0;
  const last = recv.at(-2) ?? 0;
  const prev = recv.at(-3) ?? 0;
  const chg = changePct(last, prev);
  const rate = total ? Math.round((doneTotal / total) * 100) : 0;
  const switcher = `<div class="scope" role="group" aria-label="집계 단위">${PERIODS.map(([key, label]) => `<button type="button" data-action="stats-period" data-id="${key}" aria-pressed="${view.period === key}">${label}</button>`).join("")}</div>`;
  const cards = [
    metricCard(`${meta.label} 접수`, `${fmt(total)}건`, `일평균 ${(total / meta.days).toFixed(1)}건`, "blue"),
    metricCard(`${meta.label} 처리 완료`, `${fmt(doneTotal)}건`, `처리율 ${rate}%`, rate >= 90 ? "green" : "gold"),
    metricCard(
      `지난 ${meta.unit} 접수`,
      `${fmt(last)}건`,
      chg == null ? `비교 대상 없음 · 이번 ${meta.unit} ${current}건` : `${chg > 0 ? "▲" : chg < 0 ? "▼" : "–"} ${Math.abs(chg)}% 그 전 ${meta.unit} 대비 · 이번 ${meta.unit} ${current}건(진행 중)`,
      chg != null && chg >= 15 ? "red" : chg != null && chg > 0 ? "gold" : "green",
    ),
    metricCard("AI 안내 완료율", `${n(analytics.aiFirstResponseRate)}%`, "AI 결과가 FAQ 안내로 끝난 비율", "blue"),
  ].join("");
  const weekdayTotals = (analytics.hourWeekday || []).map((row) => sum(row));
  const weekdayRows = WEEKDAYS.map((d, i) => [d, weekdayTotals[i] || 0, i >= 5 ? "#d97b06" : undefined]);
  return `${sectionTitle("통계 분석", `${meta.label} 기준`)}<div class="stats-toolbar">${switcher}</div><div class="stats-metric-grid">${cards}</div>
<section class="panel stats-panel"><header><h3>${esc(meta.label)} 접수·처리 추이</h3><span class="r">막대에 마우스를 올리면 정확한 건수가 보입니다</span></header><div class="pad">${trendBars(series)}</div></section>
${sectionTitle("민원 분야 분포", meta.label)}
<section class="panel stats-panel"><div class="catrows">${categoryRanking(series, analytics, includeSynthetic)}</div></section>
<div class="stats-two"><section class="panel stats-panel"><header><h3>시간대별 접수 분포</h3><span class="r">0시 ~ 23시 · 한국 시간</span></header><div class="pad">${hourPanel(analytics)}</div></section>
<section class="panel stats-panel"><header><h3>요일별 접수</h3><span class="r">주말은 주황</span></header><div class="pad">${barsChart(weekdayRows)}</div></section></div>
${sectionTitle("기간 비교 요약")}
<section class="panel stats-panel"><div class="pad flush">${periodCompare(analytics)}</div></section>`;
}

/** 종합 탭: 분야별 12개월 곡선 시계열과 이번 달·지난달 레이더입니다. */
function classifyOverview(analytics) {
  const month = analytics.trends.find((t) => t.unit === "month") || analytics.trends[0];
  const cats = Object.keys(month.categoryReceived || {});
  const colored = cats.map((name, i) => [name, (month.categoryReceived[name] || []).map(n), SERIES_COLORS[i % SERIES_COLORS.length]]);
  const radar = [
    ["지난달", colored.map((s) => s[1].at(-2) ?? 0), "#a6aebd"],
    ["이번 달(진행 중)", colored.map((s) => s[1].at(-1) ?? 0), "#2f6fed"],
  ];
  const growth = (analytics.categoryTrends || []).filter((c) => c.changePct != null && c.total > 0).sort((a, b) => b.changePct - a.changePct)[0];
  const insight = growth
    ? `지난달 가장 크게 늘어난 분야는 <b>${esc(growth.category)}</b>(${growth.changePct > 0 ? "+" : ""}${growth.changePct}%)입니다. 늘어나는 분야는 안내 문구와 담당 배정을 미리 점검할 만한 후보입니다.`
    : "비교할 지난달 자료가 아직 부족합니다. 접수가 쌓이면 늘어나는 분야를 알려 줍니다.";
  return `<div class="stats-two wide"><section class="panel stats-panel"><header><h3>분야별 12개월 접수 추이</h3><span class="r">건 · 마지막 달은 진행 중 · 점에 마우스를 올리면 값</span></header><div class="pad">${lineChart(colored, month.labels || [])}${legend(colored)}</div></section>
<section class="panel stats-panel"><header><h3>분야 레이더 — 이번 달 vs 지난달</h3><span class="r">건수</span></header><div class="pad">${radarChart(cats, radar)}${legend([["지난달", null, "#a6aebd"], ["이번 달", null, "#2f6fed"]])}</div></section></div>
<div class="stats-note gold"><b>이렇게 읽습니다</b> — ${insight}</div>`;
}

/** 지역별 탭: 지역×분야 히트맵(행 선택)과 선택 지역 레이더·상위 분야입니다. */
function classifyRegion(analytics, includeSynthetic) {
  const cats = analytics.categories || [];
  const rows = analytics.districtCategory || [];
  const index = Math.min(view.region, Math.max(0, rows.length - 1));
  const row = rows[index];
  const peak = Math.max(1, ...rows.flatMap((r) => (r.counts || []).map(n)));
  const syn = includeSynthetic ? "" : "&synthetic=0";
  const head = `<tr><th></th>${cats.map((c) => `<th>${esc(c)}</th>`).join("")}<th>합계</th></tr>`;
  const body = rows
    .map(
      (r, i) =>
        `<tr class="pick${i === index ? " on" : ""}" data-action="stats-region" data-id="${i}"><td class="dept">${esc(districtName(r.district))}</td>${(r.counts || []).map((v) => `<td><b class="${heatLevel(n(v), peak)}">${n(v)}</b></td>`).join("")}<td><b class="hl-total">${n(r.total)}</b></td></tr>`,
    )
    .join("");
  const avg = cats.map((_, j) => Math.round(rows.reduce((acc, r) => acc + n(r.counts?.[j]), 0) / Math.max(1, rows.length)));
  const ranked = row ? cats.map((c, j) => [c, n(row.counts?.[j])]).sort((a, b) => b[1] - a[1]) : [];
  const top = ranked.slice(0, 3).filter((r) => r[1] > 0);
  const name = row ? districtName(row.district) : "";
  const topText = top.length ? top.map((r) => `<b>${esc(r[0])}</b>(${r[1]}건)`).join(" · ") : "아직 접수가 없습니다";
  return `<section class="panel stats-panel"><header><h3>지역 × 분야 — 접수 건수</h3><span class="r">행을 누르면 아래 레이더가 바뀝니다</span></header><div class="heat-wrap"><table class="heat">${head}${body}</table></div></section>
<div class="stats-two"><section class="panel stats-panel"><header><h3>${esc(name)} — 분야 레이더</h3><span class="r">vs 전체 평균</span></header><div class="pad">${row ? radarChart(cats, [["전체 평균", avg, "#a6aebd"], [name, (row.counts || []).map(n), "#2f6fed"]]) : ""}${legend([["전체 평균", null, "#a6aebd"], [name, null, "#2f6fed"]])}</div></section>
<section class="panel stats-panel"><header><h3>${esc(name)} 상위 분야</h3><span class="r"><a class="text-link" href="#/staff/complaints?district=${encodeURIComponent(row?.district || "")}${syn}">이 지역 목록 보기</a></span></header><div class="pad">${barsChart(ranked.slice(0, 6), "#4f46e5")}<div class="stats-note blue"><b>${esc(name)}</b>에서 많이 접수된 분야: ${topText}</div></div></section></div>`;
}

/** 시간대·요일 탭: 요일×24시간 히트맵, 시간대 막대, 요일 레이더입니다. */
function classifyTime(analytics) {
  const matrix = analytics.hourWeekday || [];
  const peak = Math.max(1, ...matrix.flat().map(n));
  const head = `<tr><th></th>${Array.from({ length: 24 }, (_, h) => `<th>${h % 3 === 0 ? h : ""}</th>`).join("")}</tr>`;
  const body = WEEKDAYS.map(
    (day, d) =>
      `<tr><td class="dept">${day}요일</td>${Array.from({ length: 24 }, (_, h) => `<td><b class="${heatLevel(n(matrix[d]?.[h]), peak)}" title="${day}요일 ${h}시 ${n(matrix[d]?.[h])}건"></b></td>`).join("")}</tr>`,
  ).join("");
  const weekday = matrix.map((row) => sum(row));
  const mean = Math.round(sum(weekday) / 7);
  return `<section class="panel stats-panel"><header><h3>요일 × 시간대 — 접수 건수</h3><span class="r">진할수록 접수가 몰립니다 · 한국 시간</span></header><div class="heat-wrap"><table class="heat tight">${head}${body}</table></div></section>
<div class="stats-two"><section class="panel stats-panel"><header><h3>시간대별 접수</h3><span class="r">0시 ~ 23시</span></header><div class="pad">${hourPanel(analytics)}</div></section>
<section class="panel stats-panel"><header><h3>요일 레이더</h3><span class="r">vs 요일 평균</span></header><div class="pad">${radarChart(WEEKDAYS, [["요일 평균", WEEKDAYS.map(() => mean), "#a6aebd"], ["요일별 접수", weekday, "#2f6fed"]])}${legend([["요일 평균", null, "#a6aebd"], ["요일별 접수", null, "#2f6fed"]])}</div></section></div>`;
}

/** 처리기간 탭: 접수부터 답변 게시까지 구간 분포와 분야별 평균 처리일입니다. */
function classifyPeriod(analytics) {
  const buckets = analytics.resolutionBuckets || [];
  const done = sum(buckets.map((b) => b.count));
  const peak = Math.max(1, ...buckets.map((b) => n(b.count)));
  const dist = buckets
    .map((b) => `<div class="stats-bar-row static"><span class="stats-bar-label">${esc(b.label)}</span><span class="stats-bar-track" aria-hidden="true"><i class="stats-bar-fill tone-teal" style="width:${n(b.count) ? Math.max(4, Math.round((n(b.count) / peak) * 100)) : 0}%"></i></span><span class="stats-bar-val"><b>${n(b.count)}</b><small>${done ? Math.round((n(b.count) / done) * 100) : 0}%</small></span></div>`)
    .join("");
  const rows = [...(analytics.resolutionByCategory || [])].sort((a, b) => (b.avgDays ?? -1) - (a.avgDays ?? -1));
  const maxAvg = Math.max(1, ...rows.map((r) => n(r.avgDays)));
  const table = rows
    .map(
      (r) =>
        `<div class="catrow"><div class="nm"><b>${esc(r.category)}</b><span>처리 ${n(r.resolved)}건</span></div><div class="bw"><div class="bar"><i style="width:${r.avgDays == null ? 0 : Math.max(4, Math.round((n(r.avgDays) / maxAvg) * 100))}%;background:#0d9488"></i></div></div><span class="av wide">${r.avgDays == null ? "–" : `${Number(r.avgDays).toFixed(1)}일`}</span></div>`,
    )
    .join("");
  const slowest = rows.find((r) => r.avgDays != null);
  const insight = slowest
    ? `평균 처리 기간이 가장 긴 분야는 <b>${esc(slowest.category)}</b>(${Number(slowest.avgDays).toFixed(1)}일)입니다. 답변이 게시된 민원 ${done}건 기준이며 아직 답변이 없는 민원은 포함하지 않습니다.`
    : "아직 답변이 게시된 민원이 없어 처리 기간을 계산할 수 없습니다.";
  return `<div class="stats-two"><section class="panel stats-panel"><header><h3>접수부터 답변 게시까지</h3><span class="r">구간별 건수</span></header><div class="pad"><div class="stats-bar-list">${dist}</div></div></section>
<section class="panel stats-panel"><header><h3>분야별 평균 처리일</h3><span class="r">긴 순서</span></header><div class="catrows">${table}</div></section></div>
<div class="stats-note gold"><b>이렇게 읽습니다</b> — ${insight}</div>`;
}

/**
 * `민원 분류` 구역: 탭 막대와 선택한 탭의 차트·표를 만듭니다.
 *
 * @param {object} analytics 서버 `analytics` 객체입니다.
 * @param {boolean} includeSynthetic 공개 시연 데이터 포함 여부입니다.
 * @returns {string} 구역 HTML입니다.
 */
function classifySection(analytics, includeSynthetic) {
  const tabs = CLASSIFY_TABS.map(
    ([key, label]) => `<button type="button" role="tab" class="stats-tab" aria-selected="${view.tab === key}" data-action="stats-tab" data-id="${key}">${esc(label)}</button>`,
  ).join("");
  let panel;
  if (view.tab === "region") panel = classifyRegion(analytics, includeSynthetic);
  else if (view.tab === "time") panel = classifyTime(analytics);
  else if (view.tab === "period") panel = classifyPeriod(analytics);
  else panel = classifyOverview(analytics);
  return `${sectionTitle("민원 분류", "분야·지역·시간·처리기간으로 민원을 읽습니다")}<div class="stats-tabs" role="tablist" aria-label="분류 보기">${tabs}</div>${panel}`;
}

/** 통계 분석과 민원 분류 두 구역을 이어 붙입니다. 집계가 없으면 빈 문자열입니다. */
function analyticsSection(analytics, includeSynthetic) {
  if (!analytics || !analytics.trends?.length) return "";
  return statsAnalysis(analytics, includeSynthetic) + classifySection(analytics, includeSynthetic);
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

  return `<div class="page-content staff-stats-page">${headerBar}<div class="info-banner">${icon("spark", 18)}<span>부서 담당자에게는 자기 부서 민원만 집계됩니다. 막대나 지표를 누르면 해당 조건의 민원 목록으로 바로 이동하며, CSV 내보내기에는 미게시 AI 초안과 순화 본문이 제외됩니다.</span></div>${sectionTitle("업무 현황", "지표를 누르면 해당 목록으로 이동합니다")}${kpiHtml}${analyticsSection(stats.analytics, includeSynthetic)}${sectionTitle("처리 현황 분포", "막대를 누르면 해당 조건의 민원 목록으로 이동합니다")}${chartsHtml}${dbSection}</div>`;
}
