"""응대 검사기 API가 담당자 로그인으로만 동작하고 민원 CRUD와 분리되는지 확인합니다."""

import json
import os
from collections.abc import Iterator

from flask_openapi3.openapi import OpenAPI
from flask.testing import FlaskClient
import pytest

from src import create_app
from src.complaints.config import Settings
from src.complaints.models import AssistResponse


@pytest.fixture
def app() -> OpenAPI:
    """검사기 테스트용 메모리 저장소 앱입니다."""
    return create_app(
        Settings(
            secret_key="isolated-test-key",
            backend="memory",
            testing=True,
        )
    )


STAFF_PW = os.environ.get("COMPLAINT_STAFF_INIT_PASSWORD", "cheongju-staff-2026!")
CITIZEN_PW = os.environ.get("COMPLAINT_CITIZEN_INIT_PASSWORD", "cheongju-citizen-2026!")


def _login(client: FlaskClient, site: str, login_id: str, password: str) -> FlaskClient:
    """지정 사이트 헤더로 로그인한 클라이언트를 돌려줍니다."""
    res = client.post(
        "/api/v1/auth/login",
        json={"loginId": login_id, "password": password},
        headers={"X-Cheongju-Site": site},
    )
    assert res.status_code == 200
    return client


def _staff(app: OpenAPI) -> FlaskClient:
    """담당자로 로그인한 테스트 클라이언트입니다."""
    return _login(app.test_client(), "staff", "staff_admin", STAFF_PW)


def _payload(query: str = "대형폐기물 배출 방법을 알고 싶어요.") -> dict:
    """검사기 응답 계약을 만족하는 합성 결과입니다."""
    return {
        "query": query,
        "district": None,
        "outcome": "human_handoff",
        "reason_code": "llm_unavailable",
        "answer": "언어 모델이 없어 담당자 검토로 연결합니다.",
        "handoff_required": True,
        "automatic_transfer": False,
        "faq": [],
        "cases": [],
        "departments": [],
        "decision": {
            "scope": "uncertain",
            "intent": "unclear",
            "outcome": "human_handoff",
            "reason_code": "llm_unavailable",
            "evidence_refs": [],
            "department_ids": [],
            "model_raw": None,
        },
        "policy_failures": ["LLM 토큰 없음"],
        "stages": [{"name": "검색", "elapsed_ms": 1.0, "ok": True}],
        "llm_configured": False,
        "retrieval": {
            "retrieval_only": True,
            "decision": "requires_gate",
            "elapsed_ms": 1.0,
            "pipeline": "test",
        },
    }


def test_assist_schema_accepts_pipeline_result() -> None:
    """파이프라인 딕셔너리가 응답 모델과 맞습니다."""
    AssistResponse.model_validate(_payload())


def test_assist_requires_staff_login(
    app: OpenAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """검사기 API는 비로그인·시민에게 막히고 담당자에게만 열립니다(CASE-129)."""
    monkeypatch.setattr(
        "src.complaints.api.run_web_assist", lambda *args: _payload(args[0])
    )
    body = {"query": "대형폐기물 배출 방법을 알고 싶어요."}
    anon = app.test_client()
    for method, path in (
        ("get", "/api/v1/assist/fields"),
        ("get", "/api/v1/assist/examples"),
        ("post", "/api/v1/assist"),
        ("post", "/api/v1/assist/stream"),
    ):
        res = getattr(anon, method)(
            path, **({"json": body} if method == "post" else {})
        )
        assert res.status_code == 401, path
    citizen = _login(app.test_client(), "citizen", "citizen_01", CITIZEN_PW)
    assert citizen.post("/api/v1/assist", json=body).status_code == 403
    assert citizen.get("/api/v1/assist/examples").status_code == 403

    client = _staff(app)
    response = client.post(
        "/api/v1/assist", json={"query": "대형폐기물 배출 방법을 알고 싶어요."}
    )
    assert response.status_code == 200
    body = response.json  # type: ignore[assignment]
    assert body["outcome"] == "human_handoff"
    assert body["automaticTransfer"] is False  # type: ignore[comparison-overlap]
    assert body["retrieval"]["retrievalOnly"] is True
    assert body["retrieval"]["decision"] == "requires_gate"


def test_assist_examples_and_health_flags(
    app: OpenAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """예시 목록과 검색·LLM 설정 플래그를 반환합니다."""
    monkeypatch.setattr("src.complaints.api.search_available", lambda: True)
    monkeypatch.setattr("src.complaints.api.llm_configured", lambda: False)
    client: FlaskClient = _staff(app)
    health = client.get("/api/v1/health").json
    assert health["storage"] == "memory"
    assert health["aiConnected"] is False
    assert health["assistSearch"] is True
    assert health["assistLlm"] is False
    examples = client.get("/api/v1/assist/examples").json["examples"]
    assert {item["id"] for item in examples} >= {
        "faq",
        "action",
        "routing",
        "handoff",
        "district",
    }
    spec = client.get("/openapi/openapi.json").json
    assert "/api/v1/assist" in spec["paths"]
    assert "/api/v1/assist/stream" in spec["paths"]


def test_assist_stream_sends_progress_then_result(
    app: OpenAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """흐름 응답은 짧은 진행 안내 뒤에 최종 결과를 붙입니다."""

    def fake_iter(
        query: str, district: str | None, limit: int, rerank: bool
    ) -> Iterator[dict]:
        """스트림 진행 이벤트와 최종 done 페이로드를 생성하는 모의 이터레이터입니다."""
        yield {
            "type": "progress",
            "key": "search",
            "label": "저장된 안내와 사례를 찾고 있어요",
        }
        yield {"type": "done", "result": _payload(query)}

    monkeypatch.setattr("src.complaints.api.iter_web_assist", fake_iter)
    client: FlaskClient = _staff(app)
    response = client.post(
        "/api/v1/assist/stream",
        json={"query": "대형폐기물 배출 방법을 알고 싶어요."},
    )
    assert response.status_code == 200
    lines = [line for line in response.get_data(as_text=True).splitlines() if line]
    first = json.loads(lines[0])
    last = json.loads(lines[-1])
    assert first["type"] == "progress"
    assert first["key"] == "search"
    assert last["type"] == "done"
    assert last["result"]["automaticTransfer"] is False
    assert last["result"]["retrieval"]["decision"] == "requires_gate"


def test_assist_runs_are_rate_limited_per_staff_account(
    app: OpenAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """같은 담당자 계정은 10분에 20회까지만 검사기를 실행하고 초과분은 429입니다."""
    monkeypatch.setattr(
        "src.complaints.api.run_web_assist", lambda *args: _payload(args[0])
    )
    client = _staff(app)
    body = {"query": "대형폐기물 배출 방법을 알고 싶어요."}
    for _ in range(20):
        assert client.post("/api/v1/assist", json=body).status_code == 200
    blocked = client.post("/api/v1/assist", json=body)
    assert blocked.status_code == 429
    assert blocked.json["code"] == "rate_limited"
    assert client.post("/api/v1/assist/stream", json=body).status_code == 429
    # 조회용 엔드포인트는 횟수에 포함하지 않는다.
    assert client.get("/api/v1/assist/examples").status_code == 200
