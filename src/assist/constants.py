"""응대 파이프라인이 공유하는 허용 값과 안내 문구입니다.

판정 JSON의 범위·의도·갈래와 시민 진행 안내, 고정 예시 질문을 둡니다.
시스템 지시는 `docs/harness/prompts/`의 PREFIX 파일을 읽어 조립합니다.
"""

from __future__ import annotations

from typing import Any

from src.assist.prompts import ANSWER_SYSTEM, DECISION_SYSTEM

SCOPES = ("in_scope", "out_of_scope", "uncertain")
INTENTS = ("information", "action", "mixed", "unclear")
OUTCOMES = ("faq_answer", "department_suggestion", "human_handoff")
CORPORA = ("faq", "routing")
REASON_CODES = (
    "insufficient_evidence",
    "out_of_scope",
    "action_required",
    "mixed_request",
    "department_unverified",
    "condition_unclear",
    "invalid_model_output",
    "policy_rejected",
    "llm_unavailable",
    "search_failed",
    "faq_generation_failed",
    "ok",
)
HANDOFF_REASONS = {
    "insufficient_evidence": "현재 검색 근거만으로 안내를 확정하기 어렵습니다. 담당자 검토가 필요합니다.",
    "out_of_scope": "현재 FAQ·공개 사례 범위에서 확정하기 어렵습니다. 담당자 검토가 필요합니다.",
    "action_required": "현장 조치가 필요한 요청으로 보입니다. 담당자가 부서 후보와 함께 검토합니다.",
    "mixed_request": "안내와 조치가 섞여 있어 일부 FAQ만으로 전체를 종결하지 않습니다. 담당자 검토가 필요합니다.",
    "department_unverified": "부서 후보의 업무분장·관할이 확인되지 않아 담당자 검토가 필요합니다.",
    "condition_unclear": "적용 조건이 충분하지 않습니다. 담당자 검토가 필요합니다.",
    "invalid_model_output": "판정 결과를 코드에서 검증하지 못해 담당자 검토로 연결합니다.",
    "policy_rejected": "모델이 가리킨 근거 또는 부서가 검색 결과와 맞지 않아 담당자 검토로 연결합니다.",
    "llm_unavailable": "언어 모델이 설정되지 않았거나 호출에 실패했습니다. 검색 근거만 표시하고 담당자 검토로 연결합니다.",
    "search_failed": "검색에 실패했습니다. 담당자 검토가 필요합니다.",
    "faq_generation_failed": "FAQ 답변 생성·검사를 통과하지 못해 담당자 검토로 연결합니다.",
    "ok": "검색 근거를 바탕으로 안내합니다.",
}
PROGRESS_LABELS = {
    "read": "민원 내용을 읽고 있어요",
    "search": "저장된 안내와 사례를 찾고 있어요",
    "review": "찾은 자료를 살펴보고 있어요",
    "write": "안내문을 준비하고 있어요",
}
EXAMPLES: list[dict[str, Any]] = [
    {
        "id": "faq",
        "title": "FAQ로 안내 가능한 정보 문의",
        "query": "대형폐기물 배출 방법을 알고 싶어요.",
        "district": None,
    },
    {
        "id": "action",
        "title": "현장 조치가 필요한 민원",
        "query": "우리집 앞 가로등이 밤새 깜빡거려 수리를 요청합니다.",
        "district": "흥덕구",
    },
    {
        "id": "routing",
        "title": "유사 사례로 부서 후보가 나오는 민원",
        "query": "711번 버스가 정류장에 서지 않고 지나갔습니다.",
        "district": None,
    },
    {
        "id": "handoff",
        "title": "근거가 부족해 담당자 검토로 가는 민원",
        "query": "다른 시 소속 시설의 이용 요금을 청주시가 환불해 주세요.",
        "district": None,
    },
    {
        "id": "district",
        "title": "관할 구를 명시한 민원",
        "query": "아파트 앞 불법 주정차로 통행이 불편합니다. 단속을 요청합니다.",
        "district": "상당구",
    },
]

