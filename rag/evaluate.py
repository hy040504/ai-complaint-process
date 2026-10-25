"""실제 검색 API의 소규모 회귀 확인. 민원 자동화 정확도 평가셋은 아닙니다."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .__main__ import api_request


def main():
    """검색 API의 소규모 회귀 예제를 실행하고 결과를 출력·저장합니다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8007")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    examples = json.loads(Path(__file__).with_name("evaluation_queries.json").read_text())
    results = []
    for item in examples:
        payload = {k: item[k] for k in ("query", "collection", "district") if k in item}
        payload["limit"] = 5
        result = api_request(args.api_url.rstrip("/") + "/search", payload)
        hits = [h for collection in result["results"].values() for h in collection["hits"]]
        passed = True
        rank = None
        if "expected_source_id" in item:
            rank = next((h["rank"] for h in hits if h["source_id"] == item["expected_source_id"]), None)
            passed = rank is not None
        if "expected_department" in item:
            rank = next((h["rank"] for h in hits if h.get("department") and
                         h["department"]["canonical_name"] == item["expected_department"]), None)
            passed = rank is not None
        # 최근접 결과가 나와도 답변 가능/이관 가능으로 확정하지 않는 계약을 확인합니다.
        passed = passed and result["retrieval_only"] and result["decision"] == "requires_gate"
        for hit in hits:
            if hit.get("department_status") == "review_required":
                passed = passed and not hit["routing_eligible"] and hit["department"] is None
            if item.get("district") and hit.get("department"):
                passed = passed and hit["department"]["district"] in (None, item["district"])
        row = {"name": item["name"], "passed": bool(passed), "expected_rank": rank,
               "elapsed_ms": result["elapsed_ms"], "top_titles": [h["title"] for h in hits[:5]],
               "candidate_counts": {k: v["candidate_counts"] for k, v in result["results"].items()}}
        results.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    report = {"description": "10개 예제의 검색/계약 회귀 점검. 한국어 민원 자동화 정확도 측정이 아님.",
              "passed": sum(r["passed"] for r in results), "total": len(results), "results": results}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    if not all(r["passed"] for r in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
