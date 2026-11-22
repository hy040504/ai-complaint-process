# 업무 DB 실행 설계

[하네스 안내](README.md) · [데이터 계약](data-contracts.md) · [서버 안내](../../src/README.md) · [사례 색인](../cases/README.md)

**기준일: 2026-11-20 KST (`CASE-111` 7테이블 정규화 완료).** 이 문서는 현재 실행 중인 민원 업무 DB(`complaint_app`)의 구조를 설명합니다. 기존 jsonb 기반 실행 구조(`2026-11-06~16`)의 하위 호환성을 100% 유지하면서 2026-10-30 설계의 7개 핵심 정규화 테이블을 실제 PostgreSQL 테이블·외래 키·CHECK 제약으로 구현했습니다([CASE-111](../cases/사례-111-운영-본인담당자-인증과-PostgreSQL-7테이블-정규화-구현-2026-11-20.md)).

## 1. 한눈에 보기

- 저장소: 같은 PostgreSQL 서버의 `complaint_app` 스키마 (기본값, `COMPLAINT_APP_SCHEMA`로 바꿀 수 있음)
- **총 10테이블 구성 (7개 핵심 정규화 테이블 + 3개 운영 보조 테이블):**
  - 핵심 7테이블: `users`(민원인·담당자 아이디/비밀번호 `scrypt` 해시·부서 권한), `complaints`(민원 본체 + 기존 `payload` JSONB/생성 칼럼 5개 호환 + `owner_user_id`/`assignee_user_id` FK), `messages`(추가 문의·답변), `message_versions`(초안·게시·철회 버전 이력), `ai_jobs`(AI 작업 이력), `ai_results`(판정·근거·`CHECK (automatic_transfer = false)`·`complaint_rag.department_directory` 조건부 교차 FK), `job_events`(작업 단계 타임라인, `ON DELETE CASCADE`)
  - 보조 3테이블: `idempotency`(등록 중복 방지), `answer_templates`(담당자 자주 쓰는 답변 템플릿), `app_meta`(기본 템플릿 최초 1회 시드 플래그)
- `PostgresRepository`는 민원 생성(`create`)·변경(`change`) 시 동일 PostgreSQL 트랜잭션에서 `complaints`와 하위 5개 정규화 테이블을 원자적으로 동기화하며, 서버 기동 시 기존 행을 무손실 자동 백필합니다. 담당자 전용 `GET /api/v1/staff/db-summary`로 7테이블 실시간 행 수·역할·AI 판정 분포를 SQL 집계합니다.
- 목록·필터용 칼럼 5개(`status`·`owner`·`visibility`·`district`·`is_synthetic`)는 `complaints.payload`에서 자동 계산되는 **생성 칼럼**으로 유지되어 기존 쿼리·테스트와 어긋나지 않습니다.
- 검색 색인 `complaint_rag`에 업무 행을 섞지 않습니다(`ai_results.department_id`만 `complaint_rag.department_directory` 존재 시 참조 FK로 연결).

## 2. 실제 구조

### 2.1 `complaint_app.complaints`

| 칼럼 | 형식 | 원천 | 설명 |
| --- | --- | --- | --- |
| `id` | text, PK | 서버 발급 | `DEMO-YYYY-XXXXXXXXXXXX` 형식의 민원 번호 |
| `version` | integer, `> 0` | payload | 동시 수정 검사용 기대 버전 |
| `created_at` | timestamptz | 등록 시각 | 목록 정렬 기준 |
| `payload` | jsonb | 원본 | 민원 전체 (아래 2.3절) |
| `status` | text, **생성** | `payload.status` | 상태. CHECK로 허용 값만 받음 |
| `owner` | text, **생성** | `payload.owner` | 작성자 세션 ID (`citizen-demo` 등) |
| `visibility` | text, **생성** | `payload.visibility` | `private`·`public`. CHECK |
| `district` | text, **생성** | `payload.district` | 상당구·서원구·흥덕구·청원구·모름. CHECK |
| `is_synthetic` | boolean, **생성** | `payload.isSynthetic` | 시연용 민원 표시. 키가 없으면 `false` |

색인:
- `complaints_status_created (status, created_at)`: 상태별 최신순 목록
- `complaints_owner_created (owner, created_at)`: 작성자별 목록

