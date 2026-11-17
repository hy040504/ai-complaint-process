"""네이버 지도 웹 인스턴트 검색을 이용한 장소 주소 추적 도구입니다.

네이버 로그인 세션이나 별도 유료 API 키 없이, 네이버 지도의 공개
인스턴트 검색 엔드포인트를 호출하여 특정 장소(건물, 학교, 시설명 등)의
도로명·지번 주소와 청주시 관할 자치구(상당구·서원구·흥덕구·청원구) 및
행정/법정동을 조회합니다.
"""

from __future__ import annotations

from collections.abc import Callable
import json
import re
import sys
import urllib.parse
import urllib.request
from typing import Any

PLACE_TOOL_NAME = "lookup_navermap_place"
CHEONGJU_COORDS = "36.6424341,127.4890319"
CHEONGJU_DISTRICTS = ("상당구", "서원구", "흥덕구", "청원구")
NAVER_MAP_INSTANT_SEARCH_URL = "https://map.naver.com/p/api/search/instant-search"

PLACE_TOOL_USAGE = (
    "lookup_navermap_place는 민원 본문에 언급된 장소명(예: 건물, 학교, "
    "공원, 시장, 교차로 등)으로 실제 주소와 청주시 관할 구(상당구·서원구·흥덕구·청원구) "
    "및 동을 추적하는 도구입니다. 네이버 지도 웹 검색을 활용하며 로그인 없이 동작합니다."
)

# 동일 세션 내 반복 호출을 방지하기 위한 인메모리 캐시 (최대 256건)
_PLACE_CACHE: dict[str, dict[str, Any]] = {}
_MAX_CACHE_SIZE = 256

_TAG_RE = re.compile(r"<[^>]+>")
_GU_RE = re.compile(r"(상당구|서원구|흥덕구|청원구)")
_DONG_RE = re.compile(r"([가-힣\d]+(?:동|읍|면|가))\b")

_STOP_SUFFIXES: tuple[str, ...] = (
    "근처에서", "근처에", "근처", "부근에서", "부근에", "부근",
    "주변에서", "주변에", "주변", "인근에서", "인근에", "인근",
    "맞은편에서", "맞은편에", "맞은편", "건너편에서", "건너편에", "건너편",
    "앞쪽에서", "앞쪽에", "앞쪽", "앞에서", "앞에", "에서", "으로", "에는", "에", "이", "가",
    "을", "를", "은", "는", "도", "쪽", "방면",
)

# 서술어·종결어미로 끝나는 어절은 어간만 잘라 장소를 찾으면('궁금합니다'→'궁금'→'궁금해아트')
# 엉뚱한 상호를 검색하게 되므로 후보에서 통째로 제외합니다.
_PREDICATE_SUFFIXES: tuple[str, ...] = (
    "겠습니다", "었습니다", "았습니다", "했습니다", "하겠습니다", "되었습니다",
    "합니다", "됩니다", "입니다", "있습니다", "없습니다", "바랍니다", "드립니다",
    "습니다", "ㅂ니다", "해주세요", "알려주세요", "부탁합니다", "주십시오",
    "원합니다", "싶습니다", "궁금해", "하네요", "인가요", "되나요", "하나요",
    "할까요", "일까요", "있나요", "없나요", "거든요", "는데요", "어요", "아요", "네요",
)

