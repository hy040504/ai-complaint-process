# 변경 이력

## 2026-11-21

- **시연 비밀번호 환경변수 이전 ([CASE-123](docs/cases/사례-123-시연-비밀번호-환경변수-이전과-푸시-배포-2026-11-22.md)):** 공개 저장소에 올라갈 뻔한 시연 계정 비밀번호를 코드·테스트·문서에서 제거하고 `COMPLAINT_DEMO_ACCOUNT_PASSWORD` 환경변수로만 받게 했다(없으면 계정을 만들지 않음). 푸시 전 로컬 커밋 기록에서도 값을 지웠고, 시연 로그인은 서버에서 이전과 같게 동작한다.
- **폴더 재배치 ([CASE-122](docs/cases/사례-122-plan을-docs-plans로-db를-rag-db로-재배치-2026-11-22.md)):** 루트 `plan/`을 `docs/plans/`로, `db/`를 `rag/db/`로 옮겨(`git mv`로 이력 보존) 루트 폴더를 줄였다. 링크 183개를 새 위치 기준으로 재계산해 깨진 링크가 0이며, `rag/`는 패키지라 이름·위치를 유지했다. 사례·CHANGELOG의 옛 경로 표기는 이력이라 그대로 둔다.
- **글자 대비 보정·홈/모바일 개선·README 쉬운 개편 ([CASE-121](docs/cases/사례-121-글자대비-보정과-홈·모바일-개선-및-README-쉬운-개편-2026-11-22.md)):** 라이트 글자 대비 미달 270개를 규칙 단위로 고쳐 시민·담당자 5개 화면의 라이트·다크·모바일 4조합에서 0으로 만들었고(`--muted` 토큰·활성 단계 숫자 버그 포함), 홈 질문 입력창을 위로 올리고 작은 화면 헤더의 숨겨진 로그인 버튼을 되살렸다. README를 577줄에서 152줄로 줄여 쉬운 말로 다시 쓰고, 이전 내용은 `docs/기술_개요.md`로 보존했으며 게스트·민원인·담당자 비교 그림·흐름 그림·화면 캡처 8장을 넣었다. `ui test` `65`. 시연 계정이 공개 저장소에 올라갈 위험은 미결이다.
- **게스트 접수를 공개로 변경(2026-11-22):** 게스트가 낸 민원은 비공개 요청도 서버가 공개로 바꿔 민원 게시판에 올린다. 작성 화면은 "게시판에 공개, 개인정보 쓰지 마세요"로 안내하고, 소유자만 수정·삭제할 수 있다. 이미 접수된 게스트 민원은 그대로다. `pytest` `212`·`ui test` `62`.
- **디자인 토큰·공통 상태 칩·동적 효과 ([CASE-120](docs/cases/사례-120-디자인-토큰과-공통-상태칩-모션-적용-2026-11-21.md)):** `tokens.css`(색·상태·모서리·그림자·간격·모션)와 `design.css`를 추가해 라이트의 청록과 다크의 파랑으로 갈라져 있던 브랜드색을 통일하고, 4곳에 중복되던 상태 배지 정의를 한 곳(5.4:1 이상)으로 모았으며 검정이던 담당자 출처 태그를 브랜드색으로 바꿨습니다. `motion.js`로 호버 들림·눌림·부유·맥동·라이브 점·스켈레톤·화면 진입·숫자 카운트업·새 민원 행 플래시를 넣고 동작 줄이기에서는 모두 멈춥니다. 정리 스크립트가 `:is(a, b)`의 쉼표에서 선택자를 잘라 다크 테마가 깨진 것을 전후 스크린샷 비교로 찾아 고치고 `css-integrity.test.mjs`를 추가했습니다. 이어서 모서리 164개를 4단계 토큰으로, 다크 색 911개를 190개 토큰으로 변수화하고 사이드바 활성 막대를 추가했다(`ui test` `59`). 제목 3종을 타입 스케일 토큰(`--ty-*`) 한 곳으로 모으고 카드 그림자·행 호버를 통일했다(`ui test` `61`). 카드류 11종의 흰 배경·테두리를 `design.css` 공통 규칙으로 모았다(`ui test` `62`, 라이트·다크 픽셀 비교 통과). 서버에는 아직 배포하지 않았습니다.

- **비로그인 게스트 접수와 방문자 홈 ([CASE-119](docs/cases/사례-119-비로그인-게스트-접수와-방문자-홈-2026-11-21.md)):** 시민 사이트는 로그인하지 않아도 홈·민원 작성·AI 도우미·안내가 보이고, 접수하거나 AI 도우미를 쓰는 순간 서명 세션 기반 게스트(`POST /api/v1/auth/guest`, `Actor.guest`)가 자동으로 시작됩니다. 게스트 민원은 비공개로 강제하고 IP당 시간당 10회·게스트당 5건으로 제한하며, 로그인·가입하면 계정으로 옮겨집니다. 로그인 모달은 탭이 하나뿐이면 탭 막대를 없애고 제출 버튼을 단순히 "로그인"으로 바꿨습니다. `pytest` `208 passed`·`ui test` `39`.

- **시연 민원 웹 무료 외부 공개 ([CASE-118](docs/cases/사례-118-무료-외부-공개-Cloudflare-Quick-Tunnel-2026-11-21.md)):** 서버 `navy2025`의 민원 웹(`:5000`)만 Cloudflare Quick Tunnel로 공개하고(응대 검사기·검색 API는 비공개), `cloudflared`는 SHA-256 다이제스트 검증 후 설치해 사용자 서비스 `cheongju-tunnel`로 등록했습니다. HTTPS 요청에 `Secure` 쿠키·HSTS, 전체 응답에 `X-Frame-Options`·`Referrer-Policy`를 추가하고, `CF-Ray` 헤더가 있는 프록시 경유 요청은 `/docs`·`/swagger`·`/openapi*`·`/design/*`를 `404`로 숨깁니다. `main`을 `origin/main`에 push했습니다. `pytest` `201 passed`. 주소는 재시작마다 바뀌고 IP 속도 제한은 없습니다.

- **시민·담당자 사이트 분리와 원격 서버 배포 ([CASE-117](docs/cases/사례-117-시민·담당자-사이트-분리와-원격-서버-배포-2026-11-21.md)):** 시민 `/`와 담당자 `/staff/`를 별도 진입 화면·허용 경로·사이트별 세션 쿠키(`cj_citizen`·`cj_staff`)로 분리하고, 담당자 계정을 시민 사이트에서(또는 반대로) 로그인하면 `403`으로 거부합니다. 담당자 계정 추가·비밀번호 재설정·비활성화용 Flask CLI(`create-staff`·`reset-password`·`deactivate-user`·`activate-user`·`list-users`)를 추가했습니다. `main`을 `llm` 상태 우선으로 `origin/main`과 병합(로컬)하고, `scripts/ops/deploy-remote.ps1`로 서버 `navy2025`에 배포해 시연 로그인을 끄고 시드 계정 비밀번호를 교체했습니다. `pytest` `199 passed`·`ui test` `39`·mypy 0오류. 원격 push와 LLM 키 설정은 하지 않았습니다. [배포 안내](docs/harness/원격_서버_배포.md)

- **프로젝트 폴더·파일 구조 정비 ([CASE-116](docs/cases/사례-116-프로젝트-폴더-파일-구조-정비-2026-11-21.md)):** `scripts/`를 `ops`·`run`·`eval`·`reports`로 분류하고 영문 이름 하나로 통합했으며, 루트 실행 파일을 `bin/`으로, `docs/report`·`docs/test`를 `docs/reports/{daily,analysis}`로, Swagger PDF를 `docs/api/`로, 초기 기획 자료를 `plan/archive/`로 옮겼습니다. `db/`는 `sql`·`samples`·`docs`로 정리하고 `rag/origin/`과 중복이던 JSON을 제거했으며, `src/rag`는 `src/search_client`로 이름을 바꾸고 `repository.py`·`service.py`·`place_tool.py`의 일부를 분리했습니다. 동작 변경 없음. `pytest` `189 passed`·`rag` `49 passed`·mypy 0오류·링크 검사 깨짐 0. Linux 셸 스크립트는 `bash`가 없어 검증하지 못했습니다.

- **민원 파일 첨부 업로드 · 이미지 EXIF 자동 제거 · 비공개 권한 격리 구현 ([CASE-115](docs/cases/사례-115-민원-파일첨부-업로드-EXIF제거-권한격리-구현-2026-11-21.md)):**
  - **매직바이트 검증 · 무의존성 EXIF 제거 · 안전 저장소 (`src/complaints/attachments.py`·`config.py`·`http.py`·`src/app.py`):** 외부 이미지 라이브러리 없이 표준 라이브러리만으로 `JPG`·`PNG`·`WebP`·`PDF` 매직바이트 검증(최대 5MB × 민원당 5개, 위조 확장자 차단)과 JPEG `APP1/APP2/COM`·PNG `eXIf/tEXt/iTXt/zTXt/tIME`·WebP `EXIF/XMP` 메타데이터 자동 제거를 구현했습니다. 운영 파일은 Git 제외 `.web-data/uploads/`에 추측 불가 평면 키로 원자 저장하며, `protect_api()`에서 첨부 업로드 외 모든 일반 JSON API의 기존 `64 KiB` 한도(`413`)를 보존했습니다.
  - **PostgreSQL `attachments` · 권한 격리 API · UI (`schema/complaint_app.sql`·`models.py`·`repository.py`·`service.py`·`api.py`, `ui/src/attachments.js`·`app.js`·`staff.js`·`icons.js`·`styles.css`·`themes.css`):** `POST/GET/DELETE /api/v1/complaints/{complaint_id}/attachments*`를 추가해 비공개 민원 첨부의 타 시민 접근을 `404`로 차단하고 CSP 샌드박스·`nosniff` 헤더·답변 게시 후 삭제 금지(`409`)·민원 영구 삭제 시 디스크 연쇄 정리를 강제했습니다. `#/citizen/write` 드래그 앤 드롭 업로드, 시민·담당자 상세 썸네일 갤러리·이미지 라이트박스·PDF 다운로드·담당자 큐 `첨부 N` 배지를 라이트/다크 테마로 연동했습니다.
  - **Swagger PDF 및 전수 검증:** [`청주톡톡_민원_업무_API_Swagger.pdf`](docs/api/청주톡톡_민원_업무_API_Swagger.pdf) **36경로 · 44오퍼레이션 (`1,596,061`바이트)** 갱신, `black` 통과, `mypy` **45모듈 0오류**, `RUN_PG_TESTS=1 pytest src/tests` **`189 passed`**, `ui check 29 / test 36/36`, `:5000` 실서버 PostgreSQL·디스크 + Headless Edge CDP(EXIF 제거·라이트박스·담당자 열람·영구 삭제 후 고아 파일 `0건`·콘솔 오류 `0건`) 통과.

- **시민 다중 턴 AI 챗봇(PostgreSQL 영속 저장) 및 담당자 RBAC 통계 대시보드·통합 검색·안전 CSV 내보내기 구현 ([CASE-114](docs/cases/사례-114-시민-다중턴챗봇-PG영속저장과-담당자-통계대시보드-CSV내보내기-구현-2026-11-21.md)):**
  - **시민 다중 턴 챗봇 및 PostgreSQL 세션 저장 (`src/complaints/schema/complaint_app.sql`·`models.py`·`chat.py`·`repository.py`·`service.py`·`api.py`, `src/assist/policy.py`·`pipeline.py`·`__init__.py`, `ui/src/chatbot.js`·`app.js`·`citizen.css`·`themes.css`):** `complaint_app.chat_sessions`·`chat_messages`(`ON DELETE CASCADE`, 안전 투영 `CitizenChatResponse` JSON만 저장)와 `GET/DELETE /api/v1/citizen/chat/sessions*`를 추가했습니다. `build_multiturn_chat_context()`로 추가 LLM 호출 없이(0ms) 짧은 후속 질문·관할 보완에 직전 주제와 구를 보강하고(주제 전환·타 지자체 오염 차단), `conversation_history`를 `PREFIX-01`/`02` 가변 `user` JSON에만 주입해 Prefix Caching을 보존했습니다. 로그인 민원인은 PostgreSQL 자동 저장·복원·삭제(타인 404·담당자 403 격리), 비로그인 시연 시민은 브라우저 `sessionStorage` 임시 저장 + `"로그인하면 대화가 저장됩니다"` 안내를 제공하며 다중 턴 시민 발화를 민원 작성 폼으로 일괄 이관합니다.
  - **담당자 RBAC 통계 대시보드·큐 통합 검색·안전 CSV 내보내기 (`src/complaints/models.py`·`service.py`·`api.py`, `ui/src/staff-stats.js`·`staff.js`·`app.js`·`icons.js`·`staff.css`·`themes.css`):** `GET /api/v1/staff/stats`(총괄 전체 vs 부서 담당자 미배정+소속 부서 RBAC 강제, `includeSynthetic` 토글, 11종 운영 KPI·5종 드릴다운 분포·7테이블 요약)와 `GET /api/v1/staff/complaints/export.csv`(UTF-8 BOM·엑셀 수식 주입 `=+-@\t\r` 중화·업무 메타데이터 15열·미게시 초안/순화 완전 제외)를 구현했습니다. `#/staff/stats` 클릭형 드릴다운 차트와 큐 통합 검색(제목·본문·ID·부서)·AI 판정 필터·4종 정렬·시연 토글·`queueRows` 담당자 실명(`c.assigneeName`) 수정을 반영했습니다.
  - **Swagger PDF 및 전수 검증:** [`청주톡톡_민원_업무_API_Swagger.pdf`](docs/api/청주톡톡_민원_업무_API_Swagger.pdf) **34경로 · 41오퍼레이션 (`1,515,107`바이트)** 갱신, `black` 통과, `mypy` **43모듈 0오류**, `RUN_PG_TESTS=1 pytest src/tests` **`186 passed`**, `rag/tests` **`49 passed(3 skipped)`** + `rag.verify` **`passed: true`**, `regression_112_rules.py` **실패 0**, `ui check 27 / test 33/33`, `:5000` 실서버 PostgreSQL + Headless Edge CDP(다중 턴 DB 저장/복원/삭제·RBAC 통계·드릴다운·CSV·라이트/다크 콘솔 오류 `0건`) 통과.

## 2026-11-20

