"""환경변수 인증으로 독립 LLM 예제의 응답 본문을 출력합니다."""

import os
from urllib.request import Request, urlopen

BODY: str = '\n{\n  "model": "0bserverx__Qwen3.8-27B-Heretic-Abliterated-Uncensored-GGUF",\n  "messages": [{"role": "user", "content": "안녕하세요. 간단히 자기소개해 주세요."}],\n  "max_tokens": 128,\n  "stream": false\n}\n'


def main() -> None:
    """시연 민원 데이터와 분리된 예제 질문을 외부 모델에 전송합니다.

    Raises:
        SystemExit: PUBLIC_LLM_TOKEN 환경변수가 없으면 발생합니다.
        OSError: 외부 서버 연결·HTTP 응답에 실패하면 발생합니다.
    """
    token = os.environ.get("PUBLIC_LLM_TOKEN")
    if not token:
        raise SystemExit("PUBLIC_LLM_TOKEN 환경변수에 발급받은 토큰을 지정해 주세요.")
    request = Request(
        url="https://llm.mib.dpdns.org/v1/chat/completions",
        headers={"token": token, "Content-Type": "application/json", "User-Agent": "LLMmanager-Python-Example/1.0"},
        data=BODY.encode("utf-8"),
        method="POST",
    )
    with urlopen(request, timeout=180) as response:
        print(response.read().decode("utf-8"))


if __name__ == "__main__":
    main()
