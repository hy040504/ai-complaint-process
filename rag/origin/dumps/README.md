# 검색 DB 덤프

이 폴더는 PostgreSQL `complaint_rag` 스키마의 논리 백업을 둡니다. SQL 스키마 파일과 달리 **FAQ·사례·벡터·BM25가 들어 있습니다.**

기본 파일 이름: `complaint_rag.dump`

## 만드는 방법 (자료가 있는 우분투)

저장소 루트에서:

```bash
source scripts/native-env.sh
scripts/export-rag-dump.sh
```

프로젝트 폴더를 다른 컴퓨터로 복사할 때 이 dump 파일을 함께 가져갑니다. Git에는 넣지 않습니다.

## 다른 컴퓨터에서 쓰는 방법

PostgreSQL 18과 pgvector를 설치한 뒤:

```bash
scripts/setup-native-db.sh
source scripts/native-env.sh
scripts/restore-rag-dump.sh
```

dump가 없으면 스키마만 만들고, 원본 JSON으로 다시 임베딩하려면 `.venv/bin/python -m rag ingest`를 실행합니다. 검색 API는 질의 벡터를 위해 모델 캐시도 필요합니다.

## 원본 JSON과의 관계

| 파일 | 역할 |
| --- | --- |
| `rag/origin/자주_묻는_민원.json`, `rag/origin/공개_민원_사례.json` | Git에 있는 검색 원문 |
| `rag/origin/schema/complaint_rag.sql` | 빈 테이블 정의 |
| `rag/origin/dumps/complaint_rag.dump` | 적재가 끝난 검색 DB 복사본 |
