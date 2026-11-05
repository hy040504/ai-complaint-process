# CASE-036: Windows 로컬 RAG 가상환경과 PostgreSQL 기동

[사례 색인](README.md) · [네이티브 운영](../harness/네이티브_운영.md) · [변경 이력](../../CHANGELOG.md)

## 1. 개요와 상태

| 항목 | 기록 |
| --- | --- |
| 사례 ID / 유형 | CASE-036 / 운영·구현·문서 |
| 작업 상태 | 완료 · 이 Windows 호스트 로컬 기동. 관리자 설치·Windows 서비스는 아님 |
| 사건·작업 기준일 / 기록일 / 최종 갱신일 | 2026-11-05 UTC / 2026-11-05 UTC / 2026-11-05 UTC |
| 목적·영향 범위 | 검색 API와 `ask-assist.cmd`가 쓸 RAG `.venv`와 `complaint_rag` DB |
| 기준 환경 | Windows / Python 3.12.10, PostgreSQL 18.6 사용자 디렉터리, pgvector 0.8.7 |
| 구현·적용 범위 | `.rag-data/pgsql`·`.rag-data/postgres`(Git 제외), `.venv`, e5-small 적재 5109건, `start-rag.cmd` |
| 관련 사례·기준 문서 | [CASE-010](사례-010-네이티브-검색환경-전환-2026-10-28.md), [CASE-029](사례-029-가벼운-임베딩과-응대-CMD-2026-11-05.md), [CASE-035](사례-035-응대-CMD-검색API-자동시작-2026-11-05.md) |

## 2. 배경·증상과 기대 동작

- 관찰한 사실과 영향: 이 호스트에 PostgreSQL 서비스·RAG `.venv`·검색 dump가 없어 `ask-assist.cmd`가 검색 API를 띄울 수 없었다.
- 기대 동작 또는 요구사항: Docker 없이 로컬에서 검색 DB와 검색 API를 켜고 민원 문장 검색이 되게 한다.
- 확인 근거와 시점: 2026-11-05 사용자 요청.

## 3. 재현·확인 방법

- 비교한 기존 동작: 네이티브 안내는 Ubuntu 소켓·`sudo` 설치 기준이었다.
- 판단 근거: 관리자 권한 없이 EDB PostgreSQL 18 바이너리 zip과 Windows용 pgvector 0.8.7을 `.rag-data/`에 풀어 사용자 프로세스로 기동한다.

## 4. 원인 분석 또는 결정 근거

- 확인된 원인·근거: Windows에는 PostgreSQL 서비스와 winget/choco가 없고 WSL 배포판도 없었다.
- 검토한 선택지와 결정 이유: 설치 마법사·Docker는 쓰지 않는다. 바이너리 zip은 관리자 없이 동작하고, 데이터 디렉터리는 `.rag-data/postgres`다. Linux 서버의 `/var/lib/postgresql` 구성은 바꾸지 않는다.

## 5. 조치와 변경 내용

| 파일·계약 | 변경 내용 | 구현·반영 상태 |
| --- | --- | --- |
| `.rag-data/pgsql` · `.rag-data/postgres` | PostgreSQL 18.6 + pgvector 0.8.7, DB `complaints_native` | 로컬만. Git 제외 |
| `.venv` | CPU torch 2.9.1과 `rag/requirements.txt` | 로컬 |
| `python -m rag ingest` | e5-small로 FAQ 94·사례 5,015 적재 | 2026-11-05 07:02 UTC |
| [`rag/ingest.py`](../../rag/ingest.py) | 캐시 저장을 `cursor.executemany`로 맞춤 | 적용 |
| [`rag/store.py`](../../rag/store.py) | Windows에서 PG 연결 기본값 localhost/`complaints_native` | 적용 |
| [`scripts/windows_rag.py`](../../scripts/windows_rag.py) · [`start-rag.cmd`](../../start-rag.cmd) | PostgreSQL·검색 API 별도 창 기동 | 적용 |

## 6. 검증 결과와 한계

| 수행일·환경 | 확인 방법·명령 | 실제 결과 | 증거 파일·커밋 |
| --- | --- | --- | --- |
| 2026-11-05 UTC / Windows | `GET http://127.0.0.1:8007/health` | `status=ready`, FAQ 94, 사례 5015, 부서 127 | 로컬 |
| 2026-11-05 UTC / Windows | `python scripts/ask_assist.py --no-start 나무가 쓰러짐` | 사례 근거에 「나무쓰러짐」 등 5건. LLM 미설정으로 `human_handoff` | 로컬. 검색 111ms |

- PostgreSQL과 검색 API는 이 세션의 사용자 프로세스다. 창을 닫거나 세션이 끝나면 다시 [`start-rag.cmd`](../../start-rag.cmd)가 필요하다. Windows 서비스로 등록하지 않았다.
- `.env` LLM 키는 만들지 않았다. 응대 문장은 검색 근거와 담당자 검토 안내까지다.
- `rag.verify`와 검색 회귀 10건은 이 작업에서 실행하지 않았다.

## 7. 완료 조건·후속 작업·복구

- 완료: 이 Windows 호스트에서 검색 API ready와 `나무가 쓰러짐` 실검색을 확인했다.
- 남은 작업: LLM `.env` 설정, `rag.verify`, 재부팅 후 `start-rag.cmd`로 기동.
- 되돌림: `.rag-data/`와 `.venv`를 지우면 로컬 서버·색인이 사라진다. 원본 JSON은 `rag/origin/`에 남는다.

## 8. 후속 이력

| 날짜 | 변경·재발·후속 검증 | 상태·관련 사례 |
| --- | --- | --- |
| 2026-11-05 UTC | Windows 로컬 RAG·PostgreSQL 기동 | 이 사례 |
