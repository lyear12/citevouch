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

from pathlib import Path

import pytest

from citevouch.matching import find_in_pages
from citevouch.scan import ScanOptions, scan
from citevouch.sources import PageText
from citevouch.verify import verify


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


class TestTheVerifierAgreesWithTheMatcher:
    """The matcher knowing about page breaks is only half the promise.

    verify makes two decisions from a crossing match, and both are written down
    as promises in the changelog: a ledger pointing at either of the two pages
    is verified rather than moved, and a number carried by either half counts as
    present.  Neither decision had a test.  Reverting the page rule to
    "usable_page == match.page" and reverting the number rule to
    "_number_checks(claim, pages, match.page)" each left the whole suite green,
    and the second one does not merely miss a feature: it reports
    number-absent-in-quote, a *high* finding, about a number the author can read
    on page 2 with their own eyes.  That is the failure this tool exists to
    prevent, so each test below fails on the code before the rule it pins.
    """

    LEAD = "We evaluated the model on a corpus of 154,391"
    TAIL = "utterances drawn from OntoNotes and the EWT. We counted 40,688 entries."
    QUOTE = "We evaluated the model on a corpus of 154,391 utterances drawn from OntoNotes"

    def _project(self, tmp_path: Path, page: int) -> tuple[Path, Path]:
        """A two-page source, and a claim whose quote crosses the break."""
        (tmp_path / "papers").mkdir()
        (tmp_path / "papers" / "2026_cross.txt").write_text(
            self.LEAD + "\f" + self.TAIL, encoding="utf-8"
        )
        (tmp_path / "sources.toml").write_text(
            '[sources]\ncross2026 = "papers/2026_cross.txt"\n', encoding="utf-8"
        )
        manuscript = tmp_path / "manuscript.md"
        manuscript.write_text(
            "# Crossing\n\n"
            f"```claim id=c1 source=cross2026 page={page}\n"
            "quote: |\n"
            f"  {self.QUOTE}\n"
            "claim: |\n"
            "  The model was evaluated on a large corpus.\n"
            "```\n",
            encoding="utf-8",
        )
        return tmp_path, manuscript

    def _verify(self, project: Path, manuscript: Path):
        ledger, _ = scan(ScanOptions(manuscript=str(manuscript), root=str(project)))
        assert [c.id for c in ledger.claims] == ["c1"]
        return verify(ledger, ScanOptions(manuscript=str(manuscript), root=str(project)))

    @pytest.mark.parametrize("page", [1, 2])
    def test_a_ledger_pointing_at_either_page_is_verified(self, tmp_path: Path, page: int):
        project, manuscript = self._project(tmp_path, page)
        result = self._verify(project, manuscript)
        assert [f.code for f in result.findings] == ["quote-found"], (
            "a quote that starts on page 1 and ends on page 2 is on both, so a "
            "ledger naming either one is right, not moved"
        )
        assert result.verified == 1
        assert result.moved == 0

    @pytest.mark.parametrize("page", [1, 2])
    def test_the_two_page_span_is_named_in_the_finding(self, tmp_path: Path, page: int):
        project, manuscript = self._project(tmp_path, page)
        result = self._verify(project, manuscript)
        message = result.findings[0].message
        assert "page 1 (running onto page 2)" in message, (
            "a reader told only 'page 1' who finds the sentence continuing on "
            "page 2 has been told a half-truth"
        )

    def test_a_number_on_the_second_half_is_not_called_absent(self, tmp_path: Path):
        """The quote carries 154,391 on page 1 and 40,688 on page 2."""
        project, manuscript = self._project(tmp_path, page=1)
        manuscript.write_text(
            "# Crossing\n\n"
            "```claim id=c1 source=cross2026 page=1\n"
            "quote: |\n"
            "  We evaluated the model on a corpus of 154,391 utterances drawn from\n"
            "  OntoNotes and the EWT. We counted 40,688\n"
            "claim: |\n"
            "  The model was evaluated on a large corpus.\n"
            "```\n",
            encoding="utf-8",
        )
        ledger, _ = scan(ScanOptions(manuscript=str(manuscript), root=str(project)))
        numbers = ledger.claims[0].numbers
        assert numbers == ("154,391", "40,688"), (
            "the fixture must quote one number on each half, or this test proves "
            f"nothing about the second page: {numbers}"
        )
        result = verify(ledger, ScanOptions(manuscript=str(manuscript), root=str(project)))
        codes = [f.code for f in result.findings]
        assert codes == ["quote-found"], (
            "40,688 is on page 2, which the quote runs onto; reporting it "
            f"absent is the high-severity lie: {codes}"
        )
