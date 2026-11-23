/**
 * 담당자 통계 대시보드가 쓰는 SVG 차트 모음입니다. 외부 라이브러리 없이 문자열로 그립니다.
 *
 * 선·영역 시계열, 레이더, 세로 막대를 제공하며 격자·글자 색은 CSS 클래스
 * (`chart-grid`·`chart-axis`·`chart-label`)로 정해 라이트·다크 테마에서 함께 동작합니다.
 */

import { escapeHTML as esc } from "./citizen.js";

/** 시리즈 색 순서입니다. 분야·지역처럼 이름이 붙은 항목에 차례로 씁니다. */
export const SERIES_COLORS = ["#2f6fed", "#1f9d55", "#d97b06", "#7c5cd6", "#d5453c", "#7a8496"];

let chartSeq = 0;

/** 같은 페이지에서 여러 차트가 그라데이션 아이디를 겹치지 않게 새 접두어를 만듭니다. */
function nextUid(prefix) {
  chartSeq += 1;
  return `${prefix}${chartSeq}`;
}

const num = (value) => Number(value) || 0;

/**
 * 점 목록을 부드러운 곡선 경로(SVG `d`)로 바꿉니다.
 *
 * @param {Array<[number, number]>} pts 화면 좌표 점 목록입니다.
 * @returns {string} 3차 베지어 곡선 경로 문자열입니다. 점이 3개 미만이면 직선입니다.
 */
export function smoothPath(pts) {
  if (pts.length < 3) {
    return pts.map((p, i) => `${i ? "L" : "M"}${p[0]},${p[1]}`).join(" ");
  }
  let d = `M${pts[0][0]},${pts[0][1]}`;
  for (let i = 0; i < pts.length - 1; i += 1) {
    const p0 = pts[i - 1] || pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] || p2;
    const c1x = p1[0] + (p2[0] - p0[0]) / 6;
    const c1y = p1[1] + (p2[1] - p0[1]) / 6;
    const c2x = p2[0] - (p3[0] - p1[0]) / 6;
    const c2y = p2[1] - (p3[1] - p1[1]) / 6;
    d += ` C${c1x.toFixed(1)},${c1y.toFixed(1)} ${c2x.toFixed(1)},${c2y.toFixed(1)} ${p2[0]},${p2[1]}`;
  }
  return d;
}

/**
 * 영역 그라데이션이 있는 곡선 시계열 차트를 그립니다.
 *
 * @param {Array<[string, number[], string]>} series `[이름, 값 목록, 색]` 목록입니다.
 * @param {string[]} labels 가로축 표시 문구입니다.
 * @param {object} [opt] 표시 설정입니다.
 * @param {number} [opt.cur] 강조할 구간 번호입니다(기본: 마지막). 음수면 강조하지 않습니다.
 * @param {string} [opt.unit="건"] 값 뒤에 붙는 단위입니다.
 * @returns {string} SVG 문자열입니다.
 */
