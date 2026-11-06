"""실행 중인 검색 API에 연결하는 클라이언트입니다.

루트 `rag/` 검색 엔진·PostgreSQL 색인을 복제하지 않습니다. FAQ와 공개
사례는 검색 API가 컬렉션별로 돌려 주고, 이 모듈은 그 응답의
`retrieval_only` / `requires_gate` 계약만 확인합니다.
"""

from __future__ import annotations

import os
from typing import Any

from src.rag.http import http_json


def search_api_url() -> str:
    """검색 API 기본 주소를 반환합니다.

    Returns:
        `RAG_API_URL` 또는 `http://127.0.0.1:8007`입니다. 끝 슬래시는 뺍니다.
    """
    return os.environ.get("RAG_API_URL", "http://127.0.0.1:8007").rstrip("/")


def search_available() -> bool:
    """검색 API 준비 상태를 짧게 확인합니다.

    Returns:
        `/health`가 ready이면 True입니다. 연결 실패는 False입니다.
    """
    try:
        body = http_json(search_api_url() + "/health", timeout=2)
    except (ValueError, OSError, TimeoutError):
        return False
    return isinstance(body, dict) and body.get("status") == "ready"


def require_search_contract(search: dict[str, Any]) -> dict[str, Any]:
    """검색 전용 계약을 지키지 않으면 실패합니다.

    Args:
        search: 검색 API JSON입니다.

    Returns:
        그대로 통과한 검색 응답입니다.

    Raises:
        ValueError: `retrieval_only`/`requires_gate`가 아닌 경우 발생합니다.
    """
    if (
        search.get("retrieval_only") is not True
        or search.get("decision") != "requires_gate"
    ):
        raise ValueError(
            "검색 응답이 retrieval_only/requires_gate 계약을 지키지 않습니다."
        )
    return search


def search_via_api(
    query: str,
    district: str | None = None,
    limit: int = 5,
    rerank: bool = True,
) -> dict[str, Any]:
    """실행 중인 검색 API에서 FAQ와 사례 근거를 가져옵니다.

    Args:
        query: 한국어 민원 원문입니다.
        district: 명시한 관할 구입니다.
        limit: 컬렉션별 반환 수입니다.
        rerank: 재정렬 여부입니다.

    Returns:
        검색 전용 계약을 통과한 검색 API JSON입니다.

    Raises:
        ValueError: 연결 실패이거나 `retrieval_only`/`requires_gate`가 아닌 경우 발생합니다.
    """
    return require_search_contract(
        http_json(
            search_api_url() + "/search",
            {
                "query": query,
                "collection": "both",
                "limit": limit,
                "district": district,
                "rerank": rerank,
            },
        )
    )
