-- =====================================================================
-- 01_complaint_rag.sql
-- complaint_rag 스키마 : AI가 답을 찾을 때 검색하는 자료
--
-- 한눈에 보기
--   - JSON 파일 기준으로 FAQ 94건, 과거 민원 사례 5,015건, 부서 127개를 저장할 구조다.
--   - 이 파일은 구조(테이블)만 만들고, 자료 적재는 따로 한다. (아직 하지 않음)
--   - FAQ와 사례에는 비슷한 글을 찾기 위한 벡터가 함께 저장된다.
--     1024차원은 임베딩 모델에 맞춘 값이며, 모델이 바뀌면 바꿔야 한다.
--   - 테이블 7개
--       index_metadata      색인 정보
--       department_directory 부서 목록
--       faq_knowledge        FAQ 안내 자료
--       routing_cases        과거 민원 사례와 처리 부서
--       term_postings        키워드 검색용 : 문서별 단어 등장 횟수
--       term_statistics      키워드 검색용 : 단어별 등장 문서 수
--       corpus_statistics    키워드 검색용 : 자료 묶음별 문서 수와 평균 길이
--
-- 실행 방법
--   - psql -d <DB이름> -f 01_complaint_rag.sql
--   - pgvector 확장이 필요하다. (맨 위 CREATE EXTENSION)
--   - IF NOT EXISTS 가 붙어 있어서 여러 번 실행해도 이미 있는 것은 건드리지 않는다.
--   - 02_complaint_app.sql 보다 먼저 실행한다.
--
-- 이 파일의 주석에 대해
--   - SQL 코드는 원본과 같고, 설명 주석만 추가했다.
--   - 컬럼 이름을 바탕으로 정리한 설명이다.
--     "(이름 기준 설명)" 표시가 있는 곳은 원본 담당자에게 확인이 필요하다.
--
-- 이 스키마와 complaint_app 의 연결
--   - complaint_app.ai_results.department_id -> department_directory.department_id (1곳)
-- =====================================================================

-- 벡터(숫자 목록) 저장과 검색 기능. vector(1024) 자료형과 hnsw 색인에 필요하다.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS complaint_rag;

-- ---------------------------------------------------------------------
-- 1. index_metadata : 색인 정보
--   - 키와 값 형태로 색인 관련 설정이나 상태를 저장한다. (이름 기준 설명)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS complaint_rag.index_metadata (
    key text PRIMARY KEY,                                  -- 항목 이름 (겹치지 않음)
    value jsonb NOT NULL                                   -- 항목 내용 (JSON)
);

-- ---------------------------------------------------------------------
-- 2. department_directory : 부서 목록
--   - 부서의 현재 이름, 별칭, 담당 지역, 확인 상태를 저장한다.
--   - routing_cases 와 complaint_app.ai_results 가 이 테이블의 부서 번호를 가리킨다.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS complaint_rag.department_directory (
    department_id text PRIMARY KEY,                        -- 부서 번호
    canonical_name text UNIQUE NOT NULL,                   -- 현재 공식 부서 이름 (겹치지 않음)
    aliases text[] NOT NULL,                               -- 다르게 부르는 이름들
    district text,                                         -- 해당 구. 없으면 NULL
    jurisdiction jsonb NOT NULL,                           -- 담당 지역 정보 (JSON)
    jurisdiction_status text NOT NULL,                     -- 담당 지역을 확인했는지 나타내는 상태 (값 제한 없음)
    duty_description text,                                 -- 업무 설명. 없으면 NULL
    -- 업무 확인 상태 : unverified 미확인, verified 확인됨
    duty_status text NOT NULL CHECK (duty_status IN ('unverified', 'verified')),
    duty_source_urls text[] NOT NULL DEFAULT '{}',         -- 업무 설명의 근거 웹 주소들 (기본값 빈 목록)
    name_checked_on date NOT NULL,                         -- 부서 이름을 확인한 날짜
    name_source_urls text[] NOT NULL,                      -- 부서 이름의 근거 웹 주소들
    observed_case_titles text[] NOT NULL,                  -- 이 부서가 처리한 것으로 확인된 사례 제목들
    automatic_routing_ready boolean NOT NULL DEFAULT false, -- 자동 추천해도 되는 상태인지 (기본값 false)
    updated_at timestamptz NOT NULL DEFAULT now()          -- 갱신 시각
);

-- ---------------------------------------------------------------------
-- 3. faq_knowledge : FAQ 안내 자료 (94건)
--   - 청주톡톡의 자주 묻는 질문 원문과, 검색용 벡터를 저장한다.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS complaint_rag.faq_knowledge (
    source_id text PRIMARY KEY,                            -- 원문 글 번호 (출처 사이트의 번호)
    title text NOT NULL,                                   -- 제목 (업무 이름)
    category text NOT NULL,                                -- 분류
    search_text text NOT NULL,                             -- 검색에 쓰는 본문 (업무명, 분류, 안내 내용 등을 합친 글)
    payload jsonb NOT NULL,                                -- 원문 전체 (JSON)
    source_url text NOT NULL,                              -- 출처 웹 주소
    source_retrieved_at timestamptz NOT NULL,              -- 원문을 가져온 시각
    content_hash text NOT NULL,                            -- 본문 내용의 해시값 (이름 기준 설명: 내용이 바뀌었는지 확인용)
    embedding_hash text NOT NULL,                          -- 벡터를 만든 입력의 해시값 (이름 기준 설명: 벡터를 다시 만들어야 하는지 확인용)
    embedding vector(1024) NOT NULL,                       -- 검색용 벡터 (1024차원). 비슷한 글 찾기에 사용
    token_count integer NOT NULL CHECK (token_count > 0),  -- 검색 본문의 토큰(단어 조각) 수. 0보다 커야 함
    updated_at timestamptz NOT NULL DEFAULT now()          -- 갱신 시각
);

