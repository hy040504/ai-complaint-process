"""11월 24일(화) 업무보고 PDF 생성 스크립트입니다.

기존 `업무보고_20261123.pdf`와 같은 틀(1쪽 메인 표 + 별첨)을 따라 한국어로 쉽게 풀어 씁니다.

1페이지: 11/24 업무보고 메인 표
2페이지: [별첨 1] 핵심 수치와 작업 분야별 요약, 상세설명서 구성
3페이지: [별첨 1] AI 민원 처리 파이프라인 그림과 갈래별 결과
4~5페이지: [별첨 2] 민원 AI 처리과정 상세설명서 주요 쪽 캡처 (쪽당 2장)
"""

from __future__ import annotations

from pathlib import Path
import sys

import pypdf

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from report_common import WORK_REPORT_CSS, encode_file, render_html_to_pdf  # noqa: E402

ROOT_DIR = _SCRIPTS_DIR.parents[1]
OUTPUT_PDF_PATH = ROOT_DIR / "docs" / "reports" / "daily" / "업무보고_20261124.pdf"
SOURCE = ROOT_DIR / "docs" / "reports" / "daily" / "source"
MANUAL_PDF = ROOT_DIR / "docs" / "plans" / "민원_AI_처리과정_상세설명서.pdf"

# (페이지를 찾는 글, 저장 파일 이름, 제목, 설명, 자를 시작 글, 자를 끝 글)
# 시작·끝 글을 주면 그 사이 영역만 잘라 글자가 읽히게 크게 싣는다.
MANUAL_SHOTS = (
    (
        "민원을 올리면 AI는 어떻게 처리하나",
        "설명서_표지.png",
        "① 설명서 첫 쪽 · 두 영역으로 나눈 장 구성",
        "제1부(서버·화면)와 제2부(AI 계층)로 나눈 장 구성과 각 장의 핵심입니다.",
        "이 문서를 읽는 법",
        "두 가지 먼저 알아둘 점",
    ),
    (
        "서버와 AI 계층의 경계",
        "설명서_경계.png",
        "② 두 영역의 경계 · 서버와 AI가 주고받는 값",
        "서버가 넘기는 값(질의·구·공급자)과 AI가 돌려주는 값(결과·진행 알림), 책임 구분을 표로 정리했습니다.",
        "서버와 AI 계층의 경계",
        "서버 쪽 호출 지점은",
    ),
    (
        "department_suggestion과 human_handoff 비교",
        "설명서_갈래비교.png",
        "③ 부서 추천과 담당자 검토 비교 (8-1)",
        "두 갈래 모두 담당자 초안을 만들고, 부서 후보·시민 문구·초안 입력이 어떻게 다른지 비교했습니다.",
        "department_suggestion과 human_handoff 비교",
        "8-2. 후속 호출 조건",
    ),
    (
        "1차 판정 뒤 호출 레시피",
        "설명서_케이스레시피.png",
        "④ 케이스별 대응 한눈에 (8-3)",
        "케이스마다 판정 뒤 어떤 시스템 프롬프트로 무엇을 넘기는지, 시민용·담당자용 구분과 함께 보여 줍니다.",
        "8-3. 케이스별 대응 한눈에",
        "8-4. 케이스별 두 번째 로직",
    ),
)

