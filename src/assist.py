"""검색 API와 LLM을 호출해 시연 응대 결과를 만듭니다."""

from collections.abc import Iterator
from typing import Any, cast

from rag.assist import (
    EXAMPLES,
    http_json,
    iter_assist,
    llm_configured as llm_token_present,
    run_assist,
    search_api_url,
)


def llm_configured() -> bool:
    """응대 LLM 토큰이 환경에 있는지 반환합니다."""
    return bool(llm_token_present())


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


def assist_examples() -> list[dict[str, Any]]:
    """검사기에 고정한 예시 질문을 반환합니다."""
    return [dict(item) for item in EXAMPLES]


def run_web_assist(
    query: str,
    district: str | None,
    limit: int,
    rerank: bool,
) -> dict[str, Any]:
    """웹 검사기가 사용하는 응대 파이프라인을 실행합니다.

    Args:
        query: 한국어 민원 원문입니다.
        district: 명시한 관할 구입니다.
        limit: 컬렉션별 검색 수입니다.
        rerank: 재정렬 여부입니다.

    Returns:
        `rag.assist.run_assist`의 결과 딕셔너리입니다.
    """
    return cast(dict[str, Any], run_assist(query, district, limit=limit, rerank=rerank))


def iter_web_assist(
    query: str,
    district: str | None,
    limit: int,
    rerank: bool,
) -> Iterator[dict[str, Any]]:
    """웹 검사기가 진행 안내와 최종 결과를 순서대로 받습니다.

    Args:
        query: 한국어 민원 원문입니다.
        district: 명시한 관할 구입니다.
        limit: 컬렉션별 검색 수입니다.
        rerank: 재정렬 여부입니다.

    Yields:
        짧은 진행 안내 또는 최종 응대 결과입니다.
    """
    yield from iter_assist(query, district, limit=limit, rerank=rerank)
