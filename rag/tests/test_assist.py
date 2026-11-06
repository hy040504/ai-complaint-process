"""검색 근거와 어긋난 판정은 담당자 검토로 떨어지는지 검증합니다."""

from pathlib import Path
from types import SimpleNamespace

from rag.assist import (
    complete_chat,
    llm_configured,
    llm_settings,
    parse_json_object,
    run_assist,
    validate_decision,
)
from src.llm.complete import (
    codex_tool_instruction,
    complete_result,
    resolve_codex_argv,
    usage_from_openai,
)


def sample_search() -> dict:
    """FAQ 1건과 유효 부서 후보 1건을 가진 검색 응답입니다."""
    return {
        "retrieval_only": True,
        "decision": "requires_gate",
        "elapsed_ms": 1,
        "pipeline": "test",
        "results": {
            "faq_knowledge": {
                "hits": [
                    {
                        "rank": 1,
                        "source_id": "faq-1",
                        "title": "대형폐기물 배출 방법",
                        "source_url": "https://example.test/faq-1",
                        "evidence": {
                            "detail": {
                                "target": "대형폐기물 배출자",
                                "processing_period": "평일 1~2일",
                                "warnings": "무단배출 과태료",
                                "main_content": "읍면동에서 신고 후 배출합니다.",
                            }
                        },
                    }
                ]
            },
            "routing_cases": {
                "hits": [
                    {
                        "rank": 1,
                        "source_id": "case-1",
                        "title": "가로등 고장",
                        "source_url": "https://example.test/case-1",
                        "routing_eligible": True,
                        "department_status": "current",
                        "evidence": {"summary": "가로등 수리 요청"},
                        "department": {
                            "department_id": "dept-1",
                            "canonical_name": "도로시설과",
                            "district": "흥덕구",
                            "duty_status": "unverified",
                            "jurisdiction_status": "inferred_from_name",
                        },
                    }
                ],
                "department_candidates": [
                    {
                        "department_id": "dept-1",
                        "canonical_name": "도로시설과",
                        "district": "흥덕구",
                        "duty_status": "unverified",
                        "jurisdiction_status": "inferred_from_name",
                        "supporting_cases": [{"source_id": "case-1"}],
                        "automatic_transfer": False,
                    }
                ],
            },
        },
    }


def test_parse_json_from_fence() -> None:
    """코드 울타리 안의 JSON 객체를 읽습니다."""
    value = parse_json_object('설명\n```json\n{"scope":"in_scope"}\n```\n')
    assert value["scope"] == "in_scope"


def test_unknown_evidence_is_rejected() -> None:
    """검색에 없는 출처는 근거에서 제거합니다."""
    decision, failures = validate_decision(
        {
            "scope": "in_scope",
            "intent": "information",
            "outcome": "faq_answer",
            "reason_code": "ok",
            "evidence_refs": [{"corpus": "faq", "source_id": "missing"}],
            "department_ids": [],
        },
        sample_search(),
    )
    assert decision["outcome"] == "human_handoff"
    assert any("검색에 없는 근거" in item for item in failures)


def test_action_cannot_close_with_faq() -> None:
    """실제 조치 요청은 FAQ 안내만으로 종결하지 않습니다."""
    decision, failures = validate_decision(
        {
            "scope": "in_scope",
            "intent": "action",
            "outcome": "faq_answer",
            "reason_code": "ok",
            "evidence_refs": [{"corpus": "faq", "source_id": "faq-1"}],
            "department_ids": ["dept-1"],
        },
        sample_search(),
    )
    assert decision["outcome"] == "department_suggestion"
    assert decision["reason_code"] == "action_required"
    assert failures


def test_review_required_department_is_not_selectable() -> None:
    """후보 목록에 없는 부서 ID는 추천에서 제외합니다."""
    decision, failures = validate_decision(
        {
            "scope": "in_scope",
            "intent": "action",
            "outcome": "department_suggestion",
            "reason_code": "action_required",
            "evidence_refs": [{"corpus": "routing", "source_id": "case-1"}],
            "department_ids": ["other-dept"],
        },
        sample_search(),
    )
    assert decision["department_ids"] == []
    assert decision["outcome"] == "human_handoff"
    assert any("유효 후보가 아닌 부서" in item for item in failures)


def test_mixed_request_goes_to_handoff() -> None:
    """복합 요청은 담당자 검토로 연결합니다."""
    decision, _failures = validate_decision(
        {
            "scope": "in_scope",
            "intent": "mixed",
            "outcome": "faq_answer",
            "reason_code": "ok",
            "evidence_refs": [{"corpus": "faq", "source_id": "faq-1"}],
            "department_ids": ["dept-1"],
        },
        sample_search(),
    )
    assert decision["outcome"] == "human_handoff"
    assert decision["reason_code"] == "mixed_request"


