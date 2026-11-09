"""The report must name the bibliography the ledger recorded, not just its size.

Measured before the fix: a project scanned with ``--bib refs.bib`` where that
file held no readable entry produced

    - records: 1 claim against 1 source
    - bibliography: 0 entries

which is the same line an old project that never passed ``--bib`` at all
produces.  The ledger does record the file name (``bibliographies``), so the
command that answers "what does the ledger say" was answering a different
question than the one it was asked.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NL = chr(10)
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"}
PAGE = "We collected 154,391 examples from the corpus." + NL
MANUSCRIPT = (
    "```claim id=c1 source=paper page=1 ref=knuth2020"
    + NL
    + "quote: |"
    + NL
    + "  We collected 154,391 examples from the corpus."
    + NL
    + "```"
    + NL
)
GOOD_BIB = "@book{knuth2020," + NL + "  title = {The Art}," + NL + "}" + NL
BINARY_BIB = "\x01\x02\x03 not a bib at all \x04" + NL
EMPTY_BIB = ""


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "citevouch", *args],
        cwd=root,
        env=ENV,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _project(tmp_path: Path, bib: str | None = None, name: str = "refs.bib") -> Path:
    root = tmp_path / "paper"
    root.mkdir(parents=True)
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    (root / "manuscript.md").write_text(MANUSCRIPT, encoding="utf-8", newline=NL)
    if bib is not None:
        (root / name).write_text(bib, encoding="utf-8", newline=NL)
    return root


def _scan(root: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return _run(root, "scan", "manuscript.md", "--root", ".", *extra)


def _report(root: Path) -> str:
    proc = _run(root, "report", "--root", ".")
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def _line(text: str, prefix: str) -> str:
    for line in text.splitlines():
        if line.startswith(prefix):
            return line
    raise AssertionError(f"no line starting {prefix!r} in:\n{text}")


class TestTheLineNamesTheFile:
    def test_a_readable_bibliography_is_named(self, tmp_path: Path) -> None:
        root = _project(tmp_path, GOOD_BIB)
        _scan(root, "--bib", "refs.bib")
        line = _line(_report(root), "- bibliography:")
        assert "refs.bib" in line
        assert "1 entry" in line

    def test_a_bibliography_nothing_could_be_read_from_is_still_named(
        self, tmp_path: Path
    ) -> None:
        # The whole point: the scan was red, the ledger names the file, and the
        # report used to say the same thing it says when there is no file.
        root = _project(tmp_path, BINARY_BIB)
        scan = _scan(root, "--bib", "refs.bib")
        assert scan.returncode == 1
        line = _line(_report(root), "- bibliography:")
        assert "refs.bib" in line
        assert "0 entries" in line

    def test_an_empty_bibliography_is_named(self, tmp_path: Path) -> None:
        root = _project(tmp_path, EMPTY_BIB)
        _scan(root, "--bib", "refs.bib")
        line = _line(_report(root), "- bibliography:")
        assert "refs.bib" in line
        assert "0 entries" in line

    def test_a_missing_bibliography_file_is_named(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        scan = _scan(root, "--bib", "refs.bib")
        assert scan.returncode == 1
        line = _line(_report(root), "- bibliography:")
        assert "refs.bib" in line


class TestWhatItSaysWhenThereIsNoBibliography:
    def test_no_file_recorded_says_so(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _scan(root)
        line = _line(_report(root), "- bibliography:")
        assert "none recorded" in line
        # The count is still there, because a reader asking about a ledger with
        # no bibliography still wants to know it held nothing.  What changed is
        # that `none recorded` is now said out loud instead of being implied by
        # the same `0 entries` a given-but-unreadable file produced.
        assert "0 entries" in line

    def test_an_old_ledger_says_so(self, tmp_path: Path) -> None:
        # `bibliographies` arrived in 0.22.33; a ledger written before that has
        # no key, and reading it must not turn "unknown" into "none".
        root = _project(tmp_path, GOOD_BIB)
        _scan(root, "--bib", "refs.bib")
        lock = root / "citevouch.lock.json"
        blob = json.loads(lock.read_text(encoding="utf-8"))
        blob.pop("bibliographies")
        lock.write_text(json.dumps(blob), encoding="utf-8", newline=NL)
        line = _line(_report(root), "- bibliography:")
        assert "none recorded" in line


class TestSeveralFiles:
    def test_two_files_are_both_named(self, tmp_path: Path) -> None:
        root = _project(tmp_path, GOOD_BIB)
        (root / "more.bib").write_text(
            "@book{lamport1994," + NL + "  title = {LaTeX}," + NL + "}" + NL,
            encoding="utf-8",
            newline=NL,
        )
        _scan(root, "--bib", "refs.bib", "--bib", "more.bib")
        line = _line(_report(root), "- bibliography:")
        assert "refs.bib" in line
        assert "more.bib" in line
        assert "2 entries" in line

    def test_a_long_path_is_clipped_not_wrapped(self, tmp_path: Path) -> None:
        deep = "a" * 70
        root = _project(tmp_path, GOOD_BIB, name="refs.bib")
        (root / "nested").mkdir()
        (root / "nested" / (deep + ".bib")).write_text(GOOD_BIB, encoding="utf-8", newline=NL)
        _scan(root, "--bib", "nested/" + deep + ".bib")
        line = _line(_report(root), "- bibliography:")
        assert "…" in line
        assert len(line) < 200


class TestTheJsonAgrees:
    def test_the_payload_names_the_files(self, tmp_path: Path) -> None:
        root = _project(tmp_path, BINARY_BIB)
        _scan(root, "--bib", "refs.bib")
        proc = _run(
            root, "check", "manuscript.md", "--root", ".", "--use-recorded", "--format", "json"
        )
        payload = json.loads(proc.stdout)
        assert payload["ledger"]["bibliographies"] == ["refs.bib"]

    def test_an_old_ledger_gives_an_empty_list(self, tmp_path: Path) -> None:
        root = _project(tmp_path, GOOD_BIB)
        _scan(root, "--bib", "refs.bib")
        lock = root / "citevouch.lock.json"
        blob = json.loads(lock.read_text(encoding="utf-8"))
        blob.pop("bibliographies")
        lock.write_text(json.dumps(blob), encoding="utf-8", newline=NL)
        proc = _run(
            root, "check", "manuscript.md", "--root", ".", "--use-recorded", "--format", "json"
        )
        payload = json.loads(proc.stdout)
        assert payload["ledger"]["bibliographies"] == []
