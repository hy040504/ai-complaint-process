"""RAG와 분리된 7테이블 정규화 업무 저장소와 원자적 버전·멱등성 검사를 제공합니다.

시연·운영은 PostgreSQL `complaint_app` 스키마의 7개 핵심 정규화 테이블
(`users`, `complaints`, `messages`, `message_versions`, `ai_jobs`, `ai_results`,
`job_events`)과 보조 3테이블(`idempotency`, `answer_templates`, `app_meta`)을
사용합니다. 단위 테스트는 같은 계약을 메모리 저장소로 검증할 수 있습니다.

구성:
    - `schema`: DDL·CHECK 식·기본 템플릿 상수와 정규화 보조 함수
    - `base`: `ComplaintRepository` 프로토콜
    - `memory`: `MemoryRepository`
    - `postgres`: `PostgresRepository`
"""

from src.complaints.repository.base import ComplaintRepository
from src.complaints.repository.memory import MemoryRepository
from src.complaints.repository.postgres import PostgresRepository
from src.complaints.repository.schema import (
    DEFAULT_ANSWER_TEMPLATES,
    NORMALIZED_TABLE_NAMES,
    StorageKind,
)

__all__ = [
    "DEFAULT_ANSWER_TEMPLATES",
    "NORMALIZED_TABLE_NAMES",
    "ComplaintRepository",
    "MemoryRepository",
    "PostgresRepository",
    "StorageKind",
]
