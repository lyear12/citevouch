"""A claim body line that reads like a field, but names no key this format has.

Measured before the fix, on a project whose quote really is on page 2 and whose
page hint was misspelt:

    Page: 1 above ``quote:``  -> the hint was dropped, no finding, exit 0
    Page: 1 below ``quote:``  -> the line joined the quote, and the run printed
                                 [high] quote-missing "…constructions. Page: 1"

The first is a check switched off in silence.  The second is an accusation
against the author for a typo in their own field name - the failure this file
exists to keep out of the tool.

In a ``quote: |`` block a line at the left margin is a sibling key in YAML and
never continuation text, so the reading that loses nothing is: this is a field,
it is not one this format has, and the reader is told both facts by line.
"""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

import pytest

from citevouch.cli import main
from citevouch.manuscript import parse_manuscript

B3 = "`" * 3
QUOTE = "The resulting grammar consists of a network of 40,688 constructions."
PAGE_ONE = "A first page of other words."
PAGE_TWO = "A second page, and on it: " + QUOTE


def _fenced(body: str, attrs: str = "id=c1 source=paper") -> str:
    return (
        "# T"
        + chr(10)
        + chr(10)
        + f"{B3}claim {attrs}"
        + chr(10)
        + body
        + chr(10)
        + B3
        + chr(10)
    )


def _commented(body: str, attrs: str = "id=c1 source=paper") -> str:
    return (
        "# T"
        + chr(10)
        + chr(10)
        + f"<!-- claim {attrs}"
        + chr(10)
        + body
        + chr(10)
        + "-->"
        + chr(10)
    )


def _project(tmp_path: Path, manuscript: str) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "page.txt").write_text(
        PAGE_ONE + chr(12) + PAGE_TWO + chr(10), encoding="utf-8", newline="\n"
    )
    (root / "sources.toml").write_text(
        "[sources]" + chr(10) + 'paper = "page.txt"' + chr(10), encoding="utf-8", newline="\n"
    )
    (root / "m.md").write_text(manuscript, encoding="utf-8", newline="\n")
    return root


