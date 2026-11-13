"""지명 정규화 및 본문 자치구 추론 모듈(src.assist.district) 단위 테스트입니다."""

from src.assist.district import (
    DISTRICT_AREAS,
    DISTRICTS,
    extract_district,
    normalize_district,
    resolve_complaint_district,
)


def test_district_constants():
    """청주시 4개 구와 하위 지역 매핑 상수가 올바르게 정의되어 있는지 확인합니다."""
    assert len(DISTRICTS) == 4
    assert set(DISTRICTS) == {"상당구", "서원구", "흥덕구", "청원구"}
    assert set(DISTRICT_AREAS.keys()) == set(DISTRICTS)
    for district, areas in DISTRICT_AREAS.items():
        assert len(areas) >= 10, f"{district} 산하 지명이 충분해야 합니다."


def test_normalize_district_exact():
    """정확한 구 명칭이 들어왔을 때 그대로 정규화되는지 확인합니다."""
    assert normalize_district("상당구") == "상당구"
    assert normalize_district("서원구") == "서원구"
    assert normalize_district("흥덕구") == "흥덕구"
    assert normalize_district("청원구") == "청원구"
    assert normalize_district("흥덕") == "흥덕구"
    assert normalize_district("") is None
    assert normalize_district(None) is None


def test_normalize_district_with_area():
    """세부 지역 또는 구분자가 포함된 문자열이 상위 구로 정규화되는지 확인합니다."""
    assert normalize_district("흥덕구:오송읍") == "흥덕구"
    assert normalize_district("흥덕구 오송읍") == "흥덕구"
    assert normalize_district("오송읍") == "흥덕구"
    assert normalize_district("가경동") == "흥덕구"
    assert normalize_district("분평동") == "서원구"
    assert normalize_district("사창동") == "서원구"
    assert normalize_district("율량동") == "청원구"
    assert normalize_district("오창읍") == "청원구"
    assert normalize_district("금천동") == "상당구"
    assert normalize_district("용암동") == "상당구"


def test_extract_district_single_match():
    """제목이나 본문에 지명이 단일하게 포함되어 있을 때 정확히 구를 추론하는지 확인합니다."""
    # 구 이름 명시
    assert extract_district("흥덕구 복대동 사거리 포트홀 신고합니다") == "흥덕구"
    assert extract_district("서원구 분평동 가로등이 나갔어요") == "서원구"

    # 동·읍·면만 명시
    assert extract_district("오송읍 원룸 단지 쓰레기 무단 투기") == "흥덕구"
    assert extract_district("가경동 터미널 앞 불법주차 단속 요청") == "흥덕구"
    assert extract_district("사창동 충북대 중문 소음이 심해요") == "서원구"
    assert extract_district("오창읍 호수공원 근처 도로 파손") == "청원구"
    assert extract_district("율량동 어린이공원 시설 보수") == "청원구"
    assert extract_district("금천동 행정복지센터 앞 인도 보도블록") == "상당구"
    assert extract_district("문의면 대청호 주변 안전 펜스 설치") == "상당구"


def test_extract_district_with_particles():
    """조사가 결합된 경우에도 자연스럽게 인식하는지 확인합니다."""
    assert extract_district("복대동에서 가경동으로 가는 길입니다") == "흥덕구"
    assert extract_district("오창읍에 가로등을 추가 설치해 주세요") == "청원구"
    assert extract_district("산남동의 도로에 싱크홀이 생겼습니다") == "서원구"
    assert extract_district("용암동은 청소가 필요합니다") == "상당구"


def test_extract_district_conflict_and_none():
    """지명이 없거나 서로 다른 2개 이상의 구가 상충할 때 None을 반환하는지 확인합니다."""
    # 지명 없음
    assert extract_district("청주시 도로에 포트홀이 생겼어요") is None
    assert extract_district("") is None

    # 서로 다른 구가 동시에 등장하는 경우 (충돌 방지)
    assert extract_district("상당구에서 흥덕구로 이사했습니다") is None
    assert extract_district("오송읍에서 오창읍으로 출퇴근하는 버스 노선") is None
    assert extract_district("가경동과 사창동 경계 도로 문의") is None


def test_resolve_complaint_district():
    """명시적 선택 우선 및 본문 추론 폴백 동작을 확인합니다."""
    # 명시적 선택이 있으면 본문과 상관없이 명시적 선택 적용
    district, inferred = resolve_complaint_district(
        "서원구", "흥덕구 가경동에 포트홀이 있습니다"
    )
    assert district == "서원구"
    assert inferred is False

    # 세부 지역 명시 선택 시 상위 구로 정규화
    district, inferred = resolve_complaint_district(
        "흥덕구:오송읍", "도로가 파손되었습니다"
    )
    assert district == "흥덕구"
    assert inferred is False

    # 명시적 선택이 없으면 본문에서 자동 추론
    district, inferred = resolve_complaint_district(
        None, "가경동 터미널 근처 소음 문제입니다"
    )
    assert district == "흥덕구"
    assert inferred is True

    # 명시적 선택도 없고 본문에도 지명이 없으면 None
    district, inferred = resolve_complaint_district(
        "", "시내 도로에 신호등이 고장 났습니다"
    )
    assert district is None
    assert inferred is False


def test_resolve_district_and_place_single_lookup(monkeypatch) -> None:
    """관할 구와 장소 추적을 함께 풀 때 네이버 지도 검색을 1회만 호출하는지 확인합니다."""
    from src.assist.district import resolve_district_and_place
    import src.llm.place_tool as place_tool

    calls: list[str] = []

    def fake_lookup(query: str, coords: str | None = None, **kwargs):
        calls.append(query)
        return {
            "query": query,
            "found": True,
            "total": 1,
            "primary_place": {
                "title": "창신초등학교",
                "road_address": "충청북도 청주시 서원구 구룡산로 330",
                "jibun_address": "충청북도 청주시 서원구 사직동 622",
                "gu": "서원구",
                "dong": "사직동",
                "is_cheongju": True,
            },
            "places": [],
        }

    monkeypatch.setattr(place_tool, "lookup_navermap_place", fake_lookup)

    district, inferred, place = resolve_district_and_place(
        None, "창신초등학교 앞 보도블럭이 파손됐어요"
    )
    assert district == "서원구"
    assert inferred is True
    assert place is not None and place["title"] == "창신초등학교"
    assert len(calls) == 1

    # 명시적 구가 있어도 장소 배지는 유지하되 district_inferred는 False입니다.
    district2, inferred2, place2 = resolve_district_and_place(
        "흥덕구", "창신초등학교 근처 문의"
    )
    assert district2 == "흥덕구"
    assert inferred2 is False
    assert place2 is not None and place2["title"] == "창신초등학교"
    assert len(calls) == 2