- **100건 실증 세부 문제 패치 및 `:5010` Codex CLI 전용 신규 100건 실증 평가 (`99/100, 99.0%`) ([CASE-113](docs/cases/사례-113-100건실증-세부문제-패치와-Codex-CLI-신규100건-실증평가-2026-11-20.md)):**
  - **명확 불가 FAQ · JSON 자동 복구/재시도 · Codex 오류 축약 · 지연/폴백 개선 (`docs/harness/prompts/PREFIX-01.txt`, `src/llm/settings.py`·`complete.py`, `src/assist/pipeline.py`, `.env.example`):** `PREFIX-01.txt`에 명확한 불가/제외 FAQ 안내 지침·고정 예시(`faq-demo-4`)를 추가해 `A24` 과도 보류를 해소했습니다. `parse_json_object()`에 경량 JSON 자동 복구(`_repair_json_text`)와 `PREFIX-03`/`04` 파싱·스키마 실패 1회 자동 재시도(`N32` 대응), Codex CLI 실패 시 핵심 `ERROR:` 240자 발췌(`_extract_codex_error`, `A15` 24KB 프롬프트 덤프 차단), EXAONE `decision` `max_tokens=8192` 상한(`EXAONE_DECISION_MAX_TOKENS`) 및 타임아웃 시 `low`/`4096` 1회 자동 재시도(`N18` 대응), `codex_cli` `staff_draft` 불필요 MCP 기동 생략(`_disable_mcp`), 미고정(`provider=None`) 한도/타임아웃 시 1회 투명 폴백(`COMPLAINT_LLM_AUTO_FALLBACK`, 명시 고정 호출 전환 금지)을 적용했습니다.
  - **`:5010` Codex CLI 전용 신규 100건 실증 ([`scripts/eval/live_eval_100_codex.py`](scripts/eval/live_eval_100_codex.py) · [`lab-5010-eval-100-codex-20261120.json`](rag/reports/lab-5010-eval-100-codex-20261120.json)):** `patch_reverify_20`(20건) + 기존 평가셋과 비중복 신규 청주 민원 `fresh_codex_80`(80건) = 총 100건을 전수 `codex_cli`(`gpt-6-luna`)로 실측해 **`99 / 100 (99.0%)`**(`patch_reverify_20` **20/20** · `fresh_codex_80` **79/80** · B/C/D/E축 **100%** · `staff_draft` **71/71** · `automatic_transfer=True` **0건** · 평균 **`16.11s`** / 최대 `29.33s` / 조기차단 `0.013s`)를 달성했습니다.
  - **사후 감사 후속 패치 및 표적 5건 실서버 재검증 (`docs/harness/prompts/PREFIX-01.txt`, `src/llm/place_tool.py`, `src/tests/test_place_tool.py`):** 사후 감사로 포착된 `K12`(`부모`·`기관` 불용어 16종 + 시설물 8종), `K17`(`PREFIX-01` 일반 이용 주의사항 vs 담당자 상담 예외 분리), `K31`·`K33`(`청주시` 접두 단조 정규화·본문 동명 일치 가산·`(예정)`/외부 브랜드 입점 지점 감점·복합시설 본체 접미어 보강)을 패치했습니다. `:5010` 표적 5건 재검증(`K17` `faq_answer/ok`, `K12` `place=None`, `K31` `청주시농수산물도매시장(봉명동)`, `K33` `지웰시티몰II(복대동)`, `A35` 예외 비회귀) **`5/5`** 및 `RUN_PG_TESTS=1 pytest src/tests` **`181 passed`**, `mypy` **44모듈 0오류**, `regression_112_rules.py` **실패 0**, `ui check 25 / test 29/29`, `rag/tests` **49 passed** · `rag.verify` **`passed: true`**를 확인했습니다.
  - **상세 테스트 분석 보고서 정리 ([`청주_민원_100건_Codex_상세분석보고서_2026-11-20.md`](docs/reports/analysis/청주_민원_100건_Codex_상세분석보고서_2026-11-20.md) · [6쪽 PDF](docs/reports/analysis/청주_민원_100건_Codex_상세분석보고서_2026-11-20.pdf)):** 4단계 누적 실증 추이 및 Codex 100건 판정·지연시간 SVG 차트 2종과 전수 감사·100건 상세표를 [`scripts/reports/analysis_report_100_codex.py`](scripts/reports/analysis_report_100_codex.py)로 생성했습니다.

- **실시간 SSE · 시민 챗봇 · 로그인 · 7테이블 정규화 후속 품질 검수 및 최적화 ([CASE-112](docs/cases/사례-112-실시간SSE-시민챗봇-로그인-7테이블정규화-후속품질검수와-최적화-2026-11-20.md)):**
  - **데이터 무결성 · 보안 · 메모리 최적화 (`src/complaints/repository.py`·`service.py`·`events.py`·`auth.py`):** 불변 이력 테이블 `message_versions`의 `ON CONFLICT`를 `DO NOTHING`으로 교정해 후속 담당자 변경 시 과거 버전의 `actor_user_id`·`context_version` 덮어쓰기 및 불필요한 WAL 갱신을 제거했습니다(`test_auth_and_normalized_db.py` 불변성 회귀 추가). `ComplaintService.change()`에 `FOR UPDATE` 잠금 내부 `guarded_action` RBAC/소유자 재검증을 추가해 TOCTOU를 차단하고, `StaffEventBroker._replay_since_locked()`로 중복 커서 판정을 통합했으며 `LoginRateLimiter` 만료 항목 자동 정리(512건 초과 시)를 추가했습니다.
  - **UI 문구·주석 일치화 및 Swagger 배지 개선 (`ui/src/citizen.js`·`app.js`, `src/complaints/swagger_page.py`):** 시민 홈·서비스·소식 카드·이용 안내 FAQ의 구 문구(`실제 AI는 아직 연결되지 않았어요` 등) 5곳과 `nextStepBox` 구 주석을 실제 구현(RAG+LLM 도우미·아이디/비밀번호 로그인)에 맞게 교정하고, 담당자 상세 게시자 표시(`c.assigneeName`)와 Swagger 포털 세션 배지(`displayName (role)`)를 실계정 기준으로 통일했습니다.
  - **최종 전수 검증:** `black --check` · `mypy` **44모듈 0오류**, `RUN_PG_TESTS=1 pytest src/tests` **`179 passed`**, `rag/tests` **`49 passed(3 skipped)`** + `rag.verify` **`passed: true`**, `regression_112_rules.py` **실패 0**, `ui check 25 / test 29/29`, 전수 주석·JSDoc·링크 깨짐 `0건`, 실서버 `:5000`·`:5010`·`:8007` 및 Headless Edge CDP 검증 완료.

- **민원인·담당자 아이디/비밀번호 로그인 및 PostgreSQL 7테이블 정규화 구현 ([CASE-111](docs/cases/사례-111-운영-본인담당자-인증과-PostgreSQL-7테이블-정규화-구현-2026-11-20.md)):**
  - **민원인·담당자 아이디/비밀번호 로그인 (`src/complaints/auth.py`·`models.py`·`http.py`·`service.py`·`api.py`, `ui/src/auth.js`·`store.js`·`citizen.js`·`staff.js`·`app.js`·`styles.css`·`themes.css`):** 초기 구현한 2단계 휴대전화 OTP 본인확인 흐름을 사용자 지시에 따라 제거하고, 민원인(`citizen_01`)·담당자(`staff_admin`·`staff_seowon`·`staff_heungdeok`) 아이디·비밀번호(`scrypt`·5회 연속 실패 60초 `429` 잠금·세션 회전) 로그인(`POST /api/v1/auth/login`, `/logout`, `GET /api/v1/auth/me`)과 아이디·비밀번호·이름만 받는 민원인 간단 가입(`POST /api/v1/auth/register`), 담당자 소속 부서 범위 RBAC(`403 department_scope_forbidden`), 2탭 로그인 모달(`민원인 로그인` | `담당자 로그인`) 및 다중 사용자 비공개 민원 격리로 간소화했습니다.
  - **PostgreSQL 7테이블 정규화 (`src/complaints/schema/complaint_app.sql`·`repository.py`·`api.py`):** 기존 `complaints.payload` JSONB·생성 칼럼 5개·CHECK 호환성을 유지하면서 `users`(10컬럼: `verified`·`phone_last4` 제거)·`complaints`·`messages`·`message_versions`·`ai_jobs`·`ai_results`(`CHECK (automatic_transfer = false)` 및 `complaint_rag.department_directory` 교차 스키마 FK)·`job_events`(`ON DELETE CASCADE`) 7개 핵심 테이블을 구축했습니다. 민원 생성·수정 시 동일 트랜잭션 원자적 동기화, 기동 시 기존 행 무손실 자동 백필, 담당자 전용 SQL 집계 API(`GET /api/v1/staff/db-summary`)를 추가했습니다.
  - **Swagger PDF 및 전수 검증:** [`청주톡톡_민원_업무_API_Swagger.pdf`](docs/api/청주톡톡_민원_업무_API_Swagger.pdf) **30경로 (`1,308,396`바이트)** 갱신, `mypy` **44모듈 0오류**, `RUN_PG_TESTS=1 pytest src/tests` **`179 passed`**, `ui check` **25** · `ui test` **`29 / 29`**, 실서버 `:5000` PostgreSQL `users` 10컬럼/7테이블 및 Headless Edge CDP 2탭 로그인(`citizen_01`·`staff_seowon`) E2E(런타임 오류 `0건`) 통과.

- **담당자 실시간 SSE 푸시(`BE07`·`UI08`) 및 시민 AI 챗봇 실연결 구현 ([CASE-110](docs/cases/사례-110-담당자-실시간-SSE-푸시와-시민-AI-챗봇-실연결-구현-2026-11-20.md)):**
  - **담당자 실시간 SSE 이벤트 브로커·API·UI (`src/complaints/events.py`·`service.py`·`api.py`·`http.py`, `ui/src/realtime.js`·`app.js`·`staff.css`·`themes.css`):** 단조 증가 커서·256건 링 버퍼·`Last-Event-ID` 재전송·`resync_required`·15초 하트비트를 제공하는 `StaffEventBroker`와 담당자 전용 `GET /api/v1/staff/events`(익명 401·시민 403, 민감 본문/초안 미포함)를 구현했습니다. `#/staff/monitor`의 1.5초 폴링을 실시간 `EventSource`(단절 시 3초 폴링 자동 대체·복구 시 원복·편집 초안 보호)로 전환했습니다.
  - **시민 민원 도우미(`#/citizen/assistant`) 실시간 RAG+LLM 연결 (`src/complaints/chat.py`·`models.py`·`api.py`, `src/assist/pipeline.py`, `ui/src/chatbot.js`·`app.js`·`citizen.css`·`themes.css`):** `include_staff_outputs=False` 최적화로 직원용 `PREFIX-03/04` 호출을 생략하고, `POST /api/v1/citizen/chat(/stream)`에서 `CitizenChatResponse` 투영으로 `staffDraft`·`sanitize`·`codex`·`cases`·`modelRaw`를 구조적으로 배제했습니다. 시민 화면에 실시간 NDJSON 진행 안내, FAQ 출처·참고 부서·관할 구 선택·`새 대화`·민원 작성 폼 구 자동 채움을 연동했습니다.
  - **Swagger PDF 및 전수 검증:** [`청주톡톡_민원_업무_API_Swagger.pdf`](docs/api/청주톡톡_민원_업무_API_Swagger.pdf) 25경로 갱신, `mypy` 41모듈 **0오류**, `RUN_PG_TESTS=1 pytest src/tests` **`176 passed`**, `ui check` **23** · `ui test` **`27 / 27`**, `:5000` Headless Edge CDP 실시간 SSE·시민 챗봇·작성 이관 E2E(콘솔 오류 `0건`) 통과.

- **패치 후 `:5010` 100건 실증 재검증(`98/100, 98.0%`) 및 생활 기반시설 노이즈 보강 ([CASE-109](docs/cases/사례-109-패치후-100건-실증재검증-98퍼센트와-생활시설-노이즈보강-2026-11-20.md)):**
  - **100건 실서버 재검증 ([`scripts/eval/live_eval_100_recheck.py`](scripts/eval/live_eval_100_recheck.py) · [`lab-5010-eval-100-20261120.json`](rag/reports/lab-5010-eval-100-20261120.json)):** 기존 문제·노이즈·회귀 60건(`reverify_60`)과 신규 변형·경계 스트레스 40건(`fresh_40`, `N01~N40`)을 `:5010` 실서버(`codex_cli` 50 · `exaone_api` 50)로 호출해 **`98 / 100 (98.0%)` 통과**(실응답 `98 / 99, 99.0%`)를 확인했습니다. `CASE-105` 미통과 10건(`10/10`)·장소 노이즈 13건(`13/13`, 재발 0건)·신규 4개 구 도로+번지(`4/4`)·도+시 약칭 조기차단(평균 `0.011s`)·`automatic_transfer=True` `0건`을 검증했습니다.
  - **생활 기반시설 일반명사 불용어 보강 (`src/llm/place_tool.py`, `src/tests/test_place_tool.py`):** 100건 재검증 `N28`에서 포착된 `"하수구"` 민간 업체 오매칭(`청주하수구막힘변기뚫음누수탐지`) 방지를 위해 `_STOP_WORDS`에 `하수구·배수구·하수관·오수관·우수관·정화조·전신주·변압기·과속방지턱·가드레일·안전펜스·안전난간·중앙분리대·적치물` 14종(기존 `"난간"` 중복 제거로 `351종` 고유화)과 단위 회귀 테스트를 추가해 `src/tests` **`172 passed`**를 확인했습니다.
  - **최적화 · 전수 주석/JSDoc · 문서 디자인 정비 (`scripts/eval/live_eval_100_recheck.py`, `README.md`, `src/lab_web/README.md`, `docs/harness/README.md`):** `live_eval_100_recheck.py`의 EXAONE 직렬/병렬 결과 기록·로그·저장을 `_record_and_log_exaone()`으로 통합하고 동시 레인 파일 경합을 막는 `threading.Lock`(`state_lock`)과 `_run_one` Google docstring(`Args:`/`Returns:`)을 보완했습니다. 추적 Python **115개**·비테스트 JS **17개** 전수 주석/JSDoc 누락 `0건`을 확인하고, `README.md`에 **3단계 실증 추이 비교표(`112건 83.9% → 200건 95.0% → 패치 후 100건 98.0%`)** 및 관련 문서 동기화를 마쳤습니다.

- **11/19 업무보고 PDF 공용화·저장소 전수 주석/JSDoc·`README`/`docs` 가독성 개편 ([CASE-108](docs/cases/사례-108-11월19일-업무보고-코드공통화-전체주석-최종검증-2026-11-20.md)):**
  - **공용 UI 캡처 헬퍼 통합 (`scripts/reports/report_common.py`, `daily_report_20261118.py`, `daily_report_20261119.py`):** `render_ui_captures_html()`로 11/18·11/19 UI 캡처 그리드 조립 중복을 제거하고 11/18 불필요 1줄 래퍼(`extract_unique_ui_images`) 및 11/19 보고서 내 상태 코드 표기`(400)`를 삭제해 8쪽 보고서(`711,758 bytes`)를 재생성했습니다.
  - **저장소 전수 한국어 docstring · 타입 정리 (`db/load_samples.py`, `scripts/eval/compare_assist.py`, `src/tests/*`):** 추적 중인 114개 `.py`·21개 `.js` 파일 전수 검사 후 `db/load_samples.py`(모듈+7함수 Google docstring·한글화), `scripts/eval/compare_assist.py`(3함수 `Args:`/`Returns:`·`mypy` 2오류 해소), 테스트 내부 모의 헬퍼 6건(`test_assist_api.py`·`test_backend_split.py`·`test_lab_web.py`·`test_rag_tool.py`)을 모두 보완했습니다.
  - **`docs/README.md` · `README.md` 가독성 개편 및 최종 검증:** 장문 벽돌 문단을 4개 불릿으로 분리하고 `CASE-108`·`11/19 8Pages` 배지 반영 후 `black`·`mypy`·전수 주석/JSDoc·135개 Markdown 링크 깨짐 `0건`·`171`/`49`/`22`/규칙 `112` 검증을 마쳤습니다.

