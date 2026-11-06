"""응대 검사기 웹이 민원 JSON을 검색·판정에 넘기는지 확인합니다."""

from pathlib import Path

from flask.testing import FlaskClient
from flask import Flask
import pytest

from src.lab_web import create_app
from src.lab_web.models import LabComplaint
from src.lab_web.service import compose_search_query, handle_complaint


def _assist_payload(query: str, district: str | None = None) -> dict:
    """검색 계약을 만족하는 합성 응대 결과입니다."""
    return {
        "query": query,
        "district": district,
        "outcome": "human_handoff",
        "reason_code": "llm_unavailable",
        "answer": "언어 모델이 없어 담당자 검토로 연결합니다.",
        "handoff_required": True,
        "automatic_transfer": False,
        "faq": [
            {
                "rank": 1,
                "source_id": "faq-1",
                "title": "대형폐기물 배출 방법",
                "excerpt": "읍면동에서 신고합니다.",
                "corpus": "faq",
            }
        ],
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


@pytest.fixture
def app() -> Flask:
    """합성 응대로 검사기 웹을 만듭니다."""

    def fake_assist(query: str, district: str | None, limit: int, rerank: bool) -> dict:
        assert limit == 5
        assert rerank is False
        return _assist_payload(query, district)

    return create_app(assist_fn=fake_assist)


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """검사기 웹 테스트 클라이언트입니다."""
    return app.test_client()


def _body() -> dict[str, object]:
    """유효한 민원 JSON입니다."""
    return {
        "title": "대형폐기물 배출",
        "category": "환경·청소",
        "district": "흥덕구",
        "body": "대형폐기물 배출 방법이 궁금합니다.",
    }


def test_search_query_omits_category() -> None:
    """검색 질의는 제목과 본문만 쓰고 분야는 빼습니다."""
    complaint = LabComplaint.model_validate(
        {
            "title": "청원구 식당부근 싸움",
            "category": "도로·교통",
            "district": "청원구",
            "body": "청원구 근처 식당에서 싸움남",
        }
    )
    query = compose_search_query(complaint)
    assert query == "청원구 식당부근 싸움\n\n청원구 근처 식당에서 싸움남"
    assert "도로·교통" not in query


def test_handle_complaint_runs_assist() -> None:
    """수신 후 검색 질의를 응대 함수에 넘깁니다."""
    seen: list[tuple[str, str | None, int, bool]] = []

    def fake(query: str, district: str | None, limit: int, rerank: bool) -> dict:
        seen.append((query, district, limit, rerank))
        return _assist_payload(query, district)

    result = handle_complaint(LabComplaint.model_validate(_body()), assist_fn=fake)
    assert seen == [
        (
            "대형폐기물 배출\n\n대형폐기물 배출 방법이 궁금합니다.",
            "흥덕구",
            5,
            False,
        )
    ]
    assert result.llm.sent is True
    assert result.llm.status == "completed"
    assert result.assist.outcome == "human_handoff"
    assert result.assist.retrieval.decision == "requires_gate"
    assert result.assist.automatic_transfer is False


def test_health(client: FlaskClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """검사기 웹 health는 검색·LLM 준비 여부를 담습니다."""
    monkeypatch.setattr("src.lab_web.app.search_available", lambda: True)
    monkeypatch.setattr("src.lab_web.app.llm_configured", lambda: False)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json == {
        "status": "ok",
        "service": "lab_web",
        "intake": True,
        "searchAvailable": True,
        "llmConfigured": False,
    }


def test_fields(client: FlaskClient) -> None:
    """작성 양식 목록을 줍니다."""
    response = client.get("/api/v1/lab/fields")
    assert response.status_code == 200
    assert "환경·청소" in response.json["categories"]
    assert "흥덕구" in response.json["districts"]


def test_index_is_lab_form(client: FlaskClient) -> None:
    """루트는 추출한 검사기 화면입니다."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "민원 보내기" in html
    assert "/#/citizen" not in html
    assert 'name="title"' in html


def test_accepts_complaint_json(client: FlaskClient) -> None:
    """민원 JSON을 받아 검색 질의와 판정을 돌려줍니다."""
    response = client.post("/api/v1/lab/complaints", json=_body())
    assert response.status_code == 200
    body = response.json
    assert body["accepted"] is True
    assert body["searchQuery"] == (
        "대형폐기물 배출\n\n대형폐기물 배출 방법이 궁금합니다."
    )
    assert "환경·청소" not in body["searchQuery"]
    assert body["llm"]["sent"] is True
    assert body["assist"]["outcome"] == "human_handoff"
    assert body["assist"]["retrieval"]["retrievalOnly"] is True
    assert body["assist"]["faq"][0]["title"] == "대형폐기물 배출 방법"


def test_blank_district_becomes_null(client: FlaskClient) -> None:
    """발생 지역을 비우면 검색 필터도 비웁니다."""
    payload = _body()
    payload["district"] = ""
    response = client.post("/api/v1/lab/complaints", json=payload)
    assert response.status_code == 200
    assert response.json["complaint"]["district"] is None
    assert response.json["assist"]["district"] is None


def test_rejects_unknown_field(client: FlaskClient) -> None:
    """계약 밖 필드는 거부합니다."""
    payload = _body()
    payload["owner"] = "citizen-demo"
    response = client.post("/api/v1/lab/complaints", json=payload)
    assert response.status_code == 422
    assert response.json["code"] == "invalid_request"


def test_rejects_short_body(client: FlaskClient) -> None:
    """상세 내용이 짧으면 422입니다."""
    payload = _body()
    payload["body"] = "짧음"
    response = client.post("/api/v1/lab/complaints", json=payload)
    assert response.status_code == 422
    assert "body" in response.json["fields"]


def test_launcher_cmd_uses_crlf() -> None:
    """Windows cmd.exe가 명령을 깨지 않도록 CRLF를 유지합니다."""
    path = Path(__file__).resolve().parents[2] / "검사기-시작.cmd"
    data = path.read_bytes()
    assert data.count(b"\n") > 0
    assert data.count(b"\r\n") == data.count(b"\n")


def test_rejects_non_object(client: FlaskClient) -> None:
    """배열 JSON은 받지 않습니다."""
    response = client.post("/api/v1/lab/complaints", json=["민원"])
    assert response.status_code == 400
    assert response.json["code"] == "invalid_json"
