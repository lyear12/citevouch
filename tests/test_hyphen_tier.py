"""A compound broken at a line end, and the quote that should still match it.

``-\n`` means "typeset hyphenation" in one paper and "compound word" in the
next, and the extracted bytes do not say which.  Joining is right for
``pro-\ncessing`` and wrong for ``high-\ndimensional``; an author quoting the
page as it is printed writes ``high-dimensional`` and, before the ``hyphen``
tier, got ``quote-missing`` at high severity for a sentence that is on the
page.  On this project's own 20-page sample of real linguistics PDFs that
shape occurs 312 times.
"""

from __future__ import annotations

import pytest

from citevouch import cli
from citevouch.matching import Match, find_in_pages
from citevouch.sources import PageText
from citevouch.textnorm import normalize


def page(text: str, number: int = 1) -> PageText:
    return PageText(number=number, text=text)


def find(quote: str, *pages: PageText) -> Match:
    return find_in_pages(normalize(quote).casefold(), list(pages))


class TestTheExtractionIsWhatItIs:
    """The shape the tier exists for, asserted at the level it comes from."""

    def test_a_typeset_break_is_joined(self) -> None:
        assert normalize("the pro-\ncessing is") == "the processing is"

    def test_a_compound_break_is_joined_too(self) -> None:
        # Not a bug in ``normalize``: the two shapes are the same bytes.  This
        # test exists so that a future "fix" here has to face the fact that
        # joining is correct for the sentence above and wrong for this one.
        assert normalize("a high-\ndimensional space") == "a highdimensional space"

    @pytest.mark.parametrize("word", ["high-dimensional", "data-driven", "frame-work"])
    def test_the_hyphen_survives_in_the_quote(self, word: str) -> None:
        assert normalize(word) == word


class TestACompoundQuoteIsFound:
    @pytest.mark.parametrize(
        "page_text, quote",
        [
            (
                "input in the form of a sequence of high-\ndimensional vectors",
                "a sequence of high-dimensional vectors",
            ),
            (
                "we encoded a data-\ndriven representation of the constructions",
                "a data-driven representation of the constructions",
            ),
            (
                "the onto-\nlogical status of constructions is disputed",
                "the onto-logical status of constructions is disputed",
            ),
        ],
    )
    def test_the_quote_as_the_page_prints_it_is_found(self, page_text: str, quote: str) -> None:
        match = find(quote, page(page_text))
        assert match.tier == "hyphen"
        assert match.found
        assert match.similarity == 1.0

    def test_the_joined_spelling_is_found_too(self) -> None:
        # The other direction: a reader who copies the extraction rather than
        # the page writes "highdimensional" and means the same sentence.
        match = find("a highdimensional space", page("a high-\ndimensional space"))
        assert match.found

    def test_the_hyphen_tier_names_the_page(self) -> None:
        match = find(
            "a high-dimensional space",
            page("filler\n\nmore filler", 1),
            page("a high-\ndimensional space", 7),
        )
        assert match.page == 7

    def test_the_hyphen_tier_says_what_it_saw(self) -> None:
        # Every other tier explains itself, and the JSON report renders this
        # string: a generic one leaves a reader with a verdict and no reason.
        # The word that has to appear is the one that tells the two shapes
        # apart - the page prints a hyphen, or the extraction joined one.
        match = find("a high-dimensional space", page("a high-\ndimensional space"))
        assert "hyphen" in match.reason


