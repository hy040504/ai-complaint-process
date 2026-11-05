"""경로와 시연 설정을 불변 타입으로 관리합니다."""

from dataclasses import dataclass
import os
from pathlib import Path
import re
import secrets
from typing import Literal

ROOT = Path(__file__).resolve().parents[2]
# 시연 웹 PostgreSQL DDL. 검색 스키마는 rag/origin/schema.
APP_SCHEMA_SQL = Path(__file__).resolve().parent / "schema" / "complaint_app.sql"
StoreBackend = Literal["postgresql", "memory"]


def _schema_name(raw: str) -> str:
    """업무 스키마 이름이 PostgreSQL 식별자로 안전한지 확인합니다.

    Args:
        raw: 환경변수 또는 호출자가 준 스키마 이름입니다.

    Returns:
        공백을 제거한 스키마 이름입니다.

    Raises:
        ValueError: 식별자로 쓸 수 없으면 발생합니다.
    """
    name = raw.strip() or "complaint_app"
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError("COMPLAINT_APP_SCHEMA는 영문·숫자·밑줄이어야 합니다.")
    return name


@dataclass(frozen=True)
class Settings:
    """앱 생성에 필요한 값만 명시적으로 전달합니다.

    Attributes:
        backend: `postgresql`은 시연·운영, `memory`는 단위 테스트 전용입니다.
        conninfo: PostgreSQL 연결 문자열입니다. 비면 libpq 환경변수를 씁니다.
        schema: 업무 스키마 이름입니다. 검색 스키마 `complaint_rag`와 구별합니다.
        secret_key: 서명 세션의 비밀키이며 응답·로그에 노출하지 않습니다.
        testing: 격리 테스트 여부입니다.
        demo_login: 로컬 역할 선택을 허용할지 여부입니다.
    """

    secret_key: str
    backend: StoreBackend = "postgresql"
    conninfo: str = ""
    schema: str = "complaint_app"
    testing: bool = False
    demo_login: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        """환경 설정과 로컬 비밀키 파일을 읽습니다.

        Returns:
            PostgreSQL 업무 저장을 기본으로 한 불변 설정입니다.
        """
        secrets_dir = ROOT / ".web-data"
        secrets_dir.mkdir(exist_ok=True)
        secret = os.environ.get("COMPLAINT_SECRET_KEY")
        if not secret:
            key_file = secrets_dir / "session.key"
            try:
                with key_file.open("x", encoding="utf-8") as output:
                    output.write(secrets.token_hex(32))
            except FileExistsError:
                pass
            secret = key_file.read_text(encoding="utf-8").strip()
        backend = os.environ.get("COMPLAINT_STORE", "postgresql").strip().lower()
        if backend != "postgresql":
            raise ValueError("시연 서버의 COMPLAINT_STORE는 postgresql 만 허용합니다.")
        return cls(
            secret_key=secret,
            backend="postgresql",
            conninfo=os.environ.get("COMPLAINT_DATABASE_URL", "").strip(),
            schema=_schema_name(
                os.environ.get("COMPLAINT_APP_SCHEMA", "complaint_app")
            ),
            demo_login=os.environ.get("COMPLAINT_DEMO_LOGIN", "1") == "1",
        )
