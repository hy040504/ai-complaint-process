import test from "node:test";
import assert from "node:assert/strict";
import { hiddenByStaff, staffProcess } from "../src/staff.js";

const base = {
  id: "DEMO-1",
  status: "submitted",
  visibility: "public",
  assigned: false,
  department: null,
  draft: "",
  draftVersion: 0,
  published: null,
  messages: [],
  history: [],
};

test("담당자가 내린 상태는 이력의 마지막 조정으로 판별한다", () => {
  assert.equal(hiddenByStaff({ ...base, history: [] }), false);
  assert.equal(hiddenByStaff({ ...base, history: [{ text: "게시판에서 내림(비공개 전환): 개인정보" }] }), true);
  assert.equal(
    hiddenByStaff({
      ...base,
      history: [{ text: "게시판에서 내림(비공개 전환): 개인정보" }, { text: "게시판에 다시 공개: 확인" }],
    }),
    false,
  );
  assert.equal(hiddenByStaff({ ...base, history: [{ text: "시민이 민원 내용 수정" }] }), false);
});

test("공개 민원에는 내리기, 담당자가 내린 민원에는 다시 공개 버튼만 보인다", () => {
  const publicHtml = staffProcess({ ...base });
  assert.match(publicHtml, /data-action="hide-complaint"/);
  assert.doesNotMatch(publicHtml, /data-action="restore-complaint"/);

  const hidden = { ...base, visibility: "private", history: [{ text: "게시판에서 내림(비공개 전환): 사유" }] };
  const hiddenHtml = staffProcess(hidden);
  assert.match(hiddenHtml, /data-action="restore-complaint"/);
  assert.doesNotMatch(hiddenHtml, /data-action="hide-complaint"/);
});

test("작성자가 직접 비공개로 정한 민원과 철회된 민원에는 버튼이 없다", () => {
  const authorPrivate = staffProcess({ ...base, visibility: "private" });
  assert.doesNotMatch(authorPrivate, /data-action="(hide|restore)-complaint"/);
  const withdrawn = staffProcess({ ...base, status: "withdrawn" });
  assert.doesNotMatch(withdrawn, /data-action="(hide|restore)-complaint"/);
});
