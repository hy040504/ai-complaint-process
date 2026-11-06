#!/usr/bin/env bash
# Linux counterpart of 문장-임베딩.cmd. Encodes one sentence and lists pgvector neighbors.
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
if [[ "$#" -eq 0 ]]; then
  printf '%s' 'Sentence to embed: '
  IFS= read -r SENTENCE
  exec "$PYTHON" "$ROOT/scripts/문장_임베딩.py" "$SENTENCE"
fi
exec "$PYTHON" "$ROOT/scripts/문장_임베딩.py" "$@"
