"""Jev 모델을 1차 판정에 쓰는 제안서 PDF(`docs/plans/Jev_1차판정_도입_제안서.pdf`)를 만드는 스크립트입니다.

표지 요약, 현재 구조와 Jev의 두 가지 자리(대체·보완), 보완 방식의 판정 규칙,
구현 변경 목록, 비교 실험 계획, 위험과 결정 필요 사항을 그림과 표로 설명합니다.
내용은 제안이며 구현되지 않았습니다.

실행 예: `.venv-web\\Scripts\\python.exe scripts/reports/plan_jev_proposal.py`
"""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from report_common import render_html_to_pdf  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "plans" / "Jev_1차판정_도입_제안서.pdf"

CSS = """
@page { size: A4 portrait; margin: 12mm 13mm; }
* { box-sizing: border-box; }
body { font-family: "Malgun Gothic","맑은 고딕",sans-serif; color:#16203a; font-size:9.6pt; line-height:1.55; margin:0; }
.page { page-break-after: always; }
.page:last-child { page-break-after: auto; }
h1 { font-size:22pt; margin:0 0 4px; }
h2 { font-size:14pt; margin:0 0 8px; padding-bottom:5px; border-bottom:2px solid #2f6fed; }
h3 { font-size:10.6pt; margin:12px 0 4px; color:#1e4fc7; }
.kicker { color:#2f6fed; font-weight:700; letter-spacing:1.5px; font-size:9pt; }
.lead { font-size:11pt; color:#3d4860; margin:6px 0 10px; }
.badge { display:inline-block; background:#fff1d6; color:#8a5200; border-radius:10px; padding:1px 9px; font-size:8.5pt; font-weight:700; }
.badge.b { background:#e8f0ff; color:#1e4fc7; }
.grid3 { display:flex; gap:8px; }
.card { border:1px solid #d6deec; border-radius:8px; padding:8px 10px; flex:1; background:#fff; }
.card h4 { margin:0 0 3px; font-size:10pt; }
.card.g { border-top:4px solid #1f9d55; } .card.bl { border-top:4px solid #2f6fed; } .card.o { border-top:4px solid #d97b06; }
table { width:100%; border-collapse:collapse; margin:6px 0; font-size:8.8pt; }
th { background:#eef3fc; text-align:left; padding:4px 6px; border:1px solid #cdd7ea; }
td { padding:4px 6px; border:1px solid #d9e0ee; vertical-align:top; }
.note { background:#f3f6fc; border-left:4px solid #2f6fed; padding:6px 10px; margin:8px 0; font-size:9pt; }
.warn { background:#fff8e6; border-left:4px solid #d97b06; padding:6px 10px; margin:8px 0; font-size:9pt; }
code { background:#eef1f7; padding:0 3px; border-radius:3px; font-size:8.6pt; font-family: Consolas,"Malgun Gothic",monospace; }
ul { margin:3px 0 3px 16px; padding:0; } li { margin:1px 0; }
.fig { border:1px solid #d6deec; border-radius:8px; padding:4px; margin:6px 0; background:#f6f8fc; }
.fig svg { width:100%; height:auto; display:block; }
.cap { font-size:8.4pt; color:#5a6782; margin:2px 0 6px; }
"""

