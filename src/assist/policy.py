"""LLM 판정을 검색 근거와 대조하는 코드 정책 검사입니다."""

from __future__ import annotations

import json
from typing import Any

from src.assist.constants import (
    CORPORA,
    HANDOFF_REASONS,
    INTENTS,
    OUTCOMES,
    REASON_CODES,
    SCOPES,
)
from src.rag.evidence import (
    SearchParts,
    compact_case,
    compact_faq,
    department_candidates,
    hit_excerpt,
    search_parts,
)


def empty_decision(reason: str) -> dict[str, Any]:
    """검증 실패 시 담당자 검토 판정을 만듭니다.

    Args:
        reason: `REASON_CODES`에 있는 사유 코드입니다. 없으면 `invalid_model_output`입니다.

    Returns:
        `human_handoff` 판정 딕셔너리입니다.
    """
    return {
        "scope": "uncertain",
        "intent": "unclear",
        "outcome": "human_handoff",
        "reason_code": reason if reason in REASON_CODES else "invalid_model_output",
        "evidence_refs": [],
        "department_ids": [],
    }


def decision_payload(
    query: str,
    district: str | None,
    search: dict[str, Any],
    parts: SearchParts | None = None,
) -> dict[str, Any]:
    """판정에 넘길 민원·검색 후보 딕셔너리를 만듭니다.

    시스템 지시와 섞지 않는 가변 접미입니다. 키 순서는
    `query` → `district` → FAQ·사례·부서 후보로 고정합니다.
    검색 전용 계약 표식은 여기 넣지 않습니다.

    Args:
        query: 한국어 민원 원문입니다.
        district: 명시한 관할 구입니다.
        search: 검색 API 응답입니다.
        parts: 이미 구한 검색 조각입니다. 생략하면 `search`에서 한 번 만듭니다.

    Returns:
        FAQ·사례·부서 후보를 담은 딕셔너리입니다.
    """
    data = parts or search_parts(search)
    return {
        "query": query,
        "district": district,
        "faq_candidates": [compact_faq(hit) for hit in data.faqs],
        "case_candidates": [compact_case(hit) for hit in data.cases],
        "department_candidates": [
            {
                "department_id": item.get("department_id"),
                "canonical_name": item.get("canonical_name"),
                "district": item.get("district"),
                "duty_status": item.get("duty_status"),
                "jurisdiction_status": item.get("jurisdiction_status"),
                "supporting_case_ids": [
                    case.get("source_id") for case in item.get("supporting_cases") or []
                ],
            }
            for item in data.departments
        ],
    }


def decision_prompt(
    query: str,
    district: str | None,
    search: dict[str, Any],
    parts: SearchParts | None = None,
) -> str:
    """판정 JSON만 요청하는 사용자 본문을 구성합니다.

    Args:
        query: 한국어 민원 원문입니다.
        district: 명시한 관할 구입니다.
        search: 검색 API 응답입니다.
        parts: 이미 구한 검색 조각입니다. 생략하면 `search`에서 한 번 만듭니다.

    Returns:
        `decision_payload`를 들여쓴 JSON 문자열입니다.
    """
    return json.dumps(
        decision_payload(query, district, search, parts),
        ensure_ascii=False,
        indent=2,
    )