def _run(root: Path, *args: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main([*args, "m.md", "--root", str(root)])
    return code, out.getvalue()


class TestTheParserSaysWhichLineAndWhichKey:
    def test_a_line_above_the_quote_is_named(self) -> None:
        body = "Page: 1" + chr(10) + "quote: |" + chr(10) + "  " + QUOTE
        result = parse_manuscript(_fenced(body))
        assert [finding.code for finding in result.findings] == ["claim-field-unknown"]
        assert result.findings[0].line == 4, "the line the editor shows"
        assert "line 4" in result.findings[0].message, "the message names the line too"

    def test_a_line_below_the_quote_is_named_and_stays_out_of_it(self) -> None:
        body = "quote: |" + chr(10) + "  " + QUOTE + chr(10) + "Page: 1"
        result = parse_manuscript(_fenced(body))
        assert [claim.quote for claim in result.claims] == [QUOTE]
        assert [finding.code for finding in result.findings] == ["claim-field-unknown"]
        assert "Page" in result.findings[0].message

    @pytest.mark.parametrize("key", ["Page", "pge", "pages", "footnote", "Source"])
    def test_every_spelling_is_named_by_its_own_name(self, key: str) -> None:
        body = "quote: |" + chr(10) + "  " + QUOTE + chr(10) + f"{key}: 1"
        result = parse_manuscript(_fenced(body))
        assert key in result.findings[0].message

    def test_two_unknown_keys_are_two_findings(self) -> None:
        body = (
            "Page: 1"
            + chr(10)
            + "Source: paper"
            + chr(10)
            + "quote: |"
            + chr(10)
            + "  "
            + QUOTE
        )
        result = parse_manuscript(_fenced(body))
        assert len([f for f in result.findings if f.code == "claim-field-unknown"]) == 2

    def test_the_html_dialect_is_told_too(self) -> None:
        body = "quote: |" + chr(10) + "  " + QUOTE + chr(10) + "Page: 1"
        result = parse_manuscript(_commented(body))
        assert [finding.code for finding in result.findings] == ["claim-field-unknown"]


class TestWhatIsNotAField:
    def test_an_indented_line_is_continuation_text(self) -> None:
        body = (
            "quote: |" + chr(10) + "  " + QUOTE + chr(10) + "  Page: 1 is what the source says"
        )
        result = parse_manuscript(_fenced(body))
        assert result.findings == []
        assert [claim.quote for claim in result.claims] == [
            QUOTE + chr(10) + "Page: 1 is what the source says"
        ]

    def test_a_correct_key_is_quiet(self) -> None:
        body = "quote: |" + chr(10) + "  " + QUOTE + chr(10) + "page: 1"
        result = parse_manuscript(_fenced(body))
        assert result.findings == []
        assert [claim.page for claim in result.claims] == [1]

    def test_a_numbers_line_is_still_a_known_key(self) -> None:
        body = "quote: |" + chr(10) + "  " + QUOTE + chr(10) + "numbers: 1"
        result = parse_manuscript(_fenced(body))
        assert result.findings == []

    def test_a_body_without_keys_is_untouched(self) -> None:
        result = parse_manuscript(_fenced(QUOTE))
        assert result.findings == []
        assert [claim.quote for claim in result.claims] == [QUOTE]


class TestTheTwoSilentPathsAreGone:
    def test_the_dropped_hint_is_no_longer_silent(self, tmp_path: Path) -> None:
        body = "Page: 1" + chr(10) + "quote: |" + chr(10) + "  " + QUOTE
        root = _project(tmp_path, _fenced(body))
        code, output = _run(root, "check")
        assert "claim-field-unknown" in output
        assert code == 0, "a medium finding is below the default --fail-on high"

    def test_the_false_accusation_is_gone(self, tmp_path: Path) -> None:
        body = "quote: |" + chr(10) + "  " + QUOTE + chr(10) + "Page: 1"
        root = _project(tmp_path, _fenced(body))
        code, output = _run(root, "check")
        assert "quote-missing" not in output, (
            "the quote is on the page; only the field was wrong"
        )
        assert "quote-found" in output
        assert code == 0

    def test_the_hint_still_works_when_it_is_spelt_right(self, tmp_path: Path) -> None:
        body = "quote: |" + chr(10) + "  " + QUOTE + chr(10) + "page: 2"
        root = _project(tmp_path, _fenced(body))
        code, output = _run(root, "check")
        assert "claim-field-unknown" not in output
        assert code == 0

    def test_a_wrong_page_hint_is_still_a_wrong_page_hint(self, tmp_path: Path) -> None:
        body = "quote: |" + chr(10) + "  " + QUOTE + chr(10) + "page: 1"
        root = _project(tmp_path, _fenced(body))
        code, output = _run(root, "check")
        assert "quote-moved" in output
        assert code == 0

    def test_fail_on_medium_refuses_the_run(self, tmp_path: Path) -> None:
        body = "quote: |" + chr(10) + "  " + QUOTE + chr(10) + "Page: 1"
        root = _project(tmp_path, _fenced(body))
        code, _ = _run(root, "check", "--fail-on", "medium")
        assert code == 1

    def test_scan_and_verify_say_it_too(self, tmp_path: Path) -> None:
        body = "quote: |" + chr(10) + "  " + QUOTE + chr(10) + "Page: 1"
        root = _project(tmp_path, _fenced(body))
        scanned, out_scan = _run(root, "scan")
        assert "claim-field-unknown" in out_scan
        verified, out_verify = _run(root, "verify")
        assert "claim-field-unknown" in out_verify
        # Both are medium, so the default `--fail-on high` lets them pass -
        # the same rule the check tests above rely on.  What matters for
        # this file is that neither verb is silent about it.
        assert scanned == 0 and verified == 0
        scanned, _ = _run(root, "scan", "--fail-on", "medium")
        verified, _ = _run(root, "verify", "--fail-on", "medium")
        assert scanned == 1 and verified == 1

    def test_the_sarif_rule_exists(self, tmp_path: Path) -> None:
        body = "quote: |" + chr(10) + "  " + QUOTE + chr(10) + "Page: 1"
        root = _project(tmp_path, _fenced(body))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            main(["check", "m.md", "--root", str(root), "--format", "sarif"])
        blob = json.loads(out.getvalue())
        rules = [rule["id"] for rule in blob["runs"][0]["tool"]["driver"]["rules"]]
        assert "claim-field-unknown" in rules
