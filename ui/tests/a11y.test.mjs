import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = (name) => readFileSync(new URL(`../src/${name}`, import.meta.url), "utf8");
const lin = (v) => { const s = v / 255; return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; };
const lum = (hex) => { const n = parseInt(hex.slice(1), 16); return 0.2126 * lin((n >> 16) & 255) + 0.7152 * lin((n >> 8) & 255) + 0.0722 * lin(n & 255); };
const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };

test("보조 글자색(--muted)은 흰 바탕과 연한 회청 바탕에서 4.5:1 이상이다", () => {
  for (const file of ["citizen.css", "staff.css"]) {
    const m = read(file).match(/--muted:\s*(#[0-9a-fA-F]{6})/);
    assert.ok(m, `${file}에 --muted가 있어야 한다`);
    for (const bg of ["#ffffff", "#f6f8fc", "#eef2f9"]) {
      assert.ok(ratio(m[1], bg) >= 4.5, `${file} --muted ${m[1]} / ${bg} = ${ratio(m[1], bg).toFixed(2)}`);
    }
  }
});

test("작성 단계 숫자: 활성 단계의 파란 원 위 글자는 흰색이다", () => {
  const css = read("citizen.css");
  const rule = css.match(/\.citizen-shell \.form-steps \.active b\s*\{([^}]*)\}/);
  assert.ok(rule, "활성 단계 숫자 규칙이 있어야 한다");
  assert.match(rule[1], /color:\s*#fff/i);
  assert.ok(ratio("#ffffff", "#2f6fed") >= 4.4, "흰 글자/파란 원 대비");
});

test("작은 화면 헤더에서 로그인 버튼이 숨겨지지 않는다", () => {
  const design = read("design.css");
  assert.match(design, /max-width:\s*1100px[\s\S]*?\.btn\.auth-account-btn\s*\{\s*display:\s*inline-flex/, "1100px 이하에서 로그인 버튼을 다시 보이게 한다");
});
