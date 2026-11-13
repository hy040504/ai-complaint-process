"""AI 초안 생성 모듈의 재시도·길이·빈 응답 처리를 검증합니다. 실제 LLM은 호출하지 않습니다."""

from __future__ import annotations

import pytest

from src.assist import draft


def test_user_prompt_wraps_complaint_body_with_markers() -> None:
    """민원 원문을 구분선으로 감싸 지시문과 섞이지 않게 합니다."""
    prompt = draft.build_user_prompt("제목", "본문 내용입니다.", "상당구", "도로·교통")

    assert "----- 민원 원문 시작 -----" in prompt
    assert prompt.index("본문 내용입니다.") < prompt.index("----- 민원 원문 끝 -----")


def test_draft_answer_returns_stripped_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """모델 응답의 앞뒤 공백을 정리해 돌려줍니다."""
    monkeypatch.setattr(draft, "llm_settings", lambda: {"provider": "exaone_api"})
    monkeypatch.setattr(draft, "complete_chat", lambda *a, **k: "  답변입니다.  \n")

    assert (
        draft.draft_answer("제목", "본문입니다 충분히 길게.", "상당구", "기타")
        == "답변입니다."
    )


def test_draft_answer_rejects_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """빈 응답은 저장하지 않도록 ValueError로 막습니다."""
    monkeypatch.setattr(draft, "llm_settings", lambda: {"provider": "exaone_api"})
    monkeypatch.setattr(draft, "complete_chat", lambda *a, **k: "   ")

    with pytest.raises(ValueError):
        draft.draft_answer("제목", "본문입니다 충분히 길게.", "상당구", "기타")


def test_draft_answer_truncates_overlong_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """허용 길이를 넘는 응답은 잘라서 저장합니다."""
    monkeypatch.setattr(draft, "llm_settings", lambda: {"provider": "exaone_api"})
    monkeypatch.setattr(
        draft, "complete_chat", lambda *a, **k: "가" * (draft.MAX_DRAFT_CHARS + 50)
    )

    assert (
        len(draft.draft_answer("제목", "본문입니다 충분히 길게.", "상당구", "기타"))
        == draft.MAX_DRAFT_CHARS
    )


def test_backoff_retries_on_429_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """과부하(429)는 기다렸다가 다시 요청하고 성공하면 그 결과를 씁니다."""
    calls: list[float] = []
    responses = iter([ValueError("API 429: busy"), ValueError("API 429: busy"), "성공"])

    def fake_chat(*args: object, **kwargs: object) -> str:
        value = next(responses)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(draft, "complete_chat", fake_chat)
    monkeypatch.setattr(draft.time, "sleep", lambda s: calls.append(s))

    assert draft._complete_with_backoff("입력", {"provider": "exaone_api"}) == "성공"
    assert calls == list(draft.RETRY_DELAYS)


def test_backoff_does_not_retry_other_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """429가 아닌 오류는 바로 올려 보냅니다."""
    monkeypatch.setattr(
        draft,
        "complete_chat",
        lambda *a, **k: (_ for _ in ()).throw(ValueError("인증 실패")),
    )
    monkeypatch.setattr(
        draft.time, "sleep", lambda s: pytest.fail("재시도하면 안 됩니다")
    )

    with pytest.raises(ValueError):
        draft._complete_with_backoff("입력", {"provider": "exaone_api"})