# 그림 1: 현재 5단계 흐름과 Jev의 두 자리
FIG_FLOW = """
<svg viewBox="0 0 1100 330" font-family="'Malgun Gothic',sans-serif">
 <defs><marker id="a" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1l8 4-8 4z" fill="#5b6f95"/></marker></defs>
 <g font-size="15" font-weight="700" fill="#16203a">
  <rect x="10" y="40" width="190" height="86" rx="10" fill="#fff" stroke="#c9d4ea"/><text x="105" y="76" text-anchor="middle">① 접수·관할 확인</text><text x="105" y="100" text-anchor="middle" font-size="12.5" font-weight="400" fill="#4a5873">코드가 먼저 거름</text>
  <rect x="235" y="40" width="190" height="86" rx="10" fill="#fff" stroke="#c9d4ea"/><text x="330" y="76" text-anchor="middle">② 근거 검색</text><text x="330" y="100" text-anchor="middle" font-size="12.5" font-weight="400" fill="#4a5873">FAQ · 공개 사례</text>
  <rect x="460" y="40" width="210" height="86" rx="10" fill="#e8f0ff" stroke="#2f6fed" stroke-width="2.5"/><text x="565" y="76" text-anchor="middle">③ 1차 판정 (LLM)</text><text x="565" y="100" text-anchor="middle" font-size="12.5" font-weight="400" fill="#1e4fc7">세 갈래로 분류</text>
  <rect x="705" y="40" width="170" height="86" rx="10" fill="#fff" stroke="#c9d4ea"/><text x="790" y="76" text-anchor="middle">④ 코드 검증</text><text x="790" y="100" text-anchor="middle" font-size="12.5" font-weight="400" fill="#4a5873">validate_decision</text>
  <rect x="910" y="40" width="180" height="86" rx="10" fill="#fff" stroke="#c9d4ea"/><text x="1000" y="76" text-anchor="middle">⑤ 응답 구성</text><text x="1000" y="100" text-anchor="middle" font-size="12.5" font-weight="400" fill="#4a5873">안내 · 초안 · 순화</text>
 </g>
 <g stroke="#5b6f95" stroke-width="2" fill="none" marker-end="url(#a)"><path d="M200 83h33"/><path d="M425 83h33"/><path d="M670 83h33"/><path d="M875 83h33"/></g>
 <!-- 방식 A -->
 <rect x="440" y="170" width="250" height="110" rx="12" fill="#ffffff" stroke="#1f9d55" stroke-width="2.5"/>
 <text x="565" y="200" text-anchor="middle" font-size="15" font-weight="800" fill="#16803f">방식 A · 대체</text>
 <text x="565" y="224" text-anchor="middle" font-size="12.5" fill="#3d4860">③을 Jev가 대신 판정</text>
 <text x="565" y="246" text-anchor="middle" font-size="12.5" fill="#3d4860">비용·지연 절감이 목표</text>
 <text x="565" y="266" text-anchor="middle" font-size="11.5" fill="#8a5200">한국어 정확도 검증 필요</text>
 <path d="M565 170V130" stroke="#1f9d55" stroke-width="2.5" fill="none" marker-end="url(#a)"/>
 <!-- 방식 B -->
 <rect x="735" y="170" width="330" height="110" rx="12" fill="#ffffff" stroke="#d97b06" stroke-width="2.5"/>
 <text x="900" y="200" text-anchor="middle" font-size="15" font-weight="800" fill="#a85f00">방식 B · 보완 (추천)</text>
 <text x="900" y="224" text-anchor="middle" font-size="12.5" fill="#3d4860">기존 판정 뒤, 불확실할 때만</text>
 <text x="900" y="246" text-anchor="middle" font-size="12.5" fill="#3d4860">Jev가 두 번째 의견을 냄</text>
 <text x="900" y="266" text-anchor="middle" font-size="11.5" fill="#16803f">안내를 더 신중하게 하는 방향으로만</text>
 <path d="M820 170V130" stroke="#d97b06" stroke-width="2.5" fill="none" marker-end="url(#a)" stroke-dasharray="6 4"/>
 <text x="10" y="22" font-size="13" font-weight="700" fill="#2f6fed">현재 흐름과 Jev를 붙일 수 있는 두 자리</text>
 <text x="10" y="310" font-size="12" fill="#5a6782">입력(검색 근거 JSON)과 출력(판정 JSON)은 그대로 두고, ④ 코드 검증은 어느 방식에서도 반드시 거친다.</text>
</svg>
"""

