"""A quote that runs across a page break, proved against a real paper.

The synthetic tests in `test_cross_page.py` pin the mechanism.  These pin the
premise: that a real extractor really does cut a real sentence in half, and
that this tool now reads across that cut.  Without them the mechanism could be
correct and the situation could be imaginary.

The fixture is one of the two PDFs the demo already ships, at a page boundary
the demo does not otherwise exercise.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from citevouch.matching import find_in_pages
from citevouch.sources import extract_pages

ROOT = Path(__file__).resolve().parent.parent
PAPER = ROOT / "demo" / "papers" / "2026_VanEecke-Beuls_CoNLL2026_large-scale-CxG.pdf"


@pytest.fixture(scope="module")
def pages():
    """The real pages, extracted once."""
    extracted, problem = extract_pages(str(PAPER), str(ROOT / "demo"), use_cache=False)
    assert problem is None, f"the fixture paper could not be read: {problem.message}"
    return extracted


def _across(pages, first: int, second: int, words: int = 8) -> tuple[str, str]:
    """The tail of one page plus the head of the next, as an author would quote it."""
    left = pages[first - 1].text.split()
    right = pages[second - 1].text.split()
    return " ".join(left[-words:]), " ".join(right[:words])


class TestA_real_page_break:
    def test_the_fixture_paper_really_splits_sentences_at_page_edges(self, pages):
        """If this ever stops being true the other test stops proving anything.

        A PDF whose pages all end on a full stop would make the cross-page test
        a tautology.  Assert the premise directly.
        """
        left, right = _across(pages, 6, 7)
        assert left, "page 6 should have text"
        assert right, "page 7 should have text"
        assert not left.rstrip().endswith("."), (
            "page 6 ends on a full stop in this fixture, so it is not a page "
            "break anyone would quote across"
        )

    def test_a_sentence_that_crosses_pages_6_and_7_is_found(self, pages):
        left, right = _across(pages, 6, 7)
        quote = f"{left} {right}"
        match = find_in_pages(quote, pages)
        assert match.found, f"a real quote across pages 6-7 was reported missing: {quote!r}"
        assert match.page == 6
        assert match.spans_to == 7

    def test_the_other_direction_is_found_too(self, pages):
        """The pairing must not be hard-wired to one page of one fixture."""
        left, right = _across(pages, 3, 4)
        match = find_in_pages(f"{left} {right}", pages)
        assert match.found
        assert (match.page, match.spans_to) == (3, 4)
