from __future__ import annotations

from collections import defaultdict
from time import perf_counter

from psycopg import sql

from .config import COLLECTIONS, DISTRICTS, RERANKER_MODEL, RERANKER_REVISION, Settings
from .data import normalize_text
from .korean import KoreanTokenizer
from .models import Models
from .store import check_index, connect, table


def reciprocal_rank_fusion(dense: list[dict], lexical: list[dict], k: int = 60) -> list[dict]:
    fused = {}
    for name, rows in (("vector", dense), ("bm25", lexical)):
        seen = set()
        for rank, row in enumerate(rows, 1):
            sid = row["source_id"]
            if sid in seen:
                continue
            seen.add(sid)
            item = fused.setdefault(sid, {"source_id": sid, "rrf_score": 0.0})
            item["rrf_score"] += 1.0 / (k + rank)
            item[name + "_rank"] = rank
            item[name + "_score"] = float(row["score"])
    return sorted(fused.values(), key=lambda r: (-r["rrf_score"], r["source_id"]))


def scope_filter(corpus: str, district: str | None):
    if corpus == "routing" and district:
        # 시 본청/관할 미확인 사례는 남기고, 다른 구로 확인된 사례만 제외합니다.
        return sql.SQL("(d.district = %s OR d.district IS NULL)"), [district]
    return sql.SQL("TRUE"), []


def dense_search(conn, corpus, vector, limit, district):
    condition, params = scope_filter(corpus, district)
    query = sql.SQL("SELECT d.source_id, 1 - (d.embedding <=> %s) AS score FROM {} d "
                    "WHERE {} ORDER BY d.embedding <=> %s LIMIT %s").format(table(corpus), condition)
    return conn.execute(query, [vector, *params, vector, limit]).fetchall()


def bm25_search(conn, corpus, terms, limit, district, settings):
    if not terms:
        return []
    condition, params = scope_filter(corpus, district)
    # Robertson/Lucene 양수 IDF: ln(1 + (N-df+0.5)/(df+0.5)). 문서 길이는 Kiwi 토큰 수입니다.
    query = sql.SQL("""
        SELECT p.source_id,
               SUM(ln(1 + (s.document_count - t.document_frequency + 0.5) /
                              (t.document_frequency + 0.5)) *
                   (p.tf * (%s + 1)) /
                   (p.tf + %s * (1 - %s + %s * d.token_count / s.average_length))) AS score
        FROM complaint_rag.term_postings p
        JOIN complaint_rag.term_statistics t USING (corpus, term)
        JOIN complaint_rag.corpus_statistics s USING (corpus)
        JOIN {} d ON d.source_id = p.source_id
        WHERE p.corpus = %s AND p.term = ANY(%s) AND {}
        GROUP BY p.source_id ORDER BY score DESC, p.source_id LIMIT %s
    """).format(table(corpus), condition)
    return conn.execute(query, [settings.bm25_k1, settings.bm25_k1, settings.bm25_b, settings.bm25_b,
                                corpus, sorted(set(terms)), *params, limit]).fetchall()


def fetch_candidates(conn, corpus: str, source_ids: list[str]):
    fields = sql.SQL("d.source_id, d.title, d.search_text, d.payload, d.source_url")
    extra = sql.SQL("")
    join = sql.SQL("")
    if corpus == "routing":
        extra = sql.SQL(", d.routing_eligible, d.summary_missing, d.department_status, "
                        "dd.department_id, dd.canonical_name, dd.district, dd.jurisdiction_status, "
                        "dd.duty_status, dd.automatic_routing_ready")
        join = sql.SQL(" LEFT JOIN complaint_rag.department_directory dd ON dd.department_id = d.department_id")
    query = sql.SQL("SELECT {}{} FROM {} d{} WHERE d.source_id = ANY(%s)").format(fields, extra, table(corpus), join)
    return {r["source_id"]: r for r in conn.execute(query, (source_ids,))}


