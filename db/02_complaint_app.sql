-- =====================================================================
-- 02_complaint_app.sql
-- complaint_app 스키마 (DB01) : 민원 게시판이 쓰는 업무 데이터
--
-- 한눈에 보기
--   - 시연 웹에 보이는 민원, 답변, AI 작업 기록을 저장하는 스키마
--   - 테이블 8개 : users, complaints, ai_jobs, ai_results, job_events, messages, message_versions,
--                  complaint_events (담당자 처리 이력과 감사 기록)
--   - AI 검색 자료(FAQ, 사례, 부서)는 complaint_rag 스키마에 있고, 여기서는 읽기만 한다.
--   - 두 스키마의 연결은 1곳 : ai_results.department_id -> complaint_rag.department_directory.department_id
--
-- 실행 방법
--   - 순서 : 01_complaint_rag.sql 먼저(있는 경우), 그 다음 이 파일
--   - 명령 : psql -d <DB이름> -f 02_complaint_app.sql
--   - 여러 번 실행해도 된다. 맨 위에서 complaint_app 스키마만 지우고 다시 만든다.
--     (complaint_rag 는 건드리지 않는다.)
--   - complaint_rag 가 없는 DB에서도 오류 없이 실행된다. 부서 연결만 건너뛴다.
--
-- 값 기준
--   - 처리 상태(complaints.status), 단계(complaints.stage), 공개 구분(job_events.vis)은
--     프로토타입 HTML 의 데이터 모델(2.1 Case, 2.3 Event)을 따른다.
--
-- 바뀐 점 (2026-11-03)
--   - ai_results.confidence 추가 : AI가 낸 신뢰도(0~1)를 저장한다. 값이 없으면 NULL.
--
-- 바뀐 점 (2026-11-02)
--   - complaints.due_at 추가 : 처리 기한을 화면이 계산하지 않고 DB에 저장한다.
--   - complaint_events 추가 : 담당자가 한 일(배정, 열람, 계획, 조치, 협조 요청, 기한 연장, 반려)과
--     원문 열람 감사 기록을 한 테이블에 쌓는다. job_events 는 AI 작업 기록 전용이라 따로 둔다.
--
-- 읽는 순서 : 테이블 번호 순서와 같다. 서로 가리키는 외래 키는 맨 아래에서 건다.
-- =====================================================================

DROP SCHEMA IF EXISTS complaint_app CASCADE;
CREATE SCHEMA complaint_app;
SET search_path TO complaint_app;

-- ---------------------------------------------------------------------
-- 1. users : 사용자 (시민, 담당자)
--   - 민원 작성자, 담당자, 답변 수정자, 답변 게시자가 모두 이 테이블을 가리킨다.
--   - 비밀번호 칸은 없다. 시연에서는 인증을 넣지 않기로 했다.
-- ---------------------------------------------------------------------
CREATE TABLE users (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,   -- 사용자 번호 (자동 증가)
    login_id     text        NOT NULL UNIQUE,                       -- 아이디 (겹치면 안 됨)
    display_name text        NOT NULL,                              -- 화면에 보이는 이름 (겹쳐도 됨)
    role         text        NOT NULL
                 CHECK (role IN ('citizen', 'staff')),              -- citizen = 시민, staff = 담당자
    created_at   timestamptz NOT NULL DEFAULT now()                 -- 만든 시각
);