_EXTRA_CSS = """
  .visual-card {
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    background: #ffffff;
    padding: 6px 8px;
    margin-bottom: 7px;
  }
  .visual-cap {
    font-size: 8.6pt;
    font-weight: 800;
    color: #0f172a;
    margin: 0 0 2px 0;
  }
  .visual-sub {
    font-size: 7.7pt;
    color: #475569;
    margin: 0 0 4px 0;
    word-break: keep-all;
  }
  .visual-img-box {
    text-align: center;
    background: #fff;
  }
  .visual-img-box img {
    width: 100%;
    height: auto;
    object-fit: contain;
    display: block;
    margin: 0 auto;
  }
  .pl-lane { border-radius: 6px; padding: 5px 8px 6px; margin-bottom: 6px; }
  .pl-lane.srv { background: #eef1f7; border: 1px solid #c7cfe0; }
  .pl-lane.ai { background: #eaf1ff; border: 1px solid #b6cdf5; }
  .pl-title { font-size: 8.6pt; font-weight: 800; margin: 0 0 3px 0; color: #16203a; }
  .pl-lane.ai .pl-title { color: #1546a8; }
  .pl-step { border: 1px solid #94a3b8; border-radius: 4px; background: #fff; padding: 3px 7px; margin: 3px 0; font-size: 8pt; word-break: keep-all; }
  .pl-step b { color: #0f172a; }
  .pl-arrow { text-align: center; color: #64748b; font-size: 8pt; line-height: 8pt; }
  .pl-branch { display: flex; gap: 5px; margin: 3px 0; }
  .pl-branch > div { flex: 1; border: 1px solid #94a3b8; border-radius: 4px; background: #fff; padding: 3px 6px; font-size: 7.7pt; word-break: keep-all; }
  .tag { display: inline-block; padding: 0 6px; border-radius: 9px; font-size: 7.4pt; font-weight: 700; white-space: nowrap; }
  .tag.cit { background: #e3edff; color: #1546a8; }
  .tag.stf { background: #ffe9d2; color: #a14b00; }
  .tag.int { background: #e8ebf0; color: #444c5a; }
"""


def _render_manual_shots() -> None:
    """상세설명서 PDF에서 주요 쪽을 찾아 캡처 이미지로 저장합니다.

    설명서 PDF가 없거나 변환 도구가 없으면 이미 저장된 이미지를 그대로 씁니다.
    """
    if not MANUAL_PDF.exists():
        return
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return
    from PIL import Image, ImageChops

    scale = 2.0
    reader = pypdf.PdfReader(str(MANUAL_PDF))
    texts = [(page.extract_text() or "") for page in reader.pages]
    document = pdfium.PdfDocument(str(MANUAL_PDF))
    SOURCE.mkdir(parents=True, exist_ok=True)

    def top_px(textpage: object, height: float, key: str) -> float | None:
        """글자가 나오는 위치의 위쪽 가장자리를 화면 픽셀 좌표로 반환합니다."""
        found = textpage.search(key).get_next()  # type: ignore[attr-defined]
        if not found:
            return None
        _left, _bottom, _right, top = textpage.get_charbox(found[0])  # type: ignore[attr-defined]
        return (height - top) * scale

    for key, filename, _title, _desc, start_key, end_key in MANUAL_SHOTS:
        for index, text in enumerate(texts):
            if key not in text:
                continue
            page = document[index]
            image = page.render(scale=scale).to_pil().convert("RGB")
            textpage = page.get_textpage()
            height = page.get_height()
            start = top_px(textpage, height, start_key)
            end = top_px(textpage, height, end_key)
            upper = max(int((start or 0) - 8), 0)
            lower = min(int((end or image.height) - 8), image.height)
            if lower > upper:
                image = image.crop((0, upper, image.width, lower))
            background = Image.new("RGB", image.size, (255, 255, 255))
            box = ImageChops.difference(image, background).getbbox()
            if box:
                pad = 10
                image = image.crop(
                    (
                        max(box[0] - pad, 0),
                        max(box[1] - pad, 0),
                        min(box[2] + pad, image.width),
                        min(box[3] + pad, image.height),
                    )
                )
            image.save(SOURCE / filename)
            break


