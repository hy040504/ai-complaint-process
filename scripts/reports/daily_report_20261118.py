"""11월 18일 종합 업무보고 PDF 생성 스크립트입니다.

1페이지: '업무보고_20261111.pdf' 틀을 바탕에 두고, 내부 코드·함수 용어를 풀어서 정리한
         11/18 업무보고 메인 표
2~4페이지: [별첨 1] 11/18 백엔드 API 변경/누적 현황표(쉬운 기능 중심), AI 처리 흐름도,
           점검 결과 요약 및 라이브 Swagger 페이지 실서버 캡처 4종
5~10페이지: [별첨 2] 'UI_수정_보고_2026-11-18.pdf' 원문 내용 및 고유 캡처 14장 무수정 수록
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
    UiFixItem,
    build_ui_detail_pages_html,
    encode_file,
    extract_unique_pdf_images,
    render_html_to_pdf,
)

ROOT_DIR = _SCRIPTS_DIR.parents[1]
DEFAULT_UI_PDF = Path(
    r"C:\Users\user\Documents\카카오톡 받은 파일\UI_수정_보고_2026-11-18.pdf"
)
DEFAULT_SCENES_DIR = Path(
    r"C:\Users\user\.gemini\antigravity-cli\brain\3197986d-ee70-477b-9852-28bbba3b7616\scratch"
)
OUTPUT_PDF_PATH = ROOT_DIR / "docs" / "reports" / "daily" / "업무보고_20261118.pdf"


@dataclass(frozen=True)
class WorkSceneSpec:
    """11/18 백엔드 Swagger UI 실서버 캡처 한 건의 메타데이터입니다."""

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
        caption="1. 민원 업무 백엔드 API 문서 (Swagger) — 기본 라이트 화면",
        description="브라우저에서 22종 민원 업무 API의 분류와 설명을 한국어로 확인하고, 상단 버튼을 눌러 담당자·시민 체험 상태를 바꿔 가며 바로 시험해 볼 수 있는 실제 화면입니다.",
        alt="민원 업무 백엔드 API 문서 기본 라이트 화면",
    ),
    WorkSceneSpec(
        filename="rep18_swagger_dark_assist.png",
        caption="2. 민원 업무 백엔드 API 문서 (Swagger) — 다크 모드 및 AI 응대 요청 상세",
        description="어두운 화면에서도 글자가 선명히 읽히도록 명암 대비를 보완했으며, AI 민원 응대 API(/api/v1/assist)의 입력 항목과 바로 실행(Try it out) 기능을 확인할 수 있는 화면입니다.",
        alt="민원 업무 백엔드 API 문서 다크 모드 AI 응대 상세 화면",
    ),
)

WORK_SCENES_PAGE_4: tuple[WorkSceneSpec, ...] = (
    WorkSceneSpec(
        filename="rep18_staff_api_dark.png",
        caption="3. 담당자 사이트 내 백엔드 API 현황 및 전체 기능 목록 화면",
        description="담당자 포털 안에서 데이터베이스·검색·AI 연결 상태를 한눈에 살펴보고, 총 28개 세부 백엔드 기능을 분류와 검색어로 빠르게 찾을 수 있는 화면입니다.",
        alt="담당자 사이트 내 백엔드 API 현황 및 전체 기능 목록 화면",
    ),
    WorkSceneSpec(
        filename="rep18_rag_8007_docs.png",
        caption="4. 청주 민원 근거 검색 서버 API 문서 (Swagger)",
        description="민원 내용과 비슷한 자주 묻는 민원·과거 사례를 찾아 주는 별도 검색 서버(:8007/docs)의 API 문서 화면으로, 검색 요청 형식과 응답 기준을 확인할 수 있습니다.",
        alt="청주 민원 근거 검색 서버 API 문서 화면",
    ),
)


_REPORT_CSS = WORK_REPORT_CSS


def _build_page1_main_report_html() -> str:
    """1페이지: `업무보고_20261111.pdf` 틀을 바탕으로 쉽고 명확히 정리한 11/18 메인 표를 반환합니다.

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
    <td colspan="3">실전 테스트에서 남은 주소·지명 인식 및 AI 응답 지연 문제 개선, 백엔드 API·문서 페이지(Swagger) 점검 및 기민 님 11/18 UI 수정 통합 확인</td>
  </tr>
  <tr>
    <td class="header-label">주제</td>
    <td colspan="3">산학공동프로젝트 민원 주소·응답 속도 개선, 백엔드 API·문서(Swagger) 점검 및 UI 수정 통합 보고 (11/18)</td>
  </tr>
  <tr>
    <td class="label-cell">담당 업무<br>(전체)</td>
    <td colspan="3" class="full-val">
      <div class="section-title">1. 서버 &amp; 검색 기능</div>
      <div class="bullet-item">- 청주시 민원 자료(자주 묻는 민원 94건, 공개 민원 사례 5,015건, 부서 127개)를 바탕으로 비슷한 민원과 근거를 찾아주는 검색 서버 구축 및 운영</div>
      <div class="bullet-item">- 민원 접수·조회·답변 관리 및 백엔드 API 안내 화면(Swagger) 개발과 연동 유지</div>
      <div class="section-title">2. AI &amp; 테스트 화면</div>
      <div class="bullet-item">- 검색 자료를 바탕으로 AI가 답변 안내·부서 추천·거친 표현 순화를 판단하는 응대 로직과 지도 기반 장소 찾기 기능 개발</div>
      <div class="bullet-item">- AI 응답 결과를 바로 시험해 볼 수 있는 검사기 화면 및 민원 웹 연동 관리 (마감 2026-11-27)</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">진행 내용<br>(11/18)</td>
    <td colspan="3" class="full-val">
      <div class="section-title">1. 민원 주소·장소 인식 및 오탐 개선</div>
      <div class="bullet-item">- <span class="highlight-tag">도로명과 번지 번호 함께 인식</span> : '오송생명14로 283', '2순환로 1374'처럼 도로명 뒤에 붙은 번지 숫자가 지도 검색에서 빠지던 문제를 고치고, '사고로'·'주차로' 같은 일반 표현이 장소 이름으로 잘못 잡히지 않게 걸러냄</div>
      <div class="bullet-item">- <span class="highlight-tag">청주 지역 판별 확대 및 타 지역·예외 분리</span> : 괄호 뒤 지명('긴급)복대동')과 청주 단일 구 주요 도로명을 반영해 관할 구 판별 건수를 높이고(697→751건), '서울시'·'경기도 화성시 동탄대로' 등 타 지역은 정확히 차단하되 타지 거주 후 청주 시설을 신고하거나 청주 시내버스를 이용하는 민원은 정상 처리되도록 분리함</div>
      <div class="bullet-item">- <span class="highlight-tag">시설 고장 신고 오탐 해소</span> : '가로등 여러 개가 동시에 꺼져 있습니다'처럼 시설 고장을 알리는 평범한 문장이 거친 표현으로 잘못 분류되던 판단 기준을 손봄</div>
      <div class="section-title">2. AI 응답 지연·시간 초과 개선 및 백엔드 효율화</div>
      <div class="bullet-item">- <span class="highlight-tag">타 지역 민원 즉시 검토 연결</span> : 명백한 타 지역 관할 민원으로 확인되면 검색과 불필요한 AI 분석 단계를 건너뛰고 즉시(약 0.01초) 담당자 검토로 넘기도록 단축함</div>
      <div class="bullet-item">- <span class="highlight-tag">단계별 추론 최적화 및 동시 처리</span> : AI의 깊은 생각(추론)은 핵심 1차 판정에만 적용하고 안내·요약·순화 단계는 빠르고 가볍게 조정했으며, 담당자 초안과 순화 요약을 동시에 실행하고 관할 외 민원은 불필요한 초안 생성을 생략해 대기 시간을 크게 줄임</div>
      <div class="bullet-item">- <span class="highlight-tag">오류 시 사용량 섞임 수정</span> : 순화 단계가 실패했을 때 앞선 판정 단계의 사용량 기록이 남아 잘못 기록되던 오류를 바로잡음</div>
      <div class="section-title">3. 백엔드 API 정리·Swagger 페이지 점검 및 검증·문서 정비</div>
      <div class="bullet-item">- <span class="highlight-tag">API 정리 및 Swagger 화면 확인</span> : 민원 업무 백엔드(22종 API)와 검색 서버 API 동작을 점검하고, 다크 모드 글씨 대비 개선·중복 계산 축소·실서버 Swagger 화면 4종 캡처를 정리함 ([별첨 1] 수록)</div>
      <div class="bullet-item">- <span class="highlight-tag">자동 규칙 점검 및 안내 문서 개편</span> : 유료·원격 AI 호출 없이도 1초 내로 지명·오탐 규칙을 검증할 수 있는 도구를 마련하고, 프로젝트 소개 문서(README)에 AI 지시문 구조 그림과 읽기 쉬운 요약표를 추가함</div>
      <div class="section-title">4. 기민 님 11/18 UI 수정 사항 통합 확인 (UI_수정_보고_2026-11-18.pdf)</div>
      <div class="bullet-item">- <span class="highlight-tag">접근성·사용성·다크 대비 점검</span> : 시민 화면 글자 크기 확대(12px 이상)·명암 대비 개선, 색 기준 6종 정리, 상담 입력창 상단 이동, 담당자 상세 필터 접기, 민원 철회 영역 분리, 검사기 다크 모드 보조 글자 61곳 흰색 전환 확인 ([별첨 2] 원문 그대로 수록)</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">진행 결과</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- <span class="highlight-tag">전체 기능 및 규칙 재확인 통과</span> : 백엔드·DB 기능 시험 <strong>168건 전부 통과</strong>, 112건 민원 규칙 재점검 <strong>실패 0건 · 타 지역 오탐 0건</strong>, 검색·화면 동작 시험 및 문법 검사 모두 이상 없이 통과함</div>
      <div class="bullet-item">- <span class="highlight-tag">실서버 API·Swagger 동작 확인</span> : 민원 업무 서버·담당자 API 목록·검색 서버(Swagger)가 정상 작동하며, 타 지역 민원 조기 분리 기능이 <strong>0.011초</strong> 만에 즉시 응답함을 확인함</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">남은 일</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- 외부 AI 모델 사용 한도 확보 후 112건 실서버 재측정 진행, 담당자 실시간 알림 및 최종 발표 자료 정리 (마감 2026-11-27)</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">참고 사항</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- 역할 분담 : 기민 님 / 화면 사용성·접근성 개선([별첨 2]), 연승현 / 백엔드 API·Swagger·AI 응답 품질 및 속도 개선([별첨 1])</div>
      <div class="bullet-item">- 구성 : <strong>[별첨 1: 2~4쪽]</strong> 백엔드 API 정리·AI 처리 흐름·점검 결과 및 Swagger 캡처 4종, <strong>[별첨 2: 5~10쪽]</strong> 'UI 수정 보고서(2026-11-18)' 원문·고유 이미지 14장 무수정 수록</div>
    </td>
  </tr>
