"""11월 20일(금)~23일(월) 종합 업무보고 PDF 생성 스크립트입니다.

기존 `업무보고_20261119.pdf`와 같은 틀(1쪽 메인 표 + 별첨)을 따라 한국어로 쉽게 풀어 씁니다.

1페이지: 11/20~11/23 업무보고 메인 표
2페이지: [별첨 1] 핵심 수치와 날짜별 작업 요약
3페이지: [별첨 1] 서비스 구성도·역할별 권한 그림
4~6페이지: [별첨 2] 담당자 통계 대시보드 재구성 화면 (통계 분석·민원 분류, 쪽당 2장)
7페이지: [별첨 2] 시민 게시판·담당자 목록·민원 작성 화면
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
OUTPUT_PDF_PATH = ROOT_DIR / "docs" / "reports" / "daily" / "업무보고_20261123.pdf"
ASSETS = ROOT_DIR / "docs" / "assets"
SOURCE = ROOT_DIR / "docs" / "reports" / "daily" / "source"

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


def _build_page1_main_report_html() -> str:
    """1페이지: 11/20~11/23 업무보고 메인 표를 반환합니다.

    Returns:
        1페이지 업무보고 메인 표 HTML 문자열입니다.
    """
    return """<div class="page-break">
<h1 class="title">업무보고</h1>

