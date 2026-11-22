"""설정 → 민원 저장소 → 서비스 → API·화면 순서로 Flask 앱을 구성합니다.

민원 CRUD는 `src.complaints`에 있고, 검사기 API는 같은 블루프린트에서
`src.assist`를 호출합니다.
"""

import os

import click
from flask_openapi3.models.info import Info
from flask_openapi3.openapi import OpenAPI
from werkzeug.middleware.proxy_fix import ProxyFix

from src.assist import iter_web_assist
from src.complaints.api import create_api
from src.complaints.attachments import (
    MAX_UPLOAD_REQUEST_BYTES,
    AttachmentStorage,
    DiskAttachmentStorage,
    MemoryAttachmentStorage,
)
from src.complaints.auth import AuthService
from src.complaints.config import ROOT, Settings
from src.complaints.demo_data import seed_public_demo
from src.complaints.errors import AppError
from src.complaints.http import register_http, validation_error
from src.complaints.models import ErrorResponse
from src.complaints.pages import web
from src.complaints.repository import MemoryRepository, PostgresRepository
from src.complaints.seed import seed_demo
from src.complaints.sites import SiteSessionInterface
from src.complaints.demo_accounts import ensure_demo_accounts
from src.complaints.user_admin import create_staff, reset_password, set_active
from src.complaints.service import AssistIterFn, ComplaintService


