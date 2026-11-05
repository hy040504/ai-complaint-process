"""실제 PostgreSQL 업무 스키마에 민원 JSON이 저장되는지 확인합니다."""

from __future__ import annotations

import os
import uuid

import psycopg
from psycopg import sql
import pytest

from src.complaints.models import Complaint
from src.complaints.repository import PostgresRepository

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_PG_TESTS") != "1",
    reason="RUN_PG_TESTS=1에서 PostgreSQL 업무 저장소를 검증합니다.",
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
    finally:
        with psycopg.connect(autocommit=True, connect_timeout=10) as conn:
            conn.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                    sql.Identifier(schema)
                )
            )
