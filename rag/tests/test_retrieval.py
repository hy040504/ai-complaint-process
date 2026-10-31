"""원본 보존·검색 본문·부서 경계와 검색 순위 결합을 검증합니다."""
import copy
import json

import pytest

from rag.config import CASES_JSON, FAQ_JSON
from rag.data import case_text, department_id, faq_text, infer_district, load_sources
from rag.korean import KoreanTokenizer
from rag.search import department_candidates, reciprocal_rank_fusion


@pytest.fixture(scope="module")
def sources():
    """모듈 내 테스트에서 재사용할 원본과 검색 문서를 읽습니다.

    Returns:
        검색 문서·부서 디렉터리·원본 사례 목록의 튜플입니다.
    """
    return load_sources()


def test_every_source_survives_and_unknown_departments_are_not_candidates(sources):
    """원본 항목이 보존되고 미확인 부서는 후보에서 제외되는지 검증합니다.

    Args:
        sources: 원본에서 구성한 검색 문서·부서 사전·사례를 제공하는 픽스처입니다.
    """
    docs, departments, cases = sources
    faq = json.loads(FAQ_JSON.read_text(encoding="utf-8"))
    assert len(docs) == sum(len(rows) for rows in faq.values()) + len(cases)
    assert len({(d["corpus"], d["source_id"]) for d in docs}) == len(docs)
    current_ids = {d["department_id"] for d in departments}
    for doc in docs:
        if doc["corpus"] == "routing":
            if doc["payload"]["department_status"] == "review_required":
                assert doc["department_id"] is None
                assert not doc["routing_eligible"]
            else:
                assert doc["department_id"] in current_ids


def test_faq_conditions_and_reception_channels_are_preserved(sources):
    """건축 조건·접수처가 보존되고 본문 구성이 원본을 수정하지 않는지 검증합니다.

    Args:
        sources: 원본에서 구성한 검색 문서·부서 사전·사례를 제공하는 픽스처입니다.
    """
    docs, _, _ = sources
    building = next(d for d in docs if d["source_id"] == "1304815")
    text = building["search_text"]
    assert "6층 이하" in text and "7층 이상" in text
    assert "2,000" in text
    assert building["payload"]["detail"]["received_by"]
    for doc in docs:
        if doc["corpus"] != "faq":
            continue
        original = doc["payload"]
        before = copy.deepcopy(original)
        faq_text(original)
        assert original == before


def test_historical_answers_and_department_labels_do_not_leak_into_search():
    """과거 답변과 부서명이 검색 본문에 섞이지 않는지 검증합니다."""
    record = {"title": "도로 파임", "summary": "", "resolution": "비밀 표지: 과거 답변",
              "department_current": "흥덕구 건설과"}
    assert case_text(record) == "민원 제목: 도로 파임"
    assert "과거 답변" not in case_text(record)
    assert "건설과" not in case_text(record)


def test_district_departments_have_different_stable_ids():
    """구가 다른 부서의 ID를 구별하고 이름 기반 구 추출을 검증합니다."""
    assert department_id("흥덕구 건설과") != department_id("청원구 건설과")
    assert department_id("흥덕구 건설과") == department_id("흥덕구 건설과")
    assert infer_district("흥덕구 건설과") == "흥덕구"
    assert infer_district("청원보건소") == "청원구"
    assert infer_district("건설교통국 도로시설과") is None


def test_directory_does_not_invent_official_duties(sources):
    """부서 별칭을 유지하고 공식 업무·자동 이관 상태를 임의로 확정하지 않는지 검증합니다.

    Args:
        sources: 원본에서 구성한 검색 문서·부서 사전·사례를 제공하는 픽스처입니다.
    """
    _, departments, _ = sources
    assert all(d["duty_description"] is None and d["duty_status"] == "unverified" for d in departments)
    transit = next(d for d in departments if d["canonical_name"] == "건설교통국 대중교통과")
    assert "대중교통과" in transit["aliases"]
    assert all(not d["automatic_routing_ready"] for d in departments)


def test_rrf_uses_ranks_not_incompatible_score_scales():
    """RRF가 서로 다른 점수의 크기 대신 순위로 결합하는지 검증합니다."""
    dense = [{"source_id": "a", "score": .9}, {"source_id": "shared", "score": .8}]
    lexical = [{"source_id": "b", "score": 500}, {"source_id": "shared", "score": 20}]
    fused = reciprocal_rank_fusion(dense, lexical)
    assert fused[0]["source_id"] == "shared"
    assert len(fused) == 3
    assert fused[0]["vector_rank"] == 2 and fused[0]["bm25_rank"] == 2


def test_department_evidence_never_becomes_automatic_transfer():
    """사례 근거만으로 자동 이관이 허용되지 않는지 검증합니다."""
    valid = {"rank": 1, "source_id": "1", "source_url": "https://example.test/1",
             "routing_eligible": True,
             "department": {"department_id": "d1", "canonical_name": "흥덕구 건설과", "duty_status": "unverified"}}
    unknown = {"rank": 2, "source_id": "2", "routing_eligible": False, "department": None}
    result = department_candidates([valid, unknown])
    assert len(result) == 1
    assert not result[0]["automatic_transfer"]
    assert result[0]["duty_status"] == "unverified"


def test_duplicate_source_fails_before_any_database_write(tmp_path):
    """출처 ID 중복을 DB 기록 전에 거부하는지 검증합니다.

    Args:
        tmp_path: 변형한 FAQ 원본을 저장할 임시 디렉터리입니다.
    """
    faqs = json.loads(FAQ_JSON.read_text(encoding="utf-8"))
    key = next(k for k, records in faqs.items() if records)
    faqs[key].append(copy.deepcopy(faqs[key][0]))
    path = tmp_path / "faq.json"
    path.write_text(json.dumps(faqs))
    with pytest.raises(ValueError, match="중복"):
        load_sources(faq_path=path)


def test_inconsistent_current_department_fails(tmp_path):
    """현행 부서와 검토 상태가 불일치하는 원본을 거부하는지 검증합니다.

    Args:
        tmp_path: 변형한 공개 사례 원본을 저장할 임시 디렉터리입니다.
    """
    cases = json.loads(CASES_JSON.read_text(encoding="utf-8"))
    cases[0]["department_status"] = "review_required"
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(cases))
    with pytest.raises(ValueError, match="불일치"):
        load_sources(cases_path=path)


def test_kiwi_keeps_bus_number_and_strips_korean_particles():
    """버스 번호·업무 명사는 유지하고 한국어 조사는 제외하는지 검증합니다."""
    tokens = KoreanTokenizer().tokens("711번 버스가 정류장을 그냥 지나갔어요.")
    assert {"711", "버스", "정류장"}.issubset(tokens)
    assert "버스가" not in tokens and "정류장을" not in tokens
