#!/usr/bin/env bash
# 현재 계정에 검색 API 사용자 서비스를 설치합니다.
set -euo pipefail
RAG_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ "$RAG_ROOT" =~ [[:space:]] ]]; then
  printf '%s\n' '공백이 없는 경로에서 서비스 설치를 진행해 주세요.' >&2
  exit 1
fi
mkdir -p "$HOME/.config/systemd/user"
cat > "$HOME/.config/systemd/user/cheongju-rag.service" <<UNIT
[Unit]
Description=청주 민원 근거 검색 API
After=network-online.target

[Service]
Type=simple
WorkingDirectory=$RAG_ROOT
ExecStart=$RAG_ROOT/scripts/native-serve.sh
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
UNIT
systemctl --user daemon-reload
systemctl --user enable --now cheongju-rag.service
