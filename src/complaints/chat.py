"""시민 챗봇 응답에서 담당자 전용 내부 필드를 제거하고 안전하게 투영합니다.

`src.assist` 파이프라인의 결과에서 `staff_draft`(미게시 담당자 초안),
`sanitize`(특이민원 직원 보호 순화), `codex`(내부 프롬프트·토큰), `cases`(과거
공개 민원 원문), `model_raw`를 구조적으로 배제하고 시민에게 허용된 안내·
FAQ 출처·참고 부서명·감지 관할 구만 반환합니다.
"""

from __future__ import annotations

from typing import Any, Literal

from src.assist.district import normalize_district
from src.complaints.models import (
    CitizenChatResponse,
    CitizenFaqSource,
    District,
)

DEMO_CHAT_NOTICE = "이 안내는 청주톡톡 RAG + LLM 시연 응답이며, 청주시 공식 민원 접수·외부 부서 이관이 아닙니다."

_VALID_DISTRICTS: set[str] = {"상당구", "서원구", "흥덕구", "청원구"}

_HANDOFF_GUIDANCE: dict[str, str] = {
    "out_of_scope": (
        "말씀하신 내용은 청주시 관할 범위를 벗어나거나 별도 기관 확인이 필요한 사안으로 보여 "
        "바로 안내하지 않았어요. 청주시 관련 민원이라면 발생 위치를 보완해 민원으로 등록해 주세요."
    ),
    "llm_unavailable": (
        "현재 AI 안내 엔진 연결이 잠시 제한되어 바로 답변을 만들지 못했어요. "
        "아래 버튼으로 민원을 작성해 두시면 담당자가 확인 후 답변드릴 수 있어요."
    ),
    "faq_generation_failed": (
        "관련 공식 안내 자료(FAQ)를 찾았지만 일시적으로 AI 안내 문장 생성이 제한되었어요. "
        "아래 공식 출처를 참고하시거나 민원으로 작성해 주시면 담당자가 확인해 드려요."
    ),
    "search_failed": (
        "현재 검색 자료를 불러오지 못해 바로 안내해 드리기 어려워요. "
        "잠시 후 다시 물어보시거나 아래 버튼으로 민원을 작성해 주세요."
    ),
    "condition_unclear": (
        "질문하신 내용만으로는 적용 대상이나 세부 조건을 단정하기 어려워 담당자 확인이 필요해요. "
        "발생 위치와 구체적인 상황을 보완해 민원으로 작성해 주세요."
    ),
    "insufficient_evidence": (
        "저장된 공식 안내 자료(FAQ)에서 정확히 일치하는 근거를 찾지 못해 추측으로 답하지 않았어요. "
        "아래 버튼으로 민원을 남겨 주시면 담당자가 검토 후 안내해 드려요."
    ),
    "policy_blocked": (
        "인허가·처분·배상·긴급 안전 점검 등 담당자의 직접 확인과 판단이 필요한 요청이에요. "
        "아래 버튼으로 민원을 등록해 주시면 담당자가 검토할 수 있어요."
    ),
}


def _to_form_district(value: object) -> District:
    """추론된 관할 지역 문자열을 민원 작성 폼의 5종 선택지로 정규화합니다.

    Args:
        value: `AssistResponse.district` 값입니다.

    Returns:
        청주시 4개 구 중 하나 또는 `'모름'`입니다.
    """
    if isinstance(value, str) and value.strip():
        gu = normalize_district(value)
        if gu in _VALID_DISTRICTS:
            return gu  # type: ignore[return-value]
    return "모름"


def _extract_place_title(inferred_place: object) -> str | None:
    """추론된 장소 객체에서 시민에게 보여 줄 안전한 장소명만 뽑습니다.

    Args:
        inferred_place: 네이버 지도 장소 추적 사전 또는 None입니다.

    Returns:
        장소 제목 문자열 또는 None입니다.
    """
    if not isinstance(inferred_place, dict):
        return None
    title = str(inferred_place.get("title") or "").strip()
    return title or None


def _select_faq_sources(raw: dict[str, Any]) -> list[CitizenFaqSource]:
    """판정 근거에 연결된 공식 FAQ 출처만 안전하게 추출합니다.

    과거 공개 사례(`routing`)는 정책 안내 근거로 쓰지 않으므로 제외합니다.

    Args:
        raw: `run_web_assist`·`iter_web_assist`가 반환한 원시 결과 사전입니다.

    Returns:
        시민에게 표시할 공식 FAQ 출처 목록입니다.
    """
    faqs = raw.get("faq") or []
    if not isinstance(faqs, list):
        return []
    decision = raw.get("decision") or {}
    refs = decision.get("evidence_refs") or decision.get("evidenceRefs") or []
    cited_ids = {
        str(ref.get("source_id") or ref.get("sourceId") or "")
        for ref in refs
        if isinstance(ref, dict) and ref.get("corpus") == "faq"
    }
    selected = [
        hit
        for hit in faqs
        if isinstance(hit, dict)
        and str(hit.get("source_id") or hit.get("sourceId") or "") in cited_ids
    ]
    if not selected and raw.get("outcome") == "faq_answer":
        selected = [hit for hit in faqs[:2] if isinstance(hit, dict)]
    out: list[CitizenFaqSource] = []
    for hit in selected[:3]:
        source_id = str(hit.get("source_id") or hit.get("sourceId") or "").strip()
        title = str(hit.get("title") or "").strip()
        if not title:
            continue
        url = str(hit.get("source_url") or hit.get("sourceUrl") or "").strip() or None
        excerpt = str(hit.get("excerpt") or "").strip()[:180]
        out.append(
            CitizenFaqSource(
                source_id=source_id,
                title=title,
                source_url=url,
                excerpt=excerpt,
            )
        )
    return out


