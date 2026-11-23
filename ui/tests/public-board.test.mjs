/** 로그인하지 않은 방문자의 공개 민원 게시판 읽기(CASE-132)를 검증합니다. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { loadPublicWorkspace, read, visible } from "../src/store.js";

test("방문자는 세션 없이 공개 스냅샷을 받고, 어떤 민원의 작성자로도 간주되지 않는다", async () => {
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return {
      ok: true,
      status: 200,
      json: async () => ({
        role: "citizen",
        revision: 3,
        complaints: [
          { id: "DEMO-1", owner: "citizen-demo", status: "submitted", visibility: "public" },
          { id: "DEMO-2", owner: "guest-abc", status: "withdrawn", visibility: "public" },
        ],
      }),
    };
  };
  await loadPublicWorkspace();
  assert.equal(calls[0].url, "/api/v1/public/workspace");
  assert.equal(calls[0].options.method, "GET");
  assert.equal(read().complaints.length, 2);
  // 게시판(전체)에는 철회되지 않은 공개 민원이 보이고,
  assert.deepEqual(visible(read()).map((c) => c.id), ["DEMO-1"]);
  // 방문자는 시연 민원인("citizen-demo")의 글도 "내 민원"으로 잡지 않는다.
  assert.deepEqual(visible(read(), true), []);
});
