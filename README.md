<div align="center">

<img src="docs/assets/project-banner.svg" width="100%" alt="AI Complaint Process — 청주 민원 AI 완충지대" />

# AI 민원 처리 시스템

![Flask](https://img.shields.io/badge/Web-Flask-2f6fed?style=flat-square) ![Lab](https://img.shields.io/badge/Lab-5010-b45309?style=flat-square) ![Runs](https://img.shields.io/badge/Lab_runs-JSON_file-b45309?style=flat-square) ![Eval](https://img.shields.io/badge/Eval-초안_29-0f766e?style=flat-square) ![Holdout](https://img.shields.io/badge/Holdout-3%2F3-0f766e?style=flat-square) ![MCP](https://img.shields.io/badge/MCP-NDJSON-0d9488?style=flat-square) ![OpenAPI](https://img.shields.io/badge/API-Swagger-85a329?style=flat-square) ![PDF](https://img.shields.io/badge/Swagger-PDF-b91c1c?style=flat-square) ![PostgreSQL](https://img.shields.io/badge/Demo_PostgreSQL-complaint__app-4169e1?style=flat-square) ![Origin](https://img.shields.io/badge/Origin-rag/origin-0f766e?style=flat-square) ![Luna](https://img.shields.io/badge/LLM-GPT--6_Luna-6d28d9?style=flat-square) ![Assist](https://img.shields.io/badge/Assist-RAG_+_LLM-0f766e?style=flat-square) ![Prefix](https://img.shields.io/badge/Prompt-PREFIX--00~04-7c3aed?style=flat-square) ![RagTool](https://img.shields.io/badge/Codex-search__complaint__rag-0d9488?style=flat-square) ![Embed](https://img.shields.io/badge/Embed-e5--small--ko_384-0284c7?style=flat-square) ![CMD](https://img.shields.io/badge/CMD-민원응대-334155?style=flat-square) ![RAG](https://img.shields.io/badge/CMD-검색시작-1e3a5f?style=flat-square) ![EmbedCMD](https://img.shields.io/badge/CMD-문장임베딩-0f766e?style=flat-square)

**반복 문의에는 공식 근거를, 현장 조치에는 담당 부서 연결을.**

청주톡톡의 FAQ와 공개 민원 사례를 활용해 시민과 담당자 사이에 AI 완충지대를 만듭니다.

![Stage](https://img.shields.io/badge/Stage-Web_&_Retrieval_MVP-0f766e?style=flat-square) ![Python](https://img.shields.io/badge/Python-3.12-3776ab?style=flat-square&logo=python&logoColor=white) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-4169e1?style=flat-square&logo=postgresql&logoColor=white) ![pgvector](https://img.shields.io/badge/pgvector-0.8.1-475569?style=flat-square) ![GitHub](https://img.shields.io/badge/Repository-GitHub-334155?style=flat-square&logo=github&logoColor=white)

[구현 현황](#현재-구현-상태) · [응대 검사기](#응대-검사기) · [DB와 검색](#저장과-검색) · [처리 흐름](#처리-흐름) · [빠른 시작](#빠른-시작) · [LLM 하네스](docs/harness/LLM_완충지대_하네스.md) · [문서 목차](docs/README.md) · [변경 이력](CHANGELOG.md)

</div>

---

> [!IMPORTANT]
> **브랜치 `llm` · GitHub 기본 브랜치 · 응대 검사기 웹**<br>
> 추출한 작성 화면은 [`http://127.0.0.1:5010/`](http://127.0.0.1:5010/)다. `POST /api/v1/lab/complaints`는 제목·상세로 검색 API를 먼저 호출하고 판정한다. [CASE-057](docs/cases/사례-057-검사기웹-검색판정-연결-2026-11-06.md) · [`src/lab_web`](src/lab_web/README.md)

> [!NOTE]
> **현재 단계 · 2026-11-07 · 검색 + 웹 업무 시연 + 응대 검사기**<br>
> **구현:** 시민·담당자 화면, Flask API·Swagger, PostgreSQL `complaint_app` 업무 저장, 검색 원본 `rag/origin`, 검사기 웹 [`src/lab_web`](src/lab_web/README.md) `:5010` 검색·판정·오른쪽 테스트 기록(파일), PREFIX-00~04 호출(03은 FAQ가 아닐 때, 04는 원문 힌트), FAQ 본문에 없는 항목은 안내하지 않음, PREFIX 조립 적격 검사, 초안 응대 평가셋 29건(개발 26/26, 보류 3/3, 400문항 아님), Codex MCP 줄 단위 JSON-RPC, `assist.codex` 사용자 JSON 표시, `gpt-6-luna` API·Codex CLI 선택, Windows `setup.cmd`·`검사기-시작.cmd`·`웹-시작.cmd`·`검색-시작.cmd`·`민원-응대.cmd`·`문장-임베딩.cmd`, Linux `setup.sh`·`start-lab.sh`·`start-web.sh`·`start-search.sh`·`embed-sentence.sh`·`ask-assist.sh`. 기본 임베딩은 CPU용 `dragonkue/multilingual-e5-small-ko`(384차원). e5-small-ko 검색 예제 10건은 상위 5개 포함·`requires_gate`를 통과했습니다.<br>
> **다음:** openai_api `cached_tokens` 실측(키 필요), 민원 CRUD LLM. 시민 챗봇·담당자 SSE·공식 이관은 `main` 후속.

| 지금 됨 | 응대 검사기 | 아직 |
| --- | --- | --- |
| 시민·담당자 CRUD, Flask·Swagger, PostgreSQL `complaint_app` | `:5010` `src/lab_web` · 오른쪽 테스트 기록(파일) · `python -m rag assist` · `민원-응대.cmd` | 민원 CRUD의 LLM 연결 |
| FAQ 94 · 사례 5,015 · 부서 127, 원본 `rag/origin` | 제목·상세로 검색 후 PREFIX-00+01 판정. `assist.codex` | 시민 챗봇 실연결 · 담당자 SSE |
| Windows `setup.cmd` · `검사기-시작.cmd` · `검색-시작.cmd` · Linux `setup.sh` · CPU용 e5-small-ko · [Swagger PDF](docs/청주톡톡_민원_업무_API_Swagger.pdf) | `gpt-6-luna` API 또는 Codex CLI. MCP는 NDJSON. PREFIX-03/04 · 조립 적격 | openai_api `cached_tokens`(키 필요) · 공식 이관 |

<img src="docs/assets/lab-overview.svg" width="100%" alt="응대 검사기: 작성, 검색, 판정, 안내 또는 처리 사유" />

| 화면 | 주소 | 실행 |
| --- | --- | --- |
| 환경 준비 | 가상환경·PostgreSQL·임베딩 모델 | Windows [`setup.cmd`](setup.cmd) · Linux [`setup.sh`](setup.sh). `--check`는 설치 없이 확인 |
| 응대 검사기 웹 | `http://127.0.0.1:5010/` | 검색 후 판정. Windows [`검사기-시작.cmd`](검사기-시작.cmd) · Linux [`start-lab.sh`](start-lab.sh) |
| 기존 시연 Flask | `http://127.0.0.1:5000/#/lab` | 민원 CRUD 서버의 검사기 해시. 이 브랜치 기본은 `:5010` |
| 민원 응대 | [`민원-응대.cmd`](민원-응대.cmd) · [`ask-assist.sh`](ask-assist.sh) | 꺼진 localhost 검색 API는 자동 시작, 기본 재정렬 끔 |
| 문장 임베딩 | [`문장-임베딩.cmd`](문장-임베딩.cmd) · [`embed-sentence.sh`](embed-sentence.sh) | 벡터 출력 뒤 FAQ·사례 pgvector 이웃. `--raw`는 숫자만 |
| RAG 기동 | [`검색-시작.cmd`](검색-시작.cmd) · [`start-search.sh`](start-search.sh) | Windows는 PostgreSQL·검색 API를 별도 창. Linux는 `:8007` 검색 API |
| API 문서 | `http://127.0.0.1:5000/docs` | [Flask 설치](src/README.md) · [Swagger PDF](docs/청주톡톡_민원_업무_API_Swagger.pdf) |
| 검색 CLI/API | `http://127.0.0.1:8007/docs` | [검색 실행](rag/README.md) · [데이터 사전](rag/origin/README.md) |
| 개발 기록 | [문서 목차](docs/README.md) | [사례 색인](docs/cases/README.md) |

| 패키지 | 역할 | 위치 |
| --- | --- | --- |
| 민원 웹 | CRUD·세션·Swagger·정적 UI | [`src/complaints`](src/README.md) |
| 검색 원본 | FAQ·사례 JSON·검색 DDL | [`rag/origin`](rag/origin/README.md) |
| 검색 클라이언트 | 검색 API 호출, FAQ·사례 근거 | [`src/rag`](src/README.md) · 엔진은 [`rag/`](rag/README.md) |
| LLM | Luna·Codex·legacy 공급자 | [`src/llm`](src/README.md) |
| 응대 | 검색 다음 판정·정책 검사·조건부 FAQ | [`src/assist`](src/README.md) · [`prompts/`](docs/harness/prompts/README.md) |
| 검사기 웹 | 작성 화면·민원 JSON 수신·검색·판정 | [`src/lab_web`](src/lab_web/README.md) · `:5010` |

설계 문서는 [LLM + RAG 구현계획](plan/언어모델과_검색증강생성_우선_구현계획.md), [웹 상세설계](plan/민원_웹_MVP_상세설계와_분야별_작업계획.md), [모델 제안](plan/모델_선정과_미세조정_제안.md)을 이어서 읽습니다.

| FAQ 안내 근거 | 공개 민원 사례 | 부서 디렉터리 | 임베딩 |
| :---: | :---: | :---: | :---: |
| **94건** | **5,015건** | **127개** | **기본 e5-small-ko 384차원 · 이전 색인은 e5-small · bge-m3** |

## 현재 구현 상태

시민·담당자 웹과 Flask 업무 서버는 Python 3.12 `.venv-web`에서 실행하고, 민원·답변·이력은 같은 PostgreSQL의 `complaint_app` 스키마에 저장합니다. `version` 칸이 없는 예전 `complaints` 테이블은 저장소 준비 때 채웁니다. 검색 색인은 `complaint_rag`이며 행을 섞지 않습니다. 응대 검사기는 `src/lab_web` `:5010`과 `src/assist`가 `src/rag`와 `src/llm`을 이어 그 검색 위에 판정만 올립니다. 실제 민원 CRUD의 LLM 연결·SSE·운영 인증·공식 이관은 미구현입니다. [서버 안내](src/README.md) · [CASE-014](docs/cases/사례-014-Flask-업무서버와-Swagger-구현-2026-10-31.md) · [CASE-026](docs/cases/사례-026-백엔드-민원웹-RAG-LLM-분리-2026-11-05.md) · [CASE-031](docs/cases/사례-031-업무저장-PostgreSQL-통일-2026-11-05.md) · [Swagger PDF](docs/청주톡톡_민원_업무_API_Swagger.pdf)

| 영역 | 구성·역할 | 상태 |
| --- | --- | --- |
| 데이터 | 두 JSON, 원문 ID·URL·수집 시각, 부서 정규화 | 완료 |
| 관계형 DB | FAQ·사례·부서 사전, 사례와 부서의 외래 키 연결 | 생성·적재 완료 |
| 벡터 DB | FAQ·사례 임베딩, pgvector/HNSW 색인 | 생성·적재 완료 |
| 검색 | 벡터 + 한국어 BM25 + RRF + 재정렬, CLI/API | 구현 완료 |
| 개발 하네스 | 작업 규칙·구조·데이터 계약·평가·운영·실행 계획 | 기본 문서 완료 |
| 부서 검증 | 현행 이름·별칭·내부 ID 정리 | 공식 업무분장·관할 보완 필요 |
| 외부 LLM 예제 | [독립 호출 예제](scripts/외부_LLM_예제.py) · [실행 안내](docs/harness/외부_LLM_API_호출.md) | 구현 · 민원 RAG와 분리된 대화 예제 |
| AI 판정·응답 | 검색 후 판정 JSON·정책 검사·조건부 FAQ 생성 | CLI/`POST /api/v1/assist`·`src/lab_web` `:5010` · `gpt-6-luna` API 또는 Codex CLI 선택 · 초안 평가 개발 26/26 · 보류 3/3 · 400문항 아님 · openai_api 캐시 실측은 키 후속 |
| 시연 웹 | 시민·담당자 화면, 목록·CRUD·초안·게시·단계 시연 | Flask·Swagger·PostgreSQL `complaint_app` · Windows `웹-시작.cmd` |
| 응대 검사기 | `:5010` 작성 → 검색 → 판정. `assist.codex` 표시 | 업무 DB 없음 · `.rag-cache/lab-runs` 파일 기록 · MCP NDJSON 핸드셰이크 · 시민 챗봇은 고정 응답 |
| Jev 확장 | 기본 LLM + RAG의 판정 성능과 비교 후 추가 | 후속 단계 · 초기 필수 아님 |

현재 검색 CLI는 **FAQ 원문과 출처, 유사 사례와 부서 후보를 JSON으로 반환**합니다. 모든 검색 응답은 `retrieval_only=true`, `decision="requires_gate"`입니다. 이는 검색 후 별도 판단이 필요하다는 의미이며 Jev 전용 계약이 아닙니다. `python3 -m rag assist`와 `src/lab_web` `:5010`은 그 검색 결과 위에 판정·정책 검사를 올립니다. 시연 웹의 등록·답변 교환은 Flask와 PostgreSQL `complaint_app`으로 구현했으며 검사기와 민원 CRUD는 분리합니다. 청주시 공식 접수·외부 부서 이관 연계는 별도 개발 범위입니다.

웹 단계는 민원 목록·작성·상세에서 서버에 저장된 글과 답변·처리 상태를 확인하도록 구성합니다. 같은 AI 응대 계층을 CLI와 공유하고, 등록한 민원은 기존 RAG 지식과 구분해 저장하는 안을 제안합니다. [시연 웹·민원 서버 구현계획](plan/시연_웹_게시판과_민원_서버_구현계획.md)

<details>
<summary><strong>통합 설계서의 분야별 작업 범위</strong></summary>

추가 요구에 따라 AI 답변의 작성 기원·담당자 수정 이력을 표시하고, 담당자는 검색·판정·작성·검증의 실제 진행 상태를 확인하도록 설계했습니다. [통합 설계서](plan/민원_웹_MVP_상세설계와_분야별_작업계획.md)는 분야·화면·구성도 7개, CRUD·게시·실시간 이벤트 계약, 분야별 작업 38개와 인수 시나리오 16개를 포함합니다. **UI 10개·백엔드 10개·AI 9개·DB 9개**로 작업을 나누고, 앞부분의 전체 작업표와 14~17절에서 구현 내용·완료 기준을 확인할 수 있습니다. [PDF](plan/민원_웹_MVP_상세설계와_분야별_작업계획.pdf)도 같은 내용입니다. 문서 완성과 웹 기능 구현은 구분합니다.

</details>

## 응대 검사기

`llm` 브랜치의 기본 화면은 [`http://127.0.0.1:5010/`](http://127.0.0.1:5010/)입니다. 제목과 상세로 검색 API를 먼저 호출하고 PREFIX-00+01 판정을 붙입니다. 결과에는 시민 안내와 함께 `assist.codex` 사용자 JSON을 보여 줍니다. 민원 CRUD 테이블에는 쓰지 않으며, 화면 오른쪽 테스트 기록은 `.rag-cache/lab-runs` JSON으로 남깁니다. 공식 접수·자동 이관이 아닙니다. 기존 Flask 해시 `/#/lab`는 `:5000` CRUD 서버에 남아 있습니다.

```mermaid
flowchart LR
    W[lab_web :5010 작성] --> S[검색 API :8007]
    S --> C[PREFIX-00+01]
    C --> V[코드 검증]
    V -->|faq_answer| F[안내 문장]
    V -->|department_suggestion| D[부서 후보 · 이관 아님]
    V -->|human_handoff| H[담당자 검토 사유]
    classDef ready fill:#ecfdf5,stroke:#0d9488,color:#134e4a
    classDef human fill:#fff7ed,stroke:#fb923c,color:#7c2d12
    class W,S,C,V,F,D ready
    class H human
```

진행 문구는 `민원 내용을 읽고 있어요` → `저장된 안내와 사례를 찾고 있어요` → `찾은 자료를 살펴보고 있어요` → (FAQ 안내일 때만) `안내문을 준비하고 있어요` → (원문 힌트) `거친 표현을 정리하고 있어요` → (FAQ가 아니면) `담당자용 초안을 준비하고 있어요`입니다. 검색 파이프라인·판정 JSON·정책 검사 이름은 화면에 올리지 않습니다. LLM은 `.env`의 `COMPLAINT_LLM_PROVIDER`로 고릅니다.

시스템 접두는 [`docs/harness/prompts/`](docs/harness/prompts/README.md)의 PREFIX `.txt`입니다. `src/assist/prompts.py`가 읽어 조립하며, 민원·검색 후보는 `user` JSON에만 둡니다. 호출마다 **공통 헌법 `PREFIX-00`과 그 작업 블록 하나**를 붙입니다. Codex가 쓸 수 있는 도구는 `search_complaint_rag` 하나이며, 민원 문장을 검색 API로 넘겨 `retrieval_only` 후보를 받습니다. 후보가 이미 있으면 다시 호출하지 않고, 순화 작업은 이 도구를 쓰지 않습니다. MCP stdio는 줄 단위 JSON-RPC입니다.

| 호출 | 시스템 프롬프트 | 하는 일 | 지금 |
| --- | --- | --- | --- |
| 1차 판정 | `PREFIX-00` + `PREFIX-01` | 판정 JSON | 검사기가 사용 |
| FAQ 안내 | `PREFIX-00` + `PREFIX-02` | 조건이 남은 한국어 평문 | `faq_answer`일 때만 두 번째 호출 |
| 담당자 초안 | `PREFIX-00` + `PREFIX-03` | 요약·초안 JSON | FAQ가 아니면 호출. 시민 안내를 덮지 않음 |
| 특이민원 순화 | `PREFIX-00` + `PREFIX-04` | 순화 요약 JSON | 원문 힌트가 있을 때만. 자동 차단 아님 |

[CASE-022](docs/cases/사례-022-RAG-LLM-응대검사기-2026-11-01.md) · [CASE-057](docs/cases/사례-057-검사기웹-검색판정-연결-2026-11-06.md) · [CASE-064](docs/cases/사례-064-초안응대평가셋확대-2026-11-06.md) · [CASE-066](docs/cases/사례-066-검사기-테스트기록-파일저장-2026-11-06.md) · [CASE-067](docs/cases/사례-067-패치-주석-문서-최적화-2026-11-07.md)

## 저장과 검색

**같은 PostgreSQL에서 스키마만 나눕니다.** 검색 지식은 `complaint_rag`, 시연 웹 민원 CRUD는 `complaint_app`입니다. 민원 행을 검색 색인에 넣지 않습니다. 이 컴퓨터의 DB 이름은 `complaints_native`입니다.

| 테이블 | 관계형으로 저장하는 내용 | 벡터 검색 본문 | 규모 |
| --- | --- | --- | ---: |
| `faq_knowledge` | FAQ 원문·분류·적용 조건·출처 | 업무명 + 분류 + 전체 안내·대상·접수 조건·기간·주의사항 | 94건 |
| `routing_cases` | 민원 원문·과거 처리 맥락·현재 부서 연결 | 제목 + 민원 요지 | 5,015건 |
| `department_directory` | 부서 ID·현행 명칭·별칭·관할 및 검증 상태 | 일반 관계형 테이블로 관리 | 127개 |

FAQ·사례 테이블에는 현재 프로필 차원의 `embedding` 벡터가 함께 저장됩니다. 기본은 384차원입니다. `routing_cases.department_id`는 부서 사전을 참조합니다. BM25 토큰·통계와 색인 메타데이터를 관리하는 보조 테이블까지 총 **7개 테이블**입니다. [SQL 스키마](rag/origin/schema/complaint_rag.sql) · [데이터 사전](rag/origin/README.md) · [시스템 구조](docs/harness/architecture.md)

| 검색 단계 | 현재 설정 |
| --- | --- |
| 의미 검색 | 기본 `dragonkue/multilingual-e5-small-ko` 384차원, cosine/HNSW 상위 30건. 이전 intfloat 색인은 `RAG_EMBEDDING_PROFILE=e5-small`, BGE-M3는 `bge-m3` |
| 키워드 검색 | Kiwi 형태소 분석 + PostgreSQL BM25 상위 30건 |
| 순위 결합 | RRF `k=60`, FAQ·사례 각각 계산 |
| 재정렬 | `BAAI/bge-reranker-v2-m3`, 상위 20건 평가 후 기본 5건 반환 |

모델 리비전은 [config.py](rag/config.py)에 고정되어 있습니다. FAQ는 한 항목의 안내와 조건을 함께 보존하고, 사례는 제목·요지로 검색합니다. 과거 답변은 현재 정책 안내로 사용하지 않습니다. 검색 점수는 자동 답변·이관 가능 확률이 아닙니다. [상세 검색·검증 문서](rag/README.md)

## 처리 흐름

### 초기 구현: Jev 없는 LLM + RAG

아래는 **Jev 없는 초기 LLM + RAG 흐름**입니다. 검색·판정·정책 검사까지 로컬 구현했으며, FAQ 문장 생성은 LLM이 설정됐을 때만 호출합니다. `gpt-6-luna`·`medium`은 OpenAI API 또는 Codex CLI 공급자로 선택할 수 있고, 실측 평가와 운영 모델 확정은 후속입니다.

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

## 확정한 방향과 남은 데이터 검증

| 항목 | 결정 |
| --- | --- |
| 데이터 역할 | FAQ는 안내 근거, 공개 사례는 부서 추천 근거 |
| 초기 구성 | **LLM + RAG 우선 구현**, Jev는 추후 확장 |
| 입력 언어 | 한국어 원문으로 먼저 평가, Papago 번역은 추후 비교 |
| 모델 비용 | 무료 모델 우선 검토; 최종 LLM 미선정 |
| 부서 구분 | 확인된 별칭은 통합, 구가 다른 동명 과는 별도 유지 |
| MVP 순서 | 한국어 평가·LLM 연결 → CLI 챗봇 → 게시판·민원 교환 서버를 포함한 웹 MVP; Jev는 기준 성능 확보 후 별도 비교 |

Qwen3.5-4B부터 비교하고 추가 학습 없이 시작하는 안은 [모델 선정·미세조정 제안](plan/모델_선정과_미세조정_제안.md)에 정리했습니다. 모델 선정·LoRA 적용이 확정된 상태는 아닙니다.

**현재 부서 사전의 존재와 업무 검증 완료는 구분해야 합니다.** 이름에서 관할 구를 추출한 상태이며 127개 부서 모두 공식 업무분장이 미검증입니다. 미래산업과 계열 10건·과거 안전정책과 17건은 현행 담당 부서 검토 대상으로, 검색에는 남기되 부서 후보 확정 근거에서 제외합니다.

요지가 없는 58건은 제목으로 검색하고 과거 답변이 없는 101건도 보존합니다. 두 집합은 겹칠 수 있습니다. FAQ의 대상·접수 조건·주의사항은 유지했으나 정책 내용·연락처의 현행성 검증은 별도로 필요합니다. **수집일은 정책 유효성 확인일이 아닙니다.**

원본: [청주톡톡 FAQ](https://toktalk.cheongju.go.kr/home/sub.do?menukey=7403) · [공개 민원 사례](https://toktalk.cheongju.go.kr/home/sub.do?menukey=7401). 수집·정규화 기준일과 필드·누락값·변경 전 표기 보존 범위는 [데이터 사전](rag/origin/README.md)에 정리했습니다.

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

Windows에서 추출한 응대 검사기를 열려면 [`검사기-시작.cmd`](검사기-시작.cmd) 또는 [`웹-시작.cmd`](웹-시작.cmd)를 실행합니다. `http://127.0.0.1:5010/`이 열리고, 민원 JSON은 검색 후 판정합니다. Linux는 [`start-lab.sh`](start-lab.sh)입니다. [CASE-057](docs/cases/사례-057-검사기웹-검색판정-연결-2026-11-06.md) · [CASE-058](docs/cases/사례-058-Codex-MCP-핸드셰이크-줄단위JSON-2026-11-06.md)

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

검색 예제의 통과 기준은 기대 대상의 상위 5개 포함과 검색 전용 계약입니다. **10개 예제는 민원 자동 응답 정확도나 범위 밖 탐지 성능의 평가 결과가 아닙니다.** 보고서·성능 측정 조건은 [RAG 문서](rag/README.md), 변경별 검증과 후속 평가셋 설계는 [평가 하네스](docs/harness/evaluation.md)를 확인합니다.

## 문서와 저장소 구조

| 문서 | 확인할 내용 |
| --- | --- |
| [전체 문서 목차](docs/README.md) | 목적별 읽기 순서와 원본 계획서 |
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
│   ├── complaints/               # 민원 웹 CRUD·세션·UI
│   ├── rag/                      # 검색 API 클라이언트
│   ├── llm/                      # Luna·Codex·legacy 공급자
│   └── assist/                   # RAG와 LLM을 잇는 응대. prompts.py가 PREFIX 조립
├── ui/                           # 시민·담당자·검사기 화면
├── scripts/                      # 한국어 파일명 실행 스크립트. 안내 scripts/README.md
├── docs/                         # 목차·사례·하네스·배너
│   └── harness/prompts/          # PREFIX-00~04 시스템 접두 원문
├── rag/                          # 검색 엔진·색인·CLI. 원본은 origin/
├── db/                           # 이전 경로 안내. 검색 원본은 rag/origin/
├── plan/                         # 원본 계획서·MVP 실행 계획
└── PACKET/                       # 수집기·부서 정규화
```

저장소의 공개 범위는 GitHub 설정을 기준으로 확인합니다. `.env`, 실행 DB, 모델 캐시, 쿠키가 포함된 원본 패킷 캡처(`PACKET/*.saz`)는 Git에서 제외합니다. 원래 계획서의 전체 행정 시스템 구상과 현재 검색 MVP의 범위는 [문서 목차](docs/README.md)에서 구분해 안내합니다.
