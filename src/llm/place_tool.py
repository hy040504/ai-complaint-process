"""네이버 지도 웹 인스턴트 검색을 이용한 장소 주소 추적 도구입니다.

네이버 로그인 세션이나 별도 유료 API 키 없이, 네이버 지도의 공개
인스턴트 검색 엔드포인트를 호출하여 특정 장소(건물, 학교, 시설명 등)의
도로명·지번 주소와 청주시 관할 자치구(상당구·서원구·흥덕구·청원구) 및
행정/법정동을 조회합니다.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
import json
import re
import sys
import threading
import time
import urllib.error
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

# 네이버 지도 대량 연속 조회 시 HTTP 400/429 제한을 피하기 위한 스레드 안전 페이싱·서킷브레이커입니다.
_HTTP_THROTTLE_LOCK = threading.Lock()
_LAST_HTTP_REQUEST_AT = 0.0
_HTTP_COOLDOWN_UNTIL = 0.0
_MIN_REQUEST_INTERVAL_S = 0.16
_COOLDOWN_SECONDS = 60.0
_RETRYABLE_HTTP_CODES = frozenset({400, 429, 502, 503, 504})
_COOLDOWN_HTTP_CODES = frozenset({400, 429})
_MAX_HTTP_RETRIES = 1

_TAG_RE = re.compile(r"<[^>]+>")
_GU_RE = re.compile(r"(상당구|서원구|흥덕구|청원구)")
_DONG_RE = re.compile(r"([가-힣\d]+(?:동|읍|면|가))\b")

_STOP_SUFFIXES: tuple[str, ...] = (
    "근처에서",
    "근처에",
    "근처",
    "부근에서",
    "부근에",
    "부근",
    "주변에서",
    "주변에",
    "주변",
    "인근에서",
    "인근에",
    "인근",
    "맞은편에서",
    "맞은편에",
    "맞은편",
    "건너편에서",
    "건너편에",
    "건너편",
    "앞쪽에서",
    "앞쪽에",
    "앞쪽",
    "앞에서",
    "앞에",
    "에서",
    "으로",
    "에는",
    "에",
    "이",
    "가",
    "을",
    "를",
    "은",
    "는",
    "도",
    "쪽",
    "방면",
    "이나",
    "거나",
    "라고",
    "이라",
    "에서부터",
    "까지는",
    "으로부터",
    "로써",
    "로서",
    "처럼",
)

# 서술어·종결어미로 끝나는 어절은 어간만 잘라 장소를 찾으면('궁금합니다'→'궁금'→'궁금해아트')
# 엉뚱한 상호를 검색하게 되므로 후보에서 통째로 제외합니다.
_PREDICATE_SUFFIXES: tuple[str, ...] = (
    "겠습니다",
    "었습니다",
    "았습니다",
    "했습니다",
    "하겠습니다",
    "되었습니다",
    "되었는데",
    "었는데",
    "았는데",
    "였는데",
    "흔들었는데",
    "청구하면",
    "결제하면",
    "찾아가서",
    "깜빡거립니다",
    "거립니다",
    "합니다",
    "됩니다",
    "입니다",
    "있습니다",
    "없습니다",
    "바랍니다",
    "드립니다",
    "갑니다",
    "옵니다",
    "습니다",
    "ㅂ니다",
    "해주세요",
    "알려주세요",
    "부탁합니다",
    "주십시오",
    "원합니다",
    "싶습니다",
    "미부여된",
    "궁금해",
    "하네요",
    "인가요",
    "되나요",
    "하나요",
    "할까요",
    "일까요",
    "있나요",
    "없나요",
    "었나요",
    "았나요",
    "었나",
    "았나",
    "였나",
    "거든요",
    "는데요",
    "어요",
    "아요",
    "네요",
)

_STOP_WORDS: frozenset[str] = frozenset(
    {
        "청주",
        "청주시",
        "충북",
        "충청북도",
        "시내",
        "도로",
        "도로에",
        "골목",
        "골목길",
        "차도",
        "인도",
        "인도로",
        "차도로",
        "보도",
        "보도블럭",
        "보도블록",
        "횡단보도",
        "우회도로",
        "하상도로",
        "이면도로",
        "순환도로",
        "간선도로",
        "지하차도",
        "지하도로",
        "고속도로",
        "진입로",
        "보행로",
        "통행로",
        "산책로",
        "자전거로",
        "출근로",
        "교차로",
        "농로",
        "신호등",
        "음향신호기",
        "가로등",
        "가로등이",
        "보안등",
        "가로수",
        "포트홀",
        "싱크홀",
        "경계석",
        "자전거도로",
        "현수막",
        "불법현수막",
        "노상적치물",
        "비산먼지",
        "나무가",
        "나무",
        "쓰러짐",
        "파손",
        "고장",
        "고장났어요",
        "수리",
        "공사",
        "발생",
        "소음",
        "악취",
        "냄새",
        "쓰레기",
        "폐기물",
        "대형폐기물",
        "종량제",
        "종량제봉투",
        "봉투",
        "불법주정차",
        "불법주차",
        "주정차",
        "단속",
        "신고",
        "요청",
        "문의",
        "질문",
        "부탁드립니다",
        "주세요",
        "알려주세요",
        "해결해주세요",
        "있어요",
        "있나요",
        "없나요",
        "안됩니다",
        "때문에",
        "어디",
        "공무원",
        "불친절",
        "안내",
        "답변",
        "처리",
        "확인",
        "점검",
        "안녕하세요",
        "감사합니다",
        "수고하십니다",
        "문제",
        "민원",
        "민원위치",
        "상태",
        "상황",
        "현장",
        "조치",
        "건의",
        "불편",
        "불편합니다",
        "사항",
        "위험해요",
        # 원인조사(-로)·시간·일반 시설 행위어 오매칭 방지 불용어
        "사고로",
        "주차로",
        "불법주정차로",
        "불법주차로",
        "쓰레기로",
        "악취로",
        "공사로",
        "문제로",
        "추가로",
        "제대로",
        "정도로",
        "수시로",
        "그대로",
        "출근길",
        "퇴근길",
        "등하굣길",
        "주말",
        "야간",
        "평일",
        "반사경",
        "전구",
        "전멸",
        "소리",
        "지도",
        "계도",
        "유턴",
        # FAQ·일반 행정 서술 및 보고서 3순위 식별 일반명사 오매칭 방지 불용어
        "지역",
        "접수",
        "공식",
        "신청",
        "신청서",
        "무료",
        "유료",
        "방문",
        "발급",
        "재발급",
        "등록",
        "방법",
        "대상",
        "조건",
        "기준",
        "규격",
        "기간",
        "처리기간",
        "수수료",
        "비용",
        "환불",
        "할인",
        "현금",
        "본인",
        "대리",
        "세대원",
        "전입신고",
        "미성년자",
        "미만",
        "이상",
        "여권",
        "자동차",
        "차량",
        "온라인",
        "인터넷",
        "사이트",
        "자동이체",
        "번호",
        "내선번호",
        "연락처",
        "전화",
        "과태료",
        "버스",
        "시내버스",
        "노선",
        "정기권",
        "동물",
        "사체",
        "로드킬",
        "신고처",
        "재난문자",
        "알림",
        "해지",
        "관련",
        "인한",
        "대한",
        "따른",
        "개선",
        "보수",
        "교체",
        "설치",
        "제거",
        "관리",
        "청소",
        "정비",
        "시간",
        "일원",
        "현재",
        "오늘",
        "최근",
        "어제",
        "계속",
        "자꾸",
        "너무",
        "정말",
        "진짜",
        "제발",
        "동네",
        "어딘가",
        "학교",
        "미기재",
        "부서",
        "부서명",
        "담당",
        "담당자",
        "시민",
        "주민",
        "부모",
        "어머니",
        "아버지",
        "아기",
        "자녀",
        "세대주",
        "보호자",
        "임산부",
        "어르신",
        "가족",
        "출생신고",
        "출생증명서",
        "신고기관",
        "기관",
        "직접",
        "주민복지과",
        "편의점",
        "원룸",
        "원룸촌",
        "화장실",
        "공중화장실",
        "벤치",
        "볼라드",
        "맨홀",
        "배수로",
        "빗물받이",
        "면접",
        "정장",
        "대여",
        "준비",
        "서류",
        "구비서류",
        "여부",
        "가능",
        "존재하지",
        "않는",
        "청주페이",
        "qr코드",
        "QR코드",
        "가맹점",
        "결제",
        "지원사업",
        "자전거",
        "부과",
        "재교부",
        "현황",
        "배출",
        "수거",
        "궁금",
        "필요",
        "부탁",
        "알고",
        "무단",
        "불법",
        "투기",
        "무단투기",
        "무단배출",
        "적치",
        "침하",
        "누수",
        "막힘",
        "소등",
        "상수도",
        "하수도",
        "하수구",
        "배수구",
        "하수관",
        "오수관",
        "우수관",
        "정화조",
        "수도관",
        "음식물",
        "생활쓰레기",
        "폐가구",
        "전봇대",
        "전신주",
        "변압기",
        "과속방지턱",
        "가드레일",
        "안전펜스",
        "안전난간",
        "중앙분리대",
        "적치물",
        "공사장",
        "비꼬기",
        "비꼬는",
        "비꼬",
        "조롱",
        "비유",
        "협박",
        "표현",
        "폭언",
        "욕설",
        "보복",
        "예고",
        "모욕",
        "단순",
        "신규",
        "기존",
        "모호",
        "혼합",
        "긴급",
        "일반",
        "사유지",
        "임시",
        "임시청사",
        "대조",
        "직영",
        "체험장",
        "귀신의",
        "귀신의집",
        "방치",
        "위반",
        "배상금",
        "청구",
        "접수번호",
        "민원실",
        "창구",
        "인센티브",
        "캐시백",
        "지급",
        "감면",
        "면제",
        "승인",
        "확약",
        "가부",
        "불만",
        "앵무새",
        "루팡",
        "탁상",
        "책상",
        "벽화",
        "데크",
        "계단",
        "안전",
        "난간",
        "지연",
        "시스템",
        "오류",
        "대행사",
        "정산",
        "가이드",
        "박스",
        "전액",
        "이름",
        "명칭",
        "기억",
        "기억나지",
        "기억나",
        "준공",
        "이전",
        "미부여",
        "도로명주소",
        "단독주택",
        "차선",
        "주행차로",
        "도색",
    }
)

# 고유 수식어 없이 단독으로 쓰이면 특정 위치를 특정할 수 없는 일반 시설·장소 명사입니다.
_GENERIC_PLACE_NOUNS: frozenset[str] = frozenset(
    {
        "초등학교",
        "중학교",
        "고등학교",
        "대학교",
        "대학",
        "초교",
        "중교",
        "고교",
        "유치원",
        "어린이집",
        "학교",
        "병원",
        "의원",
        "약국",
        "보건소",
        "행정복지센터",
        "주민센터",
        "동사무소",
        "면사무소",
        "읍사무소",
        "구청",
        "시청",
        "법원",
        "경찰서",
        "지구대",
        "파출소",
        "소방서",
        "우체국",
        "아파트",
        "단지",
        "빌라",
        "주택",
        "상가",
        "빌딩",
        "건물",
        "매장",
        "상점",
        "카페",
        "식당",
        "편의점",
        "공원",
        "생태공원",
        "주차장",
        "공영주차장",
        "시장",
        "전통시장",
        "종합시장",
        "백화점",
        "마트",
        "아울렛",
        "사거리",
        "오거리",
        "삼거리",
        "네거리",
        "교차로",
        "로터리",
        "회전교차로",
        "정류장",
        "정류소",
        "버스정류장",
        "승강장",
        "터미널",
        "역",
        "출구",
        "정문",
        "후문",
        "중문",
        "남문",
        "북문",
        "서문",
        "동문",
        "육교",
        "지하차도",
        "터널",
        "대교",
        "매표소",
        "전망대",
        "호수",
        "캠핑장",
        "휴게소",
        "체육관",
        "국제공항",
        "공항",
        "박물관",
        "기념관",
        "도서관",
        "미술관",
        "행궁",
        "산성",
    }
)

# 청구·문의·사칭 문맥에서 현장 위치로 오인되기 쉬운 관공서 명칭입니다.
_ADMIN_OFFICE_NOUNS: frozenset[str] = frozenset(
    {
        "시청",
        "청주시청",
        "구청",
        "상당구청",
        "서원구청",
        "흥덕구청",
        "청원구청",
        "행정복지센터",
        "주민센터",
        "동사무소",
        "면사무소",
        "읍사무소",
    }
)

# 일반 시설 명사 앞에 붙어도 구체적 지점을 특정하지 못하는 비고유 수식어입니다.
_NON_PLACE_MODIFIERS: frozenset[str] = frozenset(
    {
        "우리",
        "동네",
        "해당",
        "각각",
        "각종",
        "모든",
        "무슨",
        "어떤",
        "이런",
        "그런",
        "저런",
        "다른",
        "일반",
        "개인",
        "공동",
        "단독",
        "읍면동",
        "내일",
        "어제",
        "오늘",
        "지난",
        "이번",
        "다음",
        "앞쪽",
        "뒤쪽",
        "안쪽",
        "바깥쪽",
    }
)

# 끝 글자가 1글자 조사('을','도','로','이','가')와 우연히 겹쳐 어근이 잘리지 않도록 보호하는 어미입니다.
_PROTECTED_WORD_ENDINGS: tuple[str, ...] = (
    "마을",
    "수도",
    "차도",
    "인도",
    "복도",
    "정도",
    "시도",
    "도로",
    "선로",
    "수로",
    "거리",
    "센터",
    "타워",
    "파크",
    "빌라",
    "마트",
    "시청",
    "구청",
    "학교",
    "공원",
    "시장",
)

_PHYSICAL_PLACE_NEAR_OFFICE_RE = re.compile(
    r"(?:청주시청|시청|상당구청|서원구청|흥덕구청|청원구청|구청|행정복지센터|주민센터|동사무소|면사무소|읍사무소)"
    r"(?:\s*임시청사)?"
    r"\s*(?:앞|뒤|옆|근처|부근|주변|인근|건너편|맞은편|주차장|정문|후문|입구|횡단보도|사거리|인도|보도블[록럭]|가로등)"
)

# 고유 장소·시설 접미어를 가진 후보는 5후보 컷오프 시 앞쪽 일반 조합보다 우선 정렬합니다.
_PLACE_PRIORITY_SUFFIXES: tuple[str, ...] = (
    "국제공항",
    "공항",
    "생태공원",
    "공원",
    "종합시장",
    "시장",
    "박물관",
    "기념관",
    "도서관",
    "미술관",
    "전망대",
    "행궁",
    "산성",
    "터미널",
    "역",
    "출구",
    "초등학교",
    "중학교",
    "고등학교",
    "대학교",
    "대학",
    "초교",
    "중교",
    "고교",
    "병원",
    "보건소",
    "행정복지센터",
    "주민센터",
    "구청",
    "시청",
    "법원",
    "우체국",
    "사거리",
    "오거리",
    "삼거리",
    "교차로",
    "네거리",
    "아파트",
    "단지",
    "지구",
    "휴게소",
    "캠핑장",
    "체육관",
    "백화점",
    "마트",
    "아울렛",
    "대교",
    "매표소",
    "호수",
    "정문",
    "후문",
    "중문",
    "정류장",
    "정류소",
    "육교",
    "지하차도",
    "터널",
    "자이",
    "푸르지오",
    "아이파크",
    "더샵",
    "힐스테이트",
    "파라곤",
    "대로",
    "번길",
    "길",
)

# 긴 문장 보완 검색 시 과도한 외부 HTTP 호출을 막기 위한 후보 상한입니다.
_MAX_FALLBACK_CANDIDATES = 5

# 토큰 정제·장소명 대조에서 반복 호출되는 정규식을 모듈 로드 시 1회 컴파일합니다.
# 숫자-숫자 번지 하이픈('16-19', '874-2')은 유지하고 문자 결합 하이픈('은행나무-바닥')만 분리합니다.
_CLEAN_PUNCT_RE = re.compile(r"[()\[\]{}<>\"'·~!,?:]|(?<!\d)-(?!\d)")
_NORM_TITLE_RE = re.compile(r"[\s\-_()\[\]]")
_ALPHA_HANGUL_RE = re.compile(r"[가-힣A-Za-z]")
_PLACE_COUNTER_RE = re.compile(
    r"^\d+(?:세|살|명|개|건|회|원|만원|천원|억|분|초|시간|일|주|개월|년|kg|km|cm|mm|%)$"
)
_ROAD_SUFFIX_RE = re.compile(r"[가-힣0-9]{2,14}(?:대로|번길|로|길)$")
_ROAD_WITH_NUM_RE = re.compile(
    r"(?:^|[\s,(·\"':)\]])([가-힣0-9]{2,14}(?:대로|번길|로|길))\s*(\d+(?:-\d+)?)(?=\s|[.,)에서으로에의로와과도\]]|$)"
)


@lru_cache(maxsize=1)
def _cheongju_admin_tokens() -> frozenset[str]:
    """청주시 4대 구 및 관할 읍·면·동 이름 집합을 지연 로드해 반환합니다.

    모듈 임포트 순환을 피하기 위해 최초 조회 시 1회만 불러와 캐시합니다.

    Returns:
        청주시 구·동·읍·면 명칭 `frozenset`입니다.
    """
    from src.assist.district import DISTRICT_AREAS, DISTRICTS

    tokens: set[str] = set(DISTRICTS)
    for areas in DISTRICT_AREAS.values():
        tokens.update(areas)
    return frozenset(tokens)


def _has_place_suffix(token: str) -> bool:
    """토큰이 구체적인 장소·시설·도로명 고유 접미어로 끝나는지 확인합니다.

    고유 수식어 없는 일반 시설명(`초등학교`, `아파트`, `시청` 등) 단독은
    우선 승격에서 제외합니다.

    Args:
        token: 정제된 단일 단어 또는 2단어 조합 문자열입니다.

    Returns:
        고유 장소·시설·도로명 접미어가 포함되어 있으면 True입니다.
    """
    if token in _STOP_WORDS or token in _GENERIC_PLACE_NOUNS:
        return False
    if any(token.endswith(suffix) for suffix in _PLACE_PRIORITY_SUFFIXES):
        return True
    return bool(_ROAD_SUFFIX_RE.match(token))


def _extract_road_number_pairs(text: str) -> list[str]:
    """문장에서 '도로명 + 번지수'('오송생명14로 283', '2순환로 1374') 쌍을 추출합니다.

    일반 단어 정리 단계에서 숫자 번지가 버려지지 않도록 원문에서 먼저 결합합니다.

    Args:
        text: 민원 원문 또는 검색어 문자열입니다.

    Returns:
        중복을 제거한 '도로명 번지' 문자열 목록입니다.
    """
    pairs: list[str] = []
    for match in _ROAD_WITH_NUM_RE.finditer(text):
        road_name = match.group(1)
        road_num = match.group(2)
        if road_name in _STOP_WORDS or road_name in _STOP_SUFFIXES:
            continue
        pairs.append(f"{road_name} {road_num}")
    return list(dict.fromkeys(pairs))


def _road_fallback_variants(road_num_pair: str) -> list[str]:
    """미등록 도로명+번지('2순환로 1374')의 주번지·인접 번지 보조 검색어를 생성합니다.

    네이버 지도 인스턴트 검색에 특정 건물번호가 누락된 경우 주변 ±1·±2 인접
    번호나 주번지로 생활권·관할 구를 추적하기 위해 사용합니다.

    Args:
        road_num_pair: `'도로명 번호'` 형식 문자열입니다.

    Returns:
        중복을 제거한 보조 검색어 목록입니다.
    """
    parts = road_num_pair.split()
    if len(parts) != 2:
        return []
    road_name, num_part = parts
    variants: list[str] = []
    if "-" in num_part:
        main_num = num_part.split("-", 1)[0]
        if main_num.isdigit():
            variants.append(f"{road_name} {main_num}")
        return variants
    if num_part.isdigit():
        base = int(num_part)
        for delta in (1, -1, 2, -2):
            adj = base + delta
            if adj > 0:
                variants.append(f"{road_name} {adj}")
    return variants


def _clean_query_tokens(text: str) -> list[str]:
    """문장에서 조사·문장부호·일반 불용어를 걸러 장소 비교용 핵심 토큰을 추출합니다.

    어근 끝 글자(`벽화마을`, `상수도`) 손실 및 행정구역+조사 결합(`청주시로`,
    `도로와`)의 도로명 오인을 함께 차단합니다.

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
        is_protected_root = cur.endswith(_PROTECTED_WORD_ENDINGS)
        for suf in _STOP_SUFFIXES:
            if len(suf) == 1 and is_protected_root:
                continue
            if cur.endswith(suf) and len(cur) > len(suf):
                cur = cur[: -len(suf)].strip(".,:;~/-")
                break
        if (
            not cur
            or cur in _STOP_WORDS
            or cur in _STOP_SUFFIXES
            or cur.endswith(_PREDICATE_SUFFIXES)
            or (
                cur.endswith(
                    ("로", "과", "와", "랑", "에", "의", "도", "만", "를", "을")
                )
                and cur[:-1] in _STOP_WORDS
            )
            or len(cur) < 2
            or not _ALPHA_HANGUL_RE.search(cur)
            or _PLACE_COUNTER_RE.match(cur)
        ):
            continue
        refined_words.append(cur)
    return refined_words


