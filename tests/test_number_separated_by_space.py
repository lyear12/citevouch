"""A page that parts a number from its separator still prints the number.

A PDF extraction of a table column, and more than one journal style, prints
forty thousand six hundred and eighty-eight as ``40, 688`` - the grouping
comma and a space, not the comma alone.  The quote is the author's own typing,
so it says ``40,688``.

Before this file existed, the word matcher removed the whitespace and reported
``quote-found`` - the quote *is* that sentence - while the number reader split
the page's token at the space and reported ``number-absent-in-quote``: one run
saying both "this is the page's own text" and "this page does not contain that
number", about a figure printed in front of the reader.  The mirror case failed
too: a quote that types ``40, 688`` against a page printing ``40,688`` was read
as two numbers, ``40`` and ``688``, and both were reported missing.

The rule is pinned here rather than left to the comment above ``_THOUSANDS``.
"""

from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from citevouch.cli import main
from citevouch.textnorm import CANON_PATTERN, canonical_number, quote_numbers

NL = chr(10)
B3 = chr(96) * 3

SENTENCE = "We collected 40,688 examples of it entirely."
SPACED = "We collected 40, 688 examples of it entirely."


def _check(root: Path) -> tuple[int, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(["check", "m.md", "--root", str(root)])
    return code, out.getvalue() + err.getvalue()


def _project(root: Path, page: str, quote: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "page.txt").write_text(page, encoding="utf-8", newline=chr(10))
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=chr(10)
    )
    (root / "m.md").write_text(
        B3
        + "claim id=c1 source=paper page=1"
        + NL
        + "quote: |"
        + NL
        + "  "
        + quote
        + NL
        + B3
        + NL,
        encoding="utf-8",
        newline=chr(10),
    )
    return root


class TestTheSpacingsAreOneNumber:
    @pytest.mark.parametrize(
        "spelling",
        [
            "40,688",
            "40, 688",
            "40 ,688",
            "40 , 688",
            "40,6 88",
            "40,68 8",
            "4 0,688",
            "40 688",
        ],
    )
    def test_the_pattern_reads_one_token(self, spelling: str) -> None:
        assert [m.group(0) for m in CANON_PATTERN.finditer(spelling)] == [spelling]

    @pytest.mark.parametrize(
        "spelling",
        ["40, 688", "40 ,688", "40,6 88", "4 0,688"],
    )
    def test_the_value_is_the_same_value(self, spelling: str) -> None:
        assert canonical_number(spelling) == "40688"

    def test_a_quote_that_types_the_space_carries_one_number(self) -> None:
        assert quote_numbers("we counted 40, 688 of them") == ("40, 688",)


class TestTheNeighboursAreUnchanged:
    def test_a_year_still_does_not_start_a_group(self) -> None:
        found = [m.group(0) for m in CANON_PATTERN.finditer("2019 2020 2021")]
        assert found == ["2019", "2020", "2021"]

    def test_a_page_range_still_reads_as_one_number(self) -> None:
        """Pinned deliberately: 219 then a three-digit run is a group shape."""
        found = [m.group(0) for m in CANON_PATTERN.finditer("pages 219 220")]
        assert found == ["219 220"]

    def test_a_four_digit_left_side_still_does_not_start_a_group(self) -> None:
        # The parting rule must not widen the group rule: a year followed by a
        # three digit count is two numbers, not one seven digit number.
        assert [m.group(0) for m in CANON_PATTERN.finditer("1234 567")] == ["1234", "567"]
        assert [m.group(0) for m in CANON_PATTERN.finditer("pages 1234 567")] == [
            "1234",
            "567",
        ]

    def test_a_group_never_cuts_a_longer_run_of_digits(self) -> None:
        # ``40, 6888`` is not ``40, 688`` with a stray 8: a group is exactly
        # three digits and the digit after it must not be one more.
        assert [m.group(0) for m in CANON_PATTERN.finditer("40, 6888")] == ["40", "6888"]
        assert [m.group(0) for m in CANON_PATTERN.finditer("40,6888")] == ["40", "6888"]

    def test_a_line_break_is_not_a_parting(self) -> None:
        # A PDF column ends the line in the middle of a number often enough
        # that joining across one would make ``40,\n688`` a figure the page
        # never printed.  Only the spaces in ``_SPACES`` part digits.
        assert [m.group(0) for m in CANON_PATTERN.finditer("40," + NL + "688")] == [
            "40",
            "688",
        ]

    @pytest.mark.parametrize(("spelling", "value"), [("48.4", "48.4"), ("1.000,5", "1000.5")])
    def test_the_decimals_keep_their_points(self, spelling: str, value: str) -> None:
        assert canonical_number(spelling) == value
        assert [m.group(0) for m in CANON_PATTERN.finditer(spelling)] == [spelling]


class TestTheVerdict:
    def test_a_spaced_page_does_not_accuse_the_quote(self, tmp_path: Path) -> None:
        root = _project(tmp_path / "proj", SPACED + NL, "We collected 40,688 examples")
        code, printed = _check(root)
        assert "quote-found" in printed
        assert "number-absent-in-quote" not in printed
        assert code == 0

    def test_a_spaced_quote_does_not_accuse_the_page(self, tmp_path: Path) -> None:
        root = _project(tmp_path / "proj", SENTENCE + NL, "We collected 40, 688 examples")
        code, printed = _check(root)
        assert "quote-found" in printed
        assert "number-absent-in-quote" not in printed
        assert code == 0

    def test_both_spaced_is_still_one_number(self, tmp_path: Path) -> None:
        root = _project(tmp_path / "proj", SPACED + NL, "We collected 40, 688 examples")
        code, printed = _check(root)
        assert "number-absent-in-quote" not in printed
        assert code == 0

    def test_a_different_number_is_still_absent(self, tmp_path: Path) -> None:
        # Long enough that the numbers tier can mask the figure out and find
        # the rest of the sentence: the page's 40, 688 is one number, the
        # quote's 40,689 is another, and the run must say so rather than call
        # the sentence absent.
        page = (
            "We collected 40, 688 examples of written English from the corpus "
            "and filtered them by length before splitting." + NL
        )
        quote = (
            "We collected 40,689 examples of written English from the corpus "
            "and filtered them by length before splitting."
        )
        root = _project(tmp_path / "proj", page, quote)
        code, printed = _check(root)
        assert "number-absent-in-quote" in printed
        assert "quote-missing" not in printed
        assert code == 1
