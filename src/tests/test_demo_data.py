"""공개 데이터 기반 시연 민원의 마스킹과 중복 방지를 확인합니다."""

import re
from pathlib import Path

from src.complaints.config import ROOT
from src.complaints.demo_data import mask_text, seed_public_demo
from src.complaints.repository import MemoryRepository

DATA_DIR: Path = ROOT / "db"

# 마스킹 후 남으면 안 되는 개인정보 형태입니다. 기관 대표번호는 제외합니다.
_RESIDUAL = [
    re.compile(r"(?<!\d)01[016789][-. ]?\d{3,4}[-. ]?\d{4}(?!\d)"),
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    re.compile(r"(?<!\d)\d{6}[-\s]?[1-4]\d{6}(?!\d)"),
]


def test_mask_text_hides_mobile_email_rrn_and_labelled_name() -> None:
    """휴대전화·이메일·주민등록번호 형태와 라벨 뒤 성명을 가립니다."""
    masked = mask_text(
        "연락처 010-1234-5678, 메일 kim@gmail.com, 주민 230605-2106275, 성명: 김철수 로 접수"
    )
    assert "1234" not in masked
    assert "kim@" not in masked
    assert "2106275" not in masked
    assert "김철수" not in masked
    assert "성명: 김**" in masked


def test_mask_text_keeps_public_office_number() -> None:
    """기관 대표번호는 개인정보가 아니므로 그대로 둡니다."""
    assert mask_text("문의: 043-201-2895") == "문의: 043-201-2895"


def test_seed_creates_all_statuses_and_is_idempotent() -> None:
    """모든 상태의 민원을 만들고, 두 번째 실행에서는 아무것도 추가하지 않습니다."""
    repo = MemoryRepository()
    first = seed_public_demo(repo, DATA_DIR)
    assert first == 56
    assert seed_public_demo(repo, DATA_DIR) == 0

    rows = repo.all()
    statuses = {row.status for row in rows}
    assert {"submitted", "under_review", "answered", "withdrawn"} <= statuses
    assert any(row.messages for row in rows)
    assert any(row.job.status == "succeeded" and row.ai_candidate for row in rows)
    assert any(row.job.status == "cancelled" for row in rows)
    assert any(
        row.owner == "citizen-demo" and row.visibility == "private" for row in rows
    )
    assert {row.district for row in rows} == {"모름"}
    assert all(row.is_synthetic for row in rows)


def test_seeded_text_has_no_residual_personal_info() -> None:
    """저장된 시연 민원 본문에 개인정보 형태가 남지 않습니다."""
    repo = MemoryRepository()
    seed_public_demo(repo, DATA_DIR)
    for row in repo.all():
        text = row.model_dump_json()
        for pattern in _RESIDUAL:
            assert not pattern.search(text), (row.id, pattern.pattern)
