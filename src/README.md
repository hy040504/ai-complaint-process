# Flask 민원 업무 서버

프로젝트 루트의 `src/`에 구현한 Flask 서버다. 시민·담당자 UI와 API, Swagger를 같은 출처에서 제공한다. 민원·추가 문의·초안·게시 답변·시연 작업 이벤트는 별도 업무 SQLite DB에 저장한다.

## 설치와 실행

저장소 루트에서 Python 3.12로 실행한다. 기존 RAG 추론 가상환경·DB·모델을 변경하지 않는다. Docker가 필요 없다.

```powershell
py -3.12 -m venv .venv-web
.\.venv-web\Scripts\python.exe -m pip install -r src/requirements-dev.txt

# 선택 사항: 비어 있는 업무 DB에 개인정보 없는 합성 민원 24건 생성
.\.venv-web\Scripts\python.exe -m flask --app src:create_app seed-demo

.\.venv-web\Scripts\python.exe -m src
```

실행 의존성만 설치하려면 `src/requirements.txt`를 사용한다. Linux에서는 `python3.12 -m venv .venv-web`로 준비하고 `.venv-web/bin/python`을 사용한다. 환경 준비 후 `npm --prefix ui run dev`도 같은 Flask 서버를 실행하는 편의 명령이다.

| 주소 | 제공 내용 |
| --- | --- |
| http://127.0.0.1:5000/#/citizen | 시민 사이트 |
| http://127.0.0.1:5000/#/staff | 담당자 사이트 |
| http://127.0.0.1:5000/#/lab | RAG·LLM 응대 검사기 · 민원 CRUD와 분리 |
| http://127.0.0.1:5000/docs | Swagger UI · `/swagger`도 동일 |
| http://127.0.0.1:5000/openapi/openapi.json | 자동 생성 OpenAPI 3.1 · `/openapi.json`은 이 주소로 이동 |
| http://127.0.0.1:5000/api/v1/health | 상태·저장 방식·실제 AI 연결 여부 |

Swagger의 `POST /api/v1/session`에서 `{"role":"citizen"}` 또는 `{"role":"staff"}`를 실행한 뒤 필요한 API를 호출한다. 같은 출처의 서명 세션 쿠키가 요청에 전달된다. UI 상단 역할 선택도 같은 API를 사용한다. 시민·담당자 탭이 같은 쿠키를 공유하므로 역할을 바꾼 뒤 이전 탭을 사용할 때는 해당 화면을 다시 불러온다.

## 정적 타입과 구성

읽을 때는 `app.py → api.py → service.py → repository.py` 순서로 따라가면 된다. `app.py`는 설정을 읽고 저장소·서비스·API·화면을 연결한다. 요청은 API에서 입력을 검증한 뒤 서비스에서 권한·상태를 확인하고 저장소에서 변경한다. 공통 인증·JSON·오류는 `http.py`, 시민·담당자 정적 화면은 `web.py`에 모았다.

| 파일 | 책임·타입 경계 |
| --- | --- |
| `models.py` | Pydantic 요청·응답·업무 모델, `Literal` 상태·역할·지역, `Annotated` 길이·정수 제한, 공개·내부 DTO 분리 |
| `api.py` | Flask APIBlueprint, 모델 기반 요청·응답 검증과 Swagger 자동 생성 |
| `service.py` | 권한·버전 검사와 업무 동작. 답변 저장·철회, 작업 시작·취소를 짧은 전용 메서드로 구분 |
| `repository.py` | `ComplaintRepository(Protocol)`과 SQLite 구현. 트랜잭션 안의 기대 버전·멱등성 검사 |
| `config.py` | `@dataclass(frozen=True)` 설정, 업무 DB 경로·시연 계정 선택 설정 |
| `app.py` | 설정 → 저장소 → 서비스 → 공통 처리·API·화면 등록 순서의 앱 팩토리 |
| `http.py` | 세션 사용자 확인, JSON 응답, 동일 출처 검사, 오류 응답, 캐시·보안 헤더 |
| `web.py` | 시민·담당자 정적 파일과 Swagger·OpenAPI 진입 주소 |
| `assist.py` | 검색 API·LLM 호출과 응대 파이프라인 연결. 민원 CRUD와 분리 |
| `seed.py` | 사용자가 명시적으로 실행하는 합성 자료 생성 |
| `tests/test_api.py` | 격리 DB의 API·권한·게시·경쟁·영속화·OpenAPI 회귀 |
| `tests/test_assist_api.py` | 검사기 세션 생략·응답 계약·health 플래그 |

