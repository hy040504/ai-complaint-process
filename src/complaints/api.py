"""검증 모델을 Swagger와 공유하는 Flask 업무 API 경로입니다."""

import json
from collections.abc import Iterator
import os
from urllib.parse import quote

from flask import Response, current_app, request, session, stream_with_context
from flask_openapi3.models.file import FileStorage
from flask_openapi3.blueprint import APIBlueprint
from flask_openapi3.models.tag import Tag
from pydantic import BaseModel
from src.complaints.auth import AuthService
from src.complaints.http import actor, current_guest_id, reply, set_session_actor
from src.complaints.sites import explicit_site, wrong_site_message

from src.complaints.errors import AppError
from src.assist import (
    assist_examples,
    iter_web_assist,
    llm_configured,
    run_web_assist,
    search_available,
)
from src.assist.district import DISTRICT_AREAS, DISTRICTS
from src.complaints.models import (
    CATEGORIES,
    Actor,
    AnswerInput,
    AnswerTemplate,
    AssignmentInput,
    AssistExampleList,
    AssistFields,
    AssistInput,
    AssistResponse,
    AttachmentDownloadQuery,
    AttachmentItem,
    AttachmentPath,
    ChatSessionDetail,
    ChatSessionListResponse,
    ChatSessionPath,
    CitizenChatInput,
    CitizenChatResponse,
    ComplaintInput,
    ComplaintPath,
    ComplaintResponse,
    ComplaintUpdate,
    CreateHeaders,
    DepartmentListResponse,
    ErrorResponse,
    Health,
    JobStartInput,
    ListQuery,
    LoginInput,
    MessageInput,
    NormalizedDbSummary,
    PageResponse,
    ProviderStatus,
    PublicWorkspace,
    ReasonInput,
    VisibilityInput,
    RegisterInput,
    SessionInput,
    StaffEventsQuery,
    StaffExportQuery,
    StaffStatsQuery,
    StaffStatsResponse,
    TemplateCreateInput,
    TemplateListResponse,
    TemplatePath,
    VersionInput,
    WorkspaceResponse,
)
from src.complaints.service import ComplaintService, Operation
from src.llm.settings import provider_availability_map

ASSIST_LIMIT_MESSAGE = "검사기 실행이 너무 잦습니다. 10분에 20회까지 쓸 수 있으니 잠시 뒤 다시 시도해 주세요."


class AttachmentUploadForm(BaseModel):
    """민원 현장 사진·PDF 멀티파트 파일 업로드 폼 계약입니다."""

    file: FileStorage


