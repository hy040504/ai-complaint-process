#!/usr/bin/env bash
# 서버에서 사이트 분리·로그인 경계를 상태 코드로만 검증합니다(비밀번호 값은 출력하지 않습니다).
BASE=http://127.0.0.1:5000
ACCOUNTS=$HOME/.config/cheongju/accounts.txt
pw() { awk -F'\t' -v u="$1" '$1==u{print $2}' "$ACCOUNTS"; }
code() { curl -s -o /dev/null -w "%{http_code}" "$@"; }
J='Content-Type: application/json'
JAR=$(mktemp)
trap 'rm -f "$JAR"' EXIT

echo "시연 로그인(/session)      : $(code -X POST $BASE/api/v1/session -H "$J" -H 'X-Cheongju-Site: staff' -d '{"role":"staff"}')  (기대 403)"
echo "기본 비밀번호(staff_admin) : $(code -X POST $BASE/api/v1/auth/login -H "$J" -H 'X-Cheongju-Site: staff' -d '{"loginId":"staff_admin","password":"cheongju-staff-2026!"}')  (기대 401)"
echo "기본 비밀번호(citizen_01)  : $(code -X POST $BASE/api/v1/auth/login -H "$J" -H 'X-Cheongju-Site: citizen' -d '{"loginId":"citizen_01","password":"cheongju-citizen-2026!"}')  (기대 401)"
S=$(pw staff_admin)
C=$(pw citizen_01)
echo "담당자 로그인(담당자 사이트): $(code -c "$JAR" -X POST $BASE/api/v1/auth/login -H "$J" -H 'X-Cheongju-Site: staff' -d "{\"loginId\":\"staff_admin\",\"password\":\"$S\"}")  (기대 200)"
echo "담당자 계정을 시민 사이트로 : $(code -X POST $BASE/api/v1/auth/login -H "$J" -H 'X-Cheongju-Site: citizen' -d "{\"loginId\":\"staff_admin\",\"password\":\"$S\"}")  (기대 403)"
echo "민원인 계정을 담당자 사이트 : $(code -X POST $BASE/api/v1/auth/login -H "$J" -H 'X-Cheongju-Site: staff' -d "{\"loginId\":\"citizen_01\",\"password\":\"$C\"}")  (기대 403)"
echo "민원인 로그인(시민 사이트)  : $(code -b "$JAR" -c "$JAR" -X POST $BASE/api/v1/auth/login -H "$J" -H 'X-Cheongju-Site: citizen' -d "{\"loginId\":\"citizen_01\",\"password\":\"$C\"}")  (기대 200)"
echo "쿠키 이름                  : $(awk '$6 ~ /^cj_/ {print $6}' "$JAR" | sort | tr '\n' ' ')  (기대 cj_citizen cj_staff)"
echo "담당자 통계(담당자 쿠키)    : $(code -b "$JAR" $BASE/api/v1/staff/stats -H 'X-Cheongju-Site: staff')  (기대 200)"
echo "담당자 통계(시민 헤더)      : $(code -b "$JAR" $BASE/api/v1/staff/complaints/export.csv -H 'X-Cheongju-Site: citizen')  (기대 401 또는 403)"
echo "시민 화면 /                : $(code $BASE/)  담당자 화면 /staff/ : $(code $BASE/staff/)"
