"""한 문장 임베딩 스크립트의 인자·출력 형식을 확인합니다."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture(scope="module")
def embed_sentence() -> ModuleType:
    """scripts/문장_임베딩.py를 한 번만 불러옵니다."""
    path = Path(__file__).resolve().parents[2] / "scripts" / "문장_임베딩.py"
    spec = importlib.util.spec_from_file_location("embed_sentence", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resolve_text_joins_words(embed_sentence: ModuleType) -> None:
    """위치 인자를 한 문장으로 이어 붙입니다."""
    args = embed_sentence.parse_args(["나무가", "쓰러짐"])
    assert embed_sentence.resolve_text(args) == "나무가 쓰러짐"
    assert args.role == "query"


def test_resolve_text_rejects_empty(embed_sentence: ModuleType) -> None:
    """문장이 없으면 오류입니다."""
    args = embed_sentence.parse_args([])
    with pytest.raises(ValueError, match="문장"):
        embed_sentence.resolve_text(args)


def test_format_vector_raw_is_numbers_only(embed_sentence: ModuleType) -> None:
    """--raw 는 숫자만 공백으로 출력합니다."""
    meta = {
        "model": "demo",
        "revision": "abc",
        "dimension": 3,
        "role": "query",
        "prefix": "query: ",
        "text": "시험",
        "norm": 1.0,
    }
    text = embed_sentence.format_vector(
        [0.1, -0.2, 0.3], raw=True, as_json=False, meta=meta
    )
    assert text.startswith("0.10000000")
    assert "모델" not in text


def test_format_vector_json_includes_vector(embed_sentence: ModuleType) -> None:
    """--json 은 벡터 배열을 포함합니다."""
    meta = {
        "model": "demo",
        "revision": "abc",
        "dimension": 2,
        "role": "passage",
        "prefix": "passage: ",
        "text": "시험",
        "norm": 1.0,
    }
    payload = embed_sentence.format_vector(
        [0.25, 0.75], raw=False, as_json=True, meta=meta
    )
    assert '"dimension": 2' in payload
    assert "0.25" in payload


def test_format_vector_text_includes_meta(embed_sentence: ModuleType) -> None:
    """기본 출력은 모델·문장·노름과 벡터를 함께 보여 줍니다."""
    meta = {
        "model": "demo",
        "revision": "abc",
        "dimension": 2,
        "role": "query",
        "prefix": "query: ",
        "text": "시험",
        "norm": 1.0,
    }
    text = embed_sentence.format_vector(
        [0.25, 0.75], raw=False, as_json=False, meta=meta
    )
    assert "모델: demo" in text
    assert "문장: 시험" in text
    assert "노름: 1.00000000" in text
    assert "0.25000000" in text
