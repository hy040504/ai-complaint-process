"""PREFIX-03 담당자 초안과 PREFIX-04 순화 요약을 검사·조립합니다.

시민 세 갈래 판정을 바꾸지 않습니다. 민원 CRUD 테이블에도 쓰지 않습니다.
PREFIX-04는 검색 도구를 부르지 않으며, 원문 힌트가 있을 때만 호출합니다.
"""

from __future__ import annotations

from typing import Any

from src.assist.constants import CORPORA
from src.assist.policy import decision_payload
from src.rag.evidence import SearchParts

RISK_SIGNALS = (
    "profanity_insult",
    "threat_intimidation",
    "sexual_harassment",
    "repeated_obsession",
    "legal_threat",
    "excessive_personal_info_demand",
    "urgent_safety_hazard",
    "discretionary_disposition_pressure",
)

SANITIZE_HINTS = (
    "씨발",
    "시발",
    "개새끼",
    "꺼져",
    "죽어",
    "패죽",
    "협박",
    "고발하겠다",
    "미친놈",
    "쓰레기같은",
    "조져",
    "병신",
)


def needs_sanitize(query: str) -> bool:
    """원문에 순화 호출을 켤 표현이 있는지 봅니다.

    Args:
        query: 민원 원문입니다.

    Returns:
        힌트 문자열이 하나라도 있으면 True입니다.
    """
    text = query or ""
    return any(hint in text for hint in SANITIZE_HINTS)


def sanitize_payload(query: str) -> dict[str, Any]:
    """순화 호출의 사용자 JSON을 만듭니다.

    검색 후보는 넣지 않습니다. PREFIX-04는 원문만 다룹니다.

    Args:
        query: 민원 원문입니다.

    Returns:
        `query`만 담은 딕셔너리입니다.
    """
    return {"query": query}


def validate_sanitize(raw: dict[str, Any]) -> dict[str, Any] | None:
    """순화 JSON을 허용 목록으로 검사합니다.

    Args:
        raw: 모델이 반환한 객체입니다.

    Returns:
        검증된 순화 결과입니다. 스키마가 아니면 None입니다.
    """
    summary = raw.get("sanitized_summary")
    requests = raw.get("legitimate_requests")
    signals = raw.get("risk_signals")
    review = raw.get("human_protection_review_needed")
    if not isinstance(summary, str) or len(summary.strip()) < 10:
        return None
    if not isinstance(requests, list) or not all(
        isinstance(item, str) and item.strip() for item in requests
    ):
        return None
    if not isinstance(signals, list) or not all(
        item in RISK_SIGNALS for item in signals
    ):
        return None
    if not isinstance(review, bool):
        return None
    return {
        "sanitized_summary": summary.strip(),
        "legitimate_requests": [item.strip() for item in requests],
        "risk_signals": list(signals),
        "human_protection_review_needed": review,
    }


def staff_draft_payload(
    query: str,
    district: str | None,
    search: dict[str, Any],
    decision: dict[str, Any],
    parts: SearchParts | None = None,
    inferred_place: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """담당자 초안 호출의 사용자 JSON을 만듭니다.

    검색 후보가 이미 있으므로 PREFIX-03은 도구를 다시 부르지 않습니다.

    Args:
        query: 민원 원문입니다.
        district: 명시한 관할 구입니다.
        search: 검색 API 응답입니다.
        decision: 코드 검증을 거친 판정입니다.
        parts: 이미 구한 검색 조각입니다.
        inferred_place: 네이버 지도로 추론된 장소 객체입니다.

    Returns:
        판정 갈래와 검색 후보를 담은 딕셔너리입니다.
    """
    payload = decision_payload(query, district, search, parts, inferred_place=inferred_place)
    result = {
        "query": payload["query"],
        "district": payload["district"],
        "outcome": decision.get("outcome"),
        "reason_code": decision.get("reason_code"),
        "faq_candidates": payload["faq_candidates"],
        "case_candidates": payload["case_candidates"],
        "department_candidates": payload["department_candidates"],
    }
    if inferred_place:
        result["inferred_place"] = inferred_place
    return result


def validate_staff_draft(
    raw: dict[str, Any],
    parts: SearchParts,
) -> dict[str, Any] | None:
    """담당자 초안 JSON을 검사하고 입력에 있는 출처만 남깁니다.

    Args:
        raw: 모델이 반환한 객체입니다.
        parts: 검색 조각입니다.

    Returns:
        검증된 초안입니다. 스키마가 아니면 None입니다.
    """
    card = raw.get("summary_card")
    draft = raw.get("draft_answer")
    citations = raw.get("citations")
    field_check = raw.get("requires_field_check")
    if not isinstance(card, dict):
        return None
    core = card.get("core_summary")
    request = card.get("citizen_request")
    location = card.get("location_or_target")
    missing = card.get("missing_info")
    if not isinstance(core, str) or not core.strip():
        return None
    if not isinstance(request, str) or not request.strip():
        return None
    if not isinstance(location, str):
        return None
    if not isinstance(missing, list) or not all(
        isinstance(item, str) for item in missing
    ):
        return None
    if not isinstance(draft, str) or len(draft.strip()) < 20:
        return None
    if not isinstance(citations, list):
        return None
    if not isinstance(field_check, bool):
        return None
    kept: list[dict[str, str]] = []
    for item in citations:
        if not isinstance(item, dict):
            continue
        corpus = item.get("corpus")
        source_id = item.get("source_id")
        if corpus not in CORPORA or not isinstance(source_id, str):
            continue
        if (corpus, source_id) not in parts.by_key:
            continue
        kept.append({"corpus": corpus, "source_id": source_id})
    return {
        "summary_card": {
            "core_summary": core.strip(),
            "citizen_request": request.strip(),
            "location_or_target": location.strip(),
            "missing_info": [item.strip() for item in missing if item.strip()],
        },
        "draft_answer": draft.strip(),
        "citations": kept,
        "requires_field_check": field_check,
    }
