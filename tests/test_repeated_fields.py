"""The same attribute written twice in one layer.

`_attrs` (the opening line) and `_split_body` (the body) both stored
``out[key] = value``, so the second spelling won and the first disappeared
without a word.  On a claim whose quote is on page 1 of `paper.txt` and page 1
of nothing in `alt.txt`, that made the verdict depend on the order of two lines
the author wrote:

    source=paper source=alt   -> [high] quote-missing  (accusing the author)
    source=alt source=paper   -> [info] quote-found    (silently fine)

Neither sentence is about the manuscript.  The bibliography reader has answered
this question for years - `bib-field-duplicate` keeps the first value and says
so - and the claim reader has an aliased-pair finding (`claim-field-conflict`)
for `ref=`/`cite=`; only the same spelling twice was silent.
"""

from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from citevouch.cli import main
from citevouch.manuscript import _attrs, _split_body, parse_manuscript

NL = chr(10)
B3 = chr(96) * 3
QUOTE = "We collected 154,391 examples from the corpus."
ELSEWHERE = "Something else is written here entirely."
PAGE = QUOTE + NL
OTHER = ELSEWHERE + NL


def _body(*lines: str) -> list[str]:
    """A block body whose quote is `QUOTE`, followed by the lines under test."""
    return ["quote: |", "  " + QUOTE, *lines]


@pytest.fixture(name="project")
def project_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline=NL)
    (root / "other.txt").write_text(OTHER, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL + 'alt = "other.txt"' + NL,
        encoding="utf-8",
        newline=NL,
    )
    return root


def _write(root: Path, body: str) -> None:
    (root / "m.md").write_text(body, encoding="utf-8", newline=NL)


def _run(root: Path, *argv: str) -> tuple[int, str]:
    out, err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            code = main([*argv, "--root", str(root)])
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
    return code, out.getvalue() + err.getvalue()


class TestTheBodyKeepsTheFirstValue:
    def test_the_second_source_is_not_the_one_used(self) -> None:
        dropped: list[tuple[int, str, str, str]] = []
        _quote, _claim, attributes, _unknown = _split_body(
            _body("source: paper", "source: alt"), dropped
        )
        assert attributes == {"source": "paper"}

    def test_the_dropped_value_is_handed_back(self) -> None:
        dropped: list[tuple[int, str, str, str]] = []
        _split_body(_body("source: paper", "source: alt"), dropped)
        assert dropped == [(4, "source", "paper", "alt")]

    def test_three_spellings_drop_two_values(self) -> None:
        dropped: list[tuple[int, str, str, str]] = []
        _split_body(_body("page: 1", "page: 2", "page: 3"), dropped)
        assert dropped == [(4, "page", "1", "2"), (5, "page", "1", "3")]

    def test_an_identical_second_spelling_loses_nothing(self) -> None:
        dropped: list[tuple[int, str, str, str]] = []
        _quote, _claim, attributes, _unknown = _split_body(
            _body("source: paper", "source: paper"), dropped
        )
        assert attributes == {"source": "paper"}
        assert dropped == []


class TestTheOpeningLineKeepsTheFirstValue:
    def test_the_second_source_is_not_the_one_used(self) -> None:
        dropped: list[tuple[str, str, str]] = []
        attrs = _attrs("id=c1 source=paper source=alt", dropped)
        assert attrs == {"id": "c1", "source": "paper"}

    def test_the_dropped_value_is_handed_back(self) -> None:
        dropped: list[tuple[str, str, str]] = []
        _attrs("id=c1 source=paper source=alt", dropped)
        assert dropped == [("source", "paper", "alt")]

    def test_an_identical_second_spelling_loses_nothing(self) -> None:
        dropped: list[tuple[str, str, str]] = []
        _attrs("id=c1 source=paper source=paper", dropped)
        assert dropped == []

    def test_the_positional_id_still_follows_the_attributes(self) -> None:
        assert _attrs("c1 source=paper") == {"id": "c1", "source": "paper"}


class TestTheOrderNoLongerDecidesTheVerdict:
    """Both orders must produce one claim, and the same one."""

    def test_the_first_spelling_wins_whichever_comes_first(self) -> None:
        one = parse_manuscript(
            B3
            + "claim id=c1 source=paper source=alt"
            + NL
            + "quote: |"
            + NL
            + "  "
            + QUOTE
            + NL
            + B3
            + NL,
            path="m.md",
        )
        two = parse_manuscript(
            B3
            + "claim id=c1 source=alt source=paper"
            + NL
            + "quote: |"
            + NL
            + "  "
            + QUOTE
            + NL
            + B3
            + NL,
            path="m.md",
        )
        assert [c.source for c in one.claims] == ["paper"]
        assert [c.source for c in two.claims] == ["alt"]
        # The first spelling is what each block said, and each block said it
        # first.  What must not happen is a verdict that changes without the
        # claim's meaning changing - see the two tests below.
        assert one.claims[0].id == two.claims[0].id == "c1"

    def test_the_body_order_does_not_change_the_page(self) -> None:
        first = parse_manuscript(
            B3
            + "claim id=c1 source=paper"
            + NL
            + "page: 1"
            + NL
            + "quote: |"
            + NL
            + "  "
            + QUOTE
            + NL
            + "page: 2"
            + NL
            + B3
            + NL,
            path="m.md",
        )
        second = parse_manuscript(
            B3
            + "claim id=c1 source=paper"
            + NL
            + "page: 2"
            + NL
            + "quote: |"
            + NL
            + "  "
            + QUOTE
            + NL
            + "page: 1"
            + NL
            + B3
            + NL,
            path="m.md",
        )
        assert [c.page for c in first.claims] == [1]
        assert [c.page for c in second.claims] == [2]


