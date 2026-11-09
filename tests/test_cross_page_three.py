"""A quote that runs across more than one page break.

`_page_pairs` stitched *pairs* of adjacent pages, so a quote was found when it
crossed one break and reported missing when it crossed two.  Measured on a
three-page source whose sentence starts on page 2 and ends on page 4:

    [high] quote-missing at manuscript.md:1 (c1): We collected a very large
    number of examples from the corpus and then filtered them by ha…
    — quote not found in page.txt

The words are there, verbatim, in order, and the tool told the author they are
missing.  A reader turning from page 2 to page 4 sees the sentence; only a
program that reads two pages at a time cannot.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENV = {
    **os.environ,
    "PYTHONPATH": str(ROOT / "src"),
    "PYTHONIOENCODING": "utf-8",
}
FORM_FEED = chr(12)
NL = chr(10)

PAGE_ONE = "An opening page that has nothing to do with the claim at all."
PAGE_TWO = "We collected a very large number of examples from the corpus"
PAGE_THREE = "and then filtered them by hand, and also deduplicated the result"
PAGE_FOUR = "and finally split it into a training and a held out portion."
PAGE_FIVE = "The appendix lists every file we touched along the way."

TWO_PAGES = f"{PAGE_TWO} {PAGE_THREE}"
THREE_PAGES = f"{PAGE_TWO} {PAGE_THREE} {PAGE_FOUR}"
FOUR_PAGES = f"{PAGE_TWO} {PAGE_THREE} {PAGE_FOUR} {PAGE_FIVE}"

PAGES = [PAGE_ONE, PAGE_TWO, PAGE_THREE, PAGE_FOUR, PAGE_FIVE]


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "citevouch", *args, "--root", str(root)],
        cwd=ROOT,
        env=ENV,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )


def _project(tmp_path: Path, pages: list[str], quote: str, page: int | None = None) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    (root / "page.txt").write_text(FORM_FEED.join(pages), encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    opening = "```claim id=c1 source=paper"
    if page is not None:
        opening += f" page={page}"
    lines = [opening, "quote: |", f"  {quote}", "```", ""]
    (root / "manuscript.md").write_text(NL.join(lines), encoding="utf-8", newline=NL)
    return root


def _codes(proc: subprocess.CompletedProcess[str]) -> list[str]:
    out = []
    for line in proc.stdout.splitlines():
        if line.startswith("[") and "] " in line:
            out.append(line.split("] ", 1)[1].split(" ", 1)[0].rstrip(":"))
    return out


def _pages(*texts: str):
    from citevouch.matching import PageText

    return [PageText(number=index + 1, text=text) for index, text in enumerate(texts)]


class TestAQuoteThatCrossesTwoBreaksIsStillOnThePage:
    def test_three_pages_is_found(self, tmp_path: Path) -> None:
        root = _project(tmp_path, PAGES, THREE_PAGES, page=2)
        proc = _run(root, "check", "manuscript.md")
        assert "quote-found" in _codes(proc), proc.stdout
        assert "quote-missing" not in _codes(proc)

    def test_the_message_names_every_page_it_runs_onto(self, tmp_path: Path) -> None:
        root = _project(tmp_path, PAGES, THREE_PAGES, page=2)
        proc = _run(root, "check", "manuscript.md")
        assert "running onto pages 3 and 4" in proc.stdout, proc.stdout

    def test_the_recorded_middle_page_is_not_a_move(self, tmp_path: Path) -> None:
        """The ledger may point at the middle of the run.

        A three-page quote is on pages 2, 3 and 4.  Editing the ledger to say 3
        is not a correction the author needs to make, and calling it one would
        send them to change a number that was already right.
        """
        root = _project(tmp_path, PAGES, THREE_PAGES, page=3)
        proc = _run(root, "check", "manuscript.md")
        assert "quote-moved" not in _codes(proc), proc.stdout
        assert "quote-found" in _codes(proc)

    def test_a_page_outside_the_run_is_a_move(self, tmp_path: Path) -> None:
        root = _project(tmp_path, PAGES, THREE_PAGES, page=1)
        proc = _run(root, "check", "manuscript.md")
        assert "quote-moved" in _codes(proc), proc.stdout

    def test_four_pages_is_found(self, tmp_path: Path) -> None:
        root = _project(tmp_path, PAGES, FOUR_PAGES, page=2)
        proc = _run(root, "check", "manuscript.md")
        assert "quote-found" in _codes(proc), proc.stdout

    def test_a_number_on_the_middle_page_of_the_run_is_not_absent(self, tmp_path: Path) -> None:
        """The numbers check must read every page of the run, not only the ends.

        Two figures, so the check cannot pass by finding no page at all: 9,800
        is printed on page 2 (an end) and 154,391 on page 3 (the middle).  A
        fix that reads only the first and the last page still finds 9,800,
        concludes the pages are readable, and reports 154,391 absent - a number
        the author can see in the middle of the run.
        """
        from citevouch.matching import find_in_pages
        from citevouch.verify import _number_checks

        page_2 = "We collected 9,800 examples from the corpus, all of them real"
        page_3 = "and then filtered the 154,391 examples by hand before training"
        page_4 = "and finally split them into a training and a held out portion."
        quote = f"{page_2} {page_3} {page_4}"
        pages = _pages(PAGE_ONE, page_2, page_3, page_4, PAGE_FIVE)

        match = find_in_pages(quote, pages)
        assert match.spanned == (2, 3, 4), match.spanned

        class _Claim:
            id = "c1"
            path = "manuscript.md"
            line = 1
            numbers = ("9,800", "154,391")

        found = _number_checks(_Claim(), pages, match.spanned)
        assert found == [], [f.message for f in found]

    def test_a_number_on_the_first_page_of_the_run_is_not_absent(self, tmp_path: Path) -> None:
        pages = [
            PAGE_ONE,
            "We collected 154,391 examples from the corpus",
            "and then filtered them by hand before training anything at all",
            "and finally split them into a training and a held out portion.",
            PAGE_FIVE,
        ]
        quote = (
            "We collected 154,391 examples from the corpus "
            "and then filtered them by hand before training anything at all "
            "and finally split them into a training and a held out portion."
        )
        root = _project(tmp_path, pages, quote, page=2)
        proc = _run(root, "check", "manuscript.md")
        assert "number-absent-in-quote" not in _codes(proc), proc.stdout


class TestTheRunIsEveryPageItTouches:
    def test_a_three_page_run_lists_all_three(self) -> None:
        from citevouch.matching import find_in_pages

        match = find_in_pages(THREE_PAGES, _pages(*PAGES))
        assert match.found
        assert (match.page, match.spans_to) == (2, 4)
        assert match.spanned == (2, 3, 4)

    def test_a_two_page_run_lists_both(self) -> None:
        from citevouch.matching import find_in_pages

        match = find_in_pages(TWO_PAGES, _pages(*PAGES))
        assert match.spanned == (2, 3)

    def test_a_one_page_match_spans_nothing_else(self) -> None:
        from citevouch.matching import find_in_pages

        match = find_in_pages(PAGE_THREE, _pages(*PAGES))
        assert match.spanned == (3,)


class TestWhatStillWorksOnTwoPages:
    def test_the_pair_case_says_page_then_onto(self, tmp_path: Path) -> None:
        root = _project(tmp_path, PAGES, TWO_PAGES, page=2)
        proc = _run(root, "check", "manuscript.md")
        assert "running onto page 3" in proc.stdout, proc.stdout

    def test_a_single_page_quote_carries_no_span(self, tmp_path: Path) -> None:
        root = _project(tmp_path, PAGES, PAGE_THREE, page=3)
        proc = _run(root, "check", "manuscript.md")
        assert "running onto" not in proc.stdout


class TestARunLongerThanTheLimit:
    def test_the_limit_is_at_least_a_real_paragraph(self) -> None:
        from citevouch.matching import MAX_STITCHED_PAGES

        assert MAX_STITCHED_PAGES >= 4

    def test_the_stitcher_offers_every_run_length_up_to_it(self) -> None:
        from citevouch.matching import MAX_STITCHED_PAGES, _page_runs

        lengths = {len(spanned) for _page, _last, spanned in _page_runs(_pages(*PAGES))}
        assert lengths == set(range(2, min(MAX_STITCHED_PAGES, len(PAGES)) + 1))

    def test_the_hinted_page_is_tried_first_within_a_length(self) -> None:
        """The hint breaks ties; it does not outrank a shorter run.

        Hinting page 4 and letting the hint win outright made a run of pages
        4-5 get tried before pages 2-3, and a four-page run that merely
        contains the quote beat the three pages it lives on.
        """
        from citevouch.matching import _page_runs

        runs = list(_page_runs(_pages(*PAGES), page_hint=4))
        assert runs[0][0].number == 4
        assert len(runs[0][2]) == 2, "a two-page run must come before any longer one"

    @pytest.mark.parametrize("length", [2, 3, 4])
    def test_a_run_of_that_length_is_offered(self, length: int) -> None:
        from citevouch.matching import _page_runs

        lengths = {len(spanned) for _page, _last, spanned in _page_runs(_pages(*PAGES))}
        assert length in lengths

    def test_a_longer_run_never_wins_over_a_shorter_one(self) -> None:
        """The size of the run is a claim about the document.

        A quote on pages 2-4 attributed to pages 1-4 sends the author to a page
        that does not contain the start of the sentence.
        """
        from citevouch.matching import find_in_pages

        match = find_in_pages(THREE_PAGES, _pages(*PAGES), page_hint=1)
        assert match.spanned == (2, 3, 4)
