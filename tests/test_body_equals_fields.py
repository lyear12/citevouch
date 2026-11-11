"""A claim body is a mapping: `page=2` there is a field written with the wrong separator.

A claim block teaches two spellings and each reader accepted one: the opening
line reads ``key=value``, the body reads ``key: value``.  A body line *at the
margin* that spelled a field with ``=`` matched no key pattern, so it fell
through to the last branch of ``_split_body``, which appends it to the field
that is open - and when no field is open, drops it.

Measured on a source whose quote is on page 2:

    page: 2 above quote, correct page  -> [info] quote-found page 2
    page=2 above quote, correct page   -> [info] quote-found page 2, hint dropped
    page: 2 above quote, WRONG page    -> [medium] quote-moved
    page=2 above quote, WRONG page     -> [info] quote-found, exit 0, NO finding
    page=2 below quote                 -> [high] quote-missing "…corpus. page=2"

Two spellings, two failure modes: above the quote the line switched a check off
without saying so, below it the line was quoted and the run accused the author
of quoting a passage the source really prints.

The fix reports instead of guessing, which is what ``_opening_colon_findings``
already does in the other direction: the author cannot tell from the key alone
whether the key or the separator was wrong, so both are named.

Note the margin: an *indented* ``page=2`` is quotation, not a field - that is
the rule the previous fix established and it does not change here.
"""

from __future__ import annotations

import contextlib
import io
from pathlib import Path

import pytest

from citevouch.cli import main
from citevouch.manuscript import (
    _BODY_FIELD_NAMES,
    _split_body,
    _unknown_field_message,
    parse_manuscript,
)

NL = chr(10)
B3 = "`" * 3
QUOTE = "We collected 154,391 examples from the corpus."
SECOND = "We also invented a sentence that is nowhere in the paper."
ELSEWHERE = "This page is about something else entirely."
# Page 1 is a decoy; the quote is on page 2, so `page: 2` is the honest hint and
# `page: 1` is the lie.
PAGES = ELSEWHERE + chr(12) + QUOTE + NL

BODY_NAMES = (
    "cite",
    "claim",
    "id",
    "marker",
    "number",
    "numbers",
    "page",
    "quote",
    "ref",
    "source",
)


def _body(*lines: str) -> tuple[str, str, dict[str, str], list[tuple[int, str]]]:
    """A body whose quote is one indented line and whose other lines sit at the margin."""
    return _split_body(["quote: |", "  " + QUOTE, *lines])


class TestTheBodyReportsTheOtherSeparator:
    """It is reported, never applied, and never left to look like quote text."""

    @pytest.mark.parametrize("name", BODY_NAMES)
    def test_it_is_reported_whatever_the_name(self, name: str) -> None:
        quote, _claim, attributes, unknown = _body(f"{name}=somewhere")
        assert unknown == [(3, name)]
        assert attributes == {}
        assert quote == QUOTE

    def test_it_is_reported_above_the_quote_too(self) -> None:
        quote, _claim, attributes, unknown = _split_body(["page=2", "quote: |", "  " + QUOTE])
        assert unknown == [(1, "page")]
        assert attributes == {}
        assert quote == QUOTE

    def test_a_name_this_format_does_not_have_is_reported_the_same_way(self) -> None:
        quote, _claim, _attributes, unknown = _body("Page=2")
        assert unknown == [(3, "Page")]
        assert quote == QUOTE

    def test_two_of_them_are_both_reported(self) -> None:
        _quote, _claim, _attributes, unknown = _split_body(
            ["page=1", "id=c2", "quote: |", "  " + QUOTE]
        )
        assert unknown == [(1, "page"), (2, "id")]

    def test_a_comparison_is_not_a_field(self) -> None:
        # `a == b` is prose that happens to contain the separator; `=(?!=)`
        # keeps it out, because a finding nobody can act on is how a real one
        # gets ignored.  Being at the margin it is still quote text, which is
        # the pre-existing rule for a margin line that names no key.
        quote, _claim, attributes, unknown = _body("a == b")
        assert unknown == []
        assert attributes == {}
        assert quote == QUOTE + NL + "a == b"

    def test_an_equals_field_at_the_margin_is_reported_in_the_body(self) -> None:
        # The same mistake one line up from the quote: before the fix it was
        # dropped in silence, which is how a page hint disappears.
        result = _split_body(["id=c1", "source=paper", "quote: |", "  " + QUOTE])
        assert result[2] == {}
        assert result[3] == [(1, "id"), (2, "source")]

    def test_the_lines_after_it_are_not_quoted_either(self) -> None:
        # Reporting the line is not enough: the branch has to clear the open
        # field, or the `=` line is reported *and* the quote keeps growing
        # underneath it.  Compared with the same body where the line is a
        # colon field, so the two separators must leave the quote identical.
        after_equals = _split_body(["quote: |", "  " + QUOTE, "page=1", "  " + SECOND])
        after_colon = _split_body(["quote: |", "  " + QUOTE, "page: 1", "  " + SECOND])
        assert after_equals[0] == after_colon[0] == QUOTE
        assert after_equals[3] == [(3, "page")]

    def test_an_indented_one_is_quotation_not_a_field(self) -> None:
        # The margin rule from the previous fix: deeper than the block's own
        # keys is content, whatever separator it happens to contain.
        quote, _claim, attributes, unknown = _split_body(["quote: |", "  " + QUOTE, "  page=2"])
        assert unknown == []
        assert attributes == {}
        assert quote == QUOTE + NL + "page=2"

    def test_the_opening_line_still_reads_equals_without_a_finding(self) -> None:
        # This is the spelling the opening line documents, so a claim that uses
        # it must produce no finding at all.  The body here carries no `=` line
        # of its own - that is the difference from the test above.
        text = (
            B3 + "claim id=c1 source=paper" + NL + "quote: |" + NL + "  " + QUOTE + NL + B3 + NL
        )
        result = parse_manuscript(text, path="m.md")
        assert [finding.code for finding in result.findings] == []
        assert [(c.id, c.source) for c in result.claims] == [("c1", "paper")]


