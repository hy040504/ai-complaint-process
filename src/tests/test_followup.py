"""PREFIX-03·04 검사와 파이프라인 후속 호출을 확인합니다."""

from __future__ import annotations

from src.assist.followup import (
    needs_sanitize,
    sanitize_payload,
    validate_sanitize,
    validate_staff_draft,
)
from src.assist.pipeline import run_assist
from src.rag import search_parts


def _search() -> dict:
    """FAQ 한 건이 있는 합성 검색 응답입니다."""
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


def test_needs_sanitize_only_on_hints() -> None:
    """힌트 문자열이 있을 때만 순화 호출을 켭니다."""
    assert needs_sanitize("쓰레기같은 가로등을 지금 고쳐 주세요.") is True
    assert needs_sanitize("대형폐기물 배출 방법이 궁금합니다.") is False


def test_sanitize_payload_has_query_only() -> None:
    """순화 사용자 JSON에는 검색 후보를 넣지 않습니다."""
    payload = sanitize_payload("쓰레기같은 가로등")
    assert list(payload) == ["query"]


def test_validate_sanitize_rejects_unknown_signals() -> None:
    """허용 목록 밖 위험 배지는 버립니다."""
    assert (
        validate_sanitize(
            {
                "sanitized_summary": "가로등 수리를 요청합니다.",
                "legitimate_requests": ["가로등 수리"],
                "risk_signals": ["ban_citizen"],
                "human_protection_review_needed": True,
            }
        )
        is None
    )


def test_validate_staff_draft_drops_unknown_citations() -> None:
    """검색에 없는 출처는 초안에서 뺍니다."""
    parts = search_parts(_search())
    draft = validate_staff_draft(
        {
            "summary_card": {
                "core_summary": "대형폐기물 배출 안내가 필요합니다.",
                "citizen_request": "배출 방법 안내",
                "location_or_target": "흥덕구",
                "missing_info": [],
            },
            "draft_answer": "읍면동에서 신고한 뒤 배출하시면 됩니다. 담당자 확인이 필요합니다.",
            "citations": [
                {"corpus": "faq", "source_id": "faq-1"},
                {"corpus": "faq", "source_id": "missing"},
            ],
            "requires_field_check": True,
        },
        parts,
    )
    assert draft is not None
    assert draft["citations"] == [{"corpus": "faq", "source_id": "faq-1"}]


def test_run_assist_staff_draft_on_handoff() -> None:
    """FAQ가 아닌 갈래는 담당자 초안을 한 번 더 호출합니다."""
    calls: list[str] = []

    def llm(system: str, user: str) -> str:
        calls.append(system)
        if "판정기" in system:
            return (
                '{"scope":"in_scope","intent":"action","outcome":"human_handoff",'
                '"reason_code":"action_required","evidence_refs":[],'
                '"department_ids":[]}'
            )
        if "순화" in system:
            raise AssertionError("힌트 없는 민원에 순화를 호출했습니다.")
        return (
            '{"summary_card":{"core_summary":"가로등 수리를 요청합니다.",'
            '"citizen_request":"가로등 수리","location_or_target":"흥덕구",'
            '"missing_info":["정확한 위치"]},'
            '"draft_answer":"[담당자 확인 필요: 현장 점검 예정일/조치 계획 입력] '
            '가로등 점검을 검토하겠습니다.",'
            '"citations":[{"corpus":"faq","source_id":"faq-1"}],'
            '"requires_field_check":true}'
        )

    result = run_assist(
        "우리집 앞 가로등이 밤새 깜빡거려 수리를 요청합니다.",
        "흥덕구",
        search_fn=lambda query, district, limit, rerank: _search(),
        llm_fn=llm,
    )
    assert result["outcome"] == "human_handoff"
    assert result["staff_draft"]["citations"][0]["source_id"] == "faq-1"
    assert result["sanitize"] is None
    assert [item["role"] for item in result["codex"]] == ["decision", "staff_draft"]
    assert len(calls) == 2
    assert "자동 이관" in (result["answer"] or "") or "담당자" in (
        result["answer"] or ""
    )
    assert result["staff_draft"]["draft_answer"] not in (result["answer"] or "")


def test_run_assist_sanitize_then_staff_draft() -> None:
    """힌트가 있으면 순화 다음 담당자 초안을 호출합니다."""
    calls: list[str] = []

    def llm(system: str, user: str) -> str:
        calls.append(system)
        if "판정기" in system:
            return (
                '{"scope":"in_scope","intent":"action","outcome":"human_handoff",'
                '"reason_code":"action_required","evidence_refs":[],'
                '"department_ids":[]}'
            )
        if "순화" in system:
            assert "faq_candidates" not in user
            return (
                '{"sanitized_summary":"가로등 수리를 요청하는 민원입니다.",'
                '"legitimate_requests":["가로등 수리"],'
                '"risk_signals":["profanity_insult"],'
                '"human_protection_review_needed":true}'
            )
        return (
            '{"summary_card":{"core_summary":"가로등 수리를 요청합니다.",'
            '"citizen_request":"가로등 수리","location_or_target":"",'
            '"missing_info":[]},'
            '"draft_answer":"[담당자 확인 필요: 현장 점검 예정일/조치 계획 입력] '
            '점검을 검토하겠습니다.",'
            '"citations":[],'
            '"requires_field_check":true}'
        )

    result = run_assist(
        "쓰레기같은 가로등을 지금 고쳐 주세요.",
        search_fn=lambda query, district, limit, rerank: _search(),
        llm_fn=llm,
    )
    assert result["sanitize"]["risk_signals"] == ["profanity_insult"]
    assert result["staff_draft"] is not None
    assert [item["role"] for item in result["codex"]] == [
        "decision",
        "sanitize",
        "staff_draft",
    ]
    assert len(calls) == 3