-- ---------------------------------------------------------------------
-- 2. complaints : 민원 한 건
--   - 시민이 쓴 민원 글과 처리 상태를 저장한다.
--   - 사용자(users) 1명이 민원을 여러 건 쓴다. (작성자)
--   - 담당자(users)도 여러 건을 맡을 수 있다. (맡은 담당자, 아직 없을 수 있음)
-- ---------------------------------------------------------------------
CREATE TABLE complaints (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,   -- 민원 번호 (내부용, 자동 증가)

    -- 화면에 보이는 민원번호. 프로토타입 형식 YYYY-MMDD-NNNN (예: 2026-1030-0001)
    public_code     text        NOT NULL UNIQUE
                    CHECK (public_code ~ '^[0-9]{4}-[0-9]{4}-[0-9]{4}$'),

    author_id       bigint      NOT NULL REFERENCES users(id),         -- 작성자

    -- 제목 2~120자, 내용 10~2,000자
    title           text        NOT NULL
                    CHECK (char_length(title) BETWEEN 2 AND 120),
    body            text        NOT NULL
                    CHECK (char_length(body) BETWEEN 10 AND 2000),

    category        text,                                              -- 분류. 프로토타입 표기 "대분류 › 중분류". NULL 허용
    district        text,                                              -- 민원이 해당하는 구. 모르면 NULL

    -- 처리 상태 : 프로토타입 status 10가지. 화면에 이 글자 그대로 표시된다.
    --   AI검토, 배정완료, 처리중, 보완요청, 답변완료,
    --   총괄검토, 조정대기, 재배정, 반려, 소관외 종결
    status          text        NOT NULL DEFAULT 'AI검토'
                    CHECK (status IN ('AI검토', '배정완료', '처리중', '보완요청', '답변완료',
                                      '총괄검토', '조정대기', '재배정', '반려', '소관외 종결')),

    -- 단계 : 진행 막대에 쓰는 1~5
    --   1 접수, 2 AI검토, 3 배정, 4 처리중, 5 답변완료
    stage           smallint    NOT NULL DEFAULT 1
                    CHECK (stage BETWEEN 1 AND 5),

    version         integer     NOT NULL DEFAULT 1,                    -- 민원 글을 몇 번 고쳤는지 (동시에 고칠 때 충돌 검사용)
    context_version integer     NOT NULL DEFAULT 1,                    -- AI에게 보낸 글이 몇 번째 수정본인지
    assignee_id     bigint      REFERENCES users(id),                  -- 맡은 담당자. 배정 전이면 NULL

    -- 처리 기한. 화면의 D-day(남은 일수)는 이 값에서 계산한다. 시연은 접수 후 5일로 넣는다.
    -- 기한 연장이 승인되면 이 값을 바꾸고, 바꾼 기록은 complaint_events 에 남긴다. 정해지기 전이면 NULL
    due_at          timestamptz,

    is_synthetic    boolean     NOT NULL DEFAULT false,                -- true = 시연용으로 만든 가짜 민원
    created_at      timestamptz NOT NULL DEFAULT now(),                -- 접수 시각
    updated_at      timestamptz NOT NULL DEFAULT now(),                -- 마지막 변경 시각
    deleted_at      timestamptz                                        -- 철회해서 숨긴 시각. 철회 안 했으면 NULL
);
-- 목록 화면에서 상태별, 작성자별로 최신순 조회가 많아서 만든 색인
CREATE INDEX idx_complaints_status_created ON complaints (status, created_at);
CREATE INDEX idx_complaints_author_created ON complaints (author_id, created_at);

-- ---------------------------------------------------------------------
-- 3. ai_jobs : AI가 일한 기록
--   - 민원 1건에 AI 작업이 여러 번 생길 수 있다. (다시 돌리기, 글이 고쳐져서 재실행)
--   - 작업이 끝나면 결과는 ai_results 에 저장하고, result_id 로 연결한다.
--   - result_id 의 외래 키는 ai_results 를 만든 뒤 맨 아래에서 건다. (서로 가리키기 때문)
-- ---------------------------------------------------------------------
CREATE TABLE ai_jobs (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,   -- 작업 번호
    complaint_id    bigint      NOT NULL REFERENCES complaints(id),    -- 어느 민원의 작업인지
    context_version integer     NOT NULL,                              -- 작업 시작 때 민원 글이 몇 번째 수정본이었는지

    attempt         integer     NOT NULL DEFAULT 1,                    -- 같은 민원, 같은 수정본에서 몇 번째 시도인지

    -- 작업 상태 6가지 (AI 쪽 서버가 바꾼다)
    --   queued 대기, running 진행 중, succeeded 성공,
    --   failed 실패, cancelled 취소, superseded 새 작업으로 대체
    state           text        NOT NULL DEFAULT 'queued'
                    CHECK (state IN ('queued', 'running', 'succeeded', 'failed', 'cancelled', 'superseded')),

    stage           text,                                              -- 지금 어느 단계인지. 값 종류는 AI 쪽 흐름에 맞춰 정하므로 CHECK 없음
    error           text,                                              -- 실패했을 때 이유. 성공이면 NULL
    result_id       bigint,                                            -- 이 작업이 낸 결과 (아래에서 외래 키). 결과 전이면 NULL
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (complaint_id, context_version, attempt)                    -- 같은 시도가 두 번 생기지 않게 막음
);
CREATE INDEX idx_ai_jobs_state ON ai_jobs (state);                     -- 대기 중인 작업을 빨리 찾기 위한 색인
CREATE INDEX idx_ai_jobs_complaint ON ai_jobs (complaint_id);