- **패치 정비 · 한국어 주석/JSDoc · 코드 최적화 · README/하네스 문서 디자인 정비 ([CASE-107](docs/cases/사례-107-패치정비-주석JSDoc-코드최적화-README디자인-최종검증-2026-11-20.md)):**
  - **중복 추론·미사용 제거 및 타입 강화 (`src/llm/place_tool.py`, `src/assist/district.py`, `eval_set.py`, `constants.py`, `pipeline.py`, `complaints/demo_data.py`):** `_build_place_candidates(text, road_num_pairs=...)`로 `lookup_navermap_place`의 `_extract_road_number_pairs` 중복 정규식 패스를 제거하고 `_append_unique_place()` 공용 헬퍼·`place_obj["gu"]` 재활용으로 `_parse_navermap_items` 중복을 정리했습니다. `district.py`는 `_fallback_district_after_lookup()`으로 지도→사례 색인 fallback을 통합했으며, `eval_set.py` `load_eval_spec` 타입 주석으로 `mypy --strict` `0` 오류를 맞추고 미사용 import(`normalize_district`, `timedelta`, `OpenAPI`) 및 PEP-484 `constants.py` 명시 재내보내기를 정비했습니다.
  - **주석·docstring·JSDoc 및 깨진 링크 보완 (`src/tests/*`, `rag/tests/test_assist.py`, `ui/src/app.js`, `CASE-065`):** 테스트 내부 모의 헬퍼·클래스 21건 docstring과 `$()` JSDoc을 보완해 점검 대상 누락 0건·비한국어 0건을 확인했고, `CASE-065` 깨진 구 링크(`test_lab_runs.mjs`→`test_lab_runs.py`)를 고쳐 저장소 상대 링크 깨짐 **0건**을 달성했습니다.
  - **README 디자인·하네스·서버 문서 동기화 (`README.md`, `decision-policy.md`, `architecture.md`, `src/README.md`, `src/lab_web/README.md`):** `README.md` `CASE-104` 잔여 표기·중복 접이식 인덱스를 통합하고 `CASE-100·103·106·107` 전/후 요약표·Mermaid 흐름도·`eval-200` 4종 차트 안내를 정비했으며, 하네스·서버 README를 최신 MCP/예외 가드/`4096` 상한 계약과 일치시켰습니다.
  - **최종 검증:** `black --check`(수정 12파일), `mypy`(39모듈+`eval_set --strict`+`scripts/` 4종 **0오류**), `regression_112_rules.py`(112건 실패 `0` · 5,015건 `exact=762/wrong=17/ext_fp=0`), `RUN_PG_TESTS=1 pytest src/tests` **`171 passed`**, `rag/tests` **`49 passed(3 skipped)`** + `rag.verify` **`passed: true`**, `ui check 19 / test 22/22`, 재기동 `:5010`·`:5000` `/api/v1/health` 200 및 `천안 두정동` `early_external_reject` 스모크 통과.

## 2026-11-19

- **11/19 종합 업무보고 PDF 생성 ([`docs/reports/daily/업무보고_20261119.pdf`](docs/reports/daily/업무보고_20261119.pdf) · [`scripts/reports/daily_report_20261119.py`](scripts/reports/daily_report_20261119.py)):**
  - `업무보고_20261111` 양식 틀을 바탕으로 200건 실증 재평가(`95.0%`), 취약 10건·노이즈 13건 보완, 배너·`README` 지시 구조 시각화, 코드·주석 정비를 쉬운 한국어로 추상화해 1쪽에 정리했습니다.
  - **[별첨 1]** (2~3쪽)에 200건 KPI 카드·5대 축 실증 차트(`eval-200-axis-breakdown.svg`)·취약 사례 개선표·수정 배너(`project-banner.svg`)·`PREFIX` 계층 구조도(`prefix-architecture.svg`)·최종 점검 결과표를 배치하고, **[별첨 2]** (4~8쪽)에 `UI_수정_보고_2026-11-19.pdf` 항목 `2-1~2-8` 표와 고유 이미지 12장(`그림 1~12`)을 원문 수정 없이 기존 업무보고 양식으로 재구성해 수록했습니다.
  - 또한 `scripts/reports/report_common.py`에 UI 카드·이미지 추출/인코딩·공통 A4 스타일을 분리해 `daily_report_20261118.py`와 `daily_report_20261119.py` 간 중복을 제거했습니다.

- **200건 실증 식별 미통과 10건·장소 노이즈 13건·경계 개선 패치 및 `:5010` 실서버 재검증 ([CASE-106](docs/cases/사례-106-단독검사기-200건-미통과-10건과-노이즈-개선패치-및-실서버-재검증-2026-11-19.md)):**
  - **네이버 지도 `address`·`ac` 파싱·HTTP 400 서킷브레이커·오프라인 사례 도로+번지 색인 (`src/llm/place_tool.py`, `src/assist/district.py`):** `instant-search`의 `address` 배열과 `ac` 괄호 동명을 통합 파싱하고 도로명+번지 장문의 1차 직행·인접 번지(±1/±2) 탐침을 적용했으며, `HTTP 400/429` 연속 제한 시 60초 쿨다운 서킷브레이커로 연쇄 지연 폭증(`62.66s→24.77s`)을 제거했습니다. 또한 오탐 `wrong=0` 검증을 거친 청주 랜드마크(`서원대`·`육거리시장`·`수암골 벽화마을/전망대` 등)와 `공개_민원_사례.json` 단일 구 확정 `(도로명, 번지)` 235쌍 오프라인 색인을 추가해 외부 지도 쿨다운 중에도 `B22·B23·B24·B35·F05·F09` 6건 관할 구를 100% 복구했습니다(`5,015건` 구 적중 `751→762`, `wrong=17` 유지).
  - **일반 시설명·관공서·조사 결합·상충 구 오매칭 제거 (`src/llm/place_tool.py`, `src/assist/district.py`):** `_GENERIC_PLACE_NOUNS`·`_NON_PLACE_MODIFIERS`·관공서 현장 수식 가드(`_PHYSICAL_PLACE_NEAR_OFFICE_RE`)·`_PROTECTED_WORD_ENDINGS`(`벽화마을`·`상수도` 보호)·`"청주시로"` 조사 분리 및 본문 확정 구 대비 상충 장소 배지 폐기로 `B12`(`초등학교`→`우암초`) 결함, `C09`(`청주시청`→`상당구`) 취약 및 `spurious_place_noise` 13건을 해소했습니다.
  - **FAQ 예외 보류·조건부 안내 구분·도+시 약칭 차단·EXAONE 토큰 캡 (`docs/harness/prompts/PREFIX-01.txt`, `src/assist/policy.py`, `pipeline.py`, `settings.py`, `followup.py`):** `PREFIX-01.txt`와 `validate_decision(..., citizen_query=text)` 2중 안전 가드로 `A35`(`"담당자 연결/상담처리"` 예외)의 `faq_answer` 종결을 `human_handoff`로 교정하고 `A31` 조건부 제도 안내를 복구했습니다. 또한 `_EXT_DO_SHORT_CITIES`(`충남 천안 두정동` → `0.01s` `early_external_reject`), `settings_for_role` `staff_draft` `max_tokens<=4096` 상한(`D20` `223.87s→200.22s`), `D30` 조롱 백업을 보완했습니다.
  - **검증:** `RUN_PG_TESTS=1 pytest src/tests` **`171 passed`**(`22.28s`), `regression_112_rules.py` **112건 실패 `0` · 5,015건 `exact=762 / wrong=17 / ext_fp=0`**, `black`·`mypy`·Google docstring·`rag/tests` **49 passed(3 skipped)**·`rag.verify` **`passed: true`**·`ui check 19 / test 22` 및 `:5010` 미통과 10건+`C32·D20` 12건 실서버 표적 재검증 통과.

- **`:5010` 단독 응대 검사기 200건 재실증 평가 및 SourceTrail 스타일 분석 보고서 생성 ([CASE-105](docs/cases/사례-105-단독검사기-5010-200건-실증평가와-SourceTrail-분석보고서-2026-11-19.md) · [보고서 MD](docs/reports/analysis/청주_민원_200건_상세분석보고서_2026-11-19.md) · [14쪽 PDF](docs/reports/analysis/청주_민원_200건_상세분석보고서_2026-11-19.pdf) · [원자료 JSON](rag/reports/lab-5010-eval-200-20261119.json)):**
  - **11/17 112건 동일 재측정 + 신규 경계 스트레스 88건 = 총 200건 전수 실측 ([`scripts/eval/live_eval_200.py`](scripts/eval/live_eval_200.py)):** `codex_cli` 186건 + `exaone_api` 14건(청주 184 · 타지역 대조 16)을 실서버에 호출해 **`190 / 200건 (95.0%)`**(`+11.1%p` vs 11/17 `83.9%`) 의미 통과, 기준선 112건 재측정 **`108 / 112건 (96.4%)`**, D축 **`38 / 38 (100.0%)`**, E축 **`30 / 30 (100.0%)`**, EXAONE **`14 / 14 (100% 완주, 타임아웃·429 0건)`**, 순수 타지역 `early_external_reject` 12건 평균 **`0.012s`**, `automaticTransfer=True` **0건**을 실측했습니다.
  - **SourceTrail 시각 체계 + 핵심 차트 4종 보고서 ([`scripts/reports/analysis_report_200.py`](scripts/reports/analysis_report_200.py) · `docs/assets/eval-200-*.svg`):** SourceTrail PDF 디자인(백색·청색 `#1d4ed8` 헤더, 3열 메타 바, KPI 6종·델타 배지, `@page` 머리글/`N / 14` 바닥글, 2줄 전수 상세표, 기준과 정의)과 핵심 시각화 4종(`axis-breakdown`, `outcome-reason`, `latency-engines`, `district-and-gaps`)을 통합하고, 실측에서 새로 드러난 **잔여 한계 4대 과제**(네이버 지도 연속 호출 `HTTP 400` 제한 6건, 단독 일반명사 `초등학교`·`청주시청` 오매칭, `A35` `"담당자 연결"` 예외 종결·`A31` 과도 보류, EXAONE `D20` 223.9s·`충남 천안` 시 생략 경계)를 함께 기록했습니다.

- **`CASE-103` 후속 정규식 중복 최적화·신규 테스트 docstring 정비·하네스 6종 및 README 최종 동기화 ([CASE-104](docs/cases/사례-104-잔여한계패치-주석-하네스동기화-중복최적화-최종검증-2026-11-19.md)):**
  - **중복 탐색·정규화 제거 (`src/assist/district.py`, `pipeline.py`):** `_split_external_residence_clause()` 헬퍼로 `has_external_residence_context`·`_strip_external_residence_clause`·`extract_district`·`resolve_district_and_place`의 3회 중복 탐색을 1회로 통합하고 `extract_external_jurisdiction()` 선두 `cheongju_area_found is True` 조기 반환을 앞당겼으며, `iter_assist()`의 중복 `normalize_district(district)` 호출을 제거했습니다.
  - **주석·하네스·문서 정비 및 최종 재검증 (`src/tests/`, `docs/harness/`, `README.md`, `docs/assets/`, `docs/cases/`):** 신규 테스트 내부 헬퍼 8종 한국어 docstring 보완(`11개` 수정 `.py` 신규·운영 docstring 누락 0건), 하네스 6종(`LLM_완충지대_하네스.md`·`AI_정보전달과_응답_하네스.md`·`시스템_프롬프트와_프리픽스_캐싱_지침.md`·`architecture.md`·`prompts/README.md`·`docs/harness/README.md`) 동기화를 마쳤습니다. 또한 [`docs/assets/prefix-architecture.svg`](docs/assets/prefix-architecture.svg)(`PREFIX-00~04` 계층 구조도) 추가와 함께 `README.md`에 시스템 프롬프트 전용 섹션·5종 상세표·관련 자료 소개를 신설하고 장문 벽돌 문단을 구조화 표·불릿·접이식으로 개편했습니다. 최종 `black --check`(11개), `mypy`(9모듈 0오류), `regression_112_rules.py`(112건 실패 0·5,015건 적중 `751`·외부 오탐 `0`), `RUN_PG_TESTS=1 pytest src/tests` **168 passed**(`24.63s`), `rag/tests` **49 passed(3 skipped)** + `rag.verify` **`passed: true`**, `ui check 19` · `ui test 22/22`, 재기동 `:5010`(`0.011s` `early_external_reject`) · `:5000` `/api/v1/health` 200 및 문서·앵커·이미지·SVG 깨짐 0건을 확인했습니다.

  - **11/18 종합 업무보고 PDF 생성 ([`docs/reports/daily/업무보고_20261118.pdf`](docs/reports/daily/업무보고_20261118.pdf) · [`scripts/reports/daily_report_20261118.py`](scripts/reports/daily_report_20261118.py)):** 기존 `업무보고_20261111.pdf` 틀 기반 쉬운 한국어 추상화 보고(1쪽) + [별첨 1] 백엔드 API 변경/누적 22종 요약·4단계 AI 처리 흐름·라이브 Swagger 캡처 4종(`:5000/swagger` 라이트·다크·`#/staff/api`·`:8007/docs`, 2~4쪽) + [별첨 2] `UI_수정_보고_2026-11-18.pdf` 항목 `2-1~2-9` 및 고유 이미지 14장 원문 무수정 수록(5~10쪽). 또한 [`docs/assets/project-banner.svg`](docs/assets/project-banner.svg)의 `Lab :5010` 칩과 우측 `담당자 연결` 카드 간 겹침을 수정하고 좌우 영역(`52px` 간격)을 재정렬했습니다.

## 2026-11-18

- **112건 실측·5,015건 사례 기반 잔여 한계 분석 및 도로·번지·거주지 예외·EXAONE 차등 추론·조기 차단 패치 ([CASE-103](docs/cases/사례-103-잔여한계-도로번지-광역시약칭-거주지예외-EXAONE추론차등-병렬실행-2026-11-18.md)):**
  - **도로명+번지·정밀 지명·오탐 방어 보완 (`src/llm/place_tool.py`, `src/assist/district.py`, `followup.py`):** `_extract_road_number_pairs()`로 숫자가 탈락하던 도로+번지 쌍(`오송생명14로 283`, `2순환로 1374` 등 93건)을 최우선 후보로 보존하고, 문자 결합 하이픈(`은행나무-바닥에`) 분리(번지 하이픈 `16-19` 보존)·원인조사(`사고로` 등) 불용어를 추가했습니다. `district.py`에는 닫는 괄호/콜론(`)]}>:`) 경계(`긴급)복대동`)와 실사례 100% 검증 단일구 도로(`성안길`·`충청대로`·`팔결신대로`·`오송생명\d*로` 등, 구 적중 `697→751`·추가 오분류 `0`)를 반영하고, `followup.py` `_FACILITY_OFF_RE` 간격 확장으로 `B14`(`"가로등 여러 개가 동시에 꺼져"`) 오탐을 해소했습니다.
  - **광역시 `~시` 약칭 차단·거주지·청주 운수 예외 (`district.py`):** `서울시 종로구 사직동`·`대전시 유성구 봉명동`·`경기도 화성시 동탄대로 123`을 외부 관할로 정확히 차단하면서도, 청주시 시내버스 운수사(사례 913 `청신운수 109` 등 5,015건 외부 오탐 `0`) 및 타지역 거주·이사 술어 뒤 청주 본문(`"대전 유성구 봉명동 사는데 서원대 후문..."`)은 거주지 제거 후 정상 추론하도록 분리했습니다.
  - **EXAONE 지연/타임아웃·토큰·버그 개선 (`src/llm/settings.py`, `complete.py`, `pipeline.py`, `.env.example`):** `settings_for_role()`로 EXAONE 추론 강도를 단계별 차등(`decision=high`, `faq_answer`/`sanitize`/`staff_draft=low`, 정형 단계 `max_tokens` 4096 상한) 적용하고, `codex_cli` `faq_answer`/`sanitize` 단계의 불필요한 MCP 기동(`_disable_mcp`)을 제거했으며, ① 순수 타지역 `early_external_reject`(0.02~0.07s) ② `out_of_scope` 판정 시 `PREFIX-03` 생략 및 고정 초안 ③ `PREFIX-04`∥`PREFIX-03` `ThreadPoolExecutor` 병렬 실행(EXAONE `1.05s` 스태거) ④ 호출 시작 시 `usage_box` 선초기화로 실패 단계 직전 토큰 오염 제거를 적용했습니다.
  - **검증 및 회귀 자동화 (`scripts/eval/regression_112_rules.py`, `src/tests/`):** 112건 결정론적 규칙 회귀 **실패 0건**, 공개 사례 `5,015`건 오탐 **0건**, `src/tests` **168 passed**, `mypy` 8모듈 **0오류**, `rag/tests` **49 passed(3 skipped)**, `ui` 19/22 통과 및 실서버 `:5010` 타지역 조기차단(`0.02s`)·거주지 예외(`27.06s`→`서원구`)·`B14`(`25.82s`→`sanitize=False`) 확인.

