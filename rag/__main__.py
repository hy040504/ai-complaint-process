"""검색 클라이언트는 표준 라이브러리만 사용합니다: python3 -m rag search '민원'."""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def api_request(url: str, payload=None):
    """JSON 요청을 보내고 응답을 읽습니다.

    Args:
        url: 호출할 API의 전체 주소입니다.
        payload: POST 요청 본문입니다. None이면 GET으로 요청합니다.

    Returns:
        JSON으로 해석한 API 응답입니다.

    Raises:
        ValueError: HTTP 오류나 API 연결 실패가 발생한 경우 발생합니다.
    """
    data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise ValueError(f"API {exc.code}: {message}") from None
    except urllib.error.URLError as exc:
        raise ValueError(f"검색 API에 연결할 수 없습니다 ({url}). systemctl --user status cheongju-rag.service 또는 네이티브 실행 상태를 확인해 주세요: {exc.reason}") from None


def main():
    """명령줄 옵션에 따라 적재·검색·상태 조회·API 실행을 수행합니다."""
    parser = argparse.ArgumentParser(description="청주 민원 RAG 근거 검색/색인")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("ingest", help="두 원본 JSON으로 벡터/BM25 색인 동기화")
    p.add_argument("--faq", type=Path)
    p.add_argument("--cases", type=Path)
    p.add_argument("--reembed", action="store_true", help="벡터 캐시를 사용하지 않고 다시 생성")
    p = sub.add_parser("search", help="실행 중인 API에서 FAQ/부서 추천 근거 검색")
    p.add_argument("query")
    p.add_argument("--collection", choices=["faq", "routing", "both"], default="both")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--district", choices=["상당구", "서원구", "흥덕구", "청원구"])
    p.add_argument("--no-rerank", action="store_true", help="RRF까지만 실행하여 검색 비교")
    p.add_argument("--api-url", default=os.getenv("RAG_API_URL", "http://127.0.0.1:8007"))
    p = sub.add_parser("assist", help="검색 근거로 LLM 판정·정책 검사 응대")
    p.add_argument("query", nargs="?", default="")
    p.add_argument("--example", choices=["faq", "action", "routing", "handoff", "district"])
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--district", choices=["상당구", "서원구", "흥덕구", "청원구"])
    p.add_argument("--no-rerank", action="store_true")
    p.add_argument("--json", action="store_true", help="원본 JSON만 출력")
    p.add_argument("--api-url", default=os.getenv("RAG_API_URL", "http://127.0.0.1:8007"))
    p = sub.add_parser("status", help="적재 건수/설정 확인")
    p.add_argument("--direct", action="store_true", help="API 대신 PostgreSQL 직접 조회")
    p.add_argument("--api-url", default=os.getenv("RAG_API_URL", "http://127.0.0.1:8007"))
    p = sub.add_parser("serve", help="모델을 메모리에 유지하는 검색 API")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8007)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stderr)
    try:
        if args.command == "ingest":
            from .ingest import ingest
            result = ingest(args.faq, args.cases, args.reembed)
        elif args.command == "search":
            result = api_request(args.api_url.rstrip("/") + "/search", {
                "query": args.query, "collection": args.collection, "limit": args.limit,
                "district": args.district, "rerank": not args.no_rerank})
        elif args.command == "assist":
            from .assist import EXAMPLES, render_assist, run_assist

            query = args.query
            district = args.district
            if args.example:
                sample = next(item for item in EXAMPLES if item["id"] == args.example)
                query = query or str(sample["query"])
                if district is None:
                    district = sample["district"]
            if not query:
                raise ValueError("민원 문장 또는 --example 을 지정해 주세요.")
            os.environ["RAG_API_URL"] = args.api_url
            result = run_assist(
                query,
                district,
                limit=args.limit,
                rerank=not args.no_rerank,
            )
            if not args.json:
                print(render_assist(result))
                return
        elif args.command == "status":
            if args.direct:
                from .store import connect, read_status
                with connect() as conn:
                    result = read_status(conn)
            else:
                result = api_request(args.api_url.rstrip("/") + "/health")
        elif args.command == "serve":
            import uvicorn
            uvicorn.run("rag.api:app", host=args.host, port=args.port, workers=1)
            return
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    except (ValueError, OSError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
