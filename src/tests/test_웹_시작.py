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


def test_main_checks_backend_services(
    start_web: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """웹 서버 준비 후 백엔드 서비스(PostgreSQL·검색 API) 상태를 점검합니다."""
    backend_checked = []
    browser_opened = []

    monkeypatch.setattr(start_web.Path, "is_file", lambda self: True)
    monkeypatch.setattr(start_web.subprocess, "run", lambda *args, **kwargs: type("Proc", (), {"returncode": 0})())
    monkeypatch.setattr(start_web, "port_open", lambda port: True)
    monkeypatch.setattr(start_web, "wait_until_ready", lambda url: True)
    monkeypatch.setattr(
        start_web,
        "ensure_backend_services",
        lambda wait_seconds=60.0: backend_checked.append(True) or True,
    )
    monkeypatch.setattr(start_web.webbrowser, "open", lambda url: browser_opened.append(url))

    exit_code = start_web.main()
    assert exit_code == 0
    assert len(backend_checked) == 1
    assert len(browser_opened) == 1

