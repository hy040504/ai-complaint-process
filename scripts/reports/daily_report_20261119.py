"""11월 19일 종합 업무보고 PDF 생성 스크립트입니다.

1페이지: '업무보고_20261111.pdf' 틀을 바탕으로 코드·함수 용어를 풀어서 정리한
         11/19 업무보고 메인 표
2~3페이지: [별첨 1] 200건 실증 재평가, 취약 사례 보완, 배너·안내 문서·지시 구조
           시각화 및 전수 점검 결과 (기능·효과 중심의 추상화 요약)
4~8페이지: [별첨 2] 'UI_수정_보고_2026-11-19.pdf' 원문 내용 및 고유 캡처 12장 무수정 수록
"""

from __future__ import annotations

from dataclasses import dataclass
import html
from pathlib import Path
import sys
import pypdf

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from report_common import (  # noqa: E402
    WORK_REPORT_CSS,
    UiFixCapture,
    encode_file,
    extract_unique_pdf_images,
    render_html_to_pdf,
    render_ui_captures_html,
)

ROOT_DIR = _SCRIPTS_DIR.parents[1]
DEFAULT_UI_PDF = Path(
    r"C:\Users\user\Documents\카카오톡 받은 파일\UI_수정_보고_2026-11-19.pdf"
)
OUTPUT_PDF_PATH = ROOT_DIR / "docs" / "reports" / "daily" / "업무보고_20261119.pdf"


@dataclass(frozen=True)
class UiCompareRow:
    """`UI_수정_보고_2026-11-19.pdf` 상세 표의 비교 행(수정 전·후 또는 단일 설명)입니다."""

    label: str
    before: str
    after: str | None = None


@dataclass(frozen=True)
class UiCompareItem:
    """`UI_수정_보고_2026-11-19.pdf`의 수정 항목 한 건을 원문 그대로 보관합니다."""

    code: str
    title: str
    rows: tuple[UiCompareRow, ...]
    captures: tuple[UiFixCapture, ...] = ()
    side_by_side: bool = True
    max_img_height_mm: int = 78


UI_FIX_TOC: tuple[tuple[str, str, str, str], ...] = (
    ("2-1", "담당자 사이드바 숫자 기준 통일", "Nielsen 1 (시스템 상태 가시성)", "적용"),
    ("2-2", "사이드바 숫자 배지 색 절제", "폰 레스토프 효과 (고립 효과)", "적용"),
    ("2-3", "접수 14일 초과 경과일 강조", "시각 위계, 경고 색 기준", "적용"),
    ("2-4", "상세 필터 접힘 시 여백 축소", "게슈탈트 근접성", "적용"),
    (
        "2-5",
        "응대 검사기 입력·결과 두 열 배치 (1100px 이상)",
        "도허티 임계치, 근접성",
        "적용",
    ),
    (
        "2-6",
        "응대 검사기 입력 안내를 고정 힌트로 이동",
        "Nielsen 6 (회상보다 인식)",
        "적용",
    ),
    ("2-7", "비활성 LLM 엔진 명암 대비 개선", "WCAG 1.4.3 (명암 대비 4.5:1)", "적용"),
    ("2-8", "시민 홈 질문 예시 칩 3개 추가", "Nielsen 6, 힉의 법칙", "적용"),
)

