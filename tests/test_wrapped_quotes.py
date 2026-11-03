"""A quote wrapped in quotation marks was reported as not verbatim.

The marks are the author's way of saying "these are somebody else's words".
They are not on the page unless the page quoted somebody too, so a sentence
copied out of the source and put in quotation marks matched no tier.  It came
back as ``quote-fuzzy`` at high severity with the message

    the source has a similar passage but not these words verbatim
    (closest passage, page 1, similarity 1.00)

which contradicts itself: similarity 1.00 is verbatim.  Measured before the
fix, on a page holding the sentence bare:

    bare       tier='exact'  -> [info] quote-found
    straight   tier='fuzzy'  -> [high] quote-fuzzy, similarity 1.00
    curly      tier='fuzzy'  -> [high] quote-fuzzy, similarity 1.00
    corner 「」 tier='fuzzy'  -> [high] quote-fuzzy, similarity 1.00
    book 《》   tier='fuzzy'  -> [high] quote-fuzzy, similarity 1.00

Every one of those shapes is how a humanities manuscript introduces a quote.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path

import pytest

from citevouch import matching, textnorm
from citevouch.cli import main
from citevouch.sources import PageText

EN_PAGE = "The method works on every corpus we tried. It is robust.\n"
CN_PAGE = "相关研究指出，词汇与构式之间存在互动关系。这一点很重要。\n"
EN_QUOTE = "The method works on every corpus we tried."
CN_QUOTE = "相关研究指出，词汇与构式之间存在互动关系。"

WRAPPINGS = {
    "straight double": ('"', '"'),
    "straight single": ("'", "'"),
    "curly double": ("\u201c", "\u201d"),
    "curly single": ("\u2018", "\u2019"),
    "corner (Japanese/Chinese)": ("\u300c", "\u300d"),
    "white corner": ("\u300e", "\u300f"),
    "book title (Chinese)": ("\u300a", "\u300b"),
    "angle (Chinese)": ("\u3008", "\u3009"),
    "lenticular (Chinese)": ("\u3010", "\u3011"),
    "tortoise (Chinese)": ("\u3014", "\u3015"),
    "halfwidth (Japanese)": ("\uff62", "\uff63"),
}


def _pages(text: str) -> list[PageText]:
    return [PageText(number=1, text=text, folded=textnorm.fold(text))]


class TestTheMarksAreNotTheSentence:
    @pytest.mark.parametrize("label", sorted(WRAPPINGS))
    def test_a_wrapped_verbatim_quote_is_found(self, label: str) -> None:
        opener, closer = WRAPPINGS[label]
        match = matching.find_in_pages(opener + EN_QUOTE + closer, _pages(EN_PAGE))
        assert match.found, match.reason
        assert match.tier == "exact"
        assert match.similarity == 1.0

    @pytest.mark.parametrize("label", ["curly double", "corner (Japanese/Chinese)"])
    def test_it_works_in_chinese_too(self, label: str) -> None:
        opener, closer = WRAPPINGS[label]
        match = matching.find_in_pages(opener + CN_QUOTE + closer, _pages(CN_PAGE))
        assert match.found, match.reason
        assert match.tier == "exact"

    def test_the_mark_itself_is_not_certified(self) -> None:
        """A page holding the marks must not make a bare quote of them match."""
        page = "\u201cThe method works on every corpus we tried.\u201d\n"
        bare = matching.find_in_pages(EN_QUOTE, _pages(page))
        assert bare.found


class TestTheMarksThatAreNotPairs:
    def test_an_unmatched_opener_is_left_alone(self) -> None:
        match = matching.find_in_pages("\u201c" + EN_QUOTE, _pages(EN_PAGE))
        assert not match.found

    def test_an_empty_pair_is_not_peeled_to_nothing(self) -> None:
        assert textnorm.strip_wrapping_quotes("\u201c\u201d") == "\u201c\u201d"
        assert textnorm.strip_wrapping_quotes("\u201c \u201d") == "\u201c \u201d"

    def test_a_mismatched_pair_is_left_alone(self) -> None:
        assert textnorm.strip_wrapping_quotes("\u201cabc'") == "\u201cabc'"

    def test_two_layers_come_off(self) -> None:
        assert textnorm.strip_wrapping_quotes("\u201c\u300eabc\u300f\u201d") == "abc"

    def test_a_quote_with_no_marks_is_untouched(self) -> None:
        assert textnorm.strip_wrapping_quotes(EN_QUOTE) == EN_QUOTE


class TestTheRetryCannotMakeThingsWorse:
    def test_an_absent_wrapped_quote_keeps_the_worse_verdict(self) -> None:
        """The retry is only accepted when it finds something.

        A weaker verdict about text the author did not write is not an
        improvement on the verdict about the text they did.
        """
        quote = "\u201c" + "Zebra quixotic flamboyance underwhelming juxtaposition." + "\u201d"
        match = matching.find_in_pages(quote, _pages(EN_PAGE))
        assert not match.found

    def test_a_wrapped_near_miss_is_still_reported_as_a_near_miss(self) -> None:
        """The retry must not quietly certify a quote that differs."""
        near = "The method works on each corpus we tried."
        wrapped = matching.find_in_pages("\u201c" + near + "\u201d", _pages(EN_PAGE))
        assert not wrapped.found
        assert wrapped.tier in ("fuzzy", "none")

    def test_the_page_winning_is_not_a_pretext_to_accept_anything(self) -> None:
        page = "Nothing like it appears anywhere here.\n"
        match = matching.find_in_pages("\u201c" + EN_QUOTE + "\u201d", _pages(page))
        assert not match.found


class TestTheVerdictOnAProject:
    def _run(self, root: Path, argv: list[str]) -> tuple[int, str]:
        out = io.StringIO()
        here = Path.cwd()
        try:
            os.chdir(root)
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                code = main(argv)
        finally:
            os.chdir(here)
        return code, out.getvalue()

    @pytest.mark.parametrize("label", ["curly double", "corner (Japanese/Chinese)"])
    def test_a_wrapped_quote_exits_zero_and_says_found(
        self, tmp_path: Path, label: str
    ) -> None:
        opener, closer = WRAPPINGS[label]
        quote = opener + CN_QUOTE + closer
        (tmp_path / "page.txt").write_text(CN_PAGE, encoding="utf-8", newline="\n")
        (tmp_path / "sources.toml").write_text(
            '[sources]\npage = "page.txt"\n', encoding="utf-8", newline="\n"
        )
        (tmp_path / "m.md").write_text(
            "# t\n\n```claim id=c1 source=page page=1\n"
            "claim: |\n  " + quote + "\n"
            "quote: |\n  " + quote + "\n```\n",
            encoding="utf-8",
            newline="\n",
        )
        code, out = self._run(tmp_path, ["check", "m.md", "--format", "json"])
        data = json.loads(out)
        codes = [f["code"] for f in data["findings"]]
        assert code == 0, out
        assert codes == ["quote-found"], codes

    def test_an_absent_wrapped_quote_still_fails(self, tmp_path: Path) -> None:
        quote = "\u201cThis sentence is not in the file at all, anywhere.\u201d"
        (tmp_path / "page.txt").write_text(EN_PAGE, encoding="utf-8", newline="\n")
        (tmp_path / "sources.toml").write_text(
            '[sources]\npage = "page.txt"\n', encoding="utf-8", newline="\n"
        )
        (tmp_path / "m.md").write_text(
            "# t\n\n```claim id=c1 source=page page=1\n"
            "claim: |\n  " + quote + "\n"
            "quote: |\n  " + quote + "\n```\n",
            encoding="utf-8",
            newline="\n",
        )
        code, out = self._run(tmp_path, ["check", "m.md", "--format", "json"])
        data = json.loads(out)
        codes = [f["code"] for f in data["findings"]]
        assert code == 1, out
        assert "quote-missing" in codes, codes
