#!/usr/bin/env bash
# 네이티브 환경에서 검색 API를 실행합니다.
set -euo pipefail
source "$(dirname "$0")/네이티브_환경.sh"
cd "$RAG_ROOT"
exec "$RAG_ROOT/.venv/bin/python" -m rag serve --host 127.0.0.1 --port 8007
