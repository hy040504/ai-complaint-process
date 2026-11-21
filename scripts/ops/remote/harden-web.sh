#!/usr/bin/env bash
# 서버의 민원 웹을 실사용 설정으로 맞춥니다(재실행해도 안전). 비밀번호 값은 화면에 출력하지 않습니다.
#   1) 시연 로그인 끄기(COMPLAINT_DEMO_LOGIN=0)를 담당 환경 파일에 기록하고 서비스에 연결
#   2) 시드 계정(citizen_01·staff_admin·staff_seowon·staff_heungdeok)의 기본 비밀번호를
#      무작위 값으로 바꿔 ~/.config/cheongju/accounts.txt(권한 600)에만 저장
#   --rotate 를 주면 이미 저장된 비밀번호도 새로 발급합니다.
set -e
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
ROOT=$HOME/ai-complaint-process
CONF=$HOME/.config/cheongju
ACCOUNTS=$CONF/accounts.txt
ENVFILE=$CONF/web.env
ROTATE=0
for arg in "$@"; do [ "$arg" = "--rotate" ] && ROTATE=1; done

mkdir -p "$CONF"
chmod 700 "$CONF"

# 1) 환경 파일과 서비스 연결
touch "$ENVFILE"
chmod 600 "$ENVFILE"
grep -q '^COMPLAINT_DEMO_LOGIN=' "$ENVFILE" || echo 'COMPLAINT_DEMO_LOGIN=0' >> "$ENVFILE"
UNIT=$HOME/.config/systemd/user/cheongju-web.service
if ! grep -q "EnvironmentFile=$ENVFILE" "$UNIT"; then
  sed -i "/^ExecStart=/i EnvironmentFile=$ENVFILE" "$UNIT"
fi
systemctl --user daemon-reload

# 2) 시드 계정 비밀번호 교체
cd "$ROOT"
PY=$ROOT/.venv-web/bin/python
export PGHOST=/var/run/postgresql PGPORT=5432 PGDATABASE=complaints_native PGUSER=$(id -un) PYTHONUTF8=1
if [ "$ROTATE" = "1" ] || [ ! -s "$ACCOUNTS" ]; then
  : > "$ACCOUNTS"
  chmod 600 "$ACCOUNTS"
  for login in staff_admin staff_seowon staff_heungdeok citizen_01; do
    pw=$($PY -c 'import secrets; print(secrets.token_urlsafe(18))')
    COMPLAINT_NEW_PASSWORD="$pw" "$PY" -m flask --app src:create_app reset-password --login-id "$login" >/dev/null
    printf '%s\t%s\n' "$login" "$pw" >> "$ACCOUNTS"
  done
  echo "시드 계정 비밀번호 4개를 새로 발급해 $ACCOUNTS 에 저장했습니다."
else
  echo "기존 $ACCOUNTS 를 유지합니다(새로 발급하려면 --rotate)."
fi
systemctl --user restart cheongju-web.service
sleep 12
systemctl --user is-active cheongju-web
curl -s -m 10 http://127.0.0.1:5000/api/v1/health
echo
