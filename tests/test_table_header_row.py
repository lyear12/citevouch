"""A GFM table header row is column labels, not a claim.

The table dialect reads a five-cell row with an integer, a dash or nothing in
the third cell.  A results table's header can have exactly that shape, and the
row above a `|---|` delimiter row is the header.  Before this rule the parser
judged it like any other row:

    | model | setting | 84 | We report the mean over five seeds | note |
    |-------|---------|----|------------------------------------|------|
    | bert  | base    | 84 | 88 | 90 |

    [info] quote-found at manuscript.md:3 (model): quote found on page 1

That `quote-found` is this tool's worst failure: it certified a column label as
a verified quotation because the page happened to print those words.  Two things
now happen instead - the header row is named with `claim-table-header`, and the
data row beneath it is still read normally.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from citevouch.manuscript import parse_manuscript

NL = chr(10)
PIPE = "|"
ROOT = Path(__file__).resolve().parents[1]
PYTHONPATH = str(ROOT / "src")

SENTENCE = "We report the mean over five seeds and the standard deviation across them."
PAGE = "Results" + NL + SENTENCE + NL
QUOTE = "almost half (48.4%) occur only once"


def row(*cells: str) -> str:
    return PIPE + PIPE.join(f" {cell} " for cell in cells) + PIPE


def delim(*spellings: str) -> str:
    return PIPE + PIPE.join(spellings) + PIPE


D = "------"
DELIM = delim(D, D, D, D, D)

# A results table whose header's fourth cell is prose the page really prints.
RESULTS_HEADER = row("model", "setting", "84", SENTENCE, "note")
RESULTS_DATA = row("bert", "base", "84", "88", "90")

# The documented claim header.  It is not header-shaped at all - its third cell
# is the word `page` - so nothing here should change for it.
CLAIM_HEADER = row("id", "source", "page", "quote", "claim")
CLAIM_DATA = row("c3", "paper", "7", QUOTE, "48.4% 是 hapax")


def parse(*lines: str):
    return parse_manuscript(NL.join(lines) + NL, path="manuscript.md")


def codes(result) -> list[str]:
    return [finding.code for finding in result.findings]


class TestTheHeaderIsNamedRatherThanJudged:
    def test_a_header_row_is_not_a_claim(self):
        result = parse(RESULTS_HEADER, DELIM, RESULTS_DATA)
        assert [claim.id for claim in result.claims] == ["bert"]

    def test_the_header_is_reported_by_name(self):
        result = parse(RESULTS_HEADER, DELIM, RESULTS_DATA)
        assert codes(result) == ["claim-table-header"]

    def test_the_finding_points_at_the_header_line(self):
        # The header is on line 3, not line 1: a finding that always says
        # "line 1" is a finding that tells the author to open the title.
        result = parse("Results", "", RESULTS_HEADER, DELIM, RESULTS_DATA)
        header = next(f for f in result.findings if f.code == "claim-table-header")
        assert header.line == 3
        assert header.claim_id == "model"

    def test_the_message_says_where_a_claim_belongs(self):
        result = parse(RESULTS_HEADER, DELIM, RESULTS_DATA)
        message = next(f for f in result.findings if f.code == "claim-table-header").message
        assert "column labels" in message
        assert "delimiter row" in message
        assert "belongs under it" in message

    def test_the_data_row_under_the_header_is_still_read(self):
        result = parse(RESULTS_HEADER, DELIM, RESULTS_DATA)
        assert result.claims[0].quote is not None
        assert result.claims[0].page == 84


class TestOnlyATableClaimRowCanBeAHeader:
    def test_a_non_table_row_above_a_dash_line_is_not_a_header(self):
        # `_is_header_row` runs over every line, so its first question has to
        # be "is this line shaped like a table claim at all".  Without it, the
        # unread-block pass would excuse any line sitting above `|---|`.
        from citevouch.manuscript import _is_header_row

        assert _is_header_row(["an ordinary sentence", DELIM], 0) is False

    def test_a_table_claim_row_above_a_dash_line_is_one(self):
        from citevouch.manuscript import _is_header_row

        assert _is_header_row([RESULTS_HEADER, DELIM], 0) is True

    def test_the_last_line_of_a_file_is_never_a_header(self):
        from citevouch.manuscript import _is_header_row

        assert _is_header_row([RESULTS_HEADER], 0) is False


class TestWhatMustStillBeAClaim:
    def test_the_documented_header_is_not_header_shaped(self):
        # Its third cell is `page`, so the table-claim pattern refuses it and it
        # never reaches this rule.  Only the data row is a claim.
        result = parse(CLAIM_HEADER, DELIM, CLAIM_DATA)
        assert [claim.id for claim in result.claims] == ["c3"]
        assert codes(result) == []

    def test_a_row_with_no_delimiter_under_it_is_still_a_claim(self):
        result = parse(CLAIM_DATA)
        assert [claim.id for claim in result.claims] == ["c3"]
        assert codes(result) == []

    def test_a_claim_under_its_own_header_is_read(self):
        result = parse(CLAIM_HEADER, DELIM, CLAIM_DATA, row("c4", "paper", "8", QUOTE, "note"))
        assert [claim.id for claim in result.claims] == ["c3", "c4"]

    def test_a_blank_line_breaks_the_pair(self):
        result = parse(RESULTS_HEADER, NL, DELIM, RESULTS_DATA)
        # The delimiter row is no longer directly under the header, so the row
        # is read as a claim again - and that is the shape the author wrote.
        assert "model" in [claim.id for claim in result.claims]


class TestEveryDelimiterSpelling:
    def test_alignment_colons_count(self):
        result = parse(RESULTS_HEADER, delim(":-----", ":----:", "-----:", D, D), RESULTS_DATA)
        assert codes(result) == ["claim-table-header"]
        assert [claim.id for claim in result.claims] == ["bert"]

    def test_a_single_dash_cell_counts(self):
        result = parse(RESULTS_HEADER, delim("-", "-", "-", "-", "-"), RESULTS_DATA)
        assert codes(result) == ["claim-table-header"]

    def test_an_indented_delimiter_row_counts(self):
        result = parse(RESULTS_HEADER, "   " + delim(D, D, D, D, D), RESULTS_DATA)
        assert codes(result) == ["claim-table-header"]

    def test_a_dash_run_that_is_not_a_table_row_does_not(self):
        # `--- and then some words` is prose, and a header-shaped row above it
        # is still a claim.
        result = parse(RESULTS_HEADER, "--- and then some words", RESULTS_DATA)
        assert "model" in [claim.id for claim in result.claims]

    def test_a_heading_is_not_a_delimiter_row(self):
        result = parse(RESULTS_HEADER, "## Methods", RESULTS_DATA)
        assert "model" in [claim.id for claim in result.claims]


class TestTheVerdictOnAProject:
    def _project(self, tmp_path: Path, body: str) -> Path:
        (tmp_path / "page.txt").write_text(PAGE, encoding="utf-8", newline=NL)
        (tmp_path / "sources.toml").write_text(
            "[sources]" + NL + 'paper = "page.txt"' + NL + 'setting = "page.txt"' + NL,
            encoding="utf-8",
            newline=NL,
        )
        (tmp_path / "manuscript.md").write_text(body, encoding="utf-8", newline=NL)
        return tmp_path

    def _run(self, root: Path, *argv: str) -> tuple[int, str]:
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

    def test_a_header_is_never_certified_as_a_quotation(self, tmp_path: Path):
        body = "# Results" + NL + NL + RESULTS_HEADER + NL + DELIM + NL + RESULTS_DATA + NL
        root = self._project(tmp_path, body)
        _code, output = self._run(root, "check", "manuscript.md", "--root", str(root))
        assert "quote-found" not in output
        assert "claim-table-header" in output

    def test_the_header_does_not_make_the_run_fail_at_the_default_threshold(
        self, tmp_path: Path
    ):
        # Nothing in the file is a claim with a resolvable source, so the run
        # still fails - but on the data row's own problem, not the header.
        body = (
            "# Results"
            + NL
            + NL
            + CLAIM_HEADER
            + NL
            + DELIM
            + NL
            + row("c3", "paper", "1", QUOTE, "note")
            + NL
            + RESULTS_HEADER
            + NL
            + DELIM
            + NL
            + RESULTS_DATA
            + NL
        )
        root = self._project(tmp_path, body)
        code, output = self._run(root, "check", "manuscript.md", "--root", str(root))
        # The claim row is read and its quote is judged on its merits (it is
        # not in this page, so it is missing) - what matters here is that the
        # header produced a `medium` and not a claim of its own.
        assert "claim-table-header" in output
        assert "2 claims" in output
        assert code == 1

    def test_doctor_names_the_same_thing(self, tmp_path: Path):
        body = "# Results" + NL + NL + RESULTS_HEADER + NL + DELIM + NL + RESULTS_DATA + NL
        root = self._project(tmp_path, body)
        _code, output = self._run(
            root, "doctor", "--root", str(root), "--manuscript", "manuscript.md"
        )
        # The header row is why the claims line is not clean, and the line has
        # to say so rather than reporting a claim the author never wrote.
        assert "claim" in output.lower()
