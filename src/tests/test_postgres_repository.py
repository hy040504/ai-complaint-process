"""실제 PostgreSQL 업무 스키마에 민원 JSON이 저장되는지 확인합니다."""

from __future__ import annotations

import json
import os
import uuid

import psycopg
from psycopg import sql
import pytest

from src.complaints.models import AnswerTemplate, Complaint
from src.complaints.repository import PostgresRepository

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_PG_TESTS") != "1",
    reason="RUN_PG_TESTS=1에서 PostgreSQL 업무 저장소를 검증합니다.",
)


def test_postgres_repository_adds_version_to_old_table() -> None:
    """version 컬럼이 없는 예전 테이블을 지우지 않고 채웁니다."""
    schema = "complaint_app_test_" + uuid.uuid4().hex[:12]
    try:
        with psycopg.connect(autocommit=True, connect_timeout=10) as conn:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
            conn.execute(
                sql.SQL(
                    "CREATE TABLE {}.complaints ("
                    "id text PRIMARY KEY, created_at timestamptz NOT NULL, "
                    "payload jsonb NOT NULL)"
                ).format(sql.Identifier(schema))
            )
            conn.execute(
                sql.SQL(
                    "INSERT INTO {}.complaints (id, created_at, payload) "
                    "VALUES ('OLD-1', now(), %s::jsonb)"
                ).format(sql.Identifier(schema)),
                (json.dumps({"version": 3}),),
            )
        PostgresRepository(schema=schema)
        with psycopg.connect(connect_timeout=10) as conn:
            version = conn.execute(
                sql.SQL("SELECT version FROM {}.complaints WHERE id = 'OLD-1'").format(
                    sql.Identifier(schema)
                )
            ).fetchone()
        assert version is not None
        assert version[0] == 3
        with psycopg.connect(connect_timeout=10) as conn:
            column = conn.execute(
                """
                SELECT is_nullable
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = 'complaints'
                  AND column_name = 'version'
                """,
                (schema,),
            ).fetchone()
        assert column is not None
        assert column[0] == "NO"
    finally:
        with psycopg.connect(autocommit=True, connect_timeout=10) as conn:
            conn.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                    sql.Identifier(schema)
                )
            )


def test_postgres_repository_roundtrip() -> None:
    """같은 스키마에 저장한 민원을 다시 읽습니다."""
    schema = "complaint_app_test_" + uuid.uuid4().hex[:12]
    try:
        store = PostgresRepository(schema=schema)
        row = Complaint(
            id="DEMO-TEST-1",
            title="합성 보행로 점검 요청",
            body="보행로 시설 점검을 요청합니다.",
            category="도로·교통",
            district="흥덕구",
            owner="citizen-1",
            visibility="private",
        )
        stored = store.create(row, key="k1", fingerprint="fp")
        again = store.create(row, key="k1", fingerprint="fp")
        assert again.id == stored.id
        loaded = store.get(stored.id)
        assert loaded.title == row.title
        listed = store.all()
        assert listed[0].id == stored.id
        with pytest.raises(Exception) as wrong_version:
            store.delete(stored.id, 99, lambda _row: None)
        assert getattr(wrong_version.value, "status", None) == 409
        store.delete(stored.id, 1, lambda _row: None)
        with pytest.raises(Exception) as missing:
            store.get(stored.id)
        assert getattr(missing.value, "status", None) == 404
        with psycopg.connect(connect_timeout=10) as conn:
            leftover = conn.execute(
                sql.SQL(
                    "SELECT count(*) FROM {}.idempotency WHERE complaint_id = %s"
                ).format(sql.Identifier(schema)),
                (stored.id,),
            ).fetchone()
        assert leftover == (0,)
    finally:
        with psycopg.connect(autocommit=True, connect_timeout=10) as conn:
            conn.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                    sql.Identifier(schema)
                )
            )


def test_postgres_repository_templates_persist_across_reinit() -> None:
    """PostgreSQL 답변 템플릿 추가·삭제·복원 결과가 재초기화 후에도 유지됩니다."""
    schema = "complaint_app_test_" + uuid.uuid4().hex[:12]
    try:
        store = PostgresRepository(schema=schema)
        initial = store.list_templates()
        assert len(initial) == 5

        store.delete_template("TPL-DEF-1")
        custom = store.create_template(
            AnswerTemplate(
                id="TPL-CUSTOM-PG1",
                title="보행로 점검",
                content="보행로 현장 점검 결과를 확인한 뒤 안내드리겠습니다.",
                is_default=False,
            )
        )
        assert custom.id == "TPL-CUSTOM-PG1"

        # 같은 스키마에 저장소를 다시 열어도 삭제한 기본 템플릿이 되살아나면 안 됩니다.
        reopened = PostgresRepository(schema=schema)
        ids = [item.id for item in reopened.list_templates()]
        assert "TPL-DEF-1" not in ids
        assert "TPL-CUSTOM-PG1" in ids

        restored = reopened.reset_default_templates()
        restored_ids = [item.id for item in restored]
        assert "TPL-DEF-1" in restored_ids and "TPL-CUSTOM-PG1" in restored_ids
    finally:
        with psycopg.connect(autocommit=True, connect_timeout=10) as conn:
            conn.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                    sql.Identifier(schema)
                )
            )
