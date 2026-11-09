"""청주시 행정구역(4개 구 및 관할 읍·면·동) 지명 정규화와 본문 지명 추출기입니다.

민원 제목과 상세 본문에서 청주시 관할 구와 동·읍·면을 감지하여
검색 API의 `district` 필터로 안전하게 연결합니다. 복수 구가 감지되거나
충돌하면 필터를 걸지 않고 None을 반환합니다.
"""

from __future__ import annotations

import re
from typing import Final

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

# 동·읍·면 패턴: 앞뒤 단어 경계(공백, 문장부호 등)와 결합 조사 고려
_AREA_PATTERN = re.compile(
    r"(?:(?<=[\s\(\[\{<\"'.,~·/!?-])|^)("
    + "|".join(re.escape(a) for a in _SORTED_AREAS)
    + r")(?:에서|으로|[은는이가을를의에로와과도만]?)(?=\s|[^\w가-힣]|$)"
)


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

    found_districts: set[str] = set()

    # 1. 구 이름 명시 탐색 ('상당구', '서원구', '흥덕구', '청원구')
    for match in _DISTRICT_PATTERN.finditer(text):
        found_districts.add(match.group(1))
        if len(found_districts) > 1:
            return None

    # 2. 읍·면·동 지명 탐색
    for match in _AREA_PATTERN.finditer(text):
        area_name = match.group(1)
        if area_name in _AREA_TO_DISTRICT:
            found_districts.add(_AREA_TO_DISTRICT[area_name])
            if len(found_districts) > 1:
                return None

    # 3. 오직 하나의 구만 발견된 경우에만 확정 반환
    if len(found_districts) == 1:
        return next(iter(found_districts))

    return None


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