<table class="report-table">
  <tr>
    <td class="header-label">보고 기간</td>
    <td class="header-val">2026-11-20 (금) ~ 2026-11-23 (월)</td>
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
    <td colspan="3">민원 웹을 인터넷에 공개해 쓸 수 있는 서비스('청주톡톡')로 완성하고, 로그인·실시간 알림·파일 첨부·통계 같은 빠진 기능을 채우고, 사용 가이드와 발표 준비 자료를 정리</td>
  </tr>
  <tr>
    <td class="header-label">주제</td>
    <td colspan="3">산학공동프로젝트 민원 웹 기능 완성, 인터넷 공개·서버 배포, 사용 가이드 및 담당자 통계 대시보드 확장 보고 (11/20~11/23)</td>
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
    <td class="label-cell">진행 내용<br>(11/20~11/23)</td>
    <td colspan="3" class="full-val">
      <div class="section-title">1. 11/20(금) 실시간 알림·AI 챗봇·로그인 구현과 Codex 100건 실증</div>
      <div class="bullet-item">- <span class="highlight-tag">담당자 실시간 알림과 시민 AI 챗봇 연결</span> : 새 민원이나 AI 분석 진행이 담당자 화면에 바로 뜨도록 하고, 시민이 AI와 여러 번 대화하며 민원을 정리하는 챗봇을 실제 AI에 연결함</div>
      <div class="bullet-item">- <span class="highlight-tag">아이디·비밀번호 로그인과 DB 7테이블 정리</span> : 민원인과 담당자가 각자 계정으로 로그인하고(5회 틀리면 잠깐 잠김), 민원 데이터를 사용자·민원·답변·AI 결과 등 7개 표로 나눠 저장함</div>
      <div class="bullet-item">- <span class="highlight-tag">Codex로 새 100건 실증 (99/100)</span> : 새로 만든 민원 100건을 실제 AI로 시험해 99건에서 기대한 동작을 확인하고, 남은 문제를 사후 점검해 고침</div>
      <div class="section-title">2. 11/21(토) 파일 첨부·통계·폴더 정비·사이트 분리·서버 배포</div>
      <div class="bullet-item">- <span class="highlight-tag">챗봇 대화 저장, 담당자 통계, 사진·PDF 첨부</span> : 대화 기록 DB 저장, 담당자 통계와 안전한 CSV 내려받기, 사진·PDF 첨부(사진 속 위치 정보 삭제, 본인·담당자만 열람), 저장소 폴더 정비(코드 동작 그대로)</div>
      <div class="bullet-item">- <span class="highlight-tag">시민(/)·담당자(/staff/) 사이트 분리와 원격 서버 배포</span> : 두 사이트가 서로 로그인 정보를 공유하지 않게 나누고, 리눅스 서버에 올리는 배포 스크립트를 만들어 처음으로 서버에서 동작을 확인함</div>
      <div class="bullet-item">- <span class="highlight-tag">비로그인 게스트 접수와 디자인 통일</span> : 로그인 없이도 민원을 낼 수 있게 하고, 색·글자·모서리·그림자를 공통 규칙으로 통일해 시민·담당자 화면의 일관성을 높임</div>
      <div class="section-title">3. 11/22(일) 고정 주소로 인터넷 공개와 README 개편</div>
      <div class="bullet-item">- <span class="highlight-tag">고정 주소 cheongju.mib.dpdns.org 공개</span> : 무료 도메인과 Cloudflare 터널로 서버를 인터넷에 공개하고, 설정 스크립트와 배포 안내를 정리함</div>
      <div class="bullet-item">- <span class="highlight-tag">시연 비밀번호를 코드·문서에서 제거</span> : 공개 저장소에서 계정 비밀번호가 보이지 않도록 환경변수로 옮기고, 아직 올리지 않은 커밋 기록에서도 지움</div>
      <div class="bullet-item">- <span class="highlight-tag">README를 쉬운 말로 개편</span> : 역할별 권한 표와 그림, 화면 캡처를 넣어 처음 보는 사람도 흐름을 이해하도록 다시 씀. 게스트가 낸 민원을 게시판에 공개하는 정책도 반영함</div>
      <div class="section-title">4. 11/23(월) 사용 가이드·담당자 사이트 단독화·방문자 게시판·통계 확장</div>
      <div class="bullet-item">- <span class="highlight-tag">사용 가이드 PDF 2종</span> : 번호를 붙인 화면 그림으로 민원인 가이드(18쪽)와 담당자 가이드(24쪽)를 만들고, 배정 해제·CSV 내려받기 설명을 더함</div>
      <div class="bullet-item">- <span class="highlight-tag">담당자 사이트 단독화와 검사기 보호</span> : 응대 검사기를 별도 주소(/lab/)로 떼어 담당자 로그인 때만 열리게 하고, 계정당 10분 20회로 실행 횟수를 제한함. 공개 주소에서도 담당자가 로그인하면 API 문서 화면을 보게 복구함</div>
      <div class="bullet-item">- <span class="highlight-tag">이름 '청주톡톡' 통일과 비로그인 게시판 열람</span> : 서비스 이름을 통일하고, 로그인하지 않은 방문자도 공개된 민원 게시판을 볼 수 있게 함(초안·AI 결과·첨부는 제외). 방문자 게시판은 30초마다 자동 새로고침. 담당자가 게시판에서 민원을 내리는 기능도 추가함</div>
      <div class="bullet-item">- <span class="highlight-tag">담당자 통계 대시보드 확장</span> : 설계 시안의 통계 분석·민원 분류 구성에 맞춰 화면을 재구성함. 접수·처리 막대, 분야 순위표, 분야별 곡선·레이더, 지역×분야·요일×시간 히트맵, 처리기간 분포를 추가함 ([별첨 2] 화면 수록)</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">진행 결과</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- <span class="highlight-tag">인터넷에 공개된 서비스 완성</span> : https://cheongju.mib.dpdns.org/ 에서 시민 화면과 담당자 화면(/staff/)이 동작하고, 서버에 최신 상태로 배포됨 (서비스 3개 정상, 상태 확인 ok)</div>
      <div class="bullet-item">- <span class="highlight-tag">자동 시험 전부 통과</span> : 백엔드·DB 시험 <strong>216건 통과(10건은 환경 때문에 건너뜀)</strong>, 화면 시험 <strong>71건 통과</strong>, 자동 타입 검사 <strong>88개 파일 오류 0건</strong></div>
      <div class="bullet-item">- 개발 기록 <strong>CASE-109~133</strong>과 변경 이력(CHANGELOG)을 모두 정리하고 GitHub·서버에 반영 완료</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">남은 일</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- 실제 서버 데이터로 통계 화면 확인, 최종 발표 자료(PPT) 정리 (마감 2026-11-27)</div>
    </td>
  </tr>
  <tr>
    <td class="label-cell">참고 사항</td>
    <td colspan="3" class="full-val">
      <div class="bullet-item">- 구성 : <strong>[별첨 1: 2~3쪽]</strong> 핵심 수치·날짜별 작업 표·서비스 구성도, <strong>[별첨 2: 4~7쪽]</strong> 통계 확장 화면(로컬 시험 데이터 160건, 실제 수치 아님)·주요 화면. 계정·서버 접속 정보는 보안상 넣지 않음</div>
    </td>
  </tr>
