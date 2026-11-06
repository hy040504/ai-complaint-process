#!/usr/bin/env bash
# Prepare Ubuntu native Python venvs, PostgreSQL/pgvector, and the embedding model.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

uname_s="$(uname -s 2>/dev/null || true)"
case "$uname_s" in
  MINGW*|MSYS*|CYGWIN*)
    printf '%s\n' 'setup.sh is for Linux. On Windows run setup.cmd' >&2
    exit 1
    ;;
esac

if [[ "$(id -u)" -eq 0 ]]; then
  printf '%s\n' 'Run setup.sh as a regular user. The script calls sudo only for apt and DB prep.' >&2
  exit 1
fi

check_only=0
skip_db=0
for arg in "$@"; do
  case "$arg" in
    --check) check_only=1 ;;
    --skip-db) skip_db=1 ;;
  esac
done

if ! command -v python3.12 >/dev/null 2>&1; then
  printf '%s\n' 'python3.12 is required. Install it before running setup.sh.' >&2
  exit 1
fi

need_apt=0
if [[ "$skip_db" -eq 0 ]] && ! command -v psql >/dev/null 2>&1; then
  need_apt=1
fi
if ! python3.12 -c 'import venv, ensurepip' >/dev/null 2>&1; then
  need_apt=1
fi

if [[ "$check_only" -eq 0 && "$need_apt" -eq 1 ]]; then
  if [[ ! -r /etc/os-release ]] || ! grep -qiE 'debian|ubuntu' /etc/os-release; then
    printf '%s\n' 'Install PostgreSQL 18, postgresql-18-pgvector, and python3.12-venv, then re-run.' >&2
    exit 1
  fi
  sudo apt-get update
  sudo apt-get install -y python3.12-venv postgresql-18 postgresql-18-pgvector
fi

exec python3.12 "$ROOT/scripts/setup_env.py" "$@"
