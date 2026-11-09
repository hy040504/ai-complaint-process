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
from src.assist.district import resolve_complaint_district
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
from src.llm import complete_result, llm_configured, llm_settings, parse_json_object
from src.llm.complete import CompleteUsage, format_codex_stdin
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


def llm_enabled(llm_fn: object) -> bool:
    """이번 호출이 언어 모델을 사용하는지 반환합니다.

    Args:
        llm_fn: 환경 설정 사용 표시, 직접 함수, 또는 비활성화 `None`입니다.

    Returns:
        모델을 호출할 수 있으면 True입니다.
    """
    if llm_fn is USE_ENV_LLM:
        return llm_configured()
    return callable(llm_fn)


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
) -> Iterator[dict[str, Any]]:
    """검색 다음에 LLM 판정을 이어 진행 안내와 최종 결과를 넘깁니다.

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
    effective_district, district_inferred = resolve_complaint_district(district, text)
    llm_on = llm_enabled(llm_fn)
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
            ),
        }
        return

    yield progress("review")
    parts = search_parts(search)
    user_payload = decision_payload(text, effective_district, search, parts)
    decision_user = json.dumps(user_payload, ensure_ascii=False, indent=2)
    usage_box: list[CompleteUsage | None] = [None]
    chat: Callable[[str, str], str] | None
    if llm_fn is USE_ENV_LLM:
        if llm_on:
            bound = llm_settings()

            def chat_env(system: str, user: str) -> str:
                result = complete_result(system, user, settings=bound)
                usage_box[0] = result.usage
                return result.text

            chat = chat_env
        else:
            chat = None
    else:
        chat = llm_fn if callable(llm_fn) else None

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
    started = time.perf_counter()
    if chat is None:
        stages.append(stage("판정", started, False))
        decision = empty_decision("llm_unavailable")
        failures = [
            "COMPLAINT_LLM_PROVIDER(openai_api·codex_cli) 또는 "
            "COMPLAINT_LLM_TOKEN·PUBLIC_LLM_TOKEN·XAI_API_KEY가 필요합니다."
        ]
    else:
        try:
            raw_decision = parse_json_object(chat(DECISION_SYSTEM, decision_user))
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
    if chat is not None and needs_sanitize(text):
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
    if chat is not None and decision["outcome"] != "faq_answer":
        yield progress("draft")
        started = time.perf_counter()
        draft_user = staff_draft_payload(text, effective_district, search, decision, parts)
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
) -> dict[str, Any]:
    """검색 → 판정 → 정책 검사 → 조건부 FAQ·순화·담당자 초안 순서로 응대 결과를 만듭니다.

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
