/** llm 브랜치 응대 검사기의 질의 합성과 화면 경계를 검증합니다. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { labQuery, labShell } from "../src/lab.js";

test("제목·분야·본문을 검색 질의로 합친다", () => {
  const query = labQuery({
    category: "청소",
    title: "대형폐기물",
    body: "배출 방법이 궁금합니다",
  });
  assert.equal(query, "분야: 청소\n\n대형폐기물\n\n배출 방법이 궁금합니다");
});

test("검사기 껍데기에 시민·담당자 화면 링크가 없다", () => {
  const html = labShell("<p>본문</p>");
  assert.match(html, /href="#\/lab"/);
  assert.doesNotMatch(html, /href="#\/citizen"/);
  assert.doesNotMatch(html, /href="#\/staff"/);
});
