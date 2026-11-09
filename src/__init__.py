"""청주 민원 업무 서버의 애플리케이션 팩토리를 제공합니다.

민원 웹은 `src.complaints`, 검색 클라이언트는 `src.rag`, LLM은 `src.llm`,
둘을 잇는 응대는 `src.assist`입니다.
"""

from __future__ import annotations

from typing import Any

__all__ = ["create_app"]


def __getattr__(name: str) -> Any:
    """Flask 종속성이 없는 RAG 환경에서도 src 하위 모듈을 임포트할 수 있게 지연 로딩합니다.

    Args:
        name: 속성 이름입니다.

    Returns:
        요청한 속성 객체입니다.

    Raises:
        AttributeError: 지원하지 않는 속성일 때 발생합니다.
    """
    if name == "create_app":
        from src.app import create_app

        return create_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

