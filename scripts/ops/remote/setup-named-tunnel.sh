#!/usr/bin/env bash
# 민원 웹(:5000)을 Cloudflare 이름 있는 터널(고정 도메인)로 공개합니다.
#   사용법: bash setup-named-tunnel.sh <공개 호스트 이름>
#   - 터널 실행 토큰은 ~/.config/cheongju/tunnel.env 의 TUNNEL_TOKEN=... 한 줄(권한 600)에서만 읽습니다.
#     토큰을 저장소·명령행·로그에 남기지 않습니다. 터널·DNS·입구 규칙은 Cloudflare 쪽에서 미리 만들어 둡니다.
#   - 사용자 서비스 cheongju-domain-tunnel 로 등록하고, 임시 터널(cheongju-tunnel)은 중지·해제합니다.
#   - cloudflared 는 setup-tunnel.sh 가 ~/.local/bin 에 설치한 것을 씁니다(없으면 먼저 setup-tunnel.sh 실행).
set -e
HOST=${1:?공개 호스트 이름(예: cheongju.mib.dpdns.org)을 인자로 주세요}
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
BIN=$HOME/.local/bin/cloudflared
CONF=$HOME/.config/cheongju
ENVF=$CONF/tunnel.env
UNIT=$HOME/.config/systemd/user/cheongju-domain-tunnel.service

[ -x "$BIN" ] || { echo "cloudflared 가 없습니다. 먼저 setup-tunnel.sh 를 실행하세요." >&2; exit 2; }
[ -s "$ENVF" ] || { echo "$ENVF 가 없습니다(TUNNEL_TOKEN=... 한 줄)." >&2; exit 2; }
chmod 600 "$ENVF"
grep -q '^TUNNEL_TOKEN=' "$ENVF" || { echo "$ENVF 에 TUNNEL_TOKEN 이 없습니다." >&2; exit 2; }

cat > "$UNIT" <<UNIT_EOF
[Unit]
Description=청주 민원 웹 외부 공개 터널 (Cloudflare 이름 있는 터널)
After=cheongju-web.service network-online.target

[Service]
Type=simple
EnvironmentFile=$ENVF
ExecStart=$BIN tunnel --no-autoupdate run
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
UNIT_EOF
systemctl --user daemon-reload
systemctl --user enable cheongju-domain-tunnel.service >/dev/null 2>&1
systemctl --user restart cheongju-domain-tunnel.service

# 임시 터널은 같은 주소를 두 곳에서 열 필요가 없으므로 중지합니다(공개 주소가 바뀌는 문제 제거).
systemctl --user disable --now cheongju-tunnel.service >/dev/null 2>&1 || true

for i in $(seq 1 20); do
  CODE=$(curl -s -o /dev/null -m 8 -w '%{http_code}' "https://$HOST/" || true)
  [ "$CODE" = "200" ] && break
  sleep 3
done
echo "https://$HOST" > "$CONF/public-url.txt"
echo "터널 서비스: $(systemctl --user is-active cheongju-domain-tunnel.service)"
echo "공개 주소  : https://$HOST  (응답 $CODE)"
