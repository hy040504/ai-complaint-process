from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .config import COLLECTIONS, TOKENIZER_VERSION, embedding_signature


@contextmanager
def connect(initialize: bool = False):
    # PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD 표준 환경변수로 연결합니다.
    with psycopg.connect(connect_timeout=10, row_factory=dict_row) as conn:
        if initialize:
            conn.execute(Path(__file__).with_name("schema.sql").read_text())
            conn.commit()
        register_vector(conn)
        conn.commit()  # 타입 등록 조회를 마쳐 호출자가 읽기 스냅샷을 새로 시작할 수 있게 합니다.
        yield conn


def table(corpus: str):
    return sql.Identifier("complaint_rag", COLLECTIONS[corpus])


def metadata(conn, key: str):
    row = conn.execute("SELECT value FROM complaint_rag.index_metadata WHERE key = %s", (key,)).fetchone()
    return row["value"] if row else None


def set_metadata(conn, key: str, value):
    conn.execute("INSERT INTO complaint_rag.index_metadata VALUES (%s, %s) "
                 "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (key, Jsonb(value)))


def check_index(conn):
    config = metadata(conn, "configuration")
    if not config:
        raise ValueError("색인이 없습니다. 먼저 ingest를 실행해 주세요.")
    if config["embedding_signature"] != embedding_signature() or config["tokenizer"] != TOKENIZER_VERSION:
        raise ValueError("실행 코드와 색인 설정이 다릅니다. ingest --reembed로 재구축해 주세요.")


def read_status(conn) -> dict:
    counts = {name: conn.execute(sql.SQL("SELECT count(*) AS n FROM {}").format(table(corpus))).fetchone()["n"]
              for corpus, name in COLLECTIONS.items()}
    counts["department_directory"] = conn.execute(
        "SELECT count(*) AS n FROM complaint_rag.department_directory").fetchone()["n"]
    counts["review_required"] = conn.execute(
        "SELECT count(*) AS n FROM complaint_rag.routing_cases WHERE NOT routing_eligible").fetchone()["n"]
    counts["duties_unverified"] = conn.execute(
        "SELECT count(*) AS n FROM complaint_rag.department_directory WHERE duty_status = 'unverified'").fetchone()["n"]
    return {"counts": counts, "configuration": metadata(conn, "configuration"),
            "last_ingestion": metadata(conn, "last_ingestion")}
