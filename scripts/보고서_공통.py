"""보고서 HTML을 헤드리스 브라우저 PDF로 변환하는 공용 유틸리티입니다.

`업무보고_20261116_pdf_생성.py`와 `상세분석보고서_112건_생성.py`가 같은
브라우저 탐색 및 A4 인쇄 경로를 공유합니다. 직접 실행하지 않는 공용 모듈입니다.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile

CHROME_CANDIDATES = (
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path.home() / r"AppData\Local\Google\Chrome\Application\chrome.exe",
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
)


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
