"""통합 설계 Markdown과 SVG를 같은 내용의 한글 PDF로 내보냅니다.

문서 변환에는 markdown-it-py와 Chrome, NanumGothic 글꼴 파일이 필요합니다.
임시 HTML에는 글꼴을 포함하며 저장소의 문서 링크는 GitHub로 연결합니다.
"""

from __future__ import annotations

import argparse
import base64
import html
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[2]
GITHUB = "https://github.com/hy040504/ai-complaint-process/blob/main/"


def render_document(source: Path, font_dir: Path) -> tuple[str, int]:
    """Markdown 페이지와 로컬 SVG·글꼴을 인쇄용 HTML로 구성합니다.

    Args:
        source: 저장소 안의 Markdown 원본 경로입니다.
        font_dir: NanumGothic-Regular.ttf와 NanumGothic-Bold.ttf 위치입니다.

    Returns:
        인쇄용 HTML과 원본의 페이지 수입니다.

    Raises:
        ValueError: 연결된 로컬 파일이 저장소 범위를 벗어납니다.
        OSError: 원본·그림·글꼴을 읽을 수 없습니다.
    """
    css = (ROOT / "docs/assets/web-mvp/인쇄.css").read_text(encoding="utf-8")
    for weight, name in [(400, "Regular"), (700, "Bold")]:
        encoded = base64.b64encode((font_dir / f"NanumGothic-{name}.ttf").read_bytes()).decode()
        css += f'\n@font-face{{font-family:"Nanum Gothic";font-weight:{weight};src:url(data:font/ttf;base64,{encoded}) format("truetype");}}'
    renderer = MarkdownIt("commonmark", {"html": True}).enable("table")
    source_text = source.read_text(encoding="utf-8")
    sections = source_text.split("<!-- page -->")
    version = re.search(r"문서 버전 \*\*([^*]+)\*\*", source_text)
    date = re.search(r"설계 기준 \*\*(\d{4}-\d{2}-\d{2}) UTC\*\*", source_text)
    footer = " · ".join(filter(None, [
        date.group(1).replace("-", ".") if date else None,
        "통합 설계 " + version.group(1) if version else "통합 설계",
    ]))
    pages = []
    for index, section in enumerate(sections, start=1):
        body = renderer.render(section)
        for match in list(re.finditer(r'<img src="([^"]+)"[^>]*>', body)):
            asset = (source.parent / unquote(html.unescape(match.group(1)))).resolve()
            asset.relative_to(ROOT)
            if asset.suffix == ".svg":
                body = body.replace(match.group(0), asset.read_text(encoding="utf-8"))
        for match in list(re.finditer(r'href="([^"]+)"', body)):
            target = html.unescape(match.group(1))
            parsed = urlsplit(target)
            if parsed.scheme or target.startswith("#"):
                continue
            local = (source.parent / unquote(parsed.path)).resolve()
            relative = local.relative_to(ROOT).as_posix()
            address = GITHUB + quote(relative) + ("#" + quote(parsed.fragment) if parsed.fragment else "")
            body = body.replace(match.group(0), 'href="' + html.escape(address, quote=True) + '"')
        # 절이 여러 페이지로 늘어나도 머리말의 번호는 원본 제목을 따릅니다.
        heading = re.search(r"^## ([\d-]+)\.", section, re.MULTILINE)
        label = "표지" if index == 1 else ("설계 " + heading.group(1) if heading else "설계")
        pages.append(
            f'<section class="page {"cover" if index == 1 else ""}">'
            f'<header>청주 민원 AI 완충지대 <span>{label} · 구현 전 설계</span></header>'
            f'<main>{body}</main><footer>{html.escape(footer)}'
            f'<span>{index:02d} / {len(sections):02d}</span></footer></section>'
        )
    check = """
    document.fonts.ready.then(() => {
      const overflow = [...document.querySelectorAll('.page')].flatMap((page, index) => {
        const main = page.querySelector('main').getBoundingClientRect();
        const footer = page.querySelector('footer').getBoundingClientRect();
        return main.bottom > footer.top - 10 ? [index + 1] : [];
      });
      document.body.dataset.overflow = JSON.stringify(overflow);
    });
    """
    document = '<!doctype html><html lang="ko"><meta charset="utf-8">'
    document += '<title>민원 웹 MVP 상세설계와 2인 개발계획</title>'
    document += f'<style>{css}</style><body>{"".join(pages)}<script>{check}</script></body></html>'
    return document, len(sections)


def main() -> None:
    """인자를 읽고 페이지 넘침을 확인한 뒤 Chrome으로 PDF를 생성합니다.

    Raises:
        RuntimeError: 본문이 바닥글 영역을 침범하거나 PDF가 생성되지 않았습니다.
        subprocess.CalledProcessError: Chrome 실행이 실패했습니다.
    """
    parser = argparse.ArgumentParser(description="통합 설계 문서를 PDF로 생성합니다.")
    parser.add_argument("source", type=Path, help="Markdown 원본 경로")
    parser.add_argument("--font-dir", required=True, type=Path, help="NanumGothic 글꼴 두 개가 있는 폴더")
    parser.add_argument("--chrome", default="google-chrome", help="Chrome 실행 파일")
    parser.add_argument("--output", type=Path, help="출력 PDF, 기본값은 원본과 같은 이름")
    args = parser.parse_args()
    source = args.source.resolve()
    output = (args.output or source.with_suffix(".pdf")).resolve()
    document, pages = render_document(source, args.font_dir)
    with tempfile.TemporaryDirectory(prefix="complaint-design-") as temporary:
        folder = Path(temporary)
        page = folder / "document.html"
        page.write_text(document, encoding="utf-8")
        command = [args.chrome, "--headless", "--disable-gpu", "--disable-dev-shm-usage",
                   "--no-first-run", "--no-default-browser-check", "--no-pdf-header-footer",
                   "--virtual-time-budget=5000", f"--user-data-dir={folder / 'chrome'}"]
        checked = subprocess.run(command + ["--dump-dom", page.as_uri()], check=True, capture_output=True, text=True)
        match = re.search(r'data-overflow="([^"]+)"', checked.stdout)
        if match is None or html.unescape(match.group(1)) != "[]":
            raise RuntimeError("인쇄 본문이 바닥글을 침범하거나 글꼴 로딩 확인에 실패했습니다: " + (match.group(1) if match else "확인 불가"))
        subprocess.run(command + [f"--print-to-pdf={output}", page.as_uri()], check=True, capture_output=True, text=True)
        if not output.is_file() or not output.read_bytes().startswith(b"%PDF-"):
            raise RuntimeError("유효한 PDF를 생성하지 못했습니다.")
    print(f"PDF 생성: {output.name} / 설계 페이지 {pages}개 / {output.stat().st_size:,}바이트")


if __name__ == "__main__":
    main()
