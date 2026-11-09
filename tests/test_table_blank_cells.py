"""A table row with an empty cell is a claim the author has not finished.

Measured before this fix, on a one-page source whose quote is verbatim on page
1, with the row's `page` cell left blank:

    | id | source | page | quote | claim |
    |---|---|---|---|---|
    | c1 | paper |  | <quote> | ok |

    -> [high] no-claim-blocks at m.md: "m.md contains no claim blocks, so
       nothing was checked ... This file has none.", exit 1

over a file that plainly holds one.  The same row with the `id` cell blank said
the same thing, and a row whose `page` cell was blank was dropped from a file
that held a good row as well - the run reported `1 claim - 1 verified` and no
line at all mentioned the second row.

The cause is `_TABLE_CLAIM`: its `id` cell required one character and its
`page` cell required a digit or `-`, so a row with an unfinished cell matched
nothing and the file looked empty.  Both omissions already have an honest
answer once the row is read: a blank id is `claim-uncheckable ... has no id=`,
and a blank page is "no page hint" (the same thing `-` means).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from citevouch.manuscript import parse_manuscript

NL = chr(10)
# The em dash in the summary line is a byte sequence, not a character, until
# both ends of the pipe agree on an encoding. Left alone, the child writes with
# the Windows code page and the parent decodes with the locale, which is UTF-8
# on this machine and cp1252 on the runner - so the same assertion passed here
# and failed on all three windows-latest jobs (E2 80 94 on one side of the
# comparison, EF BF BD on the other). Pin both ends instead of trusting the
# ambient locale.
ENV = {
    **os.environ,
    "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
    "PYTHONIOENCODING": "utf-8",
}
PAGE = "We collected 154,391 examples from the corpus."
MANIFEST = "[sources]" + NL + 'paper = "page.txt"' + NL
HEADER = "| id | source | page | quote | claim |" + NL + "|---|---|---|---|---|" + NL


def _row(cid: str = "c1", source: str = "paper", page: str = "1") -> str:
    return f"| {cid} | {source} | {page} | {PAGE} | it says so |" + NL


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
        line.split(":")[0].removeprefix("[high] ").removeprefix("[medium] ")
        for line in proc.stdout.splitlines()
        if line.startswith("[")
    ]


class TestABlankCellIsNotAnEmptyFile:
    def test_a_blank_page_cell_still_reads_the_row(self, tmp_path):
        root = _project(tmp_path, HEADER + _row(page=""))
        result = _run(root, "check", "m.md")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "1 claim — 1 verified" in result.stdout
        assert "This file has none" not in result.stdout

    def test_a_blank_id_cell_is_named_not_erased(self, tmp_path):
        root = _project(tmp_path, HEADER + _row(cid=""))
        result = _run(root, "check", "m.md")
        assert result.returncode == 1, result.stdout + result.stderr
        assert "claim-uncheckable" in result.stdout
        assert "This file has none" not in result.stdout

    def test_the_blank_row_does_not_disappear_behind_a_good_one(self, tmp_path):
        # The quietest shape: one row the parser cannot read, one it can. The
        # run used to report a perfect single-claim file with no line about the
        # row it walked past.
        root = _project(tmp_path, HEADER + _row(page="") + _row(cid="c2"))
        result = _run(root, "check", "m.md")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "2 claims — 2 verified" in result.stdout

    def test_a_blank_source_cell_is_already_named(self, tmp_path):
        root = _project(tmp_path, HEADER + _row(source=""))
        result = _run(root, "check", "m.md")
        assert result.returncode == 1
        assert "claim-uncheckable" in result.stdout


class TestTheParserItself:
    def test_a_blank_page_cell_means_no_page_hint(self):
        result = parse_manuscript(HEADER + _row(page=""), "m.md")
        assert result.claims, [f.code for f in result.findings]
        assert result.claims[0].page is None

    def test_a_blank_id_cell_makes_an_uncheckable_claim(self):
        result = parse_manuscript(HEADER + _row(cid=""), "m.md")
        assert not result.claims
        assert [f.code for f in result.findings] == ["claim-uncheckable"]

    @pytest.mark.parametrize("page", ["-", ""])
    def test_both_spellings_of_no_hint_agree(self, page):
        result = parse_manuscript(HEADER + _row(page=page), "m.md")
        assert result.claims, [f.code for f in result.findings]
        assert result.claims[0].page is None

    def test_a_header_row_is_not_a_claim(self):
        # The row above a claim table looks the same shape; it must not become
        # a claim now that an empty cell is allowed.
        result = parse_manuscript(HEADER, "m.md")
        assert not result.claims


class TestTheWrapperDetectorSeesTheSameShape:
    """The table opener is derived from `_TABLE_CLAIM`, not retyped.

    A row inside a blockquote is not a claim (Markdown renders it as a code
    sample), but it is still a claim-shaped line, and the run has to name it.
    The detector that finds such lines reuses `_TABLE_CLAIM.pattern`; a second
    hand-typed copy is a copy that drifts, and a drifted copy here means the
    blank-cell row becomes invisible twice over - not parsed, and not named.
    """

    @pytest.mark.parametrize(
        "row", [_row(cid=""), _row(page="")], ids=["blank-id", "blank-page"]
    )
    def test_a_wrapped_blank_row_is_still_named(self, tmp_path, row):
        root = _project(tmp_path, "> " + row)
        result = _run(root, "check", "m.md")
        assert result.returncode == 1, result.stdout + result.stderr
        assert "blockquote" in result.stdout
        assert "line 1" in result.stdout
