"""응대 검사기 API가 세션 없이 동작하고 민원 CRUD와 분리되는지 확인합니다."""

import json
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


def test_assist_does_not_need_session(app: OpenAPI, monkeypatch: object) -> None:
    """검사기는 시연 세션 없이 호출할 수 있습니다."""
    monkeypatch.setattr(
        "src.complaints.api.run_web_assist", lambda *args: _payload(args[0])
    )
    client = app.test_client()
    response = client.post(
        "/api/v1/assist", json={"query": "대형폐기물 배출 방법을 알고 싶어요."}
    )
    assert response.status_code == 200
    body = response.json
    assert body["outcome"] == "human_handoff"
    assert body["automaticTransfer"] is False
    assert body["retrieval"]["retrievalOnly"] is True
    assert body["retrieval"]["decision"] == "requires_gate"


def test_assist_examples_and_health_flags(app: OpenAPI, monkeypatch: object) -> None:
    """예시 목록과 검색·LLM 설정 플래그를 반환합니다."""
    monkeypatch.setattr("src.complaints.api.search_available", lambda: True)
    monkeypatch.setattr("src.complaints.api.llm_configured", lambda: False)
    client: FlaskClient = app.test_client()
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
    app: OpenAPI, monkeypatch: object
) -> None:
    """흐름 응답은 짧은 진행 안내 뒤에 최종 결과를 붙입니다."""

    def fake_iter(
        query: str,
        district: str | None,
        limit: int,
        rerank: bool,
        provider: str | None = None,
    ) -> Iterator[dict]:
        yield {
            "type": "progress",
            "key": "search",
            "label": "저장된 안내와 사례를 찾고 있어요",
        }
        yield {"type": "done", "result": _payload(query)}

    monkeypatch.setattr("src.complaints.api.iter_web_assist", fake_iter)
    client: FlaskClient = app.test_client()
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
