"""민원 CRUD와 응대 검사기(LLM + RAG) 통합·비공개 경계·초안 보호를 검증합니다."""

from __future__ import annotations

import json
import os
import threading
import uuid
from typing import Any

from flask.testing import FlaskClient
from flask_openapi3 import OpenAPI
import psycopg
from psycopg import sql
import pytest

from src import create_app
from src.complaints.config import Settings
from src.complaints.models import AssistResponse, Complaint, Job
from src.complaints.repository import PostgresRepository
from src.complaints.service import extract_ai_candidate


def _fake_assist_payload(
    *,
    query: str,
    district: str | None = "흥덕구",
    outcome: str = "faq_answer",
    provider: str = "exaone_api",
    model: str = "k-exaone_v2.5",
    answer: (
        str | None
    ) = "대형폐기물은 수거 신청 후 수수료 납부필증을 부착해 배출해 주세요.",
    staff_draft_answer: str | None = None,
) -> dict[str, Any]:
    """`AssistResponse` 계약을 만족하는 합성 판정 결과를 만듭니다.

    Args:
        query: 검색·판정에 넣은 질의 본문입니다.
        district: 적용·감지된 자치구 이름입니다.
        outcome: 세 갈래 판정 결과입니다.
        provider: 응답에 기록할 LLM 공급자 식별자입니다.
        model: 응답에 기록할 모델 이름입니다.
        answer: FAQ 안내 본문입니다.
        staff_draft_answer: PREFIX-03 담당자 초안 본문입니다.

    Returns:
        `AssistResponse.model_validate`를 통과하는 JSON 호환 사전입니다.
    """
    payload: dict[str, Any] = {
        "query": query,
        "district": district or "흥덕구",
        "districtInferred": district in (None, "모름"),
        "inferredPlace": {
            "title": "오송읍 행정복지센터",
            "roadAddress": "충청북도 청주시 흥덕구 오송읍 오송가락로 123",
        },
        "outcome": outcome,
        "reasonCode": "ok" if outcome == "faq_answer" else "department_candidate",
        "answer": answer,
        "handoffRequired": outcome != "faq_answer",
        "automaticTransfer": False,
        "faq": (
            [
                {
                    "rank": 1,
                    "sourceId": "FAQ-1",
                    "title": "대형폐기물 배출 안내",
                    "excerpt": "수수료 납부필증 부착 안내",
                    "corpus": "faq",
                }
            ]
            if outcome == "faq_answer"
            else []
        ),
        "cases": [
            {
                "rank": 1,
                "sourceId": "CASE-10",
                "title": "오송읍 가로등 점검 요청",
                "excerpt": "현장 확인 예정",
                "corpus": "routing",
                "routingEligible": True,
                "departmentName": "흥덕구 건설과",
                "departmentStatus": "verified",
            }
        ],
        "departments": (
            [
                {
                    "departmentId": "dept-1",
                    "canonicalName": "흥덕구 건설과",
                    "district": "흥덕구",
                    "dutyStatus": "unverified",
                    "jurisdictionStatus": "unverified",
                    "supportingCases": [],
                    "selected": True,
                    "automaticTransfer": False,
                }
            ]
            if outcome != "faq_answer"
            else []
        ),
        "decision": {
            "scope": "in_scope",
            "intent": "faq" if outcome == "faq_answer" else "action",
            "outcome": outcome,
            "reasonCode": "ok" if outcome == "faq_answer" else "department_candidate",
            "evidenceRefs": (
                [{"corpus": "faq", "sourceId": "FAQ-1"}]
                if outcome == "faq_answer"
                else [{"corpus": "routing", "sourceId": "CASE-10"}]
            ),
            "departmentIds": [] if outcome == "faq_answer" else ["dept-1"],
        },
        "policyFailures": [],
        "stages": [{"name": "search", "elapsedMs": 12.0, "ok": True}],
        "llmConfigured": True,
        "llmProvider": provider,
        "llmModel": model,
        "retrieval": {"retrievalOnly": True, "decision": "requires_gate"},
        "codex": [
            {
                "role": "decision",
                "system": "PREFIX-00 + PREFIX-01",
                "user": {"query": query, "provider": provider},
                "sent": True,
                "prompt": f"SYSTEM + {query}",
            }
        ],
    }
    if staff_draft_answer is not None:
        payload["staffDraft"] = {
            "summaryCard": {
                "coreSummary": "가로등 점등 불량 현장 점검 요청",
                "citizenRequest": "현장 점등 확인 요청",
                "locationOrTarget": "흥덕구 오송읍 일원",
                "missingInfo": ["전주 번호"],
            },
            "draftAnswer": staff_draft_answer,
            "citations": [{"corpus": "routing", "sourceId": "CASE-10"}],
            "requiresFieldCheck": True,
        }
    return payload


