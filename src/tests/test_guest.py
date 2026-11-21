"""로그인 없는 게스트 세션·접수·계정 연결·남용 방지 테스트입니다."""

from __future__ import annotations

import io
import os
from typing import Any
from uuid import uuid4

from src.app import create_app
from src.complaints.auth import GUEST_COMPLAINT_LIMIT
from src.complaints.config import Settings
from src.complaints.errors import AppError
from src.complaints.sites import SITE_HEADER

CITIZEN = {SITE_HEADER: "citizen"}
STAFF = {SITE_HEADER: "staff"}
CITIZEN_PW = os.environ.get("COMPLAINT_CITIZEN_INIT_PASSWORD", "cheongju-citizen-2026!")
STAFF_PW = os.environ.get("COMPLAINT_STAFF_INIT_PASSWORD", "cheongju-staff-2026!")
PAYLOAD = {
    "title": "게스트로 접수하는 가로등 고장",
    "body": "로그인 없이 접수합니다. 사창동 사거리 가로등이 며칠째 꺼져 있습니다.",
    "district": "서원구",
    "category": "도로·교통",
    "visibility": "public",
}


def _app() -> Any:
    """메모리 저장소의 테스트용 앱을 만듭니다."""
    return create_app(
        Settings(secret_key="test-guest", backend="memory", testing=True),
        auto_start_ai=False,
    )


def _start(client: Any) -> Any:
    """시민 사이트로 게스트 세션을 시작합니다."""
    return client.post("/api/v1/auth/guest", headers=CITIZEN)


def _submit(client: Any, **override: Any) -> Any:
    """게스트로 민원을 접수합니다."""
    return client.post(
        "/api/v1/complaints", json={**PAYLOAD, **override}, headers=CITIZEN
    )


def test_guest_session_start_is_idempotent_and_citizen_only() -> None:
    """게스트는 시민 사이트에서만 시작되고 같은 세션에서는 새로 만들지 않는다."""
    app = _app()
    client = app.test_client()
    first = _start(client)
    assert first.status_code == 200
    actor = first.get_json()
    assert actor["guest"] is True and actor["role"] == "citizen"
    assert actor["authMode"] == "guest" and actor["demo"] is False
    assert actor["id"].startswith("guest-") and actor["displayName"] == "게스트"
    assert client.get_cookie("cj_citizen") is not None
    assert _start(client).get_json()["id"] == actor["id"], "같은 세션은 같은 게스트"
    assert client.get("/api/v1/auth/me", headers=CITIZEN).get_json()["guest"] is True

    staff_side = app.test_client()
    blocked = staff_side.post("/api/v1/auth/guest", headers=STAFF)
    assert blocked.status_code == 403
    assert blocked.get_json()["code"] == "wrong_site"
    assert staff_side.get_cookie("cj_staff") is None


def test_guest_complaint_is_private_visible_to_staff_and_isolated() -> None:
    """게스트 민원은 공개를 요청해도 비공개로 저장되고 다른 방문자에게는 보이지 않는다."""
    app = _app()
    guest = app.test_client()
    _start(guest)
    created = _submit(guest)
    assert created.status_code == 201
    body = created.get_json()
    assert body["visibility"] == "private", "게스트 접수는 비공개로 강제"
    cid = body["id"]
    assert guest.get(f"/api/v1/complaints/{cid}", headers=CITIZEN).status_code == 200

    other = app.test_client()
    _start(other)
    assert other.get(f"/api/v1/complaints/{cid}", headers=CITIZEN).status_code == 404

    staff = app.test_client()
    login = staff.post(
        "/api/v1/auth/login",
        json={"loginId": "staff_admin", "password": STAFF_PW},
        headers=STAFF,
    )
    assert login.status_code == 200
    seen = staff.get(f"/api/v1/complaints/{cid}", headers=STAFF)
    assert seen.status_code == 200 and seen.get_json()["visibility"] == "private"


