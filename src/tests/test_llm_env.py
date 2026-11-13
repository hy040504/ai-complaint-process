"""`.env`로 API·CLI LLM 공급자를 고를 수 있는지 확인합니다."""

from __future__ import annotations

from pathlib import Path

import src.llm.settings as settings


def test_env_file_selects_openai_api(tmp_path: Path, monkeypatch: object) -> None:
    """`.env`의 openai_api와 OPENAI_API_KEY를 프로세스 환경에 넣습니다."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "COMPLAINT_LLM_PROVIDER=openai_api\nOPENAI_API_KEY=sk-test-key\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "_ENV_FILE", env_file)
    settings._LLM_ENV_LOADED = False
    monkeypatch.delenv("COMPLAINT_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    loaded = settings.llm_settings()
    assert loaded["provider"] == "openai_api"
    assert loaded["token"] == "sk-test-key"
    assert settings.llm_configured() is True


def test_env_file_selects_exaone_api(tmp_path: Path, monkeypatch: object) -> None:
    """`.env`의 exaone_api와 EXAONE_API_KEY를 읽어 K-EXAONE-2.5로 구성합니다."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "COMPLAINT_LLM_PROVIDER=exaone_api\nEXAONE_API_KEY=exaone-secret-key\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "_ENV_FILE", env_file)
    settings._LLM_ENV_LOADED = False
    monkeypatch.delenv("COMPLAINT_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("EXAONE_API_KEY", raising=False)
    monkeypatch.delenv("COMPLAINT_LLM_MODEL", raising=False)

    loaded = settings.llm_settings()
    assert loaded["provider"] == "exaone_api"
    assert loaded["token"] == "exaone-secret-key"
    assert loaded["model"] == "k-exaone_v2.5"
    assert loaded["url"] == "https://api.exaone.ai/v1/chat/completions"
    assert loaded["auth"] == "bearer"
    assert settings.llm_configured() is True


def test_env_file_selects_codex_cli(tmp_path: Path, monkeypatch: object) -> None:
    """`.env`의 codex_cli와 실행 파일 이름을 읽습니다."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "COMPLAINT_LLM_PROVIDER=codex_cli\nCOMPLAINT_CODEX_COMMAND=C:/tools/codex.exe\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "_ENV_FILE", env_file)
    settings._LLM_ENV_LOADED = False
    monkeypatch.delenv("COMPLAINT_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("COMPLAINT_CODEX_COMMAND", raising=False)
    monkeypatch.setattr(settings.shutil, "which", lambda command: command)

    loaded = settings.llm_settings()
    assert loaded["provider"] == "codex_cli"
    assert loaded["auth"] == "codex"
    assert settings.llm_configured() is True


def test_env_file_reads_legacy_token(tmp_path: Path, monkeypatch: object) -> None:
    """`.env`의 기존 호환 토큰도 읽습니다."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "COMPLAINT_LLM_PROVIDER=legacy\nCOMPLAINT_LLM_TOKEN=legacy-secret\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "_ENV_FILE", env_file)
    settings._LLM_ENV_LOADED = False
    monkeypatch.delenv("COMPLAINT_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("COMPLAINT_LLM_TOKEN", raising=False)
    monkeypatch.delenv("PUBLIC_LLM_TOKEN", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)

    loaded = settings.llm_settings()
    assert loaded["provider"] == "legacy"
    assert loaded["token"] == "legacy-secret"
    assert settings.llm_configured() is True


def test_use_provider_overrides_process_env_only(
    tmp_path: Path, monkeypatch: object
) -> None:
    """공급자 전환은 프로세스 환경만 바꾸고 `.env` 파일은 쓰지 않습니다."""
    env_file = tmp_path / ".env"
    original = "COMPLAINT_LLM_PROVIDER=codex_cli\nOPENAI_API_KEY=\n"
    env_file.write_text(original, encoding="utf-8")
    monkeypatch.setattr(settings, "_ENV_FILE", env_file)
    settings._LLM_ENV_LOADED = False
    monkeypatch.setenv("COMPLAINT_LLM_PROVIDER", "codex_cli")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-compare-only")
    monkeypatch.setattr(settings.shutil, "which", lambda command: command)

    loaded = settings.use_provider("openai_api")
    assert loaded["provider"] == "openai_api"
    assert loaded["token"] == "sk-compare-only"
    assert env_file.read_text(encoding="utf-8") == original


def test_complete_exaone_result_with_mock(monkeypatch: object) -> None:
    """EXAONE Chat Completions 모의 응답과 토큰 사용량을 파싱합니다."""
    import src.llm.complete as complete

    def mock_http_json(url: str, body: dict, headers: dict) -> dict:
        assert url == "https://api.exaone.ai/v1/chat/completions"
        assert headers["Authorization"] == "Bearer test-exaone-key"
        assert body["model"] == "k-exaone_v2.5"
        assert body["reasoning_effort"] == "high"
        assert body["max_tokens"] == 16384
        assert body["temperature"] == 0.7
        assert body["top_p"] == 0.95
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": '```json\n{"scope":"in_scope","outcome":"department_suggestion"}\n```',
                        "reasoning_content": "나무 쓰러짐 민원이므로 서원구 조치 필요",
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 45,
                "total_tokens": 165,
                "reasoning_tokens": 30,
            },
        }

    monkeypatch.setattr(complete, "http_json", mock_http_json)

    exaone_cfg = {
        "provider": "exaone_api",
        "url": "https://api.exaone.ai/v1/chat/completions",
        "model": "k-exaone_v2.5",
        "token": "test-exaone-key",
        "auth": "bearer",
        "reasoning_effort": "high",
        "max_tokens": "16384",
        "temperature": "0.7",
        "top_p": "0.95",
    }
    result = complete.complete_result("시스템지시", "사용자입력", settings=exaone_cfg)
    assert result.text == '{"scope":"in_scope","outcome":"department_suggestion"}'
    assert result.usage is not None
    assert result.usage["input_tokens"] == 120
    assert result.usage["output_tokens"] == 45
    assert result.usage.get("reasoning_tokens") == 30


