# 시연 웹 업무 DB

현재 시연 웹은 SQLite 파일이 아니라 PostgreSQL 스키마 `complaint_app`에 민원·답변을 저장합니다. 검색 색인 `complaint_rag`와 테이블을 섞지 않습니다. [스키마](../../src/complaints/schema/complaint_app.sql) · [서버 안내](../../src/README.md)

연결은 `COMPLAINT_DATABASE_URL` 또는 표준 `PG*` 환경변수입니다. 서버를 처음 띄우면 스키마와 테이블을 만듭니다. 시연 민원 24건은 `python -m flask --app src:create_app seed-demo`로 넣습니다.

이 폴더의 `complaints.sqlite3`는 이전 로컬 시연 잔여 파일일 수 있습니다. Git에 넣지 않으며, 새 서버가 자동으로 옮기지 않습니다.
