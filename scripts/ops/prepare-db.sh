#!/usr/bin/env bash
# 관리자 권한으로 현재 OS 계정의 DB와 확장을 준비합니다. 기존 DB는 삭제하지 않습니다.
set -euo pipefail
source "$(dirname "$0")/native-env.sh"
if [[ "$PGHOST" != /var/run/postgresql || "$PGUSER" != "$(id -un)" ]]; then
  printf '%s\n' '초기 준비는 현재 OS 계정과 로컬 PostgreSQL 소켓을 사용해야 합니다.' >&2
  exit 1
fi
sudo -u postgres psql -X -v ON_ERROR_STOP=1 -v owner="$PGUSER" -v db="$PGDATABASE" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN CREATEDB', :'owner')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'owner') \gexec
SELECT format('CREATE DATABASE %I OWNER %I', :'db', :'owner')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db') \gexec
SELECT 'CREATE DATABASE complaint_rag_test_template'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'complaint_rag_test_template') \gexec
SQL
sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d "$PGDATABASE" -c 'CREATE EXTENSION IF NOT EXISTS vector'
sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d complaint_rag_test_template -c 'CREATE EXTENSION IF NOT EXISTS vector'
sudo -u postgres psql -X -v ON_ERROR_STOP=1 -c 'ALTER DATABASE complaint_rag_test_template IS_TEMPLATE true'