_STOP_WORDS: frozenset[str] = frozenset({
    "청주", "청주시", "충북", "충청북도",
    "시내", "도로", "도로에", "골목", "차도", "인도", "보도", "보도블럭", "보도블록", "횡단보도",
    "신호등", "가로등", "가로등이", "가로수", "포트홀", "싱크홀",
    "나무가", "나무", "쓰러짐", "파손", "고장", "고장났어요", "수리", "공사", "발생", "소음", "악취", "냄새",
    "쓰레기", "폐기물", "대형폐기물", "종량제", "종량제봉투", "봉투", "불법주정차", "불법주차", "주정차",
    "단속", "신고", "요청", "문의", "질문", "부탁드립니다",
    "주세요", "알려주세요", "해결해주세요", "있어요", "있나요", "없나요", "안됩니다", "때문에", "어디",
    "공무원", "불친절", "안내", "답변", "처리", "확인", "점검", "안녕하세요", "감사합니다", "수고하십니다",
    "문제", "민원", "민원위치", "상태", "상황", "현장", "조치", "건의", "불편", "불편합니다", "사항", "위험해요",
    # FAQ·일반 행정 서술 및 보고서 3순위 식별 일반명사 오매칭 방지 불용어
    "지역", "접수", "공식", "신청", "신청서", "무료", "유료", "방문", "발급", "재발급", "등록",
    "방법", "대상", "조건", "기준", "규격", "기간", "처리기간", "수수료", "비용", "환불", "할인", "현금",
    "본인", "대리", "세대원", "전입신고", "미성년자", "미만", "이상", "여권", "자동차", "차량",
    "온라인", "인터넷", "사이트", "자동이체", "번호", "내선번호", "연락처", "전화", "과태료",
    "버스", "시내버스", "노선", "정기권", "동물", "사체", "로드킬", "신고처", "재난문자", "알림", "해지",
    "관련", "인한", "대한", "따른", "개선", "보수", "교체", "설치", "제거", "관리", "청소", "정비",
    "시간", "일원", "현재", "오늘", "최근", "어제", "계속", "자꾸", "너무", "정말", "진짜", "제발",
    "동네", "어딘가", "학교", "미기재", "부서", "부서명", "담당", "담당자", "시민", "주민",
    "편의점", "원룸", "원룸촌", "화장실", "공중화장실", "벤치", "볼라드", "맨홀", "배수로", "빗물받이",
    "면접", "정장", "대여", "준비", "서류", "구비서류", "여부", "가능", "존재하지", "않는",
    "청주페이", "qr코드", "QR코드", "가맹점", "결제", "지원사업", "자전거", "부과", "재교부", "현황",
    "배출", "수거", "궁금", "필요", "부탁", "알고",
    "무단", "불법", "투기", "무단투기", "무단배출", "적치", "침하", "누수", "막힘", "소등",
})

# 고유 장소·시설 접미어를 가진 후보는 5후보 컷오프 시 앞쪽 일반 조합보다 우선 정렬합니다.
_PLACE_PRIORITY_SUFFIXES: tuple[str, ...] = (
    "국제공항", "공항", "생태공원", "공원", "종합시장", "시장", "박물관", "기념관",
    "도서관", "미술관", "전망대", "행궁", "산성", "터미널", "역", "출구",
    "초등학교", "중학교", "고등학교", "대학교", "대학", "초교", "중교", "고교",
    "병원", "보건소", "행정복지센터", "주민센터", "구청", "시청", "법원", "우체국",
    "사거리", "오거리", "삼거리", "교차로", "네거리", "아파트", "휴게소", "캠핑장",
    "체육관", "백화점", "마트", "아울렛", "대교", "매표소", "호수", "정문", "후문", "중문",
)

# 긴 문장 보완 검색 시 과도한 외부 HTTP 호출을 막기 위한 후보 상한입니다.
_MAX_FALLBACK_CANDIDATES = 5

# 토큰 정제·장소명 대조에서 반복 호출되는 정규식을 모듈 로드 시 1회 컴파일합니다.
_CLEAN_PUNCT_RE = re.compile(r"[()\[\]{}<>\"'·~!,?]")
_NORM_TITLE_RE = re.compile(r"[\s\-_()\[\]]")
_ALPHA_HANGUL_RE = re.compile(r"[가-힣A-Za-z]")
_PLACE_COUNTER_RE = re.compile(
    r"^\d+(?:세|살|명|개|건|회|원|만원|천원|억|분|초|시간|일|주|개월|년|kg|km|cm|mm|%)$"
)


def _has_place_suffix(token: str) -> bool:
    """토큰이 구체적인 장소·시설 고유 접미어로 끝나는지 확인합니다.

    Args:
        token: 정제된 단일 단어 또는 2단어 조합 문자열입니다.

    Returns:
        고유 장소·시설 접미어가 포함되어 있으면 True입니다.
    """
    return any(token.endswith(suffix) for suffix in _PLACE_PRIORITY_SUFFIXES)


