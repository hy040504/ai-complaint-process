"""응대 검사기 웹이 민원 JSON만 받고 업무 DB에 쓰지 않는지 확인합니다."""

from flask.testing import FlaskClient
from flask import Flask
import pytest

from src.lab_web import create_app
from src.lab_web.models import LabComplaint
from src.lab_web.service import accept_complaint, compose_query


@pytest.fixture
def app() -> Flask:
    """검사기 웹 앱입니다."""
    return create_app()


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


def test_compose_query_joins_fields() -> None:
    """분야·제목·본문을 한 질의로 붙입니다."""
    complaint = LabComplaint.model_validate(_body())
    assert compose_query(complaint) == (
        "분야: 환경·청소\n\n대형폐기물 배출\n\n대형폐기물 배출 방법이 궁금합니다."
    )


def test_accept_does_not_mark_llm_sent() -> None:
    """수신 단계에서는 언어 모델을 호출하지 않습니다."""
    result = accept_complaint(LabComplaint.model_validate(_body()))
    assert result.accepted is True
    assert result.llm.sent is False
    assert result.llm.status == "accepted"


def test_health(client: FlaskClient) -> None:
    """검사기 웹 health는 lab_web 서비스입니다."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json == {
        "status": "ok",
        "service": "lab_web",
        "intake": True,
        "llmSent": False,
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
    assert 'name="category"' in html
    assert 'name="district"' in html
    assert 'name="body"' in html


def test_accepts_complaint_json(client: FlaskClient) -> None:
    """민원 JSON을 받아 모델 봉투를 돌려줍니다."""
    response = client.post("/api/v1/lab/complaints", json=_body())
    assert response.status_code == 202
    body = response.json
    assert body["accepted"] is True
    assert body["complaint"]["title"] == "대형폐기물 배출"
    assert body["complaint"]["category"] == "환경·청소"
    assert body["complaint"]["district"] == "흥덕구"
    assert body["complaint"]["body"] == "대형폐기물 배출 방법이 궁금합니다."
    assert body["llm"]["sent"] is False
    assert "분야: 환경·청소" in body["llm"]["query"]


def test_blank_district_becomes_null(client: FlaskClient) -> None:
    """발생 지역을 비우면 null입니다."""
    payload = _body()
    payload["district"] = ""
    response = client.post("/api/v1/lab/complaints", json=payload)
    assert response.status_code == 202
    assert response.json["complaint"]["district"] is None


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


def test_rejects_non_object(client: FlaskClient) -> None:
    """배열 JSON은 받지 않습니다."""
    response = client.post("/api/v1/lab/complaints", json=["민원"])
    assert response.status_code == 400
    assert response.json["code"] == "invalid_json"