</table>
</div>"""


def _build_att1_page2_html() -> str:
    """2페이지: [별첨 1] 핵심 수치와 날짜별 작업 요약표를 반환합니다.

    Returns:
        2페이지 HTML 문자열입니다.
    """
    return """<div class="page-break">
  <div class="att-header">
    <h2>[별첨 1] 11/20~11/23 핵심 수치와 날짜별 작업 요약</h2>
    <p class="att-meta">작성자: 연승현 · 기준일: 2026-11-23 (어려운 개발 용어 대신 기능과 효과 중심으로 정리)</p>
  </div>

  <div class="kpi-strip">
    <div class="kpi-card">
      <div class="kpi-label">백엔드·DB 시험</div>
      <div class="kpi-val">216건 통과</div>
      <div class="kpi-sub">실패 0건 · 10건은 환경 때문에 건너뜀</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">화면 시험 · 타입 검사</div>
      <div class="kpi-val">71건 · 0건 오류</div>
      <div class="kpi-sub">타입 검사 88개 파일 전체</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Codex 새 100건 실증</div>
      <div class="kpi-val">99 / 100</div>
      <div class="kpi-sub">남은 문제는 사후 점검으로 정리</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">API 경로 · 개발 기록</div>
      <div class="kpi-val">39개 · CASE 25건</div>
      <div class="kpi-sub">CASE-109~133, GitHub·서버 동기화</div>
    </div>
  </div>

  <div class="att-sec-title">1. 날짜별 작업 요약</div>
  <table class="diff-table">
    <thead>
      <tr>
        <th style="width: 14%;">날짜</th>
        <th style="width: 26%;">작업 분야</th>
        <th style="width: 60%;">내용과 효과</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="col-center"><strong>11/20 (금)</strong></td>
        <td><strong>실시간 알림 · AI 챗봇 · 로그인 · DB</strong></td>
        <td>담당자 화면에 새 민원과 AI 분석 상황이 바로 표시되고, 시민 AI 챗봇이 실제 AI와 대화함. 민원인·담당자 로그인과 7개 표 DB가 갖춰져 민원이 정식 데이터로 저장됨. 새 100건 실증 99/100</td>
      </tr>
      <tr>
        <td class="col-center"><strong>11/21 (토)</strong></td>
        <td><strong>첨부 · 통계 · 사이트 분리 · 서버 배포</strong></td>
        <td>사진·PDF를 안전하게 첨부(위치 정보 삭제)하고 담당자 통계·CSV를 제공함. 시민·담당자 사이트를 분리해 리눅스 서버에 처음 배포. 게스트 접수와 디자인 공통 규칙 적용. 폴더 구조 정비</td>
      </tr>
      <tr>
        <td class="col-center"><strong>11/22 (일)</strong></td>
        <td><strong>인터넷 공개 · 보안 정리 · README</strong></td>
        <td>고정 주소로 인터넷 공개. 시연 비밀번호를 코드·문서·올리기 전 커밋 기록에서 제거(환경변수로 이전). README를 쉬운 말과 그림으로 개편하고 게스트 민원 공개 정책 반영</td>
      </tr>
      <tr>
        <td class="col-center"><strong>11/23 (월)</strong></td>
        <td><strong>가이드 · 사이트 정리 · 게시판 · 통계 확장</strong></td>
        <td>민원인·담당자 사용 가이드 PDF 2종. 담당자 사이트 단독화와 검사기 로그인 전용·횟수 제한. 이름 '청주톡톡' 통일, 비로그인 방문자 게시판 열람과 자동 새로고침. 통계 대시보드를 통계 분석·민원 분류 구성으로 재구성</td>
      </tr>
    </tbody>
  </table>

  <div class="att-sec-title">2. 통계 대시보드 재구성 (11/23) 요약</div>
  <table class="diff-table">
    <thead>
      <tr>
        <th style="width: 22%;">구역</th>
        <th style="width: 44%;">보여주는 것</th>
        <th style="width: 34%;">활용</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>통계 분석</strong></td>
        <td>일·주·월 전환, 접수·처리 막대(값 표시), 분야 순위표(비중·평균 처리일·전기 대비), 시간대·요일별 접수, 기간 비교 표</td>
        <td>업무량 변화와 처리 속도 파악</td>
      </tr>
      <tr>
        <td><strong>민원 분류 · 종합</strong></td>
        <td>분야별 12개월 곡선, 이번 달과 지난달 비교 레이더 (전기 대비는 진행 중인 달 제외)</td>
        <td>늘고 있는 민원 분야 확인</td>
      </tr>
      <tr>
        <td><strong>민원 분류 · 지역별</strong></td>
        <td>구×분야 히트맵, 행을 누르면 해당 지역과 평균을 비교하는 레이더·상위 분야</td>
        <td>지역별로 많은 민원 유형 파악</td>
      </tr>
      <tr>
        <td><strong>민원 분류 · 시간대·요일</strong></td>
        <td>요일×24시간 히트맵(한국 시간), 시간대 막대, 요일 레이더</td>
        <td>접수가 몰리는 시간 파악</td>
      </tr>
      <tr>
        <td><strong>민원 분류 · 처리기간</strong></td>
        <td>1일 이내·1~3일·3~7일·7일 초과 분포와 분야별 평균</td>
        <td>처리 지연 분야 확인</td>
      </tr>
    </tbody>
  </table>
  <p style="margin: 6px 0 0 0; font-size: 7.9pt; color: #555;">※ 담당자는 자기 부서 민원만, 총괄 담당자는 전체를 집계합니다. 설계 시안의 채널·만족도·정책 연계처럼 저장하지 않는 데이터는 넣지 않았습니다.</p>
