"""Windows에서 별도 콘솔 프로세스 기동과 TCP 포트 확인을 맡습니다.

`민원_응대.py`·`검색_시작.py`·`웹_시작.py`가 같은 기동 규칙을 씁니다.
검색 엔진 `rag.store.apply_connect_defaults`는 이 모듈을 의존하지 않습니다.
"""

from __future__ import annotations

import os
import socket
import subprocess
import time
from collections.abc import Mapping, Sequence
from pathlib import Path


def port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    """지정한 TCP 포트에 연결되면 True입니다.

    `localhost`와 `0.0.0.0`은 `127.0.0.1`로 붙습니다.

    Args:
        host: 연결할 호스트입니다.
        port: 연결할 포트입니다.
        timeout: 연결 대기 시간(초)입니다.

    Returns:
        연결에 성공하면 True입니다.
    """
    target = "127.0.0.1" if host.lower() in {"localhost", "0.0.0.0"} else host
    try:
        with socket.create_connection((target, port), timeout):
            return True
    except OSError:
        return False


def wait_for_port(
    host: str, port: int, seconds: float, *, interval: float = 0.4
) -> bool:
    """포트가 열릴 때까지 기다립니다.

    Args:
        host: 연결할 호스트입니다.
        port: 연결할 포트입니다.
        seconds: 최대 대기 시간(초)입니다.
        interval: 재시도 간격(초)입니다.

    Returns:
        열리면 True입니다.
    """
    deadline = time.time() + max(seconds, 0.0)
    while time.time() <= deadline:
        if port_open(host, port):
            return True
        time.sleep(interval)
    return port_open(host, port)


def apply_windows_libpq(env: dict[str, str]) -> dict[str, str]:
    """Windows에서 비어 있는 libpq 연결 기본값을 채웁니다.

    Linux 네이티브는 `scripts/네이티브_환경.sh`가 소켓과 계정을 지정하므로
    여기서는 Windows만 다룹니다. 이미 있는 값은 덮어쓰지 않습니다.

    Args:
        env: 채울 환경 딕셔너리입니다.

    Returns:
        같은 딕셔너리입니다.
    """
    if os.name != "nt":
        return env
    env.setdefault("PGHOST", "127.0.0.1")
    env.setdefault("PGPORT", "5432")
    env.setdefault("PGDATABASE", "complaints_native")
    user = env.get("USERNAME") or env.get("USER")
    if user:
        env.setdefault("PGUSER", user)
    return env


def spawn_console(
    command: Sequence[str],
    *,
    cwd: str | Path,
    env: Mapping[str, str] | None = None,
) -> subprocess.Popen[bytes]:
    """가능하면 새 콘솔에서 명령을 시작하고, 아니면 새 세션으로 띄웁니다.

    Windows `CREATE_NEW_CONSOLE`이 있으면 `cmd.exe /k`로 감싸 창을 유지합니다.

    Args:
        command: 실행 파일과 인자입니다.
        cwd: 작업 디렉터리입니다.
        env: 자식 환경입니다. None이면 현재 프로세스를 따릅니다.

    Returns:
        시작한 프로세스입니다.
    """
    argv = list(command)
    flags = int(getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
    if flags:
        argv = ["cmd.exe", "/k", *argv]
    kwargs: dict[str, object] = {
        "cwd": str(cwd),
        "creationflags": flags,
    }
    if env is not None:
        kwargs["env"] = dict(env)
    if not flags:
        kwargs["start_new_session"] = True
    return subprocess.Popen(argv, **kwargs)
