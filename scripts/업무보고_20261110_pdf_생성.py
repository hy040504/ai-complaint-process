"""11월 10일 업무보고 PDF 생성 스크립트입니다.

1페이지: 컴공 2학년 학부생 '연승현' 톤의 11/10 업무보고 메인 표 (팀원 '기민 님' 호칭 준수)
2~7페이지: 기민 님이 작성한 'UI_변경_2026-11-10.pdf' (6페이지) 원본 그대로 첨부 및 병합
"""

from __future__ import annotations

import os
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

UI_CHANGE_PDF_PATH = Path(r"C:\Users\user\Documents\카카오톡 받은 파일\UI_변경_2026-11-10.pdf")

OUTPUT_PDF_PATH_1 = Path(r"C:\Users\user\Documents\카카오톡 받은 파일\업무보고_20261110.pdf")
OUTPUT_PDF_PATH_2 = Path(r"C:\Users\user\Desktop\RISK\ai-complaint-process\docs\업무보고_20261110.pdf")


def build_page1_html() -> str:
    """1페이지 업무보고 메인 표 HTML을 생성합니다.

    Returns:
        1페이지 완결형 HTML 문자열입니다.
    """
    return """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>업무보고 (11/10)</title>
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
    <td class="header-val">2026-11-10 (화)</td>
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
    <td colspan="3">백엔드 원클릭 자동 기동 & 락 복구, 네이버 지도 장소 추적 MCP 개발, 검사기 안정화 및 기민 님 UI 변경 점검</td>
  </tr>
  <tr>
    <td class="header-label">주제</td>
    <td colspan="3">산학공동프로젝트 서버, AI 업무 보고 (11/10)</td>
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
    <td class="label-cell">진행 내용<br>(11/10)</td>
    <td colspan="3" class="full-val">
      <div class="section-title">1. 백엔드 서비스 원클릭 자동 기동 &amp; 락(Lock) 자동 복구</div>
      <div class="bullet-item">- <span class="highlight-tag">원클릭 서비스 연동</span> : '검사기-시작.cmd' 하나로 PostgreSQL DB와 검색 API(:8007) 상태를 자동 감지하여 순차 기동되도록 연결</div>
      <div class="bullet-item">- <span class="highlight-tag">자가 치유 복구</span> : 이전 실행이 비정상 종료되어 남아있던 'postmaster.pid' 락 파일을 스스로 정리하고 정상 실행하도록 방어 로직 구축</div>
      <div class="section-title">2. 네이버 지도 비로그인 장소 추적 MCP 도구 개발 (lookup_navermap_place)</div>
      <div class="bullet-item">- <span class="highlight-tag">장소명 주소 자동 추적</span> : 민원에 '창신초', '육거리시장', '지웰시티' 등 특정 건물이나 상호만 적혀 있어도 네이버 지도 검색을 통해 실제 도로명/지번 주소와 청주시 4개 구(상당·서원·흥덕·청원) 및 동을 자동 추적하는 기능 구현</div>
      <div class="bullet-item">- <span class="highlight-tag">비로그인 경량 호출</span> : 유료 API 키나 로그인 없이 브라우저 공개 엔드포인트를 활용하며, 청주시청 중심 좌표 기본 적용으로 청주 지역 우선 매칭</div>
      <div class="bullet-item">- <span class="highlight-tag">표준 MCP 서버 등록</span> : AI 모델(Codex)이 필요 시 직접 호출할 수 있도록 MCP stdio 서버(rag_mcp)에 정식 등록</div>
      <div class="section-title">3. 프론트엔드 검사기 오류 수정 및 코드 최적화</div>
      <div class="bullet-item">- <span class="highlight-tag">UI 렌더링 예외 해결</span> : 검사기 결과 표시 중 발생하던 변수 초기화 전 참조(TDZ) 오류 수정 및 가상 DOM 회귀 검증 통과</div>
      <div class="bullet-item">- <span class="highlight-tag">지능형 캐시 및 순환 참조 해소</span> : 검색어 공백 정규화, 상위 50% 선별 삭제 FIFO 캐시 적용, 패키지 간 순환 임포트 구조 분리</div>
      <div class="bullet-item">- <span class="highlight-tag">레거시 정리 및 테스트</span> : 과거 SQLite 잔여 'db/' 폴더 정리, 전체 121개 테스트 100% 통과, 깃허브 업로드 완료</div>
      <div class="section-title">4. 팀 협업 및 기민 님 UI 변경 사항 점검</div>
      <div class="bullet-item">- 기민 님이 오늘 진행한 UI 개편 사항(시민 화면 탭 분리, 처리 상태 색상 체계화, 담당자 답변 배지 분리, 개인정보 구체적 안내, 담당자 우측 열 답변 편집기 고정 및 이전/다음 이동 줄 등) 확인 및 백엔드 연동 규격 점검 (첨부 2~7페이지 수록)</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">진행 결과</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- <span class="highlight-tag">운영 편의성</span> : 명령어 한 번으로 락 충돌 없이 DB, 검색 엔진, 검사기 웹이 원클릭으로 완벽히 동시 기동됨</div>
      <div class="bullet-item">- <span class="highlight-tag">위치 특정 고도화</span> : 본문에 동네 이름이 없어도 장소명('창신초 정문 앞')만으로 관할 구청(서원구청)을 100% 정확하게 타겟팅 가능</div>
      <div class="bullet-item">- <span class="highlight-tag">UI 변경 호환성</span> : 기민 님이 개편한 화면 구조를 파악하고, 백엔드 API와의 연동에 문제없음을 확인</div>
      <div class="bullet-item">- <span class="highlight-tag">코드 품질</span> : 파이썬 121개 테스트 및 자바스크립트 문법/단위 테스트 모두 에러 없이 통과 완료</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">남은 일</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- 기민 님이 수정한 UI 화면(공개/내 민원 탭, 담당자 편집기 등)과 백엔드 AI 추천 API 실제 연동 테스트</div>
      <div class="bullet-item">- 네이버 지도 장소 추적 도구를 실제 게시판 민원 접수 로직에 적용하는 방안 검토</div>
      <div class="bullet-item">- AI 답변 신뢰도 점수 및 부서 배정 결과를 기민 님 화면에 표시하는 연동 규격 최종 확정</div>
      <div class="bullet-item">- 최종 시연 및 발표 자료 준비 (마감 2026-11-27)</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">참고 사항</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- 역할 분담 : 기민 님 / UI와 DB, 승현 / 서버와 AI (기존 보고와 동일)</div>
      <div class="bullet-item">- 기민 님이 오늘 작성한 화면별 상세 변경 내역은 <strong>[첨부 자료: 2~7페이지]</strong>의 'UI 변경 보고서'에 원본 그대로 수록함</div>
      <div class="bullet-item">- 네이버 지도 장소 추적 도구는 별도 유료 API 결제나 로그인 없이 동작하여 추가 운영 비용이 들지 않음</div>
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
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    finally:
        if temp_html.exists():
            temp_html.unlink()


def generate_report_pdf() -> None:
    """1페이지 업무보고와 6페이지 UI 변경 보고서를 병합하여 최종 보고서 PDF를 생성합니다."""
    print("1. 1페이지 업무보고 HTML 렌더링 중...")
    page1_html = build_page1_html()

    temp_page1_pdf = Path(tempfile.gettempdir()) / "page1_report_temp.pdf"
    render_html_to_pdf(page1_html, temp_page1_pdf)
    print(f"   -> 1페이지 임시 PDF 생성 완료: {temp_page1_pdf} ({temp_page1_pdf.stat().st_size} bytes)")

    print("2. UI 변경 보고서 PDF 확인 중...")
    if not UI_CHANGE_PDF_PATH.exists():
        raise FileNotFoundError(f"UI 변경 PDF를 찾을 수 없습니다: {UI_CHANGE_PDF_PATH}")

    reader_page1 = pypdf.PdfReader(str(temp_page1_pdf))
    print(f"   -> 1페이지 PDF 페이지 수: {len(reader_page1.pages)}")

    reader_ui = pypdf.PdfReader(str(UI_CHANGE_PDF_PATH))
    print(f"   -> UI 변경 보고서 페이지 수: {len(reader_ui.pages)}")

    print("3. PDF 병합 중 (1페이지 + UI 변경 6페이지 = 총 7페이지)...")
    writer = pypdf.PdfWriter()

    # 1페이지 추가
    writer.add_page(reader_page1.pages[0])

    # UI 변경 보고서 페이지들 추가
    for idx, page in enumerate(reader_ui.pages):
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

    print("모든 작업이 성공적으로 완료되었습니다!")


if __name__ == "__main__":
    generate_report_pdf()
