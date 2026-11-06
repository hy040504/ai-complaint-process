#!/usr/bin/env bash
# Linux counterpart of 웹-시작.cmd. Starts the lab intake web (default :5010).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
if [[ -x "$ROOT/.venv-web/bin/python" ]]; then
  PYTHON="$ROOT/.venv-web/bin/python"
elif [[ -x "$ROOT/.venv-web/Scripts/python.exe" ]]; then
  PYTHON="$ROOT/.venv-web/Scripts/python.exe"
else
  printf '%s\n' 'Missing .venv-web. Run ./setup.sh (Linux) or setup.cmd (Windows).' >&2
  exit 1
fi
export LAB_WEB_PORT="${LAB_WEB_PORT:-5010}"
exec "$PYTHON" -m src.lab_web

