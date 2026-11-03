"""A claim block the author wrapped in a blockquote or a list item is skipped.

Measured before this file existed, on a project whose ``page.txt`` holds the
sentence both blocks quote::

    ```claim id=c1 source=paper page=1
    quote: |
      The resulting grammar consists of a network of 40,688 constructions.
    ```

    > ```claim id=c2 source=paper page=1
    > quote: |
    >   The resulting grammar consists of a network of 40,688 constructions.
    > ```

``scan`` wrote ``citevouch.lock.json (1 claim)``, exited **0**, and ``check``
answered ``1 claim - 1 verified, 0 moved, 0 missing`` with ``worst severity:
info``. ``id=c2`` appeared in no finding and in no ledger row.

The same shape with a list marker (``- ```claim``), an ordinal (``1.
```claim``) and a bare indent behaves identically.

The near-miss sentence already in the codebase names the indented case
correctly, but it only runs when the file produced *zero* claims
(``ParseResult.nothing_to_check``). One good block anywhere in the manuscript
switches that sentence off, and every skipped block after it becomes
invisible. Partial recognition is the worst shape: the author is told the
run verified their claims, and it verified some of them.

The decision this file pins: an indented or container-prefixed claim fence is
**not** silently accepted as a claim (Markdown renders an indented fence as a
code sample, and that reading is deliberate), and it is **not** silently
skipped either. It is reported, by line, with the reason it was not read.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from citevouch.manuscript import parse_manuscript

NL = chr(10)
FENCE = "`" * 3

QUOTE = "The resulting grammar consists of a network of 40,688 constructions."
PAGE = "The resulting grammar consists of a network of 40,688 constructions." + NL


def _good(claim_id: str = "c1") -> list[str]:
    return [
        FENCE + f"claim id={claim_id} source=paper page=1",
        "quote: |",
        "  " + QUOTE,
        FENCE,
    ]


def _project(tmp_path: Path, manuscript: str) -> Path:
    (tmp_path / "page.txt").write_text(PAGE, encoding="utf-8", newline=NL)
    (tmp_path / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    (tmp_path / "manuscript.md").write_text(manuscript, encoding="utf-8", newline=NL)
    return tmp_path


def _run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "citevouch",
            *args,
            str(root / "manuscript.md"),
            "--root",
            str(root),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _codes(result) -> list[str]:
    return [finding.code for finding in result.findings]


BLOCKQUOTE = [
    "> " + FENCE + "claim id=c2 source=paper page=1",
    "> quote: |",
    ">   " + QUOTE,
    "> " + FENCE,
]
LIST_ITEM = [
    "- " + FENCE + "claim id=c2 source=paper page=1",
    "  quote: |",
    "  " + QUOTE,
    "  " + FENCE,
]
ORDINAL = [
    "1. " + FENCE + "claim id=c2 source=paper page=1",
    "   quote: |",
    "   " + QUOTE,
    "   " + FENCE,
]
INDENTED = [
    "  " + FENCE + "claim id=c2 source=paper page=1",
    "  quote: |",
    "  " + QUOTE,
    "  " + FENCE,
]

SHAPES = {
    "blockquote": BLOCKQUOTE,
    "list_item": LIST_ITEM,
    "ordinal": ORDINAL,
    "indented": INDENTED,
}


class TestTheParserSaysItSkippedABlock:
    @pytest.mark.parametrize("name", sorted(SHAPES))
    def test_a_wrapped_block_is_reported_not_swallowed(self, name: str) -> None:
        text = NL.join([*_good(), "", "Prose between the two blocks.", "", *SHAPES[name], ""])
        parsed = parse_manuscript(text, "manuscript.md")
        assert [claim.id for claim in parsed.claims] == ["c1"], "the good block still parses"
        assert "claim-block-unread" in [finding.code for finding in parsed.findings], [
            finding.code for finding in parsed.findings
        ]

    @pytest.mark.parametrize("name", sorted(SHAPES))
    def test_the_finding_names_the_line_the_author_wrote(self, name: str) -> None:
        body = ["intro", "", *_good(), "", "Prose between.", ""]
        text = NL.join([*body, *SHAPES[name], ""])
        parsed = parse_manuscript(text, "manuscript.md")
        unread = [f for f in parsed.findings if f.code == "claim-block-unread"]
        assert len(unread) == 1, [f.message for f in parsed.findings]
        # 1 intro, 2 blank, 3-6 the good block, 7 blank, 8 prose, 9 blank -> 10
        assert unread[0].line == 10, unread[0].line
        assert "c2" in unread[0].message or "line 10" in unread[0].message

    def test_two_of_them_are_both_named(self) -> None:
        text = NL.join([*_good(), "", *BLOCKQUOTE, "", *INDENTED, ""])
        parsed = parse_manuscript(text, "manuscript.md")
        unread = [f for f in parsed.findings if f.code == "claim-block-unread"]
        assert len(unread) == 2, [f.message for f in unread]

    def test_a_block_inside_a_four_backtick_sample_is_not_reported(self) -> None:
        """The sample case this feature must not break.

        A manuscript that documents the syntax - four backticks around an
        example claim block - is the reason the parser skips other fences
        wholesale. Nothing inside a sample is a claim, so nothing inside one
        can be a claim the parser failed to read.
        """
        text = NL.join(
            [
                *_good(),
                "",
                FENCE * 2 + "markdown",
                FENCE + "claim id=example source=paper page=1",
                "quote: |",
                "  sample text",
                FENCE,
                FENCE * 2,
                "",
            ]
        )
        parsed = parse_manuscript(text, "manuscript.md")
        assert [f.code for f in parsed.findings].count("claim-block-unread") == 0

    def test_a_well_formed_manuscript_is_quiet(self) -> None:
        text = NL.join([*_good("c1"), "", *_good("c2"), ""])
        parsed = parse_manuscript(text, "manuscript.md")
        assert [claim.id for claim in parsed.claims] == ["c1", "c2"]
        assert [f.code for f in parsed.findings] == []

    def test_the_html_comment_dialect_is_untouched(self) -> None:
        text = NL.join(
            [
                *_good(),
                "",
                "<!-- claim: c2 source=paper page=1",
                ">> " + QUOTE,
                "-->",
                "",
            ]
        )
        parsed = parse_manuscript(text, "manuscript.md")
        assert [claim.id for claim in parsed.claims] == ["c1", "c2"]


class TestTheCommand:
    def test_scan_exits_one_and_names_the_skipped_block(self, tmp_path: Path) -> None:
        manuscript = NL.join([*_good(), "", "Prose.", "", *BLOCKQUOTE, ""])
        root = _project(tmp_path, manuscript)
        result = _run(root, "scan")
        assert result.returncode == 1, (result.returncode, result.stdout, result.stderr)
        assert "claim-block-unread" in result.stdout, result.stdout

    def test_check_does_not_call_the_run_a_verification(self, tmp_path: Path) -> None:
        manuscript = NL.join([*_good(), "", "Prose.", "", *BLOCKQUOTE, ""])
        root = _project(tmp_path, manuscript)
        result = _run(root, "check")
        assert result.returncode == 1, (result.returncode, result.stdout, result.stderr)
        assert "c2" in result.stdout
        assert "2 claims" not in result.stdout or "unread" in result.stdout

    def test_the_ledger_records_the_refusal_so_the_recorded_path_agrees(
        self, tmp_path: Path
    ) -> None:
        """`action.yml` runs `check --use-recorded`, so this is the CI path."""
        manuscript = NL.join([*_good(), "", "Prose.", "", *BLOCKQUOTE, ""])
        root = _project(tmp_path, manuscript)
        _run(root, "scan")
        recorded = _run(root, "check", "--use-recorded")
        live = _run(root, "check")
        assert recorded.returncode == live.returncode == 1, (
            recorded.returncode,
            live.returncode,
        )
        assert "claim-block-unread" in recorded.stdout, recorded.stdout
