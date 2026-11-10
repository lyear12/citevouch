"""A page range in a table claim is a hint the tool cannot apply, and says so.

Measured before this fix, on a one-page source whose quote is verbatim on page
1, with a good row and a row whose `page` cell is a range:

    | id | source | page | quote | text |
    |---|---|---|---|---|
    | c1 | paper | 1 | <quote> | full sentence |
    | c2 | paper | 1-2 | <quote> | full sentence |

    -> citevouch: 1 claim — 1 verified, 0 moved, 0 missing
       worst severity: info
       exit 0

over a file that plainly holds two rows.  The second row is not merely
ignored: it is not mentioned anywhere, so an author reading the tally has no
way to learn it was walked past.  Alone, the same row gave

    -> [high] no-claim-blocks at m.md: "m.md contains no claim blocks, so
       nothing was checked ... This file has none.", exit 1

over a file that holds one.

The cause is `_TABLE_CLAIM`: its `page` cell accepted `\\d+`, `-` or nothing, so
any other spelling made the whole row match nothing.  The fence dialect has had
an honest answer for the same value since it was written - `page=1-2` reports
`[medium] page-unreadable ... the hint is ignored and the quote will be located
by search`, and the claim is verified by search anyway.  So one dialect said
"I did not use your hint" and the other said nothing at all, about the same
value, in the same tool.

`iv` and other spellings that are not a number or a numeric range still match
nothing; that is recorded as a limit rather than pretended away.  Widening the
cell to any text would make a header row a claim, which the last test here
pins.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from citevouch.manuscript import parse_manuscript

NL = chr(10)
ENV = {
    **os.environ,
    "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
    "PYTHONIOENCODING": "utf-8",
}
PAGE = "We collected 154,391 examples from the corpus."
MANIFEST = "[sources]" + NL + 'paper = "page.txt"' + NL
HEADER = "| id | source | page | quote | text |" + NL + "|---|---|---|---|---|" + NL


def _row(cid: str = "c1", page: str = "1") -> str:
    return f"| {cid} | paper | {page} | {PAGE} | it says so |" + NL


def _project(tmp_path: Path, body: str) -> Path:
    root = tmp_path / "project"
    root.mkdir(parents=True, exist_ok=True)
    (root / "page.txt").write_text(PAGE + NL, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(MANIFEST, encoding="utf-8", newline=NL)
    (root / "m.md").write_text(body, encoding="utf-8", newline=NL)
    return root


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "citevouch", *args, "--root", str(root)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=ENV,
        check=False,
    )


def _codes(proc: subprocess.CompletedProcess[str]) -> list[str]:
    return [
        line.split("] ", 1)[1].split(" at ", 1)[0]
        for line in proc.stdout.splitlines()
        if line.startswith("[")
    ]


class TestTheRowIsReadAndTheHintIsRefused:
    def test_a_range_row_is_a_claim(self, tmp_path):
        root = _project(tmp_path, HEADER + _row() + _row("c2", "1-2"))
        result = _run(root, "check", "m.md")
        assert "2 claims — 2 verified" in result.stdout, result.stdout + result.stderr
        assert "This file has none" not in result.stdout
        assert "page-unreadable" in result.stdout

    def test_the_range_row_alone_is_not_an_empty_file(self, tmp_path):
        # The quietly wrong answer: the file holds one row and the run says it
        # holds none, at `high`.
        root = _project(tmp_path, HEADER + _row("c1", "1-2"))
        result = _run(root, "check", "m.md")
        assert "This file has none" not in result.stdout, result.stdout
        assert "1 claim — 1 verified" in result.stdout

    @pytest.mark.parametrize(
        "page",
        ["1-2", "2-1", "1-", "1 – 2", "12–14"],
        ids=["range", "backwards", "open-ended", "spaced-en-dash", "en-dash"],
    )
    def test_every_spelling_of_a_range_is_read(self, page):
        result = parse_manuscript(HEADER + _row("c1", page), "m.md")
        assert [claim.id for claim in result.claims] == ["c1"], [
            f.code for f in result.findings
        ]
        assert result.claims[0].page is None
        assert [f.code for f in result.findings] == ["page-unreadable"]

    def test_the_hint_is_what_gets_refused_not_the_claim(self):
        # A refused hint must not cost the author their verification, which is
        # what `page-unreadable` has always meant for the fence dialect.
        result = parse_manuscript(HEADER + _row("c1", "1-2"), "m.md")
        assert result.claims[0].quote == PAGE

    def test_a_plain_number_still_sets_the_page(self):
        result = parse_manuscript(HEADER + _row("c1", "2"), "m.md")
        assert result.claims[0].page == 2
        assert result.findings == []

    def test_the_tally_does_not_count_a_refused_hint_as_a_skip(self, tmp_path):
        # A refused hint is not a claim the tool declined to judge: both rows
        # are checked and both are verified, so the tally has to say two and
        # the skipped counter has to stay at zero.
        root = _project(tmp_path, HEADER + _row() + _row("c2", "1-2"))
        result = _run(root, "check", "m.md")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "2 claims — 2 verified, 0 moved, 0 missing" in result.stdout
        assert "skipped" not in result.stdout


class TestWhatTheHeaderRowMustKeep:
    def test_a_header_row_is_not_a_claim(self):
        # This is the reason the page cell was narrow in the first place, and
        # it is the reason it did not become "any text".
        result = parse_manuscript(HEADER, "m.md")
        assert not result.claims

    def test_a_separator_row_is_not_a_claim(self):
        result = parse_manuscript(HEADER + "|---|---|---|---|---|" + NL, "m.md")
        assert not result.claims
