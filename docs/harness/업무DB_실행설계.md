# 업무 DB 실행 설계

[하네스 안내](README.md) · [데이터 계약](data-contracts.md) · [서버 안내](../../src/README.md) · [사례 색인](../cases/README.md)

**기준일: 2026-11-06 UTC.** 이 문서는 현재 실행 중인 민원 업무 DB의 구조를 설명합니다. 2026-10-30 설계 초안(7테이블)과 다른 점은 [3절](#3-2026-10-30-설계와의-대응)에 정리했습니다. 2026-11-06 이전 자료의 구조 설명은 이 문서로 대체합니다.

## 1. 한눈에 보기

- 저장소: 같은 PostgreSQL 서버의 `complaint_app` 스키마 (기본값, `COMPLAINT_APP_SCHEMA`로 바꿀 수 있음)
- 테이블 2개: `complaints`(민원 한 건 = 한 행), `idempotency`(등록 중복 방지)
- 원본은 `complaints.payload`(jsonb) 하나입니다. 답변 버전·추가 문의·AI 후보·작업 단계는 모두 payload 안에 있습니다.
- 목록·필터용 칼럼 5개는 payload에서 자동 계산되는 **생성 칼럼**입니다. 따로 쓰지 않으므로 payload와 어긋나지 않습니다.
- 검색 색인 `complaint_rag`와 섞지 않습니다. 현재 `complaint_rag`는 이 DB에 없습니다(검색 적재는 별도 작업).

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

### 2.2 `complaint_app.idempotency`

| 칼럼 | 설명 |
| --- | --- |
| `owner`, `key` | 작성자별 `Idempotency-Key` (기본 키) |
| `fingerprint` | 등록 본문의 SHA-256 해시. 같은 키에 다른 본문이 오면 409 |
| `complaint_id` | 등록된 민원 (`complaints.id` 외래 키) |

이 테이블은 2026-10-30 설계에 없습니다. 웹 등록의 재전송 안전성을 위해 추가했습니다.

### 2.3 `payload` 구조 (camelCase JSON)

서버는 Pydantic 모델을 `model_dump(mode="json")`으로 저장합니다. 키는 camelCase입니다. 실제 DB에서 확인한 키는 다음과 같습니다.

| 키 | 내용 | 공개 범위 |
| --- | --- | --- |
| `id`, `title`, `body`, `category`, `district`, `owner`, `visibility`, `status`, `date`, `version`, `contextVersion`, `isSynthetic` | 민원 기본 정보 | 시민 응답 포함 |
| `messages[]` | 시민 추가 문의 `{author, text, date}` | 시민 응답 포함 |
| `published` | 현재 게시된 답변 `{text, origin, reason, date}` 또는 `null` | 시민 응답 포함 |
| `history[]` | 처리 이력 `{text, stage, date, public}` | `public=true`만 시민에게 |
| `assigned`, `draft`, `draftVersion` | 담당 여부, 담당자 초안 | 담당자만 |
| `versions[]` | 답변 버전 `{version, text, reason, kind, date}` (`kind`: 초안 저장·게시·게시 철회·시민 원문 수정 전 등) | 담당자만 |
| `aiOriginal`, `aiCandidate` | AI 원본 문장, 시연 후보 문장 | 담당자만 |
| `job` | 시연 작업 `{status, stage, attempt, contextVersion, startedAt, events[]}` | 담당자만 |

`origin`은 `ai`, `ai_edited`, `staff` 중 하나입니다. 담당자 응답에서 `aiOriginal`이 있으면 작성 기원을 서버가 정합니다.

## 3. 2026-10-30 설계와의 대응

2026-10-30 설계(`plan/db 설계 1차/2026-10-30/02_complaint_app.sql`)는 7테이블 정규화 초안입니다. 현재 구현은 이 설계를 **미채택**했습니다. 근거는 [CASE-031](../cases/사례-031-업무저장-PostgreSQL-통일-2026-11-05.md)과 [CASE-054](../cases/사례-054-업무DB-실행구조와-설계-정합-2026-11-06.md)입니다.

| 설계 테이블 | 현재 위치 | 상태 |
| --- | --- | --- |
| `users` | 없음. `owner`에 세션 ID 문자열 | 미구현 (시연에 인증 없음) |
| `complaints` | `complaints` (payload + 생성 칼럼) | 구조 다름 |
| `messages` (inquiry) | `payload.messages[]` | 미정규화 |
| `message_versions` | `payload.versions[]`, `payload.published` | 미정규화 |
| `ai_jobs` | `payload.job` (최신 1건만 보존) | 미정규화, 이전 시도 기록 없음 |
| `ai_results` | `payload.aiCandidate` (근거·부서 없음) | 미구현 |
| `job_events` | `payload.job.events[]` (공개 구분 `vis` 없음) | 미정규화 |
| (없음) | `idempotency` | 추가됨 |

설계와 다른 값 기준:

| 항목 | 설계 | 현재 |
| --- | --- | --- |
| 상태 | 한글 10개 (`AI검토`, `배정완료` …) | 영문 5개 (`submitted` …) |
| 민원 번호 | `YYYY-MMDD-NNNN` (bigint 내부 번호 별도) | `DEMO-YYYY-…` 문자열 |
| 분류 | "대분류 › 중분류" 자유 텍스트 | 6개 고정 목록 (`도로·교통` …) |
| 지역 | 모르면 `NULL` | `모름` 문자열 |
| 시연 표시 | `is_synthetic` 칼럼 | 같은 이름의 생성 칼럼 (2026-11-06 반영) |
| 삭제 | `deleted_at` | `withdrawn` 상태 |

**2026-11-06에 설계 쪽으로 맞춘 것:** 시연 표시(`is_synthetic`)와 상태·지역·공개 범위 검사만 맞췄습니다. 나머지 차이는 현재 구조를 유지하는 결정입니다.

## 4. 다른 자료와의 관계

- **검색 스키마 `complaint_rag`:** 이 DB에 아직 없습니다. 현재 설계는 AI 결과의 부서 번호를 외래 키가 아니라 **payload 안의 값으로 두고, 코드에서 `department_directory`와 대조**하는 방식입니다. 검색 적재 후 결정합니다.
- **`ui` 목업 (`minwon-toktok-ui04.html`):** 목업 안의 데이터 저장소는 설계 테이블 이름(`users`, `ai_jobs`, `message_versions`…)을 씁니다. 목업은 이 문서의 구조와 다르므로, 서버에 연결할 때 위 대응표로 변환합니다.
- **시연 데이터:** `seed-public-demo`는 공개 사례·자주 묻는 민원 JSON에서 만든 민원에 `isSynthetic=true`를 넣습니다. 지역은 `모름`입니다.

## 5. 변경 절차

구조를 바꿀 때 다음 순서를 따릅니다.

1. 이 문서와 [CASE 색인](../cases/README.md)에서 같은 주제의 기존 결정을 찾습니다.
2. `src/complaints/models.py`의 필드를 바꿉니다. 모델이 payload 형식의 기준입니다.
3. 목록·필터에 쓸 값이면 생성 칼럼을 추가합니다. 저장소 `_SCHEMA_STATEMENTS`와 `src/complaints/schema/complaint_app.sql`을 같이 고칩니다. 두 곳은 같은 내용이어야 합니다.
4. 허용 값을 바꾸면 CHECK 목록(`_VALUE_CHECKS`)과 SQL 파일의 DO 블록을 같이 바꿉니다.
5. 예전 행을 맞춰야 하면 `UPDATE`를 `_SCHEMA_STATEMENTS`에 **멱등하게** 추가합니다. 이미 맞춘 행은 다시 바꾸지 않아야 합니다.
6. 스키마 변경 전에 백업합니다. 예: `pg_dump -n complaint_app -f <백업 경로>`
7. 검증: 아래 명령을 실행하고 결과를 사례에 기록합니다.

```powershell
.\.venv-web\Scripts\python.exe -m pytest src/tests -q -p no:cacheprovider
$env:RUN_PG_TESTS = "1"; .\.venv-web\Scripts\python.exe -m pytest src/tests/test_postgres_schema.py src/tests/test_postgres_repository.py -q -p no:cacheprovider
```

PostgreSQL 테스트는 `PGUSER`·`PGHOST`·`PGDATABASE` 환경변수로 접속합니다. 임시 스키마를 만들고 끝나면 지웁니다.

## 6. 현재 한계

- **목록은 전체를 읽습니다.** `PostgresRepository.all()`이 모든 행을 가져와 Python에서 필터링합니다. 생성 칼럼과 색인은 준비됐지만, 목록 쿼리는 아직 이를 쓰지 않습니다. 시연 규모(수십~수백 건)에서는 충분하며, 대규모 운영 전에 페이지네이션 쿼리로 바꿔야 합니다.
- **`payload` 구조 검사는 Python 모델에만 있습니다.** DB는 생성 칼럼이 가리키는 값만 검사합니다.
- **이전 시도 기록이 없습니다.** 작업은 최신 1건만 `payload.job`에 남습니다.
- **인증과 사용자 테이블이 없습니다.** 시연 세션 ID만 씁니다.

## 7. 설계 문서의 기준일 표기

다음 문서는 직접 고칠 수 없거나 아직 고치지 않았습니다. 기준일을 확인하고 현재 구조는 이 문서를 따릅니다.

| 문서 | 기준일 | 현재와의 관계 |
| --- | --- | --- |
| `plan/db 설계 1차/2026-10-30/README.md` | 2026-10-30 | 상단에 2026-11-06 주의 표기 추가 |
| `plan/db 설계 1차/2026-10-30/02_complaint_app_초안_미채택.sql` | 2026-10-30 | 미채택 초안 (이름 변경) |
| `plan/db 설계 1차/2026-10-30/DB01_테이블_설명.pdf` | 2026-10-30 | 7테이블 기준. 수정 불가, 현재와 다름 |
| `plan/db 설계 1차/2026-10-30/DB설계.pptx` | 2026-10-30 | 7테이블 기준. 수정 불가, 현재와 다름 |
| `plan/db 설계 1차/2026-10-30/회의록_2026-10-30.pdf` | 2026-10-30 | 회의 당시 결정. 수정 불가 |
| `plan/db 설계 1차/AI민원처리시스템_수정1.pptx` | 2026-10-30 전후 | 7테이블 기준. 수정 불가, 현재와 다름 |
| `plan/민원_웹_MVP_상세설계와_분야별_작업계획.md`(·.pdf) | 2026-10-27 | 7테이블 객체를 계획으로 적음. 상단 주의 표기 추가 (PDF는 수정 불가) |
| `plan/시연_웹_게시판과_민원_서버_구현계획.md` | 2026-10-25 | 업무 DB 계획. 상단 주의 표기 추가 |
| `ui/minwon-toktok-ui04.html`, `프로토타입_DB샘플연동.html` | 목업 (날짜 미기록) | 설계 테이블 이름 사용. 서버와 미연결 |
