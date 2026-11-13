# CASE-084: K-EXAONE 2.5 API 공급자 추가와 Tabular 연동 구상

[사례 색인](README.md) · [전체 문서](../README.md) · [서버 안내](../../src/README.md)

## 1. 개요와 상태

| 항목 | 기록 |
| --- | --- |
| 사례 ID / 유형 | CASE-084 / 구현·개선·문서 |
| 작업 상태 | 완료 |
| 사건·작업 기준일 / 기록일 / 최종 갱신일 | 2026-11-13 UTC / 2026-11-13 UTC / 2026-11-13 UTC |
| 목적·영향 범위 | 무료 국산 LLM 공급자(K-EXAONE 2.5) 추가, `.env` 키 연동, EXAONE Tabular 후속 확장 경로 수립 |
| 기준 환경 | Windows 10, Python 3.12, Node 22, EXAONE API Platform (`docs.exaone.ai`) |
| 구현·적용 범위 | `src/llm/settings.py`, `src/llm/complete.py`, `src/assist/`, `src/lab_web/`, `src/complaints/models.py`, `.env.example`, `.env`, `README.md`, `src/README.md`, `src/tests/` |
| 관련 사례·기준 문서 | [CASE-023](사례-023-GPT-6-Luna-공급자-선택-2026-11-05.md), [CASE-062](사례-062-PREFIX캐시조립-공급자비교-초안평가-2026-11-06.md), [CASE-083](사례-083-서원대후문-장소추적-MCP연동-위치인식-2026-11-13.md) |

## 2. 배경과 요구사항

- **배경:**
  - 본 저장소의 작업 지침([AGENTS.md](../../AGENTS.md))은 **"한국어 직접 입력과 무료 모델 우선"**을 기본 원칙으로 정하고 있습니다.
  - 기존에는 유료 API 키가 필요한 `openai_api`와 로컬 CLI 설치가 필요한 `codex_cli` 위주로 구성되어 있어, 외부 키 없이 바로 테스트할 수 있는 무료 국산 초거대 생성 모델 도입 필요성이 제기되었습니다.
  - LG AI연구원이 공식 개발자 플랫폼([docs.exaone.ai](https://docs.exaone.ai))을 통해 완전 무료로 공개한 `K-EXAONE 2.5` (`k-exaone_v2.5`)는 750B(활성 31B) 파라미터의 에이전틱 생성 모델로서, OpenAI 호환 규격 및 상시 추론(Thinking)을 지원합니다.
  - 아울러 함께 공개된 정형(표) 데이터 특화 예측 모델인 `EXAONE Tabular`의 후속 프로젝트 연계 위치를 명확히 정립할 필요가 있었습니다.

## 3. 조치 내용

1. **환경변수 및 설정 템플릿 확충 (`.env`, `.env.example`):**
   - `EXAONE_API_KEY` 환경변수 키 항목을 추가.
   - `COMPLAINT_LLM_PROVIDER=exaone_api`, `COMPLAINT_LLM_MODEL=k-exaone_v2.5` 주석 안내 템플릿 반영.
2. **공급자 설정 로직 구현 (`src/llm/settings.py`):**
   - `_LLM_ENV_KEYS`에 `EXAONE_API_KEY` 등록.
   - `EXAONE_COMPLETIONS_URL = "https://api.exaone.ai/v1/chat/completions"`, `DEFAULT_EXAONE_MODEL = "k-exaone_v2.5"` 상수 정의.
   - `llm_settings()` 내 `provider == "exaone_api"` 처리 구현: 모델이 미지정이거나 기본 `gpt-6-luna`인 경우 자동으로 `k-exaone_v2.5`로 전환되도록 편의 로직 적용.
   - `llm_configured()`에서 `EXAONE_API_KEY` 존재 시 호출 가능(True)으로 판정.
3. **완성 요청 어댑터 및 토큰 집계 구현 (`src/llm/complete.py`):**
   - `complete_exaone_result(settings, system, user) -> CompleteResult`:
     - OpenAI 호환 `chat/completions` 포맷으로 HTTP JSON 요청 전송.
     - `reasoning_effort` (`low`, `high`, `max`) 옵션 지원.
     - `choices[0].message.content` 답변 파싱 및 `usage_from_openai` 토큰 집계.
   - `usage_from_openai`: Responses API(`input_tokens`)뿐만 아니라 Chat Completions 표준(`prompt_tokens`, `completion_tokens`)도 모두 파싱할 수 있도록 정규화.
   - `complete_result` 함수에 `provider == "exaone_api"` 분기 연결.
4. **`EXAONE Tabular` 모델의 후속 추가 위치 문서화 (`README.md`, `src/README.md`):**
   - 메인 README에 `K-EXAONE 2.5` 배지 추가.
   - 정형 데이터 전문 예측 모델인 `EXAONE Tabular`는 텍스트 생성이 아닌 수치/범주형 예측을 담당하므로, 추후 **`src/complaints/analytics/`** (또는 `src/assist/tabular.py`) 경로에 추가하여 (1) 민원 처리 예상 소요일(회귀) 예측, (2) 부서 핑퐁(재이송) 위험도 사전 판별, (3) 긴급도 스코어링의 보조 엔진으로 결합하기에 적합함을 구상 항목으로 명시.
5. **응대 검사기 웹 UI 엔진 선택 및 장소 추적 배지 연동 (`src/lab_web/`):**
   - 검사기 상단에 LLM 공급자 선택 버튼 그룹(기본 설정, K-EXAONE 2.5, Codex CLI, GPT-6 Luna API) 배치.
   - `localStorage`(`cheongju_lab_llm_provider`)를 통해 마지막 선택 엔진 유지.
   - 폼 전송 시 `provider`가 `/api/v1/lab/complaints` 및 `/stream` 파이프라인으로 전달되어 해당 공급자 모델로 판정/초안 수행.
   - 결과 화면에 선택된 LLM 엔진 배지(`🤖 LLM 엔진: ...`) 및 네이버 지도 장소 추적 배지(`🗺️ 장소 추적: ...`) 렌더링.
   - `AssistResponse` 모델에 `inferred_place` 스키마 필드 반영.
   - 시스템 프롬프트(PREFIX-00, PREFIX-01, PREFIX-03)에 `lookup_navermap_place` 및 장소 추론 결과 활용 지침 명시.
6. **단위 테스트 추가 및 검증 (`src/tests/`):**
   - `.env`에서 `exaone_api` 선택 및 기본 설정 파싱 검증 (`test_env_file_selects_exaone_api`).
   - 모의 HTTP 응답을 통한 `complete_exaone_result` 호출 및 토큰 사용량 집계 검증 (`test_complete_exaone_result_with_mock`).
   - 검사기 웹의 `provider` 수신 및 유지 검증 (`test_complaint_accepts_provider`).

## 4. 검증 결과

- **단위 테스트 실행:**
  - `pytest src/tests/test_llm_env.py -q` ➡️ **6 passed** (신규 테스트 2건 포함)
  - `pytest src/tests -q` ➡️ **127 passed, 2 skipped** (100% 통과)
  - `pytest rag/tests -q -p no:cacheprovider` ➡️ **48 passed, 3 skipped** (100% 통과)
- **프론트엔드 검사:**
  - `npm --prefix ui run check` ➡️ **JavaScript 문법 검사 14개 통과**
  - `npm --prefix ui test` ➡️ **단위 테스트 6개 통과**
