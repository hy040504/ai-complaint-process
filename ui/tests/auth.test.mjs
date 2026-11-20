/** 운영 계정 인증 모달 렌더러와 다중 사용자 소유권 필터링을 검증합니다. */
import assert from "node:assert/strict";
import test from "node:test";

import { renderAuthBadge, renderAuthModalHtml } from "../src/auth.js";
import {
  ensureRoleSession,
  getActor,
  loginAccount,
  logoutAccount,
  visible,
} from "../src/store.js";

test("renderAuthBadge와 renderAuthModalHtml은 3개 탭·본인확인 OTP·XSS 이스케이프를 처리한다", () => {
  assert.match(
    renderAuthBadge({ role: "citizen", verified: true, demo: false }),
    /본인확인 완료/,
  );
  assert.match(
    renderAuthBadge({ role: "staff", verified: true, demo: false }),
    /담당자 인증/,
  );
  assert.match(
    renderAuthBadge({ role: "citizen", verified: true, demo: true }),
    /시연 계정/,
  );

  const step1 = renderAuthModalHtml({
    tab: "citizen-register",
    verifyChallenge: null,
    error: "잘못된 <script>오류</script>",
  });
  assert.match(step1, /auth-citizen-verify-form/);
  assert.doesNotMatch(step1, /<script>/);

  const step2 = renderAuthModalHtml({
    tab: "citizen-register",
    verifyChallenge: {
      challengeId: "VER-12345678",
      maskedPhone: "010-****-5678",
      expiresInSeconds: 300,
      demoCode: "482910",
      name: "홍길동",
    },
  });
  assert.match(step2, /auth-citizen-register-form/);
  assert.match(step2, /010-\*\*\*\*-5678/);
  assert.match(step2, /482910/);

  const staffTab = renderAuthModalHtml({
    tab: "staff-login",
    actor: {
      displayName: "서원구 건설과 담당자",
      department: "서원구 건설과",
      role: "staff",
      demo: false,
    },
  });
  assert.match(staffTab, /auth-staff-login-form/);
  assert.match(staffTab, /staff_seowon/);
  assert.match(staffTab, /auth-logout/);
});

test("loginAccount와 visible은 실계정 사용자 ID 기준으로 본인 민원을 분리하고 세션을 유지한다", async () => {
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    if (url.endsWith("/auth/login")) {
      return {
        ok: true,
        status: 200,
        json: async () => ({
          id: "USR-CIT-REAL1",
          loginId: "real_user",
          displayName: "실제시민",
          role: "citizen",
          verified: true,
          demo: false,
        }),
      };
    }
    if (url.endsWith("/auth/logout")) {
      return { ok: true, status: 204, json: async () => null };
    }
    return {
      ok: true,
      status: 200,
      json: async () => ({ id: "citizen-demo", role: "citizen", demo: true }),
    };
  };

  const actor = await loginAccount({
    loginId: "real_user",
    password: "password123",
  });
  assert.equal(actor.id, "USR-CIT-REAL1");
  assert.equal(getActor().id, "USR-CIT-REAL1");

  // ensureRoleSession은 이미 인증된 동일 역할 실계정을 demo 세션으로 덮어쓰지 않습니다.
  const kept = await ensureRoleSession("citizen");
  assert.equal(kept.id, "USR-CIT-REAL1");
  assert.ok(!calls.some((u) => u.endsWith("/session")));

  const sample = {
    complaints: [
      { id: "C1", owner: "USR-CIT-REAL1", status: "submitted" },
      { id: "C2", owner: "citizen-demo", status: "submitted" },
      { id: "C3", owner: "USR-CIT-REAL1", status: "withdrawn" },
    ],
  };
  assert.deepEqual(
    visible(sample, true).map((c) => c.id),
    ["C1"],
  );

  await logoutAccount();
  assert.equal(getActor(), null);
});
