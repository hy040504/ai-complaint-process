# 데이터 경로 안내

2026-11-05부터 검색 원본 JSON·검색 스키마·벡터 dump는 [`rag/origin/`](../rag/origin/README.md)에 둡니다. 시연 웹 업무 스키마는 [`src/complaints/schema/complaint_app.sql`](../src/complaints/schema/complaint_app.sql)입니다. [CASE-039](../docs/cases/사례-039-검색코퍼스와-업무스키마-배치-2026-11-05.md)

이 폴더의 [`app/`](app/README.md)은 이전 시연 SQLite 잔여 경로입니다. Git에 넣지 않으며 새 서버가 자동으로 옮기지 않습니다.

| 현재 위치 | 내용 |
| --- | --- |
| [`rag/origin/자주_묻는_민원.json`](../rag/origin/자주_묻는_민원.json) | FAQ 원문 |
| [`rag/origin/공개_민원_사례.json`](../rag/origin/공개_민원_사례.json) | 공개 사례 원문 |
| [`rag/origin/schema/complaint_rag.sql`](../rag/origin/schema/complaint_rag.sql) | 검색 DDL |
| [`rag/origin/dumps/`](../rag/origin/dumps/README.md) | 검색 벡터 dump |
| [`src/complaints/schema/complaint_app.sql`](../src/complaints/schema/complaint_app.sql) | 시연 웹 업무 DDL |
