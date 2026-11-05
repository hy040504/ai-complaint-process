"""PostgreSQL 연결과 검색 색인의 메타데이터·상태 조회를 관리합니다."""

from __future__ import annotations

import os
from contextlib import contextmanager

import psycopg
from pgvector.psycopg import register_vector
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .config import (
    COLLECTIONS,
    DIMENSION,
    TOKENIZER_VERSION,
    embedding_signature,
    schema_sql,
)

_HNSW_INDEX = {
    "faq_knowledge": "faq_embedding_hnsw",
    "routing_cases": "routing_embedding_hnsw",
}


def apply_connect_defaults() -> None:
    """Windows에서 비어 있는 libpq 연결 기본값을 채웁니다.

    Linux 네이티브 환경은 `scripts/native-env.sh`가 소켓과 계정을 지정하므로
    여기서 덮어쓰지 않습니다. 이미 있는 환경변수는 유지합니다.
    검색 엔진은 `scripts/`를 의존하지 않습니다. CMD 기동 쪽 같은 기본값은
    `scripts/console_spawn.py`의 `apply_windows_libpq`입니다.
    """
    if os.name != "nt":
        return
    os.environ.setdefault("PGHOST", "127.0.0.1")
    os.environ.setdefault("PGPORT", "5432")
    os.environ.setdefault("PGDATABASE", "complaints_native")
    user = os.environ.get("USERNAME") or os.environ.get("USER")
    if user:
        os.environ.setdefault("PGUSER", user)


@contextmanager
def connect(initialize: bool = False):
    """표준 PG 환경변수로 연결하고 pgvector 타입을 등록합니다.

    `PGHOST`/`PGPORT`/`PGDATABASE`/`PGUSER`/`PGPASSWORD`를 사용합니다.
    Windows에서 값이 비면 localhost의 `complaints_native`를 씁니다.

    Args:
        initialize: 연결 시 스키마와 색인이 없으면 생성할지 나타냅니다.

    Yields:
        호출자가 쿼리와 트랜잭션을 관리하는 PostgreSQL 연결입니다.
    """
    apply_connect_defaults()
    with psycopg.connect(connect_timeout=10, row_factory=dict_row) as conn:
        if initialize:
            conn.execute(schema_sql())
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
    row = conn.execute(
        "SELECT value FROM complaint_rag.index_metadata WHERE key = %s", (key,)
    ).fetchone()
    return row["value"] if row else None


def set_metadata(conn, key: str, value):
    """색인 메타데이터 키의 JSON 값을 추가하거나 교체합니다.

    Args:
        conn: 호출자가 트랜잭션을 관리하는 PostgreSQL 연결입니다.
        key: 추가하거나 갱신할 메타데이터 키입니다.
        value: 저장할 JSON 직렬화 가능 값입니다.
    """
    conn.execute(
        "INSERT INTO complaint_rag.index_metadata VALUES (%s, %s) "
        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
        (key, Jsonb(value)),
    )


def parse_vector_dimension(type_name: str) -> int | None:
    """`vector(n)` 형식의 자료형 이름에서 차원을 꺼냅니다.

    Args:
        type_name: PostgreSQL `format_type` 결과입니다.

    Returns:
        양의 정수 차원 또는 형식이 아니면 None입니다.
    """
    text = type_name.strip()
    if not text.startswith("vector(") or not text.endswith(")"):
        return None
    inner = text[7:-1]
    if not inner.isdigit():
        return None
    return int(inner)


def embedding_column_dimension(conn, table_name: str) -> int | None:
    """검색 테이블 임베딩 열의 현재 차원을 읽습니다.

    Args:
        conn: PostgreSQL 연결입니다.
        table_name: `faq_knowledge` 또는 `routing_cases`입니다.

    Returns:
        저장된 차원 또는 열이 없으면 None입니다.
    """
    row = conn.execute(
        """
        SELECT format_type(a.atttypid, a.atttypmod) AS typ
        FROM pg_attribute a
        JOIN pg_class c ON a.attrelid = c.oid
        JOIN pg_namespace n ON c.relnamespace = n.oid
        WHERE n.nspname = 'complaint_rag'
          AND c.relname = %s
          AND a.attname = 'embedding'
          AND NOT a.attisdropped
        """,
        (table_name,),
    ).fetchone()
    if not row or not row["typ"]:
        return None
    return parse_vector_dimension(str(row["typ"]))


def align_embedding_dimension(conn) -> bool:
    """임베딩 열 차원을 현재 설정과 맞춥니다.

    차원이 다르면 HNSW 색인과 임베딩 열을 다시 만듭니다. 원문 행은 남기고
    벡터 열은 NULL 허용으로 두었다가 적재가 채운 뒤 NOT NULL을 겁니다.

    Args:
        conn: 호출자가 트랜잭션을 관리하는 PostgreSQL 연결입니다.

    Returns:
        열을 다시 만든 테이블이 있으면 True입니다.
    """
    changed = False
    for corpus, table_name in COLLECTIONS.items():
        current = embedding_column_dimension(conn, table_name)
        if current is None or current == DIMENSION:
            continue
        index_name = _HNSW_INDEX[table_name]
        conn.execute(
            sql.SQL("DROP INDEX IF EXISTS {}").format(
                sql.Identifier("complaint_rag", index_name)
            )
        )
        conn.execute(
            sql.SQL("ALTER TABLE {} DROP COLUMN embedding").format(table(corpus))
        )
        conn.execute(
            sql.SQL("ALTER TABLE {} ADD COLUMN embedding vector({dim})").format(
                table(corpus), dim=sql.SQL(str(int(DIMENSION)))
            )
        )
        conn.execute(
            sql.SQL(
                "CREATE INDEX IF NOT EXISTS {idx} ON {tbl} USING hnsw "
                "(embedding vector_cosine_ops)"
            ).format(
                idx=sql.Identifier(index_name),
                tbl=table(corpus),
            )
        )
        changed = True
    return changed


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
    if (
        config["embedding_signature"] != embedding_signature()
        or config["tokenizer"] != TOKENIZER_VERSION
    ):
        raise ValueError(
            "실행 코드와 색인 설정이 다릅니다. ingest --reembed로 재구축해 주세요."
        )


def read_status(conn) -> dict:
    """현재 문서·부서 건수와 색인·적재 메타데이터를 읽습니다.

    Args:
        conn: PostgreSQL 연결입니다.

    Returns:
        검토·업무 미검증 건수, 모델 설정, 최근 적재 정보를 포함한 상태입니다.
    """
    counts = {
        name: conn.execute(
            sql.SQL("SELECT count(*) AS n FROM {}").format(table(corpus))
        ).fetchone()["n"]
        for corpus, name in COLLECTIONS.items()
    }
    counts["department_directory"] = conn.execute(
        "SELECT count(*) AS n FROM complaint_rag.department_directory"
    ).fetchone()["n"]
    counts["review_required"] = conn.execute(
        "SELECT count(*) AS n FROM complaint_rag.routing_cases WHERE NOT routing_eligible"
    ).fetchone()["n"]
    counts["duties_unverified"] = conn.execute(
        "SELECT count(*) AS n FROM complaint_rag.department_directory WHERE duty_status = 'unverified'"
    ).fetchone()["n"]
    return {
        "counts": counts,
        "configuration": metadata(conn, "configuration"),
        "last_ingestion": metadata(conn, "last_ingestion"),
    }
