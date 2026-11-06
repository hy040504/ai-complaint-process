#!/usr/bin/env bash
# Linux counterpart of 검색-시작.cmd. Serves the search API on :8007.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source "$ROOT/scripts/네이티브_환경.sh"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
elif [[ -x "$ROOT/.venv/Scripts/python.exe" ]]; then
  PYTHON="$ROOT/.venv/Scripts/python.exe"
else
  printf '%s\n' 'Missing .venv. Run ./setup.sh (Linux) or setup.cmd (Windows).' >&2
  exit 1
fi
exec "$PYTHON" -m rag serve --host 127.0.0.1 --port 8007
