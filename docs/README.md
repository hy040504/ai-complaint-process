# 문서 안내

[프로젝트 소개](../README.md) · [변경 이력](../CHANGELOG.md) · [저장소 작업 지침](../AGENTS.md)

처음에는 프로젝트 소개에서 현재 구현 범위를 확인하고, 아래에서 작업에 맞는 문서를 선택합니다. **구현된 기능**, **다음 단계의 설계**, **원래 계획서**를 구분해 읽습니다. 개별 패치의 경위는 [사례 색인](cases/README.md), 날짜별 요약은 [CHANGELOG](../CHANGELOG.md)입니다.

기준일: **2026-11-21 KST**.

## 시작점

| 하고 싶은 작업 | 먼저 읽을 문서 |
| --- | --- |
| 민원 웹 **사용법**(민원인·담당자, 화면 그림) | [사용 가이드](guides/README.md) |
| 지금 무엇이 완성됐는지 확인 | [프로젝트 README](../README.md), [기술 개요(이전 README 전체)](기술_개요.md), [업무보고서 모음 (`docs/reports/daily/`, 11/04~11/19)](reports/daily/README.md), [테스트 분석 (`docs/reports/analysis/`, 200건·112건)](reports/analysis/README.md), [2026-11-05 진행 보고](reports/진행보고-2026-11-05.md), [변경 이력](../CHANGELOG.md), 아래 [변경·패치 목록](#변경패치-목록) |
| 검색 API·CLI 설치와 실행 | [RAG 실행 문서](../rag/README.md), [네이티브 설치·운영](harness/네이티브_운영.md) |
| 터미널 메뉴로 실제 검색 시험 | [검색 테스트 메뉴](../rag/README.md#검색-테스트-메뉴), [Bash 스크립트](../rag/test-search.sh) |
| 원본 JSON·스키마 SQL·덤프·업무 PostgreSQL 위치 | [데이터 사전](../rag/origin/README.md), [검색 스키마](../rag/origin/schema/complaint_rag.sql), [업무 스키마](../src/complaints/schema/complaint_app.sql), [업무 DB 실행 설계](harness/업무DB_실행설계.md) |
| 처음 환경 준비 | Windows [`setup.cmd`](../setup.cmd), Linux [`setup.sh`](../setup.sh), [CASE-054(환경)](cases/사례-054-환경준비-스크립트와-리눅스-실행기-2026-11-06.md) · [CASE-054(업무DB)](cases/사례-054-업무DB-실행구조와-설계-정합-2026-11-06.md) |
| 응대 검사기 (`llm` 브랜치 기본) | `http://127.0.0.1:5010/`, Windows [`bin/start-lab.cmd`](../bin/start-lab.cmd), Linux [`bin/start-lab.sh`](../bin/start-lab.sh), [검사기 웹](../src/lab_web/README.md), [CASE-057](cases/사례-057-검사기웹-검색판정-연결-2026-11-06.md) · [CASE-072](cases/사례-072-검사기-청주지역선택-지명추출-2026-11-09.md) · [CASE-083](cases/사례-083-서원대후문-장소추적-MCP연동-위치인식-2026-11-13.md) · [CASE-084](cases/사례-084-K-EXAONE-API공급자-추가와-Tabular-구상-2026-11-13.md) · [CASE-085](cases/사례-085-API키-미설정시-LLM선택-비활성화-UI효과-2026-11-13.md) · [CASE-086](cases/사례-086-K-EXAONE-추론강도-최대토큰-파라미터-최적화-2026-11-13.md) · [CASE-087](cases/사례-087-패치-주석-코드최적화-문서디자인-개선-2026-11-13.md) · [CASE-088](cases/사례-088-EXAONE-429-재시도와-스트림-오류-전체점검-2026-11-13.md) · [CASE-089](cases/사례-089-패치-주석-하네스문서-최적화-디자인-개선-2026-11-13.md) · [CASE-090](cases/사례-090-검사기-LLM별-데이터-프롬프트-표시와-배치순서-변경-2026-11-13.md) |
| 한 문장 임베딩과 pgvector 이웃 | Windows [`bin/embed-sentence.cmd`](../bin/embed-sentence.cmd), [`scripts/run/embed_sentence.py`](../scripts/run/embed_sentence.py), [CASE-043](cases/사례-043-문장-임베딩과-한국어-스크립트명-2026-11-05.md), [CASE-051](cases/사례-051-문장임베딩-pgvector-이웃-2026-11-06.md) |
| 민원 문장으로 RAG+LLM 응대 | Windows [`bin/ask-assist.cmd`](../bin/ask-assist.cmd), [CASE-029](cases/사례-029-가벼운-임베딩과-응대-CMD-2026-11-05.md), [CASE-035](cases/사례-035-응대-CMD-검색API-자동시작-2026-11-05.md) |
| Windows PostgreSQL·검색 API 기동 | [`bin/start-search.cmd`](../bin/start-search.cmd), [CASE-036](cases/사례-036-Windows-RAG-PostgreSQL-로컬기동-2026-11-05.md) |
| Flask 민원 웹·검색 클라이언트·LLM·응대 연결 | [서버 안내](../src/README.md), [CASE-026](cases/사례-026-백엔드-민원웹-RAG-LLM-분리-2026-11-05.md) |
| 응대 검사기 LLM 공급자 선택 (K-EXAONE·Luna·Codex) | [서버 안내](../src/README.md), `.env.example`, [CASE-023](cases/사례-023-GPT-6-Luna-공급자-선택-2026-11-05.md), [CASE-084](cases/사례-084-K-EXAONE-API공급자-추가와-Tabular-구상-2026-11-13.md), [CASE-086](cases/사례-086-K-EXAONE-추론강도-최대토큰-파라미터-최적화-2026-11-13.md) |
| 코드 수정·검증·운영 | [작업 지침](../AGENTS.md), [하네스 안내](harness/README.md) |
| 한국어 주석·Google/NumPy 형식·커밋 규칙 확인 | [코드 작성·주석 규칙](harness/코드_작성과_주석_규칙.md) |
| 버그·개선·결정의 경위와 미해결 과제 확인·기록 | [프로젝트 사례 색인](cases/README.md), [사례 작성 양식](cases/사례_작성_양식.md) |
| Jev 없는 LLM + RAG 연결 준비 | [우선 구현계획](plans/언어모델과_검색증강생성_우선_구현계획.md), [판정 정책 초안](harness/decision-policy.md) |
| AI 완충지대에서 LLM이 지킬 사항·RAG·응답·서버 | [LLM 완충지대 하네스](harness/LLM_완충지대_하네스.md), [실제 프리픽스](harness/prompts/README.md) |
| AI 입출력 계약·프리픽스 캐싱 규칙·안전 가드레일 | [입출력 하네스](harness/AI_정보전달과_응답_하네스.md), [캐싱 지침](harness/시스템_프롬프트와_프리픽스_캐싱_지침.md), [안전 가드레일](harness/AI_안전_보안_가드레일.md) |
| 시연 웹의 게시판·민원 작성·답변 서버 설계 | [시연 웹·민원 서버 구현계획](plans/시연_웹_게시판과_민원_서버_구현계획.md) |
| CRUD·AI 답변 편집·실시간 모니터와 네 분야 작업 | [통합 상세설계](plans/민원_웹_MVP_상세설계와_분야별_작업계획.md) · [그림 포함 PDF](plans/민원_웹_MVP_상세설계와_분야별_작업계획.pdf) |
| Flask 민원 웹 Swagger를 인쇄·보고 | [청주톡톡 민원 업무 API Swagger PDF](api/청주톡톡_민원_업무_API_Swagger.pdf), 재생성 [`export_swagger_pdf.py`](../scripts/reports/export_swagger_pdf.py) |
| 민원 접수부터 AI 응답까지의 처리 과정(주소·JSON·프롬프트·판정 규칙·AI 워커·갈래별 호출 레시피, 36쪽) | [민원 AI 처리과정 상세설명서 PDF](plans/민원_AI_처리과정_상세설명서.pdf) |
| Jev를 1차 판정에 쓰는 방안(제안·미구현) | [Jev 1차 판정 도입 제안서 PDF](plans/Jev_1차판정_도입_제안서.pdf) |
| LLM 추천·LoRA 필요 여부 검토 | [모델 선정과 미세조정 제안](plans/모델_선정과_미세조정_제안.md) |

## 현재 구현과 데이터 위치

- **검색·판정 계층:** 검색 CLI/API, 응대 CLI/`minwon`/`src/lab_web` `:5010`이 로컬에서 동작하며, `docs/harness/prompts/` `PREFIX-00~04`로 판정·조건 보존 FAQ 안내·담당자 초안(`out_of_scope` 고정 템플릿)·순화 요약을 분리 실행(`PREFIX-03∥04` 병렬, 순수 타지역 `early_external_reject`)합니다.
- **응대 검사기 (`:5010`, `llm` 브랜치 기본):** 제목·상세로 지명·도로명+번지·사례 235쌍 도로 색인·네이버 지도(`address`/`ac`·HTTP 400/429 60초 서킷브레이커)를 추적해 검색하고 선택한 공급자(`K-EXAONE 2.5` 단계별 차등 `high<=8192`/`low<=4096`·타임아웃 `low` 1회 재시도·`GPT-6 Luna`·`Codex CLI`)로 판정하며, 오른쪽 테스트 기록(`.rag-cache/lab-runs`) 클릭 시 입력 폼을 복원합니다. Codex MCP는 줄 단위 JSON-RPC이며 `search_complaint_rag`·`lookup_navermap_place` 2종을 제공합니다(`PREFIX-02`/`03`/`04`는 `_disable_mcp`, `PREFIX-03`/`04` JSON 복구·1회 재시도 및 Codex 오류 축약 적용).
- **시연 웹 (`:5000`):** 시민·담당자 UI, 한국어 Swagger(`/docs`·`/swagger`·`#/staff/api`, **36경로 · 44오퍼레이션**), Flask, **민원인·담당자 아이디/비밀번호 로그인(`/api/v1/auth/*`, `scrypt`·5회 `429` 잠금·부서 범위 RBAC·간단 가입)**, **현장 사진·PDF 파일 첨부(`/api/v1/complaints/{id}/attachments*`, 매직바이트 검증·EXIF 자동 제거·비공개 `404` 격리·연쇄 정리)**, **PostgreSQL `complaint_app` 7테이블 정규화 + `chat_sessions`/`attachments`**, 비동기 AI 분석 워커, **담당자 실시간 SSE 푸시(`/api/v1/staff/events`)**, **시민 다중 턴 AI 챗봇(`/api/v1/citizen/chat*`)**, **담당자 RBAC 통계 대시보드(`#/staff/stats`)·큐 통합 검색·수식 방어 CSV 내보내기**를 지원합니다.
- **임베딩·평가 범위 및 후속:** 기본 임베딩은 CPU `dragonkue/multilingual-e5-small-ko`(5,109건 적재 완료)이며 200건 실증 `190/200 (95.0%)` → 혼합 100건 재검증 `98/100 (98.0%)` → **Codex CLI 전용 신규 100건 실증 `99/100 (99.0%, CASE-113)`**과 규칙 `112/5,015` 회귀를 통과했습니다. 외부 PASS/행정 SSO 연동·`openai_api` `cached_tokens` 실측·다중 워커 브로커(현 단계 제외)·청주시 공식 이관은 후속입니다.

| 구분 | 위치 | 상태 |
| --- | --- | --- |
| FAQ·사례 원문 | `rag/origin/자주_묻는_민원.json`, `rag/origin/공개_민원_사례.json` | Git에 포함. 94건·5,015건 |
| 검색 테이블 정의 | `rag/origin/schema/complaint_rag.sql` | Git에 포함. `rag/store.py`가 읽음 |
| 게시판 PostgreSQL 스키마 | `src/complaints/schema/complaint_app.sql`, `rag/db/sql/02_complaint_app.sql` | Git에 포함. **7개 핵심 정규화 테이블(`users`·`complaints`·`messages`·`message_versions`·`ai_jobs`·`ai_results`·`job_events`) + 보조 3테이블(`idempotency`·`answer_templates`·`app_meta`)**, 생성 칼럼 5개·CHECK 27종·`complaint_rag` 교차 FK. [실행 설계](harness/업무DB_실행설계.md) |
| 검색 실데이터(벡터 포함) | 우분투 PostgreSQL DB 이름 `complaints_native`, 스키마 `complaint_rag` | 클러스터 경로 `/var/lib/postgresql/18/main`. 프로젝트 파일이 아님 |
| 검색 DB 복사본 | `rag/origin/dumps/complaint_rag.dump` | Git 제외. 우분투에서 `scripts/ops/export-dump.sh` |
| 시연 웹 민원·답변 | PostgreSQL 스키마 `complaint_app` | Flask 기본. 검색 `complaint_rag`와 분리 |
| 임베딩 체크포인트 | `complaint_rag.embedding_cache` | 적재 벡터 재사용. 예전 sqlite 캐시 대체 |
| 모델 캐시 | `.rag-cache/` | Hugging Face 모델·평가 보고. Git 제외 |

SQL만으로는 검색 행이 없습니다. 다른 컴퓨터에서 검색까지 쓰려면 dump를 가져가거나 JSON으로 `python -m rag ingest`를 실행합니다. 스키마만 적용은 `scripts/ops/apply-schema.sh`, dump 복원은 `scripts/ops/restore-dump.sh`입니다. [CASE-016](cases/사례-016-프로젝트-내부-DB-파일-배치-2026-10-31.md) · [CASE-039](cases/사례-039-검색코퍼스와-업무스키마-배치-2026-11-05.md)

## 변경·패치 목록

상세 본문은 각 사례, 날짜별 한 줄 요약은 [CHANGELOG](../CHANGELOG.md)입니다.

| 사례 | 기준일 | 변경 내용 | 상태 |
| --- | --- | --- | --- |
| [CASE-125](cases/사례-125-민원인·담당자-사용-가이드와-주석-캡처-도구-2026-11-23.md) | 2026-11-23 | 민원인·담당자 사용 가이드(번호 화면 그림 19장·PDF)와 주석 캡처 도구 | 완료 |
| [CASE-126](cases/사례-126-Swagger-PDF-갱신과-오래된-점검-문제-정리-2026-11-23.md) | 2026-11-23 | Swagger PDF 갱신과 오래된 점검 문제 정리 | 완료 |
| [CASE-127](cases/사례-127-공개-주소의-담당자-콘솔-API-화면-복구-2026-11-23.md) | 2026-11-23 | 공개 주소의 담당자 콘솔 API 화면 복구 | 완료 |
| [CASE-128](cases/사례-128-담당자-사이트-단독화와-응대검사기-별도-경로-2026-11-23.md) | 2026-11-23 | 담당자 사이트 단독화와 응대 검사기 별도 경로 | 완료 |
| [CASE-129](cases/사례-129-응대-검사기-담당자-인증과-실행-횟수-제한-2026-11-23.md) | 2026-11-23 | 응대 검사기 담당자 인증과 실행 횟수 제한 | 완료 |
| [CASE-130](cases/사례-130-가이드-화면-보강과-PDF-쪽나눔-및-서버-PG-테스트-오류-원인-2026-11-23.md) | 2026-11-23 | 가이드 화면 보강과 PDF 쪽 나눔, 서버 PG 테스트 오류 원인 | 완료 |
| [CASE-131](cases/사례-131-민원웹-디자인-다듬기-시안표기-개발용어-정리-2026-11-23.md) | 2026-11-23 | 민원 웹 디자인 다듬기 (시안 표기·개발 용어 정리) | 완료 |
| [CASE-132](cases/사례-132-서비스-이름-청주톡톡-통일과-비로그인-민원게시판-열람-2026-11-23.md) | 2026-11-23 | 서비스 이름 "청주톡톡" 통일과 비로그인 민원 게시판 열람 | 완료 |
| [CASE-124](cases/사례-124-게스트-공개-정책의-수정-구멍-보정과-담당자-게시판-내리기-2026-11-23.md) | 2026-11-23 | 게스트 공개 정책의 수정 우회 구멍 보정과 담당자 게시판 내리기(`PUT /visibility`) | 완료 · 로컬 |
| [CASE-123](cases/사례-123-시연-비밀번호-환경변수-이전과-푸시-배포-2026-11-22.md) | 2026-11-22 | 시연 비밀번호를 코드·문서에서 빼 환경변수로 이전(공개 저장소 노출 방지)하고 푸시·배포 | 완료 |
| [CASE-122](cases/사례-122-plan을-docs-plans로-db를-rag-db로-재배치-2026-11-22.md) | 2026-11-22 | `plan/`→`docs/plans/`, `db/`→`rag/db/` 재배치와 링크 183개 보정 | 완료 |
| [CASE-121](cases/사례-121-글자대비-보정과-홈·모바일-개선-및-README-쉬운-개편-2026-11-22.md) | 2026-11-22 | 글자 대비 보정(미달 270→0)·홈 입력창 위로·모바일 로그인 복구, README 쉬운 개편과 역할 그림 | 완료 |
| [CASE-120](cases/사례-120-디자인-토큰과-공통-상태칩-모션-적용-2026-11-21.md) | 2026-11-21 | 디자인 토큰·공통 상태 칩·동적 효과(카운트업·진입·새 행 플래시), 다크 회귀 수정과 CSS 무결성 테스트 | 일부 완료 |
| [CASE-119](cases/사례-119-비로그인-게스트-접수와-방문자-홈-2026-11-21.md) | 2026-11-21 | 비로그인 게스트 접수·방문자 홈, 로그인 모달 단순화 | 완료 |
| [CASE-118](cases/사례-118-무료-외부-공개-Cloudflare-Quick-Tunnel-2026-11-21.md) | 2026-11-21 | 민원 웹 무료 외부 공개(Cloudflare Quick Tunnel), HTTPS 쿠키·보안 헤더, 프록시 경유 시 문서 숨김 | 완료 |
| [CASE-117](cases/사례-117-시민·담당자-사이트-분리와-원격-서버-배포-2026-11-21.md) | 2026-11-21 | 시민(`/`)·담당자(`/staff/`) 사이트 분리, 사이트별 세션, 담당자 계정 관리 CLI, 서버 배포 | 완료 |
| [CASE-116](cases/사례-116-프로젝트-폴더-파일-구조-정비-2026-11-21.md) | 2026-11-21 | 폴더·파일 구조 정비: `scripts` 분류·`bin/`·`db/`·`docs/reports`·`plan/archive`·`src/search_client`·저장소/서비스 모듈 분리 | 완료(일부) |
| [CASE-115](cases/사례-115-민원-파일첨부-업로드-EXIF제거-권한격리-구현-2026-11-21.md) | 2026-11-21 | 민원 현장 사진(JPG·PNG·WebP)·PDF 파일 첨부 업로드(표준 라이브러리 매직바이트 검증·EXIF/GPS 자동 제거·최대 5개×5MB·비공개 `404` 격리·CSP 샌드박스·일반 JSON 64 KiB 한도 유지·민원 삭제 시 디스크 연쇄 정리), 작성 드롭존·상세 썸네일/라이트박스·담당자 큐 `첨부 N` 배지, Swagger PDF 36경로 갱신 및 `189`/`49`/`36`/실PG·Edge E2E(`0오류`) 검증 | 완료 |
| [CASE-114](cases/사례-114-시민-다중턴챗봇-PG영속저장과-담당자-통계대시보드-CSV내보내기-구현-2026-11-21.md) | 2026-11-21 | 시민 다중 턴 챗봇(0ms 문맥 보강·`PREFIX` 보존·로그인 PostgreSQL `chat_sessions`/`chat_messages` 영속 저장·타인 404/담당자 403 격리·비로그인 `sessionStorage` 임시 저장) + 담당자 RBAC 통계 대시보드(`#/staff/stats` · 5종 드릴다운 차트 · 시연 토글) + 큐 통합 검색(제목·본문·ID·부서)·AI 판정·정렬·수식 주입 방어 CSV 내보내기, Swagger PDF 34경로 갱신 및 `186`/`49`/`33`/실PG·Edge E2E(`0오류`) 검증 | 완료 |
| [CASE-113](cases/사례-113-100건실증-세부문제-패치와-Codex-CLI-신규100건-실증평가-2026-11-20.md) | 2026-11-20 | `CASE-109` 세부 문제 패치(`PREFIX-01` 명확 불가 FAQ·일반 주의사항/예외 구분, 단일·다중행 JSON 복구·1회 재시도, Codex 오류 240자 축약, `staff_draft` `_disable_mcp`, EXAONE `decision <=8192`/타임아웃 `low` 재시도, 미고정 폴백, 시설·가족 불용어 24종·동명/복합시설 본체 우선순위), `:5010` Codex 전용 신규 100건 **`99/100 (99.0%)`** + 사후 표적 **`5/5`** 재검증 및 6쪽 분석 보고서 | 완료 |
| [CASE-112](cases/사례-112-실시간SSE-시민챗봇-로그인-7테이블정규화-후속품질검수와-최적화-2026-11-20.md) | 2026-11-20 | `CASE-110·111` 패치 후속 QA 검수·최적화: `message_versions` 이력 불변 보존(`DO NOTHING`), `change()` 잠금 내 RBAC 재검증(TOCTOU 제거), `StaffEventBroker._replay_since_locked` 중복 통합, `LoginRateLimiter` 만료 정리, 구 UI 문구 5곳 정정·Swagger 세션 표시 보강 및 전수 재검증 | 완료 |
| [CASE-111](cases/사례-111-운영-본인담당자-인증과-PostgreSQL-7테이블-정규화-구현-2026-11-20.md) | 2026-11-20 | 민원인·담당자 아이디/비밀번호 로그인(`/api/v1/auth/*`: `scrypt`·5회 `429` 잠금·부서 RBAC·2탭 로그인 모달·간단 가입·다중 사용자 격리; OTP 본인확인 제거로 간소화) 및 PostgreSQL 7테이블 정규화(`users`~`job_events`·`automatic_transfer=false` CHECK·`complaint_rag` 교차 FK·자동 백필·`GET /api/v1/staff/db-summary`), Swagger PDF 30경로 갱신 및 `179`/`29`/실PG·Edge E2E 검증 | 완료 |
| [CASE-110](cases/사례-110-담당자-실시간-SSE-푸시와-시민-AI-챗봇-실연결-구현-2026-11-20.md) | 2026-11-20 | 담당자 실시간 SSE 푸시(`GET /api/v1/staff/events`, `StaffEventBroker`·`Last-Event-ID`·`resync_required`·3초 대체) 및 시민 AI 챗봇 실연결(`POST /api/v1/citizen/chat(/stream)`, 비공개 초안/순화 구조 차단·`include_staff_outputs=False`), Swagger PDF 25경로 갱신 및 `176`/`27`/Edge E2E 검증 | 완료 |
| [CASE-109](cases/사례-109-패치후-100건-실증재검증-98퍼센트와-생활시설-노이즈보강-2026-11-20.md) | 2026-11-20 | 패치 후 `:5010` 100건 실증 재검증(`98/100, 98.0%`, 실응답 `98/99, 99.0%`; 기존 미통과 10/10·노이즈 13/13 전원 해소·신규 39/40 통과), `하수구` 등 생활 기반시설 14종 불용어 보강·중복/스레드안전 최적화·전수 주석/README 3단계 추이표 정비(`src/tests 172`) | 완료 |
| [CASE-108](cases/사례-108-11월19일-업무보고-코드공통화-전체주석-최종검증-2026-11-20.md) | 2026-11-20 | 11/19 종합 업무보고 8쪽 PDF([`업무보고_20261119.pdf`](reports/daily/업무보고_20261119.pdf)), `report_common.py` UI 캡처 공용화, 저장소 114 Py/21 JS 전수 docstring/JSDoc·`db/load_samples.py`·`compare_assist.py` 정비, `README.md`/`docs/README.md` 가독성 개편 및 최종 검증 | 완료 |
| [CASE-107](cases/사례-107-패치정비-주석JSDoc-코드최적화-README디자인-최종검증-2026-11-20.md) | 2026-11-20 | 패치 정비: `place_tool`/`district` 중복 추론·미사용 import 제거, `eval_set --strict`, 테스트 모의 docstring 21건·JSDoc 보완, `decision-policy`/`architecture`/`README` 정비 및 전수 검증(`171`/`49`/`22`) | 완료 |
| [CASE-106](cases/사례-106-단독검사기-200건-미통과-10건과-노이즈-개선패치-및-실서버-재검증-2026-11-19.md) | 2026-11-19 | 200건 실증 비통과 10건(`B12·A35·A31·C09·B22~B24·B35·F05·F09`)·장소 노이즈 13건·`C32`/`D20` 경계 패치(`address`/`ac` 파싱, HTTP 400 서킷브레이커, 사례 도로+번지 색인, 일반시설/관공서 필터, `PREFIX-01` 예외/조건 가드, `staff_draft` 4096 상한) 및 `:5010` 표적 12건·`src/tests 171` 통과 | 완료 |
| [CASE-105](cases/사례-105-단독검사기-5010-200건-실증평가와-SourceTrail-분석보고서-2026-11-19.md) | 2026-11-19 | `:5010` 200건(기존 112건 재측정+신규 88건) 재실증 (`190/200, 95.0%`·D축 100%·EXAONE 14/14·조기차단 0.012s), SourceTrail 스타일 14쪽 PDF·SVG 4종 생성 및 잔여 한계 4과제 식별 | 완료 |
| [CASE-104](cases/사례-104-잔여한계패치-주석-하네스동기화-중복최적화-최종검증-2026-11-19.md) | 2026-11-19 | `CASE-103` 후속 최적화(`_split_external_residence_clause`·조기 반환)·신규 테스트 docstring·하네스 6종·`README.md`(`PREFIX` 전용 섹션/구조도 SVG·가독성 개편)·`project-banner.svg` 겹침 수정·11/18 종합 보고 PDF(10쪽·Swagger 4종) 및 최종 재검증 (`168`/`49`/`rag.verify`/`22/22`/`:5010` `0.011s`) | 완료 |
| [CASE-103](cases/사례-103-잔여한계-도로번지-광역시약칭-거주지예외-EXAONE추론차등-병렬실행-2026-11-18.md) | 2026-11-18 | 112건/5,015건 잔여 한계 개선: `place_tool` 도로+번지(93건)·하이픈·불용어, `district` 닫는괄호·100% 단일구 도로(+54건)·광역시 `~시`·외부 도로명·거주지/운수 예외, `B14` 오탐 교정, EXAONE 단계별 추론(`high`/`low`)·`PREFIX-03∥04` 병렬·조기 차단(`0.02s`)·`usage` 격리 및 규칙 회귀 스크립트 | 완료 |
| [CASE-102](cases/사례-102-Swagger포털-1117보고서-주석-최적화-README디자인-최종점검-2026-11-18.md) | 2026-11-18 | `CASE-101` Swagger 포털·`daily_report_20261117.py` 주석/f-string 교정, `api-docs.js`/`app.js` 캐시·중복 제거, `#/staff/api` 다크 색인 대비·README 3행 디자인 개선 및 최종 검증 | 완료 |
| [CASE-101](cases/사례-101-민원웹-5000-백엔드-Swagger-포털과-담당자콘솔-API문서-구현-2026-11-17.md) | 2026-11-17 | `:5000` `/docs`·`/swagger` 한국어 대화형 Swagger 포털(`?embed=1`·다크 동기화·세션 전환), 담당자 `#/staff/api` 콘솔·빠른 색인, `api.py` 태그 정정 및 Swagger PDF 재생성 | 완료 |
| [CASE-100](cases/사례-100-문맥기반-순화판단과-지명장소추론-결함보완-2026-11-17.md) | 2026-11-17 | `PREFIX-01` 문맥 `sanitize_needed`·`sarcasm_mockery` 순화, `district.py` 동+숫자·단일구 랜드마크·동명이인 타지역 차단, `policy.py` `out_of_scope` 강제, `place_tool.py` 서술어 배제·불용어·우선정렬 보완 | 완료 |
| [CASE-099](cases/사례-099-112건-시각화분석보고서와-테스트폴더-분리-최종점검-2026-11-17.md) | 2026-11-17 | 112건 실증 SVG 차트 4종·MD/6쪽 PDF 상세 분석 보고서 생성, `docs/reports/analysis/` 분리, `report_common.py` 중복 제거 및 README 차트 디자인 개선 | 완료 |
| [CASE-098](cases/사례-098-검사기-기록-폼복원과-업무보고-전용폴더-통합-2026-11-17.md) | 2026-11-17 | `:5010` 테스트 기록 클릭 시 입력 폼(`fillComplaintForm`) 자동 복원, 11/16 종합 업무보고 5쪽 PDF 작성 및 `docs/reports/daily/` 일괄 통합·주석/코드 최적화 | 완료 |
| [CASE-097](cases/사례-097-단독검사기-5010-청주한정-112건-실증테스트와-한계식별-2026-11-17.md) | 2026-11-17 | 단독 검사기(`:5010`) 청주 한정 110건(+타지역 2건=112건) 5대 축 실증 테스트, 탐지·지명 한계 3건 식별 및 주석·부서명 캐시·README 정리 | 완료 |
| [CASE-096](cases/사례-096-패치-주석-최적화-문서디자인-최종점검-2026-11-16.md) | 2026-11-16 | 최근 패치(CASE-094·095) 주석/docstring/JSDoc 보완, TTL/더미검증/세션 캐시 최적화, 문서 디자인·정합 최종 점검 및 검증 | 완료 |
| [CASE-095](cases/사례-095-담당자-부서배정-및-답변템플릿-추가삭제-2026-11-16.md) | 2026-11-16 | 담당자 사이트 청주시 127개 다른 부서 배정(검색·AI 후보 선택·해제) 및 답변 템플릿 커스텀 추가·삭제·복원(`answer_templates` DB) | 완료 |
| [CASE-094](cases/사례-094-다크테마-청주시로고-호버-검사기UI-담당자폰트-시민민원삭제-2026-11-16.md) | 2026-11-16 | 다크 테마 청주시 투명 로고·서비스 SVG·호버 19종 수정, `#/lab`·`:5010` UI 다듬기 및 다크 토글, 담당자 폰트 확대, 시민 영구 삭제(`POST /complaints/{id}/delete`) | 완료 |
| [CASE-093](cases/사례-093-민원웹-CRUD-검사기-LLM-RAG-실시간통합-2026-11-15.md) | 2026-11-15 | 민원 웹(`:5000`) CRUD 비동기 AI 분석(`EXAONE`/`Codex`/`openai_api` 가드)·담당자 콘솔 `aiAssist`·`#/lab` 검사기 패리티·`rerank=False` 기본값·실서버 E2E 검증 | 완료 |
| [CASE-092](cases/사례-092-main브랜치-UI04-업무DB-비응대기능-병합-2026-11-13.md) | 2026-11-13 | `origin/main` 비응대 기능(UI02~04·편집기, `db/`, 생성 칼럼 5개·CHECK 3종·`seed-public-demo`, `업무DB_실행설계.md`) 선택 병합 (`:5010`·LLM 로직 보존) | 완료 |
| [CASE-091](cases/사례-091-패치-주석-코드최적화-문서디자인-최종점검-2026-11-13.md) | 2026-11-13 | 패치 후속 `legacy` 배지·`.env 기본` 엔진명 표시·`applyLlmSection()` 중복 제거·문서 동기화 및 전체 테스트/실서버 최종 검증 | 완료 |
| [CASE-090](cases/사례-090-검사기-LLM별-데이터-프롬프트-표시와-배치순서-변경-2026-11-13.md) | 2026-11-13 | 검사기 데이터(JSON) 영역 위·프롬프트 영역 아래 배치 및 엑사온 API·Codex CLI·GPT API 동적 표시(`llmProvider`·`resolvedProvider`) | 완료 |
| [CASE-089](cases/사례-089-패치-주석-하네스문서-최적화-디자인-개선-2026-11-13.md) | 2026-11-13 | 패치 주석·JSDoc·`models.py`/`complete.py` 최적화, 하네스 4종 동기화 및 README 디자인·검증 근거 최신화 | 완료 |
| [CASE-088](cases/사례-088-EXAONE-429-재시도와-스트림-오류-전체점검-2026-11-13.md) | 2026-11-13 | 전체 연동 점검: HTTP 429(`retry-after`·백오프) 재시도, API 실패 연쇄 호출 차단, `EXAONE_URL`/`EXAONE_MODEL` 격리, 스트림 버퍼·422 보완 | 완료 |
| [CASE-087](cases/사례-087-패치-주석-코드최적화-문서디자인-개선-2026-11-13.md) | 2026-11-13 | 패치 점검(주소 키/잠금 복원 경쟁 버그 수정)·장소추적 재귀/중복 조회 최적화·문서/README 디자인 개선 | 완료 |
| [CASE-086](cases/사례-086-K-EXAONE-추론강도-최대토큰-파라미터-최적화-2026-11-13.md) | 2026-11-13 | LG K-EXAONE 2.5 `max_tokens` 16384 상향 및 `EXAONE_REASONING_EFFORT` 연동·방어 파싱 | 완료 |
| [CASE-085](cases/사례-085-API키-미설정시-LLM선택-비활성화-UI효과-2026-11-13.md) | 2026-11-13 | 검사기 UI 키/실행파일 미설정 공급자 비활성화 및 흔들림 안내 효과 | 완료 |
| [CASE-084](cases/사례-084-K-EXAONE-API공급자-추가와-Tabular-구상-2026-11-13.md) | 2026-11-13 | LG AI연구원 K-EXAONE 2.5 API 공급자(`exaone_api`) 추가 및 EXAONE Tabular 연동 구상 문서화 | 완료 |
| [CASE-083](cases/사례-083-서원대후문-장소추적-MCP연동-위치인식-2026-11-13.md) | 2026-11-13 | 서원대학교 후문 등 시설명 민원 장소 추적 및 네이버 지도 MCP 연동을 통한 위치·부서 인식 개선 | 완료 |
| [CASE-082](cases/사례-082-패치-주석-문서-최적화-2026-11-11.md) | 2026-11-11 | 패치 주석 정비·README 기준일 및 업무보고서 링크 최신화·문서 최적화 | 완료 |
| [CASE-081](cases/사례-081-11월11일-업무보고서-PDF-생성과-UI변경-병합-2026-11-11.md) | 2026-11-11 | 11월 11일 업무보고서 PDF 생성 및 기민 님 11/11 UI 변경 보고서 3페이지 무손실 병합 | 완료 |
| [CASE-080](cases/사례-080-11월10일-업무보고서-PDF-생성과-UI변경-병합-2026-11-10.md) | 2026-11-10 | 11월 10일 업무보고서 PDF 생성 및 기민 님 UI 변경 보고서 6페이지 무손실 병합 | 완료 |
| [CASE-079](cases/사례-079-패치-주석-문서-최적화-2026-11-10.md) | 2026-11-10 | 패치 주석 정비·README 다이어그램/배지 디자인 개편·장소 추적 캐시 최적화 | 완료 |
| [CASE-078](cases/사례-078-네이버지도-비로그인-장소추적-MCP-도구-2026-11-10.md) | 2026-11-10 | 네이버 지도 비로그인 장소 주소 추적 MCP 도구(`lookup_navermap_place`) 구현 및 등록 | 완료 |
| [CASE-077](cases/사례-077-패치-주석-문서-최적화-2026-11-10.md) | 2026-11-10 | 코드 주석 정비·README/문서 갱신·UI/API 검증 최적화 | 완료 |
| [CASE-076](cases/사례-076-검사기-화면-assist-초기화전참조-수정-2026-11-10.md) | 2026-11-10 | 검사기 화면 assist 변수 초기화 전 참조 오류 수정 | 완료 |
| [CASE-070](cases/사례-070-검사기-Codex프롬프트전문-2026-11-09.md) | 2026-11-09 | 검사기에 Codex stdin 전문 표시 | 완료 |
| [CASE-069](cases/사례-069-검사기-응답JSON-복사단추-2026-11-09.md) | 2026-11-09 | 검사기 결과 JSON 칸마다 복사 단추 | 완료 |
| [CASE-068](cases/사례-068-패치-주석-문서-최적화-2026-11-07.md) | 2026-11-07 | 보류셋 실측 주석·README·보고 경로 | 완료 · 이 커밋 |
| [CASE-067](cases/사례-067-패치-주석-문서-최적화-2026-11-07.md) | 2026-11-07 | CASE-064~066 주석·README·기록 JSON 읽기 | 완료 · GitHub는 CASE-067 |
| [CASE-066](cases/사례-066-검사기-테스트기록-파일저장-2026-11-06.md) | 2026-11-06 | 검사기 테스트 기록을 파일로 저장 | 완료 · GitHub는 CASE-066 |
| [CASE-065](cases/사례-065-검사기-테스트기록목록-2026-11-06.md) | 2026-11-06 | 검사기 오른쪽 테스트 기록 목록 | 완료 · GitHub는 CASE-065 |
| [CASE-064](cases/사례-064-초안응대평가셋확대-2026-11-06.md) | 2026-11-06 | 초안 응대 평가셋 29건, 개발/보류 분할, 조건 부족 안내 금지 | 완료 · 개발 26/26 · 보류 3/3 |
| [CASE-063](cases/사례-063-여권FAQ조건부족-검사기사유표시-2026-11-06.md) | 2026-11-06 | 여권 FAQ 조건 부족, 검사기 사유, 평가 라벨 정정 | 완료 · GitHub는 CASE-063 |
| [CASE-062](cases/사례-062-PREFIX캐시조립-공급자비교-초안평가-2026-11-06.md) | 2026-11-06 | PREFIX 조립 적격, openai_api 비교 건너뜀, 초안 응대 | 완료 · GitHub는 CASE-062. 여권 문항은 CASE-063 |
| [CASE-061](cases/사례-061-PREFIX-03-04-검색재평가-실측-2026-11-06.md) | 2026-11-06 | PREFIX-03/04 연결, 검색 예제 10건, codex_cli 실측 | 완료 · GitHub는 CASE-061 |
| [CASE-060](cases/사례-060-패치-주석-문서-최적화-2026-11-06.md) | 2026-11-06 | CASE-057~059 주석·README·MCP 본문 검사 | 완료 · GitHub는 CASE-060 |
| [CASE-059](cases/사례-059-검사기-Codex입력-표시-2026-11-06.md) | 2026-11-06 | 검사기에 Codex 사용자 JSON 표시 | 완료 · GitHub는 CASE-060 |
| [CASE-058](cases/사례-058-Codex-MCP-핸드셰이크-줄단위JSON-2026-11-06.md) | 2026-11-06 | Codex MCP 줄 단위 JSON-RPC 핸드셰이크 | 완료 · GitHub는 CASE-060 |
| [CASE-057](cases/사례-057-검사기웹-검색판정-연결-2026-11-06.md) | 2026-11-06 | 검사기 웹 민원 JSON → 검색 API → 판정 | 완료 · 핸드셰이크는 CASE-058 |
| [CASE-056](cases/사례-056-응대검사기-웹추출과-수신API-2026-11-06.md) | 2026-11-06 | 검사기 프론트 추출과 민원 JSON 수신 API | 완료 · 판정 연결은 CASE-057 |
| [CASE-055](cases/사례-055-llm브랜치-응대검사기-집중-2026-11-06.md) | 2026-11-06 | GitHub `llm` 브랜치, 기본 화면 `/#/lab` | 완료 · GitHub 기본 브랜치 `llm` |
| [CASE-054](cases/사례-054-환경준비-스크립트와-리눅스-실행기-2026-11-06.md) | 2026-11-06 | setup.cmd/setup.sh와 영어 파일명 Linux 실행기 | 완료 · GitHub는 `llm` 브랜치 |
| [CASE-053](cases/사례-053-패치-주석-문서-최적화-2026-11-06.md) | 2026-11-06 | CASE-051·052 주석·README·이웃 조회 순서 정리 | 완료 · 이 커밋 |
| [CASE-052](cases/사례-052-한국어-e5-small-ko-임베딩-2026-11-06.md) | 2026-11-06 | 기본 임베딩을 dragonkue multilingual-e5-small-ko로 바꾸고 5,109건 재적재 | 완료 · GitHub는 CASE-053 |
| [CASE-051](cases/사례-051-문장임베딩-pgvector-이웃-2026-11-06.md) | 2026-11-06 | 문장 임베딩 뒤에 FAQ·사례 pgvector 이웃 출력 | 완료 · GitHub는 CASE-053 |
| [CASE-050](cases/사례-050-패치-주석-문서-최적화-2026-11-06.md) | 2026-11-06 | CASE-046~049 주석·README·검색 후보 직렬화 정리 | 완료 · 이 커밋 |
| [CASE-049](cases/사례-049-업무테이블-version-컬럼-2026-11-06.md) | 2026-11-06 | 예전 업무 테이블에 `version` 컬럼을 채움 | 완료 · GitHub는 CASE-050 |
| [CASE-048](cases/사례-048-Codex-RAG-검색-도구-2026-11-06.md) | 2026-11-06 | Codex `search_complaint_rag`와 PREFIX-00~04 호출 조건 | 완료 · 핸드셰이크는 CASE-058 |
| [CASE-047](cases/사례-047-Codex-허용-도구-조건-2026-11-06.md) | 2026-11-06 | Codex·PREFIX-00은 개발자가 허용한 도구만 사용 | 완료 · GitHub는 CASE-050 |
| [CASE-046](cases/사례-046-기동-CMD-창-유지-2026-11-06.md) | 2026-11-06 | `bin/start-search.cmd` 창 유지, `bin/embed-sentence.cmd` 문장 입력 | 완료 · GitHub는 CASE-050 |
| [CASE-045](cases/사례-045-패치-주석-문서-최적화-2026-11-06.md) | 2026-11-06 | CASE-043·044 주석·README 디자인·PREFIX 조립 정리 | 완료 · 이 커밋 |
| [CASE-044](cases/사례-044-LLM-완충지대-하네스와-프리픽스-원문-2026-11-06.md) | 2026-11-06 | LLM 완충지대 하네스 정리와 PREFIX-00~04 원문 파일 | 완료 · GitHub는 CASE-045 |
| [CASE-043](cases/사례-043-문장-임베딩과-한국어-스크립트명-2026-11-05.md) | 2026-11-05 | 한 문장 임베딩 숫자 출력과 실행 스크립트 한국어 파일명 | 완료 · GitHub는 CASE-045 |
| [CASE-042](cases/사례-042-AI-입출력-프리픽스-캐싱-하네스-2026-11-05.md) | 2026-11-05 | 두 기획서와 현재 코드를 결합한 AI 입출력·프리픽스 캐싱 시스템 프롬프트·안전 가드레일 하네스 3종 | 완료 · 로컬 문서 |
| [CASE-041](cases/사례-041-잔여-SQLite-삭제-2026-11-05.md) | 2026-11-05 | 시연 sqlite 잔여와 `db/app` 안내 폴더 삭제 | 완료 · 로컬 |
| [CASE-040](cases/사례-040-패치-주석-문서-최적화-2026-11-05.md) | 2026-11-05 | CASE-035~039 주석·README 디자인·콘솔 기동 공유 | 완료 · 로컬 |
| [CASE-039](cases/사례-039-검색코퍼스와-업무스키마-배치-2026-11-05.md) | 2026-11-05 | 검색 원본을 `rag/origin`, 업무 스키마를 `src/complaints/schema`로 배치 | 완료 · 로컬 경로 |
| [CASE-038](cases/사례-038-Windows-Codex-명령줄-길이-2026-11-05.md) | 2026-11-05 | Codex CLI stdin + Windows npm 래퍼 우회 | 완료 · 로컬. 실호출 확인 |
| [CASE-036](cases/사례-036-Windows-RAG-PostgreSQL-로컬기동-2026-11-05.md) | 2026-11-05 | Windows 사용자 디렉터리 PostgreSQL·RAG `.venv`·e5-small 적재 | 완료 · 이 호스트 로컬 |
| [CASE-035](cases/사례-035-응대-CMD-검색API-자동시작-2026-11-05.md) | 2026-11-05 | `bin/ask-assist.cmd`가 꺼진 localhost 검색 API를 자동 시작 | 완료 · 로컬 스크립트. 실검색은 후속 |
| [CASE-034](cases/사례-034-패치-주석-문서-최적화-2026-11-05.md) | 2026-11-05 | CASE-031~033 주석·현재 문서·README 디자인·캐시 조회 | 완료 · 로컬 |
| [CASE-033](cases/사례-033-민원웹-Swagger-PDF-2026-11-05.md) | 2026-11-05 | Flask `/docs` Swagger를 OpenAPI 스냅샷 PDF로 `docs/`에 저장 | 완료 · 로컬 문서 |
| [CASE-032](cases/사례-032-호환모듈-제거-2026-11-05.md) | 2026-11-05 | 루트 호환 모듈 삭제, `src.complaints` 직접 import | 완료 · 로컬 |
| [CASE-031](cases/사례-031-업무저장-PostgreSQL-통일-2026-11-05.md) | 2026-11-05 | 시연 웹·임베딩 캐시를 PostgreSQL로 통일 | 완료 · 로컬. 7테이블 정규화는 후속 |
| [진행 보고](reports/진행보고-2026-11-05.md) | 2026-11-05 | CASE-023~034을 보고용으로 요약한 문서 | 로컬 문서 |
| [CASE-030](cases/사례-030-임베딩-주석-문서-최적화-2026-11-05.md) | 2026-11-05 | e5-small·CMD 주석·README 디자인·중복 토큰화 정리 | 완료 · 로컬. 재임베딩은 후속 |
| [CASE-029](cases/사례-029-가벼운-임베딩과-응대-CMD-2026-11-05.md) | 2026-11-05 | CPU용 e5-small 임베딩 기본값과 `bin/ask-assist.cmd` | 완료 · 재임베딩은 후속 |
| [CASE-028](cases/사례-028-README-디자인과-검색조각-최적화-2026-11-05.md) | 2026-11-05 | README 히어로·배너와 검색 조각·HTTP 재사용 | 완료 · 로컬 |
| [CASE-027](cases/사례-027-분리-패치-주석-문서-점검-2026-11-05.md) | 2026-11-05 | 분리 코드 Google 주석·README/docs 경로 정리 | 완료 · 로컬 |
| [CASE-026](cases/사례-026-백엔드-민원웹-RAG-LLM-분리-2026-11-05.md) | 2026-11-05 | `src/`를 민원 웹·RAG·LLM·연결 계층으로 분리 | 완료 · 로컬. CRUD AI는 후속 |
| [CASE-025](cases/사례-025-패치-주석-문서-최적화-2026-11-05.md) | 2026-11-05 | 패치 코드 주석·README 디자인·공급자 설정 조회 정리 | 완료 · 로컬 |
| [CASE-024](cases/사례-024-Windows-서버-시작-스크립트-2026-11-05.md) | 2026-11-05 | Windows `bin/start-web.cmd`로 Flask 시작과 시민 화면 열기 | 완료 · 로컬 개발용 |
| [CASE-023](cases/사례-023-GPT-6-Luna-공급자-선택-2026-11-05.md) | 2026-11-05 | GPT-6 Luna `medium`의 OpenAI API·Codex CLI 선택 | 완료 · 실측 평가는 후속 |
| [CASE-022](cases/사례-022-RAG-LLM-응대검사기-2026-11-01.md) | 2026-11-01 | RAG 검색 위 판정·정책 검사 CLI/API와 `/#/lab` 검사기 | 완료 · 로컬. 최종 모델 미선정 |
| [CASE-021](cases/사례-021-Flask-서버-코드-구조-간소화-2026-10-31.md) | 2026-10-31 | Flask 앱 조립과 HTTP·업무 처리 간소화 | 완료 · 서버 구조 |
| [CASE-020](cases/사례-020-패치-종합점검과-서버-저장소-최신화-2026-10-31.md) | 2026-10-31 | 한국어 주석·회귀·README·DB 보존·서버 최신화·원격 병합 종합 점검 | 완료 · GitHub 반영 |
| [CASE-018](cases/사례-018-시민-담당자-다크라이트-테마-전환-2026-10-31.md) | 2026-10-31 | 시민·담당자 공통 테마 버튼·저장·가독성 | 완료 · 로컬 UI |
| [CASE-017](cases/사례-017-민원과-담당자-화면-디자인-개편-2026-10-31.md) | 2026-10-31 | 담당자 화면을 민원과 참고 남색 레이아웃·Pretendard로 개편 | 완료 · 로컬 UI |
| [CASE-016](cases/사례-016-프로젝트-내부-DB-파일-배치-2026-10-31.md) | 2026-10-31 | 원본 JSON·스키마 SQL·덤프·업무 SQLite를 `db/`로 모으고 코드 경로를 맞춤 | 완료 · 로컬 경로. 벡터 dump는 우분투에서 생성 |
| [CASE-015](cases/사례-015-예시-시민-화면-디자인과-효과-반영-2026-10-31.md) | 2026-10-31 | 시민 화면 파랑 UI, 민원톡톡 헤더, 서비스 아이콘 SVG, 모바일 효과 | 완료 · 로컬 UI |
| [CASE-014](cases/사례-014-Flask-업무서버와-Swagger-구현-2026-10-31.md) | 2026-10-31 | Flask 업무 서버·Swagger·SQLite 저장, UI를 API에 연결 | 완료 · 로컬 서버. 실제 AI·SSE·운영 인증 미구현 |
| [CASE-013](cases/사례-013-시민과-담당자-웹-UI-구현-2026-10-31.md) | 2026-10-31 | 시민·담당자 로컬 UI와 CRUD·초안·게시 흐름 | 완료 · 로컬 UI |
| [CASE-019](cases/사례-019-검색-테스트-스크립트-CRLF-수정-2026-10-30.md) | 2026-10-30 | `rag/test-search.sh` CRLF로 인한 WSL `pipefail` 수정, `*.sh`는 LF | 완료 |
| [CASE-011](cases/사례-011-검색-테스트-터미널-메뉴-추가-2026-10-28.md) | 2026-10-28 | FAQ·사례 검색 Bash TUI와 원문·출처 표시 | 완료 |
| [CASE-010](cases/사례-010-네이티브-검색환경-전환-2026-10-28.md) | 2026-10-28 | Docker 제거, 호스트 PostgreSQL 18 + 사용자 검색 서비스 | 완료 |
| [CASE-009](cases/사례-009-게시판-CRUD와-AI-모니터링-통합설계-2026-10-27.md) | 2026-10-27 | CRUD·AI 모니터 통합 상세설계, 분야별 38개 작업 | 완료 · 설계 문서. 전체 목표 기능은 후속 |
| [CASE-008](cases/사례-008-프로젝트-종합점검과-저장소-반영-2026-10-25.md) | 2026-10-25 | 문서·저장소 종합 점검 | 완료 |
| [CASE-007](cases/사례-007-시연-웹-게시판과-민원-서버-범위-구체화-2026-10-25.md) | 2026-10-25 | 시연 웹·민원 서버 범위 확정 | 완료 · 설계. 로컬 웹은 CASE-013·014에서 일부 구현 |
| [CASE-006](cases/사례-006-한국어-주석과-커밋-규칙-정비와-검색-조회-최적화-2026-10-25.md) | 2026-10-25 | 한국어 주석·커밋 규칙, 검색 조회 범위 정리 | 완료 |
| [CASE-005](cases/사례-005-프로젝트-사례-기록-체계-도입-2026-10-25.md) | 2026-10-25 | 사례 번호·한국어 양식 도입 | 완료 |
| [CASE-004](cases/사례-004-FAQ-정책과-연락처-현행성-미확인-2026-10-25.md) | 2026-10-25 | FAQ 정책·연락처 현행성 미확인 | 확인 필요 |
| [CASE-003](cases/사례-003-부서-업무분장과-관할-미검증-2026-10-25.md) | 2026-10-25 | 부서 업무분장·관할 미검증 | 확인 필요 |
| [CASE-002](cases/사례-002-LLM-RAG-우선-구현과-Jev-후속-확장-2026-10-25.md) | 2026-10-25 | 초기 MVP는 Jev 없는 LLM + RAG, Jev는 후속 | 완료 · 설계. 응대 계층은 CASE-022 |
| [CASE-001](cases/사례-001-관계형-벡터-DB-구축과-검색-검증-2026-10-24.md) | 2026-10-24 | FAQ·사례·부서 적재와 하이브리드 검색 검증 | 완료 |

CASE-001은 2026-10-24 구축을 뒤늦게 정리한 기록입니다. CASE-003·004는 데이터 검증 과제로 남아 있습니다.

## 개발·운영 문서

| 문서 | 역할 | 문서 상태 |
| --- | --- | --- |
| [시스템 구조](harness/architecture.md) | 코드 경로, DB·검색 흐름, API 계약, LLM 응대 계층 | 검색·로컬 응대 계층·Luna 공급자 선택 구현. 실측·SSE는 후속 |
| [데이터 계약](harness/data-contracts.md) | 문서 키, 조건·원문 보존, 부서 검증 의미 | 현재 계약. 스키마 정본은 `rag/origin/schema/complaint_rag.sql` |
| [판정 정책](harness/decision-policy.md) | FAQ 답변·부서 추천·담당자 검토 분기 | 로컬 응대 계층 구현 · 최종 모델 미선정 |
| [AI 정보 전달과 응답 하네스](harness/AI_정보전달과_응답_하네스.md) | 두 기획서·현재 코드 기준 AI 입력 JSON·제외 정보·출력 검증·역할별 공개 범위 | 현재 코드 계약 + 기획서 원칙 통합 |
| [시스템 프롬프트와 프리픽스 캐싱 지침](harness/시스템_프롬프트와_프리픽스_캐싱_지침.md) | 불변 접두·가변 접미 분리, 캐시 유지 8원칙, `PREFIX-00~04` 표준 시스템 프롬프트 블록 | 프리픽스 캐싱 적용 명세 |
| [AI 안전·보안·개인정보 가드레일](harness/AI_안전_보안_가드레일.md) | PII 마스킹·프롬프트 인젝션 격리·긴급/처분성 차단·특이민원 순화·폴백 | 안전·보안 가드레일 기준 |
| [평가 기준](harness/evaluation.md) | 실행 가능한 검증과 추가할 한국어 판정 평가 | 기존 검증과 제안 구분 |
| [코드 작성·주석 규칙](harness/코드_작성과_주석_규칙.md) | 한국어 주석·커밋, 기존 docstring 형식, 최적화 점검 | 현재 개발 지침 |
| [운영 절차](harness/runbook.md) | 상태 확인, 백업, 갱신, 복구 | 현행 명령. dump는 `rag/origin/dumps/` |
| [네이티브 설치·운영](harness/네이티브_운영.md) | PostgreSQL 18·Python 설치, 적재, 서비스, dump 내보내기·복원 | 검색 운영 기준 |
| [프로젝트 사례](cases/README.md) | 번호별 버그·조치·설계·검증 기록과 미해결 데이터 과제 | 사례별 작업·구현·검증 상태 구분 |
| [MVP 실행 계획](plans/harness-roadmap.md) | 우선순위, 완료 조건, 결정 기록 | 다음 작업 계획. 로컬 웹은 일부 구현됨 |
| [LLM + RAG 우선 구현계획](plans/언어모델과_검색증강생성_우선_구현계획.md) | 사용자 변경 요구, 이전 계획과 차이, 초기 흐름, Jev 후속 확장 | 2026-10-25 결정과 구현 제안 구분 |
| [시연 웹·민원 서버 구현계획](plans/시연_웹_게시판과_민원_서버_구현계획.md) | 게시판·작성·상세·민원 교환 서버, 데이터·API 제안·완료 조건 | 범위 문서. 로컬 Flask·UI는 구현, 공식 이관·실제 AI는 미구현 |
| [청주톡톡 민원 업무 API Swagger PDF](api/청주톡톡_민원_업무_API_Swagger.pdf) | Flask `/docs`·`#/staff/api`와 같은 OpenAPI 3.1 경로·모델 인쇄본. 검색 `:8007/docs`는 제외 | 2026-11-17 재생성 (`22` 경로·`28` 오퍼레이션). API 변경 시 스크립트 재실행 |
| [웹 상세설계·분야별 작업계획](plans/민원_웹_MVP_상세설계와_분야별_작업계획.md) · [PDF](plans/민원_웹_MVP_상세설계와_분야별_작업계획.pdf) | UI·백엔드·AI·DB 그림·전체 38개 작업표, 도판 7개·CRUD·SSE·DB/API·인수 시나리오 16개 | 2026-10-27 요구 반영 설계. SSE·실제 AI 등은 미구현 |
| [모델 선정과 미세조정 제안](plans/모델_선정과_미세조정_제안.md) | LLM 후보·실행 조건·평가·LoRA·후속 Jev 후보 | 조사·제안; 모델 미선정·실측 전 |

현재 PostgreSQL `complaints_native`에는 관계형 데이터와 5,109개 임베딩이 함께 적재되어 있습니다. 이 호스트의 벡터는 2026-11-06 `dragonkue/multilingual-e5-small-ko` 384차원 적재입니다. 이전 intfloat 색인은 `RAG_EMBEDDING_PROFILE=e5-small`, BGE-M3 dump는 `bge-m3`입니다. 부서 디렉터리도 존재하지만 공식 업무분장·관할 보완은 남아 있습니다. **초기에는 LLM + RAG를 연결하고 Jev는 추후 추가**합니다. 시연 웹의 청주시 공식 접수·외부 이관 연계는 별도 범위입니다.

## 원래 계획서와 참고 자료

| 자료 | 읽을 때 구분할 점 |
| --- | --- |
| [AI 민원 프로세스 분석](plans/archive/민원AI_계획서_상세분석.md) · [원본 PDF](plans/archive/civil_complaint_plan_enhanced_redacted.pdf) | 전체 사업·시민/담당자 서비스 구상 |
| [VoteLab 상세 기획안 분석](plans/archive/VoteLab_AI민원_상세기획안_상세분석.md) · [원본 PDF](<plans/archive/보트랩 VoteLab _ AI 민원 상세 기획안 - 산학공동.pdf>) | 장기 화면·API·TAXO·인수 조건의 설계 자료 |
| [수집·정규화 코드](../PACKET/) | 현재 원본 수집 방식의 구현 근거 |
| [기존 검증 보고서](../rag/reports/) | 실행 당시의 결과; 새 변경의 통과를 자동 보장하지 않음 |
| [2026-10-30 DB 설계 복사본](plans/archive/db%20%EC%84%A4%EA%B3%84%201%EC%B0%A8/2026-10-30/README.md) | 당시 SQL 설명. 실행용 검색 DDL은 `rag/origin/schema/`, 업무 DDL은 `src/complaints/schema/` |

계획서의 일정·기술 스택·목표 수치·화면과 API 개수는 현재 구현 실적이 아닙니다. 초기 MVP의 최신 방향은 [LLM + RAG 우선 구현계획](plans/언어모델과_검색증강생성_우선_구현계획.md)을 따릅니다. 원래 상세 기획안의 TAXO 자동 배정·전체 행정 연계는 첫 CLI의 필수 범위가 아닙니다. 현재 구현은 루트 README, 코드, 해당 검증 결과를 함께 확인합니다.

## 문서 관리

- 프로젝트 목적·현재 상태는 루트 README, 필드 정의와 파일 배치는 데이터 사전, 검색 실행 명령은 RAG 문서, 시연 웹 실행은 `src/`·`ui/` 문서를 기준으로 유지합니다.
- 설계가 구현되면 상태 표현과 검증 근거를 함께 갱신합니다. 제안을 구현 완료로 표시하지 않습니다.
- 기능·데이터·계약·운영 방식의 의미 있는 변경은 [CHANGELOG](../CHANGELOG.md)에 정리하고, 이 목차의 패치 표와 사례 상태를 맞춥니다. 문서 간 같은 내용을 길게 복제하기보다 상세 문서로 연결합니다.
- 개별 버그·개선·설계·운영 기록은 [사례 관리 규칙](cases/README.md)에 따라 번호와 한국어 파일명으로 작성합니다. 경위·증거는 사례에, 현재 적용할 기준은 하네스·데이터·실행 문서에 기록하고 서로 연결합니다.
- `.env`, PostgreSQL 클러스터, 모델 캐시, `.web-data/`, `rag/origin/dumps/*.dump`, 쿠키가 포함된 SAZ는 Git에 넣지 않습니다. 검색 원본 JSON과 검색 스키마 SQL은 `rag/origin/`에 둡니다. 이전 시연 SQLite 잔여는 [CASE-041](cases/사례-041-잔여-SQLite-삭제-2026-11-05.md)에서 삭제했습니다.

외부 LLM 독립 예제는 [../scripts/run/external_llm_example.py](../scripts/run/external_llm_example.py)를 사용한다. 토큰은 `PUBLIC_LLM_TOKEN` 환경변수로 전달하며, 민원 RAG 통합·최종 모델 선택은 후속 작업이다.