export function lineChart(series, labels, { cur = labels.length - 1, unit = "건" } = {}) {
  const w = 640;
  const h = 290;
  const P = { l: 36, r: 40, t: 16, b: 28 };
  const W = w - P.l - P.r;
  const H = h - P.t - P.b;
  const n = Math.max(2, labels.length);
  const peak = Math.max(1, ...series.flatMap((s) => s[1].map(num))) * 1.1;
  const x = (i) => +(P.l + i * (W / (n - 1))).toFixed(1);
  const y = (v) => +(P.t + H - (num(v) / peak) * H).toFixed(1);
  const uid = nextUid("lg");
  const defs = `<defs>${series
    .map(
      (s, i) =>
        `<linearGradient id="${uid}${i}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${s[2]}" stop-opacity=".22"/><stop offset="1" stop-color="${s[2]}" stop-opacity="0"/></linearGradient>`,
    )
    .join("")}</defs>`;
  const band =
    cur >= 0
      ? `<rect x="${x(cur) - W / (n - 1) / 2}" y="${P.t}" width="${W / (n - 1)}" height="${H}" class="chart-band" rx="6"/>`
      : "";
  const grid = [0, 0.25, 0.5, 0.75, 1]
    .map((g) => {
      const yy = y(peak * g);
      return `<line x1="${P.l}" x2="${P.l + W}" y1="${yy}" y2="${yy}" class="chart-grid dash"/><text x="${P.l - 8}" y="${yy + 3.5}" text-anchor="end" class="chart-axis">${Math.round(peak * g)}</text>`;
    })
    .join("");
  const body = series
    .map((s, i) => {
      const values = s[1].map(num);
      const pts = values.map((v, j) => [x(j), y(v)]);
      const d = smoothPath(pts);
      const area = `${d} L${x(values.length - 1)},${y(0)} L${x(0)},${y(0)} Z`;
      const dots = pts
        .map(
          (p, j) =>
            `<circle cx="${p[0]}" cy="${p[1]}" r="9" fill="transparent"><title>${esc(s[0])} · ${esc(labels[j])}: ${values[j]}${unit}</title></circle>${j === cur ? `<circle cx="${p[0]}" cy="${p[1]}" r="4.5" fill="${s[2]}" class="chart-dot"/>` : ""}`,
        )
        .join("");
      const end = i < 3 ? `<text x="${x(values.length - 1) + 6}" y="${y(values.at(-1)) + 3.5}" font-size="10" font-weight="700" fill="${s[2]}">${values.at(-1)}</text>` : "";
      return `<path d="${area}" fill="url(#${uid}${i})"/><path d="${d}" fill="none" stroke="${s[2]}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>${dots}${end}`;
    })
    .join("");
  const axisLabels = labels
    .map(
      (l, i) =>
        `<text x="${x(i)}" y="${h - 8}" text-anchor="middle" class="chart-axis${i === cur ? " cur" : ""}">${esc(l)}</text>`,
    )
    .join("");
  const baseline = `<line x1="${P.l}" x2="${P.l + W}" y1="${P.t + H}" y2="${P.t + H}" class="chart-base"/>`;
  return `<svg class="stats-svg" viewBox="0 0 ${w} ${h}" role="img" aria-label="시계열 차트">${defs}${band}${grid}${baseline}${body}${axisLabels}</svg>`;
}

/**
 * 여러 항목을 한 번에 비교하는 레이더(거미줄) 차트를 그립니다.
 *
 * @param {string[]} axes 축 이름 목록입니다(3개 이상).
 * @param {Array<[string, number[], string]>} series `[이름, 값 목록, 색]` 목록입니다. 마지막 시리즈가 주 시리즈입니다.
 * @returns {string} SVG 문자열입니다.
 */
export function radarChart(axes, series) {
  const size = 320;
  const cx = size / 2;
  const cy = size / 2 + 4;
  const R = size / 2 - 46;
  const n = axes.length;
  const pt = (i, r) => {
    const a = -Math.PI / 2 + (i * 2 * Math.PI) / n;
    return [+(cx + r * Math.cos(a)).toFixed(1), +(cy + r * Math.sin(a)).toFixed(1)];
  };
  const peak = Math.max(1, ...series.flatMap((s) => s[1].map(num))) * 1.05;
  const rings = [1, 0.75, 0.5, 0.25]
    .map(
      (g, k) =>
        `<polygon points="${axes.map((_, i) => pt(i, R * g).join(",")).join(" ")}" class="chart-ring ${k % 2 ? "alt" : ""}"/>`,
    )
    .join("");
  const spokes = axes
    .map((_, i) => {
      const p = pt(i, R);
      return `<line x1="${cx}" y1="${cy}" x2="${p[0]}" y2="${p[1]}" class="chart-grid"/>`;
    })
    .join("");
  const uid = nextUid("rg");
  const defs = `<defs>${series
    .map(
      (s, i) =>
        `<radialGradient id="${uid}${i}"><stop offset="0" stop-color="${s[2]}" stop-opacity=".05"/><stop offset="1" stop-color="${s[2]}" stop-opacity=".28"/></radialGradient>`,
    )
    .join("")}</defs>`;
  const polys = series
    .map(
      (s, i) =>
        `<polygon points="${s[1].map((v, j) => pt(j, (R * num(v)) / peak).join(",")).join(" ")}" fill="url(#${uid}${i})" stroke="${s[2]}" stroke-width="2.2" stroke-linejoin="round"/>${s[1]
          .map((v, j) => {
            const p = pt(j, (R * num(v)) / peak);
            return `<circle cx="${p[0]}" cy="${p[1]}" r="3.4" fill="${s[2]}" class="chart-dot"><title>${esc(s[0])} · ${esc(axes[j])}: ${num(v)}</title></circle>`;
          })
          .join("")}`,
    )
    .join("");
  const main = series[series.length - 1];
  const labels = axes
    .map((a, i) => {
      const l = pt(i, R + 22);
      const anchor = Math.abs(l[0] - cx) < 8 ? "middle" : l[0] < cx ? "end" : "start";
      return `<text x="${l[0]}" y="${l[1] + 1}" text-anchor="${anchor}" class="chart-label">${esc(a)}</text><text x="${l[0]}" y="${l[1] + 13}" text-anchor="${anchor}" font-size="9.5" font-weight="700" fill="${main[2]}">${num(main[1][i])}</text>`;
    })
    .join("");
  return `<svg class="stats-svg radar" viewBox="0 0 ${size} ${size + 14}" role="img" aria-label="레이더 차트">${defs}${rings}${spokes}${polys}${labels}</svg>`;
}

