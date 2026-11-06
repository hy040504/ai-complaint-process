# 실행 스크립트

[프로젝트 소개](../README.md) · [검색 실행](../rag/README.md) · [서버 안내](../src/README.md)

파일 이름은 한국어입니다. Python 모듈·가상환경·명령 식별자는 그대로 둡니다.

| 파일 | 역할 | 실행 환경 |
| --- | --- | --- |
| [`문장_임베딩.py`](문장_임베딩.py) | 한 문장의 임베딩 숫자. DB·검색 API·LLM 없음 | RAG `.venv` |
| [`민원_응대.py`](민원_응대.py) | 검색 API 위 RAG+LLM 응대 | `.venv-web` |
| [`검색_시작.py`](검색_시작.py) | Windows PostgreSQL·검색 API 기동 | `.venv-web`이 기동, 검색은 `.venv` |
| [`웹_시작.py`](웹_시작.py) | Flask 민원 웹 기동·시민 화면 | `.venv-web` |
| [`콘솔_기동.py`](콘솔_기동.py) | 새 콘솔·포트 확인 공유 모듈. 직접 실행하지 않음 | 표준 라이브러리 |
| [`외부_LLM_예제.py`](외부_LLM_예제.py) | 민원 RAG와 분리된 공개 LLM 호출 예제 | `PUBLIC_LLM_TOKEN` |
| [`네이티브_환경.sh`](네이티브_환경.sh) | 우분투 네이티브 PG·모델 캐시 환경 | `source` |
| [`검색파이썬_준비.sh`](검색파이썬_준비.sh) | `.venv`와 CPU 검색 의존성 | 우분투 |
| [`검색DB_준비.sh`](검색DB_준비.sh) | 로컬 PostgreSQL 계정·확장 | 우분투, sudo |
| [`검색스키마_적용.sh`](검색스키마_적용.sh) | `complaint_rag`·`complaint_app` DDL | 우분투 |
| [`검색덤프_내보내기.sh`](검색덤프_내보내기.sh) | `rag/origin/dumps/complaint_rag.dump` | 우분투 |
| [`검색덤프_복원.sh`](검색덤프_복원.sh) | dump 복원 또는 스키마만 적용 | 우분투 |
| [`검색서비스_실행.sh`](검색서비스_실행.sh) | `python -m rag serve` | 우분투 `.venv` |
| [`검색서비스_설치.sh`](검색서비스_설치.sh) | systemd 사용자 서비스 | 우분투 |

Windows 바로 가기는 저장소 루트의 [`문장-임베딩.cmd`](../문장-임베딩.cmd), [`민원-응대.cmd`](../민원-응대.cmd), [`검색-시작.cmd`](../검색-시작.cmd), [`웹-시작.cmd`](../웹-시작.cmd)입니다. CMD는 UTF-8(무 BOM)·CRLF입니다. ASCII로 가상환경 Python을 정한 뒤 `chcp 65001`을 켜고 한국어 `.py` 경로를 호출합니다. 검색 시험 메뉴는 [`rag/검색_시험.sh`](../rag/검색_시험.sh)입니다. 우분투 `.sh`는 이 Windows 호스트에서 `bash -n`을 실행하지 못했습니다.

```powershell
.\.venv\Scripts\python.exe scripts\문장_임베딩.py 나무가 쓰러짐
.\.venv\Scripts\python.exe scripts\문장_임베딩.py --raw 나무가 쓰러짐
```
