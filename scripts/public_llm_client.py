"""토큰 헤더로 공개 LLM API에 접속하는 Python 3.10 이상 대화 예제입니다."""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Literal, TypedDict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_BASE_URL: str = "https://llm.mib.dpdns.org/v1"
TIMEOUT_SECONDS: float = 180.0


class Message(TypedDict):
    """대화 API에 전달할 역할과 메시지 본문입니다."""

    role: Literal["system", "user", "assistant"]
    content: str


def request_json(
    path: str,
    token: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """인증된 GET 또는 POST 요청을 보내고 JSON 객체를 반환합니다.

    Args:
        path: 기본 주소 뒤에 붙일 API 경로입니다.
        token: 서버에 설정한 인증 토큰입니다.
        payload: POST 요청 본문입니다. 생략하면 GET으로 요청합니다.

    Returns:
        서버가 반환한 JSON 객체입니다.

    Raises:
        RuntimeError: 인증·HTTP·연결 오류 또는 잘못된 JSON 응답입니다.
        TypeError: 서버가 JSON 객체가 아닌 자료형을 반환했습니다.
    """
    # 토큰은 URL이나 본문 대신 서버가 요구하는 token 헤더에 넣습니다.
    headers: dict[str, str] = {
        "token": token,
        "Accept": "application/json",
        # 기본 Python urllib 사용자 에이전트의 엣지 차단을 피합니다.
        "User-Agent": "LLMmanager-Python-Example/1.0",
    }
    body: bytes | None = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    request = Request(
        url=f"{API_BASE_URL}{path}",
        data=body,
        headers=headers,
        method="POST" if payload is not None else "GET",
    )
    try:
        # HTTPS 인증서를 검증하며, 응답 연결은 with 블록에서 닫습니다.
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            result: Any = json.load(response)
    except HTTPError as exc:
        status: int = exc.code
        exc.close()
        if status == 401:
            raise RuntimeError("인증 실패: LLM_API_TOKEN 값을 확인하세요.") from None
        raise RuntimeError(f"서버가 HTTP {status} 오류를 반환했습니다.") from None
    except (URLError, TimeoutError):
        raise RuntimeError("서버 연결에 실패했거나 응답 대기 시간이 초과됐습니다.") from None
    except ValueError:
        raise RuntimeError("서버 응답이 올바른 JSON이 아닙니다.") from None

    if not isinstance(result, dict):
        raise TypeError("서버 응답이 JSON 객체가 아닙니다.")
    return result


def get_model_id(token: str) -> str:
    """현재 공개된 첫 번째 모델의 ID를 조회합니다.

    Args:
        token: 서버에 설정한 인증 토큰입니다.

    Returns:
        대화 요청의 model 필드에 넣을 모델 ID입니다.

    Raises:
        RuntimeError: 조회 실패 또는 사용할 모델이 없는 경우입니다.
        TypeError: 서버가 JSON 객체가 아닌 자료형을 반환했습니다.
    """
    result = request_json("/models", token)
    models = result.get("data")
    if isinstance(models, list) and models and isinstance(models[0], dict):
        model_id = models[0].get("id")
        if isinstance(model_id, str) and model_id:
            return model_id
    raise RuntimeError("현재 사용할 수 있는 모델이 없습니다.")


def send_message(token: str, model_id: str, messages: list[Message]) -> str:
    """대화 기록을 전송하고 완성된 답변을 받습니다.

    Args:
        token: 서버에 설정한 인증 토큰입니다.
        model_id: 모델 목록에서 조회한 ID입니다.
        messages: 시스템 지시·이전 대화·이번 질문을 순서대로 담은 기록입니다.

    Returns:
        모델이 생성한 답변 텍스트입니다.

    Raises:
        RuntimeError: 요청 실패 또는 답변 형식이 잘못된 경우입니다.
        TypeError: 서버가 JSON 객체가 아닌 자료형을 반환했습니다.
    """
    result = request_json(
        "/chat/completions",
        token,
        {
            "model": model_id,
            "messages": messages,
            "max_tokens": 512,
            # False이면 전체 답변이 완성된 뒤 JSON 한 건으로 받습니다.
            "stream": False,
        },
    )
    try:
        content: Any = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("응답에서 모델의 답변을 찾을 수 없습니다.") from None
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("모델이 텍스트 답변을 반환하지 않았습니다.")
    return content


def main() -> int:
    """환경변수의 토큰으로 접속해 종료 입력까지 대화를 이어갑니다."""
    token: str = os.environ.get("LLM_API_TOKEN", "").strip()
    if not token:
        print("LLM_API_TOKEN 환경변수를 먼저 설정하세요.", file=sys.stderr)
        return 1

    try:
        model_id: str = get_model_id(token)
        print(f"연결 모델: {model_id}\n종료: /exit 또는 /quit")
        history: list[Message] = [
            {"role": "system", "content": "한국어로 명확하게 답변해 주세요."},
        ]
        while True:
            question: str = input("나: ").strip()
            if question in {"/exit", "/quit"}:
                return 0
            if not question:
                continue
            # 성공한 요청만 기록에 추가해, 실패한 질문이 다음 요청에 섞이지 않게 합니다.
            user_message: Message = {"role": "user", "content": question}
            answer: str = send_message(token, model_id, [*history, user_message])
            history.extend([user_message, {"role": "assistant", "content": answer}])
            print(f"AI: {answer}\n")
    except (EOFError, KeyboardInterrupt):
        print("\n대화를 종료합니다.")
        return 0
    except (RuntimeError, TypeError) as exc:
        # 오류에 토큰·요청 헤더·대화 원문을 포함하지 않습니다.
        print(f"오류: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