def _clean_query_tokens(text: str) -> list[str]:
    """문장에서 조사·문장부호·일반 불용어를 걸러 장소 비교용 핵심 토큰을 추출합니다.

    Args:
        text: 민원 원문 또는 검색어 문자열입니다.

    Returns:
        장소 관련성 판별과 후보 생성에 사용할 정제 단어 목록입니다.
    """
    cleaned = _CLEAN_PUNCT_RE.sub(" ", text)
    refined_words: list[str] = []
    for raw_word in cleaned.split():
        word = raw_word.strip(".,:;~/-")
        if (
            not word
            or word in _STOP_WORDS
            or word in _STOP_SUFFIXES
            or word.endswith(_PREDICATE_SUFFIXES)
        ):
            continue
        cur = word
        for suf in _STOP_SUFFIXES:
            if cur.endswith(suf) and len(cur) > len(suf):
                cur = cur[: -len(suf)].strip(".,:;~/-")
                break
        if (
            not cur
            or cur in _STOP_WORDS
            or cur in _STOP_SUFFIXES
            or len(cur) < 2
            or not _ALPHA_HANGUL_RE.search(cur)
            or _PLACE_COUNTER_RE.match(cur)
        ):
            continue
        refined_words.append(cur)
    return refined_words


def is_place_relevant(title: str, query: str) -> bool:
    """검색 결과의 장소 제목이 검색어 키워드와 실제 일치하는지 검증합니다.

    청주시에 위치한 무관한 식당이나 일반 상점이 우연히 검색되는 문제를
    방지하기 위해, 일반 행정 불용어를 제외한 핵심 키워드만 장소 제목과 대조합니다.

    Args:
        title: 네이버 지도 장소 제목입니다.
        query: 검색에 사용한 키워드입니다.

    Returns:
        핵심 키워드가 장소 제목에 유의미하게 포함되어 있으면 True입니다.
    """
    if not title or not query:
        return False
    norm_title = _NORM_TITLE_RE.sub("", title.lower())
    if not norm_title or len(norm_title) < 2:
        return False
    words = _clean_query_tokens(query)
    if not words:
        return False
    return any(
        w.lower() in norm_title
        or (
            norm_title not in _STOP_WORDS
            and (
                len(norm_title) >= 4
                or (len(norm_title) >= 3 and len(norm_title) >= len(w) * 0.6)
            )
            and norm_title in w.lower()
        )
        for w in words
    )


def extract_place_candidates(text: str) -> list[str]:
    """긴 문장이나 복합 민원에서 장소명 후보 키워드 목록을 추출합니다.

    '청주 서원대학교 후문 편의점근처에서 나무가 쓰러짐' 같은 문장에서
    조사·일반 불용어를 제거한 뒤 공항·공원·시장·역·병원 등 고유 장소 접미어
    후보를 최우선으로 배치해 5후보 절단 시에도 핵심 랜드마크가 남도록 구성합니다.

    Args:
        text: 민원 문장 또는 검색어입니다.

    Returns:
        우선순위가 높은 장소명 후보 문자열 목록입니다.
    """
    refined_words = _clean_query_tokens(text)
    if not refined_words:
        return []

    tier_combo_priority: list[str] = []
    tier_single_priority: list[str] = []
    tier_combo_general: list[str] = []
    tier_single_general: list[str] = []

    for i in range(len(refined_words) - 1):
        left, right = refined_words[i], refined_words[i + 1]
        combo = f"{left} {right}"
        if _has_place_suffix(left) or _has_place_suffix(right) or right.endswith("점"):
            tier_combo_priority.append(combo)
        else:
            tier_combo_general.append(combo)

    for w in refined_words:
        if _has_place_suffix(w):
            tier_single_priority.append(w)
        else:
            tier_single_general.append(w)

    return list(
        dict.fromkeys(
            [
                *tier_combo_priority,
                *tier_single_priority,
                *tier_combo_general,
                *tier_single_general,
            ]
        )
    )


