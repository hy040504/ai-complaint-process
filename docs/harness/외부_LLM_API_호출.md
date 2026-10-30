# 외부 LLM API 호출 예제

[프로젝트 소개](../../README.md) · [문서 목차](../README.md) · [변경 이력](../../CHANGELOG.md) · [CASE-012](../cases/사례-012-외부-LLM-호출-예제와-저장소-반영-정정-2026-10-30.md)

기준일: **2026-10-30 UTC**. LLMmanager에서 제공하는 외부 모델과 질문·답변을 주고받는 독립 Python 예제다. 이 프로젝트의 검색·FAQ 판정·답변 검증과 연결된 민원 챗봇은 아직 미구현이며, 최종 모델 선정·정책 평가와도 구별한다.

## 주소와 인증

| 항목 | 값 |
| --- | --- |
| 기본 주소 | `https://llm.mib.dpdns.org/v1` |
| 현재 모델 목록 | `GET /v1/models` |
| 대화 생성 | `POST /v1/chat/completions` |
| 필수 요청 헤더 | `token: 운영자가_발급한_값` |
| 토큰 설정 | `LLM_API_TOKEN` 환경변수 |

토큰이 없거나 다르면 HTTP 401이다. Bearer 인증과 URL 쿼리로는 인증하지 않는다. 토큰 원문은 코드·문서·Git에 넣지 않는다. 공개 주소의 프록시·터널·모델 서버는 별도 [LLMmanager 저장소](https://github.com/hy040504/LLMmanager/tree/linux)에서 관리한다. 이 저장소에는 호출 예제와 프로젝트 문서를 보관한다.

## 실행

[예제 코드](../../scripts/public_llm_client.py)는 한국어 주석·Google 형식 docstring·타입 힌트를 포함한다. Python 3.10 이상 표준 라이브러리만 사용하며 별도 패키지·Docker·검색 DB·임베딩 모델이 필요하지 않다. 프로젝트의 기본 네이티브 Python 3.12 환경에서도 사용할 수 있다.

저장소 루트에서 실행한다. 다음 명령은 실제 모델 추론을 호출하므로 요청할 질문을 직접 입력한다.

```bash
read -rs -p 'API token: ' LLM_API_TOKEN
printf '\n'
export LLM_API_TOKEN
python3 scripts/public_llm_client.py
unset LLM_API_TOKEN
```

프로그램은 현재 공개된 첫 번째 모델 ID를 조회한 뒤 질문을 받는다. `/exit` 또는 `/quit`으로 종료한다. 모델 이름을 고정하지 않으며 목록에 모델이 없으면 오류를 알린다.

## 코드 흐름과 한계

| 함수·자료형 | 역할 |
| --- | --- |
| `Message` | `system`·`user`·`assistant` 역할과 본문에 타입 지정 |
| `request_json()` | `token` 헤더와 JSON 요청 전송, HTTP·연결·JSON 오류 처리 |
| `get_model_id()` | 현재 모델 목록에서 첫 번째 ID 선택 |
| `send_message()` | 이전 대화와 새 질문을 전송하고 답변 텍스트 수신 |
| `main()` | 환경변수 확인·질문 입력·성공한 질문과 답변의 이력 유지 |

`stream=false`로 전체 답변을 한 번에 받으며 최대 출력은 512토큰, 요청 제한 시간은 180초다. 대화 이력은 메모리에만 유지하고 자동으로 자르지 않는다. 긴 대화는 다시 시작하거나 호출부에서 컨텍스트 한도를 관리해야 한다. 실패한 생성 요청은 자동 재전송하지 않는다.

예제는 명시적 사용자 에이전트 `LLMmanager-Python-Example/1.0`을 사용한다. 초기 확인에서 기본 Python urllib 사용자 에이전트는 Cloudflare 1010으로 거부됐으며, 예제의 사용자 에이전트로 실제 모델 목록 HTTP 200을 확인했다. 토큰 인증과 Cloudflare의 기존 보안 정책은 각각 적용된다.

이 예제는 검색 근거·출처·조건 보존·부서 검증을 구현하지 않는다. 생성된 일반 답변을 공식 FAQ 안내나 자동 이관 판단으로 사용하지 않는다. 기존 검색 API의 `retrieval_only=true`, `decision="requires_gate"` 계약을 유지하며 판정·FAQ 생성·코드 검증 연결은 [후속 계획](../../plan/harness-roadmap.md)을 따른다.

## 검증 범위

2026-10-30 UTC에 이 저장소의 예제에서 공개 모델 목록 HTTP 200을 확인하고, 격리한 모의 HTTP 서버로 한국어 질문 두 차례의 왕복·이력 전달·`token` 헤더와 401·잘못된 JSON 오류 처리를 검사했다. Python 구문·한국어 설명·타입 힌트와 문서 링크도 점검했다. 실제 생성 요청과 RAG 통합·모델 품질 평가는 실행하지 않았다.

GitHub 반영 대상은 **`hy040504/ai-complaint-process`의 `main`**이다. `ui` 브랜치는 변경하지 않는다. 별도 LLMmanager 커밋을 이 프로젝트의 반영으로 간주하지 않는다.
