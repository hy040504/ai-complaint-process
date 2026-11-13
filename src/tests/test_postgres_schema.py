"""PostgreSQL 민원 스키마의 생성 칼럼·CHECK 제약·시연 표시 백필을 확인합니다.

`RUN_PG_TESTS=1`일 때만 실행합니다. 매 시험마다 임시 스키마를 만들고 끝나면 지웁니다.
"""

from __future__ import annotations

import json
import os
import uuid

import psycopg
from psycopg import sql
from psycopg.errors import CheckViolation
import pytest

from src.complaints.models import Complaint
from src.complaints.repository import PostgresRepository

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_PG_TESTS") != "1",
    reason="RUN_PG_TESTS=1에서 PostgreSQL 민원 스키마를 검증합니다.",
)


def _new_schema() -> str:
    """시험마다 겹치지 않는 임시 스키마 이름을 만듭니다.

    Returns:
        `complaint_app_test_` 접두어의 스키마 이름입니다.
    """
    return "complaint_app_test_" + uuid.uuid4().hex[:12]


def _drop(schema: str) -> None:
    """임시 스키마를 내용과 함께 지웁니다.

    Args:
        schema: 지울 스키마 이름입니다.
    """
    with psycopg.connect(autocommit=True, connect_timeout=10) as conn:
        conn.execute(
            sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema))
        )


def _complaint(complaint_id: str, synthetic: bool) -> Complaint:
    """검증용 민원 모델을 만듭니다.

    Args:
        complaint_id: 민원 식별자입니다.
        synthetic: 시연 표시 여부입니다.

    Returns:
        저장 가능한 민원 모델입니다.
    """
    return Complaint(
        id=complaint_id,
        title="검증용 민원",
        body="검증용 본문입니다. 열 글자 이상입니다.",
        category="기타",
        district="모름",
        owner="citizen-demo",
        visibility="public",
        is_synthetic=synthetic,
    )


def test_generated_columns_follow_payload() -> None:
    """목록용 생성 칼럼이 payload 값과 같고 시연 표시를 따릅니다."""
    schema = _new_schema()
    try:
        repo = PostgresRepository(schema=schema)
        repo.create(_complaint("DEMO-PUB-G1", synthetic=True), None, "")
        repo.create(_complaint("REAL-G2", synthetic=False), None, "")
        with psycopg.connect(connect_timeout=10) as conn:
            rows = conn.execute(
                sql.SQL(
                    "SELECT id, status, owner, visibility, district, is_synthetic "
                    "FROM {}.complaints ORDER BY id"
                ).format(sql.Identifier(schema))
            ).fetchall()
        assert rows == [
            ("DEMO-PUB-G1", "submitted", "citizen-demo", "public", "모름", True),
            ("REAL-G2", "submitted", "citizen-demo", "public", "모름", False),
        ]
    finally:
        _drop(schema)


def test_check_rejects_unknown_status() -> None:
    """허용 목록 밖의 상태는 DB가 저장을 거부합니다."""
    schema = _new_schema()
    try:
        PostgresRepository(schema=schema)
        payload = json.dumps(
            {"status": "bogus", "owner": "citizen-demo", "visibility": "public"}
        )
        with psycopg.connect(connect_timeout=10) as conn:
            with pytest.raises(CheckViolation):
                conn.execute(
                    sql.SQL(
                        "INSERT INTO {}.complaints (id, version, created_at, payload) "
                        "VALUES ('BAD-1', 1, now(), %s::jsonb)"
                    ).format(sql.Identifier(schema)),
                    (payload,),
                )
    finally:
        _drop(schema)


def test_backfill_marks_only_public_demo_rows() -> None:
    """예전 DEMO-PUB 행만 시연 표시를 채우고, 일반 민원은 그대로 둡니다."""
    schema = _new_schema()
    try:
        PostgresRepository(schema=schema)
        old = json.dumps(
            {"status": "submitted", "owner": "citizen-demo", "visibility": "public"}
        )
        with psycopg.connect(autocommit=True, connect_timeout=10) as conn:
            for row_id in ("DEMO-PUB-OLD", "REAL-OLD"):
                conn.execute(
                    sql.SQL(
                        "INSERT INTO {}.complaints (id, version, created_at, payload) "
                        "VALUES (%s, 1, now(), %s::jsonb)"
                    ).format(sql.Identifier(schema)),
                    (row_id, old),
                )
        # 두 번째 초기화는 백필을 다시 실행해도 결과가 같아야 합니다.
        PostgresRepository(schema=schema)
        PostgresRepository(schema=schema)
        with psycopg.connect(connect_timeout=10) as conn:
            rows = dict(
                conn.execute(
                    sql.SQL("SELECT id, is_synthetic FROM {}.complaints").format(
                        sql.Identifier(schema)
                    )
                ).fetchall()
            )
        assert rows == {"DEMO-PUB-OLD": True, "REAL-OLD": False}
    finally:
        _drop(schema)
