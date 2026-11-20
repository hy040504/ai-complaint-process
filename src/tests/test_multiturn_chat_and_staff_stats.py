"""시민 다중 턴 챗봇(DB 영속·임시 대화)과 담당자 통계·CSV 내보내기 테스트입니다."""

from __future__ import annotations

import csv
import io
import json
import os
from typing import Any
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from src.app import create_app
from src.assist.pipeline import iter_assist
from src.complaints.chat import build_multiturn_chat_context
from src.complaints.config import Settings
from src.complaints.models import (
    AssistResponse,
    ChatTurnItem,
    Complaint,
    Message,
    utcnow,
)
from src.complaints.repository import PostgresRepository


def _make_assist_payload(
    *,
    query: str,
    district: str | None = "흥덕구",
    outcome: str = "faq_answer",
    reason_code: str = "ok",
    answer: str = "대형폐기물 신고필증을 부착해 배출해 주세요.",
    include_sensitive: bool = True,
) -> dict[str, Any]:
    """테스트용 응대 결과 원시 사전을 생성합니다.

    Args:
        query: 검색·판정에 전달된 질의 문자열입니다.
        district: 추론 또는 지정된 관할 구입니다.
        outcome: 판정 갈래입니다.
        reason_code: 판정 사유 코드입니다.
        answer: 안내 문장입니다.
        include_sensitive: 민감 내부 필드(`staffDraft`, `sanitize`, `codex`) 포함 여부입니다.

    Returns:
        `AssistResponse` 호환 딕셔너리입니다.
    """
    payload: dict[str, Any] = {
        "query": query,
        "district": district,
        "districtInferred": district is not None,
        "inferredPlace": None,
        "outcome": outcome,
        "reasonCode": reason_code,
        "answer": answer,
        "handoffRequired": outcome != "faq_answer",
        "automaticTransfer": False,
        "faq": [
            {
                "rank": 1,
                "sourceId": "FAQ-01",
                "title": "대형폐기물 배출 안내",
                "sourceUrl": "https://toktalk.cheongju.go.kr/faq/1",
                "excerpt": "신고필증 부착 및 수수료 안내",
                "corpus": "faq",
            }
        ],
        "cases": [
            {
                "rank": 1,
                "sourceId": "CASE-900",
                "title": "과거 공개 사례 비공개 검증용",
                "excerpt": "절대 시민 챗봇에 노출 금지 사례 본문",
                "corpus": "routing",
                "routingEligible": True,
                "departmentName": "흥덕구 환경위생과",
                "departmentStatus": "verified",
            }
        ],
        "departments": [
            {
                "departmentId": "dept-env",
                "canonicalName": "흥덕구 환경위생과",
                "district": "흥덕구",
                "dutyStatus": "unverified",
                "jurisdictionStatus": "inferred_from_name",
                "supportingCases": [],
                "selected": True,
                "automaticTransfer": False,
            }
        ],
        "decision": {
            "scope": "in_scope",
            "intent": "faq" if outcome == "faq_answer" else "action",
            "outcome": outcome,
            "reasonCode": reason_code,
            "evidenceRefs": [{"corpus": "faq", "sourceId": "FAQ-01"}],
            "departmentIds": ["dept-env"],
            "modelRaw": {"secret": "internal_model_raw_only"},
        },
        "policyFailures": [],
        "stages": [{"name": "search", "elapsedMs": 5.0, "ok": True}],
        "llmConfigured": True,
        "llmProvider": "codex_cli",
        "llmModel": "gpt-5.4",
        "retrieval": {
            "retrievalOnly": True,
            "decision": "requires_gate",
            "elapsedMs": 5.0,
            "pipeline": "test",
        },
        "codex": [],
        "staffDraft": None,
        "sanitize": None,
    }
    if include_sensitive:
        payload["codex"] = [
            {
                "role": "decision",
                "system": "PREFIX-00+01",
                "user": {"query": query},
                "sent": True,
                "prompt": "내부 시스템 프롬프트 전문",
            }
        ]
        payload["staffDraft"] = {
            "summaryCard": {
                "coreSummary": "담당자 비공개 요약",
                "citizenRequest": "요청",
                "locationOrTarget": "흥덕구",
                "missingInfo": [],
            },
            "draftAnswer": "절대노출금지_담당자초안_본문",
            "citations": [{"corpus": "faq", "sourceId": "FAQ-01"}],
            "requiresFieldCheck": False,
        }
        payload["sanitize"] = {
            "sanitizedSummary": "절대노출금지_순화요약_본문",
            "legitimateRequests": ["정상 요청"],
            "riskSignals": ["profanity_insult"],
            "humanProtectionReviewNeeded": True,
        }
    return payload