def _token_matches_title(token: str, norm_title: str) -> bool:
    """단일 정제 토큰이 정규화된 장소 제목과 유의미하게 겹치는지 판별합니다.

    Args:
        token: 정제된 검색어 토큰입니다.
        norm_title: 공백·기호 제거 및 소문자화된 장소 제목입니다.

    Returns:
        토큰이 장소 제목에 포함되거나 충분한 길이의 역포함이면 True입니다.
    """
    low = token.lower()
    if low in norm_title:
        if len(low) <= 2 and len(norm_title) > 12:
            return False
        return True
    return (
        norm_title not in _STOP_WORDS
        and (
            len(norm_title) >= 4
            or (len(norm_title) >= 3 and len(norm_title) >= len(token) * 0.6)
        )
        and norm_title in low
    )


def is_place_relevant(title: str, query: str) -> bool:
    """검색 결과의 장소 제목이 검색어 키워드와 실제 일치하는지 검증합니다.

    청주시에 위치한 무관한 식당·상점이나 일반 시설 접미어(`초등학교`, `아파트`,
    `시장`) 및 행정동(`봉명동`→`봉명동내커피`) 단독 우연 매칭을 차단합니다.

    Args:
        title: 네이버 지도 장소 제목입니다.
        query: 검색에 사용한 키워드입니다.

    Returns:
        고유 장소 키워드가 제목과 유의미하게 일치하면 True입니다.
    """
    if not title or not query:
        return False
    norm_title = _NORM_TITLE_RE.sub("", title.lower())
    if not norm_title or len(norm_title) < 2:
        return False
    words = _clean_query_tokens(query)
    if not words:
        return False
    admin_tokens = _cheongju_admin_tokens()
    if len(words) == 1:
        only = words[0]
        if (
            only in _GENERIC_PLACE_NOUNS or only in admin_tokens
        ) and norm_title != _NORM_TITLE_RE.sub("", only.lower()):
            return False
        return _token_matches_title(only, norm_title)

    matched = [w for w in words if _token_matches_title(w, norm_title)]
    if not matched:
        return False
    # 2어절 이상 조합·문장에서는 일반 시설 접미어나 행정구역명 단독 일치만으로 통과시키지 않습니다.
    return any(w not in _GENERIC_PLACE_NOUNS and w not in admin_tokens for w in matched)


