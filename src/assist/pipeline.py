"""RAG 검색과 LLM 판정을 이어 응대 결과를 만듭니다.

민원 CRUD와 검색 색인을 변경하지 않습니다. 검색 응답은
`retrieval_only` / `requires_gate`를 유지하고, 그 위에 판정·정책 검사·
조건부 FAQ 생성을 올립니다. 시스템 지시는 `docs/harness/prompts/`의
PREFIX 파일을 조립한 `DECISION_SYSTEM`·`ANSWER_SYSTEM`입니다.
담당자 초안은 PREFIX-03, 순화는 PREFIX-04이며 시민 갈래를 덮지 않습니다.
결과의 `codex`는 모델에 넣은 사용자 JSON과 Codex stdin 전문 목록입니다.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from typing import Any, Callable

from src.assist.constants import PROGRESS_LABELS
from src.assist.district import resolve_district_and_place
from src.assist.prompts import (
    ANSWER_SYSTEM,
    DECISION_SYSTEM,
    SPECIAL_SANITIZE_SYSTEM,
    STAFF_DRAFT_SYSTEM,
)
from src.assist.followup import (
    needs_sanitize,
    sanitize_payload,
    staff_draft_payload,
    validate_sanitize,
    validate_staff_draft,
)
from src.assist.policy import (
    citizen_answer,
    decision_payload,
    empty_decision,
    public_hit,
    validate_decision,
)
from src.llm.complete import (
    CompleteUsage,
    complete_result,
    format_codex_stdin,
    parse_json_object,
)
from src.llm.settings import (
    check_provider_availability,
    llm_configured,
    llm_settings,
    settings_for_provider,
)
from src.rag import (
    SearchParts,
    compact_faq,
    require_search_contract,
    search_parts,
    search_via_api,
)

USE_ENV_LLM = object()


def stage(name: str, started: float, ok: bool = True) -> dict[str, Any]:
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


def llm_enabled(llm_fn: object, provider: str | None = None) -> bool:
    """이번 호출이 언어 모델을 사용하는지 반환합니다.

    Args:
        llm_fn: 환경 설정 사용 표시, 직접 함수, 또는 비활성화 `None`입니다.
        provider: 검사기에서 고른 공급자입니다. 환경 설정을 쓸 때만 봅니다.

    Returns:
        모델을 호출할 수 있으면 True입니다.
    """
    if llm_fn is USE_ENV_LLM:
        if provider:
            return check_provider_availability(provider)[0]
        return llm_configured()
    return callable(llm_fn)


def _resolve_bound_settings(
    llm_fn: object, provider: str | None
) -> tuple[bool, dict[str, str | None] | None]:
    """공급자 선택과 환경 설정으로 호출 가능 여부와 실제 설정을 함께 구합니다.

    Args:
        llm_fn: 환경 설정 사용 표시, 직접 함수, 또는 비활성화 `None`입니다.
        provider: 검사기에서 고른 공급자입니다. 환경 설정을 쓸 때만 봅니다.

    Returns:
        `(호출 가능 여부, 환경 설정 딕셔너리 또는 None)`입니다.
    """
    if llm_fn is not USE_ENV_LLM:
        return callable(llm_fn), None
    if provider:
        return check_provider_availability(provider)[0], settings_for_provider(provider)
    return llm_configured(), llm_settings()


def resolve_chat(
    llm_fn: object,
    provider: str | None,
    usage_box: list[CompleteUsage | None],
) -> Callable[[str, str], str] | None:
    """이번 응대에 쓸 `(system, user) → 텍스트` 함수를 하나로 정합니다.

    직접 넘긴 `llm_fn`(테스트 주입)이 가장 우선합니다. 환경 설정을 쓸 때는
    검사기에서 고른 `provider`를, 없으면 `.env` 기본 공급자를 씁니다.
    호출할 수 없는 공급자면 None을 돌려 모델 없이 판정합니다.

    Args:
        llm_fn: 환경 설정 사용 표시, 직접 함수, 또는 비활성화 `None`입니다.
        provider: `exaone_api`·`openai_api`·`codex_cli` 중 하나이거나 None입니다.
        usage_box: 마지막 호출의 토큰 사용량을 담을 한 칸 목록입니다.

    Returns:
        완성 함수 또는 모델을 쓰지 않을 때 None입니다.
    """
    if llm_fn is not USE_ENV_LLM:
        return llm_fn if callable(llm_fn) else None
    usable, bound = _resolve_bound_settings(llm_fn, provider)
    if not usable or bound is None:
        return None

    def chat(system: str, user: str) -> str:
        """설정을 고정한 채 모델 호출을 1회 실행하고 토큰 사용량을 기록합니다.

        Args:
            system: 조립된 시스템 프롬프트입니다.
            user: 직렬화된 사용자 민원·검색 후보 JSON입니다.

        Returns:
            모델이 반환한 응답 문자열입니다.
        """
        result = complete_result(system, user, settings=bound)
        usage_box[0] = result.usage
        return result.text

    return chat


def progress(key: str) -> dict[str, str]:
    """화면에 보여줄 짧은 진행 안내를 만듭니다.

    Args:
        key: `PROGRESS_LABELS`의 키입니다.

    Returns:
        사건 형식으로 감싼 짧은 안내입니다.
    """
    return {"type": "progress", "key": key, "label": PROGRESS_LABELS[key]}


def build_result(
    query: str,
    district: str | None,
    search: dict[str, Any],
    decision: dict[str, Any],
    failures: list[str],
    generated: str | None,
    stages: list[dict[str, Any]],
    llm_on: bool,
    raw_decision: dict[str, Any] | None = None,
    parts: SearchParts | None = None,
    codex: list[dict[str, Any]] | None = None,
    staff_draft: dict[str, Any] | None = None,
    sanitize: dict[str, Any] | None = None,
    district_inferred: bool = False,
    inferred_place: dict[str, Any] | None = None,
    llm_provider: str | None = None,
    llm_model: str | None = None,
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
        parts: 이미 구한 검색 조각입니다. 생략하면 `search`에서 한 번 만듭니다.
        codex: Codex에 넣은 호출 목록입니다. 사용자 JSON과 stdin 전문을 담습니다.
        staff_draft: PREFIX-03 담당자 초안입니다. 없으면 비웁니다.
        sanitize: PREFIX-04 순화 결과입니다. 없으면 비웁니다.
        district_inferred: 본문 지명으로 구를 자동 추론했으면 True입니다.
        inferred_place: 네이버 지도로 추론된 장소 객체입니다. 없으면 None입니다.
        llm_provider: 실제 선택·해석된 LLM 공급자 식별자입니다.
        llm_model: 실제 호출 대상 모델 이름입니다.

    Returns:
        API·CLI가 공유하는 응대 결과입니다.
    """
    data = parts or search_parts(search)
    departments = data.departments
    selected = set(decision["department_ids"])
    answer = citizen_answer(decision, search, generated, departments)
    return {
        "query": query,
        "district": district,
        "district_inferred": district_inferred,
        "inferred_place": inferred_place,
        "outcome": decision["outcome"],
        "reason_code": decision["reason_code"],
        "answer": answer,
        "handoff_required": decision["outcome"] != "faq_answer",
        "automatic_transfer": False,
        "faq": [public_hit(hit, "faq") for hit in data.faqs],
        "cases": [public_hit(hit, "routing") for hit in data.cases],
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
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "retrieval": {
            "retrieval_only": search.get("retrieval_only", True),
            "decision": search.get("decision", "requires_gate"),
            "elapsed_ms": search.get("elapsed_ms"),
            "pipeline": search.get("pipeline"),
        },
        "codex": list(codex or []),
        "staff_draft": staff_draft,
        "sanitize": sanitize,
    }


