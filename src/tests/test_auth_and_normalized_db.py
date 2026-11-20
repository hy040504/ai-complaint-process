"""민원인·담당자 아이디/비밀번호 로그인과 PostgreSQL 7테이블 정규화를 검증합니다."""

from __future__ import annotations

import os
import uuid
from typing import Any

import psycopg
from psycopg import sql
from psycopg.errors import CheckViolation
import pytest

from src import create_app
from src.complaints.auth import (
    DEFAULT_CITIZEN_INIT_PASSWORD,
    DEFAULT_STAFF_INIT_PASSWORD,
)
from src.complaints.config import Settings
from src.complaints.repository import NORMALIZED_TABLE_NAMES, PostgresRepository
from src.tests.test_complaint_ai import _fake_assist_payload


def test_citizen_id_password_login_register_and_isolation() -> None:
    """민원인 기본 계정 로그인·간단 가입·다중 사용자 비공개 민원 격리를 검증합니다."""
    app = create_app(
        Settings(
            secret_key="auth-citizen-test",
            backend="memory",
            testing=True,
            demo_login=False,
        )
    )
    cit_a = app.test_client()
    cit_b = app.test_client()

    # demo_login=False이면 기존 시연 세션 전환은 403으로 막히고 로그인 경로만 허용됩니다.
    assert cit_a.post("/api/v1/session", json={"role": "citizen"}).status_code == 403

    # 기본 민원인 계정(citizen_01)으로 바로 아이디·비밀번호 로그인 가능
    seeded_login = cit_a.post(
        "/api/v1/auth/login",
        json={
            "loginId": "citizen_01",
            "password": DEFAULT_CITIZEN_INIT_PASSWORD,
            "expectedRole": "citizen",
        },
    )
    assert seeded_login.status_code == 200
    actor_a = seeded_login.get_json()
    assert actor_a["role"] == "citizen"
    assert actor_a["demo"] is False
    assert actor_a["authMode"] == "password"
    assert "passwordHash" not in actor_a and "password_hash" not in actor_a
    assert DEFAULT_CITIZEN_INIT_PASSWORD not in str(actor_a)

    # 민원인 A 비공개 민원 등록
    created = cit_a.post(
        "/api/v1/complaints",
        json={
            "title": "민원인A 비공개 민원",
            "body": "민원인A만 조회하고 수정할 수 있어야 하는 비공개 민원 본문입니다.",
            "district": "서원구",
            "category": "도로·교통",
            "visibility": "private",
        },
    )
    assert created.status_code == 201
    cid = created.get_json()["id"]
    assert created.get_json()["owner"] == actor_a["id"]

    # 중복 아이디 가입 차단(409)
    dup = cit_b.post(
        "/api/v1/auth/register",
        json={
            "loginId": "citizen_01",
            "password": "otherpassword",
            "displayName": "중복시도",
        },
    )
    assert dup.status_code == 409

    # 민원인 B 간단 가입(아이디·비밀번호·이름만) -> 민원인 A 비공개 민원 접근·삭제 차단
    reg_b = cit_b.post(
        "/api/v1/auth/register",
        json={
            "loginId": "citizen_beta",
            "password": "cheongju456",
            "displayName": "청주시민B",
        },
    )
    assert reg_b.status_code == 201
    assert reg_b.get_json()["authMode"] == "password"
    assert cit_b.get(f"/api/v1/complaints/{cid}").status_code == 404
    assert (
        cit_b.post(f"/api/v1/complaints/{cid}/delete", json={"version": 1}).status_code
        == 404
    )
    assert all(
        row["id"] != cid
        for row in cit_b.get("/api/v1/workspace").get_json()["complaints"]
    )

    # 민원인 A 로그아웃 -> 401 -> 재로그인 -> 본인 민원 정상 조회
    assert cit_a.post("/api/v1/auth/logout").status_code == 204
    assert cit_a.get("/api/v1/auth/me").status_code == 401
    relogin = cit_a.post(
        "/api/v1/auth/login",
        json={
            "loginId": "citizen_01",
            "password": DEFAULT_CITIZEN_INIT_PASSWORD,
            "expectedRole": "citizen",
        },
    )
    assert relogin.status_code == 200
    assert relogin.get_json()["id"] == actor_a["id"]
    assert cit_a.get(f"/api/v1/complaints/{cid}").status_code == 200


