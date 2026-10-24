from __future__ import annotations

import logging
import os
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from psycopg import sql
from psycopg.types.json import Jsonb

from .config import (COLLECTIONS, DIMENSION, EMBEDDING_MODEL, EMBEDDING_REVISION, ROOT,
                     TOKENIZER_VERSION, embedding_signature)
from .data import load_sources
from .korean import KoreanTokenizer
from .models import Models
from .store import connect, metadata, read_status, set_metadata, table

log = logging.getLogger(__name__)


def ingest(faq_path: Path | None = None, cases_path: Path | None = None, reembed: bool = False) -> dict:
    docs, departments, _ = load_sources(faq_path or ROOT / "db/자주_묻는_민원.json",
                                       cases_path or ROOT / "db/공개_민원_사례.json")
    with connect(initialize=True) as conn:
        if not conn.execute("SELECT pg_try_advisory_lock(730402401) AS acquired").fetchone()["acquired"]:
            raise ValueError("다른 적재 작업이 실행 중입니다.")
        old_config = metadata(conn, "configuration")
        signature = embedding_signature()
        compatible = old_config and old_config["embedding_signature"] == signature
        if old_config and not compatible and not reembed:
            raise ValueError("임베딩 모델/본문 구성 변경: ingest --reembed가 필요합니다.")
        existing = {}
        if compatible and not reembed:
            for corpus in COLLECTIONS:
                rows = conn.execute(sql.SQL("SELECT source_id, embedding_hash, embedding FROM {}").format(table(corpus)))
                for row in rows:
                    row["embedding"] = row["embedding"].to_numpy()
                    existing[(corpus, row["source_id"])] = row
        conn.commit()

        cache_dir = Path(os.getenv("RAG_CACHE_DIR", "/cache" if Path("/cache").exists() else ROOT / ".rag-cache"))
        cache_dir.mkdir(parents=True, exist_ok=True)
        reused = cached = 0
        pending = []
        with sqlite3.connect(cache_dir / "embeddings.sqlite3") as cache:
            cache.execute("CREATE TABLE IF NOT EXISTS embeddings (signature TEXT, text_hash TEXT, vector BLOB, PRIMARY KEY(signature,text_hash))")
            for doc in docs:
                prior = existing.get((doc["corpus"], doc["source_id"]))
                if prior and prior["embedding_hash"] == doc["embedding_hash"]:
                    doc["embedding"] = prior["embedding"]
                    reused += 1
                    continue
                row = None if reembed else cache.execute(
                    "SELECT vector FROM embeddings WHERE signature=? AND text_hash=?",
                    (signature, doc["embedding_hash"])).fetchone()
                if row:
                    vector = np.frombuffer(row[0], dtype="<f4").copy()
                    if vector.shape == (DIMENSION,) and np.isfinite(vector).all():
                        doc["embedding"] = vector
                        cached += 1
                        continue
                pending.append(doc)
            log.info("문서 %d건: DB 재사용 %d, 캐시 재사용 %d, 새 임베딩 %d", len(docs), reused, cached, len(pending))
            if pending:
                models = Models()
                for start in range(0, len(pending), 128):
                    batch = pending[start:start + 128]
                    vectors = models.encode([doc["search_text"] for doc in batch])
                    for doc, vector in zip(batch, vectors, strict=True):
                        doc["embedding"] = vector
                        cache.execute("INSERT OR REPLACE INTO embeddings VALUES (?, ?, ?)",
                                      (signature, doc["embedding_hash"], vector.astype("<f4").tobytes()))
                    cache.commit()
                    log.info("임베딩 %d/%d 완료", min(start + 128, len(pending)), len(pending))

        tokenizer = KoreanTokenizer()
        for doc in docs:
            doc["terms"] = tokenizer.counts(doc["search_text"])
            doc["token_count"] = sum(doc["terms"].values())
            if not doc["token_count"]:
                raise ValueError(f"검색할 형태소가 없는 문서: {doc['source_id']}")
        log.info("한국어 토큰화 완료. 새 검색 스냅샷 저장 중")
        # 원문 검증/모델 추론이 모두 성공한 뒤 한 트랜잭션으로 교체합니다.
        write_departments(conn, departments)
        for corpus in COLLECTIONS:
            subset = [doc for doc in docs if doc["corpus"] == corpus]
            write_documents(conn, corpus, subset)
            conn.execute(sql.SQL("DELETE FROM {} WHERE NOT (source_id = ANY(%s))").format(table(corpus)),
                         ([doc["source_id"] for doc in subset],))
        conn.execute("DELETE FROM complaint_rag.department_directory WHERE NOT (department_id = ANY(%s))",
                     ([d["department_id"] for d in departments],))
        write_bm25(conn, docs)
        set_metadata(conn, "configuration", {
            "schema_version": 1, "embedding_model": EMBEDDING_MODEL,
            "embedding_revision": EMBEDDING_REVISION, "embedding_dimension": DIMENSION,
            "embedding_signature": signature, "tokenizer": TOKENIZER_VERSION,
        })
        set_metadata(conn, "last_ingestion", {
            "finished_at": datetime.now(timezone.utc).isoformat(), "source_documents": len(docs),
            "new_embeddings": len(pending), "reused_embeddings": reused, "cached_embeddings": cached,
            "source_files": {"faq": str(faq_path or "db/자주_묻는_민원.json"),
                             "routing": str(cases_path or "db/공개_민원_사례.json")},
        })
        conn.commit()
        for corpus in COLLECTIONS:
            conn.execute(sql.SQL("ANALYZE {}").format(table(corpus)))
        conn.execute("ANALYZE complaint_rag.term_postings")
        conn.execute("ANALYZE complaint_rag.term_statistics")
        return read_status(conn)


