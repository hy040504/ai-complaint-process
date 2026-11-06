"""민원 응대에 쓰는 LLM 공급자 어댑터입니다.

검색·민원 저장과 분리합니다. 판정 프롬프트와 정책 검사는 `src.assist`가
담당합니다.
"""

from src.llm.complete import complete_chat, parse_json_object
from src.rag.http import http_json
from src.llm.settings import llm_configured, llm_settings

__all__ = [
    "complete_chat",
    "http_json",
    "llm_configured",
    "llm_settings",
    "parse_json_object",
]
