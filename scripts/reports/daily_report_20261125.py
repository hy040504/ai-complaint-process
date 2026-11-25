"""11월 25일(수) 업무보고 PDF 생성 스크립트입니다.

`업무보고_20261124.pdf`와 같은 틀(1쪽 메인 표 + 별첨)을 따라 한국어로 쉽게 풀어 씁니다.

1페이지: 11/25 업무보고 메인 표
2페이지: [별첨 1] 핵심 수치, 작업 분야별 요약, 프로젝트 최종 점검 결과
3~4페이지: [별첨 2] 상세설명서 새 쪽(파이프라인 요약·부록 C RAG) 캡처 (쪽당 2장)
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
OUTPUT_PDF_PATH = ROOT_DIR / "docs" / "reports" / "daily" / "업무보고_20261125.pdf"
SOURCE = ROOT_DIR / "docs" / "reports" / "daily" / "source"
MANUAL_PDF = ROOT_DIR / "docs" / "plans" / "민원_AI_처리과정_상세설명서.pdf"

# (페이지를 찾는 글, 저장 파일 이름, 제목, 설명)
# 설명서에서 해당 글이 처음 나오는 쪽 전체를 여백만 잘라 싣는다.
MANUAL_SHOTS = (
    (
        "한눈에 보는 처리 파이프라인",
        "설명서_파이프라인요약.png",
        "① 한눈에 보는 처리 파이프라인 (설명서 3쪽)",
        "민원 한 건이 접수된 뒤 결과가 저장되기까지의 흐름을 한 쪽에 모았습니다. 괄호 안 번호로 각 장의 근거를 찾아갑니다.",
    ),
    (
        "만들 때 — 적재(ingest)",
        "설명서_부록C개요.png",
        "② 부록 C · 두 JSON에서 벡터 DB까지 (그림 C-1)",
        "FAQ 94건·공개 사례 5,015건이 검사, 검색 본문, 임베딩·낱말 색인을 거쳐 PostgreSQL에 저장되는 순서입니다.",
    ),
    (
        "C-2 DB 구조",
        "설명서_부록C구조.png",
        "③ 부록 C · DB 구조 (그림 C-3)",
        "complaint_rag 스키마의 표 8개와 pgvector 벡터 열, 부서 사전 연결(외래 키), HNSW 색인을 그린 그림입니다.",
    ),
    (
        "C-3 적재 과정",
        "설명서_부록C적재.png",
        "④ 부록 C · 벡터를 다시 계산하지 않는 판단 순서 (그림 C-4)",
        "DB의 벡터 → 캐시의 벡터 → 새로 계산 순으로 확인해, 바뀐 문서만 계산하는 적재 방식을 보여 줍니다.",
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
"""


