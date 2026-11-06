"""민원 JSON을 검색 질의로 만들고 RAG+판정 파이프라인에 넘깁니다.

민원 CRUD 테이블에는 쓰지 않습니다. 검색은 `src.rag` 검색 API이고,
판정은 `src.assist`입니다.
"""

from collections.abc import Callable
from typing import Any

from src.assist import run_web_assist
from src.complaints.models import AssistResponse
from src.lab_web.models import LabAcceptResult, LabComplaint, LlmEnvelope

AssistFn = Callable[[str, str | None, int, bool], dict[str, Any]]


def compose_search_query(complaint: LabComplaint) -> str:
    """제목과 상세 내용만 검색 질의로 합칩니다.

    민원 분야는 검색 임베딩에 넣지 않습니다. 분야가 본문과 다를 때
    FAQ 쪽으로 검색이 기울지 않게 합니다.

    Args:
        complaint: 검증된 민원 내용입니다.

    Returns:
        2,000자 이하 검색 질의입니다.
    """
    parts = [complaint.title]
    if complaint.body:
        parts.append(complaint.body)
    return "\n\n".join(parts)[:2000]


def handle_complaint(
    complaint: LabComplaint,
    *,
    assist_fn: AssistFn | None = None,
) -> LabAcceptResult:
    """검색 API를 먼저 돌린 뒤 판정 결과를 붙입니다.

    Args:
        complaint: 검증된 민원 내용입니다.
        assist_fn: `(query, district, limit, rerank)` 응대 함수입니다.
            생략하면 `run_web_assist`를 씁니다.

    Returns:
        수신 확인과 응대 결과입니다.
    """
    query = compose_search_query(complaint)
    run = assist_fn or run_web_assist
    raw = run(query, complaint.district, 5, False)
    assist = AssistResponse.model_validate(raw)
    failed = assist.reason_code == "search_failed"
    return LabAcceptResult(
        complaint=complaint,
        search_query=query,
        llm=LlmEnvelope(
            status="search_failed" if failed else "completed",
            sent=True,
            query=query,
        ),
        assist=assist,
        message=(
            "검색 서버에 연결하지 못했습니다. 검색 API(:8007)를 확인해 주세요."
            if failed
            else "검색 후보를 찾은 뒤 판정했습니다."
        ),
    )
