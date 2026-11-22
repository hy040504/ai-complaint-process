"""담당자의 게시판 공개 범위 조정과 게스트·작성자 수정 경계 테스트입니다."""

from __future__ import annotations

import os
from typing import Any

from src.app import create_app
from src.complaints.config import Settings
from src.complaints.sites import SITE_HEADER

CITIZEN = {SITE_HEADER: "citizen"}
STAFF = {SITE_HEADER: "staff"}
CITIZEN_PW = os.environ.get("COMPLAINT_CITIZEN_INIT_PASSWORD", "cheongju-citizen-2026!")
STAFF_PW = os.environ.get("COMPLAINT_STAFF_INIT_PASSWORD", "cheongju-staff-2026!")
PAYLOAD = {
    "title": "공개 범위 시험 민원",
    "body": "공개 범위 조정 기능을 확인하기 위한 시험 민원입니다. 사창동 사거리 가로등.",
    "district": "서원구",
    "category": "도로·교통",
    "visibility": "public",
}


def _app() -> Any:
    """메모리 저장소의 테스트용 앱을 만듭니다."""
    return create_app(
        Settings(secret_key="test-visibility", backend="memory", testing=True),
        auto_start_ai=False,
    )


def _staff(app: Any) -> Any:
    """담당자로 로그인한 클라이언트를 반환합니다."""
    client = app.test_client()
    res = client.post(
        "/api/v1/auth/login",
        json={"loginId": "staff_admin", "password": STAFF_PW},
        headers=STAFF,
    )
    assert res.status_code == 200
    return client


def _citizen(app: Any) -> Any:
    """로그인한 민원인 클라이언트를 반환합니다."""
    client = app.test_client()
    res = client.post(
        "/api/v1/auth/login",
        json={"loginId": "citizen_01", "password": CITIZEN_PW},
        headers=CITIZEN,
    )
    assert res.status_code == 200
    return client


def _guest(app: Any) -> Any:
    """게스트 세션을 시작한 클라이언트를 반환합니다."""
    client = app.test_client()
    assert client.post("/api/v1/auth/guest", headers=CITIZEN).status_code == 200
    return client


def _create(client: Any, **override: Any) -> dict[str, Any]:
    """민원을 접수하고 응답 본문을 반환합니다."""
    res = client.post(
        "/api/v1/complaints", json={**PAYLOAD, **override}, headers=CITIZEN
    )
    assert res.status_code == 201, res.get_json()
    body: dict[str, Any] = res.get_json()
    return body


def _set_visibility(
    staff: Any, cid: str, version: int, visibility: str, reason: str = "개인정보 포함"
) -> Any:
    """담당자 공개 범위 조정 API를 호출합니다."""
    return staff.put(
        f"/api/v1/complaints/{cid}/visibility",
        json={"version": version, "visibility": visibility, "reason": reason},
        headers=STAFF,
    )


def _update(client: Any, body: dict[str, Any], **override: Any) -> Any:
    """작성자 본인 수정 API를 호출합니다."""
    payload = {
        "title": body["title"],
        "body": body["body"],
        "district": body["district"],
        "category": body["category"],
        "visibility": body["visibility"],
        "version": body["version"],
        **override,
    }
    return client.put(f"/api/v1/complaints/{body['id']}", json=payload, headers=CITIZEN)


def test_guest_cannot_change_visibility_by_editing() -> None:
    """게스트가 수정으로 비공개를 요청해도 접수 때 정해진 공개 상태가 유지된다."""
    app = _app()
    guest = _guest(app)
    created = _create(guest)
    assert created["visibility"] == "public"
    res = _update(guest, created, visibility="private")
    assert res.status_code == 200, res.get_json()
    assert (
        res.get_json()["visibility"] == "public"
    ), "게스트는 수정으로 공개 범위를 못 바꾼다"