-- ---------------------------------------------------------------------
-- 4. ai_results : AI가 낸 결과
--   - AI 작업 1번에 결과 1개 (job_id 가 UNIQUE).
--   - 추천 부서, 근거, 답변 초안을 저장한다. 자동 이관은 하지 않는다. (참고용 추천만)
--   - adopted_version_id 의 외래 키는 message_versions 를 만든 뒤 맨 아래에서 건다.
-- ---------------------------------------------------------------------
CREATE TABLE ai_results (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,           -- 결과 번호
    job_id             bigint      NOT NULL UNIQUE REFERENCES ai_jobs(id),        -- 어느 AI 작업의 결과인지
    attempt            integer     NOT NULL DEFAULT 1,                            -- 몇 번째 시도의 결과인지

    -- 결과 종류 3가지
    --   faq_answer 자주 묻는 질문으로 답변, department_suggestion 부서 추천, human_handoff 사람에게 넘김
    outcome            text        NOT NULL
                       CHECK (outcome IN ('faq_answer', 'department_suggestion', 'human_handoff')),

    -- AI 신뢰도 (0 이상 1 이하). AI가 계산해서 주는 값이며 우리는 저장만 한다.
    --   화면의 신뢰도 표시와 자동 배정 기준(기본 0.70, 관리자 설정)에 쓴다. AI가 값을 주지 않으면 NULL
    confidence         numeric(3,2)
                       CHECK (confidence BETWEEN 0 AND 1),

    department_id      text,                                  -- 추천 부서 번호. 참고용. complaint_rag.department_directory 를 가리킴 (맨 아래에서 연결)
    department_name    text,                                  -- 추천할 때의 부서 이름 복사본 (나중에 부서 이름이 바뀌어도 기록 유지)
    evidence           jsonb,                                 -- 답변 근거 목록. 항목마다 corpus, source_id, source_url, content_hash
    draft_body         text,                                  -- 답변 초안
    guide_body         text,                                  -- 자주 묻는 질문 안내 글
    automatic_transfer boolean     NOT NULL DEFAULT false
                       CHECK (automatic_transfer = false),    -- 자동 이관 여부. 항상 false (자동으로 부서에 넘기지 않음)
    adopted_version_id bigint,                                -- 이 결과의 초안으로 만든 답변 글 (아래에서 외래 키)
    model_version      text,                                  -- 사용한 AI 모델 이름
    policy_version     text,                                  -- 답변 규칙을 검사한 기준의 버전
    prompt_version     text,                                  -- AI에게 준 지시문의 버전
    created_at         timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- 5. job_events : AI 작업 중 생긴 일
--   - 담당자 화면의 "AI 작업 진행 상태"에 보이는 기록. 작업 1번에 여러 줄이 순서대로 쌓인다.
--   - 예) 검색 시작, 부서 판단 중, 답변 초안 작성 완료
-- ---------------------------------------------------------------------
CREATE TABLE job_events (
    id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,   -- 번호 (순서대로 커지므로 정렬에도 사용)
    job_id bigint      NOT NULL REFERENCES ai_jobs(id),       -- 어느 AI 작업에서 생긴 일인지
    at     timestamptz NOT NULL DEFAULT now(),                -- 일어난 시각
    text   text        NOT NULL,                              -- 일어난 일의 내용

    -- 공개 구분 (프로토타입 Event 의 vis 와 같은 값)
    --   pub 자동 공개 (시민에게 보임), int 내부 전용 (담당자만), ai AI 산출
    vis    text        NOT NULL DEFAULT 'ai'
           CHECK (vis IN ('pub', 'int', 'ai'))
);
CREATE INDEX idx_job_events_job ON job_events (job_id, id);

