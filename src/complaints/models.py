"""업무 상태와 요청·응답을 정의하는 타입 및 실행 시 검증 모델입니다."""

from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, StringConstraints
from pydantic.alias_generators import to_camel

Role = Literal["citizen", "staff"]
Status = Literal["submitted", "under_review", "answered", "closed", "withdrawn"]
JobStatus = Literal[
    "queued", "running", "succeeded", "failed", "cancelled", "superseded"
]
District = Literal["상당구", "서원구", "흥덕구", "청원구", "모름"]
Category = Literal[
    "도로·교통", "환경·청소", "공원·녹지", "생활·복지", "주택·건축", "기타"
]
Visibility = Literal["private", "public"]
Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]
Content = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=10, max_length=2000)
]
Reason = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
AnswerText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
]
Version = Annotated[int, Field(strict=True, ge=1)]


def utcnow() -> datetime:
    """시간대가 포함된 현재 UTC 시각을 반환합니다."""
    return datetime.now(timezone.utc)


class Model(BaseModel):
    """미정의 필드를 거부하고 웹 계약은 camelCase로 직렬화합니다."""

    model_config = ConfigDict(
        extra="forbid",
        alias_generator=to_camel,
        populate_by_name=True,
        validate_assignment=True,
        serialize_by_alias=True,
    )


class Actor(Model):
    """서버 세션에서 확인한 시연 사용자의 역할과 식별자입니다."""

    id: str
    role: Role
    demo: Literal[True] = True


class SessionInput(Model):
    """로컬 시연 계정 선택 요청이며 운영용 로그인과 구별합니다."""

    role: Role


class Event(Model):
    """외부로 공개 가능한 작업 단계와 기록 시각입니다."""

    stage: str
    date: datetime = Field(default_factory=utcnow)


class History(Event):
    """초안 관련 내부 이력을 시민용 이력과 구별합니다."""

    text: str
    stage: str = ""
    public: bool = True


class Message(Model):
    """민원 작성자가 남긴 추가 문의입니다."""

    author: Literal["citizen"] = "citizen"
    text: str
    date: datetime = Field(default_factory=utcnow)


class Answer(Model):
    """현재 게시된 답변과 서버가 결정한 작성 기원입니다."""

    text: str
    origin: Literal["ai", "ai_edited", "staff"]
    reason: str
    date: datetime = Field(default_factory=utcnow)


class AnswerVersion(Model):
    """원문·답변의 이전 본문과 수정 사유를 보존합니다."""

    version: int
    text: str
    reason: str
    kind: str
    date: datetime = Field(default_factory=utcnow)


class Job(Model):
    """실제 AI와 분리된 서버 측 단계 시연 작업입니다."""

    status: JobStatus = "queued"
    stage: str = "AI 미연동 · 담당자 검토 대기"
    attempt: int = 0
    context_version: int = 1
    started_at: datetime | None = None
    events: list[Event] = Field(default_factory=list)


class PublicComplaint(Model):
    """시민에게 반환할 수 있는 민원 필드만 정의합니다."""

    id: str
    title: str
    body: str
    category: Category
    district: District
    owner: str
    visibility: Visibility
    status: Status = "submitted"
    date: datetime = Field(default_factory=utcnow)
    version: int = 1
    context_version: int = 1
    published: Answer | None = None
    messages: list[Message] = Field(default_factory=list)
    history: list[History] = Field(default_factory=list)


class Complaint(PublicComplaint):
    """담당자만 조회하는 초안·AI 원본·내부 작업 정보를 포함합니다."""

    assigned: bool = False
    ai_original: str = ""
    ai_candidate: str = ""
    draft: str = ""
    draft_version: int = 0
    versions: list[AnswerVersion] = Field(default_factory=list)
    job: Job = Field(default_factory=Job)


class ComplaintInput(Model):
    """시민 원문과 공개 범위를 검사합니다. 작성자는 세션에서 결정합니다."""

    title: Title
    body: Content
    district: District
    category: Category
    visibility: Visibility = "private"


class ComplaintUpdate(ComplaintInput):
    """수정 대상 민원의 현재 버전을 함께 받습니다."""

    version: Version


class VersionInput(Model):
    """동시 변경을 거부하기 위한 기대 버전입니다."""

    version: Version