def test_guest_without_session_cannot_submit_and_cannot_use_staff_api() -> None:
    """세션이 없으면 접수할 수 없고 게스트는 담당자 API를 쓸 수 없다."""
    app = _app()
    anonymous = app.test_client()
    assert _submit(anonymous).status_code == 401
    guest = app.test_client()
    _start(guest)
    assert guest.get("/api/v1/staff/stats", headers=CITIZEN).status_code in (401, 403)
    sessions = guest.get("/api/v1/citizen/chat/sessions", headers=CITIZEN)
    assert sessions.status_code == 200
    assert sessions.get_json()["persisted"] is False, "게스트 대화는 저장하지 않는다"


def test_guest_complaint_limit_and_attachment() -> None:
    """게스트 한도를 넘기면 429이고 본인 민원에는 첨부할 수 있다."""
    app = _app()
    guest = app.test_client()
    _start(guest)
    first = _submit(guest)
    assert first.status_code == 201
    pdf = b"%PDF-1.4\n1 0 obj <<>> endobj\ntrailer <<>>\n%%EOF\n"
    upload = guest.post(
        f"/api/v1/complaints/{first.get_json()['id']}/attachments",
        data={"file": (io.BytesIO(pdf), "증빙.pdf")},
        content_type="multipart/form-data",
        headers=CITIZEN,
    )
    assert upload.status_code == 201
    for _ in range(GUEST_COMPLAINT_LIMIT - 1):
        assert _submit(guest).status_code == 201
    over = _submit(guest)
    assert over.status_code == 429 and over.get_json()["code"] == "guest_limit"


def test_guest_complaints_move_to_account_on_register_and_login() -> None:
    """게스트 민원은 가입하거나 로그인하면 그 계정으로 옮겨진다."""
    app = _app()
    # 가입으로 연결
    visitor = app.test_client()
    _start(visitor)
    cid = _submit(visitor).get_json()["id"]
    login_id = f"claim_{uuid4().hex[:8]}"
    registered = visitor.post(
        "/api/v1/auth/register",
        json={
            "loginId": login_id,
            "password": "claim-password-2026!",
            "displayName": "연결시민",
        },
        headers=CITIZEN,
    )
    assert registered.status_code == 201
    new_id = registered.get_json()["id"]
    assert registered.get_json()["guest"] is False
    mine = visitor.get(f"/api/v1/complaints/{cid}", headers=CITIZEN)
    assert mine.status_code == 200 and mine.get_json()["owner"] == new_id
    assert "게스트 민원을 계정에 연결" in str(mine.get_json()["history"])

    # 기존 계정 로그인으로 연결
    returning = app.test_client()
    _start(returning)
    cid2 = _submit(returning).get_json()["id"]
    login = returning.post(
        "/api/v1/auth/login",
        json={"loginId": "citizen_01", "password": CITIZEN_PW},
        headers=CITIZEN,
    )
    assert login.status_code == 200
    assert (
        returning.get(f"/api/v1/complaints/{cid2}", headers=CITIZEN).get_json()["owner"]
        == login.get_json()["id"]
    )

    # 옮겨진 뒤 새 게스트는 접근할 수 없다
    stranger = app.test_client()
    _start(stranger)
    assert stranger.get(f"/api/v1/complaints/{cid}", headers=CITIZEN).status_code == 404


def test_guest_session_creation_is_rate_limited_per_ip() -> None:
    """같은 IP의 게스트 세션 발급은 시간당 10회로 제한한다."""
    app = _app()
    codes = [_start(app.test_client()).status_code for _ in range(11)]
    assert codes[:10] == [200] * 10
    assert codes[10] == 429


def test_forged_guest_identity_is_rejected() -> None:
    """형식이 올바르지 않은 게스트 ID나 역할 불일치는 세션 복원에서 거부한다."""
    auth = _app().extensions["auth_service"]
    for user_id, role in (
        ("guest-xyz", "citizen"),
        (None, "citizen"),
        ("guest-" + "a" * 32, "staff"),
    ):
        try:
            auth.resolve_session_actor(user_id=user_id, role=role, auth_mode="guest")
        except AppError as error:
            assert error.status == 401
        else:
            raise AssertionError(f"거부되어야 합니다: {user_id}/{role}")
    ok = auth.resolve_session_actor(
        user_id="guest-" + "a" * 32, role="citizen", auth_mode="guest"
    )
    assert ok.guest is True
