"""`doctor` has to notice when a claim names a source nobody binds.

The check that came before this one asks whether `sources.toml` names files
that are on disk.  Every line could pass and the project still be unable to
check anything, because the key the *claims* name is not the key the manifest
binds:

    sources.toml:   other = "other.txt"
    manuscript:     ```claim id=c1 source=paper page=1

Measured before this check existed: `doctor` printed seven `[ok  ]` lines and
exited 0, closing with "Everything this tool needs is on this machine. If
quotes are still reported missing, the source files are the place to look."
while `check` printed `[high] source-missing ... claim c1 names source='paper'
but no entry in sources.toml` and exited 1.

That is the whole reason `doctor` exists - it is the command a reader runs
*because* the report looked empty - so it is the one command that may not be
quiet about the only thing that guarantees every claim will fail.

This is the fifth instance of one shape: the manifest check asked whether the
file existed but not whether it pointed anywhere (0.19.44), the manuscript
check called a directory absent (0.19.45), a .tex file got a clean bill
(0.19.46), a file with no claim blocks got a clean bill (0.19.47), and this
one.  The lesson in LESSONS.md says a diagnostic's list of checks is a claim
about what can go wrong, and the list has to be written from the side of the
command that finds nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from citevouch import doctor
from citevouch.cli import main

B3 = "```"


def _manuscript(*keys: str) -> str:
    """A manuscript that names one source per key, in order."""
    lines = ["# t", ""]
    for index, key in enumerate(keys):
        lines += [
            f"{B3}claim id=c{index} source={key} page=1",
            "quote: |",
            "  alpha beta gamma",
            B3,
            "",
        ]
    return "\n".join(lines)


def _project(tmp_path: Path, *, keys: tuple[str, ...], manifest: str | None) -> Path:
    (tmp_path / "manuscript.md").write_text(_manuscript(*keys), encoding="utf-8", newline="\n")
    (tmp_path / "other.txt").write_text("alpha beta gamma\n", encoding="utf-8", newline="\n")
    (tmp_path / "paper.txt").write_text("alpha beta gamma\n", encoding="utf-8", newline="\n")
    if manifest is not None:
        (tmp_path / "sources.toml").write_text(manifest, encoding="utf-8", newline="\n")
    return tmp_path


def _sources(tmp_path: Path) -> doctor.Report:
    reports = doctor.diagnose(root=tmp_path, manuscript="manuscript.md")
    return next(report for report in reports if report.name == "sources")


class TestTheKeyNobodyBinds:
    def test_a_claim_naming_an_unbound_key_is_a_problem(self, tmp_path: Path):
        project = _project(
            tmp_path,
            keys=("paper",),
            manifest='[sources]\nother = "other.txt"\n',
        )
        report = _sources(project)
        assert not report.ok
        assert "paper" in report.detail

    def test_the_failure_makes_the_command_exit_one(self, tmp_path: Path, capsys):
        project = _project(
            tmp_path,
            keys=("paper",),
            manifest='[sources]\nother = "other.txt"\n',
        )
        assert main(["doctor", "--root", str(project)]) == 1
        out = capsys.readouterr().out
        assert "[FAIL] sources" in out
        # The sentence that used to close this run, on a project where every
        # claim was doomed to source-missing.
        assert "Everything this tool needs is on this machine" not in out

    def test_the_message_names_the_file_nearest_on_disk(self, tmp_path: Path):
        project = _project(
            tmp_path,
            keys=("paper-2026",),
            manifest='[sources]\nother = "other.txt"\n',
        )
        (project / "2026_paper-large.pdf").write_text("x", encoding="utf-8")
        report = _sources(project)
        assert not report.ok
        assert "2026_paper-large.pdf" in report.detail

    def test_two_unbound_keys_are_both_named(self, tmp_path: Path):
        project = _project(
            tmp_path,
            keys=("alpha", "beta"),
            manifest='[sources]\nother = "other.txt"\n',
        )
        report = _sources(project)
        assert not report.ok
        assert "alpha" in report.detail
        assert "beta" in report.detail

    def test_a_key_the_manifest_binds_is_not_a_problem(self, tmp_path: Path):
        project = _project(
            tmp_path,
            keys=("paper",),
            manifest='[sources]\npaper = "paper.txt"\n',
        )
        report = _sources(project)
        assert report.ok
        assert report.detail == "1 source key, every one of them bound to a file"

    def test_the_fix_names_what_to_do_next(self, tmp_path: Path):
        project = _project(
            tmp_path,
            keys=("paper",),
            manifest='[sources]\nother = "other.txt"\n',
        )
        report = _sources(project)
        assert "sources.toml" in report.fix
        assert "citevouch scan" in report.fix


class TestTheStatesThatAreNotThisProblem:
    """One line per cause, and only the cause that is missing."""

    def test_a_project_with_no_manifest_is_reported_as_unbound(self, tmp_path: Path):
        # No manifest is a supported way to work (`--source`), but only if the
        # caller passes it. `doctor` does not accept `--source`, so from here a
        # claim naming a key resolves to nothing, and saying so is the truth.
        project = _project(tmp_path, keys=("paper",), manifest=None)
        report = _sources(project)
        assert not report.ok
        assert "paper" in report.detail

    def test_a_broken_manifest_does_not_get_a_second_complaint(self, tmp_path: Path):
        # `manifest` already printed the parser's message and the run exits 1 on
        # that line. Repeating it here would make one problem look like two.
        project = _project(tmp_path, keys=("paper",), manifest="[sources\n")
        report = _sources(project)
        assert report.ok
        assert "manifest could not be read" in report.detail

    def test_a_key_whose_file_is_missing_is_left_to_the_manifest_line(self, tmp_path: Path):
        # Measured: the first version of this check counted only keys the
        # manifest never mentions, so for this project it printed "1 source
        # key, every one of them bound to a file" one line below the manifest
        # check that had just said the file is not there.
        project = _project(
            tmp_path,
            keys=("paper",),
            manifest='[sources]\npaper = "gone.txt"\n',
        )
        report = _sources(project)
        assert report.ok
        assert "cannot be used" in report.detail
        assert "bound to a file" not in report.detail

    def test_a_manuscript_with_no_claim_blocks_leaves_it_to_the_claims_line(
        self, tmp_path: Path
    ):
        (tmp_path / "manuscript.md").write_text("# t\n\nnothing here\n", encoding="utf-8")
        (tmp_path / "sources.toml").write_text('[sources]\na = "a.txt"\n', encoding="utf-8")
        (tmp_path / "a.txt").write_text("alpha beta gamma\n", encoding="utf-8")
        report = _sources(tmp_path)
        assert report.ok
        assert report.detail == "no claim names a source"

    def test_a_claim_with_no_source_names_nothing(self, tmp_path: Path):
        # A block without `source=` never enters `parsed.claims`; it is reported
        # as `claim-uncheckable` by `check`, and the `claims` line now reports
        # the refusal itself. This check has nothing to add - but it may not
        # say "no claim names a source" either, because there *is* a claim and
        # it is named one line up. It points at that line instead.
        body = f"# t\n\n{B3}claim id=c1 page=1\nquote: |\n  alpha beta gamma\n{B3}\n"
        (tmp_path / "manuscript.md").write_text(body, encoding="utf-8", newline="\n")
        (tmp_path / "sources.toml").write_text('[sources]\na = "a.txt"\n', encoding="utf-8")
        (tmp_path / "a.txt").write_text("alpha beta gamma\n", encoding="utf-8")
        report = _sources(tmp_path)
        assert report.ok
        assert (
            report.detail
            == "not checked, because the parser refused the blocks this file holds"
        )


class TestTheDemoStillPasses:
    def test_the_repository_demo_binds_every_key_its_manuscript_names(self):
        demo = Path(__file__).resolve().parent.parent / "demo"
        reports = doctor.diagnose(root=demo, manuscript="manuscript.md")
        report = next(item for item in reports if item.name == "sources")
        assert report.ok
        assert "every one of them bound" in report.detail
        assert doctor.problems(reports) == []


class TestTheTwoCommandsTellOneStory:
    """The point of the check is that `doctor` explains `check`, not contradicts it.

    Written as a comparison rather than as two remembered strings: a test that
    records what each command prints today stops testing the agreement the day
    either message is reworded, which is the day it matters.
    """

    @pytest.mark.parametrize(
        "keys,manifest",
        [
            (("paper",), '[sources]\nother = "other.txt"\n'),
            (("alpha", "beta"), '[sources]\nother = "other.txt"\n'),
            (("paper",), '[sources]\npaper = "paper.txt"\n'),
        ],
    )
    def test_both_commands_fail_the_same_projects(
        self, tmp_path: Path, capsys, keys: tuple[str, ...], manifest: str
    ):
        project = _project(tmp_path, keys=keys, manifest=manifest)
        check_code = main(["check", "manuscript.md", "--root", str(project), "--quiet"])
        capsys.readouterr()
        doctor_code = main(["doctor", "--root", str(project)])
        capsys.readouterr()
        assert (doctor_code == 0) == (check_code == 0), (
            "doctor and check disagree about "
            f"keys={keys}: doctor said {doctor_code}, check said {check_code}"
        )

    def test_the_doctor_line_names_the_key_the_check_line_names(self, tmp_path: Path, capsys):
        project = _project(
            tmp_path,
            keys=("paper",),
            manifest='[sources]\nother = "other.txt"\n',
        )
        main(["check", "manuscript.md", "--root", str(project), "--quiet"])
        checked = capsys.readouterr().out
        main(["doctor", "--root", str(project)])
        diagnosed = capsys.readouterr().out
        assert "paper" in checked, checked
        assert "paper" in diagnosed, diagnosed
