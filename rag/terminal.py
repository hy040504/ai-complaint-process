"""검색 테스트 메뉴의 JSON 응답을 한국어 터미널 출력으로 구성합니다."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def safe_text(value: Any) -> str:
    """수집 문서의 터미널 제어 문자를 보이는 대체 문자로 바꿉니다.

    Args:
        value: 화면에 표시할 값입니다.

    Returns:
        줄바꿈·탭을 보존하고 다른 제어 문자를 제거한 문자열입니다.
    """
    return _CONTROL.sub("�", str(value))


def render(result: dict) -> str:
    """API 상태 또는 검색 응답을 원문·출처와 함께 표시합니다.

    Args:
        result: 상태 API 또는 검색 API의 JSON 객체입니다.

    Returns:
        검색 전용 계약과 문서 전체 근거를 보존하는 표시 문자열입니다.
    """
    lines = []
    if "counts" in result:
        lines.append(f"● 서비스 상태: {result.get('status', 'DB 직접 조회')}")
        labels = {"faq_knowledge": "FAQ", "routing_cases": "공개 사례",
                  "department_directory": "부서", "review_required": "부서 검토 필요",
                  "duties_unverified": "업무분장 미검증"}
        lines.extend(f"  {labels.get(key, key)}: {value:,}건" for key, value in result["counts"].items())
        config = result.get("configuration", {})
        lines.append(f"  임베딩: {config.get('embedding_model')} / {config.get('embedding_dimension')}차원")
        return safe_text("\n".join(lines))
    lines.append(f"● 검색 완료 · {result.get('elapsed_ms', '?')} ms")
    lines.append(f"  검색 전용: {result.get('retrieval_only')} / 판정: {result.get('decision')}")
    lines.append("  검색 점수는 자동 응답·이관 확률이 아닙니다.")
    for name, collection in result.get("results", {}).items():
        label = "FAQ 안내 근거" if name == "faq_knowledge" else "공개 사례 · 부서 근거"
        lines.extend(["", "━" * 56, f"  {label}", "━" * 56])
        hits = collection.get("hits", [])
        if not hits:
            lines.append("  검색 결과 없음 · 담당자 판단이 필요합니다.")
        for hit in hits:
            lines.append(f"\n[{hit['rank']}] {hit['title']}  (출처 ID: {hit['source_id']})")
            lines.append(f"출처: {hit['source_url']}")
            lines.append("점수: " + json.dumps(hit.get("scores", {}), ensure_ascii=False))
            department = hit.get("department")
            if department:
                lines.append(f"부서: {department.get('canonical_name')} / 업무 검증: {department.get('duty_status')}")
            if "routing_eligible" in hit:
                lines.append(f"부서 후보 사용 가능: {hit['routing_eligible']} (자동 이관 허가 아님)")
            # FAQ 조건을 잘라 표시하지 않고 API가 반환한 원본 근거를 전부 보여줍니다.
            lines.append("원본 근거:")
            lines.append(json.dumps(hit.get("evidence", {}), ensure_ascii=False, indent=2))
        candidates = collection.get("department_candidates", [])
        if candidates:
            lines.append("\n부서 후보 (업무분장·관할 확인 후 담당자 판단):")
            for candidate in candidates:
                lines.append(f"  • {candidate['canonical_name']} / 업무 검증: {candidate.get('duty_status')}")
    return safe_text("\n".join(lines))


def main():
    """메뉴가 저장한 응답 파일을 읽어 표시하고 잘못된 응답은 오류로 종료합니다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("response", type=Path)
    parser.add_argument("--raw", action="store_true")
    args = parser.parse_args()
    try:
        result = json.loads(args.response.read_text(encoding="utf-8"))
        if not isinstance(result, dict):
            raise ValueError("JSON 객체 응답이 필요합니다.")
        print(safe_text(json.dumps(result, ensure_ascii=False, indent=2)) if args.raw else render(result))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"응답 표시 실패: {exc}\n")


if __name__ == "__main__":
    main()
