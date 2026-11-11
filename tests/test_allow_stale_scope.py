"""What `--allow-stale` is allowed to answer, and what it is not.

The flag exists for one sentence in the README: *the manuscript changed since
the ledger was recorded*.  Three different things used to be reported under
that one code, and the flag switched all three off together:

* the recorded manuscript is **gone** - there is no draft to be newer than;
* the ledger describes **another document** - it is not a drift check at all;
* the text **changed** - this is the one the flag is for.

Measured before the fix, with a ledger about `a.md` and a command asking about
`b.md`, `--allow-stale` printed `[info] quote-found at a.md:1 (c1): quote found
on page 1` and exited 0 - a green verdict, quoting a file the command was not
asked about.  Deleting `a.md` produced the same green line about a document
that is not on disk.
"""

from __future__ import annotations

import json
from pathlib import Path

from citevouch.cli import main

NL = chr(10)
B3 = chr(96) * 3

GOOD = "The corpus holds 40,688 examples of written English."
ELSEWHERE = "Something else is written on this page entirely."


def _block(claim_id: str, quote: str) -> str:
    return (
        B3
        + f"claim id={claim_id} source=paper page=1"
        + NL
        + "quote: |"
        + NL
        + "  "
        + quote
        + NL
        + B3
        + NL
    )