def extract_cheongju_district(address: str | None) -> str | None:
    """주소 문자열에서 청주시 4개 구 이름을 추출합니다.

    Args:
        address: 도로명주소 또는 지번주소 문자열입니다.

    Returns:
        상당구, 서원구, 흥덕구, 청원구 중 일치하는 구 이름입니다. 없으면 None입니다.
    """
    if not address or not isinstance(address, str):
        return None
    match = _GU_RE.search(address)
    return match.group(1) if match else None


def extract_cheongju_dong(address: str | None) -> str | None:
    """주소 문자열에서 동, 읍, 면, 가 단위를 추출합니다.

    Args:
        address: 지번주소 또는 도로명주소 문자열입니다.

    Returns:
        추출된 동·읍·면 이름입니다. 없으면 None입니다.
    """
    if not address or not isinstance(address, str):
        return None
    match = _DONG_RE.search(address)
    return match.group(1) if match else None


def _clean_text(text: str | None) -> str:
    """문자열의 HTML 태그 및 불필요한 공백을 제거합니다.

    Args:
        text: 원본 문자열입니다.

    Returns:
        정리된 텍스트입니다.
    """
    if not text:
        return ""
    stripped = _TAG_RE.sub("", text)
    return " ".join(stripped.split())


def fetch_navermap_instant_search(
    query: str,
    coords: str = CHEONGJU_COORDS,
    timeout: float = 5.0,
) -> dict[str, Any]:
    """네이버 지도 웹 인스턴트 검색 API를 호출합니다.

    네이버 로그인 세션이 없는 비로그인 상태에서도 동작하도록 일반적인 브라우저
    헤더(User-Agent, Referer)를 전송합니다.

    Args:
        query: 장소 검색어입니다.
        coords: 기준 좌표 (위도,경도)입니다. 기본값은 청주시청입니다.
        timeout: HTTP 요청 타임아웃(초)입니다.

    Returns:
        네이버 지도 검색 응답 JSON 객체입니다.

    Raises:
        OSError: 네트워크 요청 실패 시 발생합니다.
        ValueError: 응답 본문이 올바른 JSON이 아닌 경우 발생합니다.
    """
    params = {
        "query": query,
        "coords": coords,
        "type": "all",
    }
    url = f"{NAVER_MAP_INSTANT_SEARCH_URL}?{urllib.parse.urlencode(params)}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://map.naver.com/",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as res:
        raw_body = res.read().decode("utf-8")
        parsed = json.loads(raw_body)
        if not isinstance(parsed, dict):
            raise ValueError("네이버 지도 응답이 JSON 객체 형식이 아닙니다.")
        return parsed


