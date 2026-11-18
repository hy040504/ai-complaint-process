"""11월 18일 종합 업무보고 PDF 생성 스크립트입니다.

1페이지: '업무보고_20261111.pdf' 틀을 바탕에 둔 11/18 업무보고 메인 표
         (112건 잔여 한계 해결·EXAONE 차등/병렬/조기차단·백엔드 API·Swagger 점검·UI 통합 확인)
2~4페이지: [별첨 1] 11/18 백엔드 API 변경/누적 현황표, PREFIX 구조도, 최종 검증표 및
           라이브 Swagger 포털·담당자 API 콘솔·검색 API Swagger 캡처 4종
5~끝 페이지: [별첨 2] 'UI_수정_보고_2026-11-18.pdf' 원문 내용 및 고유 캡처 14장 무수정·기존 양식 수록
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import html
from pathlib import Path
import sys
import pypdf

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from 보고서_공통 import render_html_to_pdf  # noqa: E402

ROOT_DIR = _SCRIPTS_DIR.parent
DEFAULT_UI_PDF = Path(
    r"C:\Users\user\Documents\카카오톡 받은 파일\UI_수정_보고_2026-11-18.pdf"
)
DEFAULT_SCENES_DIR = Path(
    r"C:\Users\user\.gemini\antigravity-cli\brain\3197986d-ee70-477b-9852-28bbba3b7616\scratch"
)
DEFAULT_PREFIX_SVG = ROOT_DIR / "docs" / "assets" / "prefix-architecture.svg"
OUTPUT_PDF_PATH = ROOT_DIR / "docs" / "report" / "업무보고_20261118.pdf"


@dataclass(frozen=True)
class UiFixCapture:
    """원본 `UI_수정_보고_2026-11-18.pdf`에 수록된 고유 캡처 이미지 설명입니다."""

    unique_index: int
    label: str


@dataclass(frozen=True)
class UiFixItem:
    """원본 `UI_수정_보고_2026-11-18.pdf`의 항목 한 건을 원문 무수정으로 보관합니다."""

    code: str
    title: str
    rule_note: str
    detail_rows: tuple[tuple[str, str], ...]
    captures: tuple[UiFixCapture, ...] = ()
    side_by_side: bool = True
    max_img_height_mm: int = 86


@dataclass(frozen=True)
class WorkSceneSpec:
    """11/18 백엔드 API 및 Swagger UI 실서버 캡처 한 건의 메타데이터입니다."""

    filename: str
    caption: str
    description: str
    alt: str


UI_FIX_INDEX: tuple[tuple[str, str], ...] = (
    ("2-1", "글자 크기와 대비 (WCAG 1.4.3, 1.4.4)"),
    ("2-2", "색 토큰 정리"),
    ("2-3", "시민 홈 상담 바 위치 (주 행동 우선 배치)"),
    ("2-4", "헤더 버튼 정리 (Hick 법칙)"),
    ("2-5", "시연 안내 정리 (Nielsen 휴리스틱 1, 시스템 상태 가시성)"),
    ("2-6", "아이콘 버튼 터치 영역 (Fitts 법칙)"),
    ("2-7", "담당자 목록 필터 정리 (Hick 법칙)"),
    ("2-8", "담당 버튼 이름 (스크린리더)"),
    ("2-8*", "민원 철회 위험 영역 분리 (Nielsen 휴리스틱 5, 오류 예방)"),
    ("2-9", "다크 모드 보조 글자 흰색 전환 (대비)"),
)

UI_FIX_ITEMS: tuple[UiFixItem, ...] = (
    UiFixItem(
        code="2-1",
        title="2-1. 글자 크기와 대비 (WCAG 1.4.3, 1.4.4)",
        rule_note="WCAG 1.4.3은 글자와 배경의 명암 대비 기준, 1.4.4는 글자를 확대해도 내용이 깨지지 않는 기준",
        detail_rows=(
            (
                "수정 전",
                "8~11px 글자 약 124곳, 보조 문구 대비 약 2.65 : 1 ~ 3.7 : 1",
            ),
            (
                "수정 후",
                "시민 화면 글자 12px 이상, 보조 문구 대비 4.5 : 1 이상 (#5d6c86, #5f7261)",
            ),
            ("추가 정리", "제목 크기 21~27px을 20px, 24px 두 단계로 정리"),
        ),
        captures=(
            UiFixCapture(0, "그림 1. 시민 홈 PC, 수정 전"),
            UiFixCapture(1, "그림 2. 시민 홈 PC, 수정 후"),
        ),
        side_by_side=True,
        max_img_height_mm=84,
    ),
    UiFixItem(
        code="2-2",
        title="2-2. 색 토큰 정리",
        rule_note="",
        detail_rows=(
            ("수정 전", "시민 화면 색 하드코딩 325개, 토큰 사용 1개"),
            ("수정 후", "시민 화면 색 토큰 6개 도입, 값은 기존과 같아 화면 변화 없음"),
        ),
    ),
    UiFixItem(
        code="2-3",
        title="2-3. 시민 홈 상담 바 위치 (주 행동 우선 배치)",
        rule_note="상단 그림 1~2(전체 비교) 및 아래 그림 6(확대 영역)에 변경 전·후 반영",
        detail_rows=(
            ("수정 전", "상담 바가 소식과 서비스 메뉴 아래에 있음"),
            ("수정 후", "환영 문구 바로 아래로 이동, 소식은 2건만 표시"),
        ),
    ),
    UiFixItem(
        code="2-4",
        title="2-4. 헤더 버튼 정리 (Hick 법칙)",
        rule_note="Hick 법칙 : 선택지가 많을수록 결정이 느려지므로, 같은 행동을 가리키는 버튼은 하나만 강조함",
        detail_rows=(
            ("수정 전", "'직접 작성'과 '접수 시작'이 같은 행동을 가리킴"),
            ("수정 후", "헤더 '직접 작성'을 기본 스타일로 낮춤"),
        ),
        captures=(
            UiFixCapture(2, "그림 3. 헤더 버튼, 수정 전"),
            UiFixCapture(3, "그림 4. 헤더 버튼, 수정 후"),
        ),
        side_by_side=True,
        max_img_height_mm=22,
    ),
    UiFixItem(
        code="2-5",
        title="2-5. 시연 안내 정리 (Nielsen 휴리스틱 1, 시스템 상태 가시성)",
        rule_note="Nielsen 휴리스틱 1 : 사용자가 현재 상태를 항상 알 수 있도록 보여야 한다는 원칙",
        detail_rows=(
            (
                "수정 전",
                "홈 한 화면에 시연 안내가 네 곳 (상단 배너, 소식 라벨, 상담 바 문구, 푸터)에 반복",
            ),
            ("수정 후", "상단 DEMO 배너 한 곳만 유지, 나머지 반복 문구 제거"),
        ),
        captures=(
            UiFixCapture(4, "그림 5. 시연 안내와 소식 영역, 수정 전"),
            UiFixCapture(5, "그림 6. 상담 바 위치와 소식 영역, 수정 후"),
        ),
        side_by_side=True,
        max_img_height_mm=44,
    ),
    UiFixItem(
        code="2-6",
        title="2-6. 아이콘 버튼 터치 영역 (Fitts 법칙)",
        rule_note="Fitts 법칙 : 대상이 작고 멀수록 누르는 데 시간이 더 걸리므로, 터치 영역을 키움",
        detail_rows=(
            ("수정 전", "아이콘 버튼 34 × 34px (알림, 테마, 담당자 메뉴와 도움말)"),
            ("수정 후", "44 × 44px로 확대 (시민 헤더와 담당자 화면)"),
        ),
        captures=(
            UiFixCapture(6, "그림 7. 헤더 아이콘 버튼 확대, 수정 전"),
            UiFixCapture(7, "그림 8. 헤더 아이콘 버튼 확대, 수정 후"),
        ),
        side_by_side=True,
        max_img_height_mm=24,
    ),
    UiFixItem(
        code="2-7",
        title="2-7. 담당자 목록 필터 정리 (Hick 법칙)",
        rule_note="Hick 법칙 : 한 줄에 조작 요소가 많으면 고르기 어려우므로, 자주 쓰지 않는 필터는 접어 둠",
        detail_rows=(
            (
                "수정 전",
                "검색창, 지역, 분야, 담당 선택 3개, 검색 버튼, 아이콘 초기화가 한 줄에 있고 칩과 배너가 겹쳐 있음",
            ),
            (
                "수정 후",
                "지역, 분야, 담당은 '상세 필터 (지역, 분야, 담당)'로 접음, 조건이 걸려 있으면 자동으로 펼침 / 초기화는 '조건 지우기' 글자 버튼으로 변경",
            ),
        ),
        captures=(
            UiFixCapture(8, "그림 9. 담당자 목록 상단, 수정 전"),
            UiFixCapture(9, "그림 10. 담당자 목록 상단, 수정 후"),
        ),
        side_by_side=True,
        max_img_height_mm=72,
    ),
    UiFixItem(
        code="2-8",
        title="2-8. 담당 버튼 이름 (스크린리더)",
        rule_note="원본 PDF 2쪽 수록 항목 원문 그대로 유지 (다음 항목과 원본 2-8 번호 병기)",
        detail_rows=(
            ("수정 전", "'내가 담당', '담당 해제'만 읽힘"),
            ("수정 후", "민원 제목을 포함한 이름으로 읽힘 (예 : 민원 제목 담당 지정)"),
        ),
    ),
    UiFixItem(
        code="2-8*",
        title="2-8. 민원 철회 위험 영역 분리 (Nielsen 휴리스틱 5, 오류 예방)",
        rule_note="Nielsen 휴리스틱 5 : 실수로 누르기 쉬운 동작을 떼어 놓아 오류를 미리 막는 원칙",
        detail_rows=(
            (
                "수정 전",
                "'수정' 링크 옆에 같은 형태의 '민원 철회' 버튼이 있어 실수로 누르기 쉬움",
            ),
            (
                "수정 후",
                "본문 아래 점선으로 분리, 철회 결과 설명 추가, 빨간 버튼에 흰 글자 적용",
            ),
        ),
        captures=(
            UiFixCapture(10, "그림 11. 시민 민원 상세, 수정 전"),
            UiFixCapture(11, "그림 12. 시민 민원 상세, 수정 후"),
        ),
        side_by_side=True,
        max_img_height_mm=134,
    ),
    UiFixItem(
        code="2-9",
        title="2-9. 다크 모드 보조 글자 흰색 전환 (대비)",
        rule_note="원본 PDF 4쪽 수록 항목 원문 그대로 유지",
        detail_rows=(
            (
                "수정 전",
                "응대 검사기의 '펼쳐서 고르면 입력란에 채워집니다', '* 필수 입력 항목' 등이 회색 또는 연한 파랑으로 흐림",
            ),
            (
                "수정 후",
                "회색, 청회색 보조 글자 61개 선택자를 흰색으로 변경 / 배지, 상태 태그, 버튼은 밝은 바탕이라 제외",
            ),
        ),
        captures=(
            UiFixCapture(12, "그림 13. 응대 검사기 다크 모드, 수정 전"),
            UiFixCapture(13, "그림 14. 응대 검사기 다크 모드, 수정 후"),
        ),
        side_by_side=True,
        max_img_height_mm=134,
    ),
)

UI_FIX_PAGE_GROUPS: tuple[tuple[str, ...], ...] = (
    ("2-1", "2-2", "2-3"),
    ("2-4", "2-5", "2-6"),
    ("2-7", "2-8"),
    ("2-8*",),
    ("2-9",),
)

WORK_SCENES_PAGE_3: tuple[WorkSceneSpec, ...] = (
    WorkSceneSpec(
        filename="rep18_swagger_light.png",
        caption="1. 민원 웹 백엔드 Swagger UI (:5000/swagger) — 라이트 테마 포털 및 API 분류 목록",
        description="자체 호스팅 한국어 Swagger 포털(/docs·/swagger)에서 실시간 DB·:8007·LLM 상태 배지, 원클릭 담당자/시민 세션 전환, 통합 필터(opsFilter) 및 '서버 상태'·'응대 검사기' 경로가 정상 렌더링된 실제 화면입니다.",
        alt="민원 웹 백엔드 Swagger UI 라이트 테마 화면",
    ),
    WorkSceneSpec(
        filename="rep18_swagger_dark_assist.png",
        caption="2. 민원 웹 백엔드 Swagger UI (:5000/swagger) — 다크 테마 및 POST /api/v1/assist 스키마",
        description="다크 테마에서 POST /api/v1/assist(조기 타지역 차단·병렬 PREFIX-03∥04·EXAONE 차등 추론 연계)의 Parameters·Request body 예시·Try it out이 WCAG 4.5+ 대비로 선명하게 표시되는 실제 화면입니다.",
        alt="민원 웹 백엔드 Swagger UI 다크 테마 POST /api/v1/assist 상세",
    ),
)

WORK_SCENES_PAGE_4: tuple[WorkSceneSpec, ...] = (
    WorkSceneSpec(
        filename="rep18_staff_api_dark.png",
        caption="3. 담당자 콘솔(#/staff/api) — 실시간 상태 카드 및 엔드포인트 빠른 색인 (28개 오퍼레이션)",
        description="담당자 포털 M-05 API 문서 화면에서 PostgreSQL(complaint_app)·검색 :8007·비동기 RAG+LLM 워커 활성 상태와 OpenAPI 22경로/28개 오퍼레이션 빠른 색인(다크 표 대비·openApiSummary 캐싱 적용)을 확인한 화면입니다.",
        alt="담당자 콘솔 엔드포인트 빠른 색인 다크 테마 화면",
    ),
    WorkSceneSpec(
        filename="rep18_rag_8007_docs.png",
        caption="4. 검색 백엔드 FastAPI Swagger (:8007/docs) — 청주 민원 근거 검색(/health · /search)",
        description="민원 백엔드·검사기가 호출하는 RAG 근거 검색 서버(:8007) Swagger UI로, POST /search(query·collection·limit·district·rerank) 요청 규격 및 retrieval_only/requires_gate 계약을 확인한 화면입니다.",
        alt="검색 백엔드 8007 포트 FastAPI Swagger UI 화면",
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
    font-size: 8.5pt;
    line-height: 1.38;
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
    margin: 0 0 8px 0;
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
    padding: 4.3px 7.5px;
  }
  .label-cell {
    width: 14%;
    text-align: center;
    font-weight: bold;
    vertical-align: middle;
    background-color: #ffffff;
    line-height: 1.32;
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
    margin: 1px 0;
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
    margin-bottom: 7px;
    border-bottom: 1.5px solid #222;
    padding-bottom: 4.5px;
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
    font-size: 10.2pt;
    font-weight: 800;
    margin: 8px 0 4px 0;
    color: #111;
  }

  /* 비교표 */
  table.diff-table {
    width: 100%;
    border-collapse: collapse;
    border: 1.2px solid #222;
    margin-top: 3px;
    font-size: 7.9pt;
    line-height: 1.35;
  }
  table.diff-table th {
    background-color: #f3f5f8;
    border: 1px solid #333;
    padding: 4px 6px;
    text-align: center;
    font-weight: bold;
  }
  table.diff-table td {
    border: 1px solid #333;
    padding: 4px 6.5px;
    vertical-align: middle;
    word-break: keep-all;
  }
  .col-center {
    text-align: center;
    white-space: nowrap;
  }
  code {
    font-family: Consolas, "Courier New", monospace;
    font-size: 7.6pt;
    background: #f1f5f9;
    padding: 0.5px 3px;
    border-radius: 2px;
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
  .svg-wrap {
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    background: #0b1220;
    padding: 3px;
    margin-top: 4px;
    text-align: center;
  }
  .svg-wrap img {
    width: 100%;
    max-height: 76mm;
    object-fit: contain;
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


def extract_unique_ui_images(ui_pdf_path: Path) -> list[bytes]:
    """원본 `UI_수정_보고_2026-11-18.pdf`에서 XObject 중복을 제거한 고유 PNG 14장을 추출합니다.

    PDF Form XObject 공유로 인해 페이지 객체상 반복 참조되는 동일 이미지는
    SHA-256 해시로 첫 등장 순서(`그림 1` ~ `그림 14`)만 한 번씩 보존합니다.

    Args:
        ui_pdf_path: 원본 UI 수정 보고서 PDF 파일 경로입니다.

    Returns:
        고유 PNG 이미지 바이트 리스트(14장)입니다.
    """
    reader = pypdf.PdfReader(str(ui_pdf_path))
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


def _build_page1_main_report_html() -> str:
    """1페이지: `업무보고_20261111.pdf` 틀을 계승한 11/18 종합 업무보고 메인 표를 반환합니다.

    Returns:
        1페이지 업무보고 메인 표 HTML 문자열입니다.
    """
    return """<div class="page-break">