- **Swagger 포털·11/17 보고서 후속 한국어 주석·코드 최적화·접근성 대비·README 디자인 최종 점검 ([CASE-102](docs/cases/사례-102-Swagger포털-1117보고서-주석-최적화-README디자인-최종점검-2026-11-18.md)):**
  - **주석·docstring·JSDoc 및 f-string 교정 (`src/complaints/swagger_page.py`, `scripts/reports/daily_report_20261117.py`, `ui/src/api-docs.js`):** 인라인 JS 함수 JSDoc의 Python f-string 중괄호(`{{...}}`) 이스케이프 교정과 보고서 생성기 전 함수 Google docstring(`Args:`/`Returns:`/`Raises:`) 보완을 마쳤습니다.
  - **중복 제거·성능 최적화 (`swagger_page.py`, `daily_report_20261117.py`, `ui/src/api-docs.js`·`app.js`):** 공용 `updateSession(method, role)` 헬퍼 및 `_build_ui_item_card_html` 단일 `capture_blocks` 루프 통합, `citizen.js` `escapeHTML` 재사용, `searchText` 사전 계산·`openApiSummary` 캐싱(`renderApiEndpointListHtml`/`backendSwaggerPage`)으로 `#/staff/api` 중복 명세 파싱·문자열 재할당을 제거했습니다.
  - **`#/staff/api` 다크/라이트 WCAG 대비 및 `README.md` 디자인 개선 (`ui/src/themes.css`·`staff.css`, `README.md`):** 다크 색인 표 `td:nth-child(4) strong`(`1.05→#f8fafc`)·활성 태그 칩(`3.49→>8.5`)·라이트 `M-05`/안내 배너 대비를 교정하고, `README.md` 상단 배지를 3행 균형 배치로 개편했으며 최종 테스트(`src/tests` **164 passed**, `ui check` **19**·`ui test` **22/22**, `rag/tests` **49 passed/3 skipped**, `rag.verify` 통과, `mypy` 37모듈 0오류, Edge CDP `lowContrast: []`)를 검증했습니다.

## 2026-11-17

- **민원 웹(:5000) 한국어 백엔드 Swagger 포털 및 담당자 콘솔 API 문서 페이지(`#/staff/api`) 구현 ([CASE-101](docs/cases/사례-101-민원웹-5000-백엔드-Swagger-포털과-담당자콘솔-API문서-구현-2026-11-17.md)):**
  - **자체 호스팅 한국어 Swagger UI 포털 (`src/complaints/swagger_page.py`·`pages.py`·`api.py`):** 외부 CDN 없이 `flask-openapi3` 로컬 정적 자산(`/openapi/swagger/*`)과 `/openapi/openapi.json`을 재사용해 `/docs`·`/swagger`에서 실시간 `/api/v1/health` 상태 배지, 원클릭 시연 세션 전환(`staff`/`citizen`/해제), 라이트·다크 테마 동기화(`minwon-ui-theme` + `postMessage` + `resolveInitialTheme()`), `?embed=1` 임베드 모드 및 `:8007/docs` 링크를 제공합니다. 또한 `CheongjuSwaggerPlugin`으로 빈 `securitySchemes`에 의해 나타나던 무기능 `Authorize` 모달을 제거하고 경로·메서드·태그·설명 통합 `opsFilter` 및 라이트·다크 WCAG 4.5+ 대비(배지·OAS 3.1 스키마·클립보드 복사 아이콘 포함)를 적용했으며, `api.py`의 `민원`·`담당자 답변`·`AI 작업 · 단계 시연` 태그 설명을 최신 구현에 맞게 정정하고 [`청주톡톡_민원_업무_API_Swagger.pdf`](docs/api/청주톡톡_민원_업무_API_Swagger.pdf)(22경로·1,060,653바이트)를 재생성했습니다.
  - **담당자 콘솔 통합 백엔드 문서 화면 (`ui/src/api-docs.js`·`staff.js`·`app.js`·`icons.js`·`staff.css`·`themes.css`):** 담당자 사이드바(`BACKEND` → `API 문서 · Swagger`)와 모바일 빠른 메뉴에 `#/staff/api` 경로를 추가해 저장소·검색·LLM 헬스 요약 카드, `cleanDocText()` HTML 정리 및 태그·키워드 검색 기반 **엔드포인트 빠른 색인** 탭, 임베드 Swagger UI 탭을 구축했고, `src/tests` **164 passed**·`ui check` **19개**·`ui test` **22/22**·headless Edge 스크린샷·WCAG `< 4.5` **0건** 및 `401→200` `Try it out` 검증을 마쳤습니다.
  - **11/17 종합 업무보고 PDF 생성 (`docs/reports/daily/업무보고_20261117.pdf` · `scripts/reports/daily_report_20261117.py`):** 11/17 서버·AI·Swagger 주요 작업(`CASE-098~101`) 1쪽 업무보고 + [별첨 1] 개선 요약·차트·실서버 캡처(2~4쪽) + [별첨 2] `UI_수정_보고_2026-11-17.pdf` 전체 10건·이미지 21장을 원문 내용 무수정으로 기존 보고서 양식에 맞춰 12쪽 PDF로 통합했습니다.

- **112건 실측 식별 3대 코드 한계(문맥 기반 순화·동+숫자 경계·장소 추론 오매칭) 보완 ([CASE-100](docs/cases/사례-100-문맥기반-순화판단과-지명장소추론-결함보완-2026-11-17.md)):**
  - **문맥 기반 욕설·비꼬기·우회 표현 순화 (`PREFIX-01.txt`·`PREFIX-04.txt`, `src/assist/followup.py`·`pipeline.py`):** 1차 판정기 JSON에 `sanitize_needed` 문맥 플래그를 추가하고 `RISK_SIGNALS`에 `sarcasm_mockery`(비꼬기·조롱)를 편입했으며, `should_run_sanitize()`로 1차 LLM 판단 우선 + 명백 욕설/폭력 인젝션 안전망 + 시설 소등/침하(`꺼져`)·가로수 고사(`죽어`)·`시발점`·`전염병` 배제 휴리스틱을 결합했습니다.
  - **지명·장소 추론 및 타 지자체 관할 방어 보완 (`src/assist/district.py`, `policy.py`, `constants.py`, `src/llm/place_tool.py`, `src/lab_web/static/app.js`):** `_AREA_PATTERN` 뒤쪽 숫자 lookahead·`청주` 접두·`_EUP_UNSPACED_PATTERN`·단일 구 8대 시설 매핑으로 `B17`(`봉명동1349`)·`B06`·`F12`를 보완하고, `place_tool.py`에 서술어 어미(`_PREDICATE_SUFFIXES`) 배제·일반명사 불용어(`지역`·`접수`·`공식`·`신청`·`무료`·`청주페이` 등)·고유 장소 접미어 5후보 최우선 정렬·짧은 상호 부분일치 하한을 적용했습니다. 또한 `_EXTERNAL_PREFIX_RE`·`extract_external_jurisdiction()`으로 `대전 유성구 봉명동`·`서울 종로구 사직동` 등 동명이인 타지역의 구 오인·네이버 조회를 차단하고 `policy.py`에서 `out_of_scope`·`uncertain`·타 지자체 입력의 부서 추천까지 `human_handoff`로 강제해 `src/tests` **163 passed**·`rag/tests` **49 passed(3 skipped)**·`:5010` 라이브 프로브를 검증했습니다.

- **청주 민원 `:5010` 112건 실증 시각화 상세 분석 보고서 추가 및 `docs/reports/analysis/` 전용 폴더 배치 ([CASE-099](docs/cases/사례-099-112건-시각화분석보고서와-테스트폴더-분리-최종점검-2026-11-17.md) · [보고서 MD](docs/reports/analysis/청주_민원_112건_상세분석보고서_2026-11-17.md) · [PDF](docs/reports/analysis/청주_민원_112건_상세분석보고서_2026-11-17.pdf) · [안내](docs/reports/analysis/README.md)):**
  - 원자료 112건 정식 통합([`rag/reports/lab-5010-eval-112-20261117.json`](rag/reports/lab-5010-eval-112-20261117.json)) 및 재현 스크립트([`scripts/reports/analysis_report_112.py`](scripts/reports/analysis_report_112.py)) 구축: SVG 차트 4종(`docs/assets/eval-112-axis-breakdown.svg` · `outcome-reason.svg` · `latency-engines.svg` · `district-and-gaps.svg`), 축별 심층 분석, 3대 코드 한계 및 개선안, 112건 전수 결과표를 Markdown 및 6쪽 PDF로 생성해 [`docs/reports/analysis/`](docs/reports/analysis/README.md) 전용 폴더에 배치했습니다.
  - **주석·코드 최적화·README 디자인 개선:** 공용 브라우저·PDF 인쇄 모듈 [`scripts/reports/report_common.py`](scripts/reports/report_common.py)로 `daily_report_20261116.py`·`analysis_report_112.py` 간 인쇄 코드 중복을 제거하고 `_extract_report_cells()`로 MD/PDF 표 행 생성을 통합했으며, [`README.md`](README.md) 상단 `Test-112_Analysis_6Pages` 배지 및 `검증 근거` 5대 축 SVG 차트를 추가했습니다.

- **검사기 테스트 기록 폼 복원 및 업무보고 전용 폴더(`docs/reports/daily/`) 통합·주석/코드 최적화 ([CASE-098](docs/cases/사례-098-검사기-기록-폼복원과-업무보고-전용폴더-통합-2026-11-17.md)):**
  - **`:5010` 기록 클릭 시 입력 폼 복원 (`src/lab_web/static/app.js`, `ui/tests/lab.test.mjs`):** 오른쪽 **테스트 기록** 항목 클릭 시 결과와 함께 `fillComplaintForm()`·`setSelectValue()`·`updateCharCounters()`로 당시 보낸 제목·민원 분야·발생 지역(`null` 포함)·LLM 엔진 선택 단추·상세 내용·글자 수를 왼쪽 작성 폼에 복원(`loadFields()` 로딩 전 값 유실 방지 포함)하고, 단위 테스트 및 `:5010` Edge 실서버 3건 클릭 검증을 통과했습니다.
  - **업무보고 전용 폴더 통합 및 11/16 종합 보고서 (`docs/reports/daily/`, `scripts/업무보고_*_pdf_생성.py`):** 실서버(`:5000`·`:5010`) 테스트 캡처 6종과 112건 실증 요약을 수록한 `업무보고_20261116.pdf`(5쪽)를 작성하고, 기존 `docs/` 루트의 일자별 업무보고 PDF(`20261109`~`20261111`)까지 [`docs/reports/daily/`](docs/reports/daily/README.md)로 일괄 통합(`20261104` 포함 5종)했습니다. 4개 PDF 생성 스크립트의 저장 경로, `README.md`·`docs/README.md`·`src/lab_web/README.md`·`scripts/README.md`·`CASE-077·080·081` 링크를 모두 일치시켰습니다.
  - **주석·최적화·검증:** `scripts/reports/daily_report_20261116.py` 중복 HTML/파일 목록을 `SCENE_PAGES` 데이터 테이블·`_build_scene_pages_html()`·`_REPORT_CSS`로 리팩터링하고 `Raises:` docstring을 보완했으며, `src/lab_web/app.py` Google `Returns:` 보완 및 `black` 포맷 정비 후 `src/tests` **156 passed**, `ui check` **17개**·`ui test` **19/19**, `mypy` **31모듈 0오류**, `rag.verify` **`passed: true`**, 실서버 `:5010` Edge 검증을 완료했습니다.

- **단독 응대 검사기(`:5010`) 청주 한정 112건 실증 테스트 및 한계·최적화 점검 ([CASE-097](docs/cases/사례-097-단독검사기-5010-청주한정-112건-실증테스트와-한계식별-2026-11-17.md)):**
  - 실증 평가(`:5010` `POST /api/v1/lab/complaints`, 112건 = 청주 한정 110건 + 타 지자체 대조 2건): `codex_cli` 102건(0 HTTP 오류·평균 `23.27s`) + `exaone_api` 교차 10건(8건 평균 `121.86s`, 200초 타임아웃 2건, 429 폴백 2건). FAQ 1차 안내·경계(20/20), RAG 모순 유도질문 방어(23/23), 탈옥·인젝션 방어(20/20)를 검증했고, 후속 개선 과제 3건(`SANITIZE_HINTS` `"꺼져"` 오탐 3건·우회/비꼬기 11건 미감지, `"봉명동1349"` 숫자 경계, `"지역"`·`"접수"` 오매칭 및 `"청주국제공항"` 5개 컷오프)을 식별·기록했습니다.
  - 주석·최적화·문서 디자인 정비: `src/complaints/repository.py`·`service.py` Google `Returns:` 보완 및 `black` 정렬, `departments.py` `@lru_cache` 기반 `_fallback_department_names()` 캐시 추가, `README.md` 112건 실증 접이식 요약표·이전 검증 이력 접기 정비 및 관련 문서 일괄 동기화.

## 2026-11-16

- **최근 패치(CASE-094·095) 주석·최적화·문서 디자인 최종 점검 ([CASE-096](docs/cases/사례-096-패치-주석-최적화-문서디자인-최종점검-2026-11-16.md)):**
  - 주석·최적화(`src/complaints/departments.py`·`repository.py`·`service.py`, `ui/src/app.js`·`staff.js`·`staff.css`): Google docstring·JSDoc·한국어 주석 보완 및 `black` 정렬, `:8007/departments` 원격 목록 60초 TTL 캐시(`_remote_cache`), `repository.py` 기본 템플릿 불필요 더미 모델/지연 import 제거, `service.py` `change()` `_require_staff()` 재사용, 담당자 UI `staffDepartments`·`templatesLoaded` 세션 캐시(`force=true` 갱신) 및 부서 모달 `<select>` 폭 정렬 보완.
  - 문서 정합·디자인(`README.md`, `docs/harness/업무DB_실행설계.md`, `docs/README.md`, `docs/cases/README.md`, `src/README.md`, `ui/README.md`): `complaint_app` 4테이블(`complaints`·`idempotency`·`answer_templates`·`app_meta`), 영구 삭제(`POST /complaints/{id}/delete`), 검사기 전용 메타 분리 설명, `README.md` 상태/DB 비교표/검증 근거 최신화.
  - 검증: `ui check` **17개**·`ui test` **18/18**, `RUN_PG_TESTS=1 pytest src/tests` **156 passed**, `mypy` **31개 모듈 0오류**, `pytest rag/tests` **48 passed(3 skipped)** + `rag.verify` **`passed: true`**, 실서버 Edge `verify_staff_features.mjs` + `audit_dark_ui.mjs` **24/24** + PG DB `complaints` 3행/`answer_templates` 5행 보존 확인.

- **담당자 사이트 다른 부서 배정 및 답변 템플릿 커스텀 추가·삭제 구현 ([CASE-095](docs/cases/사례-095-담당자-부서배정-및-답변템플릿-추가삭제-2026-11-16.md)):**
  - 다른 부서 배정(`src/search_client/client.py`, `src/complaints/departments.py`·`models.py`·`service.py`·`api.py`, `ui/src/llm-meta.js`·`staff.js`·`app.js`): 기존 `내가 담당`/`담당 해제` 외에 `GET /api/v1/departments`(`:8007/departments` 우선 + `공개_민원_사례.json` 127개 부서 fallback)와 확장된 `PUT /api/v1/complaints/{id}/assignment`(`department`·`reason`)를 추가하고, 목록·상세에 검색/구별 필터링 및 AI 추천 후보 원클릭 선택 모달(`#assign-dept-form`)을 구현했습니다(`automatic_transfer=False`·시민 비공개 경계 유지).
  - 답변 템플릿 커스텀 추가·삭제(`src/complaints/repository.py`·`schema/complaint_app.sql`·`service.py`·`api.py`, `ui/src/app.js`·`staff.css`·`themes.css`): `complaint_app.answer_templates`·`app_meta`(최초 1회 기본 5종 시드) 테이블과 `GET/POST /api/v1/templates`, `DELETE /api/v1/templates/{id}`, `POST /api/v1/templates/reset`을 추가해 편집 중 답변을 유지한 채 템플릿 추가(`현재 편집 중 답변 불러오기` 지원)·삽입·삭제·기본 복원이 가능하도록 구현했습니다.
  - 검증: `npm --prefix ui run check` **17개**·`npm --prefix ui test` **18/18 통과**, `RUN_PG_TESTS=1 pytest src/tests` **156 passed**, `mypy` **31개 모듈 0오류**, Edge 다크 24/24(0건) 및 부서 배정·템플릿 CRUD 실브라우저 E2E 확인.

