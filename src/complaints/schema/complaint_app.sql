-- =====================================================================
-- complaint_app.sql
-- 민원 업무 스키마 (7테이블 정규화 + 보조 3테이블). Flask `src.complaints`가 사용한다.
--
-- 핵심 정규화 7테이블:
--   1. users            : 민원인·담당자 로그인 계정(아이디·scrypt 비밀번호·담당 부서)
--   2. complaints       : 민원 원문·상태·버전·작성자/담당자 FK (하위 호환 payload jsonb + 생성 칼럼 유지)
--   3. messages         : 민원별 답변 스레드 및 시민 추가 문의
--   4. message_versions : 답변 초안·게시·철회·원문 수정 버전 이력
--   5. ai_jobs          : 민원별 AI 실행 작업(시도·맥락 버전·상태·공급자)
--   6. ai_results       : AI 판정·근거·부서 추천 결과(automatic_transfer=false CHECK 강제)
--   7. job_events       : AI 작업 단계별 진행 로그(pub/int/ai 가시성 구분)
--
-- 보조 3테이블:
--   - idempotency       : 중복 등록 방지 Idempotency-Key
--   - answer_templates  : 담당자 답변 편집기 템플릿
--   - app_meta          : 최초 1회 시드/마이그레이션 플래그
--
-- 경계:
--   - 검색 색인 `complaint_rag`와 민원 본문을 섞지 않는다.
--   - 유일한 스키마 간 연결은 선택적 FK `ai_results.department_id -> complaint_rag.department_directory(department_id)`다.
--   - IF NOT EXISTS / ADD COLUMN IF NOT EXISTS로 반복 실행해도 기존 행을 지우지 않는다.
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS complaint_app;

-- 1. users : 민원인·담당자 아이디/비밀번호 계정
CREATE TABLE IF NOT EXISTS complaint_app.users (
    id            text        PRIMARY KEY,
    login_id      text        NOT NULL UNIQUE,
    display_name  text        NOT NULL,
    role          text        NOT NULL CHECK (role IN ('citizen', 'staff')),
    password_hash text        NOT NULL,
    department    text,
    is_demo       boolean     NOT NULL DEFAULT false,
    active        boolean     NOT NULL DEFAULT true,
    created_at    timestamptz NOT NULL DEFAULT now(),
    last_login_at timestamptz
);

ALTER TABLE complaint_app.users
    DROP COLUMN IF EXISTS verified,
    DROP COLUMN IF EXISTS phone_last4;

CREATE INDEX IF NOT EXISTS idx_app_users_role_dept
    ON complaint_app.users (role, department);

-- 2. complaints : 민원 본문·상태·낙관적 잠금·작성자/담당자 FK
CREATE TABLE IF NOT EXISTS complaint_app.complaints (
    id          text        PRIMARY KEY,
    version     integer     NOT NULL CHECK (version > 0),
    created_at  timestamptz NOT NULL,
    payload     jsonb       NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_app_complaints_created
    ON complaint_app.complaints (created_at DESC, id DESC);

ALTER TABLE complaint_app.complaints
    ADD COLUMN IF NOT EXISTS version integer;

UPDATE complaint_app.complaints
SET version = CASE
    WHEN COALESCE(payload->>'version', '') ~ '^[1-9][0-9]*$'
    THEN (payload->>'version')::integer
    ELSE 1
END
WHERE version IS NULL;

ALTER TABLE complaint_app.complaints
    ALTER COLUMN version SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'complaint_app.complaints'::regclass
          AND contype = 'c'
          AND position('version > 0' in pg_get_constraintdef(oid)) > 0
    ) THEN
        ALTER TABLE complaint_app.complaints
            ADD CONSTRAINT complaints_version_positive CHECK (version > 0);
    END IF;
END $$;

-- 목록·필터용 생성 칼럼(하위 호환 유지) + 정규화 관계형 칼럼
ALTER TABLE complaint_app.complaints
    ADD COLUMN IF NOT EXISTS status text
        GENERATED ALWAYS AS (payload->>'status') STORED,
    ADD COLUMN IF NOT EXISTS owner text
        GENERATED ALWAYS AS (payload->>'owner') STORED,
    ADD COLUMN IF NOT EXISTS visibility text
        GENERATED ALWAYS AS (payload->>'visibility') STORED,
    ADD COLUMN IF NOT EXISTS district text
        GENERATED ALWAYS AS (payload->>'district') STORED,
    ADD COLUMN IF NOT EXISTS is_synthetic boolean
        GENERATED ALWAYS AS (COALESCE((payload->>'isSynthetic')::boolean, false)) STORED,
    ADD COLUMN IF NOT EXISTS owner_user_id text
        REFERENCES complaint_app.users(id),
    ADD COLUMN IF NOT EXISTS assignee_user_id text
        REFERENCES complaint_app.users(id),
    ADD COLUMN IF NOT EXISTS title text,
    ADD COLUMN IF NOT EXISTS body text,
    ADD COLUMN IF NOT EXISTS category text,
    ADD COLUMN IF NOT EXISTS department text,
    ADD COLUMN IF NOT EXISTS context_version integer NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS complaints_status_created
    ON complaint_app.complaints (status, created_at);
