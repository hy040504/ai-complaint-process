"""청주시 행정구역(4개 구 및 관할 읍·면·동) 지명 정규화와 본문 지명 추출기입니다.

민원 제목과 상세 본문에서 청주시 관할 구와 동·읍·면을 감지하여
검색 API의 `district` 필터로 안전하게 연결합니다. 복수 구가 감지되거나
충돌하면 필터를 걸지 않고 None을 반환합니다.
"""

from __future__ import annotations

import re
from typing import Any, Final

# 청주시 4대 자치구 명칭입니다.
DISTRICTS: Final[tuple[str, ...]] = ("상당구", "서원구", "흥덕구", "청원구")

# 청주시 4개 구 산하 읍·면·동 매핑입니다.
# 행정동과 대표 법정동을 함께 포함하여 시민의 다양한 표기를 지원합니다.
DISTRICT_AREAS: Final[dict[str, tuple[str, ...]]] = {
    "상당구": (
        "낭성면", "미원면", "가덕면", "남일면", "문의면",
        "중앙동", "성안동", "탑대성동", "탑동", "대성동",
        "영운동", "금천동", "용담명암산성동", "용담동", "명암동", "산성동",
        "용암1동", "용암2동", "용암동", "방서동", "평촌동", "지북동", "운동동", "월오동",
        "북문로1가", "북문로2가", "북문로3가", "북문로",
        "남문로1가", "남문로2가", "남문로",
        "서운동", "서문동", "남주동", "문화동", "수동",
    ),
    "서원구": (
        "남이면", "현도면",
        "사직1동", "사직2동", "사직동",
        "사창동", "모충동", "산남동", "분평동",
        "수곡1동", "수곡2동", "수곡동",
        "성화개신죽림동", "성화동", "개신동", "죽림동",
        "장암동", "미평동",
    ),
    "흥덕구": (
        "오송읍", "강내면", "옥산면",
        "운천신봉동", "운천동", "신봉동",
        "복대1동", "복대2동", "복대동",
        "가경동",
        "봉명1동", "봉명2송정동", "봉명2동", "봉명동", "송정동",
        "강서1동", "강서2동", "강서동",
        "비하동", "석소동", "휴암동", "신성동", "향정동", "문암동", "송절동", "화계동",
    ),
    "청원구": (
        "오창읍", "내수읍", "북이면",
        "우암동",
        "내덕1동", "내덕2동", "내덕동",
        "율량사천동", "율량동", "사천동",
        "오근장동", "주중동", "주성동", "외남동", "외평동", "외하동", "정하동", "정평동",
    ),
}

# 세부 지명 -> 구 이름 역색인입니다. 긴 명칭을 먼저 대조하도록 정렬합니다.
_AREA_TO_DISTRICT: dict[str, str] = {}
for _district, _areas in DISTRICT_AREAS.items():
    for _area in _areas:
        _AREA_TO_DISTRICT[_area] = _district

# 정규식 패턴: 구 이름 및 읍·면·동 이름을 긴 순서대로 정렬하여 매칭합니다.
_SORTED_AREAS = sorted(_AREA_TO_DISTRICT.keys(), key=len, reverse=True)

# 4대 구 패턴: '상당구', '서원구', '흥덕구', '청원구'
_DISTRICT_PATTERN = re.compile(r"(상당구|서원구|흥덕구|청원구)")

# 동·읍·면 패턴: 앞뒤 경계(공백, 문장부호, '청주'/'청주시' 접두)와 결합 조사 및 뒤쪽 숫자·방위 접미 허용
_AREA_PATTERN = re.compile(
    r"(?:(?<=[\s\(\[\{<\"'.,~·/!?-])|(?<=청주시)|(?<=청주)|^)("
    + "|".join(re.escape(a) for a in _SORTED_AREAS)
    + r")(?:에서|으로|[은는이가을를의에로와과도만]?)(?=[0-9]|\s|[^\w가-힣]|$|근처|부근|주변|인근|일대)"
)

# 읍 단위('오송읍'·'오창읍'·'내수읍')는 띄어쓰기 없이 시설명이 바로 이어져도 오탐 위험이 없어 별도 매칭합니다.
_EUP_UNSPACED_PATTERN = re.compile(r"(오송읍|오창읍|내수읍)")

