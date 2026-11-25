"""상세설명서 부록 C(RAG 지식베이스: 두 JSON에서 벡터 DB까지)의 쪽을 만드는 모듈입니다.

`plan_ai_process.py`가 불러 쓰며, 숫자는 `rag/origin`의 JSON과 `rag/config.py`·`rag/search.py`·
`rag/ingest.py`·`rag/origin/schema/complaint_rag.sql`에서 읽은 값입니다. 건수는 이 모듈이 JSON을
직접 세어 쓰므로 원본이 바뀌어도 어긋나지 않습니다. 비밀 값(키·접속 정보)은 싣지 않습니다.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORIGIN = ROOT / "rag" / "origin"

FAQ_KO = {
    "invest": "경제투자",
    "transport": "교통",
    "farming": "농업정책",
    "road": "도로",
    "cityRealty": "도시부동산",
    "MCST": "문화체육관광",
    "PHC": "보건소",
    "WE": "복지교육",
    "tax": "세무",
    "WaterSupply": "수도사업",
    "CarRegister": "차량등록",
    "AS": "행정지원",
    "Environment": "환경",
}


def _load() -> tuple[dict, list]:
    """두 원본 JSON을 읽습니다."""
    faq = json.loads((ORIGIN / "자주_묻는_민원.json").read_text(encoding="utf-8"))
    cases = json.loads((ORIGIN / "공개_민원_사례.json").read_text(encoding="utf-8"))
    return faq, cases


def _district(name: str | None) -> str:
    """부서 이름에서 구를 뽑습니다(`rag/data.py`의 `infer_district`와 같은 규칙)."""
    if not name:
        return "미지정"
    for d in ("상당구", "서원구", "흥덕구", "청원구"):
        if name.startswith(d + " ") or name.startswith(d[:-1] + "보건소"):
            return d
    return "미지정"


MARKER = (
    '<defs><marker id="{i}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" '
    'markerHeight="7" orient="auto"><path d="M1 1l8 4-8 4z" fill="#5b6f95"/></marker></defs>'
)


def _box(x, y, w, h, title, lines=(), fill="#fff", stroke="#c9d4ea", sw=1, tsize=13.5):
    """제목과 설명 줄이 든 둥근 상자 SVG 조각을 만듭니다."""
    out = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="{sw}"/>'
    ]
    cx = x + w / 2
    top = y + 20
    out.append(
        f'<text x="{cx}" y="{top}" text-anchor="middle" font-size="{tsize}" '
        f'font-weight="800" fill="#16203a">{title}</text>'
    )
    for i, line in enumerate(lines):
        out.append(
            f'<text x="{cx}" y="{top + 19 + i * 16}" text-anchor="middle" '
            f'font-size="11.3" fill="#4a5873">{line}</text>'
        )
    return "".join(out)


def _arrow(path, mid, dashed=False):
    """화살표 선 SVG 조각을 만듭니다."""
    dash = ' stroke-dasharray="6 4"' if dashed else ""
    return (
        f'<path d="{path}" stroke="#5b6f95" stroke-width="2" fill="none"{dash} '
        f'marker-end="url(#{mid})"/>'
    )


def fig_overview(n_faq: int, n_case: int, n_dept: int) -> str:
    """그림 C-1: 만들 때(적재)와 찾을 때(검색)의 전체 흐름."""
    s = [
        '<svg viewBox="0 0 1100 540" font-family="\'Malgun Gothic\',sans-serif">',
        MARKER.format(i="cm"),
        '<rect x="0" y="0" width="1100" height="268" rx="10" fill="#eef3fc" stroke="#c9d4ea"/>',
        '<text x="14" y="24" font-size="14" font-weight="800" fill="#1e4fc7">'
        "만들 때 — 적재(ingest) · 데이터가 바뀔 때만 한다</text>",
        _box(12, 40, 200, 62, "자주_묻는_민원.json", [f"FAQ {n_faq}건"], tsize=12.5),
        _box(
            12,
            116,
            200,
            62,
            "공개_민원_사례.json",
            [f"공개 사례 {n_case:,}건"],
            tsize=12.5,
        ),
        _box(
            252,
            52,
            210,
            114,
            "① 검사·정리",
            [
                "출처 ID 중복·누락 검사",
                "부서 상태 일치 확인",
                f"부서 사전 {n_dept}개 생성",
            ],
            fill="#fff",
        ),
        _box(
            502,
            52,
            222,
            114,
            "② 검색 본문 만들기",
            [
                "FAQ = 업무명+분류+안내+대상",
                "+접수처+기간+주의사항",
                "사례 = 제목+요지만",
            ],
        ),
        _box(
            764,
            40,
            324,
            62,
            "③-a 뜻을 숫자로 (임베딩)",
            ["e5-small-ko · 숫자 384개 · 접두 passage:"],
            fill="#e8f0ff",
            stroke="#2f6fed",
            sw=2,
        ),
        _box(
            764,
            116,
            324,
            62,
            "③-b 낱말 색인 (BM25 재료)",
            ["Kiwi 형태소 → 문서별 낱말 등장 횟수"],
            fill="#e8f0ff",
            stroke="#2f6fed",
            sw=2,
        ),
        _arrow("M212 71H250", "cm"),
        _arrow("M212 147H232V125H250", "cm"),
        _arrow("M462 109H500", "cm"),
        _arrow("M724 109H744V71H762", "cm"),
        _arrow("M744 109V147H762", "cm"),
        _box(
            12,
            204,
            1076,
            52,
            "④ PostgreSQL 의 complaint_rag 스키마에 한 번에 교체 저장",
            [
                f"faq_knowledge {n_faq} · routing_cases {n_case:,} · department_directory {n_dept} · "
                "낱말 표 3개 · 벡터 HNSW 색인"
            ],
            fill="#fff",
            stroke="#2f6fed",
            sw=2,
        ),
        _arrow("M926 178V202", "cm"),
        '<rect x="0" y="284" width="1100" height="246" rx="10" fill="#f3faf5" stroke="#bfe3cd"/>',
        '<text x="14" y="308" font-size="14" font-weight="800" fill="#16803f">'
        "찾을 때 — 민원이 들어올 때마다 (검색 서버 :8007)</text>",
        _box(12, 346, 150, 74, "민원 질문", ["제목 + 본문"]),
        _box(204, 326, 210, 52, "질문 → 숫자 384개", ["접두 query:"]),
        _box(204, 398, 210, 52, "질문 → 낱말", ["Kiwi 형태소"]),
        '<rect x="446" y="316" width="232" height="144" rx="10" fill="none" stroke="#7a8db3" '
        'stroke-width="1.5" stroke-dasharray="6 4"/>',
        _box(456, 326, 212, 52, "뜻 검색 (코사인)", ["pgvector · 상위 30건"]),
        _box(456, 398, 212, 52, "낱말 검색 (BM25)", ["표 3개로 계산 · 상위 30건"]),
        _box(718, 346, 170, 74, "RRF 합치기", ["순위로 합산 (k=60)", "FAQ·사례 따로"]),
        _box(918, 346, 170, 74, "상위 5건 + 부서 후보", ["→ 4장 AI 판정으로"]),
        _arrow("M162 383H182V352H202", "cm"),
        _arrow("M162 383H182V424H202", "cm"),
        _arrow("M414 352H454", "cm"),
        _arrow("M414 424H454", "cm"),
        _arrow("M668 352H690V383H716", "cm"),
        _arrow("M668 424H690V383H716", "cm"),
        _arrow("M888 383H916", "cm"),
        _arrow("M562 256V314", "cm", dashed=True),
        '<text x="574" y="290" font-size="12" fill="#3d4860">저장된 벡터·색인을 읽는다</text>',
        '<text x="14" y="500" font-size="11.5" fill="#6a7690">'
        "※ 서버(AI 워커)는 재정렬을 끄고(rerank=false) 검색하므로 RRF 상위 5건이 그대로 후보가 된다. "
        "재정렬 모델 bge-reranker-v2-m3는 코드에 있으나 접수 경로에서는 쓰지 않는다.</text>",
        '<text x="14" y="520" font-size="11.5" fill="#6a7690">'
        "※ 위 두 줄은 서로 독립이다. 위쪽은 DB를 채우는 일이고, 아래쪽은 채워진 DB를 읽기만 한다.</text>",
        "</svg>",
    ]
    return "".join(s)


def fig_data(faq: dict, cases: list) -> str:
    """그림 C-2: 두 원본의 구성(FAQ 분야별 건수, 사례의 부서 상태·구·부서)."""
    rows = sorted(
        ((FAQ_KO[k], len(v)) for k, v in faq.items() if k in FAQ_KO and v),
        key=lambda r: (-r[1], r[0]),
    )
    peak = max(n for _, n in rows)
    s = [
        '<svg viewBox="0 0 1100 412" font-family="\'Malgun Gothic\',sans-serif">',
        '<rect x="6" y="6" width="516" height="372" rx="10" fill="#fff" stroke="#c9d4ea"/>',
        f'<text x="20" y="30" font-size="14" font-weight="800" fill="#16203a">'
        f"FAQ {sum(n for _, n in rows)}건 — 분야별 건수</text>",
    ]
    for i, (name, n) in enumerate(rows):
        y = 48 + i * 25
        w = 330 * n / peak
        s.append(
            f'<text x="130" y="{y + 14}" text-anchor="end" font-size="12.5" fill="#3d4860">{name}</text>'
            f'<rect x="140" y="{y}" width="{w:.1f}" height="18" rx="4" fill="#2f6fed"/>'
            f'<text x="{146 + w:.1f}" y="{y + 14}" font-size="12.5" font-weight="700" '
            f'fill="#16203a">{n}</text>'
        )
    total = len(cases)
    status = Counter(c["department_status"] for c in cases)
    status_def = [
        ("current", "#2f6fed", "현재 부서 그대로"),
        ("normalized", "#0ea5a4", "표기 보완"),
        ("renamed", "#d97b06", "조직개편 반영"),
        ("review_required", "#d64545", "확인 필요(추천 근거 제외)"),
    ]
    s.append(
        '<rect x="540" y="6" width="554" height="372" rx="10" fill="#fff" stroke="#c9d4ea"/>'
        f'<text x="554" y="30" font-size="14" font-weight="800" fill="#16203a">'
        f"공개 사례 {total:,}건 — 부서 상태와 구</text>"
        '<text x="554" y="56" font-size="12.5" font-weight="700" fill="#3d4860">부서 상태 (department_status)</text>'
    )
    x = 554.0
    for key, color, _ in status_def:
        w = 520 * status[key] / total
        s.append(
            f'<rect x="{x:.1f}" y="64" width="{w:.1f}" height="24" fill="{color}"/>'
        )
        x += w
    for i, (key, color, label) in enumerate(status_def):
        lx = 554 + (i % 2) * 262
        ly = 112 + (i // 2) * 20
        s.append(
            f'<rect x="{lx}" y="{ly - 10}" width="11" height="11" rx="2" fill="{color}"/>'
            f'<text x="{lx + 16}" y="{ly}" font-size="11.5" fill="#3d4860">'
            f"{key} {status[key]:,} · {label}</text>"
        )
    dist = Counter(_district(c.get("department_current")) for c in cases)
    dist_def = [
        ("미지정", "#8794b3", "구 미지정(본청 등)"),
        ("흥덕구", "#2f6fed", "흥덕구"),
        ("청원구", "#1f9d55", "청원구"),
        ("상당구", "#d97b06", "상당구"),
        ("서원구", "#7c4dcc", "서원구"),
    ]
    s.append(
        '<text x="554" y="170" font-size="12.5" font-weight="700" fill="#3d4860">'
        "구 분포 (현재 부서 이름에서 추출)</text>"
    )
    x = 554.0
    for key, color, _ in dist_def:
        w = 520 * dist[key] / total
        s.append(
            f'<rect x="{x:.1f}" y="178" width="{w:.1f}" height="24" fill="{color}"/>'
        )
        x += w
    for i, (key, color, label) in enumerate(dist_def):
        lx = 554 + (i % 3) * 176
        ly = 226 + (i // 3) * 20
        s.append(
            f'<rect x="{lx}" y="{ly - 10}" width="11" height="11" rx="2" fill="{color}"/>'
            f'<text x="{lx + 16}" y="{ly}" font-size="11.5" fill="#3d4860">'
            f"{label} {dist[key]:,}</text>"
        )
    top = Counter(c["department_current"] for c in cases if c.get("department_current"))
    top5 = top.most_common(5)
    s.append(
        '<text x="554" y="278" font-size="12.5" font-weight="700" fill="#3d4860">'
        "사례가 많은 부서 5곳 (전체 부서 127개)</text>"
    )
    for i, (name, n) in enumerate(top5):
        y = 288 + i * 17
        w = 250 * n / top5[0][1]
        s.append(
            f'<text x="756" y="{y + 11}" text-anchor="end" font-size="11" fill="#3d4860">{name}</text>'
            f'<rect x="764" y="{y}" width="{w:.1f}" height="13" rx="3" fill="#2f6fed"/>'
            f'<text x="{770 + w:.1f}" y="{y + 11}" font-size="11" font-weight="700" fill="#16203a">{n:,}</text>'
        )
    s.append(
        '<text x="14" y="402" font-size="11.5" fill="#6a7690">'
        "※ 건수는 rag/origin의 JSON을 직접 센 값이다. 구는 민원 내용이 아니라 담당 부서 이름(예: 흥덕구 건설과)에서 뽑는다.</text>"
        "</svg>"
    )
    return "".join(s)


def _table_box(x, y, w, title, sub, rows, color="#2f6fed", dashed=False, fill="#fff"):
    """표(테이블) 상자: 이름·설명과 열 목록을 그립니다. 높이를 함께 돌려줍니다."""
    h = 44 + 17 * len(rows)
    dash = ' stroke-dasharray="6 4"' if dashed else ""
    s = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{fill}" stroke="{color}" '
        f'stroke-width="2"{dash}/>',
        f'<rect x="{x}" y="{y}" width="{w}" height="26" rx="9" fill="{color}"/>',
        f'<rect x="{x}" y="{y + 14}" width="{w}" height="12" fill="{color}"/>',
        f'<text x="{x + 10}" y="{y + 18}" font-size="13" font-weight="800" fill="#fff">{title}</text>',
        f'<text x="{x + w - 10}" y="{y + 18}" text-anchor="end" font-size="11" fill="#fff">{sub}</text>',
    ]
    for i, row in enumerate(rows):
        s.append(
            f'<text x="{x + 10}" y="{y + 46 + i * 17}" font-size="11.2" fill="#16203a">{row}</text>'
        )
    return "".join(s), h


def fig_er(n_faq: int, n_case: int, n_dept: int) -> str:
    """그림 C-3: complaint_rag 스키마 표의 구성과 연결."""
    faq, fh = _table_box(
        10,
        14,
        340,
        "faq_knowledge",
        f"FAQ {n_faq}건",
        [
            "source_id (PK) · title · category",
            "search_text  ← 검색에 쓴 본문",
            "payload (JSONB)  ← 원문 전체",
            "source_url · source_retrieved_at",
            "embedding vector(384)",
            "content_hash · embedding_hash",
            "token_count",
        ],
    )
    cas, ch = _table_box(
        10,
        232,
        340,
        "routing_cases",
        f"공개 사례 {n_case:,}건",
        [
            "source_id (PK) · title",
            "search_text  ← 제목 + 요지",
            "payload (JSONB)  ← 원문 전체(답변 포함)",
            "department_id (FK) · department_status",
            "district · complaint_date",
            "routing_eligible · summary_missing",
            "embedding vector(384)",
            "content_hash · embedding_hash",
            "token_count",
        ],
    )
    dep, dh = _table_box(
        404,
        232,
        320,
        "department_directory",
        f"부서 {n_dept}개",
        [
            "department_id (PK)",
            "canonical_name (현재 공식 이름)",
            "aliases (옛 이름·별칭)",
            "district · jurisdiction (JSONB)",
            "duty_status: unverified | verified",
            "automatic_routing_ready (기본 false)",
            "observed_case_titles",
        ],
    )
    ai, ah = _table_box(
        404,
        14,
        320,
        "complaint_app.ai_results",
        "업무 스키마",
        ["department_id  → 부서 사전을 가리킴", "automatic_transfer = false 강제"],
        color="#8794b3",
        dashed=True,
    )
    tp, _ = _table_box(
        776,
        14,
        316,
        "term_postings",
        "낱말 × 문서",
        ["corpus · term · source_id (PK)", "tf  (그 문서에서 나온 횟수)"],
        color="#1f9d55",
    )
    ts, _ = _table_box(
        776,
        100,
        316,
        "term_statistics",
        "낱말별 문서 수",
        ["corpus · term (PK)", "document_frequency"],
        color="#1f9d55",
    )
    cs, _ = _table_box(
        776,
        186,
        316,
        "corpus_statistics",
        "묶음별 통계",
        ["corpus (PK) · document_count", "average_length (평균 낱말 수)"],
        color="#1f9d55",
    )
    ec, _ = _table_box(
        776,
        272,
        316,
        "embedding_cache",
        "벡터 보관함",
        ["signature · text_hash (PK)", "vector (float32 바이트)"],
        color="#d97b06",
    )
    im, _ = _table_box(
        776,
        358,
        316,
        "index_metadata",
        "색인 설정 기록",
        ["key (PK) · value (JSONB)", "모델·차원·서명·최근 적재"],
        color="#d97b06",
    )
    s = [
        '<svg viewBox="0 0 1100 470" font-family="\'Malgun Gothic\',sans-serif">',
        MARKER.format(i="ce"),
        faq,
        cas,
        dep,
        ai,
        tp,
        ts,
        cs,
        ec,
        im,
        _arrow("M350 330H402", "ce"),
        '<text x="376" y="320" text-anchor="middle" font-size="11" fill="#1e4fc7" font-weight="700">FK</text>',
        _arrow("M564 100V230", "ce", dashed=True),
        '<text x="574" y="170" font-size="11" fill="#5a6782">교차 스키마 FK</text>',
        '<text x="404" y="446" font-size="11.3" fill="#3d4860">초록 표 3개는 BM25(낱말 검색)용이고, 외래 키 대신</text>',
        '<text x="404" y="463" font-size="11.3" fill="#3d4860">corpus + source_id 값으로 문서와 이어진다.</text>',
        '<text x="10" y="463" font-size="11.3" fill="#6a7690">※ 파란 표 3개가 지식 본체, 주황 표 2개는 재적재 보조.</text>',
        "</svg>",
    ]
    return "".join(s)


def fig_reuse() -> str:
    """그림 C-4: 벡터를 다시 계산하지 않는 판단 순서."""
    s = [
        '<svg viewBox="0 0 1100 250" font-family="\'Malgun Gothic\',sans-serif">',
        MARKER.format(i="cr"),
        _box(10, 24, 190, 70, "문서 한 건", ["search_text의 해시", "(embedding_hash)"]),
        _box(
            250,
            12,
            250,
            94,
            "DB에 같은 문서의 벡터가",
            ["있고, 해시와 모델 서명이", "모두 같은가?"],
            fill="#e8f0ff",
            stroke="#2f6fed",
            sw=2,
            tsize=12.5,
        ),
        _box(
            560,
            12,
            220,
            94,
            "캐시(embedding_cache)에",
            ["같은 서명 + 같은 해시가", "있는가?"],
            fill="#e8f0ff",
            stroke="#2f6fed",
            sw=2,
            tsize=12.5,
        ),
        _box(
            840,
            12,
            250,
            94,
            "모델로 새로 계산",
            ["128건씩 묶어 계산", "계산 즉시 캐시에 저장"],
            fill="#fff3d6",
            stroke="#d97b06",
            sw=2,
        ),
        _box(
            250,
            150,
            250,
            60,
            "DB 벡터 재사용",
            ["(가장 흔한 경우)"],
            fill="#e9f7ee",
            stroke="#1f9d55",
            sw=2,
        ),
        _box(
            560,
            150,
            220,
            60,
            "캐시 벡터 재사용",
            ["(문서 표가 바뀌어도 OK)"],
            fill="#e9f7ee",
            stroke="#1f9d55",
            sw=2,
        ),
        _arrow("M200 59H248", "cr"),
        _arrow("M500 59H558", "cr"),
        _arrow("M780 59H838", "cr"),
        _arrow("M375 106V148", "cr"),
        _arrow("M670 106V148", "cr"),
        '<text x="386" y="132" font-size="12" font-weight="700" fill="#16803f">예</text>',
        '<text x="681" y="132" font-size="12" font-weight="700" fill="#16803f">예</text>',
        '<text x="528" y="50" text-anchor="middle" font-size="12" font-weight="700" fill="#a85f00">아니오</text>',
        '<text x="810" y="50" text-anchor="middle" font-size="12" font-weight="700" fill="#a85f00">아니오</text>',
        '<text x="10" y="236" font-size="11.5" fill="#6a7690">'
        "※ 모델·리비전·차원·접두·본문 버전 중 하나라도 바뀌면 서명이 달라져, --reembed 없이는 적재가 멈춘다(옛 벡터와 섞이지 않게).</text>",
        "</svg>",
    ]
    return "".join(s)


def build_pages() -> dict[str, str]:
    """부록 C의 쪽 HTML(키: 쪽 이름)을 만듭니다."""
    faq, cases = _load()
    n_faq = sum(len(v) for v in faq.values())
    n_case = len(cases)
    n_dept = len(
        {c["department_current"] for c in cases if c.get("department_current")}
    )
    n_no_summary = sum(1 for c in cases if not (c.get("summary") or "").strip())
    n_review = sum(1 for c in cases if c["department_status"] == "review_required")
    dates = [c["complaint_date"] for c in cases if c.get("complaint_date")]

    c1 = f"""
