"""공통 JSON 응답·세션 인증·오류·응답 헤더를 처리합니다."""

from flask import Response, current_app, jsonify, request, session
from flask_openapi3.openapi import OpenAPI
from pydantic import BaseModel, ValidationError
from werkzeug.exceptions import HTTPException

from src.errors import AppError
from src.models import Actor, ErrorResponse


def actor() -> Actor:
    """세션에 저장된 사용자만 반환하며 미인증 요청은 거부합니다.

    Returns:
        서버가 확인한 시연 사용자입니다.

    Raises:
        AppError: 유효한 세션이 없으면 발생합니다.
    """
    role = session.get("role")
    if role not in ("citizen", "staff"):
        raise AppError(
            401, "authentication_required", "먼저 시연 계정을 선택해 주세요."
        )
    return Actor(
        id="staff-demo" if role == "staff" else "citizen-demo",
        role="staff" if role == "staff" else "citizen",
    )


def reply(model: BaseModel, status: int = 200) -> Response:
    """검증된 모델만 camelCase JSON 응답으로 직렬화합니다.

    Args:
        model: 응답 계약을 만족하는 모델입니다.
        status: HTTP 상태 코드입니다.

    Returns:
        JSON 형식의 Flask 응답입니다.
    """
    response = jsonify(model.model_dump(mode="json", by_alias=True))
    response.status_code = status
    return response


def validation_error(error: ValidationError) -> Response:
    """입력 원문을 반사하지 않고 잘못된 필드 위치만 안내합니다.

    Args:
        error: Pydantic이 수집한 입력 오류입니다.

    Returns:
        동일한 오류 계약을 따르는 422 응답입니다.
    """
    fields = ", ".join(
        ".".join(str(part) for part in entry["loc"])
        for entry in error.errors(include_input=False)
    )
    return reply(
        ErrorResponse(
            code="validation_error",
            message="입력 형식·길이·필수 항목을 확인해 주세요: " + fields,
        ),
        422,
    )


def protect_api() -> None:
    """인증을 입력 검증보다 먼저 수행하고 다른 출처의 쓰기를 거부합니다."""
    if not request.path.startswith("/api/v1/"):
        return
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("Origin")
        if origin and origin.rstrip("/") != request.host_url.rstrip("/"):
            raise AppError(403, "origin_rejected", "같은 사이트에서 요청해 주세요.")
    if request.path not in (
        "/api/v1/health",
        "/api/v1/session",
        "/api/v1/assist",
        "/api/v1/assist/examples",
        "/api/v1/assist/stream",
    ):
        actor()
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.is_json:
        request.get_json()


def handle_app_error(error: AppError) -> Response:
    """업무 오류를 공통 JSON으로 응답합니다.

    Args:
        error: 권한·상태·저장 충돌 오류입니다.

    Returns:
        명시한 HTTP 상태의 오류 응답입니다.
    """
    return reply(ErrorResponse(code=error.code, message=error.message), error.status)


def handle_http_error(error: HTTPException) -> Response:
    """잘못된 JSON·경로·크기 제한도 HTML 대신 JSON으로 반환합니다.

    Args:
        error: Flask 또는 Werkzeug의 HTTP 오류입니다.

    Returns:
        본문 입력을 노출하지 않는 공통 오류 응답입니다.
    """
    return reply(
        ErrorResponse(
            code="http_error",
            message="요청 경로·메서드·JSON 형식 또는 본문 크기를 확인해 주세요.",
        ),
        error.code or 500,
    )


def handle_unexpected(error: Exception) -> Response:
    """내부 오류의 비밀 값과 SQL을 응답에 포함하지 않습니다.

    Args:
        error: 처리되지 않은 내부 예외입니다.

    Returns:
        민원 재등록을 유도하지 않는 500 안내입니다.
    """
    current_app.logger.error("업무 요청 내부 오류: %s", type(error).__name__)
    return reply(
        ErrorResponse(
            code="internal_error",
            message="요청 처리 중 오류가 발생했습니다. 입력 내용을 보관한 뒤 다시 확인해 주세요.",
        ),
        500,
    )


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


def register_http(app: OpenAPI) -> None:
    """공통 요청·응답 규칙을 Flask 앱에 등록합니다.

    Args:
        app: 공통 처리를 연결할 애플리케이션입니다.
    """
    app.before_request(protect_api)
    app.after_request(response_headers)
    app.register_error_handler(AppError, handle_app_error)
    app.register_error_handler(HTTPException, handle_http_error)
    app.register_error_handler(Exception, handle_unexpected)
