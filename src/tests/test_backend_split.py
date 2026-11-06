"""민원 웹·RAG·LLM 패키지와 연결 계층이 분리돼 동작하는지 확인합니다."""

from src.assist import run_assist
from src.complaints.config import APP_SCHEMA_SQL
from src.llm import llm_configured, llm_settings
from src.rag import require_search_contract, search_parts


def _search() -> dict:
    """연결 계층 시험용 FAQ 검색 응답입니다."""
    return {
        "retrieval_only": True,
        "decision": "requires_gate",
        "elapsed_ms": 1,
        "pipeline": "test",
        "results": {
            "faq_knowledge": {
                "hits": [
                    {
                        "rank": 1,
                        "source_id": "faq-1",
                        "title": "대형폐기물 배출 방법",
                        "source_url": "https://example.test/faq-1",
                        "evidence": {
                            "detail": {
                                "target": "대형폐기물 배출자",
                                "processing_period": "평일 1~2일",
                                "warnings": "무단배출 과태료",
                                "main_content": "읍면동에서 신고 후 배출합니다.",
                            }
                        },
                    }
                ]
            },
            "routing_cases": {"hits": [], "department_candidates": []},
        },
    }


def test_app_schema_sql_lives_with_complaints() -> None:
    """업무 DDL이 민원 웹 패키지 아래에 있는지 확인합니다."""
    assert APP_SCHEMA_SQL.is_file()
    assert APP_SCHEMA_SQL.parent.name == "schema"
    assert APP_SCHEMA_SQL.parent.parent.name == "complaints"
    text = APP_SCHEMA_SQL.read_text(encoding="utf-8")
    assert "CREATE SCHEMA IF NOT EXISTS complaint_app" in text


def test_search_parts_indexes_faq_once() -> None:
    """검색 조각을 한 번 만들면 FAQ 색인과 부서 목록을 함께 얻습니다."""
    parts = search_parts(_search())
    assert len(parts.faqs) == 1
    assert parts.cases == []
    assert parts.departments == []
    assert parts.by_key[("faq", "faq-1")]["title"] == "대형폐기물 배출 방법"


def test_packages_are_importable() -> None:
    """세 백엔드 패키지와 연결 계층을 각각 가져올 수 있습니다."""
    import src.assist
    import src.complaints
    import src.llm
    import src.rag

    assert src.complaints.ComplaintService is not None
    assert src.rag.search_via_api is not None
    assert src.llm.complete_chat is not None
    assert src.assist.run_assist is not None


def test_bridge_runs_search_then_llm() -> None:
    """연결 계층이 검색 근거를 받은 뒤 LLM 판정으로 FAQ 안내를 만듭니다."""
    calls: list[str] = []

    def llm(system: str, user: str) -> str:
        calls.append(system)
        if "판정기" in system:
            return (
                '{"scope":"in_scope","intent":"information","outcome":"faq_answer",'
                '"reason_code":"ok","evidence_refs":[{"corpus":"faq","source_id":"faq-1"}],'
                '"department_ids":[]}'
            )
        return "대형폐기물 배출자는 읍면동에서 신고한 뒤 배출합니다. 처리기간은 평일 1~2일이며 무단배출 시 과태료가 있습니다."

    result = run_assist(
        "대형폐기물 배출 방법을 알고 싶어요.",
        search_fn=lambda query, district, limit, rerank: _search(),
        llm_fn=llm,
    )
    assert result["outcome"] == "faq_answer"
    assert result["handoff_required"] is False
    assert "과태료" in (result["answer"] or "")
    assert len(calls) == 2
    assert result["retrieval"]["retrieval_only"] is True
    assert result["retrieval"]["decision"] == "requires_gate"


def test_search_contract_helper_rejects_answers() -> None:
    """검색 클라이언트가 검색 전용 계약을 강제합니다."""
    try:
        require_search_contract({"retrieval_only": False, "decision": "answer"})
    except ValueError as exc:
        assert "requires_gate" in str(exc)
    else:
        raise AssertionError("검색 계약을 통과시키면 안 됩니다.")


def test_llm_settings_are_separate_from_search(monkeypatch: object) -> None:
    """LLM 설정은 검색 API 주소와 별도로 읽습니다."""
    monkeypatch.setenv("COMPLAINT_LLM_PROVIDER", "openai_api")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    assert llm_settings()["provider"] == "openai_api"
    assert llm_settings()["token"] is None
    assert llm_configured() is False