CHECK 제약:
- `complaints_version_check`: `version > 0`
- `complaints_status_valid`: `submitted`, `under_review`, `answered`, `closed`, `withdrawn`
- `complaints_visibility_valid`: `private`, `public`
- `complaints_district_valid`: `상당구`, `서원구`, `흥덕구`, `청원구`, `모름`

생성 칼럼의 CHECK는 NULL을 통과시킵니다. 그래서 `payload`에 해당 키가 없는 예전 행도 저장을 막지 않습니다.

### 2.2 `complaint_app.idempotency` · `answer_templates` · `app_meta`

| 테이블 | 칼럼 | 설명 |
| --- | --- | --- |
| `idempotency` | `owner`, `key` | 작성자별 `Idempotency-Key` (기본 키) |
| `idempotency` | `fingerprint` | 등록 본문의 SHA-256 해시. 같은 키에 다른 본문이 오면 409 |
| `idempotency` | `complaint_id` | 등록된 민원 (`complaints.id` 외래 키). 시민 영구 삭제 시 먼저 정리 |
| `answer_templates` | `id`, `title`, `content`, `is_default`, `created_at` | 담당자 답변 편집기 커스텀·기본 답변 템플릿(CRUD) |
| `app_meta` | `key`, `value` | `default_templates_seeded` 등 초기화 완료 플래그(삭제한 기본 템플릿 부활 방지) |

이 테이블들은 2026-10-30 설계에 없으며 재전송 안전성과 담당자 편집기 템플릿 영속화를 위해 추가했습니다.

### 2.3 `payload` 구조 (camelCase JSON)

서버는 Pydantic 모델을 `model_dump(mode="json")`으로 저장합니다. 키는 camelCase입니다. 실제 DB에서 확인한 키는 다음과 같습니다.

| 키 | 내용 | 공개 범위 |
| --- | --- | --- |
| `id`, `title`, `body`, `category`, `district`, `owner`, `visibility`, `status`, `date`, `version`, `contextVersion`, `isSynthetic` | 민원 기본 정보 | 시민 응답 포함 |
| `messages[]` | 시민 추가 문의 `{author, text, date}` | 시민 응답 포함 |
| `published` | 현재 게시된 답변 `{text, origin, reason, date}` 또는 `null` | 시민 응답 포함 |
| `history[]` | 처리 이력 `{text, stage, date, public}` | `public=true`만 시민에게 |
| `assigned`, `department`, `draft`, `draftVersion` | 담당 여부, 시연 배정 부서명, 담당자 초안 | 담당자만 |
| `versions[]` | 답변 버전 `{version, text, reason, kind, date}` (`kind`: 초안 저장·게시·게시 철회·시민 원문 수정 전 등) | 담당자만 |
| `aiOriginal`, `aiCandidate`, `aiAssist` | AI 원본 문장, 시연 후보 문장, 응대 분석 결과(`AssistResponse`) | 담당자만 |
| `job` | 작업 상태 `{status, stage, attempt, contextVersion, provider, startedAt, events[]}` | 담당자만 |

`origin`은 `ai`, `ai_edited`, `staff` 중 하나입니다. 담당자 응답에서 `aiOriginal`이 있으면 작성 기원을 서버가 정합니다.

## 3. 2026-10-30 설계와의 대응 (`CASE-111` 정규화 완료)

2026-10-30 설계(`docs/plans/archive/db 설계 1차/2026-10-30/02_complaint_app.sql`)의 7테이블 정규화는 [CASE-031](../cases/사례-031-업무저장-PostgreSQL-통일-2026-11-05.md)과 [CASE-054](../cases/사례-054-업무DB-실행구조와-설계-정합-2026-11-06.md) 단계에서 일시 보류했으나, **2026-11-20 [CASE-111](../cases/사례-111-운영-본인담당자-인증과-PostgreSQL-7테이블-정규화-구현-2026-11-20.md)로 기존 JSONB 계약을 보존하면서 7개 핵심 테이블을 모두 구현·자동 백필·원자적 동기화**했습니다.

