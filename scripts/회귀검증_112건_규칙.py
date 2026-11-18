"""112건 실증 원자료와 공개 민원 사례를 대상으로 규칙·전처리 회귀를 1초 내 검증합니다.

LLM 호출 없이 결정론적 코드 규칙(`district.py`, `followup.py`, `place_tool.py`,
`policy.py`)의 정확도와 오탐 방지를 점검할 때 사용합니다.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.assist.district import _find_regex_district, extract_external_jurisdiction
from src.assist.followup import needs_sanitize
from src.llm.place_tool import extract_place_candidates

EVAL_112_PATH = ROOT / "rag" / "reports" / "lab-5010-eval-112-20261117.json"
ROUTING_CASES_PATH = ROOT / "rag" / "origin" / "공개_민원_사례.json"


def _composed_query(item: dict[str, Any]) -> str:
    """112건 평가 항목에서 제목·상세 본문을 결합한 질의 문자열을 만듭니다.

    Args:
        item: 평가 JSON의 단일 문항 딕셔너리입니다.

    Returns:
        제목과 본문을 공백으로 합친 문자열입니다.
    """
    return f"{item.get('title') or ''} {item.get('body') or ''}".strip()


def run_eval112_deterministic_checks() -> list[str]:
    """112건 원자료의 핵심 결함군과 대조군에 대해 규칙 회귀를 검사합니다.

    Returns:
        실패 사유 문자열 목록입니다. 비어 있으면 모든 단언을 통과한 것입니다.
    """
    if not EVAL_112_PATH.is_file():
        return [f"원자료 파일을 찾지 못했습니다: {EVAL_112_PATH}"]
    raw = json.loads(EVAL_112_PATH.read_text(encoding="utf-8"))
    by_id = {item["id"]: item for item in raw.get("results") or []}
    failures: list[str] = []

    # 1. 시설·생태 서술 '꺼져' 오탐 배제 검증 (B02, B14, E17)
    for case_id in ("B02", "B14", "E17"):
        q = _composed_query(by_id[case_id])
        if needs_sanitize(q):
            failures.append(f"[{case_id}] 정상 시설 '꺼져' 서술에 순화 휴리스틱 오탐")

    # 2. 초성·띄어쓰기·직접 욕설·보복·고정 조롱 휴리스틱 안전망 검증
    for case_id in ("D09", "D10", "D11", "D12", "D13", "D14", "D15", "D18"):
        q = _composed_query(by_id[case_id])
        if not needs_sanitize(q):
            failures.append(f"[{case_id}] 욕설·변형·보복·조롱 안전망 미감지")

    # 3. 지명·숫자 경계 및 단일구 랜드마크 추론 검증 (B02, B06, B14, B17, F12)
    expected_districts = {
        "B02": ("상당구", False),
        "B06": ("청원구", False),
        "B12": (None, False),
        "B14": (None, True),
        "B17": ("흥덕구", False),
        "F12": ("흥덕구", False),
    }
    for case_id, expected in expected_districts.items():
        actual = _find_regex_district(_composed_query(by_id[case_id]))
        if actual != expected:
            failures.append(
                f"[{case_id}] 구 정규식 불일치: expected={expected}, actual={actual}"
            )

    # 4. B06/F12 상위 5후보 내 랜드마크 보존 & 일반 FAQ 불용어 오매칭 차단 (B12)
    if (
        "청주국제공항"
        not in extract_place_candidates(_composed_query(by_id["B06"]))[:5]
    ):
        failures.append(
            "[B06] extract_place_candidates 상위 5후보에 '청주국제공항' 누락"
        )
    if (
        "문암생태공원"
        not in extract_place_candidates(_composed_query(by_id["F12"]))[:5]
    ):
        failures.append(
            "[F12] extract_place_candidates 상위 5후보에 '문암생태공원' 누락"
        )

    b12_cands = extract_place_candidates(_composed_query(by_id["B12"]))
    if any(tok in b12_cands for tok in ("지역", "어딘가", "학교", "미기재")):
        failures.append(f"[B12] 일반어 오매칭 후보 잔존: {b12_cands}")

    # 5. 추가 경계 패치 검증: 광역시 '~시'·외부 도로명·닫는 괄호·도로+번지 결합
    if extract_external_jurisdiction("서울시 종로구 사직동 도로 포트홀 보수") is None:
        failures.append("[EXT] '서울시 종로구 사직동' 외부 관할 미감지")
    if extract_external_jurisdiction("대전시 유성구 봉명동 가로등 고장") is None:
        failures.append("[EXT] '대전시 유성구 봉명동' 외부 관할 미감지")
    if (
        extract_external_jurisdiction("경기도 화성시 동탄대로 123 보도블록 파손")
        is None
    ):
        failures.append("[EXT] '경기도 화성시 동탄대로 123' 외부 도로명 관할 미감지")
    if _find_regex_district("긴급)복대동 영조2차 아파트 앞")[0] != "흥덕구":
        failures.append("[BOUNDARY] '긴급)복대동' 닫는 괄호 경계 미감지")
    if (
        extract_place_candidates("주말 주차단속 오송생명14로 283 앞")[0]
        != "오송생명14로 283"
    ):
        failures.append("[PLACE] 도로명+번지 결합 최우선 후보 누락")
    return failures


def run_corpus_district_checks() -> dict[str, Any]:
    """공개 민원 사례 5,015건을 대상으로 구 정규식 정밀도와 외부 오탐 0건을 확인합니다.

    Returns:
        정확 일치·오분류·충돌·미추출·외부 오탐 건수 요약 딕셔너리입니다.
    """
    cases = json.loads(ROUTING_CASES_PATH.read_text(encoding="utf-8"))
    exact = wrong = conflict = none_count = 0
    ext_fp: list[Any] = []
    for item in cases:
        text = f"{item.get('title') or ''} {item.get('summary') or ''}"
        if extract_external_jurisdiction(text) is not None:
            ext_fp.append(item.get("id"))
        dept = str(item.get("department_current") or "").strip()
        m = re.match(r"^(?:청주시\s*)?(상당구|서원구|흥덕구|청원구)\b", dept)
        if not m:
            continue
        pred, is_conf = _find_regex_district(text)
        if pred == m.group(1):
            exact += 1
        elif is_conf:
            conflict += 1
        elif pred is not None:
            wrong += 1
        else:
            none_count += 1
    return {
        "exact": exact,
        "wrong": wrong,
        "conflict": conflict,
        "none": none_count,
        "ext_fp_count": len(ext_fp),
        "ext_fp_ids": ext_fp,
    }


def main() -> int:
    """112건 규칙 회귀와 공개 사례 5,015건 안전성 검사를 실행합니다.

    Returns:
        모두 통과하면 0, 실패가 있으면 1입니다.
    """
    failures = run_eval112_deterministic_checks()
    corpus = run_corpus_district_checks()
    print("112건 결정론적 규칙 회귀 실패:", len(failures))
    for msg in failures:
        print(" -", msg)
    print("공개 사례 5,015건 집계:", json.dumps(corpus, ensure_ascii=False))
    if failures or int(corpus["ext_fp_count"]) > 0 or int(corpus["wrong"]) > 17:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
