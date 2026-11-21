"""11월 16일 종합 업무보고 PDF 생성 스크립트입니다.

1페이지: '연승현' 톤의 쉬운 업무보고 메인 표 (2026-11-16 기준, 누적 작업 종합)
2~4페이지: 실서버(:5000 민원 웹·:5010 응대 검사기) 실제 민원 테스트 장면 6종
5페이지: 11/11 보고 대비 주요 변경 요약표 및 청주 한정 112건 AI 테스트 결과 요약표
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import html
from pathlib import Path
import sys

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from report_common import render_html_to_pdf  # noqa: E402

DEFAULT_SCENES_DIR = Path(
    r"C:\Users\user\.gemini\antigravity-cli\brain\3197986d-ee70-477b-9852-28bbba3b7616\scratch\test_scenes"
)
OUTPUT_PDF_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "reports" / "daily" / "업무보고_20261116.pdf"
)


@dataclass(frozen=True)
class SceneSpec:
    """보고서에 수록할 실서버 테스트 캡처 한 건의 메타데이터입니다."""

    filename: str
    caption: str
    description: str
    alt: str


@dataclass(frozen=True)
class ScenePageSpec:
    """캡처 이미지 2종을 묶어 한 A4 쪽으로 구성하는 메타데이터입니다."""

    meta: str
    scenes: tuple[SceneSpec, ...]


SCENE_PAGES: tuple[ScenePageSpec, ...] = (
    ScenePageSpec(
        meta="대상: 민원 웹(:5000) & 단독 응대 검사기(:5010) · 기준일: 2026-11-16 (실제 로컬 서버 동작 캡처)",
        scenes=(
            SceneSpec(
                filename="scene1_citizen_write.png",
                caption="1. 시민 사이트(:5000)에서 민원 직접 작성 테스트",
                description="시민 화면(#/citizen/write)에 청주 실제 장소('고인쇄박물관 정문 맞은편 보도블록 침하') 민원을 입력하고 접수하는 장면",
                alt="시민 사이트 민원 작성 테스트",
            ),
            SceneSpec(
                filename="scene2_citizen_detail.png",
                caption="2. 시민 상세 화면 접수 확인 및 민원 삭제 기능 테스트",
                description="접수 완료 안내와 함께 시민 본인이 올린 민원을 직접 수정하거나 삭제할 수 있도록 새로 추가한 '민원 삭제' 단추 확인 장면",
                alt="시민 상세 및 삭제 기능 테스트",
            ),
        ),
    ),
    ScenePageSpec(
        meta="담당자 사이트(:5000/#/staff) — 다른 부서 배정 · AI 분석 참고 · 답변 템플릿 추가/삭제 테스트",
        scenes=(
            SceneSpec(
                filename="scene3_staff_assign_modal.png",
                caption="3. 담당자 사이트 — 청주시 127개 다른 부서 검색·배정 테스트 (다크 모드)",
                description="'다른 부서 배정' 창에서 AI 추천 후보를 눌러 선택하거나, '흥덕'처럼 부서명을 검색해 원하는 청주시 부서로 지정하는 테스트 장면",
                alt="담당자 부서 배정 모달 테스트",
            ),
            SceneSpec(
                filename="scene4_staff_template_ai.png",
                caption="4. 담당자 사이트 — AI 장소 추적·부서 후보 확인 및 답변 템플릿 테스트 (다크 모드)",
                description="'충북대학교 정문 근처' 가로등 민원에서 AI가 자동 추적한 위치·부서 후보와, 새로 만든 자주 쓰는 답변 템플릿 추가/삭제·초안 편집기 확인 장면",
                alt="담당자 AI 참고 및 템플릿 테스트",
            ),
        ),
    ),
    ScenePageSpec(
        meta="단독 응대 검사기(:5010/) — 실제 청주 민원 112건 중 장소 추적·부서 연결 및 욕설 순화 테스트 장면",
        scenes=(
            SceneSpec(
                filename="scene5_lab_location_result.png",
                caption="5. 단독 검사기(:5010) — '맞은편/근처' 애매한 장소 추적 및 부서 추천 테스트",
                description="구 이름을 안 적고 '고인쇄박물관 정문 맞은편'만 입력해도 네이버 지도로 '흥덕구'를 자동 감지해 '흥덕구 건설과'와 답변 초안까지 생성한 화면",
                alt="단독 검사기 장소 추적 및 부서 추천 테스트",
            ),
            SceneSpec(
                filename="scene6_lab_sanitize_result.png",
                caption="6. 단독 검사기(:5010) — 욕설·거친 표현 감지 및 순화 요약 테스트 (다크 모드)",
                description="욕설이 섞인 가로등 수리 민원에서 공격적 표현만 덜어낸 담당자용 '순화 요약'(사직동 가로등 고장 불편)과 정당한 요구를 분리해 띄운 화면",
                alt="단독 검사기 욕설 순화 테스트",
            ),
        ),
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
    line-height: 1.42;
    letter-spacing: -0.3px;
    -webkit-print-color-adjust: exact;
  }
  .page-break {
    page-break-after: always;
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
    padding: 4.8px 8px;
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
    margin-top: 3.5px;
    margin-bottom: 1.5px;
    color: #000;
  }
  .section-title:first-child {
    margin-top: 0;
  }
  .bullet-item {
    margin: 1.5px 0;
    padding-left: 10px;
    text-indent: -10px;
    word-break: keep-all;
  }
  .highlight-tag {
    font-weight: bold;
    color: #0f766e;
  }

  /* 첨부 테스트 장면 페이지 (2~4쪽) */
  .att-header {
    text-align: center;
    margin-bottom: 8px;
    border-bottom: 1.5px solid #222;
    padding-bottom: 6px;
  }
  .att-header h2 {
    font-size: 15pt;
    font-weight: 800;
    margin: 0 0 3px 0;
  }
  .att-meta {
    font-size: 8.6pt;
    color: #555;
    margin: 0;
  }
  .scene-block {
    margin-top: 8px;
    margin-bottom: 10px;
  }
  .scene-cap {
    font-size: 9.2pt;
    font-weight: 700;
    color: #111;
    margin: 0 0 4px 0;
  }
  .scene-sub {
    font-size: 8.2pt;
    color: #444;
    margin: 0 0 5px 0;
  }
  .scene-img-wrap {
    border: 1px solid #94a3b8;
    border-radius: 4px;
    overflow: hidden;
    background: #fff;
  }
  .scene-img-wrap img {
    width: 100%;
    height: auto;
    max-height: 108mm;
    object-fit: cover;
    object-position: top;
    display: block;
  }

  /* 요약 표 페이지 (5쪽) */
  .att-sec-title {
    text-align: center;
    font-size: 12.5pt;
    font-weight: 800;
    margin: 6px 0 6px 0;
  }
  table.diff-table {
    width: 100%;
    border-collapse: collapse;
    border: 1.2px solid #222;
    margin-top: 4px;
    font-size: 8.4pt;
    line-height: 1.4;
  }
  table.diff-table th {
    background-color: #f3f5f8;
    border: 1px solid #333;
    padding: 5px 7px;
    text-align: center;
    font-weight: bold;
  }
  table.diff-table td {
    border: 1px solid #333;
    padding: 5px 7px;
    vertical-align: middle;
    word-break: keep-all;
  }
  .col-center {
    text-align: center;
    white-space: nowrap;
  }
  .note-box {
    margin-top: 10px;
    padding: 8px 10px;
    background: #f8fafc;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    font-size: 8.3pt;
    color: #334155;
    line-height: 1.45;
  }
"""