<h2>부록 C. RAG 지식베이스 — 두 JSON에서 벡터 DB까지</h2>
<p>4장은 질문이 들어왔을 때 <b>어떻게 찾는지</b>를 설명했습니다. 이 부록은 그 앞에서 일어나는 일, 곧 <b>찾을 대상을 어떻게 만들어 두는지</b>를 설명합니다. 재료는 청주톡톡에서 수집한 JSON 파일 두 개이고, 이를 PostgreSQL의 <code>complaint_rag</code> 스키마에 <b>벡터(뜻)와 낱말 색인</b>으로 저장해 둡니다. 민원 업무 데이터(<code>complaint_app</code>)와는 스키마가 달라 서로 섞이지 않습니다.</p>
<div class="fig">{fig_overview(n_faq, n_case, n_dept)}</div><div class="cap">그림 C-1. 지식베이스를 만드는 일(위)과 찾는 일(아래)</div>
<div class="grid3">
 <div class="card bl"><h4>컬렉션을 둘로 나눈 이유</h4><p class="small"><b>FAQ</b>는 "지금 이렇게 안내해도 되는 근거", <b>공개 사례</b>는 "비슷한 과거 민원과 부서 후보"입니다. 역할이 달라 표·색인·검색을 따로 하며, 사례의 과거 답변은 현재 정책 안내로 쓰지 않습니다.</p></div>
 <div class="card g"><h4>색인을 둘로 만든 이유</h4><p class="small">뜻으로 찾는 <b>벡터(pgvector)</b>와 낱말로 찾는 <b>BM25</b>는 서로의 약점을 메웁니다. 둘 다 같은 문서 본문(<code>search_text</code>)에서 만들어집니다(부록 A).</p></div>
 <div class="card o"><h4>문서를 자르지 않은 이유</h4><p class="small">FAQ는 대상·접수 조건·처리기간·주의사항이 한 건에 함께 있어야 뜻이 맞습니다. 그래서 <b>한 건이 한 행</b>이고, 조각내어 저장하지 않습니다(부록 A-5).</p></div>
