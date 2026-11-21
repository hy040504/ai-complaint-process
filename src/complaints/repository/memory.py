"""단위 테스트와 임시 실행에 쓰는 메모리 업무 저장소입니다."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from threading import Lock
from uuid import uuid4

from src.complaints.auth import StoredUser, default_seed_users
from src.complaints.errors import AppError
from src.complaints.models import (
    AnswerTemplate,
    AttachmentItem,
    ChatMessageRecord,
    ChatSessionDetail,
    ChatSessionSummary,
    CitizenChatResponse,
    Complaint,
    History,
    NormalizedDbSummary,
    utcnow,
)
from src.complaints.repository.schema import StorageKind, DEFAULT_ANSWER_TEMPLATES


class MemoryRepository:
    """프로세스 안의 업무 저장소입니다. 단위 테스트 전용입니다.

    PostgreSQL 없이 7테이블 계약과 인증 계정을 동일한 인터페이스로 검증할 때 씁니다.
    """

    storage: StorageKind = "memory"

    def __init__(self) -> None:
        """빈 민원·멱등성 맵, 기본 시드 사용자·답변 템플릿과 변경 잠금을 준비합니다."""
        self._rows: dict[str, Complaint] = {}
        self._keys: dict[tuple[str, str], tuple[str, str]] = {}
        self._users: dict[str, StoredUser] = {
            user.id: user for user in default_seed_users()
        }
        self._templates: list[AnswerTemplate] = [
            AnswerTemplate(id=tpl_id, title=title, content=content, is_default=True)
            for tpl_id, title, content in DEFAULT_ANSWER_TEMPLATES
        ]
        self._chat_sessions: dict[
            str, tuple[str, ChatSessionSummary, list[ChatMessageRecord]]
        ] = {}
        self._attachments: dict[tuple[str, str], tuple[AttachmentItem, str, str]] = {}
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
            stale_atts = [
                att_key for att_key in self._attachments if att_key[0] == complaint_id
            ]
            for att_key in stale_atts:
                del self._attachments[att_key]

    def list_templates(self) -> list[AnswerTemplate]:
        """담당자 답변 편집기용 템플릿 목록을 등록순으로 반환합니다.

        Returns:
            등록순으로 정렬된 답변 템플릿 모델 목록 사본입니다.
        """
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

    def get_user_by_id(self, user_id: str) -> StoredUser | None:
        """고유 식별자로 메모리 사용자 계정을 조회합니다.

        Args:
            user_id: 사용자 고유 ID입니다.

        Returns:
            일치하는 `StoredUser` 또는 None입니다.
        """
        with self._lock:
            return self._users.get(user_id)

    def get_user_by_login(self, login_id: str) -> StoredUser | None:
        """로그인 아이디(대소문자 무시)로 메모리 사용자 계정을 조회합니다.

        Args:
            login_id: 로그인 아이디입니다.

        Returns:
            일치하는 `StoredUser` 또는 None입니다.
        """
        target = login_id.casefold()
        with self._lock:
            for user in self._users.values():
                if user.login_id.casefold() == target:
                    return user
        return None

    def create_user(self, user: StoredUser) -> StoredUser:
        """새 사용자 계정을 메모리에 저장하며 아이디 중복을 거부합니다.

        Args:
            user: 저장할 사용자 레코드입니다.

        Returns:
            저장된 사용자 레코드입니다.

        Raises:
            AppError: 동일한 `login_id`가 이미 존재하면 409를 발생합니다.
        """
        target = user.login_id.casefold()
        with self._lock:
            if any(u.login_id.casefold() == target for u in self._users.values()):
                raise AppError(409, "login_id_taken", "이미 사용 중인 아이디입니다.")
            self._users[user.id] = user
        return user

    def touch_user_login(self, user_id: str) -> None:
        """메모리 사용자의 마지막 로그인 시각을 현재 UTC로 갱신합니다.

        Args:
            user_id: 사용자 고유 ID입니다.
        """
        with self._lock:
            old = self._users.get(user_id)
            if old is None:
                return
            self._users[user_id] = StoredUser(
                id=old.id,
                login_id=old.login_id,
                display_name=old.display_name,
                role=old.role,
                password_hash=old.password_hash,
                department=old.department,
                is_demo=old.is_demo,
                active=old.active,
                created_at=old.created_at,
                last_login_at=utcnow(),
            )

    def list_users(self) -> list[StoredUser]:
        """메모리에 저장된 전체 사용자 계정을 반환합니다."""
        with self._lock:
            return list(self._users.values())

    def normalized_summary(self) -> NormalizedDbSummary:
        """메모리 저장소의 7테이블 환산 행 수와 AI·역할 집계를 계산합니다.

        Returns:
            `NormalizedDbSummary` 응답 모델입니다.
        """
        with self._lock:
            rows = list(self._rows.values())
            users = list(self._users.values())
        msg_count = 0
        ver_count = 0
        job_count = len(rows)
        result_count = 0
        event_count = 0
        outcomes: dict[str, int] = {}
        for row in rows:
            msg_count += len(row.messages) + (
                1 if (row.versions or row.draft or row.published) else 0
            )
            ver_count += len(row.versions)
            event_count += len(row.job.events)
            if row.ai_assist is not None:
                result_count += 1
                out = row.ai_assist.outcome
                outcomes[out] = outcomes.get(out, 0) + 1
        roles: dict[str, int] = {}
        for user in users:
            roles[user.role] = roles.get(user.role, 0) + 1
        return NormalizedDbSummary(
            schema_name="memory",
            storage="memory",
            normalized_tables={
                "users": len(users),
                "complaints": len(rows),
                "messages": msg_count,
                "message_versions": ver_count,
                "ai_jobs": job_count,
                "ai_results": result_count,
                "job_events": event_count,
            },
            ai_outcomes=outcomes,
            user_roles=roles,
        )

    def list_chat_sessions(
        self, user_id: str, limit: int = 30
    ) -> list[ChatSessionSummary]:
        """메모리 저장소에서 특정 민원인의 챗봇 세션 목록을 최근 갱신순으로 반환합니다.

        Args:
            user_id: 소유 민원인의 `users.id`입니다.
            limit: 최대 반환 세션 수입니다.

        Returns:
            소유 민원인의 `ChatSessionSummary` 사본 목록입니다.
        """
        with self._lock:
            owned = [
                summary.model_copy(update={"message_count": len(messages)}, deep=True)
                for owner, summary, messages in self._chat_sessions.values()
                if owner == user_id
            ]
        owned.sort(key=lambda item: (item.updated_at, item.id), reverse=True)
        return owned[: max(1, limit)]

    def get_chat_session(self, session_id: str, user_id: str) -> ChatSessionDetail:
        """메모리 저장소에서 소유권을 검증해 챗봇 세션 상세와 발화 이력을 반환합니다.

        Args:
            session_id: 조회할 챗봇 세션 ID입니다.
            user_id: 요청한 민원인의 `users.id`입니다.

        Returns:
            세션 요약과 메시지 목록이 담긴 `ChatSessionDetail`입니다.

        Raises:
            AppError: 세션이 없거나 소유자가 다르면 404를 발생합니다.
        """
        with self._lock:
            entry = self._chat_sessions.get(session_id)
            if entry is None or entry[0] != user_id:
                raise AppError(404, "not_found", "대화 세션을 찾을 수 없습니다.")
            _, summary, messages = entry
            return ChatSessionDetail(
                session=summary.model_copy(
                    update={"message_count": len(messages)}, deep=True
                ),
                messages=[msg.model_copy(deep=True) for msg in messages],
            )

    def save_chat_exchange(
        self,
        *,
        user_id: str,
        session_id: str | None,
        user_text: str,
        user_district: str | None,
        assistant_response: CitizenChatResponse,
    ) -> str:
        """시민 질문과 안전 투영된 도우미 응답을 메모리 세션에 저장합니다.

        Args:
            user_id: 소유 민원인의 `users.id`입니다.
            session_id: 이어 쓸 기존 세션 ID 또는 None입니다.
            user_text: 시민이 입력한 질문 원문입니다.
            user_district: 이번 턴에 적용된 관할 구 또는 None입니다.
            assistant_response: 시민 전용 안전 응답 모델입니다.

        Returns:
            생성 또는 갱신된 세션 ID입니다.

        Raises:
            AppError: 지정한 세션이 없거나 소유자가 다르면 404를 발생합니다.
        """
        user_ts = utcnow()
        assistant_ts = user_ts + timedelta(milliseconds=1)
        resolved_district = (
            assistant_response.district
            if assistant_response.district != "모름"
            else user_district
        )
        with self._lock:
            if session_id:
                entry = self._chat_sessions.get(session_id)
                if entry is None or entry[0] != user_id:
                    raise AppError(404, "not_found", "대화 세션을 찾을 수 없습니다.")
                _, summary, messages = entry
                resolved_sid = session_id
                summary = summary.model_copy(
                    update={
                        "last_district": resolved_district or summary.last_district,
                        "updated_at": assistant_ts,
                    },
                    deep=True,
                )
            else:
                resolved_sid = f"CHAT-{user_ts.year}-{uuid4().hex[:10].upper()}"
                title = " ".join(user_text.split())[:60] or "새 대화"
                summary = ChatSessionSummary(
                    id=resolved_sid,
                    title=title,
                    last_district=resolved_district,
                    message_count=0,
                    created_at=user_ts,
                    updated_at=assistant_ts,
                )
                messages = []
            safe_payload = assistant_response.model_copy(
                update={"session_id": resolved_sid, "persisted": True}, deep=True
            )
            messages.append(
                ChatMessageRecord(
                    id=f"CMSG-{uuid4().hex[:12].upper()}",
                    role="user",
                    content=user_text,
                    district=user_district,
                    created_at=user_ts,
                )
            )
            messages.append(
                ChatMessageRecord(
                    id=f"CMSG-{uuid4().hex[:12].upper()}",
                    role="assistant",
                    content=safe_payload.answer,
                    district=resolved_district,
                    outcome=safe_payload.outcome,
                    reason_code=safe_payload.reason_code,
                    payload=safe_payload,
                    created_at=assistant_ts,
                )
            )
            summary = summary.model_copy(update={"message_count": len(messages)})
            self._chat_sessions[resolved_sid] = (user_id, summary, messages)
        return resolved_sid

    def delete_chat_session(self, session_id: str, user_id: str) -> None:
        """메모리 저장소에서 소유 민원인의 챗봇 세션을 삭제합니다.

        Args:
            session_id: 삭제할 챗봇 세션 ID입니다.
            user_id: 요청한 민원인의 `users.id`입니다.

        Raises:
            AppError: 세션이 없거나 타인 소유이면 404를 발생합니다.
        """
        with self._lock:
            entry = self._chat_sessions.get(session_id)
            if entry is None or entry[0] != user_id:
                raise AppError(404, "not_found", "대화 세션을 찾을 수 없습니다.")
            del self._chat_sessions[session_id]

    def add_attachment(
        self,
        *,
        complaint_id: str,
        item: AttachmentItem,
        sha256_hex: str,
        storage_key: str,
        max_count: int,
        action_check: Callable[[Complaint], None],
    ) -> tuple[Complaint, AttachmentItem]:
        """메모리 저장소에서 잠금 안에 권한·개수를 검사하고 첨부 메타데이터를 저장합니다.

        Args:
            complaint_id: 대상 민원 식별자입니다.
            item: 저장할 첨부 메타데이터 모델입니다.
            sha256_hex: 정제된 바이트의 SHA-256 해시입니다.
            storage_key: 저장소에 기록된 파일 키입니다.
            max_count: 민원당 최대 허용 첨부 개수입니다.
            action_check: 작성자·상태를 검증하는 콜백입니다.

        Returns:
            `(갱신된 민원 사본, 저장된 첨부 메타데이터 사본)` 튜플입니다.
        """
        with self._lock:
            current = self._rows.get(complaint_id)
            if current is None:
                raise AppError(404, "not_found", "민원을 찾을 수 없습니다.")
            row = current.model_copy(deep=True)
            action_check(row)
            if len(row.attachments) >= max_count:
                raise AppError(
                    409,
                    "attachment_limit_exceeded",
                    f"민원당 첨부파일은 최대 {max_count}개까지 등록할 수 있습니다.",
                )
            stored_item = item.model_copy(deep=True)
            row.attachments.append(stored_item)
            row.history.append(
                History(text=f"시민이 첨부파일 등록: {stored_item.filename}")
            )
            row.version += 1
            self._rows[complaint_id] = row
            self._attachments[(complaint_id, stored_item.id)] = (
                stored_item,
                sha256_hex,
                storage_key,
            )
        return row.model_copy(deep=True), stored_item.model_copy(deep=True)

    def get_attachment_meta(
        self, complaint_id: str, attachment_id: str
    ) -> tuple[AttachmentItem, str]:
        """메모리 저장소에서 첨부 메타데이터와 저장 키를 조회합니다.

        Args:
            complaint_id: 소속 민원 식별자입니다.
            attachment_id: 조회할 첨부 식별자입니다.

        Returns:
            `(첨부 메타데이터 사본, storage_key)` 튜플입니다.
        """
        with self._lock:
            entry = self._attachments.get((complaint_id, attachment_id))
        if entry is None:
            raise AppError(404, "not_found", "첨부파일을 찾을 수 없습니다.")
        return entry[0].model_copy(deep=True), entry[2]

    def list_attachment_keys(self, complaint_id: str) -> list[str]:
        """메모리 저장소에서 특정 민원의 첨부 저장 키 목록을 반환합니다.

        Args:
            complaint_id: 대상 민원 식별자입니다.

        Returns:
            연결된 `storage_key` 문자열 목록입니다.
        """
        with self._lock:
            return [
                storage_key
                for (cid, _aid), (_item, _sha, storage_key) in self._attachments.items()
                if cid == complaint_id
            ]

    def delete_attachment(
        self,
        *,
        complaint_id: str,
        attachment_id: str,
        action_check: Callable[[Complaint], None],
    ) -> tuple[Complaint, str]:
        """메모리 저장소에서 권한을 검증하고 첨부 항목을 제거합니다.

        Args:
            complaint_id: 소속 민원 식별자입니다.
            attachment_id: 삭제할 첨부 식별자입니다.
            action_check: 삭제 권한·상태를 검증하는 콜백입니다.

        Returns:
            `(갱신된 민원 사본, 삭제할 storage_key)` 튜플입니다.
        """
        with self._lock:
            current = self._rows.get(complaint_id)
            if current is None:
                raise AppError(404, "not_found", "민원을 찾을 수 없습니다.")
            entry = self._attachments.get((complaint_id, attachment_id))
            if entry is None:
                raise AppError(404, "not_found", "첨부파일을 찾을 수 없습니다.")
            row = current.model_copy(deep=True)
            action_check(row)
            removed_item, _sha, storage_key = entry
            row.attachments = [
                att for att in row.attachments if att.id != attachment_id
            ]
            row.history.append(
                History(text=f"시민이 첨부파일 삭제: {removed_item.filename}")
            )
            row.version += 1
            self._rows[complaint_id] = row
            del self._attachments[(complaint_id, attachment_id)]
        return row.model_copy(deep=True), storage_key
