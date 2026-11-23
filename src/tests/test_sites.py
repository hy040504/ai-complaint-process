"""시민·담당자 사이트 분리(주소·세션 쿠키·로그인 경계) 테스트입니다."""

from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

from src.app import create_app
from src.complaints.config import Settings
from src.complaints.sites import SITE_HEADER

CITIZEN_PW = os.environ.get("COMPLAINT_CITIZEN_INIT_PASSWORD", "cheongju-citizen-2026!")
STAFF_PW = os.environ.get("COMPLAINT_STAFF_INIT_PASSWORD", "cheongju-staff-2026!")
CITIZEN = {SITE_HEADER: "citizen"}
STAFF = {SITE_HEADER: "staff"}


def _app() -> Any:
    """메모리 저장소의 테스트용 앱을 만듭니다."""
    return create_app(
        Settings(secret_key="test-sites", backend="memory", testing=True),
        auto_start_ai=False,
    )


def _login(client: Any, site: dict[str, str], login_id: str, password: str) -> Any:
    """지정 사이트 헤더로 로그인합니다."""
    return client.post(
        "/api/v1/auth/login",
        json={"loginId": login_id, "password": password},
        headers=site,
    )


def test_site_pages_are_separate() -> None:
    """`/`는 시민, `/staff/`는 담당자 화면이며 `/staff`는 슬래시 주소로 보낸다."""
    client = _app().test_client()
    citizen = client.get("/")
    staff = client.get("/staff/")
    assert citizen.status_code == 200 and staff.status_code == 200
    assert b'data-site="citizen"' in citizen.data
    assert b'data-site="staff"' in staff.data
    assert b"staff.css" not in citizen.data and b"lab.css" not in citizen.data
    assert b"staff.css" in staff.data
    assert b"noindex" in staff.data
    redirect = client.get("/staff")
    assert redirect.status_code == 308
    assert redirect.headers["Location"] == "/staff/"


def test_sessions_are_isolated_per_site_in_one_browser() -> None:
    """같은 브라우저에서 시민·담당자로 동시에 로그인해도 서로 덮어쓰지 않는다."""
    client = _app().test_client()
    assert _login(client, CITIZEN, "citizen_01", CITIZEN_PW).status_code == 200
    assert _login(client, STAFF, "staff_admin", STAFF_PW).status_code == 200
    assert client.get_cookie("cj_citizen") is not None
    assert client.get_cookie("cj_staff") is not None

    assert (
        client.get("/api/v1/auth/me", headers=CITIZEN).get_json()["role"] == "citizen"
    )
    assert client.get("/api/v1/auth/me", headers=STAFF).get_json()["role"] == "staff"

    # 담당자 로그아웃이 시민 세션을 끊지 않는다.
    assert client.post("/api/v1/auth/logout", headers=STAFF).status_code == 204
    assert client.get("/api/v1/auth/me", headers=STAFF).status_code == 401
    assert (
        client.get("/api/v1/auth/me", headers=CITIZEN).get_json()["role"] == "citizen"
    )


def test_wrong_site_login_is_rejected() -> None:
    """담당자 계정은 시민 사이트에서, 민원인 계정은 담당자 사이트에서 로그인할 수 없다."""
    client = _app().test_client()
    staff_on_citizen = _login(client, CITIZEN, "staff_admin", STAFF_PW)
    assert staff_on_citizen.status_code == 403
    assert staff_on_citizen.get_json()["code"] == "role_mismatch"
    citizen_on_staff = _login(client, STAFF, "citizen_01", CITIZEN_PW)
    assert citizen_on_staff.status_code == 403
    assert (
        client.get_cookie("cj_citizen") is None
        and client.get_cookie("cj_staff") is None
    )

    # 담당자 사이트에서는 민원인 가입 자체가 막히고 계정도 만들어지지 않는다.
    login_id = f"site_{uuid4().hex[:8]}"
    payload = {
        "loginId": login_id,
        "password": "site-password-2026!",
        "displayName": "가입시도",
    }
    blocked = client.post("/api/v1/auth/register", json=payload, headers=STAFF)
    assert blocked.status_code == 403
    assert blocked.get_json()["code"] == "wrong_site"
    assert _login(client, CITIZEN, login_id, "site-password-2026!").status_code == 401
    assert (
        client.post("/api/v1/auth/register", json=payload, headers=CITIZEN).status_code
        == 201
    )


def test_demo_session_must_match_site() -> None:
    """시연 역할 선택도 사이트와 같은 역할만 허용한다."""
    client = _app().test_client()
    other = client.post("/api/v1/session", json={"role": "staff"}, headers=CITIZEN)
    assert other.status_code == 403
    assert other.get_json()["code"] in ("wrong_site", "demo_login_disabled")
    assert client.get_cookie("cj_citizen") is None