def iter_assist(
    query: str,
    district: str | None = None,
    *,
    limit: int = 5,
    rerank: bool = True,
    search_fn: Callable[..., dict[str, Any]] | None = None,
    llm_fn: Callable[[str, str], str] | object | None = USE_ENV_LLM,
    provider: str | None = None,
) -> Iterator[dict[str, Any]]:
    """검색 다음에 LLM 판정을 이어 진행 안내와 최종 결과를 넘깁니다.

    Args:
        query: 한국어 민원 원문입니다.
        district: 명시한 관할 구입니다. 생략하거나 세부 지역·본문 지명이 있으면 자동 추론·정규화합니다.
        limit: 컬렉션별 검색 수입니다.
        rerank: 재정렬 여부입니다.
        search_fn: 검색 함수입니다. 생략하면 검색 API를 호출합니다.
        llm_fn: (system, user) → 텍스트 함수입니다. 생략하면 환경 설정의 LLM을 쓰고, None이면 호출하지 않습니다.
        provider: 'exaone_api', 'openai_api', 'codex_cli' 중 선택할 LLM 공급자입니다.

    Yields:
        `progress` 사건 또는 최종 `done` 결과입니다.
    """
    stages: list[dict[str, Any]] = []
    text = (query or "").strip()
    effective_district, district_inferred, inferred_place = resolve_district_and_place(
        district, text
    )
    llm_on, bound_meta = _resolve_bound_settings(llm_fn, provider)
    resolved_provider = (
        bound_meta.get("provider") if bound_meta else (provider or None)
    )
    if not llm_on and not provider and resolved_provider == "legacy":
        resolved_provider = None
    resolved_model = (
        bound_meta.get("model") if bound_meta and resolved_provider else None
    )
    yield progress("read")
    if not text or len(text) > 2000:
        decision = empty_decision("invalid_model_output")
        decision["reason_code"] = "condition_unclear"
        yield {
            "type": "done",
            "result": build_result(
                query=text,
                district=effective_district,
                search={},
                decision=decision,
                failures=["민원은 1~2000자로 입력해 주세요."],
                generated=None,
                stages=stages,
                llm_on=llm_on,
                district_inferred=district_inferred,
                inferred_place=inferred_place,
                llm_provider=resolved_provider,
                llm_model=resolved_model,
            ),
        }
        return

    search: dict[str, Any] = {}
    yield progress("search")
    started = time.perf_counter()
    try:
        fetch = search_fn or search_via_api
        search = require_search_contract(fetch(text, effective_district, limit, rerank))
        stages.append(stage("검색", started, True))
    except (ValueError, OSError, TypeError, KeyError) as exc:
        stages.append(stage("검색", started, False))
        decision = empty_decision("search_failed")
        yield {
            "type": "done",
            "result": build_result(
                query=text,
                district=effective_district,
                search={},
                decision=decision,
                failures=[str(exc)],
                generated=None,
                stages=stages,
                llm_on=False,
                district_inferred=district_inferred,
                inferred_place=inferred_place,
                llm_provider=resolved_provider,
                llm_model=resolved_model,
            ),
        }
        return

    yield progress("review")
    parts = search_parts(search)
    user_payload = decision_payload(text, effective_district, search, parts, inferred_place=inferred_place)
    decision_user = json.dumps(user_payload, ensure_ascii=False, indent=2)
    usage_box: list[CompleteUsage | None] = [None]
    chat: Callable[[str, str], str] | None = resolve_chat(llm_fn, provider, usage_box)

    def record_call(
        role: str,
        system_label: str,
        system_text: str,
        user_obj: dict[str, Any],
        sent: bool,
        user_json: str | None = None,
    ) -> dict[str, Any]:
        """모델에 넣은 사용자 JSON과 Codex stdin 전문을 한 칸에 담습니다.

        Args:
            role: 판정·FAQ 안내·담당자 초안·순화 중 하나입니다.
            system_label: PREFIX 조합 이름입니다.
            system_text: 실제로 넣은 PREFIX 본문입니다.
            user_obj: 사용자 JSON 객체입니다.
            sent: 모델에 넣었으면 True입니다.
            user_json: `chat`에 넣은 사용자 문자열입니다. 생략하면 다시 직렬화합니다.

        Returns:
            검사기 `assist.codex` 한 칸입니다.
        """
        dumped = (
            user_json
            if user_json is not None
            else json.dumps(user_obj, ensure_ascii=False, indent=2)
        )
        item: dict[str, Any] = {
            "role": role,
            "system": system_label,
            "user": user_obj,
            "sent": sent,
            "prompt": format_codex_stdin(system_text, dumped),
        }
        if sent and usage_box[0] is not None:
            item["usage"] = usage_box[0]
        return item

    raw_decision: dict[str, Any] | None = None
    decision_call_failed = False
    started = time.perf_counter()
    if chat is None:
        stages.append(stage("판정", started, False))
        decision = empty_decision("llm_unavailable")
        unavailable_reason = (
            check_provider_availability(provider)[1]
            if llm_fn is USE_ENV_LLM and provider
            else ""
        )
        failures = [
            unavailable_reason
            or "EXAONE_API_KEY(exaone_api)·OPENAI_API_KEY(openai_api)·codex_cli 또는 legacy 토큰이 필요합니다."
        ]
    else:
        try:
            raw_reply = chat(DECISION_SYSTEM, decision_user)
        except (ValueError, OSError) as exc:
            # 외부 API(429·연결 오류)나 CLI 실패면 후속 LLM 호출을 연달아 보내지 않습니다.
            decision_call_failed = True
            stages.append(stage("판정", started, False))
            decision = empty_decision("llm_unavailable")
            failures = [str(exc)]
        else:
            try:
                raw_decision = parse_json_object(raw_reply)
                stages.append(stage("판정", started, True))
                checked = time.perf_counter()
                decision, failures = validate_decision(raw_decision, search, parts)
                stages.append(stage("정책검사", checked, not failures))
            except (ValueError, json.JSONDecodeError, OSError) as exc:
                stages.append(stage("판정", started, False))
                decision = empty_decision("invalid_model_output")
                failures = [str(exc)]

    codex_calls: list[dict[str, Any]] = [
        record_call(
            "decision",
            "PREFIX-00 + PREFIX-01",
            DECISION_SYSTEM,
            user_payload,
            chat is not None,
            decision_user,
        )
    ]
    generated: str | None = None
    if decision["outcome"] == "faq_answer" and chat is not None:
        yield progress("write")
        started = time.perf_counter()
        selected = [
            compact_faq(parts.by_key[("faq", ref["source_id"])])
            for ref in decision["evidence_refs"]
            if ref["corpus"] == "faq"
        ]
        faq_user = {"query": text, "faq": selected}
        faq_json = json.dumps(faq_user, ensure_ascii=False, indent=2)
        try:
            generated = chat(ANSWER_SYSTEM, faq_json).strip()
            if len(generated) < 20:
                raise ValueError("FAQ 답변이 너무 짧습니다.")
            stages.append(stage("답변생성", started, True))
            stages.append(stage("검증", time.perf_counter(), True))
        except (ValueError, OSError) as exc:
            stages.append(stage("답변생성", started, False))
            decision["outcome"] = "human_handoff"
            decision["reason_code"] = "faq_generation_failed"
            failures.append(str(exc))
            generated = None
        codex_calls.append(
            record_call(
                "faq_answer",
                "PREFIX-00 + PREFIX-02",
                ANSWER_SYSTEM,
                faq_user,
                True,
                faq_json,
            )
        )

    sanitize: dict[str, Any] | None = None
    if chat is not None and not decision_call_failed and needs_sanitize(text):
        yield progress("sanitize")
        started = time.perf_counter()
        sanitize_user = sanitize_payload(text)
        sanitize_json = json.dumps(sanitize_user, ensure_ascii=False, indent=2)
        try:
            sanitize = validate_sanitize(
                parse_json_object(chat(SPECIAL_SANITIZE_SYSTEM, sanitize_json))
            )
            if sanitize is None:
                raise ValueError("순화 결과를 코드에서 검증하지 못했습니다.")
            stages.append(stage("순화", started, True))
        except (ValueError, json.JSONDecodeError, OSError) as exc:
            stages.append(stage("순화", started, False))
            failures.append(str(exc))
            sanitize = None
        codex_calls.append(
            record_call(
                "sanitize",
                "PREFIX-00 + PREFIX-04",
                SPECIAL_SANITIZE_SYSTEM,
                sanitize_user,
                True,
                sanitize_json,
            )
        )

    staff_draft: dict[str, Any] | None = None
    if (
        chat is not None
        and not decision_call_failed
        and decision["outcome"] != "faq_answer"
    ):
        yield progress("draft")
        started = time.perf_counter()
        draft_user = staff_draft_payload(
            text, effective_district, search, decision, parts, inferred_place=inferred_place
        )
        draft_json = json.dumps(draft_user, ensure_ascii=False, indent=2)
        try:
            staff_draft = validate_staff_draft(
                parse_json_object(chat(STAFF_DRAFT_SYSTEM, draft_json)),
                parts,
            )
            if staff_draft is None:
                raise ValueError("담당자 초안을 코드에서 검증하지 못했습니다.")
            stages.append(stage("담당자초안", started, True))
        except (ValueError, json.JSONDecodeError, OSError) as exc:
            stages.append(stage("담당자초안", started, False))
            failures.append(str(exc))
            staff_draft = None
        codex_calls.append(
            record_call(
                "staff_draft",
                "PREFIX-00 + PREFIX-03",
                STAFF_DRAFT_SYSTEM,
                draft_user,
                True,
                draft_json,
            )
        )

    yield {
        "type": "done",
        "result": build_result(
            query=text,
            district=effective_district,
            search=search,
            decision=decision,
            failures=failures,
            generated=generated,
            stages=stages,
            llm_on=chat is not None,
            raw_decision=raw_decision,
            parts=parts,
            codex=codex_calls,
            staff_draft=staff_draft,
            sanitize=sanitize,
            district_inferred=district_inferred,
            inferred_place=inferred_place,
            llm_provider=resolved_provider,
            llm_model=resolved_model,
        ),
    }


