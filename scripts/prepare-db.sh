#!/usr/bin/env bash
# English alias for 검색DB_준비.sh
set -euo pipefail
exec "$(cd "$(dirname "$0")" && pwd)/검색DB_준비.sh" "$@"
