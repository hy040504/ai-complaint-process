"""`search_complaint_rag` 하나만 제공하는 MCP stdio 서버입니다.

Codex 자식 프로세스로 실행합니다. 표준 입출력의 Content-Length 프레임만
읽고, 민원 문장을 검색 API로 넘깁니다.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from src.llm.rag_tool import RAG_TOOL_NAME, RAG_TOOL_USAGE, search_complaint_rag

PROTOCOL = "2024-11-05"


def tool_spec() -> dict[str, Any]:
    """Codex에 공개할 도구 스키마를 만듭니다.

    Returns:
        MCP `tools/list`에 넣을 도구 정의입니다.
    """
    return {
        "name": RAG_TOOL_NAME,
        "description": RAG_TOOL_USAGE,
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "query": {"type": "string", "description": "민원 원문"},
                "district": {
                    "type": "string",
                    "description": "상당구, 서원구, 흥덕구, 청원구 중 하나. 없으면 생략",
                },
            },
            "required": ["query"],
        },
        "annotations": {"readOnlyHint": True},
    }


def dispatch(message: dict[str, Any]) -> dict[str, Any] | None:
    """MCP 요청 하나를 처리합니다.

    Args:
        message: JSON-RPC 요청입니다.

    Returns:
        응답 객체입니다. 알림이면 None입니다.
    """
    method = message.get("method")
    request_id = message.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        params = message.get("params") or {}
        version = params.get("protocolVersion") or PROTOCOL
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "complaint-rag", "version": "1"},
            },
        }
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": [tool_spec()]},
        }
    if method == "tools/call":
        return _call_tool(request_id, message.get("params") or {})
    if request_id is None:
        return None
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": "지원하지 않는 메서드입니다."},
    }


def _call_tool(request_id: Any, params: dict[str, Any]) -> dict[str, Any]:
    """허용된 도구 호출만 검색 API로 넘깁니다.

    Args:
        request_id: JSON-RPC id입니다.
        params: `name`과 `arguments`를 담은 객체입니다.

    Returns:
        MCP 도구 결과입니다. 실패도 `isError` 본문으로 반환합니다.
    """
    name = params.get("name")
    arguments = params.get("arguments") or {}
    if name != RAG_TOOL_NAME or not isinstance(arguments, dict):
        return _tool_error(request_id, "허용되지 않은 도구입니다.")
    query = arguments.get("query")
    if not isinstance(query, str):
        return _tool_error(request_id, "query는 문자열이어야 합니다.")
    district = arguments.get("district")
    if district is not None and not isinstance(district, str):
        return _tool_error(request_id, "district는 문자열이거나 생략해야 합니다.")
    try:
        payload = search_complaint_rag(query, district)
    except (ValueError, OSError, TimeoutError) as exc:
        return _tool_error(request_id, str(exc))
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(payload, ensure_ascii=False),
                }
            ],
            "isError": False,
        },
    }


def _tool_error(request_id: Any, message: str) -> dict[str, Any]:
    """도구 실패를 MCP 본문으로 만듭니다.

    Args:
        request_id: JSON-RPC id입니다.
        message: 호출자에게 보여줄 짧은 사유입니다.

    Returns:
        `isError`가 참인 도구 결과입니다.
    """
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "content": [{"type": "text", "text": message}],
            "isError": True,
        },
    }


def read_message(stream: Any) -> dict[str, Any] | None:
    """Content-Length 프레임 하나를 읽습니다.

    Args:
        stream: 바이너리 읽기 스트림입니다.

    Returns:
        JSON 객체입니다. 입력이 끝나면 None입니다.
    """
    headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        key, _, value = line.decode("ascii").partition(":")
        headers[key.lower().strip()] = value.strip()
    length = int(headers.get("content-length", "0"))
    if length <= 0:
        return None
    return json.loads(stream.read(length).decode("utf-8"))


def write_message(stream: Any, payload: dict[str, Any]) -> None:
    """JSON-RPC 응답을 Content-Length 프레임으로 씁니다.

    Args:
        stream: 바이너리 쓰기 스트림입니다.
        payload: 응답 객체입니다.
    """
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    stream.write(f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii") + raw)
    stream.flush()


def serve_stdio() -> None:
    """표준 입력이 닫힐 때까지 MCP 요청을 처리합니다."""
    while True:
        message = read_message(sys.stdin.buffer)
        if message is None:
            return
        response = dispatch(message)
        if response is not None:
            write_message(sys.stdout.buffer, response)


if __name__ == "__main__":
    serve_stdio()