def _render_manual_shots() -> None:
    """상세설명서 PDF에서 새로 추가한 쪽을 찾아 캡처 이미지로 저장합니다.

    설명서 PDF가 없거나 변환 도구가 없으면 이미 저장된 이미지를 그대로 씁니다.
    """
    if not MANUAL_PDF.exists():
        return
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return
    from PIL import Image, ImageChops

    reader = pypdf.PdfReader(str(MANUAL_PDF))
    texts = [(page.extract_text() or "") for page in reader.pages]
    document = pdfium.PdfDocument(str(MANUAL_PDF))
    SOURCE.mkdir(parents=True, exist_ok=True)

    for key, filename, _title, _desc in MANUAL_SHOTS:
        for index, text in enumerate(texts):
            if key not in text:
                continue
            image = document[index].render(scale=2.0).to_pil().convert("RGB")
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
    """1페이지: 11/25 업무보고 메인 표를 반환합니다.

    Returns:
        1페이지 업무보고 메인 표 HTML 문자열입니다.
    """
    return """<div class="page-break">
<h1 class="title">업무보고</h1>

<table class="report-table">
  <tr>
    <td class="header-label">보고 기간</td>
    <td class="header-val">2026-11-25 (수)</td>
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
    <td colspan="3">11/24에 만든 처리과정 상세설명서에 빠져 있던 RAG 지식베이스(두 JSON → 벡터 DB) 구성을 보완하고, 발표 전 마지막으로 프로젝트 전체(코드·시험·문서·보안·운영 서버)에 문제가 없는지 점검해 정리</td>
  </tr>
  <tr>
    <td class="header-label">주제</td>
    <td colspan="3">상세설명서 부록 C(RAG 지식베이스) 추가, 발표자료(PPT) 검토, 프로젝트 최종 점검과 문서·코드 불일치 정정 보고 (11/25)</td>
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
    <td class="label-cell">진행 내용<br>(11/25)</td>
    <td colspan="3" class="full-val">
      <div class="section-title">1. 상세설명서에 RAG 지식베이스 내용 추가 (부록 C, 5쪽)</div>
      <div class="bullet-item">- <span class="highlight-tag">두 JSON에서 벡터 DB까지</span> : FAQ 94건·공개 사례 5,015건이 검사·정리 → 검색 본문(FAQ는 업무명·안내·대상·접수 조건·기간·주의사항, 사례는 제목+요지만) → 임베딩 384차원과 낱말(BM25) 색인 → PostgreSQL(pgvector)에 저장되는 순서를 그림 4개로 설명</div>
      <div class="bullet-item">- <span class="highlight-tag">DB 구조·적재·검색 정리</span> : complaint_rag 표 8개와 HNSW 색인, 이미 만든 벡터를 해시로 알아보고 다시 계산하지 않는 적재 순서, 찾을 때 DB가 하는 일(후보 30건·RRF 60 등)과 한계. 건수·분포는 JSON을 직접 센 값이고 낱말 예시는 실제 형태소 분석 결과</div>
      <div class="bullet-item">- <span class="highlight-tag">한눈에 보는 파이프라인 쪽 추가</span> : 설명서 3쪽에 처리 흐름 요약을 넣고 부록 B(코드 위치 사전)에 7개 이름을 더해 설명서가 <strong>42쪽</strong>이 됨. 문서 목차도 갱신</div>
      <div class="section-title">2. 발표자료(PPT) 검토</div>
      <div class="bullet-item">- <span class="highlight-tag">평가와 교체 문구 제안</span> : 16·17장이 거의 같은 화면인 점, 목차 04 제목 비어 있음, 기술·검증·한계 내용 부재, 중복 이미지로 인한 약 12MB 용량을 지적. 16·17장 캡션·본문 문구 초안과 다시 찍을 화면을 안내(PPT 파일은 수정하지 않음)</div>
      <div class="section-title">3. 프로젝트 최종 점검</div>
      <div class="bullet-item">- <span class="highlight-tag">시험·타입 검사 전체 재실행</span> : 코드 문제는 발견되지 않음. 공개 사이트와 상태 확인 API 정상, 추적 파일에서 비밀번호·토큰·키 흔적 없음, 문서 상대 링크 깨짐 0건</div>
      <div class="bullet-item">- <span class="highlight-tag">문서와 코드 불일치 정정</span> : 검색 스키마 표 수를 7개 → 8개(임베딩 캐시 표 포함), 업무 스키마 표 수 표기를 현재 DDL의 13개로 고침. 변경 이력(CHANGELOG)의 "아직 커밋·배포 전" 낡은 문구 2곳을 실제 상태로 정정</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">진행 결과</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- <span class="highlight-tag">상세설명서 42쪽 완성</span> : RAG 지식베이스 구성이 설명서에 들어가 접수 → 검색 대상 구성 → 판정까지 한 문서로 이어서 읽을 수 있음</div>
      <div class="bullet-item">- <span class="highlight-tag">자동 시험 전부 통과 (11/25 다시 실행)</span> : 백엔드 시험 <strong>217건 통과(10건은 환경 때문에 건너뜀)</strong>, 화면 시험 <strong>71건 통과</strong>, 화면 문법 검사 <strong>39개 통과</strong>, 자동 타입 검사 <strong>88개 파일 오류 0건</strong></div>
      <div class="bullet-item">- <span class="highlight-tag">GitHub 반영 완료</span> : 설명서 부록 C와 최종 점검 정정분을 main에 올려 원격과 로컬이 같은 상태임을 확인. 11/24에 남았던 통계 보정 4건과 설명서 후속 보강도 모두 GitHub에 반영되어 있고, 통계 보정은 서버 배포본에 포함되어 있음</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">남은 일</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- 최종 발표 자료(PPT) 16·17장 화면 다시 찍어 교체와 기술·검증·한계 장 보강, 실제 서버 데이터로 통계 화면 다시 확인, 데이터베이스 격리 시험 10건 실행, Jev 도입 여부와 모델 서빙 정보 확정 (마감 2026-11-27)</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">참고 사항</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- 구성 : <strong>[별첨 1: 2쪽]</strong> 핵심 수치·작업 분야별 요약·최종 점검 결과, <strong>[별첨 2: 3~4쪽]</strong> 상세설명서 새 쪽 캡처. 알려진 한계로 서버가 다시 시작되면 진행 중이던 AI 작업은 자동으로 복구되지 않음(문서에 기재). 계정·서버 접속 정보는 보안상 넣지 않음</div>
    </td>
  </tr>
</table>
</div>"""


