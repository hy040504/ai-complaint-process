"""담당자 실시간 SSE 푸시(`BE07`)와 시민 챗봇 실연결·비공개 경계를 검증합니다."""

from __future__ import annotations

import json
import threading
from typing import Any

from src import create_app
from src.assist.pipeline import iter_assist
from src.complaints.config import Settings
from src.complaints.events import StaffEventBroker
from src.tests.test_complaint_ai import _fake_assist_payload


def _parse_sse_frames(raw_text: str) -> list[dict[str, Any]]:
    """SSE 응답 원문을 이벤트 프레임 사전 목록으로 분해합니다.

    Args:
        raw_text: `text/event-stream` 응답 문자열입니다.

    Returns:
        `id`·`event`·`data`·`comment` 키를 담은 프레임 목록입니다.
    """
    frames: list[dict[str, Any]] = []
    for block in raw_text.split("\n\n"):
        if not block.strip():
            continue
        frame: dict[str, Any] = {}
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith(":"):
                frame["comment"] = line[1:].strip()
            elif line.startswith("id:"):
                frame["id"] = int(line.split(":", 1)[1].strip())
            elif line.startswith("event:"):
                frame["event"] = line.split(":", 1)[1].strip()
            elif line.startswith("retry:"):
                frame["retry"] = int(line.split(":", 1)[1].strip())
            elif line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].strip())
        if data_lines:
            frame["data"] = json.loads("\n".join(data_lines))
        frames.append(frame)
    return frames


def test_staff_event_broker_cursor_replay_resync_and_heartbeat() -> None:
    """SSE 브로커는 커서 재전송, 만료 재동기화, 버퍼 초과 복구, 하트비트를 보장합니다."""
    broker = StaffEventBroker(max_history=3, max_queue_size=2)
    e1 = broker.publish(
        "complaint.created",
        "DEMO-1",
        context_version=1,
        attempt=1,
        job_status="running",
        stage="민원 저장 완료",
    )
    e2 = broker.publish(
        "ai_job.stage_changed",
        "DEMO-1",
        context_version=1,
        attempt=1,
        job_status="running",
        stage="검색 중",
    )
    assert (e1.event_id, e2.event_id) == (1, 2)
    # 페이로드에는 민원 본문·초안 등 민감 필드가 들어가지 않습니다.
    assert set(e2.to_payload()) == {
        "eventId",
        "type",
        "complaintId",
        "contextVersion",
        "attempt",
        "jobStatus",
        "stage",
        "occurredAt",
    }

    # Last-Event-ID=1 재연결 시 2번 이벤트만 재전달합니다.
    replay_text = "".join(
        broker.subscribe(last_event_id=1, max_events=1, max_seconds=0.5)
    )
    replay_frames = _parse_sse_frames(replay_text)
    assert any(f.get("event") == "connected" for f in replay_frames)
    data_frames = [f for f in replay_frames if f.get("event") == "ai_job.stage_changed"]
    assert len(data_frames) == 1
    assert data_frames[0]["id"] == 2

    # 링 버퍼(max_history=3)를 밀어낸 뒤 오래된 커서(1)로 재연결하면 resync_required가 나옵니다.
    broker.publish("ai_job.stage_changed", "DEMO-1", stage="판정 중")
    broker.publish("ai_job.stage_changed", "DEMO-1", stage="초안 작성 중")
    broker.publish("ai_job.completed", "DEMO-1", job_status="succeeded", stage="완료")
    expired_text = "".join(
        broker.subscribe(last_event_id=1, max_events=1, max_seconds=0.5)
    )
    expired_frames = _parse_sse_frames(expired_text)
    assert any(
        f.get("event") == "resync_required" and f["data"]["reason"] == "cursor_expired"
        for f in expired_frames
    )

    # 서버 재기동 등으로 커서보다 큰 Last-Event-ID가 오면 resync_required가 나옵니다.
    future_text = "".join(
        broker.subscribe(last_event_id=999, max_events=1, max_seconds=0.5)
    )
    assert any(
        f.get("event") == "resync_required" for f in _parse_sse_frames(future_text)
    )

    # 유휴 구간에서는 연결 유지 하트비트 주석을 보냅니다.
    hb_text = "".join(
        broker.subscribe(
            last_event_id=broker.cursor, heartbeat_seconds=0.05, max_seconds=0.14
        )
    )
    assert any("heartbeat" in f.get("comment", "") for f in _parse_sse_frames(hb_text))
    assert broker.subscriber_count == 0


