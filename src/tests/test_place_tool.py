"""네이버 지도 장소 주소 추적 도구 단위 테스트입니다.

비로그인 상태의 네이버 지도 인스턴트 검색을 이용한 주소 및 청주시 구/동
추출 동작, 모의 응답 정제, 예외 처리를 검증합니다.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.llm.place_tool import (
    PLACE_TOOL_NAME,
    extract_cheongju_district,
    extract_cheongju_dong,
    extract_place_candidates,
    is_place_relevant,
    lookup_navermap_place,
)


def test_extract_cheongju_district() -> None:
    """장소 추적 도구 상수와 청주시 4개 구 이름을 올바르게 검증합니다."""
    assert PLACE_TOOL_NAME == "lookup_navermap_place"
    assert extract_cheongju_district("충청북도 청주시 서원구 사창동 351") == "서원구"
    assert extract_cheongju_district("충북 청주시 상당구 상당로 143") == "상당구"
    assert extract_cheongju_district("청주시 흥덕구 복대동 288-1") == "흥덕구"
    assert extract_cheongju_district("청원구 오창읍 양청리 820") == "청원구"
    # 청주시 구가 아닌 경우
    assert extract_cheongju_district("서울특별시 종로구 세종대로 209") is None
    assert extract_cheongju_district("경기도 수원시 팔달구 매산로") is None
    assert extract_cheongju_district("") is None
    assert extract_cheongju_district(None) is None


def test_extract_cheongju_dong() -> None:
    """주소에서 동, 읍, 면, 가 단위를 올바르게 추출합니다."""
    assert extract_cheongju_dong("충청북도 청주시 서원구 사창동 351") == "사창동"
    assert extract_cheongju_dong("청원구 오창읍 양청리") == "오창읍"
    assert extract_cheongju_dong("상당구 남일면 효촌리") == "남일면"
    assert extract_cheongju_dong("상당구 북문로1가 12") == "북문로1가"
    assert extract_cheongju_dong("1순환로709번길 44") is None
    assert extract_cheongju_dong("") is None
    assert extract_cheongju_dong(None) is None


def test_lookup_navermap_place_rejects_empty_query() -> None:
    """빈 검색어는 ValueError를 일으킵니다."""
    with pytest.raises(ValueError, match="비어"):
        lookup_navermap_place("   ")


def test_lookup_navermap_place_with_mock_results() -> None:
    """모의 검색 응답을 받아 청주시 장소를 최우선으로 정제합니다."""
    called_count = 0

    def mock_fetch(query: str, coords: str) -> dict:
        """캐시 적중 여부를 검증하기 위해 호출 횟수를 세고 고정 장소 JSON을 반환합니다."""
        nonlocal called_count
        called_count += 1
        return {
            "place": [
                {
                    "title": "<b>창신초등학교</b>",
                    "roadAddress": "충청북도 청주시 서원구 1순환로709번길 44",
                    "jibunAddress": "충청북도 청주시 서원구 사창동 351",
                    "x": "127.4643881",
                    "y": "36.629467",
                    "ctg": "초등학교",
                },
                {
                    "title": "창신초등학교",
                    "roadAddress": "서울특별시 종로구 지봉로 73",
                    "jibunAddress": "서울특별시 종로구 창신동 128-32",
                    "x": "127.0145551",
                    "y": "37.5760844",
                    "ctg": "초등학교",
                },
            ]
        }

    res = lookup_navermap_place("창신초", fetch_fn=mock_fetch)
    assert called_count == 1
    assert res["found"] is True
    assert res["total"] == 2

    # 청주시 장소가 primary_place로 선정되었는지 검증
    primary = res["primary_place"]
    assert primary is not None
    assert primary["title"] == "창신초등학교"  # HTML 태그 제거 확인
    assert primary["gu"] == "서원구"
    assert primary["dong"] == "사창동"
    assert primary["road_address"] == "충청북도 청주시 서원구 1순환로709번길 44"
    assert primary["is_cheongju"] is True


def test_lookup_navermap_place_handles_fetch_exception() -> None:
    """네트워크나 원격 API 오류 발생 시 예외를 던지지 않고 안전한 에러 객체를 반환합니다."""

    def failing_fetch(_query: str, coords: str = "") -> dict:
        """네트워크 연결 실패 상황을 재현하는 모의 검색 함수입니다."""
        raise OSError("네트워크 연결 실패")

    res = lookup_navermap_place("없는장소", fetch_fn=failing_fetch)
    assert res["found"] is False
    assert res["total"] == 0
    assert res["primary_place"] is None
    assert "error" in res
    assert "네트워크 연결 실패" in res["error"]


def test_lookup_navermap_place_cache_hit() -> None:
    """동일한 장소를 반복 검색할 때 모의 호출 없이 캐시를 반환합니다."""
    called_count = 0

    def mock_fetch(query: str, coords: str = "") -> dict:
        """검색어 관련성과 무관 장소 필터링 검증용 모의 장소 목록을 반환합니다."""
        nonlocal called_count
        called_count += 1
        return {
            "place": [
                {
                    "title": "청주시청",
                    "roadAddress": "충청북도 청주시 상당구 상당로 143",
                    "jibunAddress": "충청북도 청주시 상당구 북문로3가 89-1",
                    "x": "127.4890319",
                    "y": "36.6424341",
                    "ctg": "시청",
                }
            ]
        }

    first = lookup_navermap_place("청주시청테스트", fetch_fn=mock_fetch)
    assert called_count == 1
    assert first["found"] is True
    assert first["primary_place"]["gu"] == "상당구"

    # 기본 캐시 검증을 위해 fetch_fn 없이 다시 호출하기 전 임의 캐시에 주입 확인
    from src.llm.place_tool import _PLACE_CACHE

    cache_key = "청주시청테스트|36.6424341,127.4890319"
    _PLACE_CACHE[cache_key] = first
    cached = lookup_navermap_place("청주시청테스트")
    assert cached["primary_place"]["gu"] == "상당구"


def test_extract_place_candidates() -> None:
    """긴 민원 문장에서 불용어와 조사를 제거하고 검색 가능한 장소 후보를 추출합니다."""
    from src.llm.place_tool import extract_place_candidates

    text = "청주 서원대학교 후문 편의점근처에서 나무가 쓰러짐"
    candidates = extract_place_candidates(text)
    assert "서원대학교 후문" in candidates
    assert "서원대학교" in candidates
    assert "나무가" not in candidates
    assert "쓰러짐" not in candidates

    # 지명 후보가 없는 일반 민원 문장은 빈 목록 반환
    plain_text = "시내 도로에 신호등이 고장 났습니다"
    assert extract_place_candidates(plain_text) == []


def test_is_place_relevant() -> None:
    """검색 결과의 제목과 검색 키워드의 관련성 검증 동작을 확인합니다."""
    from src.llm.place_tool import is_place_relevant

    assert is_place_relevant("서원대학교후문", "서원대학교 후문") is True
    assert (
        is_place_relevant(
            "모모랩 청주시내성안길본점", "시내 도로에 신호등이 고장 났습니다"
        )
        is False
    )
    assert is_place_relevant("창신초등학교", "창신초") is True
    assert is_place_relevant("", "서원대학교") is False


def test_lookup_navermap_place_fallback_candidates() -> None:
    """문장형 검색 시 1차 결과가 없으면 후보 키워드로 fallback 검색하여 청주시 장소를 반환합니다."""

    def mock_fetch(query: str, coords: str = "") -> dict:
        """긴 문장 검색은 비워 두고 정제 후보 검색에만 서원대 후문을 반환합니다."""
        # 문장 전체 검색 시에는 일치 장소 없음
        if "나무가" in query or len(query.split()) > 3:
            return {"place": []}
        # 정제된 후보 키워드로 검색 시 서원대학교 후문 반환
        if "서원대학교" in query:
            return {
                "place": [
                    {
                        "title": "서원대학교후문",
                        "roadAddress": "충청북도 청주시 서원구 무심서로 377-3",
                        "jibunAddress": "충청북도 청주시 서원구 모충동 243-18",
                        "x": "127.4818259",
                        "y": "36.6232074",
                        "ctg": "방면정보",
                    }
                ]
            }
        return {"place": []}

    res = lookup_navermap_place(
        "청주 서원대학교 후문 편의점근처에서 나무가 쓰러짐", fetch_fn=mock_fetch
    )
    assert res["found"] is True
    assert res["primary_place"] is not None
    assert res["primary_place"]["title"] == "서원대학교후문"
    assert res["primary_place"]["gu"] == "서원구"
    assert res["primary_place"]["dong"] == "모충동"


def test_lookup_navermap_place_bounds_fallback_recursion() -> None:
    """보완 검색은 1단계 후보 최대 상한까지만 수행하고 재귀 폭발하지 않아야 합니다."""
    called_queries: list[str] = []

    def empty_fetch(query: str, coords: str = "") -> dict:
        """실제 호출된 후보 검색어를 기록하고 빈 장소 목록을 돌려줍니다."""
        called_queries.append(query)
        return {"place": []}

    res = lookup_navermap_place(
        "가나다라 마바사아 자차카타 파하가나 교차로 정문 입구",
        fetch_fn=empty_fetch,
    )
    assert res["found"] is False
    assert res["primary_place"] is None
    # 최초 원문 1회 + 1단계 보완 후보 최대 5회 = 최대 6회 이내여야 합니다.
    assert len(called_queries) <= 6
    assert called_queries[0] == "가나다라 마바사아 자차카타 파하가나 교차로 정문 입구"


def test_place_tool_filters_generic_faq_nouns_and_prioritizes_landmarks() -> None:
    """보고서 3순위 일반명사 오매칭 차단(A04·A07·B12·C15)과 고유 접미어 우선정렬(B06·F12)을 확인합니다."""
    from src.llm.place_tool import extract_place_candidates, is_place_relevant

    # B06·F12: 앞쪽 일반/수식 어구가 길어도 공항·생태공원 접미어 후보가 5후보 컷오프 안쪽에 우선 배치
    airport_cands = extract_place_candidates(
        "장기간 방치된 야간 우천 시 차량 통행 불편 청주국제공항 진입로 부근 도로 포트홀 보수"
    )
    assert "청주국제공항" in airport_cands[:5]

    park_cands = extract_place_candidates(
        "주말 가족 나들이 이용객이 많은 청주 문암생태공원 화장실 방치 민원"
    )
    assert "문암생태공원" in park_cands[:5]

    # 일반 행정·FAQ·모호 민원은 후보가 비거나 엉뚱한 상점 오매칭이 차단되어야 합니다.
    assert extract_place_candidates("1. 여권 발급 방문 신청 방법 안내") == []
    assert (
        extract_place_candidates("동네 어딘가 학교 앞 골목 가로등 고장 (지역 미기재)")
        == []
    )
    assert (
        is_place_relevant(
            "한국방송통신대학교 충북지역대학",
            "동네 어딘가 학교 앞 골목 가로등 고장 (지역 미기재)",
        )
        is False
    )
    assert (
        is_place_relevant(
            "상하목장신청주유기농DS대리점",
            "미성년자(8세 미만) 여권 대리 신청 및 비용",
        )
        is False
    )
    assert (
        is_place_relevant(
            "무료배달렌트카 오창점",
            "청년희망날개 면접 정장 무료 대여 조건",
        )
        is False
    )
    assert (
        is_place_relevant(
            "코웨이 청주코웨이렌탈공식접수센터",
            "존재하지 않는 부서명·내선번호로 공식 접수 확인 요구",
        )
        is False
    )
    # 2글자 상호가 긴 행정 명사 일부에 우연히 들어가는 오탐도 차단합니다.
    assert is_place_relevant("원부", "자동차등록원부") is False


def test_lookup_navermap_place_skips_http_for_generic_faq_sentence() -> None:
    """장소 후보가 없는 3어절 이상 FAQ/일반 문장은 외부 HTTP 호출 없이 빈 결과를 반환합니다."""
    called = 0

    def should_not_call(_query: str, coords: str = "") -> dict[str, Any]:
        """외부 지도 API가 호출되지 않아야 함을 검증하는 가짜 조회 함수입니다."""
        nonlocal called
        called += 1
        return {"place": []}

    res = lookup_navermap_place(
        "미성년자(8세 미만) 여권 대리 신청 및 비용",
        fetch_fn=should_not_call,
    )
    assert called == 0
    assert res["found"] is False
    assert res["primary_place"] is None


def test_road_number_pairs_and_hyphen_splitting() -> None:
    """도로명+번지 결합 후보 최우선 배치, 문자 하이픈 분리 및 원인조사 불용어 배제를 확인합니다."""
    from src.llm.place_tool import extract_place_candidates

    road_num = extract_place_candidates("주말 주차단속 차량 소리 오송생명14로 283 앞")
    assert road_num[0] == "오송생명14로 283"

    ring_road = extract_place_candidates("2순환로 1374 버스정류승강장 하차문제")
    assert ring_road[0] == "2순환로 1374"

    sub_num = extract_place_candidates("호미로201번길 16-19 무단방치 차량 신고")
    assert sub_num[0] == "호미로201번길 16-19"

    hyphen_split = extract_place_candidates(
        "은행나무-바닥에은행에너무많이떨어져악취심함"
    )
    assert all(len(c) < 25 for c in hyphen_split)

    cause_words = extract_place_candidates("잦은 사고로 반사경 설치 해주세요")
    assert "사고로" not in cause_words


def test_address_section_ac_dong_adjacent_road_and_generic_place_guards() -> None:
    """address/ac 파싱, 인접 번지 탐침, 일반 시설·관공서·조사 결합 차단을 검증합니다."""
    from src.llm.place_tool import extract_place_candidates, is_place_relevant

    # 1. B12·A12·A18·C09·D11·D08 유형 오매칭 후보·관련성 차단
    b12_cands = extract_place_candidates(
        "동네 어딘가 학교 앞 골목 가로등 고장 정확한 이름은 기억나지 않는데 우리 동네 초등학교 앞 골목길 가로등이 깜빡거립니다"
    )
    assert "초등학교" not in b12_cands
    assert "우리 초등학교" not in b12_cands
    assert is_place_relevant("우암초등학교", "우리 초등학교") is False
    assert is_place_relevant("청주시로컬푸드직매장", "청주시로 전입신고") is False
    assert is_place_relevant("봉명동내커피 오송점", "흥덕구 봉명동 수도관") is False
    assert is_place_relevant("육거리종합시장", "용암동 시장") is False

    # 관공서는 청구/비판 문맥에서 제외하되 물리적 현장('앞' 등) 수식이 있으면 허용
    office_claim = extract_place_candidates(
        "지난주 대전 도로 파손으로 청주시청에 청구하면 전액 배상된다던데 어디로 내나요"
    )
    assert "청주시청" not in office_claim
    office_near = extract_place_candidates("청주시청 앞 횡단보도 보도블록이 깨졌어요")
    assert "청주시청" in office_near

    # 2. B23·B24 유형: place=[] 이어도 address + ac 괄호 동명에서 청주시 주소·구·동 추출
    def address_only_fetch(query: str, coords: str = "") -> dict[str, Any]:
        """네이버 address 및 ac 섹션만 포함한 모의 검색 응답을 반환합니다."""
        if "직지대로 874-2" in query:
            return {
                "ac": ["충청북도청주시청원구직지대로874-2(우암동)"],
                "place": [],
                "address": [
                    {
                        "title": "충북 청주시 청원구 직지대로 874-2 상당빌딩",
                        "fullAddress": "충청북도 청주시 청원구 직지대로 874-2",
                        "x": "127.4869975",
                        "y": "36.6504171",
                    }
                ],
            }
        return {"place": [], "address": []}

    addr_res = lookup_navermap_place(
        "직지대로 874-2 앞 보행로 보도블록이 침하되고 가로등이 꺼졌어요",
        fetch_fn=address_only_fetch,
    )
    assert addr_res["found"] is True
    assert addr_res["primary_place"]["gu"] == "청원구"
    assert addr_res["primary_place"]["dong"] == "우암동"
    assert addr_res["primary_place"]["category"] == "도로명주소"

    # 3. B22 유형: 원 번지 미등록 시 ±1 인접 번지 탐침으로 관할 구 추적
    def adjacent_road_fetch(query: str, coords: str = "") -> dict[str, Any]:
        """인접 번지 '2순환로 1375'에만 청주 결과를 반환하는 모의 검색 함수입니다."""
        if query == "2순환로 1375":
            return {
                "place": [
                    {
                        "title": "2순환로1375번길",
                        "roadAddress": None,
                        "jibunAddress": "충청북도 청주시 흥덕구 가경동",
                        "x": "127.43",
                        "y": "36.62",
                        "ctg": "도로명칭",
                    }
                ]
            }
        return {"place": [], "address": []}

    ring_res = lookup_navermap_place(
        "2순환로 1374 앞 주행차로 차선 도색 및 맨홀 소음 점검 바랍니다",
        fetch_fn=adjacent_road_fetch,
    )
    assert ring_res["found"] is True
    assert ring_res["primary_place"]["gu"] == "흥덕구"
    assert ring_res["primary_place"]["dong"] == "가경동"

    # 4. HTTP 400 제한 시 나머지 후보 5회 연쇄 재시도를 즉시 중단합니다.
    limit_calls: list[str] = []

    def http400_fetch(query: str, coords: str = "") -> dict[str, Any]:
        """HTTP 400 호출 제한 오류를 모사하는 가짜 검색 함수입니다."""
        limit_calls.append(query)
        raise OSError("HTTP Error 400: Bad Request")

    blocked = lookup_navermap_place(
        "가나다라 사거리 신호등 고장 수리 요청", fetch_fn=http400_fetch
    )
    assert blocked["found"] is False
    assert "error" in blocked
    assert len(limit_calls) <= 2


def test_municipal_drainage_and_facility_nouns_do_not_trigger_contractor_noise() -> (
    None
):
    """'하수구'·'과속방지턱' 등 생활 기반시설 일반명사가 민간 업체 오매칭 후보로 남지 않습니다."""
    n28_text = (
        "가경동 하수구 악취 방치 세금 낭비 조롱 시민 세금으로 놀고 먹는 건지 "
        "가경동 하수구 악취가 몇 달째 진동하는데 코 막고 출근하라는 겁니까? 청소하세요."
    )
    cands = extract_place_candidates(n28_text)
    assert all("하수구" not in c for c in cands)
    assert is_place_relevant("청주하수구막힘변기뚫음누수탐지", n28_text) is False

    speedbump_text = (
        "우리 동네 고등학교 앞 과속방지턱과 안전난간 가드레일 보수 요청합니다"
    )
    sb_cands = extract_place_candidates(speedbump_text)
    assert all(
        bad not in sb_cands
        for bad in ("과속방지턱", "안전난간", "가드레일", "고등학교")
    )
