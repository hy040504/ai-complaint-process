"""모델 리비전과 색인 서명, 검색 실행 설정을 정의합니다."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# 검색 원본 JSON·DDL·벡터 dump. 시연 웹 DDL은 src/complaints/schema.
ORIGIN_DIR = Path(__file__).resolve().parent / "origin"
FAQ_JSON = ORIGIN_DIR / "자주_묻는_민원.json"
CASES_JSON = ORIGIN_DIR / "공개_민원_사례.json"
RAG_SCHEMA_SQL = ORIGIN_DIR / "schema" / "complaint_rag.sql"
RAG_DUMP = ORIGIN_DIR / "dumps" / "complaint_rag.dump"
COLLECTIONS = {"faq": "faq_knowledge", "routing": "routing_cases"}
DISTRICTS = ("상당구", "서원구", "흥덕구", "청원구")
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
RERANKER_REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
TOKENIZER_VERSION = "kiwi-0.24.1-content-words-v1"
TEXT_VERSION = "parent-document-v1"

# 기본은 한국어 미세조정 e5-small. 이전 intfloat 색인은 e5-small, 1024차원은 bge-m3.
EMBEDDING_PROFILES = {
    "e5-small-ko": {
        "model": "dragonkue/multilingual-e5-small-ko",
        "revision": "bba4cb8e3299d445c04f62bf62e2b26461d03715",
        "dimension": 384,
        "max_seq_length": 512,
        "query_prefix": "query: ",
        "passage_prefix": "passage: ",
    },
    "e5-small": {
        "model": "intfloat/multilingual-e5-small",
        "revision": "960310a7742a4e0a250dd720466bed84fee8caac",
        "dimension": 384,
        "max_seq_length": 512,
        "query_prefix": "query: ",
        "passage_prefix": "passage: ",
    },
    "bge-m3": {
        "model": "BAAI/bge-m3",
        "revision": "5617a9f61b028005a4858fdac845db406aefb181",
        "dimension": 1024,
        "max_seq_length": 8192,
        "query_prefix": "",
        "passage_prefix": "",
    },
}


def _text_env(name: str, default: str) -> str:
    """환경변수 문자열을 읽고 비면 기본값을 씁니다.

    Args:
        name: 환경변수 이름입니다.
        default: 없거나 공백일 때 쓸 값입니다.

    Returns:
        비어 있지 않은 문자열입니다.
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip()
    return value or default


def _int_env(name: str, default: int) -> int:
    """환경변수 정수를 읽고 비면 기본값을 씁니다.

    Args:
        name: 환경변수 이름입니다.
        default: 없거나 공백일 때 쓸 값입니다.

    Returns:
        정수 값입니다.
    """
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    return int(raw)


def embedding_profile_name() -> str:
    """선택한 임베딩 프로필 이름을 반환합니다.

    Returns:
        `e5-small-ko`, `e5-small`, `bge-m3` 중 하나입니다.

    Raises:
        ValueError: 알 수 없는 프로필 이름이면 발생합니다.
    """
    name = _text_env("RAG_EMBEDDING_PROFILE", "e5-small-ko").lower()
    if name not in EMBEDDING_PROFILES:
        allowed = ", ".join(sorted(EMBEDDING_PROFILES))
        raise ValueError(f"RAG_EMBEDDING_PROFILE는 {allowed} 중 하나여야 합니다.")
    return name


_PROFILE = EMBEDDING_PROFILES[embedding_profile_name()]
EMBEDDING_MODEL = _text_env("RAG_EMBEDDING_MODEL", str(_PROFILE["model"]))
EMBEDDING_REVISION = _text_env("RAG_EMBEDDING_REVISION", str(_PROFILE["revision"]))
DIMENSION = _int_env("RAG_EMBEDDING_DIMENSION", int(_PROFILE["dimension"]))
EMBEDDING_MAX_SEQ = _int_env("RAG_EMBEDDING_MAX_SEQ", int(_PROFILE["max_seq_length"]))
EMBEDDING_QUERY_PREFIX = os.getenv(
    "RAG_EMBEDDING_QUERY_PREFIX", str(_PROFILE["query_prefix"])
)
EMBEDDING_PASSAGE_PREFIX = os.getenv(
    "RAG_EMBEDDING_PASSAGE_PREFIX", str(_PROFILE["passage_prefix"])
)