- **다크 테마 청주시 로고·아이콘·호버 개선, 양쪽 검사기 UI 다듬기, 담당자 폰트 확대 및 시민 민원 삭제 구현 ([CASE-094](docs/cases/사례-094-다크테마-청주시로고-호버-검사기UI-담당자폰트-시민민원삭제-2026-11-16.md)):**
  - 다크 테마 브랜드·호버 정비(`ui/src/citizen-brand.css`, `ui/src/service-icons.js`, `ui/assets/service-icons/`, `ui/src/themes.css`, `ui/src/styles.css`, `ui/favicon.svg`): 투명 배경 다크 청주시 로고 PNG 분리·흰 박스 제거, 서비스 12종 SVG `<rect class="service-artwork-bg">` 재추출, `.citizen-shell` `--teal-soft`·`.icon-btn:hover`·`.citizen-update-row:hover`·`.citizen-bottom-nav > a:hover`·`.suggestions .btn:hover`·`.inline-actions` 등 밝은 호버 번쩍임 수정.
  - 검사기 UI·담당자 가독성·부서 메타 분리(`ui/src/lab.js`, `ui/src/lab.css`, `ui/src/staff.css`, `ui/src/staff.js`, `src/lab_web/static/`): `#/lab` 및 `:5010`을 시민 사이트 디자인(`#2f6fed`·히어로·단계 안내·카드형 부서/보조 카드)으로 다듬고 `:5010`에 `minwon-ui-theme` 공유 다크 테마 전환 단추(`#lab-theme-toggle`) 추가, 담당자 포털 전체 폰트 크기 확대, `(업무분장: unverified, 관할: inferred_from_name · 자동 이관 아님)` 원시 표기를 검사기 전용으로 분리.
  - 시민 본인 민원 영구 삭제(`src/complaints/repository.py`·`service.py`·`api.py`, `ui/src/app.js`, `src/tests/test_api.py`·`test_postgres_repository.py`): 논리 철회(`DELETE /complaints/{id}`)를 보존한 채 소유자·버전 검증 후 `idempotency` FK를 선삭제하는 `POST /api/v1/complaints/<complaint_id>/delete`(204)와 상세(`민원 삭제`)·내 민원 목록(`삭제`) UI 추가.
  - 검증: `npm --prefix ui run check` **17개**·`npm --prefix ui test` **17/17 통과**, `RUN_PG_TESTS=1 pytest src/tests` **153개 통과**, `mypy` **30개 모듈 0오류**, 헤드리스 Edge 다크 전수 audit **24/24**·`:5010` **0오류**, 실마우스 호버 19종(`brightFlash: false`) 및 시민 상세·목록 삭제 E2E 확인.

## 2026-11-15

- **민원 웹(`:5000`) CRUD·담당자 콘솔·`#/lab`에 응대 검사기 RAG+LLM 실시간 통합 ([CASE-093](docs/cases/사례-093-민원웹-CRUD-검사기-LLM-RAG-실시간통합-2026-11-15.md)):**
  - 백엔드(`src/complaints/models.py`·`http.py`·`api.py`·`service.py`·`src/app.py`, `src/llm/settings.py`, `src/lab_web/models.py`): `GET /api/v1/assist/fields`(4개 구·98개 읍·면·동·공급자 상태) 추가, `/health`의 `aiConnected` 실제 연동, `AssistInput.rerank=False` 기본화 및 읍·면·동 검증(`normalize_district`), `Complaint.ai_assist`·`Job.provider` 추가, `ComplaintService(..., iter_assist_fn, auto_start_ai)` 비동기 백그라운드 워커 및 `_live_jobs` 메모리 진행 병합(폴링 중 `version` 불필요 증가 방지·취소/수정 무효화·편집 초안 및 최초 `aiOriginal` 보호·실패 시 민원 보존). `Provider`·`AssistResponse`·`ProviderStatus`·`normalize_optional_text` 중복 제거.
  - 프론트엔드(`ui/src/llm-meta.js` 신규, `ui/src/lab.js`·`lab.css`·`staff.js`·`staff.css`·`app.js`·`themes.css`, `ui/adapters/ui04-adapter.js`): `/#/lab`에 `:5010`과 동일한 4종 엔진 선택/잠금, 읍·면·동 선택, `분야:` 제외 질의, 장소 추적·엔진 배지, 데이터(JSON ↑)·프롬프트(↓) 트레이스 반영; 담당자 참고 카드에 `aiAssist` 판정·부서 후보(`dutyStatus`/`자동 이관 아님`)·FAQ/사례·요약 카드·원문 순화 표시 및 편집기 엔진 선택·`AI 후보 채우기` 추가.
  - 검증: `ui` JS 문법 17개·단위 테스트 **16/16 통과**, `mypy` **30개 모듈 0오류**, `RUN_PG_TESTS=1 pytest src/tests` **151개 통과**, `pytest rag/tests` **48개 통과**(3건너뜀), `rag.verify` 통과, 격리 DB(`complaint_app_e2e`) `:5000`+`:8007` 실서버 모델별(`exaone_api`, `codex_cli`, `openai_api` 가드) E2E 검증 완료.

## 2026-11-13

- **`origin/main` 비응대 기능 선택 병합 ([CASE-092](docs/cases/사례-092-main브랜치-UI04-업무DB-비응대기능-병합-2026-11-13.md)):** `llm` 브랜치의 응대 검사기(`:5010` `src/lab_web`) 및 `src/assist`·`src/llm`·`src/search_client`·`docs/harness/prompts/` 로직은 그대로 보존하고, `origin/main`에 있던 비응대 기능 두 축을 편입했습니다(Docker 파일 3종은 `AGENTS.md` 원칙에 따라 제외). ① 업무 DB(`db/` 실행 SQL·`load_samples.py`·샘플 JSON, `PublicComplaint.is_synthetic`, `complaint_app.complaints` 생성 칼럼 5개·색인 2개·`CHECK` 제약 3종·`DEMO-PUB-` 백필, `src/complaints/demo_data.py`, `seed-public-demo` CLI, [`업무DB_실행설계.md`](docs/harness/업무DB_실행설계.md), [`사례-054-업무DB...`](docs/cases/사례-054-업무DB-실행구조와-설계-정합-2026-11-06.md)). ② 시민 UI02~04·편집기(`/design/ui04` + `ui04-adapter.js`, `:5000` `#/citizen` 기본 해시 정렬·`#/lab` 보존, `PHRASES` 문구 바·글자 수·`Ctrl+S`/`⌘S`·`staffPager`·`nextStepBox`·`foldAnswer`·`daysSince`). 병합 후 `RUN_PG_TESTS=1 pytest src/tests` **147개 통과**, `mypy` 30개 모듈 0오류, `ui` 문법 16개·단위 테스트 12개 통과, Flask `/design/ui04` 및 `:5010` `/api/v1/health` 200 응답을 확인했습니다.

- **패치 후속 최적화·문서·검증 최종 점검 ([CASE-091](docs/cases/사례-091-패치-주석-코드최적화-문서디자인-최종점검-2026-11-13.md)):** `styles.css`에 `.llm-engine-badge[data-provider="legacy"]` 스타일을 추가하고, `app.js`에서 `applyLlmSection()` 헬퍼로 `showResult()`의 데이터/프롬프트 섹션 갱신 중복을 제거했으며 `updateLlmAvailability()`가 `.env 기본` 버튼 `<small>`에 해석된 기본 엔진명을 표시하도록 개선했습니다(`ui/tests/lab.test.mjs` 단위 테스트 추가). `README.md`·`src/README.md`·`src/lab_web/README.md`·`docs/README.md`를 `CASE-089`~`091` 기준으로 동기화·디자인 정돈하고, 전체 테스트(`src/tests` 140통과, `ui` 12통과, `mypy` 11파일, `rag/tests` 48통과/3건너뜀, `rag.verify`, `:5010` 실응답)를 검증했습니다.

- 응대 검사기(`src/lab_web`) 결과 화면에서 `보낸 데이터(JSON)` 영역(`#llm-data-block`)을 위, `보낸 프롬프트` 영역(`#llm-prompt-block`)을 아래로 재배치하고, 실제로 사용한 LLM(`assist.llmProvider`·`resolvedProvider`)에 따라 **엑사온 API (K-EXAONE 2.5)**·**Codex CLI**·**GPT API (GPT-6 Luna)** 이름과 엔진 배지 칩·안내 문구를 두 섹션 모두에 동적 표시한다. `.env` 기본 설정 사용 시에도 해석된 공급자·모델명을 백엔드(`src/assist/pipeline.py`, `src/complaints/models.py`, `src/llm/settings.py`)가 함께 기록한다. [CASE-090](docs/cases/사례-090-검사기-LLM별-데이터-프롬프트-표시와-배치순서-변경-2026-11-13.md)

- 최근 패치([CASE-083](docs/cases/사례-083-서원대후문-장소추적-MCP연동-위치인식-2026-11-13.md)~[CASE-088](docs/cases/사례-088-EXAONE-429-재시도와-스트림-오류-전체점검-2026-11-13.md)) 전반의 한국어 docstring/JSDoc 누락(`pipeline.py`·`app.py`·`complete.py`·`lab.test.mjs`)과 `test_place_tool.py` 미사용 import를 보완하고, `src/lab_web/models.py` 중복 검증기(`blank_optional_to_none`) 통합 및 `src/llm/complete.py` `_as_int`/`_first_int`의 `bool` 배제·`0` 토큰 보존을 적용한다. 하네스 문서 4종(`AI_안전_보안_가드레일.md`·`AI_정보전달과_응답_하네스.md`·`architecture.md`·`시스템_프롬프트와_프리픽스_캐싱_지침.md`)과 `README.md` 상단 배지·빠른 탐색·Mermaid·환경변수 표·검증 근거를 최신화한다. [CASE-089](docs/cases/사례-089-패치-주석-하네스문서-최적화-디자인-개선-2026-11-13.md)

- 전체 연동 점검 중 확인된 EXAONE HTTP 429(동시 요청 600·초당 한도 1) 연쇄 실패와 스트림·환경변수 누락을 보완한다. `src/search_client/http.py`에 `retry-after-ms`/`retry-after`와 지수 백오프(최대 2회, 일일 한도 소진 시 즉시 중단)·`TimeoutError` 한국어 안내를 추가하고, `src/assist/pipeline.py`는 판정 API/CLI 실패 시 `llm_unavailable`로 조기 종료해 후속 `sanitize`/`staff_draft` 중복 429를 막는다. `EXAONE_URL`·`EXAONE_MODEL` 격리 로딩 및 `app.js`/`ui/src/lab.js`의 개행 없는 NDJSON EOF 플러시·422/오류 후 중복 재시도 차단을 반영하고 `:5010` 검사기 웹을 최신 코드로 재기동한다. [CASE-088](docs/cases/사례-088-EXAONE-429-재시도와-스트림-오류-전체점검-2026-11-13.md)

- 최근 LLM·MCP·검사기 UI 패치 전반(CASE-083~086)의 주석·docstring·버그·성능·문서를 점검·정비한다. `resolve_district_and_place` 통합 및 `_allow_fallback` 가드로 네이버 지도 중복·재귀 조회를 제거하고, `showResult` 주소 키(`road_address`/`jibun_address`) 누락과 비활성화 단추 비동기 `localStorage` 복원 경쟁 버그를 수정한다. OpenAI `usage_from_openai`의 `reasoning_tokens` 생략 호환과 `mypy` 타입 검사를 정비하고, `PREFIX-01`·`README.md` 디자인·`docs/README.md`·`src/README.md`·`src/lab_web/README.md`를 최신화한다. [CASE-087](docs/cases/사례-087-패치-주석-코드최적화-문서디자인-개선-2026-11-13.md)

- K-EXAONE 2.5 API의 추론 토큰 특성을 감안하여 `max_tokens`를 기본 16,384로 상향하고, `.env`에 `EXAONE_REASONING_EFFORT`(`low`, `high`, `max`) 및 `EXAONE_MAX_TOKENS`, `EXAONE_TEMPERATURE`, `EXAONE_TOP_P` 설정 키를 새로 연결한다. 마크다운 코드블록 방어 파싱과 `reasoning_tokens` 사용량 집계를 지원한다. [CASE-086](docs/cases/사례-086-K-EXAONE-추론강도-최대토큰-파라미터-최적화-2026-11-13.md)

- 응대 검사기 웹 UI에서 `.env`에 키가 설정되지 않은 API 기반 LLM(K-EXAONE 2.5, GPT-6 Luna 등)은 선택되지 않도록 비활성화하고 '키 미설정' 배지, 안내 툴팁 및 클릭 시 흔들림 애니메이션 피드백을 제공한다. `src/llm/settings.py`에 공급자별 가용성 판별 로직을 추가하고 `/api/v1/lab/fields` 계약을 확장하여 화면 초기화 시점에 실시간 상태를 동기화하며, 비활성 항목 선택 시 사용 가능한 기본 엔진으로 자동 fallback 전환한다. [CASE-085](docs/cases/사례-085-API키-미설정시-LLM선택-비활성화-UI효과-2026-11-13.md)

- LG AI연구원의 한국어 특화 무료 생성형 모델인 K-EXAONE 2.5를 API LLM 선택지로 추가하고 응대 검사기 웹 UI에서 엔진을 즉시 전환할 수 있도록 구현한다. `.env.example` 및 `.env`에 `EXAONE_API_KEY` 설정을 추가하고, `src/llm/settings.py`와 `src/llm/complete.py`에 `exaone_api` 전용 엔드포인트(`https://api.exaone.ai/v1/chat/completions`) 호출 및 추론 옵션(`reasoning_effort`) 연동 로직을 구현한다. 응대 검사기 화면에 LLM 엔진 세그먼트 버튼과 장소 추적·엔진 배지를 배치하고, 시스템 프롬프트(PREFIX)의 장소 추적 도구 활용 지침을 갱신한다. 수치·정형 데이터 전문 모델인 `EXAONE Tabular`의 후속 추가 위치(예상 처리기간 회귀 및 부서 재이송 위험도 분류)를 README에 명시한다. [CASE-084](docs/cases/사례-084-K-EXAONE-API공급자-추가와-Tabular-구상-2026-11-13.md)

- '서원대학교 후문 편의점근처 나무 쓰러짐' 등 랜드마크·시설명 민원의 위치 특정 오류를 개선한다. `lookup_navermap_place` 도구의 문장 키워드 정제 및 관련성 검증을 도입하고, `extract_district`와 파이프라인의 2차 fallback 장소 추적, Codex CLI MCP 도구 활성화, 시스템 프롬프트(PREFIX-00, PREFIX-01) 권한 지침을 갱신하여 서원구 모충동 특정 및 타 구 부서 혼입 배제를 구현한다. [CASE-083](docs/cases/사례-083-서원대후문-장소추적-MCP연동-위치인식-2026-11-13.md)

## 2026-11-11

- 11/11 업무보고서 PDF 생성 스크립트의 Google docstring 및 한국어 주석을 점검하고, README 기준일과 보고서 링크를 최신화하며 문서를 정비한다. [CASE-082](docs/cases/사례-082-패치-주석-문서-최적화-2026-11-11.md)

