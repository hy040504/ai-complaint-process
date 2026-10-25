"""원본을 검증하고 검색 본문과 현행 명칭 기반 부서 사전을 구성합니다."""
from __future__ import annotations

import json
import unicodedata
import uuid
from collections import defaultdict
from pathlib import Path

from PACKET.department_normalization import DEPARTMENT_ALIASES, ORGANIZATION_URL
from .config import DISTRICTS, ROOT, digest

DEPARTMENT_NAMESPACE = uuid.UUID("ea41f8fa-9802-45e2-b8a5-de987c872879")
STATUSES = {"current", "normalized", "renamed", "review_required"}


def normalize_text(text: str) -> str:
    """검색 본문을 NFKC로 정규화하고 숨은 공백과 바깥 공백을 제거합니다.

    Args:
        text: 정규화할 문자열입니다.

    Returns:
        원본 객체를 바꾸지 않고 정리한 문자열입니다.
    """
    return unicodedata.normalize("NFKC", text).replace("\u200b", "").strip()


def department_id(name: str) -> str:
    """부서명으로 내부 식별자를 만듭니다.

    정부 부서 코드와 구별하며 명칭 변경 시에는 별도 이력 관리가 필요합니다.

    Args:
        name: 정규화된 부서명입니다.

    Returns:
        고정 네임스페이스와 명칭으로 생성한 UUID 기반 식별자입니다.
    """
    return "cj_" + uuid.uuid5(DEPARTMENT_NAMESPACE, name).hex


def infer_district(name: str) -> str | None:
    """부서 이름에 드러난 구청·보건소의 구를 추출합니다.

    Args:
        name: 관할 표기를 확인할 부서명입니다.

    Returns:
        이름에서 추출한 구 이름 또는 None입니다. 실제 업무 관할을 확정하지 않습니다.
    """
    for district in DISTRICTS:
        if name.startswith(district + " ") or name.startswith(district[:-1] + "보건소"):
            return district
    return None


def faq_text(record: dict) -> str:
    """FAQ 한 항목의 분류·안내·적용 조건을 검색 본문으로 묶습니다.

    Args:
        record: 상세 안내를 포함한 원본 FAQ 항목입니다.

    Returns:
        대상·접수처·기간·주의사항을 함께 보존한 정규화 문자열입니다.
    """
    detail = record["detail"]
    lines = [f"업무명: {record['title']}",
             "분류: " + " / ".join(record.get(k, "") for k in ("major", "medium", "minor"))]
    for key, label in (("main_content", "상세 안내"), ("target", "대상"),
                       ("received_by", "접수처와 조건"), ("processing_period", "처리기간"),
                       ("warnings", "주의사항")):
        if detail.get(key):
            lines.append(f"{label}: {detail[key]}")
    return normalize_text("\n".join(lines))


def case_text(record: dict) -> str:
    # 과거 답변/부서명은 의미 검색에 섞지 않습니다. summary가 없으면 제목만 검색합니다.
    """공개 사례의 제목과 요지만 검색 본문으로 묶습니다.

    Args:
        record: 원본 공개 민원사례입니다.

    Returns:
        과거 답변과 부서명을 섞지 않은 본문입니다. 요지가 없으면 제목만 사용합니다.
    """
    lines = [f"민원 제목: {record['title']}"]
    if record.get("summary", "").strip():
        lines.append(f"민원 요지: {record['summary']}")
    return normalize_text("\n".join(lines))


