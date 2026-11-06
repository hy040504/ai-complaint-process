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


def test_shape_neighbors_keeps_faq_and_routing_apart(
    embed_sentence: ModuleType,
) -> None:
    """FAQ에는 부서 필드를 넣지 않고, 근거 없는 사례는 확정 후보가 아닙니다."""
    faq = embed_sentence.shape_neighbors(
        "faq",
        [{"source_id": "F1", "score": 0.8}],
        {
            "F1": {
                "source_id": "F1",
                "title": "배출",
                "source_url": "https://example.test/faq",
                "search_text": "대형폐기물 안내",
            }
        },
    )
    case = embed_sentence.shape_neighbors(
        "routing",
        [{"source_id": "C1", "score": 0.4}],
        {
            "C1": {
                "source_id": "C1",
                "title": "과거 민원",
                "source_url": "https://example.test/case",
                "search_text": "요지",
                "routing_eligible": False,
                "canonical_name": None,
            }
        },
    )
    assert "department_name" not in faq[0]
    assert faq[0]["excerpt"] == "대형폐기물 안내"
    assert case[0]["routing_eligible"] is False
    report = embed_sentence.format_neighbors({"faq": faq, "routing": case})
    assert "[FAQ]" in report
    assert "[공개 사례]" in report
    assert "부서 확정 근거에서 제외" in report
    assert "0.8000" in report


def test_format_vector_json_includes_neighbors(embed_sentence: ModuleType) -> None:
    """이웃을 넣으면 JSON에 검색 전용 계약을 붙입니다."""
    meta = {
        "model": "demo",
        "revision": "abc",
        "dimension": 1,
        "role": "query",
        "prefix": "query: ",
        "text": "시험",
        "norm": 1.0,
    }
    payload = embed_sentence.format_vector(
        [0.5],
        raw=False,
        as_json=True,
        meta=meta,
        neighbors={"faq": [], "routing": []},
    )
    assert '"retrieval_only": true' in payload
    assert '"decision": "requires_gate"' in payload
    assert '"neighbors"' in payload


def test_parse_args_search_defaults(embed_sentence: ModuleType) -> None:
    """기본은 pgvector 이웃 5건이고, raw는 숫자만 출력하는 선택입니다."""
    args = embed_sentence.parse_args(["가로등"])
    assert args.no_search is False
    assert args.raw is False
    assert args.limit == 5
    raw = embed_sentence.parse_args(["--raw", "--no-search", "가로등"])
    assert raw.raw is True
    assert raw.no_search is True
