"""검색 도구와 MCP 프레임이 민원 문장만 넘기는지 확인합니다."""

from __future__ import annotations

import io

from src.llm.rag_mcp import dispatch, read_message, write_message
from src.llm.rag_tool import search_complaint_rag


def test_search_complaint_rag_rejects_empty_or_unknown_district() -> None:
    """빈 문장과 허용 밖 구 이름은 검색 API를 호출하지 않습니다."""
    called = {"n": 0}

    def fetch(*_args: object, **_kwargs: object) -> dict:
        called["n"] += 1
        return {}

    try:
        search_complaint_rag("  ", search_fn=fetch)
    except ValueError as exc:
        assert "비어" in str(exc)
    else:
        raise AssertionError("빈 문장을 통과시켰습니다.")
    try:
        search_complaint_rag("가로등", "서울", search_fn=fetch)
    except ValueError as exc:
        assert "district" in str(exc)
    else:
        raise AssertionError("다른 지역을 통과시켰습니다.")
    assert called["n"] == 0


def test_search_complaint_rag_returns_gate_contract() -> None:
    """도구 결과는 판정용 후보이고 검색 전용 계약을 유지합니다."""

    def fetch(query: str, district: str | None, **_kwargs: object) -> dict:
        assert query == "대형폐기물"
        assert district == "상당구"
        return {
            "retrieval_only": True,
            "decision": "requires_gate",
            "results": {
                "faq_knowledge": {
                    "hits": [
                        {
                            "source_id": "faq-1",
                            "title": "스티커",
                            "evidence": {
                                "detail": {
                                    "target": "가정",
                                    "processing_period": "즉시",
                                    "warnings": "수수료",
                                }
                            },
                        }
                    ]
                },
                "routing_cases": {"hits": [], "department_candidates": []},
            },
        }

    payload = search_complaint_rag("대형폐기물", "상당구", search_fn=fetch)
    assert payload["retrieval_only"] is True
    assert payload["decision"] == "requires_gate"
    assert payload["faq_candidates"][0]["detail"]["warnings"] == "수수료"
    assert payload["case_candidates"] == []


def test_mcp_lists_only_the_search_tool() -> None:
    """MCP 목록에는 검색 도구만 있고 다른 메서드는 거절합니다."""
    listed = dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = [item["name"] for item in listed["result"]["tools"]]
    assert names == ["search_complaint_rag"]
    denied = dispatch(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "shell", "arguments": {}},
        }
    )
    assert denied["result"]["isError"] is True
    assert dispatch({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_mcp_frame_roundtrip() -> None:
    """Content-Length 프레임으로 초기화 응답을 주고받습니다."""
    incoming = io.BytesIO()
    write_message(
        incoming,
        {"jsonrpc": "2.0", "id": 7, "method": "initialize", "params": {}},
    )
    incoming.seek(0)
    message = read_message(incoming)
    assert message is not None
    response = dispatch(message)
    assert response is not None
    assert response["id"] == 7
    assert response["result"]["serverInfo"]["name"] == "complaint-rag"