def test_staff_password_auth_rate_limit_and_department_scope_rbac() -> None:
    """담당자 아이디/비밀번호 로그인·5회 실패 잠금·부서 권한 스코프(RBAC)를 검증합니다."""
    app = create_app(
        Settings(
            secret_key="auth-staff-test",
            backend="memory",
            testing=True,
            demo_login=False,
        )
    )
    admin = app.test_client()
    seowon = app.test_client()
    heungdeok = app.test_client()
    citizen = app.test_client()

    # 1. 민원인 로그인 및 민원 등록
    assert (
        citizen.post(
            "/api/v1/auth/login",
            json={
                "loginId": "citizen_01",
                "password": DEFAULT_CITIZEN_INIT_PASSWORD,
                "expectedRole": "citizen",
            },
        ).status_code
        == 200
    )
    row = citizen.post(
        "/api/v1/complaints",
        json={
            "title": "서원구 도로 파손 보수 요청",
            "body": "서원구 사창동 보행로가 심하게 파손되어 보수가 필요합니다.",
            "district": "서원구",
            "category": "도로·교통",
            "visibility": "private",
        },
    ).get_json()

    # 2. 역할 불일치 차단 + 연속 5회 실패 잠금(429)
    assert (
        admin.post(
            "/api/v1/auth/login",
            json={
                "loginId": "staff_admin",
                "password": DEFAULT_STAFF_INIT_PASSWORD,
                "expectedRole": "citizen",
            },
        ).status_code
        == 403
    )
    for _ in range(5):
        bad = heungdeok.post(
            "/api/v1/auth/login",
            json={"loginId": "staff_heungdeok", "password": "wrong-password"},
        )
        assert bad.status_code == 401
    locked = heungdeok.post(
        "/api/v1/auth/login",
        json={
            "loginId": "staff_heungdeok",
            "password": DEFAULT_STAFF_INIT_PASSWORD,
        },
    )
    assert locked.status_code == 429
    assert locked.get_json()["code"] == "auth_locked"

    # 3. 총괄 담당자 로그인 -> '서원구 건설과' 배정
    assert (
        admin.post(
            "/api/v1/auth/login",
            json={
                "loginId": "staff_admin",
                "password": DEFAULT_STAFF_INIT_PASSWORD,
                "expectedRole": "staff",
            },
        ).status_code
        == 200
    )
    assigned = admin.put(
        f"/api/v1/complaints/{row['id']}/assignment",
        json={"version": 1, "department": "서원구 건설과", "assigned": True},
    )
    assert assigned.status_code == 200
    ver_num = assigned.get_json()["version"]

    # 4. 다른 부서(흥덕구 환경위생과) 담당자는 타 부서 배정 민원 초안·게시 차단(403)
    app.extensions["auth_service"].rate_limiter.reset("staff_heungdeok")
    assert (
        heungdeok.post(
            "/api/v1/auth/login",
            json={
                "loginId": "staff_heungdeok",
                "password": DEFAULT_STAFF_INIT_PASSWORD,
                "expectedRole": "staff",
            },
        ).status_code
        == 200
    )
    forbidden = heungdeok.put(
        f"/api/v1/complaints/{row['id']}/draft",
        json={"version": ver_num, "text": "타 부서 무단 초안", "reason": "시도"},
    )
    assert forbidden.status_code == 403
    assert forbidden.get_json()["code"] == "department_scope_forbidden"

    # 5. 소관 부서(서원구 건설과) 담당자는 정상 초안 저장·게시 가능
    login_sw = seowon.post(
        "/api/v1/auth/login",
        json={
            "loginId": "staff_seowon",
            "password": DEFAULT_STAFF_INIT_PASSWORD,
            "expectedRole": "staff",
        },
    )
    assert login_sw.status_code == 200
    assert login_sw.get_json()["department"] == "서원구 건설과"
    drafted = seowon.put(
        f"/api/v1/complaints/{row['id']}/draft",
        json={
            "version": ver_num,
            "text": "현장 점검 후 보수 예정입니다.",
            "reason": "검토",
        },
    )
    assert drafted.status_code == 200
    published = seowon.post(
        f"/api/v1/complaints/{row['id']}/publish",
        json={
            "version": drafted.get_json()["version"],
            "text": "현장 점검 후 보수 예정입니다.",
            "reason": "서원구 건설과 게시",
        },
    )
    assert published.status_code == 200
    assert any(
        "서원구 건설과 담당자" in h["text"] for h in published.get_json()["history"]
    )


