"""The sentence has to name the bibliography that was actually consulted.

`bib-key-missing` has three ways to reach the reader, and each consulted a
different thing:

    check --bib refs.bib          reads refs.bib, writes no ledger
    verify                        re-reads every file the ledger names
    verify (old ledger)           only the entries `scan` captured

The old wording named "the bibliography the ledger recorded" in all three.  Two
of those sentences were true.  The first was not - a plain `check` never writes
a ledger, so on a project that has never been scanned the message pointed the
author at a file that does not exist.  Measured:

    check --bib refs.bib  -> 1, [high] bib-key-missing
                             "not in the bibliography the ledger recorded"
    citevouch.lock.json   -> absent, before and after

A sentence that tells the author to inspect something that is not there costs
them a search and teaches them to distrust the message.  The tests below pin
all three cases at once, because fixing one branch of a three-way choice is how
a repair reaches two readers and leaves the third saying the old thing.
"""

from __future__ import annotations

import json
from pathlib import Path

from citevouch.cli import main

NL = chr(10)
B3 = chr(96) * 3
PAGE = "We collected 154,391 examples from the corpus." + NL
MANUSCRIPT = (
    B3
    + "claim id=c1 source=paper ref=knuth2020 page=1"
    + NL
    + "quote: |"
    + NL
    + "  We collected 154,391 examples from the corpus."
    + NL
    + B3
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


def _project(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    (root / "manuscript.md").write_text(MANUSCRIPT, encoding="utf-8", newline=NL)
    (root / "refs.bib").write_text(LAMPORT, encoding="utf-8", newline=NL)
    return root


def _missing(captured: str) -> str:
    lines = [line for line in captured.splitlines() if "bib-key-missing" in line]
    return lines[0] if lines else ""


class TestTheSentenceNamesWhatWasRead:
    def test_a_run_that_read_the_file_does_not_blame_a_ledger(
        self, tmp_path: Path, capsys
    ) -> None:
        root = _project(tmp_path / "case")

        assert main(["check", "manuscript.md", "--root", str(root), "--bib", "refs.bib"]) == 1
        captured = capsys.readouterr()
        sentence = _missing(captured.out + captured.err)

        assert sentence, captured.out
        assert "the bibliography the ledger recorded" not in sentence, sentence
        assert "the bibliography this run read" in sentence, sentence
        # The premise of the complaint, checked rather than assumed: there is
        # no ledger for the old sentence to have been talking about.
        assert (root / "citevouch.lock.json").exists() is False

    def test_a_recorded_pass_that_re_read_the_file_names_the_file(
        self, tmp_path: Path, capsys
    ) -> None:
        root = _project(tmp_path / "case")
        assert main(["scan", "manuscript.md", "--root", str(root), "--bib", "refs.bib"]) == 0

        assert main(["verify", "manuscript.md", "--root", str(root)]) == 1
        captured = capsys.readouterr()
        sentence = _missing(captured.out + captured.err)

        assert "not in the bibliography" in sentence, sentence
        assert "ledger recorded" not in sentence, sentence
        assert "this run read" not in sentence, sentence

    def test_a_ledger_with_no_file_behind_it_says_recorded(
        self, tmp_path: Path, capsys
    ) -> None:
        root = _project(tmp_path / "case")
        assert main(["scan", "manuscript.md", "--root", str(root), "--bib", "refs.bib"]) == 0
        ledger_path = root / "citevouch.lock.json"
        recorded = json.loads(ledger_path.read_text(encoding="utf-8"))
        del recorded["bibliographies"]
        ledger_path.write_text(json.dumps(recorded, indent=2), encoding="utf-8", newline=NL)

        assert main(["verify", "manuscript.md", "--root", str(root)]) == 1
        captured = capsys.readouterr()
        sentence = _missing(captured.out + captured.err)

        assert "the bibliography the ledger recorded" in sentence, sentence


class TestWhatTheOtherTwoSentencesStillSay:
    def test_the_source_key_fallback_keeps_its_own_wording(
        self, tmp_path: Path, capsys
    ) -> None:
        root = _project(tmp_path / "case")
        (root / "manuscript.md").write_text(
            MANUSCRIPT.replace("ref=knuth2020", ""), encoding="utf-8", newline=NL
        )

        assert main(["check", "manuscript.md", "--root", str(root), "--bib", "refs.bib"]) == 1
        captured = capsys.readouterr()
        sentence = _missing(captured.out + captured.err)

        assert "names no `ref=`" in sentence, sentence
        assert "has no such entry" in sentence, sentence
        assert "the bibliography this run read" in sentence, sentence
        assert "cites 'paper'" not in sentence, sentence

    def test_a_bibliography_that_went_away_is_not_a_missing_key(
        self, tmp_path: Path, capsys
    ) -> None:
        root = _project(tmp_path / "case")
        assert main(["scan", "manuscript.md", "--root", str(root), "--bib", "refs.bib"]) == 0
        (root / "refs.bib").unlink()

        assert main(["verify", "manuscript.md", "--root", str(root)]) == 1
        captured = capsys.readouterr()
        output = captured.out + captured.err

        assert "bib-key-missing" not in output, output
        assert "source-missing" in output, output
