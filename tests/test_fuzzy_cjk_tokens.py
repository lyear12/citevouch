"""The fuzzy tier counts tokens, and a Chinese character is one token.

Before this, `_TOKEN = re.compile(r"[^\\s]+")` split on whitespace, which is how
Latin script separates words and is not how Chinese does.  A 40-character
Chinese quote was therefore exactly one token, so `MIN_FUZZY_TOKENS` refused it
with "too short for a fuzzy comparison" - a sentence whose every character had
just been compared.  Measured on the same page, one character changed:

    quote = 相关研究指出词汇与构式之间存在互动關聯，这种互动可以解释许多...
    before: tier='none'  reason='quote not found (too short for a fuzzy comparison)'
    after:  tier='fuzzy' similarity=0.947

The tier is the only one that can say "the source has a passage like this but
not these words"; without it every slightly-mistranscribed Chinese quote was
reported as absent, at high severity, which is the tool saying words the author
copied are not on the page.
"""

from __future__ import annotations

import contextlib
import io
import json

from citevouch.matching import FUZZY_THRESHOLD, MIN_FUZZY_TOKENS, _tokens, find_in_pages
from citevouch.sources import PageText

BS = chr(92)

PAGE = (
    "构式语法认为句法结构本身承载意义，而不是词义的简单相加。"
    "相关研究指出词汇与构式之间存在互动关系，这种互动可以解释许多看似例外的语言现象。"
    "我们据此提出了一个分析框架，并在四个语料库上进行了验证。"
)


def _pages(text: str = PAGE) -> list[PageText]:
    return [PageText(number=1, text=text)]


def _fuzzy(quote: str) -> object:
    return find_in_pages(quote, _pages())


class TestWhatATokenIs:
    def test_a_chinese_character_is_one_token(self) -> None:
        assert _tokens("相关研究") == ["相", "关", "研", "究"]

    def test_a_latin_word_is_still_one_token(self) -> None:
        assert _tokens("the method works") == ["the", "method", "works"]

    def test_a_mixed_sentence_counts_both_ways(self) -> None:
        assert _tokens("我们 used the 构式 framework") == [
            "我",
            "们",
            "used",
            "the",
            "构",
            "式",
            "framework",
        ]

    def test_punctuation_is_not_a_token(self) -> None:
        assert _tokens("甲，乙。丙！") == ["甲", "乙", "丙"]

    def test_a_latin_word_does_not_merge_with_the_character_before_it(self) -> None:
        # "构式used" - no space, which is how Chinese-and-English prose is
        # actually written.  The character has to end the run rather than be
        # buffered into it; buffering produced the single token "式used" here
        # and "used" alone in the same sentence, so the same English word was
        # a token or not depending on which script came first.
        assert _tokens("构式used") == ["构", "式", "used"]
        assert _tokens("used构式") == ["used", "构", "式"]

    def test_numbers_are_not_tokens_of_their_own(self) -> None:
        # `_LATIN_WORD` is `[^\W\d_]+`, so a bare number contributes nothing to
        # the token stream; this is the existing Latin behaviour and the CJK
        # change must not alter it.
        assert _tokens("40,688 examples") == ["examples"]

    def test_a_long_chinese_sentence_is_many_tokens(self) -> None:
        quote = "相关研究指出词汇与构式之间存在互动关系"
        assert len(_tokens(quote)) == len(quote) == 19


class TestTheTierCanNowAnswer:
    def test_a_one_character_slip_reaches_the_fuzzy_tier(self) -> None:
        quote = (
            "相关研究指出词汇与构式之间存在互动關聯，这种互动可以解释许多看似例外的语言现象。"
        )
        match = _fuzzy(quote)
        assert match.tier == "fuzzy", match.reason
        assert match.similarity >= FUZZY_THRESHOLD

    def test_the_reason_no_longer_blames_the_length(self) -> None:
        quote = "我们据此提出了一个分析框架，并在四个语料库上进行了检验。"
        match = _fuzzy(quote)
        assert "too short" not in match.reason
        assert match.reason == "the source has a similar passage but not these words verbatim"

    def test_the_closest_passage_reads_as_prose_not_as_characters(self) -> None:
        quote = (
            "相关研究指出词汇与构式之间存在互动關聯，这种互动可以解释许多看似例外的语言现象。"
        )
        match = _fuzzy(quote)
        assert "相 关 研 究" not in match.context
        assert "相关研究" in match.context

    def test_the_verbatim_quote_still_lands_in_an_exact_tier_first(self) -> None:
        assert find_in_pages("相关研究指出词汇与构式之间存在互动关系", _pages()).tier == "exact"

    def test_a_genuinely_absent_quote_is_still_absent(self) -> None:
        quote = "这一整句话说的是完全不一样的内容而且页面从未提到过它。"
        match = _fuzzy(quote)
        assert match.tier == "none"


class TestTheFloorStillApplies:
    def test_four_characters_are_below_the_floor(self) -> None:
        # Four characters that are *not* on the page: the shorter tiers cannot
        # help, so the fuzzy floor is what refuses this one, and its reason
        # says so.
        assert MIN_FUZZY_TOKENS == 5
        match = _fuzzy("构式语意")
        assert match.tier == "none"
        assert "too short" in match.reason

    def test_one_character_is_refused(self) -> None:
        assert _fuzzy("构").tier == "none"

    def test_five_characters_can_reach_the_tier(self) -> None:
        # Five is the documented floor: a five-character run that is not on the
        # page must get past the length gate and be compared, rather than
        # refused for being too short.
        match = find_in_pages("句法结构身", _pages())
        assert match.tier == "none"
        assert "too short" not in match.reason


LATIN_PAGE = "The method works on the corpus and was validated on four collections of examples."


class TestLatinIsUnchanged:
    def test_a_latin_typo_still_reaches_the_tier(self) -> None:
        match = find_in_pages(
            "The method works on the corpus and was validated on four collections of instances.",
            [PageText(number=1, text=LATIN_PAGE)],
        )
        assert match.tier == "fuzzy"

    def test_a_latin_window_is_still_joined_with_spaces(self) -> None:
        match = find_in_pages(
            "The method works on the corpus and was validated on four collections of instances.",
            [PageText(number=1, text=LATIN_PAGE)],
        )
        assert " " in match.context


class TestTheEndToEndVerdict:
    def test_a_mistranscribed_chinese_quote_is_fuzzy_not_missing(self, tmp_path) -> None:
        from citevouch.cli import main

        (tmp_path / "page.txt").write_text(PAGE + "\n", encoding="utf-8", newline="\n")
        (tmp_path / "sources.toml").write_text(
            '[sources]\npage = "page.txt"\n', encoding="utf-8", newline="\n"
        )
        (tmp_path / "m.md").write_text(
            "```claim id=c1 source=page page=1\nquote: |\n"
            "  相关研究指出词汇与构式之间存在互动關聯，这种互动可以解释许多看似例外的语言现象。\n"
            "```\n",
            encoding="utf-8",
            newline="\n",
        )
        assert main(["scan", "m.md", "--root", str(tmp_path), "--quiet"]) in (0, 1)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main(
                ["check", "m.md", "--root", str(tmp_path), "--use-recorded", "--format", "json"]
            )
        assert code == 1
        blob = json.loads(buffer.getvalue())
        codes = [finding["code"] for finding in blob["findings"]]
        assert "quote-fuzzy" in codes, codes
        assert "quote-missing" not in codes, codes
