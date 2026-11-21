#!/usr/bin/env bash
# 사용자 서비스를 순서대로 재시작하고 헬스를 확인합니다(검색 → 민원 웹·검사기).
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
systemctl --user daemon-reload
systemctl --user restart cheongju-rag.service
for i in $(seq 1 40); do
  curl -sf -m 3 http://127.0.0.1:8007/health >/dev/null && break
  sleep 3
done
systemctl --user restart cheongju-web.service cheongju-lab.service
sleep 12
systemctl --user is-active cheongju-rag cheongju-web cheongju-lab
curl -s -m 10 http://127.0.0.1:5000/api/v1/health
echo
curl -s -o /dev/null -w "citizen / %{http_code}\n" http://127.0.0.1:5000/
curl -s -o /dev/null -w "staff /staff/ %{http_code}\n" http://127.0.0.1:5000/staff/
