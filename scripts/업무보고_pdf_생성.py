"""11월 9일 업무보고 PDF 생성 스크립트입니다. (스크린샷 첨부 자료 포함)

컴공 2학년 학부생 '연승현' 톤의 업무보고 표와 함께,
최근 개선된 기능(진행 상태 표시, 프롬프트 전문, JSON 복사)의
실제 캡처 스크린샷 3장을 [첨부 자료]로 포함하여 PDF를 재구성합니다.
팀원 호칭은 '기민 님'으로 정중하게 표기합니다.
"""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

CHROME_CANDIDATES = (
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path.home() / r"AppData\Local\Google\Chrome\Application\chrome.exe",
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
)

SCREENSHOT_PATHS = [
    Path(r"C:\Users\user\Pictures\Screenshots\스크린샷(115).png"),
    Path(r"C:\Users\user\Pictures\Screenshots\스크린샷(116).png"),
    Path(r"C:\Users\user\Pictures\Screenshots\스크린샷(117).png"),
]


def encode_image(path: Path) -> str:
    """이미지 파일을 base64 data URI 문자열로 변환합니다.

    Args:
        path: 읽을 이미지 파일 경로입니다.

    Returns:
        `data:image/png;base64,...` 형식의 문자열입니다.
    """
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def build_html() -> str:
    """스크린샷을 인라인 임베딩한 전체 HTML 보고서를 조립합니다.

    Returns:
        완성된 단일/다중 페이지 HTML 문자열입니다.
    """
    img1 = encode_image(SCREENSHOT_PATHS[0])
    img2 = encode_image(SCREENSHOT_PATHS[1])
    img3 = encode_image(SCREENSHOT_PATHS[2])

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>업무보고 (11/09)</title>
<style>
  @page {{
    size: A4 portrait;
    margin: 11mm 14mm 11mm 14mm;
  }}
  * {{
    box-sizing: border-box;
  }}
  body {{
    font-family: "Malgun Gothic", "맑은 고딕", Dotum, sans-serif;
    color: #111;
    margin: 0;
    padding: 0;
    font-size: 9.1pt;
    line-height: 1.44;
    letter-spacing: -0.3px;
    -webkit-print-color-adjust: exact;
  }}

  /* 1페이지: 업무보고 메인 표 */
  .page-main {{
    page-break-after: always;
  }}
  h1.title {{
    text-align: center;
    font-size: 20pt;
    font-weight: 800;
    margin: 0 0 12px 0;
    letter-spacing: 3px;
  }}
  table.report-table {{
    width: 100%;
    border-collapse: collapse;
    border: 1.2px solid #222;
  }}
  table.report-table th,
  table.report-table td {{
    border: 1px solid #333;
    padding: 5px 8px;
  }}
  .label-cell {{
    width: 15%;
    text-align: center;
    font-weight: bold;
    vertical-align: middle;
    background-color: #ffffff;
    line-height: 1.35;
  }}
  .header-label {{
    width: 15%;
    text-align: center;
    font-weight: bold;
    background-color: #ffffff;
    white-space: nowrap;
  }}
  .header-val {{
    width: 35%;
  }}
  .full-val {{
    width: 85%;
    vertical-align: top;
  }}
  .section-title {{
    font-weight: bold;
    margin-top: 3px;
    margin-bottom: 1.5px;
    color: #000;
  }}
  .section-title:first-child {{
    margin-top: 0;
  }}
  .bullet-item {{
    margin: 1.5px 0;
    padding-left: 11px;
    text-indent: -11px;
    word-break: keep-all;
  }}

  /* 2페이지: 첨부 자료 */
  .page-attachment {{
    page-break-before: always;
  }}
  h2.attachment-title {{
    font-size: 13.5pt;
    font-weight: 800;
    margin: 0 0 4px 0;
    color: #111;
    border-bottom: 2px solid #222;
    padding-bottom: 5px;
  }}
  p.attachment-desc {{
    font-size: 8.6pt;
    color: #555;
    margin: 0 0 10px 0;
  }}

  .grid-container {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-bottom: 10px;
  }}

  .card {{
    border: 1px solid #bbb;
    border-radius: 4px;
    background: #fafafa;
    padding: 7px;
    display: flex;
    flex-direction: column;
  }}
  .card.full {{
    grid-column: 1 / -1;
    width: 84%;
    margin: 0 auto;
    background: #fdfdfd;
  }}

  .card-header {{
    margin-bottom: 5px;
    font-size: 8.7pt;
    font-weight: bold;
    display: flex;
    align-items: center;
    gap: 6px;
  }}
  .badge {{
    background: #087f72;
    color: #fff;
    padding: 1.5px 6px;
    border-radius: 3px;
    font-size: 7.5pt;
    font-weight: bold;
  }}
  .img-box {{
    border: 1px solid #ddd;
    border-radius: 3px;
    overflow: hidden;
    background: #fff;
    text-align: center;
  }}
  .img-box img {{
    width: 100%;
    height: auto;
    display: block;
  }}
  .card-caption {{
    margin-top: 5px;
    font-size: 8pt;
    color: #333;
    line-height: 1.35;
    word-break: keep-all;
  }}
