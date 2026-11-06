"""응대 검사기만 제공하는 간단한 웹 서버입니다.

프론트는 `static/`, 민원 JSON 수신은 `POST /api/v1/lab/complaints`입니다.
언어 모델 호출과 민원 CRUD 저장은 이 패키지 범위가 아닙니다.
"""

from src.lab_web.app import create_app

__all__ = ["create_app"]
