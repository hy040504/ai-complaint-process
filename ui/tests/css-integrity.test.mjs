import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";

const dir = new URL("../src/", import.meta.url);
const files = readdirSync(dir).filter((name) => name.endsWith(".css"));

/** 주석을 제거합니다. */
function stripComments(css) {
  return css.replace(/\/\*[\s\S]*?\*\//g, "");
}
function count(text, ch) {
  return text.split(ch).length - 1;
}

test("모든 CSS 파일의 중괄호·소괄호·대괄호가 짝이 맞는다", () => {
  assert.ok(files.length >= 6, "CSS 파일을 찾지 못했다");
  for (const name of files) {
    const css = stripComments(readFileSync(new URL(name, dir), "utf8"));
    for (const [open, close] of [["{", "}"], ["(", ")"], ["[", "]"]]) {
      assert.equal(count(css, open), count(css, close), `${name}: ${open}${close} 개수 불일치`);
    }
  }
});

test("선택자는 괄호가 열린 채 잘리지 않는다(:is(a, b) 내부 쉼표 보존)", () => {
  for (const name of files) {
    const css = stripComments(readFileSync(new URL(name, dir), "utf8"));
    for (const m of css.matchAll(/([^{}]+)\{/g)) {
      const selector = m[1].trim();
      if (selector.startsWith("@")) continue;
      assert.equal(
        count(selector, "("),
        count(selector, ")"),
        `${name}: 괄호가 깨진 선택자 → ${selector.slice(0, 90)}`,
      );
      assert.equal(count(selector, "["), count(selector, "]"), `${name}: 대괄호가 깨진 선택자 → ${selector.slice(0, 90)}`);
    }
  }
});

test("다크 테마가 의존하는 표·제목 규칙이 남아 있다", () => {
  const themes = readFileSync(new URL("themes.css", dir), "utf8");
  assert.match(themes, /\.row-title/, "다크 row-title 규칙");
  assert.match(themes, /thead/, "다크 표 머리 규칙");
  assert.match(themes, /body\[data-theme="dark"\]/, "다크 테마 선택자");
});

test("모서리는 px 직접 값 없이 4단계 토큰만 쓴다", () => {
  for (const name of files) {
    if (name === "tokens.css") continue;
    const css = stripComments(readFileSync(new URL(name, dir), "utf8"));
    const bad = [...css.matchAll(/border(?:-(?:top|bottom)-(?:left|right))?-radius\s*:\s*([^;}]+)/g)]
      .map((m) => m[1].trim())
      .filter((v) => /\d+(\.\d+)?px/.test(v));
    assert.deepEqual(bad, [], `${name}: px 직접 모서리 ${bad.slice(0, 3).join(" | ")}`);
  }
});

test("다크 테마 색은 var(--d-*) 토큰을 거치고 tokens.css에 모두 정의돼 있다", () => {
  const themes = readFileSync(new URL("themes.css", dir), "utf8");
  const tokens = readFileSync(new URL("tokens.css", dir), "utf8");
  const used = new Set([...themes.matchAll(/var\((--d-(?:bg|text|line)-\d+)\)/g)].map((m) => m[1]));
  assert.ok(used.size >= 100, `다크 토큰 사용 수 ${used.size}`);
  for (const t of used) assert.match(tokens, new RegExp(`${t}:\\s*#[0-9a-fA-F]{6}`), `${t} 미정의`);
});

test("제목 3종의 글자 크기·굵기·자간은 design.css에서만 정의한다", () => {
  const owned = [
    ".page-heading h1", ".staff-page-title h1", ".section-title h2", ".citizen-section-label h2",
    ".staff-section-rule > h2", ".staff-section-rule h2", ".eyebrow", ".staff-workspace .eyebrow", ".citizen-shell .eyebrow",
  ];
  for (const name of files) {
    if (name === "design.css" || name === "tokens.css") continue;
    const css = stripComments(readFileSync(new URL(name, dir), "utf8"));
    for (const m of css.matchAll(/([^{}@;]+)\{([^{}]*)\}/g)) {
      const sel = m[1].trim().replace(/\s+/g, " ");
      if (!owned.includes(sel)) continue;
      assert.doesNotMatch(m[2], /font-size|font-weight|letter-spacing|line-height/, `${name}: ${sel}가 design.css 밖에서 글자 규격을 정의`);
    }
  }
  const design = readFileSync(new URL("design.css", dir), "utf8");
  for (const v of ["--ty-title", "--ty-section", "--ty-sub", "--ty-eyebrow"]) assert.match(design, new RegExp(`var\\(${v}\\)`), `${v} 미사용`);
});

test("타입 토큰은 라이트(:root)에서 정의된다", () => {
  const tokens = readFileSync(new URL("tokens.css", dir), "utf8");
  const root = tokens.slice(tokens.indexOf(":root"), tokens.indexOf("}", tokens.indexOf(":root")));
  for (const v of ["--ty-title", "--ty-section", "--ty-sub", "--ty-eyebrow"]) assert.match(root, new RegExp(`${v}:`), `${v}가 :root 밖에 있음`);
});
