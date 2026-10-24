from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from threading import Lock
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from .search import SearchEngine
from .store import check_index, connect, read_status

log = logging.getLogger(__name__)
engine = None
search_lock = Lock()


@asynccontextmanager
async def lifespan(app):
    global engine
    with connect() as conn:
        check_index(conn)
    engine = SearchEngine()
    engine.models.embedding
    engine.models.load_reranker()
    engine.tokenizer.tokens("청주시 버스 민원")
    log.info("검색 API 준비 완료")
    yield


app = FastAPI(title="청주 민원 근거 검색", version="0.1.0", lifespan=lifespan)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    collection: Literal["faq", "routing", "both"] = "both"
    limit: int = Field(default=5, ge=1, le=20)
    district: Literal["상당구", "서원구", "흥덕구", "청원구"] | None = None
    rerank: bool = True


@app.get("/health")
def health():
    try:
        with connect() as conn:
            check_index(conn)
            return {"status": "ready", **read_status(conn)}
    except Exception:
        log.exception("검색 색인 상태 확인 실패")
        raise HTTPException(status_code=503, detail="검색 색인을 사용할 수 없습니다.") from None


@app.post("/search")
def search(request: SearchRequest):
    try:
        # 모델을 중복 로드하거나 동시에 큰 배치를 실행하지 않도록 직렬화합니다.
        with search_lock:
            return engine.search(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except Exception:
        log.exception("검색 실패")
        raise HTTPException(status_code=503, detail="검색에 실패했습니다. 서버 로그를 확인해 주세요.") from None


@app.get("/departments")
def departments(query: str = Query(default="", max_length=200)):
    with connect() as conn:
        rows = conn.execute("SELECT * FROM complaint_rag.department_directory ORDER BY canonical_name").fetchall()
    needle = query.strip()
    return {"departments": [r for r in rows if not needle or needle in r["canonical_name"]
                             or any(needle in alias for alias in r["aliases"])]}