</div>
<h3>C-0. 한눈에 숫자</h3>
<table>
<tr><th style="width:26%">항목</th><th style="width:30%">값</th><th>출처</th></tr>
<tr><td>FAQ 안내 자료</td><td><b>{n_faq}건</b></td><td><code>rag/origin/자주_묻는_민원.json</code></td></tr>
<tr><td>공개 민원 사례</td><td><b>{n_case:,}건</b> ({min(dates)} ~ {max(dates)} 신청)</td><td><code>rag/origin/공개_민원_사례.json</code></td></tr>
<tr><td>부서 사전</td><td><b>{n_dept}개</b> (현행 부서가 확인된 사례에서 생성)</td><td><code>rag/data.py</code>의 <code>build_directory</code></td></tr>
<tr><td>임베딩 모델</td><td><code>dragonkue/multilingual-e5-small-ko</code> · <b>384차원</b></td><td><code>rag/config.py</code> (<code>RAG_EMBEDDING_PROFILE</code>로 바꿈)</td></tr>
<tr><td>벡터 색인</td><td>HNSW · 코사인 거리</td><td><code>rag/origin/schema/complaint_rag.sql</code></td></tr>
<tr><td>낱말 분석</td><td>Kiwi 형태소(명사·동사·형용사·외국어·숫자만)</td><td><code>rag/korean.py</code></td></tr>
<tr><td>후보·합치기</td><td>컬렉션당 후보 30건 → RRF(k=60) → 상위 5건</td><td><code>rag/config.py</code>·<code>rag/search.py</code></td></tr>
</table>
"""

    faq_ex = (
        "업무명: 대형폐기물 배출 방법\n"
        "분류: 환경 / 폐기물지도 / 대형폐기물\n"
        "상세 안내: ■ 방문신고 … ■ 인터넷신고 … ■ 모바일어플 …\n"
        "대상: 대형폐기물 배출자\n"
        "접수처와 조건: 읍면동 행정복지센터, 홈페이지, 어플\n"
        "처리기간: 평일 1 ~ 2일 내 수거 (공휴일 미수거) / …\n"
        "주의사항: ※ 수거된 폐기물 접수건은 취소불가 …"
    )
    case_ex = "민원 제목: 711번 버스 운행 불만\n민원 요지: 711번 버스 운행 불편 민원"
    c2 = f"""