def _is_address_relevant(address_text: str, query: str) -> bool:
    """네이버 `address` 응답 주소가 검색 질의의 도로명+번지와 일치하는지 확인합니다.

    Args:
        address_text: 네이버 지도 `fullAddress` 또는 `title` 문자열입니다.
        query: 검색에 사용한 질의 문자열입니다.

    Returns:
        질의 내 도로명+번호가 주소 문자열에 포함되면 True입니다.
    """
    if not address_text or not query:
        return False
    norm_addr = _NORM_TITLE_RE.sub("", address_text.lower())
    road_pairs = _extract_road_number_pairs(query)
    if road_pairs:
        for pair in road_pairs:
            norm_pair = _NORM_TITLE_RE.sub("", pair.lower())
            if norm_pair in norm_addr:
                return True
        return False
    return is_place_relevant(address_text, query)


def _is_valid_two_word_combo(
    left: str,
    right: str,
    *,
    allow_office: bool,
    admin_tokens: frozenset[str],
) -> bool:
    """2단어 조합이 실제 장소 후보로 적합한지 검증합니다.

    일반 시설명 앞에 비고유 수식어나 동명이 붙은 조합(`우리 초등학교`,
    `용암동 시장`), 행정구역 단독 쌍(`흥덕구 봉명동`), 현장 수식 없는 관공서
    언급(`청주시청 청구하면`, `시청 민원실`)을 제외합니다.

    Args:
        left: 앞쪽 정제 토큰입니다.
        right: 뒤쪽 정제 토큰입니다.
        allow_office: 원문 문맥에 관공서 주변 현장 위치 수식이 있으면 True입니다.
        admin_tokens: 청주시 4대 구 및 읍·면·동 이름 집합입니다.

    Returns:
        후보 조합으로 유지할 수 있으면 True입니다.
    """
    if (
        left in _ADMIN_OFFICE_NOUNS or right in _ADMIN_OFFICE_NOUNS
    ) and not allow_office:
        return False
    if left in admin_tokens and right in admin_tokens:
        return False
    if right in _GENERIC_PLACE_NOUNS and (
        left in _NON_PLACE_MODIFIERS
        or left in admin_tokens
        or left in _GENERIC_PLACE_NOUNS
    ):
        return False
    if left in _NON_PLACE_MODIFIERS and right in _NON_PLACE_MODIFIERS:
        return False
    return True


