"""업무 저장소가 구현해야 하는 `ComplaintRepository` 프로토콜입니다."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from src.complaints.auth import StoredUser
from src.complaints.models import (
    AnswerTemplate,
    AttachmentItem,
    ChatSessionDetail,
    ChatSessionSummary,
    CitizenChatResponse,
    Complaint,
    NormalizedDbSummary,
)
from src.complaints.repository.schema import StorageKind


class ComplaintRepository(Protocol):
    """업무·인증 서비스가 의존하는 저장소 인터페이스입니다."""

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
        """민원과 등록 키·정규화 하위 테이블을 같은 트랜잭션에 저장합니다.

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
        """최신 버전을 검사한 뒤 업무 변경과 7테이블 동기화를 원자적으로 저장합니다.

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
        """최신 버전을 검사한 뒤 민원과 연결된 하위 테이블·멱등성 키를 영구 삭제합니다.

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

    def get_user_by_id(self, user_id: str) -> StoredUser | None:
        """고유 식별자로 사용자 계정을 조회합니다.

        Args:
            user_id: `users.id` 값입니다.
        """
        ...

    def get_user_by_login(self, login_id: str) -> StoredUser | None:
        """로그인 아이디로 사용자 계정을 조회합니다.

        Args:
            login_id: 로그인 아이디 문자열입니다.
        """
        ...

    def create_user(self, user: StoredUser) -> StoredUser:
        """새 사용자 계정을 저장하고 반환합니다.

        Args:
            user: 저장할 `StoredUser` 레코드입니다.
        """
        ...

    def touch_user_login(self, user_id: str) -> None:
        """사용자의 마지막 로그인 시각(`last_login_at`)을 갱신합니다.

        Args:
            user_id: 로그인에 성공한 `users.id`입니다.
        """
        ...

    def list_users(self) -> list[StoredUser]:
        """저장된 전체 사용자 계정 목록을 반환합니다."""
        ...

    def normalized_summary(self) -> NormalizedDbSummary:
        """정규화 7테이블의 행 수와 AI 판정·사용자 역할 집계를 반환합니다."""
        ...

    def list_chat_sessions(
        self, user_id: str, limit: int = 30
    ) -> list[ChatSessionSummary]:
        """특정 민원인의 챗봇 대화 세션 목록을 최근 갱신순으로 반환합니다.

        Args:
            user_id: 소유 민원인의 `users.id`입니다.
            limit: 최대 반환 세션 개수입니다.
        """
        ...

    def get_chat_session(self, session_id: str, user_id: str) -> ChatSessionDetail:
        """소유권을 검증해 단일 챗봇 대화 세션과 발화 이력을 반환합니다.

        Args:
            session_id: 조회할 챗봇 세션 ID입니다.
            user_id: 요청한 민원인의 `users.id`입니다.

        Raises:
            AppError: 세션이 없거나 타인 소유이면 404를 발생합니다.
        """
        ...

    def save_chat_exchange(
        self,
        *,
        user_id: str,
        session_id: str | None,
        user_text: str,
        user_district: str | None,
        assistant_response: CitizenChatResponse,
    ) -> str:
        """시민 발화와 안전 투영된 도우미 응답 한 쌍을 원자적으로 저장합니다.

        Args:
            user_id: 소유 민원인의 `users.id`입니다.
            session_id: 이어 쓸 기존 세션 ID입니다. None이면 새 세션을 생성합니다.
            user_text: 시민이 입력한 이번 턴 원문입니다.
            user_district: 이번 턴에 적용한 관할 구 또는 None입니다.
            assistant_response: 민감 필드가 제거된 `CitizenChatResponse` 모델입니다.

        Returns:
            저장된 세션 ID입니다.
        """
        ...

    def delete_chat_session(self, session_id: str, user_id: str) -> None:
        """소유 민원인의 챗봇 대화 세션과 하위 메시지를 연쇄 삭제합니다.

        Args:
            session_id: 삭제할 챗봇 세션 ID입니다.
            user_id: 요청한 민원인의 `users.id`입니다.

        Raises:
            AppError: 세션이 없거나 타인 소유이면 404를 발생합니다.
        """
        ...

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
        """민원 잠금 안에서 권한·개수를 검증하고 첨부 메타데이터를 원자 저장합니다.

        Args:
            complaint_id: 대상 민원 식별자입니다.
            item: 저장할 첨부파일 메타데이터 모델입니다.
            sha256_hex: 정제된 바이트의 SHA-256 해시입니다.
            storage_key: 저장소에 기록된 평면 파일 키입니다.
            max_count: 민원당 최대 허용 첨부 개수입니다.
            action_check: 잠금된 민원의 작성자·상태를 검증하는 콜백입니다.

        Returns:
            `(갱신된 민원, 저장된 첨부 메타데이터)` 튜플입니다.
        """
        ...

    def get_attachment_meta(
        self, complaint_id: str, attachment_id: str
    ) -> tuple[AttachmentItem, str]:
        """첨부파일 메타데이터와 내부 저장 키를 조회합니다.

        Args:
            complaint_id: 소속 민원 식별자입니다.
            attachment_id: 조회할 첨부파일 식별자입니다.

        Returns:
            `(첨부 메타데이터, storage_key)` 튜플입니다.
        """
        ...

    def list_attachment_keys(self, complaint_id: str) -> list[str]:
        """민원에 연결된 모든 첨부파일 저장 키 목록을 반환합니다.

        Args:
            complaint_id: 대상 민원 식별자입니다.
        """
        ...

    def delete_attachment(
        self,
        *,
        complaint_id: str,
        attachment_id: str,
        action_check: Callable[[Complaint], None],
    ) -> tuple[Complaint, str]:
        """민원 잠금 안에서 권한을 검증하고 첨부 행을 제거한 뒤 저장 키를 반환합니다.

        Args:
            complaint_id: 소속 민원 식별자입니다.
            attachment_id: 삭제할 첨부파일 식별자입니다.
            action_check: 삭제 권한·상태를 검증하는 콜백입니다.

        Returns:
            `(갱신된 민원, 삭제할 storage_key)` 튜플입니다.
        """
        ...
