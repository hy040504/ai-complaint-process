"""Windows 콘솔 기동 도우미의 포트·환경 기본값을 확인합니다."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture(scope="module")
def console_spawn() -> ModuleType:
    """scripts/console_spawn.py를 한 번만 불러옵니다."""
    path = Path(__file__).resolve().parents[2] / "scripts" / "console_spawn.py"
    spec = importlib.util.spec_from_file_location("console_spawn", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_apply_windows_libpq_keeps_existing(console_spawn: ModuleType) -> None:
    """이미 있는 PG 환경변수는 덮어쓰지 않습니다."""
    env = {
        "PGHOST": "10.0.0.2",
        "PGPORT": "6543",
        "PGDATABASE": "other",
        "PGUSER": "keep",
        "USERNAME": "user",
    }
    filled = console_spawn.apply_windows_libpq(env)
    assert filled["PGHOST"] == "10.0.0.2"
    assert filled["PGPORT"] == "6543"
    assert filled["PGDATABASE"] == "other"
    assert filled["PGUSER"] == "keep"


def test_port_open_closed_port(console_spawn: ModuleType) -> None:
    """닫힌 포트는 False입니다."""
    assert console_spawn.port_open("127.0.0.1", 1) is False
