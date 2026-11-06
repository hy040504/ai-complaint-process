"""JSON HTTP 호출입니다.

검색 클라이언트와 LLM 공급자가 같은 전송 함수를 씁니다. 검색 색인이나
모델 프롬프트 로직은 넣지 않습니다.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


def http_json(
    url: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 180,
) -> Any:
    """JSON HTTP 요청을 보내고 본문을 해석합니다.

    Args:
        url: 호출 주소입니다.
        payload: POST 본문입니다. None이면 GET입니다.
        headers: 추가 헤더입니다.
        timeout: 초 단위 제한 시간입니다.

    Returns:
        JSON으로 해석한 응답입니다.

    Raises:
        ValueError: HTTP 오류나 연결 실패가 발생한 경우 발생합니다.
    """
    data = (
        json.dumps(payload, ensure_ascii=False).encode()
        if payload is not None
        else None
    )
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise ValueError(f"API {exc.code}: {message}") from None
    except urllib.error.URLError as exc:
        raise ValueError(f"연결 실패 ({url}): {exc.reason}") from None
