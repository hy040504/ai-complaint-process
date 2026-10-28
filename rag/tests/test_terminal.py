"""검색 테스트 화면의 근거 보존과 터미널 제어 문자 처리를 확인합니다."""
from rag.terminal import render, safe_text


def test_faq_conditions_and_source_remain_visible():
    """FAQ의 대상·기한·주의사항과 출처가 화면에 모두 남는지 확인합니다."""
    result = {"retrieval_only": True, "decision": "requires_gate", "elapsed_ms": 12,
              "results": {"faq_knowledge": {"hits": [
                  {"rank": 1, "title": "시험 안내", "source_id": "test-1",
                   "source_url": "https://example.test/faq", "scores": {},
                   "evidence": {"detail": {"target": "청주시민", "period": "접수 후 7일",
                                           "warnings": "예외 조건을 담당자에게 확인"}}}]}}}
    output = render(result)
    for text in ("청주시민", "접수 후 7일", "예외 조건을 담당자에게 확인",
                 "https://example.test/faq", "requires_gate", "확률이 아닙니다"):
        assert text in output


def test_untrusted_text_cannot_emit_terminal_escape_sequences():
    """문서의 화면 삭제·색상 제어 문자는 실행되지 않게 치환합니다."""
    output = safe_text("문서\x1b[2J\x9b31m\n조건\t확인")
    assert "\x1b" not in output and "\x9b" not in output
    assert "\n조건\t확인" in output
