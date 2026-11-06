"""RAG 검색과 LLM을 이어 주는 응대 계층입니다.

`src.rag`로 FAQ·사례를 찾고 `src.llm`으로 판정·조건부 안내를 만든 뒤
코드 정책 검사로 자동 이관을 막습니다. 민원 CRUD는 `src.complaints`가
담당하며 이 패키지는 글을 저장하지 않습니다.
"""

from collections.abc import Iterator
from typing import Any

from src.assist.constants import EXAMPLES
from src.assist.pipeline import iter_assist, render_assist, run_assist
from src.assist.policy import validate_decision
from src.llm import complete_chat, llm_configured, parse_json_object
from src.rag import search_api_url, search_available


def assist_examples() -> list[dict[str, Any]]:
    """검사기에 고정한 예시 질문을 반환합니다.

    Returns:
        원본을 바꾸지 않도록 복사한 예시 목록입니다.
    """
    return [item.copy() for item in EXAMPLES]


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
        `run_assist`의 결과 딕셔너리입니다.
    """
    return run_assist(query, district, limit=limit, rerank=rerank)


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


__all__ = [
    "EXAMPLES",
    "assist_examples",
    "complete_chat",
    "iter_assist",
    "iter_web_assist",
    "llm_configured",
    "parse_json_object",
    "render_assist",
    "run_assist",
    "run_web_assist",
    "search_api_url",
    "search_available",
    "validate_decision",
]
