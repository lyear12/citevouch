"""A bibliography the recording could not read must still speak on the recorded path.

The ledger records the *entries* a bibliography yielded.  A file that yielded
none - binary, an entry left unclosed, a path that is no longer there - records
as the same empty mapping as a project that named no bibliography at all, so
``check --use-recorded`` (which is what ``action.yml`` runs on every pull
request) used to report a green run for it:

    scan                  -> 1, [high] bib-unreadable
    check --use-recorded  -> 0, [info] quote-found

The fix records the bibliography files themselves in the ledger and re-reads
them in the recorded pass, exactly as the manuscript is re-parsed when its
recorded digest matches.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src")}

PAGE = "We collected 154,391 examples from the corpus.\n"
MANIFEST = '[sources]\npaper = "page.txt"\n'
MANUSCRIPT = (
    "```claim id=c1 source=paper ref=knuth2020 page=1\n"
    "quote: |\n"
    "  We collected 154,391 examples from the corpus.\n"
    "```\n"
)
GOOD_BIB = (
    "@article{knuth2020,"
    + chr(10)
    + "  author = {Knuth, Donald},"
    + chr(10)
    + "  title = {Literate Programming},"
    + chr(10)
    + "  year = {1984},"
    + chr(10)
    + "  journal = {The Computer Journal}"
    + chr(10)
    + "}"
    + chr(10)
)
BINARY_BIB = "\x01\x02\x03 not a bib at all \x04\n"
UNCLOSED_BIB = "@article{broken2020,\n  author = {Someone},\n" + GOOD_BIB


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "citevouch", *args, "--root", str(root)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env=ENV,
    )


def _project(tmp_path: Path, bib: str | None = None, name: str = "") -> Path:
    root = tmp_path / (name or "case")
    root.mkdir(parents=True)
    (root / "page.txt").write_text(PAGE, encoding="utf-8")
    (root / "sources.toml").write_text(MANIFEST, encoding="utf-8")
    (root / "manuscript.md").write_text(MANUSCRIPT, encoding="utf-8")
    if bib is not None:
        (root / "refs.bib").write_text(bib, encoding="utf-8")
    return root


def _scan(root: Path) -> subprocess.CompletedProcess[str]:
    return _run(root, "scan", "manuscript.md", "--bib", "refs.bib")


def _recorded(root: Path) -> subprocess.CompletedProcess[str]:
    return _run(
        root, "check", "manuscript.md", "--use-recorded", "--ledger", "citevouch.lock.json"
    )


def _ledger(root: Path) -> dict:
    return json.loads((root / "citevouch.lock.json").read_text("utf-8"))


class TestTheRecordingNamesTheBibliographyItRead:
    def test_a_good_bibliography_is_named(self, tmp_path: Path) -> None:
        root = _project(tmp_path, GOOD_BIB)
        assert _scan(root).returncode == 0
        assert _ledger(root)["bibliographies"] == ["refs.bib"]

    def test_the_recorded_path_agrees_with_scan_about_a_good_file(self, tmp_path: Path) -> None:
        root = _project(tmp_path, GOOD_BIB)
        _scan(root)
        result = _recorded(root)
        assert result.returncode == 0
        assert "bib-" not in result.stdout

    def test_an_empty_bibliography_stays_quiet(self, tmp_path: Path) -> None:
        # An empty file is a stated fact: there are no entries and the author
        # can see that.  It is not a file nobody could read.
        root = _project(tmp_path, "")
        assert _scan(root).returncode == 0
        assert _recorded(root).returncode == 0

    def test_a_project_with_no_bibliography_is_unchanged(self, tmp_path: Path) -> None:
        root = _project(tmp_path, None)
        (root / "sources.toml").write_text(MANIFEST, encoding="utf-8")
        assert _run(root, "scan", "manuscript.md").returncode == 0
        assert _ledger(root)["bibliographies"] == []
        assert _recorded(root).returncode == 0


class TestAnUnreadableBibliographySurvivesTheRecording:
    def test_a_binary_bibliography_is_reported_on_the_recorded_path(
        self, tmp_path: Path
    ) -> None:
        root = _project(tmp_path, BINARY_BIB)
        assert _scan(root).returncode == 1
        result = _recorded(root)
        assert result.returncode == 1, result.stdout
        assert "bib-unreadable" in result.stdout

    def test_an_unclosed_entry_is_reported_on_the_recorded_path(self, tmp_path: Path) -> None:
        root = _project(tmp_path, UNCLOSED_BIB)
        assert _scan(root).returncode == 1
        result = _recorded(root)
        assert result.returncode == 1, result.stdout
        assert "bib-unparsed-entry" in result.stdout

    def test_the_two_verbs_agree(self, tmp_path: Path) -> None:
        root = _project(tmp_path, BINARY_BIB)
        _scan(root)
        recorded = _recorded(root)
        live = _run(root, "verify", "manuscript.md", "--ledger", "citevouch.lock.json")
        assert recorded.returncode == live.returncode == 1
        assert "bib-unreadable" in recorded.stdout
        assert "bib-unreadable" in live.stdout

    def test_a_deleted_bibliography_is_named(self, tmp_path: Path) -> None:
        root = _project(tmp_path, GOOD_BIB)
        _scan(root)
        (root / "refs.bib").unlink()
        result = _recorded(root)
        assert result.returncode == 1, result.stdout
        assert "source-missing" in result.stdout
        assert "refs.bib" in result.stdout

    def test_allow_stale_does_not_silence_it(self, tmp_path: Path) -> None:
        # `--allow-stale` says the ledger describes an older draft of the
        # manuscript.  It says nothing about the bibliography being gone.
        root = _project(tmp_path, BINARY_BIB)
        _scan(root)
        result = _run(
            root,
            "check",
            "manuscript.md",
            "--use-recorded",
            "--allow-stale",
            "--ledger",
            "citevouch.lock.json",
        )
        assert result.returncode == 1, result.stdout
        assert "bib-unreadable" in result.stdout


class TestTheLiveRunDoesNotSayItTwice:
    def test_the_live_check_names_the_failure_once(self, tmp_path: Path) -> None:
        root = _project(tmp_path, BINARY_BIB)
        result = _run(root, "check", "manuscript.md", "--bib", "refs.bib")
        assert result.returncode == 1
        assert result.stdout.count("bib-unreadable") == 1, result.stdout

    def test_scan_names_the_failure_once(self, tmp_path: Path) -> None:
        root = _project(tmp_path, BINARY_BIB)
        result = _scan(root)
        assert result.stdout.count("bib-unreadable") == 1, result.stdout


class TestAnOldLedgerStillReads:
    def test_a_ledger_without_the_key_reads_as_no_bibliography(self, tmp_path: Path) -> None:
        root = _project(tmp_path, GOOD_BIB)
        _scan(root)
        blob = _ledger(root)
        del blob["bibliographies"]
        (root / "citevouch.lock.json").write_text(json.dumps(blob), encoding="utf-8")
        result = _recorded(root)
        assert result.returncode == 0, result.stdout

    def test_the_key_round_trips(self, tmp_path: Path) -> None:
        from citevouch.model import Ledger

        root = _project(tmp_path, GOOD_BIB)
        _scan(root)
        written = _ledger(root)
        assert Ledger.from_json(written).to_json() == written

    @pytest.mark.parametrize("value", [5, {"a": 1}, [1], True])
    def test_a_damaged_value_is_refused(self, tmp_path: Path, value: object) -> None:
        root = _project(tmp_path, GOOD_BIB)
        _scan(root)
        blob = _ledger(root)
        blob["bibliographies"] = value
        (root / "citevouch.lock.json").write_text(json.dumps(blob), encoding="utf-8")
        assert _recorded(root).returncode == 2
