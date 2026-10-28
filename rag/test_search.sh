#!/usr/bin/env bash
# 검색 API를 시험하는 메뉴입니다. 서비스·원본·색인을 변경하지 않습니다.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../scripts/native-env.sh"
cd "$RAG_ROOT" || exit 1
RAG_PYTHON="$RAG_ROOT/.venv/bin/python"
[[ -x "$RAG_PYTHON" ]] || RAG_PYTHON=python3
RAG_RESULT="$(mktemp)" || exit 1
chmod 600 "$RAG_RESULT"
trap 'rm -f "$RAG_RESULT"' EXIT
RAG_HAS_RESULT=false
RAG_RERANK=false
RAG_DISTRICT=''
RAG_LIMIT=3
RAG_API_URL="${RAG_API_URL:-http://127.0.0.1:8007}"
C_ACCENT='' C_DIM='' C_RESET='' C_OK=''
if [[ -t 1 && "${TERM:-dumb}" != dumb && -z "${NO_COLOR+x}" ]]; then
  C_ACCENT=$'\033[1;36m' C_DIM=$'\033[2m' C_RESET=$'\033[0m' C_OK=$'\033[1;32m'
fi

# 인자 없이 실행하면 대화형 메뉴, 옵션을 주면 자동 점검용 명령을 실행합니다.
usage() {
  cat <<'HELP'
사용법: bash rag/test_search.sh
        bash rag/test_search.sh --status
        bash rag/test_search.sh --search '민원 내용' [검색 옵션]
검색 옵션: --collection faq|routing|both  --district 흥덕구
           --limit 1~20  --rerank  --no-rerank  --json
공통 옵션: --api-url http://127.0.0.1:8007  --help
기본값: 양쪽 검색 / 3건 / 재정렬 끔(빠른 검색). --json은 원본 JSON을 출력합니다.
HELP
}

# 마지막 성공 응답을 보관하고, 실패 시 이전 응답을 현재 결과처럼 표시하지 않습니다.
request() {
  RAG_HAS_RESULT=false
  if "$RAG_PYTHON" -m rag "$@" --api-url "$RAG_API_URL" > "$RAG_RESULT"; then
    RAG_HAS_RESULT=true
    if [[ "${RAG_RAW:-false}" == true ]]; then
      cat "$RAG_RESULT"
    else
      "$RAG_PYTHON" -m rag.terminal "$RAG_RESULT"
    fi
  else
    printf '%s\n' '요청에 실패했습니다. API 주소와 네이티브 검색 서비스 상태를 확인해 주세요.' >&2
    return 1
  fi
}

# 민원·필터를 배열로 전달해 입력 문자를 셸 명령으로 실행하지 않습니다.
search_query() {
  local query="$1" collection="$2"
  local args=(search "$query" --collection "$collection" --limit "$RAG_LIMIT")
  [[ -z "$RAG_DISTRICT" ]] || args+=(--district "$RAG_DISTRICT")
  [[ "$RAG_RERANK" == true ]] || args+=(--no-rerank)
  request "${args[@]}"
}

# 검색 대상과 질문을 입력받고 실제 API 검색을 수행합니다.
ask_query() {
  local query
  printf '\n민원 내용: '
  IFS= read -r query || return 1
  [[ -n "${query//[[:space:]]/}" ]] || { printf '%s\n' '민원 내용을 입력해 주세요.'; return 1; }
  printf '%s\n' '검색 중입니다. 재정렬을 켜면 시간이 더 걸릴 수 있습니다.'
  search_query "$query" "$1"
}

