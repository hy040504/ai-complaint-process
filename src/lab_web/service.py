"""민원 JSON을 받아 언어 모델용 질의로 정규화합니다.

이 단계는 저장·검색·모델 호출을 하지 않습니다.
"""

from src.lab_web.models import LabAcceptResult, LabComplaint, LlmEnvelope


def compose_query(complaint: LabComplaint) -> str:
    """제목·분야·본문을 모델에 넘길 한 질의로 합칩니다.

    Args:
        complaint: 검증된 민원 내용입니다.

    Returns:
        2,200자 이하 질의입니다.
    """
    parts = [f"분야: {complaint.category}", complaint.title, complaint.body]
    return "\n\n".join(parts)[:2200]


def accept_complaint(complaint: LabComplaint) -> LabAcceptResult:
    """민원 JSON을 수신하고 모델 호출 전 봉투를 만듭니다.

    Args:
        complaint: 검증된 민원 내용입니다.

    Returns:
        수신 확인과 아직 보내지 않은 모델 봉투입니다.
    """
    return LabAcceptResult(
        complaint=complaint,
        llm=LlmEnvelope(query=compose_query(complaint)),
    )