/**
 * 차트 아래 범례를 만듭니다. 값 목록이 있으면 현재 값과 직전 구간 대비 증감을 함께 보여 줍니다.
 *
 * @param {Array<[string, number[]|null, string]>} series `[이름, 값 목록 또는 null, 색]` 목록입니다.
 * @param {number} [cur] 현재로 볼 값의 번호입니다(기본: 마지막).
 * @returns {string} 범례 HTML입니다.
 */
export function legend(series, cur) {
  const items = series
    .map((s) => {
      const values = s[1];
      const at = cur == null ? (values?.length ?? 1) - 1 : cur;
      const v = values?.length ? num(values[at]) : null;
      const prev = values?.length && at > 0 ? num(values[at - 1]) : null;
      const delta = v != null && prev != null ? v - prev : null;
      const mark = delta == null ? "" : `<em class="${delta > 0 ? "up" : delta < 0 ? "down" : ""}">${delta > 0 ? "▲" : delta < 0 ? "▼" : "—"}${Math.abs(delta)}</em>`;
      return `<span class="lg-item"><i style="background:${s[2]}"></i>${esc(s[0])}${v != null ? ` <b>${v}</b>${mark}` : ""}</span>`;
    })
    .join("");
  return `<div class="lgd">${items}</div>`;
}

/**
 * 값 라벨이 붙은 세로 막대 차트를 그립니다.
 *
 * @param {Array<[string, number, string?]>} rows `[이름, 값, 색(선택)]` 목록입니다.
 * @param {string} [color="#2f6fed"] 기본 막대 색입니다.
 * @returns {string} SVG 문자열입니다.
 */
export function barsChart(rows, color = "#2f6fed") {
  const w = 420;
  const h = 190;
  const P = { l: 8, r: 8, t: 16, b: 26 };
  const W = w - P.l - P.r;
  const H = h - P.t - P.b;
  const n = Math.max(1, rows.length);
  const peak = Math.max(1, ...rows.map((r) => num(r[1]))) * 1.15;
  const bw = (W / n) * 0.62;
  const bars = rows
    .map((r, i) => {
      const bh = (num(r[1]) / peak) * H;
      const bx = P.l + i * (W / n) + (W / n - bw) / 2;
      const by = P.t + H - bh;
      return `<rect x="${bx.toFixed(1)}" y="${by.toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" rx="5" fill="${r[2] || color}"><title>${esc(r[0])}: ${num(r[1])}</title></rect><text x="${(bx + bw / 2).toFixed(1)}" y="${(by - 4).toFixed(1)}" text-anchor="middle" class="chart-label small">${num(r[1])}</text><text x="${(bx + bw / 2).toFixed(1)}" y="${h - 8}" text-anchor="middle" class="chart-axis">${esc(r[0])}</text>`;
    })
    .join("");
  return `<svg class="stats-svg" viewBox="0 0 ${w} ${h}" role="img" aria-label="막대 차트">${bars}</svg>`;
}