def _build_page1_main_report_html() -> str:
    """1페이지: 11/24 업무보고 메인 표를 반환합니다.

    Returns:
        1페이지 업무보고 메인 표 HTML 문자열입니다.
    """
    return """<div class="page-break">
<h1 class="title">업무보고</h1>

<table class="report-table">
  <tr>
    <td class="header-label">보고 기간</td>
    <td class="header-val">2026-11-24 (화)</td>
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
    <td colspan="3">11/23에 넓힌 담당자 통계 대시보드의 잘못된 표시를 점검해 고치고, AI가 민원을 처리하는 과정을 누구나 읽을 수 있는 설명서로 정리하며, 1차 판정에 Jev 모델을 넣는 방법을 제안서로 정리</td>
  </tr>
  <tr>
    <td class="header-label">주제</td>
    <td colspan="3">담당자 통계 대시보드 코드 리뷰 반영, 민원 AI 처리과정 상세설명서(서버·화면 / AI 계층 2부 구성)와 Jev 도입 제안서 작성 보고 (11/24)</td>
  </tr>
  <tr>
    <td class="label-cell">담당 업무<br>(전체)</td>
    <td colspan="3" class="full-val">
      <div class="section-title">1. 서버 &amp; 검색 기능</div>
      <div class="bullet-item">- 비슷한 민원과 근거를 찾아주는 검색 서버 운영, 민원 웹 백엔드(접수·로그인·알림·첨부·통계) 개발과 리눅스 서버 배포·운영</div>
      <div class="section-title">2. AI &amp; 테스트 화면</div>
      <div class="bullet-item">- AI 응대 로직·시민용 AI 상담 챗봇 개발, 응대 검사기 화면 관리 및 민원 웹 연동 (마감 2026-11-27)</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">진행 내용<br>(11/24)</td>
    <td colspan="3" class="full-val">
      <div class="section-title">1. 담당자 통계 대시보드 코드 점검과 보정</div>
      <div class="bullet-item">- <span class="highlight-tag">코드 리뷰 지적 7건 반영</span> : 분야 값이 목록 밖이면 통계 화면 전체가 오류로 멈추던 문제를 막고, 100%를 넘을 수 있는 "처리율"을 "답변 게시·접수 대비"로 고쳐 안내 문구를 붙임. 일평균은 진행 중인 구간을 빼고 계산하고, 접수 5건 미만 분야의 전기 대비는 "–"로 표시해 소수 건에서 +200%처럼 튀지 않게 함. 0건 막대를 1건과 구별하고 지역 선택 표시를 바로잡음</div>
      <div class="section-title">2. Jev 1차 판정 도입 제안서 (제안 단계, 구현 아님)</div>
      <div class="bullet-item">- <span class="highlight-tag">Jev 도입 제안서 PDF 5쪽</span> : 1차 판정에 Jev를 대체하거나 보완하는 방식, 보완 방식의 조합별 최종 결과, 코드 변경 목록과 위험, 비교 실험 계획을 그림·표로 정리함. 모델 서빙 정보가 정해져야 구현할 수 있어 코드는 바꾸지 않음</div>
      <div class="section-title">3. 민원 AI 처리과정 상세설명서 작성 (35쪽)</div>
      <div class="bullet-item">- <span class="highlight-tag">처리 흐름 전체를 코드에서 읽어 정리</span> : 접수 요청·응답, 비동기 AI 워커·저장·실시간 알림, 검색 API, 판정 입력과 시스템 프롬프트(PREFIX 00~04), LLM 호출 3종, 코드 검증 14규칙, 세 갈래·케이스 대응, 결과 구조, 실제 예시, 오류·폴백</div>
      <div class="bullet-item">- <span class="highlight-tag">두 영역으로 재구성</span> : 서버·화면에서 치르는 일(제1부)과 민원을 받아 AI 계층에서 치르는 일(제2부)로 나누고, 둘이 주고받는 값을 경계 쪽에 정리함</div>
      <div class="bullet-item">- <span class="highlight-tag">AI 워커와 갈래별 후속 호출 설명 보강</span> : 워커는 세션이 아니라 민원 한 건의 분석 1회를 맡는 스레드이고 AI 계층 코드도 그 스레드 안에서 실행됨을 설명. 1차 판정 뒤 갈래마다 어떤 프롬프트로 무엇을 넘기고 무엇이 저장되는지, 부서 추천과 담당자 검토의 차이, 순화(PREFIX-04)의 위치를 표로 정리함</div>
      <div class="bullet-item">- <span class="highlight-tag">읽기 쉽게 개선</span> : 모든 JSON 예시 밑에 키를 우리말로 옮긴 사본, 시민용·담당자용·내부 구분 표시, 함수·파일·필드 같은 코드 이름 종류 표시, 이름별 위치를 모은 부록 B(코드 위치 사전)를 넣음</div>
      <div class="section-title">4. 설명서를 코드와 대조해 바로잡은 내용</div>
      <div class="bullet-item">- <span class="highlight-tag">확인 가능한 것만 수록</span> : 시민 챗봇은 FAQ 안내문만 AI 문장을 그대로 쓰고 부서 추천·담당자 검토 문구는 다시 구성함, 판정이 "불확실"이어도 담당자 초안 호출이 이어짐(고정 초안은 범위 밖만), 키 표의 뜻 4곳을 근거 코드와 맞춰 고침</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">진행 결과</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- <span class="highlight-tag">설명서 2종 완성</span> : 민원 AI 처리과정 상세설명서 <strong>35쪽</strong>과 Jev 도입 제안서 <strong>5쪽</strong> PDF를 만들고 문서 목차·변경 이력(CHANGELOG)에 연결함</div>
      <div class="bullet-item">- <span class="highlight-tag">자동 시험 전부 통과 (11/24 다시 실행)</span> : 백엔드 시험 <strong>217건 통과(10건은 환경 때문에 건너뜀)</strong>, 화면 시험 <strong>71건 통과</strong>, 화면 문법 검사 <strong>39개 통과</strong>, 자동 타입 검사 <strong>88개 파일 오류 0건</strong></div>
      <div class="bullet-item">- 통계 보정 7건 중 3건은 서버에 배포했고, 나머지 4건은 GitHub에는 올렸으나 서버 배포 전임. 설명서 후속 보강은 로컬 커밋 상태로 아직 푸시하지 않음</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">남은 일</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- 통계 보정 4건 서버 배포와 실제 서버 데이터로 통계 화면 확인, 설명서 최종본 GitHub 반영, Jev 도입 여부와 모델 서빙 정보 확정, 최종 발표 자료(PPT) 정리 (마감 2026-11-27)</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">참고 사항</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- 구성 : <strong>[별첨 1: 2~3쪽]</strong> 핵심 수치·작업 분야별 요약·AI 처리 파이프라인 그림, <strong>[별첨 2: 4~5쪽]</strong> 상세설명서 주요 쪽 캡처. 설명서는 현재 구현 기준이며 Jev는 제안(미구현)임. 계정·서버 접속 정보는 보안상 넣지 않음</div>
    </td>
  </tr>
</table>
</div>"""


