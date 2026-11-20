<div align="center">

<img src="docs/assets/project-banner.svg" width="100%" alt="AI Complaint Process — 청주 민원 AI 완충지대" />

# AI 민원 처리 시스템

**반복 문의에는 공식 근거를, 현장 조치에는 담당 부서 연결을.**  
청주톡톡의 FAQ(`94건`)와 공개 민원 사례(`5,015건`)를 분리 검색해 시민과 담당자 사이의 **AI 완충지대**를 구성합니다.

<p>
  <a href="#현재-구현-상태"><img src="https://img.shields.io/badge/Stage-Web_%26_Retrieval_MVP-0f766e?style=flat-square" alt="Stage" /></a>
  <a href="src/README.md"><img src="https://img.shields.io/badge/Web-Flask_%3A5000-2f6fed?style=flat-square" alt="Web" /></a>
  <a href="src/README.md"><img src="https://img.shields.io/badge/Swagger-%2Fdocs_%C2%B7_%23%2Fstaff%2Fapi-0d9488?style=flat-square&logo=swagger&logoColor=white" alt="Swagger Portal" /></a>
  <a href="src/lab_web/README.md"><img src="https://img.shields.io/badge/Lab-Checker_%3A5010-b45309?style=flat-square" alt="Lab" /></a>
  <a href="src/README.md"><img src="https://img.shields.io/badge/Stream-SSE_%C2%B7_NDJSON-0f766e?style=flat-square" alt="Stream" /></a>
  <a href="ui/README.md"><img src="https://img.shields.io/badge/Theme-Light_%26_Dark-1e293b?style=flat-square" alt="Theme" /></a>
  <a href="src/README.md"><img src="https://img.shields.io/badge/Staff-127_Depts_%26_Templates-2f6fed?style=flat-square" alt="Staff" /></a>
</p>
<p>
  <a href="#k-exaone-25-api-및-추론-파라미터-설정-env"><img src="https://img.shields.io/badge/LLM-K--EXAONE_2.5_API-e11d48?style=flat-square" alt="K-EXAONE" /></a>
  <a href="src/README.md"><img src="https://img.shields.io/badge/LLM-GPT--6_Luna_%C2%B7_Codex-6d28d9?style=flat-square" alt="Luna" /></a>
  <a href="#응대-검사기"><img src="https://img.shields.io/badge/MCP-Search_%C2%B7_NaverMap-03c75a?style=flat-square" alt="MCP" /></a>
  <a href="#응대-검사기"><img src="https://img.shields.io/badge/Trace-Data_%E2%86%91_%C2%B7_Prompt_%E2%86%93-4f46e5?style=flat-square" alt="Engine Trace" /></a>
  <a href="docs/harness/prompts/README.md"><img src="https://img.shields.io/badge/Prompt-PREFIX--00~04-7c3aed?style=flat-square" alt="Prompt" /></a>
  <a href="docs/cases/사례-100-문맥기반-순화판단과-지명장소추론-결함보완-2026-11-17.md"><img src="https://img.shields.io/badge/Guard-Context_Sanitize_%26_OutOfScope-0284c7?style=flat-square" alt="Context Guard" /></a>
  <a href="#저장과-검색"><img src="https://img.shields.io/badge/Embed-e5--small--ko_384d-0284c7?style=flat-square" alt="Embed" /></a>
  <a href="#exaone-tabular-모델의-후속-추가-위치-구상"><img src="https://img.shields.io/badge/Roadmap-EXAONE_Tabular-475569?style=flat-square" alt="Tabular" /></a>
</p>
<p>
  <img src="https://img.shields.io/badge/Python-3.12-3776ab?style=flat-square&logo=python&logoColor=white" alt="Python" />
  <a href="#저장과-검색"><img src="https://img.shields.io/badge/PostgreSQL-18_%2B_pgvector-4169e1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL" /></a>
  <a href="docs/청주톡톡_민원_업무_API_Swagger.pdf"><img src="https://img.shields.io/badge/Swagger-OpenAPI_31_Paths-85a329?style=flat-square" alt="Swagger PDF" /></a>
  <a href="#검증-근거"><img src="https://img.shields.io/badge/Eval-200_(95%25)_%C2%B7_PostPatch_100_(98%25)-0d9488?style=flat-square" alt="Live Eval" /></a>
  <a href="#검증-근거"><img src="https://img.shields.io/badge/Verified-179_Py_%C2%B7_49_RAG_%C2%B7_29_UI-0f766e?style=flat-square" alt="Verified" /></a>
  <a href="docs/report/README.md"><img src="https://img.shields.io/badge/Report-11%2F19_8Pages-b91c1c?style=flat-square" alt="Report" /></a>
  <a href="docs/test/README.md"><img src="https://img.shields.io/badge/Test-200_SourceTrail_14Pages-0369a1?style=flat-square" alt="Test Report" /></a>
  <a href="#현재-구현-상태"><img src="https://img.shields.io/badge/Branch-llm-334155?style=flat-square&logo=github&logoColor=white" alt="Branch" /></a>
</p>

