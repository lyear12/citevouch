"""The recorded pass re-reads the bibliography, so it must judge the file it read.

0.22.33 taught the recorded pass to re-read every bibliography the ledger names,
because a file that yielded no entries left no trace in the ledger.  The parse
findings became fresh; the *judgements* about keys and fields stayed stale,
because they were still read off ``ledger.entries`` - the mapping captured when
``scan`` ran.  One run therefore held two opinions about one file.

Measured on a project scanned with a bibliography holding ``knuth2020``, then
edited so the file holds only ``lamport1994``:

    check --bib refs.bib              -> 1, [high] bib-key-missing 'knuth2020'
    check --bib refs.bib --use-recorded -> 0, [info] quote-found

and the mirror image, for a file whose entry grew the fields it was missing:

    refs.bib at scan time: knuth2020 without `publisher` / `year`
    refs.bib now:          knuth2020 replaced by a complete lamport1994
    check --use-recorded  -> [medium] bib-field-empty ... knuth2020: 2 required
                             fields missing   <-- about an entry not in the file

So the recorded pass must use the entries it just read, and fall back to the
recorded mapping only when a file could not be read at all - a key missing from
an unreadable file is not a missing key.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"}
NL = chr(10)

PAGE = "We collected 154,391 examples from the corpus." + NL
MANIFEST = "[sources]" + NL + 'paper = "page.txt"' + NL
MANUSCRIPT = (
    "```claim id=c1 source=paper ref=knuth2020 page=1"
    + NL
    + "quote: |"
    + NL
    + "  We collected 154,391 examples from the corpus."
    + NL
    + "```"
    + NL
)

KNUTH = (
    "@article{knuth2020,"
    + NL
    + "  author = {Knuth, Donald},"
    + NL
    + "  title = {Literate Programming},"
    + NL
    + "  year = {1984},"
    + NL
    + "  journal = {The Computer Journal}"
    + NL
    + "}"
    + NL
)
KNUTH_THIN = (
    "@article{knuth2020,"
    + NL
    + "  author = {Knuth, Donald},"
    + NL
    + "  title = {Literate Programming},"
    + NL
    + "}"
    + NL
)
LAMPORT = (
    "@article{lamport1994,"
    + NL
    + "  author = {Lamport, Leslie},"
    + NL
    + "  title = {LaTeX},"
    + NL
    + "  year = {1994},"
    + NL
    + "  journal = {TUGboat}"
    + NL
    + "}"
    + NL
)
BINARY_BIB = "\x01\x02\x03 not a bib at all \x04" + NL


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "citevouch", *args, "--root", str(root)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env=ENV,
    )


def _project(tmp_path: Path, bib: str, name: str = "") -> Path:
    root = tmp_path / (name or "case")
    root.mkdir(parents=True)
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline="\n")
    (root / "sources.toml").write_text(MANIFEST, encoding="utf-8", newline="\n")
    (root / "manuscript.md").write_text(MANUSCRIPT, encoding="utf-8", newline="\n")
    (root / "refs.bib").write_text(bib, encoding="utf-8", newline="\n")
    return root


def _scan(root: Path) -> subprocess.CompletedProcess[str]:
    return _run(root, "scan", "manuscript.md", "--bib", "refs.bib")


def _recorded(root: Path) -> subprocess.CompletedProcess[str]:
    return _run(root, "check", "manuscript.md", "--use-recorded")


def _live(root: Path) -> subprocess.CompletedProcess[str]:
    return _run(root, "check", "manuscript.md", "--bib", "refs.bib")


def _codes(proc: subprocess.CompletedProcess[str]) -> list[str]:
    out = []
    for line in proc.stdout.splitlines():
        if line.startswith("[") and "] " in line:
            out.append(line.split("] ", 1)[1].split(" ", 1)[0].rstrip(":"))
    return out


def _ledger(root: Path) -> dict:
    return json.loads((root / "citevouch.lock.json").read_text("utf-8"))


class TestTheRecordedPassJudgesTheFileItRead:
    def test_a_key_removed_after_the_scan_is_reported(self, tmp_path: Path) -> None:
        root = _project(tmp_path, KNUTH)
        assert _scan(root).returncode == 0
        (root / "refs.bib").write_text(LAMPORT, encoding="utf-8", newline="\n")

        recorded = _recorded(root)

        assert recorded.returncode == 1, recorded.stdout
        assert "bib-key-missing" in _codes(recorded)
        assert "knuth2020" in recorded.stdout
        # The sentence must name the file this run read.  "the ledger recorded"
        # points the author at a mapping they cannot open.
        assert "the bibliography the ledger recorded" not in recorded.stdout
        assert "not in the bibliography" in recorded.stdout

    def test_the_two_verbs_agree_about_a_replaced_bibliography(self, tmp_path: Path) -> None:
        root = _project(tmp_path, KNUTH)
        assert _scan(root).returncode == 0
        (root / "refs.bib").write_text(LAMPORT, encoding="utf-8", newline="\n")

        live = _live(root)
        recorded = _recorded(root)

        assert _codes(live) == _codes(recorded)

    def test_a_field_finding_is_about_an_entry_that_is_still_there(
        self, tmp_path: Path
    ) -> None:
        root = _project(tmp_path, KNUTH_THIN)
        assert _scan(root).returncode == 0
        assert "bib-field-empty" in _codes(_recorded(root))

        (root / "refs.bib").write_text(LAMPORT, encoding="utf-8", newline="\n")
        recorded = _recorded(root)

        # The entry the field complaint was about has left the file.  A missing
        # key is the honest verdict now; "2 required fields missing" about an
        # entry nobody can open is not.
        assert "bib-field-empty" not in _codes(recorded), recorded.stdout
        assert "required fields missing" not in recorded.stdout

    def test_an_entry_added_after_the_scan_is_the_one_called_unused(
        self, tmp_path: Path
    ) -> None:
        root = _project(tmp_path, KNUTH)
        assert _scan(root).returncode == 0
        (root / "refs.bib").write_text(KNUTH + LAMPORT, encoding="utf-8", newline="\n")

        recorded = _recorded(root)

        assert "bib-key-unused" in _codes(recorded)
        assert "lamport1994" in recorded.stdout
        assert "knuth2020" not in recorded.stdout


class TestAFileThatCouldNotBeReadIsNotAMissingKey:
    def test_a_deleted_bibliography_does_not_accuse_the_claim(self, tmp_path: Path) -> None:
        root = _project(tmp_path, KNUTH)
        assert _scan(root).returncode == 0
        (root / "refs.bib").unlink()

        recorded = _recorded(root)

        assert recorded.returncode == 1
        assert "source-missing" in _codes(recorded)
        assert "bib-key-missing" not in _codes(recorded), recorded.stdout

    def test_an_unreadable_bibliography_does_not_accuse_the_claim(self, tmp_path: Path) -> None:
        root = _project(tmp_path, KNUTH)
        assert _scan(root).returncode == 0
        (root / "refs.bib").write_text(BINARY_BIB, encoding="utf-8", newline="\n")

        recorded = _recorded(root)

        assert "bib-unreadable" in _codes(recorded)
        assert "bib-key-missing" not in _codes(recorded), recorded.stdout

    def test_an_unclosed_entry_does_not_accuse_the_claim(self, tmp_path: Path) -> None:
        root = _project(tmp_path, KNUTH)
        assert _scan(root).returncode == 0
        (root / "refs.bib").write_text(
            "@article{broken2020," + NL + "  author = {Someone}," + NL,
            encoding="utf-8",
            newline="\n",
        )

        recorded = _recorded(root)

        assert "bib-unreadable" in _codes(recorded)
        assert "bib-key-missing" not in _codes(recorded), recorded.stdout


class TestWhatMustNotChange:
    def test_a_clean_project_is_still_green(self, tmp_path: Path) -> None:
        root = _project(tmp_path, KNUTH)
        assert _scan(root).returncode == 0

        recorded = _recorded(root)

        assert recorded.returncode == 0, recorded.stdout
        assert [c for c in _codes(recorded) if c.startswith("bib-key")] == []

    def test_a_ledger_that_names_no_bibliography_still_reads(self, tmp_path: Path) -> None:
        root = _project(tmp_path, KNUTH)
        assert _scan(root).returncode == 0
        blob = _ledger(root)
        blob.pop("bibliographies")
        (root / "citevouch.lock.json").write_text(
            json.dumps(blob), encoding="utf-8", newline="\n"
        )
        (root / "refs.bib").write_text(LAMPORT, encoding="utf-8", newline="\n")

        recorded = _recorded(root)

        # Nothing named the file, so nothing re-read it: the old rule stands and
        # the recorded mapping still backs the claim.
        assert recorded.returncode == 0, recorded.stdout

    def test_an_old_ledger_is_still_judged_by_its_entries(self, tmp_path: Path) -> None:
        # A ledger written before `bibliographies` existed names no file, so
        # there is nothing to re-read - but it does hold entries, and a claim
        # citing a key those entries lack is still a missing key.
        root = _project(tmp_path, LAMPORT)
        assert _scan(root).returncode == 0
        blob = _ledger(root)
        blob.pop("bibliographies")
        (root / "citevouch.lock.json").write_text(
            json.dumps(blob), encoding="utf-8", newline="\n"
        )

        recorded = _recorded(root)

        assert recorded.returncode == 1, recorded.stdout
        assert "bib-key-missing" in _codes(recorded), recorded.stdout

    def test_the_live_pass_is_unchanged(self, tmp_path: Path) -> None:
        root = _project(tmp_path, KNUTH_THIN)

        live = _live(root)

        # A medium finding is under the default --fail-on high, so the exit code
        # stays 0; what matters is that the live pass still names the entry.
        assert "bib-field-empty" in _codes(live)
        assert "knuth2020" in live.stdout
