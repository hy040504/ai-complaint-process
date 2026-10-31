# 시연 웹 업무 DB

기본 파일: `complaints.sqlite3`

Flask 서버가 민원·답변을 여기에 저장합니다. RAG JSON·PostgreSQL 검색 자료와 섞이지 않습니다. Git에는 넣지 않으며, 서버를 처음 실행하면 파일이 생깁니다. 시연 민원 24건은 `python -m flask --app src:create_app seed-demo`로 넣습니다.