def _make_fake_iter(
    calls: list[dict[str, Any]],
    *,
    gate: threading.Event | None = None,
    gate_first_only: bool = False,
    fail: bool = False,
) -> Any:
    """백그라운드 워커·검사기 스트림 호출을 기록하는 가짜 이터레이터를 만듭니다.

    Args:
        calls: 전달된 인자를 누적할 목록입니다.
        gate: 설정하면 작업 도중 대기 후 진행합니다.
        gate_first_only: True이면 첫 번째 호출만 대기합니다.
        fail: True이면 `error` 이벤트를 내고 종료합니다.

    Returns:
        `iter_web_assist` 시그니처와 호환되는 제너레이터 함수입니다.
    """

    def _iter(
        query: str,
        district: str | None = None,
        limit: int = 5,
        rerank: bool = False,
        *,
        provider: str | None = None,
    ):
        """가짜 RAG+LLM 스트림 이벤트를 순차 생성하고 호출 인자를 기록합니다."""
        calls.append(
            {
                "query": query,
                "district": district,
                "limit": limit,
                "rerank": rerank,
                "provider": provider,
            }
        )
        call_index = len(calls)
        yield {
            "type": "progress",
            "stage": "search",
            "label": "관련 안내와 사례를 찾고 있어요",
        }
        if gate is not None and (not gate_first_only or call_index == 1):
            gate.wait(timeout=3.0)
        if fail:
            yield {"type": "error", "message": "API 429 rate_limit_exceeded"}
            return
        resolved = provider or "exaone_api"
        if "가로등" in query:
            result = _fake_assist_payload(
                query=query,
                district=district,
                outcome="department_suggestion",
                provider=resolved,
                model="gpt-6-luna" if resolved == "codex_cli" else "k-exaone_v2.5",
                answer=None,
                staff_draft_answer=f"[{resolved}] 담당 부서 후보 확인 후 현장 점검 안내 초안입니다.",
            )
        else:
            result = _fake_assist_payload(
                query=query,
                district=district,
                outcome="faq_answer",
                provider=resolved,
                model="gpt-6-luna" if resolved == "codex_cli" else "k-exaone_v2.5",
                answer=f"[{resolved}] 대형폐기물 배출 안내입니다.",
            )
        yield {"type": "progress", "stage": "done", "label": "정리 완료"}
        yield {"type": "done", "result": result}

    return _iter