| 설계 테이블 | 현재 위치 (`complaint_app`) | 상태 (`2026-11-20`) |
| --- | --- | --- |
| `users` | `complaint_app.users` (`login_id`, `password_hash`, `role`, `department`, `is_demo`, `active`) | **구현 완료** (시연 2계정 + 기본 민원인 1계정 + 담당자 3계정 멱등 시드 + 간단 가입) |
| `complaints` | `complaint_app.complaints` (기존 `payload` + 생성 칼럼 5개 + `owner_user_id`/`assignee_user_id` FK·`title`/`body`/`category`/`department`/`context_version`) | **구현 완료** (하위 호환 + 정규화 병행) |
| `messages` | `complaint_app.messages` (`complaint_id` `ON DELETE CASCADE`, `author_user_id` FK) | **구현 완료** (원자 동기화·자동 백필) |
| `message_versions` | `complaint_app.message_versions` (`message_id`/`complaint_id` `ON DELETE CASCADE`, `actor_user_id` FK, `origin` CHECK) | **구현 완료** (초안·게시·철회·수정 전 이력) |
| `ai_jobs` | `complaint_app.ai_jobs` (`complaint_id` `ON DELETE CASCADE`, `status`·`stage`·`provider`·`attempt`) | **구현 완료** |
| `ai_results` | `complaint_app.ai_results` (`CHECK (automatic_transfer = false)`, `fk_ai_results_department` → `complaint_rag.department_directory`) | **구현 완료** (DB 레벨 자동이관 차단 + 교차 FK) |
| `job_events` | `complaint_app.job_events` (`job_id`/`complaint_id` `ON DELETE CASCADE`, `seq`·`stage`·`visibility`) | **구현 완료** |
| (없음) | `idempotency` | 운영 보조 테이블 유지 |
| (없음) | `answer_templates`, `app_meta` | 운영 보조 테이블 유지 (담당자 템플릿 CRUD·1회 시드) |

설계와 다른 값 기준:

| 항목 | 설계 | 현재 |
| --- | --- | --- |
| 상태 | 한글 10개 (`AI검토`, `배정완료` …) | 영문 5개 (`submitted` …) |
| 민원 번호 | `YYYY-MMDD-NNNN` (bigint 내부 번호 별도) | `DEMO-YYYY-…` 문자열 |
| 분류 | "대분류 › 중분류" 자유 텍스트 | 6개 고정 목록 (`도로·교통` …) |
| 지역 | 모르면 `NULL` | `모름` 문자열 |
| 시연 표시 | `is_synthetic` 칼럼 | 같은 이름의 생성 칼럼 (2026-11-06 반영) |
| 삭제 | `deleted_at` | `withdrawn` 논리 철회(`DELETE /complaints/{id}`) + 작성자 영구 삭제(`POST /complaints/{id}/delete`) |

**2026-11-06~2026-11-20 진화 요약:** 시연 표시(`is_synthetic`)·상태·지역·공개 범위 CHECK 제약, 시민 영구 삭제(`idempotency` 선삭제 후 삭제), `payload.department`·`payload.aiAssist`, 담당자 템플릿 테이블(`answer_templates`·`app_meta`)에 이어 **2026-11-20 `CASE-111`로 7개 정규화 테이블(`users`~`job_events`), `automatic_transfer=false` CHECK, `complaint_rag` 교차 FK, 자동 백필 및 `GET /api/v1/staff/db-summary` SQL 집계**를 반영했습니다.

## 4. 다른 자료와의 관계

- **검색 스키마 `complaint_rag`:** 같은 `complaints_native` DB에 분리 스키마로 공존합니다. 업무 행을 검색 색인에 섞지 않되, `complaint_app.ai_results.department_id`는 `complaint_rag.department_directory(department_id)`가 존재할 때 조건부 외래 키(`fk_ai_results_department`)로 참조 무결성을 보장합니다.
- **`ui` 목업 (`minwon-toktok-ui04.html`):** 목업 안의 데이터 저장소는 설계 테이블 이름(`users`, `ai_jobs`, `message_versions`…)을 씁니다. `/design/ui04` 경로의 `ui04-adapter.js`로 `/api/v1`에 연결합니다.
- **시연 데이터:** `seed-public-demo`는 공개 사례·자주 묻는 민원 JSON에서 만든 민원에 `isSynthetic=true`를 넣습니다. 지역은 `모름`입니다.

## 5. 변경 절차

구조를 바꿀 때 다음 순서를 따릅니다.

