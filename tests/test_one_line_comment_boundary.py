"""A one-line ``<!-- claim ... -->`` must not read the next block as its quote.

Measured on v0.22.68, a project whose source page is

    Preface
    We collected 40,688 examples from the corpus.

Each manuscript below is one documented claim and nothing else.  The one-line
comment dialect has no terminator of its own, so its body runs to the next
block boundary; ``_continues_one_line_html`` says in its own docstring that the
block ends "at a blank line, or where the next construct starts".  Two
constructs were not in the list, and both were read as the quote:

    <!-- claim: c1 source=paper page=1 -->
    ## Methods
    -> [high] quote-missing at manuscript.md:1 (c1): ## Methods — quote not found

    <!-- claim: c1 source=paper page=1 -->
    ---
    -> [high] quote-missing at manuscript.md:1 (c1): --- — quote not found

Both accuse the source page of not printing a Markdown heading and a horizontal
rule.  The claim carries no quote at all, and the true finding is the one the
tool already has for that (`claim-uncheckable`), which at least sends the
author to their own block instead of to their PDF.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from citevouch.manuscript import parse_manuscript

NL = chr(10)

QUOTE = "We collected 40,688 examples from the corpus."
PAGE = "Preface" + NL + QUOTE + NL

OPENER = "<!-- claim: c1 source=paper page=1 -->"


def _parse(*lines: str):
    return parse_manuscript(NL.join(lines) + NL, path="manuscript.md")


def _quote_of(*lines: str) -> list[str]:
    """Every claim's quote; an empty list means the block held no quote at all.

    A block whose quote comes back empty is not accepted as a claim - the
    parser reports ``claim-uncheckable`` instead, which is the honest answer
    for a block that carries no words to search for.
    """
    return [claim.quote for claim in _parse(*lines).claims]


def _codes(*lines: str) -> list[str]:
    return [finding.code for finding in _parse(*lines).findings]


def _run(root: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "citevouch", *argv, "--root", str(root)],
        cwd=root,
        env={
            **os.environ,
            "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
            "PYTHONIOENCODING": "utf-8",
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _project(tmp_path: Path, lines: list[str]) -> Path:
    (tmp_path / "page.txt").write_text(PAGE, encoding="utf-8", newline=NL)
    (tmp_path / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    (tmp_path / "manuscript.md").write_text(NL.join(lines) + NL, encoding="utf-8", newline=NL)
    return tmp_path


class TestABlockThatStartsTheNextThingIsNotTheQuote:
    def test_an_atx_heading_is_not_part_of_the_quote(self) -> None:
        assert _quote_of(OPENER, "## Methods") == []
        assert _codes(OPENER, "## Methods") == ["claim-uncheckable"]

    def test_a_thematic_break_is_not_part_of_the_quote(self) -> None:
        assert _quote_of(OPENER, "---") == []
        assert _codes(OPENER, "---") == ["claim-uncheckable"]

    def test_every_heading_level_starts_a_block(self) -> None:
        for level in range(1, 7):
            heading = "#" * level + " A heading"
            assert _quote_of(OPENER, heading) == [], heading

    def test_every_thematic_break_starts_a_block(self) -> None:
        for rule in ("---", "***", "___", "- - -", "* * *", "------"):
            assert _quote_of(OPENER, rule) == [], rule

    def test_a_deeply_indented_hashtag_is_a_code_block(self) -> None:
        """Four spaces of indent is a code sample, not a heading."""
        # The parser strips the quote, so the indent is not what is asserted -
        # the words are still the author's quote instead of being thrown away.
        assert _quote_of(OPENER, "    # not a heading") == ["# not a heading"]

    def test_two_dashes_are_not_a_break(self) -> None:
        assert _quote_of(OPENER, "--") == ["--"]

    def test_two_stars_are_not_a_break(self) -> None:
        assert _quote_of(OPENER, "**") == ["**"]

    def test_a_hashtag_that_is_not_a_heading_stays_text(self) -> None:
        parsed = _parse(OPENER, "#hashtag no space")
        assert parsed.claims[0].quote == "#hashtag no space"

    def test_a_dash_run_that_is_not_a_break_stays_text(self) -> None:
        parsed = _parse(OPENER, "--- and then some words")
        assert parsed.claims[0].quote == "--- and then some words"


class TestWhatTheDocumentedShapesStillDo:
    def test_the_arrow_marker_still_carries_the_quote(self) -> None:
        parsed = _parse(OPENER, ">> " + QUOTE)
        assert parsed.claims[0].quote == QUOTE

    def test_plain_prose_still_carries_the_quote(self) -> None:
        parsed = _parse(OPENER, QUOTE)
        assert parsed.claims[0].quote == QUOTE

    def test_a_heading_after_the_quote_does_not_join_it(self) -> None:
        parsed = _parse(OPENER, ">> " + QUOTE, "## Methods")
        assert parsed.claims[0].quote == QUOTE


class TestTheVerdictOnAProject:
    def test_a_heading_after_the_block_is_not_a_missing_quote(self, tmp_path: Path) -> None:
        root = _project(tmp_path, [OPENER, "## Methods"])
        proc = _run(root, "check", "manuscript.md")
        assert "quote-missing" not in proc.stdout + proc.stderr
        assert "claim-uncheckable" in proc.stdout + proc.stderr

    def test_a_rule_after_the_block_is_not_a_missing_quote(self, tmp_path: Path) -> None:
        root = _project(tmp_path, [OPENER, "---"])
        proc = _run(root, "check", "manuscript.md")
        assert "quote-missing" not in proc.stdout + proc.stderr
        assert "claim-uncheckable" in proc.stdout + proc.stderr

    def test_a_real_quote_after_a_heading_is_still_checked(self, tmp_path: Path) -> None:
        root = _project(tmp_path, ["## Methods", OPENER, ">> " + QUOTE])
        proc = _run(root, "check", "manuscript.md")
        assert "quote-found" in proc.stdout + proc.stderr
        assert proc.returncode == 0
