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
    return unicodedata.normalize("NFKC", text).replace("\u200b", "").strip()


def department_id(name: str) -> str:
    """내부 식별자. 정부의 부서 코드가 아니며 명칭 변경은 별도 이력 관리가 필요합니다."""
    return "cj_" + uuid.uuid5(DEPARTMENT_NAMESPACE, name).hex


def infer_district(name: str) -> str | None:
    for district in DISTRICTS:
        if name.startswith(district + " ") or name.startswith(district[:-1] + "보건소"):
            return district
    return None


def faq_text(record: dict) -> str:
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
    lines = [f"민원 제목: {record['title']}"]
    if record.get("summary", "").strip():
        lines.append(f"민원 요지: {record['summary']}")
    return normalize_text("\n".join(lines))


def load_sources(faq_path: Path = ROOT / "db/자주_묻는_민원.json",
                 cases_path: Path = ROOT / "db/공개_민원_사례.json") -> tuple[list[dict], list[dict], list[dict]]:
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
