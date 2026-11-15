"""A ledger records *one* document, and scanning another into it says so.

``scan`` writes whatever document it was pointed at into whatever ledger it was
given.  On a project whose ledger already describes the manuscript, that made
``scan claims.md`` - which is exactly what ``draft``'s own output used to print
as advice - replace the record of the manuscript with a record of the
proposals: exit 0, nothing on stderr, and the next ``check final.md
--use-recorded`` said ``[high] ledger-stale`` about a manuscript nobody had
touched (measured in ``docs/final-manuscript.md``; task CV-022).

Two things are pinned here, because either one alone leaves the trap reachable
by following the tool's instructions:

* ``scan`` refuses to retarget a ledger that names another document, and the
  refusal names both documents and a command that keeps both;
* ``draft`` prints a ``scan`` command that writes a second ledger, and that
  command actually runs.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
B3 = chr(96) * 3
ENV = {**os.environ, "PYTHONPATH": str(SRC), "PYTHONIOENCODING": "utf-8"}

PAGE = "We collected 40,688 examples from the corpus.\n"

BLOCK = (
    B3
    + "claim id=c1 source=paper\n"
    + "quote: |\n"
    + "  We collected 40,688 examples from the corpus.\n"
    + "claim: |\n"
    + "  We collected 40,688 examples.\n"
    + B3
    + "\n"
)

MANUSCRIPT = "# Method\n\nWe collected 40,688 examples from the corpus [@paper].\n\n" + BLOCK


def _project(parent: Path) -> Path:
    root = parent / "proj"
    root.mkdir(parents=True)
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline="\n")
    (root / "sources.toml").write_text(
        '[sources]\npaper = "page.txt"\n', encoding="utf-8", newline="\n"
    )
    (root / "final.md").write_text(MANUSCRIPT, encoding="utf-8", newline="\n")
    return root


def _run(root: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "citevouch", *argv],
        cwd=root,
        env=ENV,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _recorded(root: Path, name: str = "citevouch.lock.json") -> dict:
    return json.loads((root / name).read_text(encoding="utf-8"))


def _header(root: Path) -> str:
    """The two comment blocks ``draft`` puts at the top of its output."""
    text = (root / "claims.md").read_text(encoding="utf-8")
    end = text.find("-->", text.find("-->") + 1)
    assert end != -1, text[:400]
    return text[: end + 3]


class TestALedgerIsAboutOneDocument:
    def test_recording_the_same_document_again_is_the_ordinary_repair(
        self, tmp_path: Path
    ) -> None:
        root = _project(tmp_path)
        first = _run(root, "scan", "final.md")
        assert first.returncode == 0, first.stdout + first.stderr
        again = _run(root, "scan", "final.md")
        assert again.returncode == 0, again.stdout + again.stderr
        assert _recorded(root)["manuscript"] == "final.md"

    def test_scanning_another_document_into_the_project_ledger_is_refused(
        self, tmp_path: Path
    ) -> None:
        root = _project(tmp_path)
        assert _run(root, "scan", "final.md").returncode == 0
        (root / "claims.md").write_text(BLOCK, encoding="utf-8", newline="\n")

        refused = _run(root, "scan", "claims.md")

        assert refused.returncode == 2, refused.stdout + refused.stderr
        assert "usage error" in refused.stderr.lower() or "already records" in refused.stderr
        # Both documents are named: a message that says only "refused" leaves
        # the reader unable to tell which half is wrong.
        assert "final.md" in refused.stderr and "claims.md" in refused.stderr
        assert _recorded(root)["manuscript"] == "final.md", (
            "the ledger must still describe the manuscript it described before"
        )

    def test_the_refusal_names_a_command_that_keeps_both_records(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        assert _run(root, "scan", "final.md").returncode == 0
        (root / "claims.md").write_text(BLOCK, encoding="utf-8", newline="\n")
        refused = _run(root, "scan", "claims.md")
        assert "--ledger claims.lock.json" in refused.stderr

        # Run the command out of the message rather than trusting its shape.
        kept = _run(root, "scan", "claims.md", "--ledger", "claims.lock.json")
        assert kept.returncode == 0, kept.stdout + kept.stderr
        assert _recorded(root, "claims.lock.json")["manuscript"] == "claims.md"
        assert _recorded(root)["manuscript"] == "final.md"

    def test_a_dry_run_says_what_it_would_say_and_writes_nothing(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        assert _run(root, "scan", "final.md").returncode == 0
        (root / "claims.md").write_text(BLOCK, encoding="utf-8", newline="\n")
        before = (root / "citevouch.lock.json").read_bytes()

        dry = _run(root, "scan", "claims.md", "--dry-run")

        # A dry run has written nothing, so the ledger is not at risk and the
        # refusal would be a sentence about a write that was never going to
        # happen.  What it must not do is change the file.
        assert dry.returncode == 0, dry.stdout + dry.stderr
        assert (root / "citevouch.lock.json").read_bytes() == before

    def test_a_ledger_that_cannot_be_read_is_still_overwritten(self, tmp_path: Path) -> None:
        """Only a *proved* difference is refused.

        A file that is not a ledger cannot name another document, so this run
        has no fact to act on; refusing would turn every damaged ledger into a
        project that can no longer be recorded, and ``scan`` is the repair.
        """
        for name, payload in (
            ("unparsable", "{not json"),
            ("not an object", "[]"),
            ("an object without claims", '{"schema": 1}'),
        ):
            root = _project(tmp_path / name.replace(" ", "-"))
            (root / "citevouch.lock.json").write_text(payload, encoding="utf-8", newline="\n")
            replaced = _run(root, "scan", "final.md")
            assert replaced.returncode == 0, f"{name}: " + replaced.stdout + replaced.stderr
            assert _recorded(root)["manuscript"] == "final.md", name

    def test_a_ledger_without_a_manuscript_name_is_overwritten(self, tmp_path: Path) -> None:
        """A ledger that names no document has no other document to be about.

        ``manuscript`` is written by every ``scan``; a file that lacks it was
        damaged, and the honest answer is to record the run rather than to
        refuse a repair because the broken thing cannot be asked what it meant.
        """
        root = _project(tmp_path)
        (root / "citevouch.lock.json").write_text(
            json.dumps({"schema": 1, "claims": [], "sources": {}}),
            encoding="utf-8",
            newline="\n",
        )
        replaced = _run(root, "scan", "final.md")
        assert replaced.returncode == 0, replaced.stdout + replaced.stderr
        assert _recorded(root)["manuscript"] == "final.md"

    def test_check_never_writes_a_ledger(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        assert _run(root, "draft", "final.md").returncode == 0
        checked = _run(root, "check", "claims.md")
        assert checked.returncode == 0, checked.stdout + checked.stderr
        assert not (root / "citevouch.lock.json").exists()


class TestDraftsAdviceIsNotTheTrap:
    def test_the_header_names_a_ledger_of_its_own(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        drafted = _run(root, "draft", "final.md")
        assert drafted.returncode == 0, drafted.stdout + drafted.stderr
        header = _header(root)
        assert "--ledger claims.lock.json" in header, header
        # The bare command is what replaced the project's ledger.
        assert "`citevouch scan`" not in header

    def test_the_advice_it_prints_can_be_run(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        assert _run(root, "draft", "final.md").returncode == 0
        assert _run(root, "scan", "claims.md", "--ledger", "claims.lock.json").returncode == 0
        assert _recorded(root, "claims.lock.json")["manuscript"] == "claims.md"

    def test_the_advice_is_the_same_bytes_from_either_side(self, tmp_path: Path) -> None:
        """The header names paths the way the ledger does, not the way this run ran.

        An absolute path, or a ``--root`` carved out of this invocation, makes
        the same project produce different bytes depending on where the command
        was typed from - which broke three existing equivalence tests when it
        was tried.  The header therefore carries the root-relative spelling and
        says where to run it from, so the advice is both diffable and runnable.
        """
        inside = _project(tmp_path / "inside")
        above = tmp_path / "above"
        above.mkdir()
        outside = _project(above)

        assert _run(inside, "draft", "final.md").returncode == 0
        drafted = subprocess.run(
            [sys.executable, "-m", "citevouch", "draft", "proj/final.md", "--root", "proj"],
            cwd=above,
            env=ENV,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert drafted.returncode == 0, drafted.stdout + drafted.stderr

        first = _header(inside)
        second = _header(outside)
        assert "--root" not in second, second
        assert first == second, first + "\n---\n" + second
        assert "from the project root" in second, second

        ran = subprocess.run(
            [
                sys.executable,
                "-m",
                "citevouch",
                "scan",
                "claims.md",
                "--ledger",
                "claims.lock.json",
            ],
            cwd=outside,
            env=ENV,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert ran.returncode == 0, ran.stdout + ran.stderr
        assert _recorded(outside, "claims.lock.json")["manuscript"] == "claims.md"


class TestTheRefusalIsNotAskingForPermission:
    def test_it_is_a_usage_error_not_a_finding(self, tmp_path: Path) -> None:
        """Exit 2 means "you asked for something impossible", not "a claim failed".

        A finding would be a statement about the manuscript.  This is a
        statement about the command, and CI distinguishes the two.
        """
        root = _project(tmp_path)
        assert _run(root, "scan", "final.md").returncode == 0
        (root / "claims.md").write_text(BLOCK, encoding="utf-8", newline="\n")
        refused = _run(root, "scan", "claims.md")
        assert refused.returncode == 2
        assert "citevouch: " in refused.stderr


@pytest.mark.parametrize("severity", ["high"])
def test_the_severity_is_not_involved(tmp_path: Path, severity: str) -> None:
    """A ledger with a claim the parser refused still names its manuscript."""
    root = _project(tmp_path)
    (root / "final.md").write_text(
        "# Method\n\n" + B3 + "claim\nquote: |\n  something else entirely.\n" + B3 + "\n",
        encoding="utf-8",
        newline="\n",
    )
    _run(root, "scan", "final.md")
    # The scan may report findings (a block with no id=), but it still recorded
    # the file it was pointed at, and that record is what the guard reads.
    assert _recorded(root)["manuscript"] == "final.md"
    (root / "claims.md").write_text(BLOCK, encoding="utf-8", newline="\n")
    assert _run(root, "scan", "claims.md").returncode == 2
    assert _recorded(root)["manuscript"] == "final.md"
    assert severity == "high"
