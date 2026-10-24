import copy
import json

import pytest

from rag.config import ROOT
from rag.data import case_text, department_id, faq_text, infer_district, load_sources
from rag.korean import KoreanTokenizer
from rag.search import department_candidates, reciprocal_rank_fusion


@pytest.fixture(scope="module")
def sources():
    return load_sources()


def test_every_source_survives_and_unknown_departments_are_not_candidates(sources):
    docs, departments, cases = sources
    faq = json.loads((ROOT / "db/자주_묻는_민원.json").read_text())
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
    record = {"title": "도로 파임", "summary": "", "resolution": "비밀 표지: 과거 답변",
              "department_current": "흥덕구 건설과"}
    assert case_text(record) == "민원 제목: 도로 파임"
    assert "과거 답변" not in case_text(record)
    assert "건설과" not in case_text(record)


def test_district_departments_have_different_stable_ids():
    assert department_id("흥덕구 건설과") != department_id("청원구 건설과")
    assert department_id("흥덕구 건설과") == department_id("흥덕구 건설과")
    assert infer_district("흥덕구 건설과") == "흥덕구"
    assert infer_district("청원보건소") == "청원구"
    assert infer_district("건설교통국 도로시설과") is None


def test_directory_does_not_invent_official_duties(sources):
    _, departments, _ = sources
    assert all(d["duty_description"] is None and d["duty_status"] == "unverified" for d in departments)
    transit = next(d for d in departments if d["canonical_name"] == "건설교통국 대중교통과")
    assert "대중교통과" in transit["aliases"]
    assert all(not d["automatic_routing_ready"] for d in departments)


def test_rrf_uses_ranks_not_incompatible_score_scales():
    dense = [{"source_id": "a", "score": .9}, {"source_id": "shared", "score": .8}]
    lexical = [{"source_id": "b", "score": 500}, {"source_id": "shared", "score": 20}]
    fused = reciprocal_rank_fusion(dense, lexical)
    assert fused[0]["source_id"] == "shared"
    assert len(fused) == 3
    assert fused[0]["vector_rank"] == 2 and fused[0]["bm25_rank"] == 2


def test_department_evidence_never_becomes_automatic_transfer():
    valid = {"rank": 1, "source_id": "1", "source_url": "https://example.test/1",
             "routing_eligible": True,
             "department": {"department_id": "d1", "canonical_name": "흥덕구 건설과", "duty_status": "unverified"}}
    unknown = {"rank": 2, "source_id": "2", "routing_eligible": False, "department": None}
    result = department_candidates([valid, unknown])
    assert len(result) == 1
    assert not result[0]["automatic_transfer"]
    assert result[0]["duty_status"] == "unverified"


def test_duplicate_source_fails_before_any_database_write(tmp_path):
    faqs = json.loads((ROOT / "db/자주_묻는_민원.json").read_text())
    key = next(k for k, records in faqs.items() if records)
    faqs[key].append(copy.deepcopy(faqs[key][0]))
    path = tmp_path / "faq.json"
    path.write_text(json.dumps(faqs))
    with pytest.raises(ValueError, match="중복"):
        load_sources(faq_path=path)


def test_inconsistent_current_department_fails(tmp_path):
    cases = json.loads((ROOT / "db/공개_민원_사례.json").read_text())
    cases[0]["department_status"] = "review_required"
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(cases))
    with pytest.raises(ValueError, match="불일치"):
        load_sources(cases_path=path)


def test_kiwi_keeps_bus_number_and_strips_korean_particles():
    tokens = KoreanTokenizer().tokens("711번 버스가 정류장을 그냥 지나갔어요.")
    assert {"711", "버스", "정류장"}.issubset(tokens)
    assert "버스가" not in tokens and "정류장을" not in tokens
