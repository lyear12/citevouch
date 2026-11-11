"""A table row is a claim whether or not its last cell is followed by a pipe.

GFM makes the leading and trailing pipe of a table row optional.  The dialect
in this repository reads a row only when the trailing pipe is there, and the
row it refuses is not refused loudly: it is a line the parser never looks at.
Measured before this file existed, with the documented header above the row and
the trailing pipe left off:

    alone                   -> [high] no-claim-blocks "a claim block opens with
                               three backticks, the word `claim`, ..." - which
                               is the wrong shape for a row of pipes
    beside one good fence   -> exit 0, "1 claim - 1 verified", and the row's
                               id appears in no finding at all

The same two shapes with the trailing pipe present are read and judged.  So
whether a row of evidence was looked at depended on a character Markdown says
may be left out, and the answer the author got was silence.
"""

from __future__ import annotations

import contextlib
import io
import os

import pytest

from citevouch.cli import main
from citevouch.manuscript import _unread_opener, parse_manuscript

NL = chr(10)
B3 = chr(96) * 3
QUOTE = "The corpus holds 40,688 examples"
TEXT = "The corpus is large."
PAGE = "The corpus holds 40,688 examples of written English." + NL

HEADER = "| id | source | page | quote | claim |" + NL
DELIMITER = "|----|--------|------|-------|-------|" + NL

WITH_TAIL = f"| c1 | paper | 1 | {QUOTE} | {TEXT} |"
WITHOUT_TAIL = f"| c1 | paper | 1 | {QUOTE} | {TEXT}"

GOOD_FENCE = (
    B3 + "claim id=g1 source=paper page=1" + NL + "quote: |" + NL + "  " + QUOTE + NL + B3 + NL
)


def _claims(text):
    return parse_manuscript(text, path="m.md").claims


def _codes(text):
    return [finding.code for finding in parse_manuscript(text, path="m.md").findings]


@pytest.fixture()
def project(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    return root


def _write(root, body):
    (root / "m.md").write_text(body, encoding="utf-8", newline=NL)


def _run(root, *args):
    out, err = io.StringIO(), io.StringIO()
    old = os.getcwd()
    os.chdir(root)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(args))
    finally:
        os.chdir(old)
    return code, out.getvalue() + err.getvalue()


class TestTheRowIsReadEitherWay:
    @pytest.mark.parametrize("row", [WITH_TAIL, WITHOUT_TAIL])
    def test_it_is_one_claim(self, row):
        assert len(_claims(row + NL)) == 1

    @pytest.mark.parametrize("row", [WITH_TAIL, WITHOUT_TAIL])
    def test_the_columns_land_in_the_same_places(self, row):
        (claim,) = _claims(row + NL)
        assert (claim.id, claim.source, claim.page, claim.quote, claim.text) == (
            "c1",
            "paper",
            1,
            QUOTE,
            TEXT,
        )

    def test_the_two_spellings_are_the_same_claim(self):
        (with_tail,) = _claims(WITH_TAIL + NL)
        (without_tail,) = _claims(WITHOUT_TAIL + NL)
        assert with_tail == without_tail

    def test_the_row_under_the_documented_header_is_read(self):
        parsed = parse_manuscript(HEADER + DELIMITER + WITHOUT_TAIL + NL, path="m.md")
        assert [claim.id for claim in parsed.claims] == ["c1"]

    def test_a_row_with_a_fourth_column_but_no_fifth_is_not_a_claim_row(self):
        # `| c1 | paper | 1 | <quote>` has four cells, not five: the documented
        # row is id, source, page, quote and claim, and the trailing pipe is
        # what tells this reader that the fifth cell is there and empty (the
        # `| c1 | paper | 1 | <quote> |` shape, which *is* read).  Without it
        # the row is a different table, and this dialect does not guess.
        assert [claim.id for claim in _claims("| c1 | paper | 1 | " + QUOTE + NL)] == []
        assert [claim.id for claim in _claims("| c1 | paper | 1 | " + QUOTE + " |" + NL)] == [
            "c1"
        ]

    def test_a_row_with_an_empty_page_cell_keeps_working(self):
        parsed = parse_manuscript("| c1 | paper |  | " + QUOTE + " | " + TEXT + NL, path="m.md")
        assert [(claim.id, claim.page) for claim in parsed.claims] == [("c1", None)]

    @pytest.mark.parametrize("trailing", [" ", "  ", "\t", " \t ", "\u00a0"])
    def test_trailing_whitespace_after_the_last_cell_is_not_a_column(self, trailing):
        # A line an editor padded, or one whose author left a space before the
        # newline, is the same row.  Narrowing the end of the pattern to spaces
        # alone was a surviving mutation until this test existed - and the
        # comparison is the whole claim, because a run that lets the padding
        # fall into the last cell reads the same row with a different text.
        (claim,) = _claims(WITHOUT_TAIL + trailing + NL)
        assert (claim.id, claim.quote, claim.text) == ("c1", QUOTE, TEXT)


class TestProseIsStillProse:
    @pytest.mark.parametrize(
        "line",
        [
            "The model | the data | the result | we saw | finally",
            "| the model | the data | the result | we saw | finally",
            "| the model | the data | 5 | we saw | finally",
            "| c1 | paper | 1 |",
            "| c1 | paper | 1 | " + QUOTE + " | " + TEXT + " | a note",
        ],
    )
    def test_it_is_not_a_claim(self, line):
        # The third line fails on the leading cell being a sentence rather than
        # an id, the fourth on there being only three cells, and the fifth on
        # the row carrying a sixth column (which is left to `_CELL`'s lazy
        # `text` column and reads as a claim - see the next test).
        parsed = parse_manuscript(line + NL, path="m.md")
        if line.endswith("a note"):
            assert [claim.id for claim in parsed.claims] == ["c1"]
        else:
            assert parsed.claims == []


class TestTheVerdictOnAProject:
    def test_alone_it_is_judged_instead_of_called_a_missing_fence(self, project):
        _write(project, HEADER + DELIMITER + WITHOUT_TAIL + NL)
        code, out = _run(project, "check", "m.md", "--root", ".")
        assert "no-claim-blocks" not in out
        assert "c1" in out
        assert "1 claim — 1 verified" in out
        assert code == 0

    def test_beside_a_good_block_it_is_named(self, project):
        _write(project, GOOD_FENCE + NL + HEADER + DELIMITER + WITHOUT_TAIL + NL)
        code, out = _run(project, "check", "m.md", "--root", ".")
        assert "c1" in out
        assert "2 claims — 2 verified" in out
        assert code == 0

    def test_a_row_the_header_refuses_is_still_refused(self, project):
        _write(project, HEADER + DELIMITER + WITHOUT_TAIL.replace("paper", "nowhere") + NL)
        code, out = _run(project, "check", "m.md", "--root", ".")
        assert "source-missing" in out
        assert code == 1


class TestTheDetectorAgreesWithTheParser:
    @pytest.mark.parametrize("row", [WITH_TAIL, WITHOUT_TAIL])
    def test_a_row_inside_a_blockquote_is_still_not_reachable(self, row):
        hit = _unread_opener("> " + row)
        assert hit is not None
        assert hit[0] == "table"

    def test_a_prose_line_with_pipes_is_not_a_table_opener(self):
        assert _unread_opener("> The model | the data | the result") is None

    def test_a_blockquoted_row_without_a_trailing_pipe_is_reported(self):
        body = GOOD_FENCE + NL + "> " + WITHOUT_TAIL + NL
        parsed = parse_manuscript(body, path="m.md")
        assert "claim-block-unread" in [finding.code for finding in parsed.findings]
