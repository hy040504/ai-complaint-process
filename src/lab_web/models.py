"""검사기 웹이 주고받는 JSON 계약을 정의합니다.

민원 CRUD 테이블에 쓰지 않습니다. 응대 결과는 `src.assist` 계약을 따릅니다.
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from pydantic.alias_generators import to_camel

from src.complaints.models import AssistResponse
from src.lab_web.constants import CATEGORIES, DISTRICT_AREAS, DISTRICTS, Category, District

Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]
Body = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=10, max_length=2000)
]
Provider = Literal["exaone_api", "codex_cli", "openai_api"]
"""검사기에서 고를 수 있는 LLM 공급자입니다. `src.llm.settings.LAB_PROVIDERS`와 맞춥니다."""


class Model(BaseModel):
    """미정의 필드를 거부하고 JSON은 camelCase로 직렬화합니다."""

    model_config = ConfigDict(
        extra="forbid",
        alias_generator=to_camel,
        populate_by_name=True,
        validate_assignment=True,
        serialize_by_alias=True,
    )


class LabComplaint(Model):
    """프론트가 보내는 민원 내용입니다.

    Attributes:
        title: 민원 제목입니다.
        category: 허용 목록의 민원 분야입니다.
        district: 발생 지역입니다. 4개 구 또는 산하 세부 지역이며 없으면 비웁니다.
        body: 상세 내용입니다.
        provider: 검사기에서 고른 LLM 공급자입니다. 비우면 `.env` 기본 설정을 씁니다.
    """

    title: Title
    category: Category
    district: str | None = None
    body: Body
    provider: Provider | None = None

    @field_validator("district", mode="before")
    @classmethod
    def blank_district_to_none(cls, value: object) -> object:
        """빈 문자열은 지역 없음으로 둡니다."""
        if value == "" or value is None:
            return None
        return str(value).strip() or None

    @field_validator("provider", mode="before")
    @classmethod
    def blank_provider_to_none(cls, value: object) -> object:
        """빈 문자열은 공급자 미지정으로 두고, 나머지는 소문자로 맞춥니다."""
        if value is None:
            return None
        return str(value).strip().lower() or None


class LlmEnvelope(Model):
    """검색에 넣은 질의와 파이프라인 진행 상태입니다.

    Attributes:
        status: 검색·판정이 끝났는지, 검색 서버 연결이 실패했는지입니다.
        sent: 응대 파이프라인을 호출했으면 True입니다.
        query: 제목·상세로 만든 검색 질의입니다.
    """

    status: Literal["completed", "search_failed"]
    sent: bool
    query: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class LabRunSummary(Model):
    """테스트 기록 목록에 쓰는 짧은 칸입니다.

    Attributes:
        id: 파일 이름에 쓰는 기록 ID입니다.
        at: 저장 시각(UTC)입니다.
        title: 민원 제목입니다.
        outcome: 응대 갈래입니다.
        reason_code: 처리 사유입니다.
    """

    id: str
    at: str
    title: str = ""
    outcome: str = ""
    reason_code: str = ""


class LabAcceptResult(Model):
    """수신 후 검색·판정까지 마친 응답입니다.

    Attributes:
        accepted: 수신 성공입니다.
        complaint: 검증된 민원 내용입니다.
        search_query: 검색 API에 넣은 질의입니다.
        effective_district: 실제 검색에 적용한 구 이름입니다.
        district_inferred: 본문에서 구를 자동 추론했으면 True입니다.
        llm: 파이프라인 진행 봉투입니다.
        assist: 세 갈래 응대와 `codex` 호출 목록입니다.
        message: 화면에 보여줄 짧은 안내입니다.
        run: 파일로 남긴 기록 요약입니다.
    """

    accepted: Literal[True] = True
    complaint: LabComplaint
    search_query: str
    effective_district: str | None = None
    district_inferred: bool = False
    llm: LlmEnvelope
    assist: AssistResponse
    message: str = "검색 후보를 찾은 뒤 판정했습니다."
    run: LabRunSummary | None = None


class ProviderStatus(Model):
    """LLM 공급자별 가용 상태입니다.

    Attributes:
        available: 현재 환경에서 호출 가능한지 여부입니다.
        reason: 미설정 또는 사용 불가 시 안내 문구입니다.
    """

    available: bool
    reason: str = ""


class LabFields(Model):
    """작성 양식에 쓰는 분야·지역 및 LLM 공급자 목록입니다.

    Attributes:
        categories: 허용 민원 분야 목록입니다.
        districts: 청주시 4대 자치구 목록입니다.
        district_areas: 각 자치구 산하 관할 읍·면·동 세부 지역 매핑입니다.
        providers: LLM 공급자별 가용 상태 매핑입니다.
    """

    categories: tuple[Category, ...] = Field(default=CATEGORIES)
    districts: tuple[District, ...] = Field(default=DISTRICTS)
    district_areas: dict[str, tuple[str, ...]] = Field(default=DISTRICT_AREAS)
    providers: dict[str, ProviderStatus] = Field(default_factory=dict)


class LabHealth(Model):
    """검사기 웹 서버 상태입니다."""

    status: Literal["ok"] = "ok"
    service: Literal["lab_web"] = "lab_web"
    intake: Literal[True] = True
    search_available: bool = False
    llm_configured: bool = False


class LabRunList(Model):
    """저장된 테스트 기록 목록입니다.

    Attributes:
        items: 최신순 요약입니다.
    """

    items: list[LabRunSummary] = Field(default_factory=list)


class LabRunRecord(LabRunSummary):
    """파일에서 다시 읽는 검사 결과입니다.

    Attributes:
        payload: 검사기에 보낸 민원입니다.
        received: 검색·판정 응답입니다.
    """

    payload: dict[str, Any]
    received: dict[str, Any]


class LabClearResult(Model):
    """기록 삭제 결과입니다.

    Attributes:
        removed: 지운 JSON 파일 수입니다.
    """

    removed: int


class ErrorBody(Model):
    """입력 오류 안내입니다. 원문은 반사하지 않습니다."""

    code: str
    message: str
    fields: list[str] = Field(default_factory=list)
