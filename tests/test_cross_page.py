"""A quote that runs across a page break is still a quote.

Extractors cut pages wherever the paper cut them.  A sentence that starts near
the bottom of page 6 and ends near the top of page 7 is one sentence to the
author and was two unrelated strings to this tool, which searched every page
alone and reported the quote as missing - a `high` finding, the same severity
as a fabricated citation.  That is the worst failure this tool can have: it
does not merely lack a feature, it tells the author their evidence is gone.

Each test below fails on the code before the fix.
"""

from __future__ import annotations

from citevouch.matching import find_in_pages
from citevouch.sources import PageText


def _pages(*texts: str) -> list[PageText]:
    return [PageText(number=i + 1, text=text) for i, text in enumerate(texts)]


BOTTOM = "We evaluated the model on a corpus of 154,391"
TOP = "utterances drawn from OntoNotes and the EWT."
CROSSING = "We evaluated the model on a corpus of 154,391 utterances drawn from OntoNotes"


class TestAQuoteThatCrossesAPageBreak:
    def test_it_is_found(self):
        match = find_in_pages(CROSSING, _pages(BOTTOM, TOP))
        assert match.found, "a quote split across two pages was reported as missing"
        assert match.tier == "exact"

    def test_it_reports_the_page_it_starts_on(self):
        match = find_in_pages(CROSSING, _pages(BOTTOM, TOP))
        assert match.page == 1, "the reader starts where the quote starts"

    def test_it_says_which_page_it_runs_onto(self):
        match = find_in_pages(CROSSING, _pages(BOTTOM, TOP))
        assert match.spans_to == 2

    def test_the_reason_names_the_cause(self):
        match = find_in_pages(CROSSING, _pages(BOTTOM, TOP))
        assert "page break" in match.reason

    def test_a_quote_that_fits_on_one_page_is_not_called_crossing(self):
        whole = BOTTOM + " " + TOP
        match = find_in_pages(CROSSING, _pages(whole))
        assert match.page == 1
        assert match.spans_to is None, "nothing was stitched, so nothing spans"

    def test_a_single_page_still_wins_over_a_stitched_pair(self):
        # Page 3 holds the sentence whole; pages 1+2 hold it split.  A reader
        # wants page 3, and a tool that answers "pages 1-2" has answered a
        # question nobody asked.
        match = find_in_pages(
            CROSSING,
            _pages(BOTTOM, TOP, "padding. " + CROSSING + " And more."),
        )
        assert match.page == 3
        assert match.spans_to is None

    def test_the_hinted_page_is_tried_first(self):
        # Two different pairs could both contain the text; the hint decides
        # which one is reported, so a correct page hint is never "moved".
        first = "alpha beta gamma delta epsilon zeta"
        second = "one two three four five six"
        match = find_in_pages("three four five", _pages(first, second), page_hint=2)
        assert match.found
        assert match.page == 2

    def test_a_quote_in_no_page_at_all_is_still_missing(self):
        match = find_in_pages(
            "this sentence appears in none of these pages whatsoever", _pages(BOTTOM, TOP)
        )
        assert not match.found
        assert match.tier == "none"

    def test_stitching_does_not_join_a_word_across_the_break(self):
        # Extractors wrap at different points.  If the halves are glued with no
        # separator, "154,391" + "utterances" becomes one token and a quote
        # written the way the paper reads would not match it.
        match = find_in_pages("154,391 utterances", _pages(BOTTOM, TOP))
        assert match.found

    def test_a_single_page_source_cannot_cross_anything(self):
        match = find_in_pages("anything at all here", _pages("nothing here"))
        assert not match.found