<h2>부록 C (계속). C-1 원본 두 파일과 검색 본문</h2>
<table>
<tr><th style="width:16%"></th><th style="width:42%">자주_묻는_민원.json</th><th>공개_민원_사례.json</th></tr>
<tr><td>하는 일</td><td>지금 안내해도 되는 근거 (<code>faq_answer</code>)</td><td>비슷한 과거 민원, 담당 부서 후보 (<code>department_suggestion</code>)</td></tr>
<tr><td>건수·구조</td><td>{n_faq}건 · 분야 코드 → 민원 배열(객체). 14개 키 중 13개 분야에 있음</td><td>{n_case:,}건 · 민원 배열. 게시물 번호 내림차순</td></tr>
<tr><td>문서 키</td><td colspan="2"><code>source_id</code>(상세 페이지의 <code>no</code>). 화면의 표시 번호 <code>id</code>는 바뀔 수 있어 키로 쓰지 않는다.</td></tr>
<tr><td>검색 본문에 넣는 것</td><td>업무명 · 분류(대/중/소) · 상세 안내 · 대상 · 접수처와 조건 · 처리기간 · 주의사항</td><td>민원 제목 + 민원 요지 (요지가 없는 {n_no_summary}건은 제목만)</td></tr>
<tr><td>넣지 않는 것</td><td>값이 빈 항목만 생략한다. 조건을 줄이거나 잘라내지 않는다.</td><td><b>처리 답변(<code>resolution</code>)과 부서 이름</b>. 뜻 검색에 섞지 않는다.</td></tr>
<tr><td>본문 평균 길이</td><td>약 502자 · 낱말(형태소) 평균 약 129개</td><td>약 229자 · 낱말 평균 약 49개</td></tr>
<tr><td>원문 보관</td><td colspan="2"><code>payload</code>(JSONB)에 원문 전체와 <code>source_url</code>·수집 시각을 함께 둔다. 검색 응답의 <code>evidence</code>가 이 값이다.</td></tr>
</table>
<div class="fig">{fig_data(faq, cases)}</div><div class="cap">그림 C-2. 두 원본의 구성 (JSON을 직접 센 값)</div>
<h3>검색 본문 만들기 (<span class="kind fn">함수</span> <code>faq_text()</code> · <code>case_text()</code>)</h3>
<p class="small">두 함수는 원본 항목을 "라벨: 값" 줄로 묶고, 유니코드 NFKC 정규화와 폭 없는 공백 제거(<code>normalize_text</code>)를 합니다. 이 문자열이 <code>search_text</code>이며 <b>벡터와 낱말 색인이 모두 이것에서 만들어집니다.</b></p>
<div class="grid3">
 <div style="flex:1.3"><b class="small">FAQ 한 건의 search_text (줄임)</b><pre>{faq_ex}</pre></div>
 <div style="flex:1"><b class="small">공개 사례 한 건의 search_text</b><pre>{case_ex}</pre>
 <p class="small">사례의 <code>resolution</code>(답변)과 <code>department</code>는 본문에 없다. 답변 문장이 섞이면 "과거 답변이 비슷한 민원"이 뽑히는 오염이 생기고, 현재 정책 안내로 오해될 수 있기 때문이다.</p></div>
