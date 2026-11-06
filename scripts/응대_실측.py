"""현재 LLM 공급자로 고정 예제 몇 건을 실측합니다.

운영 모델 선정이 아닙니다. 민원 CRUD와 검색 색인은 바꾸지 않습니다.
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

CASES = (
    {
        "name": "FAQ_대형폐기물",
        "query": "대형폐기물 배출 방법을 알고 싶어요.",
        "district": None,
    },
    {
        "name": "조치_가로등",
        "query": "우리집 앞 가로등이 밤새 깜빡거려 수리를 요청합니다.",
        "district": "흥덕구",
    },
    {
        "name": "순화_가로등",
        "query": "쓰레기같은 가로등을 지금 고쳐 주세요.",
        "district": "흥덕구",
    },
)


def main() -> int:
    """검색 API와 환경 LLM으로 고정 예제를 돌리고 JSON을 씁니다.

    Returns:
        검색 API가 없으면 1, 아니면 0입니다.
    """
    load_llm_env_file()
    settings = llm_settings()
    if not search_available():
        print("검색 API가 없습니다.", file=sys.stderr)
        return 1
    rows: list[dict] = []
    started_all = time.perf_counter()
    for item in CASES:
        started = time.perf_counter()
        result = run_assist(
            item["query"],
            item["district"],
            limit=5,
            rerank=False,
        )
        rows.append(
            {
                "name": item["name"],
                "query": item["query"],
                "district": item["district"],
                "outcome": result.get("outcome"),
                "reason_code": result.get("reason_code"),
                "automatic_transfer": result.get("automatic_transfer"),
                "staff_draft": result.get("staff_draft") is not None,
                "sanitize": result.get("sanitize") is not None,
                "codex_roles": [call.get("role") for call in result.get("codex") or []],
                "stages": result.get("stages") or [],
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            }
        )
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    report = {
        "description": "응대 파이프라인 실측. 운영 모델 선정이 아닙니다.",
        "provider": settings.get("provider"),
        "model": settings.get("model"),
        "elapsed_ms": round((time.perf_counter() - started_all) * 1000, 1),
        "results": rows,
    }
    output = ROOT / "rag" / "reports" / "assist-codex-cli.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(str(output), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