def _select_department_hints(raw: dict[str, Any]) -> list[str]:
    """현장 조치 민원에서 참고용 부서 명칭 후보만 중복 없이 추출합니다.

    Args:
        raw: 응대 파이프라인 원시 결과 사전입니다.

    Returns:
        최대 3개의 참고용 부서 명칭 목록입니다(공식 배정·자동 이관 아님).
    """
    if raw.get("outcome") != "department_suggestion":
        return []
    depts = raw.get("departments") or []
    if not isinstance(depts, list):
        return []
    chosen = [d for d in depts if isinstance(d, dict) and d.get("selected")]
    pool = chosen or [d for d in depts if isinstance(d, dict)]
    names: list[str] = []
    for item in pool:
        name = str(
            item.get("canonical_name") or item.get("canonicalName") or ""
        ).strip()
        if name and name not in names:
            names.append(name)
        if len(names) >= 3:
            break
    return names


def _build_citizen_message(
    outcome: Literal["faq_answer", "department_suggestion", "human_handoff"],
    reason_code: str,
    raw_answer: str,
    department_hints: list[str],
    district: District,
    place_title: str | None,
) -> str:
    """시민 말풍선에 바로 보여 줄 명확하고 안전한 안내 문장을 구성합니다.

    Args:
        outcome: 검증을 통과한 세 갈래 판정 결과입니다.
        reason_code: 판정 사유 코드입니다.
        raw_answer: 파이프라인이 생성한 원시 안내 문장입니다.
        department_hints: 참고용 부서 후보 목록입니다.
        district: 정규화된 관할 자치구 또는 `'모름'`입니다.
        place_title: 추론된 장소명 또는 None입니다.

    Returns:
        시민에게 표시할 자연어 한국어 안내 문장입니다.
    """
    if outcome == "faq_answer" and raw_answer:
        return raw_answer
    if outcome == "department_suggestion":
        loc_parts: list[str] = []
        if district != "모름":
            loc_parts.append(district)
        if place_title:
            loc_parts.append(place_title)
        loc_prefix = f"({' · '.join(loc_parts)} 기준) " if loc_parts else ""
        dept_clause = (
            f"유사 사례 기준 참고 부서 후보는 {', '.join(department_hints)}이며(공식 배정·자동 이관 아님), "
            if department_hints
            else ""
        )
        return (
            f"{loc_prefix}현장 확인이나 조치가 필요한 민원으로 보여 공식 민원 접수가 필요해요. "
            f"{dept_clause}아래 버튼으로 내용을 옮겨 발생 위치와 요청 사항을 확인한 뒤 등록해 주세요."
        )
    if reason_code in _HANDOFF_GUIDANCE:
        return _HANDOFF_GUIDANCE[reason_code]
    return (
        "정확한 안내를 위해 담당자의 확인이 필요한 문의예요. "
        "아래 버튼으로 민원을 작성해 주시면 검토 후 답변드릴 수 있어요."
    )


def project_citizen_chat(raw: dict[str, Any]) -> CitizenChatResponse:
    """응대 파이프라인 결과를 시민 챗봇 전용 계약으로 안전하게 투영합니다.

    미게시 담당자 초안(`staff_draft`), 직원 보호 순화(`sanitize`), 내부 프롬프트
    호출(`codex`), 과거 민원 사례(`cases`)는 결과 모델에 포함하지 않습니다.

    Args:
        raw: `run_web_assist` 또는 `iter_web_assist` `done` 결과 사전입니다.

    Returns:
        시민에게 안전하게 반환할 수 있는 `CitizenChatResponse` 모델입니다.
    """
    raw_outcome = str(raw.get("outcome") or "human_handoff")
    outcome: Literal["faq_answer", "department_suggestion", "human_handoff"]
    if raw_outcome == "faq_answer":
        outcome = "faq_answer"
    elif raw_outcome == "department_suggestion":
        outcome = "department_suggestion"
    else:
        outcome = "human_handoff"

    reason_code = str(
        raw.get("reason_code") or raw.get("reasonCode") or "condition_unclear"
    )
    district = _to_form_district(raw.get("district"))
    place_title = _extract_place_title(
        raw.get("inferred_place") or raw.get("inferredPlace")
    )
    faq_sources = _select_faq_sources(raw)
    department_hints = _select_department_hints(raw)
    raw_answer = str(raw.get("answer") or "").strip()
    answer = _build_citizen_message(
        outcome, reason_code, raw_answer, department_hints, district, place_title
    )
    return CitizenChatResponse(
        query=str(raw.get("query") or ""),
        outcome=outcome,
        reason_code=reason_code,
        answer=answer,
        handoff_required=outcome != "faq_answer",
        automatic_transfer=False,
        district=district,
        district_inferred=bool(
            raw.get("district_inferred") or raw.get("districtInferred")
        )
        and district != "모름",
        inferred_place_title=place_title,
        faq_sources=faq_sources,
        department_hints=department_hints,
        llm_provider=raw.get("llm_provider") or raw.get("llmProvider"),
        llm_configured=bool(raw.get("llm_configured") or raw.get("llmConfigured")),
        demo_notice=DEMO_CHAT_NOTICE,
    )