</div>"""


def _build_att1_page3_html() -> str:
    """3페이지: [별첨 1] 서비스 구성도와 역할별 권한 그림을 반환합니다.

    Returns:
        3페이지 HTML 문자열입니다.
    """
    deploy_svg = encode_file(ASSETS / "deploy.svg")
    roles_svg = encode_file(ASSETS / "roles.svg")
    return f"""<div class="page-break">
  <div class="att-header">
    <h2>[별첨 1] 서비스 공개 구성과 역할별 권한</h2>
    <p class="att-meta">README에 정리한 그림 · 11/22 인터넷 공개와 11/21~23 로그인·권한 구조 기준</p>
  </div>

  <div class="att-sec-title">3. 인터넷 공개 구성 (도메인 · Cloudflare 터널 · 리눅스 서버)</div>
  <div class="visual-card">
    <p class="visual-sub">방문자는 고정 주소로 접속하고, 요청은 Cloudflare 터널을 거쳐 서버의 민원 웹에 도착합니다. 서버 접속 정보와 토큰은 문서에 두지 않습니다.</p>
    <div class="visual-img-box" style="border: 1px solid #cbd5e1; border-radius: 3px; padding: 3px;">
      <img src="{deploy_svg}" alt="인터넷 공개 구성도" style="max-height: 98mm;">
    </div>
  </div>

  <div class="att-sec-title">4. 게스트 · 민원인 · 담당자 역할별 권한</div>
  <div class="visual-card">
    <p class="visual-sub">로그인하지 않은 방문자는 공개된 민원만 보고, 민원인은 자기 민원을 관리하며, 담당자는 부서 범위 안에서 검토·답변·통계를 사용합니다. AI는 안내만 하고 최종 결정은 담당자가 합니다.</p>
    <div class="visual-img-box" style="border: 1px solid #cbd5e1; border-radius: 3px; padding: 3px;">
      <img src="{roles_svg}" alt="역할별 권한 그림" style="max-height: 98mm;">
    </div>
  </div>