def _build_place_candidates(
    text: str, road_num_pairs: list[str] | None = None
) -> list[str]:
    """미리 계산한 도로+번지 목록을 재사용해 장소명 후보 목록을 만듭니다.

    Args:
        text: 민원 문장 또는 검색어입니다.
        road_num_pairs: 미리 추출한 '도로명 번지' 쌍 목록입니다. 생략 시 내부에서 추출합니다.

    Returns:
        우선순위가 높은 장소명 후보 문자열 목록입니다.
    """
    tier_road_num = (
        road_num_pairs
        if road_num_pairs is not None
        else _extract_road_number_pairs(text)
    )
    refined_words = _clean_query_tokens(text)
    if not tier_road_num and not refined_words:
        return []

    admin_tokens = _cheongju_admin_tokens()
    is_long_sentence = len(text.split()) >= 3
    allow_office = (not is_long_sentence) or bool(
        _PHYSICAL_PLACE_NEAR_OFFICE_RE.search(text)
    )
    road_names_with_num = {pair.split()[0] for pair in tier_road_num}

    tier_combo_priority: list[str] = []
    tier_single_priority: list[str] = []
    tier_combo_general: list[str] = []
    tier_single_general: list[str] = []
    tier_road_variants: list[str] = []

    for pair in tier_road_num:
        tier_road_variants.extend(_road_fallback_variants(pair))

    for i in range(len(refined_words) - 1):
        left, right = refined_words[i], refined_words[i + 1]
        if left == right or not _is_valid_two_word_combo(
            left, right, allow_office=allow_office, admin_tokens=admin_tokens
        ):
            continue
        if (left in road_names_with_num or right in road_names_with_num) and not (
            _has_place_suffix(left) and _has_place_suffix(right)
        ):
            # 번지가 결합된 도로명이 일반 단어('차선','도색')와 조합되어 인접 번지 탐침 순위를 밀어내지 않게 제외합니다.
            continue
        combo = f"{left} {right}"
        if _has_place_suffix(left) or _has_place_suffix(right) or right.endswith("점"):
            tier_combo_priority.append(combo)
        else:
            tier_combo_general.append(combo)

    for w in refined_words:
        if w in _GENERIC_PLACE_NOUNS or w in admin_tokens or w in _NON_PLACE_MODIFIERS:
            continue
        if w in _ADMIN_OFFICE_NOUNS and not allow_office:
            continue
        if w in road_names_with_num:
            # 번지가 이미 추출된 도로명은 무번지 단독 검색으로 타 구 지점이 걸리지 않게 제외합니다.
            continue
        if _has_place_suffix(w):
            tier_single_priority.append(w)
        elif not is_long_sentence or len(w) > 2:
            tier_single_general.append(w)

    return list(
        dict.fromkeys(
            [
                *tier_road_num,
                *tier_combo_priority,
                *tier_single_priority,
                *tier_road_variants,
                *tier_combo_general,
                *tier_single_general,
            ]
        )
    )


