"""격리 SQLite와 Flask 클라이언트로 업무·공개 경계와 문서 계약을 검증합니다."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

from flask.testing import FlaskClient
from flask_openapi3.openapi import OpenAPI
from openapi_spec_validator import validate
import pytest

from src import create_app
from src.config import Settings
from src.errors import AppError
from src.models import Complaint, utcnow
from src.seed import seed_demo
from src.service import ComplaintService

BODY = {"title": "합성 보행로 점검 요청", "body": "[테스트] 보행로에 파손된 시설이 있어 안전 점검과 검토 결과 안내를 요청합니다.", "category": "도로·교통", "district": "흥덕구"}


@pytest.fixture
def app(tmp_path: Path) -> OpenAPI:
    """테스트별 임시 DB로 구성한 Flask 앱입니다."""
    return create_app(Settings(database=tmp_path / "test.sqlite3", secret_key="isolated-test-key", testing=True))


@pytest.fixture
def citizen(app: OpenAPI) -> FlaskClient:
    """서명 세션을 선택한 독립 시민 클라이언트입니다."""
    client = app.test_client()
    assert client.post("/api/v1/session", json={"role": "citizen"}).status_code == 200
    return client


@pytest.fixture
def staff(app: OpenAPI) -> FlaskClient:
    """시민과 쿠키를 공유하지 않는 담당자 클라이언트입니다."""
    client = app.test_client()
    assert client.post("/api/v1/session", json={"role": "staff"}).status_code == 200
    return client


def test_authentication_and_role_checks(app: OpenAPI, citizen: FlaskClient, staff: FlaskClient) -> None:
    """미인증·역할 위조·시민의 담당자 작업을 서버에서 거부합니다."""
    assert app.test_client().get("/api/v1/workspace").status_code == 401
    assert staff.post("/api/v1/complaints", json=BODY).status_code == 403
    row = citizen.post("/api/v1/complaints", json=BODY).json
    assert citizen.put(f"/api/v1/complaints/{row['id']}/draft", json={"version": 1, "text": "위조 답변", "reason": "불가"}).status_code == 403
    assert citizen.post("/api/v1/complaints", json={**BODY, "owner": "다른 작성자"}).status_code == 422


@pytest.mark.parametrize("changes", [{"title": " "}, {"title": "가" * 121}, {"body": "짧음"}, {"body": "가" * 2001}, {"district": "다른 구"}, {"visibility": "임의 공개"}])
def test_input_contract(citizen: FlaskClient, changes: dict[str, str]) -> None:
    """길이·공백·지역·공개 범위를 검사하며 잘린 원문을 저장하지 않습니다."""
    response = citizen.post("/api/v1/complaints", json={**BODY, **changes})
    assert response.status_code == 422
    assert response.json["code"] == "validation_error"
    assert not citizen.get("/api/v1/workspace").json["complaints"]


def test_idempotent_registration(citizen: FlaskClient) -> None:
    """같은 등록 키의 재전송은 같은 ID를 반환하고 다른 본문은 거부합니다."""
    headers = {"Idempotency-Key": "registration-1"}
    first = citizen.post("/api/v1/complaints", json=BODY, headers=headers)
    again = citizen.post("/api/v1/complaints", json=BODY, headers=headers)
    conflict = citizen.post("/api/v1/complaints", json={**BODY, "title": "다른 내용"}, headers=headers)
    assert first.status_code == again.status_code == 201
    assert first.json["id"] == again.json["id"]
    assert conflict.status_code == 409
    assert len(citizen.get("/api/v1/workspace").json["complaints"]) == 1


def test_draft_publish_followup_and_retraction(citizen: FlaskClient, staff: FlaskClient) -> None:
    """비공개 초안은 API에서도 제거되고 게시·정정·추가 문의 이력을 보존합니다."""
    row = citizen.post("/api/v1/complaints", json=BODY).json
    url = "/api/v1/complaints/" + row["id"]
    draft_text = "절대 시민 API에 포함하지 않을 내부 초안"
    draft = staff.put(url + "/draft", json={"version": 1, "text": draft_text, "reason": "내부 검토"})
    assert draft.status_code == 200
    for endpoint in (url, "/api/v1/workspace", "/api/v1/complaints"):
        public = citizen.get(endpoint)
        assert draft_text not in public.get_data(as_text=True)
        assert '"draft"' not in public.get_data(as_text=True)
        assert "담당자 초안 저장" not in public.get_data(as_text=True)
    published = staff.post(url + "/publish", json={"version": 2, "text": "시민에게 안내할 검토 완료 답변", "reason": "검토 완료"})
    assert published.status_code == 200
    assert published.json["published"]["origin"] == "staff"
    public = citizen.get(url).json
    assert public["status"] == "answered" and public["published"]["text"] == "시민에게 안내할 검토 완료 답변"
    assert citizen.put(url, json={**BODY, "version": 3}).status_code == 409
    followup = citizen.post(url + "/messages", json={"version": 3, "message": "추가 확인을 부탁드립니다."})
    assert followup.json["status"] == "under_review" and followup.json["published"]
    retracted = staff.post(url + "/retract", json={"version": 4, "reason": "정정 검토"})
    assert retracted.status_code == 200 and retracted.json["published"] is None
    assert retracted.json["versions"][-1]["kind"] == "게시 철회"
    assert citizen.put(url, json={**BODY, "version": 5}).status_code == 409


def test_original_edit_version_conflict_and_withdraw(citizen: FlaskClient, staff: FlaskClient) -> None:
    """원문 이전 버전과 철회 이력을 보존하고 오래된 갱신은 거부합니다."""
    row = citizen.post("/api/v1/complaints", json=BODY).json
    url = "/api/v1/complaints/" + row["id"]
    updated = citizen.put(url, json={**BODY, "version": 1, "title": "수정한 제목"})
    assert updated.status_code == 200 and updated.json["contextVersion"] == 2
    assert citizen.put(url, json={**BODY, "version": 1}).status_code == 409
    assert citizen.post(url + "/review", json={"version": "2"}).status_code == 422
    withdrawn = citizen.delete(url, json={"version": 2, "reason": "시연 철회"})
    assert withdrawn.status_code == 200
    assert citizen.get(url).status_code == staff.get(url).status_code == 404
    assert not citizen.get("/api/v1/complaints").json["complaints"]


def test_private_ownership_and_public_filters(app: OpenAPI, citizen: FlaskClient, staff: FlaskClient) -> None:
    """목록·건수·상세·변경에 동일한 공개 범위와 작성 권한을 적용합니다."""
    service: ComplaintService = app.extensions["complaint_service"]
    private = Complaint(id="OTHER-PRIVATE", owner="other", visibility="private", **BODY)
    service.repository.create(private, None, "")
    public = Complaint(id="OTHER-PUBLIC", owner="other", visibility="public", **BODY)
    service.repository.create(public, None, "")
    assert citizen.get("/api/v1/complaints/OTHER-PRIVATE").status_code == 404
    assert staff.get("/api/v1/complaints/OTHER-PRIVATE").status_code == 200
    assert citizen.get("/api/v1/complaints").json["total"] == 1
    assert citizen.get("/api/v1/complaints?mine=true").json["total"] == 0
    assert citizen.put("/api/v1/complaints/OTHER-PUBLIC", json={**BODY, "version": 1}).status_code == 403
    assert citizen.get("/api/v1/complaints?assign=mine").status_code == 403
    assert citizen.get("/api/v1/complaints?limit=101").status_code == 422


def test_pagination_and_seed(app: OpenAPI, staff: FlaskClient) -> None:
    """명시적 시연 초기화는 중복 생성하지 않고 페이지 필터를 지원합니다."""
    service: ComplaintService = app.extensions["complaint_service"]
    assert seed_demo(service.repository) == 24
    assert seed_demo(service.repository) == 0
    first = staff.get("/api/v1/complaints?limit=8&page=1").json
    second = staff.get("/api/v1/complaints?limit=8&page=2").json
    assert first["total"] == 24 and len(second["complaints"]) == 8
    assert {r["id"] for r in first["complaints"]}.isdisjoint({r["id"] for r in second["complaints"]})
    assert all("보행" in r["title"] for r in staff.get("/api/v1/complaints?q=보행").json["complaints"])


def test_ai_origin_and_no_late_overwrite(app: OpenAPI, citizen: FlaskClient, staff: FlaskClient) -> None:
    """AI 원본·편집 기원과 실행 맥락을 서버가 관리하며 늦은 후보를 차단합니다."""
    service: ComplaintService = app.extensions["complaint_service"]
    seed_demo(service.repository)
    url = "/api/v1/complaints/DEMO-2026-1048"
    row = staff.get(url).json
    changed = staff.put(url + "/draft", json={"version": row["version"], "text": "담당자가 보완한 원문", "reason": "시연 검토"}).json
    started = staff.post(url + "/jobs", json={"version": changed["version"]}).json
    published = staff.post(url + "/publish", json={"version": started["version"], "text": "담당자가 보완한 원문", "reason": "검토 후 게시"}).json
    assert published["published"]["origin"] == "ai_edited"
    assert published["job"]["status"] == "superseded"
    service.advance_jobs()
    stored = staff.get(url).json
    assert stored["draft"] == "담당자가 보완한 원문" and stored["aiOriginal"] == row["aiOriginal"]
    assert "aiOriginal" not in citizen.get(url).json


def test_job_completion_and_cancellation(app: OpenAPI, citizen: FlaskClient, staff: FlaskClient) -> None:
    """시연 이벤트는 DB에 저장하고 완료·취소가 민원 해결을 뜻하지 않습니다."""
    service: ComplaintService = app.extensions["complaint_service"]
    row = citizen.post("/api/v1/complaints", json=BODY).json
    url = "/api/v1/complaints/" + row["id"]
    started = staff.post(url + "/jobs", json={"version": 1}).json
    def age_job(current: Complaint) -> None:
        """실제 대기 없이 저장된 시작 시각만 앞당깁니다."""
        current.job.started_at = utcnow() - timedelta(seconds=10)
    service.repository.change(row["id"], started["version"], age_job)
    service.advance_jobs()
    finished = staff.get(url).json
    assert finished["job"]["status"] == "succeeded" and len(finished["job"]["events"]) == 6
    assert finished["draft"] == "" and finished["published"] is None and finished["status"] == "submitted"
    again = staff.post(url + "/jobs", json={"version": finished["version"]}).json
    cancelled = staff.post(url + "/jobs/cancel", json={"version": again["version"]})
    assert cancelled.json["job"]["status"] == "cancelled"
    assert cancelled.json["body"] == BODY["body"]


def test_atomic_conflict_and_rollback(app: OpenAPI, citizen: FlaskClient) -> None:
    """동시 저장은 하나만 성공하고 중간 오류는 전체 변경을 되돌립니다."""
    service: ComplaintService = app.extensions["complaint_service"]
    row = citizen.post("/api/v1/complaints", json=BODY).json
    def write(index: int) -> int:
        """같은 기대 버전으로 경쟁하는 저장 요청을 실행합니다."""
        try:
            service.repository.change(row["id"], 1, lambda value: setattr(value, "title", f"경쟁 {index}"))
            return 200
        except AppError as error:
            return error.status
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(write, [1, 2])) == [200, 409]
    latest = service.repository.get(row["id"])
    def fail(value: Complaint) -> None:
        """변경 후 예외로 트랜잭션 원복을 확인합니다."""
        value.title = "저장하면 안 됨"
        raise ValueError("검증 실패")
    with pytest.raises(ValueError):
        service.repository.change(row["id"], latest.version, fail)
    assert service.repository.get(row["id"]).title == latest.title


def test_persistence_across_app_instances(tmp_path: Path) -> None:
    """다른 앱 인스턴스에서도 같은 업무 DB의 민원을 조회합니다."""
    settings = Settings(database=tmp_path / "persistent.sqlite3", secret_key="persistent-key", testing=True)
    one = create_app(settings).test_client()
    one.post("/api/v1/session", json={"role": "citizen"})
    row = one.post("/api/v1/complaints", json=BODY).json
    two = create_app(settings).test_client()
    two.post("/api/v1/session", json={"role": "citizen"})
    assert two.get("/api/v1/complaints/" + row["id"]).json["title"] == BODY["title"]


def test_openapi_swagger_and_static_boundary(app: OpenAPI) -> None:
    """자동 문서의 스키마·오류 형식·Swagger 자산과 서버 소스 비노출을 확인합니다."""
    client = app.test_client()
    spec = client.get("/openapi/openapi.json").json
    validate(spec)
    assert "/api/v1/complaints/{complaint_id}/publish" in spec["paths"]
    assert spec["paths"]["/api/v1/complaints"]["post"]["responses"]["422"]["content"]["application/json"]["schema"]["$ref"].endswith("ErrorResponse")
    assert client.get("/docs", follow_redirects=True).status_code == 200
    assert client.get("/").status_code == 200
    assert client.get("/src/app.js").status_code == 200
    assert client.get("/src/app.py").status_code == 404
    assert client.get("/.web-data/session.key").status_code == 404


def test_cross_origin_malformed_json_and_disabled_demo(app: OpenAPI, citizen: FlaskClient, tmp_path: Path) -> None:
    """다른 출처의 쓰기와 손상 JSON을 거부하고 시연 계정 선택을 끌 수 있습니다."""
    assert citizen.post("/api/v1/complaints", json=BODY, headers={"Origin": "https://unrelated.example"}).status_code == 403
    response = citizen.post("/api/v1/complaints", data="{", content_type="application/json")
    assert response.status_code == 400 and response.json["code"] == "http_error"
    off = create_app(Settings(database=tmp_path / "off.sqlite3", secret_key="test", testing=True, demo_login=False)).test_client()
    assert off.post("/api/v1/session", json={"role": "staff"}).status_code == 403
