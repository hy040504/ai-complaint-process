#!/usr/bin/env bash
# db/dumps/complaint_rag.dump 를 현재 DB에 복원합니다. dump가 없으면 스키마만 적용합니다.
set -euo pipefail
source "$(dirname "$0")/native-env.sh"
DUMP_FILE="$RAG_ROOT/db/dumps/complaint_rag.dump"
RAG_SQL="$RAG_ROOT/db/schema/complaint_rag.sql"
if [[ -f "$DUMP_FILE" ]]; then
  pg_restore --no-owner --no-privileges --exit-on-error -d "$PGDATABASE" "$DUMP_FILE"
  printf '%s\n' "검색 자료 복원 완료: $DUMP_FILE"
  exit 0
fi
printf '%s\n' "dump가 없어 빈 검색 스키마만 적용합니다. 이후 python -m rag ingest 가 필요합니다."
psql -d "$PGDATABASE" -v ON_ERROR_STOP=1 -f "$RAG_SQL"