모든 서버 함수에는 타입 힌트를 적용했다. `Any`나 `type: ignore`로 업무 코드 검사를 우회하지 않고 `mypy --strict`를 통과시켰다. 동적 입력은 Pydantic에서 검증한 뒤 구체 타입으로 서비스에 전달하며, DB 재조회 결과도 모델로 재검증한다. Python 타입 힌트의 정적 검사와 실행 시 검증은 별개다.

코드 형식은 개발 의존성에 포함한 Black으로 정리한다. 저장소 루트에서 `python -m black --check src`로 형식을 확인하고, 수정 시에는 같은 가상환경에서 `python -m black src`를 실행한다. 한국어 Google 형식 docstring과 타입 힌트는 유지한다. [구조 정리 기록](../docs/cases/사례-021-Flask-서버-코드-구조-간소화-2026-10-31.md)

앱 팩토리는 [Flask 공식 안내](https://flask.palletsprojects.com/en/stable/patterns/appfactories/)를 따랐다. 요청·응답 모델과 자동 문서는 [flask-openapi3 요청 선언](https://luolingchun.github.io/flask-openapi/v4.x/Usage/Request/) 및 [응답 검증](https://luolingchun.github.io/flask-openapi/v4.x/Usage/Response/) 기능을 사용한다. Swagger JS·CSS는 설치 패키지의 로컬 자산으로 제공한다.

## API 계약

JSON 필드는 기본적으로 camelCase다. 경로 이름 `complaint_id`와 쿼리 이름은 문서 그대로 사용한다. 불필요한 필드·허용 목록 밖 상태를 거부하며, 작성자·AI 기원·업무 상태를 클라이언트가 임의 지정하지 못한다.

| 메서드·경로 (`/api/v1` 기준) | 권한·기능 |
| --- | --- |
| `GET /health` | 공개 서버 상태. `assistSearch`·`assistLlm`은 검색 API·LLM 토큰 여부. `aiConnected`는 민원 CRUD AI 미연결 |
| `GET /assist/examples` | 검사기 고정 예시. 세션 불필요 |
| `POST /assist` | 검색+판정+정책 검사. 세션 불필요. 민원 저장 없음 |
| `POST /assist/stream` | 같은 파이프라인의 짧은 진행 안내 NDJSON. 세션 불필요 |
| `POST /session`, `GET /session`, `DELETE /session` | 시연 계정 선택·조회·종료 |
| `GET /workspace` | 역할별 로컬 UI 전체 스냅샷 |
| `GET /complaints` | 공개 범위 적용 후 검색·페이지 목록 |
| `POST /complaints` | 시민 등록, `Idempotency-Key` 지원 |
| `GET /complaints/{complaint_id}` | 허용된 상세만 조회 |
| `PUT /complaints/{complaint_id}` | 게시 전 본인 원문 수정 |
| `DELETE /complaints/{complaint_id}` | 본인 글 논리 철회와 사유 저장 |
| `POST /complaints/{complaint_id}/messages` | 본인 추가 문의·검토 재개 |
| `POST /complaints/{complaint_id}/review` | 본인 재검토 요청 |
| `PUT /complaints/{complaint_id}/assignment` | 담당자 지정·해제 |
| `PUT /complaints/{complaint_id}/draft` | 담당자 초안·편집 이력 저장 |
| `POST /complaints/{complaint_id}/publish` | 담당자 답변 게시·기원 판별 |
| `POST /complaints/{complaint_id}/retract` | 담당자 게시본 철회·이력 보존 |
| `POST /complaints/{complaint_id}/jobs` | 담당자 서버 단계 시연 시작 |
| `POST /complaints/{complaint_id}/jobs/cancel` | 담당자 단계 시연 취소 |

등록 본문 예시:

```json
{
  "title": "보행로 시설 점검 요청",
  "body": "화면 검증을 위해 만든 합성 민원입니다. 보행로 시설 점검과 검토 결과 안내를 요청합니다.",
  "category": "도로·교통",
  "district": "흥덕구",
  "visibility": "private"
}
```

제목 1~120자, 원문 10~2,000자, 답변 1~4,000자, 사유 1~200자다. 공백만 있는 입력을 거부한다. 기존 민원을 바꾸는 요청에는 조회한 `version` 정수가 필수다. 답변 저장·게시는 `version`, `text`, `reason`을 보낸다. 서버는 `409 version_conflict`로 오래된 저장을 거부하며 UI는 편집 입력을 유지한다. 같은 등록 키와 같은 원문을 재전송하면 같은 민원을 반환하고, 같은 키에 다른 원문은 409로 거부한다.

목록은 `q`, `status`, `district`, `category`, `mine`, `assign`, `page`, `limit`를 지원한다. 기본 8건, 최대 100건이며 시민 건수에서도 다른 사람의 비공개 글과 철회 글을 제외한다. UI는 소규모 로컬 시연을 위해 `/workspace`를 읽어 화면 필터·집계를 구성한다. 대규모 운영에서는 전체 스냅샷 대신 페이지 API·서버 집계로 전환해야 한다.

오류 응답은 `{"code":"version_conflict","message":"…"}` 형식이다. 미인증 401, 역할 위반 403, 없는 글·열람 불가 404, 버전·상태·등록 키 충돌 409, 입력 검증 422를 구분한다. 손상 JSON은 400, 64 KiB 본문 한도 초과는 413이다. 입력 오류 응답에 민원 원문을 반사하지 않는다.

## 데이터·게시·작업 경계

- 기본 DB: `db/app/complaints.sqlite3`. 민원 상태·답변 버전·작업을 Pydantic JSON으로 저장하는 `complaints`와 등록 키를 보존하는 `idempotency` 테이블이다. 변경·버전 검사와 등록 중복 방지는 SQLite 트랜잭션 안에서 수행한다. RAG 원본 JSON·검색 스키마와 같은 `db/` 아래에 두되 파일은 분리한다.
- 기존 `complaint_rag`, 원본 JSON, PostgreSQL 자료를 변경하지 않는다. [PostgreSQL 1차 업무 스키마](../plan/db%20설계%201차/2026-10-30/README.md)를 적용한 구현은 아니며, 별도 저장소 구현·마이그레이션은 후속 작업이다.
- 초안·AI 원본·후보·담당자 편집 이력·내부 작업은 담당자 응답에만 들어간다. 시민 목록·상세·스냅샷에서는 응답 전용 모델로 제거한다. 초안 저장 자체의 내부 이력도 시민에게 반환하지 않는다.
- 본문 수정·추가 문의·철회·게시·재검토는 맥락 버전을 증가시킨다. 실행 중인 기존 작업은 무효화한다. 시연 작업은 후보만 별도로 저장하고 사람의 편집본·게시본을 자동 교체하지 않는다.
- AI 완료·답변 게시·민원 상태는 구분한다. 새 민원은 실제 AI 미연동 대기 상태이며 저장 성공을 AI 성공으로 표시하지 않는다. 서버 단계 시연은 조회 시 경과 시간에 맞춰 이벤트를 저장하고 UI가 1.5초 간격으로 조회한다. 실제 추론·백그라운드 작업자·SSE가 아니다.
- 기존 브라우저 `cheongju-ui-v1` 자료는 보존하며 서버로 자동 업로드하지 않는다. 신규 업무 저장은 API만 사용한다. `sessionStorage`에는 작성 전 임시 입력만 남긴다.

## 설정·검증·남은 범위

| 환경 변수 | 기본 동작 |
| --- | --- |
| `COMPLAINT_PORT` | `5000`, localhost에만 바인딩 |
| `RAG_API_URL` | 검색 API, 기본 `http://127.0.0.1:8007` |
| `COMPLAINT_LLM_TOKEN` / `PUBLIC_LLM_TOKEN` / `XAI_API_KEY` | 응대 LLM. 없으면 검색 후 담당자 검토 |
| `COMPLAINT_LLM_URL` · `COMPLAINT_LLM_MODEL` | OpenAI 호환 주소와 모델 이름 |
| `COMPLAINT_DATABASE` | `db/app/complaints.sqlite3` |
| `COMPLAINT_SECRET_KEY` | 미지정 시 `.web-data/session.key`에 생성·보존, 로그·Git에서 제외 |
| `COMPLAINT_DEMO_LOGIN` | `1`, `0`이면 시연 계정 선택 거부 |
| `COMPLAINT_PYTHON` | npm 실행기에 사용할 Python 실행 파일 선택 |

```powershell
.\.venv-web\Scripts\python.exe -m mypy --config-file src/mypy.ini
.\.venv-web\Scripts\python.exe -m pytest src/tests -q -p no:cacheprovider
npm --prefix ui run check
npm --prefix ui test
```

2026-10-31 Windows / Python 3.12에서 서버 파일 10개 엄격한 타입 검사, API 회귀 18개, JS 문법 검사와 API 클라이언트 회귀 3개를 통과했다. OpenAPI 문서는 규격 검증도 수행했다. 실제 브라우저 검증과 한계는 [CASE-014](../docs/cases/사례-014-Flask-업무서버와-Swagger-구현-2026-10-31.md)에 기록한다.

**미구현:** 운영용 본인인증·담당자 인증, PostgreSQL 업무 스키마·마이그레이션, 실제 LLM/RAG 어댑터·작업자·SSE, 파일 첨부, 공식 행정 접수·외부 이관, 운영 배포. 역할 선택은 로컬 시연이며 운영용 권한 부여 수단이 아니다. 권한 있는 담당자 복구와 실제 보존 기간 정책은 후속 구현이다.
