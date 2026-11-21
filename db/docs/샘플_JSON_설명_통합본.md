# 테이블별 샘플 JSON 설명 (통합본)

기준: `02_complaint_app.sql`의 테이블 8개 (칸 이름과 값 목록은 그대로)

## 1. 파일과 건수

- `users.json` (31건) : 시민 5명, 담당자 26명 (부서마다 1명)
- `complaints.json` (35건) : 새로 쓴 민원 10건 (번호 1~10) + 진짜 민원 25건 (번호 11~35), 처리 기한 `due_at` 포함
- `messages.json` (34건) : 답변 묶음 33개, 추가 문의 묶음 1개
- `message_versions.json` (38건) : 답변 글의 버전
- `ai_jobs.json` (11건) : 새로 쓴 민원 10건에만 있음 (8번 민원은 2번 실행)
- `ai_results.json` (8건) : 성공한 작업의 결과
- `job_events.json` (53건) : AI 작업 중 생긴 일
- `complaint_events.json` (99건) : 담당자가 한 일(처리 이력)과 원문 열람 감사 기록

## 2. 샘플의 출처

- 진짜 민원 25건 : 크롤링한 청주시 민원 JSON(`공개_민원_사례.json`)에서 골랐다.
  - 제목, 요지, 답변이 원본과 한 글자도 다르지 않다.
  - 제목은 `title`, 요지는 `body`, 답변은 `message_versions.body`에 들어 있다.
  - 담당자는 그 민원의 원래 부서 이름을 가진 담당자 사용자다.
  - `category`와 `district`는 NULL이다.
  - 5,015건 중 개인정보 의심, 특정인 비난, 정치적 내용 등을 걸러 25건이 남았다. 부서는 25곳이 모두 다르다.
- 새로 쓴 민원 10건 : 처리 상태 10가지를 1건씩 보여 주려고 직접 쓴 예시다.
  - 소재는 청주시 JSON의 비슷한 사례를 참고했지만 글은 새로 썼다.
  - AI 초안, 안내 글, 작업 기록 문구도 모두 직접 쓴 예시다. (AI 연결 전)

## 3. 연결 구조

- 모든 번호(`id`)는 JSON 안에 직접 적었고, 서로 가리키는 번호(`author_id`, `complaint_id`, `job_id`, `actor_id` 등)가 이 번호와 맞다.
- 새로 쓴 민원 10건은 처리 상태 10가지를 1건씩 갖는다.

- 1번 : AI검토 (단계 2)
  - AI 작업 : `queued` (대기)
  - 답변 글 : 없음
  - 처리 이력 : 없음
- 2번 : 배정완료 (단계 3)
  - AI 작업 : `succeeded`
  - 답변 글 : AI 초안 (초안 상태)
  - 처리 이력 : 배정
- 3번 : 처리중 (단계 4)
  - AI 작업 : `succeeded`
  - 답변 글 : AI 초안, 담당자 수정본 (미게시)
  - 처리 이력 : 배정, 열람, 계획, 조치, 기한연장
- 4번 : 보완요청 (단계 4)
  - AI 작업 : `succeeded`
  - 답변 글 : AI 초안, 담당자가 쓴 보완 요청문 (게시)
  - 처리 이력 : 배정, 열람, 조치
- 5번 : 답변완료 (단계 5)
  - AI 작업 : `succeeded`
  - 답변 글 : AI 초안, 담당자 답변 (철회), 정정 답변 (게시), 시민 추가 문의 1건
  - 처리 이력 : 배정, 열람, 계획, 조치
- 6번 : 총괄검토 (단계 2)
  - AI 작업 : `failed` (오류 문장 있음)
  - 답변 글 : 없음
  - 처리 이력 : 없음
- 7번 : 조정대기 (단계 3)
  - AI 작업 : `succeeded`
  - 답변 글 : AI 초안 (초안 상태)
  - 처리 이력 : 배정, 열람, 협조요청, 원문열람
- 8번 : 재배정 (단계 2)
  - AI 작업 : 1차 `superseded`, 2차 `succeeded` (`faq_answer`)
  - 답변 글 : FAQ 안내 (초안 상태)
  - 처리 이력 : 배정, 반려
- 9번 : 반려 (단계 2)
  - AI 작업 : `succeeded`
  - 답변 글 : AI 초안 (초안 상태)
  - 처리 이력 : 배정, 열람, 반려