class ReasonInput(VersionInput):
    """민원·게시본 철회의 사유를 검사합니다."""

    reason: Reason


class MessageInput(VersionInput):
    """본문을 임의로 자르지 않는 추가 문의 요청입니다."""

    message: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]


class AssignmentInput(VersionInput):
    """담당자 자신의 담당 지정 또는 해제를 요청합니다."""

    assigned: bool = Field(strict=True)


class AnswerInput(VersionInput):
    """저장·게시할 답변과 사유입니다. 작성 기원은 입력받지 않습니다."""

    text: AnswerText
    reason: Reason


class ComplaintPath(BaseModel):
    """민원 경로 식별자의 형식과 길이를 검사합니다."""

    model_config = ConfigDict(extra="forbid")
    complaint_id: str = Field(pattern=r"^[A-Za-z0-9-]{1,64}$")


class ListQuery(Model):
    """검색·지역·상태·담당·페이지 조건을 검사합니다."""

    q: str = Field(default="", max_length=120)
    status: Status | None = None
    district: District | None = None
    category: Category | None = None
    mine: bool = False
    assign: Literal["mine", "none"] | None = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=8, ge=1, le=100)


class CreateHeaders(BaseModel):
    """등록 중복 요청을 구별하는 선택적 멱등성 키입니다."""

    idempotency_key: str | None = Field(
        default=None, alias="Idempotency-Key", min_length=1, max_length=100
    )


class ErrorResponse(Model):
    """업무 오류와 입력 오류의 공통 응답입니다."""

    code: str
    message: str


class PublicWorkspace(Model):
    """시민에게 허용한 시연 민원 스냅샷입니다."""

    complaints: list[PublicComplaint]
    revision: int
    role: Literal["citizen"] = "citizen"


class StaffWorkspace(Model):
    """담당자 시연 화면에서 사용하는 내부 민원 스냅샷입니다."""

    complaints: list[Complaint]
    revision: int
    role: Literal["staff"] = "staff"


class PublicPage(PublicWorkspace):
    """페이지네이션된 시민 목록입니다."""

    total: int
    page: int
    limit: int


class StaffPage(StaffWorkspace):
    """페이지네이션된 담당자 목록입니다."""

    total: int
    page: int
    limit: int


class Health(Model):
    """업무 서버와 AI 연결 범위를 명시한 상태 응답입니다."""

    status: Literal["ok"] = "ok"
    storage: Literal["postgresql", "memory"] = "postgresql"
    demo: Literal[True] = True
    ai_connected: Literal[False] = False
    assist_search: bool = False
    assist_llm: bool = False


class AssistInput(Model):
    """응대 검사기의 민원 입력입니다. 민원 CRUD와 구별합니다."""

    query: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]
    district: Literal["상당구", "서원구", "흥덕구", "청원구"] | None = None
    limit: int = Field(default=5, ge=1, le=10)
    rerank: bool = True


class AssistExample(Model):
    """검사기에 고정한 예시 질문입니다."""

    id: str
    title: str
    query: str
    district: str | None = None


class AssistExampleList(Model):
    """예시 질문 목록입니다."""

    examples: list[AssistExample]


class AssistHit(Model):
    """검색 근거 한 건의 검사기 표시용 요약입니다."""

    rank: int | None = None
    source_id: str | None = None
    title: str | None = None
    source_url: str | None = None
    excerpt: str = ""
    corpus: Literal["faq", "routing"] | None = None
    routing_eligible: bool | None = None
    department_name: str | None = None
    department_status: str | None = None


class AssistDepartment(Model):
    """검색이 만든 부서 후보이며 자동 이관 허가가 아닙니다."""

    department_id: str | None = None
    canonical_name: str | None = None
    district: str | None = None
    duty_status: str | None = None
    jurisdiction_status: str | None = None
    supporting_cases: list[dict[str, Any]] = Field(default_factory=list)
    selected: bool = False
    automatic_transfer: Literal[False] = False


class AssistEvidenceRef(Model):
    """판정이 가리킨 검색 근거 키입니다."""

    corpus: Literal["faq", "routing"]
    source_id: str


