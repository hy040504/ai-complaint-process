"""Windows에서 민원 문장을 받아 RAG 검색과 LLM 응대를 표시합니다."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.assist import EXAMPLES, render_assist, run_assist
from src.llm.settings import load_llm_env_file
from src.rag import search_api_url, search_available


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """명령줄 인자를 해석합니다.

    Args:
        argv: 인자 목록입니다. None이면 `sys.argv`를 씁니다.

    Returns:
        해석한 이름공간입니다.
    """
    parser = argparse.ArgumentParser(
        description="민원 문장으로 RAG 검색과 LLM 응대를 확인합니다."
    )
    parser.add_argument("query", nargs="*", help="한국어 민원 문장")
    parser.add_argument(
        "--example",
        choices=["faq", "action", "routing", "handoff", "district"],
        help="고정 예시 질문을 사용합니다",
    )
    parser.add_argument("--district", choices=["상당구", "서원구", "흥덕구", "청원구"])
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument(
        "--rerank",
        action="store_true",
        help="재정렬 모델을 켭니다. 기본은 끈 상태입니다.",
    )
    parser.add_argument("--json", action="store_true", help="원본 JSON만 출력합니다")
    parser.add_argument(
        "--api-url",
        default=os.getenv("RAG_API_URL", "http://127.0.0.1:8007"),
    )
    return parser.parse_args(argv)


def resolve_query(args: argparse.Namespace) -> tuple[str, str | None]:
    """민원 문장과 관할 구를 고릅니다.

    Args:
        args: 해석한 인자입니다.

    Returns:
        질문 문자열과 관할 구입니다.

    Raises:
        ValueError: 문장이 비어 있는 경우 발생합니다.
    """
    query = " ".join(args.query).strip()
    district = args.district
    if args.example:
        sample = next(item for item in EXAMPLES if item["id"] == args.example)
        query = query or str(sample["query"])
        if district is None:
            district = sample["district"]
    if not query:
        try:
            query = input("민원 내용을 입력하세요: ").strip()
        except EOFError as exc:
            raise ValueError("민원 문장 또는 --example 을 지정해 주세요.") from exc
    if not query:
        raise ValueError("민원 문장 또는 --example 을 지정해 주세요.")
    return query, district


def main(argv: list[str] | None = None) -> int:
    """검색 API와 LLM 설정을 확인한 뒤 응대 결과를 출력합니다.

    Args:
        argv: 인자 목록입니다.

    Returns:
        성공 0, 설정·검색 실패 1입니다.
    """
    load_llm_env_file()
    args = parse_args(argv)
    os.environ["RAG_API_URL"] = args.api_url.rstrip("/")
    try:
        query, district = resolve_query(args)
    except ValueError as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        return 1
    if not search_available():
        print(
            "[오류] 검색 API에 연결하지 못했습니다. "
            f"{search_api_url()} 에서 python -m rag serve 가 실행 중인지 확인하세요.",
            file=sys.stderr,
        )
        return 1

    def on_progress(_key: str, label: str) -> None:
        """진행 단계 설명을 표준 출력에 바로 씁니다.

        Args:
            _key: 내부 단계 식별자이며 표시에는 쓰지 않습니다.
            label: 화면에 보일 짧은 안내입니다.
        """
        print(f"... {label}", flush=True)

    print(f"민원: {query}")
    if district:
        print(f"관할: {district}")
    try:
        result = run_assist(
            query,
            district,
            limit=args.limit,
            rerank=args.rerank,
            on_progress=None if args.json else on_progress,
        )
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print()
    print(render_assist(result))
    if not result.get("llm_configured"):
        print()
        print(
            "안내: LLM이 설정되지 않아 검색 근거와 담당자 검토 사유만 표시했습니다. "
            ".env의 COMPLAINT_LLM_PROVIDER를 확인하세요."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
