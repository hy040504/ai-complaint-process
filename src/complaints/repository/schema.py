"""업무 저장소가 공유하는 스키마 DDL·값 검사·기본 템플릿 상수와 정규화 보조 함수입니다.

`complaint_app` 스키마 생성 문장(`SCHEMA_STATEMENTS`), CHECK 식(`VALUE_CHECKS`),
정규화 테이블 이름, 최초 시드 답변 템플릿을 한곳에 둡니다.
"""

from __future__ import annotations

from typing import Literal

from src.complaints.models import Complaint


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
SCHEMA_STATEMENTS = (
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
VALUE_CHECKS: tuple[tuple[str, str], ...] = (
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


def version_publish_state(kind: str) -> str:
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


def version_origin(kind: str, row: Complaint) -> str:
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


def extract_primary_dept(row: Complaint) -> tuple[str | None, str | None]:
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
