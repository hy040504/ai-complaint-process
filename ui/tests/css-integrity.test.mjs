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
