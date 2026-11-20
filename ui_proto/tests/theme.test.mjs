/** 저장소를 차단한 환경에서도 테마를 반복 전환할 수 있는지 확인합니다. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { getTheme, readTheme, setTheme } from "../src/theme.js";

test("브라우저 저장이 실패해도 현재 테마를 기준으로 다시 전환한다", () => {
  globalThis.document = {
    body: { dataset: {} },
    documentElement: { style: {} },
    querySelector: () => null,
    querySelectorAll: () => [],
  };
  globalThis.localStorage = {
    getItem: () => {
      throw new Error("저장소 차단");
    },
    setItem: () => {
      throw new Error("저장소 차단");
    },
  };
  assert.equal(readTheme(), "light");
  setTheme("dark");
  assert.equal(getTheme(), "dark");
  setTheme(getTheme() === "dark" ? "light" : "dark");
  assert.equal(getTheme(), "light");
  assert.equal(document.body.dataset.theme, "light");
});
