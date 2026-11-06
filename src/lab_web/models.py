"""검사기 웹이 주고받는 JSON 계약을 정의합니다.

민원 CRUD 테이블에 쓰지 않습니다. 응대 결과는 `src.assist` 계약을 따릅니다.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from pydantic.alias_generators import to_camel

from src.complaints.models import AssistResponse
from src.lab_web.constants import CATEGORIES, DISTRICTS, Category, District

Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]
Body = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=10, max_length=2000)
]


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
        district: 발생 지역입니다. 없으면 비웁니다.
        body: 상세 내용입니다.
    """

    title: Title
    category: Category
    district: District | None = None
    body: Body

    @field_validator("district", mode="before")
    @classmethod
    def blank_district_to_none(cls, value: object) -> object:
        """빈 문자열은 지역 없음으로 둡니다."""
        if value == "":
            return None
        return value


class LlmEnvelope(Model):
    """검색에 넣은 질의와 파이프라인 진행 상태입니다."""

    status: Literal["completed", "search_failed"]
    sent: bool
    query: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class LabAcceptResult(Model):
    """수신 후 검색·판정까지 마친 응답입니다."""

    accepted: Literal[True] = True
    complaint: LabComplaint
    search_query: str
    llm: LlmEnvelope
    assist: AssistResponse
    message: str = "검색 후보를 찾은 뒤 판정했습니다."


class LabFields(Model):
    """작성 양식에 쓰는 분야·지역 목록입니다."""

    categories: tuple[Category, ...] = Field(default=CATEGORIES)
    districts: tuple[District, ...] = Field(default=DISTRICTS)


class LabHealth(Model):
    """검사기 웹 서버 상태입니다."""

    status: Literal["ok"] = "ok"
    service: Literal["lab_web"] = "lab_web"
    intake: Literal[True] = True
    search_available: bool = False
    llm_configured: bool = False


class ErrorBody(Model):
    """입력 오류 안내입니다. 원문은 반사하지 않습니다."""

    code: str
    message: str
    fields: list[str] = Field(default_factory=list)
