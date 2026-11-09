"""Windows 로컬 PostgreSQL과 검색 API를 기동합니다."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from 콘솔_기동 import apply_windows_libpq, port_open, spawn_console, wait_for_port

ROOT = Path(__file__).resolve().parent.parent
PG_BIN = ROOT / ".rag-data" / "pgsql" / "bin"
PG_DATA = ROOT / ".rag-data" / "postgres"
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"


def postgres_ready() -> bool:
    """로컬 PostgreSQL 5432가 열려 있으면 True입니다."""
    return port_open("127.0.0.1", 5432)


def clean_stale_postmaster_pid() -> bool:
    """PostgreSQL 포트가 닫혀 있는데 남아 있는 잔여 락 파일(postmaster.pid)을 정리합니다.

    Returns:
        정리했으면 True, 파일이 없거나 DB가 이미 동작 중이면 False입니다.
    """
    pid_file = PG_DATA / "postmaster.pid"
    if not pid_file.is_file():
        return False
    if postgres_ready():
        return False
    try:
        pid_file.unlink(missing_ok=True)
        print("이전 비정상 종료로 남아 있던 PostgreSQL 락 파일(postmaster.pid)을 정리했습니다.")
        return True
    except OSError as exc:
        print(f"[경고] postmaster.pid 정리 실패: {exc}")
        return False


def start_postgres() -> subprocess.Popen[bytes]:
    """별도 콘솔에서 사용자 디렉터리 PostgreSQL을 시작합니다.

    Returns:
        시작한 프로세스입니다.

    Raises:
        FileNotFoundError: 바이너리 또는 데이터 디렉터리가 없는 경우 발생합니다.
    """
    postgres = PG_BIN / "postgres.exe"
    if not postgres.is_file():
        raise FileNotFoundError(
            "PostgreSQL 바이너리가 없습니다. .rag-data/pgsql 설치를 확인하세요."
        )
    if not PG_DATA.is_dir():
        raise FileNotFoundError(
            "PostgreSQL 데이터 디렉터리가 없습니다. .rag-data/postgres 를 확인하세요."
        )
    return spawn_console([str(postgres), "-D", str(PG_DATA)], cwd=ROOT)


def search_env() -> dict[str, str]:
    """검색 서버에 넘길 환경변수를 만듭니다.

    Returns:
        PG·모델 캐시 기본값을 채운 환경 딕셔너리입니다.
    """
    env = os.environ.copy()
    apply_windows_libpq(env)
    env.setdefault("HF_HOME", str(ROOT / ".rag-cache" / "huggingface"))
    env.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    env.setdefault("TOKENIZERS_PARALLELISM", "false")
    env.setdefault("RAG_DEVICE", "cpu")
    return env


def start_search_api() -> subprocess.Popen[bytes]:
    """별도 콘솔에서 `python -m rag serve`를 시작합니다.

    Returns:
        시작한 프로세스입니다.

    Raises:
        FileNotFoundError: RAG 가상환경 Python이 없는 경우 발생합니다.
    """
    if not PYTHON.is_file():
        raise FileNotFoundError("RAG 가상환경 .venv 를 찾을 수 없습니다.")
    return spawn_console(
        [str(PYTHON), "-m", "rag", "serve", "--host", "127.0.0.1", "--port", "8007"],
        cwd=ROOT,
        env=search_env(),
    )


def ensure_backend_services(wait_seconds: float = 60.0) -> bool:
    """PostgreSQL(5432)과 검색 API(8007)가 실행 중인지 확인하고, 꺼져 있으면 기동합니다.

    stale lock 파일이 남아 있으면 먼저 정리하며, 이미 열린 포트는
    중복 기동하지 않고 그대로 재사용합니다.

    Args:
        wait_seconds: 검색 API 및 DB 준비를 기다릴 최대 시간(초)입니다.

    Returns:
        두 서비스 모두 준비되면 True, 기동이나 대기 실패 시 False입니다.
    """
    clean_stale_postmaster_pid()

    if not postgres_ready():
        print("PostgreSQL이 실행되어 있지 않습니다. 별도 창에서 시작합니다.")
        try:
            start_postgres()
        except FileNotFoundError as exc:
            print(f"[오류] {exc}")
            return False
        if not wait_for_port("127.0.0.1", 5432, 20):
            print("[오류] PostgreSQL 5432 준비를 확인하지 못했습니다.")
            return False
        print("PostgreSQL(127.0.0.1:5432) 준비를 완료했습니다.")
    else:
        print("PostgreSQL이 이미 127.0.0.1:5432 에서 실행 중입니다.")

    if not port_open("127.0.0.1", 8007):
        print("검색 API(:8007)가 실행되어 있지 않습니다. 별도 창에서 시작합니다.")
        try:
            start_search_api()
        except FileNotFoundError as exc:
            print(f"[오류] {exc}")
            return False
        print(f"검색 API 준비를 기다립니다(최대 {int(wait_seconds)}초, 모델 로딩 포함)...")
        if not wait_for_port("127.0.0.1", 8007, wait_seconds):
            print("[오류] 검색 API 8007 준비를 확인하지 못했습니다.")
            return False
        print("검색 API(127.0.0.1:8007) 준비를 완료했습니다.")
    else:
        print("검색 API가 이미 127.0.0.1:8007 에서 실행 중입니다.")

    return True


def main() -> int:
    """PostgreSQL과 검색 API를 준비하고 종료 코드를 반환합니다.

    이미 열린 5432·8007은 종료하지 않습니다. 이 프로세스는 기동기이며
    DB와 검색 API는 별도 콘솔에 둡니다.

    Returns:
        준비되면 0, 바이너리·포트 확인 실패면 1입니다.
    """
    os.chdir(ROOT)
    if not ensure_backend_services(wait_seconds=60.0):
        return 1
    print("백엔드 검색 서비스(PostgreSQL·검색 API)가 모두 준비되었습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
