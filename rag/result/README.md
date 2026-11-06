# 스키마 파일 위치

이 폴더의 SQL은 검색 원본 폴더와 민원 웹 패키지로 옮겼습니다.

| 이전 파일 | 현재 위치 |
| --- | --- |
| `01_complaint_rag.sql` | [rag/origin/schema/complaint_rag.sql](../origin/schema/complaint_rag.sql) |
| `02_complaint_app.sql` | [src/complaints/schema/complaint_app.sql](../../src/complaints/schema/complaint_app.sql) |
| 테이블 설명 PDF | [rag/origin/schema/DB01_테이블_설명.pdf](../origin/schema/DB01_테이블_설명.pdf) |
| 스키마 설명 | [데이터 사전](../origin/README.md) |

검색 원문 JSON은 `rag/origin/자주_묻는_민원.json`, `rag/origin/공개_민원_사례.json`입니다. 벡터가 들어 있는 PostgreSQL 복사본은 `rag/origin/dumps/complaint_rag.dump`이며, 우분투에서 `scripts/검색덤프_내보내기.sh`로 만듭니다.