- 11월 11일 서버·AI 업무보고 메인 표(1페이지, 민원 LLM 응답 품질 및 장소 기반 부서 추천 검증)를 작성하고 기민 님의 '11/11 UI 변경 보고서'(3페이지)를 무손실 병합한 총 4페이지 정식 업무보고서 PDF를 생성한다. [CASE-081](docs/cases/사례-081-11월11일-업무보고서-PDF-생성과-UI변경-병합-2026-11-11.md)

## 2026-11-10

- 11월 10일 서버·AI 업무보고 메인 표(1페이지)를 작성하고 기민 님의 'UI 변경 보고서'(6페이지)를 무손실 병합한 총 7페이지 정식 업무보고서 PDF를 생성한다. [CASE-080](docs/cases/사례-080-11월10일-업무보고서-PDF-생성과-UI변경-병합-2026-11-10.md)

- `lookup_navermap_place` 도구의 주석과 docstring을 정비하고, 검색어 공백 정규화 및 FIFO 캐시 퇴출 최적화를 적용하며, README 다이어그램과 배지 디자인을 개선한다. [CASE-079](docs/cases/사례-079-패치-주석-문서-최적화-2026-11-10.md)

- 네이버 지도 비로그인 웹 인스턴트 검색을 이용해 특정 장소(건물, 학교, 시장, 공원 등)에서 도로명·지번 주소와 청주시 4개 구 및 동을 추적하는 MCP 도구 `lookup_navermap_place`를 구현하고, MCP stdio 서버에 등록한다. 불필요한 레거시 `db/` 디렉터리를 정리한다. [CASE-078](docs/cases/사례-078-네이버지도-비로그인-장소추적-MCP-도구-2026-11-10.md)

- JS 프론트엔드 검증 스크립트의 표준 JSDoc 주석을 정비하고, 실서버 호출 및 가상 DOM 회귀 검증과 4페이지 업무보고서 PDF 무결성을 확인한다. [CASE-077](docs/cases/사례-077-패치-주석-문서-최적화-2026-11-10.md)

- 11월 9일 업무보고서 PDF에 검사기 웹 기능 캡처 스크린샷 3장을 첨부 자료로 추가하고 팀원 호칭을 '기민 님'으로 정비한다.

- 응대 검사기 웹(`src/lab_web/static/app.js`)의 결과 렌더링 시 `assist` 변수 초기화 전 참조(TDZ) 오류를 수정하고, 가상 DOM 및 실서버 호출 검증 스크립트를 추가한다. [CASE-076](docs/cases/사례-076-검사기-화면-assist-초기화전참조-수정-2026-11-10.md)

- CASE-074 패치의 Google 형식 한국어 docstring을 맞추고, `src/__init__.py` 지연 로딩 최적화로 RAG 환경의 Flask 종속성을 분리하며, README 원클릭 기동 순서도와 배지를 보강한다. [CASE-075](docs/cases/사례-075-패치-주석-문서-최적화-2026-11-10.md)

- `bin/start-lab.cmd` 실행 시 백엔드 검색 서비스(PostgreSQL·검색 API)의 동작 상태를 감지하여 비정상 종료 락 파일(postmaster.pid)을 정리하고 자동으로 함께 기동하도록 연동한다. [CASE-074](docs/cases/사례-074-검사기-백엔드검색서비스-자동기동-2026-11-10.md)

- CASE-070~072 패치의 Google 형식 한국어 주석과 docstring Attributes를 맞추고, 지명 추출 조기 종료 최적화 및 README 디자인을 개편한다. [CASE-073](docs/cases/사례-073-패치-주석-문서-최적화-2026-11-10.md)

## 2026-11-09

- 응대 검사기에서 청주시 4개 구 및 관할 읍·면·동 전체를 선택할 수 있게 하고, 지역 미지정 시 제목·본문 지명을 감지하여 검색 구 필터로 자동 연결한다. [CASE-072](docs/cases/사례-072-검사기-청주지역선택-지명추출-2026-11-09.md)

- 응대 검사기 민원 전송에 검색·판정 단계 안내와 대기 애니메이션을 둔다. `/api/v1/lab/complaints/stream` NDJSON을 쓴다. [CASE-071](docs/cases/사례-071-검사기-진행단계-버퍼링-2026-11-09.md)

- 응대 검사기에 Codex CLI 표준 입력 전문을 호출마다 보여 준다. `assist.codex[].prompt`는 래퍼·PREFIX 본문·사용자 JSON이다. [CASE-070](docs/cases/사례-070-검사기-Codex프롬프트전문-2026-11-09.md)

- 응대 검사기 결과의 Codex 입력·보낸 민원·받은 응답 JSON 칸마다 복사 단추를 둔다. [CASE-069](docs/cases/사례-069-검사기-응답JSON-복사단추-2026-11-09.md)

## 2026-11-07

- 보류셋 실측 패치의 Google 형식 한국어 주석을 맞추고, 보류 보고 경로를 개발셋과 나눈다. README에 Holdout 3/3 배지를 넣었다. [CASE-068](docs/cases/사례-068-패치-주석-문서-최적화-2026-11-07.md)

- 초안 응대 보류셋 3건을 `codex_cli`로 실측해 3/3을 기록한다. 개발셋 보고서는 그대로 두고, 이 결과로 PREFIX를 고치지 않는다. [CASE-064](docs/cases/사례-064-초안응대평가셋확대-2026-11-06.md)

- CASE-064~066 패치의 Google 형식 한국어 주석을 맞추고, 검사기 기록 JSON 읽기·목록 요약을 한 경로로 모은다. README에 초안 평가 29건·Lab_runs 파일 배지와 개발셋 26/26을 적었다. [CASE-067](docs/cases/사례-067-패치-주석-문서-최적화-2026-11-07.md)

## 2026-11-06

- 응대 검사기 테스트 기록을 `.rag-cache/lab-runs` JSON 파일로 남긴다. 브라우저를 바꿔도 목록이 유지되고, 민원 업무 DB와는 섞지 않는다. [CASE-066](docs/cases/사례-066-검사기-테스트기록-파일저장-2026-11-06.md)

- 응대 검사기 오른쪽에 보낸 검사 결과를 고르는 테스트 기록 목록을 둔다. 이 브라우저에만 남기며 업무 DB와 섞지 않고, 고르면 저장된 결과를 다시 보여 준다. [CASE-065](docs/cases/사례-065-검사기-테스트기록목록-2026-11-06.md)

- 초안 응대 평가셋을 유형별 29건(개발 26·보류 3)으로 늘린다. 검색 Hit와 안내 정답을 구별하고, 조건 부족 사유는 FAQ 안내로 남기지 않는다. 개발셋 26/26을 기록했다. 400문항·민원 CRUD LLM은 이번 범위가 아니다. [CASE-064](docs/cases/사례-064-초안응대평가셋확대-2026-11-06.md)

- 성인 여권 FAQ는 검색 1위여도 본문에 필요 서류가 없으면 안내하지 않는다. PREFIX-01에 조건 부족 규칙을 적고 검사기에 처리 사유를 보여 준다. [CASE-063](docs/cases/사례-063-여권FAQ조건부족-검사기사유표시-2026-11-06.md)

- PREFIX 조립이 캐시 적격인지 검사하고, openai_api 비교는 `.env`를 쓰지 않은 채 키가 없으면 건너뛴다. 초안 응대 평가 10건을 현재 공급자로 기록한다. [CASE-062](docs/cases/사례-062-PREFIX캐시조립-공급자비교-초안평가-2026-11-06.md)

- PREFIX-03 담당자 초안과 PREFIX-04 순화를 검사기·CLI 후속 호출로 잇는다. 시민 갈래와 민원 CRUD는 바꾸지 않는다. e5-small-ko 검색 예제 10건을 재평가하고 현재 공급자 실측을 기록한다. [CASE-061](docs/cases/사례-061-PREFIX-03-04-검색재평가-실측-2026-11-06.md)

- CASE-057~059 패치의 Google 형식 한국어 주석을 맞추고, MCP JSON 본문 검사를 한 함수로 모은다. README에 Lab :5010·MCP NDJSON 배지와 검사기 검색·판정 현재 단계를 적었다. [CASE-060](docs/cases/사례-060-패치-주석-문서-최적화-2026-11-06.md)

- 응대 검사기 결과에 Codex 1차(및 FAQ 2차) 사용자 JSON을 `assist.codex`로 보여 준다. PREFIX 전문은 넣지 않는다. [CASE-059](docs/cases/사례-059-검사기-Codex입력-표시-2026-11-06.md)

- Codex MCP 서버가 줄 단위 JSON-RPC 핸드셰이크를 받도록 고친다. 예전 `Content-Length` 프레임도 유지한다. [CASE-058](docs/cases/사례-058-Codex-MCP-핸드셰이크-줄단위JSON-2026-11-06.md)

- 검사기 웹이 민원 JSON을 받은 뒤 제목·상세로 검색 API를 먼저 호출하고 `src.assist` 판정을 붙인다. 분야는 검색 질의에 넣지 않는다. [CASE-057](docs/cases/사례-057-검사기웹-검색판정-연결-2026-11-06.md)

- `bin/start-lab.cmd`를 CRLF로 고쳐 cmd.exe가 줄을 명령으로 오인하지 않게 한다. `*.cmd`는 `.gitattributes`에서 CRLF를 유지한다.

- 응대 검사기 프론트를 `src/lab_web/static`으로 추출하고, 민원 JSON을 받는 작은 Flask를 `:5010`에 둔다. `POST /api/v1/lab/complaints`는 언어 모델용 봉투만 만들고 호출·CRUD 저장은 하지 않는다. GitHub 기본 브랜치는 `llm`이다. [CASE-056](docs/cases/사례-056-응대검사기-웹추출과-수신API-2026-11-06.md)

- GitHub `llm` 브랜치를 만들고 기본 화면을 `/#/lab` 응대 검사기로 고정한다. 시민·담당자 해시는 검사기로 보낸다. 민원 문장 → RAG+LLM 응답 경로만 이 브랜치에서 개발한다. [CASE-055](docs/cases/사례-055-llm브랜치-응대검사기-집중-2026-11-06.md)

- Windows `setup.cmd`와 Linux `setup.sh`로 가상환경·PostgreSQL/pgvector·임베딩 모델을 준비한다. 기존 한국어 실행기의 영어 파일명 bash 별칭을 둔다. `--check`는 설치 없이 확인만 한다. [CASE-054](docs/cases/사례-054-환경준비-스크립트와-리눅스-실행기-2026-11-06.md)

- CASE-051·052 패치의 Google 형식 한국어 주석을 맞추고, pgvector 이웃 조회에 검색 엔진과 같은 HNSW `strict_order`를 쓴다. README 다음 단계에서 이미 끝난 재임베딩을 뺀다. [CASE-053](docs/cases/사례-053-패치-주석-문서-최적화-2026-11-06.md)

- 검색 임베딩 기본값을 `dragonkue/multilingual-e5-small-ko`(384차원, 리비전 `bba4cb8e3299d445c04f62bf62e2b26461d03715`)로 바꾼다. 이 호스트에서 5,109건을 `--reembed`했다. 이전 intfloat 색인은 `RAG_EMBEDDING_PROFILE=e5-small`이다. [CASE-052](docs/cases/사례-052-한국어-e5-small-ko-임베딩-2026-11-06.md)

- `bin/embed-sentence.cmd`는 벡터를 출력한 뒤 같은 벡터로 FAQ와 공개 사례의 pgvector 이웃을 따로 보여 준다. `--raw`와 `--no-search`는 벡터만 출력한다. [CASE-051](docs/cases/사례-051-문장임베딩-pgvector-이웃-2026-11-06.md)

- CASE-046~049의 한국어 Google 주석을 맞추고, 검색 도구는 판정 후보 딕셔너리를 그대로 쓴다. README에 Codex 검색 도구 배지·배너 칩과 업무 `version` 이행을 적었다. [CASE-050](docs/cases/사례-050-패치-주석-문서-최적화-2026-11-06.md)

- 예전 `complaint_app.complaints`에 없는 `version` 컬럼을 서버 시작 때 채운다. `python -m src`도 비어 있는 `PGDATABASE`를 `complaints_native`로 둔다. [CASE-049](docs/cases/사례-049-업무테이블-version-컬럼-2026-11-06.md)

- Codex 실행 래퍼와 `PREFIX-00`은 도구를 전면 금지하지 않고, 개발자가 그 호출에 허용한 도구만 쓰게 한다. 허용 목록은 다음 항목의 `search_complaint_rag`이다. [CASE-047](docs/cases/사례-047-Codex-허용-도구-조건-2026-11-06.md)

- Codex에 `search_complaint_rag`만 허가한다. 민원 문장을 검색 API로 넘겨 `retrieval_only` 후보를 받고, PREFIX-00~04에 호출 조건을 적는다. [CASE-048](docs/cases/사례-048-Codex-RAG-검색-도구-2026-11-06.md)

- `bin/start-search.cmd`는 상태 안내 뒤 키 입력까지 창을 유지한다. 이미 켜진 PostgreSQL·검색 API는 종료하지 않는다. `bin/embed-sentence.cmd`는 문장이 없으면 입력을 받는다. [CASE-046](docs/cases/사례-046-기동-CMD-창-유지-2026-11-06.md)

- 루트 README 응대 검사기 절에 PREFIX 시스템 프롬프트 조립 표(호출마다 `00`+작업 블록 하나, `03`/`04` 미연결)를 넣었다.

- CASE-043·044 패치의 Google 형식 한국어 주석을 맞추고, PREFIX 파일은 이름 목록으로 한 번에 읽으며, 문장 임베딩 L2는 numpy에서 먼저 계산한다. README에 PREFIX 배지·하네스 목차·배너 칩을 넣었다. [CASE-045](docs/cases/사례-045-패치-주석-문서-최적화-2026-11-06.md)

- `docs/harness`를 LLM 완충지대 계약과 개발·운영 문서로 나누고, 프리픽스 캐싱용 실제 시스템 프롬프트(`PREFIX-00`~`04`)를 `docs/harness/prompts/`에 두었다. 1·2차 응대 호출은 이 파일을 읽어 조립한다. [CASE-044](docs/cases/사례-044-LLM-완충지대-하네스와-프리픽스-원문-2026-11-06.md)

## 2026-11-05

- 한 문장을 RAG e5-small로 임베딩해 벡터 숫자만 출력하는 `embed_sentence.py`·`bin/embed-sentence.cmd`를 추가하고, 실행 스크립트·CMD·`rag/test-search.sh` 파일명을 한국어로 바꿨다. Windows `start_web.py`는 Flask에 libpq 기본값을 넘긴다. [CASE-043](docs/cases/사례-043-문장-임베딩과-한국어-스크립트명-2026-11-05.md)

- 두 원본 기획서 분석(`VoteLab_AI민원_상세기획안_상세분석.md`, `민원AI_계획서_상세분석.md`)과 현재 프로젝트(`src/assist`, `src/search_client`, `src/llm`) 계약을 통합하여 AI 정보 전달·응답 하네스, 추후 Prefix Caching 적용을 위한 계층별 고정 시스템 프롬프트(`PREFIX-00~04`) 지침, 개인정보·긴급·처분성·특이민원 안전 가드레일 문서를 `docs/harness/`에 추가했다. [CASE-042](docs/cases/사례-042-AI-입출력-프리픽스-캐싱-하네스-2026-11-05.md)

- 시연 웹이 쓰지 않는 `db/app/complaints.sqlite3`와 `.web-data` sqlite·구 Flask 로그를 삭제하고, 추적 `db/app` 안내 폴더를 없앤다. Flask 세션 키와 검색 PostgreSQL은 유지한다. [CASE-041](docs/cases/사례-041-잔여-SQLite-삭제-2026-11-05.md)