</style>
</head>
<body>

<!-- 1페이지 -->
<div class="page-main">
  <h1 class="title">업무보고</h1>

  <table class="report-table">
    <tr>
      <td class="header-label">보고 기간</td>
      <td class="header-val">2026-11-09 (월)</td>
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
      <td colspan="3">AI 민원 테스트 페이지 기능 개선(지역 자동 인식, 진행 상태 표시, 프롬프트 확인) 및 서버 점검 보고</td>
    </tr>
    <tr>
      <td class="header-label">주제</td>
      <td colspan="3">산학공동프로젝트 서버, AI 업무 보고 (11/09)</td>
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
      <td class="label-cell">진행 내용<br>(11/9)</td>
      <td colspan="3" class="full-val">
        <div class="section-title">1. AI 테스트 페이지 기능 개선</div>
        <div class="bullet-item">- 지역 자동 인식 기능 추가 : 사용자가 지역을 안 골라도 제목이나 본문에 '가경동', '오송읍' 같은 동네 이름이 있으면 알아서 청주시 4개 구(상당·서원·흥덕·청원)를 찾아 검색에 반영하도록 구현</div>
        <div class="bullet-item">- 청주 전체 지역 선택 지원 : 드롭다운에서 청주시 4개 구와 그 아래 모든 동/읍/면을 직접 고를 수 있게 선택지 추가</div>
        <div class="bullet-item">- AI 생각하는 과정(로딩) 표시 : 민원을 보내면 '내용 읽는 중 → 자료 찾는 중 → 검토 중' 단계별로 로딩 애니메이션과 진행 문구가 뜨도록 수정 [첨부자료 1]</div>
        <div class="bullet-item">- AI에게 보낸 프롬프트 원문 보기 : AI 모델에게 실제로 전달된 질문과 지시문 전체를 화면에서 바로 확인하고 복사할 수 있는 칸 추가 [첨부자료 2]</div>
        <div class="bullet-item">- 결과 JSON 복사 단추 추가 : 화면에 나온 응답 데이터들을 클릭 한 번으로 복사할 수 있게 버튼 배치 [첨부자료 3]</div>
        <div class="section-title">2. 코드 정리 및 테스트</div>
        <div class="bullet-item">- 작성한 파이썬 코드들에 한글 설명 주석 추가 및 함수 정리</div>
        <div class="bullet-item">- 동네 이름 찾는 로직 속도 개선 (지역이 여러 개 겹치면 바로 걸러내도록 최적화)</div>
        <div class="bullet-item">- 테스트 코드 작성 및 실행 검사 (테스트 전체 오류 없이 통과 확인)</div>
        <div class="bullet-item">- GitHub에 오늘 작업한 코드 커밋 및 푸시 완료</div>
        <div class="section-title">3. 팀 공유</div>
        <div class="bullet-item">- 기민 님께 바뀐 검색 필터(지역 값)와 API 내용 공유 준비</div>
      </td>
    </tr>
    <tr>
      <td class="label-cell">진행 결과</td>
      <td colspan="3" class="full-val">
        <div class="bullet-item">- AI 테스트 웹 : 본문에서 동네 이름 자동 인식, 로딩 애니메이션, 프롬프트 원문 확인, JSON 복사 기능 모두 정상 동작</div>
        <div class="bullet-item">- 검색 정확도 : 본문에 적힌 동네 이름(예: 가경동, 복대동)을 파악해서 해당 구 민원만 걸러주므로 엉뚱한 부서 추천이 크게 줄어듦</div>
        <div class="bullet-item">- 코드 검사 : 테스트 모두 통과 (에러 없음), 깃허브 업로드 완료</div>
      </td>
    </tr>
    <tr>
      <td class="label-cell">남은 일</td>
      <td colspan="3" class="full-val">
        <div class="bullet-item">- 기민 님이 만든 DB 테이블(8개) 및 샘플 데이터(35건) 구조 확인하고 서버 연결 방법 상의</div>
        <div class="bullet-item">- AI 답변 신뢰도 점수를 어떻게 넘겨줄지 기민 님과 포맷 맞추기</div>
        <div class="bullet-item">- 테스트 페이지 말고 실제 민원 게시판 화면에 AI 추천 기능 붙이기</div>
        <div class="bullet-item">- 서버 실제 배포 환경 알아보기</div>
        <div class="bullet-item">- 최종 시연 준비 및 문서 정리 (최종 마감 2026-11-27)</div>
      </td>
    </tr>
    <tr>
      <td class="label-cell">참고 사항</td>
      <td colspan="3" class="full-val">
        <div class="bullet-item">- 역할 분담 : 기민 님 / UI와 DB, 승현 / 서버와 AI (기존 보고와 동일)</div>
        <div class="bullet-item">- 테스트 페이지는 기존 시연 화면과 포트(5010 / 5000)를 따로 써서 서로 충돌 없이 작업 중</div>
        <div class="bullet-item">- 본문에서 지역 찾는 기능은 AI를 쓰지 않고 단어 사전 매칭으로 짜서 속도가 매우 빠르고 비용이 안 듦</div>
      </td>
    </tr>
  </table>
