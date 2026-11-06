"""권한·업무 상태·답변 게시·입력 버전을 검증하는 서비스입니다."""

from collections.abc import Callable
from hashlib import sha256
from typing import Literal
from uuid import uuid4

from src.complaints.errors import AppError
from src.complaints.models import (
    Actor,
    Answer,
    AnswerInput,
    AnswerVersion,
    AssignmentInput,
    Complaint,
    ComplaintInput,
    ComplaintUpdate,
    Event,
    History,
    Job,
    ListQuery,
    Message,
    MessageInput,
    PublicComplaint,
    PublicPage,
    PublicWorkspace,
    ReasonInput,
    StaffPage,
    StaffWorkspace,
    VersionInput,
    utcnow,
)
from src.complaints.repository import ComplaintRepository

Operation = Literal[
    "withdraw",
    "message",
    "review",
    "assign",
    "draft",
    "publish",
    "retract",
    "retry",
    "cancel",
]


class ComplaintService:
    """저장소 구현을 알지 않고 업무 경계를 검사합니다.

    Args:
        repository: 타입 인터페이스를 만족하는 업무 저장소입니다.
    """

    def __init__(self, repository: ComplaintRepository) -> None:
        """업무 저장소 인터페이스를 주입합니다.

        Args:
            repository: 민원 조회·생성·원자 변경을 제공하는 저장소입니다.
        """
        self.repository = repository

    def get(self, actor: Actor, complaint_id: str) -> Complaint:
        """역할과 공개 범위를 검사한 민원을 반환합니다.

        Args:
            actor: 서버 세션에서 확인한 사용자입니다.
            complaint_id: 업무 민원 식별자입니다.

        Returns:
            접근 가능한 민원입니다. 시민 반환에는 별도 투영이 필요합니다.

        Raises:
            AppError: 민원이 없거나 접근할 수 없으면 발생합니다.
        """
        row = self.repository.get(complaint_id)
        if row.status == "withdrawn" or (
            actor.role != "staff"
            and row.owner != actor.id
            and row.visibility != "public"
        ):
            raise AppError(404, "not_found", "민원을 찾을 수 없습니다.")
        return row

    def project(self, actor: Actor, row: Complaint) -> PublicComplaint | Complaint:
        """시민 응답에서 초안·AI 원문·내부 이벤트를 구조적으로 제거합니다.

        Args:
            actor: 조회 사용자입니다.
            row: 권한 검사를 거친 민원입니다.

        Returns:
            역할에 맞는 응답 전용 모델입니다.
        """
        if actor.role == "staff":
            return row
        public = PublicComplaint.model_validate(
            row.model_dump(include=set(PublicComplaint.model_fields))
        )
        public.history = [entry for entry in public.history if entry.public]
        return public

    def workspace(self, actor: Actor) -> PublicWorkspace | StaffWorkspace:
        """로컬 시연 화면에 필요한 권한별 스냅샷을 반환합니다.

        Args:
            actor: 서버에서 확인한 시연 사용자입니다.

        Returns:
            시민 또는 담당자의 허용된 업무 데이터입니다.
        """
        if actor.role == "staff":
            self.advance_jobs()
        rows = [
            row
            for row in self.repository.all()
            if row.status != "withdrawn"
            and (
                actor.role == "staff"
                or row.owner == actor.id
                or row.visibility == "public"
            )
        ]
        revision = sum(row.version for row in rows)
        if actor.role == "staff":
            return StaffWorkspace(complaints=rows, revision=revision)
        return PublicWorkspace(
            complaints=[self.project(actor, row) for row in rows], revision=revision
        )

    def page(self, actor: Actor, query: ListQuery) -> PublicPage | StaffPage:
        """서버에서 검색·필터·페이지 제한을 적용한 목록을 반환합니다.

        Args:
            actor: 조회 사용자입니다.
            query: 검증된 목록 조건입니다.

        Returns:
            권한에 맞는 페이지와 전체 건수입니다.
        """
        workspace = self.workspace(actor)
        rows = [
            row
            for row in workspace.complaints
            if (not query.q or query.q.casefold() in row.title.casefold())
            and (not query.status or row.status == query.status)
            and (not query.district or row.district == query.district)
            and (not query.category or row.category == query.category)
            and (not query.mine or row.owner == actor.id)
        ]
        if query.assign:
            if actor.role != "staff":
                raise AppError(
                    403, "staff_required", "담당자만 담당 필터를 사용할 수 있습니다."
                )
            rows = [
                row
                for row in rows
                if isinstance(row, Complaint)
                and row.assigned == (query.assign == "mine")
            ]
        total = len(rows)
        selected = rows[(query.page - 1) * query.limit : query.page * query.limit]
        if actor.role == "staff":
            return StaffPage(
                complaints=[
                    Complaint.model_validate(row.model_dump()) for row in selected
                ],
                revision=workspace.revision,
                total=total,
                page=query.page,
                limit=query.limit,
            )
        return PublicPage(
            complaints=[
                PublicComplaint.model_validate(row.model_dump()) for row in selected
            ],
            revision=workspace.revision,
            total=total,
            page=query.page,
            limit=query.limit,
        )

    def create(self, actor: Actor, body: ComplaintInput, key: str | None) -> Complaint:
        """세션 작성자로 민원과 최초 작업 상태를 함께 저장합니다.

        Args:
            actor: 등록할 시민입니다.
            body: 검증된 민원 원문입니다.
            key: 동일 등록 요청의 재전송 키입니다.

        Returns:
            새 민원 또는 동일 요청의 기존 민원입니다.

        Raises:
            AppError: 시민이 아닌 역할로 등록하면 발생합니다.
        """
        if actor.role != "citizen":
            raise AppError(
                403, "citizen_required", "시민 계정에서 민원을 등록해 주세요."
            )
        row = Complaint(
            id=f"DEMO-{utcnow().year}-{uuid4().hex[:12].upper()}",
            owner=actor.id,
            **body.model_dump(),
        )
        row.history.append(History(text="시연 서버에 민원 등록"))
        row.job.events.append(Event(stage="민원 저장 완료 · 실제 AI 미연동"))
        return self.repository.create(
            row, key, sha256(body.model_dump_json().encode()).hexdigest()
        )

    def change(
        self,
        actor: Actor,
        complaint_id: str,
        version: int,
        staff: bool,
        action: Callable[[Complaint], None],
    ) -> Complaint:
        """접근·작성 권한과 기대 버전을 검사하고 업무 변경을 실행합니다.

        Args:
            actor: 동작을 요청한 사용자입니다.
            complaint_id: 대상 업무 식별자입니다.
            version: 클라이언트가 조회한 버전입니다.
            staff: 담당자 전용 작업인지 여부입니다.
            action: 트랜잭션 안에서 수행할 업무 변경입니다.

        Returns:
            저장된 최신 민원입니다.

        Raises:
            AppError: 역할·작성자·버전이 일치하지 않으면 발생합니다.
        """
        row = self.get(actor, complaint_id)
        if staff and actor.role != "staff":
            raise AppError(403, "staff_required", "담당자만 수행할 수 있는 작업입니다.")
        if not staff and (actor.role != "citizen" or row.owner != actor.id):
            raise AppError(
                403, "owner_required", "민원 작성자만 수행할 수 있는 작업입니다."
            )
        return self.repository.change(complaint_id, version, action)

    def update(
        self, actor: Actor, complaint_id: str, body: ComplaintUpdate
    ) -> Complaint:
        """게시 전 원문을 수정하고 오래된 AI 맥락을 무효화합니다.

        Args:
            actor: 원문 작성자입니다.
            complaint_id: 수정할 민원 식별자입니다.
            body: 기대 버전을 포함한 수정 내용입니다.

        Returns:
            수정 후 민원입니다.
        """

        def apply(row: Complaint) -> None:
            """검증한 민원의 이전 원문을 보존한 뒤 필드를 변경합니다.

            Args:
                row: 트랜잭션 안에서 읽은 민원입니다.
            """
            if row.published or any(v.kind == "게시" for v in row.versions):
                raise AppError(
                    409,
                    "already_published",
                    "답변 이후 정정은 추가 문의로 남겨 주세요.",
                )
            row.versions.append(
                AnswerVersion(
                    version=row.context_version,
                    text=row.body,
                    reason="시민 수정",
                    kind="시민 원문 수정 전",
                )
            )
            row.title = body.title
            row.body = body.body
            row.district = body.district
            row.category = body.category
            row.visibility = body.visibility
            self.invalidate(row)
            if row.ai_original:
                row.versions.append(
                    AnswerVersion(
                        version=row.draft_version,
                        text=row.ai_original,
                        reason="입력 맥락 변경",
                        kind="이전 AI 원본",
                    )
                )
            row.ai_original = ""
            row.ai_candidate = ""
            row.draft = ""
            row.draft_version += 1
            row.history.append(History(text="시민이 민원 내용 수정"))

        return self.change(actor, complaint_id, body.version, False, apply)

    @staticmethod
    def invalidate(row: Complaint) -> None:
        """맥락 버전을 올리고 실행 중인 시연 결과의 적용을 중단합니다.

        Args:
            row: 변경 중인 민원입니다.
        """
        row.context_version += 1
        if row.job.status == "running":
            row.job.status = "superseded"
            row.job.stage = "입력 변경으로 적용 중단"
            row.job.events.append(Event(stage=row.job.stage))

    def _save_answer(self, row: Complaint, body: AnswerInput, publish: bool) -> None:
        """답변 버전을 보존하고 게시 요청에만 공개 상태를 변경합니다.

        Args:
            row: 현재 트랜잭션의 민원입니다.
            body: 검증한 답변과 변경 사유입니다.
            publish: 시민에게 게시할지 여부입니다.
        """
        row.draft = body.text
        row.draft_version += 1
        row.versions.append(
            AnswerVersion(
                version=row.draft_version,
                text=body.text,
                reason=body.reason,
                kind="게시" if publish else "초안 저장",
            )
        )
        if not publish:
            return
        origin: Literal["ai", "ai_edited", "staff"] = "staff"
        if row.ai_original:
            origin = "ai" if body.text == row.ai_original else "ai_edited"
        row.published = Answer(text=body.text, reason=body.reason, origin=origin)
        row.status = "answered"
        self.invalidate(row)

    def _retract_answer(self, row: Complaint, body: ReasonInput) -> None:
        """게시본을 이력에 남긴 뒤 검토 상태로 돌립니다.

        Args:
            row: 현재 트랜잭션의 민원입니다.
            body: 철회 사유입니다.

        Raises:
            AppError: 게시된 답변이 없으면 발생합니다.
        """
        if row.published is None:
            raise AppError(409, "not_published", "철회할 게시 답변이 없습니다.")
        row.versions.append(
            AnswerVersion(
                version=row.draft_version,
                text=row.published.text,
                reason=body.reason,
                kind="게시 철회",
            )
        )
        row.published = None
        row.status = "under_review"
        self.invalidate(row)

    @staticmethod
    def _start_job(row: Complaint) -> None:
        """현재 맥락에 대한 별도 시연 작업을 시작합니다.

        Args:
            row: 현재 트랜잭션의 민원입니다.

        Raises:
            AppError: 이미 시연 작업이 실행 중이면 발생합니다.
        """
        if row.job.status == "running":
            raise AppError(409, "already_running", "이미 실행 중인 시연 작업입니다.")
        row.job = Job(
            status="running",
            stage="검색 대기 · 서버 시연",
            context_version=row.context_version,
            attempt=row.job.attempt + 1,
            started_at=utcnow(),
            events=[Event(stage="서버 단계 시뮬레이션 요청")],
        )

    @staticmethod
    def _cancel_job(row: Complaint) -> None:
        """원문·편집본·게시본을 보존하며 시연 작업만 취소합니다.

        Args:
            row: 현재 트랜잭션의 민원입니다.

        Raises:
            AppError: 실행 중인 작업이 없으면 발생합니다.
        """
        if row.job.status != "running":
            raise AppError(409, "not_running", "실행 중인 시연 작업이 없습니다.")
        row.job.status = "cancelled"
        row.job.stage = "담당자가 시연 작업 취소"
        row.job.events.append(Event(stage=row.job.stage))

    def act(
        self, actor: Actor, complaint_id: str, body: VersionInput, operation: Operation
    ) -> Complaint:
        """각 동작에 허용한 필드만 적용하고 상태·기원을 서버에서 결정합니다.

        Args:
            actor: 서버 세션 사용자입니다.
            complaint_id: 대상 민원 식별자입니다.
            body: 해당 경로에서 검증한 요청 모델입니다.
            operation: 경로가 결정한 업무 동작입니다.

        Returns:
            저장 후 민원입니다.
        """

        def apply(row: Complaint) -> None:
            """요청 모델의 구체 타입에 맞는 업무 동작을 수행합니다.

            Args:
                row: 현재 버전의 민원입니다.
            """
            public = True
            if operation == "withdraw" and isinstance(body, ReasonInput):
                row.status = "withdrawn"
                self.invalidate(row)
                text = "민원 철회: " + body.reason
            elif operation == "message" and isinstance(body, MessageInput):
                row.messages.append(Message(text=body.message))
                row.status = "under_review"
                self.invalidate(row)
                text = "시민 추가 문의 등록"
            elif operation == "review":
                row.status = "under_review"
                self.invalidate(row)
                text = "시민이 담당자 재검토 요청"
            elif operation == "assign" and isinstance(body, AssignmentInput):
                row.assigned = body.assigned
                if row.assigned and row.status == "submitted":
                    row.status = "under_review"
                text = "담당자 지정" if row.assigned else "담당자 지정 해제"
            elif operation in ("draft", "publish") and isinstance(body, AnswerInput):
                publish = operation == "publish"
                self._save_answer(row, body, publish)
                text = "담당자 답변 게시" if publish else "담당자 초안 저장"
                public = publish
            elif operation == "retract" and isinstance(body, ReasonInput):
                self._retract_answer(row, body)
                text = "답변 철회: " + body.reason
            elif operation == "retry":
                self._start_job(row)
                text, public = "AI 단계 시연 요청", False
            elif operation == "cancel":
                self._cancel_job(row)
                text, public = "시연 작업 취소", False
            else:
                raise AppError(
                    400, "invalid_operation", "요청 모델과 작업이 일치하지 않습니다."
                )
            row.history.append(History(text=text, public=public))

        return self.change(
            actor,
            complaint_id,
            body.version,
            operation not in ("withdraw", "message", "review"),
            apply,
        )

    def advance_jobs(self) -> None:
        """경과 시간에 따른 시연 단계를 DB에 반영하며 실제 AI 결과를 만들지 않습니다."""
        stages = [
            "검색 단계 · 실제 검색 생략",
            "판정 단계 · 담당자 검토 필요",
            "작성 단계 · 시연 후보 준비",
            "검증 단계 · 공식 근거 미연동",
            "시연 완료 · 담당자 검토 대기",
        ]
        for row in self.repository.all():
            if row.job.status != "running" or row.job.started_at is None:
                continue
            completed = min(
                5, int((utcnow() - row.job.started_at).total_seconds() / 1.2)
            )
            if completed <= len(row.job.events) - 1:
                continue

            def advance(current: Complaint) -> None:
                """현재 맥락과 일치하는 실행 중 작업의 시연 이벤트만 갱신합니다.

                Args:
                    current: 최신 저장된 민원입니다.
                """
                if (
                    current.job.status != "running"
                    or current.job.context_version != current.context_version
                ):
                    return
                for index in range(len(current.job.events) - 1, completed):
                    current.job.stage = stages[index]
                    current.job.events.append(Event(stage=stages[index]))
                if completed == 5:
                    current.job.status = "succeeded"
                    current.ai_candidate = "[서버 시연 후보] 담당자의 근거·현장 확인이 필요합니다. 현재 편집본에 자동 적용하지 않는 고정 시연 문구입니다."

            try:
                self.repository.change(row.id, row.version, advance)
            except AppError as error:
                if error.status != 409:
                    raise
