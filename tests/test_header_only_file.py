"""A file whose only table row is the table's header checked nothing.

The header row was recognised last round: a table row directly above the
``|---|`` delimiter is the table's header, its cells are column labels, and it
is not a claim.  That fix reported ``claim-table-header`` and stopped counting
the row as a claim - which is right.

What it also did, without anyone asking, was make the file exit 0.  ``scan``
and ``verify`` decide whether a run checked nothing with
``ParseResult.nothing_to_check``, which asks whether any finding's code starts
with ``claim-``: the premise is that every such code explains a block the
author wrote and the parser could not use, so the reader already knows why
nothing was checked.  ``claim-table-header`` starts with ``claim-`` and is not
that: it says the line is not a block at all.  Measured before the fix::

    | model | setting | 84 | We report the mean over five seeds. | note |
    |-------|---------|----|------------------------------------|------|
    -> [medium] claim-table-header at manuscript.md:1 (model): ...
    -> citevouch: 0 claims — 0 verified, 0 moved, 0 missing
    -> worst severity: medium, exit 0

while the same project with an empty manuscript exited 1 with
``no-claim-blocks``.  A CI gate over a manuscript whose header happened to be
claim-shaped passed while nothing at all was verified.

The second half is the sentence that followed.  With the exit code fixed, the
``no-claim-blocks`` near-miss list still pointed at the header row and said the
row was "inside a blockquote, a list item or an indent, where Markdown renders
it as a code sample rather than a table" - about a row at the left margin.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from citevouch.manuscript import parse_manuscript

NL = chr(10)
PIPE = "|"
PYTHONPATH = str(Path(__file__).resolve().parents[1] / "src")

SENTENCE = "We report the mean over five seeds and the standard deviation across them."
PAGE = "Results" + NL + SENTENCE + NL


def row(*cells: str) -> str:
    return PIPE + PIPE.join(f" {cell} " for cell in cells) + PIPE


DELIM = PIPE + PIPE.join("------" for _ in range(5)) + PIPE
HEADER = row("model", "setting", "84", SENTENCE, "note")


def _project(root: Path, manuscript: str) -> None:
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'setting = "page.txt"' + NL + 'paper = "page.txt"' + NL,
        encoding="utf-8",
        newline=NL,
    )
    (root / "manuscript.md").write_text(manuscript, encoding="utf-8", newline=NL)


def _run(root: Path, *argv: str) -> tuple[int, str]:
    done = subprocess.run(
        [sys.executable, "-m", "citevouch", *argv],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=root,
        env={
            **os.environ,
            "PYTHONPATH": PYTHONPATH,
            "PYTHONIOENCODING": "utf-8",
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        },
    )
    return done.returncode, done.stdout + done.stderr


class TestAFileThatCheckedNothingDoesNotExitClean:
    def test_the_header_alone_is_not_a_clean_run(self, tmp_path: Path) -> None:
        _project(tmp_path, HEADER + NL + DELIM + NL)
        code, output = _run(tmp_path, "check", "manuscript.md", "--root", str(tmp_path))
        assert code == 1, output
        assert "no-claim-blocks" in output
        assert "0 claims" in output
        # The header finding is still true and still printed: the reader is told
        # what the line is *and* that nothing was checked.
        assert "claim-table-header" in output

    def test_the_empty_file_still_says_the_same_thing(self, tmp_path: Path) -> None:
        """The two shapes must agree: both checked nothing, both exit 1."""
        _project(tmp_path, "")
        code, output = _run(tmp_path, "check", "manuscript.md", "--root", str(tmp_path))
        assert code == 1, output
        assert "no-claim-blocks" in output

    def test_scan_refuses_it_too(self, tmp_path: Path) -> None:
        _project(tmp_path, HEADER + NL + DELIM + NL)
        code, output = _run(tmp_path, "scan", "manuscript.md", "--root", str(tmp_path))
        assert code == 1, output
        assert "no-claim-blocks" in output

    def test_a_refused_block_still_explains_itself(self) -> None:
        """The premise of the rule, kept: a refused block needs no second finding."""
        parsed = parse_manuscript(
            "<!-- claim: -->" + NL + ">> " + SENTENCE + NL, path="manuscript.md"
        )
        assert [finding.code for finding in parsed.findings] == ["claim-uncheckable"]
        assert parsed.nothing_to_check is False

    def test_a_header_does_not_excuse_a_file_with_nothing_else(self) -> None:
        parsed = parse_manuscript(HEADER + NL + DELIM + NL, path="manuscript.md")
        assert [finding.code for finding in parsed.findings] == ["claim-table-header"]
        assert parsed.nothing_to_check is True


class TestTheSentenceDoesNotBlameTheWrongConstruct:
    def test_a_row_at_the_left_margin_is_not_called_indented(self, tmp_path: Path) -> None:
        _project(tmp_path, HEADER + NL + DELIM + NL)
        _code, output = _run(tmp_path, "check", "manuscript.md", "--root", str(tmp_path))
        assert "inside a blockquote, a list item or an indent" not in output
        assert "the table row is inside" not in output

    def test_a_real_indented_row_is_still_named(self, tmp_path: Path) -> None:
        """The indent sentence is true of an indented row and must survive."""
        _project(tmp_path, "    " + HEADER + NL + DELIM + NL)
        _code, output = _run(tmp_path, "check", "manuscript.md", "--root", str(tmp_path))
        assert "indent" in output

    @pytest.mark.parametrize(
        "table",
        [
            HEADER + NL + DELIM + NL,
            HEADER + NL + DELIM + NL + row("bert", "base", "84", "88", "90") + NL,
        ],
        ids=["header-only", "header-and-data"],
    )
    def test_no_output_names_a_construct_that_is_not_there(
        self, tmp_path: Path, table: str
    ) -> None:
        _project(tmp_path, table)
        _code, output = _run(tmp_path, "check", "manuscript.md", "--root", str(tmp_path))
        assert "blockquote" not in output


class TestWhatMustStillPass:
    def test_a_header_above_a_real_claim_is_not_a_failure(self, tmp_path: Path) -> None:
        manuscript = (
            row("id", "source", "page", "quote", "claim")
            + NL
            + DELIM
            + NL
            + row("c1", "paper", "1", SENTENCE, "note")
            + NL
        )
        _project(tmp_path, manuscript)
        code, output = _run(tmp_path, "check", "manuscript.md", "--root", str(tmp_path))
        assert code == 0, output
        assert "1 claim — 1 verified" in output