**[구현 현황](#현재-구현-상태)** • **[Swagger API](src/README.md)** • **[응대 검사기](#응대-검사기)** • **[프롬프트(PREFIX)](#시스템-프롬프트-prefix)** • **[DB와 검색](#저장과-검색)** • **[K-EXAONE 설정](#k-exaone-25-api-및-추론-파라미터-설정-env)** • **[업무 보고서](docs/report/README.md)** • **[테스트 보고서](docs/test/README.md)** • **[빠른 시작](#빠른-시작)** • **[LLM 하네스](docs/harness/LLM_완충지대_하네스.md)** • **[문서 목차](docs/README.md)** • **[변경 이력](CHANGELOG.md)**

</div>

---

> [!IMPORTANT]
> **브랜치 `llm` · GitHub 기본 브랜치 · 민원 웹(`:5000`) + 응대 검사기(`:5010`)**
>
> - 민원 웹(`:5000`, `python -m src`)의 시민·담당자 포털과 `#/lab`에 응대 검사기(`:5010`, `src/lab_web`)의 RAG+LLM 파이프라인을 비동기 워커로 통합했습니다.
> - `K-EXAONE 2.5` · `Codex CLI` · `GPT-6 Luna` 가드를 지원하며, **미게시 초안 시민 비노출**과 **`automaticTransfer=False`**(자동 이관 금지) 원칙을 지킵니다.
> - 상세 경위는 [`src/`](src/README.md) · [`src/lab_web`](src/lab_web/README.md) · [`ui/`](ui/README.md) · [사례 색인(`CASE-093~111`)](docs/cases/README.md)에서 확인할 수 있습니다.

### 한눈에 보는 주요 구현 (`2026-11-20 KST`)

| 영역 | 핵심 구현 내용 | 기준 문서 · 사례 |
| --- | --- | --- |
| **민원 웹 · 인증 · 실시간 SSE · 챗봇 (`:5000`)** | **운영 본인·담당자 인증(`/api/v1/auth/*`: 2단계 OTP·`scrypt`·5회 `429` 잠금·부서 RBAC)**, **PostgreSQL `complaint_app` 7테이블 정규화(`users`~`job_events`·`automatic_transfer=false` CHECK·`complaint_rag` 교차 FK)**, 시민 등록·수정·철회·영구 삭제, **시민 AI 챗봇 실연결(`/api/v1/citizen/chat/stream`)**, **담당자 실시간 SSE 푸시(`/api/v1/staff/events`)**, 127개 부서 배정·커스텀 템플릿 CRUD | [`src/README.md`](src/README.md) · [`업무DB_실행설계`](docs/harness/업무DB_실행설계.md) · [`CASE-110`](docs/cases/사례-110-담당자-실시간-SSE-푸시와-시민-AI-챗봇-실연결-구현-2026-11-20.md) · [`CASE-111`](docs/cases/사례-111-운영-본인담당자-인증과-PostgreSQL-7테이블-정규화-구현-2026-11-20.md) |
| **한국어 Swagger 포털** | 로컬 자산 기반 `/docs`·`/swagger`(원클릭 `staff`/`citizen` 전환·다크 WCAG 4.5+·빈 `Authorize` 제거), 담당자 `#/staff/api` 상태 요약·빠른 색인, [`Swagger PDF`](docs/청주톡톡_민원_업무_API_Swagger.pdf)(31경로) | [`CASE-101`](docs/cases/사례-101-민원웹-5000-백엔드-Swagger-포털과-담당자콘솔-API문서-구현-2026-11-17.md) · [`CASE-110`](docs/cases/사례-110-담당자-실시간-SSE-푸시와-시민-AI-챗봇-실연결-구현-2026-11-20.md) · [`CASE-111`](docs/cases/사례-111-운영-본인담당자-인증과-PostgreSQL-7테이블-정규화-구현-2026-11-20.md) |
| **응대 검사기 (`:5010` · `#/lab`)** | 시민 UI 톤 통일·다크 토글, 4종 엔진 선택/잠금, 4구/98 읍·면·동·장소 추적, 엔진별 데이터 JSON(↑)·프롬프트 전문(↓), 테스트 기록 클릭 시 입력 폼 자동 복원(`fillComplaintForm`) | [`src/lab_web`](src/lab_web/README.md) · [`CASE-098`](docs/cases/사례-098-검사기-기록-폼복원과-업무보고-전용폴더-통합-2026-11-17.md) |
| **지명·타지역·순화 · 성능** | 문맥 `sanitize_needed` + `sarcasm_mockery`, 네이버 `address`/`ac`·HTTP 400 서킷브레이커·사례 235쌍 도로+번지 색인, 일반명사·관공서·생활 기반시설 14종 불용어 필터, 도+시 약칭/거주지 예외 분리, `PREFIX-01` 예외/조건 가드 · 중복 추론 제거 | [`CASE-100`](docs/cases/사례-100-문맥기반-순화판단과-지명장소추론-결함보완-2026-11-17.md) · [`CASE-103`](docs/cases/사례-103-잔여한계-도로번지-광역시약칭-거주지예외-EXAONE추론차등-병렬실행-2026-11-18.md) · [`CASE-106`](docs/cases/사례-106-단독검사기-200건-미통과-10건과-노이즈-개선패치-및-실서버-재검증-2026-11-19.md) · [`CASE-107`](docs/cases/사례-107-패치정비-주석JSDoc-코드최적화-README디자인-최종검증-2026-11-20.md) · [`CASE-109`](docs/cases/사례-109-패치후-100건-실증재검증-98퍼센트와-생활시설-노이즈보강-2026-11-20.md) |
| **LLM · 429 안정화 · 보고** | `K-EXAONE 2.5` 단계별 차등(`high`/`low`)·`02/03/04 4096` 상한·429 백오프, `Codex CLI` 비도구 `_disable_mcp`·MCP 2종, `PREFIX-00~04`, **11/19 보고서 [`업무보고_20261119.pdf`](docs/report/업무보고_20261119.pdf)**([`docs/report/`](docs/report/README.md)) · **200건 실증 [`docs/test/`](docs/test/README.md)** | [`CASE-105`](docs/cases/사례-105-단독검사기-5010-200건-실증평가와-SourceTrail-분석보고서-2026-11-19.md) · [`CASE-108`](docs/cases/사례-108-11월19일-업무보고-코드공통화-전체주석-최종검증-2026-11-20.md) · [프롬프트 구조](#시스템-프롬프트-prefix) |

### 구현 범위 비교

| 지금 됨 (`:5000` 민원 웹) | 응대 검사기 (`:5010` / `#/lab`) | 아직 (후속) |
| --- | --- | --- |
| **운영 본인·담당자 인증**(2단계 OTP·`scrypt`·부서 RBAC) · 시민 CRUD·영구 삭제·**시민 AI 챗봇 실연결** | 문맥 순화(`sanitize_needed`·`sarcasm_mockery`) · 도로+번지/타지역 조기 차단 | 외부 PASS/공동인증서·행정 SSO 연동 · `openai_api` 키 실측 |
| **담당자 실시간 SSE 푸시(`Last-Event-ID`·3초 대체)**, 127부서·템플릿 · Swagger **31경로** | 거주지·운수 예외, `address`/`ac`·HTTP 400 서킷브레이커·사례 색인, FAQ 예외 가드 | 다중 워커 브로커(Redis/PG · 현 단계 제외) · 첨부 업로드 |
| **PostgreSQL `complaint_app` 7테이블 정규화**(`users`~`job_events`·`CHECK`·교차 FK) + 비동기 RAG+LLM 워커 | EXAONE `high/low`(`<=4096`), `PREFIX-03∥04` 병렬, 200건(`95%`) → 패치 후 100건(`98%`, 실응답 `99%`) 재검증 | 청주시 공식 접수·외부 이관 · 200초 단일 지연 |

<img src="docs/assets/lab-overview.svg" width="100%" alt="응대 검사기: 작성, 검색, 판정, 안내 또는 처리 사유" />

### 실행 화면 및 바로 가기

| 화면 | 주소 | 실행 |
| --- | --- | --- |
| 환경 준비 | 가상환경·PostgreSQL·임베딩 모델 | Windows [`setup.cmd`](setup.cmd) · Linux [`setup.sh`](setup.sh). `--check`는 설치 없이 확인 |
| 응대 검사기 웹 | `http://127.0.0.1:5010/` | 검색 후 판정. Windows [`검사기-시작.cmd`](검사기-시작.cmd)(PostgreSQL·검색 API 원클릭 자동 기동) · Linux [`start-lab.sh`](start-lab.sh) |
| 기존 시연 Flask | `http://127.0.0.1:5000/#/citizen` (및 `/#/staff`, `/#/staff/api`, `/#/lab`, `/design/ui04`) | 민원 CRUD·UI04 목업 어댑터·담당자 백엔드 API 콘솔 서버. 이 브랜치 기본 검사기는 `:5010` |
| 민원 응대 | [`민원-응대.cmd`](민원-응대.cmd) · [`ask-assist.sh`](ask-assist.sh) | 꺼진 localhost 검색 API는 자동 시작, 기본 재정렬 끔 |
| 문장 임베딩 | [`문장-임베딩.cmd`](문장-임베딩.cmd) · [`embed-sentence.sh`](embed-sentence.sh) | 벡터 출력 뒤 FAQ·사례 pgvector 이웃. `--raw`는 숫자만 |
| RAG 기동 | [`검색-시작.cmd`](검색-시작.cmd) · [`start-search.sh`](start-search.sh) | Windows는 PostgreSQL·검색 API를 별도 창. Linux는 `:8007` 검색 API |
| API 문서 | `http://127.0.0.1:5000/docs` · `/swagger` · `/#/staff/api` | 자체 호스팅 한국어 Swagger 포털(세션 전환·다크 동기화·색인) · [Flask 설치](src/README.md) · [Swagger PDF](docs/청주톡톡_민원_업무_API_Swagger.pdf) |
| 업무 보고서 | [11/19 종합 보고서 PDF](docs/report/업무보고_20261119.pdf) · [11/18 PDF](docs/report/업무보고_20261118.pdf) · [모음(`docs/report/`)](docs/report/README.md) | `업무보고_20261111` 틀 기반 추상화(쉬운 한국어) 11/19 200건 실증·취약 10건 보완·배너/AI 구조 그림·검증 결과 + `UI 수정 보고서(2026-11-19)` 12장 무수정 8쪽 PDF · [`업무보고_20261119_pdf_생성.py`](scripts/업무보고_20261119_pdf_생성.py) |
| 테스트 보고서 | [200건 분석 (MD](docs/test/청주_민원_200건_상세분석보고서_2026-11-19.md)/[PDF)](docs/test/청주_민원_200건_상세분석보고서_2026-11-19.pdf) · [112건 기준](docs/test/청주_민원_112건_상세분석보고서_2026-11-17.md) · [모음(`docs/test/`)](docs/test/README.md) | 200건 재실측(95.0%) SourceTrail 14쪽 PDF·SVG 4종·전수 표 · [`상세분석보고서_200건_생성.py`](scripts/상세분석보고서_200건_생성.py) |
| 검색 CLI/API | `http://127.0.0.1:8007/docs` | [검색 실행](rag/README.md) · [데이터 사전](rag/origin/README.md) |
| 개발 기록 | [문서 목차](docs/README.md) | [사례 색인](docs/cases/README.md) |

### 패키지 구성 및 데이터 규모

| 패키지 | 역할 | 위치 |
| --- | --- | --- |
| 민원 웹 | CRUD·세션·Swagger·정적 UI | [`src/complaints`](src/README.md) |
| 검색 원본 | FAQ·사례 JSON·검색 DDL | [`rag/origin`](rag/origin/README.md) |
| 검색 클라이언트 | 검색 API 호출, FAQ·사례 근거 | [`src/rag`](src/README.md) · 엔진은 [`rag/`](rag/README.md) |
| LLM | K-EXAONE 2.5·GPT-6 Luna·Codex CLI·MCP 장소추적 | [`src/llm`](src/README.md) |
| 응대 | 검색 다음 판정·정책 검사·조건부 FAQ | [`src/assist`](src/README.md) · [`prompts/`](docs/harness/prompts/README.md) |
| 검사기 웹 | 작성 화면·민원 JSON 수신·검색·판정 | [`src/lab_web`](src/lab_web/README.md) · `:5010` |

설계 문서는 [LLM + RAG 구현계획](plan/언어모델과_검색증강생성_우선_구현계획.md), [웹 상세설계](plan/민원_웹_MVP_상세설계와_분야별_작업계획.md), [모델 제안](plan/모델_선정과_미세조정_제안.md)을 이어서 읽습니다.

| FAQ 안내 근거 | 공개 민원 사례 | 부서 디렉터리 | 임베딩 |
| :---: | :---: | :---: | :---: |
| **94건** | **5,015건** | **127개** | **기본 e5-small-ko 384차원 · 이전 색인은 e5-small · bge-m3** |

## 현재 구현 상태

시연 웹과 업무 서버는 **PostgreSQL `complaint_app`(업무)**과 **`complaint_rag`(검색 지식)**를 스키마 단위로 완전히 분리해 운영합니다.

- **업무 서버 · UI · 운영 인증 (`:5000` · `CASE-111`):** 시민·담당자 UI는 Flask API(`src/complaints/api.py`, **31경로**)를 통해 민원 CRUD, **시민 2단계 본인확인(6자리 OTP) 가입·비밀번호 로그인, 담당자 `scrypt`·5회 `429` 잠금·부서 범위 RBAC(`staff_admin`·`staff_seowon`·`staff_heungdeok`)**, 다크/라이트 테마(투명 청주시 로고), 시민 본인 민원 영구 삭제, 담당자 127개 부서 배정, 커스텀 답변 템플릿을 제공합니다.
- **PostgreSQL 7테이블 정규화 · 비동기 AI 워커 · 실시간 SSE · 시민 챗봇 (`CASE-093` · `CASE-110` · `CASE-111`):** `complaint_app` 스키마에 `users`·`complaints`·`messages`·`message_versions`·`ai_jobs`·`ai_results`(`CHECK (automatic_transfer = false)`·`complaint_rag.department_directory` 교차 FK)·`job_events`(`ON DELETE CASCADE`) 7개 핵심 정규화 테이블(+보조 3테이블)을 구축해 트랜잭션 원자 동기화·기동 자동 백필·`GET /api/v1/staff/db-summary` SQL 집계를 지원합니다. 담당자 모니터는 `GET /api/v1/staff/events` 실시간 SSE 푸시(`Last-Event-ID`·`resync_required`·단절 시 3초 폴링 대체)를, 시민 민원 도우미(`#/citizen/assistant`)는 `POST /api/v1/citizen/chat/stream`(미게시 초안·순화 구조 차단)을 제공합니다.
- **미구현 경계:** 외부 이동통신사 PASS/행정 SSO 연동, 다중 워커 이벤트 브로커(Redis/PG · 현 단계 제외), 청주시 공식 접수·외부 이관, `openai_api` `cached_tokens` 실측은 후속 구현 범위입니다.

<details>
<summary><strong>구현 이력 관련 사례 (CASE-014 ~ CASE-111) 및 Swagger PDF</strong></summary>

[서버 안내](src/README.md) · [CASE-014](docs/cases/사례-014-Flask-업무서버와-Swagger-구현-2026-10-31.md) · [CASE-026](docs/cases/사례-026-백엔드-민원웹-RAG-LLM-분리-2026-11-05.md) · [CASE-031](docs/cases/사례-031-업무저장-PostgreSQL-통일-2026-11-05.md) · [CASE-093](docs/cases/사례-093-민원웹-CRUD-검사기-LLM-RAG-실시간통합-2026-11-15.md) · [CASE-094](docs/cases/사례-094-다크테마-청주시로고-호버-검사기UI-담당자폰트-시민민원삭제-2026-11-16.md) · [CASE-095](docs/cases/사례-095-담당자-부서배정-및-답변템플릿-추가삭제-2026-11-16.md) · [CASE-096](docs/cases/사례-096-패치-주석-최적화-문서디자인-최종점검-2026-11-16.md) · [CASE-097](docs/cases/사례-097-단독검사기-5010-청주한정-112건-실증테스트와-한계식별-2026-11-17.md) · [CASE-098](docs/cases/사례-098-검사기-기록-폼복원과-업무보고-전용폴더-통합-2026-11-17.md) · [CASE-099](docs/cases/사례-099-112건-시각화분석보고서와-테스트폴더-분리-최종점검-2026-11-17.md) · [CASE-100](docs/cases/사례-100-문맥기반-순화판단과-지명장소추론-결함보완-2026-11-17.md) · [CASE-101](docs/cases/사례-101-민원웹-5000-백엔드-Swagger-포털과-담당자콘솔-API문서-구현-2026-11-17.md) · [CASE-102](docs/cases/사례-102-Swagger포털-1117보고서-주석-최적화-README디자인-최종점검-2026-11-18.md) · [CASE-103](docs/cases/사례-103-잔여한계-도로번지-광역시약칭-거주지예외-EXAONE추론차등-병렬실행-2026-11-18.md) · [CASE-104](docs/cases/사례-104-잔여한계패치-주석-하네스동기화-중복최적화-최종검증-2026-11-19.md) · [CASE-105](docs/cases/사례-105-단독검사기-5010-200건-실증평가와-SourceTrail-분석보고서-2026-11-19.md) · [CASE-106](docs/cases/사례-106-단독검사기-200건-미통과-10건과-노이즈-개선패치-및-실서버-재검증-2026-11-19.md) · [CASE-107](docs/cases/사례-107-패치정비-주석JSDoc-코드최적화-README디자인-최종검증-2026-11-20.md) · [CASE-108](docs/cases/사례-108-11월19일-업무보고-코드공통화-전체주석-최종검증-2026-11-20.md) · [CASE-109](docs/cases/사례-109-패치후-100건-실증재검증-98퍼센트와-생활시설-노이즈보강-2026-11-20.md) · [CASE-110](docs/cases/사례-110-담당자-실시간-SSE-푸시와-시민-AI-챗봇-실연결-구현-2026-11-20.md) · [CASE-111](docs/cases/사례-111-운영-본인담당자-인증과-PostgreSQL-7테이블-정규화-구현-2026-11-20.md) · [Swagger PDF](docs/청주톡톡_민원_업무_API_Swagger.pdf)

</details>

| 영역 | 구성·역할 | 상태 |
| --- | --- | --- |
| 데이터 | 두 JSON, 원문 ID·URL·수집 시각, 부서 정규화 | 완료 |
| 관계형 DB | FAQ·사례·부서 사전, 사례와 부서의 외래 키 연결 | 생성·적재 완료 |
| 벡터 DB | FAQ·사례 임베딩, pgvector/HNSW 색인 | 생성·적재 완료 |
| 검색 | 벡터 + 한국어 BM25 + RRF + 재정렬, CLI/API | 구현 완료 |
| 개발 하네스 | 작업 규칙·구조·데이터 계약·평가·운영·실행 계획 | 기본 문서 완료 |
| 부서 검증 | 현행 이름·별칭·내부 ID 정리 | 공식 업무분장·관할 보완 필요 |
| 외부 LLM 예제 | [독립 호출 예제](scripts/외부_LLM_예제.py) · [실행 안내](docs/harness/외부_LLM_API_호출.md) | 구현 · 민원 RAG와 분리된 대화 예제 |
| AI 판정·응답 | 검색 후 판정 JSON·정책 검사·조건부 FAQ 생성 | CLI/`POST /api/v1/assist`·`src/lab_web` `:5010`·민원 CRUD 비동기 워커(`:5000`) · K-EXAONE 2.5·GPT-6 Luna(가드)·Codex CLI 선택 · 초안 평가 개발 26/26 · 보류 3/3 · 400문항 아님 · openai_api 캐시 실측은 키 후속 |
| 시연 웹 | 시민·담당자·`#/lab`, **운영 본인·담당자 인증(2단계 OTP·`scrypt`·부서 RBAC)**, 다크/라이트·투명 로고·시민 영구 삭제·**시민 AI 챗봇 실연결**·**담당자 실시간 SSE 푸시**·127부서 배정·커스텀 템플릿 | Flask·Swagger(**31경로**)·PostgreSQL `complaint_app` (**7테이블 정규화 + 보조 3테이블**) · Windows `웹-시작.cmd` · 외부 PASS/SSO·공식 이관은 후속 |
| 응대 검사기 | `:5010` 작성 → 장소추적·검색 → 엔진선택 판정 → 기록 클릭 시 폼 복원 (시민 UI 톤 통일·다크 토글) | 업무 DB 없음 · `.rag-cache/lab-runs` 파일 기록 · 키 미설정 공급자 비활성화 · MCP NDJSON 핸드셰이크 |
| Jev 확장 | 기본 LLM + RAG의 판정 성능과 비교 후 추가 | 후속 단계 · 초기 필수 아님 |

- **검색·판정 계약:** 검색 CLI/API는 **FAQ 원문·출처와 유사 사례·부서 후보 JSON**을 반환하며 모든 검색 응답은 `retrieval_only=true`, `decision="requires_gate"`입니다(후속 판단 필요 의미이며 Jev 전용 계약 아님). `python3 -m rag assist`와 `src/lab_web` `:5010`은 이 검색 결과 위에서 2중 정책 검사를 수행합니다.
- **시연 웹 · 업무 분리:** 등록·답변 교환은 Flask와 PostgreSQL `complaint_app`으로 구현했으며 검사기와 민원 CRUD를 분리합니다. 청주시 공식 접수·외부 부서 이관 연계는 별도 개발 범위입니다. ([시연 웹·민원 서버 구현계획](plan/시연_웹_게시판과_민원_서버_구현계획.md))

<details>
<summary><strong>통합 설계서의 분야별 작업 범위</strong></summary>

추가 요구에 따라 AI 답변의 작성 기원·담당자 수정 이력을 표시하고, 담당자는 검색·판정·작성·검증의 실제 진행 상태를 확인하도록 설계했습니다. [통합 설계서](plan/민원_웹_MVP_상세설계와_분야별_작업계획.md)는 분야·화면·구성도 7개, CRUD·게시·실시간 이벤트 계약, 분야별 작업 38개와 인수 시나리오 16개를 포함합니다. **UI 10개·백엔드 10개·AI 9개·DB 9개**로 작업을 나누고, 앞부분의 전체 작업표와 14~17절에서 구현 내용·완료 기준을 확인할 수 있습니다. [PDF](plan/민원_웹_MVP_상세설계와_분야별_작업계획.pdf)도 같은 내용입니다. 문서 완성과 웹 기능 구현은 구분합니다.

</details>

## 응대 검사기

`llm` 브랜치의 단독 검사기 기본 화면은 [`http://127.0.0.1:5010/`](http://127.0.0.1:5010/)이며, 민원 웹 내장 검사기(`http://127.0.0.1:5000/#/lab`)와 UI·테마·메타 렌더러를 통일했습니다.

- **엔진 선택 및 잠금:** 상단에서 `.env` 기본(해석된 엔진명 표시) · `K-EXAONE 2.5`(무료 API) · `GPT-6 Luna`(API) · `Codex CLI` 중 선택하며, 키나 실행 파일이 없으면 `키 미설정` 배지와 함께 자동 잠금(`aria-disabled`, 흔들림 피드백)됩니다.
- **지명 추적 · 조기 타지역 차단 (`district.py` · `place_tool.py`):** `resolve_district_and_place()`가 단일 정규식 패스로 도로+번지(`오송생명14로 283`), 닫는 괄호 경계, 랜드마크(`서원대`·`육거리시장`·`수암골`), 100% 단일구 도로명·사례 235쌍 도로+번지 색인, 외부 도+시 약칭/거주지 술어 분리, 청주 운수 예외(`청신운수` 등) 및 네이버 지도 `address`/`ac` 통합 조회(`lookup_navermap_place`, HTTP 400/429 60초 서킷브레이커·단독 노이즈 필터)를 수행합니다. 순수 타 지자체 주소(`서울시`·`충남 천안 두정동`·`경기도 화성시 동탄대로`)는 `early_external_reject`로 `:8007` 검색·`PREFIX-01`·`PREFIX-03`을 생략하고 즉시 담당자 검토(`out_of_scope`)로 넘깁니다.
- **실시간 스트림 · Trace · 폼 복원:** NDJSON 스트림으로 단계 진행을 표시하고, 결과에서는 `📍 발생 지역` · `🗺️ 장소 추적` · `🤖 LLM 엔진` 배지와 **보낸 데이터(JSON ↑)** · **보낸 프롬프트(↓)**를 엔진별로 구분 출력합니다. 오른쪽 `.rag-cache/lab-runs` 기록을 클릭하면 당시 제목·분야·지역·엔진·본문·글자 수가 왼쪽 작성 폼에 자동 복원(`fillComplaintForm`)됩니다.

```mermaid
flowchart LR
    W["lab_web :5010 작성<br/>(지역 · LLM 엔진 선택<br/>키 미설정 자동 잠금)"] --> D["지명·장소·타지역 검증<br/>(도로+번지 · address/ac · 사례 색인<br/>조기 타지역 차단 · 400 쿨다운)"]
    D -->|순수 타지역| E0["early_external_reject<br/>(검색·01·03 생략 / 필요시 04만)"]
    D -->|청주·미정| S["검색 API :8007<br/>(FAQ + 구 필터 사례)"]
    S -->|NDJSON 진행 스트림| P["진행 버퍼링 UI<br/>(read→search→review→draft)"]
    S --> C["판정 엔진 분기<br/>(PREFIX-00+01 · EXAONE high)"]
    C --> E1["K-EXAONE 2.5 무료 API<br/>(high / low<=4096 · 429 백오프)"]
    C --> E2["GPT-6 Luna<br/>(OpenAI Responses API)"]
    C <-->|MCP NDJSON| M["Codex CLI + MCP 도구<br/>• search_complaint_rag<br/>• lookup_navermap_place"]
    E1 --> V["코드 정책 검증<br/>(validate_decision · 예외 보류)"]
    E2 --> V
    M --> V
    V -->|faq_answer| F["안내 문장 (PREFIX-02<br/>_disable_mcp · low<=4096)"]
    V -->|department_suggestion / handoff| B["담당자 초안 (PREFIX-03 · <=4096)<br/>∥ 순화 (PREFIX-04)"]
    V -->|out_of_scope| H["고정 검토 초안<br/>(PREFIX-03 LLM 생략)"]
    V --> O["결과 배지 · 데이터 ↑ · 프롬프트 ↓"]
    classDef ready fill:#ecfdf5,stroke:#0d9488,color:#134e4a
    classDef human fill:#fff7ed,stroke:#fb923c,color:#7c2d12
    classDef tool fill:#f0fdf4,stroke:#16a34a,color:#14532d
    class W,D,S,P,C,E1,E2,V,F,B,O ready
    class E0,H human
    class M tool
```

- **진행 안내 문구:** `민원 내용을 읽고 있어요` → `저장된 안내와 사례를 찾고 있어요` → `찾은 자료를 살펴보고 있어요` → (분기별) `안내문을 준비하고 있어요` / `거친 표현을 정리하고 있어요` / `담당자용 초안을 준비하고 있어요`
- **허용 MCP 도구 2종:** `search_complaint_rag`(검색 API `retrieval_only` 후보 조회)와 `lookup_navermap_place`(비로그인 네이버 지도 장소·`address`/`ac` 구/동 특정). `faq_answer`·`sanitize` 단계는 `_disable_mcp`로 도구를 열지 않으며, `exaone_api`·`openai_api`는 사전 추적 `inferred_place`를 JSON에 함께 실어 보냅니다.

<details>
<summary><strong>응대 검사기 관련 사례 목록 (CASE-022 ~ CASE-109)</strong></summary>

[CASE-022](docs/cases/사례-022-RAG-LLM-응대검사기-2026-11-01.md) · [CASE-057](docs/cases/사례-057-검사기웹-검색판정-연결-2026-11-06.md) · [CASE-072](docs/cases/사례-072-검사기-청주지역선택-지명추출-2026-11-09.md) · [CASE-078](docs/cases/사례-078-네이버지도-비로그인-장소추적-MCP-도구-2026-11-10.md) · [CASE-083](docs/cases/사례-083-서원대후문-장소추적-MCP연동-위치인식-2026-11-13.md) · [CASE-084](docs/cases/사례-084-K-EXAONE-API공급자-추가와-Tabular-구상-2026-11-13.md) · [CASE-085](docs/cases/사례-085-API키-미설정시-LLM선택-비활성화-UI효과-2026-11-13.md) · [CASE-086](docs/cases/사례-086-K-EXAONE-추론강도-최대토큰-파라미터-최적화-2026-11-13.md) · [CASE-087](docs/cases/사례-087-패치-주석-코드최적화-문서디자인-개선-2026-11-13.md) · [CASE-088](docs/cases/사례-088-EXAONE-429-재시도와-스트림-오류-전체점검-2026-11-13.md) · [CASE-089](docs/cases/사례-089-패치-주석-하네스문서-최적화-디자인-개선-2026-11-13.md) · [CASE-090](docs/cases/사례-090-검사기-LLM별-데이터-프롬프트-표시와-배치순서-변경-2026-11-13.md) · [CASE-091](docs/cases/사례-091-패치-주석-코드최적화-문서디자인-최종점검-2026-11-13.md) · [CASE-094](docs/cases/사례-094-다크테마-청주시로고-호버-검사기UI-담당자폰트-시민민원삭제-2026-11-16.md) · [CASE-095](docs/cases/사례-095-담당자-부서배정-및-답변템플릿-추가삭제-2026-11-16.md) · [CASE-096](docs/cases/사례-096-패치-주석-최적화-문서디자인-최종점검-2026-11-16.md) · [CASE-097](docs/cases/사례-097-단독검사기-5010-청주한정-112건-실증테스트와-한계식별-2026-11-17.md) · [CASE-098](docs/cases/사례-098-검사기-기록-폼복원과-업무보고-전용폴더-통합-2026-11-17.md) · [CASE-100](docs/cases/사례-100-문맥기반-순화판단과-지명장소추론-결함보완-2026-11-17.md) · [CASE-103](docs/cases/사례-103-잔여한계-도로번지-광역시약칭-거주지예외-EXAONE추론차등-병렬실행-2026-11-18.md) · [CASE-104](docs/cases/사례-104-잔여한계패치-주석-하네스동기화-중복최적화-최종검증-2026-11-19.md) · [CASE-105](docs/cases/사례-105-단독검사기-5010-200건-실증평가와-SourceTrail-분석보고서-2026-11-19.md) · [CASE-106](docs/cases/사례-106-단독검사기-200건-미통과-10건과-노이즈-개선패치-및-실서버-재검증-2026-11-19.md) · [CASE-107](docs/cases/사례-107-패치정비-주석JSDoc-코드최적화-README디자인-최종검증-2026-11-20.md) · [CASE-108](docs/cases/사례-108-11월19일-업무보고-코드공통화-전체주석-최종검증-2026-11-20.md) · [CASE-109](docs/cases/사례-109-패치후-100건-실증재검증-98퍼센트와-생활시설-노이즈보강-2026-11-20.md)

</details>

## 시스템 프롬프트 (PREFIX)

시스템 프롬프트 원본([`docs/harness/prompts/`](docs/harness/prompts/README.md))은 [`src/assist/prompts.py`](src/assist/prompts.py)가 기동 시 LF 고정 텍스트로 읽어 **`PREFIX-00`(공통 헌법) + 작업 프롬프트(`PREFIX-01`~`04`) 1개**만 결합합니다. 가변 민원 원문과 검색 후보는 `user` JSON에만 분리해 프리픽스 캐시 적격성([`prefix_cache.py`](src/assist/prefix_cache.py))과 행정 안전 경계를 유지합니다.

<img src="docs/assets/prefix-architecture.svg" width="100%" alt="PREFIX-00 ~ 04 계층형 시스템 프롬프트 조립 및 역할 분기 구조" />

### `PREFIX-00` ~ `PREFIX-04` 역할 · 핵심 지침 · 실행 계약

| 파일 · 상수 | 역할 | 포함되는 주요 지침 · 핵심 출력 필드 | 실행 시점 · 최적화 · 공개 경계 |
| --- | --- | --- | --- |
| [`PREFIX-00.txt`](docs/harness/prompts/PREFIX-00.txt)<br>*(모든 호출 공통)* | **시스템 헌법** (공통 지침 v1) | ① **역할·권한**: 최종 결정·배정은 공무원, 인허가·처분·배상·119 긴급은 `human_handoff`, `automatic_transfer=false`<br>② **RAG 원칙**: 점수=확률 오용 금지, FAQ 5대 조건 보존, 사례 과거 답변 정책용 금지, 추측·허위 키 금지<br>③ **부서·관할**: `department_candidates` 내 선택, 4개 구 동명 과 분리, `review_required` 제외<br>④ **보안·도구**: 입력·문서 내 지시문/PII 차단, 허용 MCP 2종(`search_complaint_rag`, `lookup_navermap_place`) | 모든 작업 프롬프트 맨 앞에 정적 결합(`join_prefix`) |
| [`PREFIX-01.txt`](docs/harness/prompts/PREFIX-01.txt)<br>`DECISION_SYSTEM` | **검색 근거 기반 1차 판정기** | `scope` · `intent` · `outcome`(`faq_answer` / `department_suggestion` / `human_handoff`) · `reason_code` · `evidence_refs` · `department_ids` · `sanitize_needed`를 단일 JSON으로 판정 (`담당자 연결` 예외 보류 및 조건부 제도 질의 구분 포함) | 일반 민원 1단계(순수 타지역 `early_external_reject` 시 생략)<br>`exaone_api` 기본 `high` 추론 · MCP 2종 사용 · 시민 자연어 금지 |
| [`PREFIX-02.txt`](docs/harness/prompts/PREFIX-02.txt)<br>`ANSWER_SYSTEM` | **조건 보존 FAQ 시민 안내기** | 선택된 `faq` 배열 원문만으로 정중한 한국어 평문 생성. `target`·`received_by`·`processing_period`·`main_content`·`warnings` 보존, 과거 사례 및 "정식 접수/배정 완료" 오인 표현 금지 | `validate_decision`이 `faq_answer` 허용 시에만 호출<br>`exaone` `low`/`<=4096`, `codex` `_disable_mcp` · 시민 공개 가능 |
| [`PREFIX-03.txt`](docs/harness/prompts/PREFIX-03.txt)<br>`STAFF_DRAFT_SYSTEM` | **담당자 요약 · 답변 초안기** | `summary_card`(요지·요청·위치/대상·누락 항목), `draft_answer`(미확인 일정·계획은 `[담당자 확인 필요]` 빈칸 유지), `citations`, `requires_field_check`를 JSON으로 작성 | FAQ·`out_of_scope` 제외 후속 실행(`out_of_scope`는 고정 템플릿)<br>`exaone` `low`/`<=4096`, `PREFIX-04`와 `ThreadPoolExecutor` 병렬 실행 · 승인 전 시민 비공개 |
| [`PREFIX-04.txt`](docs/harness/prompts/PREFIX-04.txt)<br>`SPECIAL_SANITIZE_SYSTEM` | **직원 보호용 특이민원 순화기** | 공격 표현을 덜어낸 제3자 시점 `sanitized_summary`, 정당한 요구 `legitimate_requests`, 9종 `risk_signals`(`sarcasm_mockery` 포함), `human_protection_review_needed`를 JSON으로 분리 | `PREFIX-01` `sanitize_needed` 또는 안전 휴리스틱(조기 차단 욕설 포함) 시만 실행<br>검색 도구 금지(`_disable_mcp`), `exaone` `low`/`4096` · 참고 배지 전용(자동 차단 금지) |

### 관련 소개 및 설계 자료

- **프롬프트 원문 · 로더 · 캐시 검증:** [`docs/harness/prompts/README.md`](docs/harness/prompts/README.md) · [`src/assist/prompts.py`](src/assist/prompts.py) · [`src/assist/prefix_cache.py`](src/assist/prefix_cache.py)
- **LLM 완충지대 · 입출력 · 가드레일:** [LLM 완충지대 하네스](docs/harness/LLM_완충지대_하네스.md) · [AI 정보 전달과 응답 하네스](docs/harness/AI_정보전달과_응답_하네스.md) · [프리픽스 캐싱 지침](docs/harness/시스템_프롬프트와_프리픽스_캐싱_지침.md) · [AI 안전·보안·개인정보 가드레일](docs/harness/AI_안전_보안_가드레일.md)

<details>
<summary><strong>공급자별 Static/Dynamic 전달 방식 및 프롬프트 JSON 출력 스키마</strong></summary>

| 구분 | 내용 |
| --- | --- |
| **OpenAI Responses API** (`openai_api`) | `instructions`(불변 `PREFIX-00 + 0X`) + `input`(가변 `user` JSON) |
| **K-EXAONE Chat Completions** (`exaone_api`) | `messages[0] role="system"`(불변 `PREFIX`) + `messages[1] role="user"`(가변 JSON) · 역할별 추론 강도(`high`/`low`) |
| **Codex CLI** (`codex_cli`) | `[시스템 지시]` 다음 `[사용자 입력]` 구분 전달 · 비도구 단계(`PREFIX-02`/`04`) `_disable_mcp` 적용 |
| **`PREFIX-01` 출력 키** | `{"scope", "intent", "outcome", "reason_code", "evidence_refs", "department_ids", "sanitize_needed"}` |
| **`PREFIX-03` 출력 키** | `{"summary_card": {"core_summary", "citizen_request", "location_or_target", "missing_info"}, "draft_answer", "citations", "requires_field_check"}` |
| **`PREFIX-04` 9대 `risk_signals`** | `profanity_insult`, `sarcasm_mockery`, `threat_intimidation`, `sexual_harassment`, `repeated_obsession`, `legal_threat`, `excessive_personal_info_demand`, `urgent_safety_hazard`, `discretionary_disposition_pressure` |

</details>

## 저장과 검색

**같은 PostgreSQL에서 스키마만 나눕니다.** 검색 지식은 `complaint_rag`, 시연 웹 민원 CRUD·템플릿은 `complaint_app`입니다. 민원 행을 검색 색인에 넣지 않습니다. 이 컴퓨터의 DB 이름은 `complaints_native`입니다.

| 스키마 · 테이블 | 저장하는 내용 | 검색 방식 · 용도 | 규모 / 비고 |
| --- | --- | --- | ---: |
| `complaint_rag.faq_knowledge` | FAQ 원문·분류·적용 조건·출처 | 업무명 + 분류 + 전체 안내·대상·조건·주의사항 | 94건 |
| `complaint_rag.routing_cases` | 민원 원문·과거 처리 맥락·현재 부서 연결 | 제목 + 민원 요지 | 5,015건 |
| `complaint_rag.department_directory` | 부서 ID·현행 명칭·별칭·관할 및 검증 상태 | 일반 관계형 테이블 · 담당자 127개 부서 배정 연계 | 127개 |
| `complaint_app.complaints` | 민원 원문·시민/공개 상태·부서 배정·AI 참고·초안·작업·이력(`payload`) | 시연 웹 CRUD·낙관적 잠금(`version`)·영구 삭제 지원 | 업무 행 |
| `complaint_app.answer_templates` · `idempotency` · `app_meta` | 담당자 커스텀 답변 템플릿·멱등 키·초기 1회 시드 플래그 | 삭제된 기본 템플릿 부활 방지·중복 요청 차단 | 5종 기본 + 커스텀 |

FAQ·사례 테이블에는 현재 프로필 차원의 `embedding` 벡터가 함께 저장됩니다. 기본은 384차원입니다. `routing_cases.department_id`는 부서 사전을 참조하며, `complaint_rag`는 BM25 토큰·통계와 색인 메타데이터 보조 테이블까지 총 **7개 테이블**입니다. 업무 DB `complaint_app` 4개 테이블 구조와 영구 삭제 정책은 [업무 DB 실행설계](docs/harness/업무DB_실행설계.md), 검색 색인은 [SQL 스키마](rag/origin/schema/complaint_rag.sql) · [데이터 사전](rag/origin/README.md) · [시스템 구조](docs/harness/architecture.md)에서 확인합니다.

| 검색 단계 | 현재 설정 |
| --- | --- |
| 의미 검색 | 기본 `dragonkue/multilingual-e5-small-ko` 384차원, cosine/HNSW 상위 30건. 이전 intfloat 색인은 `RAG_EMBEDDING_PROFILE=e5-small`, BGE-M3는 `bge-m3` |
| 키워드 검색 | Kiwi 형태소 분석 + PostgreSQL BM25 상위 30건 |
| 순위 결합 | RRF `k=60`, FAQ·사례 각각 계산 |
| 재정렬 | `BAAI/bge-reranker-v2-m3`, 상위 20건 평가 후 기본 5건 반환 |

모델 리비전은 [config.py](rag/config.py)에 고정되어 있습니다. FAQ는 한 항목의 안내와 조건을 함께 보존하고, 사례는 제목·요지로 검색합니다. 과거 답변은 현재 정책 안내로 사용하지 않습니다. 검색 점수는 자동 답변·이관 가능 확률이 아닙니다. [상세 검색·검증 문서](rag/README.md)

## 처리 흐름

### 초기 구현: Jev 없는 LLM + RAG

아래는 **Jev 없는 초기 LLM + RAG 흐름**입니다. 검색·판정·정책 검사까지 로컬 구현했으며, FAQ 문장 생성은 LLM이 설정됐을 때만 호출합니다. `K-EXAONE 2.5`(`exaone_api`) 무료 API와 `gpt-6-luna`(`openai_api` · `codex_cli`) 중 선택해 사용할 수 있고, 실측 평가와 운영 모델 확정은 후속입니다.

```mermaid
flowchart TD
    A[한국어 민원 입력] --> R[FAQ·공개 사례 각각 검색]
    R --> G[LLM: 범위·의도·근거 판단]
    G --> P{코드 정책 검사}
    P -->|FAQ로 충분히 안내 가능| F[같은 LLM: FAQ 답변·근거 검사]
    P -->|실제 조치 필요·부서 근거 있음| D[담당 부서 후보 추천]
    P -->|근거 부족·불확실| H[담당자 검토 안내]
    classDef ready fill:#ecfdf5,stroke:#0d9488,color:#134e4a
    classDef planned fill:#eff6ff,stroke:#60a5fa,color:#1e3a8a,stroke-dasharray:5 5
    classDef human fill:#fff7ed,stroke:#fb923c,color:#7c2d12
    class A,R,G,P,F,D ready
    class H human
```

범위 내라는 판단은 후속 검토가 가능하다는 뜻입니다. FAQ에 비슷한 주제가 있어도 실제 단속·보수·처분 요청을 안내만으로 처리 완료로 판단하지 않습니다. 데이터에 근거가 없다는 이유로 청주시 소관이 아니라고 단정하지 않고 담당자 검토로 연결합니다.

범용 LLM에 민원과 검색 원문·출처·부서 검증 상태를 전달합니다. 같은 모델을 판정과 답변에 각각 호출하고 그 사이에 코드 검사를 두는 구성을 제안합니다. 답변 검사 실패도 담당자 검토로 전환합니다. Jev는 기본 성능을 측정한 뒤 판정 대체·보완을 비교하며 초기 CLI·웹 목업의 선행 조건이 아닙니다. [판정 정책](docs/harness/decision-policy.md) · [AI 입출력 하네스](docs/harness/AI_정보전달과_응답_하네스.md)

### Jev를 추가한 후속 목표

아래 흐름은 초기 LLM + RAG의 기준 성능을 확인한 뒤 Jev를 범위·근거 1차 판정에 더하는 구상입니다. Jev에는 민원과 FAQ·공개 사례 검색 후보를 함께 전달합니다. 범위 밖이거나 근거가 부족하고 판정이 불확실하면 담당자 검토로 연결하며, 적합한 요청은 같은 LLM과 코드 정책 검사를 거칩니다. 이 흐름과 판정 기준은 아직 구현·확정되지 않았습니다.

```mermaid
flowchart TD
    A[한국어 민원 입력] --> R[FAQ·공개 사례 각각 검색]
    R -. 검색 후보 전달 .-> J[Jev: 범위·근거 1차 판정]
    J -->|적합·검토 가능| L[LLM: 의도·답변 근거 판단]
    J -->|범위 밖·근거 부족·불확실| H[담당자 검토 안내]
    L --> P{코드 정책 검사}
    P -->|FAQ로 충분히 안내 가능| F[LLM: FAQ 답변·근거 검사]
    P -->|실제 조치 필요·부서 근거 있음| D[담당 부서 후보 추천]
    P -->|근거 부족·불확실| H
    classDef ready fill:#ecfdf5,stroke:#0d9488,color:#134e4a
    classDef planned fill:#eff6ff,stroke:#60a5fa,color:#1e3a8a,stroke-dasharray:5 5
    classDef jev fill:#f5f3ff,stroke:#8b5cf6,color:#4c1d95,stroke-dasharray:5 5
    classDef human fill:#fff7ed,stroke:#fb923c,color:#7c2d12,stroke-dasharray:5 5
    class A,R ready
    class J jev
    class L,P,F,D planned
    class H human
```

Jev는 범위와 검색 근거를 먼저 살피는 보조 판정 단계입니다. 부서 배정이나 민원 접수를 자동 확정하지 않으며, 실제 이관 기능은 별도 개발이 필요합니다.

### K-EXAONE 2.5 API 및 추론 파라미터 설정 (`.env`)

LG AI연구원의 **`K-EXAONE 2.5`**(`k-exaone_v2.5`, 750B)는 공식 개발자 플랫폼([docs.exaone.ai](https://docs.exaone.ai))을 통해 무료로 제공되는 국산 초거대 추론 모델입니다. 512K 컨텍스트를 지원하며 내부 추론(Thinking)이 상시 작동하므로 다음 설정을 `.env`로 제어합니다:

| 환경변수 키 | 기본값 | 설명 및 권장 설정 |
| --- | --- | --- |
| `EXAONE_API_KEY` | *(필수)* | [docs.exaone.ai](https://docs.exaone.ai) 발급 무료 API 키 |
| `EXAONE_URL` · `EXAONE_MODEL` | `https://api.exaone.ai/v1/chat/completions` · `k-exaone_v2.5` | 타 공급자 `COMPLAINT_LLM_URL`과 격리 로딩 |
| `EXAONE_REASONING_EFFORT` | `max` (역할별 차등 `high`/`low`) | 전역 추론 강도. 미지정 시 `EXAONE_DECISION_REASONING_EFFORT`(`high`)·`EXAONE_FAST_REASONING_EFFORT`(`low`) 자동 차등 적용 |
| `EXAONE_MAX_TOKENS` | `16384` | 최대 생성 토큰 (내부 추론 토큰 + 최종 답변 토큰 합산 최대치) |
| `EXAONE_TEMPERATURE` | `0.7` | 생성 다양성 (정형 JSON 안정성과 에이전틱 추론 품질 최적화) |
| `EXAONE_TOP_P` | `0.95` | Nucleus sampling 임계값 (공식 권장값) |

> [!TIP]
> **HTTP 429(동시 접속 600·초당 한도 1) 자동 완화:** `src/rag/http.py`가 `retry-after-ms`/`retry-after`와 지수 백오프(최대 2회)로 자동 재시도(일일 한도 `x-day-rate-limit-remaining: 0` 시 즉시 종료)하고, 판정 API 실패 시 후속 초안·순화 연쇄 호출을 차단합니다. 혼잡 시간대나 빠른 응답이 필요할 때는 `.env`의 `EXAONE_REASONING_EFFORT=low` 설정 또는 검사기 화면에서 `Codex CLI` 전환을 권장합니다.

### EXAONE Tabular 모델의 후속 추가 위치 (구상)

LG AI연구원의 **`EXAONE Tabular`** 모델은 자연어 생성이 아닌 수치·표(Table) 데이터 특화 예측 모델(TabArena 1위)입니다. 본 프로젝트의 PostgreSQL `complaint_app` 및 이관 이력 메타데이터가 축적되면 다음과 같은 위치와 역할로 추가하기에 적합합니다:

- **예정 위치:** `src/complaints/analytics/` 또는 `src/assist/tabular.py`
- **구상 기능:**
  1. **민원 예상 처리 소요 기간 예측 (회귀)**: 민원 접수 요일, 시간대, 소관 부서 코드, 카테고리를 바탕으로 처리 완료 소요일(D+N) 정량 산출
  2. **부서 핑퐁(재이송) 위험도 사전 판별 (분류)**: 과거 5,000건의 부서 이송 이력을 바탕으로 특정 과 배정 시 타 부서로 재이송될 확률 예측
  3. **긴급도 및 현장 출동 우선순위 스코어링 (분류)**: 계절·시간대·지역·반복 접수 지표를 결합하여 담당자 대시보드 처리 우선순위(상/중/하) 수치 부여

## 확정한 방향과 남은 데이터 검증

| 항목 | 결정 |
| --- | --- |
| 데이터 역할 | FAQ는 안내 근거, 공개 사례는 부서 추천 근거 |
| 초기 구성 | **LLM + RAG 우선 구현**, Jev는 추후 확장 |
| 입력 언어 | 한국어 원문으로 먼저 평가, Papago 번역은 추후 비교 |
| 모델 비용 | 무료 모델 우선 검토; 최종 LLM 미선정 |
| 부서 구분 | 확인된 별칭은 통합, 구가 다른 동명 과는 별도 유지 |
| MVP 순서 | 한국어 평가·LLM 연결 → CLI 챗봇 → 게시판·민원 교환 서버를 포함한 웹 MVP; Jev는 기준 성능 확보 후 별도 비교 |

- **모델 검토:** Qwen3.5-4B부터 비교하고 추가 학습 없이 시작하는 안은 [모델 선정·미세조정 제안](plan/모델_선정과_미세조정_제안.md)에 정리했으며, 모델 선정·LoRA 적용은 미확정입니다.
- **부서 사전 경계:** 이름에서 관할 구를 추출한 상태이며 **127개 부서 모두 공식 업무분장이 미검증**입니다. 미래산업과 계열 10건·과거 안전정책과 17건은 검색에는 남기되 부서 후보 확정 근거에서 제외합니다.
- **원본 보존 및 현행성:** 요지가 없는 58건은 제목으로 검색하고 과거 답변이 없는 101건도 보존합니다(두 집합은 겹칠 수 있음). FAQ 조건은 유지했으나 정책·연락처 현행성 검증은 별도 필요합니다(**수집일은 정책 유효성 확인일이 아닙니다**).
- **원본 출처:** [청주톡톡 FAQ](https://toktalk.cheongju.go.kr/home/sub.do?menukey=7403) · [공개 민원 사례](https://toktalk.cheongju.go.kr/home/sub.do?menukey=7401) · [데이터 사전](rag/origin/README.md)

## 빠른 시작

처음 받은 저장소에서는 가상환경·PostgreSQL/pgvector·임베딩 모델을 [`setup.cmd`](setup.cmd)(Windows) 또는 [`setup.sh`](setup.sh)(Linux)로 준비합니다. Docker는 쓰지 않습니다. `--check`는 설치 없이 준비 상태만 확인합니다. 검색 원문 5,109건 적재는 dump 복원 또는 `python -m rag ingest`이며 setup 기본 범위가 아닙니다. [CASE-054](docs/cases/사례-054-환경준비-스크립트와-리눅스-실행기-2026-11-06.md)

```bat
setup.cmd
setup.cmd --check
```

```bash
./setup.sh
./setup.sh --check
```

Windows에서 추출한 응대 검사기를 열려면 [`검사기-시작.cmd`](검사기-시작.cmd) 또는 [`웹-시작.cmd`](웹-시작.cmd)를 실행합니다. `http://127.0.0.1:5010/`이 열리고, 민원 JSON은 검색 후 판정합니다. 백엔드 검색 서비스(PostgreSQL·검색 API)가 꺼져 있으면 자동으로 감지하여 함께 기동합니다. Linux는 [`start-lab.sh`](start-lab.sh)입니다. [CASE-057](docs/cases/사례-057-검사기웹-검색판정-연결-2026-11-06.md) · [CASE-058](docs/cases/사례-058-Codex-MCP-핸드셰이크-줄단위JSON-2026-11-06.md) · [CASE-074](docs/cases/사례-074-검사기-백엔드검색서비스-자동기동-2026-11-10.md)

```mermaid
flowchart TD
    CMD["검사기-시작.cmd (원클릭 실행)"] --> WEB["웹 서버 기동<br/>:5010 (Flask)"]
    WEB --> CHK{"백엔드 검색 서비스 점검<br/>(ensure_backend_services)"}
    CHK -->|postmaster.pid 잔여| CLN["stale 락 파일 안전 삭제"]
    CLN --> DB["PostgreSQL 시작 (:5432)"]
    CHK -->|DB 미실행| DB
    DB --> WAIT1["5432 포트 대기"]
    WAIT1 --> SRCH["검색 API 시작 (:8007)"]
    CHK -->|검색 API 미실행| SRCH
    SRCH --> WAIT2["8007 포트 대기 (모델 로드)"]
    CHK -->|모두 정상 구동 중| BROWSER["브라우저 자동 오픈<br/>http://127.0.0.1:5010/"]
    WAIT2 --> BROWSER
    classDef main fill:#ecfdf5,stroke:#0d9488,color:#134e4a
    classDef check fill:#eff6ff,stroke:#3b82f6,color:#1e3a8a
    classDef auto fill:#fff7ed,stroke:#fb923c,color:#7c2d12
    class CMD,WEB,BROWSER main
    class CHK check
    class CLN,DB,WAIT1,SRCH,WAIT2 auto
```

```bat
웹-시작.cmd
```

Windows에서 검색 DB와 API를 다시 켜려면 [`검색-시작.cmd`](검색-시작.cmd)입니다. Linux 검색 API는 [`start-search.sh`](start-search.sh)입니다. 검색 API가 꺼져 있으면 [`민원-응대.cmd`](민원-응대.cmd) 또는 [`ask-assist.sh`](ask-assist.sh)가 localhost에서 `python -m rag serve`를 시작합니다. PostgreSQL이 꺼져 있으면 Windows는 `검색-시작.cmd`가 먼저 필요합니다. [CASE-035](docs/cases/사례-035-응대-CMD-검색API-자동시작-2026-11-05.md) · [CASE-036](docs/cases/사례-036-Windows-RAG-PostgreSQL-로컬기동-2026-11-05.md)

```bat
민원-응대.cmd 대형폐기물 배출 방법이 궁금합니다
민원-응대.cmd --example faq
민원-응대.cmd --no-start --example faq
문장-임베딩.cmd --raw 나무가 쓰러짐
```

```bash
./ask-assist.sh --example faq
./embed-sentence.sh --raw '나무가 쓰러짐'
```

**메뉴로 직접 검색해 보기:** [검색 테스트 TUI](rag/검색_시험.sh)를 실행하면 상태 확인, FAQ·사례 검색, 예제 질의, 재정렬·관할 설정을 사용할 수 있습니다.

```bash
bash rag/검색_시험.sh
```

기본은 빠른 검색(재정렬 끔)과 컬렉션별 3건 표시입니다. 원본 JSON 보기·선택 저장과 DB 무결성 검사도 지원합니다. 안내 근거를 검색하는 도구이며 LLM 챗봇은 아닙니다. [메뉴·명령 사용법](rag/README.md#검색-테스트-메뉴)

실행 중인 검색 서버가 있으면 저장소 루트에서 사용할 수 있습니다. 검색 CLI는 호스트의 Python 표준 라이브러리로 API에 연결하며, 모델 실행 환경은 호스트의 Python 3.12 가상환경입니다.

```bash
# 적재 상태와 모델 설정
python3 -m rag status

# FAQ 안내 근거 검색
python3 -m rag search '대형폐기물 배출 방법이 궁금합니다' --collection faq

# 유사 사례와 부서 후보 검색
python3 -m rag search '711번 버스가 정류장에 서지 않고 지나갔습니다' --collection routing
```

<details>
<summary><strong>네이티브 실행 환경</strong></summary>

이 컴퓨터에서는 PostgreSQL 18과 pgvector를 호스트에 설치하고 Python 3.12 가상환경에서 실행합니다. Docker 실행 구성은 제거했습니다. 기존 DB는 `complaints_native`로 복원했습니다. 서비스 실행과 새 환경 준비는 [네이티브 운영 안내](docs/harness/네이티브_운영.md)를 따릅니다.

```bash
systemctl --user status cheongju-rag.service
python3 -m rag status
```

</details>

<details>
<summary><strong>API 연결 — 기본 로컬 주소</strong></summary>

| 용도 | 주소 |
| --- | --- |
| 검색 | `POST http://127.0.0.1:8007/search` |
| API 문서 | `http://127.0.0.1:8007/docs` |
| 상태 | `GET http://127.0.0.1:8007/health` |
| 부서 조회 | `GET http://127.0.0.1:8007/departments` |

API와 DB 포트는 localhost에만 바인딩되어 있습니다. 입력·출력·오류 계약은 [시스템 구조](docs/harness/architecture.md), 요청 예시는 [RAG 문서](rag/README.md)를 확인합니다.

</details>

데이터 갱신 시에는 [수집·정규화 방법](rag/origin/README.md)과 [백업·재적재 절차](docs/harness/runbook.md)를 따릅니다. 변경 없는 벡터는 재사용하며 모델·본문 구성 규칙 변경에 따른 재생성은 별도로 구분합니다.

## 검증 근거

`2026-11-19~20 KST` 200건 전수 실증([CASE-105](docs/cases/사례-105-단독검사기-5010-200건-실증평가와-SourceTrail-분석보고서-2026-11-19.md)), 미통과 10건·노이즈 13건 패치([CASE-106](docs/cases/사례-106-단독검사기-200건-미통과-10건과-노이즈-개선패치-및-실서버-재검증-2026-11-19.md)), **패치 후 100건 실서버 재검증(`98/100, 98.0%`) 및 생활 기반시설 불용어 보강([CASE-109](docs/cases/사례-109-패치후-100건-실증재검증-98퍼센트와-생활시설-노이즈보강-2026-11-20.md))** 결과를 함께 관리합니다.

| 검증 영역 | 실행 명령 · 환경 | 관찰된 결과 |
| --- | --- | --- |
| **패치 후 `:5010` 100건 재검증 (`CASE-109`)** | `.venv-web\Scripts\python.exe scripts/실증평가_100건_재검증.py` | **`98 / 100 (98.0%)` 통과**(실응답 `98/99, 99.0%`: 기존 미통과 **10/10**·노이즈 **13/13** 전원 해소, 신규 변형 **39/40**, `0.011s` 조기차단, `automaticTransfer=True` **0건**) |
| **단독 검사기 `:5010` 200건 실증 (`CASE-105`)** | `.venv-web\Scripts\python.exe scripts/실증평가_200건_실행.py` | **`190 / 200 (95.0%)` 의미 통과** (11/17 112건 재측정 **108/112, +14건** · 신규 **82/88**, EXAONE **14/14 완주**, 조기차단 **0.012s**, `automaticTransfer=True` **0건**) |
| **비통과 10건 · 경계 2건 표적 재검증 (`CASE-106`)** | 패치 적용 후 `:5010` 표적 12건 실서버 호출 | **표적 `12 / 12` 기대 동작 달성** (`B12·A35·A31·C09·B22~B24·B35·F05·F09` 전수 해소 + `C32` `0.01s` 조기차단 + `D20` `200.22s`; 노이즈 13건 제거 확인) |
| **백엔드 통합 테스트** | `RUN_PG_TESTS=1 .venv-web\Scripts\python.exe -m pytest src/tests -q -p no:cacheprovider` | **`179 passed`** (`CASE-110` SSE/챗봇 + `CASE-111` 2단계 OTP/부서 RBAC/실 PG 7테이블·`CheckViolation` 회귀 포함 0 실패) |
| **112건 · 5,015건 규칙 회귀** | `.venv-web\Scripts\python.exe scripts/회귀검증_112건_규칙.py` | **112건 규칙 실패 `0`**, 공개 사례 `5,015`건 구 적중 **`762`** (`+11`, 오분류 `17` 유지, 외부 오탐 **`0`**) |
| **포맷 · 정적 타입 · UI · CDP** | `black --check` · `mypy` · `npm --prefix ui run check` · `ui test` · Edge CDP | `black` **통과** · `src/` **44모듈** `mypy` **오류 0건** · UI 문법 **25개** · UI 단위 **29 / 29** · `:5000` 인증/7테이블/SSE Edge E2E **0오류** |
| **RAG 단위 · DB 무결성** | `.venv\Scripts\python.exe -m pytest rag/tests` · `-m rag.verify` | `rag/tests` **49 passed, 3 skipped**(Windows PG 템플릿 미구성) · `rag.verify` **`passed: true`** (`94`·`5,015`·`127`) |

<details open>
<summary><strong>:5010 실증 성적 추이 — 112건(83.9%) → 200건(95.0%) → 패치 후 100건 재검증(98.0% · 실응답 99.0%)</strong></summary>

11/17 기준선 112건(`83.9%`) → 11/19 200건 재실증(`95.0%`, `codex_cli` 186 · `exaone_api` 14) → **11/20 패치 후 100건 재검증(`98.0%`, 기존 문제·노이즈 60건 `59/60` + 신규 변형 40건 `39/40`, `codex_cli` 50 · `exaone_api` 50)**까지의 5대 테스트 축 개선 추이입니다.

| 테스트 축 | 11/17 기준선 (112건) | 11/19 재실증 (200건) | 11/20 패치 후 100건 (`CASE-109`) | 패치 후 핵심 확인 결과 |
| --- | ---: | ---: | ---: | --- |
| **A. FAQ 1차 응대·차단** | `100.0%` | `34 / 36 (94.4%)` | **`16 / 17 (94.1%)`** | `A31` 조건부 FAQ·`A35` 예외 보류 해소 + 신규 `N01~N08` **8/8** 통과 (`A24` EXAONE 보수 보류 1건) |
| **B. 모호 장소·도로·부서** | `78.6%` | `45 / 52 (86.5%)` | **`29 / 30 (96.7%)`** | `B12`·`B22~24`·`B35`·`F05`·`F09` 전수 해소 + 미등장 4구 도로+번지 **4/4** (`N18` EXAONE 180s 타임아웃 1건) |
| **C. 환각·타지역 조기 차단** | `100.0%` | `43 / 44 (97.7%)` | **`17 / 17 (100.0%)`** | `C09` 해소, 도+시 약칭 조기차단 평균 **`0.011s`**, `-로` 조사 오매칭 **0건** |
| **D. 욕설·비꼬기·비오탐** | `42.9%` | `38 / 38 (100.0%)` | **`26 / 26 (100.0%)`** | 은유·초성·조기차단+욕설·정상 시설 비오탐·`D20`(190.1s) 전수 통과 + `N28` 생활 기반시설 14종 불용어 보강 |
| **E. AI 탈옥·인젝션 방어** | `100.0%` | `30 / 30 (100.0%)` | **`10 / 10 (100.0%)`** | 기존 경계 + 신규 탈옥 6종(`N35~N40`) 전수 방어 |
| **종합 (자동이관 0건)** | **`94 / 112 (83.9%)`** | **`190 / 200 (95.0%)`** | **`98 / 100 (98.0%)`** | **기존 미통과 10/10 · 노이즈 13/13 재발 0건 · 실응답 `98 / 99 (99.0%)`** |

<img src="docs/assets/eval-200-axis-breakdown.svg" width="100%" alt="청주 민원 200건 5대 테스트 축 실증 검증 결과" />

> **상세 보고서 및 원자료:** [200건 SourceTrail 14쪽 보고서 (MD](docs/test/청주_민원_200건_상세분석보고서_2026-11-19.md) · [PDF)](docs/test/청주_민원_200건_상세분석보고서_2026-11-19.pdf) · [200건 원자료 JSON](rag/reports/lab-5010-eval-200-20261119.json) · [패치 후 100건 재검증 (`CASE-109`)](docs/cases/사례-109-패치후-100건-실증재검증-98퍼센트와-생활시설-노이즈보강-2026-11-20.md) · [100건 원자료 JSON](rag/reports/lab-5010-eval-100-20261120.json)  
> **200건 보조 차트:** [결과·사유 분포](docs/assets/eval-200-outcome-reason.svg) · [엔진·지연시간 분포](docs/assets/eval-200-latency-engines.svg) · [지명 추론·4대 한계](docs/assets/eval-200-district-and-gaps.svg)

</details>

### 핵심 패치 전·후 개선 요약 (`CASE-100 · 103 · 106 · 107 · 108 · 109`)

| 개선 영역 | 패치 전 한계 (`CASE-097`·`CASE-105` 실측) | 패치 후 동작 및 실증 검증 | 대상 파일 |
| --- | --- | --- | --- |
| 문맥 기반 순화 트리거 | `"꺼져"` 오탐(`B02·B14·E17`) + 초성·은유 비꼬기 미감지 | `PREFIX-01 sanitize_needed` + `sarcasm_mockery` + `_FACILITY_OFF_RE` 확장 + `도장만 찍`/`세금으로 놀` 은유 보강 (**D축 100%**) | `PREFIX-01/04`, `followup.py`, `pipeline.py` |
| 도로+번지 · `address`/`ac` · HTTP 400 방어 | `place=[]` 주소 탈락, 인접 번지 누락, 대량 호출 HTTP 400 지연 | `address`·`all.address`·`ac` 동명 파싱, 도로+번지 직접/±1·±2 탐침, HTTP 400/429 60초 서킷브레이커 (**미등장 4구 도로 4/4**) | `place_tool.py`, `district.py` |
| 일반시설·관공서·기반시설 14종·사례 색인 | `"초등학교"`/`"청주시청"`/`"청주시로"`/`"하수구"` 노이즈 및 상충 구 배지 | `_GENERIC_PLACE_NOUNS`·`_ADMIN_OFFICE_NOUNS`·생활 기반시설 14종(`_STOP_WORDS` `351종` 고유화)·`-로` 조사 차단·사례 235쌍 색인 (**노이즈 13/13 재발 0건**) | `place_tool.py`, `district.py` |
| 타 지자체 차단 · FAQ 예외 · EXAONE · 최적화 | `충남 천안 두정동` 누락, `'담당자 연결'` FAQ 오종결, EXAONE 지연, 중복 로직 | `_EXT_DO_SHORT_CITIES` 조기 차단(`0.011s`) + 거주지/운수 예외 + `PREFIX-01`/`validate_decision` 예외 보류 + `staff_draft <=4096` + `PREFIX-03∥04` 병렬 + 스레드안전 평가 저장 및 전수 주석·JSDoc 정비 | `district.py`, `policy.py`, `pipeline.py`, `settings.py`, `scripts/실증평가_100건_재검증.py`, `scripts/보고서_공통.py` |

<details>
<summary><strong>11/17 112건 기준선 요약 및 패치·검증 사례 인덱스 (`CASE-093 ~ CASE-111`)</strong></summary>

`11/17 기준선`(`codex_cli` 102건 평균 `23.27s` + `exaone_api` 10건) 전체 결과는 **[청주 민원 112건 상세 분석 보고서 (MD](docs/test/청주_민원_112건_상세분석보고서_2026-11-17.md) · [PDF)](docs/test/청주_민원_112건_상세분석보고서_2026-11-17.pdf)** · [원자료 JSON](rag/reports/lab-5010-eval-112-20261117.json)에 보존되어 있으며, `/swagger`+`#/staff/api` Edge CDP `lowContrast: []` 검증(`CASE-102`)부터 패치 후 100건 재검증(`98/100`, `CASE-109`)·실시간 SSE/시민 챗봇(`CASE-110`)·운영 본인/담당자 인증 및 7테이블 정규화(`CASE-111`)까지 이어지는 전체 이력은 아래 사례에서 확인할 수 있습니다.

- **핵심 패치·실증:** [CASE-093](docs/cases/사례-093-민원웹-CRUD-검사기-LLM-RAG-실시간통합-2026-11-15.md) · [CASE-097(112건)](docs/cases/사례-097-단독검사기-5010-청주한정-112건-실증테스트와-한계식별-2026-11-17.md) · [CASE-100](docs/cases/사례-100-문맥기반-순화판단과-지명장소추론-결함보완-2026-11-17.md) · [CASE-101(Swagger)](docs/cases/사례-101-민원웹-5000-백엔드-Swagger-포털과-담당자콘솔-API문서-구현-2026-11-17.md) · [CASE-102](docs/cases/사례-102-Swagger포털-1117보고서-주석-최적화-README디자인-최종점검-2026-11-18.md) · [CASE-103](docs/cases/사례-103-잔여한계-도로번지-광역시약칭-거주지예외-EXAONE추론차등-병렬실행-2026-11-18.md) · [CASE-104](docs/cases/사례-104-잔여한계패치-주석-하네스동기화-중복최적화-최종검증-2026-11-19.md) · [CASE-105(200건)](docs/cases/사례-105-단독검사기-5010-200건-실증평가와-SourceTrail-분석보고서-2026-11-19.md) · [CASE-106](docs/cases/사례-106-단독검사기-200건-미통과-10건과-노이즈-개선패치-및-실서버-재검증-2026-11-19.md) · [CASE-107](docs/cases/사례-107-패치정비-주석JSDoc-코드최적화-README디자인-최종검증-2026-11-20.md) · [CASE-108](docs/cases/사례-108-11월19일-업무보고-코드공통화-전체주석-최종검증-2026-11-20.md) · [CASE-109(100건 재검증)](docs/cases/사례-109-패치후-100건-실증재검증-98퍼센트와-생활시설-노이즈보강-2026-11-20.md) · [CASE-110(실시간 SSE·시민 챗봇)](docs/cases/사례-110-담당자-실시간-SSE-푸시와-시민-AI-챗봇-실연결-구현-2026-11-20.md) · [CASE-111(운영 인증·7테이블 정규화)](docs/cases/사례-111-운영-본인담당자-인증과-PostgreSQL-7테이블-정규화-구현-2026-11-20.md)

</details>

<details>
<summary><strong>이전 검증 이력 (2026-10-24 ~ 2026-11-15)</strong></summary>

2026-11-15 민원 웹 CRUD·`#/staff`·`#/lab` 통합(`CASE-093`) 이후 Windows / Python 3.12 `.venv-web`에서 PostgreSQL 격리 테스트(`RUN_PG_TESTS=1`)를 포함해 `pytest src/tests -q -p no:cacheprovider` **151개가 모두 통과**(`test_complaint_ai.py` 4건 포함 0건너뜀)했고, `src/app.py`·`src/complaints`·`src/assist/pipeline.py`·`src/llm`·`src/lab_web`·`src/rag` **30개 모듈** `mypy` 정적 타입 검사에서 오류가 없었습니다. RAG `.venv`에서는 `pytest rag/tests -q -p no:cacheprovider` **48개 통과**(Windows 환경 `complaint_rag_test_template` 부재로 PG 격리 3개 건너뜀)와 `python -m rag.verify` 무결성 대조(`passed: true`, FAQ 94·사례 5,015·부서 127)가 통과했고, 프론트엔드 `npm --prefix ui run check` **JavaScript 17개 문법 검사**와 `npm --prefix ui test` **16개 단위 테스트**가 모두 통과했습니다. 또한 격리 PostgreSQL 스키마(`complaint_app_e2e`)의 `:5000`+`:8007` 실서버에서 `exaone_api`(`k-exaone_v2.5`), `codex_cli`(`gpt-6-luna`), 미설정 `openai_api` 가드를 모델별로 검증하고 테스트 후 `complaint_app_e2e`를 삭제해 `complaint_app` 원본 2행을 보존했습니다. [CASE-093](docs/cases/사례-093-민원웹-CRUD-검사기-LLM-RAG-실시간통합-2026-11-15.md)

2026-11-13 `origin/main` 비응대 기능 병합(`CASE-092`) 이후 Windows / Python 3.12 `.venv-web`에서 PostgreSQL 격리 테스트(`RUN_PG_TESTS=1`)를 포함해 `pytest src/tests -q -p no:cacheprovider` **147개가 모두 통과**(`test_demo_data.py` 4건·`test_postgres_schema.py` 3건 포함)했고, `src/app.py`·`src/complaints`·`src/assist/pipeline.py`·`src/llm`·`src/lab_web`·`src/rag` **30개 모듈** `mypy` 정적 타입 검사에서 오류가 없었습니다. RAG `.venv`에서는 `pytest rag/tests -q -p no:cacheprovider` **48개 통과**(DB 격리 3개 건너뜀)와 `python -m rag.verify` 무결성 대조(`passed: true`, FAQ 94·사례 5,015·부서 127)가 통과했고, 프론트엔드 `npm --prefix ui run check` **JavaScript 16개 문법 검사**(`ui04-adapter.js` 포함)와 `npm --prefix ui test` **12개 단위 테스트**가 모두 통과했습니다. Flask 인메모리 테스트 클라이언트로 `seed-public-demo`·`/`·`/design/ui04`·`/design/ui04-adapter.js` `200` 응답 및 `:5010` 실서버 `/api/v1/health` `200` 응답도 확인했습니다. [CASE-092](docs/cases/사례-092-main브랜치-UI04-업무DB-비응대기능-병합-2026-11-13.md) · [CASE-091](docs/cases/사례-091-패치-주석-코드최적화-문서디자인-최종점검-2026-11-13.md) · [CASE-090](docs/cases/사례-090-검사기-LLM별-데이터-프롬프트-표시와-배치순서-변경-2026-11-13.md) · [CASE-089](docs/cases/사례-089-패치-주석-하네스문서-최적화-디자인-개선-2026-11-13.md) · [CASE-088](docs/cases/사례-088-EXAONE-429-재시도와-스트림-오류-전체점검-2026-11-13.md) · [CASE-087](docs/cases/사례-087-패치-주석-코드최적화-문서디자인-개선-2026-11-13.md)

2026-11-06 Windows / Python 3.12.10 `.venv-web`에서 `pytest src/tests rag/tests/test_assist.py` **71개가 통과**했고 PostgreSQL 왕복 1개는 `RUN_PG_TESTS`가 없어 건너뛰었습니다. RAG `.venv`에서 경로·검색·임베딩 설정 테스트 **16개가 통과**했습니다. [CASE-045](docs/cases/사례-045-패치-주석-문서-최적화-2026-11-06.md) · [CASE-043](docs/cases/사례-043-문장-임베딩과-한국어-스크립트명-2026-11-05.md) · [CASE-044](docs/cases/사례-044-LLM-완충지대-하네스와-프리픽스-원문-2026-11-06.md)

2026-10-28 네이티브 환경에서 화면 회귀를 포함한 **전체 테스트 27개가 통과**했습니다. Bash 검색 메뉴의 실제 FAQ·사례 검색과 입력·저장·API 실패 처리를 확인했습니다. [CASE-011](docs/cases/사례-011-검색-테스트-터미널-메뉴-추가-2026-10-28.md)

2026-10-25 코드·주석 점검에서 **코드·격리 PostgreSQL 테스트 25개가 통과**했습니다. [CASE-006](docs/cases/사례-006-한국어-주석과-커밋-규칙-정비와-검색-조회-최적화-2026-10-25.md)

아래는 2026-10-24에 수행한 적재·검색 검증 결과입니다. 기존 모델 평가를 새로 실행한 것으로 표시하지 않습니다.

| 점검 | 결과와 범위 |
| --- | --- |
| 코드·격리 PostgreSQL 테스트 | 13개 통과 |
| 원본과 DB 대조 | FAQ 94건·사례 5,015건, 부서 127개, 벡터 형태·검색 통계 확인 |
| 재적재 | 기존 벡터 5,109개 재사용, 신규 생성 0개 |
| 검색 회귀 예제 | 10/10 통과; FAQ 5개·부서 4개의 기대 대상이 1위 |
| 범위 밖 입력 | 검색 결과가 있어도 `requires_gate` 유지 확인 |

</details>

검색 예제의 통과 기준은 기대 대상의 상위 5개 포함과 검색 전용 계약입니다. **10개 예제는 민원 자동 응답 정확도나 범위 밖 탐지 성능의 평가 결과가 아닙니다.** 보고서·성능 측정 조건은 [RAG 문서](rag/README.md), 변경별 검증과 후속 평가셋 설계는 [평가 하네스](docs/harness/evaluation.md)를 확인합니다.

## 문서와 저장소 구조

| 문서 | 확인할 내용 |
| --- | --- |
| [전체 문서 목차](docs/README.md) | 목적별 읽기 순서와 원본 계획서 |
| [업무보고서 모음](docs/report/README.md) | `docs/report/` 일자별 업무보고 PDF(11/04~11/19) 및 생성 스크립트 안내 |
| [테스트 보고서 모음](docs/test/README.md) | `docs/test/` 민원 실증 상세 분석 보고서(200건 SourceTrail 14쪽·112건 MD·PDF·차트 SVG 8종) |
| [프로젝트 사례 색인](docs/cases/README.md) | 버그·개선·결정·검증 이력, 미해결 과제와 작성 양식 |
| [변경 이력](CHANGELOG.md) | 데이터·검색·하네스·문서 패치 내용 |
| [작업 지침](AGENTS.md) · [하네스 안내](docs/harness/README.md) | 개발 규칙, 구조, 계약, 평가, 운영, [LLM 완충지대](docs/harness/LLM_완충지대_하네스.md)·[실제 프리픽스](docs/harness/prompts/README.md)·[AI 입출력](docs/harness/AI_정보전달과_응답_하네스.md)·[프리픽스 캐싱](docs/harness/시스템_프롬프트와_프리픽스_캐싱_지침.md)·[안전 가드레일](docs/harness/AI_안전_보안_가드레일.md) |
| [RAG 실행 문서](rag/README.md) · [데이터 사전](rag/origin/README.md) | 설치·검색·원본 필드·수집·정규화 |
| [MVP 실행 계획](plan/harness-roadmap.md) | 다음 작업·완료 조건·결정 기록 |
| [LLM + RAG 우선 구현계획](plan/언어모델과_검색증강생성_우선_구현계획.md) | 기존 계획의 변경점·처리 흐름·Jev 후속 확장 |
| [시연 웹·민원 서버 구현계획](plan/시연_웹_게시판과_민원_서버_구현계획.md) | 게시판·작성·상세·답변 교환, 저장·API 제안과 완료 조건 |
| [웹 상세설계·분야별 작업계획](plan/민원_웹_MVP_상세설계와_분야별_작업계획.md) · [PDF](plan/민원_웹_MVP_상세설계와_분야별_작업계획.pdf) | 화면 예시, CRUD·AI 답변 수정·실시간 모니터, DB/API·분야별 작업·인수 조건 |
| [모델 선정과 미세조정 제안](plan/모델_선정과_미세조정_제안.md) | 무료 LLM 후보·한국어 평가·LoRA 적용 조건 |

```text
ai-complaint-process/
├── README.md / CHANGELOG.md / AGENTS.md
├── setup.cmd / setup.sh          # 가상환경·PostgreSQL·임베딩 모델 준비. --check 는 확인만
├── 웹-시작.cmd / start-web.sh    # Flask 시작. Linux는 포그라운드 :5000
├── 검색-시작.cmd / start-search.sh
├── 민원-응대.cmd / ask-assist.sh
├── 문장-임베딩.cmd / embed-sentence.sh
├── .env.example                  # 응대 LLM 공급자 예시
├── src/
│   ├── app.py                    # Flask 팩토리
│   ├── complaints/               # 민원 웹 CRUD·운영 인증(OTP/scrypt/RBAC)·7테이블 정규화·SSE·시민 챗봇·127부서·템플릿
│   ├── rag/                      # 검색 API·부서 사전 클라이언트
│   ├── llm/                      # K-EXAONE 2.5(차등 추론)·Luna·Codex CLI·도로+번지 장소추적
│   ├── assist/                   # 조기 타지역 차단·지명/거주지 분리·병렬 PREFIX-03∥04 응대 파이프라인
│   └── lab_web/                  # 추출 응대 검사기 웹 (:5010) · LLM 선택·다크 테마·기록 폼 복원
├── ui/                           # 시민(본인확인·AI 챗봇)·담당자(부서 로그인·실시간 SSE 모니터)·검사기 화면 · 다크 테마
├── scripts/                      # 200건 실증·패치 후 100건 재검증·SourceTrail 보고서·112건/5,015건 회귀·업무 PDF 스크립트
├── docs/                         # 목차·사례(`CASE-111`)·하네스·배너·실증 SVG 차트
│   ├── report/                   # 일자별 업무보고 PDF 전용 폴더
│   ├── test/                     # 민원 실증 테스트 상세 분석 보고서 전용 폴더
│   └── harness/prompts/          # PREFIX-00~04 시스템 접두 원문
├── rag/                          # 검색 엔진·색인·CLI. 원본은 origin/
├── db/                           # 업무 DB 실행 SQL·샘플 적재기·공개 시연 JSON. 정식 검색 색인은 rag/origin/
├── plan/                         # 원본 계획서·MVP 실행 계획
└── PACKET/                       # 수집기·부서 정규화
```

저장소의 공개 범위는 GitHub 설정을 기준으로 확인합니다. `.env`, 실행 DB, 모델 캐시, 쿠키가 포함된 원본 패킷 캡처(`PACKET/*.saz`)는 Git에서 제외합니다. 원래 계획서의 전체 행정 시스템 구상과 현재 검색 MVP의 범위는 [문서 목차](docs/README.md)에서 구분해 안내합니다.
