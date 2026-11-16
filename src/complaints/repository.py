"""RAG와 분리된 업무 저장과 원자적 버전·멱등성 검사를 제공합니다.

시연·운영은 PostgreSQL `complaint_app` 스키마를 씁니다. 단위 테스트는
같은 계약을 메모리 저장소로 검증할 수 있습니다.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import timedelta
from threading import Lock
from typing import Literal, Protocol

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from src.complaints.errors import AppError
from src.complaints.models import AnswerTemplate, Complaint, utcnow

StorageKind = Literal["postgresql", "memory"]

# 최초 스키마 준비 시 한 번만 시드하는 담당자 기본 답변 템플릿 목록이다.
DEFAULT_ANSWER_TEMPLATES: tuple[tuple[str, str, str], ...] = (
    (
        "TPL-DEF-1",
        "검토 결과 인사",
        "안녕하십니까. 접수하신 민원의 검토 결과를 안내드립니다.",
    ),
    ("TPL-DEF-2", "불편 사과", "불편을 드려 죄송합니다."),
    (
        "TPL-DEF-3",
        "추가 조사·부서 전달",
        "확인 과정에서 추가 조사가 필요하여 담당 부서에 전달하였습니다.",
    ),
    (
        "TPL-DEF-4",
        "추가 문의 안내",
        "추가 문의가 있으시면 민원 상세 화면의 추가 문의로 남겨 주세요.",
    ),
    ("TPL-DEF-5", "맺음말 감사", "감사합니다."),
)

# psycopg는 한 execute에 여러 문을 넣지 못하므로 스키마·테이블을 나눠 적용합니다.
_SCHEMA_STATEMENTS = (
    "CREATE SCHEMA IF NOT EXISTS {schema}",
    """
    CREATE TABLE IF NOT EXISTS {schema}.complaints (
        id text PRIMARY KEY,
        version integer NOT NULL CHECK (version > 0),
        created_at timestamptz NOT NULL,
        payload jsonb NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS {schema}.idempotency (
        owner text NOT NULL,
        key text NOT NULL,
        fingerprint text NOT NULL,
        complaint_id text NOT NULL REFERENCES {schema}.complaints(id),
        PRIMARY KEY (owner, key)
    )
    """,
    # 예전 테이블은 id·created_at·payload만 있다. IF NOT EXISTS는 컬럼을 더하지 않는다.
    "ALTER TABLE {schema}.complaints ADD COLUMN IF NOT EXISTS version integer",
    """
    UPDATE {schema}.complaints
    SET version = CASE
        WHEN COALESCE(payload->>'version', '') ~ '^[1-9][0-9]*$'
        THEN (payload->>'version')::integer
        ELSE 1
    END
    WHERE version IS NULL
    """,
    "ALTER TABLE {schema}.complaints ALTER COLUMN version SET NOT NULL",
    # 목록·필터용 칼럼은 payload에서 자동 계산한다. 원본은 payload 하나다.
    "ALTER TABLE {schema}.complaints ADD COLUMN IF NOT EXISTS status text GENERATED ALWAYS AS (payload->>'status') STORED",
    "ALTER TABLE {schema}.complaints ADD COLUMN IF NOT EXISTS owner text GENERATED ALWAYS AS (payload->>'owner') STORED",
    "ALTER TABLE {schema}.complaints ADD COLUMN IF NOT EXISTS visibility text GENERATED ALWAYS AS (payload->>'visibility') STORED",
    "ALTER TABLE {schema}.complaints ADD COLUMN IF NOT EXISTS district text GENERATED ALWAYS AS (payload->>'district') STORED",
    "ALTER TABLE {schema}.complaints ADD COLUMN IF NOT EXISTS is_synthetic boolean GENERATED ALWAYS AS (COALESCE((payload->>'isSynthetic')::boolean, false)) STORED",
    "CREATE INDEX IF NOT EXISTS complaints_status_created ON {schema}.complaints (status, created_at)",
    "CREATE INDEX IF NOT EXISTS complaints_owner_created ON {schema}.complaints (owner, created_at)",
    # 예전 시연 데이터에는 isSynthetic 키가 없으므로 공개 시연 ID(DEMO-PUB-)만 한 번 채운다.
    """
    UPDATE {schema}.complaints
    SET payload = payload || jsonb_build_object('isSynthetic', true)
    WHERE left(id, 9) = 'DEMO-PUB-' AND NOT (payload ? 'isSynthetic')
    """,
    """
    CREATE TABLE IF NOT EXISTS {schema}.answer_templates (
        id text PRIMARY KEY,
        title text NOT NULL,
        content text NOT NULL,
        is_default boolean NOT NULL DEFAULT false,
        created_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS {schema}.app_meta (
        key text PRIMARY KEY,
        value text NOT NULL
    )
    """,
)


# 상태·공개 범위·지역을 DB도 검사한다. 값 목록은 src/complaints/models.py와 맞춘다.
_VALUE_CHECKS: tuple[tuple[str, str], ...] = (
    (
        "complaints_status_valid",
        "status IN ('submitted', 'under_review', 'answered', 'closed', 'withdrawn')",
    ),
    ("complaints_visibility_valid", "visibility IN ('private', 'public')"),
    (
        "complaints_district_valid",
        "district IN ('상당구', '서원구', '흥덕구', '청원구', '모름')",
    ),
)


class ComplaintRepository(Protocol):
    """업무 서비스가 의존하는 저장소 인터페이스입니다."""

    storage: StorageKind

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

        Raises:
            AppError: 같은 키로 다른 내용을 요청하면 발생합니다.
        """
        ...

    def change(
        self, complaint_id: str, expected: int, action: Callable[[Complaint], None]
    ) -> Complaint:
        """최신 버전을 검사한 뒤 업무 변경을 원자적으로 저장합니다.

        Args:
            complaint_id: 수정 대상 식별자입니다.
            expected: 호출자가 조회한 버전입니다.
            action: 검증된 민원을 변경할 업무 함수입니다.

        Returns:
            변경 후 민원입니다.
        """
        ...

    def delete(
        self, complaint_id: str, expected: int, check: Callable[[Complaint], None]
    ) -> None:
        """최신 버전을 검사한 뒤 민원과 연결된 멱등성 키를 영구 삭제합니다.

        Args:
            complaint_id: 삭제할 민원 식별자입니다.
            expected: 호출자가 조회한 현재 버전입니다.
            check: 삭제 권한을 검증할 함수입니다.
        """
        ...

    def list_templates(self) -> list[AnswerTemplate]:
        """담당자 답변 편집기용 템플릿 목록을 등록순으로 반환합니다."""
        ...

    def create_template(self, template: AnswerTemplate) -> AnswerTemplate:
        """새 답변 템플릿을 저장하고 반환합니다.

        Args:
            template: 저장할 템플릿 모델입니다.
        """
        ...

    def delete_template(self, template_id: str) -> None:
        """지정한 답변 템플릿을 삭제합니다.

        Args:
            template_id: 삭제할 템플릿 식별자입니다.
        """
        ...

    def reset_default_templates(self) -> list[AnswerTemplate]:
        """누락된 기본 답변 템플릿을 복원하고 전체 목록을 반환합니다."""
        ...


class MemoryRepository:
    """프로세스 안의 업무 저장소입니다. 단위 테스트 전용입니다.

    PostgreSQL 없이 API 계약을 검증할 때 씁니다. 시연 서버는 쓰지 않습니다.
    """

    storage: StorageKind = "memory"

    def __init__(self) -> None:
        """빈 민원·멱등성 맵, 기본 답변 템플릿과 변경 잠금을 준비합니다."""
        self._rows: dict[str, Complaint] = {}
        self._keys: dict[tuple[str, str], tuple[str, str]] = {}
        self._templates: list[AnswerTemplate] = [
            AnswerTemplate(id=tpl_id, title=title, content=content, is_default=True)
            for tpl_id, title, content in DEFAULT_ANSWER_TEMPLATES
        ]
        self._lock = Lock()

    def all(self) -> list[Complaint]:
        """저장된 전체 업무 민원을 최신 등록순으로 반환합니다."""
        with self._lock:
            return sorted(
                (item.model_copy(deep=True) for item in self._rows.values()),
                key=lambda item: (item.date, item.id),
                reverse=True,
            )

    def get(self, complaint_id: str) -> Complaint:
        """민원 식별자로 조회하며 누락은 404 업무 오류로 처리합니다.

        Args:
            complaint_id: 업무 민원 식별자입니다.

        Returns:
            저장된 민원 모델입니다.

        Raises:
            AppError: 민원이 없으면 발생합니다.
        """
        with self._lock:
            row = self._rows.get(complaint_id)
        if row is None:
            raise AppError(404, "not_found", "민원을 찾을 수 없습니다.")
        return row.model_copy(deep=True)

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
        with self._lock:
            if key:
                old = self._keys.get((row.owner, key))
                if old:
                    if old[0] != fingerprint:
                        raise AppError(
                            409,
                            "idempotency_conflict",
                            "동일 등록 키에 다른 내용이 전송되었습니다.",
                        )
                    stored = self._rows[old[1]]
                    return stored.model_copy(deep=True)
            stored = row.model_copy(deep=True)
            self._rows[stored.id] = stored
            if key:
                self._keys[(row.owner, key)] = (fingerprint, stored.id)
        return stored.model_copy(deep=True)

    def change(
        self, complaint_id: str, expected: int, action: Callable[[Complaint], None]
    ) -> Complaint:
        """잠금 안에서 버전 검사·업무 검증·갱신을 함께 수행합니다.

        Args:
            complaint_id: 수정할 민원 식별자입니다.
            expected: 기대하는 현재 버전입니다.
            action: 권한·상태를 검증하고 변경할 함수입니다.

        Returns:
            버전이 증가한 저장 결과입니다.

        Raises:
            AppError: 대상이 없거나 버전 충돌·업무 검증 실패 시 발생합니다.
        """
        with self._lock:
            current = self._rows.get(complaint_id)
            if current is None:
                raise AppError(404, "not_found", "민원을 찾을 수 없습니다.")
            if current.version != expected:
                raise AppError(
                    409,
                    "version_conflict",
                    "다른 화면에서 내용이 변경되었습니다. 입력을 보관한 뒤 최신 내용을 불러와 주세요.",
                )
            row = current.model_copy(deep=True)
            action(row)
            row.version += 1
            self._rows[complaint_id] = row
        return row.model_copy(deep=True)

    def delete(
        self, complaint_id: str, expected: int, check: Callable[[Complaint], None]
    ) -> None:
        """잠금 안에서 버전·삭제 권한을 검사한 뒤 민원과 멱등성 키를 삭제합니다.

        Args:
            complaint_id: 삭제할 민원 식별자입니다.
            expected: 호출자가 조회한 현재 버전입니다.
            check: 삭제 권한을 검증할 함수입니다.

        Raises:
            AppError: 대상이 없거나 버전 충돌·권한 검증 실패 시 발생합니다.
        """
        with self._lock:
            current = self._rows.get(complaint_id)
            if current is None:
                raise AppError(404, "not_found", "민원을 찾을 수 없습니다.")
            if current.version != expected:
                raise AppError(
                    409,
                    "version_conflict",
                    "다른 화면에서 내용이 변경되었습니다. 최신 내용을 불러온 뒤 다시 시도해 주세요.",
                )
            check(current.model_copy(deep=True))
            del self._rows[complaint_id]
            stale_keys = [
                k for k, (_, cid) in self._keys.items() if cid == complaint_id
            ]
            for key in stale_keys:
                del self._keys[key]

    def list_templates(self) -> list[AnswerTemplate]:
        """담당자 답변 편집기용 템플릿 목록을 등록순으로 반환합니다."""
        with self._lock:
            return [tpl.model_copy(deep=True) for tpl in self._templates]

    def create_template(self, template: AnswerTemplate) -> AnswerTemplate:
        """새 답변 템플릿을 저장하고 사본을 반환합니다.

        Args:
            template: 저장할 템플릿 모델입니다.

        Returns:
            저장된 템플릿 모델 사본입니다.
        """
        with self._lock:
            stored = template.model_copy(deep=True)
            self._templates.append(stored)
            return stored.model_copy(deep=True)

    def delete_template(self, template_id: str) -> None:
        """지정한 식별자의 답변 템플릿을 삭제합니다.

        Args:
            template_id: 삭제할 템플릿 식별자입니다.

        Raises:
            AppError: 일치하는 템플릿이 없을 때 발생합니다.
        """
        with self._lock:
            before = len(self._templates)
            self._templates = [tpl for tpl in self._templates if tpl.id != template_id]
            if len(self._templates) == before:
                raise AppError(404, "not_found", "템플릿을 찾을 수 없습니다.")

    def reset_default_templates(self) -> list[AnswerTemplate]:
        """삭제된 기본 답변 템플릿만 복원하고 기존 커스텀 항목은 유지합니다.

        Returns:
            복원 후 전체 템플릿 목록입니다.
        """
        with self._lock:
            existing_ids = {tpl.id for tpl in self._templates}
            for tpl_id, title, content in DEFAULT_ANSWER_TEMPLATES:
                if tpl_id not in existing_ids:
                    self._templates.append(
                        AnswerTemplate(
                            id=tpl_id, title=title, content=content, is_default=True
                        )
                    )
            return [tpl.model_copy(deep=True) for tpl in self._templates]


class PostgresRepository:
    """PostgreSQL `complaint_app`에 민원 JSON을 저장하는 업무 저장소입니다.

    검색 색인 `complaint_rag`와 테이블을 섞지 않습니다.

    Args:
        conninfo: libpq 연결 문자열입니다. 비면 `PGHOST` 등 표준 환경변수를 씁니다.
        schema: 업무 스키마 이름입니다. 기본값은 `complaint_app`입니다.
    """

    storage: StorageKind = "postgresql"

    def __init__(self, conninfo: str = "", schema: str = "complaint_app") -> None:
        """연결을 확인하고 업무 스키마·테이블을 준비합니다.

        `CREATE TABLE IF NOT EXISTS`는 예전 행의 컬럼을 더하지 않습니다.
        `version`이 없으면 payload 값 또는 1로 채운 뒤 NOT NULL과
        `version > 0` 제약을 맞추고, 상태·공개 범위·지역 값의 CHECK 제약도
        추가합니다. 기존 민원 행은 지우지 않습니다.

        Args:
            conninfo: PostgreSQL 연결 정보입니다.
            schema: 생성·사용할 스키마 이름입니다.
        """
        self.conninfo = conninfo
        self.schema = schema
        ident = sql.Identifier(schema)
        self._sql_all = sql.SQL(
            "SELECT payload FROM {}.complaints ORDER BY created_at DESC, id DESC"
        ).format(ident)
        self._sql_get = sql.SQL(
            "SELECT payload FROM {}.complaints WHERE id = %s"
        ).format(ident)
        self._sql_lock = sql.SQL(
            "SELECT payload FROM {}.complaints WHERE id = %s FOR UPDATE"
        ).format(ident)
        self._sql_key = sql.SQL(
            "SELECT fingerprint, complaint_id FROM {}.idempotency "
            "WHERE owner = %s AND key = %s"
        ).format(ident)
        self._sql_insert = sql.SQL(
            "INSERT INTO {}.complaints (id, version, created_at, payload) "
            "VALUES (%s, %s, %s, %s)"
        ).format(ident)
        self._sql_insert_key = sql.SQL(
            "INSERT INTO {}.idempotency "
            "(owner, key, fingerprint, complaint_id) VALUES (%s, %s, %s, %s)"
        ).format(ident)
        self._sql_update = sql.SQL(
            "UPDATE {}.complaints SET version = %s, payload = %s "
            "WHERE id = %s AND version = %s"
        ).format(ident)
        self._sql_delete_keys = sql.SQL(
            "DELETE FROM {}.idempotency WHERE complaint_id = %s"
        ).format(ident)
        self._sql_delete = sql.SQL(
            "DELETE FROM {}.complaints WHERE id = %s AND version = %s"
        ).format(ident)
        self._sql_list_tpl = sql.SQL(
            "SELECT id, title, content, is_default, created_at "
            "FROM {}.answer_templates ORDER BY created_at ASC, id ASC"
        ).format(ident)
        self._sql_insert_tpl = sql.SQL(
            "INSERT INTO {}.answer_templates (id, title, content, is_default, created_at) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (id) DO NOTHING"
        ).format(ident)
        self._sql_delete_tpl = sql.SQL(
            "DELETE FROM {}.answer_templates WHERE id = %s"
        ).format(ident)
        self._sql_seed_meta = sql.SQL(
            "INSERT INTO {}.app_meta (key, value) VALUES (%s, %s) "
            "ON CONFLICT (key) DO NOTHING RETURNING key"
        ).format(ident)
        with self.connection() as conn:
            for statement in _SCHEMA_STATEMENTS:
                conn.execute(sql.SQL(statement).format(schema=ident))
            self._ensure_version_check(conn)
            self._ensure_value_checks(conn)
            self._ensure_default_templates(conn)

    def _ensure_version_check(self, conn: psycopg.Connection) -> None:
        """예전 테이블에 `version > 0` 제약이 없으면 추가합니다.

        Args:
            conn: 스키마를 준비 중인 연결입니다.
        """
        table = sql.SQL("{}.{}").format(
            sql.Identifier(self.schema), sql.Identifier("complaints")
        )
        found = conn.execute(
            """
            SELECT 1
            FROM pg_constraint
            WHERE conrelid = %s::regclass
              AND contype = 'c'
              AND position('version > 0' in pg_get_constraintdef(oid)) > 0
            """,
            (f"{self.schema}.complaints",),
        ).fetchone()
        if found:
            return
        conn.execute(
            sql.SQL(
                "ALTER TABLE {} ADD CONSTRAINT complaints_version_positive "
                "CHECK (version > 0)"
            ).format(table)
        )

    def _ensure_value_checks(self, conn: psycopg.Connection) -> None:
        """상태·공개 범위·지역 값을 DB가 검사하도록 CHECK 조건을 한 번만 추가합니다.

        이미 같은 이름의 조건이 있으면 건너뜁니다. 칼럼이 NULL인 예전 행은
        CHECK가 통과시키므로 기존 데이터를 지우거나 바꾸지 않습니다.

        Args:
            conn: 스키마를 준비 중인 연결입니다.
        """
        table = sql.SQL("{}.{}").format(
            sql.Identifier(self.schema), sql.Identifier("complaints")
        )
        for name, expression in _VALUE_CHECKS:
            found = conn.execute(
                "SELECT 1 FROM pg_constraint WHERE conrelid = %s::regclass AND conname = %s",
                (f"{self.schema}.complaints", name),
            ).fetchone()
            if found:
                continue
            conn.execute(
                sql.SQL("ALTER TABLE {} ADD CONSTRAINT {} CHECK ({})").format(
                    table, sql.Identifier(name), sql.SQL(expression)
                )
            )

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection]:
        """연결을 닫고 실패 시 트랜잭션을 되돌립니다.

        `conninfo`가 비면 libpq 환경변수(`PGHOST` 등)로 접속합니다.

        Yields:
            트랜잭션을 처리할 PostgreSQL 연결입니다.
        """
        if self.conninfo:
            conn = psycopg.connect(self.conninfo, connect_timeout=10)
        else:
            conn = psycopg.connect(connect_timeout=10)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def all(self) -> list[Complaint]:
        """저장된 전체 업무 민원을 최신 등록순으로 반환합니다."""
        with self.connection() as conn:
            rows = conn.execute(self._sql_all).fetchall()
        return [Complaint.model_validate(row[0]) for row in rows]

    def get(self, complaint_id: str) -> Complaint:
        """민원 식별자로 조회하며 누락은 404 업무 오류로 처리합니다.

        Args:
            complaint_id: 업무 민원 식별자입니다.

        Returns:
            저장된 민원 모델입니다.

        Raises:
            AppError: 민원이 없으면 발생합니다.
        """
        with self.connection() as conn:
            result = conn.execute(self._sql_get, (complaint_id,)).fetchone()
        if result is None:
            raise AppError(404, "not_found", "민원을 찾을 수 없습니다.")
        return Complaint.model_validate(result[0])

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
        payload = Jsonb(row.model_dump(mode="json"))
        with self.connection() as conn:
            if key:
                old = conn.execute(self._sql_key, (row.owner, key)).fetchone()
                if old:
                    if old[0] != fingerprint:
                        raise AppError(
                            409,
                            "idempotency_conflict",
                            "동일 등록 키에 다른 내용이 전송되었습니다.",
                        )
                    stored = conn.execute(self._sql_get, (old[1],)).fetchone()
                    if stored is None:
                        raise AppError(404, "not_found", "민원을 찾을 수 없습니다.")
                    return Complaint.model_validate(stored[0])
            conn.execute(
                self._sql_insert,
                (row.id, row.version, row.date, payload),
            )
            if key:
                conn.execute(
                    self._sql_insert_key,
                    (row.owner, key, fingerprint, row.id),
                )
        return row

    def change(
        self, complaint_id: str, expected: int, action: Callable[[Complaint], None]
    ) -> Complaint:
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
        with self.connection() as conn:
            result = conn.execute(self._sql_lock, (complaint_id,)).fetchone()
            if result is None:
                raise AppError(404, "not_found", "민원을 찾을 수 없습니다.")
            row = Complaint.model_validate(result[0])
            if row.version != expected:
                raise AppError(
                    409,
                    "version_conflict",
                    "다른 화면에서 내용이 변경되었습니다. 입력을 보관한 뒤 최신 내용을 불러와 주세요.",
                )
            action(row)
            row.version += 1
            conn.execute(
                self._sql_update,
                (
                    row.version,
                    Jsonb(row.model_dump(mode="json")),
                    complaint_id,
                    expected,
                ),
            )
        return row

    def delete(
        self, complaint_id: str, expected: int, check: Callable[[Complaint], None]
    ) -> None:
        """트랜잭션 안에서 버전·권한을 검증하고 민원과 멱등성 키를 영구 삭제합니다.

        Args:
            complaint_id: 삭제할 민원 식별자입니다.
            expected: 기대하는 현재 버전입니다.
            check: 삭제 가능 여부를 검증할 함수입니다.

        Raises:
            AppError: 대상이 없거나 버전 충돌·권한 검증 실패 시 발생합니다.
        """
        with self.connection() as conn:
            result = conn.execute(self._sql_lock, (complaint_id,)).fetchone()
            if result is None:
                raise AppError(404, "not_found", "민원을 찾을 수 없습니다.")
            row = Complaint.model_validate(result[0])
            if row.version != expected:
                raise AppError(
                    409,
                    "version_conflict",
                    "다른 화면에서 내용이 변경되었습니다. 입력을 보관한 뒤 최신 내용을 불러와 주세요.",
                )
            check(row)
            # idempotency 테이블이 complaints를 외래 키로 참조하므로 먼저 정리한다.
            conn.execute(self._sql_delete_keys, (complaint_id,))
            deleted = conn.execute(self._sql_delete, (complaint_id, expected))
            if deleted.rowcount == 0:
                raise AppError(
                    409,
                    "version_conflict",
                    "다른 화면에서 내용이 변경되었습니다. 입력을 보관한 뒤 최신 내용을 불러와 주세요.",
                )

    def _ensure_default_templates(self, conn: psycopg.Connection) -> None:
        """최초 스키마 초기화 시 한 번만 기본 답변 템플릿 5건을 넣습니다.

        Args:
            conn: 스키마를 준비 중인 PostgreSQL 연결입니다.
        """
        inserted = conn.execute(
            self._sql_seed_meta, ("default_templates_seeded", "1")
        ).fetchone()
        if inserted is None:
            return
        self._insert_default_template_rows(conn)

    def _insert_default_template_rows(self, conn: psycopg.Connection) -> None:
        """누락된 기본 답변 템플릿 행을 순서대로 삽입합니다.

        Args:
            conn: 활성 PostgreSQL 연결입니다.
        """
        # created_at ASC 정렬 순서를 고정하려고 1ms 간격으로 기본 템플릿 시각을 둔다.
        base_time = utcnow()
        for idx, (tpl_id, title, content) in enumerate(DEFAULT_ANSWER_TEMPLATES):
            conn.execute(
                self._sql_insert_tpl,
                (tpl_id, title, content, True, base_time + timedelta(milliseconds=idx)),
            )

    def list_templates(self) -> list[AnswerTemplate]:
        """담당자 답변 편집기용 템플릿 목록을 등록순으로 반환합니다."""
        with self.connection() as conn:
            rows = conn.execute(self._sql_list_tpl).fetchall()
        return [
            AnswerTemplate(
                id=row[0],
                title=row[1],
                content=row[2],
                is_default=bool(row[3]),
                created_at=row[4],
            )
            for row in rows
        ]

    def create_template(self, template: AnswerTemplate) -> AnswerTemplate:
        """새 답변 템플릿을 PostgreSQL 테이블에 저장하고 반환합니다.

        Args:
            template: 저장할 템플릿 모델입니다.

        Returns:
            저장한 템플릿 모델입니다.
        """
        with self.connection() as conn:
            conn.execute(
                self._sql_insert_tpl,
                (
                    template.id,
                    template.title,
                    template.content,
                    template.is_default,
                    template.created_at,
                ),
            )
        return template

    def delete_template(self, template_id: str) -> None:
        """지정한 답변 템플릿을 PostgreSQL 테이블에서 삭제합니다.

        Args:
            template_id: 삭제할 템플릿 식별자입니다.

        Raises:
            AppError: 일치하는 템플릿이 없을 때 발생합니다.
        """
        with self.connection() as conn:
            deleted = conn.execute(self._sql_delete_tpl, (template_id,))
            if deleted.rowcount == 0:
                raise AppError(404, "not_found", "템플릿을 찾을 수 없습니다.")

    def reset_default_templates(self) -> list[AnswerTemplate]:
        """삭제된 기본 답변 템플릿만 복원하고 전체 목록을 반환합니다."""
        with self.connection() as conn:
            self._insert_default_template_rows(conn)
        return self.list_templates()
