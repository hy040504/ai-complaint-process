#!/usr/bin/env bash
# 현재 PostgreSQL의 complaint_rag 스키마를 rag/origin/dumps 로 내보냅니다.
set -euo pipefail
source "$(dirname "$0")/native-env.sh"
DUMP_DIR="$RAG_ROOT/rag/origin/dumps"
DUMP_FILE="$DUMP_DIR/complaint_rag.dump"
mkdir -p "$DUMP_DIR"
umask 077
pg_dump -Fc -n complaint_rag -f "$DUMP_FILE"
pg_restore --list "$DUMP_FILE" > "$DUMP_DIR/complaint_rag.list"
printf '%s\n' "검색 스키마 덤프: $DUMP_FILE"