def create_app(
    settings: Settings | None = None,
    repository: MemoryRepository | PostgresRepository | None = None,
    *,
    assist_iter_fn: AssistIterFn | None = None,
    auto_start_ai: bool | None = None,
) -> OpenAPI:
    """설정과 저장소를 주입하여 독립적인 Flask 앱을 만듭니다.

    Args:
        settings: 생략하면 환경 변수와 PostgreSQL 기본 스키마를 읽습니다.
        repository: 생략하면 설정의 저장 백엔드를 만듭니다.
        assist_iter_fn: 테스트나 커스텀 연동 시 주입할 응대 스트림 함수입니다.
            생략하면 `testing=False`일 때 실제 `iter_web_assist`를 연결합니다.
        auto_start_ai: 민원 등록·수정 시 AI 분석을 자동 시작할지 여부입니다.
            생략하면 `assist_iter_fn` 또는 `not config.testing`을 따릅니다.

    Returns:
        UI와 API 및 Swagger를 함께 제공하는 Flask 앱입니다.
    """
    config = settings or Settings.from_env()
    app = OpenAPI(
        __name__,
        info=Info(
            title="청주톡톡 민원 업무 API",
            version="0.3.0",
            description="청주 민원 AI 완충지대 시연 업무 서버입니다. 민원·초안·게시와 RAG+LLM 분석이 연결되며 공식 접수·행정 이관은 미연동입니다.",
        ),
        security_schemes={},
        static_folder=None,
        validation_error_model=ErrorResponse,
        validation_error_callback=validation_error,
        validation_error_status=422,
    )
    app.config.update(
        SECRET_KEY=config.secret_key,
        TESTING=config.testing,
        DEMO_LOGIN=config.demo_login,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_SECURE=False,
        MAX_CONTENT_LENGTH=MAX_UPLOAD_REQUEST_BYTES,
        SWAGGER_CONFIG={
            "docExpansion": "none",
            "validatorUrl": None,
            "persistAuthorization": False,
        },
    )
    if repository is None:
        repository = (
            MemoryRepository()
            if config.backend == "memory"
            else PostgresRepository(config.conninfo, config.schema)
        )
    resolved_iter: AssistIterFn | None = (
        assist_iter_fn
        if assist_iter_fn is not None
        else (None if config.testing else iter_web_assist)
    )
    resolved_auto = (
        auto_start_ai if auto_start_ai is not None else (resolved_iter is not None)
    )
    attachment_storage: AttachmentStorage = (
        MemoryAttachmentStorage()
        if config.testing or config.backend == "memory"
        else DiskAttachmentStorage(
            config.upload_dir or (ROOT / ".web-data" / "uploads")
        )
    )
    service = ComplaintService(
        repository,
        iter_assist_fn=resolved_iter,
        auto_start_ai=resolved_auto,
        attachment_storage=attachment_storage,
    )
    auth_service = AuthService(repository)
    app.extensions["complaint_service"] = service
    app.extensions["auth_service"] = auth_service
    # Tailscale Serve 등 로컬 프록시의 X-Forwarded-Proto를 반영해 HTTPS Origin 검사를 통과시킵니다.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)  # type: ignore[method-assign]
    register_http(app)
    # 시민(/)·담당자(/staff/) 사이트가 서로 다른 세션 쿠키를 쓰도록 합니다.
    app.session_interface = SiteSessionInterface()
    app.register_api(create_api(service, auth_service))
    app.register_blueprint(web)

    @app.cli.command("seed-demo")
    def seed_command() -> None:
        """사용자가 요청했을 때만 비어 있는 업무 DB에 합성 자료를 넣습니다."""
        click.echo(f"합성 시연 민원 {seed_demo(repository)}건 생성")

    @app.cli.command("seed-public-demo")
    def seed_public_command() -> None:
        """공개 사례·자주 묻는 민원 JSON을 개인정보 마스킹 후 시연 민원으로 넣습니다."""
        click.echo(
            f"공개 데이터 기반 시연 민원 {seed_public_demo(repository, ROOT / 'rag' / 'origin')}건 생성"
        )

    @app.cli.command("seed-demo-accounts")
    def seed_demo_accounts_command() -> None:
        """두 사이트 공통 시연 로그인(abcd)을 만들거나 되돌립니다. 비밀번호는 환경변수로만 받습니다."""
        try:
            results = ensure_demo_accounts(repository)
        except AppError as error:
            raise click.ClickException(error.message) from error
        for login_id, outcome in results:
            click.echo(f"시연 계정 {outcome}: {login_id}")

    def read_new_password(env_name: str) -> str:
        """환경변수 또는 숨김 프롬프트에서 새 비밀번호를 받습니다.

        Args:
            env_name: 비밀번호를 담은 환경변수 이름입니다.

        Returns:
            비밀번호 원문입니다. 명령줄 인자로는 받지 않습니다.
        """
        value = os.environ.get(env_name, "")
        if value:
            return value
        return str(click.prompt("비밀번호", hide_input=True, confirmation_prompt=True))

    @app.cli.command("create-staff")
    @click.option(
        "--login-id", required=True, help="로그인 아이디(영문·숫자·_.- 3~32자)"
    )
    @click.option("--name", "display_name", required=True, help="이력에 표시할 이름")
    @click.option("--department", default="", help="소속 부서. 비우면 총괄 담당자")
    @click.option(
        "--password-env",
        default="COMPLAINT_NEW_PASSWORD",
        show_default=True,
        help="비밀번호를 담은 환경변수 이름. 없으면 숨김 프롬프트로 입력",
    )
    def create_staff_command(
        login_id: str, display_name: str, department: str, password_env: str
    ) -> None:
        """담당자 계정을 만듭니다."""
        try:
            user = create_staff(
                repository,
                login_id=login_id,
                display_name=display_name,
                department=department or None,
                password=read_new_password(password_env),
            )
        except AppError as error:
            raise click.ClickException(error.message) from error
        click.echo(f"담당자 계정 생성: {user.login_id} ({user.department or '총괄'})")

    @app.cli.command("reset-password")
    @click.option("--login-id", required=True, help="대상 로그인 아이디")
    @click.option("--password-env", default="COMPLAINT_NEW_PASSWORD", show_default=True)
    def reset_password_command(login_id: str, password_env: str) -> None:
        """계정의 비밀번호를 새 값으로 바꿉니다."""
        try:
            user = reset_password(
                repository, login_id=login_id, password=read_new_password(password_env)
            )
        except AppError as error:
            raise click.ClickException(error.message) from error
        click.echo(f"비밀번호 변경: {user.login_id}")

    @app.cli.command("deactivate-user")
    @click.option("--login-id", required=True, help="대상 로그인 아이디")
    def deactivate_user_command(login_id: str) -> None:
        """계정을 비활성화합니다. 비활성 계정은 로그인과 기존 세션이 거부됩니다."""
        try:
            user = set_active(repository, login_id=login_id, active=False)
        except AppError as error:
            raise click.ClickException(error.message) from error
        click.echo(f"비활성화: {user.login_id}")

    @app.cli.command("activate-user")
    @click.option("--login-id", required=True, help="대상 로그인 아이디")
    def activate_user_command(login_id: str) -> None:
        """비활성 계정을 다시 활성화합니다."""
        try:
            user = set_active(repository, login_id=login_id, active=True)
        except AppError as error:
            raise click.ClickException(error.message) from error
        click.echo(f"활성화: {user.login_id}")

    @app.cli.command("list-users")
    def list_users_command() -> None:
        """시연 계정을 제외한 계정 목록을 표시합니다(비밀번호 해시는 출력하지 않음)."""
        for user in repository.list_users():
            if user.is_demo:
                continue
            state = "활성" if user.active else "비활성"
            click.echo(
                f"{user.login_id}\t{user.role}\t{user.department or '-'}\t{state}\t{user.display_name}"
            )

    return app
