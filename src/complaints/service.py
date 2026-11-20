"""권한·업무 상태·답변 게시·입력 버전을 검증하는 서비스입니다."""

from collections.abc import Callable, Iterator
from hashlib import sha256
import inspect
from threading import Lock, Thread
from typing import Any, Literal, Protocol
from uuid import uuid4

from src.complaints.chat import project_citizen_chat
from src.complaints.departments import (
    load_department_directory,
    valid_department_names,
)
from src.complaints.errors import AppError
from src.complaints.events import StaffEventBroker, StaffEventType
from src.complaints.models import (
    Actor,
    Answer,
    AnswerInput,
    AnswerTemplate,
    AnswerVersion,
    AssignmentInput,
    AssistResponse,
    CitizenChatInput,
    CitizenChatResponse,
    Complaint,
    ComplaintInput,
    ComplaintUpdate,
    DepartmentListResponse,
    Event,
    History,
    Job,
    JobStartInput,
    ListQuery,
    Message,
    MessageInput,
    NormalizedDbSummary,
    PublicComplaint,
    PublicPage,
    PublicWorkspace,
    ReasonInput,
    StaffPage,
    StaffWorkspace,
    TemplateCreateInput,
    TemplateListResponse,
    VersionInput,
    utcnow,
)
from src.complaints.repository import ComplaintRepository
from src.llm.settings import Provider

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

_OUTCOME_STAGE_LABELS: dict[str, str] = {
    "faq_answer": "AI 분석 완료 (FAQ 안내) · 담당자 검토 대기",
    "department_suggestion": "AI 분석 완료 (부서 후보) · 담당자 검토 대기",
    "human_handoff": "AI 분석 완료 (담당자 검토) · 담당자 검토 대기",
}


