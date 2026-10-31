#!/usr/bin/env bash
# 저장소 루트에서 source로 불러 네이티브 DB와 모델 캐시를 지정합니다.
RAG_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export RAG_DB_DIR="${RAG_DB_DIR:-$RAG_ROOT/db}"
export PGHOST="${PGHOST:-/var/run/postgresql}"
export PGPORT="${PGPORT:-5432}"
export PGDATABASE="${PGDATABASE:-complaints_native}"
export PGUSER="${PGUSER:-$(id -un)}"
export HF_HOME="${HF_HOME:-$RAG_ROOT/.rag-cache/huggingface}"
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_XET=1 TOKENIZERS_PARALLELISM=false
export RAG_DEVICE=cpu RAG_THREADS="${RAG_THREADS:-12}" RAG_BATCH_SIZE="${RAG_BATCH_SIZE:-8}"
