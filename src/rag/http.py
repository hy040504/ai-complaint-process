"""JSON HTTP 호출입니다.

검색 클라이언트와 LLM 공급자가 같은 전송 함수를 씁니다. 검색 색인이나
모델 프롬프트 로직은 넣지 않습니다.
"""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from email.message import Message
from typing import Any

_DEFAULT_MAX_429_RETRIES = 2
_MIN_RETRY_DELAY = 0.3
_MAX_RETRY_DELAY = 8.0


def _retry_delay_seconds(
    headers: Message[str, str] | Mapping[str, str] | None, attempt: int
) -> float | None:
    """HTTP 429 응답 헤더를 읽어 재시도 대기 시간(초)을 계산합니다.

    EXAONE API 등 `retry-after-ms`, `retry-after`, `x-day-rate-limit-remaining`
    헤더를 우선 확인하고, 헤더가 없으면 지수 백오프와 지터를 적용합니다.

    Args:
        headers: HTTP 오류 응답 헤더입니다.
        attempt: 0부터 시작하는 현재 재시도 횟수입니다.

    Returns:
        대기할 초 단위 시간입니다. 일일 한도(`x-day-rate-limit-remaining: 0`)가
        모두 소진된 경우 즉시 중단하도록 None을 반환합니다.
    """
    if headers is not None:
        day_remaining = headers.get("x-day-rate-limit-remaining")
        if day_remaining is not None and str(day_remaining).strip() == "0":
            return None
        for key, scale in (("retry-after-ms", 0.001), ("retry-after", 1.0)):
            raw = headers.get(key)
            if raw is None:
                continue
            try:
                parsed = float(str(raw).strip()) * scale
            except ValueError:
                continue
            if parsed >= 0:
                return min(_MAX_RETRY_DELAY, max(_MIN_RETRY_DELAY, parsed + 0.05))
    # 헤더가 없으면 일시적인 동시 요청 폭주(600) 해소를 기다리며 점진 대기합니다.
    backoff = (0.8 * float(2**attempt)) + random.uniform(0.15, 0.55)
    return float(min(_MAX_RETRY_DELAY, max(_MIN_RETRY_DELAY, backoff)))


def http_json(
    url: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 180,
    *,
    max_429_retries: int = _DEFAULT_MAX_429_RETRIES,
) -> Any:
    """JSON HTTP 요청을 보내고 본문을 해석합니다.

    HTTP 429 응답이 오면 일일 한도 고갈이 아닌 한 `retry-after-ms`/`retry-after`
    또는 짧은 지수 백오프로 최대 `max_429_retries`회 재시도합니다.

    Args:
        url: 호출 주소입니다.
        payload: POST 본문입니다. None이면 GET입니다.
        headers: 추가 헤더입니다.
        timeout: 초 단위 제한 시간입니다.
        max_429_retries: HTTP 429 응답 시 추가 재시도 최대 횟수입니다.

    Returns:
        JSON으로 해석한 응답입니다.

    Raises:
        ValueError: HTTP 오류, 요청 시간 초과, 연결 실패가 발생한 경우 발생합니다.
    """
    data = (
        json.dumps(payload, ensure_ascii=False).encode()
        if payload is not None
        else None
    )
    req_headers = {"Content-Type": "application/json", **(headers or {})}
    attempts = max(0, max_429_retries) + 1
    for attempt in range(attempts):
        request = urllib.request.Request(url, data=data, headers=req_headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429 and attempt < attempts - 1:
                delay = _retry_delay_seconds(exc.headers, attempt)
                if delay is not None:
                    time.sleep(delay)
                    continue
            raise ValueError(f"API {exc.code}: {message}") from None
        except TimeoutError:
            raise ValueError(f"요청 시간 초과 ({url}, {timeout}초)") from None
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise ValueError(f"요청 시간 초과 ({url}, {timeout}초)") from None
            raise ValueError(f"연결 실패 ({url}): {exc.reason}") from None
    raise ValueError(f"API 요청 재시도 한도를 초과했습니다 ({url})")
