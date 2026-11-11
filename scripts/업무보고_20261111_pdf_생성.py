"""11월 11일 업무보고 PDF 생성 스크립트입니다.

1페이지: 컴공 2학년 학부생 '연승현' 톤의 11/11 업무보고 메인 표 (팀원 '기민 님' 호칭 준수, 민원 LLM 테스트 중심)
2~4페이지: 기민 님이 11/11 새로 작성한 'UI_변경_2026-11-11.pdf' (3페이지) 원본 그대로 첨부 및 병합
"""

from __future__ import annotations

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

UI_CHANGE_PDF_CANDIDATES = (
    Path(r"C:\Users\user\Documents\카카오톡 받은 파일\UI_변경_2026-11-11.pdf"),
    Path(r"C:\Users\user\Desktop\RISK\ai-complaint-process\docs\UI_변경_2026-11-11.pdf"),
    Path(__file__).resolve().parent.parent / "docs" / "UI_변경_2026-11-11.pdf",
)

OUTPUT_PDF_PATH_1 = Path(r"C:\Users\user\Documents\카카오톡 받은 파일\업무보고_20261111.pdf")
OUTPUT_PDF_PATH_2 = Path(r"C:\Users\user\Desktop\RISK\ai-complaint-process\docs\업무보고_20261111.pdf")