def extract_place_candidates(text: str) -> list[str]:
    """긴 문장이나 복합 민원에서 장소명 후보 키워드 목록을 추출합니다.

    도로명+번지 쌍과 고유 시설 복합어를 최우선으로 배치하고, 단독 일반 시설명
    (`초등학교`·`아파트`·`시장`·`시청`), 행정구역 단독(`봉명동`), 무번지 다구 도로
    단독 후보는 제외해 오매칭과 불필요한 외부 호출을 방지합니다.

    Args:
        text: 민원 문장 또는 검색어입니다.

    Returns:
        우선순위가 높은 장소명 후보 문자열 목록입니다.
    """
    return _build_place_candidates(text)


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


def _pace_navermap_http() -> None:
    """네이버 지도 연속 호출 시 트래픽 제한(HTTP 400/429) 회피 간격과 쿨다운을 확인합니다.

    Raises:
        OSError: 최근 400/429 제한으로 일시 쿨다운 대기 중일 때 즉시 발생합니다.
    """
    global _LAST_HTTP_REQUEST_AT
    with _HTTP_THROTTLE_LOCK:
        now = time.monotonic()
        if now < _HTTP_COOLDOWN_UNTIL:
            raise OSError("네이버 지도 일시적 호출 제한(쿨다운 대기 중)")
        wait_s = _MIN_REQUEST_INTERVAL_S - (now - _LAST_HTTP_REQUEST_AT)
        if wait_s > 0:
            time.sleep(wait_s)
        _LAST_HTTP_REQUEST_AT = time.monotonic()