UI_FIX_ITEMS: tuple[UiCompareItem, ...] = (
    UiCompareItem(
        code="2-1",
        title="2-1. 담당자 사이드바 숫자 기준 통일 (Nielsen 1)",
        rows=(
            UiCompareRow(
                label="사이드바 숫자",
                before='"접수 대기·검토" 43 (접수 대기와 검토 중을 합친 값)',
                after='"접수 대기" 15 (접수 대기 카드 값과 동일)',
            ),
        ),
        captures=(
            UiFixCapture(0, "그림 1. 사이드바, 수정 전"),
            UiFixCapture(1, "그림 2. 사이드바, 수정 후"),
        ),
        side_by_side=True,
        max_img_height_mm=74,
    ),
    UiCompareItem(
        code="2-2",
        title="2-2. 사이드바 숫자 배지 색 절제 (폰 레스토프 효과)",
        rows=(
            UiCompareRow(
                label="배지 색",
                before="모든 숫자 배지가 빨강 (5개 동시 표시)",
                after="기본은 회색, AI 작업 실패 건수만 빨강",
            ),
            UiCompareRow(
                label="효과",
                before="긴급한 항목과 일반 건수를 구분하기 어려움",
                after="강조가 필요한 항목만 눈에 띔",
            ),
        ),
    ),
    UiCompareItem(
        code="2-3",
        title="2-3. 접수 14일 초과 경과일 강조",
        rows=(
            UiCompareRow(
                label="경과일 표시",
                before='"접수 139일째", "접수 366일째"가 본문과 같은 회색',
                after="14일을 넘으면 경과일만 주황 굵은 글씨로 표시",
            ),
            UiCompareRow(
                label="기준",
                before="14일은 화면 표시를 위한 기준이며, 법정 기한이나 처리 기한이 아닙니다.",
                after=None,
            ),
        ),
    ),
    UiCompareItem(
        code="2-4",
        title="2-4. 상세 필터 접힘 시 여백 축소 (게슈탈트 근접성)",
        rows=(
            UiCompareRow(
                label="여백",
                before='"상세 필터 (지역·분야·담당)" 제목 아래에 빈 공간이 크게 남음',
                after="접힌 상태에서 아래 여백과 제목 여백을 줄임",
            ),
        ),
        captures=(
            UiFixCapture(2, "그림 3. 목록 필터, 수정 전"),
            UiFixCapture(3, "그림 4. 목록 필터, 수정 후"),
        ),
        side_by_side=False,
        max_img_height_mm=34,
    ),
    UiCompareItem(
        code="2-5",
        title="2-5. 응대 검사기 입력·결과 두 열 배치 (도허티 임계치, 근접성)",
        rows=(
            UiCompareRow(
                label="배치",
                before="입력 폼 아래에 결과가 있어 결과를 보려면 스크롤이 필요함",
                after="1100px 이상에서 입력(왼쪽)과 결과(오른쪽)를 나란히 배치, 결과는 화면 상단에 고정",
            ),
            UiCompareRow(
                label="범위",
                before="좁은 화면에서는 기존처럼 한 열로 표시됩니다.",
                after=None,
            ),
        ),
        captures=(
            UiFixCapture(4, "그림 5. 응대 검사기, 수정 전"),
            UiFixCapture(5, "그림 6. 응대 검사기, 수정 후 (결과 대기 상태)"),
        ),
        side_by_side=True,
        max_img_height_mm=80,
    ),
    UiCompareItem(
        code="2-6",
        title="2-6. 입력 안내를 고정 힌트로 이동 (Nielsen 6)",
        rows=(
            UiCompareRow(
                label="상세 내용 칸",
                before="입력 안내가 placeholder에만 있어 입력을 시작하면 사라짐",
                after="placeholder는 짧은 예시만 표시, 어디에서·언제·무엇을 적을지는 칸 아래 고정 힌트로 표시",
            ),
        ),
        captures=(
            UiFixCapture(6, "그림 7. 상세 내용 칸, 수정 전"),
            UiFixCapture(7, "그림 8. 상세 내용 칸, 수정 후"),
        ),
        side_by_side=True,
        max_img_height_mm=58,
    ),
    UiCompareItem(
        code="2-7",
        title="2-7. 비활성 LLM 엔진 명암 대비 개선 (WCAG 1.4.3)",
        rows=(
            UiCompareRow(
                label="비활성 엔진",
                before="투명도 50%로 글자가 거의 보이지 않음",
                after="글자색 #5f6b80, 배경 #f3f5f9로 명암 대비 4.5:1 이상 확보. 잠긴 이유는 아래 힌트에 유지",
            ),
        ),
        captures=(
            UiFixCapture(8, "그림 9. LLM 엔진, 수정 전"),
            UiFixCapture(9, "그림 10. LLM 엔진, 수정 후"),
        ),
        side_by_side=False,
        max_img_height_mm=26,
    ),
    UiCompareItem(
        code="2-8",
        title="2-8. 시민 홈 질문 예시 칩 3개 추가 (Nielsen 6, 힉의 법칙)",
        rows=(
            UiCompareRow(
                label="시작 방법",
                before="질문 입력 막대 하나만 있고 예시는 막대 안의 한 문장뿐",
                after="막대 아래에 자주 묻는 질문 예시 3개를 칩으로 표시. 누르면 기존 접수 대화 화면에 질문이 채워짐",
            ),
            UiCompareRow(
                label="예시 문구",
                before='"도로에 큰 구멍이 났어요", "쓰레기를 무단으로 버리는 사람이 있어요", "불법 주정차 신고는 어떻게 하나요?" 화면 시연용 문구이며 정책 안내가 아닙니다.',
                after=None,
            ),
        ),
        captures=(
            UiFixCapture(10, "그림 11. 시민 홈 질문 영역, 수정 전"),
            UiFixCapture(11, "그림 12. 시민 홈 질문 영역, 수정 후"),
        ),
        side_by_side=False,
        max_img_height_mm=48,
    ),
)

