"""시민 사이트(`/`)와 담당자 사이트(`/staff/`)의 요청 구분과 사이트별 세션 쿠키를 제공합니다.

두 사이트는 같은 Flask 프로세스(같은 SSE 이벤트 브로커)를 쓰되 로그인 세션은 완전히
분리합니다. 같은 브라우저에서 시민과 담당자로 동시에 로그인해도 서로의 세션을 덮어쓰지
않습니다.

사이트 판별 순서:
    1. 요청 헤더 `X-Cheongju-Site`(프론트의 모든 `fetch`가 붙입니다).
    2. 경로 `/api/v1/staff/*`(담당자 전용) · `/api/v1/citizen/*`(시민 전용).
    3. 같은 호스트 `Referer`의 경로가 `/staff` 이하이면 담당자
       (이미지·첨부 링크처럼 헤더를 붙일 수 없는 요청).
    4. 사이트 쿠키가 한쪽만 있고 레거시 쿠키가 없을 때 그 사이트.
    5. 위 어느 것도 없으면 `None`: 기존 단일 쿠키(`session`) 동작을 그대로 유지합니다
       (curl·테스트·목업 어댑터·Swagger 포털 호환).
"""

from typing import Literal
from urllib.parse import urlparse

from flask import Flask, request
from flask.sessions import SecureCookieSessionInterface

Site = Literal["citizen", "staff"]

SITE_HEADER = "X-Cheongju-Site"
COOKIE_NAMES: dict[str, str] = {"citizen": "cj_citizen", "staff": "cj_staff"}


def explicit_site() -> Site | None:
    """현재 요청이 어느 사이트에서 왔는지 명시적 단서로 판별합니다.

    Returns:
        `"citizen"`·`"staff"` 또는 단서가 없으면 `None`입니다.
    """
    header = (request.headers.get(SITE_HEADER) or "").strip().lower()
    if header in COOKIE_NAMES:
        return header  # type: ignore[return-value]
    has_site_cookie = any(name in request.cookies for name in COOKIE_NAMES.values())
    if "session" in request.cookies and not has_site_cookie:
        # 사이트 쿠키 없이 기존 단일 쿠키만 가진 클라이언트(curl·테스트·Swagger 포털)입니다.
        return None
    if request.path.startswith("/api/v1/staff/"):
        return "staff"
    if request.path.startswith("/api/v1/citizen/"):
        return "citizen"
    referer = request.headers.get("Referer")
    if referer:
        parsed = urlparse(referer)
        if parsed.netloc == request.host and (
            parsed.path == "/staff" or parsed.path.startswith("/staff/")
        ):
            return "staff"
    present = [site for site, name in COOKIE_NAMES.items() if name in request.cookies]
    if len(present) == 1 and "session" not in request.cookies:
        return present[0]  # type: ignore[return-value]
    return None


class SiteSessionInterface(SecureCookieSessionInterface):
    """사이트별로 다른 이름의 서명 쿠키를 쓰는 세션 인터페이스입니다."""

    def get_cookie_name(self, app: Flask) -> str:
        """요청 사이트에 맞는 세션 쿠키 이름을 반환합니다.

        Args:
            app: 현재 Flask 애플리케이션입니다.

        Returns:
            `cj_citizen`·`cj_staff` 또는 사이트 단서가 없으면 기본 `session`입니다.
        """
        site = explicit_site()
        if site is None:
            return str(app.config["SESSION_COOKIE_NAME"])
        return COOKIE_NAMES[site]


def wrong_site_message(site: Site) -> str:
    """사이트와 계정 유형이 맞지 않을 때 안내 문구를 만듭니다.

    Args:
        site: 로그인을 시도한 사이트입니다.

    Returns:
        올바른 사이트 주소를 알려 주는 문구입니다.
    """
    if site == "citizen":
        return "시민 사이트에서는 민원인 계정만 사용할 수 있습니다. 담당자는 /staff/ 에서 로그인해 주세요."
    return "담당자 사이트에서는 담당자 계정만 사용할 수 있습니다. 민원인은 시민 사이트(/)에서 로그인해 주세요."
