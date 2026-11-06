"""CLI 호환 진입점입니다.

구현은 `src.rag`(검색 클라이언트), `src.llm`(공급자), `src.assist`(연결
계층)에 있습니다. `python -m rag assist`와 기존 단위 테스트가 이 모듈
이름을 유지합니다.
"""

from src.assist import (
    EXAMPLES,
    iter_assist,
    parse_json_object,
    render_assist,
    run_assist,
    validate_decision,
)
from src.llm import complete_chat, llm_configured, llm_settings
from src.llm.complete import http_json
from src.rag import search_api_url, search_via_api

__all__ = [
    "EXAMPLES",
    "complete_chat",
    "http_json",
    "iter_assist",
    "llm_configured",
    "llm_settings",
    "parse_json_object",
    "render_assist",
    "run_assist",
    "search_api_url",
    "search_via_api",
    "validate_decision",
]