# 그림 2: 방식 B 판정 흐름
FIG_B = """
<svg viewBox="0 0 1100 300" font-family="'Malgun Gothic',sans-serif">
 <defs><marker id="b" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1l8 4-8 4z" fill="#5b6f95"/></marker></defs>
 <g font-size="14" fill="#16203a">
  <rect x="10" y="20" width="200" height="70" rx="10" fill="#e8f0ff" stroke="#2f6fed" stroke-width="2"/><text x="110" y="50" text-anchor="middle" font-weight="700">기존 LLM 판정</text><text x="110" y="72" text-anchor="middle" font-size="12" fill="#4a5873">+ 코드 검증 통과</text>
  <polygon points="300,15 400,55 300,95 200,55" fill="#fff8e6" stroke="#d97b06" stroke-width="2"/><text x="300" y="52" text-anchor="middle" font-weight="700" font-size="13">안내 갈래인가?</text><text x="300" y="70" text-anchor="middle" font-size="11" fill="#6a5300">불확실 신호 있나?</text>
  <rect x="440" y="20" width="200" height="70" rx="10" fill="#fff" stroke="#d97b06" stroke-width="2"/><text x="540" y="50" text-anchor="middle" font-weight="700">Jev 두 번째 의견</text><text x="540" y="72" text-anchor="middle" font-size="12" fill="#4a5873">같은 입력·같은 JSON</text>
  <polygon points="750,15 850,55 750,95 650,55" fill="#fff" stroke="#2f6fed" stroke-width="2"/><text x="750" y="52" text-anchor="middle" font-weight="700" font-size="13">두 판정이</text><text x="750" y="70" text-anchor="middle" font-weight="700" font-size="13">일치하나?</text>
  <rect x="890" y="20" width="200" height="70" rx="10" fill="#e9f7ef" stroke="#1f9d55" stroke-width="2"/><text x="990" y="50" text-anchor="middle" font-weight="700">기존 안내 유지</text><text x="990" y="72" text-anchor="middle" font-size="12" fill="#4a5873">FAQ 안내·부서 추천</text>
  <rect x="640" y="180" width="260" height="70" rx="10" fill="#fff4e0" stroke="#d97b06" stroke-width="2"/><text x="770" y="210" text-anchor="middle" font-weight="700">담당자 검토로 전환</text><text x="770" y="232" text-anchor="middle" font-size="12" fill="#4a5873">불일치 · Jev 실패 · 파싱 오류</text>
  <rect x="200" y="180" width="300" height="70" rx="10" fill="#fff" stroke="#c9d4ea" stroke-width="2"/><text x="350" y="210" text-anchor="middle" font-weight="700">Jev 호출 안 함</text><text x="350" y="232" text-anchor="middle" font-size="12" fill="#4a5873">이미 담당자 검토거나 신호 없음</text>
 </g>
 <g stroke="#5b6f95" stroke-width="2" fill="none" marker-end="url(#b)">
  <path d="M210 55h-10" stroke="none"/><path d="M210 55h-8"/><path d="M400 55h38"/><path d="M640 55h8"/><path d="M850 55h38"/><path d="M750 95v83"/><path d="M300 95v83"/>
 </g>
 <g font-size="12" font-weight="700"><text x="408" y="46" fill="#a85f00">예</text><text x="858" y="46" fill="#16803f">예</text><text x="758" y="140" fill="#a85f00">아니오</text><text x="308" y="140" fill="#5a6782">아니오</text></g>
 <text x="10" y="285" font-size="12" fill="#5a6782">핵심 규칙: Jev는 안내를 더 신중하게 만드는 방향으로만 영향을 준다. 담당자 검토에서 자동 안내로 올리는 일은 없다.</text>
</svg>
"""


def page(body: str) -> str:
    return f'<div class="page">{body}</div>'


