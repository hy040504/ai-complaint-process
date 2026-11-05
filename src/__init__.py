"""청주 민원 업무 서버의 애플리케이션 팩토리를 제공합니다.

민원 웹은 `src.complaints`, 검색 클라이언트는 `src.rag`, LLM은 `src.llm`,
둘을 잇는 응대는 `src.assist`입니다.
"""

from src.app import create_app

__all__ = ["create_app"]