def test_site_hint_fallbacks_for_requests_without_header() -> None:
    """헤더를 붙일 수 없는 요청(이미지·링크)은 Referer·쿠키로 사이트를 판별한다."""
    client = _app().test_client()
    assert _login(client, STAFF, "staff_admin", STAFF_PW).status_code == 200
    assert _login(client, CITIZEN, "citizen_01", CITIZEN_PW).status_code == 200

    by_referer = client.get(
        "/api/v1/auth/me", headers={"Referer": "http://localhost/staff/"}
    )
    assert by_referer.get_json()["role"] == "staff"
    by_staff_path = client.get("/api/v1/staff/stats")
    assert by_staff_path.status_code == 200, "담당자 전용 경로는 담당자 세션을 쓴다"

    only_staff = _app().test_client()
    assert _login(only_staff, STAFF, "staff_admin", STAFF_PW).status_code == 200
    assert (
        only_staff.get("/api/v1/auth/me").get_json()["role"] == "staff"
    ), "쿠키가 하나뿐이면 그 사이트"


def test_proxied_requests_hide_dev_pages_but_local_keeps_them() -> None:
    """Cloudflare 경유(`CF-Ray`) 요청은 비로그인에게 Swagger·OpenAPI·목업이 404, 로컬은 그대로다."""
    client = _app().test_client()
    proxied = {"CF-Ray": "abc123-ICN"}
    for path in (
        "/docs",
        "/swagger",
        "/openapi.json",
        "/openapi/openapi.json",
        "/design/ui04",
    ):
        assert client.get(path, headers=proxied).status_code == 404, path
    assert client.get("/", headers=proxied).status_code == 200
    assert client.get("/staff/", headers=proxied).status_code == 200
    assert client.get("/api/v1/health", headers=proxied).status_code == 200
    assert client.get("/docs").status_code == 200, "로컬 접속은 문서를 볼 수 있다"


def test_proxied_api_docs_open_only_for_logged_in_staff() -> None:
    """공개 주소에서도 담당자 로그인 후에는 Swagger·OpenAPI가 열리고, 시민·목업은 계속 막힌다."""
    proxied = {"CF-Ray": "abc123-ICN"}
    staff = _app().test_client()
    assert _login(staff, STAFF, "staff_admin", STAFF_PW).status_code == 200
    for path in ("/swagger", "/openapi/openapi.json", "/docs"):
        assert staff.get(path, headers=proxied).status_code == 200, path
    assert (
        staff.get("/design/ui04", headers=proxied).status_code == 404
    ), "목업은 계속 숨김"

    citizen = _app().test_client()
    assert _login(citizen, CITIZEN, "citizen_01", CITIZEN_PW).status_code == 200
    assert (
        citizen.get("/swagger", headers=proxied).status_code == 404
    ), "시민은 열 수 없다"

    forged = _app().test_client()
    forged.set_cookie("cj_staff", "forged.value.sig")
    assert forged.get("/openapi/openapi.json", headers=proxied).status_code == 404


def test_lab_is_a_standalone_page_separate_from_the_staff_site() -> None:
    """응대 검사기는 `/lab/` 단독 페이지이고, 담당자 화면에는 검사기·역할 전환 띠가 없다."""
    client = _app().test_client()
    redirect = client.get("/lab")
    assert redirect.status_code == 308 and redirect.headers["Location"] == "/lab/"
    lab_html = client.get("/lab/").get_data(as_text=True)
    assert 'data-site="lab"' in lab_html and "/src/lab.css" in lab_html
    staff_html = client.get("/staff/").get_data(as_text=True)
    assert 'data-site="staff"' in staff_html and "/src/lab.css" not in staff_html
    assert client.get("/lab/", headers={"CF-Ray": "abc123-ICN"}).status_code == 200
    # 검사기 API는 로그인 없이 쓰는 기존 규칙을 유지한다.
    assert client.get("/api/v1/assist/examples").status_code == 200


def test_https_requests_get_secure_cookie_and_hsts() -> None:
    """HTTPS(프록시의 X-Forwarded-Proto) 요청만 Secure 쿠키·HSTS를 받는다."""
    app = _app()
    https = app.test_client()
    resp = https.post(
        "/api/v1/auth/login",
        json={"loginId": "staff_admin", "password": STAFF_PW},
        headers={**STAFF, "X-Forwarded-Proto": "https"},
    )
    assert resp.status_code == 200
    set_cookie = "; ".join(resp.headers.getlist("Set-Cookie"))
    assert (
        "cj_staff=" in set_cookie
        and "Secure" in set_cookie
        and "HttpOnly" in set_cookie
    )
    assert "SameSite=Strict" in set_cookie
    assert "max-age=31536000" in resp.headers["Strict-Transport-Security"]

    http = app.test_client()
    plain = _login(http, STAFF, "staff_admin", STAFF_PW)
    assert plain.status_code == 200
    assert "Secure" not in "; ".join(plain.headers.getlist("Set-Cookie"))
    assert "Strict-Transport-Security" not in plain.headers
    assert plain.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert plain.headers["Referrer-Policy"] == "same-origin"


def test_citizen_session_cannot_use_staff_api() -> None:
    """시민 세션으로는 담당자 API가 거부된다."""
    client = _app().test_client()
    assert _login(client, CITIZEN, "citizen_01", CITIZEN_PW).status_code == 200
    response = client.get("/api/v1/staff/complaints/export.csv", headers=CITIZEN)
    assert response.status_code in (401, 403)
