"""PREFIX-03 담당자 초안과 PREFIX-04 순화 요약을 검사·조립합니다.

시민 세 갈래 판정을 바꾸지 않습니다. 민원 CRUD 테이블에도 쓰지 않습니다.
PREFIX-04는 검색 도구를 부르지 않으며, 1차 판정기의 문맥 판단(`sanitize_needed`)
또는 규칙 기반 문맥 휴리스틱이 순화 필요로 판단할 때만 호출합니다.
"""

from __future__ import annotations

import re
from typing import Any

from src.assist.constants import CORPORA
from src.assist.policy import decision_payload
from src.rag.evidence import SearchParts

RISK_SIGNALS = (
    "profanity_insult",
    "sarcasm_mockery",
    "threat_intimidation",
    "sexual_harassment",
    "repeated_obsession",
    "legal_threat",
    "excessive_personal_info_demand",
    "urgent_safety_hazard",
    "discretionary_disposition_pressure",
)

# 구형 호출(sanitize_needed 미반환) 호환용 참고 목록입니다. 실제 판별은 아래 문맥 정규식이 담당합니다.
SANITIZE_HINTS = (
    "씨발",
    "시발",
    "개새끼",
    "꺼져",
    "죽어",
    "패죽",
    "협박",
    "고발하겠다",
    "미친놈",
    "쓰레기같은",
    "조져",
    "병신",
)

_FACILITY_OFF_RE = re.compile(
    r"(?:"
    r"(?:움푹|푹|깊게|깊이)\s*꺼져(?!라)"
    r"|"
    r"(?:가로등|보안등|신호등|전등|조명|전기|전원|불빛?|보도\s*블[록럭]|블[록럭]|타일|"
    r"인도|도로|차도|바닥|땅|지반|아스팔트|노면|맨홀|배수로|지붕|교각|산책로|자전거도로)"
    r"(?:(?!(?:너|니|니들|야|놈|년))[^\n.!?,]){0,24}"
    r"꺼져(?!라)"
    r")"
)

_LIVING_DYING_RE = re.compile(
    r"(?:나무|가로수|소나무|벚나무|식물|꽃|잔디|풀|물고기|생물|작물|농작물|초목)"
    r"(?:[가이도만들은는]|\s)*(?:말라|시들어|다|모두|점점|계속|\s)*죽어"
)

_UNAMBIGUOUS_ABUSE_RE = re.compile(
    r"(?:"
    r"(?<![가-힣])씨발"
    r"|(?<![가-힣])씨[\s\d\W_]+발(?:[놈년넘련색새것야아들]|(?![가-힣]))"
    r"|(?<![가-힣])시발(?!(?:점|지|역|지점))"
    r"|(?<![가-힣])시[\s\d\W_]+발(?:[놈년넘련색새것야아들]|(?![가-힣]))"
    r"|(?<![\d가-힣])개[\s\d\W_]*새[\s\d\W_]*끼"
    r"|(?<![가-힣])병[\s\d\W_]*신(?:[같놈년들짓아야이]|(?![가-힣]))"
    r"|(?<![가-힣])미[\s\d\W_]*친\s*(?:놈|년|새끼|것들|공무원)"
    r"|(?<![가-힣])미쳤(?:냐|네|나|어|소)"
    r"|(?<![가-힣])존[\s\W_]*나(?:게|많|싫|짜|화|웃|어이|느|(?![가-힣]))"
    r"|(?<![가-힣])지[\s\W_]*랄"
    r"|(?<![가-힣])염[\s\W_]*병"
    r"|(?<![ㄱ-ㅎㅏ-ㅣ])(?:[ㅅㅆ][\s._\-]*ㅂ|ㅂ[\s._\-]*ㅅ|ㅈ[\s._\-]*ㄴ|ㅁ[\s._\-]*ㅊ)(?![ㄱ-ㅎㅏ-ㅣ])"
    r"|패\s*죽|죽여\s*버린|쳐\s*죽|(?<![가-힣])조져\s*(?:버린|놓)"
    r"|죽어라|뒤져라"
    r"|가만\s*안\s*(?:둔다|둬|두겠)"
    r"|찾아가(?:서)?\s*(?:엎|뒤엎|부수|죽|패)"
    r")"
)