def create_api(
    service: ComplaintService,
    auth_service: AuthService | None = None,
) -> APIBlueprint:
    """서비스·인증 인스턴스를 경로에 주입하고 문서화한 블루프린트를 만듭니다.

    Args:
        service: 업무 검증과 저장을 수행할 서비스입니다.
        auth_service: 본인확인·비밀번호 인증 서비스입니다. 생략하면 저장소로 기본 생성합니다.

    Returns:
        요청·응답 스키마를 포함하는 API 블루프린트입니다.
    """
    auth = auth_service or AuthService(service.repository)
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
            429: ErrorResponse,
            500: ErrorResponse,
        },
        validate_response=True,
    )
    server_status = Tag(name="서버 상태")
    auth_tag = Tag(
        name="계정 로그인",
        description="민원인·담당자 아이디·비밀번호(scrypt) 로그인과 민원인 간단 가입(외부 PASS/SSO 미연동)",
    )
    sessions = Tag(
        name="시연 세션",
        description="로컬 역할 체험용 시연 전환 세션입니다(COMPLAINT_DEMO_LOGIN=0일 때 비활성).",
    )
    complaints = Tag(
        name="민원",
        description="시민 민원 등록·목록 조회·상세·수정·추가 문의·철회·삭제",
    )
    answers = Tag(
        name="담당자 답변",
        description="초안 저장·검토·게시·부서 배정·답변 템플릿(미게시 초안은 시민 API 응답에서 제외)",
    )
    jobs = Tag(
        name="AI 작업 · 단계 시연",
        description="비동기 RAG+LLM 초안·근거 생성 작업과 담당자 전용 실시간 SSE 푸시(미연결 또는 testing=True 환경에서는 서버 단계 시연으로 동작)",
    )
    assist = Tag(
        name="응대 검사기",
        description="검색 근거와 LLM 판정을 검증합니다. 민원 등록·공식 이관이 아닙니다.",
    )
    citizen_chat_tag = Tag(
        name="시민 민원 도우미",
        description="미게시 초안·순화를 제거하고 청주시 공식 FAQ·참고 부서를 안내하는 시민 전용 다중 턴 실시간 챗봇(로그인 시 PostgreSQL 저장 · 공식 접수 아님)",
    )
    staff_stats_tag = Tag(
        name="담당자 통계 · 내보내기",
        description="담당자 부서 RBAC 소관 범위 기준 운영 KPI·드릴다운 차트 집계 및 수식 주입 방어 CSV 내보내기(미게시 초안·순화 제외)",
    )

    @api.get("/health", tags=[server_status], responses={200: Health})
    def health() -> Response:
        """서버 상태와 검색·LLM·실시간 SSE·시민 챗봇·인증·정규화 DB 연결 여부를 반환합니다."""
        return reply(
            Health(
                storage=service.repository.storage,
                ai_connected=service.ai_connected,
                assist_search=search_available(),
                assist_llm=llm_configured(),
            )
        )

    @api.get(
        "/staff/db-summary",
        tags=[server_status],
        responses={200: NormalizedDbSummary},
    )
    def staff_db_summary() -> Response:
        """담당자 전용 정규화 7테이블(`users`~`job_events`) 행 수와 집계를 조회합니다."""
        return reply(service.normalized_summary(actor()))

    @api.get(
        "/staff/stats",
        tags=[staff_stats_tag],
        responses={200: StaffStatsResponse},
    )
    def staff_stats(query: StaffStatsQuery) -> Response:
        """담당자 소관 범위 기준 운영 KPI·차트 집계·정규화 DB 요약을 조회합니다.

        총괄 담당자는 전체 민원, 부서 담당자는 미배정과 소속 부서 배정 민원만 집계합니다.

        Args:
            query: 공개 시연 데이터(`DEMO-*`) 포함 여부를 지정하는 쿼리입니다.

        Returns:
            운영 KPI·5종 분포 차트·정규화 7테이블 요약이 담긴 `StaffStatsResponse`입니다.
        """
        return reply(
            service.staff_stats(actor(), include_synthetic=query.include_synthetic)
        )

    @api.get(
        "/staff/complaints/export.csv",
        tags=[staff_stats_tag],
    )
    def staff_export_csv(query: StaffExportQuery) -> Response:
        """담당자 현재 필터·소관 범위의 업무 메타데이터를 UTF-8 BOM CSV로 내려받습니다.

        미게시 AI 초안과 직원 보호 순화 본문은 제외하며, 엑셀 수식 주입 문자를 중화합니다.

        Args:
            query: 통합 검색·상태·구·분야·담당·AI 판정·정렬·시연 포함 조건입니다.

        Returns:
            `text/csv; charset=utf-8` 첨부 다운로드 응답입니다.
        """
        filename, csv_text = service.export_complaints_csv(actor(), query)
        return Response(
            csv_text.encode("utf-8"),
            mimetype="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    @api.get(
        "/assist/fields",
        tags=[assist],
        responses={200: AssistFields},
    )
    def assist_fields() -> Response:
        """응대 검사기·담당자 AI 실행에서 선택할 분야·관할 지역·LLM 가용 상태를 반환합니다."""
        providers = {
            key: ProviderStatus.model_validate(value)
            for key, value in provider_availability_map().items()
        }
        return reply(
            AssistFields(
                categories=CATEGORIES,
                districts=DISTRICTS,
                district_areas=DISTRICT_AREAS,
                providers=providers,
            )
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
            body: 민원 원문과 선택 관할·검색 옵션·LLM 공급자입니다.

        Returns:
            검증된 안내·부서 후보·담당자 검토 결과입니다.
        """
        auth.assist_limiter.hit(actor().id, ASSIST_LIMIT_MESSAGE)
        raw = (
            run_web_assist(
                body.query,
                body.district,
                body.limit,
                body.rerank,
                provider=body.provider,
            )
            if body.provider is not None
            else run_web_assist(body.query, body.district, body.limit, body.rerank)
        )
        return reply(AssistResponse.model_validate(raw))

    @api.post("/assist/stream", tags=[assist])
    def create_assist_stream(body: AssistInput) -> Response:
        """응대 진행 안내를 NDJSON으로 보내고 마지막에 결과를 붙입니다.

        Args:
            body: 민원 원문과 선택 관할·검색 옵션·LLM 공급자입니다.

        Returns:
            줄 단위 JSON 사건 흐름입니다. 민원 저장·공식 이관이 아닙니다.
        """
        auth.assist_limiter.hit(actor().id, ASSIST_LIMIT_MESSAGE)

        def generate() -> Iterator[str]:
            """진행 단계와 최종 응대 결과를 줄 단위 JSON 문자열로 생성합니다."""
            stream = (
                iter_web_assist(
                    body.query,
                    body.district,
                    body.limit,
                    body.rerank,
                    provider=body.provider,
                )
                if body.provider is not None
                else iter_web_assist(body.query, body.district, body.limit, body.rerank)
            )
            for event in stream:
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

    @api.post(
        "/citizen/chat",
        tags=[citizen_chat_tag],
        responses={200: CitizenChatResponse},
    )
    def citizen_chat(body: CitizenChatInput) -> Response:
        """시민 민원 도우미 질문을 RAG+LLM으로 분석하고 시민 안전 응답만 반환합니다.

        담당자 초안(`PREFIX-03`)·직원 보호 순화(`PREFIX-04`)·내부 프롬프트·과거 사례 원문은
        생성·반환하지 않으며 자동 이관(`automaticTransfer=False`)을 허용하지 않습니다.

        Args:
            body: 시민 문의 내용과 선택 관할·LLM 공급자입니다.

        Returns:
            시민에게 안전하게 표시할 안내·FAQ 출처·참고 부서 후보·감지 관할 구입니다.
        """
        return reply(service.run_citizen_chat(actor(), body))

    @api.post("/citizen/chat/stream", tags=[citizen_chat_tag])
    def citizen_chat_stream(body: CitizenChatInput) -> Response:
        """시민 민원 도우미 진행 안내를 NDJSON으로 보내고 마지막에 시민 안전 응답을 붙입니다.

        Args:
            body: 시민 문의 내용과 선택 관할·LLM 공급자입니다.

        Returns:
            줄 단위 JSON 진행·완료 사건 스트림입니다. 민원 저장·공식 이관이 아닙니다.
        """
        user = actor()

        def generate() -> Iterator[str]:
            """진행 단계와 시민 전용 투영 결과를 줄 단위 JSON 문자열로 생성합니다."""
            for event in service.iter_citizen_chat(user, body):
                if event.get("type") == "done":
                    result = event["result"]
                    payload = (
                        result.model_dump(mode="json", by_alias=True)
                        if isinstance(result, CitizenChatResponse)
                        else CitizenChatResponse.model_validate(result).model_dump(
                            mode="json", by_alias=True
                        )
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

    @api.get(
        "/citizen/chat/sessions",
        tags=[citizen_chat_tag],
        responses={200: ChatSessionListResponse},
    )
    def list_citizen_chat_sessions() -> Response:
        """로그인 민원인 본인의 챗봇 대화 세션 목록을 최근 갱신순으로 조회합니다.

        비로그인 시연 시민은 빈 목록과 `persisted=False`를 돌려받으며,
        담당자는 시민 개인 챗봇 대화에 접근할 수 없습니다.
        """
        return reply(service.list_chat_sessions(actor()))

    @api.get(
        "/citizen/chat/sessions/<session_id>",
        tags=[citizen_chat_tag],
        responses={200: ChatSessionDetail},
    )
    def get_citizen_chat_session(path: ChatSessionPath) -> Response:
        """로그인 민원인 본인이 소유한 챗봇 대화 세션과 안전 투영 이력을 조회합니다.

        Args:
            path: 조회할 챗봇 세션 ID 경로입니다.

        Returns:
            세션 요약과 발화 이력이 담긴 `ChatSessionDetail`입니다.
        """
        return reply(service.get_chat_session(actor(), path.session_id))

    @api.delete(
        "/citizen/chat/sessions/<session_id>",
        tags=[citizen_chat_tag],
        responses={204: None},
    )
    def delete_citizen_chat_session(path: ChatSessionPath) -> Response:
        """로그인 민원인 본인이 소유한 챗봇 대화 세션과 메시지를 삭제합니다.

        Args:
            path: 삭제할 챗봇 세션 ID 경로입니다.

        Returns:
            본문 없는 204 응답입니다.
        """
        service.delete_chat_session(actor(), path.session_id)
        return Response(status=204)

    @api.post("/auth/register", tags=[auth_tag], responses={201: Actor})
    def register_citizen_account(body: RegisterInput) -> Response:
        """아이디·비밀번호·이름으로 새 민원인 계정을 생성하고 즉시 로그인합니다.

        Args:
            body: 로그인 아이디·비밀번호·표시 이름입니다.

        Returns:
            생성·로그인된 민원인 `Actor` 모델입니다.
        """
        if explicit_site() == "staff":
            raise AppError(403, "wrong_site", wrong_site_message("staff"))
        guest_id = current_guest_id()
        user = auth.register_citizen(body)
        if guest_id:
            service.claim_guest_complaints(guest_id, user)
        set_session_actor(user)
        return reply(user, 201)

    @api.post("/auth/login", tags=[auth_tag], responses={200: Actor})
    def login_account(body: LoginInput) -> Response:
        """민원인·담당자 계정의 아이디와 `scrypt` 비밀번호로 로그인합니다.

        Args:
            body: 로그인 아이디·비밀번호·선택 기대 역할입니다.

        Returns:
            세션 쿠키가 발급된 `Actor` 모델입니다.
        """
        site = explicit_site()
        if site is not None and not body.expected_role:
            # 사이트가 명시된 요청은 해당 사이트의 계정 유형만 로그인할 수 있습니다.
            body = body.model_copy(update={"expected_role": site})
        guest_id = current_guest_id()
        user = auth.login(body)
        if guest_id and user.role == "citizen":
            service.claim_guest_complaints(guest_id, user)
        set_session_actor(user)
        return reply(user)

    @api.post("/auth/guest", tags=[auth_tag], responses={200: Actor})
    def start_guest_session() -> Response:
        """로그인 없이 민원을 접수·문의하는 게스트 세션을 시작합니다.

        이미 시민 세션(게스트 포함)이 있으면 새로 만들지 않고 현재 사용자를 돌려줍니다.
        게스트는 DB 계정 없이 서명 세션으로만 식별되며, 담당자 사이트에서는 거부합니다.
        IP당 시간당 10회까지 발급합니다.

        Returns:
            게스트 `Actor`(`guest=true`) 또는 이미 로그인한 시민 `Actor`입니다.
        """
        if explicit_site() == "staff":
            raise AppError(403, "wrong_site", wrong_site_message("staff"))
        try:
            current = actor()
        except AppError:
            current = None
        if current is not None and current.role == "citizen":
            return reply(current)
        auth.guest_session_limiter.hit(
            request.remote_addr or "unknown",
            "게스트 시작 요청이 많습니다. 잠시 뒤 다시 시도하거나 로그인해 주세요.",
        )
        user = auth.create_guest()
        set_session_actor(user)
        return reply(user)

    @api.post("/auth/logout", tags=[auth_tag], responses={204: None})
    def logout_account() -> Response:
        """현재 로그인된 세션을 즉시 파기합니다."""
        session.clear()
        return Response(status=204)

    @api.get("/auth/me", tags=[auth_tag], responses={200: Actor})
    def auth_me() -> Response:
        """현재 세션의 로그인 사용자 정보(역할·소속 부서 포함)를 반환합니다."""
        return reply(actor())

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
        user = auth.demo_actor(body.role)
        set_session_actor(user)
        return reply(user)

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

    @api.get("/public/workspace", tags=[complaints], responses={200: PublicWorkspace})
    def public_workspace() -> Response:
        """로그인 없이 민원 게시판의 공개 민원을 읽기 전용으로 반환합니다.

        공개로 정해진 민원만 담고 초안·AI 원문·내부 이력·첨부 목록은 제외합니다.
        세션을 만들지 않으며 쓰기 동작은 제공하지 않습니다.

        Returns:
            공개 민원 스냅샷입니다.
        """
        return reply(service.public_workspace())

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
        if user.guest:
            auth.guest_complaint_limiter.hit(
                request.remote_addr or "unknown",
                "게스트 접수 요청이 많습니다. 잠시 뒤 다시 시도하거나 로그인해 주세요.",
            )
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
        "/complaints/<complaint_id>/delete",
        tags=[complaints],
        responses={204: None},
    )
    def delete_complaint(path: ComplaintPath, body: VersionInput) -> Response:
        """작성자 본인의 민원을 저장소에서 완전히 삭제합니다.

        Args:
            path: 민원 식별자입니다.
            body: 기대 버전입니다.

        Returns:
            본문 없는 204 응답입니다.
        """
        service.delete_complaint(actor(), path.complaint_id, body.version)
        return Response(status=204)

    @api.post(
        "/complaints/<complaint_id>/attachments",
        tags=[complaints],
        responses={201: AttachmentItem},
    )
    def upload_complaint_attachment(
        path: ComplaintPath, form: AttachmentUploadForm
    ) -> Response:
        """민원 작성자 본인의 현장 사진(JPG·PNG·WebP) 또는 PDF를 첨부합니다.

        서버에서 매직바이트와 최대 크기(5MB)·개수(최대 5개)를 검증하고,
        이미지의 EXIF 위치·기기 메타데이터를 자동 제거해 저장합니다.

        Args:
            path: 대상 민원 식별자입니다.
            form: 멀티파트 업로드 파일(`file`) 폼입니다.

        Returns:
            저장된 첨부파일의 공개 메타데이터(`AttachmentItem`)입니다.
        """
        raw_bytes = form.file.read()
        raw_filename = form.file.filename or "첨부파일"
        saved = service.upload_attachment(
            actor(), path.complaint_id, raw_bytes, raw_filename
        )
        return reply(saved, 201)

    @api.get(
        "/complaints/<complaint_id>/attachments/<attachment_id>",
        tags=[complaints],
    )
    def get_complaint_attachment(
        path: AttachmentPath, query: AttachmentDownloadQuery
    ) -> Response:
        """권한이 허용된 민원의 첨부파일을 안전 헤더와 함께 반환합니다.

        비공개 민원의 첨부파일은 작성자 본인과 담당자만 열람할 수 있습니다.
        이미지는 기본 `inline` 미리보기(`?download=1`이면 다운로드), PDF는 항상
        `attachment`로 응답하며 스크립트 실행 방지 CSP 샌드박스 헤더를 붙입니다.

        Args:
            path: 민원 ID와 첨부파일 ID 경로입니다.
            query: 강제 다운로드(`download=1`) 여부 쿼리입니다.

        Returns:
            검증된 첨부파일 바이너리 응답입니다.
        """
        item, blob = service.download_attachment(
            actor(), path.complaint_id, path.attachment_id
        )
        ext = os.path.splitext(item.filename)[1] or ""
        disposition = (
            "attachment" if (query.download or not item.is_image) else "inline"
        )
        encoded = quote(item.filename, safe="")
        return Response(
            blob,
            mimetype=item.content_type,
            headers={
                "Content-Disposition": (
                    f'{disposition}; filename="attachment{ext}"; '
                    f"filename*=UTF-8''{encoded}"
                ),
                "Content-Security-Policy": "default-src 'none'; sandbox",
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @api.delete(
        "/complaints/<complaint_id>/attachments/<attachment_id>",
        tags=[complaints],
        responses={204: None},
    )
    def delete_complaint_attachment(path: AttachmentPath) -> Response:
        """답변 게시 전 작성자 본인의 첨부파일을 DB와 저장소에서 삭제합니다.

        Args:
            path: 민원 ID와 첨부파일 ID 경로입니다.

        Returns:
            본문 없는 204 응답입니다.
        """
        service.delete_attachment(actor(), path.complaint_id, path.attachment_id)
        return Response(status=204)

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
        "/complaints/<complaint_id>/visibility",
        tags=[answers],
        responses={200: ComplaintResponse},
    )
    def visibility(path: ComplaintPath, body: VisibilityInput) -> Response:
        """담당자가 민원을 게시판에서 내리거나(비공개 전환) 내린 민원을 다시 공개합니다.

        Args:
            path: 민원 식별자입니다.
            body: 기대 버전, 바꿀 공개 범위, 사유입니다.

        Returns:
            공개 범위가 바뀐 민원입니다.
        """
        return operate(path, body, "visibility")

    @api.put(
        "/complaints/<complaint_id>/assignment",
        tags=[answers],
        responses={200: ComplaintResponse},
    )
    def assignment(path: ComplaintPath, body: AssignmentInput) -> Response:
        """담당자 본인 지정·해제 또는 시연 부서 배정을 수행합니다.

        Args:
            path: 민원 식별자입니다.
            body: 기대 버전과 담당 여부 또는 배정 부서입니다.

        Returns:
            담당 정보가 변경된 민원입니다.
        """
        return operate(path, body, "assign")

    @api.get(
        "/departments",
        tags=[answers],
        responses={200: DepartmentListResponse},
    )
    def list_departments() -> Response:
        """담당자 부서 배정 시 사용하는 청주시 현행 부서 목록을 반환합니다.

        Returns:
            정규화된 청주시 부서 디렉터리 목록입니다.
        """
        return reply(service.list_departments(actor()))

    @api.get(
        "/templates",
        tags=[answers],
        responses={200: TemplateListResponse},
    )
    def list_templates() -> Response:
        """담당자 답변 편집기에서 사용할 자주 쓰는 템플릿 목록을 반환합니다.

        Returns:
            등록순 답변 템플릿 목록입니다.
        """
        return reply(service.list_templates(actor()))

    @api.post(
        "/templates",
        tags=[answers],
        responses={201: AnswerTemplate},
    )
    def create_template(body: TemplateCreateInput) -> Response:
        """담당자가 입력한 커스텀 답변 템플릿을 저장합니다.

        Args:
            body: 템플릿 제목과 삽입할 안내 문구입니다.

        Returns:
            저장한 템플릿 정보입니다.
        """
        return reply(service.create_template(actor(), body), 201)

    @api.delete(
        "/templates/<template_id>",
        tags=[answers],
        responses={204: None},
    )
    def delete_template(path: TemplatePath) -> Response:
        """담당자가 선택한 답변 템플릿을 삭제합니다.

        Args:
            path: 삭제할 템플릿 식별자입니다.

        Returns:
            본문 없는 204 응답입니다.
        """
        service.delete_template(actor(), path.template_id)
        return Response(status=204)

    @api.post(
        "/templates/reset",
        tags=[answers],
        responses={200: TemplateListResponse},
    )
    def reset_templates() -> Response:
        """삭제한 기본 답변 템플릿 5종을 복원합니다.

        Returns:
            복원 후 전체 템플릿 목록입니다.
        """
        return reply(service.reset_templates(actor()))

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
    def start_job(path: ComplaintPath, body: JobStartInput) -> Response:
        """서버에서 AI 응대 분석(또는 시연 작업)을 시작하며 편집본을 덮어쓰지 않습니다.

        Args:
            path: 민원 식별자입니다.
            body: 기대 버전과 선택 LLM 공급자입니다.

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

    @api.get("/staff/events", tags=[jobs])
    def staff_events(query: StaffEventsQuery) -> Response:
        """담당자 전용 실시간 작업·민원 변경 SSE(`text/event-stream`) 스트림을 엽니다.

        `Last-Event-ID` 헤더 또는 `lastEventId` 쿼리로 마지막 커서 이후 누락 이벤트를
        재전달하며, 보관 범위를 초과하면 `resync_required` 이벤트를 보냅니다.
        시민·미인증 세션은 401/403으로 차단합니다.

        Args:
            query: 선택적 `lastEventId` 재연결 커서 쿼리입니다.

        Returns:
            `text/event-stream` 형식의 실시간 SSE 응답입니다.
        """
        service.require_staff(actor())
        cursor: int | None = query.last_event_id
        raw_header = request.headers.get("Last-Event-ID", "").strip()
        if raw_header:
            try:
                parsed = int(raw_header)
                if parsed >= 0:
                    cursor = parsed
            except ValueError:
                cursor = -1

        heartbeat = float(current_app.config.get("SSE_HEARTBEAT_SECONDS", 15.0))
        max_events = current_app.config.get("SSE_MAX_EVENTS")
        max_seconds = current_app.config.get("SSE_MAX_SECONDS")
        stream = service.events.subscribe(
            last_event_id=cursor,
            ai_connected=service.ai_connected,
            heartbeat_seconds=heartbeat,
            max_events=max_events,
            max_seconds=max_seconds,
        )
        return Response(
            stream_with_context(stream),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return api
