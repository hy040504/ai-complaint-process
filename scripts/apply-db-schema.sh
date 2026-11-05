#!/usr/bin/env bash
# db/schema SQL로 검색·업무 PostgreSQL 스키마를 적용합니다. 행 데이터는 넣지 않습니다.
set -euo pipefail
source "$(dirname "$0")/native-env.sh"
RAG_SQL="$RAG_ROOT/db/schema/complaint_rag.sql"
APP_SQL="$RAG_ROOT/db/schema/complaint_app.sql"
if [[ ! -f "$RAG_SQL" || ! -f "$APP_SQL" ]]; then
  printf '%s\n' "db/schema SQL 파일이 없습니다." >&2
  exit 1
fi
python3 - <<'PY' | psql -d "$PGDATABASE" -v ON_ERROR_STOP=1
import os
import sys
sys.path.insert(0, os.environ["RAG_ROOT"])
from rag.config import schema_sql
print(schema_sql())
PY
psql -d "$PGDATABASE" -v ON_ERROR_STOP=1 -f "$APP_SQL"
printf '%s\n' "스키마 적용 완료: $PGDATABASE"
