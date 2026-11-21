/** 민원인·담당자 아이디/비밀번호 로그인 모달 렌더러와 다중 사용자 소유권 필터링을 검증합니다. */
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

test("renderAuthBadge와 renderAuthModalHtml은 민원인·담당자 로그인 탭과 간단 가입·XSS 이스케이프를 처리한다", () => {
  assert.match(renderAuthBadge({ role: "citizen", demo: false }), /민원인/);
  assert.match(renderAuthBadge({ role: "staff", demo: false }), /담당자/);
  assert.match(renderAuthBadge({ role: "citizen", demo: true }), /시연/);

  const citizenTab = renderAuthModalHtml({
    tab: "citizen-login",
    error: "잘못된 <script>오류</script>",
  });
  assert.match(citizenTab, /auth-citizen-login-form/);
  assert.doesNotMatch(citizenTab, /citizen_01/, "기본 계정 안내를 노출하지 않는다");
  assert.doesNotMatch(citizenTab, /<script>/);
  assert.doesNotMatch(citizenTab, /본인확인/);

  const registerTab = renderAuthModalHtml({ tab: "citizen-register" });
  assert.match(registerTab, /auth-citizen-register-form/);
  assert.doesNotMatch(registerTab, /휴대전화/);

  const staffTab = renderAuthModalHtml({
    tab: "staff-login",
    site: "staff",
    actor: {
      displayName: "서원구 건설과 담당자",
      department: "서원구 건설과",
      role: "staff",
      demo: false,
    },
  });
  assert.match(staffTab, /auth-staff-login-form/);
  assert.doesNotMatch(staffTab, /staff_seowon|citizen_01/, "기본 계정 안내를 노출하지 않는다");
  assert.doesNotMatch(staffTab, /data-tab="citizen-login"/, "담당자 사이트는 민원인 탭이 없다");
  const citizenOnly = renderAuthModalHtml({ tab: "staff-login", site: "citizen" });
  assert.match(citizenOnly, /auth-citizen-login-form/, "시민 사이트는 담당자 탭 요청도 민원인 화면이다");
  assert.doesNotMatch(citizenOnly, /auth-staff-login-form/);
  assert.match(staffTab, /auth-logout/);
});

test("loginAccount와 visible은 로그인 사용자 ID 기준으로 본인 민원을 분리하고 세션을 유지한다", async () => {
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    if (url.endsWith("/auth/login")) {
      return {
        ok: true,
        status: 200,
        json: async () => ({
          id: "citizen-01",
          loginId: "citizen_01",
          displayName: "청주시민",
          role: "citizen",
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
    loginId: "citizen_01",
    password: "cheongju-citizen-2026!",
  });
  assert.equal(actor.id, "citizen-01");
  assert.equal(getActor().id, "citizen-01");

  const kept = await ensureRoleSession("citizen");
  assert.equal(kept.id, "citizen-01");
  assert.ok(!calls.some((u) => u.endsWith("/session")));

  const sample = {
    complaints: [
      { id: "C1", owner: "citizen-01", status: "submitted" },
      { id: "C2", owner: "citizen-demo", status: "submitted" },
      { id: "C3", owner: "citizen-01", status: "withdrawn" },
    ],
  };
  assert.deepEqual(
    visible(sample, true).map((c) => c.id),
    ["C1"],
  );

  await logoutAccount();
  assert.equal(getActor(), null);
});