def test_provider_availability_map(monkeypatch: object) -> None:
    """공급자별 API 키 유무에 따른 사용 가능 여부를 매핑합니다."""
    monkeypatch.setenv("EXAONE_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(settings.shutil, "which", lambda cmd: None)

    avail = settings.provider_availability_map()
    assert avail["exaone_api"]["available"] is True
    assert avail["exaone_api"]["reason"] == ""
    assert avail["openai_api"]["available"] is False
    assert "OPENAI_API_KEY" in avail["openai_api"]["reason"]
    assert avail["codex_cli"]["available"] is False
    assert "Codex CLI" in avail["codex_cli"]["reason"]


def test_pipeline_resolve_chat_with_exaone_provider(monkeypatch: object) -> None:
    """`exaone_api` 공급자 키 유무에 따라 파이프라인 활성 여부와 chat 선택이 동작합니다."""
    from src.assist import pipeline

    # llm_fn=None이면 환경 키가 있어도 LLM을 비활성화합니다.
    monkeypatch.setenv("EXAONE_API_KEY", "exaone-test-token")
    assert pipeline.llm_enabled(None, "exaone_api") is False
    assert pipeline.resolve_chat(None, "exaone_api", [None]) is None

    # USE_ENV_LLM일 때 EXAONE_API_KEY 유무에 따라 활성 여부와 chat 생성을 결정합니다.
    monkeypatch.delenv("EXAONE_API_KEY", raising=False)
    monkeypatch.setattr(settings, "load_llm_env_file", lambda: {})
    assert pipeline.llm_enabled(pipeline.USE_ENV_LLM, "exaone_api") is False
    assert pipeline.resolve_chat(pipeline.USE_ENV_LLM, "exaone_api", [None]) is None

    monkeypatch.setenv("EXAONE_API_KEY", "exaone-test-token")
    assert pipeline.llm_enabled(pipeline.USE_ENV_LLM, "exaone_api") is True
    chat = pipeline.resolve_chat(pipeline.USE_ENV_LLM, "exaone_api", [None])
    assert callable(chat)


def test_strip_code_fence_handles_json_and_plain_text() -> None:
    """코드 울타리 제거 도우미가 마크다운 JSON 울타리만 안전하게 벗겨 냅니다."""
    from src.llm import complete

    assert complete.strip_code_fence('```json\n{"ok": true}\n```') == '{"ok": true}'
    assert complete.strip_code_fence('```\n{"ok": true}\n```') == '{"ok": true}'
    assert complete.strip_code_fence('{"ok": true}') == '{"ok": true}'


