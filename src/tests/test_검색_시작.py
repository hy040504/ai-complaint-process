"""Windows PostgreSQL 및 검색 API 기동 스크립트의 준비 로직을 검증합니다."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture(scope="module")
def start_search() -> ModuleType:
    """scripts/검색_시작.py를 한 번만 불러옵니다."""
    path = Path(__file__).resolve().parents[2] / "scripts" / "검색_시작.py"
    spec = importlib.util.spec_from_file_location("start_search", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_clean_stale_postmaster_pid_no_file(
    start_search: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """postmaster.pid 파일이 없으면 False를 반환합니다."""
    monkeypatch.setattr(start_search, "PG_DATA", tmp_path)
    assert start_search.clean_stale_postmaster_pid() is False


def test_clean_stale_postmaster_pid_running_db(
    start_search: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DB가 정상 구동 중(postgres_ready=True)이면 postmaster.pid를 지우지 않습니다."""
    pid_file = tmp_path / "postmaster.pid"
    pid_file.write_text("12345\n", encoding="utf-8")
    monkeypatch.setattr(start_search, "PG_DATA", tmp_path)
    monkeypatch.setattr(start_search, "postgres_ready", lambda: True)

    assert start_search.clean_stale_postmaster_pid() is False
    assert pid_file.is_file()


def test_clean_stale_postmaster_pid_stale_file(
    start_search: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DB 포트가 닫혀 있고 잔여 postmaster.pid가 남아 있으면 이를 삭제하고 True를 반환합니다."""
    pid_file = tmp_path / "postmaster.pid"
    pid_file.write_text("12345\n", encoding="utf-8")
    monkeypatch.setattr(start_search, "PG_DATA", tmp_path)
    monkeypatch.setattr(start_search, "postgres_ready", lambda: False)

    assert start_search.clean_stale_postmaster_pid() is True
    assert not pid_file.is_file()


def test_ensure_backend_services_already_ready(
    start_search: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """두 서비스가 이미 켜져 있으면 추가 기동 없이 True를 반환합니다."""
    monkeypatch.setattr(start_search, "clean_stale_postmaster_pid", lambda: False)
    monkeypatch.setattr(start_search, "postgres_ready", lambda: True)
    monkeypatch.setattr(start_search, "port_open", lambda host, port: True)

    assert start_search.ensure_backend_services() is True


def test_ensure_backend_services_starts_missing(
    start_search: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """꺼져 있는 서비스(DB, 검색 API)를 감지하여 시작하고 포트를 대기합니다."""
    started: list[str] = []
    waited: list[int] = []

    monkeypatch.setattr(start_search, "clean_stale_postmaster_pid", lambda: False)
    monkeypatch.setattr(start_search, "postgres_ready", lambda: False)
    monkeypatch.setattr(start_search, "start_postgres", lambda: started.append("postgres"))
    monkeypatch.setattr(start_search, "port_open", lambda host, port: False)
    monkeypatch.setattr(start_search, "start_search_api", lambda: started.append("search_api"))
    monkeypatch.setattr(
        start_search, "wait_for_port", lambda host, port, timeout: waited.append(port) or True
    )

    assert start_search.ensure_backend_services(wait_seconds=5.0) is True
    assert started == ["postgres", "search_api"]
    assert waited == [5432, 8007]
