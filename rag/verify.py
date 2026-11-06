"""원본 JSON과 실제 PostgreSQL 검색 스냅샷의 무결성을 대조합니다."""

from __future__ import annotations

import json

import numpy as np
from psycopg import sql

from .config import COLLECTIONS, DIMENSION
from .data import load_sources
from .store import check_index, connect, read_status, table


def verify() -> dict:
    """원본과 실제 DB의 키·본문·벡터·검색 통계·부서 사전을 대조합니다.

    Returns:
        확인한 항목과 현재 적재 상태를 담은 무결성 보고서입니다.

    Raises:
        AssertionError: 원본·색인·부서·통계 불일치나 벡터 검증 실패가 있으면 발생합니다.
    """
    docs, departments, _ = load_sources()
    checks = []
    with connect() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        check_index(conn)
        for corpus in COLLECTIONS:
            expected = {d["source_id"]: d for d in docs if d["corpus"] == corpus}
            actual = {
                r["source_id"]: r
                for r in conn.execute(sql.SQL("SELECT * FROM {}").format(table(corpus)))
            }
            assert expected.keys() == actual.keys(), f"{corpus}: source_id 불일치"
            for sid, doc in expected.items():
                row = actual[sid]
                assert (
                    row["payload"] == doc["payload"]
                ), f"{corpus}:{sid}: 원본 payload 손실"
                assert (
                    row["search_text"] == doc["search_text"]
                ), f"{corpus}:{sid}: 검색 본문 불일치"
                vector = row["embedding"].to_numpy()
                assert vector.shape == (DIMENSION,) and np.isfinite(vector).all()
                assert abs(float(np.linalg.norm(vector)) - 1.0) < 1e-4
                if corpus == "routing":
                    assert row["department_id"] == doc["department_id"]
                    assert row["routing_eligible"] == doc["routing_eligible"]
                    assert row["district"] == doc["district"]
            lengths = {
                r["source_id"]: r["length"]
                for r in conn.execute(
                    "SELECT source_id, sum(tf) AS length FROM complaint_rag.term_postings WHERE corpus=%s GROUP BY source_id",
                    (corpus,),
                )
            }
            assert lengths == {
                sid: r["token_count"] for sid, r in actual.items()
            }, f"{corpus}: 토큰 빈도/문서 길이 불일치"
            stats = conn.execute(
                "SELECT * FROM complaint_rag.corpus_statistics WHERE corpus=%s",
                (corpus,),
            ).fetchone()
            assert stats["document_count"] == len(actual)
            assert (
                abs(stats["average_length"] - sum(lengths.values()) / len(actual))
                < 1e-8
            )
            checks.append(
                f"{corpus}: {len(actual)}건 원본/출처/{DIMENSION}차원 정규화 벡터/한국어 BM25 대조"
            )
        expected_directory = {d["department_id"]: d for d in departments}
        actual_directory = {
            r["department_id"]: r
            for r in conn.execute("SELECT * FROM complaint_rag.department_directory")
        }
        assert expected_directory.keys() == actual_directory.keys()
        for key, value in expected_directory.items():
            assert value["canonical_name"] == actual_directory[key]["canonical_name"]
            assert set(value["aliases"]) == set(actual_directory[key]["aliases"])
        bad_df = conn.execute(
            """
            SELECT count(*) AS n FROM (
                SELECT corpus, term, count(*) AS actual_df FROM complaint_rag.term_postings GROUP BY corpus, term
            ) actual FULL JOIN complaint_rag.term_statistics stored USING (corpus,term)
            WHERE actual_df IS DISTINCT FROM document_frequency
        """
        ).fetchone()["n"]
        assert bad_df == 0, "BM25 문서 빈도 불일치"
        checks.append(
            f"department_directory: {len(actual_directory)}개 현행 명칭/별칭/내부 ID 대조"
        )
        indexes = conn.execute(
            "SELECT indexname FROM pg_indexes WHERE schemaname='complaint_rag' AND indexdef LIKE '%USING hnsw%'"
        ).fetchall()
        assert len(indexes) == 2, "HNSW 색인 누락"
        checks.append("FAQ/사례 HNSW 색인 2개 및 BM25 문서 빈도 확인")
        return {"passed": True, "checks": checks, **read_status(conn)}


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2, default=str))