def test_build_multiturn_chat_context_followup_and_topic_switch() -> None:
    """짧은 후속 질문은 문맥·구를 보강하고 주제 전환·타 지자체는 이전 문맥을 차단합니다."""
    history = [
        ChatTurnItem(
            role="user",
            content="흥덕구에서 대형폐기물 배출 방법이 궁금해요",
            district="흥덕구",
        ),
        ChatTurnItem(
            role="assistant",
            content="대형폐기물은 신고필증을 부착해 배출해 주세요.",
            district="흥덕구",
        ),
    ]

    # 1. 짧은 후속 질문 -> 직전 주제 보강 + 직전 구 이어받기
    eff_q, eff_d, compact = build_multiturn_chat_context(
        "그럼 수수료는요?", None, history
    )
    assert "대형폐기물 배출 방법" in eff_q
    assert "그럼 수수료는요?" in eff_q
    assert eff_d == "흥덕구"
    assert len(compact) == 2

    # 2. 관할 보완 발화 -> 직전 주제 보강하되 새 지명(오창읍=청원구)이므로 흥덕구로 덮지 않음
    eff_q2, eff_d2, _ = build_multiturn_chat_context("오창읍이에요", None, history)
    assert "대형폐기물 배출 방법" in eff_q2
    assert "오창읍이에요" in eff_q2
    assert eff_d2 is None  # 본문 내 오창읍 자동 감지가 청원구를 선택하도록 None 유지

    # 3. 명시적 주제 전환 -> 이전 주제 오염 차단
    eff_q3, eff_d3, _ = build_multiturn_chat_context(
        "다른 질문인데요 청주시 공영주차장 월정기권 신청 방법이 궁금해요", None, history
    )
    assert "대형폐기물" not in eff_q3
    assert eff_d3 is None

    # 4. 타 지자체 언급 -> 이전 청주 구 이어받기 차단
    eff_q4, eff_d4, _ = build_multiturn_chat_context(
        "천안시 서북구 가로등이 고장났어요", None, history
    )
    assert "대형폐기물" not in eff_q4
    assert eff_d4 is None


def test_iter_assist_keeps_prefix_unchanged_and_injects_history_only_in_user_json() -> (
    None
):
    """`conversation_history`는 가변 `user` JSON에만 들어가고 PREFIX-00~02는 바이트 동일 유지됩니다."""
    captured: list[tuple[str, dict[str, Any]]] = []

    def fake_search(
        query: str, district: str | None, limit: int, rerank: bool
    ) -> dict[str, Any]:
        """최소 FAQ 1건을 반환하는 테스트 검색 스텁입니다."""
        del query, district, limit, rerank
        return {
            "retrieval_only": True,
            "decision": "requires_gate",
            "results": {
                "faq_knowledge": {
                    "hits": [
                        {
                            "rank": 1,
                            "source_id": "FAQ-10",
                            "title": "대형폐기물 배출 및 수수료",
                            "excerpt": "품목별 2,000원~15,000원",
                            "source_url": "https://toktalk.cheongju.go.kr/faq/10",
                        }
                    ]
                },
                "routing_cases": {"hits": [], "department_candidates": []},
            },
        }

    def fake_llm(system: str, user: str) -> str:
        """호출된 system과 user JSON을 기록하고 판정/FAQ 답변을 반환합니다."""
        parsed = json.loads(user)
        captured.append((system, parsed))
        if len(captured) % 2 == 1:
            return json.dumps(
                {
                    "scope": "in_scope",
                    "intent": "information",
                    "outcome": "faq_answer",
                    "reason_code": "ok",
                    "evidence_refs": [{"corpus": "faq", "source_id": "FAQ-10"}],
                    "department_ids": [],
                    "sanitize_needed": False,
                },
                ensure_ascii=False,
            )
        return "대형폐기물 수수료는 품목에 따라 2,000원~15,000원입니다."

    # 1. 단일 턴 호출
    list(
        iter_assist(
            "대형폐기물 방법",
            "흥덕구",
            search_fn=fake_search,
            llm_fn=fake_llm,
            include_staff_outputs=False,
        )
    )
    # 2. 다중 턴 호출
    list(
        iter_assist(
            "대형폐기물 방법 — 그럼 수수료는요?",
            "흥덕구",
            search_fn=fake_search,
            llm_fn=fake_llm,
            include_staff_outputs=False,
            conversation_history=[
                {"role": "user", "content": "대형폐기물 방법"},
                {"role": "assistant", "content": "신고필증을 부착하세요."},
            ],
        )
    )

    assert len(captured) == 4
    single_dec_sys, single_dec_user = captured[0]
    single_faq_sys, single_faq_user = captured[1]
    multi_dec_sys, multi_dec_user = captured[2]
    multi_faq_sys, multi_faq_user = captured[3]

    # Prefix Caching 보존: 시스템 프롬프트 바이트 완전 일치
    assert single_dec_sys == multi_dec_sys
    assert single_faq_sys == multi_faq_sys
    # 단일 턴은 키 생략, 다중 턴은 user JSON에만 주입
    assert "conversation_history" not in single_dec_user
    assert "conversation_history" not in single_faq_user
    assert len(multi_dec_user["conversation_history"]) == 2
    assert len(multi_faq_user["conversation_history"]) == 2


