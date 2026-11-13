"""PREFIX 조립이 프리픽스 캐시 적중 조건을 만족하는지 검사합니다.

OpenAI `cached_tokens` 실측은 키가 있을 때만 별도 스크립트가 합니다.
이 모듈은 `.env`를 바꾸지 않고, 파일·상수 조립만 봅니다.
"""

from __future__ import annotations

import re
from typing import Any

from src.assist.prompts import (
    ANSWER_SYSTEM,
    DECISION_SYSTEM,
    PREFIX_00,
    PREFIX_01,
    PREFIX_02,
    PREFIX_03,
    PREFIX_04,
    PREFIX_NAMES,
    PROMPTS_DIR,
    SPECIAL_SANITIZE_SYSTEM,
    STAFF_DRAFT_SYSTEM,
    join_prefix,
)

_HANGUL = re.compile(r"[\uac00-\ud7a3]")
_DYNAMIC_SLOTS = ("{today}", "{district}", "{query}", "{now}", "{request_id}")
OPENAI_PREFIX_CACHE_MIN_TOKENS = 1024

SYSTEMS = (
    ("PREFIX-00 + PREFIX-01", DECISION_SYSTEM, PREFIX_01),
    ("PREFIX-00 + PREFIX-02", ANSWER_SYSTEM, PREFIX_02),
    ("PREFIX-00 + PREFIX-03", STAFF_DRAFT_SYSTEM, PREFIX_03),
    ("PREFIX-00 + PREFIX-04", SPECIAL_SANITIZE_SYSTEM, PREFIX_04),
)


def estimate_tokens(text: str) -> int:
    """한글 음절 1토큰, 그 외 4글자 1토큰으로 어림합니다.

    OpenAI 토크나이저가 아니라 캐시 임계값(1,024) 통과 여부만 가늠합니다.

    Args:
        text: 시스템 지시 본문입니다.

    Returns:
        어림 토큰 수입니다.
    """
    hangul = len(_HANGUL.findall(text))
    rest = len(text) - hangul
    return hangul + max(0, (rest + 3) // 4)


def prefix_cache_report() -> dict[str, Any]:
    """불변 접두 공유·LF·동적 슬롯 없음·어림 토큰을 묶습니다.

    Returns:
        조립 적격 여부와 시스템별 길이를 담은 딕셔너리입니다.
    """
    systems: list[dict[str, Any]] = []
    shared = True
    for label, assembled, task in SYSTEMS:
        expected = join_prefix(PREFIX_00, task)
        starts = assembled.startswith(PREFIX_00.rstrip() + "\n\n")
        tokens = estimate_tokens(assembled)
        row = {
            "system": label,
            "chars": len(assembled),
            "estimated_tokens": tokens,
            "starts_with_prefix_00": starts,
            "matches_join": assembled == expected,
            "meets_openai_min_tokens": tokens >= OPENAI_PREFIX_CACHE_MIN_TOKENS,
        }
        systems.append(row)
        if not starts or assembled != expected:
            shared = False
    crlf = any(b"\r" in (PROMPTS_DIR / name).read_bytes() for name in PREFIX_NAMES)
    dynamic = [
        slot
        for slot in _DYNAMIC_SLOTS
        if any(
            slot in block
            for block in (PREFIX_00, PREFIX_01, PREFIX_02, PREFIX_03, PREFIX_04)
        )
    ]
    eligible = shared and not crlf and not dynamic
    return {
        "description": ("PREFIX 조립 적격 검사. OpenAI cached_tokens 실측이 아닙니다."),
        "openai_prefix_cache_min_tokens": OPENAI_PREFIX_CACHE_MIN_TOKENS,
        "prefix_00_chars": len(PREFIX_00),
        "prefix_00_estimated_tokens": estimate_tokens(PREFIX_00),
        "lf_only": not crlf,
        "dynamic_slots": dynamic,
        "shared_prefix_00": shared,
        "assembly_eligible": eligible,
        "systems": systems,
        "codex_cli_note": (
            "codex_cli는 호출마다 새 프로세스라 KV 캐시 적중을 이 값으로 "
            "확인할 수 없습니다. cached_tokens는 openai_api Responses usage입니다."
        ),
    }
