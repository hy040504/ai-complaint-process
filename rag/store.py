"""PostgreSQL 연결과 검색 색인의 메타데이터·상태 조회를 관리합니다."""
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
    """표준 PG 환경변수로 연결하고 pgvector 타입을 등록합니다.

    Args:
        initialize: 연결 시 스키마와 색인이 없으면 생성할지 나타냅니다.

    Yields:
        호출자가 쿼리와 트랜잭션을 관리할 PostgreSQL 연결입니다.
    """
    with psycopg.connect(connect_timeout=10, row_factory=dict_row) as conn:
        if initialize:
            conn.execute(Path(__file__).with_name("schema.sql").read_text())
            conn.commit()
        register_vector(conn)
        conn.commit()  # 타입 등록 조회를 마쳐 호출자가 읽기 스냅샷을 새로 시작할 수 있게 합니다.
        yield conn


def table(corpus: str):
    """컬렉션에 대응하는 스키마와 테이블 식별자를 구성합니다.

    Args:
        corpus: faq 또는 routing 컬렉션 이름입니다.

    Returns:
        SQL 문자열과 안전하게 합성할 수 있는 테이블 식별자입니다.
    """
    return sql.Identifier("complaint_rag", COLLECTIONS[corpus])


def metadata(conn, key: str):
    """색인 메타데이터에서 지정한 키의 값을 읽습니다.

    Args:
        conn: PostgreSQL 연결입니다.
        key: 조회할 메타데이터 키입니다.

    Returns:
        저장된 JSON 값 또는 키가 없을 때 None입니다.
    """
    row = conn.execute("SELECT value FROM complaint_rag.index_metadata WHERE key = %s", (key,)).fetchone()
    return row["value"] if row else None


def set_metadata(conn, key: str, value):
    """색인 메타데이터 키의 JSON 값을 추가하거나 교체합니다.

    Args:
        conn: 호출자가 트랜잭션을 관리하는 PostgreSQL 연결입니다.
        key: 추가하거나 갱신할 메타데이터 키입니다.
        value: 저장할 JSON 직렬화 가능 값입니다.
    """
    conn.execute("INSERT INTO complaint_rag.index_metadata VALUES (%s, %s) "
                 "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (key, Jsonb(value)))


def check_index(conn):
    """저장된 색인의 임베딩 서명과 토크나이저 버전을 확인합니다.

    Args:
        conn: PostgreSQL 연결입니다.

    Raises:
        ValueError: 색인이 없거나 실행 코드와 색인 설정이 다르면 발생합니다.
    """
    config = metadata(conn, "configuration")
    if not config:
        raise ValueError("색인이 없습니다. 먼저 ingest를 실행해 주세요.")
    if config["embedding_signature"] != embedding_signature() or config["tokenizer"] != TOKENIZER_VERSION:
        raise ValueError("실행 코드와 색인 설정이 다릅니다. ingest --reembed로 재구축해 주세요.")


def read_status(conn) -> dict:
    """현재 문서·부서 건수와 색인·적재 메타데이터를 읽습니다.

    Args:
        conn: PostgreSQL 연결입니다.

    Returns:
        검토·업무 미검증 건수, 모델 설정, 최근 적재 정보를 포함한 상태입니다.
    """
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
