# 데이터 경로 안내

검색 원본 JSON·검색 스키마·벡터 dump는 [`rag/origin/`](../rag/origin/README.md)에 둡니다. 시연 웹 업무 스키마는 [`src/complaints/schema/complaint_app.sql`](../src/complaints/schema/complaint_app.sql)입니다. [CASE-039](../docs/cases/사례-039-검색코퍼스와-업무스키마-배치-2026-11-05.md) · [CASE-041](../docs/cases/사례-041-잔여-SQLite-삭제-2026-11-05.md)

이전 시연 SQLite(`db/app/complaints.sqlite3`, `.web-data/*.sqlite3`)는 삭제했습니다. 시연 민원은 PostgreSQL `complaint_app`에 두고, 데모 글은 `python -m flask --app src:create_app seed-demo`로 넣습니다.

| 현재 위치 | 내용 |
| --- | --- |
| [`rag/origin/자주_묻는_민원.json`](../rag/origin/자주_묻는_민원.json) | FAQ 원문 |
| [`rag/origin/공개_민원_사례.json`](../rag/origin/공개_민원_사례.json) | 공개 사례 원문 |
| [`rag/origin/schema/complaint_rag.sql`](../rag/origin/schema/complaint_rag.sql) | 검색 DDL |
| [`rag/origin/dumps/`](../rag/origin/dumps/README.md) | 검색 벡터 dump |
| [`src/complaints/schema/complaint_app.sql`](../src/complaints/schema/complaint_app.sql) | 시연 웹 업무 DDL |