UI_FIX_PAGE_GROUPS: tuple[tuple[str, ...], ...] = (
    ("2-1", "2-2", "2-3"),
    ("2-4", "2-5"),
    ("2-6", "2-7"),
    ("2-8",),
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
  table.ui-compare-table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 5px;
    font-size: 7.9pt;
    line-height: 1.36;
  }
  table.ui-compare-table th {
    background: #f3f5f8;
    border: 1px solid #64748b;
    padding: 3px 6px;
    text-align: center;
    font-weight: 700;
    vertical-align: middle;
  }
  table.ui-compare-table th.row-label {
    width: 14%;
    white-space: nowrap;
  }
  table.ui-compare-table th.half-head {
    width: 43%;
  }
  table.ui-compare-table td {
    border: 1px solid #64748b;
    padding: 3.5px 6.5px;
    vertical-align: middle;
    word-break: keep-all;
  }
"""


def _build_page1_main_report_html() -> str:
    """1페이지: `업무보고_20261111.pdf` 틀을 바탕으로 추상화해 정리한 11/19 메인 표를 반환합니다.

    Returns:
        1페이지 업무보고 메인 표 HTML 문자열입니다.
    """
    return """<div class="page-break">
<h1 class="title">업무보고</h1>

<table class="report-table">
  <tr>
    <td class="header-label">보고 기간</td>
    <td class="header-val">2026-11-19 (목)</td>
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
    <td colspan="3">민원 200건 실증 재평가 및 취약 사례 보완, 안내 문서·배너 시각 정비, 기민 님 11/19 UI 수정 통합 확인</td>
  </tr>
  <tr>
    <td class="header-label">주제</td>
    <td colspan="3">산학공동프로젝트 민원 200건 실증·취약 사례 보완, 안내 문서 정비 및 UI 수정 통합 보고 (11/19)</td>
  </tr>
  <tr>
    <td class="label-cell">담당 업무<br>(전체)</td>
    <td colspan="3" class="full-val">
      <div class="section-title">1. 서버 &amp; 검색 기능</div>
      <div class="bullet-item">- 청주시 민원 자료(자주 묻는 민원 94건, 공개 민원 사례 5,015건, 부서 127개)를 바탕으로 비슷한 민원과 근거를 찾아주는 검색 서버 구축 및 운영</div>
      <div class="bullet-item">- 민원 접수·조회·답변 관리 및 백엔드 API 안내 화면 개발과 연동 유지</div>
      <div class="section-title">2. AI &amp; 테스트 화면</div>
      <div class="bullet-item">- 검색 자료를 바탕으로 AI가 답변 안내·부서 추천·거친 표현 순화를 판단하는 응대 로직과 지도 기반 장소 찾기 기능 개발</div>
      <div class="bullet-item">- AI 응답 결과를 바로 시험해 볼 수 있는 검사기 화면 및 민원 웹 연동 관리 (마감 2026-11-27)</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">진행 내용<br>(11/19)</td>
    <td colspan="3" class="full-val">
      <div class="section-title">1. 200건 대규모 실증 재평가 및 시각화 분석 보고서 작성</div>
      <div class="bullet-item">- <span class="highlight-tag">실증 통과율 크게 향상 (83.9% → 95.0%)</span> : 기존 112건 동일 재측정과 까다로운 경계 사례 88건을 합한 총 200건을 실제 서버에서 시험해 <strong>190건(95.0%)</strong> 기대 동작을 확인함 (기존 112건 기준 94건 → <strong>108건</strong> 통과)</div>
      <div class="bullet-item">- <span class="highlight-tag">욕설·탈옥 방어 및 타 지역 조기 분류 안정화</span> : 욕설·비꼬기 탐지(38건)와 AI 우회 시도 방어(30건) <strong>100%</strong>를 달성하고, 타 지역 민원은 불필요한 단계를 건너뛰어 평균 <strong>0.012초</strong> 만에 즉시 담당자 검토로 넘김</div>
      <div class="bullet-item">- <span class="highlight-tag">핵심 차트·상세 분석 보고서 완성</span> : 유형별 성과 차트 4종과 전수 점검 표를 담은 14쪽 실증 분석 보고서를 제작하고, 후속 보완이 필요한 4가지 취약 영역을 도출함</div>
      <div class="section-title">2. 200건 평가에서 드러난 취약 사례 10건 및 오탐 개선</div>
      <div class="bullet-item">- <span class="highlight-tag">도로명·번지 인식 및 지도 호출 제한 대응</span> : 건물 이름 없이 도로명과 번지만 적힌 주소의 구·동 인식을 넓히고, 외부 지도 연속 제한 시 과도한 반복 대기를 차단해 응답 지연을 줄임 (약 62.7초 → <strong>24.8초</strong>)</div>
      <div class="bullet-item">- <span class="highlight-tag">일반 단어 장소 오인 차단 및 자체 도로 목록 보강</span> : '초등학교'·'청주시청'·'시장'처럼 일반 단어에 엉뚱한 장소가 붙던 잡음 13건을 걸러내고, 과거 공개 사례에서 확인된 단일 구 도로·번지 <strong>235쌍 자체 목록</strong>을 더해 지도 제한 중에도 관할 구를 복구함</div>
      <div class="bullet-item">- <span class="highlight-tag">타 지역 약칭·예외 안내 기준·초안 속도 보완</span> : '충남 천안 두정동' 같은 도·시 축약 표현을 0.01초 만에 분리 차단하고, 안내 문구에 '담당자 연결' 예외가 있을 때는 AI가 임의로 안내를 끝내지 않도록 2중 안전 기준과 초안 분량 상한을 맞춤 ([별첨 1] 요약 수록)</div>
      <div class="section-title">3. 프로젝트 안내 문서·배너 정비 및 코드·주석 일제 점검</div>
      <div class="bullet-item">- <span class="highlight-tag">배너 겹침 수정 및 AI 지시 구조 시각화</span> : 상단 프로젝트 배너에서 글자와 카드가 겹쳐 보이던 부분을 다시 배치하고, 소개 페이지에 AI 역할별 지시 구조도와 요약표를 넣어 가독성을 개선함</div>
      <div class="bullet-item">- <span class="highlight-tag">중복 로직 통합 및 한국어 주석·문서 정리</span> : 중복되던 지역·장소 계산을 하나로 합치고, 전체 수정 코드·화면 스크립트의 한국어 설명 주석과 끊긴 문서 링크를 빠짐없이 정비함</div>
      <div class="section-title">4. 기민 님 11/19 UI 수정 사항 통합 확인 (UI_수정_보고_2026-11-19.pdf)</div>
      <div class="bullet-item">- <span class="highlight-tag">현황 위계·검사기 2열 배치·접근성 점검</span> : 담당자 사이드바 숫자 통일 및 빨강 배지 절제, 14일 초과 경과일 주황 강조, 상세 필터 여백 축소, 검사기 입력·결과 나란히 배치(1100px 이상), 입력 안내 고정 힌트 이동, 비활성 엔진 명암 대비(4.5:1 이상), 시민 홈 질문 예시 칩 3개 추가 확인 ([별첨 2] 원문 그대로 수록)</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">진행 결과</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- <span class="highlight-tag">200건 실증 및 취약 사례 표적 재확인 통과</span> : 200건 실증 <strong>190건(95.0%)</strong> 달성 후 남은 미통과 10건과 경계 2건 등 <strong>표적 12건을 실서버에서 재시험해 전부 기대 동작으로 해소됨</strong>을 확인함</div>
      <div class="bullet-item">- <span class="highlight-tag">전체 기능·규칙·화면 일제 점검 통과</span> : 백엔드·DB 시험 <strong>171건 전부 통과</strong>, 규칙 점검 <strong>112건 실패 0건 · 타 지역 오탐 0건</strong>, 검색 49건(원본 대조 일치) · 화면 시험 <strong>22건 전부 통과</strong> 후 원격 저장소 반영 완료</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">남은 일</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- 보완 반영 후 전체 200건 일괄 재확인, 실시간 담당자 알림 연동 및 최종 발표 자료 정리 (마감 2026-11-27)</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">참고 사항</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- 역할 분담 : 기민 님 / 화면 사용성·시각 위계·접근성 개선([별첨 2]), 연승현 / 200건 실증·취약 사례 보완·배너/문서·코드 품질 정비([별첨 1])</div>
      <div class="bullet-item">- 구성 : <strong>[별첨 1: 2~3쪽]</strong> 200건 실증 결과 차트·취약 사례 보완 요약·배너/AI 구조 그림·검증 결과, <strong>[별첨 2: 4~8쪽]</strong> 'UI 수정 보고서(2026-11-19)' 원문·고유 이미지 12장 무수정 수록</div>
    </td>
  </tr>