def _build_att1_page2_html() -> str:
    """2페이지: [별첨 1] 핵심 수치·작업 분야별 요약·최종 점검 결과를 반환합니다.

    Returns:
        2페이지 HTML 문자열입니다.
    """
    return """<div class="page-break">
  <div class="att-header">
    <h2>[별첨 1] 11/25 핵심 수치와 작업 분야별 요약</h2>
    <p class="att-meta">작성자: 연승현 · 기준일: 2026-11-25 (어려운 개발 용어 대신 기능과 효과 중심으로 정리)</p>
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
      <div class="kpi-label">상세설명서</div>
      <div class="kpi-val">35쪽 → 42쪽</div>
      <div class="kpi-sub">부록 C(RAG)·요약 쪽 추가</div>
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
        <td><strong>RAG 지식베이스 설명</strong></td>
        <td>두 JSON(FAQ 94건·사례 5,015건)이 검색 본문, 임베딩·낱말 색인을 거쳐 PostgreSQL(pgvector)에 저장되는 과정과 DB 구조·적재·검색을 그림 4개로 정리</td>
        <td>"검색 대상을 어떻게 만들었나"라는 질문에 답할 근거 마련</td>
      </tr>
      <tr>
        <td><strong>처리 흐름 요약 쪽</strong></td>
        <td>설명서 3쪽에 접수부터 저장까지 한 쪽 요약, 부록 B 코드 위치 사전에 이름 7개 추가</td>
        <td>긴 설명서를 읽기 전에 전체 그림을 먼저 파악</td>
      </tr>
      <tr>
        <td><strong>발표자료 검토</strong></td>
        <td>PPT의 중복·빈 항목·누락 내용을 평가하고 16·17장 교체 문구 초안 작성</td>
        <td>발표 전 고칠 곳이 분명해짐</td>
      </tr>
      <tr>
        <td><strong>최종 점검</strong></td>
        <td>시험·타입 검사 재실행, 비밀값·링크·운영 서버 상태 점검, 문서와 DDL의 표 수 불일치 정정</td>
        <td>문서가 실제 구현과 어긋나지 않음</td>
      </tr>
    </tbody>
  </table>

  <div class="att-sec-title">2. 프로젝트 최종 점검 결과</div>
  <table class="diff-table">
    <thead>
      <tr>
        <th style="width: 22%;">점검 항목</th>
        <th style="width: 44%;">확인한 내용</th>
        <th style="width: 34%;">결과</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>자동 시험·타입 검사</strong></td>
        <td>백엔드 시험, 화면 시험, 화면 문법 검사, 타입 검사를 다시 실행</td>
        <td>모두 통과 (10건은 환경 때문에 건너뜀)</td>
      </tr>
      <tr>
        <td><strong>운영 서버·공개 사이트</strong></td>
        <td>공개 주소와 상태 확인 API 응답, AI·검색·실시간 알림·DB 연결 여부</td>
        <td>정상 응답 · 모든 연결 정상</td>
      </tr>
      <tr>
        <td><strong>비밀값·개인 정보</strong></td>
        <td>공개 저장소에 비밀번호·토큰·키·서버 접속 정보가 올라가 있는지 검색</td>
        <td>없음 (검색에 걸린 3건은 설명용 자리표시자·시험용 값)</td>
      </tr>
      <tr>
        <td><strong>문서 링크·표시</strong></td>
        <td>문서 안의 상대 링크와 코드의 TODO 표시 검사</td>
        <td>깨진 링크 0건 · TODO 없음</td>
      </tr>
      <tr>
        <td><strong>문서와 코드 일치</strong></td>
        <td>DB 정의(DDL)와 문서의 표 개수, 변경 이력의 진행 상태 문구를 대조</td>
        <td>검색 표 7→8개, 업무 표 4→13개, 낡은 문구 2곳 정정</td>
      </tr>
      <tr>
        <td><strong>저장소 상태</strong></td>
        <td>로컬 main·llm과 원격 main의 일치, 큰 파일, 로컬에 남은 서비스</td>
        <td>모두 같은 커밋 · 로컬 서비스 없음 (20MB·7MB 파일 2개는 용량만 큼)</td>
      </tr>
    </tbody>
  </table>
  <p style="margin: 6px 0 0 0; font-size: 7.9pt; color: #555;">※ 데이터베이스 격리 시험 10건과 통계 화면의 실서버 데이터 확인은 이번에 실행하지 못했습니다. 설명서는 현재 구현 기준이며 Jev는 제안(미구현)입니다.</p>
</div>"""