<h1 class="title">업무보고</h1>

<table class="report-table">
  <tr>
    <td class="header-label">보고 기간</td>
    <td class="header-val">2026-11-18 (수)</td>
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
    <td colspan="3">112건 실측 잔여 한계 해결·EXAONE 추론 차등/병렬·조기 차단 패치, 백엔드 API·Swagger 포털 점검 및 기민 님 11/18 UI 수정 통합 확인</td>
  </tr>
  <tr>
    <td class="header-label">주제</td>
    <td colspan="3">산학공동프로젝트 서버·AI 최적화, 백엔드 API·Swagger 점검 및 UI 수정 통합 보고 (11/18)</td>
  </tr>
  <tr>
    <td class="label-cell">담당 업무<br>(전체)</td>
    <td colspan="3" class="full-val">
      <div class="section-title">1. 서버 &amp; 검색 DB</div>
      <div class="bullet-item">- 청주시 민원 데이터(FAQ 94건, 공개 민원 사례 5,015건, 부서 127개) 기반 하이브리드 검색 API(:8007) 구축 및 운영</div>
      <div class="bullet-item">- 민원 CRUD·담당자 배정·템플릿·비동기 AI 워커·한국어 Swagger 포털(:5000 /docs·/swagger) 백엔드 설계 및 개발</div>
      <div class="section-title">2. AI &amp; 테스트 웹</div>
      <div class="bullet-item">- RAG 검색 근거 기반 AI 판정·FAQ 안내·담당자 초안·특이민원 순화(PREFIX-00~04) 및 네이버 지도 장소 추적 로직 구현</div>
      <div class="bullet-item">- 단독 응대 검사기(:5010) 및 민원 웹 검사기(#/lab) 구축, 실측 성능 평가·회귀 검증 수행 (마감 2026-11-27)</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">진행 내용<br>(11/18)</td>
    <td colspan="3" class="full-val">
      <div class="section-title">1. 112건·5,015건 실사례 기반 지명/장소 추적·타지역 예외·오탐 보완 (CASE-103·104)</div>
      <div class="bullet-item">- <span class="highlight-tag">도로+번지 보존 및 불용어 정제(place_tool.py)</span> : 숫자 단독 토큰 탈락(93건 누락 원인)을 해결하는 _extract_road_number_pairs() 신설('오송생명14로 283', '2순환로 1374' 최우선 배치), 문자 결합 하이픈 분리(번지 '16-19' 유지) 및 원인조사 불용어('사고로'·'주차로' 등) 보강</div>
      <div class="bullet-item">- <span class="highlight-tag">단일구 도로 확장·광역시 약칭·거주지/운수 예외(district.py)</span> : 닫는 괄호 경계(')]}>:')와 100% 검증 단일구 도로 11종+(구 적중 697→751 +54건, 추가 오분류 0건) 추가, 광역시 '~시' 약칭('서울시'·'대전시')·외부 도로명 차단, 청주 시내버스(사례 913 '청신운수')·타지 거주지 서술('대전 유성구 봉명동 사는데 서원대 후문...') 분리 및 _split_external_residence_clause() 단일 패스 통합</div>
      <div class="bullet-item">- <span class="highlight-tag">다어절 소등 비오탐 교정(followup.py)</span> : _FACILITY_OFF_RE 간격을 0~24자로 확장해 B14('가로등 여러 개가 동시에 꺼져') 정상 민원 오탐 해소</div>
      <div class="section-title">2. 백엔드 응대 API 지연·타임아웃·병렬·토큰 오염 개선 (pipeline.py·settings.py·complete.py)</div>
      <div class="bullet-item">- <span class="highlight-tag">조기 차단·초안 생략·병렬 처리</span> : 순수 타지역 민원은 early_external_reject(:8007·PREFIX-01·03 생략, 0.011s)로 즉시 담당자 검토 연결, out_of_scope 시 PREFIX-03 생략(고정 초안), PREFIX-03∥04 ThreadPoolExecutor 병렬 실행(EXAONE 1.05s 스태거) 적용</div>
      <div class="bullet-item">- <span class="highlight-tag">EXAONE 추론 차등 및 버그 수정</span> : settings_for_role()로 1차 판정 high / 빠른 단계 low(4096 상한) 차등화, Codex 비도구 _disable_mcp, 실패 호출 시 직전 usage_box 토큰 오염 버그 제거 및 POST /api/v1/assist·/lab/complaints·비동기 워커 반영</div>
      <div class="section-title">3. 백엔드 API·Swagger 포털 품질 점검 및 문서/회귀 자동화 (CASE-102·103·104)</div>
      <div class="bullet-item">- <span class="highlight-tag">Swagger 포털·콘솔 최종 점검</span> : :5000 OpenAPI 22경로(28개 오퍼레이션) 다크 표 대비 교정(1.05→#f8fafc)·태그 칩 대비 상향·openApiSummary 캐싱·빈 Authorize 모달 제거 유지 확인, :5000/swagger 라이트/다크·#/staff/api·:8007/docs 4종 실서버 캡처 ([별첨 1] 수록)</div>
      <div class="bullet-item">- <span class="highlight-tag">규칙 회귀·README·하네스 정비</span> : 112건·5,015건 1초 규칙 회귀(회귀검증_112건_규칙.py) 구축, PREFIX-00~04 계층 구조 SVG 신설 및 하네스 6종·README 가독성 개편</div>
      <div class="section-title">4. 기민 님 11/18 UI 수정 사항 통합 확인 (UI_수정_보고_2026-11-18.pdf)</div>
      <div class="bullet-item">- <span class="highlight-tag">접근성·사용성·다크 대비 점검</span> : WCAG 1.4.3/1.4.4(12px·4.5:1 대비), 색 토큰 6개, 상담 바 우선 배치, Hick/Fitts/Nielsen 휴리스틱, 담당자 상세 필터 접기, 민원 철회 분리, 응대 검사기 다크 보조 글자 61개 흰색 전환 등 확인 ([별첨 2] 원문·이미지 14장 그대로 수록)</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">진행 결과</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- <span class="highlight-tag">백엔드·RAG·UI 통합 검증</span> : PG 격리 포함 백엔드 <strong>168/168 통과</strong>(24.63s), 112건 결정론적 규칙 회귀 <strong>실패 0건 · 5,015건 외부오탐 0건</strong>, 검색 <strong>49 passed</strong>(3 skip)·rag.verify 통과, UI 문법 19·단위 <strong>22/22 통과</strong>, mypy·black 오류 0건</div>
      <div class="bullet-item">- <span class="highlight-tag">실서버 API·Swagger 동작</span> : :5000(/api/v1/health·/docs·/swagger·#/staff/api), :8007(/docs), :5010 순수 타지역 early_external_reject <strong>0.011s</strong> 응답 확인</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">남은 일</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- EXAONE_API_KEY 한도 확보 후 112건 실원격 일괄 재실측 및 담당자 실시간 SSE 알림·최종 발표 시나리오 정리 (마감 2026-11-27)</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">참고 사항</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- 역할 분담 : 기민 님 / UI·접근성·디자인 토큰 개선([별첨 2]), 연승현 / 백엔드 API·Swagger 포털·AI 파이프라인/지명/병렬 최적화([별첨 1])</div>
      <div class="bullet-item">- <strong>[별첨 1: 2~4쪽]</strong> 11/18 백엔드 API 변경/체계표·PREFIX 구조도·검증표·Swagger 4종 캡처, <strong>[별첨 2: 5~10쪽]</strong> 'UI 수정 보고서(2026-11-18)' 원문·고유 이미지 14장 무수정 수록</div>
    </td>
  </tr>
</table>
</div>"""


def _build_att1_summary_page_html() -> str:
    """2페이지: [별첨 1] 11/18 백엔드 API 변경/누적 현황표, PREFIX 구조도 및 최종 검증표를 반환합니다.

    Returns:
        2페이지 HTML 문자열입니다.
    """
    prefix_svg_uri = encode_file(DEFAULT_PREFIX_SVG)
    return f"""<div class="page-break">
  <div class="att-header">
    <h2>[별첨 1] 11/18 백엔드 API 변경 · AI 파이프라인 최적화 및 검증 요약</h2>
    <p class="att-meta">작성자: 연승현 · 기준일: 2026-11-18 (CASE-102 ~ CASE-104 백엔드·API·AI 최적화 반영)</p>
  </div>

  <div class="att-sec-title">1. 백엔드 API 수정 · 개선 및 누적 엔드포인트 체계 (:5000 22경로/28오퍼레이션 · :5010 · :8007)</div>
  <table class="diff-table">
    <thead>
      <tr>
        <th style="width: 24%;">대상 API · 모듈</th>
        <th style="width: 48%;">11/18 수정 · 최적화 내용</th>
        <th style="width: 28%;">응답·계약 변화 및 비고</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><code>POST /api/v1/assist</code><br><code>POST /api/v1/assist/stream</code><br><code>POST /api/v1/lab/complaints</code><br>(<code>pipeline.py</code>·<code>district.py</code>)</td>
        <td>① 순수 타 지자체 주소 감지 시 <code>:8007</code> 검색·<code>PREFIX-01</code>·<code>PREFIX-03</code> 생략 후 즉시 <code>out_of_scope</code> 반환<br>② <code>out_of_scope</code> 시 고정 초안 반환 / <code>PREFIX-03∥04</code> 병렬 실행<br>③ 실패 단계 직전 <code>usage_box</code> 오염 버그 제거</td>
        <td><code>retrieval.pipeline="early_external_reject"</code> (<strong>0.011s</strong> 응답), 거주지 서술·청주 시내버스 예외 분리, <code>codex[].usage</code> 정확성 보장</td>
      </tr>
      <tr>
        <td><code>POST /api/v1/complaints</code><br>비동기 AI 워커 연동<br>(<code>settings.py</code>·<code>complete.py</code>)</td>
        <td>① <code>settings_for_role()</code>로 EXAONE 1차 판정 <code>high</code> / 빠른 단계(02·03·04) <code>low</code> 및 4096 상한 자동 적용<br>② <code>codex_cli</code> 비도구 단계 <code>_disable_mcp</code> 적용</td>
        <td><code>POST /complaints</code> 등록 후 비동기 분석 지연·타임아웃 대폭 완화, 미게시 초안 시민 비노출 유지</td>
      </tr>
      <tr>
        <td><code>GET /docs</code> · <code>/swagger</code><br><code>#/staff/api</code> 포털 &amp; API<br>(<code>swagger_page.py</code>·<code>api.py</code>)</td>
        <td>자체 호스팅 한국어 Swagger 포털 다크 대비(1.05→#f8fafc)·태그 칩 대비 수정, <code>openApiSummary</code> 캐싱, 빈 <code>Authorize</code> 모달 제거·태그 설명 정정(<code>CASE-101·102</code>)</td>
        <td>22경로(28오퍼레이션) OpenAPI 3.1 명세, 원클릭 <code>staff</code>/<code>citizen</code> 세션 전환, Try it out 정상 동작</td>
      </tr>
      <tr>
        <td>누적 업무 API 전체 구성<br>(<code>src/complaints/api.py</code>)</td>
        <td><strong>시연 세션</strong>(<code>/session</code>) · <strong>민원 CRUD</strong>(<code>/complaints</code>·<code>/delete</code>·<code>/retract</code>·<code>/messages</code>) · <strong>담당자</strong>(<code>/departments</code> 127개·<code>/assignment</code>·<code>/templates</code>·<code>/draft</code>·<code>/publish</code>) · <strong>AI·검사기</strong>(<code>/assist</code>·<code>/jobs</code>·<code>:5010</code>·<code>:8007</code>)</td>
        <td><code>GET /api/v1/health</code> 200 OK (<code>postgresql</code>, <code>assistSearch=True</code>, <code>aiConnected=True</code>)</td>
      </tr>
    </tbody>
  </table>

  <div class="att-sec-title" style="margin-top: 7px;">2. 계층형 시스템 프롬프트(PREFIX-00 ~ 04) 조립 및 최적화 구조</div>
  <div class="svg-wrap">
    <img src="{prefix_svg_uri}" alt="PREFIX-00 ~ 04 계층형 시스템 프롬프트 조립 및 분기 구조">
  </div>

  <div class="att-sec-title" style="margin-top: 7px;">3. 최종 코드 · 회귀 · 실서버 검증 결과 (2026-11-18 ~ 19 최종 점검 기준)</div>
  <table class="diff-table">
    <thead>
      <tr>
        <th style="width: 24%;">검증 항목</th>
        <th style="width: 30%;">실행 명령 · 대상</th>
        <th style="width: 19%;">결과</th>
        <th style="width: 27%;">비고 및 확인 범위</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>백엔드 PG 격리 테스트</strong></td>
        <td><code>RUN_PG_TESTS=1 pytest src/tests</code></td>
        <td class="col-center"><strong>168 passed</strong> (24.63s)</td>
        <td>0 실패 · 0 건너뜀 (신규 지명/병렬/토큰 격리 포함)</td>
      </tr>
      <tr>
        <td><strong>112건·5,015건 규칙 회귀</strong></td>
        <td><code>scripts/회귀검증_112건_규칙.py</code></td>
        <td class="col-center"><strong>112건 실패 0건</strong></td>
        <td>5,015건 구 적중 697→<strong>751</strong>(+54) · 외부 오탐 <strong>0건</strong></td>
      </tr>
      <tr>
        <td><strong>RAG · 무결성 · UI · 타입</strong></td>
        <td><code>rag/tests</code>·<code>rag.verify</code>·<code>ui check/test</code>·<code>mypy</code>·<code>black</code></td>
        <td class="col-center"><strong>전체 통과</strong></td>
        <td>RAG 49 pass(3 skip)·<code>rag.verify</code> true·UI 22/22·0 오류</td>
      </tr>
      <tr>
        <td><strong>라이브 API · Swagger 확인</strong></td>
        <td><code>:5000/swagger</code>·<code>#/staff/api</code>·<code>:8007/docs</code>·<code>:5010</code></td>
        <td class="col-center"><strong>200 OK · 0.011s</strong></td>
        <td>타지역 <code>early_external_reject</code> 0.011s, Swagger 4종 캡처</td>
      </tr>
    </tbody>
  </table>
</div>"""


def _build_att1_scenes_page_html(
    scenes_dir: Path,
    scenes: tuple[WorkSceneSpec, ...],
    title: str,
    subtitle: str,
) -> str:
    """3~4페이지: [별첨 1] 백엔드 Swagger 포털 · 담당자 콘솔 · 검색 API 실서버 캡처 2종씩을 생성합니다.

    Args:
        scenes_dir: 캡처 PNG 파일이 저장된 폴더 경로입니다.
        scenes: 한 A4 쪽에 순서대로 배치할 캡처 메타데이터 2건입니다.
        title: 페이지 상단 제목입니다.
        subtitle: 페이지 부제목 설명입니다.

    Returns:
        A4 1페이지 HTML 문자열입니다.
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
    <h2>{html.escape(title)}</h2>
    <p class="att-meta">{html.escape(subtitle)}</p>
  </div>
{blocks}
</div>"""


def _build_att2_ui_cover_html() -> str:
    """5페이지: [별첨 2] `UI_수정_보고_2026-11-18.pdf` 개요·원칙 설명·목록 표지를 원문 무수정으로 구성합니다.

    Returns:
        UI 수정 보고서 개요·목록 페이지 HTML 문자열입니다.
    """
    rows = "\n".join(
        f"""      <tr>
        <td class="col-center"><strong>{html.escape(code)}</strong></td>
        <td>{html.escape(title)}</td>
      </tr>"""
        for code, title in UI_FIX_INDEX
    )
    return f"""<div class="page-break">
  <div class="att-header">
    <h2>[별첨 2] UI 수정 보고서 (원본 내용 무수정 · 기존 업무보고 양식 적용)</h2>
    <p class="att-meta">원본 문서: UI_수정_보고_2026-11-18.pdf (개요·수정 항목 2-1~2-9 및 고유 캡처 14장 원문 그대로 수록)</p>
  </div>

  <h1 class="sub-title" style="margin-top: 8px;">UI 수정 보고서</h1>

  <div class="att-sec-title">1. 기본 정보 및 개요</div>
  <table class="report-table" style="font-size: 8.3pt;">
    <tr>
      <td class="header-label">작성일</td>
      <td class="header-val">2026. 11. 18.</td>
      <td class="header-label">캡처 환경</td>
      <td class="header-val">Chrome 화면, 시험용 데이터(DEMO)</td>
    </tr>
    <tr>
      <td class="header-label">수정 전</td>
      <td class="header-val">2026. 11. 17. 보고 시점 수정본</td>
      <td class="header-label">수정 후</td>
      <td class="header-val">2026. 11. 18. 수정본</td>
    </tr>
    <tr>
      <td class="header-label">목적</td>
      <td colspan="3">시민 화면과 담당자 화면의 글자 가독성, 버튼 배치, 다크 모드 대비 개선</td>
    </tr>
    <tr>
      <td class="header-label">근거</td>
      <td colspan="3">접근성 기준(WCAG 1.4.3, 1.4.4), Hick 법칙, Fitts 법칙, Nielsen 휴리스틱(시스템 상태 가시성, 오류 예방) 적용</td>
    </tr>
    <tr>
      <td class="header-label">원칙 설명</td>
      <td colspan="3">WCAG는 웹 접근성 기준, Hick 법칙은 선택지가 많을수록 결정이 느려지는 원칙, Fitts 법칙은 대상이 작고 멀수록 누르기 어려운 원칙, Nielsen 휴리스틱은 사용성을 점검하는 기본 원칙 / WCAG 1.4.3은 글자와 배경의 명암 대비 기준, 1.4.4는 글자를 확대해도 내용이 깨지지 않는 기준</td>
    </tr>
    <tr>
      <td class="header-label">범위</td>
      <td colspan="3">시민 홈, 시민 민원 상세, 담당자 접수, 검토 목록, 응대 검사기(다크 모드)</td>
    </tr>
  </table>

  <div class="att-sec-title" style="margin-top: 12px;">2. 수정 항목 목차 (원본 2-1 ~ 2-9 전체)</div>
  <table class="diff-table">
    <thead>
      <tr>
        <th style="width: 12%;">항목 번호</th>
        <th style="width: 88%;">수정 항목 제목 (원문 그대로)</th>
      </tr>
    </thead>
    <tbody>
{rows}
    </tbody>
  </table>
  <p style="margin: 6px 0 0 0; font-size: 7.7pt; color: #555;">※ 주: 원본 PDF 2쪽의 '2-8. 담당 버튼 이름 (스크린리더)'와 3쪽의 '2-8. 민원 철회 위험 영역 분리'는 원본 번호 표기를 그대로 유지하며 목차 표기상 뒤쪽 항목을 2-8*로만 구분했습니다.</p>
</div>"""


def _build_ui_item_card_html(item: UiFixItem, unique_images: list[bytes]) -> str:
    """UI 수정 보고서 개별 항목 카드 HTML을 원문 무수정으로 조립합니다.

    Args:
        item: UI 수정 항목 원문 메타데이터입니다.
        unique_images: 원본 PDF에서 추출한 고유 PNG 바이트 14장 목록입니다.

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

    captures_html = ""
    if item.captures:
        layout_class = "ui-cap-grid" if item.side_by_side else "ui-cap-stack"
        capture_blocks = "\n".join(
            f"""    <div>
      <div class="ui-cap-label">{html.escape(cap.label)}</div>
      <div class="ui-img-box">
        <img src="{encode_binary_data_uri(unique_images[cap.unique_index], 'image/png')}"
             alt="{html.escape(item.title + ' - ' + cap.label)}"
             style="max-height: {item.max_img_height_mm}mm;">
      </div>
    </div>"""
            for cap in item.captures
        )
        captures_html = f'\n  <div class="{layout_class}">\n{capture_blocks}\n  </div>'

    return f"""  <div class="ui-item-card">
    <h3 class="ui-item-head">{html.escape(item.title)}</h3>
    <table class="ui-meta-table">
{detail_rows}
    </table>
{note_html}{captures_html}
  </div>"""


def _build_att2_ui_detail_pages_html(unique_images: list[bytes]) -> str:
    """[별첨 2] `UI_수정_보고_2026-11-18.pdf` 상세 항목 2-1~2-9 페이지들을 생성합니다.

    Args:
        unique_images: 원본 PDF에서 추출한 고유 PNG 바이트 14장 목록입니다.

    Returns:
        페이지 나눔이 포함된 상세 내역 HTML 문자열입니다.
    """
    by_code = {item.code: item for item in UI_FIX_ITEMS}
    pages: list[str] = []
    for group in UI_FIX_PAGE_GROUPS:
        cards = "\n".join(
            _build_ui_item_card_html(by_code[code], unique_images) for code in group
        )
        label = (
            group[0].replace("*", "")
            if len(group) == 1
            else f"{group[0].replace('*', '')} ~ {group[-1].replace('*', '')}"
        )
        pages.append(
            f"""<div class="page-break">
  <div class="att-header">
    <h2>[별첨 2] UI 수정 보고서 (2026-11-18) · 상세 내역 ({label})</h2>
    <p class="att-meta">캡처 환경: Chrome 화면, 시험용 데이터(DEMO) · 원본 내용 및 이미지 무수정</p>
  </div>
{cards}
</div>"""
        )
    return "\n\n".join(pages)


def build_report_html(scenes_dir: Path, ui_pdf_path: Path) -> str:
    """11/18 종합 업무보고 + Swagger 검증 + UI 수정 보고서 전체 HTML을 조립합니다.

    Args:
        scenes_dir: 라이브 Swagger 스크린샷 PNG 파일 디렉터리입니다.
        ui_pdf_path: 원본 `UI_수정_보고_2026-11-18.pdf` 파일 경로입니다.

    Returns:
        인쇄 가능한 완결형 HTML 문자열입니다.
    """
    unique_images = extract_unique_ui_images(ui_pdf_path)
    if len(unique_images) != 14:
        raise ValueError(
            f"UI_수정_보고_2026-11-18.pdf에서 14개 고유 이미지를 예상했으나 {len(unique_images)}개 추출됨"
        )
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>업무보고 및 UI 수정 보고서 (2026-11-18)</title>
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
    "[별첨 1] 백엔드 API Swagger UI 포털 실서버 확인 (라이트 · 다크)",
    ":5000 자체 호스팅 한국어 Swagger UI (/swagger) — 세션 연동 · 통합 검색 · /api/v1/assist 스키마",
)}

{_build_att1_scenes_page_html(
    scenes_dir,
    WORK_SCENES_PAGE_4,
    "[별첨 1] 담당자 API 콘솔(#/staff/api) · 검색 백엔드 Swagger (:8007/docs)",
    "엔드포인트 28개 빠른 색인 및 RAG 근거 검색 FastAPI Swagger 실서버 동작 캡처",
)}

{_build_att2_ui_cover_html()}

{_build_att2_ui_detail_pages_html(unique_images)}

</body>
</html>
"""


def main() -> None:
    """11월 18일 종합 업무보고 PDF(`docs/report/업무보고_20261118.pdf`)를 생성합니다.

    Raises:
        FileNotFoundError: 원본 UI 보고서 PDF, PREFIX SVG 또는 Swagger 캡처 PNG가 없을 때 발생합니다.
    """
    ui_pdf = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_UI_PDF
    scenes_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_SCENES_DIR
    out_pdf = Path(sys.argv[3]) if len(sys.argv) > 3 else OUTPUT_PDF_PATH

    if not ui_pdf.is_file():
        raise FileNotFoundError(f"원본 UI 보고서 PDF가 없습니다: {ui_pdf}")
    if not DEFAULT_PREFIX_SVG.is_file():
        raise FileNotFoundError(f"PREFIX 구조도 SVG가 없습니다: {DEFAULT_PREFIX_SVG}")
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