def test_progress_callback_uses_short_labels() -> None:
    """진행 안내는 파이프라인 전체가 아니라 짧은 작업 설명만 넘깁니다."""
    seen: list[tuple[str, str]] = []

    def on_progress(key: str, label: str) -> None:
        seen.append((key, label))

    run_assist(
        "대형폐기물 배출 방법을 알고 싶어요.",
        search_fn=lambda query, district, limit, rerank: sample_search(),
        llm_fn=None,
        on_progress=on_progress,
    )
    keys = [item[0] for item in seen]
    assert keys[:3] == ["read", "search", "review"]
    assert "write" not in keys
    assert all("판정" not in label and "LLM" not in label for _, label in seen)


def test_empty_query_reports_llm_off_when_disabled() -> None:
    """빈 질의는 검색 없이 인계하고, 끈 모델은 설정됨으로 표시하지 않습니다."""
    result = run_assist("", search_fn=lambda *args: sample_search(), llm_fn=None)
    assert result["outcome"] == "human_handoff"
    assert result["reason_code"] == "condition_unclear"
    assert result["llm_configured"] is False


def test_run_assist_without_llm_keeps_retrieval() -> None:
    """LLM이 없어도 검색 근거는 남기고 담당자 검토로 떨어집니다."""
    result = run_assist(
        "대형폐기물 배출 방법을 알고 싶어요.",
        search_fn=lambda query, district, limit, rerank: sample_search(),
        llm_fn=None,
    )
    assert result["outcome"] == "human_handoff"
    assert result["reason_code"] == "llm_unavailable"
    assert result["automatic_transfer"] is False
    assert result["faq"][0]["source_id"] == "faq-1"
    assert (
        "대상" in result["faq"][0]["excerpt"] or "배출자" in result["faq"][0]["excerpt"]
    )
    assert result["codex"][0]["role"] == "decision"
    assert result["codex"][0]["sent"] is False
    assert "faq_candidates" in result["codex"][0]["user"]


def test_run_assist_faq_path_uses_second_call() -> None:
    """허용된 FAQ 판정은 두 번째 호출로 안내 문장을 만듭니다."""
    calls: list[str] = []

    def llm(system: str, user: str) -> str:
        calls.append(system)
        if "판정기" in system:
            return (
                '{"scope":"in_scope","intent":"information","outcome":"faq_answer",'
                '"reason_code":"ok","evidence_refs":[{"corpus":"faq","source_id":"faq-1"}],'
                '"department_ids":[]}'
            )
        return "대형폐기물 배출자는 읍면동에서 신고한 뒤 배출합니다. 처리기간은 평일 1~2일이며 무단배출 시 과태료가 있습니다."

    result = run_assist(
        "대형폐기물 배출 방법을 알고 싶어요.",
        search_fn=lambda query, district, limit, rerank: sample_search(),
        llm_fn=llm,
    )
    assert result["outcome"] == "faq_answer"
    assert result["handoff_required"] is False
    assert "과태료" in (result["answer"] or "")
    assert len(calls) == 2
    assert [item["role"] for item in result["codex"]] == ["decision", "faq_answer"]
    assert result["codex"][0]["system"] == "PREFIX-00 + PREFIX-01"
    assert result["codex"][1]["user"]["faq"][0]["source_id"] == "faq-1"


def test_search_contract_failure() -> None:
    """검색 전용 계약이 깨지면 검색 실패로 인계합니다."""
    result = run_assist(
        "질문입니다",
        search_fn=lambda *args: {"retrieval_only": False, "decision": "answer"},
        llm_fn=lambda s, u: "{}",
    )
    assert result["reason_code"] == "search_failed"
    assert result["faq"] == []


def test_openai_api_provider_uses_responses_and_medium_effort(
    monkeypatch: object,
) -> None:
    """OpenAI API 선택은 Responses API와 medium 추론 설정을 사용합니다."""
    monkeypatch.setenv("COMPLAINT_LLM_PROVIDER", "openai_api")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    captured: dict = {}

    def fake_http(url: str, payload: dict, headers: dict) -> dict:
        captured.update({"url": url, "payload": payload, "headers": headers})
        return {"output_text": "응답"}

    monkeypatch.setattr("src.llm.complete.http_json", fake_http)
    assert llm_configured() is True
    assert complete_chat("시스템", "사용자") == "응답"
    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["payload"]["model"] == "gpt-6-luna"
    assert captured["payload"]["reasoning"] == {"effort": "medium"}
    assert captured["headers"]["Authorization"] == "Bearer test-key"


def test_openai_usage_reads_cached_tokens(monkeypatch: object) -> None:
    """Responses usage의 cached_tokens를 본문과 함께 읽습니다."""
    monkeypatch.setenv("COMPLAINT_LLM_PROVIDER", "openai_api")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_http(url: str, payload: dict, headers: dict) -> dict:
        return {
            "output_text": "응답",
            "usage": {
                "input_tokens": 2000,
                "output_tokens": 80,
                "input_tokens_details": {"cached_tokens": 1500},
            },
        }

    monkeypatch.setattr("src.llm.complete.http_json", fake_http)
    result = complete_result("시스템", "사용자")
    assert result.text == "응답"
    assert result.usage == {
        "input_tokens": 2000,
        "output_tokens": 80,
        "cached_tokens": 1500,
    }
    assert usage_from_openai({"usage": {}}) == {
        "input_tokens": None,
        "output_tokens": None,
        "cached_tokens": None,
    }