</table>
</div>"""


def _build_att1_summary_page_html() -> str:
    """2페이지: [별첨 1] 쉬운 한국어 중심의 백엔드 API 정리표, AI 처리 흐름도 및 점검 결과표를 반환합니다.

    Returns:
        2페이지 HTML 문자열입니다.
    """
    return """<div class="page-break">
  <div class="att-header">
    <h2>[별첨 1] 11/18 백엔드 API 변경 요약 · AI 처리 흐름 및 점검 결과</h2>
    <p class="att-meta">작성자: 연승현 · 기준일: 2026-11-18 (기술·코드 세부명 대신 기능과 효과 중심으로 정리)</p>
  </div>

  <div class="att-sec-title">1. 백엔드 API 수정·개선 및 전체 API 구성 (민원 업무 22종 · 검사기 · 검색 서버)</div>
  <table class="diff-table">
    <thead>
      <tr>
        <th style="width: 24%;">API 영역 · 경로</th>
        <th style="width: 47%;">11/18 수정 및 개선 내용</th>
        <th style="width: 29%;">기대 효과 및 동작 변화</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>AI 민원 응대 · 검사기 API</strong><br><code>POST /api/v1/assist</code><br><code>POST /api/v1/assist/stream</code><br>(단독 검사기 <code>:5010</code> 포함)</td>
        <td>① 명백한 타 지역 민원은 검색과 AI 호출을 건너뛰고 즉시 담당자 검토로 넘김<br>② 관할 외 민원의 불필요한 초안 생성을 생략하고, 담당자 초안·순화 요약을 동시에 처리해 대기 시간을 줄임<br>③ 단계 오류 시 직전 사용량 기록이 섞이던 문제 수정</td>
        <td>순수 타 지역 민원 약 <strong>0.011초</strong> 즉시 응답, 타지 거주 후 청주 신고·청주 시내버스 예외 정확 구분, 토큰 기록 신뢰성 확보</td>
      </tr>
      <tr>
        <td><strong>민원 등록 · 비동기 AI 연계</strong><br><code>POST /api/v1/complaints</code></td>
        <td>① 민원 접수 후 뒤에서 동작하는 AI 분석에서 핵심 1차 판정에만 깊은 추론을 쓰고 나머지 단계는 빠르게 처리하도록 조정<br>② 도구가 필요 없는 안내·순화 단계의 불필요한 외부 도구 호출 비활성화</td>
        <td>접수 후 AI 분석 대기·시간 초과 오류 감소, 담당자가 게시하기 전까지 시민 화면 비노출 유지</td>
      </tr>
      <tr>
        <td><strong>Swagger 문서 · API 콘솔</strong><br><code>GET /docs</code> · <code>/swagger</code><br>(담당자 화면 API 메뉴)</td>
        <td>한국어 API 안내 화면의 다크 모드 글씨 명암 대비(4.5 이상) 보완, API 목록 재계산 중복 축소, 무기능 빈 로그인(Authorize) 창 제거 유지</td>
        <td>22종 API 경로(28개 세부 기능) 한국어 제공, 담당자·시민 체험 클릭 전환 및 바로 시험(Try it out) 지원</td>
      </tr>
      <tr>
        <td><strong>백엔드 API 누적 전체 구성</strong><br>(<code>:5000</code> 업무 · <code>:8007</code> 검색)</td>
        <td>체험 세션 전환 · 민원 등록/조회/수정/철회/영구 삭제 · 청주시 127개 부서 배정 · 답변 템플릿 추가/삭제 · AI 분석 · 서버 상태 점검 및 검색 API(<code>/health</code>·<code>/search</code>)</td>
        <td>상태 확인(<code>/api/v1/health</code>) 기준 DB·검색·AI 워커 모두 정상 연결, 자동 이관 안 함 원칙 유지</td>
      </tr>
    </tbody>
  </table>

  <div class="att-sec-title" style="margin-top: 9px;">2. 개선된 AI 민원 응대 처리 흐름 (한눈에 보기)</div>
  <div class="flow-box">
    <div class="flow-grid">
      <div class="flow-step">
        <div class="flow-step-num">1단계 · 사전 확인</div>
        <div class="flow-step-title">지명 · 장소 · 관할 분리</div>
        <div class="flow-step-desc">도로+번지·거주지 서술·시내버스 예외를 가려내고, 순수 타 지역이면 0.01초 만에 즉시 검토로 보냄</div>
      </div>
      <div class="flow-arrow">→</div>
      <div class="flow-step">
        <div class="flow-step-num">2단계 · 근거 검색</div>
        <div class="flow-step-title">FAQ · 유사 사례 분리 검색</div>
        <div class="flow-step-desc">청주 공식 자주 묻는 민원 94건과 과거 부서 사례 5,015건을 섞지 않고 따로 검색</div>
      </div>
      <div class="flow-arrow">→</div>
      <div class="flow-step">
        <div class="flow-step-num">3단계 · 1차 판정</div>
        <div class="flow-step-title">처리 갈래 · 문맥 판단</div>
        <div class="flow-step-desc">안내 가능·부서 추천·담당자 검토 여부를 가리고, 시설 고장과 실제 욕설·비꼬기를 구분</div>
      </div>
      <div class="flow-arrow">→</div>
      <div class="flow-step">
        <div class="flow-step-num">4단계 · 결과 생성</div>
        <div class="flow-step-title">갈래별 안내 · 초안 작성</div>
        <div class="flow-step-desc">핵심 정책 검증 통과 후 시민 안내문이나 담당자 초안·순화 요약을 빠르게 생성</div>
      </div>
    </div>
    <div class="flow-branches">
      <div class="flow-branch safe">
        <b>① FAQ 안내 (빠른 경량 모드)</b>
        공식 FAQ 대상·기한·주의사항을 빠뜨리지 않고 정중한 안내문 생성
      </div>
      <div class="flow-branch">
        <b>② 담당자 초안 ∥ 순화 동시 처리</b>
        현장 조치가 필요할 때 답변 초안과 거친 표현 정리를 동시에 실행해 대기 시간 단축
      </div>
      <div class="flow-branch warn">
        <b>③ 관할 외 조기 처리</b>
        타 지역 사안은 불필요한 초안 AI 호출 없이 고정 안내문만 달아 담당자에게 전달
      </div>
    </div>
  </div>

  <div class="att-sec-title" style="margin-top: 9px;">3. 최종 점검 및 시험 결과 (2026-11-18 ~ 19 기준)</div>
  <table class="diff-table">
    <thead>
      <tr>
        <th style="width: 24%;">점검 항목</th>
        <th style="width: 31%;">확인 대상 및 내용</th>
        <th style="width: 17%;">결과</th>
        <th style="width: 28%;">주요 수치 및 비고</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>백엔드 · DB 기능 시험</strong></td>
        <td>민원 등록·조회·권한·AI 처리·API 응답 전수 시험</td>
        <td class="col-center"><strong>168건 전부 통과</strong></td>
        <td>실패 0건 · 신규 지명/병렬 시험 포함</td>
      </tr>
      <tr>
        <td><strong>주소 · 오탐 규칙 점검</strong></td>
        <td>실증 112건 및 공개 사례 5,015건 기준 규칙 재확인</td>
        <td class="col-center"><strong>112건 실패 0건</strong></td>
        <td>구 적중 697→<strong>751건</strong>(+54) · 외부 오탐 <strong>0건</strong></td>
      </tr>
      <tr>
        <td><strong>검색 · 화면 · 문법 점검</strong></td>
        <td>검색 단위 시험, DB 원본 대조, 화면·문법 검사</td>
        <td class="col-center"><strong>전체 통과</strong></td>
        <td>검색 49건(원본 대조 일치) · 화면 시험 22건 · 오류 0건</td>
      </tr>
      <tr>
        <td><strong>실서버 API · Swagger 확인</strong></td>
        <td>업무 서버 Swagger · 담당자 API · 검색 서버 · 검사기</td>
        <td class="col-center"><strong>정상 동작 확인</strong></td>
        <td>타 지역 조기 분류 <strong>0.011초</strong> · Swagger 4종 캡처 첨부</td>
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
    """3~4페이지: [별첨 1] 백엔드 Swagger 페이지 실서버 캡처 2종씩을 배치합니다.

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


def _build_att2_ui_detail_pages_html(unique_images: list[bytes]) -> str:
    """[별첨 2] `UI_수정_보고_2026-11-18.pdf` 상세 항목 2-1~2-9 페이지들을 생성합니다.

    Args:
        unique_images: 원본 PDF에서 추출한 고유 PNG 바이트 14장 목록입니다.

    Returns:
        페이지 나눔이 포함된 상세 내역 HTML 문자열입니다.
    """
    return build_ui_detail_pages_html(
        UI_FIX_ITEMS,
        UI_FIX_PAGE_GROUPS,
        unique_images,
        report_date="2026-11-18",
        subtitle="캡처 환경: Chrome 화면, 시험용 데이터(DEMO) · 원본 내용 및 이미지 무수정",
    )


def build_report_html(scenes_dir: Path, ui_pdf_path: Path) -> str:
    """11/18 종합 업무보고 + Swagger 검증 + UI 수정 보고서 전체 HTML을 조립합니다.

    Args:
        scenes_dir: 라이브 Swagger 스크린샷 PNG 파일 디렉터리입니다.
        ui_pdf_path: 원본 `UI_수정_보고_2026-11-18.pdf` 파일 경로입니다.

    Returns:
        인쇄 가능한 완결형 HTML 문자열입니다.
    """
    unique_images = extract_unique_pdf_images(ui_pdf_path)
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
    "[별첨 1] 민원 웹 백엔드 API 문서 (Swagger) 실서버 확인",
    "한국어 API 안내 화면 — 체험 세션 전환 · 바로 시험 기능 · 다크 모드 명암 대비 적용",
)}

{_build_att1_scenes_page_html(
    scenes_dir,
    WORK_SCENES_PAGE_4,
    "[별첨 1] 담당자 API 현황 화면 · 검색 서버 API 문서 (Swagger)",
    "담당자 포털 내 API 목록 (28개 기능) 및 근거 검색 서버(:8007) API 화면 캡처",
)}

{_build_att2_ui_cover_html()}

{_build_att2_ui_detail_pages_html(unique_images)}

</body>
</html>
"""


def main() -> None:
    """11월 18일 종합 업무보고 PDF(`docs/reports/daily/업무보고_20261118.pdf`)를 생성합니다.

    Raises:
        FileNotFoundError: 원본 UI 보고서 PDF 또는 Swagger 캡처 PNG가 없을 때 발생합니다.
    """
    ui_pdf = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_UI_PDF
    scenes_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_SCENES_DIR
    out_pdf = Path(sys.argv[3]) if len(sys.argv) > 3 else OUTPUT_PDF_PATH

    if not ui_pdf.is_file():
        raise FileNotFoundError(f"원본 UI 보고서 PDF가 없습니다: {ui_pdf}")
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
