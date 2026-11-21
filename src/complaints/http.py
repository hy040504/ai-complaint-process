"""공통 JSON 응답·세션 인증·오류·응답 헤더를 처리합니다."""

from flask import Response, current_app, jsonify, request, session
from flask_openapi3.openapi import OpenAPI
from pydantic import BaseModel, ValidationError
from werkzeug.exceptions import HTTPException

from src.complaints.errors import AppError
from src.complaints.models import Actor, ErrorResponse
from src.complaints.sites import explicit_site, wrong_site_message


def set_session_actor(user: Actor) -> None:
    """로그인·본인확인 가입·시연 전환 시 서명 세션 쿠키를 안전하게 회전·저장합니다.

    Args:
        user: 인증이 완료된 사용자 `Actor` 모델입니다.
    """
    site = explicit_site()
    if site is not None and user.role != site:
        raise AppError(403, "wrong_site", wrong_site_message(site))
    session.clear()
    session["user_id"] = user.id
    session["role"] = user.role
    session["auth_mode"] = user.auth_mode


def actor() -> Actor:
    """세션에 저장된 사용자를 `users` 저장소와 대조해 반환하며 미인증 요청은 거부합니다.

    Returns:
        서버가 확인한 인증 사용자 또는 시연 사용자입니다.

    Raises:
        AppError: 유효한 세션이 없거나 계정이 비활성 상태이면 발생합니다.
    """
    site = explicit_site()
    session_role = session.get("role")
    if site is not None and session_role is not None and session_role != site:
        # 사이트별 쿠키가 분리되어 정상 흐름에서는 일어나지 않지만 방어적으로 거부합니다.
        raise AppError(401, "authentication_required", wrong_site_message(site))
    auth_service = current_app.extensions.get("auth_service")
    if auth_service is not None:
        return auth_service.resolve_session_actor(
            user_id=session.get("user_id"),
            role=session.get("role"),
            auth_mode=session.get("auth_mode"),
        )
    role = session.get("role")
    if role not in ("citizen", "staff"):
        raise AppError(
            401, "authentication_required", "먼저 시연 계정을 선택해 주세요."
        )
    return Actor(
        id="staff-demo" if role == "staff" else "citizen-demo",
        login_id="staff-demo" if role == "staff" else "citizen-demo",
        display_name="김담당" if role == "staff" else "시연 시민",
        role="staff" if role == "staff" else "citizen",
        auth_mode="demo",
        demo=True,
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
    """인증을 입력 검증보다 먼저 수행하고 다른 출처의 쓰기 및 본문 한도를 검사합니다."""
    if not request.path.startswith("/api/v1/"):
        return
    is_attachment_upload = (
        request.method == "POST"
        and request.path.startswith("/api/v1/complaints/")
        and request.path.endswith("/attachments")
    )
    if not is_attachment_upload:
        # 전역 한도(업로드용 6 MiB)가 아닌 64 KiB를 이 요청에 적용합니다. 헤더 검사만으로는
        # `Transfer-Encoding: chunked`(Content-Length 없음) 본문을 막지 못하므로, 본문을
        # 읽는 시점에도 Werkzeug가 같은 한도로 413을 내도록 요청별 한도를 함께 설정합니다.
        request.max_content_length = 64 * 1024
        if request.content_length is not None and request.content_length > 64 * 1024:
            raise AppError(
                413,
                "payload_too_large",
                "요청 본문이 허용 크기(64 KiB)를 초과했습니다.",
            )
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("Origin")
        if origin and origin.rstrip("/") != request.host_url.rstrip("/"):
            raise AppError(403, "origin_rejected", "같은 사이트에서 요청해 주세요.")
    if request.path not in (
        "/api/v1/health",
        "/api/v1/session",
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        "/api/v1/auth/register",
        "/api/v1/assist",
        "/api/v1/assist/fields",
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
    if response.mimetype == "text/event-stream":
        response.headers["Cache-Control"] = "no-cache, no-store"
    else:
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
