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


def main() -> int:
    """PostgreSQL과 검색 API를 준비하고 상태를 출력합니다."""
    os.chdir(ROOT)
    if postgres_ready():
        print("PostgreSQL이 이미 127.0.0.1:5432 에서 실행 중입니다.")
    else:
        print("PostgreSQL을 별도 창에서 시작합니다.")
        try:
            start_postgres()
        except FileNotFoundError as exc:
            print(f"[오류] {exc}")
            return 1
        if not wait_for_port("127.0.0.1", 5432, 20):
            print("[오류] PostgreSQL 5432 준비를 확인하지 못했습니다.")
            return 1

    if port_open("127.0.0.1", 8007):
        print("검색 API가 이미 127.0.0.1:8007 에서 실행 중입니다.")
        return 0

    print("검색 API를 별도 창에서 시작합니다. 첫 실행은 모델 로드에 시간이 걸립니다.")
    try:
        start_search_api()
    except FileNotFoundError as exc:
        print(f"[오류] {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
