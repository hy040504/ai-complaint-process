#!/usr/bin/env bash
# Python 3.12 가상환경과 CPU용 검색 의존성을 설치합니다.
set -euo pipefail
cd "$(dirname "$0")/.."
python3.12 -m venv .venv
.venv/bin/python -m pip install torch==2.9.1 --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install -r rag/requirements.txt