def run_assist(
    query: str,
    district: str | None = None,
    *,
    limit: int = 5,
    rerank: bool = True,
    search_fn: Callable[..., dict[str, Any]] | None = None,
    llm_fn: Callable[[str, str], str] | object | None = USE_ENV_LLM,
    on_progress: Callable[[str, str], None] | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    """검색 → 판정 → 정책 검사 → 조건부 FAQ·순화·담당자 초안 순서로 응대 결과를 만듭니다.

    Args:
        query: 한국어 민원 원문입니다.
        district: 명시한 관할 구입니다. 생략하거나 세부 지역·본문 지명이 있으면 자동 추론·정규화합니다.
        limit: 컬렉션별 검색 수입니다.
        rerank: 재정렬 여부입니다.
        search_fn: 검색 함수입니다. 생략하면 검색 API를 호출합니다.
        llm_fn: (system, user) → 텍스트 함수입니다. 생략하면 환경 설정의 LLM을 쓰고, None이면 호출하지 않습니다.
        on_progress: 짧은 진행 안내를 받을 콜백입니다. `(key, label)`입니다.
        provider: 'exaone_api', 'openai_api', 'codex_cli' 중 선택할 LLM 공급자입니다.

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
        provider=provider,
    ):
        if event["type"] == "progress":
            if on_progress:
                on_progress(event["key"], event["label"])
        else:
            result = event["result"]
    if result is None:
        raise RuntimeError("응대 파이프라인이 결과를 만들지 않았습니다.")
    return result


def render_assist(result: dict[str, Any]) -> str:
    """응대 결과를 터미널에 읽기 쉽게 표시합니다.

    Args:
        result: `run_assist`가 만든 결과 딕셔너리입니다.

    Returns:
        갈래·안내·근거·정책 실패·단계를 담은 여러 줄 문자열입니다.
    """
    lines = [
        f"● 응대 결과 · {result.get('outcome')} / 사유 {result.get('reason_code')}",
        f"  자동 이관: {result.get('automatic_transfer')} / 담당자 검토: {result.get('handoff_required')}",
        f"  LLM 설정: {result.get('llm_configured')}",
        "",
        "시민 안내:",
        str(result.get("answer") or "(없음)"),
        "",
    ]
    draft = result.get("staff_draft")
    if isinstance(draft, dict):
        lines.extend(
            [
                "담당자 초안(미게시):",
                str(draft.get("draft_answer") or "(없음)"),
                "",
            ]
        )
    cleaned = result.get("sanitize")
    if isinstance(cleaned, dict):
        lines.extend(
            [
                "순화 요약(담당자 참고):",
                str(cleaned.get("sanitized_summary") or "(없음)"),
                "",
            ]
        )
    lines.append("FAQ 근거:")
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