class AssistIterFn(Protocol):
    """민원 한 건을 RAG+LLM으로 분석하며 진행·최종 이벤트를 내보내는 함수 계약입니다."""

    def __call__(
        self,
        query: str,
        district: str | None,
        limit: int,
        rerank: bool,
        provider: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        """민원 질의를 검색·판정하고 진행 이벤트와 최종 `done` 사전을 순차 반환합니다.

        Args:
            query: 검색 및 판정에 사용할 민원 질의 문자열입니다.
            district: 선택 관할 자치구·읍면동 문자열 또는 None입니다.
            limit: 컬렉션별 검색 후보 최대 개수입니다.
            rerank: 검색 결과 재정렬 사용 여부입니다.
            provider: 지정할 LLM 공급자 ID 또는 None입니다.

        Returns:
            진행 단계 이벤트와 최종 `done` 결과를 내보내는 이터레이터입니다.
        """
        ...


def compose_complaint_query(row: Complaint) -> str:
    """민원 제목·본문과 추가 문의로 검색·판정용 질의를 구성합니다.

    민원 분야(`category`)는 검색 질의에 섞지 않습니다.

    Args:
        row: 질의를 만들 대상 민원 모델입니다.

    Returns:
        RAG 검색과 LLM 판정에 전달할 질의 문자열입니다.
    """
    parts = [row.title.strip(), row.body.strip()]
    if row.messages:
        followups = "\n".join(m.text.strip() for m in row.messages if m.text.strip())
        if followups:
            parts.append("[추가 문의]\n" + followups)
    return "\n\n".join(part for part in parts if part)


def _ai_district_arg(district: str) -> str | None:
    """저장된 민원 관할 값을 응대 파이프라인 인자로 변환합니다.

    Args:
        district: 업무 민원에 저장된 관할 문자열입니다.

    Returns:
        `'모름'`이면 지명 자동 감지를 위해 None을, 그 외에는 원문 관할을 반환합니다.
    """
    return None if district == "모름" else district


def extract_ai_candidate(assist: AssistResponse) -> str:
    """응대 결과에서 담당자 편집기 후보 문장을 추출합니다.

    담당자용 초안(`staff_draft.draft_answer`)이 있으면 우선 사용하고,
    없으면 시민용 안내 문구(`answer`)를 반환합니다. 단, 부서 후보 판정에서
    초안이 비어 있을 때는 검사기용 미검증 상태 표기를 뺀 추천 안내 문구로 정리합니다.

    Args:
        assist: 검증을 통과한 응대 분석 결과입니다.

    Returns:
        공백을 정리한 후보 문장입니다.
    """
    if assist.staff_draft and assist.staff_draft.draft_answer.strip():
        return assist.staff_draft.draft_answer.strip()
    answer = (assist.answer or "").strip()
    if (
        assist.outcome == "department_suggestion"
        and "(업무분장:" in answer
        and assist.departments
    ):
        chosen = [d for d in assist.departments if d.selected] or list(
            assist.departments
        )
        lines = [
            f"- {d.canonical_name or d.department_id}"
            for d in chosen
            if d.canonical_name or d.department_id
        ]
        if lines:
            return (
                "유사한 공개 사례를 기준으로 아래 담당 부서 후보를 참고하여 "
                "답변을 검토해 주세요.\n" + "\n".join(lines)
            )
    return answer


class ComplaintService:
    """저장소 구현을 알지 않고 업무 경계와 비동기 AI 연동을 조정합니다.

    Args:
        repository: 타입 인터페이스를 만족하는 업무 저장소입니다.
        iter_assist_fn: 민원별 RAG+LLM 스트리밍 실행 함수입니다. None이면 시뮬레이션만 씁니다.
        auto_start_ai: 민원 등록·원문 수정 시 자동으로 AI 분석을 시작할지 여부입니다.
    """

    def __init__(
        self,
        repository: ComplaintRepository,
        *,
        iter_assist_fn: AssistIterFn | None = None,
        auto_start_ai: bool = False,
    ) -> None:
        """업무 저장소 인터페이스와 선택적 AI 실행기를 주입합니다.

        Args:
            repository: 민원 조회·생성·원자 변경을 제공하는 저장소입니다.
            iter_assist_fn: 검색·판정 스트림을 생성하는 응대 함수입니다.
            auto_start_ai: True이면 민원 등록·수정 직후 백그라운드 AI 분석을 자동 시작합니다.
        """
        self.repository = repository
        self.iter_assist_fn = iter_assist_fn
        self.auto_start_ai = auto_start_ai
        self._supports_staff_output_flag = bool(
            iter_assist_fn is not None
            and "include_staff_outputs" in inspect.signature(iter_assist_fn).parameters
        )
        self._live_lock = Lock()
        self._live_jobs: dict[tuple[str, int, int], tuple[str, list[Event]]] = {}
        self._active_threads: dict[tuple[str, int, int], Thread] = {}
        self.events = StaffEventBroker()

    def _publish_row_event(self, event_type: StaffEventType, row: Complaint) -> None:
        """커밋된 민원의 안전한 작업·상태 메타데이터를 담당자 SSE 브로커에 발행합니다.

        Args:
            event_type: 발행할 SSE 이벤트 유형입니다.
            row: 저장소에 커밋된 최신 민원 레코드입니다.
        """
        self.events.publish(
            event_type,
            row.id,
            context_version=row.context_version,
            attempt=row.job.attempt,
            job_status=row.job.status,
            stage=row.job.stage,
        )

    def require_staff(self, actor: Actor) -> None:
        """담당자 전용 API 경로(SSE 등) 진입 시 세션 역할을 검증합니다.

        Args:
            actor: 서버 세션에서 확인한 사용자입니다.

        Raises:
            AppError: 담당자 역할이 아니면 403 오류를 발생합니다.
        """
        self._require_staff(actor)

    def iter_citizen_chat(
        self, actor: Actor, body: CitizenChatInput
    ) -> Iterator[dict[str, Any]]:
        """시민 민원 도우미 질의를 RAG+LLM으로 분석하고 안전한 시민 전용 결과를 스트리밍합니다.

        담당자 초안(`PREFIX-03`)과 직원 보호 순화(`PREFIX-04`)는 생성·노출하지 않습니다.

        Args:
            actor: 서버 세션에서 확인한 사용자입니다.
            body: 시민이 입력한 질문과 선택 관할·공급자입니다.

        Yields:
            진행 안내(`progress`) 또는 시민 투영 완료(`done`) 이벤트 사전입니다.
        """
        del actor  # 세션 인증은 protect_api·actor()에서 선행 검증됩니다.
        iter_fn = self.iter_assist_fn
        if iter_fn is None:
            yield {
                "type": "progress",
                "key": "read",
                "label": "민원 내용을 읽고 있어요",
            }
            fallback = project_citizen_chat(
                {
                    "query": body.message,
                    "district": body.district,
                    "outcome": "human_handoff",
                    "reason_code": "llm_unavailable",
                    "llm_configured": False,
                }
            )
            yield {"type": "done", "result": fallback}
            return

        kwargs: dict[str, Any] = {}
        if body.provider is not None:
            kwargs["provider"] = body.provider
        if self._supports_staff_output_flag:
            kwargs["include_staff_outputs"] = False

        done_raw: dict[str, Any] | None = None
        try:
            for event in iter_fn(body.message, body.district, 5, False, **kwargs):
                kind = event.get("type")
                if kind == "progress":
                    # 시민 챗봇 화면에는 직원용 초안·순화 단계 라벨을 노출하지 않습니다.
                    if event.get("key") in ("sanitize", "draft"):
                        continue
                    yield {
                        "type": "progress",
                        "key": str(event.get("key") or "review"),
                        "label": str(event.get("label") or "내용을 확인하고 있어요"),
                    }
                elif kind == "done" and isinstance(event.get("result"), dict):
                    done_raw = event["result"]
                    break
                elif kind == "error":
                    done_raw = {
                        "query": body.message,
                        "district": body.district,
                        "outcome": "human_handoff",
                        "reason_code": "llm_unavailable",
                        "llm_configured": False,
                    }
                    break
        except Exception:
            done_raw = {
                "query": body.message,
                "district": body.district,
                "outcome": "human_handoff",
                "reason_code": "llm_unavailable",
                "llm_configured": False,
            }

        if done_raw is None:
            done_raw = {
                "query": body.message,
                "district": body.district,
                "outcome": "human_handoff",
                "reason_code": "llm_unavailable",
                "llm_configured": False,
            }
        yield {"type": "done", "result": project_citizen_chat(done_raw)}

    def run_citizen_chat(
        self, actor: Actor, body: CitizenChatInput
    ) -> CitizenChatResponse:
        """시민 민원 도우미 질의에 대한 최종 시민 전용 응답을 반환합니다.

        Args:
            actor: 서버 세션에서 확인한 사용자입니다.
            body: 시민 질문과 선택 관할·공급자입니다.

        Returns:
            내부 초안·순화 필드가 제거된 `CitizenChatResponse` 모델입니다.
        """
        result: CitizenChatResponse | None = None
        for event in self.iter_citizen_chat(actor, body):
            if event.get("type") == "done" and isinstance(
                event.get("result"), CitizenChatResponse
            ):
                result = event["result"]
        if result is not None:
            return result
        return project_citizen_chat(
            {
                "query": body.message,
                "district": body.district,
                "outcome": "human_handoff",
                "reason_code": "llm_unavailable",
                "llm_configured": False,
            }
        )

    @property
    def ai_connected(self) -> bool:
        """민원 CRUD 작업에 실제 RAG+LLM 실행기가 연결되어 있는지 확인합니다.

        Returns:
            실제 응대 실행 함수가 연결되어 있으면 True입니다.
        """
        return self.iter_assist_fn is not None

    def _enrich_live(self, row: Complaint) -> Complaint:
        """실행 중인 실제 AI 작업의 최신 단계 이벤트를 담당자 조회 응답에 반영합니다.

        진행 단계마다 DB 버전을 올려 편집 중 409 충돌이 나지 않도록
        메모리상의 진행 이벤트만 병합하고, 최종 결과·실패만 DB에 커밋합니다.

        Args:
            row: 저장소에서 읽은 민원 모델입니다.

        Returns:
            진행 중 작업이 있으면 최신 단계를 반영한 민원 사본입니다.
        """
        if not self.ai_connected or row.job.status != "running":
            return row
        key = (row.id, row.job.attempt, row.context_version)
        with self._live_lock:
            snapshot = self._live_jobs.get(key)
        if snapshot is None:
            return row
        stage, events = snapshot
        updated = row.model_copy(deep=True)
        updated.job.stage = stage
        updated.job.events = [
            Event(date=item.date, stage=item.stage) for item in events
        ]
        return updated

    def wait_for_jobs(self, timeout: float = 5.0) -> None:
        """실행 중인 백그라운드 AI 스레드가 끝날 때까지 대기합니다(테스트·종료용).

        Args:
            timeout: 전체 작업 완료를 기다릴 최대 시간(초)입니다.
        """
        with self._live_lock:
            threads = list(self._active_threads.values())
        for thread in threads:
            thread.join(timeout=timeout)

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
        return self._enrich_live(row) if actor.role == "staff" else row

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
            return StaffWorkspace(
                complaints=[self._enrich_live(row) for row in rows],
                revision=revision,
                event_cursor=self.events.cursor,
            )
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
                and (row.assigned or bool(row.department)) == (query.assign == "mine")
            ]
        total = len(rows)
        selected = rows[(query.page - 1) * query.limit : query.page * query.limit]
        if actor.role == "staff" and isinstance(workspace, StaffWorkspace):
            return StaffPage(
                complaints=[
                    Complaint.model_validate(row.model_dump()) for row in selected
                ],
                revision=workspace.revision,
                event_cursor=workspace.event_cursor,
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
            **body.model_dump(exclude={"provider"}),
        )
        row.history.append(History(text="시연 서버에 민원 등록"))
        if self.ai_connected and self.auto_start_ai:
            provider_note = f" · {body.provider}" if body.provider else ""
            row.job = Job(
                status="running",
                stage="민원 내용을 읽고 있어요",
                attempt=1,
                context_version=1,
                provider=body.provider,
                started_at=utcnow(),
                events=[
                    Event(stage=f"민원 저장 완료 · AI 자동 분석 시작{provider_note}")
                ],
            )
        else:
            row.job.events.append(Event(stage="민원 저장 완료 · 실제 AI 미연동"))
        saved = self.repository.create(
            row, key, sha256(body.model_dump_json().encode()).hexdigest()
        )
        self._publish_row_event("complaint.created", saved)
        if self.ai_connected and self.auto_start_ai:
            self._launch_ai_job(saved)
        return saved

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
        if staff:
            self._require_staff(actor)
            self._require_department_scope(actor, row)
        if not staff and (actor.role != "citizen" or row.owner != actor.id):
            raise AppError(
                403, "owner_required", "민원 작성자만 수행할 수 있는 작업입니다."
            )
        return self.repository.change(complaint_id, version, action)

    def delete_complaint(self, actor: Actor, complaint_id: str, version: int) -> None:
        """작성자 본인이 등록한 민원을 저장소에서 완전히 삭제합니다.

        Args:
            actor: 삭제를 요청한 사용자입니다.
            complaint_id: 삭제할 민원 식별자입니다.
            version: 클라이언트가 마지막으로 조회한 낙관적 잠금 버전입니다.

        Raises:
            AppError: 민원이 없거나 작성자 본인이 아니거나 버전이 다르면 발생합니다.
        """
        row = self.get(actor, complaint_id)
        if actor.role != "citizen" or row.owner != actor.id:
            raise AppError(
                403, "owner_required", "민원 작성자만 수행할 수 있는 작업입니다."
            )

        def check_owner(locked: Complaint) -> None:
            """트랜잭션 잠금 안에서 작성자 본인 여부와 상태를 한 번 더 검증합니다.

            Args:
                locked: 잠금으로 읽은 최신 민원입니다.
            """
            if locked.status == "withdrawn":
                raise AppError(404, "not_found", "민원을 찾을 수 없습니다.")
            if actor.role != "citizen" or locked.owner != actor.id:
                raise AppError(
                    403, "owner_required", "민원 작성자만 수행할 수 있는 작업입니다."
                )

        self.repository.delete(complaint_id, version, check_owner)
        self.events.publish(
            "complaint.deleted",
            complaint_id,
            context_version=row.context_version,
            attempt=row.job.attempt,
            job_status=row.job.status,
            stage="민원 삭제",
        )

    def _require_staff(self, actor: Actor) -> None:
        """요청 사용자가 담당자 역할인지 검증합니다.

        Args:
            actor: 인증된 시연 또는 공무원 사용자입니다.

        Raises:
            AppError: 담당자 역할이 아니면 403 오류를 발생합니다.
        """
        if actor.role != "staff":
            raise AppError(403, "staff_required", "담당자만 수행할 수 있는 작업입니다.")

    @staticmethod
    def _require_department_scope(actor: Actor, row: Complaint) -> None:
        """부서 소속 담당자가 타 부서에 배정된 민원을 무단 수정·게시하지 못하도록 검증합니다.

        소속 부서가 비어 있는 총괄 담당자(`actor.department is None`)는 모든 부서
        민원을 관리할 수 있으며, 부서 담당자는 미배정 또는 본인 소속 부서 민원만 처리합니다.

        Args:
            actor: 작업을 요청한 담당자입니다.
            row: 대상 민원 레코드입니다.

        Raises:
            AppError: 타 부서에 이미 배정된 민원이면 403 오류를 발생합니다.
        """
        if (
            actor.role == "staff"
            and actor.department
            and row.department
            and row.department != actor.department
        ):
            raise AppError(
                403,
                "department_scope_forbidden",
                f"소속 부서({actor.department})가 아닌 '{row.department}' 배정 민원은 수정·답변할 수 없습니다.",
            )

    def normalized_summary(self, actor: Actor) -> NormalizedDbSummary:
        """정규화 7테이블의 행 수와 AI·역할 집계를 담당자에게 반환합니다.

        Args:
            actor: 조회를 요청한 담당자입니다.

        Returns:
            정규화 7테이블 집계 응답입니다.
        """
        self._require_staff(actor)
        return self.repository.normalized_summary()

    def list_departments(self, actor: Actor) -> DepartmentListResponse:
        """담당자 부서 배정 모달에 표시할 청주시 현행 부서 목록을 반환합니다.

        Args:
            actor: 조회를 요청한 담당자입니다.

        Returns:
            정규화된 청주시 현행 부서 목록입니다.
        """
        self._require_staff(actor)
        return DepartmentListResponse(
            departments=load_department_directory(prefer_remote=self.ai_connected)
        )

    def list_templates(self, actor: Actor) -> TemplateListResponse:
        """담당자 답변 편집기에서 사용할 템플릿 목록을 반환합니다.

        Args:
            actor: 조회를 요청한 담당자입니다.

        Returns:
            등록순으로 정렬된 답변 템플릿 목록입니다.
        """
        self._require_staff(actor)
        return TemplateListResponse(templates=self.repository.list_templates())

    def create_template(
        self, actor: Actor, body: TemplateCreateInput
    ) -> AnswerTemplate:
        """담당자 커스텀 답변 템플릿을 저장하고 반환합니다.

        Args:
            actor: 생성을 요청한 담당자입니다.
            body: 템플릿 이름과 본문입니다.

        Returns:
            새로 저장한 템플릿입니다.
        """
        self._require_staff(actor)
        template = AnswerTemplate(
            id="TPL-" + uuid4().hex[:10].upper(),
            title=body.title,
            content=body.content,
            is_default=False,
        )
        return self.repository.create_template(template)

    def delete_template(self, actor: Actor, template_id: str) -> None:
        """담당자가 지정한 답변 템플릿을 삭제합니다.

        Args:
            actor: 삭제를 요청한 담당자입니다.
            template_id: 삭제할 템플릿 식별자입니다.
        """
        self._require_staff(actor)
        self.repository.delete_template(template_id)

    def reset_templates(self, actor: Actor) -> TemplateListResponse:
        """삭제된 기본 답변 템플릿을 복원하고 전체 목록을 반환합니다.

        Args:
            actor: 복원을 요청한 담당자입니다.

        Returns:
            복원 후 전체 템플릿 목록입니다.
        """
        self._require_staff(actor)
        return TemplateListResponse(templates=self.repository.reset_default_templates())

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
            row.ai_assist = None
            row.draft = ""
            row.draft_version += 1
            row.history.append(History(text="시민이 민원 내용 수정"))
            if self.ai_connected and self.auto_start_ai:
                next_provider = (
                    body.provider if body.provider is not None else row.job.provider
                )
                self._start_job(row, provider=next_provider, real_ai=True)

        saved = self.change(actor, complaint_id, body.version, False, apply)
        self._publish_row_event("complaint.updated", saved)
        if self.ai_connected and self.auto_start_ai:
            self._launch_ai_job(saved)
        return saved

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
    def _start_job(
        row: Complaint,
        *,
        provider: Provider | None = None,
        real_ai: bool = False,
    ) -> None:
        """현재 맥락에 대한 AI 분석 또는 시연 작업을 시작합니다.

        Args:
            row: 현재 트랜잭션의 민원입니다.
            provider: 지정할 LLM 공급자입니다. 비우면 `.env` 기본을 씁니다.
            real_ai: 실제 RAG+LLM 실행기가 연결된 경우 True입니다.

        Raises:
            AppError: 이미 작업이 실행 중이면 발생합니다.
        """
        if row.job.status == "running":
            raise AppError(409, "already_running", "이미 실행 중인 시연 작업입니다.")
        if real_ai:
            provider_note = f" · {provider}" if provider else ""
            stage = "민원 내용을 읽고 있어요"
            first_event = Event(stage=f"AI 응대 분석 요청{provider_note}")
        else:
            stage = "검색 대기 · 서버 시연"
            first_event = Event(stage="서버 단계 시뮬레이션 요청")
        row.job = Job(
            status="running",
            stage=stage,
            context_version=row.context_version,
            attempt=row.job.attempt + 1,
            provider=provider,
            started_at=utcnow(),
            events=[first_event],
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
                actor_name = actor.display_name or "김담당"
                if body.department is not None:
                    dept = body.department
                    if dept:
                        if actor.department and dept != actor.department:
                            raise AppError(
                                403,
                                "department_scope_forbidden",
                                f"타 부서('{dept}')로 이관 배정은 총괄 민원과 담당자만 수행할 수 있습니다.",
                            )
                        allowed = valid_department_names(
                            prefer_remote=self.ai_connected
                        )
                        if dept not in allowed:
                            raise AppError(
                                422,
                                "invalid_department",
                                "청주시 현행 부서 목록에서 배정할 부서를 선택해 주세요.",
                            )
                        row.department = dept
                        row.assigned = True if body.assigned is None else body.assigned
                        if row.assigned:
                            row.assignee_id = actor.id
                            row.assignee_name = actor_name
                        else:
                            row.assignee_id = None
                            row.assignee_name = None
                        if row.status == "submitted":
                            row.status = "under_review"
                        text = f"담당 부서 지정(시연 · 공식 이관 아님): {dept}"
                        if body.reason:
                            text += f" · {body.reason}"
                    else:
                        row.department = None
                        row.assigned = False if body.assigned is None else body.assigned
                        if not row.assigned:
                            row.assignee_id = None
                            row.assignee_name = None
                        text = "담당 부서 배정 해제"
                        if body.reason:
                            text += f": {body.reason}"
                else:
                    row.assigned = bool(body.assigned)
                    if row.assigned:
                        row.assignee_id = actor.id
                        row.assignee_name = actor_name
                        if actor.department and not row.department:
                            row.department = actor.department
                    else:
                        row.assignee_id = None
                        row.assignee_name = None
                    if row.assigned and row.status == "submitted":
                        row.status = "under_review"
                    text = (
                        f"담당자 지정 ({actor_name})"
                        if row.assigned
                        else "담당자 지정 해제"
                    )
            elif operation in ("draft", "publish") and isinstance(body, AnswerInput):
                publish = operation == "publish"
                self._save_answer(row, body, publish)
                if not row.assignee_id:
                    row.assignee_id = actor.id
                    row.assignee_name = actor.display_name or "김담당"
                suffix = f" ({actor.display_name})" if actor.display_name else ""
                text = (
                    f"담당자 답변 게시{suffix}"
                    if publish
                    else f"담당자 초안 저장{suffix}"
                )
                public = publish
            elif operation == "retract" and isinstance(body, ReasonInput):
                self._retract_answer(row, body)
                text = "답변 철회: " + body.reason
            elif operation == "retry":
                requested_provider = (
                    body.provider if isinstance(body, JobStartInput) else None
                )
                self._start_job(
                    row, provider=requested_provider, real_ai=self.ai_connected
                )
                if self.ai_connected:
                    suffix = f" ({requested_provider})" if requested_provider else ""
                    text, public = f"AI 응대 분석 실행 요청{suffix}", False
                else:
                    text, public = "AI 단계 시연 요청", False
            elif operation == "cancel":
                self._cancel_job(row)
                text, public = "시연 작업 취소", False
            else:
                raise AppError(
                    400, "invalid_operation", "요청 모델과 작업이 일치하지 않습니다."
                )
            row.history.append(History(text=text, public=public))

        saved = self.change(
            actor,
            complaint_id,
            body.version,
            operation not in ("withdraw", "message", "review"),
            apply,
        )
        event_kind: StaffEventType = (
            "ai_job.stage_changed"
            if operation == "retry"
            else ("ai_job.cancelled" if operation == "cancel" else "complaint.updated")
        )
        self._publish_row_event(event_kind, saved)
        if operation == "retry" and self.ai_connected:
            self._launch_ai_job(saved)
        return saved

    def _launch_ai_job(self, row: Complaint) -> None:
        """실행 중인 실제 AI 작업의 백그라운드 분석 스레드를 한 번만 시작합니다.

        Args:
            row: 저장소에 방금 커밋된 `running` 상태의 민원입니다.
        """
        if not self.ai_connected or row.job.status != "running":
            return
        key = (row.id, row.job.attempt, row.context_version)
        with self._live_lock:
            if key in self._active_threads:
                return
            self._live_jobs[key] = (row.job.stage, list(row.job.events))
            worker = Thread(
                target=self._run_ai_worker,
                args=(
                    key,
                    compose_complaint_query(row),
                    _ai_district_arg(row.district),
                    row.job.provider,
                    list(row.job.events),
                ),
                daemon=True,
            )
            self._active_threads[key] = worker
            worker.start()

    def _run_ai_worker(
        self,
        key: tuple[str, int, int],
        query: str,
        district: str | None,
        provider: Provider | None,
        base_events: list[Event],
    ) -> None:
        """백그라운드 스레드에서 RAG+LLM 스트림을 소비하고 결과를 DB에 저장합니다.

        Args:
            key: `(complaint_id, attempt, context_version)` 실행 식별 키입니다.
            query: 검색·판정에 넘길 민원 질의입니다.
            district: 선택 관할 구 또는 None입니다.
            provider: 지정한 LLM 공급자 또는 None(`.env` 기본)입니다.
            base_events: 작업 시작 시 이미 기록된 이벤트 목록입니다.
        """
        complaint_id, attempt, context_version = key
        events = list(base_events)
        iter_fn = self.iter_assist_fn
        if iter_fn is None:
            return
        try:
            done_raw: dict[str, Any] | None = None
            stream = (
                iter_fn(query, district, 5, False, provider=provider)
                if provider is not None
                else iter_fn(query, district, 5, False)
            )
            for event in stream:
                kind = event.get("type")
                if kind == "progress":
                    label = str(event.get("label") or "").strip()
                    if label:
                        if not events or events[-1].stage != label:
                            events.append(Event(stage=label))
                        with self._live_lock:
                            self._live_jobs[key] = (label, list(events))
                        self.events.publish(
                            "ai_job.stage_changed",
                            complaint_id,
                            context_version=context_version,
                            attempt=attempt,
                            job_status="running",
                            stage=label,
                        )
                elif kind == "error":
                    raise RuntimeError(
                        str(event.get("message") or "응대 분석이 실패했습니다.")
                    )
                elif kind == "done":
                    result_obj = event.get("result")
                    if not isinstance(result_obj, dict):
                        raise TypeError("응대 분석 결과가 JSON 객체가 아닙니다.")
                    done_raw = result_obj
                    break
            if done_raw is None:
                raise RuntimeError("응대 분석 최종 결과를 받지 못했습니다.")
            assist = AssistResponse.model_validate(done_raw)
            self._commit_ai_completion(
                complaint_id, attempt, context_version, assist, events
            )
        except Exception as exc:
            self._commit_ai_failure(
                complaint_id, attempt, context_version, str(exc), events
            )
        finally:
            with self._live_lock:
                self._live_jobs.pop(key, None)
                self._active_threads.pop(key, None)

    def _commit_with_retry(
        self,
        complaint_id: str,
        attempt: int,
        context_version: int,
        updater: Callable[[Complaint], None],
    ) -> Complaint | None:
        """맥락·시도·실행 상태가 유효할 때만 작업 결과를 원자적으로 저장합니다.

        시민 원문 수정, 게시, 취소, 재시도로 맥락·시도 번호가 바뀐 늦은 결과는
        저장하지 않고 버립니다. 담당자 지정·초안 저장 등으로 단순 `version`만
        증가한 경우에는 최대 4회까지 최신 버전을 다시 읽어 재시도합니다.

        Args:
            complaint_id: 대상 민원 ID입니다.
            attempt: 시작한 작업 시도 번호입니다.
            context_version: 작업 시작 당시 민원 내용 버전입니다.
            updater: 최신 민원에 최종 결과나 실패 상태를 반영할 콜백입니다.

        Returns:
            실제로 커밋에 성공한 민원 레코드입니다. 취소·맥락 변경으로 버려졌으면 None입니다.
        """
        for _ in range(4):
            try:
                latest = self.repository.get(complaint_id)
            except AppError as err:
                if err.status == 404:
                    return None
                raise
            if not self._matches_running_job(latest, attempt, context_version):
                return None

            applied = False

            def apply_checked(current: Complaint) -> None:
                """트랜잭션 잠금 안에서 실행 맥락 일치 여부를 한 번 더 검증합니다.

                Args:
                    current: 잠금으로 조회한 최신 민원 레코드입니다.
                """
                nonlocal applied
                if self._matches_running_job(current, attempt, context_version):
                    updater(current)
                    applied = True

            try:
                saved = self.repository.change(
                    complaint_id, latest.version, apply_checked
                )
                return saved if applied else None
            except AppError as err:
                if err.status != 409:
                    raise
        return None

    @staticmethod
    def _matches_running_job(
        row: Complaint, attempt: int, context_version: int
    ) -> bool:
        """민원이 삭제되지 않았고 동일 시도·맥락의 실행 중 작업인지 확인합니다.

        Args:
            row: 검사할 민원 레코드입니다.
            attempt: 백그라운드 작업이 시작한 시도 번호입니다.
            context_version: 작업 시작 시점의 민원 내용 버전입니다.

        Returns:
            결과를 커밋할 수 있는 동일 실행 중 작업이면 True입니다.
        """
        return (
            row.status != "withdrawn"
            and row.context_version == context_version
            and row.job.attempt == attempt
            and row.job.status == "running"
        )

    def _commit_ai_completion(
        self,
        complaint_id: str,
        attempt: int,
        context_version: int,
        assist: AssistResponse,
        events: list[Event],
    ) -> None:
        """완료된 RAG+LLM 분석을 민원에 저장하며 기존 편집본·게시본은 보호합니다.

        Args:
            complaint_id: 대상 민원 ID입니다.
            attempt: 작업 시도 번호입니다.
            context_version: 작업 시작 당시 내용 버전입니다.
            assist: 검증된 응대 분석 결과입니다.
            events: 진행 중 누적된 단계 이벤트 목록입니다.
        """

        def update(current: Complaint) -> None:
            """완료된 AI 판정·초안 후보·이력을 민원 레코드에 안전하게 반영합니다.

            Args:
                current: 잠금으로 읽은 최신 민원 레코드입니다.
            """
            candidate = extract_ai_candidate(assist)
            final_stage = _OUTCOME_STAGE_LABELS.get(
                assist.outcome, "AI 분석 완료 · 담당자 검토 대기"
            )
            current.ai_assist = assist
            current.job.status = "succeeded"
            current.job.stage = final_stage
            current.job.events = [*events, Event(stage=final_stage)]
            current.ai_candidate = candidate
            if candidate and not current.ai_original:
                current.ai_original = candidate
            # 담당자가 이미 초안을 작성·저장했거나 답변이 게시된 경우에는 draft를 덮어쓰지 않습니다.
            staff_touched = any(
                item.kind in ("초안 저장", "게시") for item in current.versions
            )
            if (
                candidate
                and not current.draft
                and not current.published
                and not staff_touched
            ):
                current.draft = candidate
            provider_tag = assist.llm_provider or current.job.provider or "기본 LLM"
            model_tag = f" ({assist.llm_model})" if assist.llm_model else ""
            current.history.append(
                History(
                    text=f"AI 응대 분석 완료 · {provider_tag}{model_tag}",
                    public=False,
                )
            )

        committed = self._commit_with_retry(
            complaint_id, attempt, context_version, update
        )
        if committed is not None:
            self._publish_row_event("ai_job.completed", committed)

    def _commit_ai_failure(
        self,
        complaint_id: str,
        attempt: int,
        context_version: int,
        message: str,
        events: list[Event],
    ) -> None:
        """AI 실행 오류 시에도 민원 원문과 기존 답변을 보존하고 실패만 기록합니다.

        Args:
            complaint_id: 대상 민원 ID입니다.
            attempt: 작업 시도 번호입니다.
            context_version: 작업 시작 당시 내용 버전입니다.
            message: 저장할 요약 오류 메시지입니다.
            events: 실패 직전까지 누적된 단계 이벤트 목록입니다.
        """

        def update(current: Complaint) -> None:
            """AI 실패 상태와 요약 단계를 기록하되 민원 본문·초안은 보존합니다.

            Args:
                current: 잠금으로 읽은 최신 민원 레코드입니다.
            """
            reason = (message or "알 수 없는 오류").strip()[:120]
            final_stage = f"AI 분석 실패: {reason}"
            current.job.status = "failed"
            current.job.stage = final_stage
            current.job.events = [*events, Event(stage=final_stage)]
            current.history.append(History(text=final_stage, public=False))

        committed = self._commit_with_retry(
            complaint_id, attempt, context_version, update
        )
        if committed is not None:
            self._publish_row_event("ai_job.failed", committed)

    def advance_jobs(self) -> None:
        """경과 시간에 따른 시연 단계를 DB에 반영하며 실제 AI 연결 시에는 실행하지 않습니다."""
        if self.ai_connected:
            return
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
                saved = self.repository.change(row.id, row.version, advance)
                self._publish_row_event(
                    "ai_job.completed" if completed == 5 else "ai_job.stage_changed",
                    saved,
                )
            except AppError as error:
                if error.status != 409:
                    raise
