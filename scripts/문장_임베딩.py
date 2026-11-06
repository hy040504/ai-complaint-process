"""한 문장을 RAG 검색과 같은 모델로 임베딩하고 pgvector 이웃을 출력합니다.

기본은 FAQ와 공개 사례를 컬렉션별로 코사인 유사도 순으로 보여 줍니다.
`--raw`와 `--no-search`는 벡터만 출력합니다. 저장소 루트 `.venv`에서
실행합니다. 기본 역할은 검색 질문(`query: ` 접두)입니다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """명령줄 인자를 해석합니다.

    Args:
        argv: 인자 목록입니다. None이면 `sys.argv`를 씁니다.

    Returns:
        해석한 이름공간입니다.
    """
    parser = argparse.ArgumentParser(
        description="한 문장을 임베딩한 뒤 pgvector로 비슷한 FAQ·사례를 찾습니다."
    )
    parser.add_argument("text", nargs="*", help="임베딩할 한국어 문장")
    parser.add_argument(
        "--role",
        choices=["query", "passage"],
        default="query",
        help="query는 검색 질문, passage는 적재 문서 접두입니다.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="모델·차원·문장·벡터와 이웃을 JSON으로 출력합니다.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="벡터 숫자만 공백으로 구분해 출력합니다. pgvector는 조회하지 않습니다.",
    )
    parser.add_argument(
        "--no-search",
        action="store_true",
        help="벡터만 출력하고 pgvector는 조회하지 않습니다.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="컬렉션별 이웃 수입니다. 1~20, 기본 5.",
    )
    parser.add_argument(
        "--district",
        choices=["상당구", "서원구", "흥덕구", "청원구"],
        help="공개 사례에만 적용하는 관할 구입니다.",
    )
    return parser.parse_args(argv)


def resolve_text(args: argparse.Namespace) -> str:
    """위치 인자를 한 문장으로 이어 붙입니다.

    Args:
        args: `parse_args` 결과입니다.

    Returns:
        앞뒤 공백을 제거한 문장입니다.

    Raises:
        ValueError: 문장이 비어 있으면 발생합니다.
    """
    text = " ".join(args.text).strip()
    if not text:
        raise ValueError("임베딩할 문장을 인자로 넣어 주세요.")
    return text


def excerpt(text: str, width: int = 80) -> str:
    """검색 본문을 한 줄 미리보기로 줄입니다.

    Args:
        text: 저장된 검색 본문입니다.
        width: 남길 최대 글자 수입니다.

    Returns:
        공백을 한 칸으로 접고 길이를 제한한 문자열입니다.
    """
    compact = " ".join(str(text or "").split())
    if len(compact) <= width:
        return compact
    return compact[: width - 1] + "…"


def shape_neighbors(corpus: str, ranked: list[dict], found: dict) -> list[dict]:
    """벡터 순위와 원문 행을 출력용 이웃으로 맞춥니다.

    Args:
        corpus: `faq` 또는 `routing`입니다.
        ranked: `source_id`와 `score`가 있는 순위순 행입니다.
        found: 출처 ID를 키로 하는 원문 행입니다.

    Returns:
        제목·점수·미리보기와, 사례이면 부서 후보 필드를 담은 목록입니다.
    """
    hits = []
    for rank, row in enumerate(ranked, 1):
        item = found[row["source_id"]]
        hit: dict[str, Any] = {
            "rank": rank,
            "corpus": corpus,
            "source_id": item["source_id"],
            "title": item["title"],
            "source_url": item["source_url"],
            "score": float(row["score"]),
            "excerpt": excerpt(item.get("search_text") or ""),
        }
        if corpus == "routing":
            hit["routing_eligible"] = bool(item.get("routing_eligible"))
            hit["department_name"] = item.get("canonical_name")
            hit["district"] = item.get("district")
            hit["duty_status"] = item.get("duty_status")
        hits.append(hit)
    return hits


def vector_neighbors(
    vector: Any, *, limit: int, district: str | None
) -> dict[str, list]:
    """이미 만든 질문 벡터로 FAQ·사례 이웃을 각각 조회합니다.

    Args:
        vector: 정규화된 임베딩 한 개입니다.
        limit: 컬렉션별 상한입니다.
        district: 공개 사례에만 쓰는 관할 구입니다.

    Returns:
        `faq`와 `routing` 키를 가진 이웃 목록입니다.

    Raises:
        ValueError: 색인이 없거나 실행 중인 임베딩 설정과 다르면 발생합니다.
    """
    from rag.search import dense_search, fetch_candidates
    from rag.store import check_index, connect

    groups: dict[str, list] = {}
    with connect() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        check_index(conn)
        conn.execute("SET LOCAL hnsw.ef_search = 100")
        conn.execute("SET LOCAL hnsw.iterative_scan = 'strict_order'")
        for corpus in ("faq", "routing"):
            ranked = dense_search(conn, corpus, vector, limit, district)
            ids = [row["source_id"] for row in ranked]
            found = fetch_candidates(conn, corpus, ids) if ids else {}
            groups[corpus] = shape_neighbors(corpus, ranked, found)
    return groups


def format_neighbors(groups: dict[str, list]) -> str:
    """컬렉션별 이웃을 사람이 읽는 문장으로 만듭니다.

    Args:
        groups: `faq`와 `routing` 이웃 목록입니다.

    Returns:
        점수·출처·미리보기를 담은 문자열입니다.
    """
    lines = [
        "",
        "pgvector 코사인 이웃. FAQ와 공개 사례는 따로 조회합니다.",
        "점수는 자동 답변 확률이 아닙니다. 사례의 과거 답변은 현재 정책 안내가 아닙니다.",
    ]
    labels = {"faq": "FAQ", "routing": "공개 사례"}
    for corpus in ("faq", "routing"):
        lines.append("")
        lines.append(f"[{labels[corpus]}]")
        hits = groups.get(corpus) or []
        if not hits:
            lines.append("결과 없음")
            continue
        for hit in hits:
            lines.append(
                f"{hit['rank']}. {hit['score']:.4f}  {hit['source_id']}  {hit['title']}"
            )
            if corpus == "routing":
                if hit.get("routing_eligible") and hit.get("department_name"):
                    area = hit.get("district") or "관할 미확인"
                    lines.append(
                        f"   부서 후보: {hit['department_name']} · {area} · {hit.get('duty_status')}"
                    )
                else:
                    lines.append("   부서 확정 근거에서 제외")
            if hit.get("excerpt"):
                lines.append(f"   {hit['excerpt']}")
            if hit.get("source_url"):
                lines.append(f"   {hit['source_url']}")
    return "\n".join(lines)


def format_vector(
    values: list[float],
    *,
    raw: bool,
    as_json: bool,
    meta: dict[str, Any],
    neighbors: dict[str, list] | None = None,
) -> str:
    """벡터와 부가 정보를 문자열로 만듭니다.

    Args:
        values: 차원 순서의 부동소수 목록입니다.
        raw: True이면 숫자만 공백으로 구분합니다.
        as_json: True이면 JSON 객체를 만듭니다. raw보다 우선합니다.
        meta: 모델·리비전·차원·역할·접두·문장·노름입니다.
        neighbors: pgvector 이웃입니다. None이면 벡터만 출력합니다.

    Returns:
        표준 출력에 쓸 문자열입니다.
    """
    if as_json:
        payload: dict[str, Any] = {**meta, "vector": values}
        if neighbors is not None:
            payload["retrieval_only"] = True
            payload["decision"] = "requires_gate"
            payload["neighbors"] = neighbors
        return json.dumps(payload, ensure_ascii=False, indent=2)
    numbers = " ".join(f"{item:.8f}" for item in values)
    if raw:
        return numbers
    lines = [
        f"모델: {meta['model']}",
        f"리비전: {meta['revision']}",
        f"차원: {meta['dimension']}",
        f"역할: {meta['role']}",
        f"접두: {meta['prefix']!r}",
        f"문장: {meta['text']}",
        f"노름: {meta['norm']:.8f}",
        "벡터:",
        numbers,
    ]
    text = "\n".join(lines)
    if neighbors is not None:
        text += format_neighbors(neighbors)
    return text


def main(argv: list[str] | None = None) -> int:
    """문장을 임베딩하고, 요청하면 pgvector 이웃을 출력합니다.

    Args:
        argv: 명령줄 인자입니다. None이면 `sys.argv`를 씁니다.

    Returns:
        성공 0, pgvector 실패 1, 입력 오류 2입니다.
    """
    args = parse_args(argv)
    if not 1 <= args.limit <= 20:
        print("[오류] --limit 은 1~20입니다.", file=sys.stderr)
        return 2
    try:
        text = resolve_text(args)
    except ValueError as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        return 2

    os.chdir(ROOT)
    os.environ.setdefault("HF_HOME", str(ROOT / ".rag-cache" / "huggingface"))
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("RAG_DEVICE", "cpu")

    from rag.config import (
        DIMENSION,
        EMBEDDING_MODEL,
        EMBEDDING_PASSAGE_PREFIX,
        EMBEDDING_QUERY_PREFIX,
        EMBEDDING_REVISION,
    )
    from rag.models import Models

    models = Models()
    vector = models.encode([text], role=args.role)[0]
    norm = float((vector * vector).sum() ** 0.5)
    values = [float(item) for item in vector]
    prefix = (
        EMBEDDING_QUERY_PREFIX if args.role == "query" else EMBEDDING_PASSAGE_PREFIX
    )
    meta = {
        "model": EMBEDDING_MODEL,
        "revision": EMBEDDING_REVISION,
        "dimension": DIMENSION,
        "role": args.role,
        "prefix": prefix,
        "text": text,
        "norm": norm,
    }
    neighbors = None
    if not args.raw and not args.no_search:
        try:
            neighbors = vector_neighbors(
                vector, limit=args.limit, district=args.district
            )
        except Exception as exc:
            print(
                format_vector(values, raw=False, as_json=args.json, meta=meta),
            )
            print(f"[오류] pgvector 검색에 실패했습니다: {exc}", file=sys.stderr)
            return 1
    print(
        format_vector(
            values,
            raw=args.raw,
            as_json=args.json,
            meta=meta,
            neighbors=neighbors,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
