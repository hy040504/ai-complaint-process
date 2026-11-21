# 실행 파일 (`bin/`)

[프로젝트 소개](../README.md) · [스크립트 안내](../scripts/README.md) · [네이티브 운영](../docs/harness/네이티브_운영.md)

사용자가 직접 실행하는 진입점만 모았습니다. 환경 준비는 저장소 루트의 [`setup.cmd`](../setup.cmd)(Windows)·[`setup.sh`](../setup.sh)(Linux)입니다. 모든 파일은 어느 위치에서 실행해도 저장소 루트로 이동한 뒤 동작합니다.

| 하고 싶은 일 | Windows | Linux | 주소·결과 |
| --- | --- | --- | --- |
| 민원 웹 + 응대 검사기 켜기 | [`start-web.cmd`](start-web.cmd) · [`start-lab.cmd`](start-lab.cmd) | [`start-web.sh`](start-web.sh) · [`start-lab.sh`](start-lab.sh) | 검사기 `http://127.0.0.1:5010/` (PostgreSQL·검색 API 자동 기동) |
| 검색 API(RAG) 켜기 | [`start-search.cmd`](start-search.cmd) | [`start-search.sh`](start-search.sh) | `http://127.0.0.1:8007/docs` |
| 민원 문장으로 RAG+LLM 응대 확인 | [`ask-assist.cmd`](ask-assist.cmd) | [`ask-assist.sh`](ask-assist.sh) | 터미널 출력 |
| 한 문장 임베딩·pgvector 이웃 | [`embed-sentence.cmd`](embed-sentence.cmd) | [`embed-sentence.sh`](embed-sentence.sh) | 벡터·FAQ·사례 이웃 |

- `start-web`과 `start-lab`은 같은 검사기 웹(`src.lab_web`, `:5010`)을 켭니다. 업무 서버(`:5000`)는 `python -m src`입니다([서버 안내](../src/README.md)).
- 각 파일이 호출하는 본체는 [`scripts/run/`](../scripts/run/) 아래에 있습니다.
