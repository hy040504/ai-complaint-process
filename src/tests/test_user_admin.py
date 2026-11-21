"""운영자용 계정 관리 CLI(담당자 생성·비밀번호 재설정·비활성화) 테스트입니다."""

from __future__ import annotations

from typing import Any

from src.app import create_app
from src.complaints.config import Settings
from src.complaints.sites import SITE_HEADER

STAFF = {SITE_HEADER: "staff"}
ENV = "COMPLAINT_NEW_PASSWORD"


def _app() -> Any:
    """메모리 저장소의 테스트용 앱을 만듭니다."""
    return create_app(
        Settings(secret_key="test-user-admin", backend="memory", testing=True),
        auto_start_ai=False,
    )


def _login(client: Any, login_id: str, password: str) -> int:
    """담당자 사이트로 로그인하고 상태 코드를 반환합니다."""
    return int(
        client.post(
            "/api/v1/auth/login",
            json={"loginId": login_id, "password": password},
            headers=STAFF,
        ).status_code
    )


def _run(app: Any, args: list[str], password: str | None = None) -> Any:
    """Flask CLI 명령을 실행합니다."""
    return app.test_cli_runner().invoke(
        args=args, env={ENV: password} if password is not None else None
    )


def test_create_staff_then_login_and_scope() -> None:
    """생성한 담당자는 담당자 사이트로 로그인하고 지정한 부서 범위를 가진다."""
    app = _app()
    result = _run(
        app,
        [
            "create-staff",
            "--login-id",
            "staff_new",
            "--name",
            "새 담당자",
            "--department",
            "서원구 건설과",
        ],
        "very-strong-pw-1",
    )
    assert result.exit_code == 0, result.output
    assert "staff_new" in result.output
    assert "very-strong-pw-1" not in result.output, "비밀번호를 출력하지 않는다"

    client = app.test_client()
    assert _login(client, "staff_new", "wrong-password") == 401
    assert _login(client, "staff_new", "very-strong-pw-1") == 200
    me = client.get("/api/v1/auth/me", headers=STAFF).get_json()
    assert me["role"] == "staff" and me["department"] == "서원구 건설과"


def test_create_staff_rejects_bad_input() -> None:
    """약한 비밀번호·없는 부서·중복·잘못된 아이디를 거부한다."""
    app = _app()
    weak = _run(
        app, ["create-staff", "--login-id", "staff_a", "--name", "담당자"], "short"
    )
    assert weak.exit_code != 0 and "8자" in weak.output

    unknown = _run(
        app,
        [
            "create-staff",
            "--login-id",
            "staff_b",
            "--name",
            "담당자",
            "--department",
            "없는부서과",
        ],
        "very-strong-pw-1",
    )
    assert unknown.exit_code != 0 and "부서" in unknown.output

    bad_id = _run(
        app,
        ["create-staff", "--login-id", "a b", "--name", "담당자"],
        "very-strong-pw-1",
    )
    assert bad_id.exit_code != 0

    assert (
        _run(
            app,
            ["create-staff", "--login-id", "staff_c", "--name", "담당자"],
            "very-strong-pw-1",
        ).exit_code
        == 0
    )
    dup = _run(
        app,
        ["create-staff", "--login-id", "STAFF_C", "--name", "담당자"],
        "very-strong-pw-1",
    )
    assert dup.exit_code != 0 and "이미 사용" in dup.output


def test_reset_password_and_deactivate() -> None:
    """비밀번호 재설정은 옛 비밀번호를 무효화하고 비활성 계정은 로그인과 세션이 막힌다."""
    app = _app()
    assert (
        _run(
            app,
            ["create-staff", "--login-id", "staff_r", "--name", "담당자"],
            "old-password-1",
        ).exit_code
        == 0
    )
    client = app.test_client()
    assert _login(client, "staff_r", "old-password-1") == 200

    assert (
        _run(
            app, ["reset-password", "--login-id", "staff_r"], "new-password-2"
        ).exit_code
        == 0
    )
    fresh = app.test_client()
    assert _login(fresh, "staff_r", "old-password-1") == 401
    assert _login(fresh, "staff_r", "new-password-2") == 200

    assert _run(app, ["deactivate-user", "--login-id", "staff_r"]).exit_code == 0
    assert (
        client.get("/api/v1/auth/me", headers=STAFF).status_code == 401
    ), "기존 세션도 거부"
    assert _login(app.test_client(), "staff_r", "new-password-2") == 401

    assert _run(app, ["activate-user", "--login-id", "staff_r"]).exit_code == 0
    assert _login(app.test_client(), "staff_r", "new-password-2") == 200


def test_cannot_modify_demo_or_missing_users_and_list_hides_hashes() -> None:
    """시연·없는 계정은 변경할 수 없고 목록은 해시와 시연 계정을 숨긴다."""
    app = _app()
    assert (
        _run(
            app, ["reset-password", "--login-id", "staff-demo"], "new-password-2"
        ).exit_code
        != 0
    )
    assert _run(app, ["deactivate-user", "--login-id", "nobody"]).exit_code != 0
    listing = _run(app, ["list-users"])
    assert listing.exit_code == 0
    assert "staff_admin" in listing.output
    assert "staff-demo" not in listing.output and "scrypt" not in listing.output