def build() -> str:
    p1 = page(
        f"""
<div class="kicker">제안서 · 미구현</div>
<h1>1차 판정에 Jev 모델 도입하기</h1>
<p class="lead">민원이 들어오면 AI가 먼저 '안내할지, 부서를 추천할지, 담당자에게 넘길지'를 정합니다. 이 판정 자리에 Jev 모델을 쓰면 어떨지, 어떻게 안전하게 시험할지를 정리했습니다.
<span class="badge">제안 단계</span> <span class="badge b">기본 경로는 그대로 유지</span></p>
<div class="grid3">
 <div class="card g"><h4>왜 하나요</h4><ul><li>판정 호출 비용과 지연을 줄일 수 있는지 확인</li><li>소형 모델로 로컬에서 돌릴 수 있는지 확인</li><li>두 모델의 의견이 갈릴 때를 '불확실' 신호로 활용</li></ul></div>
 <div class="card bl"><h4>무엇을 하나요</h4><ul><li>Jev를 새 공급자(<code>jev_api</code>)로 추가</li><li>같은 평가셋으로 기존 LLM과 비교</li><li>효과가 확인된 역할에만 적용</li></ul></div>
 <div class="card o"><h4>무엇을 안 하나요</h4><ul><li>자동 이관·자동 답변 확대</li><li>코드 검증(<code>validate_decision</code>) 생략</li><li>검증 전에 운영 기본 경로 변경</li></ul></div>
</div>
<h2 style="margin-top:14px">프로젝트의 기존 결정</h2>
<table>
<tr><th style="width:30%">결정</th><th>내용</th><th style="width:22%">근거 문서</th></tr>
<tr><td>도입 순서</td><td>2026-10-25 사용자 확정: Jev 없는 LLM+RAG를 먼저 구현하고, Jev는 기본 기능 이후 확장으로 추가한다.</td><td>harness-roadmap.md, CASE-002</td></tr>
<tr><td>후보 모델</td><td>OmniJev/OneJev1.6-4B(Apache 2.0)를 "구조화 판정 호출 대체 비교" 후보로 둔다. 한국어 민원 성능은 별도 평가가 필요하다.</td><td>모델_선정과_미세조정_제안.md</td></tr>
<tr><td>실험 구분</td><td>판정 호출을 대체하는 실험과 불확실 사례를 추가 확인하는 실험을 구분한다. 개선이 확인된 역할에만 적용한다.</td><td>모델_선정과_미세조정_제안.md</td></tr>
<tr><td>동시 도입 금지</td><td>Jev와 LoRA는 동시에 처음 도입하지 않고 각각 기준 구성과 비교한다.</td><td>민원_웹_MVP_상세설계…</td></tr>
</table>
<div class="note"><b>한 줄 결론</b> — 지금 기본 경로를 바꾸지 말고, 같은 조건의 비교 실험부터 한다. 먼저 <b>보완(방식 B)</b>을 시험하는 것을 추천한다. 안내를 더 신중하게 만드는 방향으로만 작동해서, 오안내 위험이 늘지 않기 때문이다.</div>
<div class="warn"><b>아직 정해지지 않은 것</b> — 사용할 Jev의 정확한 모델, 서빙 방식(OpenAI 호환 API 여부·키 필요 여부·chat template의 system 역할), 한국어 민원 정확도. 이 문서의 구현 범위는 이 결정에 따라 조정된다.</div>
"""
    )

    p2 = page(
        f"""
<h2>1. 현재 구조와 Jev의 두 자리</h2>
<p>민원 판정은 코드가 먼저 거르고, 근거를 검색한 뒤, LLM이 세 갈래 중 하나로 분류하고, 코드가 다시 검증하는 순서입니다. Jev를 붙일 수 있는 자리는 ③ 판정 단계 하나이고, 방식이 두 가지입니다.</p>
<div class="fig">{FIG_FLOW}</div>
<div class="cap">그림 1. 현재 흐름과 Jev의 두 가지 자리</div>
<table>
<tr><th style="width:18%">구분</th><th>A. 대체</th><th>B. 보완 (추천)</th></tr>
<tr><td>하는 일</td><td>판정 호출을 Jev가 전부 맡는다.</td><td>기존 LLM이 판정하고, 불확실할 때만 Jev가 두 번째 의견을 낸다.</td></tr>
<tr><td>기대 이득</td><td>호출 비용·지연 감소, 로컬 실행 가능.</td><td>오안내 감소(두 모델이 갈리면 담당자 검토). 비용은 불확실한 건만 늘어남.</td></tr>
<tr><td>위험</td><td>한국어 정확도 부족 시 판정 품질 전체가 떨어짐. 소형 모델의 JSON 형식 오류가 판정 단계에서 바로 담당자 검토로 이어짐.</td><td>호출이 늘어 지연이 늘 수 있음. 합치는 규칙이 복잡해짐.</td></tr>
<tr><td>코드 변경</td><td>공급자 추가만으로 가능(판정 단계에만 쓰려면 단계별 설정 분리 필요).</td><td>공급자 추가 + <code>pipeline.py</code>의 검증 직후에 새 분기.</td></tr>
<tr><td>적용 조건</td><td>같은 평가셋에서 기존 LLM과 같거나 나은 정확도.</td><td>오안내율이 줄고 담당자 검토 비율이 감당 가능한 수준.</td></tr>
</table>
<h3>어느 방식이든 지키는 것</h3>
<ul>
<li>입력은 같은 검색 근거 JSON, 출력은 같은 판정 JSON(<code>scope · intent · outcome · reason_code · evidence_refs · department_ids · sanitize_needed</code>).</li>
<li>코드 검증을 반드시 거친다. 입력에 없던 근거·부서 번호는 지우고 안내 수준을 낮춘다.</li>
<li>자동 이관은 없다. 검색 점수와 모델의 자기 확신은 확률이 아니다. 최종 결정은 담당 공무원이다.</li>
</ul>
"""
    )

    p3 = page(
        f"""
<h2>2. 보완 방식(B)의 판정 규칙</h2>
<p>두 번째 의견은 <b>안내를 더 신중하게 만드는 방향으로만</b> 작동합니다. 담당자 검토로 넘어간 건을 자동 안내로 올리지 않습니다.</p>
<div class="fig">{FIG_B}</div>
<div class="cap">그림 2. 보완 방식의 흐름</div>
<h3>두 판정 조합별 최종 결과 (제안)</h3>
<table>
<tr><th style="width:23%">기존 LLM</th><th style="width:23%">Jev</th><th style="width:24%">최종 결과</th><th>이유</th></tr>
<tr><td>FAQ 안내</td><td>FAQ 안내</td><td>FAQ 안내</td><td>두 모델이 같은 결론이다.</td></tr>
<tr><td>FAQ 안내</td><td>부서 추천 · 담당자 검토</td><td>담당자 검토</td><td>의견이 갈리면 사람이 본다.</td></tr>
<tr><td>부서 추천</td><td>같은 부서 추천</td><td>부서 추천</td><td>부서 후보가 일치한다.</td></tr>
<tr><td>부서 추천</td><td>다른 부서 · 담당자 검토</td><td>담당자 검토</td><td>부서가 갈린다.</td></tr>
<tr><td>안내 갈래</td><td>호출 실패 · 시간 초과 · JSON 오류</td><td>담당자 검토</td><td>확인되지 않은 안내는 내보내지 않는다.</td></tr>
<tr><td>담당자 검토</td><td>(호출 안 함)</td><td>담당자 검토</td><td>이미 안전한 쪽이다.</td></tr>
</table>
<h3>Jev를 부를 조건 후보 (실험에서 정한다)</h3>
<ul>
<li>코드 검증이 판정을 교정했다(<code>failures</code>가 비어 있지 않음).</li>
<li>검색 근거의 점수가 낮거나 후보가 하나뿐이다.</li>
<li>민원에 조치 요청과 정보 문의가 섞여 있다.</li>
<li>지역이 불명확하거나 관할 경계에 걸린다.</li>
</ul>
<div class="note">기록해야 할 것: 결과에 <b>어느 모델이 어떤 판정을 했는지</b>(<code>llm_provider</code>, 두 번째 의견의 판정)를 남겨야 실험 결과를 나눠 볼 수 있다. 현재는 호출 기록이 단계당 한 건이라 확장이 필요하다.</div>
<h3>평가에서 같이 볼 지표</h3>
<table>
<tr><th>지표</th><th>보는 이유</th></tr>
<tr><td>자동 안내 오류율 · 조치 요청 오안내율</td><td>잘못 안내한 비율. 줄어야 한다.</td></tr>
<tr><td>부서 후보 Hit@k</td><td>맞는 부서가 후보에 들어 있는 비율.</td></tr>
<tr><td>검토 회수율 · 안내 비중</td><td>담당자가 봐야 할 건을 놓치지 않는지, 담당자 검토가 과하게 늘지 않는지(과잉 이관).</td></tr>
<tr><td>파싱 실패율 · 지연</td><td>소형 모델의 JSON 형식 오류와 전체 처리 시간.</td></tr>
</table>
"""
    )

    p4 = page(
        """
<h2>3. 구현 변경 목록 (코드 조사 기준)</h2>
<p>공급자는 추상 클래스 없이 이름 문자열 분기로 고르는 구조라, 새 공급자 추가 작업은 작습니다.</p>
<table>
<tr><th style="width:30%">파일</th><th>변경</th></tr>
<tr><td><code>src/llm/settings.py</code></td><td>허용 환경변수 목록에 <code>JEV_URL · JEV_MODEL · JEV_API_KEY · JEV_MAX_TOKENS</code> 추가(목록에 없으면 <code>.env</code> 값이 조용히 무시됨). <code>Provider</code> 값에 <code>jev_api</code> 추가, <code>settings_for_provider</code> 분기, 키 없는 로컬 서버면 사용 가능 판정 분기.</td></tr>
<tr><td><code>src/llm/complete.py</code></td><td><code>complete_jev_result()</code> 신규(OpenAI 호환 chat/completions, 추론 강도 필드 제외, 코드 펜스·사용량 파싱 재사용). <code>complete_result</code> 분기 추가.</td></tr>
<tr><td><code>.env.example</code></td><td>Jev 섹션 추가(값은 비워 둠).</td></tr>
<tr><td><code>src/assist/pipeline.py</code></td><td>방식 A: 판정 단계(<code>decision</code>)만 Jev 설정을 쓰도록 단계별 설정 분리. 방식 B: <code>validate_decision</code> 직후 두 번째 의견 분기와 합치는 규칙. 결과에 두 판정 기록.</td></tr>
<tr><td><code>scripts/eval/evaluate_assist.py</code></td><td><code>--provider</code> 인자 추가, 결과 행에 실제 공급자·파싱 실패·지연 기록.</td></tr>
<tr><td>화면(선택)</td><td>공급자를 화면에서 고르려면 <code>src/lab_web/static</code>과 <code>ui/src</code> 두 곳의 목록을 함께 수정.</td></tr>
</table>
<h3>추가할 테스트 (약 9건)</h3>
<ul>
<li>설정 읽기, 미설정·공백 값 처리, 호출 요청 내용(추론 강도 필드 없음, 인증 헤더), 응답 파싱(코드 펜스, 빈 본문 오류).</li>
<li>결과의 공급자 표기, 깨진 JSON(쉼표 누락·후행 쉼표·설명문 혼입) 복구, 폴백 후보 순서.</li>
<li>방식 B의 조합별 최종 결과(일치·불일치·Jev 실패).</li>
</ul>
<h2 style="margin-top:12px">4. 위험과 대응</h2>
<table>
<tr><th style="width:27%">위험</th><th>대응</th></tr>
<tr><td>판정 단계에 JSON 재시도가 없어, 파싱 실패 시 바로 담당자 검토</td><td>Jev용 1회 재시도 추가 또는 파싱 실패율을 평가 지표로 먼저 측정</td></tr>
<tr><td>순화 호출 여부(<code>sanitize_needed</code>)는 검증을 거치지 않음</td><td>소형 모델의 오탐·미탐을 평가에 포함</td></tr>
<tr><td>한도 초과 시 후보 공급자로 자동 전환(폴백)</td><td>검증 안 된 Jev가 운영 판정을 대신하지 않게, 실험 단계에서는 폴백 후보에 넣지 않음</td></tr>
<tr><td>모델이 담당자 검토를 지나치게 자주 고름(코드는 이를 막지 않음)</td><td>과잉 이관율을 평가 지표에 포함</td></tr>
<tr><td>프롬프트는 후보가 없으면 도구를 호출하라고 하는데 API 공급자에는 도구가 없음</td><td>후보가 빈 입력에서의 동작을 별도 시험</td></tr>
<tr><td>4B 모델의 컨텍스트 한계, 순화·초안 동시 호출 시 로컬 GPU 지연</td><td>입력 길이 측정, 동시 호출 간격 조정</td></tr>
<tr><td>비밀값 노출(<code>JEV_API_KEY</code>가 Codex 하위 프로세스·로그로 새는 것)</td><td>하위 프로세스 환경에서 제거, 오류 메시지의 주소·키 마스킹</td></tr>
</table>
"""
    )

    p5 = page(
        """
<h2>5. 비교 실험 계획과 결정 필요 사항</h2>
<h3>순서 (제안)</h3>
<table>
<tr><th style="width:8%">단계</th><th style="width:34%">할 일</th><th>끝났다고 보는 기준</th></tr>
<tr><td>1</td><td>기존 LLM의 기준 수치를 평가셋(dev·holdout)으로 측정</td><td>지표 6종과 파싱 실패율·지연이 보고서로 남음</td></tr>
<tr><td>2</td><td><code>jev_api</code> 공급자 추가와 테스트</td><td>단위 테스트 통과, 폴백 후보에는 넣지 않음</td></tr>
<tr><td>3</td><td>방식 A(대체)를 같은 평가셋으로 측정</td><td>기존과 같은 보고서 형식으로 비교 가능</td></tr>
<tr><td>4</td><td>방식 B(보완) 분기 구현 후 측정</td><td>오안내율 변화와 담당자 검토 비율 증가폭이 숫자로 나옴</td></tr>
<tr><td>5</td><td>결과 검토 후 적용 여부 결정</td><td>효과가 확인된 역할에만 적용, 사례 문서(CASE)와 CHANGELOG 기록</td></tr>
</table>
<div class="note">합격 기준 수치(예: 오안내율 몇 % 이하)는 1단계의 기존 수치를 본 뒤 팀이 정한다. 이 문서는 숫자를 미리 정하지 않았다. 실제 측정 전에는 Jev의 효과를 주장할 수 없다.</div>
<h3>결정이 필요한 것</h3>
<table>
<tr><th style="width:30%">질문</th><th>선택지</th></tr>
<tr><td>사용할 Jev는 무엇인가</td><td>OneJev1.6-4B(문서의 후보) / 다른 Jev / 외부 API</td></tr>
<tr><td>서빙 방식은 무엇인가</td><td>로컬 서버(OpenAI 호환) / 외부 API · 키 필요 여부 · chat template의 system 역할 지원</td></tr>
<tr><td>어느 방식부터 시험하나</td><td>보완(B) 먼저 추천 / 대체(A) 먼저 / 둘 다 병행</td></tr>
<tr><td>실행 환경</td><td>CPU 또는 GPU, 동시 호출 허용 수</td></tr>
</table>
<h3>이 문서의 한계</h3>
<ul>
<li>구현된 것이 없다. 변경 목록과 위험은 <code>src/llm</code>, <code>src/assist</code> 코드를 읽어 정리한 것이고 Jev를 실제로 호출해 본 적은 없다.</li>
<li>Jev의 한국어 민원 성능, 지연, 비용은 측정 전이다.</li>
<li>모델 확정과 운영 반영은 비교 실험 이후의 별도 결정이다.</li>
</ul>
<p class="cap">관련 문서: docs/plans/harness-roadmap.md · docs/plans/모델_선정과_미세조정_제안.md · docs/cases/사례-002-LLM-RAG-우선-구현과-Jev-후속-확장-2026-10-25.md</p>
"""
    )
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        f"<title>Jev 1차 판정 도입 제안서</title><style>{CSS}</style></head><body>"
        + p1
        + p2
        + p3
        + p4
        + p5
        + "</body></html>"
    )


def main() -> None:
    """제안서 HTML을 만들어 PDF로 저장합니다."""
    render_html_to_pdf(build(), OUT)
    print(f"PDF 생성: {OUT}")


if __name__ == "__main__":
    main()
