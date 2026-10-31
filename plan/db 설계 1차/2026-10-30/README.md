# DB 스키마 설명

2026-10-31 이후 실행용 파일은 `db/schema/complaint_rag.sql`, `db/schema/complaint_app.sql`이다. 이 폴더는 2026-10-30 설계 복사본이다.

## 파일 구성

- `README.md` : 전체 설명 (이 파일)
- `DB01_테이블_설명.pdf` : 컬럼 설명과 관계도
  - 3쪽부터 22쪽 : 한국어 이름
  - 23쪽부터 42쪽 : 영어 원문 이름
- `01_complaint_rag.sql` : 검색용 스키마
- `02_complaint_app.sql` : 민원 게시판용 스키마
- 읽는 순서 : `README.md` → PDF의 관계 쪽 → SQL

## 1. 한눈에 보기

- 스키마 : DB 안에서 테이블을 종류별로 나누어 담는 단위
- DB 1개 안에 스키마 2개
  - `complaint_rag` : AI가 검색하는 자료 보관
  - `complaint_app` : 민원 게시판이 쓰는 데이터 보관
- 두 스키마의 연결 : 단 1곳 (부서 번호)

## 2. 스키마가 2개인 이유

- 역할이 서로 다름
  - 검색 자료 : 원본 FAQ와 과거 사례를 담는 데이터, 읽기 중심
  - 민원 데이터 : 시민과 담당자가 계속 쓰고 고치는 데이터, 쓰기 중심
- 민원 글이 검색 자료에 섞이지 않게 분리
- 검색 자료를 다시 적재해도 민원 데이터는 그대로 유지
- `complaint_app`만 지우고 다시 만들 수 있어 시연 준비 쉬움

## 3. complaint_rag (검색용)

- 역할 : AI가 답을 찾을 때 참고하는 자료 보관
- 상태 : 구조(SQL)만 있음, 자료 적재는 임베딩 모델을 정한 뒤 새로 할 예정
- 민원 게시판(`complaint_app`) 쪽에서는 읽기만 함
- 테이블 7개 (괄호 안은 JSON 파일 기준으로 적재할 건수)
  - `faq_knowledge` : FAQ 안내 자료 (94건)
  - `routing_cases` : 과거 민원 사례와 처리 부서 (5,015건)
  - `department_directory` : 부서 목록 (127개)
  - `index_metadata` : 색인 정보
  - `term_postings`, `term_statistics`, `corpus_statistics` : 키워드 검색용 통계 3개
- FAQ와 사례에는 비슷한 글을 찾기 위한 벡터(1024차원) 저장

## 4. complaint_app (민원 게시판용)

- 역할 : 시연 웹에 보이는 민원, 답변, AI 작업 기록 보관
- 상태 : 이번에 새로 만드는 스키마 (`02_complaint_app.sql`)
- 테이블 7개
  - `users` : 사용자 (시민, 담당자)
  - `complaints` : 민원 한 건
  - `messages` : 민원에 달린 답변, 추가 문의 묶음
  - `message_versions` : 답변 글의 버전
  - `ai_jobs` : AI가 일한 기록
  - `ai_results` : AI가 낸 결과
  - `job_events` : AI 작업 중 생긴 일

### 화면 기능과 테이블 연결

- AI 작성 / 담당자 수정 답변 구분 : `message_versions`의 작성 주체 칸
- 답변 수정 기록 보기 : `message_versions`에 버전별로 누적
- AI 작업 진행 상태 보기 : `ai_jobs`의 상태, 단계와 `job_events`

## 5. 두 스키마의 연결

- 연결 위치 : `ai_results.department_id` → `department_directory.department_id`
- 뜻 : AI가 추천한 부서 번호가 부서 목록의 실제 부서를 가리킴
- 자동 이관 없음 (`automatic_transfer` 항상 `false`), 추천은 참고용
- 그 외 연결 없음
  - 민원 글은 검색 자료에 들어가지 않음
  - 검색 자료는 민원 데이터를 바꾸지 않음

## 6. 민원 한 건의 흐름

1. 시민이 민원 작성 → `complaints` 저장
2. AI 작업 생성 → `ai_jobs` 저장
3. AI가 `complaint_rag`에서 FAQ와 사례 검색 (읽기만)
4. 결과 저장 → `ai_results` (근거, 추천 부서, 답변 초안), 진행 기록은 `job_events`
5. 답변 초안 → `messages`와 `message_versions`에 초안으로 저장
6. 담당자가 수정하고 게시 → `message_versions`에 새 버전 추가, 게시된 버전 1개 지정

## 7. 실행 방법

- 파일 2개
  - `01_complaint_rag.sql` : `complaint_rag` 생성 (pgvector 확장 필요)
  - `02_complaint_app.sql` : `complaint_app` 생성
- 순서 : `01` 먼저, 그 다음 `02`
- 명령 : `psql -d DB이름 -f 01_complaint_rag.sql`, `psql -d DB이름 -f 02_complaint_app.sql`
- `02`는 여러 번 실행 가능 : 맨 위에서 `complaint_app`만 지우고 다시 생성
- `02`는 `complaint_rag`를 건드리지 않음
- `complaint_rag`가 없는 DB : 부서 연결만 건너뛰고 나머지는 정상 실행

## 8. 값 정의 (프로토타입 HTML 기준)

- 처리 상태(`complaints.status`) 10가지 : AI검토, 배정완료, 처리중, 보완요청, 답변완료, 총괄검토, 조정대기, 재배정, 반려, 소관외 종결
- 단계(`complaints.stage`) 1부터 5까지
  - 1 접수, 2 AI검토, 3 배정, 4 처리중, 5 답변완료
- 공개 구분(`job_events.vis`) 3가지
  - `pub` : 자동 공개
  - `int` : 내부 전용
  - `ai` : AI 산출
- 민원번호(`complaints.public_code`) : `YYYY-MMDD-NNNN` 형식 (예: 2026-1030-0001)
- 분류(`complaints.category`) : "대분류 › 중분류" 형식

## 9. 아직 정해지지 않은 것

- AI 작업 단계(`ai_jobs.stage`) 값 : AI 쪽 흐름에 맞춰 결정
- DB 실행 위치 : `complaint_rag`와 `complaint_app`을 같은 DB에 만들지, 어디에서 실행할지 확인 필요
- 임베딩 모델 : 새로 정함, 모델에 따라 벡터 차원(`vector(1024)`)을 맞춰야 함
- 적재 코드 : JSON 파일을 읽어서 `complaint_rag`에 채워 넣는 프로그램, 앞으로 만듦
- 프로토타입 코드에는 "질문대기", "추가문의"도 상태처럼 쓰이나 데이터 모델의 상태 10가지에는 없음 (현재 SQL은 10가지만 허용)
