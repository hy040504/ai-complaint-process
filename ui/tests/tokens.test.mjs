import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const css = readFileSync(new URL("../src/tokens.css", import.meta.url), "utf8");

/** 선언 블록에서 `--이름: 값;`을 읽습니다. */
function vars(block) {
  const out = {};
  for (const m of block.matchAll(/(--[\w-]+):\s*([^;]+);/g)) out[m[1]] = m[2].trim();
  return out;
}
const rootBlock = css.match(/:root\s*\{([\s\S]*?)\n\}/)[1];
const darkBlock = css.match(/body\[data-theme="dark"\]\s*\{([\s\S]*?)\n\}/)[1];
const light = vars(rootBlock);
const dark = { ...light, ...vars(darkBlock) };

/** `#rrggbb` 또는 `rgba(r,g,b,a)`를 [r,g,b,a]로 바꿉니다. */
function rgba(value) {
  const hex = value.match(/^#([0-9a-f]{6})$/i);
  if (hex) {
    const n = parseInt(hex[1], 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255, 1];
  }
  const m = value.match(/^rgba?\(([^)]+)\)$/);
  assert.ok(m, `해석할 수 없는 색: ${value}`);
  const [r, g, b, a = 1] = m[1].split(",").map(Number);
  return [r, g, b, a];
}
/** 반투명 색을 배경 위에 합성합니다. */
function over(fg, bg) {
  const [r, g, b, a] = fg;
  return [0, 1, 2].map((i) => Math.round([r, g, b][i] * a + bg[i] * (1 - a)));
}
function luminance([r, g, b]) {
  const c = [r, g, b].map((v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}
function contrast(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const PAIRS = ["wait", "review", "done", "closed", "fail"];
const SURFACES = {
  light: [[255, 255, 255], [246, 248, 252]],
  dark: [[25, 38, 59], [16, 24, 39]],
};

test("라이트 상태 칩은 글자와 배경 대비가 4.5:1 이상이다", () => {
  for (const key of PAIRS) {
    const bg = over(rgba(light[`--st-${key}-bg`]), [255, 255, 255]);
    const fg = rgba(light[`--st-${key}-fg`]).slice(0, 3);
    assert.ok(contrast(fg, bg) >= 4.5, `${key} ${contrast(fg, bg).toFixed(2)}`);
  }
  const ring = rgba(light["--st-withdrawn-fg"]).slice(0, 3);
  assert.ok(contrast(ring, [255, 255, 255]) >= 4.5, "철회 글자");
});

test("다크 상태 칩은 두 가지 어두운 면 위에서 4.5:1 이상이다", () => {
  for (const surface of SURFACES.dark) {
    for (const key of PAIRS) {
      const bg = over(rgba(dark[`--st-${key}-bg`]), surface);
      const fg = rgba(dark[`--st-${key}-fg`]).slice(0, 3);
      assert.ok(contrast(fg, bg) >= 4.5, `${key} on ${surface} ${contrast(fg, bg).toFixed(2)}`);
    }
    assert.ok(contrast(rgba(dark["--st-withdrawn-fg"]).slice(0, 3), surface) >= 4.5, "철회 글자");
  }
});

test("브랜드 글자·버튼 조합도 기준을 만족한다", () => {
  const ink = rgba(light["--cj-ink"]).slice(0, 3);
  assert.ok(contrast(ink, rgba(light["--cj-bg"]).slice(0, 3)) >= 7, "본문");
  assert.ok(contrast(rgba(light["--cj-ink-2"]).slice(0, 3), [255, 255, 255]) >= 4.5, "보조 글자");
  assert.ok(contrast([255, 255, 255], rgba(light["--cj-blue"]).slice(0, 3)) >= 4.5, "주 버튼 글자");
  assert.ok(contrast(rgba(light["--cj-blue-deep"]).slice(0, 3), [255, 255, 255]) >= 4.5, "눌림·링크");
});

test("모서리 4단계·그림자 3단계·간격 7단계·모션 3종이 정의돼 있다", () => {
  assert.deepEqual(
    ["--r-chip", "--r-control", "--r-card", "--r-pill"].map((k) => light[k]),
    ["6px", "10px", "16px", "999px"],
  );
  for (const k of ["--e1", "--e2", "--e3"]) assert.match(light[k], /rgba\(22, 32, 58/);
  assert.equal(Object.keys(light).filter((k) => /^--sp-\d$/.test(k)).length, 7);
  assert.deepEqual(["--dur-fast", "--dur-base", "--dur-slow"].map((k) => light[k]), ["120ms", "220ms", "420ms"]);
});

test("기존 변수는 토큰으로 연결돼 라이트의 청록 잔재가 없다", () => {
  assert.equal(light["--teal"], "var(--cj-blue)");
  assert.equal(light["--radius"], "var(--r-card)");
  assert.ok(!/#087f72/i.test(css), "청록 값이 남아 있으면 안 된다");
});

test("옛 상태 배지 정의는 design.css 한 곳에만 있다", () => {
  const files = ["styles.css", "citizen.css", "staff.css", "themes.css", "lab.css"];
  for (const f of files) {
    const text = readFileSync(new URL(`../src/${f}`, import.meta.url), "utf8");
    assert.ok(
      !/\.badge\.(submitted|under_review|answered|closed|withdrawn)\b/.test(text),
      `${f}에 상태 배지 정의가 남아 있다`,
    );
  }
  const design = readFileSync(new URL("../src/design.css", import.meta.url), "utf8");
  for (const s of ["submitted", "under_review", "answered", "closed", "withdrawn"]) {
    assert.match(design, new RegExp(`\\)\\.${s}\\s*\\{`), `design.css에 ${s} 없음`);
  }
});

test("design.css의 움직임은 동작 줄이기 미설정 조건 안에만 있다", () => {
  const design = readFileSync(new URL("../src/design.css", import.meta.url), "utf8");
  const outside = design.replace(/@media \(prefers-reduced-motion: no-preference\) \{[\s\S]*?\n\}\n(?=\n@keyframes)/, "");
  assert.ok(!/animation:\s*cj-/.test(outside), "미디어 조건 밖에 animation이 있다");
});
