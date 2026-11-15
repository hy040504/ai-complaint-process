"""업무 상태와 요청·응답을 정의하는 타입 및 실행 시 검증 모델입니다."""

from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    StringConstraints,
    ValidationInfo,
    field_validator,
)
from pydantic.alias_generators import to_camel

from src.assist.district import DISTRICT_AREAS, DISTRICTS, normalize_district
from src.llm.settings import Provider, normalize_optional_text

Role = Literal["citizen", "staff"]
Status = Literal["submitted", "under_review", "answered", "closed", "withdrawn"]
JobStatus = Literal[
    "queued", "running", "succeeded", "failed", "cancelled", "superseded"
]
District = Literal["상당구", "서원구", "흥덕구", "청원구", "모름"]
Category = Literal[
    "도로·교통", "환경·청소", "공원·녹지", "생활·복지", "주택·건축", "기타"
]
CATEGORIES: tuple[Category, ...] = (
    "도로·교통",
    "환경·청소",
    "공원·녹지",
    "생활·복지",
    "주택·건축",
    "기타",
)
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
    """실제 AI 또는 서버 측 단계 시연 작업입니다.

    Attributes:
        status: 작업 진행 상태입니다.
        stage: 현재 진행 단계 안내 문구입니다.
        attempt: 같은 민원에서 누적 실행한 작업 횟수입니다.
        context_version: 이 작업이 기준으로 삼은 민원 내용 버전입니다.
        provider: 작업에 지정한 LLM 공급자입니다. 비우면 `.env` 기본을 씁니다.
        started_at: 작업 시작 시각(UTC)입니다.
        events: 진행 중 기록한 단계별 이벤트 목록입니다.
    """

    status: JobStatus = "queued"
    stage: str = "AI 미연동 · 담당자 검토 대기"
    attempt: int = 0
    context_version: int = 1
    provider: Provider | None = None
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
    # 공개 사례 등에서 만든 시연용 민원인지 표시합니다. 실제 접수와 구별합니다.
    is_synthetic: bool = False
    published: Answer | None = None
    messages: list[Message] = Field(default_factory=list)
    history: list[History] = Field(default_factory=list)


class Complaint(PublicComplaint):
    """담당자만 조회하는 초안·AI 원본·내부 작업·응대 분석 정보를 포함합니다."""

    assigned: bool = False
    ai_original: str = ""
    ai_candidate: str = ""
    ai_assist: "AssistResponse | None" = None
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
    provider: Provider | None = None

    @field_validator("provider", mode="before")
    @classmethod
    def clean_provider(cls, value: object) -> object:
        """빈 문자열·공백 공급자를 None으로 정규화하고 소문자로 통일합니다.

        Args:
            value: 검증 전 공급자 입력 값입니다.

        Returns:
            정제한 공급자 문자열 또는 None입니다.
        """
        return normalize_optional_text(value, lowercase=True)


class ComplaintUpdate(ComplaintInput):
    """수정 대상 민원의 현재 버전을 함께 받습니다."""

    version: Version


class VersionInput(Model):
    """동시 변경을 거부하기 위한 기대 버전입니다."""

    version: Version


class JobStartInput(VersionInput):
    """담당자가 AI 작업 실행 시 버전을 함께 검증하고 선택 공급자를 넘깁니다."""

    provider: Provider | None = None

    @field_validator("provider", mode="before")
    @classmethod
    def clean_provider(cls, value: object) -> object:
        """빈 문자열·공백 공급자를 None으로 정규화하고 소문자로 통일합니다.

        Args:
            value: 검증 전 공급자 입력 값입니다.

        Returns:
            정제한 공급자 문자열 또는 None입니다.
        """
        return normalize_optional_text(value, lowercase=True)


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
    ai_connected: bool = False
    assist_search: bool = False
    assist_llm: bool = False