</table>
</div>"""


def _build_att1_page2_html() -> str:
    """2페이지: [별첨 1] 200건 실증 KPI·축별 차트 및 취약 사례 10건 보완 요약표를 반환합니다.

    Returns:
        2페이지 HTML 문자열입니다.
    """
    axis_svg = encode_file(ROOT_DIR / "docs" / "assets" / "eval-200-axis-breakdown.svg")
    return f"""<div class="page-break">
  <div class="att-header">
    <h2>[별첨 1] 11/19 실증 평가 · 취약 사례 보완 및 안내 문서·품질 정비</h2>
    <p class="att-meta">작성자: 연승현 · 기준일: 2026-11-19 (어려운 개발 용어·함수명 대신 기능과 효과 중심으로 정리)</p>
  </div>

  <div class="kpi-strip">
    <div class="kpi-card">
      <div class="kpi-label">200건 실증 기대 동작 통과</div>
      <div class="kpi-val">190 / 200 (95.0%)</div>
      <div class="kpi-sub">기존 11/17(83.9%) 대비 +11.1%p</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">욕설·비꼬기 · AI 우회 방어</div>
      <div class="kpi-val">100.0% · 100.0%</div>
      <div class="kpi-sub">욕설/비꼬기 38건 · 방어 30건 전수 통과</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">취약·경계 사례 표적 재검증</div>
      <div class="kpi-val">12 / 12 전부 해소</div>
      <div class="kpi-sub">잡음 13건 차단 · 도로 색인 235쌍</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">전수 기능 · 규칙 · 화면 시험</div>
      <div class="kpi-val">171 · 112 · 22 통과</div>
      <div class="kpi-sub">실패 0건 · 타 지역 오탐 0건</div>
    </div>
  </div>

  <div class="att-sec-title">1. 단독 응대 검사기 200건 실증 결과 (5대 검증 분야별 통과율 변화)</div>
  <div class="visual-card">
    <p class="visual-sub">기존 112건 동일 문항 재측정(94→108건)과 까다로운 경계 사례 88건을 더한 총 200건을 실제 서버로 검증해 190건(95.0%)이 기대대로 동작함을 확인했습니다.</p>
    <div class="visual-img-box">
      <img src="{axis_svg}" alt="청주 민원 200건 5대 검증 축 실증 결과" style="max-height: 76mm;">
    </div>
  </div>

  <div class="att-sec-title">2. 200건 평가에서 드러난 취약 사례 10건 · 오탐 13건 및 속도 개선 요약</div>
  <table class="diff-table">
    <thead>
      <tr>
        <th style="width: 21%;">개선 분야</th>
        <th style="width: 39%;">발견된 문제 (개선 전)</th>
        <th style="width: 40%;">개선 내용 및 확인된 효과 (개선 후)</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>도로명·번지 주소 및<br>외부 지도 제한 대응</strong></td>
        <td>건물명 없이 도로명·번지만 적힌 주소가 빠지거나, 지도 연속 호출 제한 시 반복 대기로 최대 62초대 지연 발생</td>
        <td>도로·번지 주소 결과와 괄호 동명까지 통합해 읽고, 연속 제한 시 60초 대기 차단기를 적용해 연쇄 지연(<strong>62.7초→24.8초</strong>)을 크게 줄임</td>
      </tr>
      <tr>
        <td><strong>일반 단어 오인 차단 및<br>자체 도로 색인 구축</strong></td>
        <td>'초등학교'·'청주시청'·'시장' 등 일반 단어에 무관한 장소 배지가 잘못 붙고(13건), 지도 제한 시 관할 구 추적 실패</td>
        <td>일반 시설·관공서·조사 결합을 장소 후보에서 걸러 오탐 13건을 없애고, 공개 사례 기반 단일 구 도로·번지 <strong>235쌍 자체 목록</strong>으로 구를 100% 복구함</td>
      </tr>
      <tr>
        <td><strong>타 지역 약칭 차단 및<br>안내 예외 기준 보강</strong></td>
        <td>'충남 천안 두정동' 같은 도·시 약칭이 조기 차단을 빠져나가거나, '담당자 연결' 예외가 있는 안내를 AI가 혼자 종결</td>
        <td>도·시 축약 표현을 <strong>0.01초</strong> 내 즉시 분리 차단하고, 예외 안내 조항이 있으면 AI가 답변으로 끝내지 않고 담당자 검토로 넘기도록 2중 안전 기준 적용</td>
      </tr>
      <tr>
        <td><strong>초안 응답 속도 및<br>중복 계산·주석 정리</strong></td>
        <td>일부 무료 한국어 모델 초안이 과도한 분량으로 220초 이상 걸리거나, 지역·장소 탐색 중복 및 테스트 설명 주석 누락 잔존</td>
        <td>초안 최대 분량 상한을 통일(<strong>223.9초→200.2초</strong>)하고, 중복 계산 통합 · 21곳 테스트 설명 및 화면 설명 주석 보완 · 깨진 문서 링크 0건 정리</td>
      </tr>
    </tbody>
  </table>