def _build_att1_page2_html() -> str:
    """2페이지: [별첨 1] 핵심 수치와 작업 분야별 요약을 반환합니다.

    Returns:
        2페이지 HTML 문자열입니다.
    """
    return """<div class="page-break">
  <div class="att-header">
    <h2>[별첨 1] 11/24 핵심 수치와 작업 분야별 요약</h2>
    <p class="att-meta">작성자: 연승현 · 기준일: 2026-11-24 (어려운 개발 용어 대신 기능과 효과 중심으로 정리)</p>
  </div>

  <div class="kpi-strip">
    <div class="kpi-card">
      <div class="kpi-label">백엔드·DB 시험</div>
      <div class="kpi-val">217건 통과</div>
      <div class="kpi-sub">실패 0건 · 10건은 환경 때문에 건너뜀</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">화면 시험 · 문법 검사</div>
      <div class="kpi-val">71건 · 39개</div>
      <div class="kpi-sub">모두 통과</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">타입 검사</div>
      <div class="kpi-val">0건 오류</div>
      <div class="kpi-sub">88개 파일 전체</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">새 문서</div>
      <div class="kpi-val">35쪽 + 5쪽</div>
      <div class="kpi-sub">처리과정 설명서 · Jev 제안서</div>
    </div>
  </div>

  <div class="att-sec-title">1. 작업 분야별 요약</div>
  <table class="diff-table">
    <thead>
      <tr>
        <th style="width: 22%;">작업 분야</th>
        <th style="width: 48%;">내용</th>
        <th style="width: 30%;">효과</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>통계 대시보드 보정</strong></td>
        <td>목록 밖 분야로 인한 통계 오류 차단, 처리율 표기를 "답변 게시·접수 대비"로 정정, 일평균·전기 대비·0건 막대·지역 선택 표시 보정</td>
        <td>잘못 읽히던 숫자를 바로잡고 통계 화면이 멈추는 일을 막음</td>
      </tr>
      <tr>
        <td><strong>Jev 도입 제안서</strong></td>
        <td>Jev를 1차 판정에 대체·보완으로 쓰는 방식과 비교 실험 계획 (제안, 미구현)</td>
        <td>도입 여부를 결정할 근거 마련</td>
      </tr>
      <tr>
        <td><strong>처리과정 상세설명서</strong></td>
        <td>접수부터 AI 판정·검증·응답까지 전 과정을 코드에서 읽은 값으로 정리. 서버·화면 / AI 계층 2부 구성</td>
        <td>팀원과 발표 청중이 서버와 AI의 역할 경계를 이해</td>
      </tr>
      <tr>
        <td><strong>읽기 쉬운 표시</strong></td>
        <td>JSON 키 우리말 사본, 시민용·담당자용·내부 배지, 코드 이름 종류 표시, 부록 B 코드 위치 사전</td>
        <td>개발 지식이 적어도 어디에 무엇이 있는지 찾을 수 있음</td>
      </tr>
      <tr>
        <td><strong>코드 대조 검증</strong></td>
        <td>설명 내용을 소스와 하나씩 대조해 챗봇 문구 재구성·불확실 케이스 초안 호출 등 틀린 설명을 정정</td>
        <td>추측이 아닌 확인된 동작만 문서에 남음</td>
      </tr>
    </tbody>
  </table>

  <div class="att-sec-title">2. 상세설명서 구성</div>
  <table class="diff-table">
    <thead>
      <tr>
        <th style="width: 22%;">영역</th>
        <th style="width: 40%;">장</th>
        <th style="width: 38%;">핵심</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>제1부 · 서버와 화면</strong></td>
        <td>1 민원 등록 API · 2 비동기 AI 워커·저장·알림 · 3 화면에 보이는 범위와 게시 규칙</td>
        <td>저장·권한·진행 표시·알림·게시. AI 판단은 하지 않음</td>
      </tr>
      <tr>
        <td><strong>경계</strong></td>
        <td>서버와 AI 계층이 주고받는 값</td>
        <td>서버가 질의·구·공급자를 넘기고 AI가 결과와 진행 알림을 돌려줌</td>
      </tr>
      <tr>
        <td><strong>제2부 · AI 계층</strong></td>
        <td>4 검색 · 5 판정 입력·프롬프트 · 6 LLM 호출 · 7 코드 검증 · 8 세 갈래·케이스 대응 · 9 결과 구조 · 10 실제 예시 · 11 오류·폴백</td>
        <td>검색·판정·검증·응답 만들기. 화면과 DB는 직접 건드리지 않음</td>
      </tr>
      <tr>
        <td><strong>부록</strong></td>
        <td>A 검색 용어 쉬운 설명 · B 코드 위치 사전</td>
        <td>형태소·BM25·코사인·RRF 설명, 코드 이름 찾기</td>
      </tr>
    </tbody>
  </table>
  <p style="margin: 6px 0 0 0; font-size: 7.9pt; color: #555;">※ 설명서는 현재 구현 기준이며 Jev와 같은 제안 내용은 구현과 구별해 표시했습니다. 통계 화면 캡처는 11/23 보고서 [별첨 2]에 있습니다.</p>
</div>"""


