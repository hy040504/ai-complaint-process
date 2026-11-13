"""응대 LLM 공급자 설정을 환경변수와 `.env`에서 읽습니다."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

_LLM_ENV_KEYS = frozenset(
    {
        "COMPLAINT_LLM_PROVIDER",
        "COMPLAINT_LLM_MODEL",
        "COMPLAINT_LLM_REASONING_EFFORT",
        "COMPLAINT_CODEX_COMMAND",
        "OPENAI_API_KEY",
        "EXAONE_API_KEY",
        "COMPLAINT_LLM_URL",
        "COMPLAINT_LLM_TOKEN",
        "PUBLIC_LLM_TOKEN",
        "XAI_API_KEY",
    }
)
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
_LLM_ENV_LOADED = False
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_LUNA_MODEL = "gpt-6-luna"
DEFAULT_REASONING_EFFORT = "medium"

EXAONE_COMPLETIONS_URL = "https://api.exaone.ai/v1/chat/completions"
DEFAULT_EXAONE_MODEL = "k-exaone_v2.5"


def optional_env(name: str) -> str | None:
    """환경변수 값을 읽고 공백이면 없는 값으로 다룹니다.

    Args:
        name: 환경변수 이름입니다.

    Returns:
        비어 있지 않은 문자열 또는 None입니다.
    """
    value = os.environ.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def load_llm_env_file() -> None:
    """저장소 루트 `.env`의 LLM 설정만 프로세스 환경에 한 번 보완합니다.

    `COMPLAINT_LLM_PROVIDER`로 `openai_api`(Responses API 키) 또는
    `codex_cli`(로그인된 Codex 실행 파일)를 고릅니다. 이미 있는 운영체제
    환경변수는 덮어쓰지 않습니다. 지원하는 LLM 키 외의 값은 읽지 않습니다.
    파일이 없으면 아무 작업도 하지 않습니다.
    """
    global _LLM_ENV_LOADED
    if _LLM_ENV_LOADED:
        return
    _LLM_ENV_LOADED = True
    try:
        lines = _ENV_FILE.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    for line in lines:
        key, separator, value = line.strip().partition("=")
        if not separator or not key or key.startswith("#") or key not in _LLM_ENV_KEYS:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def luna_settings(
    provider: str,
    *,
    url: str | None,
    token: str | None,
    auth: str | None,
) -> dict[str, str | None]:
    """GPT-6 Luna 공급자가 공유하는 모델·추론 설정을 채웁니다.

    Args:
        provider: `openai_api` 또는 `codex_cli`입니다.
        url: Responses API 주소입니다. CLI 모드는 None입니다.
        token: API 키입니다. CLI 모드는 None입니다.
        auth: 인증 방식입니다.

    Returns:
        호출 어댑터가 읽는 설정 딕셔너리입니다.
    """
    return {
        "provider": provider,
        "url": url,
        "model": optional_env("COMPLAINT_LLM_MODEL") or DEFAULT_LUNA_MODEL,
        "token": token,
        "auth": auth,
        "reasoning_effort": (
            optional_env("COMPLAINT_LLM_REASONING_EFFORT") or DEFAULT_REASONING_EFFORT
        ),
    }


def llm_settings() -> dict[str, str | None]:
    """호출에 사용할 외부 LLM 공급자·주소·모델·인증 방식을 읽습니다.

    Returns:
        provider·url·model·token·auth·reasoning_effort를 담은 설정입니다.
        인증값이 없거나 공급자를 모를 때 token은 None입니다.
    """
    load_llm_env_file()
    provider = (os.environ.get("COMPLAINT_LLM_PROVIDER") or "legacy").strip().lower()
    if provider == "openai_api":
        return luna_settings(
            provider,
            url=OPENAI_RESPONSES_URL,
            token=optional_env("OPENAI_API_KEY"),
            auth="bearer",
        )
    if provider == "exaone_api":
        configured_model = optional_env("COMPLAINT_LLM_MODEL")
        model = (
            DEFAULT_EXAONE_MODEL
            if not configured_model or configured_model == DEFAULT_LUNA_MODEL
            else configured_model
        )
        return {
            "provider": provider,
            "url": os.environ.get("COMPLAINT_LLM_URL") or EXAONE_COMPLETIONS_URL,
            "model": model,
            "token": optional_env("EXAONE_API_KEY"),
            "auth": "bearer",
            "reasoning_effort": (
                optional_env("COMPLAINT_LLM_REASONING_EFFORT") or DEFAULT_REASONING_EFFORT
            ),
        }
    if provider == "codex_cli":
        return luna_settings(provider, url=None, token=None, auth="codex")
    if provider != "legacy":
        return {
            "provider": provider,
            "url": None,
            "model": None,
            "token": None,
            "auth": None,
            "reasoning_effort": None,
        }

    public = optional_env("COMPLAINT_LLM_TOKEN") or optional_env("PUBLIC_LLM_TOKEN")
    xai = optional_env("XAI_API_KEY")
    if public:
        return {
            "provider": provider,
            "url": os.environ.get(
                "COMPLAINT_LLM_URL",
                "https://llm.mib.dpdns.org/v1/chat/completions",
            ),
            "model": os.environ.get(
                "COMPLAINT_LLM_MODEL",
                "0bserverx__Qwen3.8-27B-Heretic-Abliterated-Uncensored-GGUF",
            ),
            "token": public,
            "auth": "token",
            "reasoning_effort": None,
        }
    if xai:
        return {
            "provider": provider,
            "url": os.environ.get(
                "COMPLAINT_LLM_URL", "https://api.x.ai/v1/chat/completions"
            ),
            "model": os.environ.get("COMPLAINT_LLM_MODEL", "grok-4-fast"),
            "token": xai,
            "auth": "bearer",
            "reasoning_effort": None,
        }
    return {
        "provider": provider,
        "url": os.environ.get("COMPLAINT_LLM_URL"),
        "model": os.environ.get("COMPLAINT_LLM_MODEL"),
        "token": None,
        "auth": "token",
        "reasoning_effort": None,
    }


def use_provider(provider: str) -> dict[str, str | None]:
    """프로세스 환경의 공급자만 바꿉니다. `.env` 파일은 쓰지 않습니다.

    Args:
        provider: `openai_api` 또는 `codex_cli` 등입니다.

    Returns:
        바꾼 뒤의 `llm_settings()` 결과입니다.
    """
    load_llm_env_file()
    os.environ["COMPLAINT_LLM_PROVIDER"] = provider.strip().lower()
    return llm_settings()


def llm_configured() -> bool:
    """응대에 사용할 LLM 공급자가 호출 가능한지 반환합니다.

    `openai_api`는 비어 있지 않은 `OPENAI_API_KEY`, `exaone_api`는
    `EXAONE_API_KEY`, `codex_cli`는 PATH의 Codex 실행 파일, `legacy`는
    기존 호환 토큰이 있을 때 True입니다.

    Returns:
        선택한 공급자를 지금 호출할 수 있으면 True입니다.
    """
    settings = llm_settings()
    if settings["provider"] == "codex_cli":
        return (
            shutil.which(os.environ.get("COMPLAINT_CODEX_COMMAND", "codex")) is not None
        )
    return bool(settings["token"])