</div>"""


def _build_att1_page3_html() -> str:
    """3페이지: [별첨 1] 배너·AI 지시 구조 시각화 및 최종 검증 결과표를 반환합니다.

    Returns:
        3페이지 HTML 문자열입니다.
    """
    banner_svg = encode_file(ROOT_DIR / "docs" / "assets" / "project-banner.svg")
    prefix_svg = encode_file(ROOT_DIR / "docs" / "assets" / "prefix-architecture.svg")
    return f"""<div class="page-break">
  <div class="att-header">
    <h2>[별첨 1] 프로젝트 배너 · AI 지시 구조 시각화 및 최종 점검 결과</h2>
    <p class="att-meta">대표 안내 페이지 시각 정비 · AI 프롬프트 5단계 역할 구조 · 11/19~20 최종 점검 완료 기준</p>
  </div>

  <div class="att-sec-title">3. 프로젝트 상단 배너 겹침 해소 및 안내 문서 가독성 개편</div>
  <div class="visual-card">
    <div class="visual-cap">① 상단 대표 배너 레이아웃 재정비</div>
    <p class="visual-sub">배너 좌측 안내 칩과 우측 담당자 연결 카드가 겹쳐 보이던 간격을 넓혀 재제작하고, 안내 문서 첫 화면의 장문 설명을 요약표·배지로 개편했습니다.</p>
    <div class="visual-img-box" style="border: 1px solid #cbd5e1; border-radius: 3px; padding: 3px;">
      <img src="{banner_svg}" alt="청주 민원 AI 완충지대 상단 배너" style="max-height: 44mm;">
    </div>
  </div>

  <div class="visual-card">
    <div class="visual-cap">② AI 시스템 지시 체계 (공통 헌법 + 역할별 4단계 분기) 구조도 신설</div>
    <p class="visual-sub">AI가 따르는 공통 안전 헌법(공무원이 최종 결정, 자동 이관 금지)과 1차 판정 · 안내 작성 · 담당자 초안 · 거친 표현 순화 역할을 한눈에 보도록 추가했습니다.</p>
    <div class="visual-img-box" style="border: 1px solid #cbd5e1; border-radius: 3px; padding: 3px;">
      <img src="{prefix_svg}" alt="AI 지시 체계 5단계 계층 구조" style="max-height: 82mm;">
    </div>
  </div>

  <div class="att-sec-title">4. 최종 검증 및 저장소 점검 결과 (11/19 패치 및 코드·문서 정비 후 재실행)</div>
  <table class="diff-table">
    <thead>
      <tr>
        <th style="width: 24%;">점검 항목</th>
        <th style="width: 34%;">확인 대상 및 내용</th>
        <th style="width: 17%;">결과</th>
        <th style="width: 25%;">주요 수치 및 비고</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>미통과 10건 · 경계 재검증</strong></td>
        <td>200건 평가 취약 사례 10건 + 타지역/초안 경계 2건 실서버 호출</td>
        <td class="col-center"><strong>12 / 12 전부 해소</strong></td>
        <td>잡음 13건 차단 · 천안 0.01초 차단</td>
      </tr>
      <tr>
        <td><strong>백엔드 · DB 기능 시험</strong></td>
        <td>민원 등록·조회·권한·장소·AI 정책 검사 전체 통합 시험</td>
        <td class="col-center"><strong>171건 전부 통과</strong></td>
        <td>실패 0건 · 건너뜀 0건</td>
      </tr>
      <tr>
        <td><strong>주소 · 오탐 규칙 회귀</strong></td>
        <td>실증 112건 규칙 및 공개 사례 5,015건 자동 규칙 점검</td>
        <td class="col-center"><strong>112건 실패 0건</strong></td>
        <td>사례 구 적중 <strong>762건</strong> · 외부 오탐 <strong>0건</strong></td>
      </tr>
      <tr>
        <td><strong>검색 · 화면 · 코드/문서 점검</strong></td>
        <td>검색/원본 대조, 화면 단위 시험, 주석·서식·타입·링크 검사</td>
        <td class="col-center"><strong>전체 통과</strong></td>
        <td>검색 49건 · 화면 22건 · 깨진 링크 <strong>0건</strong></td>
      </tr>
    </tbody>
  </table>
