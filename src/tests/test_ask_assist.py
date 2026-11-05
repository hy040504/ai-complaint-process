"""민원 응대 CMD 스크립트의 질문 해석을 확인합니다."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

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