def load_sources(faq_path: Path = ROOT / "db/자주_묻는_민원.json",
                 cases_path: Path = ROOT / "db/공개_민원_사례.json") -> tuple[list[dict], list[dict], list[dict]]:
    """두 원본을 검증하고 검색 문서와 부서 디렉터리를 구성합니다.

    Args:
        faq_path: 분야별 FAQ JSON 경로입니다.
        cases_path: 공개 민원사례 JSON 배열 경로입니다.

    Returns:
        검색 문서 목록, 부서 디렉터리 목록, 원본 사례 목록의 튜플입니다.

    Raises:
        ValueError: 빈 원본·형식 오류·출처 ID 중복·부서 상태 불일치가 있으면 발생합니다.
        OSError: 원본 파일을 읽을 수 없는 경우 발생합니다.
    """
    faq_raw = json.loads(faq_path.read_text(encoding="utf-8"))
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    if not isinstance(faq_raw, dict) or not isinstance(cases, list):
        raise ValueError("FAQ는 분야별 객체, 공개 사례는 배열이어야 합니다.")
    faqs = []
    for category, records in faq_raw.items():
        for record in records:
            faqs.append({"category": category, "payload": record})
    if not faqs or not cases:
        raise ValueError("빈 원본으로 기존 색인을 덮어쓸 수 없습니다.")
    for records in ([r["payload"] for r in faqs], cases):
        seen = set()
        for r in records:
            sid = r.get("source_id")
            if not isinstance(sid, str) or not sid or sid in seen:
                raise ValueError(f"source_id 누락/중복: {sid!r}")
            seen.add(sid)
            if not r.get("title") or not r.get("source_url") or not r.get("retrieved_at"):
                raise ValueError(f"제목/출처/수집 시각 누락: {sid}")
    for r in cases:
        if r.get("department_status") not in STATUSES:
            raise ValueError(f"부서 상태 확인 필요: {r['source_id']}")
        if (r["department_status"] == "review_required") != (r.get("department_current") is None):
            raise ValueError(f"현재 부서와 검토 상태 불일치: {r['source_id']}")
    directories = build_directory(cases)
    docs = []
    for item in faqs:
        r = item["payload"]
        docs.append({"corpus": "faq", "source_id": r["source_id"], "title": r["title"],
                     "category": item["category"], "payload": r, "search_text": faq_text(r)})
    for r in cases:
        name = r.get("department_current")
        docs.append({"corpus": "routing", "source_id": r["source_id"], "title": r["title"],
                     "payload": r, "search_text": case_text(r),
                     "department_id": department_id(name) if name else None,
                     "district": infer_district(name) if name else None,
                     "routing_eligible": bool(name) and r["department_status"] != "review_required",
                     "summary_missing": not bool(r.get("summary", "").strip())})
    for doc in docs:
        doc["content_hash"] = digest({"payload": doc["payload"], "category": doc.get("category")})
        doc["embedding_hash"] = digest(doc["search_text"])
    return docs, directories, cases


def build_directory(cases: list[dict]) -> list[dict]:
    """현행 부서가 확인된 사례에서 이름·별칭·검증 상태를 모읍니다.

    Args:
        cases: 부서 정규화 상태를 포함한 공개 민원사례 목록입니다.

    Returns:
        이름순 부서 목록입니다. 공식 업무분장은 미검증으로 두고 관할은 이름에서 추출합니다.
    """
    groups = defaultdict(list)
    for r in cases:
        if r.get("department_current") and r["department_status"] != "review_required":
            groups[r["department_current"]].append(r)
    result = []
    for name, records in sorted(groups.items()):
        aliases = {r[key] for r in records for key in ("department", "department_original") if r.get(key)}
        aliases.update(old for old, new in DEPARTMENT_ALIASES.items() if new == name)
        aliases.discard(name)
        district = infer_district(name)
        result.append({
            "department_id": department_id(name), "canonical_name": name, "aliases": sorted(aliases),
            "district": district,
            "jurisdiction": {"city": "청주시", "district": district, "coverage": "needs_verification"},
            "jurisdiction_status": "inferred_from_name",
            "duty_description": None, "duty_status": "unverified", "duty_source_urls": [],
            "name_checked_on": min(r["department_checked_on"] for r in records),
            "name_source_urls": [ORGANIZATION_URL],
            "observed_case_titles": list(dict.fromkeys(r["title"] for r in records))[:5],
            "automatic_routing_ready": False,
        })
    return result
