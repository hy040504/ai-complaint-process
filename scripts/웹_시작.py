"""Windows에서 Flask 민원 서버를 시작하고 응대 검사기를 엽니다.

자식 프로세스에는 `apply_windows_libpq`로 `PGHOST`·`PGDATABASE` 기본값을
채웁니다. 이미 있는 환경변수는 덮어쓰지 않습니다.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from 콘솔_기동 import apply_windows_libpq, port_open as tcp_open, spawn_console

ROOT = Path(__file__).resolve().parent.parent
PYTHON = ROOT / ".venv-web" / "Scripts" / "python.exe"
_NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _port() -> int:
    """COMPLAINT_PORT에서 확인할 포트를 읽습니다.

    Returns:
        양의 정수 포트입니다. 없거나 잘못된 값이면 5000입니다.
    """
    raw = os.environ.get("COMPLAINT_PORT", "5000")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 5000
    return value if value > 0 else 5000


def _health_url(port: int) -> str:
    """health 확인 주소를 만듭니다.

    Args:
        port: Flask가 바인딩한 포트입니다.

    Returns:
        `127.0.0.1` health URL입니다.
    """
    return f"http://127.0.0.1:{port}/api/v1/health"


def _site_url(port: int) -> str:
    """기본 브라우저로 열 응대 검사기 주소를 만듭니다.

    Args:
        port: Flask가 바인딩한 포트입니다.

    Returns:
        `/#/lab` 주소입니다.
    """
    return f"http://127.0.0.1:{port}/#/lab"


def port_open(port: int) -> bool:
    """업무 서버 포트가 이미 열려 있는지 반환합니다.

    Args:
        port: 확인할 TCP 포트입니다.

    Returns:
        `127.0.0.1`에서 연결되면 True입니다.
    """
    return tcp_open("127.0.0.1", port)


def health_ok(url: str) -> bool:
    """health API가 2xx를 반환하면 True입니다.

    시스템 프록시를 쓰지 않고 localhost만 직접 호출합니다.

    Args:
        url: health 확인 주소입니다.

    Returns:
        본문 읽기에 성공하고 상태 코드가 2xx이면 True입니다.
    """
    try:
        with _NO_PROXY.open(url, timeout=5) as response:
            response.read()
            return 200 <= int(response.status) < 300
    except OSError:
        return False


def wait_until_ready(url: str, seconds: float = 30.0) -> bool:
    """지정한 시간 안에 health가 성공할 때까지 기다립니다.

    Args:
        url: health 확인 주소입니다.
        seconds: 최대 대기 시간(초)입니다.

    Returns:
        준비되면 True, 시간이 끝나면 False입니다.
    """
    deadline = time.time() + seconds
    while time.time() < deadline:
        if health_ok(url):
            return True
        time.sleep(0.4)
    return False


def flask_env() -> dict[str, str]:
    """Flask 서버에 넘길 환경변수를 만듭니다.

    Windows에서 비어 있는 `PGHOST`·`PGDATABASE`를 채웁니다. 이미 있는
    값은 덮어쓰지 않습니다.

    Returns:
        libpq 기본값을 채운 환경 딕셔너리입니다.
    """
    return apply_windows_libpq(os.environ.copy())


def start_server() -> None:
    """새 콘솔 창에서 Flask 업무 서버를 실행합니다.

    창을 닫으면 서버 프로세스도 함께 종료됩니다. Windows가 아니면
    새 세션으로 실행합니다.
    """
    spawn_console([str(PYTHON), "-m", "src"], cwd=ROOT, env=flask_env())


def main() -> int:
    """가상환경을 확인하고 서버 준비 후 응대 검사기를 엽니다.

    Returns:
        성공 0, 가상환경·준비 실패 1입니다.
    """
    os.chdir(ROOT)
    if not PYTHON.is_file():
        print("[오류] .venv-web 가상환경의 Python을 찾을 수 없습니다.")
        print("먼저 src\\README.md의 설치 절차를 실행해 주세요.")
        return 1
    probe = subprocess.run(
        [str(PYTHON), "-c", "import sys"],
        check=False,
        capture_output=True,
    )
    if probe.returncode != 0:
        print("[오류] .venv-web의 Python이 이 컴퓨터에서 실행되지 않습니다.")
        print("src\\README.md의 설치 절차로 .venv-web을 다시 만들어 주세요.")
        return 1

    port = _port()
    health = _health_url(port)
    if port_open(port):
        print(f"이미 {port} 포트에서 서버가 실행 중입니다.")
    else:
        print("Flask 민원 서버를 시작합니다. 별도 창을 닫으면 서버도 종료됩니다.")
        start_server()

    if not wait_until_ready(health):
        print("[오류] 30초 안에 서버 준비를 확인하지 못했습니다.")
        print("서버 창의 오류를 확인한 뒤 다시 실행해 주세요.")
        return 1

    site = _site_url(port)
    print(f"브라우저에서 {site} 을 엽니다.")
    webbrowser.open(site)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
