# 업무 DB 샘플·스키마 참고본 (`rag/db/`)

[프로젝트 소개](../../README.md) · [문서 목차](../../docs/README.md) · [데이터 계약](../../docs/harness/data-contracts.md) · [서버 안내](../../src/README.md)

이 폴더는 **민원 업무 DB(`complaint_app`)의 초기 설계 참고본과 샘플 데이터**입니다. 검색 자료(`rag/origin/`)와 같은 폴더에 모아 두었지만 **검색 색인(`complaint_rag`)과는 별개**입니다. 실행에 쓰는 기준 DDL·원본은 다른 위치에 있습니다.

| 알고 싶은 것 | 기준 위치 |
| --- | --- |
| FAQ·공개 사례 **원본 JSON**과 필드 설명(데이터 사전) | [`rag/origin/`](../origin/README.md) |
| 검색 스키마(`complaint_rag`) 실행용 DDL | [`rag/origin/schema/`](../origin/schema/complaint_rag.sql) |
| 업무 스키마(`complaint_app`) 실행용 DDL | [`src/complaints/schema/complaint_app.sql`](../../src/complaints/schema/complaint_app.sql) |

## 폴더 구성

```text
rag/db/
├─ sql/        초기 설계 당시의 DDL 복사본 (01_complaint_rag.sql · 02_complaint_app.sql)
├─ samples/    complaint_app 8개 테이블용 샘플 JSON (users · complaints · messages …)
├─ docs/       DB 스키마·샘플 JSON 설명 통합본
└─ load_samples.py   samples/*.json을 complaint_app에 적재·검증하는 스크립트
```

- FAQ·공개 사례 JSON(`자주_묻는_민원.json`, `공개_민원_사례.json`)은 `rag/origin/`과 **내용이 같아** 이 폴더에서 제거했습니다. 원본은 `rag/origin/`이 유일한 위치입니다.
- `sql/`은 설계 기록입니다. 실제 서버가 쓰는 DDL은 위 표의 기준 위치를 따릅니다.

## 샘플 적재

```bash
# 저장소 루트에서. 환경 변수(PGHOST·PGDATABASE 등)는 서버 안내를 따릅니다.
.venv-web/bin/python rag/db/load_samples.py --create     # 테이블 생성 후 적재 (rag/db/sql/02_complaint_app.sql)
.venv-web/bin/python rag/db/load_samples.py --reset      # 비우고 다시 적재
```

기본 입력 폴더는 `rag/db/samples`, 기본 SQL은 `rag/db/sql/02_complaint_app.sql`입니다(`--json-dir`·`--sql`로 변경).