# 외부 장소 API 실패·절단에도 오탐 위험 없이 단일 구가 확정되는 대표 시설·관광지 매핑입니다.
# (경계·버스 노선 방면으로 자주 쓰이는 대학·공항 약칭·사거리 등은 네이버 장소 검색에 맡깁니다.)
_LANDMARK_TO_DISTRICT: Final[dict[str, str]] = {
    "청주국제공항": "청원구",
    "오창호수공원": "청원구",
    "초정행궁": "청원구",
    "내수시장": "청원구",
    "문암생태공원": "흥덕구",
    "청주고인쇄박물관": "흥덕구",
    "고인쇄박물관": "흥덕구",
    "청남대": "상당구",
}

_SORTED_LANDMARKS = sorted(_LANDMARK_TO_DISTRICT.keys(), key=len, reverse=True)
_LANDMARK_PATTERN = re.compile(
    r"(?:(?<=[\s\(\[\{<\"'.,~·/!?-])|(?<=청주시)|(?<=청주)|^)("
    + "|".join(re.escape(name) for name in _SORTED_LANDMARKS)
    + r")(?:에서|으로|[은는이가을를의에로와과도만]?)(?=[0-9]|\s|[^\w가-힣]|$)"
)

# 타 시·도 및 타 시·군 관할 행정구역 공통 정규식 조각입니다.
_EXT_METRO_GU_PART = (
    r"(?:서울(?:특별시)?|부산(?:광역시)?|대구(?:광역시)?|인천(?:광역시)?|"
    r"광주(?:광역시)?|대전(?:광역시)?|울산(?:광역시)?)\s+[가-힣]{1,5}[구군]"
    r"|세종(?:특별자치시|시)\s+[가-힣]{1,6}(?:읍|면|동)"
)
_EXT_DO_PART = (
    r"(?:경기도|강원(?:도|특별자치도)?|충청남도|충남|전북(?:특별자치도)?|"
    r"전라남도|전남|경상북도|경북|경상남도|경남|제주(?:도|특별자치도)?)\s+"
    r"(?!청주시)[가-힣]{1,6}(?:시|군)"
)
_EXT_CHUNGBUK_OTHERS = (
    r"(?:충주시|제천시|보은군|옥천군|영동군|증평군|진천군|괴산군|음성군|단양군)"
)
_EXT_OTHER_CITIES = (
    r"(?:충주시|제천시|보은군|옥천군|영동군|증평군|진천군|괴산군|음성군|단양군|"
    r"수원시|성남시|용인시|고양시|창원시|천안시|아산시|공주시|전주시|포항시|구미시)"
)

# '대전 유성구 봉명동', '서울 종로구 사직동'처럼 청주시와 같은 동명이인 지명이
# 타 지자체 주소에 포함되어 있을 때 청주시 관할 구로 오인식하지 않도록 선별합니다.
_EXTERNAL_PREFIX_RE = re.compile(
    rf"(?:{_EXT_METRO_GU_PART}"
    rf"|{_EXT_DO_PART}(?:\s+[가-힣]{{1,5}}[구군])?"
    rf"|(?:충청북도|충북)\s+{_EXT_CHUNGBUK_OTHERS}(?:\s+[가-힣]{{1,6}}(?:읍|면|동))?"
    rf"|{_EXT_OTHER_CITIES}(?:\s+[가-힣]{{1,5}}구)?)"
)

# 코드 차원에서 명백한 타 지자체 관할로 확정할 수 있는 2단계 이상 외부 주소 패턴입니다.
_EXTERNAL_CODE_REJECT_RE = re.compile(
    rf"(?:{_EXT_METRO_GU_PART}"
    rf"|{_EXT_DO_PART}\s+[가-힣]{{1,6}}(?:구|읍|면|동)"
    rf"|(?:충청북도|충북)\s+{_EXT_CHUNGBUK_OTHERS}\s+[가-힣]{{1,6}}(?:읍|면|동)"
    rf"|{_EXT_OTHER_CITIES}\s+[가-힣]{{1,6}}(?:구|읍|면|동))"
)


def _has_external_prefix_before(text: str, pos: int) -> bool:
    """매칭된 읍·면·동 바로 앞에 타 지자체 상위 주소가 붙었는지 확인합니다.

    Args:
        text: 민원 원문 문자열입니다.
        pos: `_AREA_PATTERN`이 매칭을 시작한 문자 인덱스입니다.

    Returns:
        타 지자체 행정구역 접두어 뒤에 이어진 동명이인 지명이면 True입니다.
    """
    window = text[max(0, pos - 28) : pos]
    matches = list(_EXTERNAL_PREFIX_RE.finditer(window))
    if not matches:
        return False
    tail = window[matches[-1].end() :]
    return "청주" not in tail and _DISTRICT_PATTERN.search(tail) is None


