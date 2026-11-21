"""보고서 HTML을 헤드리스 브라우저 PDF로 변환하고 일자별 업무·UI 보고서 구성을 공유하는 공용 모듈입니다.

`daily_report_20261116.py`·`daily_report_20261118.py`·`daily_report_20261119.py`·
`analysis_report_112.py` 등이 브라우저 탐색, PDF 인쇄, 이미지 인코딩,
UI 수정 보고서 카드 조립과 공통 A4 스타일시트를 함께 사용합니다. 직접 실행하지 않는 공용 모듈입니다.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import html
from pathlib import Path
import subprocess
import tempfile
import pypdf

CHROME_CANDIDATES = (
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path.home() / r"AppData\Local\Google\Chrome\Application\chrome.exe",
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
)


@dataclass(frozen=True)
class UiFixCapture:
    """원본 UI 수정 보고서 PDF에 수록된 고유 캡처 이미지 설명입니다."""

    unique_index: int
    label: str


@dataclass(frozen=True)
class UiFixItem:
    """원본 UI 수정 보고서 PDF의 항목 한 건을 원문 무수정으로 보관합니다."""

    code: str
    title: str
    rule_note: str
    detail_rows: tuple[tuple[str, str], ...]
    captures: tuple[UiFixCapture, ...] = ()
    side_by_side: bool = True
    max_img_height_mm: int = 86


WORK_REPORT_CSS = """
  @page {
    size: A4 portrait;
    margin: 9mm 12mm 9mm 12mm;
  }
  * {
    box-sizing: border-box;
  }
  body {
    font-family: "Malgun Gothic", "맑은 고딕", Dotum, sans-serif;
    color: #111;
    margin: 0;
    padding: 0;
    font-size: 8.6pt;
    line-height: 1.40;
    letter-spacing: -0.3px;
    -webkit-print-color-adjust: exact;
  }
  .page-break {
    page-break-after: always;
  }
  .page-break:last-child {
    page-break-after: auto;
  }
  h1.title {
    text-align: center;
    font-size: 19pt;
    font-weight: 800;
    margin: 0 0 9px 0;
    letter-spacing: 3px;
  }
  h1.sub-title {
    text-align: center;
    font-size: 16.5pt;
    font-weight: 800;
    margin: 0 0 6px 0;
    letter-spacing: 1px;
  }
  table.report-table {
    width: 100%;
    border-collapse: collapse;
    border: 1.2px solid #222;
  }
  table.report-table th,
  table.report-table td {
    border: 1px solid #333;
    padding: 4.5px 8px;
  }
  .label-cell {
    width: 14%;
    text-align: center;
    font-weight: bold;
    vertical-align: middle;
    background-color: #ffffff;
    line-height: 1.35;
  }
  .header-label {
    width: 14%;
    text-align: center;
    font-weight: bold;
    background-color: #ffffff;
    white-space: nowrap;
  }
  .header-val {
    width: 36%;
  }
  .full-val {
    width: 86%;
    vertical-align: top;
  }
  .section-title {
    font-weight: bold;
    margin-top: 3px;
    margin-bottom: 1.2px;
    color: #000;
  }
  .section-title:first-child {
    margin-top: 0;
  }
  .bullet-item {
    margin: 1.3px 0;
    padding-left: 10px;
    text-indent: -10px;
    word-break: keep-all;
  }
  .highlight-tag {
    font-weight: bold;
    color: #0f766e;
  }

  /* 별첨 공통 헤더 */
  .att-header {
    text-align: center;
    margin-bottom: 8px;
    border-bottom: 1.5px solid #222;
    padding-bottom: 5px;
  }
  .att-header h2 {
    font-size: 14pt;
    font-weight: 800;
    margin: 0 0 2px 0;
  }
  .att-meta {
    font-size: 8.2pt;
    color: #555;
    margin: 0;
  }
  .att-sec-title {
    text-align: left;
    font-size: 10.3pt;
    font-weight: 800;
    margin: 9px 0 4.5px 0;
    color: #111;
  }

  /* 핵심 요약 KPI 카드 */
  .kpi-strip {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 6px;
    margin: 4px 0 8px 0;
  }
  .kpi-card {
    border: 1px solid #cbd5e1;
    border-top: 3px solid #0f766e;
    border-radius: 4px;
    background: #f8fafc;
    padding: 5.5px 7px;
  }
  .kpi-label {
    font-size: 7.4pt;
    color: #475569;
    font-weight: 700;
    margin-bottom: 1.5px;
  }
  .kpi-val {
    font-size: 11.2pt;
    font-weight: 800;
    color: #0f172a;
    line-height: 1.2;
  }
  .kpi-sub {
    font-size: 7.2pt;
    color: #0f766e;
    margin-top: 1.5px;
    font-weight: 700;
  }

  /* 비교표 */
  table.diff-table {
    width: 100%;
    border-collapse: collapse;
    border: 1.2px solid #222;
    margin-top: 3px;
    font-size: 8pt;
    line-height: 1.38;
  }
  table.diff-table th {
    background-color: #f3f5f8;
    border: 1px solid #333;
    padding: 4.5px 6.5px;
    text-align: center;
    font-weight: bold;
  }
  table.diff-table td {
    border: 1px solid #333;
    padding: 4.5px 7px;
    vertical-align: middle;
    word-break: keep-all;
  }
  .col-center {
    text-align: center;
    white-space: nowrap;
  }
  code {
    font-family: Consolas, "Courier New", monospace;
    font-size: 7.7pt;
    background: #f1f5f9;
    padding: 0.5px 3px;
    border-radius: 2px;
  }

  /* 쉬운 흐름 다이어그램 */
  .flow-box {
    border: 1px solid #cbd5e1;
    border-radius: 5px;
    background: #f8fafc;
    padding: 8px 10px;
    margin-top: 4px;
  }
  .flow-grid {
    display: grid;
    grid-template-columns: 1fr 18px 1fr 18px 1fr 18px 1fr;
    align-items: stretch;
    gap: 3px;
  }
  .flow-step {
    background: #ffffff;
    border: 1px solid #94a3b8;
    border-radius: 4px;
    padding: 6px 7px;
  }
  .flow-step-num {
    font-size: 7.4pt;
    font-weight: 800;
    color: #0f766e;
    margin-bottom: 2px;
  }
  .flow-step-title {
    font-size: 8.5pt;
    font-weight: 800;
    color: #0f172a;
    margin-bottom: 3px;
  }
  .flow-step-desc {
    font-size: 7.6pt;
    color: #334155;
    line-height: 1.35;
    word-break: keep-all;
  }
  .flow-arrow {
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11pt;
    font-weight: 800;
    color: #0f766e;
  }
  .flow-branches {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 6px;
    margin-top: 6px;
  }
  .flow-branch {
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-left: 3px solid #2563eb;
    border-radius: 3px;
    padding: 4.5px 7px;
    font-size: 7.6pt;
    color: #1e293b;
    word-break: keep-all;
  }
  .flow-branch.warn {
    border-left-color: #d97706;
  }
  .flow-branch.safe {
    border-left-color: #0f766e;
  }
  .flow-branch b {
    display: block;
    font-size: 7.9pt;
    margin-bottom: 1.5px;
    color: #0f172a;
  }

  /* 실서버·시각화 캡처 장면 */
  .scene-block {
    margin-top: 7px;
    margin-bottom: 9px;
  }
  .scene-cap {
    font-size: 9pt;
    font-weight: 700;
    color: #111;
    margin: 0 0 2.5px 0;
  }
  .scene-sub {
    font-size: 7.9pt;
    color: #444;
    margin: 0 0 4px 0;
    word-break: keep-all;
  }
  .scene-img-wrap {
    border: 1px solid #94a3b8;
    border-radius: 4px;
    overflow: hidden;
    background: #fff;
    text-align: center;
  }
  .scene-img-wrap img {
    width: 100%;
    height: auto;
    max-height: 103mm;
    object-fit: contain;
    object-position: top center;
    display: block;
    margin: 0 auto;
  }

  /* 별첨 2: UI 수정 보고서 카드/표 (원문 무수정 · 기존 양식 통일) */
  .ui-item-card {
    border: 1.1px solid #333;
    border-radius: 4px;
    padding: 6.5px 8.5px;
    margin-bottom: 8px;
    background: #fff;
    break-inside: avoid;
  }
  .ui-item-head {
    font-size: 10.2pt;
    font-weight: 800;
    color: #111;
    margin: 0 0 4.5px 0;
    padding-bottom: 3.5px;
    border-bottom: 1px solid #cbd5e1;
  }
  table.ui-meta-table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 5px;
    font-size: 8pt;
    line-height: 1.36;
  }
  table.ui-meta-table th {
    width: 14%;
    background: #f3f5f8;
    border: 1px solid #64748b;
    padding: 3px 5.5px;
    text-align: center;
    font-weight: 700;
    vertical-align: middle;
    white-space: nowrap;
  }
  table.ui-meta-table td {
    border: 1px solid #64748b;
    padding: 3px 6.5px;
    vertical-align: middle;
    word-break: keep-all;
  }
  .ui-extra-note {
    margin: 0 0 4.5px 0;
    padding: 2.5px 6.5px;
    background: #f8fafc;
    border-left: 2.5px solid #0f766e;
    font-size: 7.7pt;
    color: #334155;
  }
  .ui-cap-label {
    font-size: 7.9pt;
    font-weight: 700;
    color: #1e293b;
    margin: 3.5px 0 2px 0;
  }
  .ui-cap-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    align-items: start;
  }
  .ui-cap-stack {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .ui-img-box {
    border: 1px solid #94a3b8;
    border-radius: 3px;
    background: #ffffff;
    overflow: hidden;
    text-align: center;
    padding: 2px;
  }
  .ui-img-box img {
    max-width: 100%;
    height: auto;
    object-fit: contain;
    display: block;
    margin: 0 auto;
  }
"""


def find_browser() -> Path:
    """Chrome 또는 Edge 브라우저 실행 파일 경로를 탐색합니다.

    Returns:
        존재하는 브라우저 실행 파일 경로입니다.

    Raises:
        FileNotFoundError: 사용 가능한 Chrome 또는 Edge가 없을 때 발생합니다.
    """
    for candidate in CHROME_CANDIDATES:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Chrome 또는 Edge 실행 파일을 찾을 수 없습니다.")


def render_html_to_pdf(html_text: str, output_pdf: Path) -> None:
    """HTML 문자열을 헤드리스 브라우저 인쇄 기능으로 A4 PDF 파일로 출력합니다.

    Args:
        html_text: 인쇄할 HTML 문서 문자열입니다.
        output_pdf: 저장할 PDF 파일 경로입니다.

    Raises:
        FileNotFoundError: 사용 가능한 Chrome 또는 Edge 브라우저를 찾지 못했을 때 발생합니다.
        subprocess.CalledProcessError: 헤드리스 브라우저 PDF 변환 명령이 실패했을 때 발생합니다.
    """
    browser = find_browser()
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", suffix=".html", delete=False
    ) as tf:
        tf.write(html_text)
        temp_html = Path(tf.name)
    try:
        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                str(browser),
                "--headless=new",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--print-to-pdf={output_pdf}",
                str(temp_html.resolve()),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    finally:
        if temp_html.exists():
            temp_html.unlink()


def encode_binary_data_uri(raw: bytes, mime: str) -> str:
    """바이너리 데이터를 HTML 임베딩용 base64 data URI로 변환합니다.

    Args:
        raw: 원본 이미지 바이트 열입니다.
        mime: `image/png` 또는 `image/svg+xml` MIME 형식입니다.

    Returns:
        `data:...;base64,...` 문자열입니다.
    """
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def encode_file(path: Path) -> str:
    """이미지 파일(PNG·SVG)을 base64 data URI로 인코딩합니다.

    Args:
        path: 읽을 이미지 파일 경로입니다.

    Returns:
        HTML `<img>` 태그에 넣을 data URI 문자열입니다.
    """
    mime = "image/svg+xml" if path.suffix.lower() == ".svg" else "image/png"
    return encode_binary_data_uri(path.read_bytes(), mime)


def extract_unique_pdf_images(pdf_path: Path) -> list[bytes]:
    """PDF 파일에서 XObject 해시 중복을 제거한 고유 이미지 바이트 목록을 추출합니다.

    Args:
        pdf_path: 이미지를 추출할 원본 PDF 경로입니다.

    Returns:
        문서 등장 순서대로 추출한 고유 이미지 바이트 리스트입니다.
    """
    reader = pypdf.PdfReader(str(pdf_path))
    seen: set[str] = set()
    unique: list[bytes] = []
    for page in reader.pages:
        for img in page.images:
            raw = bytes(img.data)
            digest = hashlib.sha256(raw).hexdigest()
            if digest not in seen:
                seen.add(digest)
                unique.append(raw)
    return unique


def render_ui_captures_html(
    title: str,
    captures: tuple[UiFixCapture, ...],
    unique_images: list[bytes],
    *,
    side_by_side: bool,
    max_img_height_mm: int,
) -> str:
    """UI 수정 항목의 전/후 비교 캡처 블록 HTML을 조립합니다.

    Args:
        title: alt 속성에 사용할 UI 수정 항목 제목입니다.
        captures: 표시할 고유 캡처 메타데이터 튜플입니다.
        unique_images: 원본 PDF에서 추출한 고유 PNG 바이트 리스트입니다.
        side_by_side: 2열 나란히 배치하면 True, 세로 적층이면 False입니다.
        max_img_height_mm: 캡처 이미지 최대 높이(mm)입니다.

    Returns:
        캡처 그리드 HTML 문자열입니다. 캡처가 없으면 빈 문자열입니다.
    """
    if not captures:
        return ""
    layout_class = "ui-cap-grid" if side_by_side else "ui-cap-stack"
    capture_blocks = "\n".join(
        f"""    <div>
      <div class="ui-cap-label">{html.escape(cap.label)}</div>
      <div class="ui-img-box">
        <img src="{encode_binary_data_uri(unique_images[cap.unique_index], 'image/png')}"
             alt="{html.escape(title + ' - ' + cap.label)}"
             style="max-height: {max_img_height_mm}mm;">
      </div>
    </div>"""
        for cap in captures
    )
    return f'\n  <div class="{layout_class}">\n{capture_blocks}\n  </div>'


def build_ui_item_card_html(item: UiFixItem, unique_images: list[bytes]) -> str:
    """UI 수정 보고서 개별 항목 카드 HTML을 원문 무수정으로 조립합니다.

    Args:
        item: UI 수정 항목 원문 메타데이터입니다.
        unique_images: 원본 PDF에서 추출한 고유 이미지 바이트 목록입니다.

    Returns:
        항목 표·원칙 주석·원본 캡처가 포함된 HTML 카드 문자열입니다.
    """
    detail_rows = "\n".join(
        f"""      <tr>
        <th>{html.escape(label)}</th>
        <td>{html.escape(text)}</td>
      </tr>"""
        for label, text in item.detail_rows
    )
    note_html = (
        f'  <div class="ui-extra-note">- {html.escape(item.rule_note)}</div>'
        if item.rule_note
        else ""
    )
    captures_html = render_ui_captures_html(
        item.title,
        item.captures,
        unique_images,
        side_by_side=item.side_by_side,
        max_img_height_mm=item.max_img_height_mm,
    )

    return f"""  <div class="ui-item-card">
    <h3 class="ui-item-head">{html.escape(item.title)}</h3>
    <table class="ui-meta-table">
{detail_rows}
    </table>
{note_html}{captures_html}
  </div>"""


def build_ui_detail_pages_html(
    items: tuple[UiFixItem, ...],
    page_groups: tuple[tuple[str, ...], ...],
    unique_images: list[bytes],
    *,
    report_date: str,
    subtitle: str,
) -> str:
    """UI 수정 보고서 상세 항목 페이지들을 그룹별로 생성합니다.

    Args:
        items: UI 수정 항목 원문 튜플입니다.
        page_groups: A4 1페이지에 함께 배치할 항목 코드 묶음입니다.
        unique_images: 원본 PDF에서 추출한 고유 이미지 바이트 목록입니다.
        report_date: 페이지 상단 헤더에 표기할 보고서 날짜(예: `2026-11-19`)입니다.
        subtitle: 페이지 상단 부제목 문자열입니다.

    Returns:
        페이지 나눔이 포함된 상세 내역 HTML 문자열입니다.
    """
    by_code = {item.code: item for item in items}
    pages: list[str] = []
    for group in page_groups:
        cards = "\n".join(
            build_ui_item_card_html(by_code[code], unique_images) for code in group
        )
        label = (
            group[0].replace("*", "")
            if len(group) == 1
            else f"{group[0].replace('*', '')} ~ {group[-1].replace('*', '')}"
        )
        pages.append(
            f"""<div class="page-break">
  <div class="att-header">
    <h2>[별첨 2] UI 수정 보고서 ({html.escape(report_date)}) · 상세 내역 ({html.escape(label)})</h2>
    <p class="att-meta">{html.escape(subtitle)}</p>
  </div>
{cards}
</div>"""
        )
    return "\n\n".join(pages)
