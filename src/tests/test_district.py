"""지명 정규화 및 본문 자치구 추론 모듈(src.assist.district) 단위 테스트입니다."""

from __future__ import annotations

import pytest

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
        """테스트용 고정 네이버 지도 조회 응답을 반환합니다."""
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


def test_extract_district_no_space_numbers_and_landmarks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """동+숫자 붙여쓰기(B17·코퍼스)와 주요 랜드마크(B06·F12)를 외부 API 없이 추론합니다."""
    import src.llm.place_tool as place_tool

    # 외부 네이버 검색이 비어 있어도 정규식·내장 랜드마크로 정확히 판별되어야 합니다.
    monkeypatch.setattr(
        place_tool,
        "lookup_navermap_place",
        lambda query, **_kwargs: {
            "query": query,
            "found": False,
            "total": 0,
            "primary_place": None,
            "places": [],
        },
    )

    assert extract_district("봉명동1349근처빗물받이막힘청소요청") == "흥덕구"
    assert extract_district("송정동70-60 앞 도로 파손 신고") == "흥덕구"
    assert extract_district("분평동4거리 신호등 고장 점검") == "서원구"
    assert extract_district("가경동2270 인근 불법주차 단속") == "흥덕구"
    assert extract_district("청주시봉명동1349 도로 침하") == "흥덕구"

    assert extract_district("청주국제공항 진입로 부근 도로 포트홀 보수") == "청원구"
    assert extract_district("청주 문암생태공원 화장실 방치 민원") == "흥덕구"
    assert extract_district("내수읍내수시장옆골목불법소각신고") == "청원구"
    assert extract_district("청주고인쇄박물관 맞은편 인도 보수 요청") == "흥덕구"
    assert extract_district("청남대 매표소 입구 근처 도로 가로등 파손 점검") == "상당구"
    assert extract_district("북이면 초정행궁 근처 도로변 불법현수막") == "청원구"

    # 다중 구 충돌(오송읍 ↔ 오창읍, 상당구 ↔ 서원구 무심천)은 단일 구로 강제하지 않습니다.
    assert extract_district("상당구와 서원구 경계 무심천 자전거도로 점검") is None
    assert extract_district("오송읍에서 오창읍으로 가는 버스 배차 문의") is None
    assert (
        extract_district("동네 어딘가 학교 앞 골목 가로등 고장 (지역 미기재)") is None
    )


def test_external_jurisdiction_prevents_homonym_dong_and_place_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """타 지자체 주소에 청주와 동명이인 동('봉명동'·'사직동'·'중앙동')이 있어도 오인하지 않습니다."""
    from src.assist.district import (
        extract_external_jurisdiction,
        resolve_district_and_place,
    )
    import src.llm.place_tool as place_tool

    called = 0

    def fail_if_called(query: str, **_kwargs: object) -> dict[str, object]:
        nonlocal called
        called += 1
        return {
            "query": query,
            "found": False,
            "total": 0,
            "primary_place": None,
            "places": [],
        }

    monkeypatch.setattr(place_tool, "lookup_navermap_place", fail_if_called)

    assert extract_district("대전 유성구 봉명동 123 도로 포트홀 보수") is None
    assert extract_district("서울특별시 종로구 사직동 가로등 수리 요청") is None
    assert extract_district("대구 수성구 중앙동 불법주정차 단속") is None
    assert extract_district("천안시 동남구 봉명동 인도 침하") is None

    assert (
        extract_external_jurisdiction("대전 유성구 봉명동 도로 파손") == "대전 유성구"
    )
    assert (
        extract_external_jurisdiction("세종시 조치원읍 가로등 수리")
        == "세종시 조치원읍"
    )
    # 청주시 연계 민원은 타 지자체가 함께 언급되어도 제외하지 않고 청주 구를 정상 인식합니다.
    assert (
        extract_external_jurisdiction("서울 쓰레기를 왜 청주시에서 처리하나요?") is None
    )
    assert (
        extract_district("서울 강남에서 온 물품 관련 청주시 서원구 사직동 문의")
        == "서원구"
    )

    dist, inferred, place = resolve_district_and_place(
        None, "대전 유성구 봉명동 도로 포트홀 보수"
    )
    assert dist is None
    assert inferred is False
    assert place is None
    assert called == 0


def test_single_gu_roads_closing_bracket_external_shortnames_and_residence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """닫는 괄호·단일구 도로명·광역시 약칭·운수예외·거주지 문맥 분리를 검증합니다."""
    from src.assist.district import (
        extract_external_jurisdiction,
        resolve_district_and_place,
    )
    import src.llm.place_tool as place_tool

    looked_up: list[str] = []

    def fake_lookup(query: str, **_kwargs: object) -> dict[str, object]:
        """서원대 질의에만 청주 장소 응답을 돌려주는 가짜 지도 조회기입니다."""
        looked_up.append(query)
        if "서원대" in query:
            return {
                "query": query,
                "found": True,
                "total": 1,
                "primary_place": {
                    "title": "서원대학교후문",
                    "road_address": "충청북도 청주시 서원구 무심서로 377-3",
                    "jibun_address": "충청북도 청주시 서원구 모충동 243-18",
                    "gu": "서원구",
                    "dong": "모충동",
                    "is_cheongju": True,
                },
                "places": [],
            }
        return {
            "query": query,
            "found": False,
            "total": 0,
            "primary_place": None,
            "places": [],
        }

    monkeypatch.setattr(place_tool, "lookup_navermap_place", fake_lookup)

    # 닫는 괄호 경계 및 공개 사례 검증 단일구 순수 도로명
    assert extract_district("긴급)복대동 영조2차 아파트 앞 가로수") == "흥덕구"
    assert extract_district("오송생명14로 283 주변 불법주차") == "흥덕구"
    assert extract_district("충청대로 233 볼록거울 설치") == "청원구"
    assert extract_district("성안길 상가 앞 보도블록 점검") == "상당구"

    # 광역시 '~시' 약칭 및 외부 도로명 주소 차단 + 지도 검색 0회
    for ext_text in (
        "서울시 종로구 사직동 도로 포트홀 보수",
        "대전시 유성구 봉명동 가로등 고장",
        "경기도 화성시 동탄대로 123 보도블록 파손",
    ):
        assert extract_external_jurisdiction(ext_text) is not None
        d, inf, p = resolve_district_and_place(None, ext_text)
        assert (d, inf, p) == (None, False, None)
    assert looked_up == []

    # 청주시 시내버스 운수사는 인접 시·군 운행 구간 표기만으로 차단하지 않음 (사례 913 유형)
    transit_text = "충북 증평군 증평읍 북부두름길 80 청신운수 109 급행버스 난폭운전"
    assert extract_external_jurisdiction(transit_text) is None

    # 타지 주소 직후 '이사/사는데' 거주 술어가 있으면 청주시 현 거주지·뒷부분 장소를 정상 추론
    moved_text = "서울 강남구 역삼동에서 이사왔는데 여기 봉명동1349 앞 가로등 고장"
    d_moved, inf_moved, _ = resolve_district_and_place(None, moved_text)
    assert d_moved == "흥덕구"
    assert inf_moved is True
    assert looked_up[-1].startswith("여기 봉명동1349")

    residence_text = "대전 유성구 봉명동 사는데 서원대 후문 앞에 쓰레기가 많아요"
    d_res, inf_res, p_res = resolve_district_and_place(None, residence_text)
    assert d_res == "서원구"
    assert inf_res is True
    assert p_res is not None and p_res["title"] == "서원대학교후문"
    assert "대전 유성구" not in looked_up[-1]
