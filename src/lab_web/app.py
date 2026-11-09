"""응대 검사기 전용 Flask 앱입니다.

정적 화면과 민원 JSON 수신 API를 제공합니다. 수신 후 `src.assist`가
검색 API를 먼저 호출하고 판정합니다. 테스트 기록은 `.rag-cache/lab-runs`
JSON이며 민원 CRUD 테이블에는 쓰지 않습니다. 스트림 경로는 진행 안내
NDJSON을 먼저 보냅니다.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context
from pydantic import BaseModel, ValidationError

from src.assist import llm_configured, search_available
from src.lab_web.models import (
    ErrorBody,
    LabAcceptResult,
    LabClearResult,
    LabComplaint,
    LabFields,
    LabHealth,
    LabRunList,
    LabRunRecord,
    LabRunSummary,
)
from src.lab_web.runs import (
    clear_runs,
    default_runs_dir,
    list_runs,
    load_run,
    run_summary,
    save_run,
)
from src.lab_web.service import AssistFn, handle_complaint, iter_complaint

STATIC_DIR = Path(__file__).resolve().parent / "static"

_FIELD_LABELS = {
    "title": "제목",
    "category": "민원 분야",
    "district": "발생 지역",
    "body": "상세 내용",
}


def _json(model: BaseModel, status: int = 200) -> Response:
    """검증된 모델을 camelCase JSON으로 돌려줍니다.

    Args:
        model: Pydantic 모델입니다.
        status: HTTP 상태 코드입니다.

    Returns:
        Flask JSON 응답입니다.
    """
    response = jsonify(model.model_dump(mode="json", by_alias=True))
    response.status_code = status
    return response


def _invalid(error: ValidationError) -> Response:
    """잘못된 필드 이름만 안내하고 입력 원문은 넣지 않습니다.

    Args:
        error: Pydantic 검증 오류입니다.

    Returns:
        422 JSON 응답입니다.
    """
    names: list[str] = []
    for item in error.errors():
        loc = item.get("loc") or ()
        if loc:
            names.append(str(loc[0]))
    unique = list(dict.fromkeys(names))
    labels = [_FIELD_LABELS.get(name, name) for name in unique] or ["요청"]
    return _json(
        ErrorBody(
            code="invalid_request",
            message=f"{', '.join(labels)}을(를) 확인해 주세요.",
            fields=unique,
        ),
        422,
    )


def _runs_dir(app: Flask) -> Path:
    """앱 설정의 기록 폴더를 돌려줍니다.

    Args:
        app: 검사기 Flask 앱입니다.

    Returns:
        JSON 기록을 두는 경로입니다.
    """
    return Path(app.config["LAB_RUNS_DIR"])


def create_app(
    assist_fn: AssistFn | None = None,
    runs_dir: Path | None = None,
) -> Flask:
    """검사기 웹 앱을 만듭니다.

    Args:
        assist_fn: 테스트용 응대 함수입니다. 생략하면 `run_web_assist`입니다.
        runs_dir: 테스트 기록 JSON 폴더입니다. 생략하면 `.rag-cache/lab-runs`입니다.

    Returns:
        정적 파일과 수신 API를 가진 Flask 앱입니다.
    """
    app = Flask(
        __name__,
        static_folder=str(STATIC_DIR),
        static_url_path="",
    )
    app.config["LAB_ASSIST_FN"] = assist_fn
    app.config["LAB_RUNS_DIR"] = Path(runs_dir) if runs_dir else default_runs_dir()

    @app.get("/")
    def index() -> Response:
        """검사기 작성 화면을 돌려줍니다."""
        return send_from_directory(STATIC_DIR, "index.html")

    @app.get("/api/v1/health")
    def health() -> Response:
        """검사기 웹이 켜져 있는지 확인합니다."""
        return _json(
            LabHealth(
                search_available=search_available(),
                llm_configured=llm_configured(),
            )
        )

    @app.get("/api/v1/lab/fields")
    def fields() -> Response:
        """작성 양식의 분야·지역 목록을 줍니다."""
        return _json(LabFields())

    def _parse_complaint() -> LabComplaint | Response:
        """요청 JSON을 민원으로 검증합니다. 실패면 오류 응답입니다."""
        raw = request.get_json(silent=True)
        if not isinstance(raw, dict):
            return _json(
                ErrorBody(
                    code="invalid_json",
                    message="민원 내용은 JSON 객체로 보내 주세요.",
                ),
                400,
            )
        try:
            return LabComplaint.model_validate(raw)
        except ValidationError as error:
            return _invalid(error)

    def _finish_run(
        complaint: LabComplaint, result: LabAcceptResult
    ) -> LabAcceptResult | Response:
        """응대 결과를 기록 파일에 남기고 run 요약을 붙입니다."""
        received = result.model_dump(mode="json", by_alias=True)
        try:
            record = save_run(
                _runs_dir(app),
                payload=complaint.model_dump(mode="json", by_alias=True),
                received=received,
            )
        except (OSError, ValueError) as exc:
            return _json(
                ErrorBody(code="run_save_failed", message=str(exc)[:200]),
                503,
            )
        result.run = LabRunSummary.model_validate(run_summary(record))
        return result

    @app.post("/api/v1/lab/complaints")
    def create_complaint() -> Response:
        """민원 JSON을 받아 검색 후 판정합니다.

        검색 질의는 제목과 상세 내용입니다. `district`는 구 필터입니다.
        민원 분야는 검색 질의에 넣지 않습니다. 민원 CRUD에는 저장하지 않습니다.
        성공하면 `.rag-cache/lab-runs` JSON에 기록을 남깁니다.

        Returns:
            수신 확인과 응대 결과 JSON 또는 오류 응답입니다.
        """
        parsed = _parse_complaint()
        if isinstance(parsed, Response):
            return parsed
        complaint = parsed
        try:
            result = handle_complaint(
                complaint,
                assist_fn=app.config.get("LAB_ASSIST_FN"),
            )
        except (OSError, ValueError, TypeError) as exc:
            return _json(
                ErrorBody(code="assist_failed", message=str(exc)[:200]),
                503,
            )
        finished = _finish_run(complaint, result)
        if isinstance(finished, Response):
            return finished
        return _json(finished)

    @app.post("/api/v1/lab/complaints/stream")
    def create_complaint_stream() -> Response:
        """민원 JSON을 받아 진행 안내 NDJSON 뒤에 판정 결과를 붙입니다.

        민원 CRUD에는 저장하지 않습니다. 성공한 `done` 결과는
        `.rag-cache/lab-runs`에도 남깁니다.

        Returns:
            진행 상태와 최종 결과를 스트리밍하는 NDJSON 응답입니다.
        """
        parsed = _parse_complaint()
        if isinstance(parsed, Response):
            return parsed
        complaint = parsed
        assist_fn = app.config.get("LAB_ASSIST_FN")

        def generate() -> Iterator[str]:
            try:
                for event in iter_complaint(complaint, assist_fn=assist_fn):
                    if event.get("type") != "done":
                        yield json.dumps(event, ensure_ascii=False) + "\n"
                        continue
                    result = event["result"]
                    if not isinstance(result, LabAcceptResult):
                        raise TypeError("검사기 스트림 결과가 올바르지 않습니다.")
                    finished = _finish_run(complaint, result)
                    if isinstance(finished, Response):
                        body = finished.get_json(silent=True) or {}
                        yield json.dumps(
                            {
                                "type": "error",
                                "message": body.get("message")
                                or "기록을 저장하지 못했습니다.",
                            },
                            ensure_ascii=False,
                        ) + "\n"
                        return
                    payload = finished.model_dump(mode="json", by_alias=True)
                    yield json.dumps(
                        {"type": "done", "result": payload},
                        ensure_ascii=False,
                    ) + "\n"
            except (OSError, ValueError, TypeError) as exc:
                yield json.dumps(
                    {"type": "error", "message": str(exc)[:200]},
                    ensure_ascii=False,
                ) + "\n"

        return Response(
            stream_with_context(generate()),
            mimetype="application/x-ndjson",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/api/v1/lab/runs")
    def get_runs() -> Response:
        """파일로 남긴 테스트 기록 목록을 줍니다.

        Returns:
            기록 요약 목록 JSON 응답입니다.
        """
        items = [
            LabRunSummary.model_validate(item) for item in list_runs(_runs_dir(app))
        ]
        return _json(LabRunList(items=items))

    @app.get("/api/v1/lab/runs/<run_id>")
    def get_run(run_id: str) -> Response:
        """기록 한 건의 민원과 응대 결과를 줍니다.

        Args:
            run_id: 파일 이름에 쓰는 기록 ID입니다.

        Returns:
            기록 한 건의 민원과 응대 결과 JSON 또는 404/500 응답입니다.
        """
        record = load_run(_runs_dir(app), run_id)
        if record is None:
            return _json(
                ErrorBody(code="run_not_found", message="기록을 찾지 못했습니다."),
                404,
            )
        try:
            return _json(LabRunRecord.model_validate(record))
        except ValidationError:
            return _json(
                ErrorBody(code="run_invalid", message="기록 파일이 깨져 있습니다."),
                500,
            )

    @app.delete("/api/v1/lab/runs")
    def delete_runs() -> Response:
        """파일로 남긴 테스트 기록을 모두 지웁니다.

        Returns:
            삭제한 기록 건수 JSON 응답입니다.
        """
        removed = clear_runs(_runs_dir(app))
        return _json(LabClearResult(removed=removed))

    return app
