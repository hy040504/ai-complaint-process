"""두 사이트 공통 시연 로그인(abcd / (시연 비밀번호)) 테스트입니다."""

from __future__ import annotations

from typing import Any

from src.app import create_app
from src.complaints.config import Settings
from src.complaints.sites import SITE_HEADER

CITIZEN = {SITE_HEADER: "citizen"}
STAFF = {SITE_HEADER: "staff"}


def _app() -> Any:
    """메모리 저장소의 테스트용 앱을 만듭니다."""
    return create_app(
        Settings(secret_key="test-demo-accounts", backend="memory", testing=True),
        auto_start_ai=False,
    )


def _login(client: Any, site: dict[str, str], role: str, password: str = "demo-pass-1") -> Any:
    """사이트가 보내는 형식(expected_role 포함)으로 abcd 로그인을 시도합니다."""
    return client.post(
        "/api/v1/auth/login",
        json={"loginId": "abcd", "password": password, "expectedRole": role},
        headers=site,
    )


def test_seed_then_both_sites_accept_abcd() -> None:
    """시연 계정 생성 후 시민·담당자 사이트가 같은 아이디/비밀번호로 각자 역할로 로그인된다."""
    app = _app()
    result = app.test_cli_runner().invoke(args=["seed-demo-accounts"])
    assert result.exit_code == 0, result.output
    assert "abcd" in result.output and "demo-pass-1" not in result.output

    citizen = app.test_client()
    assert _login(citizen, CITIZEN, "citizen").status_code == 200
    me = citizen.get("/api/v1/auth/me", headers=CITIZEN).get_json()
    assert me["role"] == "citizen" and me["authMode"] == "password"

    staff = app.test_client()
    assert _login(staff, STAFF, "staff").status_code == 200
    me = staff.get("/api/v1/auth/me", headers=STAFF).get_json()
    assert me["role"] == "staff" and me["department"] is None


def test_wrong_password_and_idempotent_seed() -> None:
    """틀린 비밀번호는 401이고, 시연 계정 생성을 반복해도 계정은 둘뿐이다."""
    app = _app()
    runner = app.test_cli_runner()
    assert "created" in runner.invoke(args=["seed-demo-accounts"]).output
    again = runner.invoke(args=["seed-demo-accounts"])
    assert (
        again.exit_code == 0
        and "created" not in again.output
        and "updated" in again.output
    )
    assert _login(app.test_client(), STAFF, "staff", "9999").status_code == 401
    listing = runner.invoke(args=["list-users"]).output
    assert listing.count("abcd") == 2


def test_not_available_before_seed_and_no_alias_registration() -> None:
    """생성 전에는 로그인되지 않고, 일반 가입으로 내부 아이디(@)를 선점할 수 없다."""
    app = _app()
    assert _login(app.test_client(), STAFF, "staff").status_code == 401
    reg = app.test_client().post(
        "/api/v1/auth/register",
        json={"loginId": "abcd@staff", "password": "123456", "displayName": "침입"},
        headers=CITIZEN,
    )
    assert reg.status_code in (400, 422)


def test_citizen_cannot_use_staff_site_with_plain_citizen_id() -> None:
    """같은 abcd라도 담당자 사이트는 담당자 계정으로만 로그인되며 시민 계정으로는 열리지 않는다."""
    app = _app()
    app.test_cli_runner().invoke(args=["seed-demo-accounts"])
    # 담당자 내부 계정을 비활성화하면 담당자 사이트는 막히고 시민 로그인은 영향이 없다.
    assert (
        app.test_cli_runner()
        .invoke(args=["deactivate-user", "--login-id", "abcd@staff"])
        .exit_code
        == 0
    )
    client = app.test_client()
    blocked = _login(client, STAFF, "staff")
    assert blocked.status_code in (401, 403)
    assert _login(app.test_client(), CITIZEN, "citizen").status_code == 200