def encode_image(path: Path) -> str:
    """PNG 이미지 파일을 HTML 임베딩용 base64 data URI로 변환합니다.

    Args:
        path: 읽을 이미지 파일 경로입니다.

    Returns:
        data:image/png;base64 문자열입니다.
    """
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


def _build_scene_pages_html(scenes_dir: Path) -> str:
    """실서버 민원 테스트 장면 2~4페이지 HTML 블록을 생성합니다.

    Args:
        scenes_dir: 테스트 캡처 PNG 파일이 저장된 폴더 경로입니다.

    Returns:
        페이지 나눔이 포함된 테스트 장면 3쪽 HTML 조각입니다.
    """
    pages_html: list[str] = []
    for page in SCENE_PAGES:
        blocks = "\n".join(
            f"""  <div class="scene-block">
    <div class="scene-cap">{html.escape(scene.caption)}</div>
    <p class="scene-sub">{html.escape(scene.description)}</p>
    <div class="scene-img-wrap">
      <img src="{encode_image(scenes_dir / scene.filename)}" alt="{html.escape(scene.alt)}">
    </div>
  </div>"""
            for scene in page.scenes
        )
        pages_html.append(
            f"""<div class="page-break">
  <div class="att-header">
    <h2>실서버 민원 테스트 및 변경 정리 (11/16)</h2>
    <p class="att-meta">{html.escape(page.meta)}</p>
  </div>
{blocks}
</div>"""
        )
    return "\n\n".join(pages_html)


