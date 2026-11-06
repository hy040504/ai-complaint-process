-- =====================================================================
-- complaint_app.sql
-- 시연 웹 민원 업무 스키마. Flask `src.complaints`가 이 스키마를 쓴다.
--
-- 한눈에 보기
--   - 민원 한 건의 상태·답변·시연 작업을 JSON으로 저장한다.
--   - 테이블 2개 : complaints, idempotency
--   - AI 검색 자료(FAQ, 사례, 부서)는 complaint_rag 에 두고 여기서 쓰지 않는다.
--   - 2026-10-30 설계의 7개 정규화 테이블 초안은 미채택이다
--     (plan/db 설계 1차/2026-10-30/02_complaint_app_초안_미채택.sql).
--     현재 구조와 기준은 docs/harness/업무DB_실행설계.md(2026-11-06 기준)를 따른다.
--   - Flask 계약은 Pydantic 민원 문서를 통째로 보존하므로 jsonb payload 를 쓴다.
--     목록·필터용 칼럼은 payload에서 자동 계산하는 생성 칼럼이다.
--
-- 실행 방법
--   - 검색 스키마가 있으면 먼저 rag/origin/schema/complaint_rag.sql
--   - 명령 : psql -d <DB이름> -f src/complaints/schema/complaint_app.sql
--   - IF NOT EXISTS 와 ADD COLUMN IF NOT EXISTS 라서 여러 번 실행해도 기존 행을 지우지 않는다.
--   - version 컬럼이 없는 예전 테이블은 payload 의 version, 없으면 1로 채운다.
--   - 서버도 시작 시 같은 DDL을 적용한다.
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS complaint_app;

CREATE TABLE IF NOT EXISTS complaint_app.complaints (
    id          text        PRIMARY KEY,                 -- 서버가 발급한 민원 식별자
    version     integer     NOT NULL CHECK (version > 0), -- 동시 수정 검사용
    created_at  timestamptz NOT NULL,                    -- 등록 시각
    payload     jsonb       NOT NULL                     -- Complaint Pydantic JSON
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

-- 목록·필터용 생성 칼럼. 원본은 payload 하나이며, 값은 payload에서 자동 계산된다.
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
        GENERATED ALWAYS AS (COALESCE((payload->>'isSynthetic')::boolean, false)) STORED;

CREATE INDEX IF NOT EXISTS complaints_status_created
    ON complaint_app.complaints (status, created_at);
CREATE INDEX IF NOT EXISTS complaints_owner_created
    ON complaint_app.complaints (owner, created_at);

-- 예전 시연 데이터에는 isSynthetic 키가 없으므로 공개 시연 ID(DEMO-PUB-)만 한 번 채운다.
UPDATE complaint_app.complaints
SET payload = payload || jsonb_build_object('isSynthetic', true)
WHERE left(id, 9) = 'DEMO-PUB-' AND NOT (payload ? 'isSynthetic');

-- 상태·공개 범위·지역을 DB도 검사한다. 값 목록은 src/complaints/models.py와 맞춘다.
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

CREATE TABLE IF NOT EXISTS complaint_app.idempotency (
    owner         text NOT NULL,                         -- 작성자 시연 계정
    key           text NOT NULL,                         -- Idempotency-Key
    fingerprint   text NOT NULL,                         -- 등록 본문 해시
    complaint_id  text NOT NULL
                  REFERENCES complaint_app.complaints(id),
    PRIMARY KEY (owner, key)
);