_FALLBACK_HOSTILE_OR_SARCASM_RE = re.compile(
    r"(?:"
    r"꺼져라|꺼지라|(?:니들이|너나|다|그냥|혼자|눈앞에서)\s*꺼져|꺼져"
    r"|(?:너나|니들이|다|공무원[^.!?\n]{0,8})\s*죽어"
    r"|쓰레기\s*같은|협박|고발하겠다|(?<![가-힣])조져"
    r"|참\s*잘\s*(?:한다|하네|돌아간다|하십니다)"
    r"|세금(?:이)?\s*(?:아깝|아까워|녹는다|줄줄|살살)"
    r"|혈세\s*(?:낭비|도둑)|월급\s*루팡|앵무새\s*(?:처럼|복붙|답변)|탁상\s*행정|일\s*좀\s*해라"
    r")"
)


def needs_sanitize(query: str) -> bool:
    """원문 문맥 휴리스틱으로 순화 호출이 필요한지 봅니다.

    "보도블록이 꺼져서"·"가로등이 꺼져"·"가로수가 죽어가요" 같은 시설물·생태 서술은
    제외하고, 명백한 욕설·초성/변형 욕설·보복 협박·노골적 비꼬기 표현만 감지합니다.

    Args:
        query: 민원 원문입니다.

    Returns:
        문맥상 순화가 필요하면 True입니다.
    """
    text = query or ""
    if not text.strip():
        return False
    if _UNAMBIGUOUS_ABUSE_RE.search(text):
        return True
    cleaned = _FACILITY_OFF_RE.sub(" ", text)
    cleaned = _LIVING_DYING_RE.sub(" ", cleaned)
    return bool(_FALLBACK_HOSTILE_OR_SARCASM_RE.search(cleaned))


def should_run_sanitize(
    query: str,
    raw_decision: dict[str, Any] | None = None,
    decision: dict[str, Any] | None = None,
) -> bool:
    """1차 판정기 문맥 판단과 안전 휴리스틱을 합쳐 PREFIX-04 호출 여부를 정합니다.

    1차 판정기(`PREFIX-01`)가 `sanitize_needed`를 불리언으로 주면 그 문맥 판단을 우선
    따릅니다. 다만 모델이 `false`를 주더라도 명백한 욕설·폭력 협박이 원문에 있으면
    프롬프트 인젝션 등을 막기 위해 순화를 켭니다. 판정 필드가 없으면
    `needs_sanitize(query)` 휴리스틱으로 폴백합니다.

    Args:
        query: 민원 원문입니다.
        raw_decision: 1차 판정기 원시 JSON 딕셔너리입니다.
        decision: 검증된 판정 딕셔너리입니다(호환용).

    Returns:
        PREFIX-04 순화를 호출해야 하면 True입니다.
    """
    text = query or ""
    flag: bool | None = None
    for source in (raw_decision, decision):
        if isinstance(source, dict) and isinstance(source.get("sanitize_needed"), bool):
            flag = source["sanitize_needed"]
            break
    if flag is True:
        return True
    if flag is False:
        return bool(_UNAMBIGUOUS_ABUSE_RE.search(text))
    return needs_sanitize(text)


def sanitize_payload(query: str) -> dict[str, Any]:
    """순화 호출의 사용자 JSON을 만듭니다.

    검색 후보는 넣지 않습니다. PREFIX-04는 원문만 다룹니다.

    Args:
        query: 민원 원문입니다.

    Returns:
        `query`만 담은 딕셔너리입니다.
    """
    return {"query": query}