def _build_att2_pages_html() -> str:
    """3~4페이지: [별첨 2] 상세설명서 새 쪽 캡처 4장을 반환합니다.

    Returns:
        3~4페이지 HTML 문자열입니다.
    """

    def card(filename: str, caption: str, desc: str) -> str:
        return f"""  <div class="visual-card">
    <div class="visual-cap">{caption}</div>
    <p class="visual-sub">{desc}</p>
    <div class="visual-img-box" style="border: 1px solid #cbd5e1; border-radius: 3px; padding: 3px;">
      <img src="{encode_file(SOURCE / filename)}" alt="{caption}" style="max-height: 108mm; width: auto; max-width: 100%;">
    </div>
  </div>"""

    cards = [card(name, title, desc) for _key, name, title, desc in MANUAL_SHOTS]
    pages = []
    for index, group in enumerate((cards[:2], cards[2:])):
        suffix = "" if index == 0 else " (계속)"
        pages.append(
            f"""<div class="page-break">
  <div class="att-header">
    <h2>[별첨 2] 상세설명서 새 쪽 — 파이프라인 요약·부록 C(RAG){suffix}</h2>
    <p class="att-meta">docs/plans/민원_AI_처리과정_상세설명서.pdf (42쪽) 중 발췌 · 2026-11-25 기준</p>
  </div>
{chr(10).join(group)}
</div>"""
        )
    return "\n\n".join(pages)


def build_report_html() -> str:
    """11/25 업무보고 전체 HTML을 조립합니다.

    Returns:
        인쇄 가능한 완결형 HTML 문자열입니다.
    """
    _render_manual_shots()
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>업무보고 (2026-11-25)</title>
<style>
{WORK_REPORT_CSS}
{_EXTRA_CSS}
</style>
</head>
<body>

{_build_page1_main_report_html()}

{_build_att1_page2_html()}

{_build_att2_pages_html()}

</body>
</html>
"""


def main() -> None:
    """11/25 업무보고 PDF(`docs/reports/daily/업무보고_20261125.pdf`)를 생성합니다."""
    out_pdf = Path(sys.argv[1]) if len(sys.argv) > 1 else OUTPUT_PDF_PATH
    render_html_to_pdf(build_report_html(), out_pdf)
    page_count = len(pypdf.PdfReader(str(out_pdf)).pages)
    print(
        f"REPORT_PDF_CREATED: {out_pdf} ({out_pdf.stat().st_size} bytes, {page_count} pages)"
    )


if __name__ == "__main__":
    main()