</div>
<h3>적재 전 검사 (<span class="kind fn">함수</span> <code>load_sources()</code>)</h3>
<ul>
<li>원본이 비어 있으면 중단한다(<b>빈 원본으로 기존 색인을 덮어쓰지 않기</b> 위해).</li>
<li><code>source_id</code>가 없거나 중복이면, 제목·출처 주소·수집 시각이 없으면 중단한다.</li>
<li>부서 상태가 <code>current · normalized · renamed · review_required</code> 넷 중 하나가 아니거나, <code>review_required</code>와 "현재 부서 없음(<code>null</code>)"이 어긋나면 중단한다. 현재 <code>review_required</code>는 {n_review}건이다.</li>
<li>검사는 DB에 쓰기 <b>전</b>에 끝나므로, 하나라도 어긋나면 기존 색인은 그대로 남는다.</li>
</ul>
"""

    c3 = f"""
<h2>부록 C (계속). C-2 DB 구조 — PostgreSQL + pgvector</h2>
<p>한 PostgreSQL 안에서 <b>스키마로 나눕니다</b>. 검색 지식은 <code>complaint_rag</code>(표 8개), 민원 업무는 <code>complaint_app</code>입니다. <b>pgvector</b>는 PostgreSQL 확장으로, 숫자 목록을 <code>vector(384)</code> 자료형으로 저장하고 가까운 것을 찾는 연산자(<code>&lt;=&gt;</code>, 코사인 거리)와 HNSW 색인을 제공합니다.</p>
<div class="fig">{fig_er(n_faq, n_case, n_dept)}</div><div class="cap">그림 C-3. complaint_rag 스키마의 표와 연결 (DDL: rag/origin/schema/complaint_rag.sql)</div>
<h3>열과 색인을 읽는 법</h3>
<table>
<tr><th style="width:22%">이름</th><th>의미</th></tr>
<tr><td><code>search_text</code></td><td>검색에 쓴 본문 그대로. 벡터와 낱말 색인의 재료이며, 재정렬을 켜면 그 입력으로도 쓴다.</td></tr>
<tr><td><code>payload</code> (JSONB)</td><td>원문 전체. 검색이 끝나면 이것이 근거(<code>evidence</code>)로 나간다. AI에게 넘기기 전에 점수·해시는 지운다(4장).</td></tr>
<tr><td><code>embedding</code></td><td>정규화한 384차원 벡터. 차원은 DDL의 <code>__EMBEDDING_DIM__</code>을 모델 프로필 값으로 바꿔 적용한다. 모델이 바뀌면 차원도 바뀔 수 있다.</td></tr>
<tr><td><code>content_hash</code> · <code>embedding_hash</code></td><td>원문이 바뀌었는지, 벡터를 다시 만들어야 하는지 판단하는 SHA256 값. <code>embedding_hash</code>는 <code>search_text</code>만의 해시다.</td></tr>
<tr><td><code>routing_eligible</code></td><td>부서 추천 근거로 써도 되는 사례인지. <code>department_id</code>가 있고 상태가 <code>review_required</code>가 아닐 때만 참이며, 표의 <b>CHECK 제약</b>이 이를 강제한다.</td></tr>
<tr><td><code>token_count</code> · <code>district</code></td><td>낱말 수(BM25의 문서 길이 보정용) · 부서 이름에서 뽑은 구(같은 이름의 과가 구마다 있어 합치지 않기 위함).</td></tr>
</table>
<div class="note"><b>HNSW는 "가까운 이웃을 빨리 찾는 지름길 지도"입니다.</b> 사례 {n_case:,}건을 하나하나 비교하지 않고 지도를 따라 가까운 후보로 좁혀 갑니다. 대신 근사 검색이라 아주 드물게 최선이 빠질 수 있어, 검색 때 탐색 폭을 넓히는 설정(<code>hnsw.ef_search = 100</code>)을 둡니다. 색인은 <code>faq_embedding_hnsw</code>·<code>routing_embedding_hnsw</code>(벡터, <code>vector_cosine_ops</code>)와 <code>routing_department</code>·<code>routing_district</code>(부서별·구별 사례 조회)입니다.</div>
<div class="warn"><b>부서 사전은 "이름 확인"이지 "업무 확인"이 아닙니다.</b> 적재 때 만드는 값은 <code>duty_status = unverified</code>, <code>automatic_routing_ready = false</code>가 기본이고, 관할(<code>jurisdiction_status</code>)도 이름에서 추정한 값(<code>inferred_from_name</code>)입니다. 공식 업무분장 대조는 끝나지 않았으므로 자동 이관 근거로 쓰지 않습니다.</div>
"""

    c4 = f"""
