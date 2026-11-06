# CASE-038: Windows Codex CLI 명령줄 길이 초과

[사례 색인](README.md) · [서버 안내](../../src/README.md) · [변경 이력](../../CHANGELOG.md)

## 1. 개요와 상태

| 항목 | 기록 |
| --- | --- |
| 사례 ID / 유형 | CASE-038 / 버그 |
| 작업 상태 | 완료 · 로컬 코드. 「나무가 쓰러짐」 실호출 확인 |
| 사건·작업 기준일 / 기록일 / 최종 갱신일 | 2026-11-05 UTC / 2026-11-05 UTC / 2026-11-05 UTC |
| 목적·영향 범위 | `codex_cli` 응대 호출. 검색 근거가 있는 민원 문장 |
| 기준 환경 | Windows / `codex.cmd` / 검색 API `:8007` |
| 구현·적용 범위 | `src/llm/complete.py`, 단위 테스트, 안내 문서 |
| 관련 사례·기준 문서 | [CASE-023](사례-023-GPT-6-Luna-공급자-선택-2026-11-05.md) |

## 2. 배경·증상과 기대 동작

- 관찰한 사실과 영향: `민원-응대.cmd`에 「나무가 쓰러짐」을 넣으면 LLM은 설정된 상태로 `invalid_model_output`이 나고, 정책 검사에 `Codex CLI 호출 실패: The command line is too long.`이 표시됐다.
- 기대 동작 또는 요구사항: 검색 근거가 길어도 Codex CLI 판정이 Windows에서 호출되어야 한다.
- 확인 근거와 시점: 2026-11-05 사용자 실행 출력.

## 3. 재현·확인 방법

- 재현 환경: `COMPLAINT_LLM_PROVIDER=codex_cli`, 검색 API ready, 민원 「나무가 쓰러짐」.
- 비교한 기존 동작: `codex exec ... <프롬프트>`처럼 시스템 지시와 FAQ·사례 근거를 명령줄 인자로 넘겼다.

## 4. 원인 분석 또는 결정 근거

- 확인된 원인·근거: Windows `cmd.exe` 명령줄은 약 8191자로 제한된다. `shutil.which("codex")`가 npm `codex.cmd`를 고르면 긴 프롬프트와 `cmd.exe` 래퍼가 그 제한을 넘는다.
- 검토한 선택지와 결정 이유: `codex exec`는 프롬프트 인자 `-`이면 표준 입력에서 지시를 읽는다. 긴 본문을 stdin으로 보내고, Windows에서는 `codex.cmd` 대신 `node`와 `codex.js`를 직접 실행한다.

## 5. 조치와 변경 내용

| 파일·계약 | 변경 내용 | 구현·반영 상태 |
| --- | --- | --- |
| [`src/llm/complete.py`](../../src/llm/complete.py) | `codex exec ... -`와 stdin, Windows npm 래퍼는 `node`+`codex.js` | 적용 |
| [`rag/tests/test_assist.py`](../../rag/tests/test_assist.py) | 마지막 인자가 `-`, `.cmd`는 node 진입 | 적용 |

## 6. 검증 결과와 한계

| 수행일·환경 | 확인 방법·명령 | 실제 결과 | 증거 파일·커밋 |
| --- | --- | --- | --- |
| 2026-11-05 UTC / Windows / `.venv-web` | `pytest rag/tests/test_assist.py src/tests/test_llm_env.py -q` | 18 passed | 로컬 |
| 2026-11-05 UTC / Windows / `codex_cli` | `python scripts/민원_응대.py --no-start "나무가 쓰러짐"` | `human_handoff` / `condition_unclear`, 판정 9.3s, 정책 실패 없음 | 로컬 실호출 |

- 명령줄 길이 오류는 재현되지 않았다. 짧은 문장 「나무가 쓰러짐」은 적용 조건이 부족해 담당자 검토로 연결됐다. 판정 JSON 품질·운영 모델 확정은 후속이다.

## 7. 완료 조건·후속 작업·복구

- 완료: Windows에서 긴 검색 근거가 명령줄 인자로 나가지 않고, npm `codex.cmd`를 거치지 않는다. 같은 민원 실호출에서 정책 검사가 모델 출력을 받았다.
- 남은 작업: 검색 FAQ 적합성·운영 모델 확정은 후속이다.
- 되돌림: `complete_codex_cli`의 프롬프트 인자를 다시 명령줄 끝으로 두고 `.cmd`를 직접 실행하면 된다.

## 8. 후속 이력

| 날짜 | 변경·재발·후속 검증 | 상태·관련 사례 |
| --- | --- | --- |
| 2026-11-05 UTC | stdin으로 Codex 프롬프트 전달 | 이 사례 |
| 2026-11-05 UTC | Windows npm `codex.cmd`를 `node`+`codex.js`로 우회 | 이 사례 |
