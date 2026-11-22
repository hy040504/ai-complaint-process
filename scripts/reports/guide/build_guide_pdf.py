"""사용 가이드(마크다운)를 인쇄용 PDF로 변환합니다.

가이드에 쓰는 마크다운 문법(제목·문단·목록·표·인용·코드·그림·굵게·링크)만 해석하는 작은
변환기입니다. 변환한 HTML을 Edge 또는 Chrome의 헤드리스 인쇄 기능으로 PDF로 저장합니다.

사용법:
    python scripts/reports/guide/build_guide_pdf.py            # docs/guides의 두 가이드를 모두 변환
    python scripts/reports/guide/build_guide_pdf.py 민원인_이용_가이드
"""

from __future__ import annotations

import html
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GUIDE_DIR = ROOT / "docs" / "guides"
DEFAULT_NAMES = ["민원인_이용_가이드", "담당자_이용_가이드"]
BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
]
ALERTS = {
    "NOTE": ("참고", "note"),
    "TIP": ("도움말", "tip"),
    "IMPORTANT": ("중요", "important"),
    "WARNING": ("주의", "warning"),
}
CSS = """
@page { size: A4; margin: 16mm 14mm; }
* { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: 'Noto Sans KR', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; font-size: 11pt; line-height: 1.7; color: #16203a; word-break: keep-all; }
h1 { font-size: 24pt; margin: 0 0 8pt; letter-spacing: -0.02em; }
h2 { font-size: 16pt; margin: 22pt 0 8pt; padding-top: 10pt; border-top: 2px solid #2f6fed; break-after: avoid; }
h3 { font-size: 13pt; margin: 16pt 0 6pt; break-after: avoid; }
p { margin: 6pt 0; }
a { color: #1e4fc7; text-decoration: none; }
img { max-width: 100%; height: auto; border: 1px solid #d6deec; border-radius: 6px; display: block; margin: 8pt auto; break-inside: avoid; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0; font-size: 10pt; break-inside: avoid; }
th, td { border: 1px solid #d6deec; padding: 5pt 7pt; vertical-align: top; text-align: left; }
th { background: #eef2f9; }
td.c, th.c { text-align: center; }
code { font-family: Consolas, 'D2Coding', monospace; background: #eef2f9; padding: 1pt 4pt; border-radius: 3px; font-size: 0.92em; }
pre { background: #f3f6fc; border: 1px solid #d6deec; border-radius: 6px; padding: 8pt; font-size: 10pt; white-space: pre-wrap; break-inside: avoid; }
pre code { background: none; padding: 0; }
blockquote { margin: 8pt 0; padding: 6pt 10pt; border-left: 4px solid #8aa3d6; background: #f3f6fc; break-inside: avoid; }
blockquote.note { border-color: #2f6fed; background: #e8f0ff; }
blockquote.tip { border-color: #1f8a4d; background: #e8f6ee; }
blockquote.important { border-color: #7a4bd6; background: #f0eaff; }
blockquote.warning { border-color: #d92d20; background: #fdecea; }
blockquote b.t { display: block; margin-bottom: 2pt; }
hr { border: 0; border-top: 1px solid #d6deec; margin: 14pt 0; }
ul, ol { margin: 6pt 0; padding-left: 20pt; }
li { margin: 2pt 0; }
"""


def slug(text: str) -> str:
    """제목을 GitHub 방식의 앵커 이름으로 바꿉니다.

    Args:
        text: 제목 글자입니다.

    Returns:
        소문자·하이픈 앵커 문자열입니다.
    """
    text = re.sub(r"[`*]", "", text).strip().lower()
    text = re.sub(r"[^\w\s가-힣-]", "", text)
    return re.sub(r"\s+", "-", text)