CREATE INDEX IF NOT EXISTS complaints_owner_created
    ON complaint_app.complaints (owner, created_at);
CREATE INDEX IF NOT EXISTS idx_app_complaints_department
    ON complaint_app.complaints (department, created_at DESC);

UPDATE complaint_app.complaints
SET payload = payload || jsonb_build_object('isSynthetic', true)
WHERE left(id, 9) = 'DEMO-PUB-' AND NOT (payload ? 'isSynthetic');

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conrelid = 'complaint_app.complaints'::regclass
                     AND conname = 'complaints_status_valid') THEN
        ALTER TABLE complaint_app.complaints
            ADD CONSTRAINT complaints_status_valid
            CHECK (status IN ('submitted', 'under_review', 'answered', 'closed', 'withdrawn'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conrelid = 'complaint_app.complaints'::regclass
                     AND conname = 'complaints_visibility_valid') THEN
        ALTER TABLE complaint_app.complaints
            ADD CONSTRAINT complaints_visibility_valid
            CHECK (visibility IN ('private', 'public'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conrelid = 'complaint_app.complaints'::regclass
                     AND conname = 'complaints_district_valid') THEN
        ALTER TABLE complaint_app.complaints
            ADD CONSTRAINT complaints_district_valid
            CHECK (district IN ('상당구', '서원구', '흥덕구', '청원구', '모름'));
    END IF;
END $$;

-- 3. messages : 민원별 답변 스레드 및 시민 추가 문의
CREATE TABLE IF NOT EXISTS complaint_app.messages (
    id                   text        PRIMARY KEY,
    complaint_id         text        NOT NULL REFERENCES complaint_app.complaints(id) ON DELETE CASCADE,
    kind                 text        NOT NULL CHECK (kind IN ('answer', 'inquiry')),
    origin               text        NOT NULL CHECK (origin IN ('ai', 'ai_edited', 'staff', 'citizen')),
    author_user_id       text        REFERENCES complaint_app.users(id),
    body                 text        NOT NULL DEFAULT '',
    published_version_id text,
    created_at           timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_app_messages_complaint
    ON complaint_app.messages (complaint_id, created_at);

-- 4. message_versions : 답변 초안·게시·철회·원문 수정 버전 이력
CREATE TABLE IF NOT EXISTS complaint_app.message_versions (
    id              text        PRIMARY KEY,
    message_id      text        NOT NULL REFERENCES complaint_app.messages(id) ON DELETE CASCADE,
    complaint_id    text        NOT NULL REFERENCES complaint_app.complaints(id) ON DELETE CASCADE,
    version_no      integer     NOT NULL,
    body            text        NOT NULL,
    origin          text        NOT NULL CHECK (origin IN ('ai', 'ai_edited', 'staff', 'citizen')),
    kind            text        NOT NULL,
    publish_state   text        NOT NULL CHECK (publish_state IN ('draft', 'published', 'retracted', 'archived')),
    reason          text        NOT NULL DEFAULT '',
    actor_user_id   text        REFERENCES complaint_app.users(id),
    context_version integer     NOT NULL DEFAULT 1,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (message_id, version_no)
);

CREATE INDEX IF NOT EXISTS idx_app_message_versions_complaint
    ON complaint_app.message_versions (complaint_id, version_no);

-- 5. ai_jobs : 민원별 AI 분석 실행 작업
CREATE TABLE IF NOT EXISTS complaint_app.ai_jobs (
    id              text        PRIMARY KEY,
    complaint_id    text        NOT NULL REFERENCES complaint_app.complaints(id) ON DELETE CASCADE,
    context_version integer     NOT NULL,
    attempt         integer     NOT NULL,
    state           text        NOT NULL CHECK (state IN ('queued', 'running', 'succeeded', 'failed', 'cancelled', 'superseded')),
    stage           text        NOT NULL DEFAULT '',
    provider        text,
    started_at      timestamptz,
    updated_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (complaint_id, context_version, attempt)
);

CREATE INDEX IF NOT EXISTS idx_app_ai_jobs_state
    ON complaint_app.ai_jobs (state, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_app_ai_jobs_complaint
    ON complaint_app.ai_jobs (complaint_id);

-- 6. ai_results : AI 판정·근거·부서 추천 결과(자동 이관 금지 강제)
CREATE TABLE IF NOT EXISTS complaint_app.ai_results (
    id                 text        PRIMARY KEY,
    job_id             text        NOT NULL UNIQUE REFERENCES complaint_app.ai_jobs(id) ON DELETE CASCADE,
    complaint_id       text        NOT NULL REFERENCES complaint_app.complaints(id) ON DELETE CASCADE,
    outcome            text        NOT NULL CHECK (outcome IN ('faq_answer', 'department_suggestion', 'human_handoff')),
    reason_code        text        NOT NULL DEFAULT '',
    department_id      text,
    department_name    text,
    evidence           jsonb       NOT NULL DEFAULT '[]'::jsonb,
    draft_body         text,
    guide_body         text,
    automatic_transfer boolean     NOT NULL DEFAULT false CHECK (automatic_transfer = false),
    llm_provider       text,
    llm_model          text,
    created_at         timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_app_ai_results_outcome
    ON complaint_app.ai_results (outcome, created_at DESC);

DO $$
BEGIN
    IF to_regclass('complaint_rag.department_directory') IS NOT NULL
       AND NOT EXISTS (
           SELECT 1 FROM pg_constraint
           WHERE conrelid = 'complaint_app.ai_results'::regclass
             AND conname = 'fk_ai_results_department'
       ) THEN
        ALTER TABLE complaint_app.ai_results
            ADD CONSTRAINT fk_ai_results_department
            FOREIGN KEY (department_id)
            REFERENCES complaint_rag.department_directory (department_id);
    END IF;
END $$;

-- 7. job_events : AI 작업 단계별 진행 로그
CREATE TABLE IF NOT EXISTS complaint_app.job_events (
    id           bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_id       text        NOT NULL REFERENCES complaint_app.ai_jobs(id) ON DELETE CASCADE,
    complaint_id text        NOT NULL REFERENCES complaint_app.complaints(id) ON DELETE CASCADE,
    seq_no       integer     NOT NULL,
    occurred_at  timestamptz NOT NULL DEFAULT now(),
    stage        text        NOT NULL,
    vis          text        NOT NULL DEFAULT 'ai' CHECK (vis IN ('pub', 'int', 'ai')),
    UNIQUE (job_id, seq_no)
);

CREATE INDEX IF NOT EXISTS idx_app_job_events_job
    ON complaint_app.job_events (job_id, seq_no);

-- 보조 5테이블: idempotency, answer_templates, app_meta, chat_sessions, chat_messages
CREATE TABLE IF NOT EXISTS complaint_app.idempotency (
    owner         text NOT NULL,
    key           text NOT NULL,
    fingerprint   text NOT NULL,
    complaint_id  text NOT NULL
                  REFERENCES complaint_app.complaints(id) ON DELETE CASCADE,
    PRIMARY KEY (owner, key)
);

CREATE TABLE IF NOT EXISTS complaint_app.answer_templates (
    id          text        PRIMARY KEY,
    title       text        NOT NULL,
    content     text        NOT NULL,
    is_default  boolean     NOT NULL DEFAULT false,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS complaint_app.app_meta (
    key         text        PRIMARY KEY,
    value       text        NOT NULL
);

-- 시민 AI 챗봇 다중 턴 영구 대화(로그인 민원인 전용, 미제출 개인 대화는 타 사용자·담당자 비공개)
CREATE TABLE IF NOT EXISTS complaint_app.chat_sessions (
    id            text        PRIMARY KEY,
    user_id       text        NOT NULL REFERENCES complaint_app.users(id) ON DELETE CASCADE,
    title         text        NOT NULL,
    last_district text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_app_chat_sessions_user
    ON complaint_app.chat_sessions (user_id, updated_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS complaint_app.chat_messages (
    id          text        PRIMARY KEY,
    session_id  text        NOT NULL REFERENCES complaint_app.chat_sessions(id) ON DELETE CASCADE,
    role        text        NOT NULL CHECK (role IN ('user', 'assistant')),
    content     text        NOT NULL,
    district    text,
    outcome     text        CHECK (outcome IS NULL OR outcome IN ('faq_answer', 'department_suggestion', 'human_handoff')),
    reason_code text,
    payload     jsonb,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_app_chat_messages_session
    ON complaint_app.chat_messages (session_id, created_at ASC, id ASC);
