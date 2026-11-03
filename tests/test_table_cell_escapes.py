"""A pipe inside a table cell is written with a backslash before it.

GFM's only escape inside a table cell is the pipe; every other spelling ends the
cell. Measured before this fix, on the row whose quote cell holds `a`, then a
backslash-pipe, then `b`:

    quote   'a' + backslash
    text    'b'

The quote was cut at the backslash and the remainder was installed as the `text`
column. The same row written *unescaped* - the spelling Markdown says is wrong -
parsed as a shorter quote and a longer text column, so the correct spelling was
the one that lost data.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from citevouch.cli import main
from citevouch.manuscript import _TABLE_CLAIM, parse_manuscript

NL = chr(10)
BS = chr(92)
ESC = BS + "|"
SENTENCE = "The corpus contains 154,391 utterances and a separator | in the middle."


def _quote(row: str) -> tuple[str, str] | None:
    result = parse_manuscript("# P" + NL + NL + row + NL, "m.md")
    if not result.claims:
        return None
    claim = result.claims[0]
    return claim.quote, claim.text


def _cell(quote: str, text: str = "short") -> str:
    return "| c1 | paper | 1 | " + quote + " | " + text + " |"


class TestAnEscapedPipeIsOneCell:
    def test_the_quote_survives_the_escape(self):
        assert _quote(_cell("a" + ESC + "b")) == ("a|b", "short")

    def test_both_cells_can_carry_one(self):
        assert _quote(_cell("a" + ESC + "b", "c" + ESC + "d")) == ("a|b", "c|d")

    def test_two_escapes_in_one_cell(self):
        assert _quote(_cell("q" + ESC + "r" + ESC + "s")) == ("q|r|s", "short")

    def test_the_source_cell_is_unescaped_too(self):
        # The rule is about the cell, not about the quote column: an author who
        # names a source `a|b` writes `a\|b` here, and the key they mean is the
        # one with the pipe in it.
        row = "| c1 | a" + ESC + "b | 1 | q | short |"
        result = parse_manuscript("# P" + NL + NL + row + NL, "m.md")
        assert result.claims, [finding.code for finding in result.findings]
        assert result.claims[0].source == "a|b"

    def test_the_unescaped_spelling_still_ends_the_cell(self):
        # The control: an unescaped pipe is a cell boundary, which is what
        # Markdown says and what the parser has always done.  The row then has
        # six cells, and the columns are read by position, so `b` lands in the
        # claim column and the trailing `short` is left over.  That is the
        # reason the escape has to exist, not a second defect.
        assert _quote(_cell("a|b")) == ("a", "b")


class TestWhatIsNotAnEscape:
    def test_an_ordinary_backslash_is_kept(self):
        # Only the pipe is defined as an escape inside a table cell; rewriting
        # any other backslash would be editing the author's text.
        assert _quote(_cell("C:" + BS + "temp")) == ("C:" + BS + "temp", "short")

    def test_a_trailing_backslash_before_the_cell_edge(self):
        assert _quote(_cell("ends" + BS)) == ("ends" + BS, "short")

    def test_a_line_with_no_escape_at_all_is_unchanged(self):
        assert _quote(_cell("plain quote")) == ("plain quote", "short")


class TestTheShapeTheParserSees:
    @pytest.mark.parametrize(
        "row",
        [
            "| c1 | paper | 1 | q | t |",
            "| c1 | paper | 1 | q" + ESC + "r | t |",
            "| c1 | paper | 1 | q | t" + ESC + "u |",
        ],
    )
    def test_the_pattern_finds_the_leading_columns(self, row: str):
        match = _TABLE_CLAIM.match(row)
        assert match is not None, row
        assert match.group("id") == "c1"
        assert match.group("source") == "paper"
        assert match.group("page") == "1"

    def test_the_pattern_does_not_split_on_an_escaped_edge(self):
        match = _TABLE_CLAIM.match("| c1 | paper | 1 | q" + ESC + "r | t |")
        assert match is not None
        assert match.group("quote") == "q" + ESC + "r"
        assert match.group("text") == "t"


class TestTheVerdictOnAProject:
    def _project(self, tmp_path: Path, quote_cell: str) -> Path:
        (tmp_path / "page.txt").write_text(SENTENCE + NL, encoding="utf-8", newline=NL)
        (tmp_path / "sources.toml").write_text(
            "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
        )
        (tmp_path / "m.md").write_text(
            "# P" + NL + NL + _cell(quote_cell) + NL, encoding="utf-8", newline=NL
        )
        return tmp_path

    def test_a_correctly_escaped_quote_is_found(self, tmp_path: Path):
        root = self._project(tmp_path, SENTENCE.replace("|", ESC))
        assert main(["check", "m.md", "--root", str(root)]) == 0

    def test_the_truncated_reading_is_not_verified(self, tmp_path: Path):
        """This is the reading the old parser produced for a correctly escaped row.

        It stopped the quote at the backslash, so the claim carried `... a
        separator ` plus a stray backslash - words the page does not have.
        """
        root = self._project(tmp_path, SENTENCE.split("|")[0].rstrip() + BS)
        assert main(["check", "m.md", "--root", str(root)]) == 1


class TestAnEmptyCellIsAClaimNotAFailure:
    """A blank column is a claim somebody has not finished, not a missing block.

    The cell quantifier used to be `+?`, which made an empty `text` or `claim`
    column stop matching the row at all.  The row then matched no dialect, and a
    manuscript whose only table row had a blank column was reported as
    `no-claim-blocks ... This file has none` - over a file that had one.  The
    quantifier is `*?` now, and what an empty column means is left to
    `claim-uncheckable`, which names the claim and says what is missing.
    """

    def test_an_empty_text_column_does_not_hide_the_row(self):
        row = "| c1 | paper | 1 | The corpus contains 154,391 utterances. ||"
        assert _quote(row) == ("The corpus contains 154,391 utterances.", "")

    def test_an_empty_quote_column_still_names_the_claim(self):
        row = "| c1 | paper | 1 || short |"
        assert _quote(row) is None
        result = parse_manuscript("# P" + NL + NL + row + NL, "m.md")
        assert [finding.code for finding in result.findings] == ["claim-uncheckable"]
        assert "no verbatim quote" in result.findings[0].message

    def test_an_empty_source_column_still_names_the_claim(self):
        row = "| c1 |  | 1 | The corpus contains 154,391 utterances. | short |"
        result = parse_manuscript("# P" + NL + NL + row + NL, "m.md")
        assert [finding.code for finding in result.findings] == ["claim-uncheckable"]
        assert "names no source" in result.findings[0].message

    def test_neither_shape_is_called_a_file_without_claims(self):
        for row in ("| c1 | paper | 1 || short |", "| c1 |  | 1 | q | short |"):
            result = parse_manuscript("# P" + NL + NL + row + NL, "m.md")
            assert "no-claim-blocks" not in [finding.code for finding in result.findings]

    def test_a_header_and_a_divider_are_still_not_claims(self):
        for row in ("| id | source | page | quote | claim |", "|----|----|----|----|----|"):
            assert _quote(row) is None
            result = parse_manuscript("# P" + NL + NL + row + NL, "m.md")
            # The parser leaves the "this file has no claim blocks" verdict to
            # the command that asks for it; what matters here is that neither
            # row is read as a claim with a problem.
            assert result.findings == []

    def test_a_project_with_an_empty_text_cell_verifies(self, tmp_path: Path):
        page = "The corpus contains 154,391 utterances and a separator | in the middle."
        (tmp_path / "page.txt").write_text(page + NL, encoding="utf-8", newline=NL)
        (tmp_path / "sources.toml").write_text(
            "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
        )
        (tmp_path / "m.md").write_text(
            "# P" + NL + NL + _cell(page.replace("|", ESC), "") + NL,
            encoding="utf-8",
            newline=NL,
        )
        assert main(["check", "m.md", "--root", str(tmp_path)]) == 0
