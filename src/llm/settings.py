"""응대 LLM 공급자 설정을 환경변수와 `.env`에서 읽습니다."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

_LLM_ENV_KEYS = frozenset(
    {
        "COMPLAINT_LLM_PROVIDER",
        "COMPLAINT_LLM_MODEL",
        "COMPLAINT_LLM_REASONING_EFFORT",
        "COMPLAINT_CODEX_COMMAND",
        "OPENAI_API_KEY",
        "EXAONE_API_KEY",
        "EXAONE_URL",
        "EXAONE_MODEL",
        "EXAONE_REASONING_EFFORT",
        "EXAONE_MAX_TOKENS",
        "EXAONE_TEMPERATURE",
        "EXAONE_TOP_P",
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
# 공식 기본 추론 강도입니다. low·high·max만 허용합니다.
DEFAULT_EXAONE_REASONING_EFFORT = "max"
EXAONE_REASONING_EFFORTS = frozenset({"low", "high", "max"})
# max_tokens에는 내부 추론 토큰이 함께 계산되므로 판정 JSON보다 넉넉히 둡니다.
DEFAULT_EXAONE_MAX_TOKENS = 16384
# 공식 권장 1.0보다 낮춰 판정 JSON 형식을 안정적으로 유지합니다.
DEFAULT_EXAONE_TEMPERATURE = 0.7
DEFAULT_EXAONE_TOP_P = 0.95

LAB_PROVIDERS: tuple[str, ...] = ("", "exaone_api", "codex_cli", "openai_api")
"""검사기 선택 단추 순서입니다. 빈 문자열은 `.env` 기본 설정입니다."""
_PROVIDER_KEY_ENV = {"exaone_api": "EXAONE_API_KEY", "openai_api": "OPENAI_API_KEY"}


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

    `COMPLAINT_LLM_PROVIDER`로 `openai_api`(Responses API 키),
    `exaone_api`(EXAONE API 키) 또는 `codex_cli`(로그인된 Codex 실행 파일)를
    고릅니다. 이미 있는 운영체제 환경변수는 덮어쓰지 않습니다. 지원하는 LLM
    키 외의 값은 읽지 않으며, 값 뒤의 `#` 주석은 지우지 않으므로 주석은 별도
    줄에 둡니다. 파일이 없으면 아무 작업도 하지 않습니다.
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


def settings_for_provider(provider: str | None = None) -> dict[str, str | None]:
    """지정한 공급자 이름을 기준으로 사용할 설정을 구성합니다.

    `exaone_api`는 `EXAONE_REASONING_EFFORT`·`EXAONE_MAX_TOKENS`·
    `EXAONE_TEMPERATURE`·`EXAONE_TOP_P`를 함께 읽습니다. 추론 강도는
    `EXAONE_REASONING_EFFORT`가 우선이고, 비어 있으면 공통
    `COMPLAINT_LLM_REASONING_EFFORT`를 씁니다.

    Args:
        provider: 'exaone_api', 'openai_api', 'codex_cli', 'legacy' 중 하나이거나 None입니다.

    Returns:
        해당 공급자의 설정 딕셔너리입니다. 생략 시 프로세스 기본값을 읽습니다.
    """
    load_llm_env_file()
    prov = (provider or os.environ.get("COMPLAINT_LLM_PROVIDER") or "legacy").strip().lower()
    if prov == "openai_api":
        return luna_settings(
            prov,
            url=OPENAI_RESPONSES_URL,
            token=optional_env("OPENAI_API_KEY"),
            auth="bearer",
        )
    if prov == "exaone_api":
        configured_model = optional_env("COMPLAINT_LLM_MODEL")
        model = (
            optional_env("EXAONE_MODEL")
            or (
                configured_model
                if configured_model and configured_model != DEFAULT_LUNA_MODEL
                else DEFAULT_EXAONE_MODEL
            )
        )
        return {
            "provider": prov,
            "url": optional_env("EXAONE_URL") or EXAONE_COMPLETIONS_URL,
            "model": model,
            "token": optional_env("EXAONE_API_KEY"),
            "auth": "bearer",
            "reasoning_effort": (
                optional_env("EXAONE_REASONING_EFFORT")
                or optional_env("COMPLAINT_LLM_REASONING_EFFORT")
                or DEFAULT_EXAONE_REASONING_EFFORT
            ),
            "max_tokens": (
                optional_env("EXAONE_MAX_TOKENS") or str(DEFAULT_EXAONE_MAX_TOKENS)
            ),
            "temperature": (
                optional_env("EXAONE_TEMPERATURE") or str(DEFAULT_EXAONE_TEMPERATURE)
            ),
            "top_p": optional_env("EXAONE_TOP_P") or str(DEFAULT_EXAONE_TOP_P),
        }
    if prov == "codex_cli":
        return luna_settings(prov, url=None, token=None, auth="codex")
    if prov != "legacy":
        return {
            "provider": prov,
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
            "provider": prov,
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
            "provider": prov,
            "url": os.environ.get(
                "COMPLAINT_LLM_URL", "https://api.x.ai/v1/chat/completions"
            ),
            "model": os.environ.get("COMPLAINT_LLM_MODEL", "grok-4-fast"),
            "token": xai,
            "auth": "bearer",
            "reasoning_effort": None,
        }
    return {
        "provider": prov,
        "url": os.environ.get("COMPLAINT_LLM_URL"),
        "model": os.environ.get("COMPLAINT_LLM_MODEL"),
        "token": None,
        "auth": "token",
        "reasoning_effort": None,
    }


def llm_settings() -> dict[str, str | None]:
    """호출에 사용할 외부 LLM 공급자·주소·모델·인증 방식을 읽습니다.

    Returns:
        provider·url·model·token·auth·reasoning_effort를 담은 설정입니다.
        인증값이 없거나 공급자를 모를 때 token은 None입니다.
    """
    return settings_for_provider(None)


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
        return codex_available()
    return bool(settings["token"])


def codex_available() -> bool:
    """`COMPLAINT_CODEX_COMMAND`(기본 `codex`) 실행 파일이 PATH에 있는지 봅니다.

    Returns:
        실행 파일을 찾으면 True입니다.
    """
    return shutil.which(os.environ.get("COMPLAINT_CODEX_COMMAND", "codex")) is not None


def check_provider_availability(provider: str | None = None) -> tuple[bool, str]:
    """공급자를 지금 호출할 수 있는지와 불가 사유를 반환합니다.

    키·실행 파일의 존재만 봅니다. 키가 유효한지, 요청 한도가 남았는지는
    실제 호출 전까지 알 수 없습니다.

    Args:
        provider: `exaone_api`·`openai_api`·`codex_cli` 또는 빈 값(`.env` 기본 설정)입니다.

    Returns:
        `(사용 가능 여부, 불가 사유)`입니다. 사용 가능하면 사유는 빈 문자열입니다.
    """
    load_llm_env_file()
    prov = (provider or "").strip().lower()
    if not prov:
        ok = llm_configured()
        return ok, "" if ok else ".env에 호출 가능한 기본 LLM 설정이 없습니다."
    if prov in _PROVIDER_KEY_ENV:
        key = _PROVIDER_KEY_ENV[prov]
        ok = bool(optional_env(key))
        return ok, "" if ok else f".env에 {key}가 설정되지 않았습니다."
    if prov == "codex_cli":
        ok = codex_available()
        return ok, "" if ok else "Codex CLI가 설치되지 않았거나 PATH에 없습니다."
    return False, f"지원하지 않는 공급자입니다: {prov}"


def provider_availability_map() -> dict[str, dict[str, Any]]:
    """검사기에서 고를 수 있는 공급자 전체의 사용 가능 상태를 돌려줍니다.

    Returns:
        `LAB_PROVIDERS` 순서의 가용 상태·불가 사유·해석된 공급자 매핑입니다.
        빈 문자열 키(`.env` 기본 설정)도 실제로 가리키는 `resolved_provider`를 담습니다.
    """
    default_provider = llm_settings().get("provider") if llm_configured() else None
    result: dict[str, dict[str, Any]] = {}
    for prov in LAB_PROVIDERS:
        ok, reason = check_provider_availability(prov)
        result[prov] = {
            "available": ok,
            "reason": reason,
            "resolved_provider": default_provider if not prov else prov,
        }
    return result