def _make_recording_iter(calls: list[dict[str, Any]]):
    """호출 인자를 기록하고 민감 필드가 섞인 가짜 응대 결과를 내보내는 스트림 함수를 만듭니다."""

    def fake_iter(
        query: str,
        district: str | None,
        limit: int,
        rerank: bool,
        provider: str | None = None,
        *,
        include_staff_outputs: bool = True,
        conversation_history: list[dict[str, str]] | None = None,
    ):
        """테스트용 가짜 RAG+LLM 스트림을 생성합니다."""
        calls.append(
            {
                "query": query,
                "district": district,
                "include_staff_outputs": include_staff_outputs,
                "conversation_history": conversation_history,
            }
        )
        yield {"type": "progress", "key": "read", "label": "민원 내용을 읽고 있어요"}
        yield {
            "type": "done",
            "result": _make_assist_payload(
                query=query,
                district=district or "흥덕구",
                outcome="faq_answer",
                answer=f"안내 응답: {query}",
                include_sensitive=True,
            ),
        }

    return fake_iter


def _run_multiturn_chat_suite(app: Any, calls: list[dict[str, Any]]) -> None:
    """Memory/PostgreSQL 공통으로 다중 턴 챗봇 저장·격리·비로그인 임시 대화를 검증합니다."""
    c1 = app.test_client()
    c2 = app.test_client()
    anon = app.test_client()
    staff = app.test_client()

    # 1. 실계정 민원인 1 로그인 (시드 계정 citizen_01)
    assert (
        c1.post(
            "/api/v1/auth/login",
            json={
                "loginId": "citizen_01",
                "password": os.environ.get(
                    "COMPLAINT_CITIZEN_INIT_PASSWORD", "cheongju-citizen-2026!"
                ),
            },
        ).status_code
        == 200
    )

    # 1턴 전송 -> 새 세션 자동 생성 및 DB 영속 저장
    r1 = c1.post(
        "/api/v1/citizen/chat",
        json={"message": "흥덕구 대형폐기물 배출 방법이 궁금해요"},
    )
    assert r1.status_code == 200
    b1 = r1.get_json()
    assert b1["persisted"] is True
    assert b1["sessionId"] and b1["sessionId"].startswith("CHAT-")
    sid = b1["sessionId"]
    assert b1["effectiveQuery"] is None
    assert calls[-1]["include_staff_outputs"] is False
    assert calls[-1]["conversation_history"] is None

    # 2턴 전송 -> sessionId 전달 시 DB 이력 자동 주입 + effectiveQuery 보강
    r2 = c1.post(
        "/api/v1/citizen/chat",
        json={"message": "그럼 수수료는요?", "sessionId": sid},
    )
    assert r2.status_code == 200
    b2 = r2.get_json()
    assert b2["sessionId"] == sid
    assert b2["persisted"] is True
    assert b2["query"] == "그럼 수수료는요?"
    assert b2["effectiveQuery"] and "대형폐기물" in b2["effectiveQuery"]
    assert calls[-1]["district"] == "흥덕구"
    assert calls[-1]["conversation_history"] is not None
    assert len(calls[-1]["conversation_history"]) == 2

    # 세션 목록 & 상세 조회 검증 (민감 필드 완전 부재)
    list_res = c1.get("/api/v1/citizen/chat/sessions")
    assert list_res.status_code == 200
    list_body = list_res.get_json()
    assert list_body["persisted"] is True
    assert len(list_body["sessions"]) == 1
    assert list_body["sessions"][0]["id"] == sid
    assert list_body["sessions"][0]["messageCount"] == 4

    detail_res = c1.get(f"/api/v1/citizen/chat/sessions/{sid}")
    assert detail_res.status_code == 200
    detail_body = detail_res.get_json()
    assert [m["role"] for m in detail_body["messages"]] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    raw_detail = json.dumps(detail_body, ensure_ascii=False)
    for forbidden in (
        "절대노출금지_담당자초안_본문",
        "절대노출금지_순화요약_본문",
        "내부 시스템 프롬프트 전문",
        "internal_model_raw_only",
        "staffDraft",
    ):
        assert forbidden not in raw_detail

    # 2. 타 민원인 격리 검증 (404)
    assert (
        c2.post(
            "/api/v1/auth/register",
            json={
                "loginId": "citizen_other_01",
                "password": "other-password-2026!",
                "displayName": "다른시민",
            },
        ).status_code
        == 201
    )
    assert c2.get(f"/api/v1/citizen/chat/sessions/{sid}").status_code == 404
    assert c2.delete(f"/api/v1/citizen/chat/sessions/{sid}").status_code == 404
    assert (
        c2.post(
            "/api/v1/citizen/chat",
            json={"message": "남의 세션 이어쓰기 시도", "sessionId": sid},
        ).status_code
        == 404
    )

    # 3. 담당자 격리 검증 (403 citizen_required)
    assert (
        staff.post(
            "/api/v1/auth/login",
            json={
                "loginId": "staff_admin",
                "password": os.environ.get(
                    "COMPLAINT_STAFF_INIT_PASSWORD", "cheongju-staff-2026!"
                ),
            },
        ).status_code
        == 200
    )
    assert staff.get("/api/v1/citizen/chat/sessions").status_code == 403
    assert staff.get(f"/api/v1/citizen/chat/sessions/{sid}").status_code == 403
    assert staff.delete(f"/api/v1/citizen/chat/sessions/{sid}").status_code == 403

    # 4. 비로그인 시연 시민 -> DB 미저장 임시 다중 턴 동작
    assert anon.post("/api/v1/session", json={"role": "citizen"}).status_code == 200
    anon_list = anon.get("/api/v1/citizen/chat/sessions")
    assert anon_list.status_code == 200
    assert anon_list.get_json() == {"sessions": [], "persisted": False}
    assert anon.get(f"/api/v1/citizen/chat/sessions/{sid}").status_code == 403
    anon_chat = anon.post(
        "/api/v1/citizen/chat",
        json={
            "message": "그럼 수수료는요?",
            "history": [
                {"role": "user", "content": "전입신고 방법", "district": "서원구"},
                {
                    "role": "assistant",
                    "content": "정부24에서 신청 가능합니다.",
                    "district": "서원구",
                },
            ],
        },
    )
    assert anon_chat.status_code == 200
    anon_body = anon_chat.get_json()
    assert anon_body["persisted"] is False
    assert anon_body["sessionId"] is None
    assert anon_body["effectiveQuery"] and "전입신고" in anon_body["effectiveQuery"]
    assert calls[-1]["district"] == "서원구"

    # 5. 소유자 삭제 -> 204 및 연쇄 삭제 확인
    assert c1.delete(f"/api/v1/citizen/chat/sessions/{sid}").status_code == 204
    assert c1.get(f"/api/v1/citizen/chat/sessions/{sid}").status_code == 404
    assert c1.get("/api/v1/citizen/chat/sessions").get_json()["sessions"] == []


