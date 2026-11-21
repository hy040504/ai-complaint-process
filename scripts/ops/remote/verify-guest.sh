#!/usr/bin/env bash
# 공개 주소(없으면 로컬 :5000)에서 비로그인 게스트 접수 흐름을 상태 코드로 검증하고, 만든 민원은 삭제합니다.
BASE=${1:-$(cat "$HOME/.config/cheongju/public-url.txt" 2>/dev/null)}
BASE=${BASE:-http://127.0.0.1:5000}
J='Content-Type: application/json'
H='X-Cheongju-Site: citizen'
JAR=$(mktemp); trap 'rm -f "$JAR"' EXIT
code() { curl -s -o /dev/null -w "%{http_code}" "$@"; }
echo "대상: ${BASE}"
echo "홈(비로그인)               : $(code "$BASE/")  (기대 200)"
echo "비로그인 접수 시도         : $(code -X POST "$BASE/api/v1/complaints" -H "$J" -H "$H" -H "Origin: $BASE" -d '{}')  (기대 401)"
START=$(curl -s -c "$JAR" -X POST "$BASE/api/v1/auth/guest" -H "$H" -H "Origin: $BASE")
echo "게스트 시작                : guest=$(echo "$START" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("guest"), d.get("authMode"))')  (기대 True guest)"
echo "담당자 사이트에서 게스트   : $(code -X POST "$BASE/api/v1/auth/guest" -H 'X-Cheongju-Site: staff' -H "Origin: $BASE")  (기대 403)"
CREATED=$(curl -s -b "$JAR" -c "$JAR" -X POST "$BASE/api/v1/complaints" -H "$J" -H "$H" -H "Origin: $BASE" \
  -d '{"title":"게스트 접수 검증(자동 삭제)","body":"공개 주소 검증용 게스트 민원입니다. 확인 후 바로 삭제합니다.","district":"서원구","category":"기타","visibility":"public"}')
CID=$(echo "$CREATED" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("id",""))')
VER=$(echo "$CREATED" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("version",1))')
VIS=$(echo "$CREATED" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("visibility",""))')
echo "게스트 민원 접수           : id=${CID:-실패} visibility=$VIS  (기대 private)"
echo "본인 조회                  : $(code -b "$JAR" "$BASE/api/v1/complaints/$CID" -H "$H")  (기대 200)"
OTHER=$(mktemp); curl -s -c "$OTHER" -X POST "$BASE/api/v1/auth/guest" -H "$H" -H "Origin: $BASE" >/dev/null
echo "다른 방문자 조회           : $(code -b "$OTHER" "$BASE/api/v1/complaints/$CID" -H "$H")  (기대 404)"
rm -f "$OTHER"
echo "게스트의 담당자 API        : $(code -b "$JAR" "$BASE/api/v1/staff/stats" -H "$H")  (기대 401 또는 403)"
echo "검증 민원 삭제             : $(code -b "$JAR" -X POST "$BASE/api/v1/complaints/$CID/delete" -H "$J" -H "$H" -H "Origin: $BASE" -d "{\"version\":$VER}")  (기대 204)"