# 터미널 여부와 무관하게 읽을 수 있는 메뉴를 표시합니다.
menu() {
  local choice value rerank_label
  while true; do
    rerank_label='끔 · 빠른 검색'
    [[ "$RAG_RERANK" == false ]] || rerank_label='켬 · 정밀 재정렬'
    printf '\n%s╭────────────────────────────────────────────────────╮%s\n' "$C_ACCENT" "$C_RESET"
    printf '%s│       청주 민원 · RAG 검색 테스트 데스크            │%s\n' "$C_ACCENT" "$C_RESET"
    printf '%s╰────────────────────────────────────────────────────╯%s\n' "$C_ACCENT" "$C_RESET"
    printf '  API %s\n  재정렬 %s  |  관할 %s  |  결과 %s건\n' "$RAG_API_URL" "$rerank_label" "${RAG_DISTRICT:-전체}" "$RAG_LIMIT"
    printf '%s  검색 근거 확인용 · 자동 답변/이관 기능은 미구현%s\n\n' "$C_DIM" "$C_RESET"
    printf '  1  서비스·적재 상태       2  FAQ 안내 검색\n  3  부서 사례 검색         4  FAQ + 사례 검색\n  5  대형폐기물 예제        6  버스 무정차 예제\n  7  재정렬 켜기/끄기       8  관할 구 설정\n  9  결과 수 설정           j  마지막 원본 JSON\n  s  마지막 응답 저장       v  DB 무결성 대조\n  0  종료\n\n선택 › '
    IFS= read -r choice || break
    case "$choice" in
      1) request status ;;
      2) ask_query faq ;;
      3) ask_query routing ;;
      4) ask_query both ;;
      5) search_query '낡은 소파와 장롱을 버리려는데 대형폐기물 배출은 어떻게 하나요?' faq ;;
      6) search_query '711번 버스가 승객이 있는데도 정류장에 서지 않고 지나갔습니다. 운전자 교육과 시정을 요청합니다.' routing ;;
      7) if [[ "$RAG_RERANK" == true ]]; then RAG_RERANK=false; else RAG_RERANK=true; fi ;;
      8) printf '관할 구 (전체/상당구/서원구/흥덕구/청원구): '; IFS= read -r value || break
         case "$value" in 전체|'') RAG_DISTRICT='' ;; 상당구|서원구|흥덕구|청원구) RAG_DISTRICT="$value" ;; *) printf '%s\n' '지원하는 구 이름을 입력해 주세요.' ;; esac ;;
      9) printf '결과 수 (1~20): '; IFS= read -r value || break
         if [[ "$value" =~ ^([1-9]|1[0-9]|20)$ ]]; then RAG_LIMIT="$value"; else printf '%s\n' '1~20의 정수를 입력해 주세요.'; fi ;;
      j) if [[ "$RAG_HAS_RESULT" == true ]]; then "$RAG_PYTHON" -m rag.terminal "$RAG_RESULT" --raw; else printf '%s\n' '성공한 응답이 없습니다.'; fi ;;
      s) if [[ "$RAG_HAS_RESULT" == true ]]; then
           mkdir -p .rag-cache/reports
           value="$(mktemp "$RAG_ROOT/.rag-cache/reports/tui-XXXXXXXX.json")" || continue
           chmod 600 "$value"; cp "$RAG_RESULT" "$value"
           printf '%s저장:%s %s\n' "$C_OK" "$C_RESET" "$value"
         else printf '%s\n' '저장할 성공 응답이 없습니다.'; fi ;;
      v) "$RAG_PYTHON" -m rag.verify ;;
      0|q|Q) break ;;
      *) printf '%s\n' '메뉴의 번호나 문자를 입력해 주세요.' ;;
    esac
  done
}

if (( $# == 0 )); then
  menu
  exit 0
fi
RAG_ACTION='' RAG_QUERY='' RAG_COLLECTION=both RAG_RAW=false
while (( $# )); do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --status) RAG_ACTION=status; shift ;;
    --search|--collection|--district|--limit|--api-url)
      (( $# >= 2 )) || { usage >&2; exit 2; }
      case "$1" in
        --search) RAG_ACTION=search; RAG_QUERY="$2" ;;
        --collection) RAG_COLLECTION="$2" ;;
        --district) RAG_DISTRICT="$2" ;;
        --limit) RAG_LIMIT="$2" ;;
        --api-url) RAG_API_URL="$2" ;;
      esac
      shift 2 ;;
    --rerank) RAG_RERANK=true; shift ;;
    --no-rerank) RAG_RERANK=false; shift ;;
    --json) RAG_RAW=true; shift ;;
    *) usage >&2; exit 2 ;;
  esac
done
case "$RAG_ACTION" in
  status) request status ;;
  search) search_query "$RAG_QUERY" "$RAG_COLLECTION" ;;
  *) usage >&2; exit 2 ;;
esac