def test_staff_events_sse_permission_boundary_and_live_replay() -> None:
    """담당자 SSE 경로는 미인증·시민을 차단하고 커밋된 AI 작업 이벤트를 순서대로 전달합니다."""
    gate = threading.Event()
    calls: list[dict[str, Any]] = []

    def fake_iter(
        query: str,
        district: str | None,
        limit: int,
        rerank: bool,
        provider: str | None = None,
        include_staff_outputs: bool = True,
    ) -> Any:
        """진행 2단계 후 완료 결과를 내보내는 테스트용 응대 이터레이터입니다.

        Args:
            query: 민원 질의입니다.
            district: 선택 관할 구입니다.
            limit: 후보 개수입니다.
            rerank: 재정렬 여부입니다.
            provider: 선택 공급자입니다.
            include_staff_outputs: 담당자 산출물 생성 여부입니다.
        """
        calls.append({"query": query, "include_staff_outputs": include_staff_outputs})
        yield {
            "type": "progress",
            "key": "search",
            "label": "저장된 안내와 사례를 찾고 있어요",
        }
        gate.wait(timeout=2.0)
        yield {
            "type": "progress",
            "key": "review",
            "label": "찾은 자료를 살펴보고 있어요",
        }
        yield {
            "type": "done",
            "result": _fake_assist_payload(
                query=query,
                district=district or "흥덕구",
                outcome="department_suggestion",
                staff_draft_answer="현장 점검 후 안내드리겠습니다.",
            ),
        }

    app = create_app(
        Settings(secret_key="test-sse-secret", backend="memory", testing=True),
        assist_iter_fn=fake_iter,
        auto_start_ai=True,
    )
    app.config["SSE_HEARTBEAT_SECONDS"] = 0.05
    app.config["SSE_MAX_SECONDS"] = 0.4

    # 1. 미인증(401) 및 시민(403) 접근 차단(T04)
    anon = app.test_client()
    assert anon.get("/api/v1/staff/events").status_code == 401

    citizen = app.test_client()
    assert citizen.post("/api/v1/session", json={"role": "citizen"}).status_code == 200
    assert citizen.get("/api/v1/staff/events").status_code == 403

    # 2. 시민이 민원 등록 -> 백그라운드 AI 완료 -> 담당자 스냅샷 커서 및 SSE 재전송 확인
    created = citizen.post(
        "/api/v1/complaints",
        json={
            "title": "오송읍 가로등 점검 요청",
            "body": "오송읍 행정복지센터 앞 가로등이 밤새 켜지지 않습니다.",
            "district": "흥덕구",
            "category": "도로·교통",
            "visibility": "private",
        },
    )
    assert created.status_code == 201
    complaint_id = created.get_json()["id"]
    gate.set()
    service = app.extensions["complaint_service"]
    service.wait_for_jobs(timeout=3.0)

    staff = app.test_client()
    assert staff.post("/api/v1/session", json={"role": "staff"}).status_code == 200
    ws = staff.get("/api/v1/workspace").get_json()
    assert ws["eventCursor"] >= 3

    sse_res = staff.get(
        "/api/v1/staff/events",
        headers={"Last-Event-ID": "0"},
    )
    assert sse_res.status_code == 200
    assert sse_res.mimetype == "text/event-stream"
    assert "no-cache" in sse_res.headers["Cache-Control"]
    assert sse_res.headers["X-Accel-Buffering"] == "no"

    frames = _parse_sse_frames(sse_res.get_data(as_text=True))
    event_types = [f.get("event") for f in frames if f.get("event")]
    assert "connected" in event_types
    assert "complaint.created" in event_types
    assert "ai_job.stage_changed" in event_types
    assert "ai_job.completed" in event_types

    # 모든 데이터 프레임에 초안 본문·민원 원문이 유출되지 않음을 확인합니다.
    raw_sse = sse_res.get_data(as_text=True)
    assert "현장 점검 후 안내드리겠습니다." not in raw_sse
    assert "밤새 켜지지 않습니다" not in raw_sse
    assert complaint_id in raw_sse

    # 3. 취소된 작업의 늦은 AI 결과는 ai_job.completed 이벤트를 발행하지 않습니다.
    gate.clear()
    created2 = citizen.post(
        "/api/v1/complaints",
        json={
            "title": "늦은 결과 차단 검증 민원",
            "body": "가로등 고장 신고 후 취소했을 때 늦은 완료 이벤트가 발행되면 안 됩니다.",
            "district": "흥덕구",
            "category": "도로·교통",
            "visibility": "private",
        },
    )
    assert created2.status_code == 201
    c2 = created2.get_json()
    cursor_before_cancel = service.events.cursor
    cancel_res = staff.post(
        f"/api/v1/complaints/{c2['id']}/jobs/cancel",
        json={"version": c2["version"]},
    )
    assert cancel_res.status_code == 200
    gate.set()
    service.wait_for_jobs(timeout=3.0)

    missed, resync = service.events.replay_since(cursor_before_cancel)
    assert resync is False
    c2_types = [ev.event_type for ev in missed if ev.complaint_id == c2["id"]]
    assert "ai_job.cancelled" in c2_types
    assert "ai_job.completed" not in c2_types