class AssistInput(Model):
    """응대 검사기의 민원 입력입니다. 민원 CRUD와 구별합니다.

    Attributes:
        query: 검색·판정에 사용할 민원 질의 본문입니다.
        district: 청주시 4개 구 또는 산하 읍·면·동 이름입니다. 없으면 None입니다.
        limit: 검색 코퍼스별 최대 후보 수입니다.
        rerank: 재정렬 사용 여부입니다. 기본 False입니다.
        provider: 호출할 LLM 공급자입니다. 비우면 `.env` 기본을 씁니다.
    """

    query: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]
    district: str | None = Field(default=None, max_length=60)
    limit: int = Field(default=5, ge=1, le=10)
    rerank: bool = False
    provider: Provider | None = None

    @field_validator("district", "provider", mode="before")
    @classmethod
    def clean_optional_fields(
        cls, value: object, info: ValidationInfo
    ) -> object:
        """선택 지역·공급자의 빈 값을 None으로 정리하고 관할 지역을 확인합니다.

        Args:
            value: 검증 전 입력 값입니다.
            info: 검증 대상 필드 정보(`district` 또는 `provider`)입니다.

        Returns:
            정제된 문자열 또는 None입니다.

        Raises:
            ValueError: `district`에 알 수 없는 지역명이 들어오면 발생합니다.
        """
        is_provider = info.field_name == "provider"
        cleaned = normalize_optional_text(value, lowercase=is_provider)
        if cleaned is None:
            return None
        if not is_provider:
            text = str(cleaned)
            if text in ("전체", "모름"):
                return None
            if normalize_district(text) is None:
                raise ValueError(
                    "청주시 4개 자치구 또는 관할 읍·면·동 이름을 입력해 주세요."
                )
            return text
        return cleaned


class ProviderStatus(Model):
    """LLM 공급자별 가용 상태입니다.

    Attributes:
        available: 현재 환경에서 호출 가능한지 여부입니다.
        reason: 미설정 또는 사용 불가 시 안내 문구입니다.
        resolved_provider: 실제 호출될 공급자 식별자입니다. `.env` 기본 해석용입니다.
    """

    available: bool
    reason: str = ""
    resolved_provider: str | None = None


class AssistFields(Model):
    """응대 검사기·담당자 AI 실행에서 선택할 수 있는 분야·지역·공급자 정보입니다.

    Attributes:
        categories: 허용 민원 분야 목록입니다.
        districts: 청주시 4대 자치구 목록입니다.
        district_areas: 각 자치구 산하 관할 읍·면·동 세부 지역 매핑입니다.
        providers: LLM 공급자별 가용 상태 매핑입니다.
    """

    categories: tuple[Category, ...] = Field(default=CATEGORIES)
    districts: tuple[str, ...] = Field(default=DISTRICTS)
    district_areas: dict[str, tuple[str, ...]] = Field(default=DISTRICT_AREAS)
    providers: dict[str, ProviderStatus] = Field(default_factory=dict)


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
    reasoning_tokens: int | None = None


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
        query: 검색과 판정에 사용한 민원 원문입니다.
        district: 검색에 적용한 관할 구입니다.
        district_inferred: 본문 지명으로 구를 자동 감지했으면 True입니다.
        inferred_place: 네이버 지도로 추론된 장소 객체입니다. 없으면 None입니다.
        outcome: `faq_answer`·`department_suggestion`·`human_handoff`입니다.
        automatic_transfer: 항상 False입니다. 공식 이관이 아닙니다.
        llm_provider: 실제 선택·해석된 LLM 공급자 식별자입니다.
        llm_model: 실제 호출 대상 모델 이름입니다.
        codex: 모델에 넣은 호출 목록입니다. 검색 실패면 빈 목록입니다.
        staff_draft: 담당자 초안입니다. FAQ 안내이거나 검증 실패면 비웁니다.
        sanitize: 순화 요약입니다. 원문 힌트가 없으면 비웁니다.
    """

    query: str
    district: str | None = None
    district_inferred: bool = False
    inferred_place: dict[str, Any] | None = None
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
    llm_provider: str | None = None
    llm_model: str | None = None
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


Complaint.model_rebuild()
StaffWorkspace.model_rebuild()
StaffPage.model_rebuild()
ComplaintResponse.model_rebuild()
WorkspaceResponse.model_rebuild()
PageResponse.model_rebuild()
