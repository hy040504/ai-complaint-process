from collections import Counter

from .data import normalize_text

# 조사/어미를 제외하고 업무·시설·지역·행위·숫자를 유지합니다.
CONTENT_TAGS = {"NNG", "NNP", "NR", "VV", "VA", "SL", "SH", "SN"}
STOP_WORDS = {"안녕", "감사", "부탁", "문의", "민원", "요청", "관련", "사항"}


class KoreanTokenizer:
    def __init__(self):
        from kiwipiepy import Kiwi
        self.kiwi = Kiwi(num_workers=1)

    def tokens(self, text: str) -> list[str]:
        return [t.form.casefold() for t in self.kiwi.tokenize(normalize_text(text))
                if t.tag.split("-")[0] in CONTENT_TAGS and t.form not in STOP_WORDS]

    def counts(self, text: str) -> Counter:
        return Counter(self.tokens(text))
