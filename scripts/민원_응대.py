"""Windows에서 민원 문장을 받아 RAG 검색과 LLM 응대를 표시합니다.

localhost 검색 API가 꺼져 있으면 별도 창에서 `python -m rag serve`를
시작합니다. 민원 CRUD와 검색 색인은 변경하지 않습니다.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from 콘솔_기동 import apply_windows_libpq, port_open, spawn_console
from src.assist import EXAMPLES, render_assist, run_assist
from src.llm.settings import load_llm_env_file
from src.rag import search_api_url, search_available

LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "0.0.0.0"})
DEFAULT_WAIT_SECONDS = 180.0
_SERVE_PROBE = "import fastapi, uvicorn"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """명령줄 인자를 해석합니다.

    Args:
        argv: 인자 목록입니다. None이면 `sys.argv`를 씁니다.

    Returns:
        해석한 이름공간입니다.
    """
    parser = argparse.ArgumentParser(
        description="민원 문장으로 RAG 검색과 LLM 응대를 확인합니다."
    )
    parser.add_argument("query", nargs="*", help="한국어 민원 문장")
    parser.add_argument(
        "--example",
        choices=["faq", "action", "routing", "handoff", "district"],
        help="고정 예시 질문을 사용합니다",
    )
    parser.add_argument("--district", choices=["상당구", "서원구", "흥덕구", "청원구"])
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument(
        "--rerank",
        action="store_true",
        help="재정렬 모델을 켭니다. 기본은 끈 상태입니다.",
    )
    parser.add_argument("--json", action="store_true", help="원본 JSON만 출력합니다")
    parser.add_argument(
        "--api-url",
        default=os.getenv("RAG_API_URL", "http://127.0.0.1:8007"),
    )
    parser.add_argument(
        "--no-start",
        action="store_true",
        help="검색 API가 꺼져 있어도 python -m rag serve 를 시작하지 않습니다",
    )
    parser.add_argument(
        "--wait",
        type=float,
        default=float(os.getenv("RAG_SERVE_WAIT_SECONDS", DEFAULT_WAIT_SECONDS)),
        help="검색 API 준비 대기 시간(초). 기본 180",
    )
    return parser.parse_args(argv)


def search_bind(api_url: str) -> tuple[str, int]:
    """검색 API 주소에서 바인드 호스트와 포트를 읽습니다.

    Args:
        api_url: `RAG_API_URL`과 같은 HTTP 주소입니다.

    Returns:
        호스트 이름과 포트입니다. 포트가 없으면 8007입니다.
    """
    parsed = urlparse(api_url if "://" in api_url else f"http://{api_url}")
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8007
    return host, port


def is_local_host(host: str) -> bool:
    """이 컴퓨터에서 검색 서버를 띄울 수 있는 주소인지 반환합니다.

    Args:
        host: URL 호스트입니다.

    Returns:
        localhost 계열이면 True입니다.
    """
    return host.lower() in LOCAL_HOSTS


def python_can_serve(python: Path) -> bool:
    """해당 Python이 검색 API 실행 의존성을 불러오면 True입니다.

    임베딩 모델은 올리지 않고 FastAPI·uvicorn만 확인합니다.

    Args:
        python: 확인할 실행 파일입니다.

    Returns:
        프로브가 성공하면 True입니다.
    """
    try:
        probe = subprocess.run(
            [str(python), "-c", _SERVE_PROBE],
            cwd=str(ROOT),
            capture_output=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return probe.returncode == 0


def _venv_python() -> Path:
    """네이티브 RAG 가상환경의 Python 경로를 반환합니다.

    Returns:
        Windows는 `.venv/Scripts/python.exe`, 그 외는 `.venv/bin/python`입니다.
    """
    if os.name == "nt":
        return ROOT / ".venv" / "Scripts" / "python.exe"
    return ROOT / ".venv" / "bin" / "python"


def resolve_rag_python() -> tuple[Path | None, str | None]:
    """검색 서버를 실행할 Python을 고릅니다.

    `RAG_PYTHON`이 있으면 그 경로만 검사합니다. 없으면 `.venv` 다음
    현재 인터프리터 순으로 FastAPI·uvicorn을 불러올 수 있는 실행 파일을 씁니다.

    Returns:
        실행 파일과 실패 안내입니다. 성공하면 안내는 None입니다.
    """
    override = os.environ.get("RAG_PYTHON", "").strip()
    if override:
        path = Path(override)
        if not path.is_file():
            return None, f"RAG_PYTHON 경로를 찾을 수 없습니다: {override}"
        if not python_can_serve(path):
            return None, (
                f"RAG_PYTHON이 검색 서버 의존성을 불러오지 못합니다: {override}. "
                "rag/requirements.txt 설치를 확인하세요."
            )
        return path, None

    for path in (_venv_python(), Path(sys.executable)):
        if path.is_file() and python_can_serve(path):
            return path, None
    return None, (
        "검색 API를 자동으로 시작할 Python을 찾지 못했습니다. "
        ".venv에 rag/requirements.txt 를 설치하거나 RAG_PYTHON을 지정하세요."
    )


def search_server_env() -> dict[str, str]:
    """검색 서버 자식 프로세스에 넘길 환경을 만듭니다.

    Hugging Face 캐시와 CPU 실행 기본값만 비어 있을 때 채웁니다.
    이미 있는 PG·모델 환경변수는 덮어쓰지 않습니다.

    Returns:
        `os.environ`을 복사한 딕셔너리입니다.
    """
    env = os.environ.copy()
    env.setdefault("HF_HOME", str(ROOT / ".rag-cache" / "huggingface"))
    env.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    env.setdefault("TOKENIZERS_PARALLELISM", "false")
    env.setdefault("RAG_DEVICE", "cpu")
    return apply_windows_libpq(env)


def start_search_server(python: Path, host: str, port: int) -> subprocess.Popen[bytes]:
    """별도 창 또는 세션에서 `python -m rag serve`를 시작합니다.

    Windows에서는 `웹-시작.cmd`와 같이 새 콘솔을 엽니다. 창을 닫으면
    검색 서버도 함께 종료됩니다.

    Args:
        python: 검색 엔진 가상환경 Python입니다.
        host: 바인드 호스트입니다.
        port: 바인드 포트입니다.

    Returns:
        시작한 프로세스입니다.
    """
    bind_host = "127.0.0.1" if host.lower() in {"localhost", "0.0.0.0"} else host
    return spawn_console(
        [
            str(python),
            "-m",
            "rag",
            "serve",
            "--host",
            bind_host,
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=search_server_env(),
    )


def wait_for_search(seconds: float) -> bool:
    """지정한 시간 안에 검색 API health가 ready가 되면 True입니다.

    Args:
        seconds: 최대 대기 시간(초)입니다.

    Returns:
        준비되면 True, 시간이 끝나면 False입니다.
    """
    deadline = time.time() + max(seconds, 0.0)
    while time.time() <= deadline:
        if search_available():
            return True
        time.sleep(0.5)
    return search_available()


def _search_start_error(api_url: str) -> str:
    """자동 기동 실패 때 출력할 안내입니다.

    Args:
        api_url: 연결을 시도한 검색 API 주소입니다.

    Returns:
        한국어 오류 문장입니다.
    """
    return (
        f"[오류] 검색 API에 연결하지 못했습니다. {api_url} 에서 "
        "python -m rag serve 가 준비되지 않았습니다. "
        "별도 창의 서버 로그, PostgreSQL complaints_native / complaint_rag, "
        "rag/requirements.txt 가상환경(.venv 또는 RAG_PYTHON)을 확인하세요."
    )


def ensure_search_api(*, auto_start: bool, wait_seconds: float) -> str | None:
    """검색 API가 꺼져 있으면 localhost에서 시작하고 준비를 기다립니다.

    이미 ready이면 다시 시작하지 않습니다. 포트만 열려 있으면 기동 중인
    것으로 보고 기다립니다. 원격 주소는 이 컴퓨터에서 시작하지 않습니다.

    Args:
        auto_start: False이면 꺼진 API를 시작하지 않습니다.
        wait_seconds: health ready 대기 시간(초)입니다.

    Returns:
        성공하면 None, 실패하면 출력할 오류 문자열입니다.
    """
    if search_available():
        return None

    api_url = search_api_url()
    host, port = search_bind(api_url)
    if port_open(host, port):
        print(
            f"... 검색 API({api_url})가 아직 준비 중입니다. 잠시 기다립니다.",
            flush=True,
        )
        if wait_for_search(wait_seconds):
            return None
        return _search_start_error(api_url)

    if not auto_start:
        return (
            f"[오류] 검색 API에 연결하지 못했습니다. {api_url} 에서 "
            "python -m rag serve 가 실행 중인지 확인하세요."
        )
    if not is_local_host(host):
        return (
            f"[오류] 검색 API에 연결하지 못했습니다. {api_url} 은 "
            "이 컴퓨터에서 자동 시작할 수 없는 주소입니다."
        )

    python, python_error = resolve_rag_python()
    if python is None:
        return f"[오류] {python_error}"

    print(
        f"... 검색 API가 꺼져 있어 별도 창에서 {python} -m rag serve 를 시작합니다.",
        flush=True,
    )
    print(
        "... 첫 실행은 임베딩 모델 로드로 1~3분이 걸릴 수 있습니다.",
        flush=True,
    )
    try:
        start_search_server(python, host, port)
    except OSError as exc:
        return f"[오류] 검색 API를 시작하지 못했습니다: {exc}"
    if wait_for_search(wait_seconds):
        return None
    return _search_start_error(api_url)


def resolve_query(args: argparse.Namespace) -> tuple[str, str | None]:
    """민원 문장과 관할 구를 고릅니다.

    Args:
        args: 해석한 인자입니다.

    Returns:
        질문 문자열과 관할 구입니다.

    Raises:
        ValueError: 문장이 비어 있는 경우 발생합니다.
    """
    query = " ".join(args.query).strip()
    district = args.district
    if args.example:
        sample = next(item for item in EXAMPLES if item["id"] == args.example)
        query = query or str(sample["query"])
        if district is None:
            district = sample["district"]
    if not query:
        try:
            query = input("민원 내용을 입력하세요: ").strip()
        except EOFError as exc:
            raise ValueError("민원 문장 또는 --example 을 지정해 주세요.") from exc
    if not query:
        raise ValueError("민원 문장 또는 --example 을 지정해 주세요.")
    return query, district


def main(argv: list[str] | None = None) -> int:
    """검색 API와 LLM 설정을 확인한 뒤 응대 결과를 출력합니다.

    Args:
        argv: 인자 목록입니다.

    Returns:
        성공 0, 설정·검색 실패 1입니다.
    """
    load_llm_env_file()
    args = parse_args(argv)
    os.environ["RAG_API_URL"] = args.api_url.rstrip("/")
    try:
        query, district = resolve_query(args)
    except ValueError as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        return 1
    search_error = ensure_search_api(
        auto_start=not args.no_start,
        wait_seconds=args.wait,
    )
    if search_error:
        print(search_error, file=sys.stderr)
        return 1

    def on_progress(_key: str, label: str) -> None:
        """진행 단계 설명을 표준 출력에 바로 씁니다.

        Args:
            _key: 내부 단계 식별자이며 표시에는 쓰지 않습니다.
            label: 화면에 보일 짧은 안내입니다.
        """
        print(f"... {label}", flush=True)

    print(f"민원: {query}")
    if district:
        print(f"관할: {district}")
    try:
        result = run_assist(
            query,
            district,
            limit=args.limit,
            rerank=args.rerank,
            on_progress=None if args.json else on_progress,
        )
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print()
    print(render_assist(result))
    if not result.get("llm_configured"):
        print()
        print(
            "안내: LLM이 설정되지 않아 검색 근거와 담당자 검토 사유만 표시했습니다. "
            ".env의 COMPLAINT_LLM_PROVIDER를 확인하세요."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