-- ---------------------------------------------------------------------
-- 6. messages : 민원에 달린 답변 또는 추가 문의 한 묶음
--   - 글 내용은 여기에 없고, message_versions 에 버전별로 저장한다.
--   - 이 테이블은 "묶음"이고, 지금 시민에게 보이는 글이 어느 버전인지만 가리킨다.
--   - published_version_id 의 외래 키는 message_versions 를 만든 뒤 맨 아래에서 건다.
-- ---------------------------------------------------------------------
CREATE TABLE messages (
    id                   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,   -- 번호
    complaint_id         bigint      NOT NULL REFERENCES complaints(id),    -- 어느 민원에 달린 글인지

    kind                 text        NOT NULL
                         CHECK (kind IN ('answer', 'inquiry')),             -- answer 답변, inquiry 추가 문의
    origin               text        NOT NULL
                         CHECK (origin IN ('ai', 'staff', 'citizen')),      -- 누가 썼는지. ai, staff 담당자, citizen 시민

    published_version_id bigint,                              -- 지금 시민에게 보이는 글(버전). 하나만. 아직 게시 전이면 NULL
    created_at           timestamptz NOT NULL DEFAULT now(),
    deleted_at           timestamptz                          -- 숨긴 시각. 안 숨겼으면 NULL
);
CREATE INDEX idx_messages_complaint ON messages (complaint_id);

-- ---------------------------------------------------------------------
-- 7. message_versions : 답변 글의 버전
--   - 답변을 고칠 때 덮어쓰지 않고 새 버전을 추가한다. (AI 초안, 담당자 수정본이 모두 남음)
--   - "AI 작성 / 담당자 수정 구분", "답변 수정 기록 보기" 화면이 이 테이블을 쓴다.
-- ---------------------------------------------------------------------
CREATE TABLE message_versions (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,    -- 버전 번호
    message_id          bigint      NOT NULL REFERENCES messages(id),       -- 어느 답변 묶음의 버전인지
    version_no          integer     NOT NULL,                               -- 몇 번째 글인지 (1, 2, 3 ...)
    body                text        NOT NULL,                               -- 글 내용

    origin              text        NOT NULL
                        CHECK (origin IN ('ai', 'staff', 'citizen')),       -- 처음 쓴 사람. ai, staff 담당자, citizen 시민

    origin_job_id       bigint      REFERENCES ai_jobs(id),                 -- 이 글을 만든 AI 작업. 사람이 쓴 글이면 NULL
    based_on_version_id bigint      REFERENCES message_versions(id),        -- 이 글의 바탕이 된 이전 글. 첫 글이면 NULL (자기 테이블을 가리킴)
    edited_by           bigint      REFERENCES users(id),                   -- 고친 담당자. 안 고쳤으면 NULL

    -- 글 상태 : draft 초안, published 게시, retracted 철회
    publish_state       text        NOT NULL DEFAULT 'draft'
                        CHECK (publish_state IN ('draft', 'published', 'retracted')),

    published_by        bigint      REFERENCES users(id),                   -- 게시한 담당자. 게시 전이면 NULL
    published_at        timestamptz,                                        -- 게시 시각. 게시 전이면 NULL
    retracted_at        timestamptz,                                        -- 철회 시각. 철회 안 했으면 NULL
    retract_reason      text,                                               -- 철회한 이유 (기록에만 남김)
    evidence_snapshot   jsonb,                                              -- 게시할 때 근거를 복사해 둔 것 (원본 자료가 바뀌어도 기록 유지)
    context_version     integer,                                            -- AI에게 보낸 글이 몇 번째 수정본이었는지
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (message_id, version_no)                                         -- 같은 묶음에서 같은 번호가 두 번 생기지 않게 막음
);
CREATE INDEX idx_message_versions_message ON message_versions (message_id);

