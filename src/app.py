"""Flask 앱 생성·동일 출처 UI·Swagger·공통 오류 경계를 구성합니다."""

from pathlib import Path

import click
from flask import Response, request, send_from_directory
from flask_openapi3.models.info import Info
from flask_openapi3.openapi import OpenAPI
from pydantic import ValidationError
from werkzeug.exceptions import HTTPException

from src.api import actor, create_api, reply
from src.config import ROOT, Settings
from src.errors import AppError
from src.models import ErrorResponse
from src.repository import SQLiteRepository
from src.seed import seed_demo
from src.service import ComplaintService


def validation_error(error: ValidationError) -> Response:
    """입력 원문을 반사하지 않고 잘못된 필드 위치만 안내합니다.

    Args:
        error: Pydantic이 수집한 입력 오류입니다.

    Returns:
        동일한 오류 계약을 따르는 422 응답입니다.
    """
    fields = ", ".join(".".join(str(part) for part in entry["loc"]) for entry in error.errors(include_input=False))
    return reply(ErrorResponse(code="validation_error", message="입력 형식·길이·필수 항목을 확인해 주세요: " + fields), 422)


def create_app(settings: Settings | None = None) -> OpenAPI:
    """설정과 저장소를 주입하여 독립적인 Flask 앱을 만듭니다.

    Args:
        settings: 생략하면 환경 변수와 로컬 기본 경로를 읽습니다.

    Returns:
        UI와 API 및 Swagger를 함께 제공하는 Flask 앱입니다.
    """
    config = settings or Settings.from_env()
    app = OpenAPI(__name__, info=Info(title="청주톡톡 민원 업무 API", version="0.2.0", description="로컬 시연 업무 서버입니다. 먼저 시연 세션에서 역할을 선택하세요. 민원·답변은 DB에 저장되며 실제 AI·공식 접수·행정 이관은 미연동입니다."), security_schemes={}, static_folder=None, validation_error_model=ErrorResponse, validation_error_callback=validation_error, validation_error_status=422)
    app.config.update(SECRET_KEY=config.secret_key, TESTING=config.testing, DEMO_LOGIN=config.demo_login, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict", MAX_CONTENT_LENGTH=64*1024, SWAGGER_CONFIG={"docExpansion": "none", "validatorUrl": None, "persistAuthorization": False})
    repository = SQLiteRepository(config.database)
    service = ComplaintService(repository)
    app.extensions["complaint_service"] = service
    app.register_api(create_api(service))

    @app.before_request
    def protect_api() -> None:
        """인증을 입력 검증보다 먼저 수행하고 다른 출처의 쓰기를 거부합니다."""
        if not request.path.startswith("/api/v1/"):
            return
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("Origin")
            if origin and origin.rstrip("/") != request.host_url.rstrip("/"):
                raise AppError(403, "origin_rejected", "같은 사이트에서 요청해 주세요.")
        if request.path not in ("/api/v1/health", "/api/v1/session"):
            actor()
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.is_json:
            request.get_json()

    @app.errorhandler(AppError)
    def handle_app_error(error: AppError) -> Response:
        """업무 오류를 공통 JSON으로 응답합니다.

        Args:
            error: 권한·상태·저장 충돌 오류입니다.

        Returns:
            명시한 HTTP 상태의 오류 응답입니다.
        """
        return reply(ErrorResponse(code=error.code, message=error.message), error.status)

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException) -> Response:
        """잘못된 JSON·경로·크기 제한도 HTML 대신 JSON으로 반환합니다.

        Args:
            error: Flask 또는 Werkzeug의 HTTP 오류입니다.

        Returns:
            본문 입력을 노출하지 않는 공통 오류 응답입니다.
        """
        return reply(ErrorResponse(code="http_error", message="요청 경로·메서드·JSON 형식 또는 본문 크기를 확인해 주세요."), error.code or 500)

    @app.errorhandler(Exception)
    def handle_unexpected(error: Exception) -> Response:
        """내부 오류의 비밀 값과 SQL을 응답에 포함하지 않습니다.

        Args:
            error: 처리되지 않은 내부 예외입니다.

        Returns:
            민원 재등록을 유도하지 않는 500 안내입니다.
        """
        app.logger.error("업무 요청 내부 오류: %s", type(error).__name__)
        return reply(ErrorResponse(code="internal_error", message="요청 처리 중 오류가 발생했습니다. 입력 내용을 보관한 뒤 다시 확인해 주세요."), 500)

    @app.after_request
    def response_headers(response: Response) -> Response:
        """세션별 업무 응답이 공유 캐시에 남지 않도록 설정합니다.

        Args:
            response: 처리된 Flask 응답입니다.

        Returns:
            캐시와 콘텐츠 해석 제한을 추가한 응답입니다.
        """
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.route("/")
    def ui_index() -> Response:
        """동일 출처에서 시민·담당자 UI를 제공합니다."""
        return send_from_directory(ROOT / "ui", "index.html")

    @app.route("/src/<path:filename>")
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

    @app.route("/favicon.svg")
    def favicon() -> Response:
        """UI의 로컬 아이콘을 제공합니다."""
        return send_from_directory(ROOT / "ui", "favicon.svg")

    @app.route("/docs")
    @app.route("/swagger")
    def docs() -> Response:
        """Swagger UI의 고정 진입 주소를 제공합니다."""
        return Response(status=302, headers={"Location": "/openapi/swagger"})

    @app.route("/openapi.json")
    def specification() -> Response:
        """자동 생성 OpenAPI JSON의 진입 주소를 제공합니다."""
        return Response(status=302, headers={"Location": "/openapi/openapi.json"})

    @app.cli.command("seed-demo")
    def seed_command() -> None:
        """사용자가 요청했을 때만 비어 있는 업무 DB에 합성 자료를 넣습니다."""
        click.echo(f"합성 시연 민원 {seed_demo(repository)}건 생성")

    return app