- 10번 : 소관외 종결 (단계 5)
  - AI 작업 : `succeeded` (`human_handoff`)
  - 답변 글 : 담당자가 직접 쓴 답변 (게시)
  - 처리 이력 : 배정, 열람

- 진짜 민원 25건은 배정, 열람, 조치 이력을 3건씩 갖는다. (`complaint_events` 75건)
- 결과 종류 : `department_suggestion` 6, `faq_answer` 1, `human_handoff` 1
- 5번 민원은 답변 수정 기록 화면을 보여 주기 위해 버전이 3개다. (AI 초안 → 철회된 답변 → 정정 답변)
- 8번의 `faq_answer`는 `자주_묻는_민원.json`의 "동물 찻길 사고(로드킬) 사체 처리"(`source_id` 1302560)를 근거로 한다.
- `ai_results.evidence`의 근거 16개는 모두 원본 JSON의 `source_id`와 `source_url`이 맞다.

### 처리 기한 (`complaints.due_at`)

- 모든 민원은 접수 후 5일이다.
- 3번 민원은 기한 연장 이력이 있어 접수 후 8일이다.

### 처리 이력 (`complaint_events`) 구성 99건

- 배정 33, 열람 31, 조치 28, 반려 2, 계획 2, 협조요청 1, 기한연장 1, 원문열람 1
- 배정은 시스템이 한 일이라 `actor_id`가 NULL이고, 나머지는 담당자 번호가 들어 있다.
- 담당자가 한 일(배정, 반려, 협조 대기)은 `job_events`에 두지 않고 `complaint_events`에 둔다.

## 4. 비워 두거나 예시로 채운 칸

- `ai_results.department_id`는 NULL (부서 번호 변환 자료가 아직 없음), 부서 이름만 채움
- `ai_results.confidence`는 직접 쓴 예시 값 (0.46 ~ 0.91). 진짜 민원 25건은 AI 결과가 없어 비어 있음
- `ai_jobs.stage`는 NULL (AI 쪽 단계 이름이 정해지기 전)
- `ai_results.evidence`의 `content_hash`는 null (계산 방법을 모름)
- `model_version`, `policy_version`, `prompt_version`은 모두 `sample`
- 새로 쓴 민원 10건은 접수일을 2026-10-26 ~ 10-30으로 했고, 시각은 한국 시간(+09:00)이다.
- 민원번호는 접수일 기준 `YYYY-MMDD-NNNN`이고, 같은 날은 접수 순서대로 번호를 붙였다.

## 5. 검사한 것

실제 PostgreSQL 16에 `02_complaint_app.sql`로 테이블 8개를 만들고, JSON 전체를 넣어 보았다.

- 오류 없이 모두 들어감 (값 목록, 글자 수, 민원번호 형식, 중복 금지, 외래 키 포함)
- DB가 막아 주지 않는 연결 오류 28가지도 따로 검사해 모두 0건
  - 게시 버전이 같은 묶음의 글인지, 게시 상태가 하나뿐인지
  - AI 작업과 결과가 서로 가리키는 번호가 맞는지
  - 시각 순서(접수, 글 작성, 게시, 철회, 작업 기록, 처리 이력)가 맞는지
  - 작성자는 시민, 담당자와 게시자와 처리 이력의 한 사람은 담당자인지
  - 단계 5인 민원에 게시된 답변이 있는지
  - 기한이 접수 시각보다 빠르지 않은지, 기한이 비어 있지 않은지
  - 담당자가 있는 민원에 배정 이력이 있는지

## 6. 쓸 때 주의

- 번호 칸이 자동 번호(`GENERATED ALWAYS`)라서 DB에 넣을 때는 `OVERRIDING SYSTEM VALUE`가 필요하다.
- 서로 가리키는 칸(`ai_jobs.result_id`, `ai_results.adopted_version_id`, `messages.published_version_id`)은 가리키는 행이 먼저 있어야 해서, 나머지를 넣은 뒤에 값을 채워야 한다.
- 넣는 순서 : `users`, `complaints`, `ai_jobs`, `ai_results`, `messages`, `message_versions`, `job_events`, `complaint_events`
- 화면(HTML)에서 쓸 때는 시각이 `2026-10-30T09:12:00+09:00` 형식의 글자다.
- 프로토타입 HTML(`프로토타입_DB샘플.html`)에는 이 JSON 8개가 들어 있다. JSON을 고치면 `build_html.py`로 HTML을 다시 만들어야 한다.