def build_page1_html() -> str:
    """1페이지 업무보고 메인 표 HTML을 생성합니다.

    Returns:
        1페이지 완결형 HTML 문자열입니다.
    """
    return """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>업무보고 (11/11)</title>
<style>
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
    letter-spacing: -0.35px;
    -webkit-print-color-adjust: exact;
  }
  h1.title {
    text-align: center;
    font-size: 19pt;
    font-weight: 800;
    margin: 0 0 9px 0;
    letter-spacing: 3px;
  }
  table.report-table {
    width: 100%;
    border-collapse: collapse;
    border: 1.2px solid #222;
  }
  table.report-table th,
  table.report-table td {
    border: 1px solid #333;
    padding: 4.5px 7.5px;
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
    margin-top: 2.5px;
    margin-bottom: 1px;
    color: #000;
  }
  .section-title:first-child {
    margin-top: 0;
  }
  .bullet-item {
    margin: 1.2px 0;
    padding-left: 10px;
    text-indent: -10px;
    word-break: keep-all;
  }
  .highlight-tag {
    font-weight: bold;
    color: #0f766e;
  }
</style>
</head>
<body>

<h1 class="title">업무보고</h1>

<table class="report-table">
  <tr>
    <td class="header-label">보고 기간</td>
    <td class="header-val">2026-11-11 (수)</td>
    <td class="header-label">작성자</td>
    <td class="header-val">연승현</td>
  </tr>
  <tr>
    <td class="header-label">프로젝트</td>
    <td class="header-val">산학공동프로젝트 (AI 민원 시스템)</td>
    <td class="header-label">담당</td>
    <td class="header-val">서버, AI</td>
  </tr>
  <tr>
    <td class="header-label">목적(목표)</td>
    <td colspan="3">민원 데이터 기반 LLM 판정 및 응답 품질 집중 테스트, 장소 기반 부서 추천 검증, 기민 님 신규 UI 변경 사항 점검</td>
  </tr>
  <tr>
    <td class="header-label">주제</td>
    <td colspan="3">산학공동프로젝트 서버, AI 업무 보고 (11/11)</td>
  </tr>
  <tr>
    <td class="label-cell">담당 업무<br>(전체)</td>
    <td colspan="3" class="full-val">
      <div class="section-title">1. 서버 &amp; 검색</div>
      <div class="bullet-item">- 청주시 민원 데이터(FAQ, 공개 민원 사례) 수집 및 검색 DB 구축</div>
      <div class="bullet-item">- 키워드 및 문맥 유사도 검색으로 비슷한 민원과 담당 부서를 찾아주는 서버 API 제작</div>
      <div class="bullet-item">- 민원 접수·조회 백엔드 서버(Flask) 개발 및 기민 님 측 화면과 연결 준비</div>
      <div class="section-title">2. AI &amp; 테스트 웹</div>
      <div class="bullet-item">- 검색된 자료를 바탕으로 AI가 답변이나 담당 부서를 판단하는 로직 작성</div>
      <div class="bullet-item">- AI에게 보낼 프롬프트(지시문) 설계 및 LLM 모델 연동</div>
      <div class="bullet-item">- AI 응답 결과를 바로 확인해볼 수 있는 테스트 페이지(검사기 웹) 개발 (마감 2026-11-27)</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">진행 내용<br>(11/11)</td>
    <td colspan="3" class="full-val">
      <div class="section-title">1. 민원 유형별 LLM 응답 품질 및 판정 정확도 집중 테스트</div>
      <div class="bullet-item">- <span class="highlight-tag">FAQ 기반 절차 안내 테스트</span> : 청주시 공식 FAQ(94건) 기반의 절차·서류 문의에 대해 AI가 거짓 정보(환각) 없이 실제 안내 조건을 온전히 보존하여 응답하는지 집중 검증 (불필요한 자동 안내 남발 방지 및 조건 적합성 확인)</div>
      <div class="bullet-item">- <span class="highlight-tag">현장 조치형 민원 부서 매칭 테스트</span> : 도로 파손, 불법 쓰레기 등 실제 조치가 필요한 민원에 대해 과거 공개 사례(5,015건)를 바탕으로 관할 부서 후보를 올바르게 추천하는지 케이스별 테스트</div>
      <div class="bullet-item">- <span class="highlight-tag">네이버 지도 장소 추적 도구(lookup_navermap_place) 실사례 검증</span> : 본문에 '성안길', '육거리시장', '오창호수공원' 등 상호·장소명만 들어간 민원에서 네이버 지도 검색을 통해 상당구, 청원구 등 청주시 4개 구를 정확히 판별하고 관할 구청 부서로 연결되는지 동작 확인</div>
      <div class="section-title">2. AI 판정 결과 및 프롬프트 안정성 점검</div>
      <div class="bullet-item">- <span class="highlight-tag">출력 JSON 규격 검증</span> : AI 모델이 반환하는 JSON 데이터(판정 결과, 추천 부서 ID, 처리 사유 등)가 백엔드 정책 검사기에서 오류 없이 파싱되고 계약 규격을 준수하는지 반복 확인</div>
      <div class="bullet-item">- <span class="highlight-tag">응답 시간 및 예외 처리 점검</span> : 긴 문장의 민원이나 특이 표현이 포함된 입력에서도 타임아웃이나 서버 멈춤 없이 안정적으로 동작하는지 점검</div>
      <div class="section-title">3. 팀 협업 및 기민 님 11/11 UI 변경 사항 확인</div>
      <div class="bullet-item">- <span class="highlight-tag">신규 담당자 UI 변경 확인</span> : 기민 님이 오늘 새로 업데이트한 UI 변경 내역(담당자 목록 행별 '접수 N일째' 경과일 표시, 편집기 글자 수 카운터, 자주 쓰는 문구 삽입 단추 5개, Ctrl+S 단축키, 처리 이력 접힘 상태 통일 등) 확인 및 백엔드 데이터 연동 호환성 점검 (첨부 2~4페이지 수록)</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">진행 결과</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- <span class="highlight-tag">LLM 판정 품질</span> : FAQ 기반 안내와 부서 추천 판정이 안정적으로 동작하며, 장소명 기반 민원에서도 관할 구청 부서가 정확하게 매칭됨을 확인</div>
      <div class="bullet-item">- <span class="highlight-tag">시스템 안정성</span> : 다양한 민원 케이스 반복 테스트 중 JSON 문법 오류나 서버 다운 없이 안정적인 응답 속도 유지</div>
      <div class="bullet-item">- <span class="highlight-tag">UI 변경 호환성</span> : 기민 님이 추가한 담당자 편의 기능(접수 경과일, 글자 수, 단축키 등)과 백엔드 민원 데이터 처리 규격이 문제없이 호환됨을 확인</div>
      <div class="bullet-item">- <span class="highlight-tag">코드 무결성</span> : 기존 백엔드 121개 테스트 및 자바스크립트 문법/단위 테스트 모두 100% 정상 통과 상태 유지</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">남은 일</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- 기민 님의 개선된 담당자 UI(단축키, 글자 수 카운터 등)와 백엔드 실제 초안 저장/게시 API 최종 연동 테스트</div>
      <div class="bullet-item">- AI 판정 결과를 실제 민원 처리 화면에 단계별로 자연스럽게 노출하는 방안 협의</div>
      <div class="bullet-item">- 최종 프로젝트 시연 및 발표 자료/시나리오 준비 (최종 마감 2026-11-27)</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">참고 사항</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- 역할 분담 : 기민 님 / UI와 DB, 승현 / 서버와 AI (기존 보고와 동일)</div>
      <div class="bullet-item">- 오늘은 대규모 신규 기능 추가 대신 어제까지 구현된 기능들의 LLM 응답 품질 및 장소 기반 부서 매칭 집중 테스트를 진행함</div>
      <div class="bullet-item">- 기민 님이 11일에 새로 작업한 화면별 상세 변경 내역은 <strong>[첨부 자료: 2~4페이지]</strong>의 'UI 변경 보고서'에 원본 그대로 수록함</div>
    </td>
  </tr>
</table>

</body>
</html>
"""