def extract_external_jurisdiction(
    text: str,
    *,
    cheongju_area_found: bool | None = None,
) -> str | None:
    """명백한 타 지자체 관할 주소가 청주 지명 없이 단독으로 적혔는지 판별합니다.

    '서울 쓰레기를 왜 청주시에서'나 '청주시 711번 진천여객'처럼 청주시와 연계된
    민원은 배제하지 않고, 순수 타 시·군·구 주소만 있을 때 해당 지명을 돌려줍니다.

    Args:
        text: 민원 제목과 본문을 합친 문자열입니다.
        cheongju_area_found: 호출자가 이미 `_find_regex_district`를 실행해
            청주시 구·동 일치 여부를 알고 있으면 전달해 중복 정규식 탐색을 생략합니다.

    Returns:
        감지된 타 지자체 주소 표기 또는 `None`입니다.
    """
    if not text:
        return None
    match = _EXTERNAL_CODE_REJECT_RE.search(text)
    if not match:
        return None
    if "청주" in text or _DISTRICT_PATTERN.search(text):
        return None
    if cheongju_area_found is True:
        return None
    if cheongju_area_found is None:
        cheongju_area, conflicted = _find_regex_district(text)
        if cheongju_area is not None or conflicted:
            return None
    return match.group(0)


def normalize_district(raw: str | None) -> str | None:
    """사용자 선택 또는 입력 문자열에서 유효한 청주시 자치구 이름을 판별합니다.

    '상당구', '서원구', '흥덕구', '청원구'는 물론, '흥덕구 가경동', '오송읍',
    '상당구:금천동' 등 세부 지역 표기도 해당 상위 자치구로 정규화합니다.

    Args:
        raw: 사용자가 선택하거나 전달한 원본 지역 문자열입니다.

    Returns:
        정규화된 자치구 이름('상당구'|'서원구'|'흥덕구'|'청원구') 또는 None입니다.
    """
    if not raw:
        return None
    val = raw.strip()
    if not val:
        return None

    # 1. 4대 구 정확 일치
    if val in DISTRICTS:
        return val

    # 2. 구 이름 2글자 접미 ('상당', '서원', '흥덕', '청원')
    for district in DISTRICTS:
        if val == district[:-1]:
            return district

    # 3. 구분자(':') 또는 공백이 포함된 세부지역 분리 ('흥덕구:가경동', '서원구 사창동')
    for district in DISTRICTS:
        if val.startswith(district + " ") or val.startswith(district + ":"):
            return district

    # 4. 읍·면·동 단독 일치
    if val in _AREA_TO_DISTRICT:
        return _AREA_TO_DISTRICT[val]

    # 5. 텍스트 추출 시도
    return extract_district(val)


def _find_regex_district(text: str) -> tuple[str | None, bool]:
    """정규표현식으로 본문에서 청주시 관할 구와 다중 구 충돌 여부를 판별합니다.

    Args:
        text: 민원 제목과 상세 본문을 합친 문자열입니다.

    Returns:
        `(단일 구 이름 또는 None, 2개 이상 구 충돌 여부)` 튜플입니다.
    """
    if not text:
        return None, False

    found_districts: set[str] = set()

    # 1. 구 이름 명시 탐색 ('상당구', '서원구', '흥덕구', '청원구')
    for match in _DISTRICT_PATTERN.finditer(text):
        found_districts.add(match.group(1))
        if len(found_districts) > 1:
            return None, True

    # 2. 읍·면·동 지명 탐색 (직전에 타 지자체 행정구역 접두가 있으면 동명이인 오인 방지)
    for match in _AREA_PATTERN.finditer(text):
        if _has_external_prefix_before(text, match.start()):
            continue
        area_name = match.group(1)
        if area_name in _AREA_TO_DISTRICT:
            found_districts.add(_AREA_TO_DISTRICT[area_name])
            if len(found_districts) > 1:
                return None, True

    for match in _EUP_UNSPACED_PATTERN.finditer(text):
        eup_name = match.group(1)
        if eup_name in _AREA_TO_DISTRICT:
            found_districts.add(_AREA_TO_DISTRICT[eup_name])
            if len(found_districts) > 1:
                return None, True

    # 3. 검증된 청주 주요 랜드마크·캠퍼스 탐색 (외부 API 컷오프/누락 보완)
    for match in _LANDMARK_PATTERN.finditer(text):
        landmark = match.group(1)
        if landmark in _LANDMARK_TO_DISTRICT:
            found_districts.add(_LANDMARK_TO_DISTRICT[landmark])
            if len(found_districts) > 1:
                return None, True

    if len(found_districts) == 1:
        return next(iter(found_districts)), False
    return None, False