def test_assist_fields_endpoint_and_district_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`/api/v1/assist/fields` 익명 조회·읍면동 검증·공급자 전달을 확인합니다."""
    calls: list[dict[str, Any]] = []
    fake_iter = _make_fake_iter(calls)

    def _fake_run(
        query: str,
        district: str | None = None,
        limit: int = 5,
        rerank: bool = False,
        *,
        provider: str | None = None,
    ) -> dict[str, Any]:
        """단건 `run_web_assist` 시그니처와 호환되는 가짜 응답을 돌려줍니다."""
        last: dict[str, Any] = {}
        for event in fake_iter(query, district, limit, rerank, provider=provider):
            if event.get("type") == "done":
                last = event["result"]
        return last

    monkeypatch.setattr("src.complaints.api.iter_web_assist", fake_iter)
    monkeypatch.setattr("src.complaints.api.run_web_assist", _fake_run)

    app = create_app(
        Settings(secret_key="isolated-test-key", backend="memory", testing=True),
        assist_iter_fn=fake_iter,
        auto_start_ai=False,
    )
    anon = app.test_client()

    fields_res = anon.get("/api/v1/assist/fields")
    assert fields_res.status_code == 200
    fields = fields_res.get_json()
    assert "환경·청소" in fields["categories"]
    assert "흥덕구" in fields["districts"]
    assert "오송읍" in fields["districtAreas"]["흥덕구"]
    assert set(fields["providers"].keys()) >= {
        "",
        "exaone_api",
        "codex_cli",
        "openai_api",
    }

    bad_district = anon.post(
        "/api/v1/assist",
        json={"query": "가로등이 안 켜져요", "district": "강남구"},
    )
    assert bad_district.status_code == 422

    ok_res = anon.post(
        "/api/v1/assist",
        json={
            "query": "오송읍 대형폐기물 배출 방법 문의",
            "district": "오송읍",
            "provider": "exaone_api",
        },
    )
    assert ok_res.status_code == 200
    body = ok_res.get_json()
    assert body["llmProvider"] == "exaone_api"
    assert calls[-1]["district"] == "오송읍"
    assert calls[-1]["rerank"] is False
    assert calls[-1]["provider"] == "exaone_api"

    stream_res = anon.post(
        "/api/v1/assist/stream",
        json={
            "query": "가로등 고장 신고합니다",
            "district": "흥덕구",
            "provider": "codex_cli",
        },
    )
    assert stream_res.status_code == 200
    events = [
        json.loads(line)
        for line in stream_res.get_data(as_text=True).splitlines()
        if line.strip()
    ]
    assert events[-1]["type"] == "done"
    assert events[-1]["result"]["llmProvider"] == "codex_cli"
    assert calls[-1]["rerank"] is False
    assert calls[-1]["provider"] == "codex_cli"

    # app 생성 시 assist_iter_fn만 바꿔도 OpenAPI에 /assist/fields 경로가 포함됩니다.
    spec = anon.get("/openapi/openapi.json").get_json()
    assert "/api/v1/assist/fields" in spec["paths"]


def test_complaint_lifecycle_ai_worker_draft_guard_and_privacy() -> None:
    """민원 등록 자동 AI 실행·시민 비공개 경계·담당자 초안 보존을 검증합니다."""
    calls: list[dict[str, Any]] = []
    app = create_app(
        Settings(secret_key="isolated-test-key", backend="memory", testing=True),
        assist_iter_fn=_make_fake_iter(calls),
        auto_start_ai=True,
    )
    service = app.extensions["complaint_service"]

    health = app.test_client().get("/api/v1/health").get_json()
    assert health["aiConnected"] is True

    citizen: FlaskClient = app.test_client()
    assert citizen.post("/api/v1/session", json={"role": "citizen"}).status_code == 200
    staff: FlaskClient = app.test_client()
    assert staff.post("/api/v1/session", json={"role": "staff"}).status_code == 200

    # 1) 시민이 민원을 등록하면 백그라운드에서 AI 분석이 자동 실행됩니다.
    created = citizen.post(
        "/api/v1/complaints",
        json={
            "title": "오송읍 가로등이 꺼져 있습니다",
            "body": "오송읍 행정복지센터 앞 도로 가로등이 밤마다 켜지지 않습니다.",
            "category": "도로·교통",
            "district": "모름",
            "visibility": "private",
        },
    )
    assert created.status_code == 201
    cid = created.get_json()["id"]
    service.wait_for_jobs(timeout=5.0)

    assert len(calls) == 1
    assert "분야:" not in calls[0]["query"]
    assert "오송읍 가로등이 꺼져 있습니다" in calls[0]["query"]
    assert calls[0]["district"] is None

    # 2) 시민 응답에는 AI 참고 정보·초안·작업 상태·미게시 답변이 노출되지 않습니다.
    citizen_view = citizen.get(f"/api/v1/complaints/{cid}").get_json()
    for secret_field in (
        "aiAssist",
        "aiOriginal",
        "aiCandidate",
        "draft",
        "versions",
        "job",
    ):
        assert secret_field not in citizen_view
    assert citizen_view["status"] == "submitted"
    assert citizen_view["published"] is None

    citizen_ws = citizen.get("/api/v1/workspace").get_json()
    assert len(citizen_ws["complaints"]) >= 1
    assert all("aiAssist" not in item for item in citizen_ws["complaints"])

    # 3) 담당자는 aiAssist·summaryCard·PREFIX-03 초안 후보와 자동 채워진 초안을 봅니다.
    staff_view = staff.get(f"/api/v1/complaints/{cid}").get_json()
    assert staff_view["job"]["status"] == "succeeded"
    assert staff_view["aiAssist"]["outcome"] == "department_suggestion"
    assert staff_view["aiAssist"]["departments"][0]["dutyStatus"] == "unverified"
    assert staff_view["aiAssist"]["departments"][0]["automaticTransfer"] is False
    assert "exaone_api" in staff_view["aiOriginal"]
    assert staff_view["draft"] == staff_view["aiCandidate"]
    assert staff_view["published"] is None

    # 4) 담당자가 초안을 수정 저장한 뒤 다른 공급자(codex_cli)로 AI를 재실행해도
    #    담당자가 편집한 draft와 최초 aiOriginal은 덮어쓰지 않습니다.
    edited = staff.put(
        f"/api/v1/complaints/{cid}/draft",
        json={
            "version": staff_view["version"],
            "text": "담당자가 현장 확인 일정을 반영해 수정한 답변 초안입니다.",
            "reason": "현장 일정 반영",
        },
    )
    assert edited.status_code == 200
    edited_body = edited.get_json()

    rerun = staff.post(
        f"/api/v1/complaints/{cid}/jobs",
        json={"version": edited_body["version"], "provider": "codex_cli"},
    )
    assert rerun.status_code == 200
    service.wait_for_jobs(timeout=5.0)

    after_rerun = staff.get(f"/api/v1/complaints/{cid}").get_json()
    assert after_rerun["job"]["status"] == "succeeded"
    assert after_rerun["job"]["provider"] == "codex_cli"
    assert after_rerun["aiAssist"]["llmProvider"] == "codex_cli"
    assert "codex_cli" in after_rerun["aiCandidate"]
    assert (
        after_rerun["draft"]
        == "담당자가 현장 확인 일정을 반영해 수정한 답변 초안입니다."
    )
    assert "exaone_api" in after_rerun["aiOriginal"]

    published = staff.post(
        f"/api/v1/complaints/{cid}/publish",
        json={
            "version": after_rerun["version"],
            "text": after_rerun["draft"],
            "reason": "최종 검토 후 게시",
        },
    )
    assert published.status_code == 200
    pub_body = published.get_json()
    assert pub_body["published"]["origin"] == "ai_edited"
    assert pub_body["status"] == "answered"
    citizen_after_pub = citizen.get(f"/api/v1/complaints/{cid}").get_json()
    assert citizen_after_pub["published"]["text"] == after_rerun["draft"]
    assert "aiAssist" not in citizen_after_pub
    assert "versions" not in citizen_after_pub


def test_late_ai_superseded_and_failure_resilience() -> None:
    """민원 수정·작업 취소 시 지연 AI 결과가 폐기되고 실패 시에도 민원이 보존됩니다."""
    calls: list[dict[str, Any]] = []
    gate = threading.Event()
    slow_app = create_app(
        Settings(secret_key="isolated-test-key", backend="memory", testing=True),
        assist_iter_fn=_make_fake_iter(calls, gate=gate),
        auto_start_ai=True,
    )
    slow_service = slow_app.extensions["complaint_service"]
    citizen = slow_app.test_client()
    staff = slow_app.test_client()
    citizen.post("/api/v1/session", json={"role": "citizen"})
    staff.post("/api/v1/session", json={"role": "staff"})

    created = citizen.post(
        "/api/v1/complaints",
        json={
            "title": "지연 실행 취소 테스트 민원입니다",
            "body": "대형폐기물 배출 수수료와 수거 신청 방법이 궁금합니다.",
            "category": "환경·청소",
            "district": "상당구",
            "visibility": "private",
        },
    ).get_json()
    cid = created["id"]

    # 진행 중 작업이 대기하는 동안 담당자가 취소하면 완료 신호가 도착해도 반영되지 않습니다.
    staff_now = staff.get(f"/api/v1/complaints/{cid}").get_json()
    cancelled = staff.post(
        f"/api/v1/complaints/{cid}/jobs/cancel",
        json={"version": staff_now["version"]},
    )
    assert cancelled.status_code == 200
    assert cancelled.get_json()["job"]["status"] == "cancelled"

    gate.set()
    slow_service.wait_for_jobs(timeout=5.0)
    after_cancel = staff.get(f"/api/v1/complaints/{cid}").get_json()
    assert after_cancel["job"]["status"] == "cancelled"
    assert after_cancel["aiAssist"] is None
    assert after_cancel["draft"] == ""

    # 시민이 민원 내용을 수정(contextVersion 증가)해도 이전 대기 작업 결과가 새 분석을 덮지 않습니다.
    update_gate = threading.Event()
    update_calls: list[dict[str, Any]] = []
    update_app = create_app(
        Settings(secret_key="isolated-test-key", backend="memory", testing=True),
        assist_iter_fn=_make_fake_iter(
            update_calls, gate=update_gate, gate_first_only=True
        ),
        auto_start_ai=True,
    )
    upd_service = update_app.extensions["complaint_service"]
    upd_citizen = update_app.test_client()
    upd_staff = update_app.test_client()
    upd_citizen.post("/api/v1/session", json={"role": "citizen"})
    upd_staff.post("/api/v1/session", json={"role": "staff"})

    first_row = upd_citizen.post(
        "/api/v1/complaints",
        json={
            "title": "수정 전 대형폐기물 민원입니다",
            "body": "대형폐기물 배출 수수료와 수거 신청 방법이 궁금합니다.",
            "category": "환경·청소",
            "district": "상당구",
            "visibility": "private",
        },
    ).get_json()
    edited = upd_citizen.put(
        f"/api/v1/complaints/{first_row['id']}",
        json={
            "version": first_row["version"],
            "title": "수정 후 오송읍 가로등 민원입니다",
            "body": "오송읍 행정복지센터 앞 가로등이 켜지지 않습니다.",
            "category": "도로·교통",
            "district": "흥덕구",
            "visibility": "private",
        },
    )
    assert edited.status_code == 200
    update_gate.set()
    upd_service.wait_for_jobs(timeout=5.0)
    final_staff = upd_staff.get(f"/api/v1/complaints/{first_row['id']}").get_json()
    assert final_staff["job"]["status"] == "succeeded"
    assert final_staff["job"]["contextVersion"] == 2
    assert final_staff["aiAssist"]["outcome"] == "department_suggestion"
    assert "가로등" in final_staff["aiAssist"]["query"]

    # 실패하는 AI 공급자에서도 민원 등록과 기존 초안은 유지됩니다.
    fail_app = create_app(
        Settings(secret_key="isolated-test-key", backend="memory", testing=True),
        assist_iter_fn=_make_fake_iter([], fail=True),
        auto_start_ai=True,
    )
    fail_service = fail_app.extensions["complaint_service"]
    fail_citizen = fail_app.test_client()
    fail_staff = fail_app.test_client()
    fail_citizen.post("/api/v1/session", json={"role": "citizen"})
    fail_staff.post("/api/v1/session", json={"role": "staff"})

    saved = fail_citizen.post(
        "/api/v1/complaints",
        json={
            "title": "API 429 오류에도 민원이 저장되어야 합니다",
            "body": "외부 모델이 혼잡해도 민원 데이터는 유지됩니다.",
            "category": "기타",
            "district": "청원구",
            "visibility": "private",
        },
    )
    assert saved.status_code == 201
    fail_id = saved.get_json()["id"]
    fail_service.wait_for_jobs(timeout=5.0)
    failed_view = fail_staff.get(f"/api/v1/complaints/{fail_id}").get_json()
    assert failed_view["job"]["status"] == "failed"
    assert "429" in failed_view["job"]["stage"]
    assert failed_view["title"] == "API 429 오류에도 민원이 저장되어야 합니다"


def test_extract_ai_candidate_strips_unverified_tag_when_staff_draft_missing() -> None:
    """담당자 초안이 비어 있을 때 민원 웹 후보 문장에 검사기용 미검증 표기를 넣지 않습니다."""
    assist = AssistResponse.model_validate(
        _fake_assist_payload(
            query="오송읍 가로등 고장",
            district="흥덕구",
            outcome="department_suggestion",
            provider="exaone_api",
            answer=(
                "유사한 공개 사례를 기준으로 담당 부서 후보를 안내합니다. "
                "공식 접수·이관이 아니며 담당자 확인이 필요합니다.\n"
                "- 흥덕구 건설과 (업무분장: unverified, 자동 이관 아님)"
            ),
            staff_draft_answer=None,
        )
    )
    candidate = extract_ai_candidate(assist)
    assert "흥덕구 건설과" in candidate
    assert "업무분장:" not in candidate
    assert "자동 이관 아님" not in candidate


@pytest.mark.skipif(
    os.getenv("RUN_PG_TESTS") != "1",
    reason="RUN_PG_TESTS=1에서 PostgreSQL ai_assist 왕복 저장을 검증합니다.",
)
def test_postgres_roundtrip_ai_assist_and_provider() -> None:
    """PostgreSQL 업무 저장소가 `ai_assist`와 `job.provider`를 손실 없이 왕복 저장합니다."""
    schema = "complaint_app_test_" + uuid.uuid4().hex[:12]
    try:
        store = PostgresRepository(schema=schema)
        assist = AssistResponse.model_validate(
            _fake_assist_payload(
                query="오송읍 가로등 고장",
                district="흥덕구",
                outcome="department_suggestion",
                provider="exaone_api",
                answer=None,
                staff_draft_answer="담당자 초안입니다.",
            )
        )
        row = Complaint(
            id="DEMO-AI-PG-1",
            title="오송읍 가로등 점등 불량",
            body="오송읍 행정복지센터 앞 도로 가로등이 꺼져 있습니다.",
            category="도로·교통",
            district="흥덕구",
            owner="citizen-1",
            visibility="private",
            job=Job(
                status="succeeded",
                stage="완료",
                attempt=1,
                context_version=1,
                provider="exaone_api",
            ),
            ai_assist=assist,
        )
        stored = store.create(row, key="ai-pg-1", fingerprint="fp-ai-pg-1")
        loaded = store.get(stored.id)
        assert loaded.job.provider == "exaone_api"
        assert loaded.ai_assist is not None
        assert loaded.ai_assist.outcome == "department_suggestion"
        assert loaded.ai_assist.departments[0].duty_status == "unverified"
        assert loaded.ai_assist.staff_draft is not None
        assert loaded.ai_assist.staff_draft.draft_answer == "담당자 초안입니다."
    finally:
        with psycopg.connect(autocommit=True, connect_timeout=10) as conn:
            conn.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                    sql.Identifier(schema)
                )
            )