def validate_sanitize(raw: dict[str, Any]) -> dict[str, Any] | None:
    """순화 JSON을 허용 목록으로 검사합니다.

    Args:
        raw: 모델이 반환한 객체입니다.

    Returns:
        검증된 순화 결과입니다. 스키마가 아니면 None입니다.
    """
    summary = raw.get("sanitized_summary")
    requests = raw.get("legitimate_requests")
    signals = raw.get("risk_signals")
    review = raw.get("human_protection_review_needed")
    if not isinstance(summary, str) or len(summary.strip()) < 10:
        return None
    if not isinstance(requests, list) or not all(
        isinstance(item, str) and item.strip() for item in requests
    ):
        return None
    if not isinstance(signals, list) or not all(
        item in RISK_SIGNALS for item in signals
    ):
        return None
    if not isinstance(review, bool):
        return None
    return {
        "sanitized_summary": summary.strip(),
        "legitimate_requests": [item.strip() for item in requests],
        "risk_signals": list(signals),
        "human_protection_review_needed": review,
    }


def staff_draft_payload(
    query: str,
    district: str | None,
    search: dict[str, Any],
    decision: dict[str, Any],
    parts: SearchParts | None = None,
    inferred_place: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """담당자 초안 호출의 사용자 JSON을 만듭니다.

    검색 후보가 이미 있으므로 PREFIX-03은 도구를 다시 부르지 않습니다.

    Args:
        query: 민원 원문입니다.
        district: 명시한 관할 구입니다.
        search: 검색 API 응답입니다.
        decision: 코드 검증을 거친 판정입니다.
        parts: 이미 구한 검색 조각입니다.
        inferred_place: 네이버 지도로 추론된 장소 객체입니다.

    Returns:
        판정 갈래와 검색 후보를 담은 딕셔너리입니다.
    """
    payload = decision_payload(
        query, district, search, parts, inferred_place=inferred_place
    )
    result = {
        "query": payload["query"],
        "district": payload["district"],
        "outcome": decision.get("outcome"),
        "reason_code": decision.get("reason_code"),
        "faq_candidates": payload["faq_candidates"],
        "case_candidates": payload["case_candidates"],
        "department_candidates": payload["department_candidates"],
    }
    if inferred_place:
        result["inferred_place"] = inferred_place
    return result


def validate_staff_draft(
    raw: dict[str, Any],
    parts: SearchParts,
) -> dict[str, Any] | None:
    """담당자 초안 JSON을 검사하고 입력에 있는 출처만 남깁니다.

    Args:
        raw: 모델이 반환한 객체입니다.
        parts: 검색 조각입니다.

    Returns:
        검증된 초안입니다. 스키마가 아니면 None입니다.
    """
    card = raw.get("summary_card")
    draft = raw.get("draft_answer")
    citations = raw.get("citations")
    field_check = raw.get("requires_field_check")
    if not isinstance(card, dict):
        return None
    core = card.get("core_summary")
    request = card.get("citizen_request")
    location = card.get("location_or_target")
    missing = card.get("missing_info")
    if not isinstance(core, str) or not core.strip():
        return None
    if not isinstance(request, str) or not request.strip():
        return None
    if not isinstance(location, str):
        return None
    if not isinstance(missing, list) or not all(
        isinstance(item, str) for item in missing
    ):
        return None
    if not isinstance(draft, str) or len(draft.strip()) < 20:
        return None
    if not isinstance(citations, list):
        return None
    if not isinstance(field_check, bool):
        return None
    kept: list[dict[str, str]] = []
    for item in citations:
        if not isinstance(item, dict):
            continue
        corpus = item.get("corpus")
        source_id = item.get("source_id")
        if corpus not in CORPORA or not isinstance(source_id, str):
            continue
        if (corpus, source_id) not in parts.by_key:
            continue
        kept.append({"corpus": corpus, "source_id": source_id})
    return {
        "summary_card": {
            "core_summary": core.strip(),
            "citizen_request": request.strip(),
            "location_or_target": location.strip(),
            "missing_info": [item.strip() for item in missing if item.strip()],
        },
        "draft_answer": draft.strip(),
        "citations": kept,
        "requires_field_check": field_check,
    }