def fetch_navermap_instant_search(
    query: str,
    coords: str = CHEONGJU_COORDS,
    timeout: float = 5.0,
) -> dict[str, Any]:
    """네이버 지도 웹 인스턴트 검색 API를 호출합니다.

    네이버 로그인 세션이 없는 비로그인 상태에서도 동작하도록 일반적인 브라우저
    헤더(User-Agent, Referer)를 전송하며, 대량 연속 요청 시 `HTTP 400/429`
    오류가 발생하면 짧은 백오프 재시도 후 일시 쿨다운으로 연쇄 지연을 차단합니다.

    Args:
        query: 장소 검색어입니다.
        coords: 기준 좌표 (위도,경도)입니다. 기본값은 청주시청입니다.
        timeout: HTTP 요청 타임아웃(초)입니다.

    Returns:
        네이버 지도 검색 응답 JSON 객체입니다.

    Raises:
        OSError: 네트워크 요청 실패 또는 일시 쿨다운 중일 때 발생합니다.
        ValueError: 응답 본문이 올바른 JSON이 아닌 경우 발생합니다.
    """
    global _HTTP_COOLDOWN_UNTIL
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
    last_exc: Exception | None = None
    for attempt in range(_MAX_HTTP_RETRIES + 1):
        _pace_navermap_http()
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as res:
                raw_body = res.read().decode("utf-8")
                parsed = json.loads(raw_body)
                if not isinstance(parsed, dict):
                    raise ValueError("네이버 지도 응답이 JSON 객체 형식이 아닙니다.")
                return parsed
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code in _RETRYABLE_HTTP_CODES and attempt < _MAX_HTTP_RETRIES:
                time.sleep(0.4 * (2**attempt))
                continue
            if exc.code in _COOLDOWN_HTTP_CODES:
                with _HTTP_THROTTLE_LOCK:
                    _HTTP_COOLDOWN_UNTIL = time.monotonic() + _COOLDOWN_SECONDS
            raise
    if last_exc is not None:
        raise last_exc
    raise OSError("네이버 지도 요청을 실행하지 못했습니다.")


