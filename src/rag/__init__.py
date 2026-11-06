"""민원 백엔드가 쓰는 RAG 검색 클라이언트입니다.

색인·임베딩·검색 엔진은 루트 `rag/` 패키지와 검색 API에 있습니다.
이 패키지는 그 API를 호출하고 FAQ·사례 근거를 꺼냅니다. 민원 CRUD
저장소와 섞지 않습니다.
"""

from src.rag.client import (
    require_search_contract,
    search_api_url,
    search_available,
    search_via_api,
)
from src.rag.evidence import (
    SearchParts,
    case_hits,
    compact_case,
    compact_faq,
    department_candidates,
    evidence_index,
    faq_hits,
    hit_excerpt,
    search_parts,
)
from src.rag.http import http_json

__all__ = [
    "SearchParts",
    "case_hits",
    "compact_case",
    "compact_faq",
    "department_candidates",
    "evidence_index",
    "faq_hits",
    "hit_excerpt",
    "http_json",
    "require_search_contract",
    "search_api_url",
    "search_available",
    "search_parts",
    "search_via_api",
]
