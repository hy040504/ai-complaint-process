"""가벼운 임베딩 기본값과 질문·문서 접두, 스키마 차원 치환을 확인합니다."""

import pytest

from rag.config import (
    DIMENSION,
    EMBEDDING_MODEL,
    EMBEDDING_PASSAGE_PREFIX,
    EMBEDDING_QUERY_PREFIX,
    prefixed_texts,
    schema_sql,
)


def test_default_embedding_is_cpu_e5_small() -> None:
    """기본 프로필은 한국어 미세조정 e5-small 384차원입니다."""
    assert EMBEDDING_MODEL == "dragonkue/multilingual-e5-small-ko"
    assert DIMENSION == 384
    assert EMBEDDING_QUERY_PREFIX == "query: "
    assert EMBEDDING_PASSAGE_PREFIX == "passage: "


def test_prefixed_texts_adds_e5_role() -> None:
    """e5는 질문과 문서에 서로 다른 접두를 붙입니다."""
    assert prefixed_texts(["대형폐기물"], "query") == ["query: 대형폐기물"]
    assert prefixed_texts(["대형폐기물"], "passage") == ["passage: 대형폐기물"]


def test_prefixed_texts_rejects_unknown_role() -> None:
    """query/passage 이외의 역할은 거절합니다."""
    with pytest.raises(ValueError, match="query 또는 passage"):
        prefixed_texts(["대형폐기물"], "document")


def test_schema_sql_uses_current_dimension() -> None:
    """검색 스키마 DDL의 벡터 차원이 현재 설정과 같습니다."""
    sql = schema_sql()
    assert f"vector({DIMENSION})" in sql
    assert "__EMBEDDING_DIM__" not in sql
    assert "embedding_cache" in sql


def test_schema_sql_is_cached() -> None:
    """스키마 파일은 같은 프로세스에서 다시 읽지 않습니다."""
    first = schema_sql()
    second = schema_sql()
    assert first == second
    assert schema_sql.cache_info().hits >= 1