def lookup_navermap_place(
    query: str,
    coords: str | None = None,
    *,
    fetch_fn: Callable[..., dict[str, Any]] | None = None,
    _allow_fallback: bool = True,
) -> dict[str, Any]:
    """장소명으로 네이버 지도를 검색하고 청주시 주소 및 구/동 정보를 반환합니다.

    Args:
        query: 장소 검색어(예: 건물명, 학교명, 시장명 등)입니다.
        coords: 검색 중심 좌표입니다. 생략 시 청주시청 좌표를 사용합니다.
        fetch_fn: HTTP 호출을 대신할 검색 함수입니다. 테스트 시 주입합니다.
        _allow_fallback: 내부 재귀 호출 시 후보 분해 재검색을 막기 위한 플래그입니다.

    Returns:
        검색 결과 요약, 청주시 최우선 장소(primary_place), 전체 장소 목록을 담은 객체입니다.

    Raises:
        ValueError: 검색어가 비어 있는 경우 발생합니다.
    """
    text = " ".join(query.split())
    if not text:
        raise ValueError("장소 검색어가 비어 있습니다.")

    center_coords = (coords.strip() if coords and coords.strip() else CHEONGJU_COORDS)
    cache_key = f"{text}|{center_coords}"

    if fetch_fn is None and cache_key in _PLACE_CACHE:
        return _PLACE_CACHE[cache_key]

    # 일반 행정·FAQ 등 3어절 이상 문장에서 장소 후보가 전혀 없으면 불필요한 외부 검색을 건너뜁니다.
    fallback_candidates = extract_place_candidates(text) if _allow_fallback else []
    if _allow_fallback and len(text.split()) >= 3 and not fallback_candidates:
        return {
            "query": text,
            "coords": center_coords,
            "found": False,
            "total": 0,
            "primary_place": None,
            "places": [],
        }

    fetcher = fetch_fn or fetch_navermap_instant_search
    try:
        raw_data = fetcher(text, coords=center_coords)
    except Exception as exc:
        return {
            "query": text,
            "coords": center_coords,
            "found": False,
            "total": 0,
            "primary_place": None,
            "places": [],
            "error": f"네이버 지도 검색 중 오류가 발생했습니다: {exc}",
        }

    raw_places = raw_data.get("place")
    if not isinstance(raw_places, list):
        raw_places = []

    places: list[dict[str, Any]] = []
    cheongju_places: list[dict[str, Any]] = []

    for item in raw_places:
        if not isinstance(item, dict):
            continue
        title = _clean_text(item.get("title"))
        if not is_place_relevant(title, text):
            continue
        road_addr = _clean_text(item.get("roadAddress")) or None
        jibun_addr = _clean_text(item.get("jibunAddress")) or None
        ctg = _clean_text(item.get("ctg")) or None
        x = item.get("x")
        y = item.get("y")

        # 자치구 및 동 추출 (지번 주소 우선, 없으면 도로명 주소 참조)
        gu = extract_cheongju_district(jibun_addr) or extract_cheongju_district(road_addr)
        dong = extract_cheongju_dong(jibun_addr) or extract_cheongju_dong(road_addr)

        combined_addr = f"{road_addr or ''} {jibun_addr or ''}"
        is_cheongju = "청주" in combined_addr or gu is not None

        place_obj = {
            "title": title,
            "road_address": road_addr,
            "jibun_address": jibun_addr,
            "gu": gu,
            "dong": dong,
            "x": str(x) if x is not None else None,
            "y": str(y) if y is not None else None,
            "category": ctg,
            "is_cheongju": is_cheongju,
        }
        places.append(place_obj)
        if is_cheongju:
            cheongju_places.append(place_obj)

    # 청주시 장소가 있으면 청주시 최상위 결과를 primary_place로 선정
    primary = cheongju_places[0] if cheongju_places else (places[0] if places else None)

    # 청주시 장소를 찾지 못했거나 결과가 없으면 장소 후보 키워드로 1회만 보완 검색합니다.
    if _allow_fallback and (primary is None or not primary.get("is_cheongju")):
        for cand in fallback_candidates[:_MAX_FALLBACK_CANDIDATES]:
            if cand == text:
                continue
            cand_res = lookup_navermap_place(
                cand,
                coords=center_coords,
                fetch_fn=fetcher,
                _allow_fallback=False,
            )
            cand_primary = cand_res.get("primary_place")
            if cand_primary and cand_primary.get("is_cheongju"):
                primary = cand_primary
                places = cand_res.get("places", [])
                break

    result = {
        "query": text,
        "coords": center_coords,
        "found": bool(places),
        "total": len(places),
        "primary_place": primary,
        "places": places,
    }

    if fetch_fn is None and (_allow_fallback or (primary is not None and primary.get("is_cheongju"))):
        if len(_PLACE_CACHE) >= _MAX_CACHE_SIZE:
            # 캐시가 가득 차면 가장 오래된 항목 절반을 정리하여 메모리 및 성능 균형 유지
            old_keys = list(_PLACE_CACHE.keys())[: _MAX_CACHE_SIZE // 2]
            for key in old_keys:
                _PLACE_CACHE.pop(key, None)
        _PLACE_CACHE[cache_key] = result

    return result


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "창신초등학교"
    print(f"장소 검색 실행: {target}")
    res = lookup_navermap_place(target)
    print(json.dumps(res, ensure_ascii=False, indent=2))
