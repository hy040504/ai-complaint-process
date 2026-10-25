"""Kiwi 형태소를 이용해 한국어 BM25 검색용 토큰을 추출합니다."""
from collections import Counter

from .data import normalize_text

# 조사/어미를 제외하고 업무·시설·지역·행위·숫자를 유지합니다.
CONTENT_TAGS = {"NNG", "NNP", "NR", "VV", "VA", "SL", "SH", "SN"}
STOP_WORDS = {"안녕", "감사", "부탁", "문의", "민원", "요청", "관련", "사항"}


class KoreanTokenizer:
    """업무·시설·지역·행위·숫자를 남기는 Kiwi 토크나이저입니다."""

    def __init__(self):
        """검색에 재사용할 단일 작업자 Kiwi 인스턴스를 준비합니다."""
        from kiwipiepy import Kiwi
        self.kiwi = Kiwi(num_workers=1)

    def tokens(self, text: str) -> list[str]:
        """검색에 필요한 형태소를 추출하고 조사·어미·상용 표현을 제외합니다.

        Args:
            text: 분석할 한국어 검색 본문 또는 질문입니다.

        Returns:
            영문 대소문자를 정규화하고 반복 출현을 보존한 토큰 목록입니다.
        """
        return [t.form.casefold() for t in self.kiwi.tokenize(normalize_text(text))
                if t.tag.split("-")[0] in CONTENT_TAGS and t.form not in STOP_WORDS]

    def counts(self, text: str) -> Counter:
        """검색 본문의 토큰별 출현 횟수를 계산합니다.

        Args:
            text: 단어 빈도를 집계할 검색 본문입니다.

        Returns:
            BM25 적재에 사용할 토큰별 빈도입니다.
        """
        return Counter(self.tokens(text))
