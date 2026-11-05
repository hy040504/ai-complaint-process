"""검색 응답에서 FAQ·사례·부서 후보를 꺼내는 도우미입니다."""

from __future__ import annotations

from typing import Any, NamedTuple


class SearchParts(NamedTuple):
    """검색 응답에서 한 번에 꺼낸 FAQ·사례·부서 후보와 근거 색인입니다.

    Attributes:
        faqs: `faq_knowledge.hits` 목록입니다.
        cases: `routing_cases.hits` 목록입니다.
        departments: `routing_cases.department_candidates` 목록입니다.
        by_key: `("faq"|"routing", source_id)`를 키로 하는 히트 사전입니다.
    """

    faqs: list[dict[str, Any]]
    cases: list[dict[str, Any]]
    departments: list[dict[str, Any]]
    by_key: dict[tuple[str, str], dict[str, Any]]


def faq_hits(search: dict[str, Any]) -> list[dict[str, Any]]:
    """검색 응답의 FAQ 후보를 반환합니다.

    Args:
        search: 검색 API JSON입니다.

    Returns:
        `faq_knowledge.hits` 목록입니다. 없으면 빈 목록입니다.
    """
    return list(
        (search.get("results") or {}).get("faq_knowledge", {}).get("hits") or []
    )


def case_hits(search: dict[str, Any]) -> list[dict[str, Any]]:
    """검색 응답의 공개 사례 후보를 반환합니다.

    Args:
        search: 검색 API JSON입니다.

    Returns:
        `routing_cases.hits` 목록입니다. 없으면 빈 목록입니다.
    """
    return list(
        (search.get("results") or {}).get("routing_cases", {}).get("hits") or []
    )


def department_candidates(search: dict[str, Any]) -> list[dict[str, Any]]:
    """검색 응답에 실린 부서 후보를 반환합니다.

    검색 API가 `routing_eligible`인 사례만 후보로 모은 목록입니다.
    이 함수는 추가 필터를 적용하지 않습니다.

    Args:
        search: 검색 API JSON입니다.

    Returns:
        `routing_cases.department_candidates` 목록입니다.
    """
    return list(
        (search.get("results") or {})
        .get("routing_cases", {})
        .get("department_candidates")
        or []
    )


def hit_excerpt(hit: dict[str, Any]) -> str:
    """FAQ 조건 또는 사례 요지를 잘라 표시용 발췌를 만듭니다.

    Args:
        hit: 검색 히트입니다.

    Returns:
        대상·기간·주의 또는 요지를 포함한 문자열입니다.
    """
    evidence = hit.get("evidence") or {}
    detail = evidence.get("detail") if isinstance(evidence, dict) else None
    if isinstance(detail, dict):
        parts = [
            detail.get("target"),
            detail.get("processing_period"),
            detail.get("received_by"),
            detail.get("main_content"),
            detail.get("warnings"),
        ]
        return "\n".join(str(part) for part in parts if part)[:1200]
    summary = evidence.get("summary") if isinstance(evidence, dict) else None
    return str(summary or hit.get("title") or "")[:1200]


def compact_faq(hit: dict[str, Any]) -> dict[str, Any]:
    """판정 모델에 넘길 FAQ 후보만 남깁니다.

    대상·접수 조건·처리기간·주의는 `detail`에 그대로 둡니다.
    검색 점수·원문 해시·임베딩은 넣지 않습니다.

    Args:
        hit: 검색 FAQ 히트입니다.

    Returns:
        source_id와 조건 원문을 담은 축소 객체입니다.
    """
    evidence = hit.get("evidence") or {}
    detail = evidence.get("detail") if isinstance(evidence, dict) else {}
    return {
        "corpus": "faq",
        "source_id": hit["source_id"],
        "title": hit.get("title"),
        "source_url": hit.get("source_url"),
        "detail": detail if isinstance(detail, dict) else {},
    }


def compact_case(hit: dict[str, Any]) -> dict[str, Any]:
    """판정 모델에 넘길 공개 사례 후보만 남깁니다.

    과거 처리 답변(`evidence.answer`)은 현재 정책 안내가 아니므로 넣지 않습니다.
    부서 확정은 `department_candidates`에서 따로 걸러집니다.

    Args:
        hit: 검색 사례 히트입니다.

    Returns:
        요지와 부서 검증 상태를 담은 축소 객체입니다.
    """
    evidence = hit.get("evidence") or {}
    department = hit.get("department") or {}
    return {
        "corpus": "routing",
        "source_id": hit["source_id"],
        "title": hit.get("title"),
        "source_url": hit.get("source_url"),
        "summary": evidence.get("summary") if isinstance(evidence, dict) else "",
        "routing_eligible": hit.get("routing_eligible"),
        "department_status": hit.get("department_status"),
        "department_id": department.get("department_id"),
        "department_name": department.get("canonical_name"),
        "duty_status": department.get("duty_status"),
    }


def search_parts(search: dict[str, Any]) -> SearchParts:
    """FAQ·사례·부서 후보와 근거 색인을 한 번에 만듭니다.

    Args:
        search: 검색 API JSON입니다.

    Returns:
        히트 목록과 `(컬렉션, source_id)` 색인을 담은 `SearchParts`입니다.
    """
    faqs = faq_hits(search)
    cases = case_hits(search)
    departments = department_candidates(search)
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for hit in faqs:
        index[("faq", str(hit["source_id"]))] = hit
    for hit in cases:
        index[("routing", str(hit["source_id"]))] = hit
    return SearchParts(faqs, cases, departments, by_key=index)


def evidence_index(search: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """(컬렉션, source_id)로 검색 히트를 찾습니다.

    Args:
        search: 검색 API JSON입니다.

    Returns:
        `("faq"|"routing", source_id)`를 키로 하는 히트 사전입니다.
    """
    return search_parts(search).by_key
