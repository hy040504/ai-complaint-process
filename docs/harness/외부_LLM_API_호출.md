# 외부 LLM API 호출 예제

[프로젝트 소개](../../README.md) · [문서 목차](../README.md) · [변경 이력](../../CHANGELOG.md) · [CASE-012](../cases/사례-012-외부-LLM-호출-예제와-저장소-반영-정정-2026-10-30.md)

기준일: **2026-10-30 UTC**. [예제 코드](../../scripts/public_llm_client.py)는 주소·모델명·질문·헤더를 직접 지정하고 POST 요청 한 번의 응답 본문을 그대로 콘솔에 출력하는 독립 Python 프로그램이다. 한국어 주석과 변수 타입 힌트를 포함하며 표준 라이브러리만 사용한다.

## 실행

저장소 루트에서 실행한다. 이 명령은 실제 AI 추론을 호출한다.

```bash
python3 scripts/public_llm_client.py
```

질문은 코드의 `body` 안에 있는 `content` 값을 바꾼다. 모델명과 `token`, `Content-Type`, `User-Agent` 헤더도 코드에 직접 적혀 있다. 별도의 환경변수 설정·모델 목록 조회·대화 입력 반복은 없다.

## 요청과 응답

- 주소: `https://llm.mib.dpdns.org/v1/chat/completions`
- 메서드: `POST`
- 인증: `token` 헤더. 누락·불일치 시 HTTP 401이다.
- 본문: `model`, `messages`, `max_tokens=128`, `stream=false`인 JSON 문자열이다.
- 출력: 서버의 응답 본문 전체를 UTF-8 문자열로 출력한다. JSON 파싱이나 `choices` 필드 추출은 하지 않는다.
- 제한 시간: 180초. HTTP·연결 오류는 Python의 기본 예외로 나타난다.

사용자가 다른 사람에게 공유하기 위해 **지정 토큰을 코드에 포함한 GitHub 업로드를 명시적으로 요청했다.** 이에 따라 이 예제는 토큰을 직접 포함하며 추가 환경변수 설정 없이 실행한다. 문서에 토큰 값을 반복해서 복사하지 않는다. 이전 커밋의 환경변수 예제는 이력으로 남긴다.

현재 모델이 바뀌면 코드의 `model`도 바꿔야 한다. 초기 확인에서 Python 기본 urllib 사용자 에이전트가 Cloudflare 1010으로 거부되어, 모델 목록 HTTP 200을 확인한 명시적 사용자 에이전트를 사용한다. 공개 API 서버·프록시·터널은 별도 LLMmanager에서 관리한다.

## 검증과 프로젝트 경계

격리된 모의 응답으로 POST·JSON 요청 본문·필수 헤더와 응답 본문 전체의 콘솔 출력을 확인했다. 실제 AI 생성 요청은 실행하지 않았다. 현재 모델명은 공개 모델 목록의 읽기 전용 조회로 확인했다.

이 예제는 RAG 검색·판정·FAQ 출처 검사와 연결하지 않는다. 기존 검색 API의 `retrieval_only=true`, `decision="requires_gate"` 계약을 유지하며, 민원 챗봇 통합과 최종 모델 선정은 [후속 계획](../../plan/harness-roadmap.md)을 따른다.
