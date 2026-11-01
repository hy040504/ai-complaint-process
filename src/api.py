"""검증 모델을 Swagger와 공유하는 Flask 업무 API 경로입니다."""

import json
from collections.abc import Iterator

from flask import Response, current_app, session, stream_with_context
from flask_openapi3.blueprint import APIBlueprint
from flask_openapi3.models.tag import Tag
from src.http import actor, reply

from src.errors import AppError
from src.assist import (
    assist_examples,
    iter_web_assist,
    llm_configured,
    run_web_assist,
    search_available,
)
from src.models import (
    Actor,
    AnswerInput,
    AssignmentInput,
    AssistExampleList,
    AssistInput,
    AssistResponse,
    ComplaintInput,
    ComplaintPath,
    ComplaintResponse,
    ComplaintUpdate,
    CreateHeaders,
    ErrorResponse,
    Health,
    ListQuery,
    MessageInput,
    PageResponse,
    ReasonInput,
    SessionInput,
    VersionInput,
    WorkspaceResponse,
)
from src.service import ComplaintService, Operation


def create_api(service: ComplaintService) -> APIBlueprint:
    """서비스 인스턴스를 경로에 주입하고 문서화한 블루프린트를 만듭니다.

    Args:
        service: 업무 검증과 저장을 수행할 서비스입니다.

    Returns:
        요청·응답 스키마를 포함하는 API 블루프린트입니다.
    """
    api = APIBlueprint(
        "complaint_api",
        __name__,
        url_prefix="/api/v1",
        abp_responses={
            400: ErrorResponse,
            401: ErrorResponse,
            403: ErrorResponse,
            404: ErrorResponse,
            409: ErrorResponse,
            413: ErrorResponse,
            422: ErrorResponse,
            500: ErrorResponse,
        },
        validate_response=True,
    )
    sessions = Tag(
        name="시연 세션",
        description="로컬 역할 체험용 세션입니다. 운영용 본인인증이 아닙니다.",
    )
    complaints = Tag(name="민원", description="시민 원문·조회·추가 문의·철회")
    answers = Tag(
        name="담당자 답변", description="초안은 시민 API 응답에서 제외합니다."
    )
    jobs = Tag(
        name="AI 단계 시연",
        description="실제 LLM·검색·공식 이관과 연결하지 않는 서버 시뮬레이션",
    )
    assist = Tag(
        name="응대 검사기",
        description="검색 근거와 LLM 판정을 검증합니다. 민원 등록·공식 이관이 아닙니다.",
    )

    @api.get("/health", tags=[Tag(name="서버 상태")], responses={200: Health})
    def health() -> Response:
        """서버 상태와 검색·LLM 설정 여부, 민원 CRUD의 AI 미연결을 반환합니다."""
        return reply(
            Health(assist_search=search_available(), assist_llm=llm_configured())
        )

    @api.get(
        "/assist/examples",
        tags=[assist],
        responses={200: AssistExampleList},
    )
    def assist_example_list() -> Response:
        """검사기에 고정한 예시 질문을 반환합니다."""
        return reply(AssistExampleList.model_validate({"examples": assist_examples()}))

    @api.post("/assist", tags=[assist], responses={200: AssistResponse})
    def create_assist(body: AssistInput) -> Response:
        """검색 후 판정·정책 검사를 실행하고 세 갈래 결과를 반환합니다.

        Args:
            body: 민원 원문과 선택 관할·검색 옵션입니다.

        Returns:
            검증된 안내·부서 후보·담당자 검토 결과입니다.
        """
        return reply(
            AssistResponse.model_validate(
                run_web_assist(body.query, body.district, body.limit, body.rerank)
            )
        )

    @api.post("/assist/stream", tags=[assist])
    def create_assist_stream(body: AssistInput) -> Response:
        """응대 진행 안내를 NDJSON으로 보내고 마지막에 결과를 붙입니다.

        Args:
            body: 민원 원문과 선택 관할·검색 옵션입니다.

        Returns:
            줄 단위 JSON 사건 흐름입니다. 민원 저장·공식 이관이 아닙니다.
        """

        def generate() -> Iterator[str]:
            for event in iter_web_assist(
                body.query, body.district, body.limit, body.rerank
            ):
                if event.get("type") == "done":
                    payload = AssistResponse.model_validate(event["result"]).model_dump(
                        mode="json"
                    )
                    yield json.dumps(
                        {"type": "done", "result": payload}, ensure_ascii=False
                    ) + "\n"
                else:
                    yield json.dumps(event, ensure_ascii=False) + "\n"

        return Response(
            stream_with_context(generate()),
            mimetype="application/x-ndjson",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @api.post("/session", tags=[sessions], responses={200: Actor})
    def select_session(body: SessionInput) -> Response:
        """로컬 시연 계정의 역할을 선택합니다.

        Args:
            body: citizen 또는 staff 역할입니다.

        Returns:
            서명 쿠키에 연결된 시연 사용자입니다.
        """
        if not current_app.config["DEMO_LOGIN"]:
            raise AppError(
                403, "demo_login_disabled", "시연 역할 선택이 비활성화되어 있습니다."
            )
        session.clear()
        session["role"] = body.role
        return reply(actor())

    @api.get("/session", tags=[sessions], responses={200: Actor})
    def get_session() -> Response:
        """현재 서버 세션 사용자를 조회합니다."""
        return reply(actor())

    @api.delete("/session", tags=[sessions], responses={204: None})
    def delete_session() -> Response:
        """시연 계정 세션을 종료합니다."""
        session.clear()
        return Response(status=204)

    @api.get("/workspace", tags=[complaints], responses={200: WorkspaceResponse})
    def workspace() -> Response:
        """로컬 UI용 전체 스냅샷을 역할에 맞춰 반환합니다."""
        return reply(service.workspace(actor()))

    @api.get("/complaints", tags=[complaints], responses={200: PageResponse})
    def list_complaints(query: ListQuery) -> Response:
        """검색·지역·상태·페이지 조건을 적용한 민원 목록입니다.

        Args:
            query: 서버에서 검사한 검색 조건입니다.

        Returns:
            권한이 적용된 페이지와 전체 건수입니다.
        """
        return reply(service.page(actor(), query))

    @api.post("/complaints", tags=[complaints], responses={201: ComplaintResponse})
    def create_complaint(body: ComplaintInput, header: CreateHeaders) -> Response:
        """민원을 DB에 등록합니다. 공식 행정 접수는 수행하지 않습니다.

        Args:
            body: 검증할 민원 원문입니다.
            header: 선택적인 Idempotency-Key입니다.

        Returns:
            작성자와 버전을 서버에서 부여한 민원입니다.
        """
        user = actor()
        return reply(
            service.project(user, service.create(user, body, header.idempotency_key)),
            201,
        )

    @api.get(
        "/complaints/<complaint_id>",
        tags=[complaints],
        responses={200: ComplaintResponse},
    )
    def get_complaint(path: ComplaintPath) -> Response:
        """민원 상세를 조회하며 시민 응답에서 내부 필드를 제거합니다.

        Args:
            path: 민원 식별자입니다.

        Returns:
            역할별 상세 모델입니다.
        """
        user = actor()
        return reply(service.project(user, service.get(user, path.complaint_id)))

    @api.put(
        "/complaints/<complaint_id>",
        tags=[complaints],
        responses={200: ComplaintResponse},
    )
    def update_complaint(path: ComplaintPath, body: ComplaintUpdate) -> Response:
        """답변 게시 전 본인의 민원 원문을 수정합니다.

        Args:
            path: 민원 식별자입니다.
            body: 버전을 포함한 전체 수정 필드입니다.

        Returns:
            수정 후 시민용 민원입니다.
        """
        user = actor()
        return reply(
            service.project(user, service.update(user, path.complaint_id, body))
        )

    def operate(
        path: ComplaintPath, body: VersionInput, operation: Operation
    ) -> Response:
        """경로가 지정한 동작만 서비스에서 실행하고 역할별 응답을 만듭니다.

        Args:
            path: 민원 식별자입니다.
            body: 경로별 검증 모델입니다.
            operation: 클라이언트가 바꿀 수 없는 동작 식별자입니다.

        Returns:
            저장 결과의 역할별 투영입니다.
        """
        user = actor()
        return reply(
            service.project(user, service.act(user, path.complaint_id, body, operation))
        )

    @api.delete(
        "/complaints/<complaint_id>",
        tags=[complaints],
        responses={200: ComplaintResponse},
    )
    def withdraw(path: ComplaintPath, body: ReasonInput) -> Response:
        """본인 민원을 논리 철회하고 이력을 보존합니다.

        Args:
            path: 민원 식별자입니다.
            body: 기대 버전과 철회 사유입니다.

        Returns:
            철회 처리 결과입니다.
        """
        return operate(path, body, "withdraw")

    @api.post(
        "/complaints/<complaint_id>/messages",
        tags=[complaints],
        responses={200: ComplaintResponse},
    )
    def add_message(path: ComplaintPath, body: MessageInput) -> Response:
        """본인 민원에 추가 문의를 남기고 검토 상태로 바꿉니다.

        Args:
            path: 민원 식별자입니다.
            body: 기대 버전과 추가 문의입니다.

        Returns:
            문의와 새 맥락 버전을 포함한 결과입니다.
        """
        return operate(path, body, "message")

    @api.post(
        "/complaints/<complaint_id>/review",
        tags=[complaints],
        responses={200: ComplaintResponse},
    )
    def request_review(path: ComplaintPath, body: VersionInput) -> Response:
        """기존 게시 답변을 보존하며 담당자 재검토를 요청합니다.

        Args:
            path: 민원 식별자입니다.
            body: 기대 버전입니다.

        Returns:
            재검토 상태의 민원입니다.
        """
        return operate(path, body, "review")

    @api.put(
        "/complaints/<complaint_id>/assignment",
        tags=[answers],
        responses={200: ComplaintResponse},
    )
    def assignment(path: ComplaintPath, body: AssignmentInput) -> Response:
        """담당자가 자신의 담당 지정 또는 해제를 수행합니다.

        Args:
            path: 민원 식별자입니다.
            body: 기대 버전과 지정 여부입니다.

        Returns:
            담당 정보가 변경된 민원입니다.
        """
        return operate(path, body, "assign")

    @api.put(
        "/complaints/<complaint_id>/draft",
        tags=[answers],
        responses={200: ComplaintResponse},
    )
    def save_draft(path: ComplaintPath, body: AnswerInput) -> Response:
        """시민 비공개 답변 초안을 새 버전으로 저장합니다.

        Args:
            path: 민원 식별자입니다.
            body: 버전·답변·수정 사유입니다.

        Returns:
            초안과 이력을 포함한 담당자 응답입니다.
        """
        return operate(path, body, "draft")

    @api.post(
        "/complaints/<complaint_id>/publish",
        tags=[answers],
        responses={200: ComplaintResponse},
    )
    def publish(path: ComplaintPath, body: AnswerInput) -> Response:
        """검토한 답변을 게시하고 작성 기원을 서버에서 결정합니다.

        Args:
            path: 민원 식별자입니다.
            body: 기대 버전과 게시할 답변입니다.

        Returns:
            답변 완료 상태와 게시본입니다.
        """
        return operate(path, body, "publish")

    @api.post(
        "/complaints/<complaint_id>/retract",
        tags=[answers],
        responses={200: ComplaintResponse},
    )
    def retract(path: ComplaintPath, body: ReasonInput) -> Response:
        """게시 답변을 철회하고 이전 본문·사유를 보존합니다.

        Args:
            path: 민원 식별자입니다.
            body: 버전과 철회 사유입니다.

        Returns:
            게시본이 숨겨진 검토 상태입니다.
        """
        return operate(path, body, "retract")

    @api.post(
        "/complaints/<complaint_id>/jobs",
        tags=[jobs],
        responses={200: ComplaintResponse},
    )
    def start_job(path: ComplaintPath, body: VersionInput) -> Response:
        """서버에서 시연 단계를 시작하며 편집본을 덮어쓰지 않습니다.

        Args:
            path: 민원 식별자입니다.
            body: 기대 버전입니다.

        Returns:
            실행 상태가 저장된 민원입니다.
        """
        return operate(path, body, "retry")

    @api.post(
        "/complaints/<complaint_id>/jobs/cancel",
        tags=[jobs],
        responses={200: ComplaintResponse},
    )
    def cancel_job(path: ComplaintPath, body: VersionInput) -> Response:
        """실행 중인 단계 시연을 취소하며 민원과 편집본을 유지합니다.

        Args:
            path: 민원 식별자입니다.
            body: 기대 버전입니다.

        Returns:
            취소 상태를 저장한 민원입니다.
        """
        return operate(path, body, "cancel")

    return api