@pytest.mark.skipif(
    os.getenv("RUN_PG_TESTS") != "1",
    reason="RUN_PG_TESTS=1에서 PostgreSQL 7테이블 정규화를 검증합니다.",
)
def test_postgres_seven_table_normalization_and_cascade_delete() -> None:
    """PostgreSQL 7테이블 정규화·원자 동기화·DB CHECK·SQL 집계·연쇄 삭제를 검증합니다."""
    schema = "complaint_app_norm_" + uuid.uuid4().hex[:10]

    def fake_iter(
        query: str,
        district: str | None,
        limit: int,
        rerank: bool,
        provider: str | None = None,
        include_staff_outputs: bool = True,
    ) -> Any:
        """완료 시 부서 추천 AI 결과를 내보내는 테스트 스트림입니다.

        Args:
            query: 민원 질의입니다.
            district: 선택 관할 구입니다.
            limit: 후보 수입니다.
            rerank: 재정렬 여부입니다.
            provider: 선택 공급자입니다.
            include_staff_outputs: 담당자 산출물 생성 여부입니다.
        """
        del limit, rerank, provider, include_staff_outputs
        yield {"type": "progress", "key": "search", "label": "저장된 자료 검색 중"}
        yield {
            "type": "done",
            "result": _fake_assist_payload(
                query=query,
                district=district or "흥덕구",
                outcome="department_suggestion",
                staff_draft_answer="현장 점검 후 보수하겠습니다.",
            ),
        }

    try:
        repo = PostgresRepository(schema=schema)
        app = create_app(
            Settings(
                secret_key="pg-norm-secret",
                backend="postgresql",
                schema=schema,
                testing=True,
                demo_login=False,
            ),
            repository=repo,
            assist_iter_fn=fake_iter,
            auto_start_ai=True,
        )

        # 1. PostgreSQL information_schema에 7개 정규화 테이블이 모두 생성되었는지 확인
        with psycopg.connect(connect_timeout=10) as conn:
            found_tables = {
                r[0]
                for r in conn.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = %s",
                    (schema,),
                ).fetchall()
            }
        assert set(NORMALIZED_TABLE_NAMES) <= found_tables

        # 2. 민원인 간단 가입 -> 민원 등록 -> AI 완료 -> 추가 문의 -> 담당자 초안/게시
        cit = app.test_client()
        reg = cit.post(
            "/api/v1/auth/register",
            json={
                "loginId": "norm_citizen",
                "password": "normuser123",
                "displayName": "정규화시민",
            },
        )
        assert reg.status_code == 201
        cit_id = reg.get_json()["id"]

        created = cit.post(
            "/api/v1/complaints",
            json={
                "title": "7테이블 정규화 점검 민원",
                "body": "오송읍 보행로 파손 현장 점검과 보수를 요청드립니다.",
                "district": "흥덕구",
                "category": "도로·교통",
                "visibility": "private",
            },
            headers={"Idempotency-Key": "norm-key-1"},
        )
        assert created.status_code == 201
        cid = created.get_json()["id"]
        app.extensions["complaint_service"].wait_for_jobs(timeout=3.0)

        staff = app.test_client()
        assert (
            staff.post(
                "/api/v1/auth/login",
                json={
                    "loginId": "staff_admin",
                    "password": DEFAULT_STAFF_INIT_PASSWORD,
                    "expectedRole": "staff",
                },
            ).status_code
            == 200
        )

        # 시민 추가 문의 + 담당자 초안/게시
        latest_cit = cit.get(f"/api/v1/complaints/{cid}").get_json()
        msg_res = cit.post(
            f"/api/v1/complaints/{cid}/messages",
            json={"version": latest_cit["version"], "message": "야간에 더 위험합니다."},
        )
        assert msg_res.status_code == 200

        latest_staff = staff.get(f"/api/v1/complaints/{cid}").get_json()
        pub_res = staff.post(
            f"/api/v1/complaints/{cid}/publish",
            json={
                "version": latest_staff["version"],
                "text": "현장 점검 후 보수 완료하겠습니다.",
                "reason": "최종 게시",
            },
        )
        assert pub_res.status_code == 200

        # 3. 7개 정규화 테이블 실제 SQL 행 검증
        with psycopg.connect(connect_timeout=10) as conn:
            ident = sql.Identifier(schema)
            c_row = conn.execute(
                sql.SQL(
                    "SELECT owner_user_id, assignee_user_id, title FROM {}.complaints WHERE id = %s"
                ).format(ident),
                (cid,),
            ).fetchone()
            assert c_row == (cit_id, "staff-admin", "7테이블 정규화 점검 민원")

            msgs = conn.execute(
                sql.SQL(
                    "SELECT kind, published_version_id FROM {}.messages WHERE complaint_id = %s ORDER BY kind"
                ).format(ident),
                (cid,),
            ).fetchall()
            assert len(msgs) == 2
            assert msgs[0][0] == "answer" and msgs[0][1] is not None
            assert msgs[1][0] == "inquiry"

            vers = conn.execute(
                sql.SQL(
                    "SELECT publish_state, actor_user_id FROM {}.message_versions WHERE complaint_id = %s"
                ).format(ident),
                (cid,),
            ).fetchall()
            assert any(v[0] == "published" and v[1] == "staff-admin" for v in vers)

            jobs = conn.execute(
                sql.SQL(
                    "SELECT id, state FROM {}.ai_jobs WHERE complaint_id = %s"
                ).format(ident),
                (cid,),
            ).fetchall()
            assert len(jobs) >= 1 and any(j[1] == "succeeded" for j in jobs)

            res_row = conn.execute(
                sql.SQL(
                    "SELECT outcome, department_name, automatic_transfer FROM {}.ai_results WHERE complaint_id = %s"
                ).format(ident),
                (cid,),
            ).fetchone()
            assert res_row == ("department_suggestion", "흥덕구 건설과", False)

            ev_cnt = conn.execute(
                sql.SQL(
                    "SELECT count(*) FROM {}.job_events WHERE complaint_id = %s"
                ).format(ident),
                (cid,),
            ).fetchone()
            assert ev_cnt is not None and ev_cnt[0] >= 2

            # automatic_transfer=true DB CHECK 위반 검증
            with pytest.raises(CheckViolation):
                conn.execute(
                    sql.SQL(
                        "INSERT INTO {}.ai_results (id, job_id, complaint_id, outcome, automatic_transfer) "
                        "VALUES ('BAD-RES', %s, %s, 'faq_answer', true)"
                    ).format(ident),
                    (jobs[0][0], cid),
                )
                conn.commit()
            conn.rollback()

        # 4. 담당자 전용 7테이블 집계 API 권한 및 수치 검증
        assert app.test_client().get("/api/v1/staff/db-summary").status_code == 401
        assert cit.get("/api/v1/staff/db-summary").status_code == 403
        summary = staff.get("/api/v1/staff/db-summary").get_json()
        assert summary["storage"] == "postgresql"
        assert summary["normalizedTables"]["users"] == 7  # 시드 6 + norm_citizen 1
        assert summary["normalizedTables"]["complaints"] == 1
        assert summary["normalizedTables"]["messages"] == 2
        assert summary["normalizedTables"]["message_versions"] >= 1
        assert summary["normalizedTables"]["ai_jobs"] >= 1
        assert summary["normalizedTables"]["ai_results"] == 1
        assert summary["normalizedTables"]["job_events"] >= 2
        assert summary["aiOutcomes"]["department_suggestion"] == 1

        # 5. 영구 삭제 시 하위 5테이블 연쇄 삭제(ON DELETE CASCADE) 검증
        del_ver = cit.get(f"/api/v1/complaints/{cid}").get_json()["version"]
        assert (
            cit.post(
                f"/api/v1/complaints/{cid}/delete", json={"version": del_ver}
            ).status_code
            == 204
        )
        after_summary = staff.get("/api/v1/staff/db-summary").get_json()
        for tbl in (
            "complaints",
            "messages",
            "message_versions",
            "ai_jobs",
            "ai_results",
            "job_events",
        ):
            assert after_summary["normalizedTables"][tbl] == 0
    finally:
        with psycopg.connect(autocommit=True, connect_timeout=10) as conn:
            conn.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                    sql.Identifier(schema)
                )
            )
