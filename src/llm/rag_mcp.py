"""민원 검색(`search_complaint_rag`) 및 장소 추적(`lookup_navermap_place`)을 제공하는 MCP stdio 서버입니다.

Codex 자식 프로세스로 실행합니다. 표준 입력은 MCP 규격의 줄 단위
JSON-RPC와 예전 Content-Length 프레임을 모두 받습니다. 응답은 받은
형식과 같게 씁니다. 민원 문장은 검색 API로, 장소명은 네이버 지도 웹
인스턴트 검색으로 넘깁니다.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from src.llm.place_tool import (
    PLACE_TOOL_NAME,
    PLACE_TOOL_USAGE,
    lookup_navermap_place,
)
from src.llm.rag_tool import RAG_TOOL_NAME, RAG_TOOL_USAGE, search_complaint_rag

PROTOCOL = "2024-11-05"


def rag_tool_spec() -> dict[str, Any]:
    """Codex에 공개할 민원 RAG 검색 도구 스키마를 만듭니다.

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


def place_tool_spec() -> dict[str, Any]:
    """Codex에 공개할 네이버 지도 장소 주소 추적 도구 스키마를 만듭니다.

    Returns:
        MCP `tools/list`에 넣을 도구 정의입니다.
    """
    return {
        "name": PLACE_TOOL_NAME,
        "description": PLACE_TOOL_USAGE,
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "query": {
                    "type": "string",
                    "description": "장소 검색어(건물명, 학교명, 시장명, 공원명 등)",
                },
                "coords": {
                    "type": "string",
                    "description": "중심 좌표(위도,경도). 없으면 청주시청 기본값",
                },
            },
            "required": ["query"],
        },
        "annotations": {"readOnlyHint": True},
    }


def tool_spec() -> dict[str, Any]:
    """이전 버전과의 호환성을 위한 기본 RAG 검색 도구 스키마입니다."""
    return rag_tool_spec()


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
            "result": {"tools": [rag_tool_spec(), place_tool_spec()]},
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
    """허용된 도구 호출만 해당 처리 함수로 넘깁니다.

    Args:
        request_id: JSON-RPC id입니다.
        params: `name`과 `arguments`를 담은 객체입니다.

    Returns:
        MCP 도구 결과입니다. 실패도 `isError` 본문으로 반환합니다.
    """
    name = params.get("name")
    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        return _tool_error(request_id, "도구 인자는 객체여야 합니다.")

    if name == RAG_TOOL_NAME:
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

    if name == PLACE_TOOL_NAME:
        query = arguments.get("query")
        if not isinstance(query, str):
            return _tool_error(request_id, "query는 문자열이어야 합니다.")
        coords = arguments.get("coords")
        if coords is not None and not isinstance(coords, str):
            return _tool_error(request_id, "coords는 문자열이거나 생략해야 합니다.")
        try:
            payload = lookup_navermap_place(query, coords)
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

    return _tool_error(request_id, "허용되지 않은 도구입니다.")


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


def _as_rpc_object(payload: Any) -> dict[str, Any]:
    """JSON-RPC 본문이 객체인지 확인합니다.

    Args:
        payload: `json.loads` 결과입니다.

    Returns:
        JSON 객체입니다.

    Raises:
        ValueError: 배열·문자열 등 객체가 아닌 경우 발생합니다.
    """
    if not isinstance(payload, dict):
        raise ValueError("MCP 본문은 JSON 객체여야 합니다.")
    return payload


def _decode_json_line(line: bytes) -> dict[str, Any]:
    """한 줄 JSON-RPC 본문을 객체로 바꿉니다.

    Args:
        line: 개행이 포함될 수 있는 UTF-8 한 줄입니다.

    Returns:
        JSON 객체입니다.

    Raises:
        ValueError: 본문이 JSON 객체가 아닌 경우 발생합니다.
        json.JSONDecodeError: JSON 문법 오류입니다.
    """
    text = line.decode("utf-8").lstrip("\ufeff").strip()
    return _as_rpc_object(json.loads(text))


def read_stdio_message(stream: Any) -> tuple[dict[str, Any] | None, str | None]:
    """stdio에서 MCP 메시지 하나와 프레임 형식을 읽습니다.

    Codex는 줄 단위 JSON-RPC를 보냅니다. 예전 단위 테스트는
    Content-Length 헤더를 씁니다. `{`로 시작하면 줄 단위로 읽고,
    그 밖에는 Content-Length 프레임으로 읽습니다.

    Args:
        stream: 바이너리 읽기 스트림입니다.

    Returns:
        `(메시지, ndjson|content-length)`입니다. 입력이 끝나면
        `(None, None)`입니다.
    """
    first = stream.readline()
    if not first:
        return None, None
    stripped = first.lstrip()
    if stripped.startswith(b"\xef\xbb\xbf"):
        stripped = stripped[3:].lstrip()
    if stripped.startswith(b"{"):
        return _decode_json_line(first), "ndjson"
    headers: dict[str, str] = {}
    line = first
    while True:
        if line in (b"\r\n", b"\n"):
            break
        key, _, value = line.decode("ascii").partition(":")
        headers[key.lower().strip()] = value.strip()
        line = stream.readline()
        if not line:
            return None, None
    length = int(headers.get("content-length", "0"))
    if length <= 0:
        return None, None
    payload = json.loads(stream.read(length).decode("utf-8"))
    return _as_rpc_object(payload), "content-length"


def write_stdio_message(stream: Any, payload: dict[str, Any], framing: str) -> None:
    """JSON-RPC 응답을 지정한 프레임 형식으로 씁니다.

    줄 단위 전송은 본문에 생 개행이 들어가면 안 되므로 공백 없는
    JSON을 씁니다.

    Args:
        stream: 바이너리 쓰기 스트림입니다.
        payload: 응답 객체입니다.
        framing: `ndjson` 또는 `content-length`입니다.
    """
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if framing == "ndjson":
        stream.write(raw + b"\n")
    else:
        stream.write(f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii") + raw)
    stream.flush()


def read_message(stream: Any) -> dict[str, Any] | None:
    """stdio 메시지 하나만 읽습니다.

    Args:
        stream: 바이너리 읽기 스트림입니다.

    Returns:
        JSON 객체입니다. 입력이 끝나면 None입니다.
    """
    message, _framing = read_stdio_message(stream)
    return message


def write_message(stream: Any, payload: dict[str, Any]) -> None:
    """JSON-RPC 응답을 Content-Length 프레임으로 씁니다.

    Args:
        stream: 바이너리 쓰기 스트림입니다.
        payload: 응답 객체입니다.
    """
    write_stdio_message(stream, payload, "content-length")


def serve_stdio() -> None:
    """표준 입력이 닫힐 때까지 MCP 요청을 처리합니다.

    첫 요청의 프레임 형식을 기억하고 같은 형식으로 응답합니다.
    """
    inbound = sys.stdin.buffer
    outbound = sys.stdout.buffer
    framing = "ndjson"
    while True:
        message, found = read_stdio_message(inbound)
        if message is None:
            return
        if found:
            framing = found
        response = dispatch(message)
        if response is not None:
            write_stdio_message(outbound, response, framing)


if __name__ == "__main__":
    serve_stdio()
