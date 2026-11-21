import test from "node:test";
import assert from "node:assert/strict";

import { SITE, SITE_HEADER, homePath, normalizePath, siteHeaders } from "../src/site.js";

test("브라우저가 아닌 환경에서는 시민 사이트가 기본이다", () => {
  assert.equal(SITE, "citizen");
  assert.equal(SITE_HEADER, "X-Cheongju-Site");
  assert.deepEqual(siteHeaders({ A: "1" }), { "X-Cheongju-Site": "citizen", A: "1" });
  assert.equal(homePath(), "/citizen");
  assert.equal(homePath("staff"), "/staff");
});

test("시민 사이트는 /citizen 경로만 허용하고 나머지는 홈으로 돌린다", () => {
  assert.equal(normalizePath("/citizen/mine", "citizen"), "/citizen/mine");
  assert.equal(normalizePath("/staff/stats", "citizen"), "/citizen");
  assert.equal(normalizePath("/lab", "citizen"), "/citizen");
  assert.equal(normalizePath("", "citizen"), "/citizen");
  assert.equal(normalizePath("/", "citizen"), "/citizen");
});

test("담당자 사이트는 /staff 경로와 검사기(/lab)만 허용한다", () => {
  assert.equal(normalizePath("/staff/complaints", "staff"), "/staff/complaints");
  assert.equal(normalizePath("/lab", "staff"), "/lab");
  assert.equal(normalizePath("/citizen/mine", "staff"), "/staff");
  assert.equal(normalizePath("", "staff"), "/staff");
});
