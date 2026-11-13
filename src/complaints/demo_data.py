"""공개 민원 사례와 자주 묻는 민원 JSON을 개인정보 마스킹 후 시연 민원으로 넣습니다.

원본 JSON은 읽기만 하며 파일을 바꾸지 않습니다. 지역 정보가 원본에 없으므로
지역은 `모름`으로 두고, 원본에 없는 담당 부서·처리 결과를 만들지 않습니다.
공개 사례의 과거 답변은 시연용 기존 답변으로만 쓰며 현재 정책 안내로 쓰지 않습니다.
"""

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.complaints.errors import AppError
from src.complaints.models import (
    Answer,
    AnswerVersion,
    Category,
    Complaint,
    Event,
    History,
    Job,
    Message,
)
from src.complaints.repository import ComplaintRepository

DEMO_PREFIX = "DEMO-PUB-"
CASE_FILE = "공개_민원_사례.json"
FAQ_FILE = "자주_묻는_민원.json"

# 이메일, 휴대전화, 주민등록번호 형태, 라벨 뒤 성명·연락처를 가린다.
# 기관 대표번호(043 등)는 개인정보가 아니므로 그대로 둔다.
_EMAIL = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")
_MOBILE = re.compile(r"(?<!\d)(01[016789])[-. ]?\d{3,4}[-. ]?\d{4}(?!\d)")
_RRN = re.compile(r"(?<!\d)\d{6}[-\s]?[1-4]\d{6}(?!\d)")
_LABEL_NAME = re.compile(
    r"(이름|성명|신청인|작성자|민원인)(\s*[:：]\s*)([가-힣])[가-힣]{1,3}"
)
_LABEL_PHONE = re.compile(r"(연락처|휴대폰|휴대전화|핸드폰)(\s*[:：]\s*)[\d\-. ]{9,14}")

_CATEGORY_RULES: tuple[tuple[tuple[str, ...], Category], ...] = (
    (("버스", "도로", "교통", "주차", "신호", "횡단보도", "보도"), "도로·교통"),
    (
        ("쓰레기", "청소", "환경", "폐기물", "재활용", "소음", "악취", "하천"),
        "환경·청소",
    ),
    (("공원", "녹지", "가로수", "산책"), "공원·녹지"),
    (("복지", "보육", "노인", "장애", "건강", "보건", "의료"), "생활·복지"),
    (("주택", "건축", "건물", "아파트", "토지", "개발"), "주택·건축"),
)


def mask_text(text: str) -> str:
    """텍스트 안의 개인정보 형태를 가린 사본을 반환합니다.

    Args:
        text: 원본 문장입니다.

    Returns:
        이메일·휴대전화·주민등록번호·라벨 뒤 성명과 연락처를 가린 문자열입니다.
    """

    def name_mask(match: re.Match[str]) -> str:
        """라벨 뒤 성명의 첫 글자만 남기고 나머지를 가립니다.

        Args:
            match: 라벨·구분자·성명 첫 글자를 가진 일치 결과입니다.

        Returns:
            가린 성명을 포함한 라벨 문자열입니다.
        """
        hidden = len(match.group(0)) - len(match.group(1)) - len(match.group(2)) - 1
        return f"{match.group(1)}{match.group(2)}{match.group(3)}{'*' * hidden}"

    text = _EMAIL.sub(lambda m: f"***@{m.group(1)}", text)
    text = _MOBILE.sub(lambda m: f"{m.group(1)}-****-****", text)
    text = _RRN.sub("******-*******", text)
    text = _LABEL_PHONE.sub(lambda m: f"{m.group(1)}{m.group(2)}***-****-****", text)
    return _LABEL_NAME.sub(name_mask, text)


def _category(text: str) -> Category:
    """제목·요약에 든 낱말로 시민 화면의 분야를 고릅니다.

    Args:
        text: 분야를 판단할 원문입니다.

    Returns:
        규칙에 맞는 분야이며 맞지 않으면 `기타`입니다.
    """
    for words, category in _CATEGORY_RULES:
        if any(word in text for word in words):
            return category
    return "기타"


