"""모델 리비전과 색인 서명, 검색 실행 설정을 정의합니다."""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COLLECTIONS = {"faq": "faq_knowledge", "routing": "routing_cases"}
DISTRICTS = ("상당구", "서원구", "흥덕구", "청원구")
EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
RERANKER_REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
DIMENSION = 1024
TOKENIZER_VERSION = "kiwi-0.24.1-content-words-v1"
TEXT_VERSION = "parent-document-v1"


def digest(value: object) -> str:
    """정렬된 JSON 표현의 SHA256 해시를 계산합니다.

    Args:
        value: JSON으로 직렬화할 수 있는 값입니다.

    Returns:
        원본·본문·설정 비교에 사용할 16진수 해시 문자열입니다.
    """
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def embedding_signature() -> str:
    """임베딩 모델·리비전·차원·정규화·본문 버전의 서명을 계산합니다.

    Returns:
        벡터 재사용 가능 여부를 비교할 해시 문자열입니다.
    """
    return digest({"model": EMBEDDING_MODEL, "revision": EMBEDDING_REVISION,
                   "dimension": DIMENSION, "normalized": True, "text_version": TEXT_VERSION})


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
