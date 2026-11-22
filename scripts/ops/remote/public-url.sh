#!/usr/bin/env bash
# 현재 외부 공개 주소와 터널 서비스 상태를 보여 줍니다(서비스를 재시작하면 주소가 바뀝니다).
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
if systemctl --user is-active --quiet cheongju-domain-tunnel.service; then
  echo "터널 서비스: active (이름 있는 터널, 고정 도메인)"
  echo "공개 주소  : $(cat "$HOME/.config/cheongju/public-url.txt" 2>/dev/null)"
  exit 0
fi
STATE=$(systemctl --user is-active cheongju-tunnel.service)
URL_NOW=$(journalctl --user -u cheongju-tunnel.service --no-pager 2>/dev/null | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1)
if [ -n "$URL_NOW" ]; then echo "$URL_NOW" > "$HOME/.config/cheongju/public-url.txt"; fi
echo "터널 서비스: $STATE"
echo "공개 주소  : ${URL_NOW:-없음}"
