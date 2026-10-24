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
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def embedding_signature() -> str:
    return digest({"model": EMBEDDING_MODEL, "revision": EMBEDDING_REVISION,
                   "dimension": DIMENSION, "normalized": True, "text_version": TEXT_VERSION})


@dataclass(frozen=True)
class Settings:
    device: str = os.getenv("RAG_DEVICE", "cpu")
    threads: int = int(os.getenv("RAG_THREADS", "4"))
    batch_size: int = int(os.getenv("RAG_BATCH_SIZE", "8"))
    candidate_k: int = 30
    rerank_k: int = 20
    rrf_k: int = 60
    bm25_k1: float = 1.5
    bm25_b: float = 0.75

    def __post_init__(self):
        if not 1 <= self.threads <= 32 or not 1 <= self.batch_size <= 64:
            raise ValueError("RAG_THREADS는 1~32, RAG_BATCH_SIZE는 1~64여야 합니다.")