</div>"""


def _build_att2_ui_cover_html() -> str:
    """4페이지: [별첨 2] `UI_수정_보고_2026-11-19.pdf` 표지·기본 개요·수정 항목 목차를 원문 무수정으로 생성합니다.

    Returns:
        UI 수정 보고서 개요·목차 페이지 HTML 문자열입니다.
    """
    rows = "\n".join(
        f"""      <tr>
        <td class="col-center"><strong>{html.escape(code)}</strong></td>
        <td>{html.escape(title)}</td>
        <td>{html.escape(basis)}</td>
        <td class="col-center">{html.escape(status)}</td>
      </tr>"""
        for code, title, basis, status in UI_FIX_TOC
    )
    return f"""<div class="page-break">
  <div class="att-header">
    <h2>[별첨 2] UI 수정 보고서 (원본 내용 무수정 · 기존 업무보고 양식 적용)</h2>
    <p class="att-meta">원본 문서: UI_수정_보고_2026-11-19.pdf (수정 항목 2-1~2-8 및 고유 캡처 12장 원문 그대로 수록)</p>
  </div>

  <h1 class="sub-title" style="margin-top: 10px;">UI 수정 보고서</h1>

  <div class="att-sec-title">1. 기본 정보 및 개요</div>
  <table class="report-table" style="font-size: 8.3pt;">
    <tr>
      <td class="header-label">작성일</td>
      <td class="header-val">2026. 11. 19.</td>
      <td class="header-label">원본 파일</td>
      <td class="header-val">UI_수정_보고_2026-11-19.pdf</td>
    </tr>
    <tr>
      <td class="header-label">주요 목적</td>
      <td colspan="3">담당자 현황 숫자·배지 시각 위계 정비, 목록 필터 여백 축소, 응대 검사기 2열 배치 및 접근성(명암 대비)·질문 예시 칩 추가</td>
    </tr>
    <tr>
      <td class="header-label">적용 원칙</td>
      <td colspan="3">Nielsen 1·6 휴리스틱, 폰 레스토프 효과(고립 효과), 게슈탈트 근접성, 도허티 임계치, 힉의 법칙, WCAG 1.4.3 (명암 대비 4.5:1)</td>
    </tr>
    <tr>
      <td class="header-label">대상 화면</td>
      <td colspan="3">담당자 사이드바·목록·상세 필터, 응대 검사기 입력·결과·LLM 엔진 선택 영역, 시민 홈 질문 영역</td>
    </tr>
  </table>

  <div class="att-sec-title" style="margin-top: 14px;">2. 수정 항목 목차 (원본 1. 수정 항목 목차 원문 그대로)</div>
  <table class="diff-table">
    <thead>
      <tr>
        <th style="width: 11%;">항목 번호</th>
        <th style="width: 45%;">수정 항목 제목</th>
        <th style="width: 33%;">근거</th>
        <th style="width: 11%;">상태</th>
      </tr>
    </thead>
    <tbody>
{rows}
    </tbody>
  </table>
  <p style="margin: 8px 0 0 0; font-size: 7.9pt; color: #555;">※ 다음 페이지(5~8쪽)에 원본 UI 수정 보고서의 상세 내역 표(2-1 ~ 2-8)와 비교 그림 1~12(고유 이미지 12장)를 원문 수정 없이 그대로 수록합니다.</p>