def find_browser() -> Path:
    """Chrome 또는 Edge 브라우저 실행 파일 경로를 탐색합니다.

    Returns:
        브라우저 실행 파일 경로입니다.

    Raises:
        FileNotFoundError: 브라우저 실행 파일을 찾을 수 없는 경우 발생합니다.
    """
    for candidate in CHROME_CANDIDATES:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Chrome 또는 Edge 실행 파일을 찾을 수 없습니다.")


def find_ui_change_pdf() -> Path:
    """기민 님의 11/11 UI 변경 보고서 PDF 경로를 탐색합니다.

    Returns:
        존재하는 UI 변경 보고서 PDF 경로입니다.

    Raises:
        FileNotFoundError: 후보 경로 중 존재하는 파일이 없을 때 발생합니다.
    """
    for candidate in UI_CHANGE_PDF_CANDIDATES:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("11/11 UI 변경 보고서 PDF를 찾을 수 없습니다.")


def render_html_to_pdf(html_text: str, output_pdf: Path) -> None:
    """HTML 문자열을 헤드리스 브라우저를 통해 PDF 파일로 렌더링합니다.

    Args:
        html_text: 렌더링할 HTML 내용입니다.
        output_pdf: 저장할 PDF 파일 경로입니다.
    """
    browser = find_browser()
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".html", delete=False) as tf:
        tf.write(html_text)
        temp_html = Path(tf.name)

    try:
        cmd = [
            str(browser),
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={output_pdf}",
            str(temp_html.resolve()),
        ]
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    finally:
        if temp_html.exists():
            temp_html.unlink()


def generate_report_pdf() -> None:
    """1페이지 업무보고와 3페이지 UI 변경 보고서를 병합하여 최종 보고서 PDF를 생성합니다.

    Raises:
        FileNotFoundError: 브라우저 실행 파일 또는 원본 UI 변경 PDF가 없는 경우 발생합니다.
        subprocess.CalledProcessError: 헤드리스 브라우저 PDF 출력 프로세스 실패 시 발생합니다.
    """
    print("1. 11/11 업무보고 1페이지 HTML 렌더링 중...")
    page1_html = build_page1_html()

    temp_page1_pdf = Path(tempfile.gettempdir()) / "page1_report_1111_temp.pdf"
    render_html_to_pdf(page1_html, temp_page1_pdf)
    print(f"   -> 1페이지 임시 PDF 생성 완료: {temp_page1_pdf} ({temp_page1_pdf.stat().st_size} bytes)")

    print("2. 기민 님 11/11 UI 변경 보고서 PDF 확인 중...")
    ui_pdf_path = find_ui_change_pdf()
    print(f"   -> UI 변경 보고서 경로: {ui_pdf_path}")

    reader_page1 = pypdf.PdfReader(str(temp_page1_pdf))
    print(f"   -> 1페이지 PDF 페이지 수: {len(reader_page1.pages)}")

    reader_ui = pypdf.PdfReader(str(ui_pdf_path))
    print(f"   -> UI 변경 보고서 페이지 수: {len(reader_ui.pages)}")

    print(f"3. PDF 병합 중 (1페이지 + UI 변경 {len(reader_ui.pages)}페이지 = 총 {len(reader_page1.pages) + len(reader_ui.pages)}페이지)...")
    writer = pypdf.PdfWriter()

    # 1페이지 추가
    writer.add_page(reader_page1.pages[0])

    # 기민 님 UI 변경 보고서 페이지들 추가
    for page in reader_ui.pages:
        writer.add_page(page)

    # 출력 경로들에 저장
    for out_path in (OUTPUT_PDF_PATH_1, OUTPUT_PDF_PATH_2):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as f:
            writer.write(f)
        print(f"   -> 최종 PDF 저장 완료: {out_path} ({out_path.stat().st_size} bytes, 총 {len(writer.pages)}쪽)")

    # 임시 파일 정리
    if temp_page1_pdf.exists():
        temp_page1_pdf.unlink()

    print("11/11 업무보고서 PDF 생성이 성공적으로 완료되었습니다!")


if __name__ == "__main__":
    generate_report_pdf()
