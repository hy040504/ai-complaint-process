"""업무 상태와 요청·응답을 정의하는 타입 및 실행 시 검증 모델입니다."""

from datetime import datetime, timezone
from typing import Annotated, Literal

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
    storage: Literal["sqlite"] = "sqlite"
    demo: Literal[True] = True
    ai_connected: Literal[False] = False


class ComplaintResponse(RootModel[PublicComplaint | Complaint]):
    """세션 역할에 맞는 민원 응답의 OpenAPI 합집합입니다."""


class WorkspaceResponse(RootModel[PublicWorkspace | StaffWorkspace]):
    """역할별 스냅샷 응답을 하나의 문서 계약으로 표현합니다."""


class PageResponse(RootModel[PublicPage | StaffPage]):
    """역할별 페이지 응답을 문서에 명시합니다."""
