-- =====================================================================
-- complaint_app.sql
-- 시연 웹 민원 업무 스키마. Flask `src.complaints`가 이 스키마를 쓴다.
--
-- 한눈에 보기
--   - 민원 한 건의 상태·답변·시연 작업을 JSON으로 저장한다.
--   - 테이블 2개 : complaints, idempotency
--   - AI 검색 자료(FAQ, 사례, 부서)는 complaint_rag 에 두고 여기서 쓰지 않는다.
--   - 7개 정규화 테이블 초안은 plan/db 설계 1차/2026-10-30/02_complaint_app.sql 이다.
--     현재 Flask 계약은 Pydantic 민원 문서를 통째로 보존하므로 jsonb payload 를 쓴다.
--
-- 실행 방법
--   - 검색 스키마가 있으면 먼저 db/schema/complaint_rag.sql
--   - 명령 : psql -d <DB이름> -f db/schema/complaint_app.sql
--   - IF NOT EXISTS 이므로 여러 번 실행해도 기존 행을 지우지 않는다.
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

CREATE TABLE IF NOT EXISTS complaint_app.idempotency (
    owner         text NOT NULL,                         -- 작성자 시연 계정
    key           text NOT NULL,                         -- Idempotency-Key
    fingerprint   text NOT NULL,                         -- 등록 본문 해시
    complaint_id  text NOT NULL
                  REFERENCES complaint_app.complaints(id),
    PRIMARY KEY (owner, key)
);
