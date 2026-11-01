"""A quote that stops in the middle of a number is not evidence for that number.

``_is_word_char`` is ``str.isalnum``, so a quote ending at ``40`` before
``.688`` ends on a character that is not a letter and passes the word-boundary
rule.  The tool then certified, at similarity 1.0, that the page says
"The value is 40" when the page says "The value is 40.688" - the number in the
claim is a truncation of the real one, presented as proven.  That is worse than
a miss: a miss sends the author to look, a false pass does not.

The spans come from ``REPORT_PATTERN``, the same pattern that decides what a
number is everywhere else, so the guard cannot disagree with the report about
where a number starts and ends.
"""

from __future__ import annotations

import pytest

from citevouch.matching import _cuts_a_number, _number_spans, find_in_pages
from citevouch.sources import PageText


def _page(text: str) -> PageText:
    return PageText(number=1, text=text)


def _find(quote: str, page_text: str):
    return find_in_pages(quote, [_page(page_text)], None)


class TestTheSpansAreWhereTheNumbersAre:
    def test_a_grouped_number_is_one_span(self) -> None:
        text = "The value is 40.688 in the table."
        assert _number_spans(text) == [(13, 19)]

    def test_a_bare_integer_is_one_span(self) -> None:
        assert _number_spans("we counted 40688 entries") == [(11, 16)]

    def test_text_without_numbers_has_no_spans(self) -> None:
        assert _number_spans("no digits here at all") == []


class TestTheGuardSeesASlice:
    def test_ending_strictly_inside_a_number_is_a_slice(self) -> None:
        spans = [(13, 19)]
        assert _cuts_a_number(spans, 0, 17)

    def test_starting_strictly_inside_a_number_is_a_slice(self) -> None:
        spans = [(13, 19)]
        assert _cuts_a_number(spans, 16, 40)

    def test_ending_exactly_at_the_number_end_is_not_a_slice(self) -> None:
        spans = [(13, 19)]
        assert not _cuts_a_number(spans, 0, 19)

    def test_stopping_before_the_number_is_not_a_slice(self) -> None:
        spans = [(13, 19)]
        assert not _cuts_a_number(spans, 0, 10)

    def test_a_match_covering_the_whole_number_is_not_a_slice(self) -> None:
        spans = [(13, 19)]
        assert not _cuts_a_number(spans, 0, 25)


class TestTheExactTierRefusesATruncatedNumber:
    """Every case here was certified as ``exact`` with similarity 1.0 before."""

    @pytest.mark.parametrize(
        ("page_text", "quote"),
        [
            ("The value is 40.688 in the table.", "The value is 40."),
            ("The value is 40.688 in the table.", "The value is 40"),
            ("The value is 40,688 in the table.", "The value is 40,"),
            ("The value is 40688 in the table.", "The value is 406"),
            ("The corpus holds 1,234,567 sentences.", "The corpus holds 1,234,"),
        ],
    )
    def test_a_slice_is_not_a_match(self, page_text: str, quote: str) -> None:
        match = _find(quote, page_text)
        assert not match.found, (
            f"{quote!r} was certified against {page_text!r}; the number in it is "
            f"a truncation of the one on the page"
        )

    def test_the_whole_number_still_matches(self) -> None:
        match = _find("The value is 40.688 in the table.", "The value is 40.688 in the table.")
        assert match.tier == "exact"
        assert match.found

    def test_the_other_spelling_of_the_same_number_still_matches(self) -> None:
        match = _find("The value is 40,688 in the table.", "The value is 40.688 in the table.")
        assert match.found


class TestTheGuardDoesNotRefuseOrdinaryQuotes:
    """The boundary rule exists so a sentence that ends a sentence still matches."""

    @pytest.mark.parametrize(
        ("page_text", "quote"),
        [
            ("The value is high. Then it fell.", "The value is high."),
            ("It was true. He left.", "It was true."),
            ("\u5f88\u5c0f\u3002\u4e0b\u4e00\u53e5", "\u5f88\u5c0f\u3002"),
            ("We counted 40688 entries in total.", "We counted 40688 entries in total."),
            ("Table 2 of the appendix", "Table 2"),
            ("Table 2 of the appendix", "Table 2 of"),
        ],
    )
    def test_a_finished_number_or_sentence_still_matches(
        self, page_text: str, quote: str
    ) -> None:
        match = _find(quote, page_text)
        assert match.found, f"{quote!r} should still match {page_text!r} ({match.reason})"


class TestTheEndToEndVerdict:
    def test_a_truncated_number_is_not_verified(self, tmp_path) -> None:
        from citevouch.cli import main

        (tmp_path / "page.txt").write_text(
            "The value is 40.688 in the table.\n", encoding="utf-8"
        )
        (tmp_path / "sources.toml").write_text(
            '[sources]\npage = "page.txt"\n', encoding="utf-8", newline="\n"
        )
        (tmp_path / "m.md").write_text(
            '```claim id=c1 source=page\nquote: "The value is 40."\n```\n',
            encoding="utf-8",
            newline="\n",
        )
        run = main(["check", str(tmp_path / "m.md"), "--root", str(tmp_path), "--no-cache"])
        assert run == 1, "a quote whose number is a truncation of the page's must not pass"


class TestTheCanonicalTierEndsWhereTheQuoteEnds:
    """The offset map says where each canonical character *starts*.

    A quote that ends on a number therefore cannot take its end from the last
    matched character: every character of a rewritten number maps to that
    number's first printed position, so ``end`` collapsed onto ``start`` and
    the span looked exactly like a truncated number.  A legitimate quote
    reading ``40,688`` against a page reading ``40.688`` was refused because
    of it, which is the guard turning on the author.

    The excerpt is where the difference shows.  ``_context`` adds sixty
    characters either side of the match, and a page shorter than that fits
    inside the excerpt with no ellipsis at all.  An ``end`` that stops one
    short of the match makes the right margin start five characters earlier
    (``40.688`` is five printed characters, ``40688`` is five canonical ones),
    so the same page comes back truncated and with an ellipsis.  Asserting on
    the ellipsis is asserting on the number the reader was promised.
    """

    # 77 characters: `hit + 60` reaches the end of the page exactly when the
    # end is mapped correctly, and stops five characters short when it is not.
    PAGE = "the value is 40.688 in the table and then some trailing words here to fill it"

    def test_a_quote_ending_on_the_other_spelling_still_matches(self) -> None:
        match = _find("the value is 40,688", self.PAGE)
        assert match.tier == "canonical", match.reason
        assert match.found

    def test_the_excerpt_reaches_the_end_of_a_page_that_fits(self) -> None:
        match = _find("the value is 40,688", self.PAGE)
        assert not match.context.endswith("…"), (
            "the excerpt was cut short of the page's end, so the match ended "
            f"before it does: {match.context!r}"
        )
        assert match.context.endswith("to fill it"), (
            f"the excerpt lost the end of the page: {match.context!r}"
        )

    def test_a_quote_ending_on_a_number_at_the_end_of_the_page(self) -> None:
        match = _find("The value is 40,688", "The value is 40.688")
        assert match.tier == "canonical", match.reason
        assert match.found

    def test_the_excerpt_of_that_match_covers_the_whole_number(self) -> None:
        match = _find("The value is 40,688", "The value is 40.688 in the table.")
        assert "40.688" in match.context, (
            f"the excerpt stops before the number it matched: {match.context!r}"
        )

    def test_a_truncated_number_still_does_not_match(self) -> None:
        match = _find("The value is 40.", "The value is 40.688 in the table.")
        assert not match.found
