#!/usr/bin/env bash
# Linux counterpart of 웹-시작.cmd. Starts Flask on :5000; the UI default is /#/lab.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source "$ROOT/scripts/네이티브_환경.sh"
if [[ -x "$ROOT/.venv-web/bin/python" ]]; then
  PYTHON="$ROOT/.venv-web/bin/python"
elif [[ -x "$ROOT/.venv-web/Scripts/python.exe" ]]; then
  PYTHON="$ROOT/.venv-web/Scripts/python.exe"
else
  printf '%s\n' 'Missing .venv-web. Run ./setup.sh (Linux) or setup.cmd (Windows).' >&2
  exit 1
fi
exec "$PYTHON" -m src