def test_multiturn_chat_persistence_and_isolation_memory() -> None:
    """메모리 저장소에서 다중 턴 챗봇 저장·타인/담당자 격리·비로그인 임시 대화를 검증합니다."""
    calls: list[dict[str, Any]] = []
    app = create_app(
        Settings(secret_key="test-mt-mem", backend="memory", testing=True),
        assist_iter_fn=_make_recording_iter(calls),
        auto_start_ai=False,
    )
    _run_multiturn_chat_suite(app, calls)


@pytest.mark.skipif(
    os.environ.get("RUN_PG_TESTS") != "1",
    reason="RUN_PG_TESTS=1 환경에서만 격리 PostgreSQL 스키마를 검증합니다.",
)
def test_multiturn_chat_persistence_and_isolation_postgres() -> None:
    """PostgreSQL 격리 스키마에서 `chat_sessions`/`chat_messages` 영속성과 ON DELETE CASCADE를 검증합니다."""
    schema = f"complaint_app_chat_{uuid4().hex[:8]}"
    calls: list[dict[str, Any]] = []
    repo = PostgresRepository(schema=schema)
    try:
        app = create_app(
            Settings(
                secret_key="test-mt-pg",
                backend="postgresql",
                schema=schema,
                testing=True,
            ),
            repository=repo,
            assist_iter_fn=_make_recording_iter(calls),
            auto_start_ai=False,
        )
        _run_multiturn_chat_suite(app, calls)
        # 삭제 후 chat_messages 행도 연쇄 삭제(0건)되었는지 직접 확인합니다.
        with repo.connection() as conn:
            row = conn.execute(
                sql.SQL("SELECT count(*) FROM {}.chat_messages").format(
                    sql.Identifier(schema)
                )
            ).fetchone()
            assert row is not None and row[0] == 0
    finally:
        with psycopg.connect(connect_timeout=10) as conn:
            conn.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                    sql.Identifier(schema)
                )
            )
            conn.commit()


