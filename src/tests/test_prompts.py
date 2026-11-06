"""프리픽스 캐싱용 시스템 프롬프트 파일과 조립을 확인합니다."""

from __future__ import annotations

from src.assist.constants import (
    ANSWER_SYSTEM,
    DECISION_SYSTEM,
    SPECIAL_SANITIZE_SYSTEM,
    STAFF_DRAFT_SYSTEM,
)
from src.assist.prompts import (
    PREFIX_00,
    PREFIX_01,
    PREFIX_02,
    PREFIX_03,
    PREFIX_04,
    PREFIX_NAMES,
    PROMPTS_DIR,
    join_prefix,
    load_prefix,
)


def test_prefix_files_are_lf_and_nonempty() -> None:
    """PREFIX 파일은 LF만 쓰고 비어 있지 않습니다."""
    assert PREFIX_NAMES == (
        "PREFIX-00.txt",
        "PREFIX-01.txt",
        "PREFIX-02.txt",
        "PREFIX-03.txt",
        "PREFIX-04.txt",
    )
    for name in PREFIX_NAMES:
        raw = (PROMPTS_DIR / name).read_bytes()
        assert b"\r" not in raw
        assert load_prefix(name).strip()


def test_decision_system_starts_with_constitution() -> None:
    """판정 시스템 지시는 공통 헌법으로 시작합니다."""
    assert DECISION_SYSTEM.startswith("[시스템 헌법:")
    assert "1차 판정기" in DECISION_SYSTEM
    assert "search_complaint_rag" in DECISION_SYSTEM
    assert DECISION_SYSTEM == join_prefix(PREFIX_00, PREFIX_01)


def test_answer_system_keeps_faq_conditions() -> None:
    """FAQ 안내 지시는 헌법 다음 조건 보존 규칙을 둡니다."""
    assert ANSWER_SYSTEM.startswith("[시스템 헌법:")
    assert "조건 보존형 FAQ" in ANSWER_SYSTEM
    assert "공식 접수" in ANSWER_SYSTEM
    assert ANSWER_SYSTEM == join_prefix(PREFIX_00, PREFIX_02)


def test_staff_and_sanitize_prefixes_load() -> None:
    """담당자 초안·순화 프리픽스는 파일로 읽을 수 있습니다."""
    assert "답변 초안" in PREFIX_03
    assert "순화 요약" in PREFIX_04
    assert "search_complaint_rag를 호출하지 않습니다." in PREFIX_04
    assert "자동 차단" in PREFIX_04
    assert STAFF_DRAFT_SYSTEM == join_prefix(PREFIX_00, PREFIX_03)
    assert SPECIAL_SANITIZE_SYSTEM == join_prefix(PREFIX_00, PREFIX_04)
    assert STAFF_DRAFT_SYSTEM.startswith("[시스템 헌법:")
    assert SPECIAL_SANITIZE_SYSTEM.startswith("[시스템 헌법:")


def test_decision_and_answer_exclude_staff_prefixes() -> None:
    """판정·FAQ 안내에 PREFIX-03·04를 넣지 않습니다."""
    assert "답변 초안" not in DECISION_SYSTEM
    assert "순화 요약" not in DECISION_SYSTEM
    assert "답변 초안" not in ANSWER_SYSTEM
    assert "순화 요약" not in ANSWER_SYSTEM


def test_prefix_cache_assembly_is_eligible() -> None:
    """네 시스템 지시가 PREFIX-00으로 시작하고 동적 슬롯이 없습니다."""
    from src.assist.prefix_cache import prefix_cache_report

    report = prefix_cache_report()
    assert report["assembly_eligible"] is True
    assert report["lf_only"] is True
    assert report["dynamic_slots"] == []
    assert report["shared_prefix_00"] is True
    assert all(row["starts_with_prefix_00"] for row in report["systems"])
    assert all(row["matches_join"] for row in report["systems"])
    assert report["systems"][0]["meets_openai_min_tokens"] is True
