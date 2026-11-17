"""문맥 기반 욕설·비꼬기(PREFIX-04) 파이프라인 연계 단위 테스트입니다."""

from __future__ import annotations

import json
from typing import Any

import pytest

from src.assist.followup import validate_sanitize
from src.assist.pipeline import run_assist


def _mock_search(
    query: str,
    district: str | None = None,
    limit: int = 5,
    rerank: bool = True,
) -> dict[str, Any]:
    """실제 DB 없이 최소 검색 계약을 반환하는 스텁입니다."""
    return {
        "query": query,
        "district": district,
        "limit": limit,
        "rerank": rerank,
        "retrieval_only": True,
        "decision": "requires_gate",
        "elapsed_ms": 1.0,
        "pipeline": "mock",
        "results": {
            "faq_knowledge": {"hits": []},
            "routing_cases": {
                "hits": [
                    {
                        "rank": 1,
                        "source_id": "case-demo-1",
                        "title": "공원 화장실 위생 민원",
                        "snippet": "공원 내 화장실 청결 정비 요청",
                        "department_current": "상당구 공원녹지과",
                        "review_required": False,
                    }
                ],
                "department_candidates": [
                    {
                        "department_id": "dept-demo-1",
                        "canonical_name": "청주시 상당구 공원녹지과",
                        "district": "상당구",
                        "duty_status": "verified",
                        "jurisdiction_status": "verified",
                        "supporting_cases": [{"source_id": "case-demo-1"}],
                    }
                ],
            },
        },
    }


def test_validate_sanitize_accepts_sarcasm_mockery_without_forced_protection_flag() -> (
    None
):
    """경미한 비꼬기 민원에서 sarcasm_mockery와 protection=False 조합을 허용합니다."""
    parsed = validate_sanitize(
        {
            "sanitized_summary": "문암생태공원 공중화장실 위생 상태에 대한 불만을 제기하며 청소를 요청했습니다.",
            "legitimate_requests": ["문암생태공원 공중화장실 청소 및 위생 점검"],
            "risk_signals": ["sarcasm_mockery"],
            "human_protection_review_needed": False,
        }
    )
    assert parsed is not None
    assert parsed["risk_signals"] == ["sarcasm_mockery"]
    assert parsed["human_protection_review_needed"] is False


def test_run_assist_runs_sanitize_on_pure_sarcasm_and_skips_facility_outage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """키워드가 없어도 문맥이 비꼬기면 순화를 켜고, 시설물 '꺼져'면 끕니다."""
    monkeypatch.setattr(
        "src.assist.pipeline.resolve_district_and_place",
        lambda d, _q: (d or "상당구", False, None),
    )
    sarcasm_calls: list[str] = []

    def sarcasm_llm(system: str, _user: str) -> str:
        """순수 비꼬기 민원에서 PREFIX-01·04·03 응답을 순서대로 모사합니다."""
        if "1차 판정기" in system:
            sarcasm_calls.append("decision")
            return json.dumps(
                {
                    "scope": "in_scope",
                    "intent": "action",
                    "outcome": "department_suggestion",
                    "reason_code": "action_required",
                    "evidence_refs": [
                        {"corpus": "routing", "source_id": "case-demo-1"}
                    ],
                    "department_ids": ["dept-demo-1"],
                    "sanitize_needed": True,
                },
                ensure_ascii=False,
            )
        if "sarcasm_mockery" in system:
            sarcasm_calls.append("sanitize")
            return json.dumps(
                {
                    "sanitized_summary": "공원 공중화장실 위생 점검과 즉각적인 청소 조치를 요청했습니다.",
                    "legitimate_requests": ["공원 화장실 위생 점검 및 청소"],
                    "risk_signals": ["sarcasm_mockery"],
                    "human_protection_review_needed": False,
                },
                ensure_ascii=False,
            )
        sarcasm_calls.append("draft")
        return json.dumps(
            {
                "summary_card": {
                    "core_summary": "공원 화장실 위생 개선 요청",
                    "citizen_request": "화장실 청소 조치",
                    "location_or_target": "문암생태공원",
                    "missing_info": [],
                },
                "draft_answer": "현장 청소 점검 후 조치하겠습니다.",
                "citations": [{"corpus": "routing", "source_id": "case-demo-1"}],
                "requires_field_check": True,
            },
            ensure_ascii=False,
        )

    sarcasm_result = run_assist(
        "문암생태공원 화장실이 변기 전시회처럼 유지되네요^^ 대단합니다.",
        district="상당구",
        search_fn=_mock_search,
        llm_fn=sarcasm_llm,
    )
    assert "sanitize" in sarcasm_calls
    assert sarcasm_result["sanitize"] is not None
    assert sarcasm_result["sanitize"]["risk_signals"] == ["sarcasm_mockery"]

    facility_calls: list[str] = []

    def facility_llm(system: str, _user: str) -> str:
        """시설물 고장 표현('꺼져')에서 순화를 건너뛰고 초안만 생성하도록 모사합니다."""
        if "1차 판정기" in system:
            facility_calls.append("decision")
            return json.dumps(
                {
                    "scope": "in_scope",
                    "intent": "action",
                    "outcome": "department_suggestion",
                    "reason_code": "action_required",
                    "evidence_refs": [
                        {"corpus": "routing", "source_id": "case-demo-1"}
                    ],
                    "department_ids": ["dept-demo-1"],
                    "sanitize_needed": False,
                },
                ensure_ascii=False,
            )
        if "sarcasm_mockery" in system:
            facility_calls.append("sanitize")
            raise AssertionError(
                "시설물 고장 표현에서는 PREFIX-04 순화를 호출하면 안 됩니다."
            )
        facility_calls.append("draft")
        return json.dumps(
            {
                "summary_card": {
                    "core_summary": "가로등 소등 수리 요청",
                    "citizen_request": "가로등 점등 복구",
                    "location_or_target": "사직대로 부근",
                    "missing_info": [],
                },
                "draft_answer": "현장 확인 후 가로등을 수리하겠습니다.",
                "citations": [{"corpus": "routing", "source_id": "case-demo-1"}],
                "requires_field_check": True,
            },
            ensure_ascii=False,
        )

    facility_result = run_assist(
        "집 앞 가로등이 어젯밤부터 꺼져 있어서 밤길이 어둡습니다.",
        district="상당구",
        search_fn=_mock_search,
        llm_fn=facility_llm,
    )
    assert "sanitize" not in facility_calls
    assert facility_result["sanitize"] is None
