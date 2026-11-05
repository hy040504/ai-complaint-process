"""민원 응대 CMD 스크립트의 질문 해석을 확인합니다."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


@pytest.fixture(scope="module")
def ask_assist() -> ModuleType:
    """scripts/ask_assist.py를 한 번만 불러옵니다."""
    path = Path(__file__).resolve().parents[2] / "scripts" / "ask_assist.py"
    spec = importlib.util.spec_from_file_location("ask_assist", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resolve_query_uses_example(ask_assist: ModuleType) -> None:
    """--example faq 이면 고정 FAQ 예시 문장을 씁니다."""
    args = ask_assist.parse_args(["--example", "faq"])
    query, district = ask_assist.resolve_query(args)
    assert "대형폐기물" in query
    assert district is None


def test_resolve_query_joins_words(ask_assist: ModuleType) -> None:
    """위치 인자를 한 문장으로 이어 붙입니다."""
    args = ask_assist.parse_args(["대형폐기물", "배출", "방법"])
    query, district = ask_assist.resolve_query(args)
    assert query == "대형폐기물 배출 방법"
    assert district is None


def test_resolve_query_rejects_empty(
    ask_assist: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """문장이 없고 입력도 비면 실패합니다."""
    args = ask_assist.parse_args([])
    monkeypatch.setattr("builtins.input", lambda _prompt="": "")
    with pytest.raises(ValueError, match="민원 문장"):
        ask_assist.resolve_query(args)


def test_parse_args_keeps_auto_start_default(ask_assist: ModuleType) -> None:
    """기본은 검색 API 자동 시작이며 --no-start 로 끕니다."""
    default_args = ask_assist.parse_args(["질문"])
    assert default_args.no_start is False
    assert default_args.wait == ask_assist.DEFAULT_WAIT_SECONDS
    skipped = ask_assist.parse_args(["--no-start", "질문"])
    assert skipped.no_start is True


def test_search_bind_defaults_port(ask_assist: ModuleType) -> None:
    """주소에 포트가 없으면 8007을 씁니다."""
    host, port = ask_assist.search_bind("http://127.0.0.1")
    assert host == "127.0.0.1"
    assert port == 8007
    host, port = ask_assist.search_bind("http://localhost:9001")
    assert host == "localhost"
    assert port == 9001


def test_is_local_host(ask_assist: ModuleType) -> None:
    """localhost 계열만 이 컴퓨터에서 자동 시작합니다."""
    assert ask_assist.is_local_host("127.0.0.1")
    assert ask_assist.is_local_host("localhost")
    assert not ask_assist.is_local_host("192.168.1.10")


def test_ensure_search_api_skips_start_when_ready(
    ask_assist: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """이미 ready이면 검색 서버를 다시 시작하지 않습니다."""
    started: list[Any] = []
    monkeypatch.setattr(ask_assist, "search_available", lambda: True)
    monkeypatch.setattr(
        ask_assist, "start_search_server", lambda *args, **kwargs: started.append(args)
    )
    assert ask_assist.ensure_search_api(auto_start=True, wait_seconds=1) is None
    assert started == []


def test_ensure_search_api_no_start_when_down(
    ask_assist: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--no-start 이고 API가 꺼져 있으면 기존 오류 안내를 반환합니다."""
    monkeypatch.setattr(ask_assist, "search_available", lambda: False)
    monkeypatch.setattr(ask_assist, "port_open", lambda _host, _port: False)
    monkeypatch.setattr(ask_assist, "search_api_url", lambda: "http://127.0.0.1:8007")
    message = ask_assist.ensure_search_api(auto_start=False, wait_seconds=1)
    assert message is not None
    assert "python -m rag serve" in message
    assert "8007" in message


def test_ensure_search_api_rejects_remote_url(
    ask_assist: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """원격 검색 API는 이 컴퓨터에서 자동 시작하지 않습니다."""
    monkeypatch.setattr(ask_assist, "search_available", lambda: False)
    monkeypatch.setattr(ask_assist, "port_open", lambda _host, _port: False)
    monkeypatch.setattr(
        ask_assist, "search_api_url", lambda: "http://192.168.1.10:8007"
    )
    message = ask_assist.ensure_search_api(auto_start=True, wait_seconds=1)
    assert message is not None
    assert "자동 시작" in message


def test_ensure_search_api_starts_local_server(
    ask_assist: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """localhost API가 꺼져 있으면 rag serve를 한 번 시작하고 준비를 기다립니다."""
    started: list[tuple[Any, ...]] = []
    python = Path("C:/fake/.venv/Scripts/python.exe")
    monkeypatch.setattr(ask_assist, "search_available", lambda: False)
    monkeypatch.setattr(ask_assist, "port_open", lambda _host, _port: False)
    monkeypatch.setattr(ask_assist, "search_api_url", lambda: "http://127.0.0.1:8007")
    monkeypatch.setattr(ask_assist, "resolve_rag_python", lambda: (python, None))
    monkeypatch.setattr(
        ask_assist,
        "start_search_server",
        lambda exe, host, port: started.append((exe, host, port)),
    )
    monkeypatch.setattr(ask_assist, "wait_for_search", lambda _seconds: True)
    assert ask_assist.ensure_search_api(auto_start=True, wait_seconds=5) is None
    assert started == [(python, "127.0.0.1", 8007)]


def test_ensure_search_api_reports_missing_python(
    ask_assist: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """검색용 Python이 없으면 설치 안내를 반환합니다."""
    monkeypatch.setattr(ask_assist, "search_available", lambda: False)
    monkeypatch.setattr(ask_assist, "port_open", lambda _host, _port: False)
    monkeypatch.setattr(ask_assist, "search_api_url", lambda: "http://127.0.0.1:8007")
    monkeypatch.setattr(
        ask_assist,
        "resolve_rag_python",
        lambda: (None, ".venv에 rag/requirements.txt 를 설치하세요."),
    )
    message = ask_assist.ensure_search_api(auto_start=True, wait_seconds=1)
    assert message is not None
    assert "rag/requirements.txt" in message
