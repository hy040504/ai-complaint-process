"""시민·담당자 정적 화면과 API 문서 진입 경로를 제공합니다."""

from pathlib import Path
from flask import Blueprint, Response, send_from_directory
from src.complaints.config import ROOT
from src.complaints.errors import AppError

web = Blueprint("web", __name__)


@web.route("/")
def ui_index() -> Response:
    """동일 출처에서 시민·담당자 UI를 제공합니다.

    Returns:
        `ui/index.html`입니다.
    """
    return send_from_directory(ROOT / "ui", "index.html")


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
    """Swagger UI의 고정 진입 주소를 제공합니다.

    Returns:
        `/openapi/swagger`로 보내는 302 응답입니다.
    """
    return Response(status=302, headers={"Location": "/openapi/swagger"})


@web.route("/openapi.json")
def specification() -> Response:
    """자동 생성 OpenAPI JSON의 진입 주소를 제공합니다.

    Returns:
        `/openapi/openapi.json`으로 보내는 302 응답입니다.
    """
    return Response(status=302, headers={"Location": "/openapi/openapi.json"})
