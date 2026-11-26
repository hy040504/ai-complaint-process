"""데이터베이스 ER 다이어그램 문서(Markdown + Mermaid)를 PDF로 출력합니다.

`docs/plans/데이터베이스_ER다이어그램.md`를 읽어 간단한 HTML로 바꾸고, Mermaid 코드 블록은
브라우저에서 Mermaid 라이브러리로 그린 뒤 헤드리스 Chrome/Edge 인쇄 기능으로 PDF를 만듭니다.
Mermaid 문법 오류가 있으면 PDF를 만들지 않고 실패합니다.

실행:
    .venv-web/Scripts/python.exe scripts/reports/export_er_diagram_pdf.py
"""

from __future__ import annotations

import html
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from report_common import find_browser  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SOURCE_MD = ROOT / "docs" / "plans" / "데이터베이스_ER다이어그램.md"
OUTPUT_PDF = SOURCE_MD.with_suffix(".pdf")
MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"

PAGE_CSS = """
@page { size: A3 landscape; margin: 12mm 14mm; }
body { font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; color: #1f2933;
       font-size: 10pt; line-height: 1.55; background: #ffffff; }
h1 { font-size: 18pt; margin: 0 0 6pt; border-bottom: 2px solid #1f4e79; padding-bottom: 4pt; }
h2 { font-size: 13pt; color: #1f4e79; margin: 14pt 0 6pt; }
h2.break { break-before: page; }
code { font-family: Consolas, monospace; background: #eef2f6; padding: 0 3px; border-radius: 3px; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0; font-size: 9pt; }
th, td { border: 1px solid #c5ced8; padding: 3pt 6pt; text-align: left; vertical-align: top; }
th { background: #e4ebf2; }
td.num { text-align: right; }
ul { margin: 4pt 0 4pt 16pt; padding: 0; }
.mermaid { text-align: center; margin: 6pt 0; }
.mermaid svg { max-width: 100% !important; max-height: 212mm !important; height: auto; }
"""


def _inline(text: str) -> str:
    """Markdown 인라인 표기(코드·굵게·링크)를 HTML로 바꿉니다.

    Args:
        text: 한 줄 또는 한 칸의 Markdown 텍스트입니다.

    Returns:
        이스케이프와 인라인 변환을 마친 HTML 문자열입니다. 링크는 PDF에서 글자만 남깁니다.
    """
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    parts = re.split(r"(`[^`]*`)", text)
    out: list[str] = []
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) >= 2:
            out.append(f"<code>{html.escape(part[1:-1])}</code>")
            continue
        piece = html.escape(part, quote=False)
        piece = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", piece)
        out.append(piece)
    return "".join(out)


def _table(rows: list[str]) -> str:
    """Markdown 표 줄 목록을 HTML 표로 바꿉니다.

    Args:
        rows: `|`로 시작하는 표 줄들입니다. 두 번째 줄은 구분선입니다.

    Returns:
        `<table>` HTML 문자열입니다.
    """
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    align = cells[1] if len(cells) > 1 else []
    head = "".join(f"<th>{_inline(c)}</th>" for c in cells[0])
    body = []
    for row in cells[2:]:
        tds = []
        for i, c in enumerate(row):
            cls = ' class="num"' if i < len(align) and align[i].endswith(":") else ""
            tds.append(f"<td{cls}>{_inline(c)}</td>")
        body.append(f"<tr>{''.join(tds)}</tr>")
    return (
        f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"
    )


def markdown_to_html(md: str) -> str:
    """이 문서에서 쓰는 Markdown 일부(제목·문단·목록·표·Mermaid 블록)를 HTML로 바꿉니다.

    Args:
        md: 원본 Markdown 전체 문자열입니다.

    Returns:
        `<body>` 안에 넣을 HTML 문자열입니다. 번호가 붙은 `##` 절은 새 쪽에서 시작합니다.
    """
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```mermaid"):
            block: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                block.append(lines[i])
                i += 1
            out.append(f'<pre class="mermaid">{html.escape(chr(10).join(block))}</pre>')
        elif line.startswith("# "):
            out.append(f"<h1>{_inline(line[2:])}</h1>")
        elif line.startswith("## "):
            title = line[3:]
            cls = ' class="break"' if re.match(r"[1-9]\.", title) else ""
            out.append(f"<h2{cls}>{_inline(title)}</h2>")
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i])
                i += 1
            out.append(_table(rows))
            continue
        elif line.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(f"<li>{_inline(lines[i][2:])}</li>")
                i += 1
            out.append(f"<ul>{''.join(items)}</ul>")
            continue
        elif line.strip():
            out.append(f"<p>{_inline(line)}</p>")
        i += 1
    return "\n".join(out)


def build_html(md: str) -> str:
    """PDF 인쇄용 완성 HTML 문서를 만듭니다.

    Args:
        md: 원본 Markdown 문자열입니다. 상단 탐색 링크 줄은 제외합니다.

    Returns:
        Mermaid 스크립트를 포함한 HTML 문서 문자열입니다.
    """
    md = "\n".join(
        ln for ln in md.splitlines() if not ln.startswith("[계획·설계 문서]")
    )
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><title>데이터베이스 ER 다이어그램</title>
<style>{PAGE_CSS}</style>
<script src="{MERMAID_CDN}"></script>
</head><body>
{markdown_to_html(md)}
<script>
mermaid.initialize({{ startOnLoad: false, theme: 'neutral',
  er: {{ useMaxWidth: true }}, fontFamily: 'Malgun Gothic, sans-serif' }});
mermaid.run({{ querySelector: '.mermaid' }}).then(() => {{
  document.body.setAttribute('data-rendered', 'ok');
}}).catch((e) => {{ document.body.setAttribute('data-rendered', 'error: ' + e); }});
</script>
</body></html>"""


def main() -> int:
    """문서를 읽어 Mermaid 렌더링을 확인한 뒤 PDF를 저장합니다.

    Returns:
        성공하면 0, Mermaid 렌더링이 실패하면 1입니다.
    """
    page_html = build_html(SOURCE_MD.read_text(encoding="utf-8"))
    browser = str(find_browser())
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        page = folder / "er.html"
        page.write_text(page_html, encoding="utf-8")
        command = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            "--virtual-time-budget=20000",
            f"--user-data-dir={folder / 'browser'}",
        ]
        dom = subprocess.run(
            command + ["--dump-dom", page.as_uri()],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        ).stdout
        state = re.search(r'data-rendered="([^"]*)"', dom)
        if state is None or state.group(1) != "ok" or "Syntax error" in dom:
            print(
                f"Mermaid 렌더링 실패: {state.group(1) if state else '완료 표시 없음'}"
            )
            return 1
        subprocess.run(
            command + [f"--print-to-pdf={OUTPUT_PDF}", page.as_uri()],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    if not OUTPUT_PDF.read_bytes().startswith(b"%PDF-"):
        print("유효한 PDF를 만들지 못했습니다.")
        return 1
    print(f"PDF 생성: {OUTPUT_PDF.name} / {OUTPUT_PDF.stat().st_size:,}바이트")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
