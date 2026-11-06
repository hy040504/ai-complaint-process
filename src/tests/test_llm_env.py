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