class TestTheRelaxationIsOneDirectional:
    """Stripping the page too would certify quotes the page does not support."""

    @pytest.mark.parametrize(
        "page_text, quote",
        [
            ("They had to re-cover the roof.", "they had to recover the roof"),
            ("He asked them to re-sign the form.", "he asked them to resign the form"),
            ("The co-op owns the building.", "the coop owns the building"),
            ("The re-form stage comes first.", "the reform stage comes first"),
        ],
    )
    def test_a_hyphen_the_page_prints_is_not_a_hyphen_the_page_lacks(
        self, page_text: str, quote: str
    ) -> None:
        match = find(quote, page(page_text))
        assert not match.found, f"{quote!r} was certified against {page_text!r}"

    @pytest.mark.parametrize(
        "page_text, quote",
        [
            # Both sides carry a hard hyphen and it is in a different place.
            # A lost hyphen is the ambiguity this tier exists for; a moved one
            # is a different word, and stripping hyphens from both sides would
            # hide exactly that.
            ("the abcd-ef layer", "the abc-def layer"),
            ("a data-driven-set model", "a data-driven set model"),
        ],
    )
    def test_a_hyphen_in_a_different_place_is_a_different_word(
        self, page_text: str, quote: str
    ) -> None:
        match = find(quote, page(page_text))
        assert not match.found, f"{quote!r} was certified against {page_text!r}"

    def test_a_hyphen_the_page_never_printed_is_not_a_hyphen_it_lost(self) -> None:
        # The first version of this tier deleted the quote's hyphens and
        # searched a page whose hyphens the join had already deleted, so every
        # one of these was certified.  They are real pairs of real words.
        for page_text, quote in [
            ("we recover the sofa", "we re-cover the sofa"),
            ("they will resign soon", "they will re-sign soon"),
            ("they reform the law", "they re-form the law"),
            ("coop the birds", "co-op the birds"),
            ("a man eating tiger", "a man-eating tiger"),
        ]:
            match = find(quote, page(page_text))
            assert not match.found, f"{quote!r} was certified against {page_text!r}"

    def test_the_page_is_the_side_that_keeps_the_hyphen(self) -> None:
        # The tier compares the quote against the page read *with* its
        # line-break hyphen.  If that ever becomes a comparison against the
        # joined page, this pair starts passing.
        match = find("we re-cover the sofa", page("we re-cover the sofa"))
        assert match.tier == "exact"

    def test_a_hit_inside_a_longer_word_is_refused(self) -> None:
        # "highdimensional" appears in "posthighdimensional" starting mid-word.
        # Without the boundary check this tier would certify a quote that
        # begins in the middle of a different word.
        match = find("high-dimensional analysis", page("the posthighdimensional analysis"))
        assert not match.found


class TestTheOrdinaryCasesStillWork:
    def test_a_typeset_break_still_matches_at_exact(self) -> None:
        match = find(
            "the subsequent processing is assumed",
            page("the subsequent pro-\ncessing is assumed"),
        )
        assert match.tier == "exact"
        assert match.found

    def test_a_page_that_prints_the_hyphen_still_matches_at_exact(self) -> None:
        match = find("a data-driven pattern", page("a data-driven pattern"))
        assert match.tier == "exact"

    def test_a_quote_with_no_hyphen_does_not_enter_the_tier(self) -> None:
        match = find("a sequence of vectors", page("a sequence of vectors"))
        assert match.tier == "exact"

    def test_a_word_that_is_simply_absent_is_still_absent(self) -> None:
        match = find("a high-dimensional space", page("a low-dimensional space"))
        assert not match.found


class TestTheTierRefusesToCutANumber:
    def test_a_quote_that_ends_inside_a_number_is_not_certified(self) -> None:
        # The hyphen tier must not be a second door to the truncation the
        # exact tier was taught to refuse.
        match = find(
            "a high-dimensional space of 40", page("a high-\ndimensional space of 40.688 rows")
        )
        assert match.tier != "hyphen" or not match.found


class TestTheVerdict:
    def test_check_exits_zero_when_the_compound_quote_is_on_the_page(self, tmp_path) -> None:
        # Before the tier this is what an author saw: a correct quote, exit 1.
        src = tmp_path / "page.txt"
        src.write_text(
            "input in the form of a sequence of high-\ndimensional vectors\n", encoding="utf-8"
        )
        (tmp_path / "sources.toml").write_text('[sources]\np = "page.txt"\n', encoding="utf-8")
        (tmp_path / "m.md").write_text(
            "```claim id=c1 source=p page=1\n"
            "quote: |\n"
            "  a sequence of high-dimensional vectors\n"
            "```\n",
            encoding="utf-8",
        )
        code = cli.main(["check", "m.md", "--root", str(tmp_path)])
        assert code == 0
