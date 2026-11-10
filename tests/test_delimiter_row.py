"""A delimiter row is punctuation, not a claim.

GFM lets a delimiter cell be a single dash, so `|-|-|-|-|-|` is a legal
delimiter row for a five-column table.  It is also, to the table-claim pattern,
a five-cell row whose third cell is `-`: the id is `-`, the source is `-`, the
page is `-`.  Measured before this fix, on a table that is correct::

    | id | source | page | quote | claim |
    |-|-|-|-|-|
    | c1 | paper | 1 | We report the mean over five seeds ... | note |
    -> [high] source-missing at manuscript.md:2 (-): claim - names source='-'
       but no entry in sources.toml and no --source path resolves it
    -> citevouch: 2 claims — 1 verified, 0 moved, 1 missing
    -> worst severity: high, exit 1

The parser already knew the answer: 0.22.70 added `_is_delimiter_row` so a
header row could be recognised by the line above it.  It asked that question
about the row *above* the delimiter and never about the delimiter itself.

Three readers had to learn it, and each was measured separately:

* the claim reader, which accepted the row as a claim named `-`;
* `_unread_findings`, which called it a claim block "inside a blockquote, a
  list item or an indent" - three things it is not;
* `scan._no_claim_blocks_finding`'s near-miss list, which said the same thing
  about it in a different command.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from citevouch.manuscript import parse_manuscript

NL = chr(10)
PIPE = "|"
PYTHONPATH = str(Path(__file__).resolve().parents[1] / "src")

SENTENCE = "We report the mean over five seeds and the standard deviation across them."
PAGE = "Results" + NL + SENTENCE + NL


def row(*cells: str) -> str:
    return PIPE + PIPE.join(f" {cell} " for cell in cells) + PIPE


def delim(*widths: str) -> str:
    return PIPE + PIPE.join(widths) + PIPE


HEADER = row("id", "source", "page", "quote", "claim")
BODY = row("c1", "paper", "1", SENTENCE, "note")


def _project(root: Path, manuscript: str) -> None:
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL,
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


class TestTheDelimiterIsNotAClaim:
    def test_a_single_dash_delimiter_produces_no_claim(self) -> None:
        parsed = parse_manuscript(
            HEADER + NL + delim("-", "-", "-", "-", "-") + NL + BODY, path="manuscript.md"
        )
        assert [claim.id for claim in parsed.claims] == ["c1"]
        assert parsed.findings == []

    def test_a_three_dash_delimiter_is_also_punctuation(self) -> None:
        parsed = parse_manuscript(
            HEADER + NL + delim("---", "---", "---", "---", "---") + NL + BODY,
            path="manuscript.md",
        )
        assert [claim.id for claim in parsed.claims] == ["c1"]

    def test_an_aligned_single_dash_delimiter_is_punctuation(self) -> None:
        parsed = parse_manuscript(
            HEADER + NL + delim(":-", "-:", ":-:", "-", "---") + NL + BODY, path="manuscript.md"
        )
        assert [claim.id for claim in parsed.claims] == ["c1"]

    def test_a_bare_delimiter_is_not_named_a_claim_block(self) -> None:
        parsed = parse_manuscript(delim("-", "-", "-", "-", "-") + NL, path="manuscript.md")
        assert parsed.claims == []
        assert [finding.code for finding in parsed.findings] == []


class TestTheVerdictOnAProject:
    def test_a_table_with_a_single_dash_delimiter_passes(self, tmp_path: Path) -> None:
        _project(tmp_path, HEADER + NL + delim("-", "-", "-", "-", "-") + NL + BODY + NL)
        code, output = _run(tmp_path, "check", "manuscript.md", "--root", str(tmp_path))
        assert code == 0, output
        assert "1 claim — 1 verified" in output
        assert "source-missing" not in output

    def test_scan_agrees_with_check(self, tmp_path: Path) -> None:
        _project(tmp_path, HEADER + NL + delim("-", "-", "-", "-", "-") + NL + BODY + NL)
        code, output = _run(tmp_path, "scan", "manuscript.md", "--root", str(tmp_path))
        assert code == 0, output
        assert "source-missing" not in output

    def test_a_file_holding_only_a_delimiter_does_not_name_a_construct(
        self, tmp_path: Path
    ) -> None:
        _project(tmp_path, delim("-", "-", "-", "-", "-") + NL)
        code, output = _run(tmp_path, "check", "manuscript.md", "--root", str(tmp_path))
        assert code == 1, output
        assert "no-claim-blocks" in output
        assert "blockquote" not in output
        assert "indent" not in output


class TestWhatMustStillBeNamed:
    def test_a_really_indented_row_is_still_reported(self, tmp_path: Path) -> None:
        """The sentence this fix removed is true of an indented row."""
        _project(tmp_path, "    " + HEADER + NL + "    " + delim("-", "-", "-", "-", "-") + NL)
        _code, output = _run(tmp_path, "check", "manuscript.md", "--root", str(tmp_path))
        assert "no-claim-blocks" in output

    def test_a_claim_row_below_the_delimiter_is_still_read(self, tmp_path: Path) -> None:
        _project(tmp_path, HEADER + NL + delim("-", "-", "-", "-", "-") + NL + BODY + NL)
        code, output = _run(tmp_path, "check", "manuscript.md", "--root", str(tmp_path))
        assert code == 0, output
        assert "quote-found" in output

    def test_a_dash_cell_inside_a_real_claim_row_survives(self) -> None:
        """A row whose page is `-` is a claim with no page hint, not a delimiter."""
        manuscript = (
            row("id", "source", "page", "quote", "claim")
            + NL
            + delim("---", "---", "---", "---", "---")
            + NL
            + row("c1", "paper", "-", SENTENCE, "note")
        )
        parsed = parse_manuscript(manuscript, path="manuscript.md")
        assert [claim.id for claim in parsed.claims] == ["c1"]


class TestTheHeaderRuleAlsoRefusesTheDelimiter:
    def test_a_delimiter_is_not_a_header_of_the_row_below_it(self) -> None:
        """With the delimiter guard removed, the delimiter becomes a header.

        The claim reader refuses the delimiter first, so this can only be seen
        by asking `_is_header_row` directly - which is what a future caller
        would do.
        """
        from citevouch.manuscript import _is_header_row

        claim_shaped = row("model", "setting", "84", "the quote", "note")
        dash = delim("-", "-", "-", "-", "-")
        # Two delimiter rows in a row: the second would be "the header of the
        # row below it" under the rule without the delimiter guard, which is a
        # sentence about punctuation. This is the only input where the guard
        # changes an answer, which is why it is the one the test uses.
        lines = [claim_shaped, dash, dash, BODY]
        assert _is_header_row(lines, 1) is False
        # The row above the first delimiter is the header, which is the rule.
        assert _is_header_row(lines, 0) is True
