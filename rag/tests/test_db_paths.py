"""검색 원본·스키마 경로가 코드 상수와 맞는지 확인합니다."""

from rag.config import CASES_JSON, FAQ_JSON, ORIGIN_DIR, RAG_SCHEMA_SQL


def test_project_origin_files_are_under_rag_origin():
    """검색 원본 JSON과 스키마 SQL이 rag/origin 아래에 있는지 확인합니다."""
    assert ORIGIN_DIR.name == "origin"
    assert ORIGIN_DIR.parent.name == "rag"
    assert FAQ_JSON.is_file()
    assert CASES_JSON.is_file()
    assert RAG_SCHEMA_SQL.is_file()
    assert FAQ_JSON.parent == ORIGIN_DIR
    assert RAG_SCHEMA_SQL.parent == ORIGIN_DIR / "schema"
    text = RAG_SCHEMA_SQL.read_text(encoding="utf-8")
    assert "CREATE SCHEMA IF NOT EXISTS complaint_rag" in text
    assert "CREATE TABLE IF NOT EXISTS complaint_rag.faq_knowledge" in text