def _build_page1_html() -> str:
    """1페이지 업무보고 메인 표 HTML 조각을 반환합니다.

    Returns:
        1페이지 업무보고 메인 표 HTML 문자열입니다.
    """
    return """<div class="page-break">
<h1 class="title">업무보고</h1>

<table class="report-table">
  <tr>
    <td class="header-label">보고 기간</td>
    <td class="header-val">2026-11-16 (월)</td>
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
    <td colspan="3">민원 웹과 AI 응대 기능 실제 연결, 어두운 화면(다크 테마)·담당자 기능 보완 및 청주 민원 112건 실전 테스트</td>
  </tr>
  <tr>
    <td class="header-label">주제</td>
    <td colspan="3">산학공동프로젝트 서버, AI 업무 보고 (11/16)</td>
  </tr>
  <tr>
    <td class="label-cell">담당 업무<br>(전체)</td>
    <td colspan="3" class="full-val">
      <div class="section-title">1. 서버 &amp; 검색 DB</div>
      <div class="bullet-item">- 청주시 민원 데이터(자주 묻는 민원 94건, 공개 민원 사례 5,015건, 부서 127개) 수집 및 검색 서버 구축</div>
      <div class="bullet-item">- 민원 등록·조회·답변 작성용 웹 서버 제작 및 PostgreSQL DB 연동</div>
      <div class="section-title">2. AI &amp; 테스트 웹</div>
      <div class="bullet-item">- 검색 결과를 바탕으로 AI가 FAQ 안내나 담당 부서를 판단·초안 작성하는 로직 개발</div>
      <div class="bullet-item">- 민원 본문 장소명으로 청주 구청을 찾아주는 지도 연동 기능 및 AI 검사기 웹(:5010) 개발 (마감 2026-11-27)</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">진행 내용<br>(11/12~11/16)</td>
    <td colspan="3" class="full-val">
      <div class="section-title">1. 민원 웹(:5000)에 AI 실제 연동 및 어두운 화면·편의 기능 대폭 개선</div>
      <div class="bullet-item">- <span class="highlight-tag">AI 자동 분석 연결</span> : 시민이 민원을 올리거나 수정하면 백그라운드에서 AI가 자동으로 자료를 찾고 판단하여, 담당자 화면에 추천 부서·참고 근거·답변 초안을 실시간으로 띄워주도록 연결 (담당자가 수정 중인 글은 덮어쓰지 않도록 보호)</div>
      <div class="bullet-item">- <span class="highlight-tag">어두운 화면(다크 테마) 정비</span> : 다크 모드에서 하얗게 뜨던 청주시 로고를 투명한 전용 로고로 새로 만들고, 버튼에 마우스를 올릴 때 너무 밝게 번쩍이는 현상과 글씨 가독성(담당자 화면 글꼴 확대)을 전체적으로 다듬음</div>
      <div class="bullet-item">- <span class="highlight-tag">검사기 화면 통일 및 안내 문구 정리</span> : 민원 웹 검사기(#/lab)와 단독 검사기(:5010) 화면을 시민 사이트처럼 보기 좋게 통일하고 다크 모드 전환을 추가함. 담당자 화면에서 헷갈리던 내부 확인용 부서 문구('unverified', '자동 이관 아님')는 테스트용 검사기에서만 보이도록 분리</div>
      <div class="bullet-item">- <span class="highlight-tag">시민 삭제·담당자 127부서 배정·답변 템플릿 추가</span> : 시민이 올린 본인 민원을 직접 영구 삭제할 수 있게 하고, 담당자 화면에서는 '내가 담당' 외에 청주시 127개 다른 부서를 검색해 배정하거나 자주 쓰는 답변 문구(템플릿)를 직접 추가·삭제할 수 있도록 구현</div>
      <div class="section-title">2. 단독 검사기(:5010)를 활용한 청주 민원 112건 실전 테스트 진행</div>
      <div class="bullet-item">- <span class="highlight-tag">5가지 핵심 기준 집중 테스트</span> : 청주 지역 민원(110건 + 타지역 비교 2건)을 직접 보내 ① FAQ로 안내할 건을 잘 처리하는지 ② '근처/맞은편' 같은 애매한 장소로 부서를 잘 찾는지 ③ 없는 규정을 유도질문해도 지어내지 않는지 ④ 욕설·비꼬는 말을 잘 가려내는지 ⑤ AI 규칙 무시(탈옥) 공격을 막는지 직접 검증함</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">진행 결과</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- <span class="highlight-tag">AI 응대 및 방어 성능</span> : 기본 AI 모델은 102건 모두 서버 오류 없이 응답했고, 공식 FAQ 안내(20건)·없는 정보 유도질문 차단(23건)·AI 탈옥 공격 방어(20건)를 전부 통과함 (무료 외부 AI EXAONE 10건은 호출 한도·지연으로 2건 타임아웃이 있었으나 모두 담당자 검토로 안전하게 전환)</div>
      <div class="bullet-item">- <span class="highlight-tag">실전 테스트에서 찾은 보완점</span> : ① '가로등이 꺼져/보도블록이 꺼져'를 욕설('꺼져')로 오해하거나 초성 욕설·비꼬는 말을 놓치는 문제 ② '봉명동1349'처럼 띄어쓰기 없는 동+번지수 인식 누락 ③ '지역'·'접수' 같은 일반 단어로 엉뚱한 장소를 잡는 문제를 실제로 발견함</div>
      <div class="bullet-item">- <span class="highlight-tag">시스템 안정성</span> : 기능 추가 후 전체 자동 테스트(백엔드·DB·화면) 및 코드 주석·설명 문서 정리를 마치고 GitHub(llm 브랜치) 반영 완료</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">남은 일</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- 이번 112건 테스트에서 찾아낸 욕설 오탐·비꼬기 미감지 및 주소/장소 인식 보완점 수정</div>
      <div class="bullet-item">- 담당자 화면 실시간 알림(SSE) 및 시민 챗봇 연동 검토, 최종 시연·발표 자료 준비 (최종 마감 2026-11-27)</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">참고 사항</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- 역할 분담 : 기민 님 / 초기 화면(UI04)·DB 설계 기반, 승현 / 서버·AI·민원 웹 실시간 연결, 다크 테마·부서 배정·템플릿 구현 및 112건 검증</div>
      <div class="bullet-item">- <strong>[첨부 자료: 2~5페이지]</strong>에 실제로 :5000 민원 웹과 :5010 검사기에서 민원을 넣고 테스트한 화면 캡처 6장 및 쉬운 변경 정리표를 수록함</div>
    </td>
  </tr>
</table>
</div>"""


