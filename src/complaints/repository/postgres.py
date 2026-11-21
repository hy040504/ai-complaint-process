"""PostgreSQL `complaint_app` 스키마를 쓰는 업무 저장소입니다."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import timedelta
from typing import Any, Literal
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from src.complaints.auth import StoredUser, default_seed_users
from src.complaints.errors import AppError
from src.complaints.models import (
    AnswerTemplate,
    AttachmentItem,
    ChatMessageRecord,
    ChatSessionDetail,
    ChatSessionSummary,
    CitizenChatResponse,
    Complaint,
    History,
    NormalizedDbSummary,
    Role,
    utcnow,
)
from src.complaints.repository.schema import (
    StorageKind,
    DEFAULT_ANSWER_TEMPLATES,
    NORMALIZED_TABLE_NAMES,
    SCHEMA_STATEMENTS,
    VALUE_CHECKS,
    version_publish_state,
    version_origin,
    extract_primary_dept,
)


class PostgresRepository:
    """PostgreSQL `complaint_app` 7테이블 정규화 스키마 업무 저장소입니다.

    검색 색인 `complaint_rag`와 민원 본문을 섞지 않으며, `ai_results.department_id`만
    선택적 외래 키로 `complaint_rag.department_directory`를 참조합니다.

    Args:
        conninfo: libpq 연결 문자열입니다. 비면 `PGHOST` 등 표준 환경변수를 씁니다.
        schema: 업무 스키마 이름입니다. 기본값은 `complaint_app`입니다.
    """

    storage: StorageKind = "postgresql"

    def __init__(self, conninfo: str = "", schema: str = "complaint_app") -> None:
        """연결을 확인하고 7개 정규화 테이블·보조 3테이블·시드·백필을 준비합니다.

        Args:
            conninfo: PostgreSQL 연결 정보입니다.
            schema: 생성·사용할 스키마 이름입니다.
        """
        self.conninfo = conninfo
        self.schema = schema
        self._has_rag_dept_dir = False
        ident = sql.Identifier(schema)
        self._sql_all = sql.SQL(
            "SELECT payload FROM {}.complaints ORDER BY created_at DESC, id DESC"
        ).format(ident)
        self._sql_get = sql.SQL(
            "SELECT payload FROM {}.complaints WHERE id = %s"
        ).format(ident)
        self._sql_lock = sql.SQL(
            "SELECT payload FROM {}.complaints WHERE id = %s FOR UPDATE"
        ).format(ident)
        self._sql_key = sql.SQL(
            "SELECT fingerprint, complaint_id FROM {}.idempotency "
            "WHERE owner = %s AND key = %s"
        ).format(ident)
        self._sql_insert = sql.SQL(
            "INSERT INTO {}.complaints "
            "(id, version, created_at, payload, owner_user_id, assignee_user_id, "
            "title, body, category, department, context_version, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())"
        ).format(ident)
        self._sql_insert_key = sql.SQL(
            "INSERT INTO {}.idempotency "
            "(owner, key, fingerprint, complaint_id) VALUES (%s, %s, %s, %s)"
        ).format(ident)
        self._sql_update = sql.SQL(
            "UPDATE {}.complaints "
            "SET version = %s, payload = %s, owner_user_id = %s, assignee_user_id = %s, "
            "title = %s, body = %s, category = %s, department = %s, "
            "context_version = %s, updated_at = now() "
            "WHERE id = %s AND version = %s"
        ).format(ident)
        self._sql_sync_complaint_cols = sql.SQL(
            "UPDATE {}.complaints "
            "SET owner_user_id = %s, assignee_user_id = %s, title = %s, body = %s, "
            "category = %s, department = %s, context_version = %s, updated_at = now() "
            "WHERE id = %s"
        ).format(ident)
        self._sql_delete_keys = sql.SQL(
            "DELETE FROM {}.idempotency WHERE complaint_id = %s"
        ).format(ident)
        self._sql_delete = sql.SQL(
            "DELETE FROM {}.complaints WHERE id = %s AND version = %s"
        ).format(ident)
        self._sql_user_exists = sql.SQL("SELECT 1 FROM {}.users WHERE id = %s").format(
            ident
        )
        self._sql_get_user_id = sql.SQL(
            "SELECT id, login_id, display_name, role, password_hash, department, "
            "is_demo, active, created_at, last_login_at "
            "FROM {}.users WHERE id = %s"
        ).format(ident)
        self._sql_get_user_login = sql.SQL(
            "SELECT id, login_id, display_name, role, password_hash, department, "
            "is_demo, active, created_at, last_login_at "
            "FROM {}.users WHERE lower(login_id) = lower(%s)"
        ).format(ident)
        self._sql_list_users = sql.SQL(
            "SELECT id, login_id, display_name, role, password_hash, department, "
            "is_demo, active, created_at, last_login_at "
            "FROM {}.users ORDER BY created_at ASC, id ASC"
        ).format(ident)
        self._sql_insert_user = sql.SQL(
            "INSERT INTO {}.users "
            "(id, login_id, display_name, role, password_hash, department, "
            "is_demo, active, created_at, last_login_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        ).format(ident)
        self._sql_seed_user = sql.SQL(
            "INSERT INTO {}.users "
            "(id, login_id, display_name, role, password_hash, department, "
            "is_demo, active, created_at, last_login_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (id) DO NOTHING"
        ).format(ident)
        self._sql_touch_login = sql.SQL(
            "UPDATE {}.users SET last_login_at = now() WHERE id = %s"
        ).format(ident)
        self._sql_update_password = sql.SQL(
            "UPDATE {}.users SET password_hash = %s WHERE id = %s"
        ).format(ident)
        self._sql_set_active = sql.SQL(
            "UPDATE {}.users SET active = %s WHERE id = %s"
        ).format(ident)
        self._sql_upsert_message = sql.SQL(
            "INSERT INTO {}.messages "
            "(id, complaint_id, kind, origin, author_user_id, body, published_version_id, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (id) DO UPDATE SET "
            "origin = EXCLUDED.origin, author_user_id = EXCLUDED.author_user_id, "
            "body = EXCLUDED.body, published_version_id = EXCLUDED.published_version_id"
        ).format(ident)
        self._sql_upsert_msg_version = sql.SQL(
            "INSERT INTO {}.message_versions "
            "(id, message_id, complaint_id, version_no, body, origin, kind, "
            "publish_state, reason, actor_user_id, context_version, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (id) DO NOTHING"
        ).format(ident)
        self._sql_upsert_ai_job = sql.SQL(
            "INSERT INTO {}.ai_jobs "
            "(id, complaint_id, context_version, attempt, state, stage, provider, started_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now()) "
            "ON CONFLICT (complaint_id, context_version, attempt) DO UPDATE SET "
            "state = EXCLUDED.state, stage = EXCLUDED.stage, provider = EXCLUDED.provider, "
            "started_at = EXCLUDED.started_at, updated_at = now() "
            "RETURNING id"
        ).format(ident)
        self._sql_upsert_job_event = sql.SQL(
            "INSERT INTO {}.job_events "
            "(job_id, complaint_id, seq_no, occurred_at, stage, vis) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (job_id, seq_no) DO UPDATE SET "
            "occurred_at = EXCLUDED.occurred_at, stage = EXCLUDED.stage, vis = EXCLUDED.vis"
        ).format(ident)
        self._sql_upsert_ai_result = sql.SQL(
            "INSERT INTO {}.ai_results "
            "(id, job_id, complaint_id, outcome, reason_code, department_id, department_name, "
            "evidence, draft_body, guide_body, automatic_transfer, llm_provider, llm_model, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, false, %s, %s, now()) "
            "ON CONFLICT (job_id) DO UPDATE SET "
            "outcome = EXCLUDED.outcome, reason_code = EXCLUDED.reason_code, "
            "department_id = EXCLUDED.department_id, department_name = EXCLUDED.department_name, "
            "evidence = EXCLUDED.evidence, draft_body = EXCLUDED.draft_body, "
            "guide_body = EXCLUDED.guide_body, llm_provider = EXCLUDED.llm_provider, "
            "llm_model = EXCLUDED.llm_model"
        ).format(ident)
        self._sql_list_tpl = sql.SQL(
            "SELECT id, title, content, is_default, created_at "
            "FROM {}.answer_templates ORDER BY created_at ASC, id ASC"
        ).format(ident)
        self._sql_insert_tpl = sql.SQL(
            "INSERT INTO {}.answer_templates (id, title, content, is_default, created_at) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (id) DO NOTHING"
        ).format(ident)
        self._sql_delete_tpl = sql.SQL(
            "DELETE FROM {}.answer_templates WHERE id = %s"
        ).format(ident)
        self._sql_seed_meta = sql.SQL(
            "INSERT INTO {}.app_meta (key, value) VALUES (%s, %s) "
            "ON CONFLICT (key) DO NOTHING RETURNING key"
        ).format(ident)
        self._sql_list_chat_sessions = sql.SQL(
            "SELECT s.id, s.title, s.last_district, count(m.id), s.created_at, s.updated_at "
            "FROM {}.chat_sessions s "
            "LEFT JOIN {}.chat_messages m ON m.session_id = s.id "
            "WHERE s.user_id = %s "
            "GROUP BY s.id "
            "ORDER BY s.updated_at DESC, s.id DESC "
            "LIMIT %s"
        ).format(ident, ident)
        self._sql_get_chat_session = sql.SQL(
            "SELECT id, title, last_district, created_at, updated_at "
            "FROM {}.chat_sessions WHERE id = %s AND user_id = %s"
        ).format(ident)
        self._sql_lock_chat_session = sql.SQL(
            "SELECT id, title, last_district, created_at, updated_at "
            "FROM {}.chat_sessions WHERE id = %s AND user_id = %s FOR UPDATE"
        ).format(ident)
        self._sql_list_chat_messages = sql.SQL(
            "SELECT id, role, content, district, outcome, reason_code, payload, created_at "
            "FROM {}.chat_messages WHERE session_id = %s "
            "ORDER BY created_at ASC, id ASC"
        ).format(ident)
        self._sql_insert_chat_session = sql.SQL(
            "INSERT INTO {}.chat_sessions "
            "(id, user_id, title, last_district, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s)"
        ).format(ident)
        self._sql_touch_chat_session = sql.SQL(
            "UPDATE {}.chat_sessions "
            "SET last_district = COALESCE(%s, last_district), updated_at = %s "
            "WHERE id = %s AND user_id = %s"
        ).format(ident)
        self._sql_insert_chat_message = sql.SQL(
            "INSERT INTO {}.chat_messages "
            "(id, session_id, role, content, district, outcome, reason_code, payload, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
        ).format(ident)
        self._sql_delete_chat_session = sql.SQL(
            "DELETE FROM {}.chat_sessions WHERE id = %s AND user_id = %s"
        ).format(ident)
        self._sql_insert_attachment = sql.SQL(
            "INSERT INTO {}.attachments "
            "(id, complaint_id, uploaded_by, filename, content_type, size_bytes, "
            "sha256, storage_key, exif_stripped, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        ).format(ident)
        self._sql_get_attachment = sql.SQL(
            "SELECT id, filename, content_type, size_bytes, exif_stripped, "
            "uploaded_by, created_at, storage_key "
            "FROM {}.attachments WHERE complaint_id = %s AND id = %s"
        ).format(ident)
        self._sql_list_attachment_keys = sql.SQL(
            "SELECT storage_key FROM {}.attachments WHERE complaint_id = %s"
        ).format(ident)
        self._sql_delete_attachment = sql.SQL(
            "DELETE FROM {}.attachments WHERE complaint_id = %s AND id = %s "
            "RETURNING filename, storage_key"
        ).format(ident)
        with self.connection() as conn:
            for statement in SCHEMA_STATEMENTS:
                conn.execute(sql.SQL(statement).format(schema=ident))
            self._ensure_version_check(conn)
            self._ensure_value_checks(conn)
            self._ensure_cross_schema_department_fk(conn)
            self._ensure_seed_users(conn)
            self._ensure_default_templates(conn)
            self._backfill_normalized_tables(conn)

    def _ensure_version_check(self, conn: psycopg.Connection) -> None:
        """예전 테이블에 `version > 0` 제약이 없으면 추가합니다.

        Args:
            conn: 스키마를 준비 중인 연결입니다.
        """
        table = sql.SQL("{}.{}").format(
            sql.Identifier(self.schema), sql.Identifier("complaints")
        )
        found = conn.execute(
            """
            SELECT 1
            FROM pg_constraint
            WHERE conrelid = %s::regclass
              AND contype = 'c'
              AND position('version > 0' in pg_get_constraintdef(oid)) > 0
            """,
            (f"{self.schema}.complaints",),
        ).fetchone()
        if found:
            return
        conn.execute(
            sql.SQL(
                "ALTER TABLE {} ADD CONSTRAINT complaints_version_positive "
                "CHECK (version > 0)"
            ).format(table)
        )

    def _ensure_value_checks(self, conn: psycopg.Connection) -> None:
        """상태·공개 범위·지역 값을 DB가 검사하도록 CHECK 조건을 한 번만 추가합니다.

        Args:
            conn: 스키마를 준비 중인 연결입니다.
        """
        table = sql.SQL("{}.{}").format(
            sql.Identifier(self.schema), sql.Identifier("complaints")
        )
        for name, expression in VALUE_CHECKS:
            found = conn.execute(
                "SELECT 1 FROM pg_constraint WHERE conrelid = %s::regclass AND conname = %s",
                (f"{self.schema}.complaints", name),
            ).fetchone()
            if found:
                continue
            conn.execute(
                sql.SQL("ALTER TABLE {} ADD CONSTRAINT {} CHECK ({})").format(
                    table, sql.Identifier(name), sql.SQL(expression)
                )
            )

    def _ensure_cross_schema_department_fk(self, conn: psycopg.Connection) -> None:
        """`complaint_rag.department_directory`가 있으면 `ai_results.department_id` FK를 연결합니다.

        Args:
            conn: 스키마를 준비 중인 PostgreSQL 연결입니다.
        """
        has_rag = conn.execute(
            "SELECT to_regclass('complaint_rag.department_directory') IS NOT NULL"
        ).fetchone()
        self._has_rag_dept_dir = bool(has_rag and has_rag[0])
        if not self._has_rag_dept_dir:
            return
        found = conn.execute(
            "SELECT 1 FROM pg_constraint WHERE conrelid = %s::regclass AND conname = %s",
            (f"{self.schema}.ai_results", "fk_ai_results_department"),
        ).fetchone()
        if found:
            return
        conn.execute(
            sql.SQL(
                "ALTER TABLE {}.ai_results ADD CONSTRAINT fk_ai_results_department "
                "FOREIGN KEY (department_id) "
                "REFERENCES complaint_rag.department_directory (department_id)"
            ).format(sql.Identifier(self.schema))
        )

    def _ensure_seed_users(self, conn: psycopg.Connection) -> None:
        """최초 스키마 초기화 시 시연·기본 담당자 계정을 `users`에 누락 없이 채웁니다.

        Args:
            conn: 활성 PostgreSQL 연결입니다.
        """
        for user in default_seed_users():
            conn.execute(
                self._sql_seed_user,
                (
                    user.id,
                    user.login_id,
                    user.display_name,
                    user.role,
                    user.password_hash,
                    user.department,
                    user.is_demo,
                    user.active,
                    user.created_at,
                    user.last_login_at,
                ),
            )

    def _resolve_existing_user_id(
        self, conn: psycopg.Connection, candidate: str | None
    ) -> str | None:
        """외래 키 무결성을 위해 `users` 테이블에 실제로 존재하는 사용자 ID만 반환합니다.

        Args:
            conn: 활성 PostgreSQL 연결입니다.
            candidate: 확인할 사용자 식별자 후보입니다.

        Returns:
            `users`에 존재하면 원래 ID, 없으면 None입니다.
        """
        if not candidate:
            return None
        row = conn.execute(self._sql_user_exists, (candidate,)).fetchone()
        return candidate if row is not None else None

    def _resolve_rag_department_id(
        self, conn: psycopg.Connection, department_id: str | None
    ) -> str | None:
        """`complaint_rag.department_directory` 외래 키에 유효한 부서 ID만 통과시킵니다.

        Args:
            conn: 활성 PostgreSQL 연결입니다.
            department_id: AI 결과의 부서 식별자입니다.

        Returns:
            외래 키를 만족하는 부서 ID 또는 None입니다.
        """
        if not department_id:
            return None
        if not self._has_rag_dept_dir:
            return department_id
        found = conn.execute(
            "SELECT 1 FROM complaint_rag.department_directory WHERE department_id = %s",
            (department_id,),
        ).fetchone()
        return department_id if found is not None else None

    def _sync_normalized_children(
        self,
        conn: psycopg.Connection,
        row: Complaint,
        owner_uid: str | None,
        assignee_uid: str | None,
    ) -> None:
        """단일 민원 변경을 정규화 하위 5테이블(`messages`~`job_events`)에 원자 동기화합니다.

        Args:
            conn: 현재 쓰기 트랜잭션 연결입니다.
            row: 저장 중인 최신 `Complaint` 모델입니다.
            owner_uid: `users`에 확인된 작성자 FK ID 또는 None입니다.
            assignee_uid: `users`에 확인된 담당자 FK ID 또는 None입니다.
        """
        # 1. 시민 추가 문의 -> messages (kind='inquiry')
        for idx, msg in enumerate(row.messages, start=1):
            conn.execute(
                self._sql_upsert_message,
                (
                    f"MSG-{row.id}-INQ-{idx:03d}",
                    row.id,
                    "inquiry",
                    "citizen",
                    owner_uid,
                    msg.text,
                    None,
                    msg.date,
                ),
            )

        # 2. 답변 스레드 + 버전 이력 -> messages (kind='answer') + message_versions
        if row.versions or row.draft or row.published:
            ans_msg_id = f"MSG-{row.id}-ANS"
            ans_origin = (
                row.published.origin
                if row.published is not None
                else ("ai" if row.ai_original else "staff")
            )
            published_ver_id: str | None = None
            if row.published is not None:
                for idx in range(len(row.versions), 0, -1):
                    if row.versions[idx - 1].kind == "게시":
                        published_ver_id = f"MV-{row.id}-{idx:04d}"
                        break
            conn.execute(
                self._sql_upsert_message,
                (
                    ans_msg_id,
                    row.id,
                    "answer",
                    ans_origin,
                    assignee_uid,
                    row.published.text if row.published is not None else row.draft,
                    published_ver_id,
                    row.published.date if row.published is not None else row.date,
                ),
            )
            for idx, ver in enumerate(row.versions, start=1):
                ver_origin = version_origin(ver.kind, row)
                actor_uid = owner_uid if ver_origin == "citizen" else assignee_uid
                conn.execute(
                    self._sql_upsert_msg_version,
                    (
                        f"MV-{row.id}-{idx:04d}",
                        ans_msg_id,
                        row.id,
                        idx,
                        ver.text,
                        ver_origin,
                        ver.kind,
                        version_publish_state(ver.kind),
                        ver.reason,
                        actor_uid,
                        row.context_version,
                        ver.date,
                    ),
                )

        # 3. AI 작업 + 단계 로그 + AI 판정 결과 -> ai_jobs, job_events, ai_results
        job_id = f"JOB-{row.id}-C{row.job.context_version}-A{row.job.attempt}"
        returned = conn.execute(
            self._sql_upsert_ai_job,
            (
                job_id,
                row.id,
                row.job.context_version,
                row.job.attempt,
                row.job.status,
                row.job.stage,
                row.job.provider,
                row.job.started_at,
            ),
        ).fetchone()
        actual_job_id = str(returned[0]) if returned else job_id

        for seq_no, ev in enumerate(row.job.events, start=1):
            conn.execute(
                self._sql_upsert_job_event,
                (actual_job_id, row.id, seq_no, ev.date, ev.stage, "ai"),
            )

        if row.ai_assist is not None:
            dept_id_raw, dept_name = extract_primary_dept(row)
            dept_id = self._resolve_rag_department_id(conn, dept_id_raw)
            evidence_refs = [
                ref.model_dump(mode="json")
                for ref in row.ai_assist.decision.evidence_refs
            ]
            draft_body = (
                row.ai_assist.staff_draft.draft_answer
                if row.ai_assist.staff_draft is not None
                else None
            )
            conn.execute(
                self._sql_upsert_ai_result,
                (
                    f"RES-{actual_job_id}",
                    actual_job_id,
                    row.id,
                    row.ai_assist.outcome,
                    row.ai_assist.reason_code,
                    dept_id,
                    dept_name,
                    Jsonb(evidence_refs),
                    draft_body,
                    row.ai_assist.answer,
                    row.ai_assist.llm_provider,
                    row.ai_assist.llm_model,
                ),
            )

    def _backfill_normalized_tables(self, conn: psycopg.Connection) -> None:
        """정규화 이전 기존 `complaints` 행을 7테이블로 1회 이상 안전하게 백필합니다.

        Args:
            conn: 스키마 초기화 트랜잭션 연결입니다.
        """
        ident = sql.Identifier(self.schema)
        rows = conn.execute(
            sql.SQL(
                "SELECT c.id, c.payload FROM {}.complaints c "
                "WHERE c.title IS NULL OR NOT EXISTS ("
                "  SELECT 1 FROM {}.ai_jobs j WHERE j.complaint_id = c.id"
                ")"
            ).format(ident, ident)
        ).fetchall()
        for _cid, raw_payload in rows:
            try:
                model = Complaint.model_validate(raw_payload)
            except ValidationError:
                # 예전 스키마 마이그레이션 단위 테스트의 최소 JSON 스텁 행은 건너뜁니다.
                continue
            owner_uid = self._resolve_existing_user_id(conn, model.owner)
            assignee_uid = self._resolve_existing_user_id(conn, model.assignee_id)
            conn.execute(
                self._sql_sync_complaint_cols,
                (
                    owner_uid,
                    assignee_uid,
                    model.title,
                    model.body,
                    model.category,
                    model.department,
                    model.context_version,
                    model.id,
                ),
            )
            self._sync_normalized_children(conn, model, owner_uid, assignee_uid)

    @staticmethod
    def _row_to_user(row: tuple[Any, ...]) -> StoredUser:
        """`users` 테이블 SELECT 튜플을 `StoredUser` 데이터클래스로 변환합니다.

        Args:
            row: 10개 컬럼 조회 튜플입니다.

        Returns:
            복원된 `StoredUser` 인스턴스입니다.
        """
        role: Role = "staff" if row[3] == "staff" else "citizen"
        return StoredUser(
            id=str(row[0]),
            login_id=str(row[1]),
            display_name=str(row[2]),
            role=role,
            password_hash=str(row[4]),
            department=row[5],
            is_demo=bool(row[6]),
            active=bool(row[7]),
            created_at=row[8],
            last_login_at=row[9],
        )

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection]:
        """연결을 닫고 실패 시 트랜잭션을 되돌립니다.

        `conninfo`가 비면 libpq 환경변수(`PGHOST` 등)로 접속합니다.

        Yields:
            트랜잭션을 처리할 PostgreSQL 연결입니다.
        """
        if self.conninfo:
            conn = psycopg.connect(self.conninfo, connect_timeout=10)
        else:
            conn = psycopg.connect(connect_timeout=10)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def all(self) -> list[Complaint]:
        """저장된 전체 업무 민원을 최신 등록순으로 반환합니다."""
        with self.connection() as conn:
            rows = conn.execute(self._sql_all).fetchall()
        return [Complaint.model_validate(row[0]) for row in rows]

    def get(self, complaint_id: str) -> Complaint:
        """민원 식별자로 조회하며 누락은 404 업무 오류로 처리합니다.

        Args:
            complaint_id: 업무 민원 식별자입니다.

        Returns:
            저장된 민원 모델입니다.

        Raises:
            AppError: 민원이 없으면 발생합니다.
        """
        with self.connection() as conn:
            result = conn.execute(self._sql_get, (complaint_id,)).fetchone()
        if result is None:
            raise AppError(404, "not_found", "민원을 찾을 수 없습니다.")
        return Complaint.model_validate(result[0])

    def create(self, row: Complaint, key: str | None, fingerprint: str) -> Complaint:
        """작성자별 동일 등록 요청을 중복 없이 7테이블에 원자 저장합니다.

        Args:
            row: 새 업무 민원입니다.
            key: 선택적인 멱등성 키입니다.
            fingerprint: 같은 키의 본문 동일성을 검사할 해시입니다.

        Returns:
            생성된 민원 또는 같은 요청의 기존 민원입니다.

        Raises:
            AppError: 같은 키로 다른 내용을 요청하면 발생합니다.
        """
        payload = Jsonb(row.model_dump(mode="json"))
        with self.connection() as conn:
            if key:
                old = conn.execute(self._sql_key, (row.owner, key)).fetchone()
                if old:
                    if old[0] != fingerprint:
                        raise AppError(
                            409,
                            "idempotency_conflict",
                            "동일 등록 키에 다른 내용이 전송되었습니다.",
                        )
                    stored = conn.execute(self._sql_get, (old[1],)).fetchone()
                    if stored is None:
                        raise AppError(404, "not_found", "민원을 찾을 수 없습니다.")
                    return Complaint.model_validate(stored[0])
            owner_uid = self._resolve_existing_user_id(conn, row.owner)
            assignee_uid = self._resolve_existing_user_id(conn, row.assignee_id)
            conn.execute(
                self._sql_insert,
                (
                    row.id,
                    row.version,
                    row.date,
                    payload,
                    owner_uid,
                    assignee_uid,
                    row.title,
                    row.body,
                    row.category,
                    row.department,
                    row.context_version,
                ),
            )
            self._sync_normalized_children(conn, row, owner_uid, assignee_uid)
            if key:
                conn.execute(
                    self._sql_insert_key,
                    (row.owner, key, fingerprint, row.id),
                )
        return row

    def change(
        self, complaint_id: str, expected: int, action: Callable[[Complaint], None]
    ) -> Complaint:
        """트랜잭션 안에서 버전 검사·업무 변경·7테이블 동기화를 함께 수행합니다.

        Args:
            complaint_id: 수정할 민원 식별자입니다.
            expected: 기대하는 현재 버전입니다.
            action: 권한·상태를 검증하고 변경할 함수입니다.

        Returns:
            버전이 증가한 저장 결과입니다.

        Raises:
            AppError: 대상이 없거나 버전 충돌·업무 검증 실패 시 발생합니다.
        """
        with self.connection() as conn:
            result = conn.execute(self._sql_lock, (complaint_id,)).fetchone()
            if result is None:
                raise AppError(404, "not_found", "민원을 찾을 수 없습니다.")
            row = Complaint.model_validate(result[0])
            if row.version != expected:
                raise AppError(
                    409,
                    "version_conflict",
                    "다른 화면에서 내용이 변경되었습니다. 입력을 보관한 뒤 최신 내용을 불러와 주세요.",
                )
            action(row)
            row.version += 1
            owner_uid = self._resolve_existing_user_id(conn, row.owner)
            assignee_uid = self._resolve_existing_user_id(conn, row.assignee_id)
            conn.execute(
                self._sql_update,
                (
                    row.version,
                    Jsonb(row.model_dump(mode="json")),
                    owner_uid,
                    assignee_uid,
                    row.title,
                    row.body,
                    row.category,
                    row.department,
                    row.context_version,
                    complaint_id,
                    expected,
                ),
            )
            self._sync_normalized_children(conn, row, owner_uid, assignee_uid)
        return row

    def delete(
        self, complaint_id: str, expected: int, check: Callable[[Complaint], None]
    ) -> None:
        """트랜잭션 안에서 버전·권한을 검증하고 민원과 정규화 하위 행을 연쇄 삭제합니다.

        Args:
            complaint_id: 삭제할 민원 식별자입니다.
            expected: 기대하는 현재 버전입니다.
            check: 삭제 가능 여부를 검증할 함수입니다.

        Raises:
            AppError: 대상이 없거나 버전 충돌·권한 검증 실패 시 발생합니다.
        """
        with self.connection() as conn:
            result = conn.execute(self._sql_lock, (complaint_id,)).fetchone()
            if result is None:
                raise AppError(404, "not_found", "민원을 찾을 수 없습니다.")
            row = Complaint.model_validate(result[0])
            if row.version != expected:
                raise AppError(
                    409,
                    "version_conflict",
                    "다른 화면에서 내용이 변경되었습니다. 입력을 보관한 뒤 최신 내용을 불러와 주세요.",
                )
            check(row)
            conn.execute(self._sql_delete_keys, (complaint_id,))
            deleted = conn.execute(self._sql_delete, (complaint_id, expected))
            if deleted.rowcount == 0:
                raise AppError(
                    409,
                    "version_conflict",
                    "다른 화면에서 내용이 변경되었습니다. 입력을 보관한 뒤 최신 내용을 불러와 주세요.",
                )

    def _ensure_default_templates(self, conn: psycopg.Connection) -> None:
        """최초 스키마 초기화 시 한 번만 기본 답변 템플릿 5건을 넣습니다.

        Args:
            conn: 스키마를 준비 중인 PostgreSQL 연결입니다.
        """
        inserted = conn.execute(
            self._sql_seed_meta, ("default_templates_seeded", "1")
        ).fetchone()
        if inserted is None:
            return
        self._insert_default_template_rows(conn)

    def _insert_default_template_rows(self, conn: psycopg.Connection) -> None:
        """누락된 기본 답변 템플릿 행을 순서대로 삽입합니다.

        Args:
            conn: 활성 PostgreSQL 연결입니다.
        """
        base_time = utcnow()
        for idx, (tpl_id, title, content) in enumerate(DEFAULT_ANSWER_TEMPLATES):
            conn.execute(
                self._sql_insert_tpl,
                (tpl_id, title, content, True, base_time + timedelta(milliseconds=idx)),
            )

    def list_templates(self) -> list[AnswerTemplate]:
        """담당자 답변 편집기용 템플릿 목록을 등록순으로 반환합니다.

        Returns:
            DB 등록순으로 조회한 답변 템플릿 목록입니다.
        """
        with self.connection() as conn:
            rows = conn.execute(self._sql_list_tpl).fetchall()
        return [
            AnswerTemplate(
                id=row[0],
                title=row[1],
                content=row[2],
                is_default=bool(row[3]),
                created_at=row[4],
            )
            for row in rows
        ]

    def create_template(self, template: AnswerTemplate) -> AnswerTemplate:
        """새 답변 템플릿을 PostgreSQL 테이블에 저장하고 반환합니다.

        Args:
            template: 저장할 템플릿 모델입니다.

        Returns:
            저장한 템플릿 모델입니다.
        """
        with self.connection() as conn:
            conn.execute(
                self._sql_insert_tpl,
                (
                    template.id,
                    template.title,
                    template.content,
                    template.is_default,
                    template.created_at,
                ),
            )
        return template

    def delete_template(self, template_id: str) -> None:
        """지정한 답변 템플릿을 PostgreSQL 테이블에서 삭제합니다.

        Args:
            template_id: 삭제할 템플릿 식별자입니다.

        Raises:
            AppError: 일치하는 템플릿이 없을 때 발생합니다.
        """
        with self.connection() as conn:
            deleted = conn.execute(self._sql_delete_tpl, (template_id,))
            if deleted.rowcount == 0:
                raise AppError(404, "not_found", "템플릿을 찾을 수 없습니다.")

    def reset_default_templates(self) -> list[AnswerTemplate]:
        """삭제된 기본 답변 템플릿만 복원하고 전체 목록을 반환합니다.

        Returns:
            기본 문구 복원 후 전체 답변 템플릿 목록입니다.
        """
        with self.connection() as conn:
            self._insert_default_template_rows(conn)
        return self.list_templates()

    def get_user_by_id(self, user_id: str) -> StoredUser | None:
        """고유 식별자로 PostgreSQL `users` 계정을 조회합니다.

        Args:
            user_id: 사용자 고유 ID입니다.

        Returns:
            조회된 `StoredUser` 또는 None입니다.
        """
        with self.connection() as conn:
            row = conn.execute(self._sql_get_user_id, (user_id,)).fetchone()
        return self._row_to_user(row) if row is not None else None

    def get_user_by_login(self, login_id: str) -> StoredUser | None:
        """로그인 아이디(대소문자 무시)로 PostgreSQL `users` 계정을 조회합니다.

        Args:
            login_id: 로그인 아이디입니다.

        Returns:
            조회된 `StoredUser` 또는 None입니다.
        """
        with self.connection() as conn:
            row = conn.execute(self._sql_get_user_login, (login_id,)).fetchone()
        return self._row_to_user(row) if row is not None else None

    def create_user(self, user: StoredUser) -> StoredUser:
        """새 사용자 계정을 PostgreSQL `users` 테이블에 저장합니다.

        Args:
            user: 저장할 `StoredUser` 레코드입니다.

        Returns:
            저장된 `StoredUser` 레코드입니다.

        Raises:
            AppError: 아이디가 중복되면 409 오류를 발생합니다.
        """
        try:
            with self.connection() as conn:
                conn.execute(
                    self._sql_insert_user,
                    (
                        user.id,
                        user.login_id,
                        user.display_name,
                        user.role,
                        user.password_hash,
                        user.department,
                        user.is_demo,
                        user.active,
                        user.created_at,
                        user.last_login_at,
                    ),
                )
        except UniqueViolation as exc:
            raise AppError(
                409, "login_id_taken", "이미 사용 중인 아이디입니다."
            ) from exc
        return user

    def touch_user_login(self, user_id: str) -> None:
        """사용자의 `last_login_at`을 PostgreSQL 현재 시각으로 갱신합니다.

        Args:
            user_id: 로그인한 사용자 ID입니다.
        """
        with self.connection() as conn:
            conn.execute(self._sql_touch_login, (user_id,))

    def update_user_password(self, user_id: str, password_hash: str) -> None:
        """PostgreSQL 사용자의 비밀번호 해시를 바꿉니다.

        Args:
            user_id: 대상 `users.id`입니다.
            password_hash: 새 `scrypt` 해시 문자열입니다.
        """
        with self.connection() as conn:
            conn.execute(self._sql_update_password, (password_hash, user_id))

    def set_user_active(self, user_id: str, active: bool) -> None:
        """PostgreSQL 사용자의 활성 상태를 바꿉니다.

        Args:
            user_id: 대상 `users.id`입니다.
            active: 활성 상태 여부입니다.
        """
        with self.connection() as conn:
            conn.execute(self._sql_set_active, (active, user_id))

    def list_users(self) -> list[StoredUser]:
        """PostgreSQL `users` 테이블의 전체 사용자 목록을 반환합니다."""
        with self.connection() as conn:
            rows = conn.execute(self._sql_list_users).fetchall()
        return [self._row_to_user(row) for row in rows]

    def normalized_summary(self) -> NormalizedDbSummary:
        """정규화 7테이블의 실제 SQL 행 수와 AI 판정·사용자 역할 집계를 조회합니다.

        Returns:
            관계형 SQL 집계 결과가 담긴 `NormalizedDbSummary`입니다.
        """
        ident = sql.Identifier(self.schema)
        counts: dict[str, int] = {}
        outcomes: dict[str, int] = {}
        roles: dict[str, int] = {}
        with self.connection() as conn:
            for table in NORMALIZED_TABLE_NAMES:
                row = conn.execute(
                    sql.SQL("SELECT count(*) FROM {}.{}").format(
                        ident, sql.Identifier(table)
                    )
                ).fetchone()
                counts[table] = int(row[0]) if row else 0
            for out_key, cnt in conn.execute(
                sql.SQL(
                    "SELECT outcome, count(*) FROM {}.ai_results GROUP BY outcome"
                ).format(ident)
            ).fetchall():
                outcomes[str(out_key)] = int(cnt)
            for role_key, cnt in conn.execute(
                sql.SQL("SELECT role, count(*) FROM {}.users GROUP BY role").format(
                    ident
                )
            ).fetchall():
                roles[str(role_key)] = int(cnt)
        return NormalizedDbSummary(
            schema_name=self.schema,
            storage="postgresql",
            normalized_tables=counts,
            ai_outcomes=outcomes,
            user_roles=roles,
        )

    def list_chat_sessions(
        self, user_id: str, limit: int = 30
    ) -> list[ChatSessionSummary]:
        """PostgreSQL에서 특정 민원인의 챗봇 세션 목록을 최근 갱신순으로 조회합니다.

        Args:
            user_id: 소유 민원인의 `users.id`입니다.
            limit: 최대 조회 건수입니다.

        Returns:
            소유 민원인의 `ChatSessionSummary` 목록입니다.
        """
        with self.connection() as conn:
            rows = conn.execute(
                self._sql_list_chat_sessions, (user_id, max(1, limit))
            ).fetchall()
        return [
            ChatSessionSummary(
                id=str(row[0]),
                title=str(row[1]),
                last_district=row[2],
                message_count=int(row[3] or 0),
                created_at=row[4],
                updated_at=row[5],
            )
            for row in rows
        ]

    def get_chat_session(self, session_id: str, user_id: str) -> ChatSessionDetail:
        """PostgreSQL에서 소유권을 검증해 단일 챗봇 세션과 전체 발화를 조회합니다.

        Args:
            session_id: 조회할 챗봇 세션 ID입니다.
            user_id: 요청한 민원인의 `users.id`입니다.

        Returns:
            세션 요약과 발화 이력이 담긴 `ChatSessionDetail`입니다.

        Raises:
            AppError: 세션이 없거나 타인 소유이면 404를 발생합니다.
        """
        with self.connection() as conn:
            sess = conn.execute(
                self._sql_get_chat_session, (session_id, user_id)
            ).fetchone()
            if sess is None:
                raise AppError(404, "not_found", "대화 세션을 찾을 수 없습니다.")
            msg_rows = conn.execute(
                self._sql_list_chat_messages, (session_id,)
            ).fetchall()
        messages: list[ChatMessageRecord] = []
        for row in msg_rows:
            role: Literal["user", "assistant"] = (
                "assistant" if row[1] == "assistant" else "user"
            )
            payload_model = (
                CitizenChatResponse.model_validate(row[6])
                if row[6] is not None
                else None
            )
            messages.append(
                ChatMessageRecord(
                    id=str(row[0]),
                    role=role,
                    content=str(row[2]),
                    district=row[3],
                    outcome=row[4],
                    reason_code=row[5],
                    payload=payload_model,
                    created_at=row[7],
                )
            )
        return ChatSessionDetail(
            session=ChatSessionSummary(
                id=str(sess[0]),
                title=str(sess[1]),
                last_district=sess[2],
                message_count=len(messages),
                created_at=sess[3],
                updated_at=sess[4],
            ),
            messages=messages,
        )

    def save_chat_exchange(
        self,
        *,
        user_id: str,
        session_id: str | None,
        user_text: str,
        user_district: str | None,
        assistant_response: CitizenChatResponse,
    ) -> str:
        """시민 발화와 안전 투영된 도우미 응답 한 쌍을 PostgreSQL에 원자 저장합니다.

        Args:
            user_id: 소유 민원인의 `users.id`입니다.
            session_id: 이어 쓸 기존 세션 ID입니다. None이면 새 세션을 만듭니다.
            user_text: 시민이 입력한 질문 원문입니다.
            user_district: 이번 턴에 적용된 관할 구 또는 None입니다.
            assistant_response: 민감 필드가 제거된 `CitizenChatResponse` 모델입니다.

        Returns:
            저장된 세션 ID입니다.

        Raises:
            AppError: 지정한 세션이 없거나 타인 소유이면 404를 발생합니다.
        """
        user_ts = utcnow()
        assistant_ts = user_ts + timedelta(milliseconds=1)
        resolved_district = (
            assistant_response.district
            if assistant_response.district != "모름"
            else user_district
        )
        with self.connection() as conn:
            if session_id:
                existing = conn.execute(
                    self._sql_lock_chat_session, (session_id, user_id)
                ).fetchone()
                if existing is None:
                    raise AppError(404, "not_found", "대화 세션을 찾을 수 없습니다.")
                resolved_sid = session_id
                conn.execute(
                    self._sql_touch_chat_session,
                    (resolved_district, assistant_ts, resolved_sid, user_id),
                )
            else:
                resolved_sid = f"CHAT-{user_ts.year}-{uuid4().hex[:10].upper()}"
                title = " ".join(user_text.split())[:60] or "새 대화"
                conn.execute(
                    self._sql_insert_chat_session,
                    (
                        resolved_sid,
                        user_id,
                        title,
                        resolved_district,
                        user_ts,
                        assistant_ts,
                    ),
                )
            safe_payload = assistant_response.model_copy(
                update={"session_id": resolved_sid, "persisted": True}, deep=True
            )
            conn.execute(
                self._sql_insert_chat_message,
                (
                    f"CMSG-{uuid4().hex[:12].upper()}",
                    resolved_sid,
                    "user",
                    user_text,
                    user_district,
                    None,
                    None,
                    None,
                    user_ts,
                ),
            )
            conn.execute(
                self._sql_insert_chat_message,
                (
                    f"CMSG-{uuid4().hex[:12].upper()}",
                    resolved_sid,
                    "assistant",
                    safe_payload.answer,
                    resolved_district,
                    safe_payload.outcome,
                    safe_payload.reason_code,
                    Jsonb(safe_payload.model_dump(mode="json", by_alias=True)),
                    assistant_ts,
                ),
            )
        return resolved_sid

    def delete_chat_session(self, session_id: str, user_id: str) -> None:
        """PostgreSQL에서 소유 민원인의 챗봇 세션과 하위 메시지를 연쇄 삭제합니다.

        Args:
            session_id: 삭제할 챗봇 세션 ID입니다.
            user_id: 요청한 민원인의 `users.id`입니다.

        Raises:
            AppError: 세션이 없거나 타인 소유이면 404를 발생합니다.
        """
        with self.connection() as conn:
            deleted = conn.execute(self._sql_delete_chat_session, (session_id, user_id))
            if deleted.rowcount == 0:
                raise AppError(404, "not_found", "대화 세션을 찾을 수 없습니다.")

    def add_attachment(
        self,
        *,
        complaint_id: str,
        item: AttachmentItem,
        sha256_hex: str,
        storage_key: str,
        max_count: int,
        action_check: Callable[[Complaint], None],
    ) -> tuple[Complaint, AttachmentItem]:
        """PostgreSQL 행 잠금 안에서 권한·개수를 검사하고 첨부 행과 민원을 원자 갱신합니다.

        Args:
            complaint_id: 대상 민원 식별자입니다.
            item: 저장할 첨부 메타데이터 모델입니다.
            sha256_hex: 정제된 바이트의 SHA-256 해시입니다.
            storage_key: 디스크/스토리지 평면 파일 키입니다.
            max_count: 민원당 최대 허용 첨부 개수입니다.
            action_check: 잠금된 민원의 작성자·상태를 검증하는 콜백입니다.

        Returns:
            `(갱신된 민원, 저장된 첨부 메타데이터)` 튜플입니다.
        """
        with self.connection() as conn:
            locked = conn.execute(self._sql_lock, (complaint_id,)).fetchone()
            if locked is None:
                raise AppError(404, "not_found", "민원을 찾을 수 없습니다.")
            row = Complaint.model_validate(locked[0])
            expected = row.version
            action_check(row)
            if len(row.attachments) >= max_count:
                raise AppError(
                    409,
                    "attachment_limit_exceeded",
                    f"민원당 첨부파일은 최대 {max_count}개까지 등록할 수 있습니다.",
                )
            uploader_uid = self._resolve_existing_user_id(conn, item.uploaded_by)
            conn.execute(
                self._sql_insert_attachment,
                (
                    item.id,
                    complaint_id,
                    uploader_uid,
                    item.filename,
                    item.content_type,
                    item.size_bytes,
                    sha256_hex,
                    storage_key,
                    item.exif_stripped,
                    item.created_at,
                ),
            )
            row.attachments.append(item)
            row.history.append(History(text=f"시민이 첨부파일 등록: {item.filename}"))
            row.version += 1
            owner_uid = self._resolve_existing_user_id(conn, row.owner)
            assignee_uid = self._resolve_existing_user_id(conn, row.assignee_id)
            conn.execute(
                self._sql_update,
                (
                    row.version,
                    Jsonb(row.model_dump(mode="json")),
                    owner_uid,
                    assignee_uid,
                    row.title,
                    row.body,
                    row.category,
                    row.department,
                    row.context_version,
                    complaint_id,
                    expected,
                ),
            )
            self._sync_normalized_children(conn, row, owner_uid, assignee_uid)
        return row, item

    def get_attachment_meta(
        self, complaint_id: str, attachment_id: str
    ) -> tuple[AttachmentItem, str]:
        """PostgreSQL `attachments` 테이블에서 메타데이터와 내부 저장 키를 조회합니다.

        Args:
            complaint_id: 소속 민원 식별자입니다.
            attachment_id: 조회할 첨부 식별자입니다.

        Returns:
            `(첨부 메타데이터, storage_key)` 튜플입니다.

        Raises:
            AppError: 일치하는 첨부가 없으면 404를 발생합니다.
        """
        with self.connection() as conn:
            found = conn.execute(
                self._sql_get_attachment, (complaint_id, attachment_id)
            ).fetchone()
        if found is None:
            raise AppError(404, "not_found", "첨부파일을 찾을 수 없습니다.")
        mime = str(found[2])
        item = AttachmentItem(
            id=str(found[0]),
            filename=str(found[1]),
            content_type=mime,  # type: ignore[arg-type]
            size_bytes=int(found[3]),
            is_image=mime.startswith("image/"),
            exif_stripped=bool(found[4]),
            uploaded_by=str(found[5] or ""),
            created_at=found[6],
        )
        return item, str(found[7])

    def list_attachment_keys(self, complaint_id: str) -> list[str]:
        """PostgreSQL에서 민원에 연결된 모든 첨부 저장 키 목록을 조회합니다.

        Args:
            complaint_id: 대상 민원 식별자입니다.

        Returns:
            `storage_key` 문자열 목록입니다.
        """
        with self.connection() as conn:
            rows = conn.execute(
                self._sql_list_attachment_keys, (complaint_id,)
            ).fetchall()
        return [str(r[0]) for r in rows if r and r[0]]

    def delete_attachment(
        self,
        *,
        complaint_id: str,
        attachment_id: str,
        action_check: Callable[[Complaint], None],
    ) -> tuple[Complaint, str]:
        """PostgreSQL 행 잠금 안에서 권한을 검증하고 첨부 행과 민원을 원자 갱신합니다.

        Args:
            complaint_id: 소속 민원 식별자입니다.
            attachment_id: 삭제할 첨부 식별자입니다.
            action_check: 삭제 권한·상태를 검증하는 콜백입니다.

        Returns:
            `(갱신된 민원, 삭제할 storage_key)` 튜플입니다.

        Raises:
            AppError: 민원 또는 첨부가 없으면 404를 발생합니다.
        """
        with self.connection() as conn:
            locked = conn.execute(self._sql_lock, (complaint_id,)).fetchone()
            if locked is None:
                raise AppError(404, "not_found", "민원을 찾을 수 없습니다.")
            row = Complaint.model_validate(locked[0])
            expected = row.version
            action_check(row)
            removed = conn.execute(
                self._sql_delete_attachment, (complaint_id, attachment_id)
            ).fetchone()
            if removed is None:
                raise AppError(404, "not_found", "첨부파일을 찾을 수 없습니다.")
            removed_name, storage_key = str(removed[0]), str(removed[1])
            row.attachments = [
                att for att in row.attachments if att.id != attachment_id
            ]
            row.history.append(History(text=f"시민이 첨부파일 삭제: {removed_name}"))
            row.version += 1
            owner_uid = self._resolve_existing_user_id(conn, row.owner)
            assignee_uid = self._resolve_existing_user_id(conn, row.assignee_id)
            conn.execute(
                self._sql_update,
                (
                    row.version,
                    Jsonb(row.model_dump(mode="json")),
                    owner_uid,
                    assignee_uid,
                    row.title,
                    row.body,
                    row.category,
                    row.department,
                    row.context_version,
                    complaint_id,
                    expected,
                ),
            )
            self._sync_normalized_children(conn, row, owner_uid, assignee_uid)
        return row, storage_key
