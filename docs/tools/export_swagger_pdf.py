"""Flask 민원 웹 OpenAPI 스펙을 Swagger 스타일 한글 PDF로 내보냅니다.

실행 서버가 없어도 메모리 저장소 앱에서 `/openapi/openapi.json`을 읽고,
Chrome 인쇄로 `docs/청주톡톡_민원_업무_API_Swagger.pdf`를 만듭니다.
검색 API(`:8007/docs`)는 대상이 아닙니다.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from src import create_app
from src.complaints.config import ROOT, Settings
from src.complaints.repository import MemoryRepository

DEFAULT_OUTPUT = ROOT / "docs" / "청주톡톡_민원_업무_API_Swagger.pdf"
CHROME_CANDIDATES = (
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path.home() / r"AppData\Local\Google\Chrome\Application\chrome.exe",
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
)
METHOD_ORDER = ("get", "post", "put", "patch", "delete")
COMMON_ERRORS = ("400", "401", "403", "404", "409", "413", "422", "500")


def load_spec() -> dict[str, Any]:
    """메모리 저장소 Flask 앱에서 자동 생성 OpenAPI 문서를 읽습니다.

    Returns:
        OpenAPI 3.1 JSON 객체입니다.
    """
    app = create_app(
        Settings(secret_key="swagger-pdf", backend="memory", testing=True),
        repository=MemoryRepository(),
    )
    payload = app.test_client().get("/openapi/openapi.json").get_json()
    if not isinstance(payload, dict) or "paths" not in payload:
        raise RuntimeError("OpenAPI 문서를 읽지 못했습니다.")
    return payload


def clean_text(value: str) -> str:
    """flask-openapi3가 넣은 HTML 줄바꿈을 일반 문장으로 바꿉니다.

    Args:
        value: summary·description 원문입니다.

    Returns:
        태그를 제거한 한 줄 또는 짧은 문단입니다.
    """
    text = value.replace("<br/>", "\n").replace("<br>", "\n")
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return re.sub(r"[ \t]+\n", "\n", text).strip()


def escape(value: object) -> str:
    """HTML에 넣을 문자열을 이스케이프합니다.

    Args:
        value: 표시할 값입니다.

    Returns:
        HTML 안전 문자열입니다.
    """
    return html.escape(str(value), quote=True)


def path_html(path: str) -> str:
    """경로를 슬래시 뒤에서만 줄바꿈할 수 있게 표시합니다.

    Args:
        path: OpenAPI 경로입니다.

    Returns:
        `<wbr>`이 들어간 HTML입니다.
    """
    return escape(path).replace("/", "/<wbr>")


def render_tag_section(
    title: str,
    description: str,
    blocks: list[str],
) -> str:
    """절 제목과 첫 블록을 같은 페이지에 묶습니다.

    Args:
        title: 태그 또는 모델 절 제목입니다.
        description: 절 설명입니다. 없으면 빈 문자열입니다.
        blocks: 연산 또는 모델 HTML 목록입니다.

    Returns:
        한 절의 HTML입니다.
    """
    if not blocks:
        return ""
    lead = [
        "<section class='tag'><div class='tag-start'><div class='tag-lead'>",
        f"<h2>{escape(title)}</h2>",
    ]
    if description:
        lead.append(f"<p class='tag-desc'>{escape(description)}</p>")
    lead.append("</div>")
    lead.append(blocks[0])
    lead.append("</div>")
    lead.extend(blocks[1:])
    lead.append("</section>")
    return "".join(lead)


def schema_name(ref: str) -> str:
    """JSON Schema `$ref`에서 모델 이름을 꺼냅니다.

    Args:
        ref: `#/components/schemas/Name` 형식의 참조입니다.

    Returns:
        마지막 경로 조각입니다.
    """
    return ref.rstrip("/").rsplit("/", 1)[-1]


def type_label(schema: dict[str, Any] | None) -> str:
    """스키마를 짧은 타입 표기로 만듭니다.

    Args:
        schema: OpenAPI schema 객체입니다.

    Returns:
        `$ref` 이름, 합집합, 또는 JSON 타입 문자열입니다.
    """
    if not schema:
        return "—"
    if "$ref" in schema:
        return schema_name(schema["$ref"])
    if "anyOf" in schema:
        return " | ".join(type_label(item) for item in schema["anyOf"])
    if "oneOf" in schema:
        return " | ".join(type_label(item) for item in schema["oneOf"])
    if schema.get("const") is not None:
        return json.dumps(schema["const"], ensure_ascii=False)
    if schema.get("type") == "array":
        items = schema.get("items") if isinstance(schema.get("items"), dict) else {}
        return f"array[{type_label(items)}]"
    parts = [str(schema.get("type") or "object")]
    if schema.get("format"):
        parts.append(str(schema["format"]))
    bounds = []
    for key, label in (
        ("minLength", "min"),
        ("maxLength", "max"),
        ("minimum", "≥"),
        ("maximum", "≤"),
    ):
        if key in schema:
            bounds.append(f"{label} {_compact_number(schema[key])}")
    if schema.get("pattern"):
        bounds.append(str(schema["pattern"]))
    extra = ", ".join(bounds)
    text = " ".join(parts)
    return f"{text} ({extra})" if extra else text


def _compact_number(value: object) -> str:
    """정수로 떨어지는 실수를 정수 표기로 줄입니다.

    Args:
        value: JSON Schema의 최소·최대 값입니다.

    Returns:
        인쇄용 숫자 문자열입니다.
    """
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def property_rows(schema: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    """객체 스키마의 필드 표 행을 만듭니다.

    Args:
        schema: `properties`를 가진 schema입니다.

    Returns:
        (이름, 필수 여부, 타입, 설명) 행 목록입니다.
    """
    required = set(schema.get("required") or [])
    rows: list[tuple[str, str, str, str]] = []
    for name, field in (schema.get("properties") or {}).items():
        note = clean_text(str(field.get("description") or ""))
        if field.get("enum"):
            values = ", ".join(str(item) for item in field["enum"])
            note = f"{note} 값: {values}".strip()
        if field.get("default") is not None:
            note = f"{note} 기본 {json.dumps(field['default'], ensure_ascii=False)}".strip()
        rows.append(
            (
                str(name),
                "필수" if name in required else "선택",
                type_label(field),
                note or "—",
            )
        )
    return rows


def media_schema(content: dict[str, Any] | None) -> dict[str, Any] | None:
    """content 맵에서 첫 JSON 스키마를 꺼냅니다.

    Args:
        content: `application/json` 등을 키로 하는 OpenAPI content입니다.

    Returns:
        schema 객체 또는 없습니다.
    """
    if not content:
        return None
    for media in content.values():
        schema = media.get("schema")
        if isinstance(schema, dict):
            return schema
    return None


def find_chrome(explicit: Path | None) -> Path:
    """인쇄에 쓸 Chrome 또는 Edge 실행 파일을 찾습니다.

    Args:
        explicit: 호출자가 지정한 경로입니다.

    Returns:
        존재하는 실행 파일 경로입니다.

    Raises:
        FileNotFoundError: 브라우저를 찾지 못했습니다.
    """
    candidates = [explicit] if explicit else []
    candidates.extend(CHROME_CANDIDATES)
    for path in candidates:
        if path is not None and path.is_file():
            return path
    raise FileNotFoundError("Chrome 또는 Edge 실행 파일을 찾지 못했습니다.")


def render_html(spec: dict[str, Any]) -> str:
    """Swagger UI와 비슷한 인쇄용 HTML을 구성합니다.

    Args:
        spec: OpenAPI JSON입니다.

    Returns:
        완결 HTML 문자열입니다.
    """
    info = spec.get("info") or {}
    title = str(info.get("title") or "민원 업무 API")
    version = str(info.get("version") or "")
    description = clean_text(str(info.get("description") or ""))
    tags_meta = {
        item["name"]: item for item in spec.get("tags") or [] if item.get("name")
    }
    schemas = (spec.get("components") or {}).get("schemas") or {}
    grouped: dict[str, list[tuple[str, str, dict[str, Any]]]] = {}
    operations: list[tuple[str, str, str, str]] = []
    for path, item in (spec.get("paths") or {}).items():
        for method in METHOD_ORDER:
            operation = item.get(method)
            if not isinstance(operation, dict):
                continue
            tag = (operation.get("tags") or ["기타"])[0]
            grouped.setdefault(tag, []).append((method, path, operation))
            operations.append(
                (
                    method.upper(),
                    path,
                    clean_text(str(operation.get("summary") or "")),
                    tag,
                )
            )
    tag_order = [name for name in tags_meta] + [
        name for name in grouped if name not in tags_meta
    ]

    parts: list[str] = [
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>",
        f"<title>{escape(title)} Swagger</title><style>",
        CSS,
        "</style></head><body>",
        "<header class='banner'>",
        "<p class='kicker'>청주 민원 AI 완충지대 · Flask /docs 스냅샷 · 검색 API :8007 제외</p>",
        f"<h1>{escape(title)}</h1>",
        f"<p class='meta'>OpenAPI {escape(version)} · 로컬 시연 · "
        "http://127.0.0.1:5000/docs · 2026-11-05</p>",
        f"<p class='lead'>{escape(description)}</p>",
        "<ul class='notes'>",
        "<li>이 PDF는 실행 중인 Swagger UI와 같은 OpenAPI 3.1 모델에서 만들었습니다. "
        "먼저 <code>POST /api/v1/session</code>으로 시연 역할을 고릅니다.</li>",
        "<li>민원 CRUD의 실제 LLM 연결·공식 접수·행정 이관은 미연동입니다. "
        "검사기 <code>/api/v1/assist</code>는 민원을 저장하지 않습니다.</li>",
        "</ul></header>",
        "<h2>엔드포인트</h2><table class='index'><colgroup>",
        "<col class='col-method'><col class='col-path'><col class='col-tag'><col class='col-sum'>",
        "</colgroup><thead><tr>",
        "<th>메서드</th><th>경로</th><th>태그</th><th>요약</th></tr></thead><tbody>",
    ]
    for method, path, summary, tag in operations:
        parts.append(
            "<tr>"
            f"<td><span class='verb {escape(method.lower())}'>{escape(method)}</span></td>"
            f"<td><code>{path_html(path)}</code></td>"
            f"<td>{escape(tag)}</td>"
            f"<td>{escape(summary)}</td>"
            "</tr>"
        )
    parts.append("</tbody></table>")

    for tag in tag_order:
        items = grouped.get(tag) or []
        if not items:
            continue
        tag_info = tags_meta.get(tag) or {}
        description = clean_text(str(tag_info.get("description") or ""))
        parts.append(
            render_tag_section(
                tag,
                description,
                [
                    render_operation(method, path, operation, schemas)
                    for method, path, operation in items
                ],
            )
        )

    parts.append(
        render_tag_section(
            "모델",
            "Swagger UI 하단 Schemas와 같은 구성 요소입니다.",
            [render_model(name, schemas[name]) for name in sorted(schemas)],
        )
    )
    parts.append("</body></html>")
    return "".join(parts)


def render_operation(
    method: str,
    path: str,
    operation: dict[str, Any],
    schemas: dict[str, Any],
) -> str:
    """한 API의 Swagger 블록 HTML을 만듭니다.

    Args:
        method: HTTP 메서드입니다.
        path: OpenAPI 경로입니다.
        operation: operation 객체입니다.
        schemas: 구성 요소 스키마 사전입니다.

    Returns:
        하나의 연산 HTML입니다.
    """
    summary = clean_text(str(operation.get("summary") or ""))
    description = clean_text(str(operation.get("description") or ""))
    if description.startswith("Args:") or description.startswith("Returns:"):
        description = ""
    blocks = [
        f"<section class='op {escape(method)}'>",
        "<div class='op-head'>",
        f"<span class='verb {escape(method)}'>{escape(method.upper())}</span>",
        f"<code class='path'>{path_html(path)}</code>",
        f"<span class='sum'>{escape(summary)}</span>",
        "</div><div class='op-body'>",
    ]
    if description and description != summary:
        blocks.append(f"<p>{escape(description)}</p>")

    parameters = operation.get("parameters") or []
    if parameters:
        blocks.append("<h3>Parameters</h3><table><thead><tr>")
        blocks.append(
            "<th>이름</th><th>위치</th><th>필수</th><th>타입</th><th>설명</th>"
        )
        blocks.append("</tr></thead><tbody>")
        for param in parameters:
            schema = (
                param.get("schema") if isinstance(param.get("schema"), dict) else {}
            )
            blocks.append(
                "<tr>"
                f"<td><code>{escape(param.get('name'))}</code></td>"
                f"<td>{escape(param.get('in'))}</td>"
                f"<td>{'필수' if param.get('required') else '선택'}</td>"
                f"<td>{escape(type_label(schema))}</td>"
                f"<td>{escape(clean_text(str(param.get('description') or schema.get('title') or '—')))}</td>"
                "</tr>"
            )
        blocks.append("</tbody></table>")

    body = operation.get("requestBody")
    if isinstance(body, dict):
        schema = media_schema(body.get("content"))
        blocks.append("<h3>Request body</h3>")
        blocks.append(
            f"<p>JSON{' · 필수' if body.get('required') else ''} · "
            f"{escape(type_label(schema))}</p>"
        )
        blocks.extend(schema_table(schema, schemas))

    responses = operation.get("responses") or {}
    success = [
        (code, item) for code, item in responses.items() if code not in COMMON_ERRORS
    ]
    blocks.append("<h3>Responses</h3><table class='resp'><colgroup>")
    blocks.append("<col class='col-code'><col><col class='col-schema'></colgroup>")
    blocks.append("<thead><tr><th>코드</th><th>설명</th><th>스키마</th></tr></thead><tbody>")
    if success:
        for code, item in success:
            schema = media_schema((item or {}).get("content"))
            blocks.append(
                "<tr>"
                f"<td><code>{escape(code)}</code></td>"
                f"<td>{escape((item or {}).get('description') or '')}</td>"
                f"<td>{escape(type_label(schema))}</td>"
                "</tr>"
            )
    else:
        blocks.append(
            "<tr>"
            "<td><code>200</code></td>"
            "<td>응대 진행 안내를 NDJSON으로 보내고 마지막에 결과를 붙입니다.</td>"
            "<td>application/x-ndjson</td>"
            "</tr>"
        )
    blocks.append("</tbody></table>")
    if any(code in responses for code in COMMON_ERRORS):
        blocks.append(
            "<p class='errors'>공통 오류 400·401·403·404·409·413·422·500은 "
            "<code>ErrorResponse</code> (<code>code</code>, <code>message</code>)입니다.</p>"
        )
    blocks.append("</div></section>")
    return "".join(blocks)


def schema_table(schema: dict[str, Any] | None, schemas: dict[str, Any]) -> list[str]:
    """요청 본문 필드를 표로 펼칩니다.

    Args:
        schema: 요청 schema 또는 `$ref`입니다.
        schemas: 구성 요소 사전입니다.

    Returns:
        HTML 조각 목록입니다.
    """
    resolved = resolve_schema(schema, schemas)
    rows = property_rows(resolved) if resolved else []
    if not rows:
        return []
    html_rows = [
        "<table><thead><tr><th>필드</th><th>필수</th><th>타입</th><th>설명</th></tr></thead><tbody>"
    ]
    for name, need, kind, note in rows:
        html_rows.append(
            "<tr>"
            f"<td><code>{escape(name)}</code></td>"
            f"<td>{escape(need)}</td>"
            f"<td>{escape(kind)}</td>"
            f"<td>{escape(note)}</td>"
            "</tr>"
        )
    html_rows.append("</tbody></table>")
    return html_rows


def resolve_schema(
    schema: dict[str, Any] | None, schemas: dict[str, Any]
) -> dict[str, Any]:
    """한 단계 `$ref`를 풀어 속성 표를 그릴 객체를 얻습니다.

    Args:
        schema: 원본 schema입니다.
        schemas: 구성 요소 사전입니다.

    Returns:
        속성 조회용 schema입니다.
    """
    if not schema:
        return {}
    if "$ref" in schema:
        return schemas.get(schema_name(schema["$ref"])) or schema
    return schema


def render_model(name: str, schema: dict[str, Any]) -> str:
    """구성 요소 스키마 한 개를 출력합니다.

    Args:
        name: 모델 이름입니다.
        schema: 스키마 객체입니다.

    Returns:
        모델 절 HTML입니다.
    """
    description = clean_text(str(schema.get("description") or ""))
    blocks = [f"<section class='model'><h3 id='{escape(name)}'>{escape(name)}</h3>"]
    if description:
        blocks.append(f"<p>{escape(description)}</p>")
    if schema.get("anyOf") or schema.get("oneOf"):
        blocks.append(f"<p>타입: {escape(type_label(schema))}</p>")
    rows = property_rows(schema)
    if rows:
        blocks.extend(schema_table(schema, {}))
    elif not schema.get("anyOf") and not schema.get("oneOf"):
        blocks.append(f"<p>타입: {escape(type_label(schema))}</p>")
    blocks.append("</section>")
    return "".join(blocks)


CSS = """
@page { size: A4; margin: 12mm 12mm 14mm; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: "Malgun Gothic", "맑은 고딕", sans-serif;
  color: #3b4151;
  font-size: 9.2pt;
  line-height: 1.45;
  word-break: keep-all;
  overflow-wrap: anywhere;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
.banner { border-bottom: 4px solid #89bf04; padding-bottom: 6mm; margin-bottom: 6mm; }
.kicker { color: #89bf04; font-weight: 700; margin: 0 0 2mm; font-size: 9pt; }
h1 { font-size: 22pt; margin: 0 0 2mm; color: #3b4151; }
.meta, .lead, .tag-desc { margin: 0 0 3mm; }
.lead { color: #3b4151; }
.notes { margin: 0 0 2mm; padding-left: 5mm; }
.tag-start {
  break-inside: avoid; page-break-inside: avoid;
  -webkit-column-break-inside: avoid;
}
.tag-lead {
  break-inside: avoid; page-break-inside: avoid;
  break-after: avoid; page-break-after: avoid;
}
.tag-start > .op, .tag-start > .model { margin-top: 0; }
h2 {
  font-size: 14pt; color: #3b4151; border-bottom: 1px solid #d8dde3;
  padding-bottom: 1.5mm; margin: 6mm 0 2.5mm;
  break-after: avoid; page-break-after: avoid;
}
h3 { font-size: 10pt; margin: 3mm 0 1.5mm; color: #3b4151; break-after: avoid; page-break-after: avoid; }
code { font-family: Consolas, "Courier New", monospace; font-size: 8.4pt; word-break: keep-all; overflow-wrap: anywhere; }
table { width: 100%; max-width: 100%; border-collapse: collapse; margin: 0 0 3mm; font-size: 8.4pt; }
thead { display: table-header-group; }
tr { break-inside: avoid; page-break-inside: avoid; }
th { text-align: left; background: #41444e; color: #fff; padding: 1.6mm 2mm; }
td {
  border-bottom: 1px solid #e4e7eb; padding: 1.5mm 2mm; vertical-align: top;
  overflow-wrap: anywhere; word-break: break-word;
}
.index { table-layout: fixed; }
.index .col-method { width: 22mm; }
.index .col-path { width: 78mm; }
.index .col-tag { width: 24mm; }
.index td:nth-child(1) { white-space: nowrap; overflow: hidden; }
.index td:nth-child(1) .verb {
  min-width: 0; width: 100%; box-sizing: border-box; padding: 0.8mm 1mm;
}
.index td:nth-child(2) code {
  font-size: 7.1pt; word-break: keep-all; overflow-wrap: anywhere;
}
.index td:nth-child(3) { overflow-wrap: anywhere; word-break: keep-all; }
.verb {
  display: inline-block; min-width: 16mm; text-align: center; color: #fff;
  font-weight: 700; font-size: 8pt; padding: 0.8mm 2mm; border-radius: 3px;
  white-space: nowrap;
}
.verb.get, .op.get .op-head { --c: #61affe; }
.verb.post { --c: #49cc90; }
.verb.put { --c: #fca130; }
.verb.delete { --c: #f93e3e; }
.verb.patch { --c: #50e3c2; }
.verb { background: var(--c, #555); }
.op {
  border: 1px solid #d4d8de; border-radius: 4px; margin: 0 0 4mm;
  background: #fff; overflow: hidden; width: 100%;
  break-inside: avoid; page-break-inside: avoid;
  -webkit-column-break-inside: avoid;
  box-decoration-break: clone; -webkit-box-decoration-break: clone;
}
.op.get { background: #ebf3fb; border-color: #61affe; }
.op.post { background: #e8f6f0; border-color: #49cc90; }
.op.put { background: #fbf1e6; border-color: #fca130; }
.op.delete { background: #fbe7e7; border-color: #f93e3e; }
.op-head {
  display: grid; grid-template-columns: auto minmax(0, 1fr);
  align-items: start; column-gap: 2.5mm; row-gap: 1.2mm;
  padding: 2.2mm 3mm;
  break-inside: avoid; break-after: avoid; page-break-after: avoid;
}
.path { font-weight: 700; color: #3b4151; word-break: keep-all; overflow-wrap: anywhere; min-width: 0; }
.sum { grid-column: 1 / -1; color: #3b4151; min-width: 0; overflow-wrap: anywhere; }
.op-body { background: #fff; padding: 3mm 3.5mm 2mm; border-top: 1px solid #e4e7eb; overflow: hidden; }
.resp { table-layout: fixed; }
.resp .col-code { width: 18mm; }
.resp .col-schema { width: 48mm; }
.errors { color: #6b7280; font-size: 8.2pt; }
.model {
  break-inside: avoid; page-break-inside: avoid; margin: 0 0 4mm; padding: 2mm 0 0;
  overflow: hidden;
}
"""


def print_pdf(html_document: str, chrome: Path, output: Path) -> None:
    """임시 HTML을 Chrome으로 PDF 인쇄합니다.

    Args:
        html_document: 완결 HTML입니다.
        chrome: Chrome 또는 Edge 실행 파일입니다.
        output: 저장할 PDF 경로입니다.

    Raises:
        RuntimeError: PDF 매직 바이트가 없거나 파일이 비었습니다.
        subprocess.CalledProcessError: 브라우저 실행이 실패했습니다.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="complaint-swagger-") as temporary:
        folder = Path(temporary)
        page = folder / "swagger.html"
        page.write_text(html_document, encoding="utf-8")
        profile = folder / "chrome-profile"
        profile.mkdir()
        command = [
            str(chrome),
            "--headless=new",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--no-default-browser-check",
            "--no-pdf-header-footer",
            f"--user-data-dir={profile}",
            f"--print-to-pdf={output}",
            page.as_uri(),
        ]
        subprocess.run(command, check=True, capture_output=True, text=True)
    if not output.is_file() or not output.read_bytes().startswith(b"%PDF-"):
        raise RuntimeError("유효한 PDF를 생성하지 못했습니다.")


def main() -> None:
    """OpenAPI 스펙을 읽고 Swagger 스타일 PDF를 저장합니다."""
    parser = argparse.ArgumentParser(
        description="민원 웹 Swagger 페이지를 PDF로 저장합니다."
    )
    parser.add_argument("--chrome", type=Path, help="Chrome 또는 Edge 실행 파일")
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT, help="출력 PDF 경로"
    )
    args = parser.parse_args()
    spec = load_spec()
    document = render_html(spec)
    output = args.output.resolve()
    print_pdf(document, find_chrome(args.chrome), output)
    paths = len(spec.get("paths") or {})
    print(f"PDF 생성: {output} / 경로 {paths}개 / {output.stat().st_size:,}바이트")


if __name__ == "__main__":
    main()
