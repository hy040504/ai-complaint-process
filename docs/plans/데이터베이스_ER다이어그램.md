# 데이터베이스 ER 다이어그램

[계획·설계 문서](README.md) · [데이터 계약](../harness/data-contracts.md) · [업무 DB 실행 설계](../harness/업무DB_실행설계.md) · [시스템 구조](../harness/architecture.md) · [PDF 버전](데이터베이스_ER다이어그램.pdf)

이 문서는 프로젝트의 PostgreSQL 데이터베이스 구조를 ER 다이어그램으로 정리합니다. 기준은 실제 DDL 두 파일입니다.

- 민원 업무 스키마 `complaint_app` (13개 테이블): [`src/complaints/schema/complaint_app.sql`](../../src/complaints/schema/complaint_app.sql)
- 검색 색인 스키마 `complaint_rag` (8개 테이블): [`rag/origin/schema/complaint_rag.sql`](../../rag/origin/schema/complaint_rag.sql)

DDL이 바뀌면 이 문서도 함께 고칩니다. PDF는 `scripts/reports/export_er_diagram_pdf.py`로 이 문서의 다이어그램을 다시 그려 만듭니다.

## 읽는 법

| 표기 | 뜻 |
| --- | --- |
| `PK` / `FK` / `UK` | 기본 키 / 외래 키 / 유일 키 |
| 실선 (`--`) | DDL에 선언된 실제 외래 키(FK) |
| 점선 (`..`) | FK는 없지만 코드가 값으로 연결하는 논리 관계 |
| 선 끝의 두 줄 / 원과 줄 | 반드시 1개 / 0 또는 1개 |
| 선 끝의 원과 까마귀발 | 0개 이상 |

두 스키마는 행을 섞지 않습니다. 스키마 사이의 연결은 `ai_results.department_id → department_directory.department_id` 하나뿐입니다. 이 FK는 `complaint_rag`가 먼저 있을 때만 조건부로 추가됩니다.

## 1. 전체 구성 (스키마 간 연결)

```mermaid
erDiagram
    users ||--o{ complaints : "작성·담당"
    complaints ||--o{ messages : "답변·추가 문의"
    messages ||--o{ message_versions : "버전 이력"
    complaints ||--o{ ai_jobs : "AI 작업"
    ai_jobs ||--o| ai_results : "판정 결과"
    ai_jobs ||--o{ job_events : "진행 로그"
    complaints ||--o{ attachments : "첨부"
    users ||--o{ chat_sessions : "챗봇 대화"
    chat_sessions ||--o{ chat_messages : "턴"
    department_directory |o--o{ ai_results : "추천 부서 (스키마 간 FK)"
    department_directory |o--o{ routing_cases : "처리 부서"
    faq_knowledge ||..o{ term_postings : "키워드 색인"
    routing_cases ||..o{ term_postings : "키워드 색인"
```

왼쪽 위의 `users`부터 `chat_messages`까지가 `complaint_app`, `department_directory`·`routing_cases`·`faq_knowledge`·`term_postings`가 `complaint_rag`입니다. 아래 2·3절에 칼럼까지 모두 그렸습니다.

## 2. 민원 업무 스키마 `complaint_app` (13개 테이블)

핵심 정규화 7개(`users`, `complaints`, `messages`, `message_versions`, `ai_jobs`, `ai_results`, `job_events`)와 보조 6개(`idempotency`, `answer_templates`, `app_meta`, `chat_sessions`, `chat_messages`, `attachments`)입니다.