def _lookup_cheongju_place(text: str) -> dict[str, Any] | None:
    """네이버 지도 장소 검색으로 청주시 최우선 장소 정보를 조회합니다.

    외부 네트워크 오류가 발생해도 민원 처리 흐름을 중단하지 않도록 예외를 삼키고
    `None`을 반환합니다.

    Args:
        text: 장소 추론 대상 민원 문자열입니다.

    Returns:
        청주시 관할로 판별된 `primary_place` 딕셔너리 또는 `None`입니다.
    """
    if not text or not text.strip():
        return None
    try:
        from src.llm.place_tool import lookup_navermap_place

        res = lookup_navermap_place(text)
        primary = res.get("primary_place")
        if isinstance(primary, dict) and primary.get("is_cheongju"):
            return primary
    except Exception:
        pass
    return None


def extract_district(text: str) -> str | None:
    """민원 제목 또는 본문에서 청주시 관할 구를 단일하게 추론합니다.

    단일 구만 명확히 감지된 경우에만 해당 구를 반환합니다. 지명이 없거나
    서로 다른 구가 2개 이상 동시에 발견(충돌)되면 검색 누락을 방지하기 위해
    None을 반환합니다.

    Args:
        text: 민원 제목과 상세 본문을 합친 문자열입니다.

    Returns:
        단일하게 추론된 구 이름('상당구'|'서원구'|'흥덕구'|'청원구') 또는 None입니다.
    """
    if not text:
        return None

    regex_district, conflicted = _find_regex_district(text)
    if conflicted:
        return None
    if regex_district:
        return regex_district

    if extract_external_jurisdiction(text, cheongju_area_found=False) is not None:
        return None

    # 정규식으로 감지되지 않은 경우 네이버 지도 장소 검색을 통한 2차 지명 추론을 시도합니다.
    primary = _lookup_cheongju_place(text)
    gu = primary.get("gu") if primary else None
    return gu if isinstance(gu, str) and gu else None


def extract_place_info(text: str) -> dict[str, Any] | None:
    """민원 본문에서 네이버 지도를 활용해 장소 정보(명칭, 주소, 구, 동)를 조회합니다.

    Args:
        text: 민원 제목과 상세 본문을 결합한 문자열입니다.

    Returns:
        청주시 장소 정보 딕셔너리 또는 None입니다.
    """
    return _lookup_cheongju_place(text)


def resolve_complaint_district(
    explicit_district: str | None, text: str
) -> tuple[str | None, bool]:
    """명시적 지역 선택을 우선하고, 없으면 본문에서 지명을 추론합니다.

    Args:
        explicit_district: 화면 입력 또는 요청 JSON에서 전달된 지역 값입니다.
        text: 민원 제목과 상세 본문을 결합한 문자열입니다.

    Returns:
        (적용할 구 이름, 본문에서 자동 추론되었는지 여부) 튜플입니다.
    """
    normalized = normalize_district(explicit_district)
    if normalized:
        return normalized, False

    inferred = extract_district(text)
    if inferred:
        return inferred, True

    return None, False


def resolve_district_and_place(
    explicit_district: str | None, text: str
) -> tuple[str | None, bool, dict[str, Any] | None]:
    """관할 구 결정과 장소 추적을 한 번에 수행해 중복 지도 조회를 방지합니다.

    명시적 구 선택과 정규식 매칭 모두에서 구가 정해지지 않았을 때도 네이버 지도
    검색을 1회만 호출하여 추론된 구와 `inferred_place`를 함께 반환합니다.

    Args:
        explicit_district: 화면 입력 또는 요청 JSON에서 전달된 지역 값입니다.
        text: 민원 제목과 상세 본문을 결합한 문자열입니다.

    Returns:
        `(적용할 구 이름, 본문에서 자동 추론되었는지 여부, 청주시 장소 정보)` 튜플입니다.
    """
    normalized = normalize_district(explicit_district)
    if normalized:
        place = _lookup_cheongju_place(text)
        return normalized, False, place

    regex_district, conflicted = _find_regex_district(text)
    if conflicted:
        place = _lookup_cheongju_place(text)
        return None, False, place
    if regex_district:
        place = _lookup_cheongju_place(text)
        return regex_district, True, place

    # 청주시 지명이 없고 명백한 타 지자체 관할 주소만 있으면 네이버 지도 오매칭을 막기 위해 조회를 건너뜁니다.
    if extract_external_jurisdiction(text, cheongju_area_found=False) is not None:
        return None, False, None

    place = _lookup_cheongju_place(text)
    inferred_gu = place.get("gu") if place else None
    if isinstance(inferred_gu, str) and inferred_gu:
        return inferred_gu, True, place

    return None, False, place
