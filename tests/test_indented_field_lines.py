"""A field-shaped line *indented* inside `quote: |` is prose, not a key.

`_split_body` reads a claim body as a YAML mapping, and its own comment says
what decides a sibling key: "in a `quote: |` block a line at the left margin is
a sibling key and never continuation text".  The rule has two halves and only
the second was implemented.  `_BODY_KEY` and `_ATTRIBUTE_KEY` are anchored on
``^\\s*``, so every indented line matched too - and an indented line inside
`quote: |` is the quote.

Measured on a claim whose quote is the first sentence of the page, with a
second sentence that is nowhere in the source:

    quote: |
      We collected 154,391 examples from the corpus.
      We also invented a sentence that is nowhere in the paper.
                                                              -> [high] quote-missing

    quote: |
      We collected 154,391 examples from the corpus.
      source: our own dataset
      We also invented a sentence that is nowhere in the paper.
                                                              -> [info] quote-found, exit 0

One indented field-shaped line turned a fabricated quotation into a verified
one: the quote was cut at `source:` and the half that remained really is on the
page.  The same line with any of the other keys (`page:`, `id:`, `ref:`,
`marker:`, `claim:`, `numbers:`) cut the quote too, and every one of them is
silent - the verdict simply describes a shorter passage than the author wrote.

`_KEYISH` (the *unknown* key branch) had the guard all along, as
`not raw[:1].isspace()`.  That is why `Page: 2` indented stayed in the quote
while `page: 2` indented vanished into an attribute: the same body, two answers
per the name of the key alone.
"""

from __future__ import annotations

import contextlib
import io
from pathlib import Path

import pytest

from citevouch.cli import main
from citevouch.manuscript import _split_body

NL = chr(10)
B3 = "`" * 3
FIRST = "We collected 154,391 examples from the corpus."
# Deliberately absent from PAGE: a sentence the author wrote and the source
# never printed.  If the reader cuts the quote before this line, it verifies.
SECOND = "We also invented a sentence that is nowhere in the paper."
THIRD = "The held-out set was 9,800 rolesets in total."
PAGE = FIRST + NL + "This page is about something else entirely." + NL


def _body(*lines: str) -> tuple[str, str, dict[str, str], list[tuple[int, str]]]:
    return _split_body(["quote: |", *("  " + line for line in lines)])


class TestTheQuoteKeepsItsIndentedLines:
    """Every key this format has, written one indent in, is quote text."""

    @pytest.mark.parametrize(
        "line",
        [
            "source: our own dataset",
            "page: 1",
            "id: c9",
            "ref: paper2026",
            "cite: paper2026",
            "marker: 【原文】",
            "claim: it holds them",
            "numbers: 1",
            "quote: nested",
        ],
    )
    def test_it_stays_in_the_quote(self, line: str) -> None:
        quote, _claim, attributes, unknown = _body(FIRST, line, THIRD)
        assert FIRST in quote
        assert THIRD in quote, (
            f"the line after {line!r} was cut off with it - the quote the "
            "author wrote is not the quote that was searched"
        )
        assert line.split(":")[1].strip() in quote
        assert attributes == {}, f"{line!r} was applied as an attribute"
        assert unknown == []

    def test_the_unknown_branch_agrees_with_the_known_one(self) -> None:
        # `Page:` indented is prose; `page:` indented must be prose too, or the
        # answer depends on whether the author happened to misspell the key.
        known_quote, _, _, _ = _body(FIRST, "page: 1", THIRD)
        unknown_quote, _, _, unknown = _body(FIRST, "Page: 1", THIRD)
        assert known_quote.replace("page:", "Page:") == unknown_quote
        assert unknown == []


class TestAMarginLineIsStillAKey:
    """The other half of the rule, unchanged: a line at the margin is a key."""

    def test_a_page_line_at_the_margin_is_applied(self) -> None:
        quote, _claim, attributes, _unknown = _split_body(["quote: |", "  " + FIRST, "page: 2"])
        assert quote == FIRST
        assert attributes == {"page": "2"}

    def test_a_page_line_before_the_quote_is_applied(self) -> None:
        quote, _claim, attributes, _unknown = _split_body(["page: 2", "quote: |", "  " + FIRST])
        assert quote == FIRST
        assert attributes == {"page": "2"}

    def test_an_unknown_key_at_the_margin_is_still_reported(self) -> None:
        _quote, _claim, _attributes, unknown = _split_body(
            ["quote: |", "  " + FIRST, "Page: 2"]
        )
        assert unknown == [(3, "Page")]


class TestTheBaseIndentIsTheBlocksOwn:
    """A block written one indent in still reads its own `quote:` line."""

    def test_a_body_at_indent_two_reads_as_a_mapping(self) -> None:
        quote, claim, _attributes, _unknown = _split_body(
            ["  quote: |", "    " + FIRST, "  claim: |", "    " + THIRD]
        )
        assert quote == FIRST
        assert claim == THIRD

    def test_its_content_is_anything_deeper_than_the_key(self) -> None:
        quote, _claim, attributes, _unknown = _split_body(
            ["  quote: |", "    " + FIRST, "      source: our own dataset", "    " + THIRD]
        )
        assert FIRST in quote
        assert THIRD in quote
        assert attributes == {}


class TestTheVerdictOnAProject:
    """The measured consequence: a fabricated half must not come back verified."""

    def _project(self, root: Path, body: list[str]) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        (root / "page.txt").write_text(PAGE, encoding="utf-8", newline=chr(10))
        (root / "sources.toml").write_text(
            "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=chr(10)
        )
        (root / "m.md").write_text(
            B3 + "claim id=c1 source=paper" + NL + NL.join(body) + NL + B3 + NL,
            encoding="utf-8",
            newline=chr(10),
        )
        return root

    def _run(self, root: Path) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = main(["check", "m.md", "--root", str(root)])
        return code, out.getvalue()

    def test_a_field_line_does_not_launder_a_fabricated_half(self, tmp_path: Path) -> None:
        root = self._project(
            tmp_path / "proj",
            ["quote: |", "  " + FIRST, "  source: our own dataset", "  " + SECOND],
        )
        code, output = self._run(root)
        assert "quote-found" not in output, (
            "the quote was cut at `source:` and the surviving half verified the "
            "block; the sentence after it is nowhere in the source"
        )
        assert code == 1
        assert "quote-missing" in output

    def test_the_control_still_fails(self, tmp_path: Path) -> None:
        root = self._project(tmp_path / "proj", ["quote: |", "  " + FIRST, "  " + SECOND])
        code, output = self._run(root)
        assert code == 1
        assert "quote-missing" in output

    def test_the_whole_quote_is_verified_when_the_whole_quote_is_on_the_page(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "proj"
        root.mkdir(parents=True)
        page = FIRST + NL + "This page is about something else entirely." + NL
        (root / "page.txt").write_text(page, encoding="utf-8", newline=chr(10))
        (root / "sources.toml").write_text(
            "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=chr(10)
        )
        (root / "m.md").write_text(
            B3
            + "claim id=c1 source=paper"
            + NL
            + "quote: |"
            + NL
            + "  "
            + FIRST
            + NL
            + "  This page is about something else entirely."
            + NL
            + B3
            + NL,
            encoding="utf-8",
            newline=chr(10),
        )
        code, output = self._run(root)
        assert code == 0
        assert "quote-found" in output
