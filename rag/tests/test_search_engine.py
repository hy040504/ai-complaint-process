"""모델·DB 대역으로 후보 조회량과 재정렬·검색 전용 계약을 검증합니다."""

from unittest.mock import MagicMock, Mock

import pytest

from rag import search as search_module
from rag.config import COLLECTIONS


@pytest.fixture
def isolated_engine(monkeypatch):
    """모델 추론·DB 접속 없이 검색 조합 계층을 실행할 대역을 준비합니다.

    Args:
        monkeypatch: 모델·토크나이저·DB·검색기 의존성을 교체할 pytest 픽스처입니다.

    Returns:
        검색 엔진, 원문 조회 대역, 모델 대역의 튜플입니다.
    """
    models = Mock()
    from rag.config import DIMENSION

    models.encode.return_value = [[0.0] * DIMENSION]
    # RRF 뒤쪽 후보에 더 높은 점수를 줘 넓은 재정렬 후보 유지 여부를 확인합니다.
    models.rerank.side_effect = lambda query, texts: list(range(len(texts)))
    tokenizer = Mock()
    tokenizer.tokens.return_value = ["버스", "정류장"]
    monkeypatch.setattr(search_module, "Models", Mock(return_value=models))
    monkeypatch.setattr(search_module, "KoreanTokenizer", Mock(return_value=tokenizer))
    monkeypatch.setattr(search_module, "connect", Mock(return_value=MagicMock()))
    monkeypatch.setattr(search_module, "check_index", Mock())
    rows = [{"source_id": str(i), "score": 1.0 / i} for i in range(1, 31)]
    monkeypatch.setattr(search_module, "dense_search", Mock(return_value=rows))
    monkeypatch.setattr(search_module, "bm25_search", Mock(return_value=[]))

    def candidates(conn, corpus, source_ids):
        """요청한 ID에 대해서만 컬렉션을 구별할 수 있는 합성 원문을 만듭니다.

        Args:
            conn: 실제로 접속하지 않는 DB 연결 대역입니다.
            corpus: 원문을 가져올 컬렉션입니다.
            source_ids: 조회 대상으로 선택한 출처 ID 목록입니다.

        Returns:
            요청한 ID만 포함하는 검색 후보 딕셔너리입니다.
        """
        return {
            sid: {
                "source_id": sid,
                "title": "합성 민원 " + sid,
                "search_text": "버스 정류장 " + sid,
                "source_url": "https://example.test/" + sid,
                "payload": {"corpus": corpus, "source_id": sid},
                "routing_eligible": False,
                "summary_missing": False,
                "department_status": "review_required",
                "department_id": None,
            }
            for sid in source_ids
        }

    fetched = Mock(side_effect=candidates)
    monkeypatch.setattr(search_module, "fetch_candidates", fetched)
    return search_module.SearchEngine(), fetched, models


@pytest.mark.parametrize("collection", ["faq", "routing", "both"])
@pytest.mark.parametrize(
    ("rerank", "limit", "fetched_count"),
    [(False, 5, 5), (False, 20, 20), (True, 5, 20), (True, 20, 20)],
)
def test_candidate_fetch_preserves_ranking_and_retrieval_contract(
    isolated_engine,
    collection,
    rerank,
    limit,
    fetched_count,
):
    """불필요한 본문 조회를 줄이면서 재정렬 후보·결과·검색 계약을 보존합니다.

    Args:
        isolated_engine: 모델·DB를 격리한 검색 엔진과 의존성 대역입니다.
        collection: 단일 또는 양쪽 컬렉션 검색 조건입니다.
        rerank: 재정렬 사용 여부입니다.
        limit: 컬렉션별 반환 수입니다.
        fetched_count: 해당 조건에서 조회해야 할 원문 수입니다.
    """
    engine, fetched, models = isolated_engine
    result = engine.search(
        "버스 정류장", collection=collection, limit=limit, rerank=rerank
    )
    corpora = list(COLLECTIONS) if collection == "both" else [collection]
    assert set(result["results"]) == {COLLECTIONS[corpus] for corpus in corpora}
    assert result["retrieval_only"] and result["decision"] == "requires_gate"
    assert [call.args[1] for call in fetched.call_args_list] == corpora
    assert all(len(call.args[2]) == fetched_count for call in fetched.call_args_list)
    expected_ids = (
        [str(i) for i in range(20, 20 - limit, -1)]
        if rerank
        else [str(i) for i in range(1, limit + 1)]
    )
    for corpus in corpora:
        response = result["results"][COLLECTIONS[corpus]]
        assert [hit["source_id"] for hit in response["hits"]] == expected_ids
        assert all(hit["evidence"]["corpus"] == corpus for hit in response["hits"])
        assert response["candidate_counts"] == {
            "vector": 30,
            "bm25": 0,
            "fused": 30,
            "reranked": fetched_count if rerank else 0,
        }
        if corpus == "routing":
            assert response["department_candidates"] == []
    assert models.rerank.call_count == (len(corpora) if rerank else 0)