_AC_DONG_RE = re.compile(r"\(([가-힣\d]+(?:동|읍|면|가))\)")


def _extract_ac_dong(raw_data: dict[str, Any], gu: str | None) -> str | None:
    """네이버 자동완성(`ac`) 문자열의 괄호(`(우암동)`)에서 보조 동 명칭을 추출합니다.

    Args:
        raw_data: 네이버 지도 인스턴트 검색 원본 JSON 객체입니다.
        gu: 이미 판별된 청주시 자치구 이름입니다.

    Returns:
        괄호 안 동·읍·면 명칭 또는 None입니다.
    """
    ac_list = raw_data.get("ac")
    if not isinstance(ac_list, list):
        return None
    for entry in ac_list:
        if not isinstance(entry, str):
            continue
        if gu and gu not in entry and "청주" not in entry:
            continue
        match = _AC_DONG_RE.search(entry)
        if match:
            return match.group(1)
    return None


def _build_place_obj(
    *,
    title: str,
    road_addr: str | None,
    jibun_addr: str | None,
    ctg: str | None,
    x: object,
    y: object,
    fallback_dong: str | None = None,
) -> dict[str, Any]:
    """정제된 장소·주소 메타데이터 딕셔너리를 조립합니다.

    Args:
        title: 정제된 장소 또는 주소 제목입니다.
        road_addr: 도로명 주소 문자열입니다.
        jibun_addr: 지번 주소 문자열입니다.
        ctg: 시설 분류 또는 주소 구분 문자열입니다.
        x: 경도 값입니다.
        y: 위도 값입니다.
        fallback_dong: 주소 문자열에 동이 없을 때 `ac`에서 추출한 보조 동 명칭입니다.

    Returns:
        정규화된 장소 결과 딕셔너리입니다.
    """
    gu = extract_cheongju_district(jibun_addr) or extract_cheongju_district(road_addr)
    dong = (
        extract_cheongju_dong(jibun_addr)
        or extract_cheongju_dong(road_addr)
        or fallback_dong
    )
    combined_addr = f"{road_addr or ''} {jibun_addr or ''}"
    is_cheongju = "청주" in combined_addr or gu is not None
    return {
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


def _append_unique_place(
    place_obj: dict[str, Any],
    places: list[dict[str, Any]],
    cheongju_places: list[dict[str, Any]],
    seen_keys: set[tuple[str, str | None, str | None]],
) -> None:
    """중복되지 않은 정제 장소 항목을 전체·청주시 목록에 함께 추가합니다.

    Args:
        place_obj: `_build_place_obj`로 정규화한 장소·주소 딕셔너리입니다.
        places: 전체 정제 결과를 누적하는 리스트입니다.
        cheongju_places: 청주시 판정 결과를 누적하는 리스트입니다.
        seen_keys: `(title, road_address, jibun_address)` 중복 제거용 집합입니다.
    """
    key = (
        place_obj["title"],
        place_obj["road_address"],
        place_obj["jibun_address"],
    )
    if key in seen_keys:
        return
    seen_keys.add(key)
    places.append(place_obj)
    if place_obj["is_cheongju"]:
        cheongju_places.append(place_obj)


def _parse_navermap_items(
    raw_data: dict[str, Any], query_text: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """네이버 지도 `place` 및 `address` 응답 목록을 함께 정제해 반환합니다.

    도로명+번지(`직지대로 874-2`, `호미로201번길 16-19`)는 `place`가 0건이고
    `address`·`ac`에만 주소가 반환되므로 두 섹션을 모두 통합 파싱합니다.

    Args:
        raw_data: 네이버 지도 검색 응답 JSON 객체입니다.
        query_text: 관련성 대조에 사용할 질의 문자열입니다.

    Returns:
        `(전체 장소·주소 목록, 청주시 장소·주소 목록)` 튜플입니다.
    """
    places: list[dict[str, Any]] = []
    cheongju_places: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str | None, str | None]] = set()

    raw_places = raw_data.get("place")
    if isinstance(raw_places, list):
        for item in raw_places:
            if not isinstance(item, dict):
                continue
            title = _clean_text(item.get("title"))
            if not is_place_relevant(title, query_text):
                continue
            place_obj = _build_place_obj(
                title=title,
                road_addr=_clean_text(item.get("roadAddress")) or None,
                jibun_addr=_clean_text(item.get("jibunAddress")) or None,
                ctg=_clean_text(item.get("ctg")) or None,
                x=item.get("x"),
                y=item.get("y"),
            )
            _append_unique_place(place_obj, places, cheongju_places, seen_keys)

    raw_addresses: list[dict[str, Any]] = []
    if isinstance(raw_data.get("address"), list):
        raw_addresses.extend(
            item for item in raw_data["address"] if isinstance(item, dict)
        )
    all_section = raw_data.get("all")
    if isinstance(all_section, dict) and isinstance(all_section.get("address"), dict):
        raw_addresses.append(all_section["address"])

    for addr_item in raw_addresses:
        full_addr = _clean_text(addr_item.get("fullAddress")) or None
        title = _clean_text(addr_item.get("title")) or (full_addr or "")
        check_target = full_addr or title
        if not check_target or not _is_address_relevant(check_target, query_text):
            continue
        place_obj = _build_place_obj(
            title=title,
            road_addr=full_addr or title,
            jibun_addr=None,
            ctg="도로명주소",
            x=addr_item.get("x"),
            y=addr_item.get("y"),
        )
        if place_obj["dong"] is None:
            gu_hint = place_obj["gu"] or extract_cheongju_district(title)
            place_obj["dong"] = _extract_ac_dong(raw_data, gu_hint)
        _append_unique_place(place_obj, places, cheongju_places, seen_keys)

    return places, cheongju_places