def test_staff_can_take_down_and_restore_public_complaint() -> None:
    """담당자는 사유와 함께 공개 민원을 내리고, 자신이 내린 것만 다시 공개한다."""
    app = _app()
    guest = _guest(app)
    created = _create(guest)
    cid, version = created["id"], created["version"]

    other = _guest(app)
    assert other.get(f"/api/v1/complaints/{cid}", headers=CITIZEN).status_code == 200

    staff = _staff(app)
    hidden = _set_visibility(staff, cid, version, "private")
    assert hidden.status_code == 200, hidden.get_json()
    assert hidden.get_json()["visibility"] == "private"
    history = [h["text"] for h in hidden.get_json()["history"]]
    assert any(
        t.startswith("게시판에서 내림") and "개인정보 포함" in t for t in history
    )

    # 다른 방문자에게서는 사라지고 작성자·담당자는 계속 본다
    assert other.get(f"/api/v1/complaints/{cid}", headers=CITIZEN).status_code == 404
    assert guest.get(f"/api/v1/complaints/{cid}", headers=CITIZEN).status_code == 200
    listed = other.get("/api/v1/complaints", headers=CITIZEN).get_json()
    rows = (
        listed
        if isinstance(listed, list)
        else listed.get("items", listed.get("complaints", []))
    )
    assert cid not in [r["id"] for r in rows]

    # 게스트 작성자가 수정해도 다시 공개되지 않는다
    fresh = guest.get(f"/api/v1/complaints/{cid}", headers=CITIZEN).get_json()
    edited = _update(guest, fresh, visibility="public")
    assert edited.status_code == 200
    assert edited.get_json()["visibility"] == "private"

    # 담당자가 내린 민원만 다시 공개할 수 있다
    latest = staff.get(f"/api/v1/complaints/{cid}", headers=STAFF).get_json()
    restored = _set_visibility(staff, cid, latest["version"], "public", "확인 후 복원")
    assert restored.status_code == 200, restored.get_json()
    assert restored.get_json()["visibility"] == "public"
    assert other.get(f"/api/v1/complaints/{cid}", headers=CITIZEN).status_code == 200


def test_logged_in_author_cannot_republish_taken_down_complaint() -> None:
    """로그인한 작성자도 담당자가 내린 민원을 수정으로 다시 공개할 수 없다."""
    app = _app()
    author = _citizen(app)
    created = _create(author)
    staff = _staff(app)
    assert (
        _set_visibility(staff, created["id"], created["version"], "private").status_code
        == 200
    )
    fresh = author.get(
        f"/api/v1/complaints/{created['id']}", headers=CITIZEN
    ).get_json()
    res = _update(author, fresh, visibility="public")
    assert res.status_code == 409
    assert res.get_json()["code"] == "hidden_by_staff"


def test_staff_cannot_publish_what_the_author_made_private() -> None:
    """작성자가 비공개로 정한 민원은 담당자가 공개로 돌릴 수 없고, 이미 비공개면 내림도 거부한다."""
    app = _app()
    author = _citizen(app)
    created = _create(author, visibility="private")
    staff = _staff(app)
    res = _set_visibility(staff, created["id"], created["version"], "public")
    assert res.status_code == 409
    assert res.get_json()["code"] == "not_hidden_by_staff"
    res = _set_visibility(staff, created["id"], created["version"], "private")
    assert res.status_code == 409
    assert res.get_json()["code"] == "already_private"


def test_visibility_requires_staff_and_reason() -> None:
    """민원인·게스트는 공개 범위 조정을 호출할 수 없고, 사유 없이는 요청이 거부된다."""
    app = _app()
    author = _citizen(app)
    created = _create(author)
    denied = _set_visibility(author, created["id"], created["version"], "private")
    assert denied.status_code in (401, 403)

    staff = _staff(app)
    empty = staff.put(
        f"/api/v1/complaints/{created['id']}/visibility",
        json={"version": created["version"], "visibility": "private", "reason": ""},
        headers=STAFF,
    )
    assert empty.status_code in (400, 422)