</div>

<!-- 2페이지: 첨부 자료 -->
<div class="page-attachment">
  <h2 class="attachment-title">[첨부 자료] AI 응대 검사기 주요 개선 기능 및 테스트 화면</h2>
  <p class="attachment-desc">
    11월 9일 진행한 AI 응대 검사기 웹(테스트 페이지) 기능 개선 사항의 실제 동작 캡처 화면입니다.
  </p>

  <div class="grid-container">
    <!-- 자료 1 -->
    <div class="card">
      <div class="card-header">
        <span class="badge">자료 1</span>
        <span>실시간 진행 상태 안내 및 다단계 애니메이션</span>
      </div>
      <div class="img-box">
        <img src="{img1}" alt="자료 1: 실시간 진행 상태 안내">
      </div>
      <div class="card-caption">
        민원 전송 시 AI 응답 대기 시간 동안 '내용 읽기 → 자료 검색 → 검토' 단계가 실시간 체크 표시되며, 우측에 최근 테스트 기록 목록이 실시간으로 관리됩니다.
      </div>
    </div>

    <!-- 자료 2 -->
    <div class="card">
      <div class="card-header">
        <span class="badge">자료 2</span>
        <span>AI 모델(Codex) 프롬프트 전문 확인 및 복사</span>
      </div>
      <div class="img-box">
        <img src="{img2}" alt="자료 2: 프롬프트 전문 확인">
      </div>
      <div class="card-caption">
        AI 모델에게 실제로 전달된 시스템 지시문(공통 헌법 PREFIX-00+01)과 사용자 JSON 전문을 호출별로 투명하게 확인하고 원클릭 복사할 수 있습니다.
      </div>
    </div>

    <!-- 자료 3 -->
    <div class="card full">
      <div class="card-header">
        <span class="badge">자료 3</span>
        <span>입출력 JSON 데이터 확인 및 원클릭 복사 기능</span>
      </div>
      <div class="img-box">
        <img src="{img3}" alt="자료 3: 입출력 JSON 확인">
      </div>
      <div class="card-caption">
        검사기 웹에 전송된 민원 JSON 원문과 검색·판정 결과(추천 부서, 근거 사례 등)를 화면에서 확인하고 복사할 수 있어 다른 팀원(기민 님)과의 데이터 포맷 공유가 편리합니다.
      </div>
    </div>
  </div>
</div>

</body>
</html>
"""


def find_browser() -> Path:
    """Chrome 또는 Edge 실행 파일 경로를 찾습니다.

    Returns:
        존재하는 브라우저 실행 파일 경로입니다.

    Raises:
        FileNotFoundError: 후보 경로 중 브라우저가 하나도 없을 때 발생합니다.
    """
    for p in CHROME_CANDIDATES:
        if p.is_file():
            return p
    raise FileNotFoundError("Chrome 또는 Edge 브라우저를 찾을 수 없습니다.")


def generate_pdf(output_paths: list[Path]) -> None:
    """HTML 문서를 Chrome headless로 PDF로 변환하여 출력 경로들에 저장합니다.

    Args:
        output_paths: 저장할 대상 PDF 파일 경로 목록입니다.

    Raises:
        FileNotFoundError: 생성된 임시 PDF 파일이 없을 때 발생합니다.
        RuntimeError: 브라우저 PDF 변환 프로세스가 실패했을 때 발생합니다.
    """
    browser = find_browser()
    html_content = build_html()

    with tempfile.TemporaryDirectory() as tmpdir:
        html_path = Path(tmpdir) / "report.html"
        pdf_path = Path(tmpdir) / "report.pdf"
        html_path.write_text(html_content, encoding="utf-8")

        cmd = [
            str(browser),
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={pdf_path}",
            str(html_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"브라우저 PDF 변환 실패: {res.stderr}")

        if not pdf_path.is_file():
            raise FileNotFoundError("생성된 PDF 파일을 찾을 수 없습니다.")

        for out_path in output_paths:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(pdf_path, out_path)
            print(f"생성 완료: {out_path} ({out_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    targets = [
        Path(r"C:\Users\user\Documents\카카오톡 받은 파일\업무보고_20261109.pdf"),
        Path(r"docs\업무보고_20261109.pdf"),
    ]
    generate_pdf(targets)
