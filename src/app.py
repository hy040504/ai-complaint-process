"""설정 → 민원 저장소 → 서비스 → API·화면 순서로 Flask 앱을 구성합니다.

민원 CRUD는 `src.complaints`에 있고, 검사기 API는 같은 블루프린트에서
`src.assist`를 호출합니다.
"""

import click
from flask_openapi3.models.info import Info
from flask_openapi3.openapi import OpenAPI
from werkzeug.middleware.proxy_fix import ProxyFix

from src.complaints.api import create_api
from src.complaints.config import ROOT, Settings
from src.complaints.demo_data import seed_public_demo
from src.complaints.http import register_http, validation_error
from src.complaints.models import ErrorResponse
from src.complaints.pages import web
from src.complaints.repository import MemoryRepository, PostgresRepository
from src.complaints.seed import seed_demo
from src.complaints.service import ComplaintService


def create_app(
    settings: Settings | None = None,
    repository: MemoryRepository | PostgresRepository | None = None,
) -> OpenAPI:
    """설정과 저장소를 주입하여 독립적인 Flask 앱을 만듭니다.

    Args:
        settings: 생략하면 환경 변수와 PostgreSQL 기본 스키마를 읽습니다.
        repository: 생략하면 설정의 저장 백엔드를 만듭니다.

    Returns:
        UI와 API 및 Swagger를 함께 제공하는 Flask 앱입니다.
    """
    config = settings or Settings.from_env()
    app = OpenAPI(
        __name__,
        info=Info(
            title="청주톡톡 민원 업무 API",
            version="0.2.0",
            description="로컬 시연 업무 서버입니다. 먼저 시연 세션에서 역할을 선택하세요. 민원·답변은 DB에 저장되며 실제 AI·공식 접수·행정 이관은 미연동입니다.",
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
        MAX_CONTENT_LENGTH=64 * 1024,
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
    service = ComplaintService(repository)
    app.extensions["complaint_service"] = service
    # Tailscale Serve 등 로컬 프록시의 X-Forwarded-Proto를 반영해 HTTPS Origin 검사를 통과시킵니다.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)  # type: ignore[method-assign]
    register_http(app)
    app.register_api(create_api(service))
    app.register_blueprint(web)

    @app.cli.command("seed-demo")
    def seed_command() -> None:
        """사용자가 요청했을 때만 비어 있는 업무 DB에 합성 자료를 넣습니다."""
        click.echo(f"합성 시연 민원 {seed_demo(repository)}건 생성")

    @app.cli.command("seed-public-demo")
    def seed_public_command() -> None:
        """공개 사례·자주 묻는 민원 JSON을 개인정보 마스킹 후 시연 민원으로 넣습니다."""
        click.echo(
            f"공개 데이터 기반 시연 민원 {seed_public_demo(repository, ROOT / 'db')}건 생성"
        )

    return app