```mermaid
erDiagram
    users {
        text id PK
        text login_id UK
        text display_name
        text role "citizen | staff"
        text password_hash "scrypt"
        text department "담당자 부서"
        boolean is_demo
        boolean active
        timestamptz created_at
        timestamptz last_login_at
    }
    complaints {
        text id PK
        integer version "낙관적 잠금, 1 이상"
        timestamptz created_at
        jsonb payload "하위 호환 원본"
        text status "생성 칼럼: submitted~withdrawn"
        text owner "생성 칼럼"
        text visibility "생성 칼럼: private | public"
        text district "생성 칼럼: 4개 구 | 모름"
        boolean is_synthetic "생성 칼럼"
        text owner_user_id FK
        text assignee_user_id FK
        text title
        text body
        text category
        text department
        integer context_version
        timestamptz updated_at
    }
    messages {
        text id PK
        text complaint_id FK
        text kind "answer | inquiry"
        text origin "ai | ai_edited | staff | citizen"
        text author_user_id FK
        text body
        text published_version_id "게시 버전(논리)"
        timestamptz created_at
    }
    message_versions {
        text id PK
        text message_id FK "UK(message_id, version_no)"
        text complaint_id FK
        integer version_no
        text body
        text origin
        text kind
        text publish_state "draft | published | retracted | archived"
        text reason
        text actor_user_id FK
        integer context_version
        timestamptz created_at
    }
    ai_jobs {
        text id PK
        text complaint_id FK "UK(complaint_id, context_version, attempt)"
        integer context_version
        integer attempt
        text state "queued~superseded"
        text stage
        text provider
        timestamptz started_at
        timestamptz updated_at
    }
    ai_results {
        text id PK
        text job_id FK, UK "작업당 결과 1개"
        text complaint_id FK
        text outcome "faq_answer | department_suggestion | human_handoff"
        text reason_code
        text department_id FK "complaint_rag 부서(조건부)"
        text department_name
        jsonb evidence "검색 근거"
        text draft_body
        text guide_body
        boolean automatic_transfer "항상 false (CHECK)"
        text llm_provider
        text llm_model
        timestamptz created_at
    }
    job_events {
        bigint id PK "IDENTITY"
        text job_id FK "UK(job_id, seq_no)"
        text complaint_id FK
        integer seq_no
        timestamptz occurred_at
        text stage
        text vis "pub | int | ai"
    }
    idempotency {
        text owner PK
        text key PK
        text fingerprint
        text complaint_id FK
    }
    attachments {
        text id PK
        text complaint_id FK
        text uploaded_by FK
        text filename
        text content_type "jpeg | png | webp | pdf"
        integer size_bytes "5MB 이하"
        text sha256
        text storage_key UK
        boolean exif_stripped
        timestamptz created_at
    }
    chat_sessions {
        text id PK
        text user_id FK
        text title
        text last_district
        timestamptz created_at
        timestamptz updated_at
    }
    chat_messages {
        text id PK
        text session_id FK
        text role "user | assistant"
        text content
        text district
        text outcome
        text reason_code
        jsonb payload
        timestamptz created_at
    }
    answer_templates {
        text id PK
        text title
        text content
        boolean is_default
        timestamptz created_at
    }
    app_meta {
        text key PK
        text value
    }

    users |o--o{ complaints : "owner_user_id"
    users |o--o{ complaints : "assignee_user_id"
    complaints ||--o{ messages : "complaint_id"
    users |o--o{ messages : "author_user_id"
    messages ||--o{ message_versions : "message_id"
    complaints ||--o{ message_versions : "complaint_id"
    users |o--o{ message_versions : "actor_user_id"
    message_versions |o..o| messages : "published_version_id (논리)"
    complaints ||--o{ ai_jobs : "complaint_id"
    ai_jobs ||--o| ai_results : "job_id"
    complaints ||--o{ ai_results : "complaint_id"
    ai_jobs ||--o{ job_events : "job_id"
    complaints ||--o{ job_events : "complaint_id"
    complaints ||--o{ idempotency : "complaint_id"
    complaints ||--o{ attachments : "complaint_id"
    users |o--o{ attachments : "uploaded_by"
    users ||--o{ chat_sessions : "user_id"
    chat_sessions ||--o{ chat_messages : "session_id"
```

- `complaints`·`messages`·`message_versions`·`ai_jobs`·`ai_results`·`job_events`·`idempotency`·`attachments`의 `complaint_id`는 모두 `ON DELETE CASCADE`입니다. `chat_sessions`(사용자 삭제 시)와 `chat_messages`(세션 삭제 시)도 같습니다.
- `answer_templates`와 `app_meta`는 다른 테이블과 FK가 없는 독립 테이블입니다.
- 첨부 원본 파일은 DB가 아니라 `.web-data/uploads/`에 두고, DB에는 메타데이터와 `storage_key`만 저장합니다.

## 3. 검색 색인 스키마 `complaint_rag` (8개 테이블)

