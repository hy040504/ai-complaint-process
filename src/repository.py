"""RAG와 분리된 SQLite 저장 및 원자적 버전·멱등성 검사를 제공합니다."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Protocol

from src.errors import AppError
from src.models import Complaint


class ComplaintRepository(Protocol):
    """업무 서비스가 의존하는 저장소 인터페이스입니다."""

    def all(self) -> list[Complaint]:
        """저장된 민원을 최신 등록순으로 반환합니다."""
        ...

    def get(self, complaint_id: str) -> Complaint:
        """식별자에 해당하는 민원을 반환합니다.

        Args:
            complaint_id: 업무 민원 식별자입니다.

        Raises:
            AppError: 해당 민원이 없을 때 발생합니다.
        """
        ...

    def create(self, row: Complaint, key: str | None, fingerprint: str) -> Complaint:
        """민원과 등록 키를 같은 트랜잭션에 저장합니다.

        Args:
            row: 새 민원입니다.
            key: 작성자별 중복 방지 키입니다.
            fingerprint: 등록 본문의 해시입니다.

        Returns:
            새 민원 또는 동일 요청으로 이미 저장된 민원입니다.
        """
        ...

    def change(self, complaint_id: str, expected: int, action: Callable[[Complaint], None]) -> Complaint:
        """최신 버전을 검사한 뒤 업무 변경을 원자적으로 저장합니다.

        Args:
            complaint_id: 수정 대상 식별자입니다.
            expected: 호출자가 조회한 버전입니다.
            action: 검증된 민원을 변경할 업무 함수입니다.

        Returns:
            변경 후 민원입니다.
        """
        ...


class SQLiteRepository:
    """각 작업에 연결과 트랜잭션을 분리하는 로컬 업무 저장소입니다.

    Args:
        path: RAG DB와 분리한 SQLite 파일 경로입니다.
    """

    def __init__(self, path: Path) -> None:
        """업무 DB 파일과 누락된 테이블을 준비합니다.

        Args:
            path: 별도 업무 SQLite 파일 경로입니다.
        """
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS complaints (
                    id TEXT PRIMARY KEY, version INTEGER NOT NULL CHECK(version > 0),
                    created_at TEXT NOT NULL, payload TEXT NOT NULL CHECK(json_valid(payload))
                );
                CREATE TABLE IF NOT EXISTS idempotency (
                    owner TEXT NOT NULL, key TEXT NOT NULL, fingerprint TEXT NOT NULL,
                    complaint_id TEXT NOT NULL REFERENCES complaints(id),
                    PRIMARY KEY(owner, key)
                );
            """)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """연결을 반드시 닫고 실패 시 트랜잭션을 되돌립니다.

        Yields:
            트랜잭션을 처리할 SQLite 연결입니다.
        """
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def all(self) -> list[Complaint]:
        """저장된 전체 업무 민원을 최신 등록순으로 반환합니다."""
        with self.connection() as db:
            return [Complaint.model_validate_json(row[0]) for row in db.execute("SELECT payload FROM complaints ORDER BY created_at DESC, id DESC")]

    def get(self, complaint_id: str) -> Complaint:
        """민원 식별자로 조회하며 누락은 404 업무 오류로 처리합니다.

        Args:
            complaint_id: 업무 민원 식별자입니다.

        Returns:
            저장된 민원 모델입니다.

        Raises:
            AppError: 민원이 없으면 발생합니다.
        """
        with self.connection() as db:
            result = db.execute("SELECT payload FROM complaints WHERE id=?", (complaint_id,)).fetchone()
        if result is None:
            raise AppError(404, "not_found", "민원을 찾을 수 없습니다.")
        return Complaint.model_validate_json(result[0])

    def create(self, row: Complaint, key: str | None, fingerprint: str) -> Complaint:
        """작성자별 동일 등록 요청을 중복 생성 없이 저장합니다.

        Args:
            row: 새 업무 민원입니다.
            key: 선택적인 멱등성 키입니다.
            fingerprint: 같은 키의 본문 동일성을 검사할 해시입니다.

        Returns:
            생성된 민원 또는 같은 요청의 기존 민원입니다.

        Raises:
            AppError: 같은 키로 다른 내용을 요청하면 발생합니다.
        """
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if key:
                old = db.execute("SELECT fingerprint, complaint_id FROM idempotency WHERE owner=? AND key=?", (row.owner, key)).fetchone()
                if old:
                    if old[0] != fingerprint:
                        raise AppError(409, "idempotency_conflict", "동일 등록 키에 다른 내용이 전송되었습니다.")
                    stored = db.execute("SELECT payload FROM complaints WHERE id=?", (old[1],)).fetchone()
                    assert stored is not None
                    return Complaint.model_validate_json(stored[0])
            db.execute("INSERT INTO complaints VALUES(?,?,?,?)", (row.id, row.version, row.date.isoformat(), row.model_dump_json()))
            if key:
                db.execute("INSERT INTO idempotency VALUES(?,?,?,?)", (row.owner, key, fingerprint, row.id))
        return row

    def change(self, complaint_id: str, expected: int, action: Callable[[Complaint], None]) -> Complaint:
        """트랜잭션 안에서 버전 검사·업무 검증·갱신을 함께 수행합니다.

        Args:
            complaint_id: 수정할 민원 식별자입니다.
            expected: 기대하는 현재 버전입니다.
            action: 권한·상태를 검증하고 변경할 함수입니다.

        Returns:
            버전이 증가한 저장 결과입니다.

        Raises:
            AppError: 대상이 없거나 버전 충돌·업무 검증 실패 시 발생합니다.
        """
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            result = db.execute("SELECT payload FROM complaints WHERE id=?", (complaint_id,)).fetchone()
            if result is None:
                raise AppError(404, "not_found", "민원을 찾을 수 없습니다.")
            row = Complaint.model_validate_json(result[0])
            if row.version != expected:
                raise AppError(409, "version_conflict", "다른 화면에서 내용이 변경되었습니다. 입력을 보관한 뒤 최신 내용을 불러와 주세요.")
            action(row)
            row.version += 1
            db.execute("UPDATE complaints SET version=?, payload=? WHERE id=? AND version=?", (row.version, row.model_dump_json(), complaint_id, expected))
        return row
