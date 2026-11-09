"""민원 JSON을 검색 질의로 만들고 RAG+판정 파이프라인에 넘깁니다.

민원 CRUD 테이블에는 쓰지 않습니다. 검색은 `src.rag` 검색 API이고,
판정은 `src.assist`입니다. 응대 결과의 `codex`는 모델에 넣은 사용자
JSON과 Codex stdin 전문입니다. 스트림은 진행 안내 뒤에 같은 결과를
붙입니다.
"""

from collections.abc import Callable, Iterator
from typing import Any

from src.assist import iter_web_assist, run_web_assist
from src.assist.constants import PROGRESS_LABELS
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


def accept_from_assist(
    complaint: LabComplaint,
    query: str,
    assist: AssistResponse,
) -> LabAcceptResult:
    """검증된 응대 결과를 검사기 수신 응답으로 감쌉니다.

    Args:
        complaint: 검증된 민원 내용입니다.
        query: 검색에 넣은 질의입니다.
        assist: 파이프라인 응대 결과입니다.

    Returns:
        수신 확인과 응대 결과입니다.
    """
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
    return accept_from_assist(
        complaint, query, AssistResponse.model_validate(raw)
    )


def iter_complaint(
    complaint: LabComplaint,
    *,
    assist_fn: AssistFn | None = None,
) -> Iterator[dict[str, Any]]:
    """진행 안내를 먼저 보내고 마지막에 검사기 수신 결과를 붙입니다.

    테스트용 `assist_fn`이 있으면 짧은 진행 안내 뒤 그 함수로 한 번
    응대합니다. 없으면 `iter_web_assist`의 실제 단계 안내를 그대로 씁니다.

    Args:
        complaint: 검증된 민원 내용입니다.
        assist_fn: 테스트용 응대 함수입니다. 생략하면 실제 파이프라인입니다.

    Yields:
        `progress` 사건 또는 `done`에 감싼 `LabAcceptResult`입니다.
    """
    query = compose_search_query(complaint)
    if assist_fn is not None:
        for key in ("read", "search", "review"):
            yield {
                "type": "progress",
                "key": key,
                "label": PROGRESS_LABELS[key],
            }
        yield {
            "type": "done",
            "result": handle_complaint(complaint, assist_fn=assist_fn),
        }
        return
    for event in iter_web_assist(query, complaint.district, 5, False):
        if event.get("type") == "progress":
            yield event
            continue
        if event.get("type") != "done":
            continue
        assist = AssistResponse.model_validate(event["result"])
        yield {
            "type": "done",
            "result": accept_from_assist(complaint, query, assist),
        }