def validate_decision(
    raw: dict[str, Any],
    search: dict[str, Any],
    parts: SearchParts | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """모델 판정을 검색 근거·부서 후보와 대조합니다.

    Args:
        raw: 모델이 반환한 객체입니다.
        search: 검색 API 응답입니다.
        parts: 이미 구한 검색 조각입니다. 생략하면 `search`에서 한 번 만듭니다.

    Returns:
        교정된 판정과 정책 실패 사유 목록입니다.
    """
    failures: list[str] = []
    data = parts or search_parts(search)
    departments = {str(item.get("department_id")): item for item in data.departments}
    scope = raw.get("scope") if raw.get("scope") in SCOPES else None
    intent = raw.get("intent") if raw.get("intent") in INTENTS else None
    outcome = raw.get("outcome") if raw.get("outcome") in OUTCOMES else None
    reason = raw.get("reason_code") if raw.get("reason_code") in REASON_CODES else "ok"
    if scope is None:
        failures.append("scope 값이 허용 목록에 없습니다.")
        scope = "uncertain"
    if intent is None:
        failures.append("intent 값이 허용 목록에 없습니다.")
        intent = "unclear"
    if outcome is None:
        failures.append("outcome 값이 허용 목록에 없습니다.")
        outcome = "human_handoff"

    refs: list[dict[str, str]] = []
    for item in raw.get("evidence_refs") or []:
        if not isinstance(item, dict):
            failures.append("evidence_refs 항목 형식이 잘못되었습니다.")
            continue
        corpus = item.get("corpus")
        source_id = str(item.get("source_id") or "")
        if corpus not in CORPORA or not source_id:
            failures.append("근거 키 corpus/source_id가 올바르지 않습니다.")
            continue
        if (corpus, source_id) not in data.by_key:
            failures.append(f"검색에 없는 근거입니다: {corpus}/{source_id}")
            continue
        refs.append({"corpus": corpus, "source_id": source_id})

    dept_ids: list[str] = []
    for item in raw.get("department_ids") or []:
        key = str(item)
        if key not in departments:
            failures.append(f"유효 후보가 아닌 부서입니다: {key}")
            continue
        dept_ids.append(key)

    if intent == "mixed":
        outcome = "human_handoff"
        reason = "mixed_request"
        failures.append("복합 요청은 담당자 검토로 연결합니다.")
    if scope in ("out_of_scope", "uncertain") and outcome == "faq_answer":
        outcome = "human_handoff"
        reason = "out_of_scope" if scope == "out_of_scope" else "insufficient_evidence"
        failures.append("범위 밖·불확실 판정은 FAQ 자동 안내를 허용하지 않습니다.")
    if intent == "action" and outcome == "faq_answer":
        outcome = "department_suggestion" if dept_ids else "human_handoff"
        reason = "action_required"
        failures.append("실제 조치 요청을 FAQ 안내만으로 종결하지 않습니다.")
    if outcome == "faq_answer":
        if intent != "information":
            outcome = "human_handoff"
            reason = "policy_rejected"
            failures.append("FAQ 안내는 information 의도에만 허용합니다.")
        elif not any(ref["corpus"] == "faq" for ref in refs):
            outcome = "human_handoff"
            reason = "insufficient_evidence"
            failures.append("FAQ 안내에는 FAQ 근거가 필요합니다.")
    if outcome == "department_suggestion" and not dept_ids:
        outcome = "human_handoff"
        reason = "department_unverified"
        failures.append("부서 추천에는 유효한 부서 후보가 필요합니다.")
    if outcome == "human_handoff" and reason == "ok":
        reason = "insufficient_evidence"

    decision = {
        "scope": scope,
        "intent": intent,
        "outcome": outcome,
        "reason_code": reason,
        "evidence_refs": refs,
        "department_ids": dept_ids,
    }
    return decision, failures


def citizen_answer(
    decision: dict[str, Any],
    search: dict[str, Any],
    generated: str | None,
    departments: list[dict[str, Any]] | None = None,
) -> str | None:
    """시민에게 보여줄 문장을 판정 갈래에 맞게 고릅니다.

    Args:
        decision: 정책 검사를 통과한 판정입니다.
        search: 검색 응답입니다.
        generated: FAQ 생성 결과입니다.
        departments: 이미 구한 부서 후보입니다. 생략하면 검색 응답에서 다시 읽습니다.

    Returns:
        안내 문장 또는 None입니다. 부서 추천·인계는 템플릿입니다.
    """
    outcome = decision["outcome"]
    if outcome == "faq_answer":
        return generated
    if outcome == "department_suggestion":
        names = []
        by_id = {
            str(item.get("department_id")): item
            for item in (
                departments
                if departments is not None
                else department_candidates(search)
            )
        }
        for dept_id in decision["department_ids"]:
            item = by_id.get(dept_id) or {}
            label = item.get("canonical_name") or dept_id
            duty = item.get("duty_status") or "unknown"
            names.append(f"- {label} (업무분장: {duty}, 자동 이관 아님)")
        return (
            "유사한 공개 사례를 기준으로 담당 부서 후보를 안내합니다. "
            "공식 접수·이관이 아니며 담당자 확인이 필요합니다.\n" + "\n".join(names)
        )
    return HANDOFF_REASONS.get(
        decision["reason_code"], HANDOFF_REASONS["insufficient_evidence"]
    )


def public_hit(hit: dict[str, Any], corpus: str) -> dict[str, Any]:
    """검사기·CLI에 보여줄 근거 한 건을 만듭니다.

    Args:
        hit: 검색 히트입니다.
        corpus: faq 또는 routing입니다.

    Returns:
        순위·제목·발췌·부서 이름을 담은 표시용 객체입니다.
    """
    department = hit.get("department") or {}
    return {
        "rank": hit.get("rank"),
        "source_id": hit.get("source_id"),
        "title": hit.get("title"),
        "source_url": hit.get("source_url"),
        "excerpt": hit_excerpt(hit),
        "corpus": corpus,
        "routing_eligible": hit.get("routing_eligible"),
        "department_name": department.get("canonical_name"),
        "department_status": hit.get("department_status"),
    }