-- ---------------------------------------------------------------------
-- 8. complaint_events : 담당자 처리 이력과 감사 기록
--   - 민원 1건에 대해 사람이 한 일을 시간 순서로 쌓는다. 한 번 쌓으면 고치지 않는다.
--   - 담당자 화면의 "처리 이력", 시민 화면의 진행 상황, 원문을 본 기록(감사)이 모두 여기서 나온다.
--   - AI 작업 중 생긴 일은 job_events 에 있고, 이 테이블에는 넣지 않는다.
-- ---------------------------------------------------------------------
CREATE TABLE complaint_events (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,   -- 번호 (순서대로 커지므로 정렬에도 사용)
    complaint_id bigint      NOT NULL REFERENCES complaints(id),    -- 어느 민원에 대한 일인지
    actor_id     bigint      REFERENCES users(id),                  -- 한 사람. 시스템이 한 일이면 NULL

    -- 한 일의 종류 8가지 (프로토타입 처리 이력의 k 값과 같음)
    --   배정, 열람, 계획, 조치, 협조요청, 기한연장, 반려, 원문열람
    --   원문열람은 감사 기록이다. 누가 왜 봤는지(목적)를 body 에 적는다.
    kind         text        NOT NULL
                 CHECK (kind IN ('배정', '열람', '계획', '조치', '협조요청', '기한연장', '반려', '원문열람')),

    body         text        NOT NULL,                              -- 일어난 일의 내용 (협조 요청은 받는 부서와 요청 내용을 여기에 적음)

    -- 공개 구분 (job_events 와 같은 방식). pub 시민에게 보임, int 내부 전용
    vis          text        NOT NULL DEFAULT 'int'
                 CHECK (vis IN ('pub', 'int')),

    at           timestamptz NOT NULL DEFAULT now()                 -- 일어난 시각
);
CREATE INDEX idx_complaint_events_complaint ON complaint_events (complaint_id, id);   -- 민원별로 순서대로 읽는 색인

-- ---------------------------------------------------------------------
-- 서로 가리키는 외래 키는 테이블을 다 만든 뒤에 건다.
--   - ai_jobs.result_id 와 ai_results.job_id 가 서로를 가리킨다.
--   - ai_results.adopted_version_id, messages.published_version_id 는 message_versions 를 가리킨다.
--   - 가리키는 테이블이 아직 없을 때는 외래 키를 만들 수 없어서 순서를 나눴다.
-- ---------------------------------------------------------------------
ALTER TABLE ai_jobs
    ADD CONSTRAINT fk_ai_jobs_result
    FOREIGN KEY (result_id) REFERENCES ai_results(id);

ALTER TABLE ai_results
    ADD CONSTRAINT fk_ai_results_adopted_version
    FOREIGN KEY (adopted_version_id) REFERENCES message_versions(id);

ALTER TABLE messages
    ADD CONSTRAINT fk_messages_published_version
    FOREIGN KEY (published_version_id) REFERENCES message_versions(id);

-- ---------------------------------------------------------------------
-- complaint_rag 와의 연결 (이 파일에서 유일한 연결)
--   - ai_results.department_id 가 complaint_rag.department_directory.department_id 를 가리킨다.
--   - complaint_rag.department_directory 가 있을 때만 외래 키를 건다.
--   - 없는 DB에서는 안내 메시지만 출력하고 건너뛴다. (오류 없음, 나머지 테이블은 정상 생성)
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF to_regclass('complaint_rag.department_directory') IS NOT NULL THEN
        ALTER TABLE complaint_app.ai_results
            ADD CONSTRAINT fk_ai_results_department
            FOREIGN KEY (department_id)
            REFERENCES complaint_rag.department_directory (department_id);
    ELSE
        RAISE NOTICE 'complaint_rag.department_directory 가 없어 부서 외래 키를 건너뜀';
    END IF;
END $$;
