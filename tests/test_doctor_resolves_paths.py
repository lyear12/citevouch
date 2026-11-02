"""`doctor` has to read a path the same way every other verb reads it.

A relative path that "already works" is never re-rooted: `_resolve` in
`citevouch.scan` returns it as typed, because for an input the file on disk is
the authority.  That is what makes `citevouch check paper/m.md --root paper`
work at all - joining blindly would look for `paper/paper/m.md`.

`doctor` joined blindly.  From the directory above the project:

    citevouch check paper/m.md --root paper                     -> verified, exit 0
    citevouch doctor --root paper --manuscript paper/m.md        -> exit 1,
        "[FAIL] manuscript  paper\\paper\\m.md does not exist"

So the command a reader runs *because* a report looked empty disagreed with
the report about which file it was reading.  Worse, the fix line printed with
that failure says "Pass the path you meant, e.g. `citevouch doctor
--manuscript paper/manuscript.md`" - following the advice reproduced the
failure, because the path the reader meant was the one that had just been
rejoined.

Every test here therefore runs with the working directory set to the folder
*above* the project, because that is where the two spellings diverge: from
inside `paper/` the typed path `paper/m.md` does not exist and both readings
agree by accident.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from citevouch import doctor
from citevouch.cli import main

B3 = "```"

MANUSCRIPT = "\n".join(
    [
        "# t",
        "",
        f"{B3}claim id=c1 source=paper page=1",
        "quote: |",
        "  We collected 40,688 examples in the corpus.",
        B3,
        "",
    ]
)


def _above(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A project in ``paper/``, with the working directory one level above it."""
    paper = tmp_path / "paper"
    paper.mkdir()
    (paper / "m.md").write_text(MANUSCRIPT, encoding="utf-8", newline="\n")
    (paper / "a.txt").write_text(
        "We collected 40,688 examples in the corpus.\n", encoding="utf-8", newline="\n"
    )
    (paper / "sources.toml").write_text(
        '[sources]\npaper = "a.txt"\n', encoding="utf-8", newline="\n"
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _doctor() -> list[doctor.Report]:
    return doctor.diagnose(root="paper", manuscript="paper/m.md")


def _manuscript_report(reports: list[doctor.Report]) -> doctor.Report:
    return next(report for report in reports if report.name == "manuscript")


class TestThePathThatWorksAsTyped:
    def test_a_rooted_path_inside_the_root_is_not_rooted_twice(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _above(tmp_path, monkeypatch)
        report = _manuscript_report(_doctor())
        assert report.ok
        assert "paper\\paper" not in report.detail
        assert "does not exist" not in report.detail

    def test_the_bare_name_still_resolves_against_the_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _above(tmp_path, monkeypatch)
        report = _manuscript_report(doctor.diagnose(root="paper", manuscript="m.md"))
        assert report.ok

    def test_the_three_spellings_name_one_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _above(tmp_path, monkeypatch)
        rooted = _manuscript_report(_doctor())
        bare = _manuscript_report(doctor.diagnose(root="paper", manuscript="m.md"))
        absolute = _manuscript_report(
            doctor.diagnose(root="paper", manuscript=str(tmp_path / "paper" / "m.md"))
        )
        # The details differ in how much of the path they print; what has to
        # match is the file they point at.
        named = [report.detail.split(" (")[0] for report in (rooted, bare, absolute)]
        resolved = {Path(name).resolve() for name in named}
        assert len(resolved) == 1
        assert rooted.ok and bare.ok and absolute.ok


class TestTheCommandsAgree:
    def test_doctor_and_check_reach_the_same_verdict_on_a_good_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _above(tmp_path, monkeypatch)
        assert main(["check", "paper/m.md", "--root", "paper"]) == 0
        assert doctor.problems(_doctor()) == []

    def test_the_path_doctor_names_is_a_file_check_would_accept(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _above(tmp_path, monkeypatch)
        report = _manuscript_report(_doctor())
        named = report.detail.split(" (")[0]
        assert Path(named).is_file()

    def test_a_latex_file_typed_with_the_root_prefix_is_still_refused(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _above(tmp_path, monkeypatch)
        (tmp_path / "paper" / "paper.tex").write_text(
            "\\documentclass{article}\n", encoding="utf-8", newline="\n"
        )
        report = _manuscript_report(doctor.diagnose(root="paper", manuscript="paper/paper.tex"))
        assert not report.ok
        assert "LaTeX" in report.detail

    def test_the_directory_advice_names_a_path_that_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _above(tmp_path, monkeypatch)
        (tmp_path / "paper" / "sub").mkdir()
        report = _manuscript_report(doctor.diagnose(root="paper", manuscript="paper/sub"))
        assert not report.ok
        assert "is a directory, not a file" in report.detail
        assert "paper\\paper" not in report.fix
