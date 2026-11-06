"""현재 공급자와 openai_api를 비교하고 PREFIX 조립 적격을 기록합니다.

`.env` 파일은 쓰지 않습니다. OPENAI_API_KEY가 없으면 API 실측은 건너뜁니다.
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
from src.assist.constants import DECISION_SYSTEM
from src.assist.prefix_cache import prefix_cache_report
from src.llm.complete import complete_result
from src.llm.settings import (
    llm_settings,
    load_llm_env_file,
    optional_env,
    use_provider,
)
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

REPORTS = ROOT / "rag" / "reports"


def _run_cases(provider: str) -> dict:
    """프로세스 공급자를 잠시 바꾸고 고정 예제를 돌립니다."""
    settings = use_provider(provider)
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
        usages = [
            call.get("usage") for call in result.get("codex") or [] if call.get("usage")
        ]
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
                "cached_tokens": [
                    usage.get("cached_tokens") for usage in usages if usage
                ],
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            }
        )
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    return {
        "description": "응대 파이프라인 실측. 운영 모델 선정이 아닙니다.",
        "provider": settings.get("provider"),
        "model": settings.get("model"),
        "elapsed_ms": round((time.perf_counter() - started_all) * 1000, 1),
        "results": rows,
    }


def _probe_prefix_cache(settings: dict) -> dict:
    """같은 시스템 지시로 두 번 호출해 cached_tokens를 읽습니다."""
    first = complete_result(
        DECISION_SYSTEM,
        json.dumps(
            {"query": "대형폐기물 배출 방법", "district": None}, ensure_ascii=False
        ),
        settings=settings,
    )
    second = complete_result(
        DECISION_SYSTEM,
        json.dumps(
            {"query": "가로등 수리를 요청합니다.", "district": "흥덕구"},
            ensure_ascii=False,
        ),
        settings=settings,
    )
    first_cached = (first.usage or {}).get("cached_tokens")
    second_cached = (second.usage or {}).get("cached_tokens")
    return {
        "ran": True,
        "first_usage": first.usage,
        "second_usage": second.usage,
        "second_cached_tokens": second_cached,
        "hit": isinstance(second_cached, int) and second_cached > 0,
        "note": (
            "두 번째 호출의 cached_tokens가 0보다 크면 같은 instructions 접두가 "
            "적중했다는 뜻입니다. 판정 정확도와는 별개입니다."
        ),
        "first_text_chars": len(first.text),
        "second_text_chars": len(second.text),
        "first_cached_tokens": first_cached,
    }


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(str(path), flush=True)


def main() -> int:
    """조립 적격을 기록하고, 키가 있으면 openai_api를 비교합니다.

    Returns:
        검색 API가 없거나 비교 중 오류면 1, 아니면 0입니다.
    """
    load_llm_env_file()
    assembly = prefix_cache_report()
    _write(REPORTS / "prefix-cache-assembly.json", assembly)

    baseline_path = REPORTS / "assist-codex-cli.json"
    baseline = None
    if baseline_path.is_file():
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))

    original = (llm_settings().get("provider") or "legacy").strip().lower()
    api_key = optional_env("OPENAI_API_KEY")
    openai_report = None
    cache_probe = {
        "ran": False,
        "reason": "OPENAI_API_KEY가 비어 있어 cached_tokens 실측을 건너뜁니다. .env는 쓰지 않았습니다.",
    }
    skipped = True
    if not search_available():
        print("검색 API가 없습니다.", file=sys.stderr)
        compare = {
            "description": "공급자 비교. 운영 모델 선정이 아닙니다.",
            "env_file_rewritten": False,
            "assembly_eligible": assembly["assembly_eligible"],
            "openai_api": "search_unavailable",
            "prefix_cache_probe": cache_probe,
            "baseline": baseline_path.name if baseline else None,
        }
        _write(REPORTS / "assist-provider-compare.json", compare)
        return 1
    if api_key:
        skipped = False
        try:
            openai_report = _run_cases("openai_api")
            _write(REPORTS / "assist-openai-api.json", openai_report)
            cache_probe = _probe_prefix_cache(llm_settings())
        finally:
            use_provider(original)
    else:
        print(cache_probe["reason"], flush=True)

    compare_rows = []
    if baseline and openai_report:
        by_name = {row["name"]: row for row in openai_report["results"]}
        for row in baseline.get("results") or []:
            other = by_name.get(row["name"], {})
            compare_rows.append(
                {
                    "name": row["name"],
                    "codex_cli_outcome": row.get("outcome"),
                    "openai_api_outcome": other.get("outcome"),
                    "same_outcome": row.get("outcome") == other.get("outcome"),
                    "codex_cli_ms": row.get("elapsed_ms"),
                    "openai_api_ms": other.get("elapsed_ms"),
                    "automatic_transfer_both_false": (
                        row.get("automatic_transfer") is False
                        and other.get("automatic_transfer") is False
                    ),
                }
            )
    compare = {
        "description": "공급자 비교. 운영 모델 선정이 아닙니다.",
        "env_file_rewritten": False,
        "original_provider": original,
        "openai_api": "skipped" if skipped else "recorded",
        "assembly_eligible": assembly["assembly_eligible"],
        "prefix_cache_probe": cache_probe,
        "baseline": baseline_path.name if baseline else None,
        "cases": compare_rows,
    }
    _write(REPORTS / "assist-provider-compare.json", compare)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
