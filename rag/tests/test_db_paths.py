"""프로젝트 db/ 원본·스키마 경로가 코드 상수와 맞는지 확인합니다."""

from rag.config import APP_SCHEMA_SQL, CASES_JSON, FAQ_JSON, RAG_SCHEMA_SQL


def test_project_db_files_are_in_db_directory():
    """검색 원본 JSON과 스키마 SQL이 db/ 아래에 있는지 확인합니다."""
    assert FAQ_JSON.is_file()
    assert CASES_JSON.is_file()
    assert RAG_SCHEMA_SQL.is_file()
    assert APP_SCHEMA_SQL.is_file()
    text = RAG_SCHEMA_SQL.read_text(encoding="utf-8")
    assert "CREATE SCHEMA IF NOT EXISTS complaint_rag" in text
    assert "CREATE TABLE IF NOT EXISTS complaint_rag.faq_knowledge" in text
    app = APP_SCHEMA_SQL.read_text(encoding="utf-8")
    assert "CREATE SCHEMA complaint_app" in app