def test_citizen_chat_endpoints_strip_staff_fields_and_skip_staff_prompts() -> None:
    """시민 챗봇 API는 미게시 초안·순화·내부 프롬프트를 제거하고 직원 단계 생성을 생략합니다."""
    recorded: list[dict[str, Any]] = []

    def fake_iter(
        query: str,
        district: str | None,
        limit: int,
        rerank: bool,
        provider: str | None = None,
        include_staff_outputs: bool = True,
    ) -> Any:
        """FAQ와 현장 조치 갈래를 반환하며 직원 전용 필드를 일부러 섞어 투영 차단을 시험합니다.

        Args:
            query: 시민 문의 문장입니다.
            district: 선택 관할 구입니다.
            limit: 검색 후보 수입니다.
            rerank: 재정렬 여부입니다.
            provider: 선택 공급자입니다.
            include_staff_outputs: 담당자 초안·순화 생성 여부입니다.
        """
        recorded.append(
            {
                "query": query,
                "district": district,
                "include_staff_outputs": include_staff_outputs,
            }
        )
        yield {"type": "progress", "key": "read", "label": "민원 내용을 읽고 있어요"}
        yield {
            "type": "progress",
            "key": "search",
            "label": "저장된 안내와 사례를 찾고 있어요",
        }
        # 혹시 내부 단계 키가 들어와도 시민 스트림에서 걸러져야 합니다.
        yield {
            "type": "progress",
            "key": "draft",
            "label": "담당자용 초안을 준비하고 있어요",
        }
        if "대형폐기물" in query:
            payload = _fake_assist_payload(
                query=query,
                district="흥덕구",
                outcome="faq_answer",
                answer="대형폐기물은 신고필증을 부착해 지정 장소에 배출해 주세요.",
                staff_draft_answer="절대 노출되면 안 되는 내부 초안",
            )
            payload["faq"][0]["sourceUrl"] = "https://toktalk.cheongju.go.kr/faq/1"
        else:
            payload = _fake_assist_payload(
                query=query,
                district="서원구",
                outcome="department_suggestion",
                answer="현장 확인이 필요합니다.",
                staff_draft_answer="담당자 전용 비공개 초안 텍스트",
            )
            payload["sanitize"] = {
                "sanitizedSummary": "담당자 전용 순화 요약",
                "legitimateRequests": ["가로등 수리"],
                "riskSignals": ["profanity_insult"],
                "humanProtectionReviewNeeded": True,
            }
        yield {"type": "done", "result": payload}

    app = create_app(
        Settings(secret_key="test-chat-secret", backend="memory", testing=True),
        assist_iter_fn=fake_iter,
        auto_start_ai=False,
    )
    client = app.test_client()

    # 미인증 차단
    assert (
        client.post(
            "/api/v1/citizen/chat", json={"message": "대형폐기물 안내"}
        ).status_code
        == 401
    )

    assert client.post("/api/v1/session", json={"role": "citizen"}).status_code == 200

    # 1. FAQ 스트림 호출 검증
    stream_res = client.post(
        "/api/v1/citizen/chat/stream",
        json={"message": "대형폐기물 배출 방법이 궁금해요"},
    )
    assert stream_res.status_code == 200
    assert stream_res.mimetype == "application/x-ndjson"
    events = [
        json.loads(line)
        for line in stream_res.get_data(as_text=True).splitlines()
        if line.strip()
    ]
    progress_keys = [e["key"] for e in events if e["type"] == "progress"]
    assert "search" in progress_keys
    assert "draft" not in progress_keys
    done = next(e["result"] for e in events if e["type"] == "done")
    assert done["outcome"] == "faq_answer"
    assert done["automaticTransfer"] is False
    assert done["handoffRequired"] is False
    assert done["faqSources"][0]["title"] == "대형폐기물 배출 안내"
    assert recorded[-1]["include_staff_outputs"] is False

    # 2. 현장 조치 동기 호출 검증 및 민감 필드 완전 배제 확인
    action_res = client.post(
        "/api/v1/citizen/chat",
        json={"message": "서원대 후문 가로등이 꺼졌어요"},
    )
    assert action_res.status_code == 200
    body = action_res.get_json()
    assert body["outcome"] == "department_suggestion"
    assert body["district"] == "서원구"
    assert body["handoffRequired"] is True
    assert body["automaticTransfer"] is False
    assert body["departmentHints"] == ["흥덕구 건설과"]
    assert body["inferredPlaceTitle"] == "오송읍 행정복지센터"
    for forbidden in ("staffDraft", "sanitize", "codex", "cases", "modelRaw"):
        assert forbidden not in body
    raw_json = json.dumps(body, ensure_ascii=False)
    assert "비공개 초안" not in raw_json
    assert "담당자 전용 순화" not in raw_json


