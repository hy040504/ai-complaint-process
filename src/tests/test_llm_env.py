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
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": '{"scope":"in_scope","outcome":"department_suggestion"}',
                        "reasoning_content": "나무 쓰러짐 민원이므로 서원구 조치 필요",
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 45,
                "total_tokens": 165,
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
    }
    result = complete.complete_result("시스템지시", "사용자입력", settings=exaone_cfg)
    assert result.text == '{"scope":"in_scope","outcome":"department_suggestion"}'
    assert result.usage is not None
    assert result.usage["input_tokens"] == 120
    assert result.usage["output_tokens"] == 45