-- ---------------------------------------------------------------------
-- 4. routing_cases : 과거 민원 사례와 처리 부서 (5,015건)
--   - 과거 민원의 제목, 요지, 처리한 부서를 저장한다. 비슷한 사례로 부서를 추천할 때 쓴다.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS complaint_rag.routing_cases (
    source_id text PRIMARY KEY,                            -- 원문 글 번호 (출처 사이트의 번호)
    title text NOT NULL,                                   -- 민원 제목
    search_text text NOT NULL,                             -- 검색에 쓰는 본문 (제목과 민원 요지)
    payload jsonb NOT NULL,                                -- 원문 전체 (JSON)
    source_url text NOT NULL,                              -- 출처 웹 주소
    source_retrieved_at timestamptz NOT NULL,              -- 원문을 가져온 시각
    complaint_date date,                                   -- 민원 날짜. 없으면 NULL
    department_id text REFERENCES complaint_rag.department_directory(department_id),  -- 처리한 부서. 연결 못 했으면 NULL
    department_status text NOT NULL,                       -- 부서 연결 상태. 'review_required' 는 검토 필요 (값 제한 없음)
    district text,                                         -- 해당 구. 없으면 NULL
    routing_eligible boolean NOT NULL,                     -- 부서 추천에 사용해도 되는 사례인지
    summary_missing boolean NOT NULL,                      -- 민원 요지가 비어 있는지
    content_hash text NOT NULL,                            -- 본문 내용의 해시값 (이름 기준 설명: 내용이 바뀌었는지 확인용)
    embedding_hash text NOT NULL,                          -- 벡터를 만든 입력의 해시값 (이름 기준 설명: 벡터를 다시 만들어야 하는지 확인용)
    embedding vector(1024) NOT NULL,                       -- 검색용 벡터 (1024차원)
    token_count integer NOT NULL CHECK (token_count > 0),  -- 검색 본문의 토큰 수. 0보다 커야 함
    updated_at timestamptz NOT NULL DEFAULT now(),         -- 갱신 시각
    -- 부서 추천에 쓸 수 있는 사례 = 부서가 연결되어 있고, 상태가 review_required 가 아닌 사례
    CHECK (routing_eligible = (department_id IS NOT NULL AND department_status <> 'review_required'))
);

-- 벡터로 비슷한 글을 빨리 찾기 위한 색인 (hnsw, 코사인 거리 기준)
CREATE INDEX IF NOT EXISTS faq_embedding_hnsw
    ON complaint_rag.faq_knowledge USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS routing_embedding_hnsw
    ON complaint_rag.routing_cases USING hnsw (embedding vector_cosine_ops);
-- 부서별, 구별 사례 조회용 색인
CREATE INDEX IF NOT EXISTS routing_department ON complaint_rag.routing_cases(department_id);
CREATE INDEX IF NOT EXISTS routing_district ON complaint_rag.routing_cases(district);

-- ---------------------------------------------------------------------
-- 5~7. 키워드 검색(BM25)용 통계 테이블 3개
--   - 벡터 검색과 별도로, 단어 일치 검색에 쓰는 자료다.
--   - corpus 는 자료 묶음 이름 : faq 는 FAQ, routing 은 과거 사례
-- ---------------------------------------------------------------------

-- 5. term_postings : 문서별 단어 등장 횟수
-- 한 행은 문서 하나에서 단어 하나의 빈도. BM25는 PostgreSQL 안에서 계산합니다.
CREATE TABLE IF NOT EXISTS complaint_rag.term_postings (
    corpus text NOT NULL CHECK (corpus IN ('faq', 'routing')),  -- 자료 묶음 (faq 또는 routing)
    term text NOT NULL,                                    -- 단어
    source_id text NOT NULL,                               -- 단어가 나온 문서 번호
    tf integer NOT NULL CHECK (tf > 0),                    -- 그 문서에서 단어가 나온 횟수. 0보다 커야 함
    PRIMARY KEY (corpus, term, source_id)                  -- 같은 문서의 같은 단어는 한 줄만
);

-- 6. term_statistics : 단어별 등장 문서 수
CREATE TABLE IF NOT EXISTS complaint_rag.term_statistics (
    corpus text NOT NULL,                                  -- 자료 묶음
    term text NOT NULL,                                    -- 단어
    document_frequency integer NOT NULL CHECK (document_frequency > 0),  -- 이 단어가 나온 문서 수. 0보다 커야 함
    PRIMARY KEY (corpus, term)
);

-- 7. corpus_statistics : 자료 묶음별 문서 수와 평균 길이
CREATE TABLE IF NOT EXISTS complaint_rag.corpus_statistics (
    corpus text PRIMARY KEY,                               -- 자료 묶음
    document_count integer NOT NULL CHECK (document_count > 0),         -- 문서 수. 0보다 커야 함
    average_length double precision NOT NULL CHECK (average_length > 0) -- 문서 평균 길이. 0보다 커야 함
);
