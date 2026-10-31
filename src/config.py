"""경로와 시연 설정을 불변 타입으로 관리합니다."""

from dataclasses import dataclass
import os
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    """앱 생성에 필요한 값만 명시적으로 전달합니다.

    Attributes:
        database: 별도 업무 SQLite 파일 경로입니다. 기본값은 db/app/complaints.sqlite3 입니다.
        secret_key: 서명 세션의 비밀키이며 응답·로그에 노출하지 않습니다.
        testing: 격리 테스트 여부입니다.
        demo_login: 로컬 역할 선택을 허용할지 여부입니다.
    """

    database: Path
    secret_key: str
    testing: bool = False
    demo_login: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        """환경 설정과 로컬 비밀키 파일을 읽습니다.

        Returns:
            기본 경로를 포함한 불변 설정입니다.
        """
        secrets_dir = ROOT / ".web-data"
        secrets_dir.mkdir(exist_ok=True)
        data_dir = ROOT / "db" / "app"
        data_dir.mkdir(parents=True, exist_ok=True)
        secret = os.environ.get("COMPLAINT_SECRET_KEY")
        if not secret:
            key_file = secrets_dir / "session.key"
            try:
                with key_file.open("x", encoding="utf-8") as output:
                    output.write(secrets.token_hex(32))
            except FileExistsError:
                pass
            secret = key_file.read_text(encoding="utf-8").strip()
        return cls(
            database=Path(
                os.environ.get(
                    "COMPLAINT_DATABASE", str(data_dir / "complaints.sqlite3")
                )
            ),
            secret_key=secret,
            demo_login=os.environ.get("COMPLAINT_DEMO_LOGIN", "1") == "1",
        )