1. 이 문서와 [CASE 색인](../cases/README.md)에서 같은 주제의 기존 결정을 찾습니다.
2. `src/complaints/models.py`의 필드를 바꿉니다. 모델이 payload 형식의 기준입니다.
3. 목록·필터·정규화 테이블을 추가할 때는 저장소 `_SCHEMA_STATEMENTS`와 `src/complaints/schema/complaint_app.sql`을 같이 고칩니다. 두 곳은 같은 내용이어야 합니다.
4. 허용 값을 바꾸면 CHECK 목록(`_VALUE_CHECKS`)과 SQL 파일의 DO 블록을 같이 바꿉니다.
5. 예전 행을 맞춰야 하면 `UPDATE`/백필 로직을 **멱등하게** 추가합니다. 이미 맞춘 행은 다시 바꾸지 않아야 합니다.
6. 스키마 변경 전에 백업합니다. 예: `pg_dump -n complaint_app -f <백업 경로>`
7. 검증: 아래 명령을 실행하고 결과를 사례에 기록합니다.

```powershell
.\.venv-web\Scripts\python.exe -m pytest src/tests -q -p no:cacheprovider
$env:RUN_PG_TESTS = "1"; .\.venv-web\Scripts\python.exe -m pytest src/tests/test_postgres_schema.py src/tests/test_postgres_repository.py src/tests/test_auth_and_normalized_db.py -q -p no:cacheprovider
```

PostgreSQL 테스트는 `PGUSER`·`PGHOST`·`PGDATABASE` 환경변수로 접속합니다. 임시 스키마를 만들고 끝나면 지웁니다.

## 6. 현재 한계

- **목록은 전체를 읽습니다.** `PostgresRepository.all()`이 모든 행을 가져와 Python에서 필터링합니다. 생성 칼럼·정규화 칼럼·색인은 준비됐지만, 목록 쿼리는 시연 규모(수십~수백 건) 호환을 위해 유지하며 대규모 운영 전에 페이지네이션 SQL 쿼리로 전환해야 합니다.
- **정규화 테이블과 `payload` JSONB 병행 유지:** 기존 API·테스트 호환을 위해 `complaints.payload` JSONB와 정규화 자식 5테이블을 동일 트랜잭션에서 원자 동기화합니다. 향후 완전 정규화 조회 전환 시 `payload` 중복 칼럼 축소를 검토할 수 있습니다.
- **로컬 로그인과 외부 기관 인증의 구별:** `users` 테이블은 로컬 서버의 민원인·담당자 아이디/`scrypt` 비밀번호·부서 권한을 저장하며, 실제 외부 PASS/공동인증서·청주시 행정 SSO 연계는 별도 배포 단계입니다.

## 7. 설계 문서의 기준일 표기

다음 문서는 직접 고칠 수 없거나 아직 고치지 않았습니다. 기준일을 확인하고 현재 구조는 이 문서를 따릅니다.

| 문서 | 기준일 | 현재와의 관계 |
| --- | --- | --- |
| `docs/plans/archive/db 설계 1차/2026-10-30/README.md` | 2026-10-30 | 상단에 2026-11-06 주의 표기 추가 |
| `docs/plans/archive/db 설계 1차/2026-10-30/02_complaint_app_초안_미채택.sql` | 2026-10-30 | 미채택 초안 (이름 변경) |
| `docs/plans/archive/db 설계 1차/2026-10-30/DB01_테이블_설명.pdf` | 2026-10-30 | 7테이블 기준. 수정 불가, 현재와 다름 |
| `docs/plans/archive/db 설계 1차/2026-10-30/DB설계.pptx` | 2026-10-30 | 7테이블 기준. 수정 불가, 현재와 다름 |
| `docs/plans/archive/db 설계 1차/2026-10-30/회의록_2026-10-30.pdf` | 2026-10-30 | 회의 당시 결정. 수정 불가 |
| `docs/plans/archive/db 설계 1차/AI민원처리시스템_수정1.pptx` | 2026-10-30 전후 | 7테이블 기준. 수정 불가, 현재와 다름 |
| `docs/plans/민원_웹_MVP_상세설계와_분야별_작업계획.md`(·.pdf) | 2026-10-27 | 7테이블 객체를 계획으로 적음. 상단 주의 표기 추가 (PDF는 수정 불가) |
| `docs/plans/시연_웹_게시판과_민원_서버_구현계획.md` | 2026-10-25 | 업무 DB 계획. 상단 주의 표기 추가 |
| `ui/minwon-toktok-ui04.html`, `ui/mockups/프로토타입_DB샘플연동.html` | 목업 (날짜 미기록) | 설계 테이블 이름 사용. 서버와 미연결 |