def test_staff_stats_rbac_synthetic_toggle_and_safe_csv_export() -> None:
    """담당자 통계 RBAC 소관 범위·시연 토글과 수식 방어·민감정보 제외 CSV 내보내기를 검증합니다."""
    app = create_app(
        Settings(secret_key="test-stats-csv", backend="memory", testing=True),
        auto_start_ai=False,
    )
    service = app.extensions["complaint_service"]
    repo = service.repository

    # 테스트 민원 4건 구성:
    # 1) 서원구 건설과 배정 + 수식 주입 제목 + 미게시 비공개 초안/순화 + AI 부서추천
    c_seowon = Complaint(
        id="DEMO-2026-SEOWON01",
        owner="citizen-01",
        title='=HYPERLINK("http://evil.example","클릭") 서원구 도로 파손',
        body="사창동 사거리 포트홀 현장 수리가 필요합니다.",
        district="서원구",
        category="도로·교통",
        status="under_review",
        visibility="private",
        department="서원구 건설과",
        assigned=True,
        assignee_id="staff-seowon",
        assignee_name="서원구 건설과 담당자",
        draft="절대CSV노출금지_미게시초안",
        ai_original="절대CSV노출금지_AI원본",
        ai_assist=AssistResponse.model_validate(
            _make_assist_payload(
                query="서원구 도로 파손",
                district="서원구",
                outcome="department_suggestion",
                reason_code="department_candidate",
            )
        ),
        messages=[Message(text="추가 문의 1"), Message(text="추가 문의 2")],
        is_synthetic=False,
    )
    # 2) 흥덕구 환경위생과 배정 (서원구 담당자는 집계·CSV에서 제외되어야 함!)
    c_heungdeok = Complaint(
        id="DEMO-2026-HEUNG01",
        owner="citizen-01",
        title="흥덕구 대형폐기물 수거 지연",
        body="복대동 대형폐기물 스티커 부착 후 미수거입니다.",
        district="흥덕구",
        category="환경·청소",
        status="submitted",
        visibility="public",
        department="흥덕구 환경위생과",
        assigned=True,
        assignee_id="staff-heungdeok",
        assignee_name="흥덕구 환경위생과 담당자",
        ai_assist=AssistResponse.model_validate(
            _make_assist_payload(
                query="대형폐기물",
                district="흥덕구",
                outcome="faq_answer",
                reason_code="ok",
            )
        ),
        is_synthetic=False,
    )
    # 3) 부서 미배정 민원 (총괄 + 서원구 담당자 모두 소관 범위 포함)
    c_unassigned = Complaint(
        id="DEMO-2026-OPEN001",
        owner="citizen-01",
        title="+1+1 공원 가로등 점멸 신고",
        body="청원구 오창 호수공원 산책로 가로등이 깜빡거립니다.",
        district="청원구",
        category="공원·녹지",
        status="submitted",
        visibility="private",
        is_synthetic=False,
    )
    # 4) 공개 시연 합성 데이터(DEMO-PUB-*)
    c_synth = Complaint(
        id="DEMO-PUB-999",
        owner="citizen-demo",
        title="시연용 공개 민원 예시",
        body="공개 시연 데이터 토글 검증용 민원입니다.",
        district="상당구",
        category="기타",
        status="answered",
        visibility="public",
        is_synthetic=True,
        date=utcnow(),
    )
    for row in (c_seowon, c_heungdeok, c_unassigned, c_synth):
        repo.create(row, None, row.id)

    citizen = app.test_client()
    admin = app.test_client()
    seowon = app.test_client()

    # 시민 계정 접근 차단 (403)
    assert citizen.post("/api/v1/session", json={"role": "citizen"}).status_code == 200
    assert citizen.get("/api/v1/staff/stats").status_code == 403
    assert citizen.get("/api/v1/staff/complaints/export.csv").status_code == 403

    staff_pw = os.environ.get("COMPLAINT_STAFF_INIT_PASSWORD", "cheongju-staff-2026!")
    assert (
        admin.post(
            "/api/v1/auth/login", json={"loginId": "staff_admin", "password": staff_pw}
        ).status_code
        == 200
    )
    assert (
        seowon.post(
            "/api/v1/auth/login", json={"loginId": "staff_seowon", "password": staff_pw}
        ).status_code
        == 200
    )

    # 1. 총괄 담당자 통계 (시연 포함 4건 / 제외 3건)
    admin_all = admin.get("/api/v1/staff/stats?includeSynthetic=1").get_json()
    assert admin_all["isAdminScope"] is True
    assert admin_all["totalComplaints"] == 4
    assert admin_all["realComplaints"] == 3
    assert admin_all["syntheticComplaints"] == 1
    assert admin_all["operational"]["unpublishedDrafts"] == 1
    assert admin_all["operational"]["withFollowups"] == 1
    assert admin_all["dbSummary"]["normalizedTables"]["complaints"] == 4

    admin_real = admin.get("/api/v1/staff/stats?includeSynthetic=0").get_json()
    assert admin_real["totalComplaints"] == 3
    assert admin_real["realComplaints"] == 3
    assert admin_real["syntheticComplaints"] == 1

    # 2. 부서 담당자(서원구 건설과) RBAC 범위 검증 -> 흥덕구 배정 1건 자동 제외!
    seowon_all = seowon.get("/api/v1/staff/stats?includeSynthetic=1").get_json()
    assert seowon_all["isAdminScope"] is False
    assert "서원구 건설과" in seowon_all["scopeLabel"]
    assert seowon_all["totalComplaints"] == 3  # c_seowon + c_unassigned + c_synth
    assert seowon_all["realComplaints"] == 2
    dept_keys = {b["key"] for b in seowon_all["byDepartment"]}
    assert "흥덕구 환경위생과" not in dept_keys

    # 3. CSV 내보내기: UTF-8 BOM, RBAC 범위, 수식 주입 방어, 민감 필드 배제
    csv_res = seowon.get(
        "/api/v1/staff/complaints/export.csv?includeSynthetic=0&sort=most_followups"
    )
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.content_type
    assert "attachment; filename=" in csv_res.headers.get("Content-Disposition", "")
    raw_bytes = csv_res.get_data()
    assert raw_bytes.startswith(b"\xef\xbb\xbf")
    text = raw_bytes.decode("utf-8-sig")

    # 미게시 초안·AI원본·순화 절대 미포함 검증
    for secret in (
        "절대CSV노출금지_미게시초안",
        "절대CSV노출금지_AI원본",
        "절대노출금지_담당자초안_본문",
        "절대노출금지_순화요약_본문",
    ):
        assert secret not in text

    parsed = list(csv.DictReader(io.StringIO(text)))
    # 서원구 담당자 + 시연 제외 -> c_seowon(문의2건), c_unassigned(문의0건) 2건만 포함
    assert [row["민원ID"] for row in parsed] == [
        "DEMO-2026-SEOWON01",
        "DEMO-2026-OPEN001",
    ]
    # 수식 선두(=, +) 중화 확인
    assert parsed[0]["제목"].startswith("'=HYPERLINK")
    assert parsed[1]["제목"].startswith("'+1+1")
    assert parsed[0]["추가문의수"] == "2"

    # 4. 본문·부서 통합 검색 + AI 판정 필터 CSV & 페이지 검증
    q_csv = admin.get(
        "/api/v1/staff/complaints/export.csv?q=포트홀&aiOutcome=department_suggestion"
    )
    q_rows = list(csv.DictReader(io.StringIO(q_csv.get_data().decode("utf-8-sig"))))
    assert [row["민원ID"] for row in q_rows] == ["DEMO-2026-SEOWON01"]

    page_res = admin.get("/api/v1/complaints?q=포트홀").get_json()
    assert [row["id"] for row in page_res["complaints"]] == ["DEMO-2026-SEOWON01"]
