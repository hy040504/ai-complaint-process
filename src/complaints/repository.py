"""RAG와 분리된 7테이블 정규화 업무 저장소와 원자적 버전·멱등성 검사를 제공합니다.

시연·운영은 PostgreSQL `complaint_app` 스키마의 7개 핵심 정규화 테이블
(`users`, `complaints`, `messages`, `message_versions`, `ai_jobs`, `ai_results`,
`job_events`)과 보조 3테이블(`idempotency`, `answer_templates`, `app_meta`)을
사용합니다. 단위 테스트는 같은 계약을 메모리 저장소로 검증할 수 있습니다.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import timedelta
from threading import Lock
from typing import Any, Literal, Protocol
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

StorageKind = Literal["postgresql", "memory"]

# 최초 스키마 준비 시 한 번만 시드하는 담당자 기본 답변 템플릿 목록이다.
DEFAULT_ANSWER_TEMPLATES: tuple[tuple[str, str, str], ...] = (
    (
        "TPL-DEF-1",
        "검토 결과 인사",
        "안녕하십니까. 접수하신 민원의 검토 결과를 안내드립니다.",
    ),
    ("TPL-DEF-2", "불편 사과", "불편을 드려 죄송합니다."),
    (
        "TPL-DEF-3",
        "추가 조사·부서 전달",
        "확인 과정에서 추가 조사가 필요하여 담당 부서에 전달하였습니다.",
    ),
    (
        "TPL-DEF-4",
        "추가 문의 안내",
        "추가 문의가 있으시면 민원 상세 화면의 추가 문의로 남겨 주세요.",
    ),
    ("TPL-DEF-5", "맺음말 감사", "감사합니다."),
)

NORMALIZED_TABLE_NAMES: tuple[str, ...] = (
    "users",
    "complaints",
    "messages",
    "message_versions",
    "ai_jobs",
    "ai_results",
    "job_events",
)

# psycopg는 한 execute에 여러 문을 넣지 못하므로 스키마·7테이블·보조 테이블을 순서대로 적용합니다.
_SCHEMA_STATEMENTS = (
    "CREATE SCHEMA IF NOT EXISTS {schema}",
    # 1. users : 민원인·담당자 아이디/비밀번호 계정
    """
    CREATE TABLE IF NOT EXISTS {schema}.users (
        id text PRIMARY KEY,
        login_id text NOT NULL UNIQUE,
        display_name text NOT NULL,
        role text NOT NULL CHECK (role IN ('citizen', 'staff')),
        password_hash text NOT NULL,
        department text,
        is_demo boolean NOT NULL DEFAULT false,
        active boolean NOT NULL DEFAULT true,
        created_at timestamptz NOT NULL DEFAULT now(),
        last_login_at timestamptz
    )
    """,
    "ALTER TABLE {schema}.users DROP COLUMN IF EXISTS verified, DROP COLUMN IF EXISTS phone_last4",
    "CREATE INDEX IF NOT EXISTS idx_app_users_role_dept ON {schema}.users (role, department)",
    # 2. complaints : 민원 본문·상태·버전·작성자/담당자 FK + 하위 호환 payload
    """
    CREATE TABLE IF NOT EXISTS {schema}.complaints (
        id text PRIMARY KEY,
        version integer NOT NULL CHECK (version > 0),
        created_at timestamptz NOT NULL,
        payload jsonb NOT NULL
    )
    """,
    # 예전 테이블은 id·created_at·payload만 있다. IF NOT EXISTS는 컬럼을 더하지 않는다.
    "ALTER TABLE {schema}.complaints ADD COLUMN IF NOT EXISTS version integer",
    """
    UPDATE {schema}.complaints
    SET version = CASE
        WHEN COALESCE(payload->>'version', '') ~ '^[1-9][0-9]*$'
        THEN (payload->>'version')::integer
        ELSE 1
    END
    WHERE version IS NULL
    """,
    "ALTER TABLE {schema}.complaints ALTER COLUMN version SET NOT NULL",
    # 목록·필터용 생성 칼럼(하위 호환) + 정규화 관계형 칼럼
    "ALTER TABLE {schema}.complaints ADD COLUMN IF NOT EXISTS status text GENERATED ALWAYS AS (payload->>'status') STORED",
    "ALTER TABLE {schema}.complaints ADD COLUMN IF NOT EXISTS owner text GENERATED ALWAYS AS (payload->>'owner') STORED",
    "ALTER TABLE {schema}.complaints ADD COLUMN IF NOT EXISTS visibility text GENERATED ALWAYS AS (payload->>'visibility') STORED",
    "ALTER TABLE {schema}.complaints ADD COLUMN IF NOT EXISTS district text GENERATED ALWAYS AS (payload->>'district') STORED",
    "ALTER TABLE {schema}.complaints ADD COLUMN IF NOT EXISTS is_synthetic boolean GENERATED ALWAYS AS (COALESCE((payload->>'isSynthetic')::boolean, false)) STORED",
    "ALTER TABLE {schema}.complaints ADD COLUMN IF NOT EXISTS owner_user_id text REFERENCES {schema}.users(id)",
    "ALTER TABLE {schema}.complaints ADD COLUMN IF NOT EXISTS assignee_user_id text REFERENCES {schema}.users(id)",
    "ALTER TABLE {schema}.complaints ADD COLUMN IF NOT EXISTS title text",
    "ALTER TABLE {schema}.complaints ADD COLUMN IF NOT EXISTS body text",
    "ALTER TABLE {schema}.complaints ADD COLUMN IF NOT EXISTS category text",
    "ALTER TABLE {schema}.complaints ADD COLUMN IF NOT EXISTS department text",
    "ALTER TABLE {schema}.complaints ADD COLUMN IF NOT EXISTS context_version integer NOT NULL DEFAULT 1",
    "ALTER TABLE {schema}.complaints ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now()",
    "CREATE INDEX IF NOT EXISTS complaints_status_created ON {schema}.complaints (status, created_at)",
    "CREATE INDEX IF NOT EXISTS complaints_owner_created ON {schema}.complaints (owner, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_app_complaints_department ON {schema}.complaints (department, created_at DESC)",
    # 예전 시연 데이터에는 isSynthetic 키가 없으므로 공개 시연 ID(DEMO-PUB-)만 한 번 채운다.
    """
    UPDATE {schema}.complaints
    SET payload = payload || jsonb_build_object('isSynthetic', true)
    WHERE left(id, 9) = 'DEMO-PUB-' AND NOT (payload ? 'isSynthetic')
    """,
    # 3. messages : 민원별 답변 스레드 및 시민 추가 문의
    """
    CREATE TABLE IF NOT EXISTS {schema}.messages (
        id text PRIMARY KEY,
        complaint_id text NOT NULL REFERENCES {schema}.complaints(id) ON DELETE CASCADE,
        kind text NOT NULL CHECK (kind IN ('answer', 'inquiry')),
        origin text NOT NULL CHECK (origin IN ('ai', 'ai_edited', 'staff', 'citizen')),
        author_user_id text REFERENCES {schema}.users(id),
        body text NOT NULL DEFAULT '',
        published_version_id text,
        created_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_app_messages_complaint ON {schema}.messages (complaint_id, created_at)",
    # 4. message_versions : 답변 초안·게시·철회·원문 수정 버전 이력
    """
    CREATE TABLE IF NOT EXISTS {schema}.message_versions (
        id text PRIMARY KEY,
        message_id text NOT NULL REFERENCES {schema}.messages(id) ON DELETE CASCADE,
        complaint_id text NOT NULL REFERENCES {schema}.complaints(id) ON DELETE CASCADE,
        version_no integer NOT NULL,
        body text NOT NULL,
        origin text NOT NULL CHECK (origin IN ('ai', 'ai_edited', 'staff', 'citizen')),
        kind text NOT NULL,
        publish_state text NOT NULL CHECK (publish_state IN ('draft', 'published', 'retracted', 'archived')),
        reason text NOT NULL DEFAULT '',
        actor_user_id text REFERENCES {schema}.users(id),
        context_version integer NOT NULL DEFAULT 1,
        created_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE (message_id, version_no)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_app_message_versions_complaint ON {schema}.message_versions (complaint_id, version_no)",
    # 5. ai_jobs : 민원별 AI 분석 실행 작업
    """
    CREATE TABLE IF NOT EXISTS {schema}.ai_jobs (
        id text PRIMARY KEY,
        complaint_id text NOT NULL REFERENCES {schema}.complaints(id) ON DELETE CASCADE,
        context_version integer NOT NULL,
        attempt integer NOT NULL,
        state text NOT NULL CHECK (state IN ('queued', 'running', 'succeeded', 'failed', 'cancelled', 'superseded')),
        stage text NOT NULL DEFAULT '',
        provider text,
        started_at timestamptz,
        updated_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE (complaint_id, context_version, attempt)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_app_ai_jobs_state ON {schema}.ai_jobs (state, updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_app_ai_jobs_complaint ON {schema}.ai_jobs (complaint_id)",
    # 6. ai_results : AI 판정·근거·부서 추천 결과(자동 이관 금지 DB CHECK 강제)
    """
    CREATE TABLE IF NOT EXISTS {schema}.ai_results (
        id text PRIMARY KEY,
        job_id text NOT NULL UNIQUE REFERENCES {schema}.ai_jobs(id) ON DELETE CASCADE,
        complaint_id text NOT NULL REFERENCES {schema}.complaints(id) ON DELETE CASCADE,
        outcome text NOT NULL CHECK (outcome IN ('faq_answer', 'department_suggestion', 'human_handoff')),
        reason_code text NOT NULL DEFAULT '',
        department_id text,
        department_name text,
        evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
        draft_body text,
        guide_body text,
        automatic_transfer boolean NOT NULL DEFAULT false CHECK (automatic_transfer = false),
        llm_provider text,
        llm_model text,
        created_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_app_ai_results_outcome ON {schema}.ai_results (outcome, created_at DESC)",
    # 7. job_events : AI 작업 단계별 진행 로그
    """
    CREATE TABLE IF NOT EXISTS {schema}.job_events (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        job_id text NOT NULL REFERENCES {schema}.ai_jobs(id) ON DELETE CASCADE,
        complaint_id text NOT NULL REFERENCES {schema}.complaints(id) ON DELETE CASCADE,
        seq_no integer NOT NULL,
        occurred_at timestamptz NOT NULL DEFAULT now(),
        stage text NOT NULL,
        vis text NOT NULL DEFAULT 'ai' CHECK (vis IN ('pub', 'int', 'ai')),
        UNIQUE (job_id, seq_no)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_app_job_events_job ON {schema}.job_events (job_id, seq_no)",
    # 보조 3테이블 : idempotency, answer_templates, app_meta
    """
    CREATE TABLE IF NOT EXISTS {schema}.idempotency (
        owner text NOT NULL,
        key text NOT NULL,
        fingerprint text NOT NULL,
        complaint_id text NOT NULL REFERENCES {schema}.complaints(id) ON DELETE CASCADE,
        PRIMARY KEY (owner, key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS {schema}.answer_templates (
        id text PRIMARY KEY,
        title text NOT NULL,
        content text NOT NULL,
        is_default boolean NOT NULL DEFAULT false,
        created_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS {schema}.app_meta (
        key text PRIMARY KEY,
        value text NOT NULL
    )
    """,
    # 시민 민원 도우미 다중 턴 대화 저장 테이블(로그인 민원인 전용·안전 투영 JSON만 저장)
    """
    CREATE TABLE IF NOT EXISTS {schema}.chat_sessions (
        id text PRIMARY KEY,
        user_id text NOT NULL REFERENCES {schema}.users(id) ON DELETE CASCADE,
        title text NOT NULL,
        last_district text,
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_app_chat_sessions_user ON {schema}.chat_sessions (user_id, updated_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS {schema}.chat_messages (
        id text PRIMARY KEY,
        session_id text NOT NULL REFERENCES {schema}.chat_sessions(id) ON DELETE CASCADE,
        role text NOT NULL CHECK (role IN ('user', 'assistant')),
        content text NOT NULL,
        district text,
        outcome text CHECK (outcome IS NULL OR outcome IN ('faq_answer', 'department_suggestion', 'human_handoff')),
        reason_code text,
        payload jsonb,
        created_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_app_chat_messages_session ON {schema}.chat_messages (session_id, created_at ASC)",
    # 민원 첨부파일 메타데이터(원본 바이트는 디스크/메모리 저장소에 분리 보관)
    """
    CREATE TABLE IF NOT EXISTS {schema}.attachments (
        id text PRIMARY KEY,
        complaint_id text NOT NULL REFERENCES {schema}.complaints(id) ON DELETE CASCADE,
        uploaded_by text REFERENCES {schema}.users(id),
        filename text NOT NULL,
        content_type text NOT NULL CHECK (content_type IN ('image/jpeg', 'image/png', 'image/webp', 'application/pdf')),
        size_bytes integer NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 5242880),
        sha256 text NOT NULL,
        storage_key text NOT NULL UNIQUE,
        exif_stripped boolean NOT NULL DEFAULT false,
        created_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_app_attachments_complaint ON {schema}.attachments (complaint_id, created_at ASC, id ASC)",
)


# 상태·공개 범위·지역을 DB도 검사한다. 값 목록은 src/complaints/models.py와 맞춘다.
_VALUE_CHECKS: tuple[tuple[str, str], ...] = (
    (
        "complaints_status_valid",
        "status IN ('submitted', 'under_review', 'answered', 'closed', 'withdrawn')",
    ),
    ("complaints_visibility_valid", "visibility IN ('private', 'public')"),
    (
        "complaints_district_valid",
        "district IN ('상당구', '서원구', '흥덕구', '청원구', '모름')",
    ),
)


def _version_publish_state(kind: str) -> str:
    """`AnswerVersion.kind` 문자열을 `message_versions.publish_state` 값으로 변환합니다.

    Args:
        kind: 버전 기록 유형 문자열입니다.

    Returns:
        `draft`·`published`·`retracted`·`archived` 중 하나입니다.
    """
    if kind == "게시":
        return "published"
    if kind == "게시 철회":
        return "retracted"
    if kind == "초안 저장":
        return "draft"
    return "archived"


def _version_origin(kind: str, row: Complaint) -> str:
    """`AnswerVersion.kind`와 민원 상태에서 버전 작성 주체(`origin`)를 결정합니다.

    Args:
        kind: 버전 기록 유형 문자열입니다.
        row: 소속 민원 모델입니다.

    Returns:
        `ai`·`ai_edited`·`staff`·`citizen` 중 하나입니다.
    """
    if kind == "시민 원문 수정 전":
        return "citizen"
    if kind == "이전 AI 원본":
        return "ai"
    if kind == "게시" and row.published is not None:
        return row.published.origin
    return "staff"


def _extract_primary_dept(row: Complaint) -> tuple[str | None, str | None]:
    """`ai_assist`에서 추천 1순위 부서의 `(department_id, department_name)`을 뽑습니다.

    Args:
        row: AI 분석 결과를 담은 민원 모델입니다.

    Returns:
        `(부서 ID 또는 None, 부서명 또는 None)` 튜플입니다.
    """
    assist = row.ai_assist
    if assist is None or not assist.departments:
        return None, None
    chosen = next((d for d in assist.departments if d.selected), assist.departments[0])
    return chosen.department_id, chosen.canonical_name


class ComplaintRepository(Protocol):
    """업무·인증 서비스가 의존하는 저장소 인터페이스입니다."""

    storage: StorageKind

    def all(self) -> list[Complaint]:
        """저장된 민원을 최신 등록순으로 반환합니다."""
        ...

    def get(self, complaint_id: str) -> Complaint:
        """식별자에 해당하는 민원을 반환합니다.

        Args:
            complaint_id: 업무 민원 식별자입니다.

        Raises:
            AppError: 해당 민원이 없을 때 발생합니다.
        """
        ...

    def create(self, row: Complaint, key: str | None, fingerprint: str) -> Complaint:
        """민원과 등록 키·정규화 하위 테이블을 같은 트랜잭션에 저장합니다.

        Args:
            row: 새 민원입니다.
            key: 작성자별 중복 방지 키입니다.
            fingerprint: 등록 본문의 해시입니다.

        Returns:
            새 민원 또는 동일 요청으로 이미 저장된 민원입니다.

        Raises:
            AppError: 같은 키로 다른 내용을 요청하면 발생합니다.
        """
        ...

    def change(
        self, complaint_id: str, expected: int, action: Callable[[Complaint], None]
    ) -> Complaint:
        """최신 버전을 검사한 뒤 업무 변경과 7테이블 동기화를 원자적으로 저장합니다.

        Args:
            complaint_id: 수정 대상 식별자입니다.
            expected: 호출자가 조회한 버전입니다.
            action: 검증된 민원을 변경할 업무 함수입니다.

        Returns:
            변경 후 민원입니다.
        """
        ...

    def delete(
        self, complaint_id: str, expected: int, check: Callable[[Complaint], None]
    ) -> None:
        """최신 버전을 검사한 뒤 민원과 연결된 하위 테이블·멱등성 키를 영구 삭제합니다.

        Args:
            complaint_id: 삭제할 민원 식별자입니다.
            expected: 호출자가 조회한 현재 버전입니다.
            check: 삭제 권한을 검증할 함수입니다.
        """
        ...

    def list_templates(self) -> list[AnswerTemplate]:
        """담당자 답변 편집기용 템플릿 목록을 등록순으로 반환합니다."""
        ...

    def create_template(self, template: AnswerTemplate) -> AnswerTemplate:
        """새 답변 템플릿을 저장하고 반환합니다.

        Args:
            template: 저장할 템플릿 모델입니다.
        """
        ...

    def delete_template(self, template_id: str) -> None:
        """지정한 답변 템플릿을 삭제합니다.

        Args:
            template_id: 삭제할 템플릿 식별자입니다.
        """
        ...

    def reset_default_templates(self) -> list[AnswerTemplate]:
        """누락된 기본 답변 템플릿을 복원하고 전체 목록을 반환합니다."""
        ...

    def get_user_by_id(self, user_id: str) -> StoredUser | None:
        """고유 식별자로 사용자 계정을 조회합니다.

        Args:
            user_id: `users.id` 값입니다.
        """
        ...

    def get_user_by_login(self, login_id: str) -> StoredUser | None:
        """로그인 아이디로 사용자 계정을 조회합니다.

        Args:
            login_id: 로그인 아이디 문자열입니다.
        """
        ...

    def create_user(self, user: StoredUser) -> StoredUser:
        """새 사용자 계정을 저장하고 반환합니다.

        Args:
            user: 저장할 `StoredUser` 레코드입니다.
        """
        ...

    def touch_user_login(self, user_id: str) -> None:
        """사용자의 마지막 로그인 시각(`last_login_at`)을 갱신합니다.

        Args:
            user_id: 로그인에 성공한 `users.id`입니다.
        """
        ...

    def list_users(self) -> list[StoredUser]:
        """저장된 전체 사용자 계정 목록을 반환합니다."""
        ...

    def normalized_summary(self) -> NormalizedDbSummary:
        """정규화 7테이블의 행 수와 AI 판정·사용자 역할 집계를 반환합니다."""
        ...

    def list_chat_sessions(
        self, user_id: str, limit: int = 30
    ) -> list[ChatSessionSummary]:
        """특정 민원인의 챗봇 대화 세션 목록을 최근 갱신순으로 반환합니다.

        Args:
            user_id: 소유 민원인의 `users.id`입니다.
            limit: 최대 반환 세션 개수입니다.
        """
        ...

    def get_chat_session(self, session_id: str, user_id: str) -> ChatSessionDetail:
        """소유권을 검증해 단일 챗봇 대화 세션과 발화 이력을 반환합니다.

        Args:
            session_id: 조회할 챗봇 세션 ID입니다.
            user_id: 요청한 민원인의 `users.id`입니다.

        Raises:
            AppError: 세션이 없거나 타인 소유이면 404를 발생합니다.
        """
        ...

    def save_chat_exchange(
        self,
        *,
        user_id: str,
        session_id: str | None,
        user_text: str,
        user_district: str | None,
        assistant_response: CitizenChatResponse,
    ) -> str:
        """시민 발화와 안전 투영된 도우미 응답 한 쌍을 원자적으로 저장합니다.

        Args:
            user_id: 소유 민원인의 `users.id`입니다.
            session_id: 이어 쓸 기존 세션 ID입니다. None이면 새 세션을 생성합니다.
            user_text: 시민이 입력한 이번 턴 원문입니다.
            user_district: 이번 턴에 적용한 관할 구 또는 None입니다.
            assistant_response: 민감 필드가 제거된 `CitizenChatResponse` 모델입니다.

        Returns:
            저장된 세션 ID입니다.
        """
        ...

    def delete_chat_session(self, session_id: str, user_id: str) -> None:
        """소유 민원인의 챗봇 대화 세션과 하위 메시지를 연쇄 삭제합니다.

        Args:
            session_id: 삭제할 챗봇 세션 ID입니다.
            user_id: 요청한 민원인의 `users.id`입니다.

        Raises:
            AppError: 세션이 없거나 타인 소유이면 404를 발생합니다.
        """
        ...

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
        """민원 잠금 안에서 권한·개수를 검증하고 첨부 메타데이터를 원자 저장합니다.

        Args:
            complaint_id: 대상 민원 식별자입니다.
            item: 저장할 첨부파일 메타데이터 모델입니다.
            sha256_hex: 정제된 바이트의 SHA-256 해시입니다.
            storage_key: 저장소에 기록된 평면 파일 키입니다.
            max_count: 민원당 최대 허용 첨부 개수입니다.
            action_check: 잠금된 민원의 작성자·상태를 검증하는 콜백입니다.

        Returns:
            `(갱신된 민원, 저장된 첨부 메타데이터)` 튜플입니다.
        """
        ...

    def get_attachment_meta(
        self, complaint_id: str, attachment_id: str
    ) -> tuple[AttachmentItem, str]:
        """첨부파일 메타데이터와 내부 저장 키를 조회합니다.

        Args:
            complaint_id: 소속 민원 식별자입니다.
            attachment_id: 조회할 첨부파일 식별자입니다.

        Returns:
            `(첨부 메타데이터, storage_key)` 튜플입니다.
        """
        ...

    def list_attachment_keys(self, complaint_id: str) -> list[str]:
        """민원에 연결된 모든 첨부파일 저장 키 목록을 반환합니다.

        Args:
            complaint_id: 대상 민원 식별자입니다.
        """
        ...

    def delete_attachment(
        self,
        *,
        complaint_id: str,
        attachment_id: str,
        action_check: Callable[[Complaint], None],
    ) -> tuple[Complaint, str]:
        """민원 잠금 안에서 권한을 검증하고 첨부 행을 제거한 뒤 저장 키를 반환합니다.

        Args:
            complaint_id: 소속 민원 식별자입니다.
            attachment_id: 삭제할 첨부파일 식별자입니다.
            action_check: 삭제 권한·상태를 검증하는 콜백입니다.

        Returns:
            `(갱신된 민원, 삭제할 storage_key)` 튜플입니다.
        """
        ...


class MemoryRepository:
    """프로세스 안의 업무 저장소입니다. 단위 테스트 전용입니다.

    PostgreSQL 없이 7테이블 계약과 인증 계정을 동일한 인터페이스로 검증할 때 씁니다.
    """

    storage: StorageKind = "memory"

    def __init__(self) -> None:
        """빈 민원·멱등성 맵, 기본 시드 사용자·답변 템플릿과 변경 잠금을 준비합니다."""
        self._rows: dict[str, Complaint] = {}
        self._keys: dict[tuple[str, str], tuple[str, str]] = {}
        self._users: dict[str, StoredUser] = {
            user.id: user for user in default_seed_users()
        }
        self._templates: list[AnswerTemplate] = [
            AnswerTemplate(id=tpl_id, title=title, content=content, is_default=True)
            for tpl_id, title, content in DEFAULT_ANSWER_TEMPLATES
        ]
        self._chat_sessions: dict[
            str, tuple[str, ChatSessionSummary, list[ChatMessageRecord]]
        ] = {}
        self._attachments: dict[tuple[str, str], tuple[AttachmentItem, str, str]] = {}
        self._lock = Lock()

    def all(self) -> list[Complaint]:
        """저장된 전체 업무 민원을 최신 등록순으로 반환합니다."""
        with self._lock:
            return sorted(
                (item.model_copy(deep=True) for item in self._rows.values()),
                key=lambda item: (item.date, item.id),
                reverse=True,
            )

    def get(self, complaint_id: str) -> Complaint:
        """민원 식별자로 조회하며 누락은 404 업무 오류로 처리합니다.

        Args:
            complaint_id: 업무 민원 식별자입니다.

        Returns:
            저장된 민원 모델입니다.

        Raises:
            AppError: 민원이 없으면 발생합니다.
        """
        with self._lock:
            row = self._rows.get(complaint_id)
        if row is None:
            raise AppError(404, "not_found", "민원을 찾을 수 없습니다.")
        return row.model_copy(deep=True)

    def create(self, row: Complaint, key: str | None, fingerprint: str) -> Complaint:
        """작성자별 동일 등록 요청을 중복 생성 없이 저장합니다.

        Args:
            row: 새 업무 민원입니다.
            key: 선택적인 멱등성 키입니다.
            fingerprint: 같은 키의 본문 동일성을 검사할 해시입니다.

        Returns:
            생성된 민원 또는 같은 요청의 기존 민원입니다.

        Raises:
            AppError: 같은 키로 다른 내용을 요청하면 발생합니다.
        """
        with self._lock:
            if key:
                old = self._keys.get((row.owner, key))
                if old:
                    if old[0] != fingerprint:
                        raise AppError(
                            409,
                            "idempotency_conflict",
                            "동일 등록 키에 다른 내용이 전송되었습니다.",
                        )
                    stored = self._rows[old[1]]
                    return stored.model_copy(deep=True)
            stored = row.model_copy(deep=True)
            self._rows[stored.id] = stored
            if key:
                self._keys[(row.owner, key)] = (fingerprint, stored.id)
        return stored.model_copy(deep=True)

    def change(
        self, complaint_id: str, expected: int, action: Callable[[Complaint], None]
    ) -> Complaint:
        """잠금 안에서 버전 검사·업무 검증·갱신을 함께 수행합니다.

        Args:
            complaint_id: 수정할 민원 식별자입니다.
            expected: 기대하는 현재 버전입니다.
            action: 권한·상태를 검증하고 변경할 함수입니다.

        Returns:
            버전이 증가한 저장 결과입니다.

        Raises:
            AppError: 대상이 없거나 버전 충돌·업무 검증 실패 시 발생합니다.
        """
        with self._lock:
            current = self._rows.get(complaint_id)
            if current is None:
                raise AppError(404, "not_found", "민원을 찾을 수 없습니다.")
            if current.version != expected:
                raise AppError(
                    409,
                    "version_conflict",
                    "다른 화면에서 내용이 변경되었습니다. 입력을 보관한 뒤 최신 내용을 불러와 주세요.",
                )
            row = current.model_copy(deep=True)
            action(row)
            row.version += 1
            self._rows[complaint_id] = row
        return row.model_copy(deep=True)

    def delete(
        self, complaint_id: str, expected: int, check: Callable[[Complaint], None]
    ) -> None:
        """잠금 안에서 버전·삭제 권한을 검사한 뒤 민원과 멱등성 키를 삭제합니다.

        Args:
            complaint_id: 삭제할 민원 식별자입니다.
            expected: 호출자가 조회한 현재 버전입니다.
            check: 삭제 권한을 검증할 함수입니다.

        Raises:
            AppError: 대상이 없거나 버전 충돌·권한 검증 실패 시 발생합니다.
        """
        with self._lock:
            current = self._rows.get(complaint_id)
            if current is None:
                raise AppError(404, "not_found", "민원을 찾을 수 없습니다.")
            if current.version != expected:
                raise AppError(
                    409,
                    "version_conflict",
                    "다른 화면에서 내용이 변경되었습니다. 최신 내용을 불러온 뒤 다시 시도해 주세요.",
                )
            check(current.model_copy(deep=True))
            del self._rows[complaint_id]
            stale_keys = [
                k for k, (_, cid) in self._keys.items() if cid == complaint_id
            ]
            for key in stale_keys:
                del self._keys[key]
            stale_atts = [
                att_key for att_key in self._attachments if att_key[0] == complaint_id
            ]
            for att_key in stale_atts:
                del self._attachments[att_key]

    def list_templates(self) -> list[AnswerTemplate]:
        """담당자 답변 편집기용 템플릿 목록을 등록순으로 반환합니다.

        Returns:
            등록순으로 정렬된 답변 템플릿 모델 목록 사본입니다.
        """
        with self._lock:
            return [tpl.model_copy(deep=True) for tpl in self._templates]

    def create_template(self, template: AnswerTemplate) -> AnswerTemplate:
        """새 답변 템플릿을 저장하고 사본을 반환합니다.

        Args:
            template: 저장할 템플릿 모델입니다.

        Returns:
            저장된 템플릿 모델 사본입니다.
        """
        with self._lock:
            stored = template.model_copy(deep=True)
            self._templates.append(stored)
            return stored.model_copy(deep=True)

    def delete_template(self, template_id: str) -> None:
        """지정한 식별자의 답변 템플릿을 삭제합니다.

        Args:
            template_id: 삭제할 템플릿 식별자입니다.

        Raises:
            AppError: 일치하는 템플릿이 없을 때 발생합니다.
        """
        with self._lock:
            before = len(self._templates)
            self._templates = [tpl for tpl in self._templates if tpl.id != template_id]
            if len(self._templates) == before:
                raise AppError(404, "not_found", "템플릿을 찾을 수 없습니다.")

    def reset_default_templates(self) -> list[AnswerTemplate]:
        """삭제된 기본 답변 템플릿만 복원하고 기존 커스텀 항목은 유지합니다.

        Returns:
            복원 후 전체 템플릿 목록입니다.
        """
        with self._lock:
            existing_ids = {tpl.id for tpl in self._templates}
            for tpl_id, title, content in DEFAULT_ANSWER_TEMPLATES:
                if tpl_id not in existing_ids:
                    self._templates.append(
                        AnswerTemplate(
                            id=tpl_id, title=title, content=content, is_default=True
                        )
                    )
            return [tpl.model_copy(deep=True) for tpl in self._templates]

    def get_user_by_id(self, user_id: str) -> StoredUser | None:
        """고유 식별자로 메모리 사용자 계정을 조회합니다.

        Args:
            user_id: 사용자 고유 ID입니다.

        Returns:
            일치하는 `StoredUser` 또는 None입니다.
        """
        with self._lock:
            return self._users.get(user_id)

    def get_user_by_login(self, login_id: str) -> StoredUser | None:
        """로그인 아이디(대소문자 무시)로 메모리 사용자 계정을 조회합니다.

        Args:
            login_id: 로그인 아이디입니다.

        Returns:
            일치하는 `StoredUser` 또는 None입니다.
        """
        target = login_id.casefold()
        with self._lock:
            for user in self._users.values():
                if user.login_id.casefold() == target:
                    return user
        return None

    def create_user(self, user: StoredUser) -> StoredUser:
        """새 사용자 계정을 메모리에 저장하며 아이디 중복을 거부합니다.

        Args:
            user: 저장할 사용자 레코드입니다.

        Returns:
            저장된 사용자 레코드입니다.

        Raises:
            AppError: 동일한 `login_id`가 이미 존재하면 409를 발생합니다.
        """
        target = user.login_id.casefold()
        with self._lock:
            if any(u.login_id.casefold() == target for u in self._users.values()):
                raise AppError(409, "login_id_taken", "이미 사용 중인 아이디입니다.")
            self._users[user.id] = user
        return user

    def touch_user_login(self, user_id: str) -> None:
        """메모리 사용자의 마지막 로그인 시각을 현재 UTC로 갱신합니다.

        Args:
            user_id: 사용자 고유 ID입니다.
        """
        with self._lock:
            old = self._users.get(user_id)
            if old is None:
                return
            self._users[user_id] = StoredUser(
                id=old.id,
                login_id=old.login_id,
                display_name=old.display_name,
                role=old.role,
                password_hash=old.password_hash,
                department=old.department,
                is_demo=old.is_demo,
                active=old.active,
                created_at=old.created_at,
                last_login_at=utcnow(),
            )

    def list_users(self) -> list[StoredUser]:
        """메모리에 저장된 전체 사용자 계정을 반환합니다."""
        with self._lock:
            return list(self._users.values())

    def normalized_summary(self) -> NormalizedDbSummary:
        """메모리 저장소의 7테이블 환산 행 수와 AI·역할 집계를 계산합니다.

        Returns:
            `NormalizedDbSummary` 응답 모델입니다.
        """
        with self._lock:
            rows = list(self._rows.values())
            users = list(self._users.values())
        msg_count = 0
        ver_count = 0
        job_count = len(rows)
        result_count = 0
        event_count = 0
        outcomes: dict[str, int] = {}
        for row in rows:
            msg_count += len(row.messages) + (
                1 if (row.versions or row.draft or row.published) else 0
            )
            ver_count += len(row.versions)
            event_count += len(row.job.events)
            if row.ai_assist is not None:
                result_count += 1
                out = row.ai_assist.outcome
                outcomes[out] = outcomes.get(out, 0) + 1
        roles: dict[str, int] = {}
        for user in users:
            roles[user.role] = roles.get(user.role, 0) + 1
        return NormalizedDbSummary(
            schema_name="memory",
            storage="memory",
            normalized_tables={
                "users": len(users),
                "complaints": len(rows),
                "messages": msg_count,
                "message_versions": ver_count,
                "ai_jobs": job_count,
                "ai_results": result_count,
                "job_events": event_count,
            },
            ai_outcomes=outcomes,
            user_roles=roles,
        )

    def list_chat_sessions(
        self, user_id: str, limit: int = 30
    ) -> list[ChatSessionSummary]:
        """메모리 저장소에서 특정 민원인의 챗봇 세션 목록을 최근 갱신순으로 반환합니다.

        Args:
            user_id: 소유 민원인의 `users.id`입니다.
            limit: 최대 반환 세션 수입니다.

        Returns:
            소유 민원인의 `ChatSessionSummary` 사본 목록입니다.
        """
        with self._lock:
            owned = [
                summary.model_copy(update={"message_count": len(messages)}, deep=True)
                for owner, summary, messages in self._chat_sessions.values()
                if owner == user_id
            ]
        owned.sort(key=lambda item: (item.updated_at, item.id), reverse=True)
        return owned[: max(1, limit)]

    def get_chat_session(self, session_id: str, user_id: str) -> ChatSessionDetail:
        """메모리 저장소에서 소유권을 검증해 챗봇 세션 상세와 발화 이력을 반환합니다.

        Args:
            session_id: 조회할 챗봇 세션 ID입니다.
            user_id: 요청한 민원인의 `users.id`입니다.

        Returns:
            세션 요약과 메시지 목록이 담긴 `ChatSessionDetail`입니다.

        Raises:
            AppError: 세션이 없거나 소유자가 다르면 404를 발생합니다.
        """
        with self._lock:
            entry = self._chat_sessions.get(session_id)
            if entry is None or entry[0] != user_id:
                raise AppError(404, "not_found", "대화 세션을 찾을 수 없습니다.")
            _, summary, messages = entry
            return ChatSessionDetail(
                session=summary.model_copy(
                    update={"message_count": len(messages)}, deep=True
                ),
                messages=[msg.model_copy(deep=True) for msg in messages],
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
        """시민 질문과 안전 투영된 도우미 응답을 메모리 세션에 저장합니다.

        Args:
            user_id: 소유 민원인의 `users.id`입니다.
            session_id: 이어 쓸 기존 세션 ID 또는 None입니다.
            user_text: 시민이 입력한 질문 원문입니다.
            user_district: 이번 턴에 적용된 관할 구 또는 None입니다.
            assistant_response: 시민 전용 안전 응답 모델입니다.

        Returns:
            생성 또는 갱신된 세션 ID입니다.

        Raises:
            AppError: 지정한 세션이 없거나 소유자가 다르면 404를 발생합니다.
        """
        user_ts = utcnow()
        assistant_ts = user_ts + timedelta(milliseconds=1)
        resolved_district = (
            assistant_response.district
            if assistant_response.district != "모름"
            else user_district
        )
        with self._lock:
            if session_id:
                entry = self._chat_sessions.get(session_id)
                if entry is None or entry[0] != user_id:
                    raise AppError(404, "not_found", "대화 세션을 찾을 수 없습니다.")
                _, summary, messages = entry
                resolved_sid = session_id
                summary = summary.model_copy(
                    update={
                        "last_district": resolved_district or summary.last_district,
                        "updated_at": assistant_ts,
                    },
                    deep=True,
                )
            else:
                resolved_sid = f"CHAT-{user_ts.year}-{uuid4().hex[:10].upper()}"
                title = " ".join(user_text.split())[:60] or "새 대화"
                summary = ChatSessionSummary(
                    id=resolved_sid,
                    title=title,
                    last_district=resolved_district,
                    message_count=0,
                    created_at=user_ts,
                    updated_at=assistant_ts,
                )
                messages = []
            safe_payload = assistant_response.model_copy(
                update={"session_id": resolved_sid, "persisted": True}, deep=True
            )
            messages.append(
                ChatMessageRecord(
                    id=f"CMSG-{uuid4().hex[:12].upper()}",
                    role="user",
                    content=user_text,
                    district=user_district,
                    created_at=user_ts,
                )
            )
            messages.append(
                ChatMessageRecord(
                    id=f"CMSG-{uuid4().hex[:12].upper()}",
                    role="assistant",
                    content=safe_payload.answer,
                    district=resolved_district,
                    outcome=safe_payload.outcome,
                    reason_code=safe_payload.reason_code,
                    payload=safe_payload,
                    created_at=assistant_ts,
                )
            )
            summary = summary.model_copy(update={"message_count": len(messages)})
            self._chat_sessions[resolved_sid] = (user_id, summary, messages)
        return resolved_sid

    def delete_chat_session(self, session_id: str, user_id: str) -> None:
        """메모리 저장소에서 소유 민원인의 챗봇 세션을 삭제합니다.

        Args:
            session_id: 삭제할 챗봇 세션 ID입니다.
            user_id: 요청한 민원인의 `users.id`입니다.

        Raises:
            AppError: 세션이 없거나 타인 소유이면 404를 발생합니다.
        """
        with self._lock:
            entry = self._chat_sessions.get(session_id)
            if entry is None or entry[0] != user_id:
                raise AppError(404, "not_found", "대화 세션을 찾을 수 없습니다.")
            del self._chat_sessions[session_id]

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
        """메모리 저장소에서 잠금 안에 권한·개수를 검사하고 첨부 메타데이터를 저장합니다.

        Args:
            complaint_id: 대상 민원 식별자입니다.
            item: 저장할 첨부 메타데이터 모델입니다.
            sha256_hex: 정제된 바이트의 SHA-256 해시입니다.
            storage_key: 저장소에 기록된 파일 키입니다.
            max_count: 민원당 최대 허용 첨부 개수입니다.
            action_check: 작성자·상태를 검증하는 콜백입니다.

        Returns:
            `(갱신된 민원 사본, 저장된 첨부 메타데이터 사본)` 튜플입니다.
        """
        with self._lock:
            current = self._rows.get(complaint_id)
            if current is None:
                raise AppError(404, "not_found", "민원을 찾을 수 없습니다.")
            row = current.model_copy(deep=True)
            action_check(row)
            if len(row.attachments) >= max_count:
                raise AppError(
                    409,
                    "attachment_limit_exceeded",
                    f"민원당 첨부파일은 최대 {max_count}개까지 등록할 수 있습니다.",
                )
            stored_item = item.model_copy(deep=True)
            row.attachments.append(stored_item)
            row.history.append(
                History(text=f"시민이 첨부파일 등록: {stored_item.filename}")
            )
            row.version += 1
            self._rows[complaint_id] = row
            self._attachments[(complaint_id, stored_item.id)] = (
                stored_item,
                sha256_hex,
                storage_key,
            )
        return row.model_copy(deep=True), stored_item.model_copy(deep=True)

    def get_attachment_meta(
        self, complaint_id: str, attachment_id: str
    ) -> tuple[AttachmentItem, str]:
        """메모리 저장소에서 첨부 메타데이터와 저장 키를 조회합니다.

        Args:
            complaint_id: 소속 민원 식별자입니다.
            attachment_id: 조회할 첨부 식별자입니다.

        Returns:
            `(첨부 메타데이터 사본, storage_key)` 튜플입니다.
        """
        with self._lock:
            entry = self._attachments.get((complaint_id, attachment_id))
        if entry is None:
            raise AppError(404, "not_found", "첨부파일을 찾을 수 없습니다.")
        return entry[0].model_copy(deep=True), entry[2]

    def list_attachment_keys(self, complaint_id: str) -> list[str]:
        """메모리 저장소에서 특정 민원의 첨부 저장 키 목록을 반환합니다.

        Args:
            complaint_id: 대상 민원 식별자입니다.

        Returns:
            연결된 `storage_key` 문자열 목록입니다.
        """
        with self._lock:
            return [
                storage_key
                for (cid, _aid), (_item, _sha, storage_key) in self._attachments.items()
                if cid == complaint_id
            ]

    def delete_attachment(
        self,
        *,
        complaint_id: str,
        attachment_id: str,
        action_check: Callable[[Complaint], None],
    ) -> tuple[Complaint, str]:
        """메모리 저장소에서 권한을 검증하고 첨부 항목을 제거합니다.

        Args:
            complaint_id: 소속 민원 식별자입니다.
            attachment_id: 삭제할 첨부 식별자입니다.
            action_check: 삭제 권한·상태를 검증하는 콜백입니다.

        Returns:
            `(갱신된 민원 사본, 삭제할 storage_key)` 튜플입니다.
        """
        with self._lock:
            current = self._rows.get(complaint_id)
            if current is None:
                raise AppError(404, "not_found", "민원을 찾을 수 없습니다.")
            entry = self._attachments.get((complaint_id, attachment_id))
            if entry is None:
                raise AppError(404, "not_found", "첨부파일을 찾을 수 없습니다.")
            row = current.model_copy(deep=True)
            action_check(row)
            removed_item, _sha, storage_key = entry
            row.attachments = [
                att for att in row.attachments if att.id != attachment_id
            ]
            row.history.append(
                History(text=f"시민이 첨부파일 삭제: {removed_item.filename}")
            )
            row.version += 1
            self._rows[complaint_id] = row
            del self._attachments[(complaint_id, attachment_id)]
        return row.model_copy(deep=True), storage_key


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
            for statement in _SCHEMA_STATEMENTS:
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
        for name, expression in _VALUE_CHECKS:
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
                ver_origin = _version_origin(ver.kind, row)
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
                        _version_publish_state(ver.kind),
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
            dept_id_raw, dept_name = _extract_primary_dept(row)
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
