# 스키마 파일 위치

이 폴더의 SQL은 `db/` 아래로 옮겼습니다.

| 이전 파일 | 현재 위치 |
| --- | --- |
| `01_complaint_rag.sql` | [db/schema/complaint_rag.sql](../../db/schema/complaint_rag.sql) |
| `02_complaint_app.sql` | [db/schema/complaint_app.sql](../../db/schema/complaint_app.sql) |
| 테이블 설명 PDF | [db/schema/DB01_테이블_설명.pdf](../../db/schema/DB01_테이블_설명.pdf) |
| 스키마 설명 | [db/README.md](../../db/README.md) |

검색 원문 JSON은 `db/자주_묻는_민원.json`, `db/공개_민원_사례.json`입니다. 벡터가 들어 있는 PostgreSQL 복사본은 `db/dumps/complaint_rag.dump`이며, 우분투에서 `scripts/export-rag-dump.sh`로 만듭니다.
