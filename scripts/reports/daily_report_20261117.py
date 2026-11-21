"""11월 17일 종합 업무보고 PDF 생성 스크립트입니다.

1페이지: '연승현' 톤의 11/17 업무보고 메인 표 (CASE-098~101 종합)
2~4페이지: [별첨 1] 11/17 서버·AI·112건 분석·Swagger 보완 요약 및 실서버 검증 캡처
5~끝 페이지: [별첨 2] 'UI_수정_보고_2026-11-17.pdf' 원문 내용·이미지를 무수정으로 보존해
             기존 보고서 표·카드·캡처 테두리 양식으로 재구성한 부록
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import html
from pathlib import Path
import sys
import pypdf

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from report_common import render_html_to_pdf  # noqa: E402

ROOT_DIR = _SCRIPTS_DIR.parents[1]
DEFAULT_UI_PDF = Path(
    r"C:\Users\user\Documents\카카오톡 받은 파일\UI_수정_보고_2026-11-17.pdf"
)
DEFAULT_SCENES_DIR = Path(
    r"C:\Users\user\.gemini\antigravity-cli\brain\3197986d-ee70-477b-9852-28bbba3b7616\scratch"
)
DEFAULT_CHART_SVG = ROOT_DIR / "docs" / "assets" / "eval-112-axis-breakdown.svg"
OUTPUT_PDF_PATH = ROOT_DIR / "docs" / "report" / "업무보고_20261117.pdf"


@dataclass(frozen=True)
class UiFixCapture:
    """원본 UI 수정 보고서에 수록된 캡처 이미지 한 건의 위치와 설명입니다."""

    page_index: int
    image_index: int
    label: str


@dataclass(frozen=True)
class UiFixItem:
    """원본 `UI_수정_보고_2026-11-17.pdf`의 항목 한 건을 무수정 원문으로 보관합니다."""

    number: int
    title: str
    location: str
    detail_rows: tuple[tuple[str, str], ...]
    extra_notes: tuple[str, ...]
    captures: tuple[UiFixCapture, ...]
    side_by_side: bool = False
    max_img_height_mm: int = 58


@dataclass(frozen=True)
class WorkSceneSpec:
    """11/17 서버·AI·Swagger 실서버 검증 캡처 한 건의 메타데이터입니다."""

    filename: str
    caption: str
    description: str
    alt: str


UI_FIX_INDEX: tuple[str, ...] = (
    "1. 응대 검사기 LLM 엔진 버튼 대비",
    "2. 응대 검사기 안내 결과 본문 대비",
    "3. 시민 헤더 청주시 로고 (다크 버전)",
    "4. 시민 홈 자주 찾는 서비스 구성",
    "5. 시민 글쓰기 폼 라벨 대비",
    "6. 담당자 필터 칩 정리 (힉의 법칙, 중복 제거)",
    "7. 시민 글쓰기 폼 묶음 구획 (밀러의 법칙, 근접성)",
    "8. 응대 검사기 안내 배너 제거와 시험용 예시 접기 (테슬러의 법칙)",
    "9. 담당자 상세 작업 영역 구분 (게스탈트 근접성)",
    "10. 아이콘, 담당 버튼 터치 크기 (피츠의 법칙)",
)

UI_FIX_ITEMS: tuple[UiFixItem, ...] = (
    UiFixItem(
        number=1,
        title="1. 응대 검사기 LLM 엔진 버튼 대비",
        location="응대 검사기 (#/lab) / 민원 내용 입력 하단 LLM 엔진 선택 영역",
        detail_rows=(
            (
                "수정 전",
                "밝은 바탕용 고정 색이 다크 카드에 적용되어 OpenAI API 버튼 글자가 회색 바탕에 묻힘",
            ),
            (
                "수정 후",
                "다크 전용 색 적용 / 선택 엔진은 파란 테두리와 밝은 글자, 사용 불가 엔진은 흐린 글자로 구분",
            ),
            ("적용 파일", "ui/src/themes.css (다크 전용 규칙 추가)"),
        ),
        extra_notes=(),
        captures=(
            UiFixCapture(1, 0, "수정 전 캡처"),
            UiFixCapture(1, 1, "수정 후 캡처"),
        ),
        max_img_height_mm=34,
    ),
    UiFixItem(
        number=2,
        title="2. 응대 검사기 안내 결과 본문 대비",
        location="응대 검사기 (#/lab) / 응대 요청 후 나타나는 안내 결과 카드",
        detail_rows=(
            (
                "수정 전",
                '안내 본문 "검색에 실패했습니다. 담당자 검토가 필요합니다."이 어두운 회색으로 표시되어 거의 보이지 않음',
            ),
            (
                "수정 후",
                "본문을 밝은 색으로, 보조 문장을 연한 회색 파랑으로 조정",
            ),
            ("적용 파일", "ui/src/themes.css (다크 전용 규칙 추가)"),
        ),
        extra_notes=(),
        captures=(
            UiFixCapture(2, 0, "수정 전 캡처"),
            UiFixCapture(2, 1, "수정 후 캡처"),
        ),
        max_img_height_mm=34,
    ),
    UiFixItem(
        number=3,
        title="3. 시민 헤더 청주시 로고 (다크 버전)",
        location="시민 사이트 전 화면 헤더 왼쪽 (#/citizen)",
        detail_rows=(
            (
                "수정 내용",
                '다크 테마용 청주시 CI 이미지를 교체함. CI의 형태와 녹색 마크는 유지하고, "CHEONGJU CITY" 글자와 "민원톡톡" 문구의 색·굵기를 조정해 어두운 배경에서 읽기 쉽게 함',
            ),
            ("적용 파일", "ui/src/themes.css (다크 로고 이미지 교체)"),
        ),
        extra_notes=(
            "수정 전후 차이가 작아 수정 후 캡처 1장만 첨부함",
            "공개 전 CI 사용 지침 확인 필요",
        ),
        captures=(UiFixCapture(3, 0, "수정 후 캡처"),),
        max_img_height_mm=24,
    ),
    UiFixItem(
        number=4,
        title="4. 시민 홈 자주 찾는 서비스 구성",
        location="시민 사이트 홈 (#/citizen) / 우리 동네 소식 아래 자주 찾는 서비스 영역",
        detail_rows=(
            (
                "수정 전",
                "12개 서비스를 가로 스크롤로 배치하여 마지막 항목이 잘려 보이고, 선택지 범위가 불분명함",
            ),
            (
                "수정 후",
                "8개를 4열 격자로 표시하고 나머지는 전체 보기로 연결 / 힉의 법칙 (선택지 수 축소)과 제이콥의 법칙 (익숙한 격자 배열) 적용 / 모바일 390px 넘침 없음 확인",
            ),
            ("적용 파일", "ui/src/citizen.js, ui/src/citizen.css"),
        ),
        extra_notes=(),
        captures=(
            UiFixCapture(4, 0, "수정 전 캡처"),
            UiFixCapture(4, 1, "수정 후 캡처"),
        ),
        max_img_height_mm=33,
    ),
    UiFixItem(
        number=5,
        title="5. 시민 글쓰기 폼 라벨 대비",
        location="시민 사이트 작성 화면 (#/citizen/write) / 민원 내용 입력 폼",
        detail_rows=(
            (
                "수정 전",
                "라이트 전용 짙은 남색 라벨이 다크 배경에서 묻힘 (제목, 상세 내용 등)",
            ),
            (
                "수정 후",
                "폼 안의 기본 라벨을 밝은 색으로 지정 / 필수 표시 파란색 유지",
            ),
            ("적용 파일", "ui/src/themes.css (다크 전용 규칙 추가)"),
        ),
        extra_notes=(),
        captures=(
            UiFixCapture(5, 0, "수정 전 캡처"),
            UiFixCapture(5, 1, "수정 후 캡처"),
        ),
        max_img_height_mm=38,
    ),
    UiFixItem(
        number=6,
        title="6. 담당자 필터 칩 정리 (힉의 법칙, 중복 제거)",
        location="담당자 사이트 접수 대기, 검토 화면 (#/staff) 상단 필터 칩",
        detail_rows=(
            (
                "수정 전",
                "칩 8개가 한 줄로 나열되고, 사이드 메뉴와 같은 목록(미지정, 추가 문의, 게시 답변)이 두 번 나타남",
            ),
            (
                "수정 후",
                "칩 4개(전체, 접수 대기, 검토 중, 미게시 초안)만 표시하고 AI 시연 실패는 더보기로 접음 / 중복 칩 3개는 사이드 메뉴에서만 이동",
            ),
            ("적용 파일", "ui/src/staff.js, ui/src/staff.css"),
        ),
        extra_notes=(),
        captures=(
            UiFixCapture(6, 0, "수정 전 캡처"),
            UiFixCapture(6, 1, "수정 후 캡처"),
        ),
        max_img_height_mm=28,
    ),
    UiFixItem(
        number=7,
        title="7. 시민 글쓰기 폼 묶음 구획 (밀러의 법칙, 근접성)",
        location="시민 사이트 작성 화면 (#/citizen/write) / 민원 내용 입력 폼",
        detail_rows=(
            (
                "수정 전",
                "입력 항목이 한 패널에 이어지고, 상단 안내 배너가 상단 시연 띠와 내용이 겹침",
            ),
            (
                "수정 후",
                "무엇에 대한 민원인가요 / 어떤 일이 있었나요 / 공개 범위 / 확인 후 등록 네 묶음으로 나눔 / 개인정보 주의는 상세 내용 힌트로 이동, 상단 배너 제거",
            ),
            (
                "적용 파일",
                "ui/src/app.js, ui/src/staff.css, ui/src/citizen.css, ui/src/themes.css",
            ),
        ),
        extra_notes=(),
        captures=(
            UiFixCapture(7, 0, "수정 전 캡처"),
            UiFixCapture(7, 1, "수정 후 캡처"),
        ),
        side_by_side=True,
        max_img_height_mm=118,
    ),
    UiFixItem(
        number=8,
        title="8. 응대 검사기 안내 배너 제거와 시험용 예시 접기 (테슬러의 법칙)",
        location="응대 검사기 (#/lab) 상단 입력 영역",
        detail_rows=(
            (
                "수정 전",
                "안내 배너가 입력란 위에 있고, 시험용 예시 5개가 펼쳐져 있어 입력란이 한 화면 아래로 밀림",
            ),
            (
                "수정 후",
                '배너 제거 (상단 시연 띠와 중복) / 개인정보 주의는 상세 내용 힌트로 이동 / 시험용 예시는 접힌 상태로 두고 "펼치기"로 연결',
            ),
            ("적용 파일", "ui/src/lab.js, ui/src/staff.css"),
        ),
        extra_notes=(),
        captures=(
            UiFixCapture(8, 0, "수정 전 캡처"),
            UiFixCapture(8, 1, "수정 후 캡처"),
        ),
        max_img_height_mm=104,
    ),
    UiFixItem(
        number=9,
        title="9. 담당자 상세 작업 영역 구분 (게스탈트 근접성)",
        location="담당자 사이트 민원 상세 검토 (#/staff/detail/민원 번호)",
        detail_rows=(
            (
                "수정 전",
                "민원 원문과 답변 편집기가 같은 평면에 있어 시민 쪽 정보와 담당자 작업 영역의 경계가 불분명함",
            ),
            (
                "수정 후",
                '오른쪽 답변 편집, 이력 영역을 옅은 면으로 묶고 "담당자 작업 영역" 표시를 붙임',
            ),
            ("적용 파일", "ui/src/staff.css, ui/src/themes.css"),
        ),
        extra_notes=(),
        captures=(
            UiFixCapture(9, 0, "수정 전 캡처"),
            UiFixCapture(9, 1, "수정 후 캡처"),
        ),
        max_img_height_mm=68,
    ),
    UiFixItem(
        number=10,
        title="10. 아이콘, 담당 버튼 터치 크기 (피츠의 법칙)",
        location="시민 사이트 헤더 우측 아이콘 (#/citizen) / 담당자 민원 목록의 담당 버튼 (#/staff/complaints)",
        detail_rows=(
            (
                "수정 전",
                "헤더 아이콘 버튼 34px / 담당 해제, 내가 담당 버튼 70×30px / 검색 초기화 버튼 27×32px (실측)",
            ),
            (
                "수정 후",
                "헤더 아이콘 버튼 40px, 터치 기기 44px / 담당 버튼 76×40px / 검색 초기화 버튼 40px",
            ),
            ("적용 파일", "ui/src/staff.css"),
        ),
        extra_notes=(),
        captures=(
            UiFixCapture(10, 0, "수정 전 캡처"),
            UiFixCapture(10, 1, "수정 후 캡처"),
            UiFixCapture(10, 2, "수정 전 캡처 (담당 버튼 행)"),
            UiFixCapture(10, 3, "수정 후 캡처 (담당 버튼 행)"),
        ),
        max_img_height_mm=28,
    ),
)

UI_FIX_PAGE_GROUPS: tuple[tuple[int, ...], ...] = (
    (1, 2),
    (3, 4),
    (5, 6),
    (7,),
    (8,),
    (9,),
    (10,),
)

WORK_SCENES_PAGE_3: tuple[WorkSceneSpec, ...] = (
    WorkSceneSpec(
        filename="today_lab5010_case100_result.png",
        caption="1. 단독 검사기(:5010) — 문맥 비꼬기(sarcasm_mockery) 순화 및 랜드마크 지명 추론 + 기록 복원",
        description="'문암생태공원 공중화장실 변기를 예술작품처럼 방치해 두셨네요^^ 세금이 참 알차게 쓰여서 감동입니다.' 민원에서 흥덕구 자동 감지, 담당 부서 후보 및 PREFIX-04 순화 요약을 생성하고, 오른쪽 기록 클릭 시 입력 폼을 복원하는 장면(CASE-098·100)",
        alt="단독 검사기 비꼬기 순화 및 장소 추론 결과",
    ),
    WorkSceneSpec(
        filename="today_lab5010_outofscope.png",
        caption="2. 단독 검사기(:5010) — 타 지자체 동명이인('대전 유성구 봉명동') 관할 외 방어 검증",
        description="'대전 유성구 봉명동' 입력 시 청주시 흥덕구 봉명동으로 잘못 분류하지 않고 지정 없음으로 유지하며, 청주시 관할 외 사안(out_of_scope)으로 부서 자동 추천 없이 담당자 검토로 안전 보류한 장면(CASE-100)",
        alt="타 지자체 동명이인 차단 검증 화면",
    ),
)

WORK_SCENES_PAGE_4: tuple[WorkSceneSpec, ...] = (
    WorkSceneSpec(
        filename="final_dark_copy_btn.png",
        caption="3. 민원 웹(:5000/swagger) — 한국어 Swagger UI 포털(다크 테마·세션 원클릭 연결·Try it out 200)",
        description="빈 Authorize 모달을 제거하고 상단 '담당자 세션 연결' 단추로 HttpOnly 쿠키를 설정한 뒤 GET /api/v1/complaints를 실행(200 OK)한 장면. 다크 대비(4.5+)·복사 아이콘·통합 검색(opsFilter) 검증 완료(CASE-101)",
        alt="민원 웹 다크 테마 한국어 Swagger UI 포털",
    ),
    WorkSceneSpec(
        filename="verified_light_index.png",
        caption="4. 담당자 콘솔(#/staff/api) — 백엔드 상태 요약 카드 및 태그·키워드 '엔드포인트 빠른 색인'",
        description="담당자 사이드바에 추가한 API 문서 콘솔 화면. PostgreSQL·검색 :8007 상태 카드, 28개 엔드포인트 태그·검색 필터, docstring <br/> HTML 정리 및 라이트/다크 iframe 실시간 테마 동기화를 적용한 장면(CASE-101)",
        alt="담당자 콘솔 엔드포인트 빠른 색인 화면",
    ),
)


_REPORT_CSS = """
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
    padding: 4.6px 8px;
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
    margin: 1.2px 0;
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
    font-size: 14.5pt;
    font-weight: 800;
    margin: 0 0 2px 0;
  }
  .att-meta {
    font-size: 8.4pt;
    color: #555;
    margin: 0;
  }
  .att-sec-title {
    text-align: center;
    font-size: 11.5pt;
    font-weight: 800;
    margin: 8px 0 5px 0;
  }

  /* 비교표 */
  table.diff-table {
    width: 100%;
    border-collapse: collapse;
    border: 1.2px solid #222;
    margin-top: 4px;
    font-size: 8.1pt;
    line-height: 1.38;
  }
  table.diff-table th {
    background-color: #f3f5f8;
    border: 1px solid #333;
    padding: 4.5px 7px;
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
  .note-box {
    margin-top: 8px;
    padding: 7px 10px;
    background: #f8fafc;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    font-size: 8.1pt;
    color: #334155;
    line-height: 1.42;
  }

  /* 실서버 캡처 장면 */
  .scene-block {
    margin-top: 7px;
    margin-bottom: 9px;
  }
  .scene-cap {
    font-size: 9pt;
    font-weight: 700;
    color: #111;
    margin: 0 0 3px 0;
  }
  .scene-sub {
    font-size: 8pt;
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
    max-height: 105mm;
    object-fit: contain;
    object-position: top center;
    display: block;
    margin: 0 auto;
  }
  .chart-wrap {
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    background: #fff;
    padding: 4px;
    margin-top: 6px;
    text-align: center;
  }
  .chart-wrap img {
    width: 100%;
    max-height: 62mm;
    object-fit: contain;
    display: block;
    margin: 0 auto;
  }

  /* 별첨 2: UI 수정 보고서 카드/표 (원문 무수정 · 기존 양식 통일) */
  .ui-item-card {
    border: 1.1px solid #333;
    border-radius: 4px;
    padding: 7px 9px;
    margin-bottom: 9px;
    background: #fff;
    break-inside: avoid;
  }
  .ui-item-head {
    font-size: 10.5pt;
    font-weight: 800;
    color: #111;
    margin: 0 0 5px 0;
    padding-bottom: 4px;
    border-bottom: 1px solid #cbd5e1;
  }
  table.ui-meta-table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 6px;
    font-size: 8.1pt;
    line-height: 1.38;
  }
  table.ui-meta-table th {
    width: 14%;
    background: #f3f5f8;
    border: 1px solid #64748b;
    padding: 3.5px 6px;
    text-align: center;
    font-weight: 700;
    vertical-align: middle;
    white-space: nowrap;
  }
  table.ui-meta-table td {
    border: 1px solid #64748b;
    padding: 3.5px 7px;
    vertical-align: middle;
    word-break: keep-all;
  }
  .ui-extra-note {
    margin: 0 0 5px 0;
    padding: 3px 7px;
    background: #f8fafc;
    border-left: 2.5px solid #0f766e;
    font-size: 7.9pt;
    color: #334155;
  }
  .ui-cap-label {
    font-size: 8pt;
    font-weight: 700;
    color: #1e293b;
    margin: 4px 0 2.5px 0;
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
        HTML `<img>` 태그에 바로 넣을 data URI 문자열입니다.
    """
    mime = "image/svg+xml" if path.suffix.lower() == ".svg" else "image/png"
    return encode_binary_data_uri(path.read_bytes(), mime)


def extract_ui_pdf_images(ui_pdf_path: Path) -> list[list[bytes]]:
    """원본 `UI_수정_보고_2026-11-17.pdf`의 페이지별 원본 이미지를 모두 추출합니다.

    Args:
        ui_pdf_path: 원본 UI 수정 보고서 PDF 경로입니다.

    Returns:
        페이지 인덱스(0부터)별 이미지 바이트 리스트입니다.
    """
    reader = pypdf.PdfReader(str(ui_pdf_path))
    return [[bytes(img.data) for img in page.images] for page in reader.pages]


def _build_page1_main_report_html() -> str:
    """1페이지: 연승현의 11/17 업무보고 메인 표 HTML 조각을 반환합니다.

    Returns:
        1페이지 업무보고 메인 표 HTML 문자열입니다.
    """
    return """<div class="page-break">
<h1 class="title">업무보고</h1>

<table class="report-table">
  <tr>
    <td class="header-label">보고 기간</td>
    <td class="header-val">2026-11-17 (화)</td>
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
    <td colspan="3">112건 실전 테스트에서 찾은 AI·지명·타지역 판정 보완, 112건 시각화 분석 보고서 작성 및 민원 웹(:5000) Swagger API 문서 구축</td>
  </tr>
  <tr>
    <td class="header-label">주제</td>
    <td colspan="3">산학공동프로젝트 서버·AI 개선, 112건 분석 보고 및 백엔드 Swagger 포털 구축 (11/17)</td>
  </tr>
  <tr>
    <td class="label-cell">담당 업무<br>(전체)</td>
    <td colspan="3" class="full-val">
      <div class="section-title">1. 서버 &amp; 검색 DB</div>
      <div class="bullet-item">- 청주시 민원 데이터(자주 묻는 민원 94건, 공개 민원 사례 5,015건, 부서 127개) 수집 및 검색 서버 구축</div>
      <div class="bullet-item">- 민원 등록·조회·답변 작성용 Flask 웹 서버·PostgreSQL DB 연동 및 Swagger API 포털 관리</div>
      <div class="section-title">2. AI &amp; 테스트 웹</div>
      <div class="bullet-item">- 검색 근거 기반 AI 판정·초안·욕설 순화·정책 검사 로직 및 네이버 지도 장소 추적 기능 개발</div>
      <div class="bullet-item">- 실전 테스트·프롬프트 검수를 위한 단독 응대 검사기(:5010) 및 민원 웹(#/lab) 구축 (마감 2026-11-27)</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">진행 내용<br>(11/17)</td>
    <td colspan="3" class="full-val">
      <div class="section-title">1. 112건 실전 테스트 한계 3대 보완 및 타지역 동명이인 차단 (CASE-100)</div>
      <div class="bullet-item">- <span class="highlight-tag">문맥 기반 욕설·비꼬기 판별</span> : 1차 판정(PREFIX-01)에 문맥 플래그를 추가해 '보도블록/가로등 꺼져'·'가로수 죽어'·'시발점'·'전염병' 같은 정상 민원 오탐을 없애고, 초성('ㅅㅂ')·띄어쓰기 욕설·비꼬는 말(sarcasm_mockery)만 순화하도록 보완</div>
      <div class="bullet-item">- <span class="highlight-tag">동+번지수·장소 오매칭 개선</span> : '봉명동1349'처럼 띄어쓰기 없는 주소 경계와 청주 단일 구 8대 시설('청주국제공항'·'문암생태공원'·'청남대' 등) 인식을 보강하고, '지역'·'접수'·'신청'·'궁금합니다' 등 일반 단어가 네이버 지도 상호로 잘못 잡히던 오류를 차단</div>
      <div class="bullet-item">- <span class="highlight-tag">타지역 동명이인·관할 외 방어</span> : '대전 유성구 봉명동'·'서울 종로구 사직동'처럼 청주와 이름이 겹치는 타지역 민원을 흥덕구·서원구로 오인하지 않도록 분리하고, 관할 외(out_of_scope) 건은 부서 추천까지 담당자 검토로 안전 보류</div>
      <div class="section-title">2. 112건 시각화 분석 보고서 제작 &amp; 검사기(:5010) 기록 복원 (CASE-098·099)</div>
      <div class="bullet-item">- <span class="highlight-tag">112건 상세 보고서 &amp; 폼 복원</span> : :5010 오른쪽 테스트 기록 클릭 시 당시 입력 제목·분야·지역·엔진·본문을 폼에 복원하도록 개선하고, 5대 축 SVG 차트 4종과 112건 전수 표를 수록한 6쪽 상세 분석 보고서(docs/test/) 및 보고서 전용 폴더(docs/report/) 통합</div>
      <div class="section-title">3. 민원 웹(:5000) 한국어 Swagger API 포털 &amp; 담당자 콘솔 문서 구현 (CASE-101)</div>
      <div class="bullet-item">- <span class="highlight-tag">한국어 Swagger UI &amp; 콘솔(#/staff/api)</span> : /docs·/swagger에 자체 정적 자산 기반 한국어 Swagger 포털(담당자·시민 세션 원클릭 연결, 헬스 배지, 통합 필터 opsFilter)을 구축하고 담당자 사이드바에 '#/staff/api' 요약 카드·엔드포인트 빠른 색인(28개)·임베드 UI 연결</div>
      <div class="bullet-item">- <span class="highlight-tag">Authorize 빈 창 해결 &amp; 대비 검수</span> : HttpOnly 세션 방식상 비어 있던 무기능 Authorize 모달을 제거하고, 라이트·다크 테마 스크린샷 및 WCAG 대비(4.5 미만 0건)·복사 아이콘·iframe 실시간 테마 동기화 전수 점검 및 OpenAPI PDF 재생성 완료</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">진행 결과</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- <span class="highlight-tag">AI·지명 실측 통과</span> : 보완 패치 후 :5010 실서버 재검증에서 시설 '꺼져' 오탐 배제, 비꼬기·초성 순화, '봉명동1349'·'청주국제공항'·'문암생태공원' 구 인식 및 타지역 동명이인 차단이 모두 기대대로 동작함을 확인</div>
      <div class="bullet-item">- <span class="highlight-tag">자동 검증 &amp; UI 대비</span> : 백엔드·DB 격리 테스트 <strong>164건</strong>·검색 테스트 <strong>49건</strong>·UI <strong>22/22건</strong>·정적 타입(mypy) 0오류 및 Edge 헤드리스 라이트/다크 Swagger WCAG 대비 결함 0건, Try it out(401→200) 정상 동작 확인</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">남은 일</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- 담당자 화면 실시간 알림(SSE) 및 시민 챗봇 연동 범위 검토, 최종 시연·발표 자료 정리 (마감 2026-11-27)</div>
      <div class="bullet-item">- 11/17 작업분(CASE-101) 커밋·GitHub 반영 및 전체 연동 최종 확인</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">참고 사항</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- 역할 분담 : 팀원 / 다크·UI 사용성 개선 보고(별첨 2), 연승현 / AI 판정·지명 보완·112건 분석·:5000 Swagger 포털 구현</div>
      <div class="bullet-item">- <strong>[별첨 1: 2~4쪽]</strong>에 11/17 작업 요약·차트·실서버 캡처를, <strong>[별첨 2: 5쪽~]</strong>에 'UI 수정 보고서(2026-11-17)' 원문을 내용 수정 없이 기존 보고서 양식으로 수록함</div>
    </td>
  </tr>
</table>
</div>"""


def _build_att1_summary_page_html() -> str:
    """2페이지: [별첨 1] 11/17 주요 개선 비교표 및 112건 분석 차트 페이지를 반환합니다.

    Returns:
        2페이지 비교표·SVG 차트·검증표 HTML 문자열입니다.
    """
    chart_uri = encode_file(DEFAULT_CHART_SVG)
    return f"""<div class="page-break">
  <div class="att-header">
    <h2>[별첨 1] 11/17 서버·AI·Swagger 주요 작업 및 검증 요약</h2>
    <p class="att-meta">작성자: 연승현 · 기준일: 2026-11-17 (CASE-098 ~ CASE-101 누적 개선 결과)</p>
  </div>

  <div class="att-sec-title">1. 이전 보고(11/16) 대비 11/17 핵심 보완·구현 내역</div>
  <table class="diff-table">
    <thead>
      <tr>
        <th style="width: 19%;">구분</th>
        <th style="width: 34%;">이전 / 보완 전 상태</th>
        <th style="width: 47%;">현재 (2026-11-17 기준)</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="col-center"><strong>문맥 기반 욕설·비꼬기</strong><br>(CASE-100)</td>
        <td>문자열 포함 검사로 '보도블록 꺼져' 오탐(3건) 및 초성('ㅅㅂ')·비꼬기(11건) 미감지</td>
        <td>PREFIX-01 <code>sanitize_needed</code> 문맥 판단 + PREFIX-04 비꼬기(<code>sarcasm_mockery</code>) 추가, 시설/식물/사전 단어 오탐 배제</td>
      </tr>
      <tr>
        <td class="col-center"><strong>지명·장소 오매칭 방지</strong><br>(CASE-100)</td>
        <td>'봉명동1349' 붙여쓰기 누락, '지역'·'접수'·'궁금합니다'가 엉뚱한 상호로 검색됨</td>
        <td>동+숫자 경계·단일 구 8대 시설 매핑 보강, 서술어 어미·일반명사 불용어 필터 및 고유 접미어 우선 정렬</td>
      </tr>
      <tr>
        <td class="col-center"><strong>타지역 동명이인 차단</strong><br>(CASE-100)</td>
        <td>'대전 유성구 봉명동' 등 타지역이 청주시 흥덕구로 잘못 매칭·부서 추천 노출</td>
        <td>타 지자체 선행 주소 차단 및 <code>out_of_scope</code>·<code>uncertain</code> 시 부서 추천까지 담당자 검토로 강제 보류</td>
      </tr>
      <tr>
        <td class="col-center"><strong>112건 분석 &amp; 폼 복원</strong><br>(CASE-098·099)</td>
        <td>:5010 기록 클릭 시 결과만 열리고 입력 폼 비어 있음, 112건 결과 요약 위주</td>
        <td>기록 클릭 시 제목·분야·지역·엔진·본문 자동 복원 + SVG 차트 4종 수록 6쪽 상세 분석 보고서 및 보고 폴더 통합</td>
      </tr>
      <tr>
        <td class="col-center"><strong>:5000 Swagger 포털</strong><br>(CASE-101)</td>
        <td>/docs가 영문 기본 화면으로 이동, 빈 Authorize 창 노출, 담당자 콘솔 내 API 메뉴 없음</td>
        <td>자체 호스팅 한국어 Swagger 포털(/docs·/swagger)·세션 원클릭 연결·<code>#/staff/api</code> 빠른 색인·빈 Authorize 제거·다크/라이트 WCAG 검수</td>
      </tr>
    </tbody>
  </table>

  <div class="att-sec-title" style="margin-top: 10px;">2. 112건 5대 축 실증 차트 및 11/17 전체 검증 결과</div>
  <div class="chart-wrap">
    <img src="{chart_uri}" alt="청주 민원 112건 5대 축 실증 분석 요약 차트">
  </div>

  <table class="diff-table" style="margin-top: 7px;">
    <thead>
      <tr>
        <th style="width: 24%;">검증 항목</th>
        <th style="width: 24%;">실행 대상</th>
        <th style="width: 22%;">검증 결과</th>
        <th style="width: 30%;">확인 세부 내역</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>백엔드·DB 격리 테스트</strong></td>
        <td class="col-center">pytest <code>src/tests</code></td>
        <td class="col-center"><strong>164 / 164 통과</strong></td>
        <td>민원 CRUD, 권한, 409 충돌, Swagger 포털·임베드·404 경계 검증</td>
      </tr>
      <tr>
        <td><strong>RAG 검색 단위 테스트</strong></td>
        <td class="col-center">pytest <code>rag/tests</code></td>
        <td class="col-center"><strong>49 passed</strong> (3 skip)</td>
        <td>Windows 격리 템플릿 3건 제외 전체 검색·정규화 회귀 통과</td>
      </tr>
      <tr>
        <td><strong>프론트엔드 &amp; 정적 타입</strong></td>
        <td class="col-center"><code>ui test</code> · <code>mypy</code> · <code>black</code></td>
        <td class="col-center"><strong>UI 22/22 · 오류 0건</strong></td>
        <td>JS 문법 19모듈, OpenAPI 색인·HTML 정리, Python strict 타입 통과</td>
      </tr>
      <tr>
        <td><strong>실서버 시각·기능 감사</strong></td>
        <td class="col-center">:5000 · :5010 Edge 실측</td>
        <td class="col-center"><strong>WCAG &lt;4.5 0건</strong></td>
        <td>라이트/다크 대비, 복사 아이콘, Try it out(401→200), 112건 보완 재검증</td>
      </tr>
    </tbody>
  </table>
</div>"""


def _build_att1_scenes_page_html(
    scenes_dir: Path, scenes: tuple[WorkSceneSpec, ...], subtitle: str
) -> str:
    """3~4페이지: [별첨 1] 실서버 검증 캡처 2종을 한 페이지로 생성합니다.

    Args:
        scenes_dir: 실서버 스크린샷 PNG 파일이 있는 디렉터리입니다.
        scenes: 한 A4 쪽에 순서대로 배치할 캡처 메타데이터 묶음입니다.
        subtitle: 상단 머리말 부제목 문자열입니다.

    Returns:
        실서버 검증 캡처 2종이 담긴 A4 페이지 HTML 문자열입니다.
    """
    blocks = "\n".join(
        f"""  <div class="scene-block">
    <div class="scene-cap">{html.escape(scene.caption)}</div>
    <p class="scene-sub">{html.escape(scene.description)}</p>
    <div class="scene-img-wrap">
      <img src="{encode_file(scenes_dir / scene.filename)}" alt="{html.escape(scene.alt)}">
    </div>
  </div>"""
        for scene in scenes
    )
    return f"""<div class="page-break">
  <div class="att-header">
    <h2>[별첨 1] 11/17 서버·AI·Swagger 실서버 동작 검증</h2>
    <p class="att-meta">{html.escape(subtitle)}</p>
  </div>
{blocks}
</div>"""


def _build_att2_ui_cover_html() -> str:
    """[별첨 2] UI 수정 보고서(2026-11-17) 표지·목록 페이지를 원문 무수정으로 구성합니다.

    Returns:
        UI 수정 보고서 표지·목록 HTML 문자열입니다.
    """
    rows = "\n".join(
        f"""      <tr>
        <td class="col-center"><strong>{idx}</strong></td>
        <td>{html.escape(line)}</td>
      </tr>"""
        for idx, line in enumerate(UI_FIX_INDEX, 1)
    )
    return f"""<div class="page-break">
  <div class="att-header">
    <h2>[별첨 2] UI 수정 보고서 (원본 내용 무수정 · 기존 양식 적용)</h2>
    <p class="att-meta">원본 문서: UI_수정_보고_2026-11-17.pdf (전체 10건 및 첨부 캡처 21장 원문 그대로 수록)</p>
  </div>

  <h1 class="sub-title" style="margin-top: 10px;">UI 수정 보고서</h1>

  <div class="att-sec-title" style="text-align: left; margin-top: 12px;">기본 정보</div>
  <table class="report-table">
    <tr>
      <td class="header-label">작성일</td>
      <td class="header-val">2026-11-17</td>
      <td class="header-label">기준 양식</td>
      <td class="header-val">산학공동프로젝트 기존 보고서 양식</td>
    </tr>
    <tr>
      <td class="header-label">대상</td>
      <td colspan="3">시민 사이트 / 담당자 사이트 / 응대 검사기 (다크 테마 기준)</td>
    </tr>
  </table>

  <div class="att-sec-title" style="text-align: left; margin-top: 16px;">수정 목록</div>
  <table class="diff-table">
    <thead>
      <tr>
        <th style="width: 10%;">번호</th>
        <th style="width: 90%;">수정 항목 (원본 목록 그대로)</th>
      </tr>
    </thead>
    <tbody>
{rows}
    </tbody>
  </table>
</div>"""


def _build_ui_item_card_html(item: UiFixItem, pdf_images: list[list[bytes]]) -> str:
    """UI 수정 보고서 개별 항목 카드 HTML을 원문 무수정으로 생성합니다.

    Args:
        item: UI 수정 항목 원문 메타데이터입니다.
        pdf_images: 원본 `UI_수정_보고_2026-11-17.pdf`에서 추출한 페이지별 PNG 바이트 목록입니다.

    Returns:
        항목 상세 표와 원본 캡처가 담긴 카드 HTML 문자열입니다.
    """
    detail_rows = "\n".join(
        f"""      <tr>
        <th>{html.escape(label)}</th>
        <td>{html.escape(text)}</td>
      </tr>"""
        for label, text in item.detail_rows
    )
    notes_html = "\n".join(
        f'  <div class="ui-extra-note">- {html.escape(note)}</div>'
        for note in item.extra_notes
    )

    layout_class = "ui-cap-grid" if item.side_by_side else "ui-cap-stack"
    capture_blocks = "\n".join(
        f"""    <div>
      <div class="ui-cap-label">{html.escape(cap.label)}</div>
      <div class="ui-img-box">
        <img src="{encode_binary_data_uri(pdf_images[cap.page_index][cap.image_index], 'image/png')}"
             alt="{html.escape(item.title + ' - ' + cap.label)}"
             style="max-height: {item.max_img_height_mm}mm;">
      </div>
    </div>"""
        for cap in item.captures
    )
    captures_html = f'<div class="{layout_class}">\n{capture_blocks}\n  </div>'

    return f"""  <div class="ui-item-card">
    <h3 class="ui-item-head">{html.escape(item.title)}</h3>
    <table class="ui-meta-table">
      <tr>
        <th>위치</th>
        <td>{html.escape(item.location)}</td>
      </tr>
{detail_rows}
    </table>
{notes_html}
{captures_html}
  </div>"""


def _build_att2_ui_detail_pages_html(pdf_images: list[list[bytes]]) -> str:
    """[별첨 2] UI 수정 보고서 1~10번 상세 항목 페이지들을 생성합니다.

    Args:
        pdf_images: 원본 `UI_수정_보고_2026-11-17.pdf`의 페이지별 이미지 바이트 목록입니다.

    Returns:
        페이지 나눔이 포함된 UI 수정 보고서 상세 페이지 HTML 문자열입니다.
    """
    item_by_num = {item.number: item for item in UI_FIX_ITEMS}
    pages: list[str] = []
    for group in UI_FIX_PAGE_GROUPS:
        cards = "\n".join(
            _build_ui_item_card_html(item_by_num[num], pdf_images) for num in group
        )
        range_label = (
            f"{group[0]}번" if len(group) == 1 else f"{group[0]}~{group[-1]}번"
        )
        pages.append(
            f"""<div class="page-break">
  <div class="att-header">
    <h2>[별첨 2] UI 수정 보고서 (2026-11-17) · 상세 내역 ({range_label})</h2>
    <p class="att-meta">대상: 시민 사이트 / 담당자 사이트 / 응대 검사기 (다크 테마 기준) · 원문 내용 무수정</p>
  </div>
{cards}
</div>"""
        )
    return "\n\n".join(pages)


def build_report_html(scenes_dir: Path, ui_pdf_path: Path) -> str:
    """11/17 종합 보고서(업무보고 1쪽 + 별첨 1 연승현 작업 3쪽 + 별첨 2 UI 수정 보고서 8쪽) HTML을 조립합니다.

    Args:
        scenes_dir: 11/17 실서버 테스트 캡처 PNG 파일 폴더입니다.
        ui_pdf_path: 원본 `UI_수정_보고_2026-11-17.pdf` 파일 경로입니다.

    Returns:
        전체 보고서 HTML 문자열입니다.
    """
    pdf_images = extract_ui_pdf_images(ui_pdf_path)
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>업무보고 및 UI 수정 보고서 (2026-11-17)</title>
<style>
{_REPORT_CSS}
</style>
</head>
<body>

{_build_page1_main_report_html()}

{_build_att1_summary_page_html()}

{_build_att1_scenes_page_html(
    scenes_dir,
    WORK_SCENES_PAGE_3,
    "단독 검사기(:5010) — 문맥 비꼬기 순화·타지역 동명이인 차단·기록 폼 복원 (CASE-098·100)",
)}

{_build_att1_scenes_page_html(
    scenes_dir,
    WORK_SCENES_PAGE_4,
    "민원 웹(:5000) — 한국어 Swagger 포털(/swagger) 및 담당자 API 문서 콘솔(#/staff/api) (CASE-101)",
)}

{_build_att2_ui_cover_html()}

{_build_att2_ui_detail_pages_html(pdf_images)}

</body>
</html>
"""


def main() -> None:
    """11월 17일 업무보고 + UI 수정 보고서 통합 PDF를 생성합니다.

    Raises:
        FileNotFoundError: 원본 UI 수정 보고서 PDF, SVG 차트 또는 실서버 캡처 파일이 없을 때 발생합니다.
    """
    ui_pdf = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_UI_PDF
    scenes_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_SCENES_DIR
    out_pdf = Path(sys.argv[3]) if len(sys.argv) > 3 else OUTPUT_PDF_PATH

    if not ui_pdf.is_file():
        raise FileNotFoundError(f"원본 UI 보고서 PDF가 없습니다: {ui_pdf}")
    if not DEFAULT_CHART_SVG.is_file():
        raise FileNotFoundError(f"SVG 차트 파일이 없습니다: {DEFAULT_CHART_SVG}")
    for spec in WORK_SCENES_PAGE_3 + WORK_SCENES_PAGE_4:
        if not (scenes_dir / spec.filename).is_file():
            raise FileNotFoundError(
                f"실서버 캡처 파일이 없습니다: {scenes_dir / spec.filename}"
            )

    html_text = build_report_html(scenes_dir, ui_pdf)
    render_html_to_pdf(html_text, out_pdf)
    page_count = len(pypdf.PdfReader(str(out_pdf)).pages)
    print(
        f"REPORT_PDF_CREATED: {out_pdf} ({out_pdf.stat().st_size} bytes, {page_count} pages)"
    )


if __name__ == "__main__":
    main()
