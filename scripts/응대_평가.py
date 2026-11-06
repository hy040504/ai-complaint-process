"""초안 응대 평가셋으로 현재 공급자의 갈래만 기록합니다.

운영 모델 선정이 아닙니다. 검색 Hit@5와 구별합니다. 민원 CRUD는 쓰지 않습니다.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.assist import run_assist
from src.llm.settings import llm_settings, load_llm_env_file
from src.rag import search_available

EVAL_PATH = ROOT / "rag" / "assist_eval_queries.json"


def main() -> int:
    """초안 평가 문항을 돌리고 JSON을 씁니다.

    Returns:
        검색 API가 없으면 1, 아니면 0입니다.
    """
    load_llm_env_file()
    settings = llm_settings()
    if not search_available():
        print("검색 API가 없습니다.", file=sys.stderr)
        return 1
    spec = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    rows: list[dict] = []
    passed = 0
    started_all = time.perf_counter()
    for item in spec["items"]:
        started = time.perf_counter()
        result = run_assist(
            item["query"],
            item.get("district"),
            limit=5,
            rerank=False,
        )
        outcome = result.get("outcome")
        transfer = result.get("automatic_transfer")
        expected = item["expected_outcomes"]
        forbidden = item.get("must_not") or []
        ok = outcome in expected and not (
            transfer is True and "automatic_transfer" in forbidden
        )
        if "faq_answer" in forbidden and outcome == "faq_answer":
            ok = False
        if ok:
            passed += 1
        row = {
            "name": item["name"],
            "outcome": outcome,
            "reason_code": result.get("reason_code"),
            "automatic_transfer": transfer,
            "expected_outcomes": expected,
            "ok": ok,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        }
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    report = {
        "description": spec["description"],
        "review_status": spec.get("review_status"),
        "provider": settings.get("provider"),
        "model": settings.get("model"),
        "passed": passed,
        "total": len(rows),
        "elapsed_ms": round((time.perf_counter() - started_all) * 1000, 1),
        "results": rows,
    }
    output = ROOT / "rag" / "reports" / "assist-eval-draft.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(str(output), flush=True)
    print(f"{passed}/{len(rows)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