def _clip(text: str, limit: int) -> str:
    """모델 글자 수 제한에 맞춰 문장을 자릅니다.

    Args:
        text: 자를 문장입니다.
        limit: 최대 글자 수입니다.

    Returns:
        공백을 정리하고 limit 이하로 자른 문자열입니다.
    """
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _load(path: Path) -> Any:
    """BOM이 있을 수 있는 JSON 파일을 읽습니다.

    Args:
        path: 읽을 JSON 파일 경로입니다.

    Returns:
        파싱된 JSON 객체입니다.
    """
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _event(stage: str, when: datetime) -> Event:
    """지정 시각의 작업 단계 기록을 만듭니다.

    Args:
        stage: 기록할 단계 문구입니다.
        when: 기록 시각입니다.

    Returns:
        단계 이벤트입니다.
    """
    return Event(stage=stage, date=when)


def _case_rows(cases: list[dict[str, Any]], count: int) -> list[Complaint]:
    """공개 사례를 고르게 나눠 상태별 시연 민원을 만듭니다.

    Args:
        cases: 공개 민원 사례 목록입니다.
        count: 만들 건수입니다.

    Returns:
        마스킹된 시연 민원 목록입니다.
    """
    usable = [c for c in cases if c.get("summary") and c.get("title")]
    step = max(1, len(usable) // count)
    rows: list[Complaint] = []
    for index, item in enumerate(usable[::step][:count]):
        title = _clip(mask_text(item["title"]), 120)
        summary = mask_text(item["summary"])
        body = _clip(
            summary if len(summary) >= 10 else f"{title} 관련 민원입니다.", 2000
        )
        resolution = _clip(mask_text(item.get("resolution") or ""), 4000)
        when = datetime.fromisoformat(item["complaint_date"]).replace(
            hour=9, tzinfo=timezone.utc
        )
        row = Complaint(
            id=f"{DEMO_PREFIX}C{index + 1:04d}",
            title=title,
            body=body,
            category=_category(title + " " + summary),
            district="모름",
            owner="citizen-demo" if index % 5 == 0 else f"sample-case-{index + 1}",
            visibility="private" if index % 5 == 0 else "public",
            is_synthetic=True,
            date=when,
            history=[History(text="시연 데이터 등록", date=when)],
        )
        mode = index % 6
        if mode == 0 and resolution:
            row.status = "answered"
            row.published = Answer(
                text=resolution,
                origin="staff",
                reason="공개 사례 답변(시연)",
                date=when,
            )
            row.versions.append(
                AnswerVersion(
                    version=1,
                    text=resolution,
                    reason="공개 사례 답변(시연)",
                    kind="게시",
                    date=when,
                )
            )
            row.draft = resolution
            row.draft_version = 1
            row.assigned = True
        elif mode == 1 and resolution:
            ai = f"[시연 AI 초안] {title}에 대한 안내 초안입니다."
            row.status = "answered"
            row.ai_original = ai
            row.published = Answer(
                text=resolution,
                origin="ai_edited",
                reason="AI 초안 수정 후 게시(시연)",
                date=when,
            )
            row.draft = resolution
            row.draft_version = 2
            row.versions.append(
                AnswerVersion(
                    version=1, text=ai, reason="AI 초안", kind="이전 AI 원본", date=when
                )
            )
            row.assigned = True
        elif mode == 2:
            row.status = "under_review"
            row.assigned = True
            row.draft = (
                "담당 부서에서 사실관계를 확인한 뒤 안내드리겠습니다. (시연 초안)"
            )
            row.draft_version = 1
            row.versions.append(
                AnswerVersion(
                    version=1,
                    text=row.draft,
                    reason="초안 저장(시연)",
                    kind="초안 저장",
                    date=when,
                )
            )
        elif mode == 3:
            row.status = "under_review"
            row.messages.append(
                Message(
                    text="처리 기간이 얼마나 걸리는지 알고 싶습니다. (시연 추가 문의)",
                    date=when,
                )
            )
            row.history.append(History(text="시민 추가 문의 등록", date=when))
        elif mode == 4:
            row.status = "submitted"
            row.job = Job(
                status="succeeded",
                stage="시연 후보 준비 · 자동 적용 안 함",
                attempt=1,
                started_at=when,
                events=[_event("서버 단계 시연 완료", when)],
            )
            row.ai_candidate = "[시연 후보] 담당자의 근거·현장 확인이 필요합니다. 자동 적용하지 않는 고정 시연 문구입니다."
        else:
            row.status = "under_review"
            row.published = None
            row.versions.append(
                AnswerVersion(
                    version=1,
                    text=resolution or "시연 답변",
                    reason="게시 철회(시연)",
                    kind="게시 철회",
                    date=when,
                )
            )
            row.history.append(History(text="답변 철회: 정정 검토(시연)", date=when))
        rows.append(row)
    return rows


def _faq_rows(faqs: dict[str, list[dict[str, Any]]], count: int) -> list[Complaint]:
    """자주 묻는 민원 제목을 시민 문의 형태로 바꿔 상태별 시연 민원을 만듭니다.

    Args:
        faqs: 분야별 자주 묻는 민원 목록입니다.
        count: 만들 건수입니다.

    Returns:
        마스킹된 시연 민원 목록입니다.
    """
    flat = [item for group in faqs.values() for item in group if item.get("title")]
    flat.sort(key=lambda item: item["id"])
    rows: list[Complaint] = []
    for index, item in enumerate(flat[:count]):
        title = _clip(mask_text(item["title"]), 120)
        body = _clip(
            f"「{title}」 관련해서 처리 절차와 준비 서류를 알고 싶습니다. (시연용 문의 문장)",
            2000,
        )
        when = datetime.fromisoformat(
            item.get("registered_date") or "2026-01-01"
        ).replace(hour=9, tzinfo=timezone.utc)
        mine = index % 4 == 0
        row = Complaint(
            id=f"{DEMO_PREFIX}F{index + 1:04d}",
            title=title,
            body=body,
            category=_category(title + " " + str(item.get("major", ""))),
            district="모름",
            owner="citizen-demo" if mine else f"sample-faq-{index + 1}",
            visibility="private" if mine else "public",
            is_synthetic=True,
            date=when,
            history=[History(text="시연 데이터 등록", date=when)],
        )
        mode = index % 5
        if mode == 0:
            row.status = "submitted"
        elif mode == 1:
            row.status = "withdrawn"
            row.history.append(History(text="민원 철회: 시연 철회", date=when))
        elif mode == 2:
            row.status = "under_review"
            row.assigned = True
            row.job = Job(
                status="cancelled",
                stage="담당자가 시연 작업 취소",
                attempt=1,
                events=[_event("시연 작업 취소", when)],
            )
        elif mode == 3:
            row.status = "under_review"
            row.messages.append(
                Message(text="추가로 확인할 점이 있습니다. (시연 추가 문의)", date=when)
            )
        else:
            row.status = "submitted"
            row.job = Job(
                status="superseded",
                stage="입력 변경으로 적용 중단",
                attempt=1,
                events=[_event("입력 변경으로 중단", when)],
            )
        rows.append(row)
    return rows


def seed_public_demo(
    repository: ComplaintRepository,
    data_dir: Path,
    case_count: int = 36,
    faq_count: int = 20,
) -> int:
    """공개 사례·자주 묻는 민원 JSON에서 마스킹된 시연 민원을 저장합니다.

    이미 같은 식별자가 있으면 건너뛰므로 여러 번 실행해도 중복 저장하지 않습니다.

    Args:
        repository: 민원을 저장할 업무 저장소입니다.
        data_dir: `공개_민원_사례.json`과 `자주_묻는_민원.json`이 있는 폴더입니다.
        case_count: 공개 사례에서 만들 건수입니다.
        faq_count: 자주 묻는 민원에서 만들 건수입니다.

    Returns:
        이번 실행에서 새로 저장한 민원 수입니다.

    Raises:
        FileNotFoundError: 원본 JSON 파일이 없으면 발생합니다.
    """
    cases = _load(data_dir / CASE_FILE)
    faqs = _load(data_dir / FAQ_FILE)
    rows = _case_rows(cases, case_count) + _faq_rows(faqs, faq_count)
    created = 0
    for row in rows:
        try:
            repository.get(row.id)
            continue
        except AppError as error:
            if error.status != 404:
                raise
        repository.create(row, None, "")
        created += 1
    return created
