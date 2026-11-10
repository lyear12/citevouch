"""The three writers that print counts must print the same counts.

`check --format text` ends with a tally line, `--format json` carries a
`summary` object, and `--format markdown` - the one `action.yml` puts in a PR
comment - opens with a bold summary row.  They are three renderings of one
`VerifyResult`, so a number one of them leaves out is a number the reader of
that surface cannot know.

Measured before this file existed, on a claim whose source file exists but holds
no text (`skipped` is 1, and the run exits 1 on a `high` finding)::

    --format text      citevouch: 1 claim — 0 verified, 0 moved, 0 missing, 1 skipped
    --format json      {"checked": 1, ..., "skipped": 1}
    --format markdown  **1** claim · **0** verified · **0** moved · **0** missing

The markdown row is the only one a reviewer reads in the PR, and its four
numbers add up to zero while the run is red over one claim.  A sentence whose
counts account for none of the document is the same defect as a tally that
counts what the ledger recorded instead of what the file holds: the reader adds
up what they can see and concludes the rest did not happen.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from citevouch.cli import main
from citevouch.report import render_json, render_markdown, render_text
from citevouch.verify import VerifyResult

NL = chr(10)
B3 = chr(96) * 3

GOOD_QUOTE = "The corpus holds 40,688 examples."
CLAIM = (
    B3
    + "claim id=c1 source=paper page=1"
    + NL
    + "quote: |"
    + NL
    + "  "
    + GOOD_QUOTE
    + NL
    + B3
    + NL
)


def _project(tmp_path: Path, page: str) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    (root / "page.txt").write_text(page, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    (root / "manuscript.md").write_text(CLAIM, encoding="utf-8", newline=NL)
    return root


def _run(root: Path, fmt: str) -> int:
    return main(["check", "manuscript.md", "--root", str(root), "--format", fmt])


def _text_counts(captured: str) -> dict[str, int]:
    tally = [line for line in captured.splitlines() if line.startswith("citevouch:")]
    assert tally, captured
    line = tally[0]
    found = {
        "checked": re.search(r"citevouch: (\d+) claim", line),
        "verified": re.search(r"(\d+) verified", line),
        "moved": re.search(r"(\d+) moved", line),
        "missing": re.search(r"(\d+) missing", line),
        "skipped": re.search(r"(\d+) skipped", line),
    }
    return {key: int(match.group(1)) if match else 0 for key, match in found.items()}


def _markdown_counts(captured: str) -> dict[str, int]:
    row = [line for line in captured.splitlines() if line.startswith("**")]
    assert row, captured
    line = row[0]
    found = {
        "checked": re.search(r"\*\*(\d+)\*\* claims?", line),
        "verified": re.search(r"\*\*(\d+)\*\* verified", line),
        "moved": re.search(r"\*\*(\d+)\*\* moved", line),
        "missing": re.search(r"\*\*(\d+)\*\* missing", line),
        "skipped": re.search(r"\*\*(\d+)\*\* skipped", line),
    }
    return {key: int(match.group(1)) if match else 0 for key, match in found.items()}


class TestTheWritersAgreeOnEveryCount:
    """One `VerifyResult`, three renderings, the same numbers."""

    @pytest.mark.parametrize(
        "result",
        [
            VerifyResult(checked=1, verified=0, moved=0, missing=0, skipped=1),
            VerifyResult(checked=3, verified=2, moved=0, missing=0, skipped=1),
            VerifyResult(checked=2, verified=0, moved=1, missing=0, skipped=1),
            VerifyResult(checked=4, verified=1, moved=1, missing=1, skipped=1),
            VerifyResult(checked=2, verified=2),
        ],
        ids=["skipped-only", "one-of-three", "moved", "all-four", "nothing-skipped"],
    )
    def test_no_writer_leaves_a_count_out(self, result: VerifyResult) -> None:
        findings: list = []
        assert _text_counts(render_text(findings, result)) == {
            "checked": result.checked,
            "verified": result.verified,
            "moved": result.moved,
            "missing": result.missing,
            "skipped": result.skipped,
        }
        assert _markdown_counts(render_markdown(findings, result)) == {
            "checked": result.checked,
            "verified": result.verified,
            "moved": result.moved,
            "missing": result.missing,
            "skipped": result.skipped,
        }
        summary = json.loads(render_json(findings, None, result))["summary"]
        assert summary["skipped"] == result.skipped

    def test_a_clean_run_does_not_grow_a_new_word(self) -> None:
        """Nothing skipped means the row has to read exactly as it always did."""
        result = VerifyResult(checked=2, verified=2)
        markdown = render_markdown([], result)
        assert "skipped" not in markdown
        assert "skipped" not in render_text([], result)

    def test_the_first_row_counts_claims_and_the_second_counts_blocks(self) -> None:
        """Two rows, two nouns: a claim somebody checked, and a block nobody could.

        The first row says how many claims this run judged; the second says how
        many blocks the file holds that it could not turn into claims.  Counting
        blocks in the first row makes the file look like it holds more claims
        than it does, and the reader has no way to see the difference because
        both rows are right below each other.
        """
        result = VerifyResult(checked=2, verified=1, skipped=1, unrecorded=1)
        assert result.blocks == 3
        rows = [
            line for line in render_markdown([], result).splitlines() if line.startswith("**")
        ]
        assert re.search(r"\*\*2\*\* claims ·", rows[0]), rows
        assert "**3**" not in rows[0], rows
        assert "**3** claim blocks" in rows[1], rows

    def test_the_row_says_skipped_once(self) -> None:
        """One number, one mention.  A row that says it twice cannot be read."""
        result = VerifyResult(checked=2, verified=1, skipped=1, unrecorded=1)
        rows = [
            line for line in render_markdown([], result).splitlines() if line.startswith("**")
        ]
        assert rows[0].count("skipped") == 1, rows[0]
        assert "skipped" in rows[0], rows[0]

    def test_the_markdown_counts_account_for_every_checked_claim(self) -> None:
        """The row has to add up, or it describes a smaller document."""
        result = VerifyResult(checked=5, verified=2, moved=1, missing=1, skipped=1)
        counts = _markdown_counts(render_markdown([], result))
        assert (
            counts["verified"] + counts["moved"] + counts["missing"] + counts["skipped"]
            == counts["checked"]
        )


class TestTheShapeNobodyWroteDown:
    """A claim that was checked and then skipped, on a real project."""

    def test_a_source_with_no_text_is_counted_as_skipped_everywhere(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root = _project(tmp_path, "")
        code = _run(root, "text")
        text = capsys.readouterr()
        assert code == 1
        assert _text_counts(text.out)["skipped"] == 1
        assert _text_counts(text.out)["checked"] == 1

        code = _run(root, "markdown")
        markdown = capsys.readouterr()
        assert code == 1
        counts = _markdown_counts(markdown.out)
        assert counts["skipped"] == 1, markdown.out
        assert counts["checked"] == 1

    def test_a_skipped_claim_is_not_reported_as_missing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Skipped means "not judged", which is not "the quote is not there"."""
        root = _project(tmp_path, "")
        _run(root, "text")
        captured = capsys.readouterr()
        assert _text_counts(captured.out)["missing"] == 0
        assert "quote-missing" not in captured.out
