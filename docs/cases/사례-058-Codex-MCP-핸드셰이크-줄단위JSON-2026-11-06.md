# CASE-058: Codex MCP 핸드셰이크 줄 단위 JSON

[사례 색인](README.md) · [검사기 웹](../../src/lab_web/README.md) · [CASE-048](사례-048-Codex-RAG-검색-도구-2026-11-06.md) · [변경 이력](../../CHANGELOG.md)

## 1. 개요와 상태

| 항목 | 기록 |
| --- | --- |
| 사례 ID / 유형 | CASE-058 / 버그 |
| 작업 상태 | 완료 · GitHub는 CASE-060. 실측 판정은 로컬에서 확인 |
| 사건·작업 기준일 / 기록일 / 최종 갱신일 | 2026-11-06 UTC / 2026-11-06 UTC / 2026-11-06 UTC |
| 목적·영향 범위 | `codex_cli` 판정이 MCP 기동에서 45초 타임아웃 나던 경로 |
| 기준 환경 | `llm` 브랜치, Codex 0.166, 검사기 `:5010`, 검색 `:8007` |
| 구현·적용 범위 | `src/llm/rag_mcp.py` stdio 프레임, `complete.py` Python `-u` |
| 관련 사례 | [CASE-048](사례-048-Codex-RAG-검색-도구-2026-11-06.md), [CASE-057](사례-057-검사기웹-검색판정-연결-2026-11-06.md) |

## 2. 배경·증상과 기대 동작

- 관찰한 사실과 영향: `POST /api/v1/lab/complaints`는 검색을 성공한 뒤 판정이 `invalid_model_output`이었다. Codex stderr는 `complaint_rag: timed out handshaking with MCP server after 45s`였다.
- 기대 동작: Codex가 `search_complaint_rag` MCP와 핸드셰이크한 뒤 PREFIX-01 판정 JSON을 반환한다.
- 확인 근거: 2026-11-06 대형폐기물 안내 민원 실호출.

## 3. 재현·확인 방법

- 재현 환경·선행 조건: `COMPLAINT_LLM_PROVIDER=codex_cli`, 검색 API 기동, 검사기 웹 기동.
- 입력: 흥덕구 대형폐기물 스티커 인터넷 발급 문의.
- 실제 결과(수정 전): 검색 약 0.16초 성공, 판정 46초 실패, MCP 핸드셰이크 45초 만료.

## 4. 원인 분석 또는 결정 근거

- 확인된 원인·근거: MCP stdio 규격은 줄 단위 JSON-RPC이다. 서버는 LSP식 `Content-Length` 헤더만 기다려 Codex `initialize` 한 줄을 헤더로 오인하고 빈 줄을 무한 대기했다. 프로세스는 살아 있어 Codex가 45초 뒤 핸드셰이크 실패로 끊었다. 모듈 import는 1초 미만이었다.
- 검토한 선택지: 타임아웃만 늘리면 교착이 길어진다. MCP를 `required=false`로 두면 핸드셰이크 실패 시 도구 없이 진행할 수는 있으나 원인 미해결이다. 줄 단위 프레임을 읽고 받은 형식으로 응답한다.

## 5. 조치와 변경 내용

| 파일·계약 | 변경 내용 | 구현·반영 상태 |
| --- | --- | --- |
| [`src/llm/rag_mcp.py`](../../src/llm/rag_mcp.py) | `{`로 시작하면 NDJSON, 아니면 Content-Length | 적용 |
| [`src/llm/complete.py`](../../src/llm/complete.py) | MCP Python 인자에 `-u` | 적용 |
| [`src/tests/test_rag_tool.py`](../../src/tests/test_rag_tool.py) | NDJSON 초기화 왕복 | 적용 |

## 6. 검증 결과와 한계

| 수행일·환경 | 확인 방법·명령 | 실제 결과 | 증거 |
| --- | --- | --- | --- |
| 2026-11-06 `.venv-web` | pytest `test_rag_tool.py` + Codex 인자 회귀 | 6 passed | 로컬 |
| 2026-11-06 | `python -u -m src.llm.rag_mcp`에 NDJSON `initialize`·`tools/list` | 0.63초 응답 | 로컬 |
| 2026-11-06 `:5010` | 흥덕구 대형폐기물 JSON POST | 검색 0.18초, 판정 5.9초, 정책검사·FAQ 안내 9.3초 모두 성공. `outcome=faq_answer`, `reason_code=ok` | 로컬 |

- 검색은 코드가 먼저 하므로 후보가 있으면 PREFIX-01은 도구를 다시 부르지 않는다. MCP는 Codex 세션 기동에 여전히 필요하다.
- 판정 JSON 스키마 불일치는 이 사례 범위가 아니다.

## 7. 완료 조건·후속 작업·복구

- 완료: Codex가 MCP `initialize`에 응답하고 검사기 판정 단계가 실패하지 않는다.
- 복구: `read_stdio_message`를 빼고 Content-Length만 쓰면 CASE-048 서버로 돌아간다.

## 8. 후속 이력

| 날짜 | 변경·재발·후속 검증 | 상태·관련 사례 |
| --- | --- | --- |
| 2026-11-06 UTC | 줄 단위 JSON-RPC 수신 | 이 사례 |
