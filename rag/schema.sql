CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS complaint_rag;

CREATE TABLE IF NOT EXISTS complaint_rag.index_metadata (
    key text PRIMARY KEY,
    value jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS complaint_rag.department_directory (
    department_id text PRIMARY KEY,
    canonical_name text UNIQUE NOT NULL,
    aliases text[] NOT NULL,
    district text,
    jurisdiction jsonb NOT NULL,
    jurisdiction_status text NOT NULL,
    duty_description text,
    duty_status text NOT NULL CHECK (duty_status IN ('unverified', 'verified')),
    duty_source_urls text[] NOT NULL DEFAULT '{}',
    name_checked_on date NOT NULL,
    name_source_urls text[] NOT NULL,
    observed_case_titles text[] NOT NULL,
    automatic_routing_ready boolean NOT NULL DEFAULT false,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS complaint_rag.faq_knowledge (
    source_id text PRIMARY KEY,
    title text NOT NULL,
    category text NOT NULL,
    search_text text NOT NULL,
    payload jsonb NOT NULL,
    source_url text NOT NULL,
    source_retrieved_at timestamptz NOT NULL,
    content_hash text NOT NULL,
    embedding_hash text NOT NULL,
    embedding vector(1024) NOT NULL,
    token_count integer NOT NULL CHECK (token_count > 0),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS complaint_rag.routing_cases (
    source_id text PRIMARY KEY,
    title text NOT NULL,
    search_text text NOT NULL,
    payload jsonb NOT NULL,
    source_url text NOT NULL,
    source_retrieved_at timestamptz NOT NULL,
    complaint_date date,
    department_id text REFERENCES complaint_rag.department_directory(department_id),
    department_status text NOT NULL,
    district text,
    routing_eligible boolean NOT NULL,
    summary_missing boolean NOT NULL,
    content_hash text NOT NULL,
    embedding_hash text NOT NULL,
    embedding vector(1024) NOT NULL,
    token_count integer NOT NULL CHECK (token_count > 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (routing_eligible = (department_id IS NOT NULL AND department_status <> 'review_required'))
);

CREATE INDEX IF NOT EXISTS faq_embedding_hnsw
    ON complaint_rag.faq_knowledge USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS routing_embedding_hnsw
    ON complaint_rag.routing_cases USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS routing_department ON complaint_rag.routing_cases(department_id);
CREATE INDEX IF NOT EXISTS routing_district ON complaint_rag.routing_cases(district);

-- 한 행은 문서 하나에서 단어 하나의 빈도. BM25는 PostgreSQL 안에서 계산합니다.
CREATE TABLE IF NOT EXISTS complaint_rag.term_postings (
    corpus text NOT NULL CHECK (corpus IN ('faq', 'routing')),
    term text NOT NULL,
    source_id text NOT NULL,
    tf integer NOT NULL CHECK (tf > 0),
    PRIMARY KEY (corpus, term, source_id)
);
CREATE TABLE IF NOT EXISTS complaint_rag.term_statistics (
    corpus text NOT NULL,
    term text NOT NULL,
    document_frequency integer NOT NULL CHECK (document_frequency > 0),
    PRIMARY KEY (corpus, term)
);
CREATE TABLE IF NOT EXISTS complaint_rag.corpus_statistics (
    corpus text PRIMARY KEY,
    document_count integer NOT NULL CHECK (document_count > 0),
    average_length double precision NOT NULL CHECK (average_length > 0)
);
