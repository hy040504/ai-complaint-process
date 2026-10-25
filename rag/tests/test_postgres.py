"""격리된 임시 DB에서 실제 pgvector/BM25/관할 필터와 트랜잭션을 검증합니다."""
import os
import uuid
from collections import Counter

import numpy as np
import psycopg
import pytest
from psycopg import sql

from rag.config import Settings
from rag.data import build_directory, department_id, digest, infer_district
from rag.ingest import write_bm25, write_departments, write_documents
from rag.search import bm25_search, dense_search
from rag.store import connect

pytestmark = pytest.mark.skipif(os.getenv("RUN_PG_TESTS") != "1", reason="RUN_PG_TESTS=1에서 격리 PostgreSQL 검증")


def doc(corpus, sid, text, vector_axis, department=None):
    """실제 모델 없이 단위 벡터를 가진 DB 검증용 문서를 구성합니다.

    Args:
        corpus: faq 또는 routing 컬렉션입니다.
        sid: 테스트 문서의 출처 ID입니다.
        text: 제목·본문·토큰 구성에 사용할 합성 문자열입니다.
        vector_axis: 1로 설정할 벡터 축의 인덱스입니다.
        department: 사례의 현행 부서명 또는 None입니다.

    Returns:
        적재 함수에 전달할 원본·벡터·부서·토큰 빈도 정보입니다.
    """
    payload = {"source_id": sid, "title": text, "summary": text,
               "source_url": "https://example.test/" + sid, "retrieved_at": "2026-10-24T00:00:00+00:00"}
    vector = np.zeros(1024, dtype=np.float32)
    vector[vector_axis] = 1
    terms = Counter(text.split())
    item = {"corpus": corpus, "source_id": sid, "title": text, "search_text": text,
            "payload": payload, "category": "test", "embedding": vector, "terms": terms,
            "token_count": sum(terms.values()), "embedding_hash": digest(text)}
    if corpus == "routing":
        payload.update(department_current=department, department_original=department or "미확인부서",
                       department=department or "미확인부서", department_checked_on="2026-10-24",
                       department_status="current" if department else "review_required")
        item.update(department_id=department_id(department) if department else None,
                    district=infer_district(department) if department else None,
                    routing_eligible=bool(department), summary_missing=False)
    item["content_hash"] = digest(payload)
    return item


@pytest.fixture
def database(monkeypatch):
    """테스트마다 독립된 임시 DB와 합성 검색 문서를 준비하고 종료 후 삭제합니다.

    Args:
        monkeypatch: 임시 DB 이름을 환경변수에 적용할 pytest 픽스처입니다.

    Yields:
        초기 적재를 마친 DB 연결과 합성 문서 목록의 튜플입니다.
    """
    name = "complaint_rag_test_" + uuid.uuid4().hex[:12]
    with psycopg.connect(autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        monkeypatch.setenv("PGDATABASE", name)
        try:
            with connect(initialize=True) as conn:
                docs = [doc("faq", "f1", "버스 지갑 분실", 0),
                        doc("faq", "f2", "대형 폐기물 배출", 1),
                        doc("routing", "r1", "포트홀 도로 보수", 0, "흥덕구 건설과"),
                        doc("routing", "r2", "포트홀 도로 보수", 1, "청원구 건설과"),
                        doc("routing", "r3", "포트홀 도로 보수", 2)]
                write_departments(conn, build_directory([d["payload"] for d in docs if d["corpus"] == "routing"]))
                for corpus in ("faq", "routing"):
                    write_documents(conn, corpus, [d for d in docs if d["corpus"] == corpus])
                write_bm25(conn, docs)
                conn.commit()
                yield conn, docs
        finally:
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def test_real_vector_and_bm25_return_separate_candidate_lists(database):
    """벡터·BM25가 다른 근거를 찾고 저장 벡터가 보존되는지 검증합니다.

    Args:
        database: 임시 PostgreSQL 연결과 합성 문서 목록을 제공하는 픽스처입니다.
    """
    conn, docs = database
    conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
    dense = dense_search(conn, "faq", docs[1]["embedding"], 5, None)
    lexical = bm25_search(conn, "faq", ["지갑"], 5, None, Settings())
    assert dense[0]["source_id"] == "f2"
    assert lexical[0]["source_id"] == "f1"
    assert len(lexical) == 1
    assert all(r["source_id"].startswith("f") for r in dense + lexical)
    stored = conn.execute("SELECT embedding FROM complaint_rag.faq_knowledge WHERE source_id='f2'").fetchone()["embedding"]
    np.testing.assert_allclose(stored.to_numpy(), docs[1]["embedding"])


def test_district_filter_is_applied_to_both_retrievers(database):
    """양쪽 검색기가 다른 구를 제외하고 관할 미확인 사례를 유지하는지 검증합니다.

    Args:
        database: 임시 PostgreSQL 연결과 합성 문서 목록을 제공하는 픽스처입니다.
    """
    conn, docs = database
    lexical = bm25_search(conn, "routing", ["포트홀"], 10, "흥덕구", Settings())
    dense = dense_search(conn, "routing", docs[3]["embedding"], 10, "흥덕구")
    for rows in (lexical, dense):
        assert {r["source_id"] for r in rows} == {"r1", "r3"}
    review = conn.execute("SELECT department_id, routing_eligible FROM complaint_rag.routing_cases WHERE source_id='r3'").fetchone()
    assert review == {"department_id": None, "routing_eligible": False}


def test_failed_write_keeps_previous_snapshot_and_repeat_upsert_does_not_duplicate(database):
    """반복 적재의 중복 방지와 실패한 트랜잭션의 원래 스냅샷 보존을 검증합니다.

    Args:
        database: 임시 PostgreSQL 연결과 합성 문서 목록을 제공하는 픽스처입니다.
    """
    conn, docs = database
    write_documents(conn, "faq", docs[:2])
    conn.commit()
    assert conn.execute("SELECT count(*) AS n FROM complaint_rag.faq_knowledge").fetchone()["n"] == 2
    conn.commit()
    with pytest.raises(psycopg.Error):
        with conn.transaction():
            conn.execute("DELETE FROM complaint_rag.faq_knowledge")
            conn.execute("INSERT INTO complaint_rag.corpus_statistics VALUES ('invalid',0,0)")
    assert conn.execute("SELECT count(*) AS n FROM complaint_rag.faq_knowledge").fetchone()["n"] == 2
