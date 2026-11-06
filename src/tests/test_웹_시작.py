"""Windows Flask 시작 스크립트의 환경 기본값을 확인합니다."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture(scope="module")
def start_web() -> ModuleType:
    """scripts/웹_시작.py를 한 번만 불러옵니다."""
    path = Path(__file__).resolve().parents[2] / "scripts" / "웹_시작.py"
    spec = importlib.util.spec_from_file_location("start_web", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_flask_env_sets_windows_libpq(
    start_web: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PGDATABASE가 비어 있으면 complaints_native를 채웁니다."""
    monkeypatch.delenv("PGHOST", raising=False)
    monkeypatch.delenv("PGDATABASE", raising=False)
    monkeypatch.delenv("PGPORT", raising=False)
    env = start_web.flask_env()
    assert env["PGHOST"] == "127.0.0.1"
    assert env["PGPORT"] == "5432"
    assert env["PGDATABASE"] == "complaints_native"


def test_health_url_uses_port(start_web: ModuleType) -> None:
    """health 주소는 지정한 포트를 씁니다."""
    assert start_web._health_url(5000).endswith(":5000/api/v1/health")
    assert start_web._site_url(5001).endswith(":5001/#/citizen")