def inline(text: str) -> str:
    """문단 안의 굵게·코드·링크·그림 표기를 HTML로 바꿉니다.

    Args:
        text: 한 줄 또는 한 칸의 마크다운 글자입니다.

    Returns:
        HTML 문자열입니다. `<img>`·`<br>` 같은 직접 쓴 태그는 그대로 둡니다.
    """
    codes: list[str] = []

    def keep_code(m: re.Match[str]) -> str:
        codes.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\x00{len(codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", keep_code, text)
    raw_tags: list[str] = []

    def keep_tag(m: re.Match[str]) -> str:
        raw_tags.append(m.group(0))
        return f"\x01{len(raw_tags) - 1}\x01"

    text = re.sub(r"<(?:img|br|b|/b|sub|/sub|kbd|/kbd)[^>]*>", keep_tag, text)
    text = html.escape(text, quote=False)
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img alt="\1" src="\2">', text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\x01(\d+)\x01", lambda m: raw_tags[int(m.group(1))], text)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], text)


def split_row(line: str) -> list[str]:
    """표의 한 줄을 칸 목록으로 나눕니다."""
    return [c.strip() for c in line.strip().strip("|").split("|")]


def convert(md: str) -> str:
    """마크다운 본문을 HTML 본문으로 변환합니다.

    Args:
        md: 가이드 마크다운 전체 글자입니다.

    Returns:
        `<body>` 안에 넣을 HTML입니다.
    """
    lines = md.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("```"):
            i += 1
            block: list[str] = []
            while i < len(lines) and not lines[i].startswith("```"):
                block.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>" + html.escape("\n".join(block)) + "</code></pre>")
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            out.append(
                f'<h{level} id="{slug(m.group(2))}">{inline(m.group(2))}</h{level}>'
            )
            i += 1
            continue
        if re.match(r"^-{3,}\s*$", line):
            out.append("<hr>")
            i += 1
            continue
        if line.lstrip().startswith("<img"):
            out.append(inline(line.strip()))
            i += 1
            continue
        if line.startswith(">"):
            quote: list[str] = []
            while i < len(lines) and lines[i].startswith(">"):
                quote.append(lines[i][1:].strip())
                i += 1
            cls, head = "", ""
            am = re.match(r"^\[!(\w+)\]$", quote[0]) if quote else None
            if am and am.group(1) in ALERTS:
                label, cls = ALERTS[am.group(1)]
                head = f'<b class="t">{label}</b>'
                quote = quote[1:]
            out.append(
                f'<blockquote class="{cls}">{head}{inline(" ".join(q for q in quote if q))}</blockquote>'
            )
            continue
        if (
            line.startswith("|")
            and i + 1 < len(lines)
            and re.match(r"^\|[\s:|-]+\|\s*$", lines[i + 1])
        ):
            header = split_row(line)
            aligns = [
                "c" if c.strip().startswith(":") and c.strip().endswith(":") else ""
                for c in split_row(lines[i + 1])
            ]
            i += 2
            rows: list[list[str]] = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            th = "".join(
                f'<th class="{aligns[k]}">{inline(c)}</th>'
                for k, c in enumerate(header)
            )
            body = "".join(
                "<tr>"
                + "".join(
                    f'<td class="{aligns[k] if k < len(aligns) else ""}">{inline(c)}</td>'
                    for k, c in enumerate(r)
                )
                + "</tr>"
                for r in rows
            )
            out.append(
                f"<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"
            )
            continue
        lm = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if lm:
            ordered = lm.group(2)[0].isdigit()
            items: list[str] = []
            while i < len(lines):
                mm = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[i])
                if not mm:
                    break
                items.append(inline(mm.group(3)))
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(
                f"<{tag}>" + "".join(f"<li>{x}</li>" for x in items) + f"</{tag}>"
            )
            continue
        para = [line.strip()]
        i += 1
        while (
            i < len(lines)
            and lines[i].strip()
            and not re.match(
                r"^(#{1,4}\s|-{3,}|>|\||```|\s*([-*]|\d+\.)\s|<img)", lines[i]
            )
        ):
            para.append(lines[i].strip())
            i += 1
        out.append(f"<p>{inline('<br>'.join(para))}</p>")
    return "\n".join(out)


def find_browser() -> str:
    """PDF 인쇄에 쓸 Edge·Chrome 실행 파일을 찾습니다.

    Returns:
        실행 파일 경로입니다.

    Raises:
        SystemExit: 설치된 브라우저가 없으면 종료합니다.
    """
    for path in BROWSERS:
        if Path(path).exists():
            return path
    raise SystemExit(
        "Edge 또는 Chrome을 찾지 못했습니다. BROWSERS 목록에 경로를 추가하세요."
    )


def build(name: str) -> Path:
    """가이드 하나를 HTML로 바꾸고 헤드리스 브라우저로 PDF를 만듭니다.

    Args:
        name: 확장자를 뺀 가이드 파일 이름입니다.

    Returns:
        만들어진 PDF 경로입니다.
    """
    source = GUIDE_DIR / f"{name}.md"
    body = convert(source.read_text(encoding="utf-8"))
    page = f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>{name}</title><style>{CSS}</style></head><body>{body}</body></html>'
    with tempfile.TemporaryDirectory() as tmp:
        # 상대 경로 그림이 열리도록 가이드 폴더 안에 임시 HTML을 두고 인쇄한 뒤 지웁니다.
        tmp_html = GUIDE_DIR / f".{name}.build.html"
        tmp_html.write_text(page, encoding="utf-8")
        pdf = GUIDE_DIR / f"{name}.pdf"
        try:
            subprocess.run(
                [
                    find_browser(),
                    "--headless",
                    "--disable-gpu",
                    "--no-first-run",
                    f"--user-data-dir={tmp}",
                    "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}",
                    tmp_html.as_uri(),
                ],
                check=True,
                timeout=180,
                capture_output=True,
            )
        finally:
            tmp_html.unlink(missing_ok=True)
    return pdf


if __name__ == "__main__":
    for target in sys.argv[1:] or DEFAULT_NAMES:
        path = build(target)
        print(f"PDF 생성: {path.relative_to(ROOT)} ({path.stat().st_size // 1024} KB)")