</div>"""


def _build_att2_page4_html() -> str:
    """4페이지: [별첨 2] 통계 대시보드 확장 화면 4장을 반환합니다.

    Returns:
        4페이지 HTML 문자열입니다.
    """
    items = (
        ("통계_분석_추이.png", "① 통계 분석 · 접수·처리 추이", "일·주·월 전환, 핵심 지표 4개, 값 라벨이 붙은 접수·처리 막대를 보여 줍니다."),
        ("통계_분석_분야시간.png", "② 통계 분석 · 분야 순위와 시간·요일", "분야별 비중·평균 처리일·전기 대비 표와 시간대별·요일별 접수 분포입니다."),
        ("통계_분류_종합.png", "③ 민원 분류 · 종합", "분야별 12개월 곡선과 이번 달·지난달 레이더로 분야 흐름을 비교합니다."),
        ("통계_분류_지역.png", "④ 민원 분류 · 지역별", "구×분야 히트맵이며 행을 누르면 그 지역과 평균을 레이더로 비교합니다."),
        ("통계_분류_시간요일.png", "⑤ 민원 분류 · 시간대·요일", "요일×24시간 히트맵과 시간대 막대, 요일 레이더로 접수가 몰리는 때를 보여 줍니다."),
        ("통계_분류_처리기간.png", "⑥ 민원 분류 · 처리기간", "접수부터 답변 게시까지 기간 구간 분포와 분야별 평균 처리일입니다."),
    )

    def card(name: str, caption: str, desc: str) -> str:
        return f"""  <div class="visual-card">
    <div class="visual-cap">{caption}</div>
    <p class="visual-sub">{desc}</p>
    <div class="visual-img-box" style="border: 1px solid #cbd5e1; border-radius: 3px; padding: 3px;">
      <img src="{encode_file(SOURCE / name)}" alt="{caption}" style="max-height: 108mm; width: auto; max-width: 100%;">
    </div>
  </div>"""

    pages = []
    for index, group in enumerate((items[:2], items[2:4], items[4:])):
        cards = "\n".join(card(*item) for item in group)
        suffix = "" if index == 0 else " (계속)"
        pages.append(
            f"""<div class="page-break">
  <div class="att-header">
    <h2>[별첨 2] 담당자 통계 대시보드 재구성 화면{suffix}</h2>
    <p class="att-meta">로컬 시험 데이터(민원 160건)로 촬영, 실제 민원 수치 아님 · 재구성 후 화면(2026-11-24 촬영)</p>
  </div>
{cards}
</div>"""
        )
    return "\n\n".join(pages)


def _build_att2_page5_html() -> str:
    """5페이지: [별첨 2] 시민 게시판·담당자 목록·기존 통계 화면 캡처를 반환합니다.

    Returns:
        5페이지 HTML 문자열입니다.
    """
    items = (
        ("citizen-board.png", "⑤ 시민 민원 게시판", "공개된 민원만 모아 보여 주며 로그인하지 않은 방문자도 열람할 수 있습니다."),
        ("staff-queue.png", "⑥ 담당자 민원 목록", "검토가 필요한 민원을 한곳에서 확인하고 배정·답변으로 이어집니다."),
        ("citizen-write.png", "⑦ 민원 작성 화면", "시민이 내용을 쓰고 사진·PDF를 첨부하면 AI가 먼저 안내합니다."),
    )
    cards = "\n".join(
        f"""  <div class="visual-card">
    <div class="visual-cap">{caption}</div>
    <p class="visual-sub">{desc}</p>
    <div class="visual-img-box" style="border: 1px solid #cbd5e1; border-radius: 3px; padding: 3px;">
      <img src="{encode_file(ASSETS / 'screens' / name)}" alt="{caption}" style="max-height: 70mm; width: auto; max-width: 100%;">
    </div>
  </div>"""
        for name, caption, desc in items
    )
    return f"""<div class="page-break">
  <div class="att-header">
    <h2>[별첨 2] 민원 웹 주요 화면</h2>
    <p class="att-meta">README에 수록한 화면 캡처 · 시연용 데이터 기준</p>
  </div>
{cards}
</div>"""


def build_report_html() -> str:
    """11/20~11/23 종합 업무보고 전체 HTML을 조립합니다.

    Returns:
        인쇄 가능한 완결형 HTML 문자열입니다.
    """
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>업무보고 (2026-11-20 ~ 2026-11-23)</title>
<style>
{WORK_REPORT_CSS}
{_EXTRA_CSS}
</style>
</head>
<body>

{_build_page1_main_report_html()}

{_build_att1_page2_html()}

{_build_att1_page3_html()}

{_build_att2_page4_html()}

{_build_att2_page5_html()}

</body>
</html>
"""


def main() -> None:
    """11/20~11/23 종합 업무보고 PDF(`docs/reports/daily/업무보고_20261123.pdf`)를 생성합니다."""
    out_pdf = Path(sys.argv[1]) if len(sys.argv) > 1 else OUTPUT_PDF_PATH
    render_html_to_pdf(build_report_html(), out_pdf)
    page_count = len(pypdf.PdfReader(str(out_pdf)).pages)
    print(
        f"REPORT_PDF_CREATED: {out_pdf} ({out_pdf.stat().st_size} bytes, {page_count} pages)"
    )


if __name__ == "__main__":
    main()