- CASE-035~039 패치의 Google 형식 한국어 주석을 맞추고, Windows 포트 확인·새 콘솔 기동·libpq 기본값을 `scripts/run/start_console.py`로 모았다. README에 `rag/origin`·`bin/start-search.cmd` 배지와 표를 넣었다. [CASE-040](docs/cases/사례-040-패치-주석-문서-최적화-2026-11-05.md)

- 검색 원본 JSON·검색 스키마·벡터 dump를 `rag/origin/`으로 옮기고, 시연 웹 업무 DDL은 `src/complaints/schema/`에 둔다. 루트 `db/`는 이전 경로 안내만 남긴다. [CASE-039](docs/cases/사례-039-검색코퍼스와-업무스키마-배치-2026-11-05.md)

- Windows에서 Codex CLI 프롬프트가 명령줄 길이 제한을 넘지 않도록 `codex exec -`의 표준 입력으로 보내고, npm `codex.cmd`는 `node`와 `codex.js`로 풀어 실행한다. [CASE-038](docs/cases/사례-038-Windows-Codex-명령줄-길이-2026-11-05.md)

- 응대 LLM의 API(`openai_api`)와 CLI(`codex_cli`)를 루트 `.env`에서 고른다. 키 칸이 있는 `.env`를 만들고, 기존 호환 토큰 키도 `.env`에서 읽는다.

- 이 Windows 호스트에 PostgreSQL 18.6·pgvector 0.8.7·RAG `.venv`를 사용자 디렉터리로 준비하고 e5-small 색인 5,109건을 적재했다. `bin/start-search.cmd`로 DB와 검색 API를 다시 켠다. 캐시 저장은 `cursor.executemany`를 쓴다. [CASE-036](docs/cases/사례-036-Windows-RAG-PostgreSQL-로컬기동-2026-11-05.md)

- Windows `bin/ask-assist.cmd`는 localhost 검색 API가 꺼져 있으면 별도 창에서 `python -m rag serve`를 시작하고 health ready를 기다린다. 이미 실행 중이거나 원격 주소면 다시 시작하지 않으며 `--no-start`로 끌 수 있다. [CASE-035](docs/cases/사례-035-응대-CMD-검색API-자동시작-2026-11-05.md)

- CASE-031~033 패치의 Google 형식 한국어 주석을 맞추고, 현재 문서의 SQLite·`complaint_app` 미사용 표기를 고쳤다. 업무 SQL 식별자는 저장소 생성 때 한 번 조합하고, 적재 캐시는 해시 목록을 묶어 읽는다. README에 두 스키마·Swagger PDF·PG 업무 칩을 넣었다. [CASE-034](docs/cases/사례-034-패치-주석-문서-최적화-2026-11-05.md)

- Flask 민원 웹 `/docs` Swagger와 같은 OpenAPI 3.1 계약을 인쇄본 PDF로 `docs/`에 둔다. 검색 API `:8007/docs`는 포함하지 않는다. 재생성은 `python scripts/reports/export_swagger_pdf.py`다. 인쇄 시 카드 절단·고아 제목·경로 잘림을 고친 뒤 25쪽으로 다시 뽑았다. [CASE-033](docs/cases/사례-033-민원웹-Swagger-PDF-2026-11-05.md)

- CASE-026이 남긴 루트 `src/*.py` 호환 모듈 9개를 삭제하고, 테스트는 `src.complaints`에서 직접 import한다. Flask 조립은 `app.py`에 둔다. [CASE-032](docs/cases/사례-032-호환모듈-제거-2026-11-05.md)

- 시연 웹 민원 CRUD를 SQLite 파일 대신 PostgreSQL `complaint_app` jsonb로 저장한다. 검색은 기존처럼 `complaint_rag`에 두고 행을 섞지 않는다. 적재 벡터 체크포인트도 `embedding_cache` 테이블로 옮겼다. 단위 테스트는 메모리 저장소를 쓴다. [CASE-031](docs/cases/사례-031-업무저장-PostgreSQL-통일-2026-11-05.md)

- 2026-11-05 작업(CASE-023~034)을 보고용으로 요약한 문서를 추가했다. [진행 보고](docs/reports/진행보고-2026-11-05.md)

- CASE-029 패치의 Google 형식 한국어 주석을 맞추고, 임베딩 시 문서마다 토크나이저를 한 번 더 돌리던 경로를 없앴다. 스키마 SQL은 프로세스에서 한 번만 읽고, 차원 정렬이 일어난 뒤에만 `SET NOT NULL`을 건다. README 배너·상태 표에 e5-small과 `bin/ask-assist.cmd`를 넣고, 데이터 계약의 긴 본문 정책을 프로필 한도 절단으로 고쳤다. [CASE-030](docs/cases/사례-030-임베딩-주석-문서-최적화-2026-11-05.md)

- 검색 임베딩 기본값을 CPU용 `intfloat/multilingual-e5-small`(384차원)로 바꿨다. 기존 BGE-M3 색인은 `RAG_EMBEDDING_PROFILE=bge-m3`로 유지한다. Windows `bin/ask-assist.cmd`로 민원 문장을 넣으면 실행 중인 검색 API 위에서 RAG+LLM 응대를 보여 준다. [CASE-029](docs/cases/사례-029-가벼운-임베딩과-응대-CMD-2026-11-05.md)

- README 배너·검사기 그림을 한국어 카드와 네 패키지 칩으로 맞추고, 지금 됨/검사기/아직 표와 백엔드 패키지 표를 넣었다. JSON HTTP는 `src.search_client.http` 한 곳으로 모으고, 응대 한 요청에서 검색 조각과 환경 LLM 설정을 재사용한다. [CASE-028](docs/cases/사례-028-README-디자인과-검색조각-최적화-2026-11-05.md)

- Flask `src/`를 민원 웹(`complaints`), 검색 클라이언트(`rag`), LLM 공급자(`llm`), 둘을 잇는 응대 계층(`assist`)으로 나눴다. CLI `python -m rag assist`는 같은 연결 함수를 쓰고, 민원 CRUD와 검색 색인은 섞지 않는다. [CASE-026](docs/cases/사례-026-백엔드-민원웹-RAG-LLM-분리-2026-11-05.md)

- 분리 패치의 Google 형식 한국어 docstring을 인자와 맞추고, README·하네스·데이터 계약의 패키지 경로와 검증 기록을 갱신했다. [CASE-027](docs/cases/사례-027-분리-패치-주석-문서-점검-2026-11-05.md)

- 최근 패치의 Google 형식 한국어 docstring을 코드와 맞추고, `.env` LLM 키를 한 번만 읽으며 공백 API 키는 미설정으로 다룬다. README 바로 시작 표·배너·저장소 트리를 현재 구현에 맞게 정리했다. [CASE-025](docs/cases/사례-025-패치-주석-문서-최적화-2026-11-05.md)

- Windows용 `bin/start-web.cmd`와 `scripts/run/start_web.py`를 추가했다. `.venv-web`의 Flask 업무 서버를 별도 창에서 시작하고 준비 상태를 확인한 뒤 기본 브라우저의 시민 화면을 열며, 이미 실행 중인 서버는 재시작하지 않는다. [CASE-024](docs/cases/사례-024-Windows-서버-시작-스크립트-2026-11-05.md)

- 응대 검사기의 LLM 공급자를 `COMPLAINT_LLM_PROVIDER`로 선택하도록 확장했다. `openai_api`는 `.env`의 `OPENAI_API_KEY`로 OpenAI Responses API에 `gpt-6-luna`·`medium`을 요청하고, `codex_cli`는 로그인된 Codex CLI를 읽기 전용 임시 작업공간에서 실행한다. 검색 전용 계약과 코드 정책 검증, 민원 CRUD 분리는 유지한다. [CASE-023](docs/cases/사례-023-GPT-6-Luna-공급자-선택-2026-11-05.md)

## 2026-11-01

- 검색 API 계약을 유지한 채 LLM 판정·코드 정책 검사 응대 계층을 추가했다. CLI `python -m rag assist`, Flask `POST /api/v1/assist`·`/assist/stream`, `/#/lab` 검사기가 같은 함수를 사용한다. 검사기는 시민 직접 작성 양식과 짧은 진행 안내, 안내 실패 시 처리 사유를 보여 준다. 기존 시민·담당자 CRUD는 그대로 둔다. 최종 모델은 미선정이며 토큰이 없으면 검색 근거와 담당자 검토로 떨어진다. 한국어 주석·중복 호출·문서 상태와 README 검사기 안내를 점검했다. [CASE-022](docs/cases/사례-022-RAG-LLM-응대검사기-2026-11-01.md)

## 2026-10-31

- Flask 앱 생성을 짧은 조립 순서로 정리하고 공통 HTTP 처리·화면 경로를 `http.py`·`web.py`로 나눴다. 답변·시연 작업의 긴 분기를 전용 메서드로 정리하고 Python 형식을 통일했다. API 회귀 18개·strict 타입 검사와 전후 OpenAPI 전체 동일성을 확인했다. [CASE-021](docs/cases/사례-021-Flask-서버-코드-구조-간소화-2026-10-31.md)

- 누적 패치의 한국어 JSDoc·Python 설명, 테마 저장 실패 회귀, 중복 직렬화, README 상태와 원격 충돌을 정리했다. 최신 민원 27건을 백업·보존해 현재 경로로 옮기고 Flask를 재시작했다. Python 43개·JS 4개 통과, 실제 PostgreSQL 3개는 환경 부재로 건너뛰었다. [CASE-020](docs/cases/사례-020-패치-종합점검과-서버-저장소-최신화-2026-10-31.md)

- 원격 main의 외부 LLM 호출 예제·문서 두 커밋을 보존해 병합하고, 예제의 고정 토큰을 `PUBLIC_LLM_TOKEN` 환경변수로 변경했다. 원격 CASE-012와 겹치던 로컬 CRLF 사례는 CASE-019로 정리했다.

- 시민·담당자 사이트 헤더에 다크·라이트 전환 버튼을 추가하고 브라우저에 설정을 저장했다. 글·카드·입력·메뉴의 두 테마를 PC·모바일에서 확인했다. [CASE-018](docs/cases/사례-018-시민-담당자-다크라이트-테마-전환-2026-10-31.md)

- [문서 목차](docs/README.md)에 현재 구현·데이터 위치와 CASE-001부터 CASE-017까지의 패치 표를 맞춰 두었다. 웹 미구현으로 남아 있던 안내를 Flask·UI·`db/` 경로 기준으로 고쳤다.

- 예시 HTML의 ‘민원과’를 참고해 담당자 사이트를 남색 사이드바·업무 요약·필터·민원 큐와 처리 단계·금색 검토 카드·답변 편집기로 개편했다. 건수·상태는 실제 서버 자료를 사용하고, 담당 지정·초안 비노출·게시·시연 중 편집 보존과 PC·모바일 화면을 검증했다. [CASE-017](docs/cases/사례-017-민원과-담당자-화면-디자인-개편-2026-10-31.md)

- 담당자 화면 글꼴을 시민 사이트와 같은 Pretendard 계열로 맞추고, 제목의 Batang 계열을 정리해 화면 전체의 읽기 흐름을 통일했다. PC·모바일의 실제 글꼴 계산·줄바꿈과 화면을 확인했다. [CASE-017 후속](docs/cases/사례-017-민원과-담당자-화면-디자인-개편-2026-10-31.md)

- ‘자주 찾는 서비스’ 버튼 12개의 이모지를 분야별로 직접 제작한 SVG 아이콘으로 교체했다. 홈·전체보기에서 같은 도안을 사용하며 개별 SVG와 내보내기 명령을 제공한다. PC·모바일 렌더링과 상담 연결을 확인했다. [아이콘 파일 안내](ui/assets/service-icons/README.md) · [CASE-015 후속](docs/cases/사례-015-예시-시민-화면-디자인과-효과-반영-2026-10-31.md)

- 시민 헤더의 청주시 로고를 왼쪽으로 옮기고 ‘시민특별시’를 ‘민원톡톡’으로 교체했다. 이름을 남색·파란색으로 구성하고 PC·모바일 정렬과 접근성 이름을 맞췄다. [CASE-015 후속](docs/cases/사례-015-예시-시민-화면-디자인과-효과-반영-2026-10-31.md)

- 검색 원본 JSON·스키마 SQL·검색 덤프·업무 SQLite 경로를 `db/` 아래로 모았다. 적재 코드는 `db/schema/complaint_rag.sql`을 읽고, 시연 웹 기본 DB는 `db/app/complaints.sqlite3`이다. dump 내보내기·복원 스크립트를 추가했다. 벡터 dump는 Git에 넣지 않으며 우분투에서 `scripts/ops/export-dump.sh`로 만든다. [CASE-016](docs/cases/사례-016-프로젝트-내부-DB-파일-배치-2026-10-31.md)

- 예시 HTML의 시민 웹을 기준으로 파랑·남색 UI, 시민특별시·CI 헤더, 소식·가로 서비스·접수 영역, 모바일 하단 메뉴와 바텀시트·말풍선·타이핑·등록 확인 효과를 반영했다. 실제 Flask 저장·게시·추가 문의를 유지하며 시연 안내와 실제 행정 기능을 구별한다. [CASE-015](docs/cases/사례-015-예시-시민-화면-디자인과-효과-반영-2026-10-31.md)

- 루트 `src/`에 Flask 업무 서버·Swagger를 구현하고 시민·담당자 UI를 API 저장으로 연결했다. Pydantic 요청·응답, `Protocol` 저장소, SQLite 트랜잭션·버전·등록 중복 검사, 역할별 초안 비노출을 적용했다. 엄격한 타입 검사·API 회귀 18개·JS 클라이언트 회귀 3개와 브라우저 흐름을 확인했다. 실제 AI·SSE·PostgreSQL 업무 스키마·운영 인증·공식 이관은 후속이다. [서버 실행·API](src/README.md) · [CASE-014](docs/cases/사례-014-Flask-업무서버와-Swagger-구현-2026-10-31.md)

- 시민 사이트와 담당자 업무 포털의 로컬 UI를 구현했다. 민원 CRUD·추가 문의, 담당자 초안·게시·이력, AI 작업 단계 시연을 브라우저 저장으로 연결했다. 실제 업무 서버·인증·DB·LLM·SSE·공식 접수는 미연동이다. 문법 검사·저장 경계 테스트 5개와 Chrome DevTools MCP의 PC·모바일 화면·교환 흐름을 검증했다. [UI 실행](ui/README.md) · [CASE-013](docs/cases/사례-013-시민과-담당자-웹-UI-구현-2026-10-31.md)

## 2026-10-30

- Windows에서 꺼낸 Bash 스크립트의 CRLF 줄 끝 때문에 `rag/test-search.sh`가 WSL bash에서 `pipefail` 오류로 실패하던 문제를 고쳤다. `*.sh`는 LF로 유지하고 Python 클라이언트 탐색을 보완했다. [CASE-019](docs/cases/사례-019-검색-테스트-스크립트-CRLF-수정-2026-10-30.md)

## 2026-10-28

- 실제 FAQ·사례 검색용 Bash TUI와 명령형 옵션, 원문·출처 표시, 선택 저장 기능을 추가했다. 전체 테스트 27개와 실제 검색·입력·실패 처리를 확인했다. [CASE-011](docs/cases/사례-011-검색-테스트-터미널-메뉴-추가-2026-10-28.md)

- 실행용 Docker 파일·전용 컨테이너·네트워크·검색 이미지를 제거하고 네이티브 설치·DB 준비·사용자 서비스·테스트 템플릿으로 통일했다. 웹 설계 MD/PDF는 1.3으로 갱신했다. 과거 실행 이력은 보존한다.

- Docker 기반 검색 DB를 네이티브 PostgreSQL 18로 복원하고 Python 검색 API를 사용자 서비스로 구성했다. [CASE-010](docs/cases/사례-010-네이티브-검색환경-전환-2026-10-28.md)

[프로젝트 소개](README.md) · [문서 목차](docs/README.md) · [다음 작업](docs/plans/harness-roadmap.md)

