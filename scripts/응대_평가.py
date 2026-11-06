"""초안 응대 평가셋으로 현재 공급자의 갈래만 기록합니다.

운영 모델 선정이 아닙니다. 검색 Hit@5와 구별합니다. 민원 CRUD는 쓰지 않습니다.
기본은 개발셋만 돌리고 보류 문항은 건너뜁니다.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.assist import run_assist
from src.assist.eval_set import load_eval_spec, select_items, validate_eval_spec
from src.llm.settings import llm_settings, load_llm_env_file
from src.rag import search_available

REPORT_PATH = ROOT / "rag" / "reports" / "assist-eval-draft.json"


def score_item(item: dict, result: dict) -> bool:
    """한 문항의 갈래·금지를 채점합니다.

    Args:
        item: 평가 문항입니다.
        result: `run_assist` 결과입니다.

    Returns:
        기대 갈래에 들고 금지 갈래가 아니면 True입니다.
    """
    outcome = result.get("outcome")
    transfer = result.get("automatic_transfer")
    expected = item["expected_outcomes"]
    forbidden = item.get("must_not") or []
    expected_reasons = item.get("expected_reason_codes")
    reason = result.get("reason_code")
    ok = outcome in expected
    if transfer is True and "automatic_transfer" in forbidden:
        ok = False
    if outcome in forbidden:
        ok = False
    if expected_reasons and reason not in expected_reasons:
        ok = False
    return ok


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """평가 실행 옵션을 읽습니다."""
    parser = argparse.ArgumentParser(description="초안 응대 갈래 평가")
    parser.add_argument(
        "--split",
        default="dev",
        choices=("dev", "holdout", "all"),
        help="기본은 개발셋만 실행합니다.",
    )
    parser.add_argument("--only", help="이 이름 한 문항만 실행합니다.")
    parser.add_argument(
        "--missing",
        action="store_true",
        help="기존 보고서에 없는 문항만 이어서 실행합니다.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """초안 평가 문항을 돌리고 JSON을 씁니다.

    Args:
        argv: 명령줄 인자입니다.

    Returns:
        검색 API가 없거나 평가셋이 깨졌으면 1, 아니면 0입니다.
    """
    args = parse_args(argv)
    load_llm_env_file()
    settings = llm_settings()
    spec = load_eval_spec()
    failures = validate_eval_spec(spec)
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    previous: dict = {}
    if REPORT_PATH.is_file():
        previous = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    done = {row["name"] for row in previous.get("results") or [] if "name" in row}
    missing = done if args.missing else None
    items = select_items(spec, split=args.split, only=args.only, missing_names=missing)
    if not items:
        print("실행할 문항이 없습니다.", flush=True)
        return 0
    if not search_available():
        print("검색 API가 없습니다.", file=sys.stderr)
        return 1
    by_name = {
        row["name"]: row for row in previous.get("results") or [] if "name" in row
    }
    started_all = time.perf_counter()
    for item in items:
        started = time.perf_counter()
        result = run_assist(
            item["query"],
            item.get("district"),
            limit=5,
            rerank=False,
        )
        ok = score_item(item, result)
        row = {
            "name": item["name"],
            "group_id": item.get("group_id"),
            "bundle": item.get("bundle"),
            "split": item.get("split"),
            "outcome": result.get("outcome"),
            "reason_code": result.get("reason_code"),
            "automatic_transfer": result.get("automatic_transfer"),
            "expected_outcomes": item["expected_outcomes"],
            "expected_reason_codes": item.get("expected_reason_codes"),
            "ok": ok,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        }
        by_name[item["name"]] = row
        print(json.dumps(row, ensure_ascii=False), flush=True)
    ordered = []
    for item in select_items(spec, split=args.split if args.split != "all" else "all"):
        row = by_name.get(item["name"])
        if row:
            ordered.append(row)
    passed = sum(1 for row in ordered if row.get("ok"))
    report = {
        "description": spec["description"],
        "review_status": spec.get("review_status"),
        "provider": settings.get("provider"),
        "model": settings.get("model"),
        "split": args.split,
        "passed": passed,
        "total": len(ordered),
        "elapsed_ms": round((time.perf_counter() - started_all) * 1000, 1),
        "results": ordered,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(str(REPORT_PATH), flush=True)
    print(f"{passed}/{len(ordered)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