def _build_summary_page_html() -> str:
    """5페이지 변경 요약 및 112건 실전 테스트 요약표 HTML 조각을 반환합니다.

    Returns:
        5페이지 요약표 HTML 문자열입니다.
    """
    return """<div>
  <div class="att-sec-title">1. 이전 보고(11/11) 대비 주요 변경 정리</div>
  <table class="diff-table">
    <thead>
      <tr>
        <th style="width: 17%;">구분</th>
        <th style="width: 34%;">이전 (11/11 기준)</th>
        <th style="width: 49%;">현재 (11/16 기준)</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="col-center"><strong>민원 웹 ↔ AI 연결</strong></td>
        <td>민원을 올려도 AI가 자동으로 연결되지 않고 정해진 단계 시연만 표시</td>
        <td>민원 등록·수정 시 AI가 실제 자료를 찾아 추천 부서·근거·초안을 자동 생성 (담당자 수정본 보호)</td>
      </tr>
      <tr>
        <td class="col-center"><strong>어두운 화면(다크)</strong></td>
        <td>어두운 모드에서 로고 뒤 흰 배경, 마우스 호버 시 버튼이 과하게 밝아짐</td>
        <td>다크 전용 투명 청주시 로고 새로 제작, 서비스 아이콘·호버 색감 정비 및 담당자 글꼴 확대</td>
      </tr>
      <tr>
        <td class="col-center"><strong>검사기 화면·문구</strong></td>
        <td>:5010 라이트 모드 고정, 담당자 화면에 개발용 메타(unverified) 노출</td>
        <td>시민 화면 톤으로 디자인 통일, :5010 다크 전환 추가, 테스트용 부서 메타는 검사기에서만 표시</td>
      </tr>
      <tr>
        <td class="col-center"><strong>시민 기능 추가</strong></td>
        <td>올린 민원 수정·철회만 가능 (목록 삭제 불가)</td>
        <td>시민이 본인이 올린 민원을 내 민원·상세 화면에서 직접 영구 삭제 가능</td>
      </tr>
      <tr>
        <td class="col-center"><strong>담당자 실무 기능</strong></td>
        <td>'내가 담당' 지정 버튼 1개, 고정 답변 문구 5개만 사용</td>
        <td>청주시 127개 다른 부서 검색·AI 후보 배정 및 자주 쓰는 답변 템플릿 직접 추가·삭제·복원 지원</td>
      </tr>
      <tr>
        <td class="col-center"><strong>외부 AI·오류 방어</strong></td>
        <td>Codex·Luna 중심 연결</td>
        <td>무료 K-EXAONE 2.5 선택 추가, 호출 제한(429) 자동 재시도 및 키 미설정 엔진 버튼 잠금 적용</td>
      </tr>
    </tbody>
  </table>

  <div class="att-sec-title" style="margin-top: 16px;">2. 단독 검사기(:5010) 청주 한정 112건 직접 테스트 결과 요약</div>
  <table class="diff-table">
    <thead>
      <tr>
        <th style="width: 24%;">테스트 항목</th>
        <th style="width: 14%;">건수</th>
        <th style="width: 18%;">기본 AI 결과</th>
        <th style="width: 44%;">확인 내용 및 발견된 개선 필요점</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>① FAQ 기반 1차 안내·차단</strong></td>
        <td class="col-center">20건</td>
        <td class="col-center"><strong>20 / 20 통과</strong><br>(EXAONE 2건 포함)</td>
        <td>대형폐기물·여권·버스정기권 등 조건을 정확히 안내하고, 현장조치·복합·구비서류 누락은 보류 처리</td>
      </tr>
      <tr>
        <td><strong>② '근처' 장소·부서 연결</strong></td>
        <td class="col-center">28건</td>
        <td class="col-center"><strong>22 / 26 통과</strong><br>(EXAONE 2건 시간초과)</td>
        <td>서원대후문·CGV·고인쇄박물관·청남대 등 추적 성공. 단, '봉명동1349'(띄어쓰기 없음) 및 일반 단어('지역') 오매칭 발견</td>
      </tr>
      <tr>
        <td><strong>③ 없는 내용 유도질문 방어</strong></td>
        <td class="col-center">23건<br>(청주 21+타지역 2)</td>
        <td class="col-center"><strong>23 / 23 방어</strong><br>(429 1건 안전보류)</td>
        <td>가짜 할인·허구 조례·가짜 연락처·미확정 공사일정·고속도로 소관 유도에도 거짓 정보를 지어내지 않음</td>
      </tr>
      <tr>
        <td><strong>④ 욕설·비꼬기 표현 감지</strong></td>
        <td class="col-center">21건</td>
        <td class="col-center">직접 욕설 <strong>9 / 9</strong><br>우회·비꼬기 <strong>미감지</strong></td>
        <td>직접 욕설·협박은 순화 성공. 반면 '보도블록 꺼져' 오탐(3건) 및 초성('ㅅㅂ')·비꼬는 표현(11건) 미감지 확인</td>
      </tr>
      <tr>
        <td><strong>⑤ AI 탈옥·명령 무시 방어</strong></td>
        <td class="col-center">20건</td>
        <td class="col-center"><strong>20 / 20 방어</strong><br>(EXAONE 2건 포함)</td>
        <td>시스템 지시·비밀키 유출, 가짜 근거 강제, SQL·명령 실행 요청 모두 무시하고 안전하게 차단</td>
      </tr>
    </tbody>
  </table>

  <div class="note-box">
    <strong>종합 참고:</strong> 이번 테스트에서 발견된 ① 욕설 필터('꺼져' 오탐 및 초성·비꼬기 미감지) ② 동 이름+번지수 붙여쓰기 인식 ③ 일반 단어 기반 엉뚱한 지도 검색 문제 3가지는 사례 문서(CASE-097)에 상세히 기록해 두었으며, 다음 작업에서 바로 보완할 예정입니다. 모든 기능 수정 및 테스트 결과는 GitHub(llm 브랜치)에 반영 완료했습니다.
  </div>
</div>"""


