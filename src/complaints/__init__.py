"""민원 웹 업무 서버입니다.

시민·담당자 CRUD, 시연 세션, 정적 UI, Swagger를 담당합니다.
검색은 `src.rag`, 모델 호출은 `src.llm`, 둘을 잇는 응대는 `src.assist`입니다.
"""

from src.complaints.config import ROOT, Settings
from src.complaints.errors import AppError
from src.complaints.repository import MemoryRepository, PostgresRepository
from src.complaints.service import ComplaintService

__all__ = [
    "AppError",
    "ComplaintService",
    "ROOT",
    "MemoryRepository",
    "PostgresRepository",
    "Settings",
]