def _build_att1_page3_html() -> str:
    """3페이지: [별첨 1] AI 민원 처리 파이프라인 그림을 반환합니다.

    Returns:
        3페이지 HTML 문자열입니다.
    """
    return """<div class="page-break">
  <div class="att-header">
    <h2>[별첨 1] AI 민원 처리 파이프라인 (민원 한 건 기준)</h2>
    <p class="att-meta">상세설명서에서 코드로 확인한 흐름 · 제2부 전체가 AI 워커 스레드 안에서 이어서 실행됨</p>
  </div>

  <div class="pl-lane srv">
    <p class="pl-title">제1부 · 서버와 화면</p>
    <div class="pl-step"><b>민원 등록</b> → 서버가 입력을 검사하고 저장 → AI 워커 스레드 시작 (질의 = 제목 + 본문)</div>
  </div>
  <div class="pl-arrow">▼ 함수 한 번 호출 (질의·구·공급자)</div>

  <div class="pl-lane ai">
    <p class="pl-title">제2부 · AI 계층</p>
    <div class="pl-step"><b>① 읽기</b> 구·장소 추정, 길이 검사(1~2000자)</div>
    <div class="pl-step"><b>② 사전 관할 검증</b> 타 지자체 주소면 검색·판정 없이 종료 (고정 초안, 욕설이면 순화만)</div>
    <div class="pl-step"><b>③ 검색</b> 검색 서버에서 FAQ 5건 + 공개 사례 5건 + 부서 후보를 받음</div>
    <div class="pl-step"><b>④ 1차 판정</b> 시스템 프롬프트 PREFIX-00+01 · 입력 = 원문 전체 + 검색 후보 전부 <span class="tag int">내부</span></div>
    <div class="pl-step"><b>⑤ 코드 검증</b> 14규칙으로 판정을 다시 검사하고 갈래를 교정</div>
    <div class="pl-arrow">▼ 갈래</div>
    <div class="pl-branch">
      <div><b>faq_answer</b><br>FAQ 안내<br><span class="tag cit">시민용</span> 안내문을 LLM이 작성(PREFIX-00+02, 원문 + 인용 FAQ만)</div>
      <div><b>department_suggestion</b><br>부서 추천<br><span class="tag cit">시민용</span> 고정 틀(LLM 없음)</div>
      <div><b>human_handoff</b><br>담당자 검토<br><span class="tag cit">시민용</span> 사유별 고정 문구(LLM 없음)</div>
    </div>
    <div class="pl-step"><b>⑥ 담당자용 산출물</b> <span class="tag stf">담당자용</span> 접수된 민원에서만 만듦(시민 챗봇 경로는 생략)<br>
      · 담당자 초안 PREFIX-00+03 : 부서 추천·담당자 검토이고 범위 밖이 아닐 때 (원문 + 후보 전부 + 갈래·사유)<br>
      · 순화 PREFIX-00+04 : 조건부, 입력은 원문뿐, 초안과 동시 실행</div>
    <div class="pl-step"><b>⑦ 결과 조립</b> 시민 문구·판정·근거·담당자용 산출물을 한 묶음으로 만들어 서버에 돌려줌</div>
  </div>
  <div class="pl-arrow">▼ 결과 한 묶음</div>

  <div class="pl-lane srv">
    <p class="pl-title">제1부 · 서버와 화면</p>
    <div class="pl-step"><b>결과 검증</b> 형식 확인 → 늦게 온 결과면 버림 → DB 저장 → 담당자 화면에 실시간 알림. 시민은 담당자가 게시한 답변만 봄</div>
  </div>

  <div class="att-sec-title">갈래별 결과 한눈에</div>
  <table class="diff-table">
    <thead>
      <tr>
        <th style="width: 24%;">갈래</th>
        <th style="width: 38%;">시민 문구</th>
        <th style="width: 38%;">담당자 초안</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>FAQ 안내</strong></td>
        <td>LLM이 쓴 안내문(조건 보존)</td>
        <td>만들지 않음</td>
      </tr>
      <tr>
        <td><strong>부서 추천</strong></td>
        <td>고정 틀(부서 후보 이름 포함), 자동 이관 아님</td>
        <td>만듦</td>
      </tr>
      <tr>
        <td><strong>담당자 검토</strong></td>
        <td>사유별 고정 문구</td>
        <td>만듦(범위 밖이면 LLM 없이 고정 초안)</td>
      </tr>
    </tbody>
  </table>
  <p style="margin: 6px 0 0 0; font-size: 7.9pt; color: #555;">※ 시민 챗봇은 FAQ 안내문만 AI 문장을 그대로 쓰고, 부서 추천·담당자 검토 문구는 챗봇이 다시 구성합니다. 어느 갈래도 자동 이관이 아닙니다.</p>
</div>"""