<h2>부록 C (계속). C-3 적재 과정 (<code>python -m rag ingest</code>)</h2>
<p>적재는 데이터가 바뀌었을 때만 하는 일회성 작업이고, 서버가 민원을 처리하는 동안에는 돌지 않습니다. 이미 만들어 둔 벡터는 해시로 알아보고 다시 계산하지 않습니다.</p>
<div class="fig">{fig_reuse()}</div><div class="cap">그림 C-4. 벡터를 다시 계산하지 않는 판단 순서</div>
<table>
<tr><th style="width:5%">순서</th><th style="width:25%">단계</th><th>하는 일</th></tr>
<tr><td>1</td><td>원본 읽기·검사</td><td><code>load_sources()</code>가 두 JSON을 검사하고, 문서 {n_faq + n_case:,}건(FAQ {n_faq} + 사례 {n_case:,})과 부서 사전 {n_dept}개를 메모리에 만든다.</td></tr>
<tr><td>2</td><td>동시 적재 방지·서명 비교</td><td>다른 적재가 돌고 있으면 중단한다. 모델·리비전·차원·접두·본문 버전을 묶은 <b>서명</b>이 기존과 다르면 <code>--reembed</code> 없이는 멈춘다.</td></tr>
<tr><td>3</td><td>벡터 준비</td><td>그림 C-4의 순서로 재사용 또는 새 계산. 문서에는 접두 <code>"passage: "</code>를 붙이고 정규화한다. 128건씩 묶어 계산하고 바로 캐시에 저장한다.</td></tr>
<tr><td>4</td><td>낱말 분석</td><td>Kiwi로 문서마다 낱말 횟수를 센다. 형태소가 하나도 없는 문서는 오류로 멈춘다.</td></tr>
<tr><td>5</td><td>한 번에 교체</td><td>부서 → FAQ·사례 → 원본에서 사라진 문서 삭제 → 낱말 표 3개 → 설정·최근 적재 기록을 <b>한 트랜잭션</b>으로 쓴다. 앞 단계(검사·모델 계산)가 모두 성공한 뒤에만 시작하므로, 중간에 실패해도 반쯤 바뀐 색인이 남지 않는다.</td></tr>
<tr><td>6</td><td>통계 갱신</td><td><code>ANALYZE</code>로 DB가 검색 계획을 잘 세우게 한다.</td></tr>
</table>
<p class="small">다른 컴퓨터에서는 JSON으로 다시 적재하는 대신 벡터까지 든 DB 복사본(<code>rag/origin/dumps/complaint_rag.dump</code>)을 복원할 수도 있습니다. 이 파일은 크기와 보안 때문에 Git에 올리지 않습니다.</p>
<h3>낱말 표 3개는 이렇게 채워진다 (<code>write_bm25</code>)</h3>
<p class="small">앞 쪽 사례(711번 버스) 한 건을 Kiwi로 쪼갠 실제 결과입니다. "민원" 같은 상용어는 걸러지지만 "제목"·"요지"처럼 모든 사례에 붙는 라벨은 남습니다(어디에나 있어 BM25 점수는 낮게 매겨집니다).</p>
<table>
<tr><th style="width:26%">표</th><th>이 사례에서 생기는 행</th></tr>
<tr><td><code>term_postings</code></td><td>(routing, 711, 638956, <b>2</b>) · (routing, 버스, 638956, <b>2</b>) · (routing, 운행, 638956, <b>2</b>) · (routing, 불만, 638956, 1) · (routing, 불편, 638956, 1) · (routing, 제목, 638956, 1) · (routing, 요지, 638956, 1)</td></tr>
<tr><td><code>term_statistics</code></td><td>낱말마다 "그 낱말이 나온 문서 수". 드문 낱말일수록 점수가 커지는 근거.</td></tr>
<tr><td><code>corpus_statistics</code></td><td>컬렉션별 문서 수와 평균 낱말 수. 현재 JSON·Kiwi로 센 값은 FAQ 평균 약 129개, 사례 평균 약 49개다.</td></tr>
</table>
<p class="small">현재 원본 기준으로 낱말 행 수는 FAQ 약 6,700행, 사례 약 17만 3천 행입니다(Kiwi 버전에 따라 조금 달라질 수 있는 계산값).</p>
"""

    dense_sql = (
        "SELECT d.source_id,\n"
        "       1 - (d.embedding &lt;=&gt; :질문벡터) AS score\n"
        "FROM complaint_rag.routing_cases d\n"
        "WHERE (d.district = :구\n"
        "       OR d.district IS NULL)\n"
        "ORDER BY d.embedding &lt;=&gt; :질문벡터\n"
        "LIMIT 30"
    )
    bm25_sql = (
        "낱말마다 더해서 문서 점수로 한다:\n"
        "  IDF = ln(1 + (N - df + 0.5) / (df + 0.5))\n"
        "        (드문 낱말일수록 큼)\n"
        "  빈도항 = tf * (k1 + 1)\n"
        "         / (tf + k1 * (1 - b + b * 길이/평균길이))\n"
        "        (긴 문서일수록 깎음)\n"
        "  점수 = SUM( IDF * 빈도항 )\n"
        "k1 = 1.5, b = 0.75\n"
        "-- 낱말 표 3개를 JOIN해 DB 안에서 계산"
    )
    c5 = f"""
