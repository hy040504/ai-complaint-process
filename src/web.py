"""시민·담당자 정적 화면과 API 문서 진입 경로를 제공합니다."""

from pathlib import Path
from flask import Blueprint, Response, send_from_directory
from src.config import ROOT
from src.errors import AppError

web = Blueprint("web", __name__)


@web.route("/")
def ui_index() -> Response:
    """동일 출처에서 시민·담당자 UI를 제공합니다."""
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
    """UI의 로컬 아이콘을 제공합니다."""
    return send_from_directory(ROOT / "ui", "favicon.svg")


@web.route("/docs")
@web.route("/swagger")
def docs() -> Response:
    """Swagger UI의 고정 진입 주소를 제공합니다."""
    return Response(status=302, headers={"Location": "/openapi/swagger"})


@web.route("/openapi.json")
def specification() -> Response:
    """자동 생성 OpenAPI JSON의 진입 주소를 제공합니다."""
    return Response(status=302, headers={"Location": "/openapi/openapi.json"})