def write_departments(conn, departments: list[dict]):
    keys = list(departments[0])
    # 보완한 공식 업무분장/관할 검증 값은 재수집에서 덮어쓰지 않습니다.
    refreshed = ("canonical_name", "aliases", "name_checked_on", "name_source_urls", "observed_case_titles")
    query = sql.SQL("INSERT INTO complaint_rag.department_directory ({}) VALUES ({}) "
                    "ON CONFLICT (department_id) DO UPDATE SET {}, updated_at=now()").format(
        sql.SQL(", ").join(map(sql.Identifier, keys)),
        sql.SQL(", ").join(sql.Placeholder() for _ in keys),
        sql.SQL(", ").join(sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(k), sql.Identifier(k)) for k in refreshed))
    with conn.cursor() as cursor:
        cursor.executemany(query, [tuple(Jsonb(d[k]) if k == "jurisdiction" else d[k] for k in keys) for d in departments])


def write_documents(conn, corpus: str, docs: list[dict]):
    keys = ["source_id", "title", "search_text", "payload", "source_url", "source_retrieved_at",
            "content_hash", "embedding_hash", "embedding", "token_count"]
    keys += ["category"] if corpus == "faq" else ["complaint_date", "department_id", "department_status",
                                                 "district", "routing_eligible", "summary_missing"]
    rows = []
    for doc in docs:
        row = dict(doc, payload=Jsonb(doc["payload"]), source_url=doc["payload"]["source_url"],
                   source_retrieved_at=doc["payload"]["retrieved_at"])
        if corpus == "routing":
            row.update(complaint_date=doc["payload"].get("complaint_date") or None,
                       department_status=doc["payload"]["department_status"])
        rows.append(tuple(row[k] for k in keys))
    query = sql.SQL("INSERT INTO {} AS existing ({}) VALUES ({}) ON CONFLICT (source_id) DO UPDATE SET {}, updated_at=now() "
                    "WHERE existing.content_hash <> EXCLUDED.content_hash OR existing.embedding_hash <> EXCLUDED.embedding_hash "
                    "OR existing.embedding IS DISTINCT FROM EXCLUDED.embedding OR existing.token_count <> EXCLUDED.token_count").format(
        table(corpus), sql.SQL(", ").join(map(sql.Identifier, keys)),
        sql.SQL(", ").join(sql.Placeholder() for _ in keys),
        sql.SQL(", ").join(sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(k), sql.Identifier(k)) for k in keys if k != "source_id"))
    with conn.cursor() as cursor:
        cursor.executemany(query, rows)


def write_bm25(conn, docs: list[dict]):
    conn.execute("DELETE FROM complaint_rag.term_postings")
    conn.execute("DELETE FROM complaint_rag.term_statistics")
    conn.execute("DELETE FROM complaint_rag.corpus_statistics")
    with conn.cursor().copy("COPY complaint_rag.term_postings (corpus, term, source_id, tf) FROM STDIN") as copy:
        for doc in docs:
            for term, count in doc["terms"].items():
                copy.write_row((doc["corpus"], term, doc["source_id"], count))
    conn.execute("INSERT INTO complaint_rag.term_statistics "
                 "SELECT corpus, term, count(*) FROM complaint_rag.term_postings GROUP BY corpus, term")
    for corpus in COLLECTIONS:
        conn.execute(sql.SQL("INSERT INTO complaint_rag.corpus_statistics SELECT %s, count(*), avg(token_count) FROM {}").format(table(corpus)), (corpus,))
