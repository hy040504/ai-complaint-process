#!/usr/bin/env bash
# English alias for 검색서비스_실행.sh
set -euo pipefail
exec "$(cd "$(dirname "$0")" && pwd)/검색서비스_실행.sh" "$@"