</div>"""


def _build_compare_card_html(item: UiCompareItem, unique_images: list[bytes]) -> str:
    """`UI_수정_보고_2026-11-19.pdf` 항목 카드(3열 수정 전·후 표 + 캡처)를 원문 그대로 조립합니다.

    Args:
        item: UI 수정 항목 원문 메타데이터입니다.
        unique_images: 원본 PDF에서 추출한 고유 PNG 바이트 12장 목록입니다.

    Returns:
        HTML 카드 문자열입니다.
    """
    rows_html_parts: list[str] = []
    for row in item.rows:
        if row.after is None:
            rows_html_parts.append(
                f"""      <tr>
        <th>{html.escape(row.label)}</th>
        <td colspan="2">{html.escape(row.before)}</td>
      </tr>"""
            )
        else:
            rows_html_parts.append(
                f"""      <tr>
        <th>{html.escape(row.label)}</th>
        <td>{html.escape(row.before)}</td>
        <td>{html.escape(row.after)}</td>
      </tr>"""
            )
    rows_html = "\n".join(rows_html_parts)
    captures_html = render_ui_captures_html(
        item.title,
        item.captures,
        unique_images,
        side_by_side=item.side_by_side,
        max_img_height_mm=item.max_img_height_mm,
    )

    return f"""  <div class="ui-item-card">
    <h3 class="ui-item-head">{html.escape(item.title)}</h3>
    <table class="ui-compare-table">
      <thead>
        <tr>
          <th class="row-label">구분</th>
          <th class="half-head">수정 전</th>
          <th class="half-head">수정 후</th>
        </tr>
      </thead>
      <tbody>
{rows_html}
      </tbody>
    </table>{captures_html}
  </div>"""


def _build_att2_ui_detail_pages_html(unique_images: list[bytes]) -> str:
    """[별첨 2] `UI_수정_보고_2026-11-19.pdf` 상세 항목 2-1~2-8 페이지들을 생성합니다.

    Args:
        unique_images: 원본 PDF에서 추출한 고유 PNG 바이트 12장 목록입니다.

    Returns:
        페이지 나눔이 포함된 상세 내역 HTML 문자열입니다.
    """
    by_code = {item.code: item for item in UI_FIX_ITEMS}
    pages: list[str] = []
    for group in UI_FIX_PAGE_GROUPS:
        cards = "\n".join(
            _build_compare_card_html(by_code[code], unique_images) for code in group
        )
        label = group[0] if len(group) == 1 else f"{group[0]} ~ {group[-1]}"
        pages.append(
            f"""<div class="page-break">
  <div class="att-header">
    <h2>[별첨 2] UI 수정 보고서 (2026. 11. 19.) · 상세 내역 ({html.escape(label)})</h2>
    <p class="att-meta">원본 문서: UI_수정_보고_2026-11-19.pdf · 표 내용 및 그림 1~12 무수정 수록</p>
  </div>
{cards}
</div>"""
        )
    return "\n\n".join(pages)


def build_report_html(ui_pdf_path: Path) -> str:
    """11/19 종합 업무보고 + 실증 시각화 + UI 수정 보고서 전체 HTML을 조립합니다.

    Args:
        ui_pdf_path: 원본 `UI_수정_보고_2026-11-19.pdf` 파일 경로입니다.

    Returns:
        인쇄 가능한 완결형 HTML 문자열입니다.

    Raises:
        ValueError: 원본 PDF에서 기대한 12장의 고유 이미지가 추출되지 않을 때 발생합니다.
    """
    unique_images = extract_unique_pdf_images(ui_pdf_path)
    if len(unique_images) != 12:
        raise ValueError(
            f"UI_수정_보고_2026-11-19.pdf에서 12개 고유 이미지를 예상했으나 {len(unique_images)}개 추출됨"
        )
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>업무보고 및 UI 수정 보고서 (2026-11-19)</title>
<style>
{WORK_REPORT_CSS}
{_EXTRA_CSS}
</style>
</head>
<body>

{_build_page1_main_report_html()}

{_build_att1_page2_html()}

{_build_att1_page3_html()}

{_build_att2_ui_cover_html()}

{_build_att2_ui_detail_pages_html(unique_images)}

</body>
</html>
"""


def main() -> None:
    """11월 19일 종합 업무보고 PDF(`docs/reports/daily/업무보고_20261119.pdf`)를 생성합니다.

    Raises:
        FileNotFoundError: 원본 UI 보고서 PDF가 없을 때 발생합니다.
    """
    ui_pdf = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_UI_PDF
    out_pdf = Path(sys.argv[2]) if len(sys.argv) > 2 else OUTPUT_PDF_PATH

    if not ui_pdf.is_file():
        raise FileNotFoundError(f"원본 UI 보고서 PDF가 없습니다: {ui_pdf}")

    html_text = build_report_html(ui_pdf)
    render_html_to_pdf(html_text, out_pdf)
    page_count = len(pypdf.PdfReader(str(out_pdf)).pages)
    print(
        f"REPORT_PDF_CREATED: {out_pdf} ({out_pdf.stat().st_size} bytes, {page_count} pages)"
    )


if __name__ == "__main__":
    main()