class LlmUsage(Model):
    """한 호출의 토큰 사용량입니다. Codex CLI는 비웁니다."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None


class CodexCall(Model):
    """Codex CLI 한 호출에 넣은 시스템 표시와 사용자 JSON입니다.

    `user`는 민원마다 바뀌는 사용자 JSON입니다. `prompt`는
    `complete_codex_cli`가 `codex exec -` 표준 입력으로 넣는 전문과
    같습니다. 예전 기록에는 `prompt`가 없을 수 있습니다.

    Attributes:
        role: 1차 판정·FAQ 안내·담당자 초안·순화 중 하나입니다.
        system: PREFIX 조합 이름입니다.
        user: Codex stdin 사용자 JSON입니다.
        sent: 모델에 실제로 넣었으면 True입니다.
        usage: openai_api가 준 토큰 사용량입니다. CLI면 비웁니다.
        prompt: 래퍼·PREFIX 본문·사용자 JSON을 이은 Codex stdin입니다.
    """

    role: Literal["decision", "faq_answer", "staff_draft", "sanitize"]
    system: str
    user: dict[str, Any]
    sent: bool
    usage: LlmUsage | None = None
    prompt: str | None = None


class AssistDecision(Model):
    """코드 검증을 거친 판정입니다."""

    scope: str
    intent: str
    outcome: Literal["faq_answer", "department_suggestion", "human_handoff"]
    reason_code: str
    evidence_refs: list[AssistEvidenceRef]
    department_ids: list[str]
    model_raw: dict[str, Any] | None = None


class AssistStage(Model):
    """응대 파이프라인의 한 단계입니다."""

    name: str
    elapsed_ms: float
    ok: bool


class StaffSummaryCard(Model):
    """담당자가 볼 민원 요약 카드입니다."""

    core_summary: str
    citizen_request: str
    location_or_target: str
    missing_info: list[str]


class StaffDraft(Model):
    """PREFIX-03 담당자 초안입니다. 시민에게 게시하지 않습니다."""

    summary_card: StaffSummaryCard
    draft_answer: str
    citations: list[AssistEvidenceRef]
    requires_field_check: bool


class SanitizeResult(Model):
    """PREFIX-04 순화 결과입니다. 접수 거부·자동 차단이 아닙니다."""

    sanitized_summary: str
    legitimate_requests: list[str]
    risk_signals: list[str]
    human_protection_review_needed: bool


class AssistRetrieval(Model):
    """원본 검색 계약을 검사기에 그대로 전달합니다."""

    retrieval_only: bool | None = None
    decision: str | None = None
    elapsed_ms: float | None = None
    pipeline: str | None = None


class AssistResponse(Model):
    """검색 근거와 검증된 세 갈래 응대입니다. 민원 게시·이관이 아닙니다.

    Attributes:
        outcome: `faq_answer`·`department_suggestion`·`human_handoff`입니다.
        automatic_transfer: 항상 False입니다. 공식 이관이 아닙니다.
        codex: 모델에 넣은 호출 목록입니다. 검색 실패면 빈 목록입니다.
        staff_draft: 담당자 초안입니다. FAQ 안내이거나 검증 실패면 비웁니다.
        sanitize: 순화 요약입니다. 원문 힌트가 없으면 비웁니다.
    """

    query: str
    district: str | None = None
    outcome: Literal["faq_answer", "department_suggestion", "human_handoff"]
    reason_code: str
    answer: str | None = None
    handoff_required: bool
    automatic_transfer: Literal[False] = False
    faq: list[AssistHit]
    cases: list[AssistHit]
    departments: list[AssistDepartment]
    decision: AssistDecision
    policy_failures: list[str]
    stages: list[AssistStage]
    llm_configured: bool
    retrieval: AssistRetrieval
    codex: list[CodexCall] = Field(default_factory=list)
    staff_draft: StaffDraft | None = None
    sanitize: SanitizeResult | None = None


class ComplaintResponse(RootModel[PublicComplaint | Complaint]):
    """세션 역할에 맞는 민원 응답의 OpenAPI 합집합입니다."""


class WorkspaceResponse(RootModel[PublicWorkspace | StaffWorkspace]):
    """역할별 스냅샷 응답을 하나의 문서 계약으로 표현합니다."""


class PageResponse(RootModel[PublicPage | StaffPage]):
    """역할별 페이지 응답을 문서에 명시합니다."""
