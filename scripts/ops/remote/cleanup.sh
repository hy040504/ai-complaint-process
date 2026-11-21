#!/usr/bin/env bash
# 서버에서 이전 배포 목록의 파일만 지웁니다. 가상환경·캐시·업로드·.env는 목록에 없어 보존됩니다.
set -e
D=__DIR__
mkdir -p "$D"
cd "$D"
if [ -f .deploy-manifest ]; then
  while IFS= read -r f; do
    if [ -n "$f" ]; then rm -f -- "$f"; fi
  done < .deploy-manifest
  find . -type d -empty -not -path './.venv*' -not -path './.rag-*' -not -path './.web-data*' -not -path './.git*' -delete 2>/dev/null || true
fi
echo ready
