#!/usr/bin/env bash
# 민원 웹(:5000)을 Cloudflare Quick Tunnel로 무료 외부 공개합니다(계정·도메인 불필요).
#   - cloudflared 를 GitHub 릴리스에서 받아 SHA-256 다이제스트와 대조한 뒤 ~/.local/bin 에 설치합니다.
#   - 사용자 서비스 cheongju-tunnel 로 등록합니다. 응대 검사기(:5010)는 공개하지 않습니다.
#   - 주소(https://무작위.trycloudflare.com)는 서비스를 재시작할 때마다 바뀝니다.
#   --upgrade 를 주면 cloudflared 를 다시 받습니다.
set -e
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
BIN=$HOME/.local/bin/cloudflared
CONF=$HOME/.config/cheongju
UNIT=$HOME/.config/systemd/user/cheongju-tunnel.service
mkdir -p "$HOME/.local/bin" "$CONF" "$(dirname "$UNIT")"

if [ ! -x "$BIN" ] || [ "$1" = "--upgrade" ]; then
  TMP=$(mktemp -d)
  trap 'rm -rf "$TMP"' EXIT
  curl -fsSL -m 30 https://api.github.com/repos/cloudflare/cloudflared/releases/latest -o "$TMP/rel.json"
  read -r URL DIGEST < <(python3 - "$TMP/rel.json" <<'PY'
import json, sys
rel = json.load(open(sys.argv[1]))
for asset in rel.get("assets", []):
    if asset["name"] == "cloudflared-linux-amd64":
        print(asset["browser_download_url"], (asset.get("digest") or "").replace("sha256:", ""))
        break
PY
)
  if [ -z "$URL" ] || [ -z "$DIGEST" ]; then echo "릴리스 URL 또는 SHA-256 다이제스트를 찾지 못했습니다. 설치를 중단합니다." >&2; exit 2; fi
  curl -fsSL -m 180 -o "$TMP/cloudflared" "$URL"
  ACTUAL=$(sha256sum "$TMP/cloudflared" | awk '{print $1}')
  if [ "$ACTUAL" != "$DIGEST" ]; then echo "SHA-256 불일치: 설치를 중단합니다." >&2; exit 3; fi
  install -m 755 "$TMP/cloudflared" "$BIN"
  echo "cloudflared 설치(SHA-256 검증 통과)"
fi
"$BIN" --version

cat > "$UNIT" <<UNIT_EOF
[Unit]
Description=청주 민원 웹 외부 공개 터널 (Cloudflare Quick Tunnel)
After=cheongju-web.service network-online.target

[Service]
Type=simple
ExecStart=$BIN tunnel --no-autoupdate --url http://127.0.0.1:5000
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
UNIT_EOF
systemctl --user daemon-reload
systemctl --user enable cheongju-tunnel.service >/dev/null 2>&1
systemctl --user restart cheongju-tunnel.service

for i in $(seq 1 30); do
  URL_NOW=$(journalctl --user -u cheongju-tunnel.service --since "-2min" --no-pager 2>/dev/null | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1)
  [ -n "$URL_NOW" ] && break
  sleep 2
done
if [ -z "$URL_NOW" ]; then echo "터널 주소를 얻지 못했습니다. journalctl --user -u cheongju-tunnel 을 확인하세요." >&2; exit 4; fi
echo "$URL_NOW" > "$CONF/public-url.txt"
echo "공개 주소: $URL_NOW"
