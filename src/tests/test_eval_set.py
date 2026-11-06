"""초안 응대 평가셋 칸과 분할 규칙을 확인합니다."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from src.assist.eval_set import (
    BUNDLES,
    load_eval_spec,
    select_items,
    validate_eval_spec,
)


@pytest.fixture(scope="module")
def eval_runner() -> ModuleType:
    """scripts/응대_평가.py를 한 번만 불러옵니다."""
    path = Path(__file__).resolve().parents[2] / "scripts" / "응대_평가.py"
    spec = importlib.util.spec_from_file_location("assist_eval_runner", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_eval_spec_passes_schema() -> None:
    """저장소 평가셋은 이름·묶음·분할 규칙을 지킵니다."""
    spec = load_eval_spec()
    assert spec["review_status"] == "draft"
    failures = validate_eval_spec(spec)
    assert failures == []
    names = [item["name"] for item in spec["items"]]
    assert len(names) == len(set(names))
    assert len(spec["items"]) >= 20
    assert {item["bundle"] for item in spec["items"]} == set(BUNDLES)


def test_group_id_stays_in_one_split() -> None:
    """같은 원문 그룹은 개발셋과 보류셋에 나뉘지 않습니다."""
    spec = load_eval_spec()
    mapping: dict[str, set[str]] = {}
    for item in spec["items"]:
        mapping.setdefault(item["group_id"], set()).add(item["split"])
    assert all(len(splits) == 1 for splits in mapping.values())


def test_select_items_default_skips_holdout() -> None:
    """기본 선택은 개발셋만 남깁니다."""
    spec = load_eval_spec()
    dev = select_items(spec, split="dev")
    holdout = select_items(spec, split="holdout")
    assert dev
    assert holdout
    assert all(item["split"] == "dev" for item in dev)
    assert all(item["split"] == "holdout" for item in holdout)
    only = select_items(spec, split="dev", only="FAQ_성인여권")
    assert [item["name"] for item in only] == ["FAQ_성인여권"]


def test_passport_and_injection_keep_handoff() -> None:
    """서류 없는 FAQ와 지시 주입 범위 밖은 안내로 통과시키지 않습니다."""
    spec = load_eval_spec()
    by_name = {item["name"]: item for item in spec["items"]}
    passport = by_name["FAQ_성인여권"]
    assert "faq_answer" in passport["must_not"]
    trash = by_name["FAQ_생활쓰레기시간"]
    assert "faq_answer" in trash["must_not"]
    assert "human_handoff" in trash["expected_outcomes"]
    abuse = by_name["오용_지시주입_영주권"]
    assert abuse["bundle"] == "abuse"
    assert "faq_answer" in abuse["must_not"]
    dump = by_name["조치_대형폐기물무단투기"]
    assert dump["bundle"] == "action_like_faq"
    assert "faq_answer" in dump["must_not"]
    holdout = {item["name"] for item in spec["items"] if item["split"] == "holdout"}
    assert holdout == {
        "보류_FAQ_청소년증",
        "보류_조치_서원구가로등",
        "보류_범위밖_대전민원",
    }


def test_eval_runner_output_keeps_holdout_file(eval_runner: ModuleType) -> None:
    """보류 실행 기본 보고 경로는 개발셋 파일과 다릅니다."""
    default = eval_runner.parse_args([])
    holdout = eval_runner.parse_args(
        ["--split", "holdout", "--output", "rag/reports/assist-eval-holdout.json"]
    )
    assert default.split == "dev"
    assert eval_runner.resolve_report_path(default.output) == eval_runner.REPORT_PATH
    assert holdout.split == "holdout"
    assert (
        eval_runner.resolve_report_path(holdout.output)
        == eval_runner.HOLDOUT_REPORT_PATH
    )
