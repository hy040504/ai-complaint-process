"""임베딩을 재사용하고 검색 데이터를 한 트랜잭션으로 적재합니다."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from psycopg import sql
from psycopg.types.json import Jsonb

from .config import (
    CASES_JSON,
    COLLECTIONS,
    DIMENSION,
    EMBEDDING_MODEL,
    EMBEDDING_REVISION,
    FAQ_JSON,
    TOKENIZER_VERSION,
    embedding_signature,
)
from .data import load_sources
from .korean import KoreanTokenizer
from .models import Models
from .store import (
    align_embedding_dimension,
    connect,
    metadata,
    read_status,
    set_metadata,
    table,
)

log = logging.getLogger(__name__)
_CACHE_CHUNK = 500


def cached_vectors(conn, signature: str, hashes: list[str]) -> dict[str, np.ndarray]:
    """서명과 본문 해시로 체크포인트 벡터를 한꺼번에 읽습니다.

    Args:
        conn: 적재 트랜잭션의 PostgreSQL 연결입니다.
        signature: 임베딩 프로필 서명입니다.
        hashes: 조회할 `embedding_hash` 목록입니다.

    Returns:
        본문 해시를 키로 하는 float32 벡터 사전입니다. 차원·유한성 검사를
        통과한 행만 넣습니다.
    """
    found: dict[str, np.ndarray] = {}
    unique = list(dict.fromkeys(hashes))
    for start in range(0, len(unique), _CACHE_CHUNK):
        chunk = unique[start : start + _CACHE_CHUNK]
        rows = conn.execute(
            "SELECT text_hash, vector FROM complaint_rag.embedding_cache "
            "WHERE signature = %s AND text_hash = ANY(%s)",
            (signature, chunk),
        )
        for row in rows:
            vector = np.frombuffer(bytes(row["vector"]), dtype="<f4").copy()
            if vector.shape == (DIMENSION,) and np.isfinite(vector).all():
                found[row["text_hash"]] = vector
    return found


def ingest(
    faq_path: Path | None = None, cases_path: Path | None = None, reembed: bool = False
) -> dict:
    """벡터를 재사용하고 검증된 검색 데이터를 한 트랜잭션으로 교체합니다.

    Args:
        faq_path: FAQ 원본 경로입니다. None이면 기본 경로를 사용합니다.
        cases_path: 공개 사례 원본 경로입니다. None이면 기본 경로를 사용합니다.
        reembed: 기존 DB·체크포인트 벡터를 재사용하지 않고 다시 생성할지 나타냅니다.

    Returns:
        반영 후 건수·색인 설정·최근 적재 정보입니다.

    Raises:
        ValueError: 동시 적재·색인 비호환·잘못된 원본·토큰 또는 벡터 오류가 있으면 발생합니다.
    """
    docs, departments, _ = load_sources(faq_path or FAQ_JSON, cases_path or CASES_JSON)
    with connect(initialize=True) as conn:
        if not conn.execute(
            "SELECT pg_try_advisory_lock(730402401) AS acquired"
        ).fetchone()["acquired"]:
            raise ValueError("다른 적재 작업이 실행 중입니다.")
        old_config = metadata(conn, "configuration")
        signature = embedding_signature()
        compatible = old_config and old_config["embedding_signature"] == signature
        if old_config and not compatible and not reembed:
            raise ValueError(
                "임베딩 모델/본문 구성 변경: ingest --reembed가 필요합니다. "
                "기존 BGE-M3 색인을 쓰려면 RAG_EMBEDDING_PROFILE=bge-m3 입니다."
            )
        dimension_changed = False
        if not compatible or reembed:
            dimension_changed = align_embedding_dimension(conn)
        existing = {}
        if compatible and not reembed:
            for corpus in COLLECTIONS:
                rows = conn.execute(
                    sql.SQL(
                        "SELECT source_id, embedding_hash, embedding FROM {}"
                    ).format(table(corpus))
                )
                for row in rows:
                    row["embedding"] = row["embedding"].to_numpy()
                    existing[(corpus, row["source_id"])] = row
        conn.commit()

        reused = cached = 0
        pending = []
        need_cache = []
        for doc in docs:
            prior = existing.get((doc["corpus"], doc["source_id"]))
            if prior and prior["embedding_hash"] == doc["embedding_hash"]:
                doc["embedding"] = prior["embedding"]
                reused += 1
                continue
            if reembed:
                pending.append(doc)
            else:
                need_cache.append(doc)
        cache_hits = (
            cached_vectors(
                conn, signature, [doc["embedding_hash"] for doc in need_cache]
            )
            if need_cache
            else {}
        )
        for doc in need_cache:
            vector = cache_hits.get(doc["embedding_hash"])
            if vector is not None:
                doc["embedding"] = vector
                cached += 1
            else:
                pending.append(doc)
        log.info(
            "문서 %d건: DB 재사용 %d, 캐시 재사용 %d, 새 임베딩 %d",
            len(docs),
            reused,
            cached,
            len(pending),
        )
        if pending:
            models = Models()
            for start in range(0, len(pending), 128):
                batch = pending[start : start + 128]
                vectors = models.encode(
                    [doc["search_text"] for doc in batch], role="passage"
                )
                payloads = []
                for doc, vector in zip(batch, vectors, strict=True):
                    doc["embedding"] = vector
                    payloads.append(
                        (
                            signature,
                            doc["embedding_hash"],
                            vector.astype("<f4").tobytes(),
                        )
                    )
                conn.executemany(
                    "INSERT INTO complaint_rag.embedding_cache "
                    "(signature, text_hash, vector) VALUES (%s, %s, %s) "
                    "ON CONFLICT (signature, text_hash) DO UPDATE "
                    "SET vector = EXCLUDED.vector",
                    payloads,
                )
                conn.commit()
                log.info(
                    "임베딩 %d/%d 완료",
                    min(start + 128, len(pending)),
                    len(pending),
                )

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
            conn.execute(
                sql.SQL("DELETE FROM {} WHERE NOT (source_id = ANY(%s))").format(
                    table(corpus)
                ),
                ([doc["source_id"] for doc in subset],),
            )
            if dimension_changed:
                conn.execute(
                    sql.SQL(
                        "ALTER TABLE {} ALTER COLUMN embedding SET NOT NULL"
                    ).format(table(corpus))
                )
        conn.execute(
            "DELETE FROM complaint_rag.department_directory WHERE NOT (department_id = ANY(%s))",
            ([d["department_id"] for d in departments],),
        )
        write_bm25(conn, docs)
        set_metadata(
            conn,
            "configuration",
            {
                "schema_version": 1,
                "embedding_model": EMBEDDING_MODEL,
                "embedding_revision": EMBEDDING_REVISION,
                "embedding_dimension": DIMENSION,
                "embedding_signature": signature,
                "tokenizer": TOKENIZER_VERSION,
            },
        )
        set_metadata(
            conn,
            "last_ingestion",
            {
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "source_documents": len(docs),
                "new_embeddings": len(pending),
                "reused_embeddings": reused,
                "cached_embeddings": cached,
                "source_files": {
                    "faq": str(faq_path or "db/자주_묻는_민원.json"),
                    "routing": str(cases_path or "db/공개_민원_사례.json"),
                },
            },
        )
        conn.commit()
        for corpus in COLLECTIONS:
            conn.execute(sql.SQL("ANALYZE {}").format(table(corpus)))
        conn.execute("ANALYZE complaint_rag.term_postings")
        conn.execute("ANALYZE complaint_rag.term_statistics")
        return read_status(conn)


def write_departments(conn, departments: list[dict]):
    """부서를 갱신하고 동일 ID에 보완된 업무·관할 검증 값은 보존합니다.

    Args:
        conn: 호출자가 트랜잭션을 관리하는 PostgreSQL 연결입니다.
        departments: 최소 한 항목을 포함하는 부서 디렉터리입니다.
    """
    keys = list(departments[0])
    # 보완한 공식 업무분장/관할 검증 값은 재수집에서 덮어쓰지 않습니다.
    refreshed = (
        "canonical_name",
        "aliases",
        "name_checked_on",
        "name_source_urls",
        "observed_case_titles",
    )
    query = sql.SQL(
        "INSERT INTO complaint_rag.department_directory ({}) VALUES ({}) "
        "ON CONFLICT (department_id) DO UPDATE SET {}, updated_at=now()"
    ).format(
        sql.SQL(", ").join(map(sql.Identifier, keys)),
        sql.SQL(", ").join(sql.Placeholder() for _ in keys),
        sql.SQL(", ").join(
            sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(k), sql.Identifier(k))
            for k in refreshed
        ),
    )
    with conn.cursor() as cursor:
        cursor.executemany(
            query,
            [
                tuple(Jsonb(d[k]) if k == "jurisdiction" else d[k] for k in keys)
                for d in departments
            ],
        )


def write_documents(conn, corpus: str, docs: list[dict]):
    """문서·벡터를 저장하고 해시·벡터·토큰 수가 같은 기존 행은 건너뜁니다.

    Args:
        conn: 호출자가 트랜잭션을 관리하는 PostgreSQL 연결입니다.
        corpus: 저장할 컬렉션인 faq 또는 routing입니다.
        docs: 원본·벡터·토큰 수를 포함한 검색 문서 목록입니다.
    """
    keys = [
        "source_id",
        "title",
        "search_text",
        "payload",
        "source_url",
        "source_retrieved_at",
        "content_hash",
        "embedding_hash",
        "embedding",
        "token_count",
    ]
    keys += (
        ["category"]
        if corpus == "faq"
        else [
            "complaint_date",
            "department_id",
            "department_status",
            "district",
            "routing_eligible",
            "summary_missing",
        ]
    )
    rows = []
    for doc in docs:
        row = dict(
            doc,
            payload=Jsonb(doc["payload"]),
            source_url=doc["payload"]["source_url"],
            source_retrieved_at=doc["payload"]["retrieved_at"],
        )
        if corpus == "routing":
            row.update(
                complaint_date=doc["payload"].get("complaint_date") or None,
                department_status=doc["payload"]["department_status"],
            )
        rows.append(tuple(row[k] for k in keys))
    query = sql.SQL(
        "INSERT INTO {} AS existing ({}) VALUES ({}) ON CONFLICT (source_id) DO UPDATE SET {}, updated_at=now() "
        "WHERE existing.content_hash <> EXCLUDED.content_hash OR existing.embedding_hash <> EXCLUDED.embedding_hash "
        "OR existing.embedding IS DISTINCT FROM EXCLUDED.embedding OR existing.token_count <> EXCLUDED.token_count"
    ).format(
        table(corpus),
        sql.SQL(", ").join(map(sql.Identifier, keys)),
        sql.SQL(", ").join(sql.Placeholder() for _ in keys),
        sql.SQL(", ").join(
            sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(k), sql.Identifier(k))
            for k in keys
            if k != "source_id"
        ),
    )
    with conn.cursor() as cursor:
        cursor.executemany(query, rows)


def write_bm25(conn, docs: list[dict]):
    """전체 문서의 토큰 빈도와 컬렉션별 BM25 통계를 교체합니다.

    Args:
        conn: 호출자가 트랜잭션을 관리하는 PostgreSQL 연결입니다.
        docs: 모든 컬렉션의 토큰 빈도와 길이가 준비된 문서 목록입니다.
    """
    conn.execute("DELETE FROM complaint_rag.term_postings")
    conn.execute("DELETE FROM complaint_rag.term_statistics")
    conn.execute("DELETE FROM complaint_rag.corpus_statistics")
    with conn.cursor().copy(
        "COPY complaint_rag.term_postings (corpus, term, source_id, tf) FROM STDIN"
    ) as copy:
        for doc in docs:
            for term, count in doc["terms"].items():
                copy.write_row((doc["corpus"], term, doc["source_id"], count))
    conn.execute(
        "INSERT INTO complaint_rag.term_statistics "
        "SELECT corpus, term, count(*) FROM complaint_rag.term_postings GROUP BY corpus, term"
    )
    for corpus in COLLECTIONS:
        conn.execute(
            sql.SQL(
                "INSERT INTO complaint_rag.corpus_statistics SELECT %s, count(*), avg(token_count) FROM {}"
            ).format(table(corpus)),
            (corpus,),
        )
