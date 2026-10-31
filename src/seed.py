"""사용자가 명시적으로 요청할 때만 합성 민원을 생성합니다."""

from datetime import timedelta

from src.models import (
    Answer,
    Category,
    Complaint,
    District,
    Event,
    History,
    Job,
    Status,
    utcnow,
)
from src.repository import ComplaintRepository


def seed_demo(repository: ComplaintRepository) -> int:
    """비어 있는 업무 저장소에 개인정보 없는 시연 민원 24건을 넣습니다.

    Args:
        repository: 합성 민원을 저장할 별도 업무 저장소입니다.

    Returns:
        생성한 민원 수이며 이미 자료가 있으면 0입니다.
    """
    if repository.all():
        return 0
    titles = [
        "보도블록 파손 점검 요청",
        "대형폐기물 배출 방법 문의",
        "산책로 가로등 점검 요청",
        "버스 정류장 안내판 점검",
        "쓰레기 무단 투기 확인 요청",
        "어린이공원 놀이시설 점검 요청",
    ]
    districts: list[District] = ["상당구", "서원구", "흥덕구", "청원구"]
    categories: list[Category] = [
        "도로·교통",
        "환경·청소",
        "공원·녹지",
        "생활·복지",
        "주택·건축",
        "기타",
    ]
    statuses: list[Status] = [
        "under_review",
        "answered",
        "submitted",
        "under_review",
        "answered",
        "closed",
    ]
    ai = "[합성 AI 초안] 남겨주신 내용을 확인했습니다. 구체적인 위치와 현장 상황을 담당자가 확인한 후 안내하겠습니다. 실제 정책 안내가 아닌 시연 문구입니다."
    for index in range(24):
        mine = index % 4 == 0 or index == 5
        row = Complaint(
            id=f"DEMO-2026-{1048-index}",
            title=f"{districts[index % 4]} {titles[index % 6]}"
            + (f" ({index // 6 + 1})" if index >= 6 else ""),
            body="화면과 API 검증을 위해 만든 합성 민원입니다. 해당 지역의 생활 불편 사항에 대한 확인과 검토를 요청합니다. 개인정보와 실제 RAG 원문을 사용하지 않았습니다.",
            owner="citizen-demo" if mine else f"sample-{index}",
            visibility="private" if mine else "public",
            district=districts[index % 4],
            category=categories[index % 6],
            date=utcnow() - timedelta(hours=index * 4),
            status=statuses[index % 6],
            ai_original=ai,
            draft=ai,
            draft_version=1,
            assigned=index % 2 == 0,
            job=Job(
                status="failed" if index == 2 else "succeeded",
                stage=(
                    "검색 미연동 · 시연 실패"
                    if index == 2
                    else "합성 초안 준비 · 검토 대기"
                ),
                attempt=1,
                events=[Event(stage="합성 시연 데이터 준비")],
            ),
            history=[History(text="합성 시연 민원 등록")],
        )
        if row.status in ("answered", "closed"):
            row.published = Answer(
                text="[합성 시연 답변] 남겨주신 의견을 확인했습니다. 실제 행정 조치나 처리 완료를 뜻하지 않는 화면 검증용 답변입니다.",
                origin="ai_edited",
                reason="합성 초기 자료",
            )
        repository.create(row, None, "")
    return 24
