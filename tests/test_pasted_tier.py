"""The fourth paste shape: the hyphen survives and the break becomes a space.

Select a hyphenated region in Acrobat, Word or a browser and copy it; the
viewer keeps the hyphen glyph it drew at the line end and hands the clipboard a
space where the break was.  So the page extracts as ``exam-\nples`` and the
author's quote reads ``exam- ples`` - a hyphen followed by a space.

That is neither of the two readings the earlier tiers compare against: tier 1
sees the joined page (``examples``) and the ``hyphen`` tier sees the page with a
bare hyphen (``exam-ples``).  Measured before this tier existed: 90 quotes taken
from 20 real PDFs in a reader's three paste shapes, 12 not found, 11 of the 12
this one.
"""

from __future__ import annotations

import pytest

from citevouch import cli
from citevouch.matching import Match, find_in_pages
from citevouch.sources import PageText
from citevouch.textnorm import fold_pasted, normalize


def page(text: str, number: int = 1) -> PageText:
    return PageText(number=number, text=text)


def find(quote: str, *pages: PageText) -> Match:
    return find_in_pages(normalize(quote).casefold(), list(pages))


BROKEN = "Through a variety of exam-\nples, we demonstrate the claim."


class TestTheFourthReadingIsWhatItIs:
    def test_the_pasted_reading_keeps_the_hyphen_and_the_space(self):
        assert (
            fold_pasted(BROKEN) == "through a variety of exam- ples, we demonstrate the claim."
        )

    def test_the_joined_reading_is_unchanged(self):
        # The default must keep guessing "join", or every existing expectation
        # about a typeset word break flips at once.
        assert normalize(BROKEN) == "Through a variety of examples, we demonstrate the claim."

    def test_the_pasted_reading_equals_the_joined_one_without_a_break(self):
        plain = "Through a variety of examples, we demonstrate the claim."
        assert fold_pasted(plain) == normalize(plain).casefold()


class TestTheQuoteAnAuthorPastesIsFound:
    @pytest.mark.parametrize(
        "quote",
        [
            "a variety of exam- ples, we",
            "a variety of exam-ples, we",
            "a variety of examples, we",
        ],
    )
    def test_every_shape_the_clipboard_can_produce(self, quote):
        match = find(quote, page(BROKEN))
        assert match.found, match.tier

    def test_the_pasted_shape_names_its_own_tier(self):
        match = find("a variety of exam- ples, we", page(BROKEN))
        assert match.tier == "pasted"

    def test_the_pasted_tier_points_at_the_page_that_has_it(self):
        pages = [
            page("Nothing here about examples at all, just filler text.", 6),
            page(BROKEN, 7),
        ]
        match = find("a variety of exam- ples, we", *pages)
        assert match.tier == "pasted"
        assert match.page == 7

    def test_the_tier_says_what_it_saw(self):
        match = find("a variety of exam- ples, we", page(BROKEN))
        assert "clipboard" in match.reason
        assert "hyphen" in match.reason

    def test_the_excerpt_shows_the_page_as_it_was_printed(self):
        match = find("a variety of exam- ples, we", page(BROKEN))
        # The map back into the pasted string, not the collapsed one.
        assert "exam- ples" in match.context


class TestTheRelaxationStaysOneDirectional:
    @pytest.mark.parametrize(
        ("printed", "quote"),
        [
            ("we re-cover the sofa carefully", "we recover the sofa carefully"),
            ("we re-sign the form carefully", "we resign the form carefully"),
            ("we re-form the mould carefully", "we reform the mould carefully"),
            ("a co-op bank rule here", "a coop bank rule here"),
        ],
    )
    def test_a_hyphen_the_page_printed_is_not_given_up(self, printed, quote):
        assert not find(quote, page(printed)).found

    @pytest.mark.parametrize(
        ("printed", "quote"),
        [
            ("we re-cover the sofa carefully", "we re-cover the sofa carefully"),
            ("a co-op bank rule here", "a co-op bank rule here"),
        ],
    )
    def test_the_same_word_with_its_hyphen_is_still_found(self, printed, quote):
        assert find(quote, page(printed)).found


class TestTheOrdinaryCasesStillWork:
    def test_a_page_with_no_line_break_hyphen_is_left_to_the_earlier_tiers(self):
        plain = page("Through a variety of examples, we demonstrate the claim.")
        assert find("a variety of examples, we", plain).tier == "exact"

    def test_a_short_quote_cannot_be_certified_by_giving_up_a_space(self):
        # Only one real word on each side of the hyphen, and no floor is being
        # bypassed: the hyphen must still be present on both sides.
        assert not find("ex- pl", page("a mixed-up thing")).found


class TestTheTierRefusesToCutANumber:
    # The page needs a line-break hyphen in a word before this tier runs at
    # all, so the fixture carries one; the number it must not slice through
    # is ordinary prose on the same page.
    BROKEN = "through the exam-\nples we saw 40.688 rows here"

    def test_a_pasted_quote_may_not_end_inside_a_number(self):
        assert not find("through the exam- ples we saw 40.", page(self.BROKEN)).found

    def test_a_pasted_quote_ending_after_the_number_is_still_found(self):
        match = find("through the exam- ples we saw 40.688 rows", page(self.BROKEN))
        assert match.found, match.tier


class TestTheVerdict:
    def test_a_pasted_quote_verifies_end_to_end(self, tmp_path):
        (tmp_path / "page.txt").write_text(BROKEN + "\n", encoding="utf-8")
        (tmp_path / "sources.toml").write_text(
            '[sources]\npage = "page.txt"\n', encoding="utf-8"
        )
        body = "\n".join(
            [
                "```claim id=c1 source=page page=1",
                "quote: |",
                "  a variety of exam- ples, we",
                "claim: |",
                "  The paper demonstrates the claim.",
                "```",
                "",
            ]
        )
        (tmp_path / "m.md").write_text(body, encoding="utf-8")
        out = str(tmp_path / "m.md")
        assert cli.main(["check", out, "--root", str(tmp_path)]) == 0