def department_candidates(hits: list[dict]) -> list[dict]:
    groups = {}
    for hit in hits:
        if not hit.get("routing_eligible") or not hit.get("department"):
            continue
        department = hit["department"]
        key = department["department_id"]
        entry = groups.setdefault(key, {**department, "supporting_cases": [],
                                         "best_case_rank": hit["rank"], "automatic_transfer": False})
        entry["supporting_cases"].append({"source_id": hit["source_id"], "source_url": hit["source_url"]})
    # 사례 수가 많은 대중교통과 등에 유리한 단순 다수결을 사용하지 않습니다.
    return sorted(groups.values(), key=lambda item: (item["best_case_rank"], item["department_id"]))


class SearchEngine:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.models = Models(self.settings)
        self.tokenizer = KoreanTokenizer()

    def search(self, query: str, collection: str = "both", limit: int = 5,
               district: str | None = None, rerank: bool = True) -> dict:
        started = perf_counter()
        query = normalize_text(query)
        if not query or len(query) > 2000:
            raise ValueError("민원은 공백을 제외하고 1~2000자 이내로 입력해 주세요.")
        if collection not in (*COLLECTIONS, "both") or not 1 <= limit <= 20:
            raise ValueError("collection은 faq/routing/both, limit은 1~20이어야 합니다.")
        if district is not None and district not in DISTRICTS:
            raise ValueError("관할 구 이름을 확인해 주세요.")
        tokens = self.tokenizer.tokens(query)
        if not tokens:
            raise ValueError("검색할 업무·시설·지역 등의 단어를 입력해 주세요.")
        # 관할은 명시적으로 받은 값만 필터링합니다. 질문에 등장한 지역이 관할이라고 추측하지 않습니다.
        vector = self.models.encode([query])[0]
        results = {}
        corpora = list(COLLECTIONS) if collection == "both" else [collection]
        with connect() as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            check_index(conn)
            conn.execute("SET LOCAL hnsw.ef_search = 100")
            conn.execute("SET LOCAL hnsw.iterative_scan = 'strict_order'")
            for corpus in corpora:
                dense = dense_search(conn, corpus, vector, self.settings.candidate_k, district)
                lexical = bm25_search(conn, corpus, tokens, self.settings.candidate_k, district, self.settings)
                fused = reciprocal_rank_fusion(dense, lexical, self.settings.rrf_k)
                shortlist = fused[:max(limit, self.settings.rerank_k)]
                candidates = fetch_candidates(conn, corpus, [r["source_id"] for r in shortlist])
                if rerank and shortlist:
                    scores = self.models.rerank(query, [candidates[r["source_id"]]["search_text"] for r in shortlist])
                    for result, score in zip(shortlist, scores, strict=True):
                        result["rerank_logit"] = score
                    shortlist.sort(key=lambda r: (-r["rerank_logit"], -r["rrf_score"], r["source_id"]))
                hits = []
                for rank, score in enumerate(shortlist[:limit], 1):
                    row = candidates[score["source_id"]]
                    hit = {"rank": rank, "source_id": row["source_id"], "title": row["title"],
                           "source_url": row["source_url"], "scores": {k: v for k, v in score.items() if k != "source_id"},
                           "evidence": row["payload"]}
                    if corpus == "routing":
                        hit.update(routing_eligible=row["routing_eligible"], summary_missing=row["summary_missing"],
                                   department_status=row["department_status"], department=None)
                        if row["department_id"]:
                            hit["department"] = {k: row[k] for k in ("department_id", "canonical_name", "district",
                                                                      "jurisdiction_status", "duty_status", "automatic_routing_ready")}
                    hits.append(hit)
                result = {"hits": hits, "candidate_counts": {"vector": len(dense), "bm25": len(lexical),
                                                              "fused": len(fused), "reranked": len(shortlist) if rerank else 0}}
                if corpus == "routing":
                    result["department_candidates"] = department_candidates(hits)
                results[COLLECTIONS[corpus]] = result
        return {"query": query, "district_filter": district, "query_terms": sorted(set(tokens)),
                "pipeline": "vector+kiwi_bm25+rrf" + ("+reranker" if rerank else ""),
                "reranker": {"model": RERANKER_MODEL, "revision": RERANKER_REVISION} if rerank else None,
                "retrieval_only": True, "decision": "requires_gate",
                "score_note": "검색 순위와 rerank_logit은 자동 답변/이관의 정답 확률이 아닙니다.",
                "results": results, "elapsed_ms": round((perf_counter() - started) * 1000, 1)}
