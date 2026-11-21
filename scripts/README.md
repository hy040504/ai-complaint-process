# 실행·운영·평가·보고서 스크립트 (`scripts/`)

[프로젝트 소개](../README.md) · [검색 실행](../rag/README.md) · [서버 안내](../src/README.md) · [`bin/` 실행 파일](../bin/README.md)

스크립트는 **무엇을 하는가**에 따라 네 폴더로 나뉩니다. 파일 이름은 모두 영문이고, 설명 주석·문서는 한국어입니다. 모든 명령은 저장소 루트에서 실행합니다.

```text
scripts/
├─ ops/       환경 준비·DB·덤프·서비스 설치 (운영)
├─ run/       서버·CLI 기동 (사용자 실행)
├─ eval/      응대 평가·실증·회귀 검증
└─ reports/   업무보고·분석보고서 PDF 생성
```

처음이라면 [`setup.cmd`](../setup.cmd)(Windows) 또는 [`setup.sh`](../setup.sh)(Linux)로 환경을 준비하고, 서버는 [`bin/`](../bin/README.md)의 실행 파일로 켭니다. 아래 파일은 그 실행 파일이 호출하는 본체입니다.

## `ops/` — 환경·DB·서비스

| 파일 | 역할 | 실행 환경 |
| --- | --- | --- |
| [`setup_env.py`](ops/setup_env.py) | 가상환경·PostgreSQL·임베딩 모델 준비. `--check`는 확인만 | Python 3.12 |
| [`native-env.sh`](ops/native-env.sh) | 우분투 네이티브 PG·모델 캐시 환경 변수 | `source` |
| [`prepare-python.sh`](ops/prepare-python.sh) | `.venv`와 CPU 검색 의존성 | 우분투 |
| [`prepare-db.sh`](ops/prepare-db.sh) | 로컬 PostgreSQL 계정·확장 | 우분투, sudo |
| [`apply-schema.sh`](ops/apply-schema.sh) | `complaint_rag`·`complaint_app` DDL 적용 | 우분투 |
| [`export-dump.sh`](ops/export-dump.sh) | `rag/origin/dumps/complaint_rag.dump` 내보내기 | 우분투 |
| [`restore-dump.sh`](ops/restore-dump.sh) | dump 복원 또는 스키마만 적용 | 우분투 |
| [`serve-search.sh`](ops/serve-search.sh) | `python -m rag serve` | 우분투 `.venv` |
| [`install-search-service.sh`](ops/install-search-service.sh) | systemd 사용자 서비스 설치 | 우분투 |
| [`deploy-remote.ps1`](ops/deploy-remote.ps1) | `main`을 SSH 서버에 올리고 서비스 재시작·헬스 확인. 원격 bash는 [`remote/`](ops/remote/) | Windows PowerShell, 접속용 배치 파일 |
| [`remote/harden-web.sh`](ops/remote/harden-web.sh) · [`remote/verify-sites.sh`](ops/remote/verify-sites.sh) | 서버 운영 설정(시연 로그인 끄기·계정 비밀번호 교체)과 사이트 분리 검증 | 서버에서 실행 |

## `run/` — 기동·CLI

| 파일 | 역할 | 실행 환경 |
| --- | --- | --- |
| [`start_web.py`](run/start_web.py) | Flask 민원 웹·검사기 기동, 시민 화면 열기 | `.venv-web` |
| [`start_search.py`](run/start_search.py) | Windows PostgreSQL·검색 API 기동 | `.venv-web`이 기동, 검색은 `.venv` |
| [`start_console.py`](run/start_console.py) | 새 콘솔·포트 확인 공유 모듈. 직접 실행하지 않음 | 표준 라이브러리 |
| [`assist_cli.py`](run/assist_cli.py) | 검색 API 위 RAG+LLM 응대 | `.venv-web` |
| [`embed_sentence.py`](run/embed_sentence.py) | 한 문장 임베딩 뒤 FAQ·사례 pgvector 이웃. `--raw`·`--no-search`는 벡터만 | RAG `.venv` |
| [`external_llm_example.py`](run/external_llm_example.py) | 민원 RAG와 분리된 공개 LLM 호출 예제 | `PUBLIC_LLM_TOKEN` |

## `eval/` — 평가·검증

| 파일 | 역할 | 실행 환경 |
| --- | --- | --- |
| [`live_eval_200.py`](eval/live_eval_200.py) | `:5010` 실서버에 200건을 호출해 [`lab-5010-eval-200-20261119.json`](../rag/reports/lab-5010-eval-200-20261119.json) 생성 | `.venv-web` + `:5010`/`:8007` |
| [`live_eval_100_recheck.py`](eval/live_eval_100_recheck.py) | `CASE-106~108` 패치 후 100건 재검증·EXAONE 이어하기, [`lab-5010-eval-100-20261120.json`](../rag/reports/lab-5010-eval-100-20261120.json) 저장 | 위와 같음 |
| [`live_eval_100_codex.py`](eval/live_eval_100_codex.py) | `CASE-113` 신규 100건 전수 `codex_cli` 실증, [`lab-5010-eval-100-codex-20261120.json`](../rag/reports/lab-5010-eval-100-codex-20261120.json) 저장 | 위와 같음 |
| [`regression_112_rules.py`](eval/regression_112_rules.py) | LLM 없이 112건·공개 사례 5,015건 규칙(지명·순화·장소·타지역) 검증 | `.venv-web` |
| [`evaluate_assist.py`](eval/evaluate_assist.py) · [`measure_assist.py`](eval/measure_assist.py) · [`compare_assist.py`](eval/compare_assist.py) | 응대 평가 세트 실행·실측·모델 비교 | `.venv-web` |
| [`verify_frontend.js`](eval/verify_frontend.js) · [`verify_live_lab_call.js`](eval/verify_live_lab_call.js) | UI 점검·실서버 검사기 호출 검증 | Node |

## `reports/` — 보고서 생성

| 파일 | 역할 | 실행 환경 |
| --- | --- | --- |
| [`report_common.py`](reports/report_common.py) | 브라우저 탐색·PDF 인쇄·UI 캡처·카드 조립 공용 모듈 | `.venv-web` + pypdf |
| [`daily_report_base.py`](reports/daily_report_base.py) · `daily_report_YYYYMMDD.py`(`20261110`·`20261111`·`20261116`·`20261117`·`20261118`·`20261119`) | 일자별 업무보고 PDF 생성·병합. 산출물은 [`docs/reports/daily/`](../docs/reports/README.md) | `.venv-web` + Chrome/Edge |
| [`analysis_report_100_codex.py`](reports/analysis_report_100_codex.py) · [`analysis_report_200.py`](reports/analysis_report_200.py) · [`analysis_report_112.py`](reports/analysis_report_112.py) | 실증 원자료 기반 SVG 차트·MD/PDF 분석 보고서. 산출물은 [`docs/reports/analysis/`](../docs/reports/README.md) | `.venv-web` + Chrome/Edge |

## 참고

- CMD 실행 파일은 UTF-8(무 BOM)·CRLF입니다. ASCII로 가상환경 Python을 정한 뒤 `chcp 65001`을 켜고 `.py` 경로를 호출합니다.
- 검색 시험 메뉴는 [`rag/test-search.sh`](../rag/test-search.sh)입니다. [CASE-054](../docs/cases/사례-054-환경준비-스크립트와-리눅스-실행기-2026-11-06.md)

```powershell
.\.venv\Scripts\python.exe scripts\run\embed_sentence.py 나무가 쓰러짐
.\.venv\Scripts\python.exe scripts\run\embed_sentence.py --raw 나무가 쓰러짐
```
