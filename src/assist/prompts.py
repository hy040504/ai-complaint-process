"""프리픽스 캐싱용 시스템 프롬프트를 파일에서 읽어 조립합니다.

원본은 `docs/harness/prompts/PREFIX-00.txt` ~ `PREFIX-04.txt`입니다.
가변 민원·검색 결과는 넣지 않습니다. LF만 유지합니다.
PREFIX-03·04는 담당자 초안·순화용이며 1차 판정·FAQ 안내 시스템 지시에는
넣지 않습니다. 호출은 `src.assist.pipeline`의 후속 단계입니다.
"""

from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "docs" / "harness" / "prompts"
PREFIX_NAMES = (
    "PREFIX-00.txt",
    "PREFIX-01.txt",
    "PREFIX-02.txt",
    "PREFIX-03.txt",
    "PREFIX-04.txt",
)


def load_prefix(name: str) -> str:
    """프리픽스 파일을 UTF-8로 읽고 끝 개행 하나를 맞춥니다.

    Args:
        name: `PREFIX-00.txt`처럼 파일 이름입니다.

    Returns:
        LF만 쓰는 본문입니다. 끝은 개행 하나입니다.

    Raises:
        FileNotFoundError: 파일이 없으면 발생합니다.
        ValueError: 본문이 비어 있으면 발생합니다.
    """
    path = PROMPTS_DIR / name
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    text = text.strip() + "\n"
    if text == "\n":
        raise ValueError(f"프리픽스 파일이 비어 있습니다: {path}")
    return text


def join_prefix(*blocks: str) -> str:
    """공통 헌법과 작업 블록을 한 시스템 지시로 이어 붙입니다.

    Args:
        *blocks: 이미 개행이 맞춰진 프리픽스 본문입니다.

    Returns:
        블록 사이에 빈 줄 하나를 둔 문자열입니다.
    """
    parts = [block.strip("\n") for block in blocks if block.strip()]
    return "\n\n".join(parts) + "\n"


PREFIX_00, PREFIX_01, PREFIX_02, PREFIX_03, PREFIX_04 = (
    load_prefix(name) for name in PREFIX_NAMES
)
DECISION_SYSTEM = join_prefix(PREFIX_00, PREFIX_01)
ANSWER_SYSTEM = join_prefix(PREFIX_00, PREFIX_02)
STAFF_DRAFT_SYSTEM = join_prefix(PREFIX_00, PREFIX_03)
SPECIAL_SANITIZE_SYSTEM = join_prefix(PREFIX_00, PREFIX_04)