def _project(tmp_path: Path) -> Path:
    (tmp_path / "page.txt").write_text("Preface" + NL + GOOD + NL, encoding="utf-8", newline=NL)
    (tmp_path / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    (tmp_path / "a.md").write_text(_block("c1", GOOD), encoding="utf-8", newline=NL)
    (tmp_path / "b.md").write_text(_block("zzz", ELSEWHERE), encoding="utf-8", newline=NL)
    return tmp_path


def _record(root: Path) -> None:
    assert main(["scan", "a.md", "--root", str(root)]) == 0


class TestTheLedgerDescribesAnotherDocument:
    """A name comparison answers "is this the same document", not "is it older"."""

    def test_verify_still_refuses_it(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        _record(root)
        capsys.readouterr()
        code = main(["verify", "b.md", "--root", str(root), "--allow-stale"])
        out = capsys.readouterr().out
        assert code == 1, out
        assert "ledger-stale" in out
        assert "ledger describes a.md" in out

    def test_it_does_not_report_a_quote_found_in_the_other_document(
        self, tmp_path: Path, capsys
    ):
        root = _project(tmp_path)
        _record(root)
        capsys.readouterr()
        main(["verify", "b.md", "--root", str(root), "--allow-stale"])
        out = capsys.readouterr().out
        assert "quote-found" not in out
        assert "1 verified" not in out

    def test_check_use_recorded_still_refuses_it(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        _record(root)
        capsys.readouterr()
        code = main(
            [
                "check",
                "b.md",
                "--root",
                str(root),
                "--use-recorded",
                "--allow-stale",
            ]
        )
        out = capsys.readouterr().out
        assert code == 1, out
        assert "ledger-stale" in out
        assert "quote-found" not in out

    def test_without_the_flag_it_says_the_same_thing(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        _record(root)
        capsys.readouterr()
        code = main(["verify", "b.md", "--root", str(root)])
        out = capsys.readouterr().out
        assert code == 1, out
        assert "ledger describes a.md" in out


class TestTheRecordedManuscriptIsGone:
    """There is no older draft of a document that does not exist."""

    def test_verify_still_refuses_it(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        _record(root)
        (root / "a.md").unlink()
        capsys.readouterr()
        code = main(["verify", "a.md", "--root", str(root), "--allow-stale"])
        out = capsys.readouterr().out
        assert code == 1, out
        assert "ledger-stale" in out
        assert "no longer exists" in out

    def test_it_does_not_report_a_quote_found_in_a_missing_file(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        _record(root)
        (root / "a.md").unlink()
        capsys.readouterr()
        main(["verify", "a.md", "--root", str(root), "--allow-stale"])
        out = capsys.readouterr().out
        assert "quote-found" not in out

    def test_check_use_recorded_still_refuses_it(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        _record(root)
        (root / "a.md").unlink()
        capsys.readouterr()
        code = main(
            [
                "check",
                "a.md",
                "--root",
                str(root),
                "--use-recorded",
                "--allow-stale",
            ]
        )
        out = capsys.readouterr().out
        assert code == 1, out
        assert "no longer exists" in out
        assert "quote-found" not in out


class TestALedgerWithNoRecordedHash:
    """Existence does not need a digest to answer.

    A ledger written before `manuscript_sha256` existed, or hand-written
    without one, can say nothing about whether the *text* changed - but it
    still names a file, and asking whether that file is on disk is a question
    the ledger can answer.
    """

    def test_a_legacy_ledger_still_notices_the_manuscript_is_gone(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        _record(root)
        ledger_path = root / "citevouch.lock.json"
        blob = json.loads(ledger_path.read_text(encoding="utf-8"))
        blob["manuscript_sha256"] = ""
        ledger_path.write_text(json.dumps(blob, indent=2), encoding="utf-8")
        (root / "a.md").unlink()
        capsys.readouterr()
        code = main(["verify", "a.md", "--root", str(root)])
        out = capsys.readouterr().out
        assert code == 1, out
        assert "no longer exists" in out
        assert "quote-found" not in out

    def test_the_flag_does_not_bring_it_back(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        _record(root)
        ledger_path = root / "citevouch.lock.json"
        blob = json.loads(ledger_path.read_text(encoding="utf-8"))
        blob["manuscript_sha256"] = ""
        ledger_path.write_text(json.dumps(blob, indent=2), encoding="utf-8")
        (root / "a.md").unlink()
        capsys.readouterr()
        code = main(["verify", "a.md", "--root", str(root), "--allow-stale"])
        out = capsys.readouterr().out
        assert code == 1, out
        assert "no longer exists" in out

    def test_a_ledger_that_recorded_no_name_still_notices_the_file_is_gone(
        self, tmp_path: Path, capsys
    ):
        root = _project(tmp_path)
        _record(root)
        ledger_path = root / "citevouch.lock.json"
        blob = json.loads(ledger_path.read_text(encoding="utf-8"))
        blob["manuscript"] = ""
        blob["manuscript_sha256"] = ""
        ledger_path.write_text(json.dumps(blob, indent=2), encoding="utf-8")
        capsys.readouterr()
        code = main(["verify", "missing.md", "--root", str(root)])
        out = capsys.readouterr().out
        assert code == 1, out
        assert "no longer exists" in out


class TestADirectoryWhereTheManuscriptWas:
    """`exists()` is true for a directory, and that is a different fault.

    Falling through to the digest comparison answers "changed since the ledger
    was written", which sends the author looking for an edit while the file
    they wrote is sitting there as a folder.
    """

    def test_the_name_of_the_fault_is_the_one_on_disk(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        _record(root)
        (root / "a.md").unlink()
        (root / "a.md").mkdir()
        capsys.readouterr()
        code = main(["verify", "a.md", "--root", str(root)])
        out = capsys.readouterr().out
        assert code == 1, out
        assert "is now a directory" in out
        assert "changed since the ledger was written" not in out

    def test_the_flag_does_not_answer_it_either(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        _record(root)
        (root / "a.md").unlink()
        (root / "a.md").mkdir()
        capsys.readouterr()
        code = main(["verify", "a.md", "--root", str(root), "--allow-stale"])
        out = capsys.readouterr().out
        assert code == 1, out
        assert "is now a directory" in out
        assert "quote-found" not in out


class TestTheTextThatChanged:
    """The one question the flag was written for still gets its answer."""

    def test_verify_accepts_a_manuscript_with_more_prose(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        _record(root)
        (root / "a.md").write_text(
            (root / "a.md").read_text(encoding="utf-8") + NL + "A new paragraph." + NL,
            encoding="utf-8",
            newline=NL,
        )
        capsys.readouterr()
        code = main(["verify", "a.md", "--root", str(root), "--allow-stale"])
        out = capsys.readouterr().out
        assert code == 0, out
        assert "quote-found" in out
        assert "ledger-stale" not in out

    def test_check_use_recorded_accepts_it_too(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        _record(root)
        (root / "a.md").write_text(
            (root / "a.md").read_text(encoding="utf-8") + NL + "More." + NL,
            encoding="utf-8",
            newline=NL,
        )
        capsys.readouterr()
        code = main(
            [
                "check",
                "a.md",
                "--root",
                str(root),
                "--use-recorded",
                "--allow-stale",
            ]
        )
        out = capsys.readouterr().out
        assert code == 0, out
        assert "quote-found" in out

    def test_without_the_flag_it_is_still_stale(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        _record(root)
        (root / "a.md").write_text(
            (root / "a.md").read_text(encoding="utf-8") + NL + "More." + NL,
            encoding="utf-8",
            newline=NL,
        )
        capsys.readouterr()
        code = main(["verify", "a.md", "--root", str(root)])
        out = capsys.readouterr().out
        assert code == 1, out
        assert "changed since the ledger was written" in out
