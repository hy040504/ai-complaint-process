"""헤더·요청 본문을 직접 지정하고 AI의 응답 본문을 그대로 출력합니다."""

from urllib.request import Request, urlopen

# 질문은 content 값에서 바꿉니다. 모델명은 현재 서버에 적재된 모델입니다.
body: str = """
{
  "model": "0bserverx__Qwen3.8-27B-Heretic-Abliterated-Uncensored-GGUF",
  "messages": [{"role": "user", "content": "안녕하세요. 간단히 자기소개해 주세요."}],
  "max_tokens": 128,
  "stream": false
}
"""

# 주소와 인증 헤더를 직접 넣어 대화 API에 POST 요청을 만듭니다.
request: Request = Request(
    url="https://llm.mib.dpdns.org/v1/chat/completions",
    headers={
        "token": "62eeaec6f299515b5df828695ffb80e02d99aa64fedece0bf23939e06505f988",
        "Content-Type": "application/json",
        "User-Agent": "LLMmanager-Python-Example/1.0",
    },
    data=body.encode("utf-8"),
    method="POST",
)

if __name__ == "__main__":
    # 응답 JSON에서 특정 필드를 추출하지 않고 본문 전체를 콘솔에 출력합니다.
    with urlopen(request, timeout=180) as response:
        print(response.read().decode("utf-8"))
