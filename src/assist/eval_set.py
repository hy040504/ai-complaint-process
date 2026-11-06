"""초안 응대 평가셋 파일을 읽고 칸을 검사합니다.

검색 Hit@5와 구별합니다. 운영 모델 선정·민원 CRUD와 섞지 않습니다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.assist.constants import OUTCOMES, REASON_CODES

ROOT = Path(__file__).resolve().parents[2]
EVAL_PATH = ROOT / "rag" / "assist_eval_queries.json"
BUNDLES = (
    "faq_apply",
    "action_like_faq",
    "department",
    "oos",
    "uncertain_mixed",
    "abuse",
)
"""초안 평가 여섯 묶음입니다. 400문항 제안과 구별합니다."""
SPLITS = ("dev", "holdout")
"""개발셋과 보류셋입니다. 같은 `group_id`는 한쪽에만 둡니다."""
REQUIRED = (
    "name",
    "group_id",
    "bundle",
    "split",
    "query",
    "expected_outcomes",
    "must_not",
    "note",
)
DISTRICTS = ("상당구", "서원구", "흥덕구", "청원구")
"""검사기 작성 화면과 같은 구 목록입니다."""


def load_eval_spec(path: Path | None = None) -> dict[str, Any]:
    """평가셋 JSON을 읽습니다.

    Args:
        path: 파일 경로입니다. 생략하면 저장소 기본 파일입니다.

    Returns:
        설명·검수 상태·문항 목록을 담은 딕셔너리입니다.

    Raises:
        OSError: 파일을 읽지 못하면 발생합니다.
        json.JSONDecodeError: JSON이 아니면 발생합니다.
    """
    target = path or EVAL_PATH
    return json.loads(target.read_text(encoding="utf-8"))


def validate_eval_spec(spec: dict[str, Any]) -> list[str]:
    """문항 칸·중복·분할 규칙을 검사합니다.

    Args:
        spec: `load_eval_spec`이 읽은 객체입니다.

    Returns:
        문제 설명 목록입니다. 비어 있으면 통과입니다.
    """
    failures: list[str] = []
    items = spec.get("items")
    if not isinstance(items, list) or not items:
        return ["items 배열이 필요합니다."]
    names: set[str] = set()
    group_split: dict[str, str] = {}
    for index, item in enumerate(items):
        prefix = f"items[{index}]"
        if not isinstance(item, dict):
            failures.append(f"{prefix}는 객체여야 합니다.")
            continue
        for key in REQUIRED:
            if key not in item:
                failures.append(f"{prefix}에 {key}가 없습니다.")
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            failures.append(f"{prefix}.name이 비어 있습니다.")
        elif name in names:
            failures.append(f"이름이 겹칩니다: {name}")
        else:
            names.add(name)
        query = item.get("query")
        if not isinstance(query, str) or len(query.strip()) < 2:
            failures.append(f"{prefix}.query가 너무 짧습니다.")
        bundle = item.get("bundle")
        if bundle not in BUNDLES:
            failures.append(f"{prefix}.bundle이 허용 목록에 없습니다: {bundle}")
        split = item.get("split")
        if split not in SPLITS:
            failures.append(f"{prefix}.split이 허용 목록에 없습니다: {split}")
        group_id = item.get("group_id")
        if isinstance(group_id, str) and group_id and split in SPLITS:
            previous = group_split.get(group_id)
            if previous and previous != split:
                failures.append(
                    f"group_id {group_id}가 {previous}와 {split}에 나뉘어 있습니다."
                )
            group_split[group_id] = str(split)
        outcomes = item.get("expected_outcomes")
        if not isinstance(outcomes, list) or not outcomes:
            failures.append(f"{prefix}.expected_outcomes가 비어 있습니다.")
        else:
            for outcome in outcomes:
                if outcome not in OUTCOMES:
                    failures.append(f"{prefix} 허용되지 않은 갈래: {outcome}")
            if "automatic_transfer" in outcomes:
                failures.append(f"{prefix}는 자동 이관을 정답으로 두면 안 됩니다.")
        forbidden = item.get("must_not") or []
        if not isinstance(forbidden, list):
            failures.append(f"{prefix}.must_not은 배열이어야 합니다.")
        elif "automatic_transfer" not in forbidden:
            failures.append(f"{prefix}.must_not에 automatic_transfer가 없습니다.")
        reasons = item.get("expected_reason_codes")
        if reasons is not None:
            if not isinstance(reasons, list) or not reasons:
                failures.append(
                    f"{prefix}.expected_reason_codes 형식이 잘못되었습니다."
                )
            else:
                for reason in reasons:
                    if reason not in REASON_CODES:
                        failures.append(f"{prefix} 허용되지 않은 사유: {reason}")
        district = item.get("district")
        if district is not None and district not in DISTRICTS:
            failures.append(f"{prefix}.district가 허용 구가 아닙니다: {district}")
    return failures


def select_items(
    spec: dict[str, Any],
    split: str = "dev",
    only: str | None = None,
    missing_names: set[str] | None = None,
) -> list[dict[str, Any]]:
    """실행할 문항을 고릅니다.

    Args:
        spec: 평가셋입니다.
        split: `dev` 또는 `holdout`입니다. `all`이면 둘 다 남깁니다.
        only: 있으면 이 이름만 남깁니다.
        missing_names: 있으면 이 집합에 없는 이름만 남깁니다.

    Returns:
        실행 대상 문항 목록입니다.
    """
    items = [item for item in spec["items"] if isinstance(item, dict)]
    if split != "all":
        items = [item for item in items if item.get("split") == split]
    if only:
        items = [item for item in items if item.get("name") == only]
    if missing_names is not None:
        items = [item for item in items if item.get("name") not in missing_names]
    return items
