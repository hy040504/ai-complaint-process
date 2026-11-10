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
) -> dict[str, Any]:
    """장소명으로 네이버 지도를 검색하고 청주시 주소 및 구/동 정보를 반환합니다.

    Args:
        query: 장소 검색어(예: 건물명, 학교명, 시장명 등)입니다.
        coords: 검색 중심 좌표입니다. 생략 시 청주시청 좌표를 사용합니다.
        fetch_fn: HTTP 호출을 대신할 검색 함수입니다. 테스트 시 주입합니다.

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

    result = {
        "query": text,
        "coords": center_coords,
        "found": bool(places),
        "total": len(places),
        "primary_place": primary,
        "places": places,
    }

    if fetch_fn is None:
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