<h2>부록 C (계속). C-4 찾을 때 DB가 하는 일</h2>
<p>질문 한 건이 들어오면 검색 서버는 <b>컬렉션(FAQ·사례)마다 같은 순서</b>를 한 번씩 밟습니다. 4장의 알고리즘 표를 DB 쪽에서 본 것입니다.</p>
<div class="grid3">
 <div style="flex:1"><b class="small">뜻 검색 (pgvector 코사인)</b><pre>{dense_sql}</pre></div>
 <div style="flex:1"><b class="small">낱말 검색 (BM25, 점수식)</b><pre>{bm25_sql}</pre></div>
</div>
<table>
<tr><th style="width:30%">설정</th><th style="width:16%">값</th><th>뜻</th></tr>
<tr><td>후보 수 <code>candidate_k</code></td><td>30</td><td>뜻 검색과 낱말 검색이 각각 가져오는 후보 수(컬렉션별)</td></tr>
<tr><td>합치기 상수 <code>rrf_k</code></td><td>60</td><td>순위 1위와 5위의 차이를 지나치게 키우지 않는 완충값</td></tr>
<tr><td>반환 수 <code>limit</code></td><td>5</td><td>서버가 컬렉션마다 받는 건수. 재정렬을 끄면 RRF 상위 5건이 곧 결과</td></tr>
<tr><td><code>hnsw.ef_search</code></td><td>100</td><td>HNSW가 탐색하는 후보 폭. 클수록 정확하고 느림</td></tr>
<tr><td><code>hnsw.iterative_scan</code></td><td>strict_order</td><td>구 조건으로 걸러 후보가 모자라면 더 탐색하되 거리순을 지킴</td></tr>
<tr><td>트랜잭션 격리</td><td>REPEATABLE READ</td><td>한 번의 검색 동안 같은 시점의 DB 내용을 봄</td></tr>
<tr><td>재정렬 <code>rerank_k</code></td><td>20 (꺼짐)</td><td>켜면 상위 20건을 <code>bge-reranker-v2-m3</code>로 다시 정렬. 접수 워커는 끔</td></tr>
</table>
<h3>찾은 뒤에 일어나는 일</h3>
<ul>
<li><b>관할 필터는 사례에만</b> 적용합니다. 구가 명시되면 같은 구 사례와 구 미지정(본청 등) 사례만 남기고, 질문 속 지명으로 구를 추측해 걸러 내지 않습니다. FAQ에는 적용하지 않습니다.</li>
<li><b>부서 후보</b>는 <code>routing_eligible</code>인 사례만으로 묶습니다. 같은 부서에 사례가 많다고 앞세우지 않고(다수결 금지), 그 부서의 <b>가장 높은 순위 사례</b>로 정렬합니다. <code>automatic_transfer</code>는 항상 거짓입니다.</li>
<li>응답은 항상 <code>retrieval_only = true</code>, <code>decision = "requires_gate"</code>입니다. 검색은 후보를 줄 세울 뿐이며 채택은 AI 판정과 코드 검증, 담당자가 정합니다.</li>
</ul>
<h3>알려진 한계 (실측하지 못했거나 보증하지 않는 것)</h3>
<table>
<tr><th style="width:30%">한계</th><th>설명</th></tr>
<tr><td>점수는 확률이 아니다</td><td>코사인·BM25·RRF 값은 정답일 확률이 아니다. 그래서 AI에게도 넘기지 않고 임계값 컷오프도 없다.</td></tr>
<tr><td>최신성을 보증하지 않는다</td><td><code>retrieved_at</code>은 수집 시각이지 원문 수정일이 아니다. FAQ의 정책·연락처·접수처 현행성은 재확인이 필요하다. 사이트를 다시 수집하고 재적재해야 반영된다.</td></tr>
<tr><td>부서 업무분장 미검증</td><td>부서 이름은 조직도와 대조했으나 업무분장·관할은 아니다. {n_review}건은 현재 부서를 정하지 못해 추천 근거에서 제외한다.</td></tr>
<tr><td>긴 본문의 뒷부분</td><td>임베딩 모델의 입력 한도는 512토큰이라 긴 FAQ는 뒷부분이 잘려 벡터에 반영되지 않을 수 있다. 몇 건이 해당하는지는 측정하지 않았다(낱말 색인은 전체를 쓴다).</td></tr>
<tr><td>평가 범위</td><td>2026-11-06 검색 회귀 10건(FAQ 5·부서 4·범위 밖 1)에서 기대 문서가 모두 1위였다. 소규모 점검이며 정확도 평가가 아니다.</td></tr>
</table>
"""
    return {"C1": c1, "C2": c2, "C3": c3, "C4": c4, "C5": c5}
