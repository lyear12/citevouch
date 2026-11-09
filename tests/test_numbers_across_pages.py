"""A quotation whose figures are printed across the pages it runs over."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"}
NL = chr(10)
FF = chr(12)

PAGES = [
    "An opening page with nothing to do with the claim at all.",
    "We collected a very large number of examples from the corpus",
    "and then filtered the 154,391 examples by hand before training",
    "and finally split them into a training and a held out portion.",
    "The appendix lists every file we touched along the way.",
]
QUOTE = (
    "We collected a very large number of examples from the corpus "
    "and then filtered the 154,391 examples by hand before training "
    "and finally split them into a training and a held out portion."
)
WRONG_QUOTE = QUOTE.replace("154,391", "987,654")


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "citevouch", *args, "--root", str(root)],
        cwd=ROOT,
        env=ENV,
        capture_output=True,
        encoding="utf-8",
    )


def _codes(proc: subprocess.CompletedProcess[str]) -> list[str]:
    """The finding codes a run printed, in order. Each line is `[sev] code at ...`."""
    out = []
    for line in proc.stdout.splitlines():
        if line.startswith("[") and "] " in line:
            out.append(line.split("] ", 1)[1].split(" ", 1)[0])
    return out


def _project(tmp_path: Path, pages: list[str], quote: str, hint: str = "2") -> Path:
    root = tmp_path / "p"
    root.mkdir(parents=True, exist_ok=True)
    (root / "page.txt").write_text(FF.join(pages), encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    body = "```claim id=c1 source=paper" + (f" page={hint}" if hint else "") + NL
    body += "quote: |" + NL
    body += "  " + quote + NL
    body += "```" + NL
    (root / "manuscript.md").write_text(body, encoding="utf-8", newline=NL)
    return root


class TestTheFigureIsOnAMiddlePage:
    """The words match across the run, so the figures have to be read there too.

    Before the run pass existed, the numbers tier read one page at a time.  The
    same sentence with the right figures was found across pages 2-4, and with a
    wrong figure on page 3 it was reported `quote-missing` - a fabricated
    quotation - because no single page held the whole sentence.
    """

    def test_a_wrong_figure_is_named_not_called_missing(self, tmp_path: Path) -> None:
        root = _project(tmp_path, PAGES, WRONG_QUOTE)
        check = _run(root, "check", "manuscript.md")
        assert check.returncode == 1
        assert _codes(check) == ["number-absent-in-quote"]
        assert "quote-missing" not in check.stdout

    def test_the_finding_names_every_page_of_the_run(self, tmp_path: Path) -> None:
        root = _project(tmp_path, PAGES, WRONG_QUOTE)
        check = _run(root, "check", "manuscript.md")
        assert "pages 2, 3 and 4 of the source do not contain that number" in check.stdout

    def test_the_right_figures_are_still_found(self, tmp_path: Path) -> None:
        root = _project(tmp_path, PAGES, QUOTE)
        check = _run(root, "check", "manuscript.md")
        assert check.returncode == 0
        assert "quote found on page 2 (running onto pages 3 and 4)" in check.stdout

    def test_the_figure_is_printed_on_the_middle_page_only(self, tmp_path: Path) -> None:
        pages = list(PAGES)
        pages[1] = "We collected a very large number of examples from the corpus"
        assert "154,391" in pages[2]
        root = _project(tmp_path, pages, QUOTE)
        check = _run(root, "check", "manuscript.md")
        assert check.returncode == 0
        assert "number-absent-in-quote" not in check.stdout


class TestTheSinglePageCaseIsUnchanged:
    def test_a_wrong_figure_on_one_page_still_names_that_page(self, tmp_path: Path) -> None:
        pages = ["We collected 9,800 examples from the corpus in total."]
        quote = "We collected 154,391 examples from the corpus in total."
        root = _project(tmp_path, pages, quote, hint="1")
        check = _run(root, "check", "manuscript.md")
        assert check.returncode == 1
        assert "page 1 of the source does not contain that number" in check.stdout
        assert "or" not in check.stdout.split("does not contain")[0].split("quote says")[-1]

    def test_a_quote_that_fits_one_page_is_never_attributed_to_a_run(
        self, tmp_path: Path
    ) -> None:
        pages = [
            "Nothing here.",
            "We collected 9,800 examples from the corpus in total.",
            "Nothing here either.",
        ]
        quote = "We collected 154,391 examples from the corpus in total."
        root = _project(tmp_path, pages, quote, hint="2")
        check = _run(root, "check", "manuscript.md")
        assert check.returncode == 1
        assert "page 2 of the source does not contain that number" in check.stdout


class TestTheMatchSaysWhichPagesItCovers:
    def test_a_run_records_every_page(self) -> None:
        from citevouch.matching import find_in_pages
        from citevouch.sources import PageText

        pages = [PageText(number=i + 1, text=text) for i, text in enumerate(PAGES)]
        match = find_in_pages(WRONG_QUOTE, pages, 2)
        assert match.tier == "numbers"
        assert match.spanned == (2, 3, 4)
        assert match.spans_to == 4

    def test_a_single_page_records_one_page(self) -> None:
        from citevouch.matching import find_in_pages
        from citevouch.sources import PageText

        pages = [PageText(number=1, text="We collected 9,800 examples in total.")]
        match = find_in_pages("We collected 154,391 examples in total.", pages, None)
        assert match.tier == "numbers"
        assert match.spanned == (1,)
        assert match.spans_to is None

    def test_the_figures_come_from_the_pages_the_match_covers(self) -> None:
        from citevouch.matching import find_in_pages
        from citevouch.sources import PageText

        pages = [PageText(number=i + 1, text=text) for i, text in enumerate(PAGES)]
        match = find_in_pages(WRONG_QUOTE, pages, 2)
        assert match.page_numbers == ("154,391",)


class TestTheRecordedPathAgrees:
    def test_both_verbs_report_the_same_code(self, tmp_path: Path) -> None:
        root = _project(tmp_path, PAGES, WRONG_QUOTE)
        assert _run(root, "scan", "manuscript.md").returncode == 0
        check = _run(root, "check", "manuscript.md")
        recorded = _run(root, "check", "manuscript.md", "--use-recorded")
        live = set(_codes(check))
        stored = set(_codes(recorded))
        assert live == stored
