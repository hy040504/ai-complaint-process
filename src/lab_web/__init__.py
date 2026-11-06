"""응대 검사기만 제공하는 간단한 웹 서버입니다.

프론트는 `static/`, 민원 JSON 수신은 `POST /api/v1/lab/complaints`입니다.
테스트 기록은 `.rag-cache/lab-runs` JSON입니다. 민원 CRUD 테이블에는 쓰지 않습니다.
"""

from src.lab_web.app import create_app

__all__ = ["create_app"]