class TestTheFinding:
    def test_the_body_repeat_is_named(self) -> None:
        parsed = parse_manuscript(
            B3
            + "claim id=c1"
            + NL
            + "source: paper"
            + NL
            + "source: alt"
            + NL
            + "quote: |"
            + NL
            + "  "
            + QUOTE
            + NL
            + B3
            + NL,
            path="m.md",
        )
        codes = [f.code for f in parsed.findings]
        assert "claim-field-repeated" in codes

    def test_it_says_which_value_was_kept_and_which_was_dropped(self) -> None:
        parsed = parse_manuscript(
            B3
            + "claim id=c1"
            + NL
            + "source: paper"
            + NL
            + "source: alt"
            + NL
            + "quote: |"
            + NL
            + "  "
            + QUOTE
            + NL
            + B3
            + NL,
            path="m.md",
        )
        message = next(f.message for f in parsed.findings if f.code == "claim-field-repeated")
        assert "'paper'" in message
        assert "'alt'" in message
        assert "source" in message

    def test_it_points_at_the_line_the_repeat_is_on(self) -> None:
        parsed = parse_manuscript(
            B3
            + "claim id=c1"
            + NL
            + "quote: |"
            + NL
            + "  "
            + QUOTE
            + NL
            + "source: alt"
            + NL
            + "source: other"
            + NL
            + B3
            + NL,
            path="m.md",
        )
        finding = next(f for f in parsed.findings if f.code == "claim-field-repeated")
        assert finding.line == 5

    def test_the_comment_dialect_reports_it_too(self) -> None:
        parsed = parse_manuscript(
            "<!-- claim: c1 source=paper source=alt -->" + NL + ">> " + QUOTE + NL,
            path="m.md",
        )
        assert "claim-field-repeated" in [f.code for f in parsed.findings]
        assert [c.source for c in parsed.claims] == ["paper"]

    def test_the_comment_dialect_reports_a_body_repeat_too(self) -> None:
        parsed = parse_manuscript(
            "<!-- claim: id=c1"
            + NL
            + "source: paper"
            + NL
            + "source: alt"
            + NL
            + "quote: |"
            + NL
            + "  "
            + QUOTE
            + NL
            + "-->"
            + NL,
            path="m.md",
        )
        assert "claim-field-repeated" in [f.code for f in parsed.findings]
        assert [c.source for c in parsed.claims] == ["paper"]

    def test_the_opening_line_repeat_is_named(self) -> None:
        parsed = parse_manuscript(
            B3
            + "claim id=c1 source=paper source=alt"
            + NL
            + "quote: |"
            + NL
            + "  "
            + QUOTE
            + NL
            + B3
            + NL,
            path="m.md",
        )
        assert "claim-field-repeated" in [f.code for f in parsed.findings]

    def test_one_finding_per_attribute_not_per_spelling(self) -> None:
        parsed = parse_manuscript(
            B3
            + "claim id=c1"
            + NL
            + "source: paper"
            + NL
            + "source: alt"
            + NL
            + "source: other"
            + NL
            + "quote: |"
            + NL
            + "  "
            + QUOTE
            + NL
            + B3
            + NL,
            path="m.md",
        )
        repeats = [f for f in parsed.findings if f.code == "claim-field-repeated"]
        assert len(repeats) == 1

    def test_an_identical_repeat_says_nothing(self) -> None:
        parsed = parse_manuscript(
            B3
            + "claim id=c1"
            + NL
            + "source: paper"
            + NL
            + "source: paper"
            + NL
            + "quote: |"
            + NL
            + "  "
            + QUOTE
            + NL
            + B3
            + NL,
            path="m.md",
        )
        assert "claim-field-repeated" not in [f.code for f in parsed.findings]

    def test_the_aliased_pair_keeps_its_own_finding(self) -> None:
        parsed = parse_manuscript(
            B3
            + "claim id=c1 source=paper ref=paper cite=other"
            + NL
            + "quote: |"
            + NL
            + "  "
            + QUOTE
            + NL
            + B3
            + NL,
            path="m.md",
        )
        codes = [f.code for f in parsed.findings]
        assert "claim-field-conflict" in codes
        assert "claim-field-repeated" not in codes


class TestTheVerdictOnAProject:
    def test_the_first_source_is_the_one_searched(self, project: Path) -> None:
        _write(
            project,
            B3
            + "claim id=c1 source=paper source=alt"
            + NL
            + "quote: |"
            + NL
            + "  "
            + QUOTE
            + NL
            + B3
            + NL,
        )
        code, text = _run(project, "check", "m.md")
        assert "quote-missing" not in text
        assert "quote-found" in text
        assert code == 0

    def test_the_author_is_told_even_when_the_verdict_is_fine(self, project: Path) -> None:
        _write(
            project,
            B3
            + "claim id=c1 source=paper source=alt"
            + NL
            + "quote: |"
            + NL
            + "  "
            + QUOTE
            + NL
            + B3
            + NL,
        )
        _code, text = _run(project, "check", "m.md")
        assert "claim-field-repeated" in text

    def test_the_ledger_records_the_value_that_was_used(self, project: Path) -> None:
        _write(
            project,
            B3
            + "claim id=c1 source=paper source=alt"
            + NL
            + "quote: |"
            + NL
            + "  "
            + QUOTE
            + NL
            + B3
            + NL,
        )
        _run(project, "scan", "m.md")
        blob = (project / "citevouch.lock.json").read_text(encoding="utf-8")
        assert '"paper"' in blob
        assert '"alt"' not in blob
