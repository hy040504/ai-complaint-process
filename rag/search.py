"""컬렉션별 의미·키워드 검색과 재정렬로 원문 근거를 반환합니다."""
from __future__ import annotations

from time import perf_counter

from psycopg import sql

from .config import COLLECTIONS, DISTRICTS, RERANKER_MODEL, RERANKER_REVISION, Settings
from .data import normalize_text
from .korean import KoreanTokenizer
from .models import Models
from .store import check_index, connect, table


def reciprocal_rank_fusion(dense: list[dict], lexical: list[dict], k: int = 60) -> list[dict]:
    """서로 다른 점수 척도를 순위로 바꿔 출처별로 합칩니다.

    Args:
        dense: 의미 검색의 순위순 후보 목록입니다.
        lexical: BM25 검색의 순위순 후보 목록입니다.
        k: 순위 기여도를 완화하는 RRF 상수입니다.

    Returns:
        결합 점수 내림차순의 후보 목록입니다. 동점이면 출처 ID로 정렬합니다.
    """
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
    """명시된 관할 구에 맞는 SQL 조건과 바인딩 값을 구성합니다.

    Args:
        corpus: 검색할 faq 또는 routing 컬렉션입니다.
        district: 명시적으로 전달한 구 이름 또는 None입니다.

    Returns:
        SQL 조건과 매개변수 목록의 튜플입니다. 본청·관할 미확인 사례는 남깁니다.
    """
    if corpus == "routing" and district:
        # 시 본청/관할 미확인 사례는 남기고, 다른 구로 확인된 사례만 제외합니다.
        return sql.SQL("(d.district = %s OR d.district IS NULL)"), [district]
    return sql.SQL("TRUE"), []


def dense_search(conn, corpus, vector, limit, district):
    """관할 조건을 적용해 코사인 유사도가 높은 벡터 후보를 조회합니다.

    Args:
        conn: 읽기 스냅샷을 제공하는 PostgreSQL 연결입니다.
        corpus: 검색할 faq 또는 routing 컬렉션입니다.
        vector: 정규화된 질문 임베딩입니다.
        limit: 가져올 후보 수의 상한입니다.
        district: 명시한 관할 구 또는 None입니다.

    Returns:
        출처 ID와 유사도 점수를 포함한 순위순 후보 목록입니다.
    """
    condition, params = scope_filter(corpus, district)
    query = sql.SQL("SELECT d.source_id, 1 - (d.embedding <=> %s) AS score FROM {} d "
                    "WHERE {} ORDER BY d.embedding <=> %s LIMIT %s").format(table(corpus), condition)
    return conn.execute(query, [vector, *params, vector, limit]).fetchall()


def bm25_search(conn, corpus, terms, limit, district, settings):
    """형태소 빈도와 문서 길이로 BM25 후보를 조회합니다.

    Args:
        conn: 읽기 스냅샷을 제공하는 PostgreSQL 연결입니다.
        corpus: 검색할 faq 또는 routing 컬렉션입니다.
        terms: 질문에서 추출한 형태소 목록입니다.
        limit: 가져올 후보 수의 상한입니다.
        district: 명시한 관할 구 또는 None입니다.
        settings: BM25 단어 빈도·문서 길이 보정 설정입니다.

    Returns:
        출처 ID와 점수를 포함한 순위순 후보 목록입니다. 토큰이 없으면 빈 목록입니다.
    """
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
    """선택한 후보의 원문·출처와 필요한 부서 메타데이터를 조회합니다.

    Args:
        conn: 읽기 스냅샷을 제공하는 PostgreSQL 연결입니다.
        corpus: 검색할 faq 또는 routing 컬렉션입니다.
        source_ids: 원문을 가져올 출처 ID 목록입니다.

    Returns:
        출처 ID를 키로 하고 후보 행을 값으로 하는 딕셔너리입니다.
    """
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
    """유효 사례를 부서별로 모아 가장 높은 사례 순위로 정렬합니다.

    Args:
        hits: 검색 순위순 사례 목록입니다. 현행 부서 미확인 사례는 제외합니다.

    Returns:
        근거 사례와 검증 상태를 가진 부서 후보 목록입니다. 자동 이관은 항상 꺼 둡니다.
    """
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
    """동일한 검색 설정·모델·토크나이저로 컬렉션별 근거를 찾습니다.

    Attributes:
        settings: 검색 후보 수와 모델 실행 설정입니다.
        models: 지연 로드하는 임베딩·재정렬 모델입니다.
        tokenizer: 한국어 BM25용 토크나이저입니다.
    """

    def __init__(self, settings: Settings | None = None):
        """검색에 재사용할 모델 래퍼와 토크나이저를 준비합니다.

        Args:
            settings: 검색 실행 설정입니다. None이면 기본 설정을 사용합니다.
        """
        self.settings = settings or Settings()
        self.models = Models(self.settings)
        self.tokenizer = KoreanTokenizer()

    def search(self, query: str, collection: str = "both", limit: int = 5,
               district: str | None = None, rerank: bool = True) -> dict:
        """컬렉션별 검색·선택적 재정렬을 수행하고 원문 근거를 반환합니다.

        Args:
            query: 정규화 후 1~2000자인 민원 입력입니다.
            collection: faq·routing·both 중 검색할 컬렉션입니다.
            limit: 컬렉션별 반환 수이며 1~20입니다.
            district: 명시한 관할 구 또는 None입니다. FAQ에는 적용하지 않습니다.
            rerank: 후보의 재정렬 여부입니다. 끄면 RRF 순위로 필요한 원문만 조회합니다.

        Returns:
            원문·출처·순위·부서 후보와 requires_gate 계약을 포함한 검색 응답입니다.

        Raises:
            ValueError: 질문·컬렉션·반환 수·관할·토큰 또는 색인 설정이 잘못되면 발생합니다.
        """
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
        # 재정렬을 끄면 반환할 후보만 조회해 불필요한 원문·JSON 전송을 줄입니다.
        shortlist_size = max(limit, self.settings.rerank_k) if rerank else limit
        with connect() as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            check_index(conn)
            conn.execute("SET LOCAL hnsw.ef_search = 100")
            conn.execute("SET LOCAL hnsw.iterative_scan = 'strict_order'")
            for corpus in corpora:
                dense = dense_search(conn, corpus, vector, self.settings.candidate_k, district)
                lexical = bm25_search(conn, corpus, tokens, self.settings.candidate_k, district, self.settings)
                fused = reciprocal_rank_fusion(dense, lexical, self.settings.rrf_k)
                shortlist = fused[:shortlist_size]
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