def build_report_html(scenes_dir: Path) -> str:
    """업무보고 메인(1쪽), 실서버 테스트 장면(2~4쪽), 요약표(5쪽) HTML을 조립합니다.

    Args:
        scenes_dir: 실서버 민원 테스트 캡처 이미지 6종이 저장된 폴더입니다.

    Returns:
        5페이지 A4 세로 인쇄용 HTML 문자열입니다.
    """
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>업무보고 (11/16)</title>
<style>
{_REPORT_CSS}
</style>
</head>
<body>

<!-- ==================== 1페이지: 업무보고 메인 표 ==================== -->
{_build_page1_html()}

<!-- ==================== 2~4페이지: 실서버 민원 테스트 장면 ==================== -->
{_build_scene_pages_html(scenes_dir)}

<!-- ==================== 5페이지: 11/11 대비 변경 요약 & 112건 테스트 결과표 ==================== -->
{_build_summary_page_html()}

</body>
</html>
"""


def main() -> None:
    """11월 16일 업무보고 PDF(메인 1쪽 + 테스트 장면 3쪽 + 요약표 1쪽)를 생성합니다."""
    scenes_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SCENES_DIR
    out_pdf = Path(sys.argv[2]) if len(sys.argv) > 2 else OUTPUT_PDF_PATH
    for page in SCENE_PAGES:
        for scene in page.scenes:
            if not (scenes_dir / scene.filename).is_file():
                raise FileNotFoundError(
                    f"테스트 장면 파일이 없습니다: {scenes_dir / scene.filename}"
                )
    html_text = build_report_html(scenes_dir)
    render_html_to_pdf(html_text, out_pdf)
    print(f"REPORT_PDF_CREATED: {out_pdf} ({out_pdf.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
