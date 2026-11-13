"""네이버 지도 장소 주소 추적 도구 단위 테스트입니다.

비로그인 상태의 네이버 지도 인스턴트 검색을 이용한 주소 및 청주시 구/동
추출 동작, 모의 응답 정제, 예외 처리를 검증합니다.
"""

from __future__ import annotations

import pytest

from src.llm.place_tool import (
    PLACE_TOOL_NAME,
    extract_cheongju_district,
    extract_cheongju_dong,
    lookup_navermap_place,
)


def test_extract_cheongju_district() -> None:
    """청주시 4개 구(상당구, 서원구, 흥덕구, 청원구) 이름을 올바르게 추출합니다."""
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
    assert is_place_relevant("모모랩 청주시내성안길본점", "시내 도로에 신호등이 고장 났습니다") is False
    assert is_place_relevant("창신초등학교", "창신초") is True
    assert is_place_relevant("", "서원대학교") is False


def test_lookup_navermap_place_fallback_candidates() -> None:
    """문장형 검색 시 1차 결과가 없으면 후보 키워드로 fallback 검색하여 청주시 장소를 반환합니다."""
    def mock_fetch(query: str, coords: str = "") -> dict:
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

    res = lookup_navermap_place("청주 서원대학교 후문 편의점근처에서 나무가 쓰러짐", fetch_fn=mock_fetch)
    assert res["found"] is True
    assert res["primary_place"] is not None
    assert res["primary_place"]["title"] == "서원대학교후문"
    assert res["primary_place"]["gu"] == "서원구"
    assert res["primary_place"]["dong"] == "모충동"


def test_lookup_navermap_place_bounds_fallback_recursion() -> None:
    """보완 검색은 1단계 후보 최대 상한까지만 수행하고 재귀 폭발하지 않아야 합니다."""
    called_queries: list[str] = []

    def empty_fetch(query: str, coords: str = "") -> dict:
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