def lookup_navermap_place(
    query: str,
    coords: str | None = None,
    *,
    fetch_fn: Callable[..., dict[str, Any]] | None = None,
    _allow_fallback: bool = True,
) -> dict[str, Any]:
    """장소명 또는 도로명 주소로 네이버 지도를 검색하고 청주시 구/동 정보를 반환합니다.

    Args:
        query: 장소 검색어(예: 건물명, 학교명, 도로명+번지 등)입니다.
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

    center_coords = coords.strip() if coords and coords.strip() else CHEONGJU_COORDS
    cache_key = f"{text}|{center_coords}"

    if fetch_fn is None and cache_key in _PLACE_CACHE:
        return _PLACE_CACHE[cache_key]

    road_num_pairs = _extract_road_number_pairs(text) if _allow_fallback else []
    fallback_candidates = (
        _build_place_candidates(text, road_num_pairs=road_num_pairs)
        if _allow_fallback
        else []
    )
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
    skip_full_sentence = (
        _allow_fallback and len(text.split()) >= 3 and bool(road_num_pairs)
    )

    places: list[dict[str, Any]] = []
    cheongju_places: list[dict[str, Any]] = []
    primary: dict[str, Any] | None = None
    last_error: str | None = None

    if not skip_full_sentence:
        try:
            raw_data = fetcher(text, coords=center_coords)
            places, cheongju_places = _parse_navermap_items(raw_data, text)
            primary = (
                cheongju_places[0]
                if cheongju_places
                else (places[0] if places else None)
            )
        except Exception as exc:
            last_error = f"네이버 지도 검색 중 오류가 발생했습니다: {exc}"
            if not _allow_fallback or not fallback_candidates:
                return {
                    "query": text,
                    "coords": center_coords,
                    "found": False,
                    "total": 0,
                    "primary_place": None,
                    "places": [],
                    "error": last_error,
                }

    # 청주시 장소를 찾지 못했거나 도로명+번지 장문이면 추출된 핵심 후보로 보완 검색합니다.
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
            if cand_res.get("error"):
                last_error = str(cand_res["error"])
                if any(
                    tok in last_error
                    for tok in ("쿨다운 대기", "HTTP Error 400", "HTTP Error 429")
                ):
                    break
                continue
            cand_primary = cand_res.get("primary_place")
            if cand_primary and cand_primary.get("is_cheongju"):
                primary = cand_primary
                places = cand_res.get("places", [])
                break

    result: dict[str, Any] = {
        "query": text,
        "coords": center_coords,
        "found": bool(places),
        "total": len(places),
        "primary_place": primary,
        "places": places,
    }
    if not places and last_error is not None:
        result["error"] = last_error

    if (
        fetch_fn is None
        and "error" not in result
        and (_allow_fallback or (primary is not None and primary.get("is_cheongju")))
    ):
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
