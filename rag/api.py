"""검색 모델을 재사용하며 근거 검색과 부서 조회 API를 제공합니다."""

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
    """색인을 확인하고 검색 임베딩·토크나이저만 미리 올립니다.

    재정렬 모델은 첫 `rerank=true` 요청에서 지연 로드합니다.

    Args:
        app: 수명 주기를 관리할 FastAPI 애플리케이션입니다.

    Yields:
        초기 준비가 끝나 요청을 받을 수 있는 구간을 엽니다.
    """
    global engine
    with connect() as conn:
        check_index(conn)
    engine = SearchEngine()
    engine.models.embedding
    engine.tokenizer.tokens("청주시 버스 민원")
    log.info("검색 API 준비 완료")
    yield


app = FastAPI(title="청주 민원 근거 검색", version="0.1.0", lifespan=lifespan)


class SearchRequest(BaseModel):
    """검색 API의 입력 형식과 범위를 검증합니다.

    Attributes:
        query: 최대 2000자의 민원 원문입니다.
        collection: FAQ·사례·양쪽 중 검색할 범위입니다.
        limit: 컬렉션별로 반환할 근거 수입니다.
        district: 명시적으로 지정한 관할 구입니다.
        rerank: 재정렬 모델의 실행 여부입니다.
    """

    query: str = Field(min_length=1, max_length=2000)
    collection: Literal["faq", "routing", "both"] = "both"
    limit: int = Field(default=5, ge=1, le=20)
    district: Literal["상당구", "서원구", "흥덕구", "청원구"] | None = None
    rerank: bool = True


@app.get("/health")
def health():
    """색인 호환성과 현재 적재 상태를 반환합니다.

    Returns:
        준비 상태·건수·색인 설정·최근 적재 정보입니다.

    Raises:
        HTTPException: 색인 상태를 확인할 수 없으면 503을 반환합니다.
    """
    try:
        with connect() as conn:
            check_index(conn)
            return {"status": "ready", **read_status(conn)}
    except Exception:
        log.exception("검색 색인 상태 확인 실패")
        raise HTTPException(
            status_code=503, detail="검색 색인을 사용할 수 없습니다."
        ) from None


@app.post("/search")
def search(request: SearchRequest):
    """공유 모델의 동시 실행을 막고 검색 근거를 반환합니다.

    Args:
        request: 입력 검증을 통과한 검색 요청입니다.

    Returns:
        컬렉션별 원문·출처·순위와 검색 전용 계약을 담은 응답입니다.

    Raises:
        HTTPException: 검색 조건 오류에는 400, 실행 장애에는 503을 반환합니다.
    """
    try:
        # 모델을 중복 로드하거나 동시에 큰 배치를 실행하지 않도록 직렬화합니다.
        with search_lock:
            return engine.search(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except Exception:
        log.exception("검색 실패")
        raise HTTPException(
            status_code=503, detail="검색에 실패했습니다. 서버 로그를 확인해 주세요."
        ) from None


@app.get("/departments")
def departments(query: str = Query(default="", max_length=200)):
    """현행 명칭 또는 별칭에 검색어가 포함된 부서를 반환합니다.

    Args:
        query: 부서 검색어입니다. 공백만 있거나 비어 있으면 전체를 반환합니다.

    Returns:
        이름과 검증 상태를 포함하는 부서 목록입니다.
    """
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM complaint_rag.department_directory ORDER BY canonical_name"
        ).fetchall()
    needle = query.strip()
    return {
        "departments": [
            r
            for r in rows
            if not needle
            or needle in r["canonical_name"]
            or any(needle in alias for alias in r["aliases"])
        ]
    }
