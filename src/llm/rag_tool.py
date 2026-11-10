"""Codex가 민원 문장으로 검색 API만 호출하는 도구입니다.

SQL, 셸, 파일 수정은 열지 않습니다. 반환은 판정 프롬프트와 같은
FAQ·사례·부서 후보이고 `retrieval_only` / `requires_gate`를 유지합니다.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.rag.client import require_search_contract, search_via_api

RAG_TOOL_NAME = "search_complaint_rag"
DISTRICTS = ("상당구", "서원구", "흥덕구", "청원구")
RAG_TOOL_USAGE = (
    "search_complaint_rag에는 민원 원문 query와, 필요할 때만 "
    "district(상당구·서원구·흥덕구·청원구)를 넘깁니다. "
    "반환은 retrieval_only 검색 후보입니다. "
    "검색 점수는 자동 답변 확률이 아니며 SQL·셸·다른 도구는 쓰지 않습니다."
)


def search_complaint_rag(
    query: str,
    district: str | None = None,
    *,
    search_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """민원 문장을 검색 API에 넘기고 판정용 후보를 돌려줍니다.

    Args:
        query: 한국어 민원 원문입니다.
        district: 명시한 관할 구입니다. 비어 있으면 구 필터를 넣지 않습니다.
        search_fn: 검색 함수입니다. 생략하면 `search_via_api`를 씁니다.

    Returns:
        `query`, `district`, FAQ·사례·부서 후보와 검색 전용 계약 표식입니다.

    Raises:
        ValueError: 문장이 비었거나 구 이름이 허용 목록 밖인 경우 발생합니다.
    """
    text = query.strip()
    if not text:
        raise ValueError("민원 문장이 비어 있습니다.")
    area = district.strip() if isinstance(district, str) else None
    if area == "":
        area = None
    if area is not None and area not in DISTRICTS:
        raise ValueError(
            "district는 상당구, 서원구, 흥덕구, 청원구 중 하나이거나 비워야 합니다."
        )
    fetch = search_fn or search_via_api
    search = require_search_contract(fetch(text, area, limit=5, rerank=False))
    from src.assist.policy import decision_payload

    payload = decision_payload(text, area, search)
    payload["retrieval_only"] = True
    payload["decision"] = "requires_gate"
    return payload
