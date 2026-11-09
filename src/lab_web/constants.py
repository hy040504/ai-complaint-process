"""응대 검사기 웹이 받는 민원 분야·지역 허용 목록입니다.

시민 화면 `ui/src/store.js`와 같은 값이며, 업무 CRUD 저장과는 분리합니다.
청주시 4대 구 및 산하 읍·면·동 세부 지역 목록을 함께 제공합니다.
"""

from typing import Final, Literal

from src.assist.district import DISTRICT_AREAS

Category = Literal[
    "도로·교통", "환경·청소", "공원·녹지", "생활·복지", "주택·건축", "기타"
]
District = Literal["상당구", "서원구", "흥덕구", "청원구"]

CATEGORIES: Final[tuple[Category, ...]] = (
    "도로·교통",
    "환경·청소",
    "공원·녹지",
    "생활·복지",
    "주택·건축",
    "기타",
)
DISTRICTS: Final[tuple[District, ...]] = (
    "상당구",
    "서원구",
    "흥덕구",
    "청원구",
)

DEFAULT_PORT: Final[int] = 5010
"""기존 민원 CRUD Flask(:5000)와 겹치지 않는 검사기 웹 기본 포트입니다."""