```mermaid
erDiagram
    index_metadata {
        text key PK
        jsonb value
    }
    department_directory {
        text department_id PK
        text canonical_name UK
        text_array aliases
        text district
        jsonb jurisdiction
        text jurisdiction_status
        text duty_description
        text duty_status "unverified | verified"
        text_array duty_source_urls
        date name_checked_on
        text_array name_source_urls
        text_array observed_case_titles
        boolean automatic_routing_ready
        timestamptz updated_at
    }
    faq_knowledge {
        text source_id PK
        text title
        text category
        text search_text
        jsonb payload "FAQ 원문 전체"
        text source_url
        timestamptz source_retrieved_at
        text content_hash
        text embedding_hash
        vector384 embedding "HNSW 코사인 색인"
        integer token_count
        timestamptz updated_at
    }
    routing_cases {
        text source_id PK
        text title
        text search_text
        jsonb payload "사례 원문 전체"
        text source_url
        timestamptz source_retrieved_at
        date complaint_date
        text department_id FK
        text department_status
        text district
        boolean routing_eligible "부서 연결 + review_required 아님"
        boolean summary_missing
        text content_hash
        text embedding_hash
        vector384 embedding "HNSW 코사인 색인"
        integer token_count
        timestamptz updated_at
    }
    term_postings {
        text corpus PK "faq | routing"
        text term PK
        text source_id PK
        integer tf
    }
    term_statistics {
        text corpus PK
        text term PK
        integer document_frequency
    }
    corpus_statistics {
        text corpus PK
        integer document_count
        double average_length
    }
    embedding_cache {
        text signature PK "모델·차원·접두 서명"
        text text_hash PK
        bytea vector "float32 바이트"
    }

    department_directory |o--o{ routing_cases : "department_id"
    faq_knowledge ||..o{ term_postings : "corpus=faq, source_id (논리)"
    routing_cases ||..o{ term_postings : "corpus=routing, source_id (논리)"
    term_statistics ||..o{ term_postings : "(corpus, term) (논리)"
    corpus_statistics ||..o{ term_statistics : "corpus (논리)"
    embedding_cache |o..o{ faq_knowledge : "text_hash = embedding_hash (논리)"
    embedding_cache |o..o{ routing_cases : "text_hash = embedding_hash (논리)"
```

- `faq_knowledge`와 `routing_cases`는 별도 컬렉션입니다. 문서 키는 `(corpus, source_id)`이고, 사이트 표시 번호는 고정 키로 쓰지 않습니다.
- `routing_cases`의 CHECK 제약: `routing_eligible = (department_id IS NOT NULL AND department_status <> 'review_required')`. 이 값은 부서 추천에 써도 되는 사례라는 뜻이지 자동 이관 허가가 아닙니다.
- 벡터는 `dragonkue/multilingual-e5-small-ko` 384차원입니다. DDL의 `__EMBEDDING_DIM__` 자리에 적재 시 차원이 들어갑니다.
- BM25 키워드 검색은 `term_postings`·`term_statistics`·`corpus_statistics` 세 테이블로 PostgreSQL 안에서 계산합니다. 벡터 후보 30개와 BM25 후보 30개를 RRF(k=60)로 합칩니다.
- `embedding_cache`는 재적재할 때 같은 서명·본문 해시의 벡터를 다시 계산하지 않게 남겨 두는 체크포인트입니다.

## 4. 테이블 요약

| 스키마 | 테이블 | 역할 | 배포 서버 행 수 (2026-11-26) |
| --- | --- | --- | ---: |
| `complaint_app` | `users` | 민원인·담당자 로그인 계정 | 8 |
| | `complaints` | 민원 본문·상태·버전·작성자/담당자 | 2 |
| | `messages` | 민원별 답변 스레드와 시민 추가 문의 | 2 |
| | `message_versions` | 답변 초안·게시·철회 버전 이력 | 1 |
| | `ai_jobs` | 민원별 AI 실행 작업 | 3 |
| | `ai_results` | AI 판정·근거·부서 추천 (자동 이관 금지) | 3 |
| | `job_events` | AI 작업 단계별 진행 로그 | 18 |
| | `idempotency` | 중복 등록 방지 키 | — |
| | `attachments` | 첨부 파일 메타데이터 (EXIF 제거) | 0 |
| | `chat_sessions` | 시민 AI 챗봇 대화 세션 | 0 |
| | `chat_messages` | 챗봇 대화 턴 | 0 |
| | `answer_templates` | 담당자 답변 템플릿 | 5 |
| | `app_meta` | 시드·마이그레이션 플래그 | — |
| `complaint_rag` | `index_metadata` | 색인 설정·상태 | — |
| | `department_directory` | 부서 목록 | 127 |
| | `faq_knowledge` | FAQ 안내 자료 + 벡터 | 94 |
| | `routing_cases` | 과거 민원 사례와 처리 부서 + 벡터 | 5,015 |
| | `term_postings` | BM25: 문서별 단어 빈도 | — |
| | `term_statistics` | BM25: 단어별 문서 수 | — |
| | `corpus_statistics` | BM25: 묶음별 문서 수·평균 길이 | — |
| | `embedding_cache` | 재적재용 벡터 체크포인트 | — |

`complaint_app` 행 수는 시연 중에 바뀌는 시점 값입니다. `—`는 이번에 세지 않은 테이블입니다.