def test_codex_cli_provider_uses_read_only_temp_workspace(monkeypatch: object) -> None:
    """Codex CLI 선택은 모델·추론 설정과 읽기 전용 격리를 전달합니다."""
    monkeypatch.setenv("COMPLAINT_LLM_PROVIDER", "codex_cli")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-reach-codex")
    captured: dict = {}
    monkeypatch.setattr(
        "src.llm.settings.shutil.which", lambda command: "C:/tools/codex.exe"
    )
    monkeypatch.setattr(
        "src.llm.complete.shutil.which", lambda command: "C:/tools/codex.exe"
    )

    def fake_run(args: list[str], **kwargs: object) -> SimpleNamespace:
        captured.update({"args": args, **kwargs})
        return SimpleNamespace(returncode=0, stdout="CLI 응답\n", stderr="")

    monkeypatch.setattr("src.llm.complete.subprocess.run", fake_run)
    assert llm_configured() is True
    assert complete_chat("시스템", "사용자") == "CLI 응답"
    assert "--sandbox" in captured["args"]
    assert captured["args"][captured["args"].index("--sandbox") + 1] == "read-only"
    assert "gpt-6-luna" in captured["args"]
    assert 'model_reasoning_effort="medium"' in captured["args"]
    assert captured["args"][-1] == "-"
    assert captured["args"][0] == "C:/tools/codex.exe"
    assert "search_complaint_rag" in captured["input"]
    joined = " ".join(captured["args"])
    assert "src.llm.rag_mcp" in joined
    assert '["-u", "-m", "src.llm.rag_mcp"]' in joined
    assert "--ignore-user-config" in captured["args"]
    assert "[시스템 지시]" in captured["input"]
    assert "사용자" in captured["input"]
    assert "OPENAI_API_KEY" not in captured["env"]


def test_codex_tool_instruction_lists_only_developer_tools() -> None:
    """허용 목록에 있는 도구 이름만 래퍼 문장에 넣습니다."""
    text = codex_tool_instruction(("search_faq",))
    assert "search_faq" in text
    assert "search_complaint_rag에는" not in text
    assert "그 밖의 도구" in text


def test_windows_codex_cmd_wrapper_runs_node_entry(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Windows npm `codex.cmd`는 cmd.exe 대신 node와 진입 스크립트를 씁니다."""
    npm_bin = tmp_path / "npm"
    script = npm_bin / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
    script.parent.mkdir(parents=True)
    script.write_text("/* test */\n", encoding="utf-8")
    wrapper = npm_bin / "codex.cmd"
    wrapper.write_text("@echo off\n", encoding="utf-8")
    node = tmp_path / "node.exe"
    node.write_text("", encoding="utf-8")

    def fake_which(name: str) -> str | None:
        if name == "codex":
            return str(wrapper)
        if name == "node":
            return str(node)
        return None

    monkeypatch.setattr("src.llm.complete.os.name", "nt")
    monkeypatch.setattr("src.llm.complete.shutil.which", fake_which)
    argv = resolve_codex_argv("codex")
    assert argv == [str(node), str(script)]

    captured: dict = {}

    def fake_run(args: list[str], **kwargs: object) -> SimpleNamespace:
        captured["args"] = args
        return SimpleNamespace(returncode=0, stdout="CLI 응답\n", stderr="")

    monkeypatch.setenv("COMPLAINT_LLM_PROVIDER", "codex_cli")
    monkeypatch.setattr("src.llm.complete.subprocess.run", fake_run)
    assert complete_chat("시스템", "사용자") == "CLI 응답"
    assert captured["args"][0] == str(node)
    assert captured["args"][1] == str(script)
    assert captured["args"][-1] == "-"


def test_unknown_provider_is_not_configured(monkeypatch: object) -> None:
    """지원하지 않는 공급자 값은 호출 가능 상태로 표시하지 않습니다."""
    monkeypatch.setenv("COMPLAINT_LLM_PROVIDER", "unknown")
    settings = llm_settings()
    assert settings["provider"] == "unknown"
    assert llm_configured() is False


def test_empty_openai_api_key_is_not_configured(monkeypatch: object) -> None:
    """OPENAI_API_KEY가 공백이면 openai_api를 호출 가능으로 표시하지 않습니다."""
    monkeypatch.setenv("COMPLAINT_LLM_PROVIDER", "openai_api")
    monkeypatch.setenv("OPENAI_API_KEY", "   ")
    assert llm_settings()["token"] is None
    assert llm_configured() is False
