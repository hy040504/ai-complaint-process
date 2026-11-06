"""검사기 웹이 주고받는 JSON 계약을 정의합니다.

민원 CRUD 테이블에 쓰지 않습니다. 언어 모델 호출 전 수신 확인용입니다.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from pydantic.alias_generators import to_camel

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
    """언어 모델에 넘길 묶음입니다. 이 단계에서는 호출하지 않습니다."""

    status: Literal["accepted"] = "accepted"
    sent: Literal[False] = False
    query: Annotated[str, StringConstraints(min_length=1, max_length=2200)]


class LabAcceptResult(Model):
    """수신 성공 응답입니다."""

    accepted: Literal[True] = True
    complaint: LabComplaint
    llm: LlmEnvelope
    message: str = "민원 내용을 받았습니다. 언어 모델 호출은 다음 단계입니다."


class LabFields(Model):
    """작성 양식에 쓰는 분야·지역 목록입니다."""

    categories: tuple[Category, ...] = Field(default=CATEGORIES)
    districts: tuple[District, ...] = Field(default=DISTRICTS)


class LabHealth(Model):
    """검사기 웹 서버 상태입니다."""

    status: Literal["ok"] = "ok"
    service: Literal["lab_web"] = "lab_web"
    intake: Literal[True] = True
    llm_sent: Literal[False] = False


class ErrorBody(Model):
    """입력 오류 안내입니다. 원문은 반사하지 않습니다."""

    code: str
    message: str
    fields: list[str] = Field(default_factory=list)
