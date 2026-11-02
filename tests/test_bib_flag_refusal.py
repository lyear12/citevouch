"""`--bib` on a command that does not read a bibliography.

`scan` parses each `.bib` and records its entries into the ledger; `verify` and
`check --use-recorded` check the manuscript's keys against `ledger.entries` and
never open a `.bib` at all.  The flag was accepted anyway, and ignored:

    citevouch check m.md --root . --use-recorded --bib nowhere.bib   ->  0
    citevouch verify  m.md --root . --bib nowhere.bib                ->  0

A green run for a path that does not exist, and `action.yml` always passes
`--use-recorded` - so on a pull request the flag was pure decoration whose
whole purpose was to make the run able to fail.

Refusing beats validating the path: a *correct* path is still not read, so
validating would only catch typos while leaving "I edited my bibliography and
nothing happened" unsaid.  Both working commands are named in the message.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from citevouch.cli import main

MANUSCRIPT = (
    "```claim id=c1 source=a page=1\n"
    "quote: |\n"
    "  We counted 40,688 examples.\n"
    "claim: |\n"
    "  It counted 40,688.\n"
    "```\n"
)
SOURCE = "We counted 40,688 examples.\n"
BIB = "@article{a,\n  title = {T},\n  author = {A},\n  journal = {J},\n  year = {2020}\n}\n"


def _project(tmp_path: Path) -> Path:
    (tmp_path / "a.txt").write_text(SOURCE, encoding="utf-8", newline="\n")
    (tmp_path / "sources.toml").write_text(
        '[sources]\na = "a.txt"\n', encoding="utf-8", newline="\n"
    )
    (tmp_path / "refs.bib").write_text(BIB, encoding="utf-8", newline="\n")
    (tmp_path / "m.md").write_text(MANUSCRIPT, encoding="utf-8", newline="\n")
    return tmp_path


def _record(root: Path) -> None:
    assert main(["scan", "m.md", "--root", str(root), "--bib", "refs.bib", "--quiet"]) == 0


class TestTheFlagIsRefusedRatherThanIgnored:
    @pytest.mark.parametrize(
        "command",
        [
            ["check", "--use-recorded"],
            ["verify"],
        ],
    )
    def test_a_missing_bibliography_is_not_a_green_run(self, tmp_path: Path, capsys, command):
        root = _project(tmp_path)
        _record(root)
        capsys.readouterr()
        assert main([*command, "m.md", "--root", str(root), "--bib", "nowhere.bib"]) == 2
        assert "is not read by this command" in capsys.readouterr().err

    @pytest.mark.parametrize(
        "command",
        [
            ["check", "--use-recorded"],
            ["verify"],
        ],
    )
    def test_a_bibliography_that_is_there_is_refused_too(self, tmp_path: Path, capsys, command):
        """Validating the path would pass here and still tell the author
        nothing, because the file is not read either way."""
        root = _project(tmp_path)
        _record(root)
        capsys.readouterr()
        assert main([*command, "m.md", "--root", str(root), "--bib", "refs.bib"]) == 2
        assert "is not read by this command" in capsys.readouterr().err

    def test_a_directory_bibliography_gets_the_same_answer(self, tmp_path: Path, capsys):
        """The point is not the path, so a directory must not get a path-shaped
        complaint either - it would send the author to fix a path that is not
        the problem."""
        root = _project(tmp_path)
        _record(root)
        (root / "adir").mkdir()
        capsys.readouterr()
        assert main(["verify", "m.md", "--root", str(root), "--bib", "adir"]) == 2
        err = capsys.readouterr().err
        assert "is not read by this command" in err
        assert "is a directory" not in err

    def test_the_message_names_a_command_that_reads_it(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        _record(root)
        capsys.readouterr()
        main(["verify", "m.md", "--root", str(root), "--bib", "refs.bib"])
        err = capsys.readouterr().err
        assert "citevouch scan --bib" in err
        assert "drop --use-recorded" in err


class TestTheCommandsThatDoReadItStillDo:
    def test_scan_records_the_bibliography(self, tmp_path: Path):
        root = _project(tmp_path)
        assert main(["scan", "m.md", "--root", str(root), "--bib", "refs.bib", "--quiet"]) == 0
        ledger = (root / "citevouch.lock.json").read_text(encoding="utf-8")
        assert '"a"' in ledger

    def test_check_without_use_recorded_reads_it(self, tmp_path: Path):
        """`check` re-scans, so the flag means exactly what the help says."""
        root = _project(tmp_path)
        (root / "refs.bib").write_text("@article{zzz,\n}\n", encoding="utf-8", newline="\n")
        assert main(["check", "m.md", "--root", str(root), "--bib", "refs.bib", "--quiet"]) == 1

    def test_check_without_the_flag_still_runs(self, tmp_path: Path):
        root = _project(tmp_path)
        _record(root)
        assert main(["check", "m.md", "--root", str(root), "--use-recorded", "--quiet"]) == 0

    def test_verify_without_the_flag_still_runs(self, tmp_path: Path):
        root = _project(tmp_path)
        _record(root)
        assert main(["verify", "m.md", "--root", str(root), "--quiet"]) == 0

    def test_draft_still_reads_the_bibliography(self, tmp_path: Path):
        """ "draft` parses the .bib for `file` fields, so its --bib has to keep
        working - the refusal is about the two commands that record nothing."""
        root = _project(tmp_path)
        (root / "paper.txt").write_text(
            "The method has been fully integrated into the framework here.\n",
            encoding="utf-8",
            newline="\n",
        )
        (root / "p.md").write_text("We cite [@a] for this.\n", encoding="utf-8", newline="\n")
        assert (
            main(["draft", "p.md", "--root", str(root), "--bib", "refs.bib", "-o", "out.md"])
            == 0
        )
