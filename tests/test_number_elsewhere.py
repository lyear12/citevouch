"""A number the page prints elsewhere is not a number the page does not print.

The ``numbers`` tier matches a quote with every number blanked out, so it knows
which of the page's numbers fall into the places the quote's numbers fall into.
Before this, the verifier threw that away and asked the page a weaker question -
"does 9,800 appear anywhere on page 1?" - and for a quote that swapped a number
between two sentences the answer is yes.  The run then had nothing specific to
say, fell back to "the words match page 1 but the numbers do not", and pointed
the author at a number printed four lines further down the same page.  An author
who turns the page, sees the number and stops trusting the tool is the worst
outcome this project has, because the tool's whole claim is that it reads the
page for you.

These tests pin the distinction: a number that is on the page in another place
is ``number-not-in-passage``, and a number that is nowhere on the page stays
``number-absent-in-quote``.
"""

from __future__ import annotations

import contextlib
import io
from pathlib import Path

import pytest

from citevouch.cli import main
from citevouch.matching import find_in_pages
from citevouch.model import CODES
from citevouch.sources import PageText

TWO_SENTENCES = (
    "We collected 40,688 examples for training. "
    "The held-out set of 9,800 rolesets was annotated separately."
)


def _pages(text: str, number: int = 1) -> list[PageText]:
    return [PageText(number=number, text=text)]


def _project(tmp_path: Path, page: str, quote: str) -> Path:
    (tmp_path / "page.txt").write_text(page, encoding="utf-8", newline="\n")
    (tmp_path / "sources.toml").write_text(
        '[sources]\npage = "page.txt"\n', encoding="utf-8", newline="\n"
    )
    (tmp_path / "m.md").write_text(
        f"```claim id=c1 source=page page=1\nquote: |\n  {quote}\nclaim: |\n  {quote}\n```\n",
        encoding="utf-8",
        newline="\n",
    )
    return tmp_path


def _run(root: Path) -> tuple[str, int]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = main(["check", "m.md", "--root", str(root)])
    return buf.getvalue(), code


class TestTheTierRecordsWhatThePagePrints:
    """The fact the message needs is computed during matching, or not at all."""

    def test_a_blind_match_reports_the_numbers_under_the_blanks(self):
        match = find_in_pages(
            "We collected 9,800 examples for training.", _pages(TWO_SENTENCES)
        )
        assert match.tier == "numbers"
        assert match.page_numbers == ("40,688",)

    def test_two_blanks_report_two_numbers_in_quote_order(self):
        page = "We counted 11,111 examples and 44,444 rolesets in total here."
        match = find_in_pages(
            "We counted 22,222 examples and 33,333 rolesets in total here.", _pages(page)
        )
        assert match.page_numbers == ("11,111", "44,444")

    def test_the_count_is_the_quote_s_own_count_not_the_page_s(self):
        # The page prints three numbers; the quote blanks the third one.  A
        # reader that took the page's first N numbers would hand back
        # ('1,000',) here, and a reader that took the last would hand back
        # ('40,688',).  The answer is the one under the blank.
        page = "Table 1,000 lists 40,688 rows. The set of 9,801 rolesets."
        match = find_in_pages("The set of 9,800 rolesets", _pages(page))
        assert match.tier == "numbers"
        assert match.page_numbers == ("9,801",)

    def test_an_exact_match_reports_no_page_numbers(self):
        match = find_in_pages("We collected 40,688 examples", _pages(TWO_SENTENCES))
        assert match.tier == "exact"
        assert match.page_numbers == ()


class TestASwappedNumberIsNotAMissingOne:
    def test_it_is_reported_under_its_own_code(self, tmp_path):
        root = _project(tmp_path, TWO_SENTENCES, "We collected 9,800 examples for training.")
        out, _ = _run(root)
        assert "number-not-in-passage" in out
        assert "number-absent-in-quote" not in out

    def test_the_message_names_both_the_claim_and_the_page(self, tmp_path):
        root = _project(tmp_path, TWO_SENTENCES, "We collected 9,800 examples for training.")
        out, _ = _run(root)
        assert "the quote says 9,800" in out
        assert "prints 40,688" in out

    def test_it_does_not_say_the_page_lacks_the_number(self, tmp_path):
        # The sentence that made the tool look broken.  9,800 is on page 1.
        root = _project(tmp_path, TWO_SENTENCES, "We collected 9,800 examples for training.")
        out, _ = _run(root)
        assert "does not contain" not in out
        assert "the numbers do not" not in out

    def test_it_still_fails_the_run_at_the_default_threshold(self, tmp_path):
        root = _project(tmp_path, TWO_SENTENCES, "We collected 9,800 examples for training.")
        _, code = _run(root)
        assert code == 1

    def test_the_severity_is_the_one_the_other_number_code_has(self):
        # A transcribed statistic is the failure this tool exists to catch, so
        # it cannot be softer than the code it replaced.
        assert CODES["number-not-in-passage"] == CODES["number-absent-in-quote"]


class TestANumberThatIsNowhereStaysAbsent:
    def test_a_digit_that_was_never_printed(self, tmp_path):
        root = _project(tmp_path, TWO_SENTENCES, "We collected 41,000 examples for training.")
        out, _ = _run(root)
        assert "number-absent-in-quote" in out
        assert "number-not-in-passage" not in out

    def test_the_error_carries_the_number_the_author_wrote(self, tmp_path):
        root = _project(tmp_path, TWO_SENTENCES, "We collected 41,000 examples for training.")
        out, _ = _run(root)
        assert "41,000" in out


class TestOnlyTheNumbersThatDifferAreNamed:
    def test_a_right_number_beside_a_wrong_one_is_not_named(self, tmp_path):
        page = (
            "We counted 11,111 examples and 44,444 rolesets in total here. "
            "Then we counted 11,111 examples and 22,222 rolesets too."
        )
        quote = "We counted 11,111 examples and 22,222 rolesets in total here."
        out, _ = _run(_project(tmp_path, page, quote))
        assert "22,222" in out
        assert "44,444" in out
        # The first number is right, so it is not one of "the quote says ...".
        assert "the quote says 11,111" not in out

    def test_one_claim_yields_one_line(self, tmp_path):
        page = "We counted 11,111 examples and 44,444 rolesets in total here."
        quote = "We counted 44,444 examples and 11,111 rolesets in total here."
        out, _ = _run(_project(tmp_path, page, quote))
        assert out.count("number-not-in-passage") == 1


@pytest.mark.parametrize(
    "page,quote",
    [
        ("The corpus holds 40,688 types.", "The corpus holds 40,688 types."),
        ("Nothing numeric is printed on this page at all.", "Nothing numeric here."),
    ],
)
def test_a_quote_that_does_not_swap_a_number_is_not_accused(
    tmp_path: Path, page: str, quote: str
) -> None:
    out, _code = _run(_project(tmp_path, page, quote))
    assert "number-not-in-passage" not in out