def test_iter_assist_skips_prefix03_04_when_include_staff_outputs_false() -> None:
    """`include_staff_outputs=False`이면 비FAQ 판정에서도 PREFIX-03/04 LLM을 호출하지 않습니다."""
    llm_calls: list[str] = []

    def fake_search(
        query: str, district: str | None, limit: int, rerank: bool
    ) -> dict[str, Any]:
        """최소 검색 계약을 만족하는 사례 후보를 반환합니다.

        Args:
            query: 민원 질의입니다.
            district: 관할 구입니다.
            limit: 후보 수입니다.
            rerank: 재정렬 여부입니다.

        Returns:
            사례 1건과 부서 후보 1건이 담긴 검색 응답입니다.
        """
        return {
            "retrieval_only": True,
            "decision": "requires_gate",
            "results": {
                "faq_knowledge": {"hits": []},
                "routing_cases": {
                    "hits": [
                        {
                            "rank": 1,
                            "source_id": "CASE-77",
                            "title": "가로등 고장 수리 요청",
                            "excerpt": "현장 점검 완료",
                            "routing_eligible": True,
                            "department_id": "dept-road",
                            "department_name": "서원구 건설과",
                            "department_status": "verified",
                        }
                    ],
                    "department_candidates": [
                        {
                            "department_id": "dept-road",
                            "canonical_name": "서원구 건설과",
                            "district": "서원구",
                            "duty_status": "unverified",
                            "jurisdiction_status": "inferred_from_name",
                            "supporting_cases": [],
                        }
                    ],
                },
            },
        }

    def fake_llm(system: str, user: str) -> str:
        """호출된 프롬프트 단계를 기록하고 부서 추천 판정 JSON을 반환합니다.

        Args:
            system: 결합된 시스템 프롬프트입니다.
            user: 사용자 JSON입니다.

        Returns:
            부서 후보 추천 판정 JSON 문자열입니다.
        """
        llm_calls.append(system[:40])
        return json.dumps(
            {
                "scope": "in_scope",
                "intent": "action",
                "outcome": "department_suggestion",
                "reason_code": "department_candidate",
                "evidence_refs": [{"corpus": "routing", "source_id": "CASE-77"}],
                "department_ids": ["dept-road"],
                "sanitize_needed": True,
            },
            ensure_ascii=False,
        )

    events = list(
        iter_assist(
            "서원구 사창동 가로등 꺼져서 진짜 짜증나는데 빨리 고쳐주세요",
            "서원구",
            search_fn=fake_search,
            llm_fn=fake_llm,
            include_staff_outputs=False,
        )
    )
    done = next(e["result"] for e in events if e["type"] == "done")
    assert done["outcome"] == "department_suggestion"
    assert done["staff_draft"] is None
    assert done["sanitize"] is None
    # PREFIX-01 판정 1회만 호출되고 PREFIX-03/04는 완전히 생략됩니다.
    assert len(llm_calls) == 1
