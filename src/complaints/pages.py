"""시민·담당자 정적 화면과 API 문서 진입 경로를 제공합니다."""

from pathlib import Path
from flask import Blueprint, Response, request, send_from_directory
from src.complaints.config import ROOT
from src.complaints.errors import AppError
from src.complaints.http import has_staff_session
from src.complaints.swagger_page import render_swagger_html

web = Blueprint("web", __name__)


@web.route("/")
def ui_index() -> Response:
    """시민 사이트 진입 화면을 제공합니다.

    Returns:
        `ui/index.html`(시민 전용 화면)입니다.
    """
    return send_from_directory(ROOT / "ui", "index.html")


@web.route("/staff")
def ui_staff_redirect() -> Response:
    """끝 슬래시 없는 담당자 주소를 `/staff/`로 보냅니다.

    Returns:
        `/staff/`로 가는 308 응답입니다.
    """
    return Response(status=308, headers={"Location": "/staff/"})


@web.route("/staff/")
def ui_staff_index() -> Response:
    """담당자 사이트 진입 화면을 제공합니다.

    Returns:
        `ui/staff.html`(담당자 전용 화면)입니다.
    """
    return send_from_directory(ROOT / "ui", "staff.html")


@web.route("/lab")
def ui_lab_redirect() -> Response:
    """끝 슬래시 없는 응대 검사기 주소를 `/lab/`로 보냅니다.

    Returns:
        `/lab/`로 가는 308 응답입니다.
    """
    return Response(status=308, headers={"Location": "/lab/"})


@web.route("/lab/")
def ui_lab_index() -> Response:
    """응대 검사기 단독 페이지를 제공합니다.

    시민·담당자 사이트에서는 연결하지 않으며 주소로만 들어갑니다. 담당자로 로그인하지
    않았으면 담당자 로그인 화면(`/staff/`)으로 보냅니다. 검사기 API(`/api/v1/assist*`)도
    담당자 세션이 필요하며 계정별 실행 횟수가 제한됩니다. 민원은 저장하지 않습니다.

    Returns:
        `ui/lab.html`(검사기 전용 화면) 또는 `/staff/`로 가는 302 응답입니다.
    """
    if not has_staff_session():
        return Response(status=302, headers={"Location": "/staff/"})
    return send_from_directory(ROOT / "ui", "lab.html")


@web.route("/src/<path:filename>")
def ui_source(filename: str) -> Response:
    """서버 소스 대신 UI 정적 자산만 제공합니다.

    Args:
        filename: ui/src 아래의 상대 자산 경로입니다.

    Returns:
        허용한 JavaScript·CSS 파일입니다.
    """
    if Path(filename).suffix not in (".js", ".css"):
        raise AppError(404, "not_found", "파일을 찾을 수 없습니다.")
    return send_from_directory(ROOT / "ui" / "src", filename)


@web.route("/favicon.svg")
def favicon() -> Response:
    """UI의 로컬 아이콘을 제공합니다.

    Returns:
        `ui/favicon.svg`입니다.
    """
    return send_from_directory(ROOT / "ui", "favicon.svg")


@web.route("/design/ui04")
def design_ui04() -> Response:
    """ui04 목업을 서버 어댑터 스크립트와 함께 제공합니다.

    목업 원본 파일은 읽기만 하며, 응답 HTML의 `<head>` 바로 뒤에 어댑터 스크립트를 넣습니다.
    어댑터는 목업의 가짜 서버 호출을 `/api/v1`로 바꿉니다.

    Returns:
        어댑터가 연결된 목업 HTML입니다.
    """
    html = (ROOT / "ui" / "minwon-toktok-ui04.html").read_text(encoding="utf-8")
    html = html.replace(
        "<head>", '<head>\n<script src="/design/ui04-adapter.js"></script>', 1
    )
    return Response(html, mimetype="text/html", headers={"Cache-Control": "no-cache"})


@web.route("/design/ui04-adapter.js")
def design_ui04_adapter() -> Response:
    """목업을 서버 API에 연결하는 어댑터 스크립트를 제공합니다.

    Returns:
        `ui/adapters/ui04-adapter.js`입니다.
    """
    return send_from_directory(
        ROOT / "ui" / "adapters", "ui04-adapter.js", mimetype="application/javascript"
    )


@web.route("/docs")
@web.route("/swagger")
def docs() -> Response:
    """청주톡톡 백엔드 API 전용 한국어 Swagger UI 포털을 제공합니다.

    쿼리 `?embed=1`을 전달하면 담당자 콘솔(`#/staff/api`) 내부 iframe용으로
    상단 포털 헤더를 숨긴 본문만 반환합니다.

    Returns:
        한국어 Swagger UI HTML 문서입니다.
    """
    html = render_swagger_html(embed=request.args.get("embed") == "1")
    return Response(html, mimetype="text/html")


@web.route("/openapi.json")
def specification() -> Response:
    """자동 생성 OpenAPI JSON의 진입 주소를 제공합니다.

    Returns:
        `/openapi/openapi.json`으로 보내는 302 응답입니다.
    """
    return Response(status=302, headers={"Location": "/openapi/openapi.json"})
