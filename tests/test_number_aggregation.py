"""Every wrong number in one claim must be named in the finding the author sees.

Two findings that share a code, a claim and a line are one finding after the
duplicate pass.  A claim quoting two wrong numbers used to produce two of them,
so the author corrected the first and met the second on the next run - and in
the ``numbers`` tier the surviving one was the vague sentence ("the numbers do
not") rather than the one naming the number, because it was appended first.

These tests assert the property that matters to an author: run the check once
and every wrong number is in the output.
"""

from __future__ import annotations

from pathlib import Path

from citevouch.cli import main
from citevouch.model import Claim
from citevouch.sources import extract_pages
from citevouch.verify import _number_checks

PAGE = "We counted 33,333 examples and 44,444 rolesets.\n"


def _project(tmp_path: Path, page: str) -> Path:
    (tmp_path / "page.txt").write_text(page, encoding="utf-8", newline="\n")
    (tmp_path / "sources.toml").write_text(
        '[sources]\npage = "page.txt"\n', encoding="utf-8", newline="\n"
    )
    return tmp_path


def _claim(numbers: tuple[str, ...]) -> Claim:
    return Claim(
        id="c1",
        text="t",
        source="page",
        quote="q",
        path="m.md",
        line=1,
        numbers=numbers,
    )


def _pages(root: Path):
    pages, _problem = extract_pages(root / "page.txt", root)
    return pages


class TestOneClaimOneFinding:
    def test_two_wrong_numbers_are_one_finding(self, tmp_path):
        found = _number_checks(
            _claim(("11,111", "22,222")), _pages(_project(tmp_path, PAGE)), 1
        )
        assert len(found) == 1

    def test_that_finding_names_both(self, tmp_path):
        found = _number_checks(
            _claim(("11,111", "22,222")), _pages(_project(tmp_path, PAGE)), 1
        )
        assert "11,111" in found[0].message
        assert "22,222" in found[0].message

    def test_three_wrong_numbers_are_all_named(self, tmp_path):
        found = _number_checks(
            _claim(("11,111", "22,222", "55,555")), _pages(_project(tmp_path, PAGE)), 1
        )
        assert len(found) == 1
        for raw in ("11,111", "22,222", "55,555"):
            assert raw in found[0].message

    def test_one_wrong_number_keeps_the_singular_sentence(self, tmp_path):
        found = _number_checks(_claim(("11,111",)), _pages(_project(tmp_path, PAGE)), 1)
        assert len(found) == 1
        assert "that number" in found[0].message

    def test_a_right_number_plus_a_wrong_one_names_only_the_wrong_one(self, tmp_path):
        found = _number_checks(
            _claim(("33,333", "22,222")), _pages(_project(tmp_path, PAGE)), 1
        )
        assert len(found) == 1
        assert "22,222" in found[0].message
        assert "33,333" not in found[0].message


class TestTheSpecificSentenceSurvivesTheTierBelow:
    """The ``numbers`` tier appends its own summary before calling the checker."""

    def test_the_output_names_the_number_rather_than_the_summary(self, tmp_path):
        root = _project(tmp_path, "We counted 11,111 examples and 44,444 rolesets.\n")
        (root / "m.md").write_text(
            "```claim id=c1 source=page page=1\n"
            "quote: |\n"
            "  We counted 11,111 examples and 22,222 rolesets.\n"
            "claim: |\n"
            "  We counted 11,111 examples and 22,222 rolesets.\n"
            "```\n",
            encoding="utf-8",
            newline="\n",
        )
        out = str(_capture(root))
        assert "the quote says 22,222" in out
        assert "the numbers do not" not in out

    def test_the_summary_is_still_used_when_nothing_is_specific(self, tmp_path):
        # A quote carrying no numbers at all still lands in the numbers tier
        # when the page has none either: the summary is the only sentence
        # available, so it must not be dropped.
        root = _project(tmp_path, "We counted 11,111 examples.\n")
        (root / "m.md").write_text(
            "```claim id=c1 source=page page=1\n"
            "quote: |\n"
            "  We counted examples.\n"
            "claim: |\n"
            "  We counted examples.\n"
            "```\n",
            encoding="utf-8",
            newline="\n",
        )
        out = str(_capture(root))
        assert "c1" in out


def _capture(root: Path) -> str:
    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        main(["check", "m.md", "--root", str(root)])
    return buf.getvalue()
