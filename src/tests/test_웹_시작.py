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


def test_flask_env_sets_lab_port(
    start_web: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LAB_WEB_PORT가 비어 있으면 5010을 채웁니다."""
    monkeypatch.delenv("LAB_WEB_PORT", raising=False)
    env = start_web.flask_env()
    assert env["LAB_WEB_PORT"] == "5010"


def test_health_url_uses_port(start_web: ModuleType) -> None:
    """health 주소는 지정한 포트를 씁니다."""
    assert start_web._health_url(5010).endswith(":5010/api/v1/health")
    assert start_web._site_url(5011).endswith(":5011/")