사용자가 확인할 수 있는 데이터·검색·문서 변경을 정리합니다. Git 도입 이전의 작업은 첫 커밋에 묶여 있으며, 별도의 릴리스 버전을 발행한 상태는 아닙니다. 날짜는 UTC 기준입니다.

## 2026-10-27 · UI·백엔드·AI·DB 분야별 작업계획

- 사용자 요청에 따라 [통합 설계서](docs/plans/민원_웹_MVP_상세설계와_분야별_작업계획.md)에서 A/B 개인별 작업 배정을 없애고 UI 10개·백엔드 10개·AI 9개·DB 9개의 38개 작업으로 구체화했습니다. 여러 분야가 섞인 기존 작업을 분해했으며 기능 범위는 유지합니다.
- 문서 제목·파일명을 분야별 작업계획으로 바꾸고, 앞부분의 그림·전체 작업표·읽는 순서와 상세 완료 기준·개발 순서·하네스를 같은 분류로 맞췄습니다. 1.2판 [PDF](docs/plans/민원_웹_MVP_상세설계와_분야별_작업계획.pdf)는 24쪽·그림 7개·인수 시나리오 16개입니다.
- README·목차·AGENTS·계획·하네스 링크를 갱신했습니다. PDF 제목은 Markdown 제목을 따르게 했습니다. 과거 버전의 A/B 작업 기록은 이력으로 보존하며, 변경 근거와 실제 검증은 [CASE-009](docs/cases/사례-009-게시판-CRUD와-AI-모니터링-통합설계-2026-10-27.md)에 기록합니다.
- 이번 변경은 문서·그림·PDF 생성 도구에 한정합니다. 기존 검색 기반을 유지하며 웹·업무 서버·LLM 기능은 미구현입니다.

## 2026-10-27 · 역할 소개와 전체 작업표 보강

- [통합 설계서](docs/plans/민원_웹_MVP_상세설계와_분야별_작업계획.md)의 ‘범위와 읽는 순서’ 앞부분에 A/B의 역할 소개·7개 작업 묶음 그림·전체 28개 작업표·담당자별 읽는 순서를 추가했습니다.
- 기존 작업 책임·우선순위는 유지하고 문서를 1.1판·22쪽·그림 7개로 갱신했습니다. Markdown과 [PDF](docs/plans/민원_웹_MVP_상세설계와_분야별_작업계획.pdf)는 같은 내용입니다.
- 절 번호·문서 버전에서 PDF 머리말·바닥글을 구성하고, 페이지 추가 후에도 편집기 그림의 인쇄 크기를 유지하도록 생성 도구를 보완했습니다. 검증은 [CASE-009](docs/cases/사례-009-게시판-CRUD와-AI-모니터링-통합설계-2026-10-27.md)의 후속 이력에 기록합니다.

## 2026-10-27 · 게시판 CRUD·AI 답변 수정·실시간 모니터와 2인 개발 설계

- 사용자 추가 요구를 [통합 설계 Markdown](docs/plans/민원_웹_MVP_상세설계와_분야별_작업계획.md)과 [동일 내용 PDF](docs/plans/민원_웹_MVP_상세설계와_분야별_작업계획.pdf)로 정리했습니다. 20쪽·그림 6개·2인 작업 28개·인수 시나리오 16개를 포함합니다.
- 실제 목록·CRUD·철회·복구, AI 기원과 담당자 수정·게시·정정, 실시간 단계·재연결·취소·늦은 결과 차단을 구체화했습니다. DB/API와 Flask·작업자·SSE는 구현 제안입니다.
- A의 업무 서버·데이터·평가와 B의 AI 연결·화면 기반·인프라 역할을 선행 작업·완료 조건으로 나눴습니다. README·목차·AGENTS·계획·하네스를 연결했습니다.
- Markdown과 SVG에서 한글 글꼴이 포함된 PDF를 생성하는 문서 도구를 추가했습니다. 변경·검증·한계는 [CASE-009](docs/cases/사례-009-게시판-CRUD와-AI-모니터링-통합설계-2026-10-27.md)에 기록합니다.
- 웹·업무 서버·LLM은 미구현입니다. 기존 검색 코드·원본 JSON·실행 DB·모델 설정은 변경하지 않았습니다.

## 2026-10-25 · 프로젝트 종합 재점검

- 최근 코드·주석 정비와 시연 웹·민원 서버 계획을 포함해 구현 상태와 저장소 내용을 점검했습니다.
- 코드·격리 DB 테스트 25개와 실제 원본/DB 무결성, API 입력 오류·부서 조회, Python 주석·문서 링크·흐름도 검증을 수행했습니다.
- 실제 검색 회귀 10개도 통과했고 새 오류는 발견되지 않았습니다. 결과·한계는 [CASE-008](docs/cases/사례-008-프로젝트-종합점검과-저장소-반영-2026-10-25.md)와 [종합 점검 보고서](rag/reports/프로젝트_종합점검_2026-10-25.json)에 기록합니다. 기존 부서·FAQ 현행성 과제와 미구현 LLM·웹 기능은 별도로 구분합니다.

## 2026-10-25 · 시연 웹의 게시판·민원 서버 범위 구체화

- 사용자 요구에 따라 시연 웹에 민원 게시판·작성 페이지와 민원을 주고받는 서버까지 구현할 계획임을 명시했습니다.
- [웹·민원 서버 구현계획](docs/plans/시연_웹_게시판과_민원_서버_구현계획.md)에 목록·상세·답변 교환·처리 상태, 업무 데이터 저장·AI 연결·API 예시와 완료 조건을 정리했습니다. 세부 설계는 제안이며 기능은 미구현입니다.
- 시연 서버 내 등록 완료와 청주시 공식 접수·외부 이관 상태를 구별하고, AI 장애 시 민원 보존과 RAG 지식·업무 데이터 분리 기준을 추가했습니다.
- README·작업 지침·계획·하네스·문서 목차와 원래 계획서 분석의 안내문을 맞췄습니다. [CASE-007](docs/cases/사례-007-시연-웹-게시판과-민원-서버-범위-구체화-2026-10-25.md)
- 실행 코드·DB·원본 데이터는 변경하지 않았습니다. 문서·링크·상태를 확인하고 웹·모델 동작 검증은 후속 구현 과제로 둡니다.

## 2026-10-25 · 한국어 주석·커밋 지침과 코드 점검

- 설명 주석·docstring과 새 커밋 제목·본문을 한국어로 작성하도록 AGENTS와 [코드 작성 규칙](docs/harness/코드_작성과_주석_규칙.md)에 명시했습니다. 기존 Google 형식을 따르고 NumPy 형식이 있는 모듈은 해당 형식을 유지합니다.
- 기존 정의 90개 중 누락된 docstring 64개와 인자·반환 설명을 보완했습니다. FAQ 상세 파서의 튜플 반환 설명과 줄바꿈 옵션도 실제 동작에 맞췄습니다.
- 재정렬 제외 검색의 기본 본문 조회를 컬렉션별 20건에서 반환 수인 5건으로 줄이고, 미사용 import 3개를 제거했습니다.
- 후보 조회·순위·검색 전용 계약 회귀 12개를 추가했고, 기존 격리 PostgreSQL 검증을 포함한 테스트 25개가 통과했습니다.
- 실제 API의 재정렬 제외 응답이 시간 외에는 수정 전과 동일했고, 재정렬 사용 FAQ 예제의 기대 문서 1위를 확인했습니다. Python 18개·정의 93개를 점검한 [보고서](rag/reports/코드_점검_2026-10-25.json)를 추가했습니다.
- 범위·결과·한계는 [CASE-006](docs/cases/사례-006-한국어-주석과-커밋-규칙-정비와-검색-조회-최적화-2026-10-25.md)에 기록합니다.

## 2026-10-25 · 프로젝트 사례 기록 체계 도입

- [사례 색인](docs/cases/README.md)과 [한국어 작성 양식](docs/cases/사례_작성_양식.md)을 추가했습니다. 번호·파일명·상태·재현·조치·검증·후속 기록 기준을 마련했습니다.
- 기존 DB·검색 구축과 LLM + RAG 우선 결정을 CASE-001·002로 정리했습니다. README의 초기·Jev 후속 흐름도 이력도 CASE-002에서 연결합니다.
- 부서 업무분장·관할과 FAQ 현행성 미확인을 CASE-003·004로 등록했습니다. 기존 자료로 확인한 미해결 과제이며 새로 발견한 코드 버그나 해결 완료 항목으로 표시하지 않습니다.
- AGENTS·README·전체 목차·하네스·실행 계획에 사례 작성과 갱신 규칙을 연결했습니다. 기록 대상은 개발 사례이며 RAG 민원 데이터와 구별합니다.
- 이번 문서 체계 도입의 배경·변경·확인 범위는 [CASE-005](docs/cases/사례-005-프로젝트-사례-기록-체계-도입-2026-10-25.md)에 기록했습니다.
- 검증 범위는 문서·상대 링크·사례 번호와 상태·기존 근거 대조입니다. 모델 평가와 데이터 재적재는 수행하지 않았습니다.

## 2026-10-25 · 문서·README·저장소 반영 점검

- 최근 LLM + RAG 우선 계획을 포함해 문서 간 구현 상태와 후속 제안을 대조했습니다.
- 문서 목차에서 시스템 구조의 현행 구현·후속 설계를 구분하고 실행 계획의 표기를 정리했습니다.
- README 상단에 한국어 구현계획·모델 제안서 바로가기를 추가하고 기능 표의 설명을 명확히 했습니다.
- 기존 문서 정리·계획 변경 항목에 실제 반영 커밋을 연결했습니다.
- 점검 범위는 문서·링크·예제·README 렌더링·GitHub 반영입니다. 기존 모델 평가 결과는 실행 당시의 기록으로 유지합니다.

## 2026-10-25 · LLM + RAG 우선 구현으로 계획 변경

반영 커밋: [`b9cd6b4`](https://github.com/hy040504/ai-complaint-process/commit/b9cd6b4ca86d5dbefef775dc929b26b0cc386b4a).

- 사용자 요구에 따라 초기 구성은 **Jev 없는 LLM + RAG**, Jev는 기준 성능 확보 후 추가하는 확장으로 변경했습니다.
- 한국어 파일명으로 [우선 구현계획](docs/plans/언어모델과_검색증강생성_우선_구현계획.md)과 [모델 선정·미세조정 제안](docs/plans/모델_선정과_미세조정_제안.md)을 추가했습니다.
- 범용 LLM 하나를 판정·생성에 재사용하는 안, 코드 검사와 담당자 검토 경로, 한국어 평가·LoRA 적용 조건을 제안했습니다. 모델 선정·추가 학습을 확정하지 않았습니다.
- README·작업 지침·구조·판정·평가·실행 계획을 맞추고, 원래 계획서 분석에는 최신 MVP와의 차이를 표시했습니다.
- 기존 검색의 `requires_gate`가 Jev 전용 계약이 아님을 명확히 했습니다. 데이터 역할·검색 계약·부서 검증 경계는 유지합니다.
- 실행 코드·원본 JSON·DB·모델 설정은 변경하지 않았습니다. 문서 검증과 조회를 수행했으며 모델 설치·학습·성능 평가 완료로 표시하지 않습니다.

## 2026-10-24 · 문서 정리와 현재 상태 명확화

반영 커밋: [`181001c`](https://github.com/hy040504/ai-complaint-process/commit/181001c6cbe3c7e288b585d50b745c48e0a798f6).

- 전체 문서의 시작점인 `docs/README.md`와 변경 이력을 추가했습니다.
- 루트 README를 현재 구현 상태, 관계형·벡터 저장 구조, 처리 흐름, 실행, 검증, 문서 안내 순으로 정리했습니다.
- 기존 배너·기술 배지를 유지하고 상태 표·목차·접이식 설치 안내를 정돈했습니다.
- FAQ 검색 결과와 향후 자연어 답변을 구분하고, 부서 사전 구축과 공식 업무분장 검증의 차이를 명시했습니다.
- 원문 내용 변경과 임베딩 모델·본문 구성 규칙 변경의 재적재 방법을 구분했습니다.
- 부서 검증 정보는 동일 ID가 유지될 때 보존된다는 조건과 기존 평가 보고서를 덮어쓰지 않는 명령을 반영했습니다.
- 데이터·검색 실행 코드는 변경하지 않았습니다. 이 작업의 점검 범위는 문서·예제·현재 적재 상태·저장소 반영이며, 기존 모델 평가를 새로 실행한 결과로 표시하지 않습니다.

## 2026-10-24 · 기본 하네스 문서

반영 커밋: [`501e02f`](https://github.com/hy040504/ai-complaint-process/commit/501e02fd2add65bf47c5bb007bf822c155c27738).

- `AGENTS.md`에 목적, 작업 위치, 데이터·검색 경계, 검증과 완료 조건을 정리했습니다.
- 하네스 안내·시스템 구조·데이터 계약·판정 정책·평가·운영 문서와 MVP 실행 계획을 추가했습니다.
- 기존 기능과 Jev 판정·평가셋·CI 등의 후속 제안을 구분하고 README에 연결했습니다.
- 문서 8개 추가와 README 갱신을 비공개 저장소에 반영했습니다.

## 2026-10-24 · 데이터·검색 기반과 첫 저장소 업로드

반영 커밋: [`51b4891`](https://github.com/hy040504/ai-complaint-process/commit/51b4891746ecc1de474d69d35f589b849c10e5cf).

| 영역 | 반영 내용 |
| --- | --- |
| 원본 정리 | 데이터는 `db/`, 계획서와 분석은 `plan/`, 수집 코드는 `PACKET/`에 배치 |
| 수집·정규화 | FAQ 94건·공개 사례 5,015건, 고정 출처 ID·URL·수집 시각, 원래/현재 부서 구분 |
| 부서 구분 | 확인된 별칭 통일, 구가 다른 동명 과 분리, 현행 담당 부서 검토 사례 27건 유지 |
| 관계형 데이터 | FAQ·공개 사례·부서 디렉터리 127개와 검색 통계 테이블 구성 |
| 벡터·검색 | 당시 BGE-M3 임베딩 5,109개(1024차원), HNSW 2개, Kiwi BM25·RRF·재정렬. 현재 코드 기본값은 e5-small 384차원([CASE-029](docs/cases/사례-029-가벼운-임베딩과-응대-CMD-2026-11-05.md)) |
| 실행 | Docker Compose, 원자적 적재·캐시 재사용, 검색 CLI/API |
| 검증 | 코드·격리 DB 테스트 13개, 검색 회귀 예제 10개, 원본/DB 대조 및 재적재 결과 |
| 문서·저장소 | 배너·기술 배지·실행 안내, Git 초기화, private 저장소 생성·업로드 |

검증 근거는 [RAG 문서](rag/README.md)와 [보고서](rag/reports/)에 있습니다. 검색 예제 10개의 통과는 한국어 민원 자동 응답 정확도나 범위 밖 판정 성능을 의미하지 않습니다.

## 남은 작업

이 호스트는 2026-11-06에 5,109건을 `dragonkue/multilingual-e5-small-ko`로 다시 임베딩했다. 검색 예제 10건과 초안 응대 평가셋 29건(개발 26/26, 보류 3/3)을 기록했다. 여권·생활쓰레기 문항은 FAQ 본문에 질문 항목이 없어 검토 갈래다. openai_api `cached_tokens`는 키가 없어 건너뛰었다. 민원 CRUD의 LLM 연결, 시민 챗봇·담당자 SSE, 운영 인증·공식 이관이 남아 있습니다. 공식 업무분장·관할과 FAQ 현행성 보완, 한국어 400문항 평가셋도 후속입니다. Jev와 LoRA는 기본 LLM + RAG 평가 이후 과제입니다. 우선순위와 완료 조건은 [실행 계획](docs/plans/harness-roadmap.md)을 따릅니다.