class TestTheSentence:
    """Reporting the same mistake in two directions needs two sentences."""

    def test_the_sentence_names_the_separator_that_works(self) -> None:
        message = _unknown_field_message(7, "page")
        assert "line 7" in message
        assert "writes page=" in message
        assert "write page: (not page=)" in message
        assert "neither applied nor searched" in message

    def test_the_old_sentence_survives_for_a_name_nobody_has(self) -> None:
        message = _unknown_field_message(7, "footnote")
        assert "footnote" in message
        assert "no such key" in message

    def test_the_sentence_lists_every_name_the_reader_has(self) -> None:
        # The list is a claim about the reader.  Typed out by hand it was a
        # claim about the day it was typed: `number:` is a body key (`numbers?`
        # in `_BODY_KEY`) and the sentence said there was no such name.
        message = _unknown_field_message(7, "footnote")
        for name in _BODY_FIELD_NAMES:
            assert name in message
        assert "numbers and page" not in message
        assert message.rstrip().endswith("and source")

    def test_a_name_with_one_letter_too_few_is_told_the_right_things(self) -> None:
        # `number=` is a name the body has (`numbers?`), so the sentence must be
        # about the separator, not about the key being unknown.
        message = _unknown_field_message(4, "number")
        assert "writes number=" in message
        assert "write number: (not number=)" in message
        assert "no such key" not in message


class TestWhatMustNotChange:
    """The other spellings, and the places where `=` is already the format."""

    def test_a_colon_field_is_still_applied(self) -> None:
        _quote, _claim, attributes, unknown = _body("page: 2")
        assert attributes == {"page": "2"}
        assert unknown == []

    def test_a_numbers_line_is_still_consumed(self) -> None:
        quote, _claim, _attributes, unknown = _split_body(
            ["quote: |", "  " + QUOTE, "numbers: |", "  99,999"]
        )
        assert quote == QUOTE
        assert unknown == []


def _project(root: Path, body_lines: list[str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "page.txt").write_text(PAGES, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    (root / "m.md").write_text(
        B3 + "claim id=c1 source=paper" + NL + NL.join(body_lines) + NL + B3 + NL,
        encoding="utf-8",
        newline=NL,
    )
    return root


def _run(root: Path) -> tuple[int, str]:
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(["check", "m.md", "--root", str(root)])
    return code, out.getvalue() + err.getvalue()


class TestTheVerdictOnAProject:
    """The two measured failures, one above the quote and one below it."""

    def test_above_the_quote_the_hint_is_not_silently_dropped(self, tmp_path: Path) -> None:
        root = _project(tmp_path / "proj", ["page=1", "quote: |", "  " + QUOTE])
        code, output = _run(root)
        assert "claim-field-unknown" in output
        assert "write page: (not page=)" in output
        assert code == 0

    def test_below_the_quote_the_line_is_not_quoted(self, tmp_path: Path) -> None:
        root = _project(tmp_path / "proj", ["quote: |", "  " + QUOTE, "page=2"])
        code, output = _run(root)
        assert "quote-missing" not in output
        assert "claim-field-unknown" in output
        assert code == 0

    def test_the_claim_is_still_verified_on_its_real_page(self, tmp_path: Path) -> None:
        root = _project(tmp_path / "proj", ["quote: |", "  " + QUOTE, "page=2"])
        code, output = _run(root)
        assert "quote-found" in output
        assert "quote found on page 2" in output
        assert "1 claim — 1 verified" in output
        assert code == 0

    def test_a_correct_equals_hint_is_not_applied_either(self, tmp_path: Path) -> None:
        # Reported, not applied - so the page hint is ignored and the quote is
        # found where it actually is.  The finding is what tells the author the
        # hint did nothing.
        root = _project(tmp_path / "proj", ["page=2", "quote: |", "  " + QUOTE])
        code, output = _run(root)
        assert "claim-field-unknown" in output
        assert "quote-found" in output
        assert code == 0
