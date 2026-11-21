import test from "node:test";
import assert from "node:assert/strict";

import {
  afterRender,
  countValue,
  easeOutCubic,
  enterAnimate,
  flashNewRows,
  prefersReducedMotion,
  runCountUps,
} from "../src/motion.js";

/** 동작 줄이기 설정을 흉내 냅니다. */
function setReduced(value) {
  globalThis.matchMedia = () => ({ matches: value });
}

function fakeCountEl(target, key = "") {
  return {
    dataset: { countup: String(target), ...(key ? { ck: key } : {}) },
    textContent: "",
    isConnected: true,
  };
}
function rootOf(elements) {
  return { querySelectorAll: () => elements };
}

test("easeOutCubic은 0~1로 잘라내고 끝으로 갈수록 느려진다", () => {
  assert.equal(easeOutCubic(-1), 0);
  assert.equal(easeOutCubic(2), 1);
  assert.equal(easeOutCubic(0), 0);
  assert.equal(easeOutCubic(1), 1);
  assert.ok(easeOutCubic(0.5) > 0.5, "초반이 빠르다");
  assert.ok(easeOutCubic(0.9) - easeOutCubic(0.8) < easeOutCubic(0.2) - easeOutCubic(0.1), "끝이 느려진다");
});

test("countValue는 시작·목표를 정확히 지나고 정수만 낸다", () => {
  assert.equal(countValue(0, 12, 0), 0);
  assert.equal(countValue(0, 12, 1), 12);
  assert.equal(countValue(5, 2, 1), 2, "감소도 지원");
  for (const p of [0.1, 0.33, 0.7]) assert.ok(Number.isInteger(countValue(0, 37, p)));
});

test("동작 줄이기가 켜져 있으면 숫자는 즉시 최종 값이고 진입 효과는 건너뛴다", () => {
  setReduced(true);
  assert.equal(prefersReducedMotion(), true);
  const a = fakeCountEl(7);
  const b = fakeCountEl(3, "k-reduced");
  runCountUps(rootOf([a, b]));
  assert.equal(a.textContent, "7");
  assert.equal(b.textContent, "3");
  assert.equal(enterAnimate({ querySelectorAll: () => [] }, "/reduced-path"), 0);
});

test("값이 바뀌지 않은 재렌더는 애니메이션 없이 최종 값을 바로 보여 준다", () => {
  setReduced(false);
  globalThis.requestAnimationFrame = () => 0; // 프레임을 돌리지 않아 시작값에서 멈춘 상태를 본다
  const first = fakeCountEl(5, "k-same");
  runCountUps(rootOf([first]));
  assert.equal(first.textContent, "0", "처음 보는 키는 0에서 시작");
  const again = fakeCountEl(5, "k-same");
  runCountUps(rootOf([again]));
  assert.equal(again.textContent, "5", "같은 값이면 즉시 최종 값");
  const changed = fakeCountEl(8, "k-same");
  runCountUps(rootOf([changed]));
  assert.equal(changed.textContent, "5", "값이 바뀌면 이전 값에서 이어서 시작");
  delete globalThis.requestAnimationFrame;
});

test("숫자가 아닌 목표는 건드리지 않는다", () => {
  setReduced(true);
  const el = { dataset: { countup: "-" }, textContent: "-", isConnected: true };
  runCountUps(rootOf([el]));
  assert.equal(el.textContent, "-");
});

function fakeRow(id) {
  const classes = new Set();
  const row = { classList: { add: (c) => classes.add(c) }, classes, style: {} };
  return {
    row,
    a: { getAttribute: () => `#/staff/detail/${id}`, closest: () => row },
  };
}

test("새 행 플래시는 같은 화면에 새로 생긴 행에만 걸리고 필터 전환에는 반응하지 않는다", () => {
  const r1 = fakeRow("A-1");
  const r2 = fakeRow("A-2");
  assert.deepEqual(flashNewRows(rootOf([r1.a, r2.a]), "#/staff"), [], "첫 렌더는 기준만 잡는다");
  const r3 = fakeRow("A-3");
  assert.deepEqual(flashNewRows(rootOf([r3.a, r1.a, r2.a]), "#/staff"), ["A-3"]);
  assert.ok(r3.row.classes.has("row-flash"));
  assert.equal(r1.row.classes.has("row-flash"), false);
  assert.deepEqual(flashNewRows(rootOf([r3.a, r1.a, r2.a]), "#/staff"), [], "같은 행은 다시 플래시하지 않는다");
  const other = fakeRow("B-9");
  assert.deepEqual(flashNewRows(rootOf([other.a]), "#/staff?status=submitted"), [], "필터가 바뀌면 기준을 새로 잡는다");
  assert.equal(other.row.classes.has("row-flash"), false);
});

test("플래시 중 화면이 다시 그려져도 같은 행에 남은 시간만큼 이어서 적용한다", () => {
  const a = fakeRow("C-1");
  flashNewRows(rootOf([a.a]), "#/staff/rerender");
  const b = fakeRow("C-2");
  assert.deepEqual(flashNewRows(rootOf([b.a, a.a]), "#/staff/rerender"), ["C-2"]);
  const reDrawn = fakeRow("C-2"); // 재렌더로 새로 만들어진 같은 민원의 행
  const keep = fakeRow("C-1");
  assert.deepEqual(flashNewRows(rootOf([reDrawn.a, keep.a]), "#/staff/rerender"), [], "새 행으로 다시 세지 않는다");
  assert.ok(reDrawn.row.classes.has("row-flash"), "다시 그려진 행에도 플래시가 이어진다");
  assert.match(reDrawn.row.style.animationDelay, /^-\d+ms$/, "남은 시간만큼 음수 지연");
  assert.equal(keep.row.classes.has("row-flash"), false, "기존 행은 플래시하지 않는다");
});

test("afterRender는 숫자·진입·플래시를 모두 호출해도 빈 화면에서 오류가 없다", () => {
  setReduced(true);
  assert.doesNotThrow(() => afterRender({ querySelectorAll: () => [] }, "/citizen", "#/citizen"));
});
