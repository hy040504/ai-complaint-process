"""한 문장을 RAG 검색과 같은 모델로 임베딩해 벡터 숫자를 출력합니다.

PostgreSQL, 검색 API, LLM을 쓰지 않습니다. 저장소 루트 `.venv`에서
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
        description="한 문장의 임베딩 벡터 숫자를 출력합니다. 검색 API는 쓰지 않습니다."
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
        help="모델·차원·문장·벡터를 JSON으로 출력합니다.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="벡터 숫자만 공백으로 구분해 출력합니다.",
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


def format_vector(
    values: list[float], *, raw: bool, as_json: bool, meta: dict[str, Any]
) -> str:
    """벡터와 부가 정보를 문자열로 만듭니다.

    Args:
        values: 차원 순서의 부동소수 목록입니다.
        raw: True이면 숫자만 공백으로 구분합니다.
        as_json: True이면 JSON 객체를 만듭니다. raw보다 우선합니다.
        meta: 모델·리비전·차원·역할·접두·문장·노름입니다.

    Returns:
        표준 출력에 쓸 문자열입니다.
    """
    if as_json:
        payload = {**meta, "vector": values}
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
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """문장을 임베딩하고 벡터를 출력합니다.

    Args:
        argv: 명령줄 인자입니다. None이면 `sys.argv`를 씁니다.

    Returns:
        성공 0, 입력 오류 2입니다.
    """
    args = parse_args(argv)
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
    values = [float(item) for item in vector.tolist()]
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
    print(format_vector(values, raw=args.raw, as_json=args.json, meta=meta))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