def _build_att2_pages_html() -> str:
    """4~5페이지: [별첨 2] 상세설명서 주요 쪽 캡처 4장을 반환합니다.

    Returns:
        4~5페이지 HTML 문자열입니다.
    """

    def card(filename: str, caption: str, desc: str) -> str:
        return f"""  <div class="visual-card">
    <div class="visual-cap">{caption}</div>
    <p class="visual-sub">{desc}</p>
    <div class="visual-img-box" style="border: 1px solid #cbd5e1; border-radius: 3px; padding: 3px;">
      <img src="{encode_file(SOURCE / filename)}" alt="{caption}" style="max-height: 108mm; width: auto; max-width: 100%;">
    </div>
  </div>"""

    cards = [
        card(name, title, desc) for _key, name, title, desc, _s, _e in MANUAL_SHOTS
    ]
    pages = []
    for index, group in enumerate((cards[:2], cards[2:])):
        suffix = "" if index == 0 else " (계속)"
        pages.append(
            f"""<div class="page-break">
  <div class="att-header">
    <h2>[별첨 2] 민원 AI 처리과정 상세설명서 주요 쪽{suffix}</h2>
    <p class="att-meta">docs/plans/민원_AI_처리과정_상세설명서.pdf (35쪽) 중 발췌 · 2026-11-24 기준</p>
  </div>
{chr(10).join(group)}
</div>"""
        )
    return "\n\n".join(pages)


def build_report_html() -> str:
    """11/24 업무보고 전체 HTML을 조립합니다.

    Returns:
        인쇄 가능한 완결형 HTML 문자열입니다.
    """
    _render_manual_shots()
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>업무보고 (2026-11-24)</title>
<style>
{WORK_REPORT_CSS}
{_EXTRA_CSS}
</style>
</head>
<body>

{_build_page1_main_report_html()}

{_build_att1_page2_html()}

{_build_att1_page3_html()}

{_build_att2_pages_html()}

</body>
</html>
"""


def main() -> None:
    """11/24 업무보고 PDF(`docs/reports/daily/업무보고_20261124.pdf`)를 생성합니다."""
    out_pdf = Path(sys.argv[1]) if len(sys.argv) > 1 else OUTPUT_PDF_PATH
    render_html_to_pdf(build_report_html(), out_pdf)
    page_count = len(pypdf.PdfReader(str(out_pdf)).pages)
    print(
        f"REPORT_PDF_CREATED: {out_pdf} ({out_pdf.stat().st_size} bytes, {page_count} pages)"
    )


if __name__ == "__main__":
    main()