def digest(value: object) -> str:
    """정렬된 JSON 표현의 SHA256 해시를 계산합니다.

    Args:
        value: JSON으로 직렬화할 수 있는 값입니다.

    Returns:
        원본·본문·설정 비교에 사용할 16진수 해시 문자열입니다.
    """
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def embedding_signature() -> str:
    """임베딩 모델·리비전·차원·접두·정규화·본문 버전의 서명을 계산합니다.

    Returns:
        벡터 재사용 가능 여부를 비교할 해시 문자열입니다.
    """
    return digest(
        {
            "model": EMBEDDING_MODEL,
            "revision": EMBEDDING_REVISION,
            "dimension": DIMENSION,
            "max_seq_length": EMBEDDING_MAX_SEQ,
            "query_prefix": EMBEDDING_QUERY_PREFIX,
            "passage_prefix": EMBEDDING_PASSAGE_PREFIX,
            "normalized": True,
            "text_version": TEXT_VERSION,
        }
    )


def prefixed_texts(texts: list[str], role: str) -> list[str]:
    """임베딩 모델이 요구하는 질문·문서 접두를 붙입니다.

    Args:
        texts: 원문 목록입니다.
        role: `query` 또는 `passage`입니다.

    Returns:
        접두를 붙인 문자열 목록입니다. 접두가 비면 원문 그대로입니다.

    Raises:
        ValueError: role이 query/passage가 아니면 발생합니다.
    """
    prefixes = {
        "query": EMBEDDING_QUERY_PREFIX,
        "passage": EMBEDDING_PASSAGE_PREFIX,
    }
    try:
        prefix = prefixes[role]
    except KeyError as exc:
        raise ValueError("role은 query 또는 passage여야 합니다.") from exc
    if not prefix:
        return list(texts)
    return [prefix + text for text in texts]


@lru_cache(maxsize=1)
def schema_sql() -> str:
    """현재 임베딩 차원을 넣은 검색 스키마 SQL을 반환합니다.

    프로세스에서 한 번만 파일을 읽습니다. 차원은 모듈 적재 시점의
    `DIMENSION`을 씁니다.

    Returns:
        `__EMBEDDING_DIM__`을 `DIMENSION`으로 바꾼 DDL입니다.
    """
    return RAG_SCHEMA_SQL.read_text(encoding="utf-8").replace(
        "__EMBEDDING_DIM__", str(DIMENSION)
    )


@dataclass(frozen=True)
class Settings:
    """모델 실행 자원과 검색 후보·순위 결합 설정을 보관합니다.

    Attributes:
        device: 모델을 실행할 장치입니다.
        threads: 모델 연산에 사용할 CPU 스레드 수입니다.
        batch_size: 임베딩 배치 크기이며 재정렬 배치의 상한에도 사용합니다.
        candidate_k: 각 검색기가 가져올 후보 수입니다.
        rerank_k: 재정렬 후보 수입니다. 반환 수가 더 크면 그만큼 확보합니다.
        rrf_k: 순위 결합의 완화 상수입니다.
        bm25_k1: BM25 단어 빈도 포화 계수입니다.
        bm25_b: BM25 문서 길이 보정 계수입니다.
    """

    device: str = os.getenv("RAG_DEVICE", "cpu")
    threads: int = int(os.getenv("RAG_THREADS", "4"))
    batch_size: int = int(os.getenv("RAG_BATCH_SIZE", "8"))
    candidate_k: int = 30
    rerank_k: int = 20
    rrf_k: int = 60
    bm25_k1: float = 1.5
    bm25_b: float = 0.75

    def __post_init__(self):
        """모델 실행 자원이 허용 범위 안에 있는지 확인합니다.

        Raises:
            ValueError: 스레드가 1~32 또는 배치 크기가 1~64 범위를 벗어나면 발생합니다.
        """
        if not 1 <= self.threads <= 32 or not 1 <= self.batch_size <= 64:
            raise ValueError("RAG_THREADS는 1~32, RAG_BATCH_SIZE는 1~64여야 합니다.")
