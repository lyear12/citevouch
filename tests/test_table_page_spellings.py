r"""The table dialect deletes a row whose page cell it cannot spell.

A page hint reaches the claim as a string, and `int()` either accepts it or
reports `page-unreadable` - the quote is located by search either way, so the
claim is still judged.  That is what the fence dialect does:

    ```claim id=c1 source=paper page=p. 3
    ```
    -> [medium] page-unreadable ... the hint is ignored and the quote will be
       located by search
    -> quote-found

The table dialect has a *pattern* for the page cell, and a value that fails the
pattern does not reach `int()` at all - the whole row stops being a claim, with
no finding.  Measured before the fix, in a project whose page holds the quote:

    | c1 | paper | p. 3 | We collected 40,688 examples from the corpus. | note |
    -> [high] no-claim-blocks ... This file has none
    citevouch: 0 claims - 0 verified, 0 moved, 0 missing, exit 1

The same for `1,2`, `pp. 3-4` and `page 5`.  The author is told the file holds
no claim blocks; it holds one.

So the cell has to admit the spellings a page hint actually takes, and let
`int()` be the thing that refuses them.  What it must keep refusing is a cell
that is a word, because a results table's third column is a column of numbers
and a five-cell row with a number in it is already too easy to mistake for a
claim.
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


def parse(*lines: str):
    return parse_manuscript(NL.join(lines) + NL, path="manuscript.md")


def codes(parsed) -> list[str]:
    return [finding.code for finding in parsed.findings]


def _run(root: Path, *argv: str) -> tuple[int, str]:
    env = {**os.environ, "PYTHONPATH": PYTHONPATH, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, "-m", "citevouch", *argv],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    return proc.returncode, proc.stdout + proc.stderr


def _project(root: Path, page: str) -> None:
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline=chr(10))
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=chr(10)
    )
    (root / "manuscript.md").write_text(
        "Title" + NL + NL + row(page) + NL, encoding="utf-8", newline=chr(10)
    )


class TestTheRowIsStillRead:
    @pytest.mark.parametrize(
        "page",
        ["1,2", "1, 2", "p. 3", "p.3", "pp. 3-4", "page 5", "pages 6-7", "P. 3", "Page 5"],
    )
    def test_a_page_spelling_the_pattern_did_not_know_still_reaches_int(self, page):
        parsed = parse("Title", "", row(page))
        assert [claim.id for claim in parsed.claims] == ["c1"]
        # The hint is refused, not the claim: `int()` cannot use it and says so.
        assert codes(parsed) == ["page-unreadable"]

    def test_the_fence_dialect_answers_the_same_value_the_same_way(self):
        for page in ("1,2", "p. 3", "pp. 3-4", "page 5"):
            fenced = (
                "Title"
                + NL
                + NL
                + "```claim id=c1 source=paper page="
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
            parsed = parse_manuscript(fenced, path="manuscript.md")
            table = parse("Title", "", row(page))
            assert codes(parsed) == codes(table) == ["page-unreadable"], page

    def test_a_row_that_was_alone_no_longer_says_the_file_is_empty(self):
        parsed = parse("Title", "", row("p. 3"))
        assert "no-claim-blocks" not in codes(parsed)


class TestWhatMustStillBeRefused:
    # `iv` and `iv-vii` used to be listed here.  They are roman numerals, and a
    # book's front matter is numbered in them, so refusing them deleted the row
    # instead of naming an ignored hint - the same defect this file is about,
    # one alphabet over.  `tests/test_table_roman_page.py` covers them now.
    @pytest.mark.parametrize(
        "cell",
        ["score", "f1", "done", "n/a", "1 to 2", "1.5", "+1", "-1"],
    )
    def test_a_cell_that_is_a_word_is_still_not_a_claim(self, cell):
        parsed = parse("Title", "", row(cell))
        assert parsed.claims == []

    def test_a_results_table_is_no_more_a_claim_than_it_was(self):
        # The header's third cell is a number here, which is the shape that
        # already read as a claim before any of this - so it is the shape the
        # page cell has to keep refusing.  A header whose third cell is a word
        # (`score`) never matched at all and is not affected either way.
        lines = [
            "| model | setting | 84 | f1 | note |",
            "|---|---|---|---|---|",
            "| bert | base | 84 | 88 | on par |",
        ]
        parsed = parse(*lines)
        assert "claim-table-header" in codes(parsed)
        assert [claim.id for claim in parsed.claims] == ["bert"]

    def test_a_cell_of_a_text_column_is_still_not_a_page(self):
        lines = [
            "| item | owner | status | note | extra |",
            "| a | alice | done | n/a | x |",
        ]
        assert parse(*lines).claims == []


class TestTheVerdictOnAProject:
    def test_a_page_hint_the_tool_cannot_use_no_longer_deletes_the_claim(self, tmp_path):
        _project(tmp_path, "p. 3")
        code, output = _run(tmp_path, "check", "manuscript.md", "--root", ".")
        assert "no-claim-blocks" not in output
        assert "[medium] page-unreadable" in output
        assert "[info] quote-found" in output
        assert "1 claim — 1 verified, 0 moved, 0 missing" in output
        assert code == 0

    def test_the_scan_names_the_same_thing(self, tmp_path):
        _project(tmp_path, "1,2")
        code, output = _run(tmp_path, "scan", "manuscript.md", "--root", ".")
        assert "no-claim-blocks" not in output
        assert "wrote citevouch.lock.json (1 claim)" in output
        assert code == 0
