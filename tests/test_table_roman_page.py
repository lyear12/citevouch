r"""A table claim whose page cell holds a roman numeral.

A book's front matter is numbered i, ii, iii, iv, and its chapters often cite
those pages.  The table dialect read the page cell with a pattern, and a value
that failed the pattern never reached `int()` - the row stopped being a claim,
with no finding at all.  Measured before the fix:

    | c1 | paper | iv | We collected 40,688 examples from the corpus. | note |
    -> [high] no-claim-blocks ... This file has none
    citevouch: 0 claims - 0 verified, 0 moved, 0 missing, exit 1

The fence dialect answered the same value the same way it answers any other
hint it cannot apply:

    ```claim id=c1 source=paper page=iv
    -> [medium] page-unreadable ... claim c1 has a non-numeric page='iv'; the
       hint is ignored and the quote will be located by search
    -> quote-found

So the cell now admits a roman numeral and lets `int()` refuse it.  The
alphabet is i, v, x and l and every run has to be a canonical numeral, so the
words that are spelled with those letters stay words: `ill`, `mix`, `class`,
`civic`, `live` and `x-ray` are not pages, and a cell holding one is still not
a claim.  M and C are left out on purpose - a table's third column is far more
likely to say `class` or `done` than to be a page numbered in the hundreds.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from citevouch.manuscript import parse_manuscript

NL = chr(10)
QUOTE = "We collected 40,688 examples from the corpus."
PAGE = "Preface" + NL + QUOTE + NL
PYTHONPATH = str(Path(__file__).resolve().parents[1] / "src")


def row(page: str) -> str:
    return "| c1 | paper | " + page + " | " + QUOTE + " | note |"


def fenced(page: str) -> str:
    return (
        "```claim id=c1 source=paper page="
        + page
        + NL
        + "quote: |"
        + NL
        + "  "
        + QUOTE
        + NL
        + "```"
        + NL
    )


def parse(*lines: str):
    return parse_manuscript(NL.join(lines) + NL, path="manuscript.md")


def codes(parsed) -> list[str]:
    return [finding.code for finding in parsed.findings]


def _run(root: Path, *argv: str) -> tuple[int, str]:
    env = {**os.environ, "PYTHONPATH": PYTHONPATH, "PYTHONIOENCODING": "utf-8"}
    got = subprocess.run(
        [sys.executable, "-m", "citevouch", *argv],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    return got.returncode, got.stdout + got.stderr


def _project(root: Path, manuscript: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline=chr(10))
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=chr(10)
    )
    (root / "manuscript.md").write_text(manuscript, encoding="utf-8", newline=chr(10))


class TestTheRowIsReadAndTheHintIsRefused:
    @pytest.mark.parametrize(
        "page",
        ["i", "ii", "iii", "iv", "v", "ix", "x", "xii", "xx", "xl", "l", "xc"],
    )
    def test_a_roman_numeral_is_a_hint_that_was_ignored(self, page):
        parsed = parse("Title", "", row(page))
        assert [claim.id for claim in parsed.claims] == ["c1"], page
        assert codes(parsed) == ["page-unreadable"], page

    @pytest.mark.parametrize("page", ["IV", "Iv", "iV"])
    def test_the_case_of_a_numeral_does_not_matter(self, page):
        parsed = parse("Title", "", row(page))
        assert [claim.id for claim in parsed.claims] == ["c1"], page
        assert codes(parsed) == ["page-unreadable"], page

    @pytest.mark.parametrize(
        "page", ["iv-vii", "iv - vii", "ii\u2013iv", "i\u2014v", "iv, vii"]
    )
    def test_a_run_of_numerals_is_read_as_one_hint(self, page):
        parsed = parse("Title", "", row(page))
        assert [claim.id for claim in parsed.claims] == ["c1"], page
        assert codes(parsed) == ["page-unreadable"], page

    @pytest.mark.parametrize("prefix", ["p. ", "pp. ", "page ", "pages ", "P. "])
    def test_the_prefix_still_applies_to_a_numeral(self, prefix):
        parsed = parse("Title", "", row(prefix + "iv"))
        assert [claim.id for claim in parsed.claims] == ["c1"], prefix
        assert codes(parsed) == ["page-unreadable"], prefix

    def test_the_fence_dialect_answers_the_same_value_the_same_way(self):
        # The property that was missing: one value, one answer, whichever
        # dialect the author wrote it in.
        for page in ["iv", "IV", "iv-vii", "xii"]:
            parsed = parse_manuscript(fenced(page), path="manuscript.md")
            table = parse("Title", "", row(page))
            assert codes(parsed) == codes(table) == ["page-unreadable"], page

    def test_a_row_that_was_alone_no_longer_says_the_file_is_empty(self):
        parsed = parse("Title", "", row("iv"))
        assert "no-claim-blocks" not in codes(parsed)


class TestWhatMustStillBeRefused:
    @pytest.mark.parametrize(
        "cell",
        [
            "ill",
            "mix",
            "class",
            "civic",
            "live",
            "x-ray",
            "1 to 2",
            "1.5",
            "score",
            "iv.",
            "mm",
            "cd",
        ],
    )
    def test_a_cell_that_is_a_word_is_still_not_a_claim(self, cell):
        parsed = parse("Title", "", row(cell))
        assert parsed.claims == [], cell

    def test_a_results_table_is_no_more_a_claim_than_it_was(self):
        # `score` is not a numeral and not a number, so this row was never
        # claim-shaped and the header rule never had to name it.  What matters
        # is that the roman branch did not make it one.
        lines = [
            "| model | setting | score | f1 | note |",
            "|---|---|---|---|---|",
            "| bert | base | score | 88 | on par |",
        ]
        parsed = parse(*lines)
        assert parsed.claims == []
        assert codes(parsed) == []


class TestTheVerdictOnAProject:
    def test_the_page_is_found_and_the_hint_is_named(self, tmp_path):
        root = tmp_path / "proj"
        _project(root, "## Methods" + NL + NL + row("iv") + NL)
        code, report = _run(root, "check", "manuscript.md", "--root", str(root))
        assert "no-claim-blocks" not in report
        assert "page-unreadable" in report
        assert "quote-found" in report
        assert "1 claim — 1 verified" in report
        assert code == 0

    def test_scan_records_the_claim(self, tmp_path):
        root = tmp_path / "proj"
        _project(root, "## Methods" + NL + NL + row("iv-vii") + NL)
        code, report = _run(root, "scan", "manuscript.md", "--root", str(root))
        assert "no-claim-blocks" not in report
        assert "wrote" in report and "1 claim" in report
        assert code == 0
