"""검색 근거 위의 LLM 판정과 코드 정책 검사로 시연 응대를 만듭니다."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any, Callable

SCOPES = ("in_scope", "out_of_scope", "uncertain")
INTENTS = ("information", "action", "mixed", "unclear")
OUTCOMES = ("faq_answer", "department_suggestion", "human_handoff")
CORPORA = ("faq", "routing")
REASON_CODES = (
    "insufficient_evidence",
    "out_of_scope",
    "action_required",
    "mixed_request",
    "department_unverified",
    "condition_unclear",
    "invalid_model_output",
    "policy_rejected",
    "llm_unavailable",
    "search_failed",
    "faq_generation_failed",
    "ok",
)
HANDOFF_REASONS = {
    "insufficient_evidence": "현재 검색 근거만으로 안내를 확정하기 어렵습니다. 담당자 검토가 필요합니다.",
    "out_of_scope": "현재 FAQ·공개 사례 범위에서 확정하기 어렵습니다. 담당자 검토가 필요합니다.",
    "action_required": "현장 조치가 필요한 요청으로 보입니다. 담당자가 부서 후보와 함께 검토합니다.",
    "mixed_request": "안내와 조치가 섞여 있어 일부 FAQ만으로 전체를 종결하지 않습니다. 담당자 검토가 필요합니다.",
    "department_unverified": "부서 후보의 업무분장·관할이 확인되지 않아 담당자 검토가 필요합니다.",
    "condition_unclear": "적용 조건이 충분하지 않습니다. 담당자 검토가 필요합니다.",
    "invalid_model_output": "판정 결과를 코드에서 검증하지 못해 담당자 검토로 연결합니다.",
    "policy_rejected": "모델이 가리킨 근거 또는 부서가 검색 결과와 맞지 않아 담당자 검토로 연결합니다.",
    "llm_unavailable": "언어 모델이 설정되지 않았거나 호출에 실패했습니다. 검색 근거만 표시하고 담당자 검토로 연결합니다.",
    "search_failed": "검색에 실패했습니다. 담당자 검토가 필요합니다.",
    "faq_generation_failed": "FAQ 답변 생성·검사를 통과하지 못해 담당자 검토로 연결합니다.",
    "ok": "검색 근거를 바탕으로 안내합니다.",
}
PROGRESS_LABELS = {
    "read": "민원 내용을 읽고 있어요",
    "search": "저장된 안내와 사례를 찾고 있어요",
    "review": "찾은 자료를 살펴보고 있어요",
    "write": "안내문을 준비하고 있어요",
}
EXAMPLES = [
    {
        "id": "faq",
        "title": "FAQ로 안내 가능한 정보 문의",
        "query": "대형폐기물 배출 방법을 알고 싶어요.",
        "district": None,
    },
    {
        "id": "action",
        "title": "현장 조치가 필요한 민원",
        "query": "우리집 앞 가로등이 밤새 깜빡거려 수리를 요청합니다.",
        "district": "흥덕구",
    },
    {
        "id": "routing",
        "title": "유사 사례로 부서 후보가 나오는 민원",
        "query": "711번 버스가 정류장에 서지 않고 지나갔습니다.",
        "district": None,
    },
    {
        "id": "handoff",
        "title": "근거가 부족해 담당자 검토로 가는 민원",
        "query": "다른 시 소속 시설의 이용 요금을 청주시가 환불해 주세요.",
        "district": None,
    },
    {
        "id": "district",
        "title": "관할 구를 명시한 민원",
        "query": "아파트 앞 불법 주정차로 통행이 불편합니다. 단속을 요청합니다.",
        "district": "상당구",
    },
]
_JSON_BLOCK = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_FIRST_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def llm_settings() -> dict[str, str | None]:
    """호출에 사용할 외부 LLM 주소·모델·인증 방식을 읽습니다.

    Returns:
        url·model·token·auth 키를 담은 설정입니다. 토큰이 없으면 token은 None입니다.
    """
    public = os.environ.get("COMPLAINT_LLM_TOKEN") or os.environ.get("PUBLIC_LLM_TOKEN")
    xai = os.environ.get("XAI_API_KEY")
    if public:
        return {
            "url": os.environ.get(
                "COMPLAINT_LLM_URL",
                "https://llm.mib.dpdns.org/v1/chat/completions",
            ),
            "model": os.environ.get(
                "COMPLAINT_LLM_MODEL",
                "0bserverx__Qwen3.8-27B-Heretic-Abliterated-Uncensored-GGUF",
            ),
            "token": public,
            "auth": "token",
        }
    if xai:
        return {
            "url": os.environ.get(
                "COMPLAINT_LLM_URL", "https://api.x.ai/v1/chat/completions"
            ),
            "model": os.environ.get("COMPLAINT_LLM_MODEL", "grok-4-fast"),
            "token": xai,
            "auth": "bearer",
        }
    return {
        "url": os.environ.get("COMPLAINT_LLM_URL"),
        "model": os.environ.get("COMPLAINT_LLM_MODEL"),
        "token": None,
        "auth": "token",
    }


def llm_configured() -> bool:
    """응대에 사용할 LLM 토큰이 환경에 있는지 반환합니다."""
    return llm_settings()["token"] is not None


def search_api_url() -> str:
    """검색 API 기본 주소를 반환합니다."""
    return os.environ.get("RAG_API_URL", "http://127.0.0.1:8007").rstrip("/")


def http_json(
    url: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 180,
) -> Any:
    """JSON HTTP 요청을 보내고 본문을 해석합니다.

    Args:
        url: 호출 주소입니다.
        payload: POST 본문입니다. None이면 GET입니다.
        headers: 추가 헤더입니다.
        timeout: 초 단위 제한 시간입니다.

    Returns:
        JSON으로 해석한 응답입니다.

    Raises:
        ValueError: HTTP 오류나 연결 실패가 발생한 경우 발생합니다.
    """
    data = (
        json.dumps(payload, ensure_ascii=False).encode()
        if payload is not None
        else None
    )
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise ValueError(f"API {exc.code}: {message}") from None
    except urllib.error.URLError as exc:
        raise ValueError(f"연결 실패 ({url}): {exc.reason}") from None


def search_via_api(
    query: str,
    district: str | None = None,
    limit: int = 5,
    rerank: bool = True,
) -> dict[str, Any]:
    """실행 중인 검색 API에서 FAQ와 사례 근거를 가져옵니다.

    Args:
        query: 한국어 민원 원문입니다.
        district: 명시한 관할 구입니다.
        limit: 컬렉션별 반환 수입니다.
        rerank: 재정렬 여부입니다.

    Returns:
        검색 API의 JSON 객체입니다.
    """
    return http_json(
        search_api_url() + "/search",
        {
            "query": query,
            "collection": "both",
            "limit": limit,
            "district": district,
            "rerank": rerank,
        },
    )


def complete_chat(system: str, user: str) -> str:
    """설정된 OpenAI 호환 엔드포인트로 한 번의 채팅 완성을 요청합니다.

    Args:
        system: 시스템 지시입니다.
        user: 사용자 본문입니다.

    Returns:
        모델이 반환한 메시지 문자열입니다.

    Raises:
        ValueError: 토큰이 없거나 응답 형식이 잘못된 경우 발생합니다.
    """
    settings = llm_settings()
    if not settings["token"] or not settings["url"] or not settings["model"]:
        raise ValueError("LLM 토큰·주소·모델이 설정되지 않았습니다.")
    headers = {"User-Agent": "cheongju-assist/0.1"}
    if settings["auth"] == "bearer":
        headers["Authorization"] = "Bearer " + str(settings["token"])
    else:
        headers["token"] = str(settings["token"])
    body = http_json(
        str(settings["url"]),
        {
            "model": settings["model"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "max_tokens": 1200,
            "stream": False,
        },
        headers=headers,
    )
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("LLM 응답에 메시지 본문이 없습니다.") from exc
    if not isinstance(content, str) or not content.strip():
        raise ValueError("LLM 응답 본문이 비어 있습니다.")
    return content


def parse_json_object(text: str) -> dict[str, Any]:
    """모델 출력에서 첫 JSON 객체를 꺼냅니다.

    Args:
        text: 원문 응답입니다.

    Returns:
        객체로 해석한 값입니다.

    Raises:
        ValueError: JSON 객체를 찾지 못한 경우 발생합니다.
    """
    block = _JSON_BLOCK.search(text)
    raw = block.group(1) if block else None
    if raw is None:
        match = _FIRST_OBJECT.search(text)
        raw = match.group(0) if match else None
    if not raw:
        raise ValueError("JSON 객체를 찾지 못했습니다.")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("JSON 객체가 필요합니다.")
    return value


def faq_hits(search: dict[str, Any]) -> list[dict[str, Any]]:
    """검색 응답의 FAQ 후보를 반환합니다."""
    return list(
        (search.get("results") or {}).get("faq_knowledge", {}).get("hits") or []
    )


def case_hits(search: dict[str, Any]) -> list[dict[str, Any]]:
    """검색 응답의 공개 사례 후보를 반환합니다."""
    return list(
        (search.get("results") or {}).get("routing_cases", {}).get("hits") or []
    )


def department_candidates(search: dict[str, Any]) -> list[dict[str, Any]]:
    """routing_eligible인 부서 후보만 반환합니다."""
    return list(
        (search.get("results") or {})
        .get("routing_cases", {})
        .get("department_candidates")
        or []
    )


def hit_excerpt(hit: dict[str, Any]) -> str:
    """FAQ 조건 또는 사례 요지를 잘라 표시용 발췌를 만듭니다.

    Args:
        hit: 검색 히트입니다.

    Returns:
        대상·기간·주의 또는 요지를 포함한 문자열입니다.
    """
    evidence = hit.get("evidence") or {}
    detail = evidence.get("detail") if isinstance(evidence, dict) else None
    if isinstance(detail, dict):
        parts = [
            detail.get("target"),
            detail.get("processing_period"),
            detail.get("received_by"),
            detail.get("main_content"),
            detail.get("warnings"),
        ]
        return "\n".join(str(part) for part in parts if part)[:1200]
    summary = evidence.get("summary") if isinstance(evidence, dict) else None
    return str(summary or hit.get("title") or "")[:1200]


def _compact_faq(hit: dict[str, Any]) -> dict[str, Any]:
    """판정 모델에 넘길 FAQ 후보만 남깁니다.

    Args:
        hit: 검색 FAQ 히트입니다.

    Returns:
        source_id와 조건 원문을 담은 축소 객체입니다.
    """
    evidence = hit.get("evidence") or {}
    detail = evidence.get("detail") if isinstance(evidence, dict) else {}
    return {
        "corpus": "faq",
        "source_id": hit["source_id"],
        "title": hit.get("title"),
        "source_url": hit.get("source_url"),
        "detail": detail if isinstance(detail, dict) else {},
    }


def _compact_case(hit: dict[str, Any]) -> dict[str, Any]:
    """판정 모델에 넘길 공개 사례 후보만 남깁니다.

    Args:
        hit: 검색 사례 히트입니다.

    Returns:
        요지와 부서 검증 상태를 담은 축소 객체입니다.
    """
    evidence = hit.get("evidence") or {}
    department = hit.get("department") or {}
    return {
        "corpus": "routing",
        "source_id": hit["source_id"],
        "title": hit.get("title"),
        "source_url": hit.get("source_url"),
        "summary": evidence.get("summary") if isinstance(evidence, dict) else "",
        "routing_eligible": hit.get("routing_eligible"),
        "department_status": hit.get("department_status"),
        "department_id": department.get("department_id"),
        "department_name": department.get("canonical_name"),
        "duty_status": department.get("duty_status"),
    }


def evidence_index(search: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """(컬렉션, source_id)로 검색 히트를 찾습니다."""
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for hit in faq_hits(search):
        index[("faq", str(hit["source_id"]))] = hit
    for hit in case_hits(search):
        index[("routing", str(hit["source_id"]))] = hit
    return index


def decision_prompt(query: str, district: str | None, search: dict[str, Any]) -> str:
    """판정 JSON만 요청하는 사용자 본문을 구성합니다."""
    payload = {
        "query": query,
        "district": district,
        "faq_candidates": [_compact_faq(hit) for hit in faq_hits(search)],
        "case_candidates": [_compact_case(hit) for hit in case_hits(search)],
        "department_candidates": [
            {
                "department_id": item.get("department_id"),
                "canonical_name": item.get("canonical_name"),
                "district": item.get("district"),
                "duty_status": item.get("duty_status"),
                "jurisdiction_status": item.get("jurisdiction_status"),
                "supporting_case_ids": [
                    case.get("source_id") for case in item.get("supporting_cases") or []
                ],
            }
            for item in department_candidates(search)
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


DECISION_SYSTEM = """당신은 청주 민원 검색 근거를 읽는 판정기입니다. 시민 답변 문장을 쓰지 말고 JSON 객체만 반환하세요.
규칙은 다음과 같습니다.
- FAQ 후보는 안내 근거입니다. 공개 사례의 과거 답변은 현재 정책이 아닙니다.
- 정보 문의이고 선택한 FAQ의 대상·기간·주의가 요청을 충분히 설명하면 outcome은 faq_answer입니다.
- 단속·보수·수거 등 실제 조치 요청이면 faq_answer를 쓰지 않습니다. 유효한 부서 후보가 있으면 department_suggestion, 없으면 human_handoff입니다.
- 안내와 조치가 섞이면 mixed이며 outcome은 human_handoff입니다.
- evidence_refs의 corpus는 faq 또는 routing이고 source_id는 입력 후보에 있는 값만 사용합니다.
- department_ids는 department_candidates의 department_id만 사용합니다.
- 추측한 출처·부서·연락처를 만들지 않습니다.
형식:
{"scope":"in_scope|out_of_scope|uncertain","intent":"information|action|mixed|unclear","outcome":"faq_answer|department_suggestion|human_handoff","reason_code":"ok|insufficient_evidence|out_of_scope|action_required|mixed_request|department_unverified|condition_unclear","evidence_refs":[{"corpus":"faq","source_id":"..."}],"department_ids":[]}
"""

ANSWER_SYSTEM = """선택한 FAQ 원문만 사용해 한국어 안내를 작성합니다. 대상·접수 방법·처리기간·주의사항을 빼지 마세요.
원문에 없는 전화번호·부서·기한·조건을 추가하지 마세요. 과거 민원 사례 답변을 섞지 마세요.
공식 접수 완료처럼 말하지 마세요. 평문만 반환하세요.
"""


def empty_decision(reason: str) -> dict[str, Any]:
    """검증 실패 시 담당자 검토 판정을 만듭니다."""
    return {
        "scope": "uncertain",
        "intent": "unclear",
        "outcome": "human_handoff",
        "reason_code": reason if reason in REASON_CODES else "invalid_model_output",
        "evidence_refs": [],
        "department_ids": [],
    }


def validate_decision(
    raw: dict[str, Any], search: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """모델 판정을 검색 근거·부서 후보와 대조합니다.

    Args:
        raw: 모델이 반환한 객체입니다.
        search: 검색 API 응답입니다.

    Returns:
        교정된 판정과 정책 실패 사유 목록입니다.
    """
    failures: list[str] = []
    index = evidence_index(search)
    departments = {
        str(item.get("department_id")): item for item in department_candidates(search)
    }
    scope = raw.get("scope") if raw.get("scope") in SCOPES else None
    intent = raw.get("intent") if raw.get("intent") in INTENTS else None
    outcome = raw.get("outcome") if raw.get("outcome") in OUTCOMES else None
    reason = raw.get("reason_code") if raw.get("reason_code") in REASON_CODES else "ok"
    if scope is None:
        failures.append("scope 값이 허용 목록에 없습니다.")
        scope = "uncertain"
    if intent is None:
        failures.append("intent 값이 허용 목록에 없습니다.")
        intent = "unclear"
    if outcome is None:
        failures.append("outcome 값이 허용 목록에 없습니다.")
        outcome = "human_handoff"

    refs: list[dict[str, str]] = []
    for item in raw.get("evidence_refs") or []:
        if not isinstance(item, dict):
            failures.append("evidence_refs 항목 형식이 잘못되었습니다.")
            continue
        corpus = item.get("corpus")
        source_id = str(item.get("source_id") or "")
        if corpus not in CORPORA or not source_id:
            failures.append("근거 키 corpus/source_id가 올바르지 않습니다.")
            continue
        if (corpus, source_id) not in index:
            failures.append(f"검색에 없는 근거입니다: {corpus}/{source_id}")
            continue
        refs.append({"corpus": corpus, "source_id": source_id})

    dept_ids: list[str] = []
    for item in raw.get("department_ids") or []:
        key = str(item)
        if key not in departments:
            failures.append(f"유효 후보가 아닌 부서입니다: {key}")
            continue
        dept_ids.append(key)

    if intent == "mixed":
        outcome = "human_handoff"
        reason = "mixed_request"
        failures.append("복합 요청은 담당자 검토로 연결합니다.")
    if scope in ("out_of_scope", "uncertain") and outcome == "faq_answer":
        outcome = "human_handoff"
        reason = "out_of_scope" if scope == "out_of_scope" else "insufficient_evidence"
        failures.append("범위 밖·불확실 판정은 FAQ 자동 안내를 허용하지 않습니다.")
    if intent == "action" and outcome == "faq_answer":
        outcome = "department_suggestion" if dept_ids else "human_handoff"
        reason = "action_required"
        failures.append("실제 조치 요청을 FAQ 안내만으로 종결하지 않습니다.")
    if outcome == "faq_answer":
        if intent != "information":
            outcome = "human_handoff"
            reason = "policy_rejected"
            failures.append("FAQ 안내는 information 의도에만 허용합니다.")
        elif not any(ref["corpus"] == "faq" for ref in refs):
            outcome = "human_handoff"
            reason = "insufficient_evidence"
            failures.append("FAQ 안내에는 FAQ 근거가 필요합니다.")
    if outcome == "department_suggestion" and not dept_ids:
        outcome = "human_handoff"
        reason = "department_unverified"
        failures.append("부서 추천에는 유효한 부서 후보가 필요합니다.")
    if outcome == "human_handoff" and reason == "ok":
        reason = "insufficient_evidence"

    decision = {
        "scope": scope,
        "intent": intent,
        "outcome": outcome,
        "reason_code": reason,
        "evidence_refs": refs,
        "department_ids": dept_ids,
    }
    return decision, failures


def citizen_answer(
    decision: dict[str, Any],
    search: dict[str, Any],
    generated: str | None,
    departments: list[dict[str, Any]] | None = None,
) -> str | None:
    """시민에게 보여줄 문장을 판정 갈래에 맞게 고릅니다.

    Args:
        decision: 정책 검사를 통과한 판정입니다.
        search: 검색 응답입니다.
        generated: FAQ 생성 결과입니다.
        departments: 이미 구한 부서 후보입니다. 생략하면 검색 응답에서 다시 읽습니다.

    Returns:
        안내 문장 또는 None입니다. 부서 추천·인계는 템플릿입니다.
    """
    outcome = decision["outcome"]
    if outcome == "faq_answer":
        return generated
    if outcome == "department_suggestion":
        names = []
        by_id = {
            str(item.get("department_id")): item
            for item in (
                departments
                if departments is not None
                else department_candidates(search)
            )
        }
        for dept_id in decision["department_ids"]:
            item = by_id.get(dept_id) or {}
            label = item.get("canonical_name") or dept_id
            duty = item.get("duty_status") or "unknown"
            names.append(f"- {label} (업무분장: {duty}, 자동 이관 아님)")
        return (
            "유사한 공개 사례를 기준으로 담당 부서 후보를 안내합니다. "
            "공식 접수·이관이 아니며 담당자 확인이 필요합니다.\n" + "\n".join(names)
        )
    return HANDOFF_REASONS.get(
        decision["reason_code"], HANDOFF_REASONS["insufficient_evidence"]
    )


def _stage(name: str, started: float, ok: bool = True) -> dict[str, Any]:
    """단계 이름과 경과 시간을 기록합니다.

    Args:
        name: 단계 표시 이름입니다.
        started: `time.perf_counter()`로 잰 시작 시각입니다.
        ok: 단계 성공 여부입니다.

    Returns:
        이름·경과 밀리초·성공 여부를 담은 기록입니다.
    """
    return {
        "name": name,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "ok": ok,
    }


_USE_ENV_LLM = object()


def _llm_enabled(llm_fn: object) -> bool:
    """이번 호출이 언어 모델을 사용하는지 반환합니다.

    Args:
        llm_fn: 환경 설정 사용 표시, 직접 함수, 또는 비활성화 `None`입니다.

    Returns:
        모델을 호출할 수 있으면 True입니다.
    """
    if llm_fn is _USE_ENV_LLM:
        return llm_configured()
    return callable(llm_fn)


def _progress(key: str) -> dict[str, str]:
    """화면에 보여줄 짧은 진행 안내를 만듭니다.

    Args:
        key: `PROGRESS_LABELS`의 키입니다.

    Returns:
        사건 형식으로 감싼 짧은 안내입니다.
    """
    return {"type": "progress", "key": key, "label": PROGRESS_LABELS[key]}


def iter_assist(
    query: str,
    district: str | None = None,
    *,
    limit: int = 5,
    rerank: bool = True,
    search_fn: Callable[..., dict[str, Any]] | None = None,
    llm_fn: Callable[[str, str], str] | object | None = _USE_ENV_LLM,
) -> Iterator[dict[str, Any]]:
    """응대 진행 안내와 최종 결과를 순서대로 넘깁니다.

    Args:
        query: 한국어 민원 원문입니다.
        district: 명시한 관할 구입니다.
        limit: 컬렉션별 검색 수입니다.
        rerank: 재정렬 여부입니다.
        search_fn: 검색 함수입니다. 생략하면 검색 API를 호출합니다.
        llm_fn: (system, user) → 텍스트 함수입니다. 생략하면 환경 설정의 LLM을 쓰고, None이면 호출하지 않습니다.

    Yields:
        `progress` 사건 또는 최종 `done` 결과입니다.
    """
    stages: list[dict[str, Any]] = []
    text = (query or "").strip()
    yield _progress("read")
    if not text or len(text) > 2000:
        decision = empty_decision("invalid_model_output")
        decision["reason_code"] = "condition_unclear"
        yield {
            "type": "done",
            "result": _result(
                query=text,
                district=district,
                search={},
                decision=decision,
                failures=["민원은 1~2000자로 입력해 주세요."],
                generated=None,
                stages=stages,
                llm_on=_llm_enabled(llm_fn),
            ),
        }
        return

    search: dict[str, Any] = {}
    yield _progress("search")
    started = time.perf_counter()
    try:
        fetch = search_fn or search_via_api
        search = fetch(text, district, limit, rerank)
        if (
            search.get("retrieval_only") is not True
            or search.get("decision") != "requires_gate"
        ):
            raise ValueError(
                "검색 응답이 retrieval_only/requires_gate 계약을 지키지 않습니다."
            )
        stages.append(_stage("검색", started, True))
    except (ValueError, OSError, TypeError, KeyError) as exc:
        stages.append(_stage("검색", started, False))
        decision = empty_decision("search_failed")
        yield {
            "type": "done",
            "result": _result(
                query=text,
                district=district,
                search={},
                decision=decision,
                failures=[str(exc)],
                generated=None,
                stages=stages,
                llm_on=False,
            ),
        }
        return

    yield _progress("review")
    if llm_fn is _USE_ENV_LLM:
        chat: Callable[[str, str], str] | None = (
            complete_chat if llm_configured() else None
        )
    else:
        chat = llm_fn if callable(llm_fn) else None
    raw_decision: dict[str, Any] | None = None
    started = time.perf_counter()
    if chat is None:
        stages.append(_stage("판정", started, False))
        decision = empty_decision("llm_unavailable")
        failures = [
            "COMPLAINT_LLM_TOKEN 또는 PUBLIC_LLM_TOKEN 또는 XAI_API_KEY가 필요합니다."
        ]
    else:
        try:
            raw_decision = parse_json_object(
                chat(DECISION_SYSTEM, decision_prompt(text, district, search))
            )
            stages.append(_stage("판정", started, True))
            checked = time.perf_counter()
            decision, failures = validate_decision(raw_decision, search)
            stages.append(_stage("정책검사", checked, not failures))
        except (ValueError, json.JSONDecodeError, OSError) as exc:
            stages.append(_stage("판정", started, False))
            decision = empty_decision("invalid_model_output")
            failures = [str(exc)]

    generated: str | None = None
    if decision["outcome"] == "faq_answer" and chat is not None:
        yield _progress("write")
        started = time.perf_counter()
        selected = [
            _compact_faq(evidence_index(search)[("faq", ref["source_id"])])
            for ref in decision["evidence_refs"]
            if ref["corpus"] == "faq"
        ]
        try:
            generated = chat(
                ANSWER_SYSTEM,
                json.dumps(
                    {"query": text, "faq": selected}, ensure_ascii=False, indent=2
                ),
            ).strip()
            if len(generated) < 20:
                raise ValueError("FAQ 답변이 너무 짧습니다.")
            stages.append(_stage("답변생성", started, True))
            stages.append(_stage("검증", time.perf_counter(), True))
        except (ValueError, OSError) as exc:
            stages.append(_stage("답변생성", started, False))
            decision["outcome"] = "human_handoff"
            decision["reason_code"] = "faq_generation_failed"
            failures.append(str(exc))
            generated = None

    yield {
        "type": "done",
        "result": _result(
            query=text,
            district=district,
            search=search,
            decision=decision,
            failures=failures,
            generated=generated,
            stages=stages,
            llm_on=chat is not None,
            raw_decision=raw_decision,
        ),
    }


def run_assist(
    query: str,
    district: str | None = None,
    *,
    limit: int = 5,
    rerank: bool = True,
    search_fn: Callable[..., dict[str, Any]] | None = None,
    llm_fn: Callable[[str, str], str] | object | None = _USE_ENV_LLM,
    on_progress: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    """검색 → 판정 → 정책 검사 → 조건부 FAQ 생성 순서로 응대 결과를 만듭니다.

    Args:
        query: 한국어 민원 원문입니다.
        district: 명시한 관할 구입니다.
        limit: 컬렉션별 검색 수입니다.
        rerank: 재정렬 여부입니다.
        search_fn: 검색 함수입니다. 생략하면 검색 API를 호출합니다.
        llm_fn: (system, user) → 텍스트 함수입니다. 생략하면 환경 설정의 LLM을 쓰고, None이면 호출하지 않습니다.
        on_progress: 짧은 진행 안내를 받을 콜백입니다. `(key, label)`입니다.

    Returns:
        세 갈래 결과·근거·정책 실패·단계를 담은 딕셔너리입니다.
    """
    result: dict[str, Any] | None = None
    for event in iter_assist(
        query,
        district,
        limit=limit,
        rerank=rerank,
        search_fn=search_fn,
        llm_fn=llm_fn,
    ):
        if event["type"] == "progress":
            if on_progress:
                on_progress(event["key"], event["label"])
        else:
            result = event["result"]
    if result is None:
        raise RuntimeError("응대 파이프라인이 결과를 만들지 않았습니다.")
    return result


def _public_hit(hit: dict[str, Any], corpus: str) -> dict[str, Any]:
    """검사기·CLI에 보여줄 근거 한 건을 만듭니다.

    Args:
        hit: 검색 히트입니다.
        corpus: faq 또는 routing입니다.

    Returns:
        순위·제목·발췌·부서 이름을 담은 표시용 객체입니다.
    """
    department = hit.get("department") or {}
    return {
        "rank": hit.get("rank"),
        "source_id": hit.get("source_id"),
        "title": hit.get("title"),
        "source_url": hit.get("source_url"),
        "excerpt": hit_excerpt(hit),
        "corpus": corpus,
        "routing_eligible": hit.get("routing_eligible"),
        "department_name": department.get("canonical_name"),
        "department_status": hit.get("department_status"),
    }


def _result(
    query: str,
    district: str | None,
    search: dict[str, Any],
    decision: dict[str, Any],
    failures: list[str],
    generated: str | None,
    stages: list[dict[str, Any]],
    llm_on: bool,
    raw_decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """세 갈래 응대와 근거·단계를 한 객체로 묶습니다.

    Args:
        query: 민원 원문입니다.
        district: 명시한 관할 구입니다.
        search: 검색 API 응답입니다.
        decision: 정책 검사를 거친 판정입니다.
        failures: 정책 실패 문구입니다.
        generated: FAQ 생성 문장입니다.
        stages: 단계 기록입니다.
        llm_on: 이번 호출에서 모델을 사용했는지입니다.
        raw_decision: 검사 전 모델 출력입니다.

    Returns:
        API·CLI가 공유하는 응대 결과입니다.
    """
    departments = department_candidates(search)
    selected = set(decision["department_ids"])
    answer = citizen_answer(decision, search, generated, departments)
    return {
        "query": query,
        "district": district,
        "outcome": decision["outcome"],
        "reason_code": decision["reason_code"],
        "answer": answer,
        "handoff_required": decision["outcome"] != "faq_answer",
        "automatic_transfer": False,
        "faq": [_public_hit(hit, "faq") for hit in faq_hits(search)],
        "cases": [_public_hit(hit, "routing") for hit in case_hits(search)],
        "departments": [
            {
                "department_id": item.get("department_id"),
                "canonical_name": item.get("canonical_name"),
                "district": item.get("district"),
                "duty_status": item.get("duty_status"),
                "jurisdiction_status": item.get("jurisdiction_status"),
                "supporting_cases": item.get("supporting_cases") or [],
                "selected": str(item.get("department_id")) in selected,
                "automatic_transfer": False,
            }
            for item in departments
        ],
        "decision": {**decision, "model_raw": raw_decision},
        "policy_failures": failures,
        "stages": stages,
        "llm_configured": llm_on,
        "retrieval": {
            "retrieval_only": search.get("retrieval_only", True),
            "decision": search.get("decision", "requires_gate"),
            "elapsed_ms": search.get("elapsed_ms"),
            "pipeline": search.get("pipeline"),
        },
    }


def render_assist(result: dict[str, Any]) -> str:
    """응대 결과를 터미널에 읽기 쉽게 표시합니다."""
    lines = [
        f"● 응대 결과 · {result.get('outcome')} / 사유 {result.get('reason_code')}",
        f"  자동 이관: {result.get('automatic_transfer')} / 담당자 검토: {result.get('handoff_required')}",
        f"  LLM 설정: {result.get('llm_configured')}",
        "",
        "시민 안내:",
        str(result.get("answer") or "(없음)"),
        "",
        "FAQ 근거:",
    ]
    for hit in result.get("faq") or []:
        lines.append(
            f"  [{hit.get('rank')}] {hit.get('title')} ({hit.get('source_id')})"
        )
        lines.append(f"      {hit.get('source_url')}")
    if not result.get("faq"):
        lines.append("  (없음)")
    lines.append("공개 사례 근거:")
    for hit in result.get("cases") or []:
        lines.append(
            f"  [{hit.get('rank')}] {hit.get('title')} ({hit.get('source_id')})"
        )
    if not result.get("cases"):
        lines.append("  (없음)")
    if result.get("policy_failures"):
        lines.append("정책 검사:")
        lines.extend(f"  - {item}" for item in result["policy_failures"])
    lines.append(
        "단계: "
        + ", ".join(
            f"{s['name']} {s['elapsed_ms']}ms{'!' if not s['ok'] else ''}"
            for s in result.get("stages") or []
        )
    )
    return "\n".join(lines)
