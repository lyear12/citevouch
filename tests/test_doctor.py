"""Tests for the one command that is allowed to be reassuring.

``doctor`` exists because the first failure a new user meets is silent: every
quote missing, no reason given. These tests hold it to two promises — that it
reports a broken machine as broken, and that it does not cry wolf on a working
one, because a diagnostic that fails for a healthy install is worse than none.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from citevouch import doctor
from citevouch.cli import build_parser, main


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    (tmp_path / "manuscript.md").write_text("# t\n", encoding="utf-8")
    (tmp_path / "sources.toml").write_text('[sources]\na = "a.txt"\n', encoding="utf-8")
    return tmp_path


def names(reports: list[doctor.Report]) -> list[str]:
    return [report.name for report in reports]


class TestWhatItChecks:
    def test_a_project_that_is_fine_reports_nothing_broken(self, project: Path):
        reports = doctor.diagnose(root=project, manuscript="manuscript.md")
        assert doctor.problems(reports) == []
        assert names(reports) == [
            "python",
            "pypdf",
            "pdftotext",
            "cache",
            "manuscript",
            "manifest",
        ]

    def test_every_check_says_something(self, project: Path):
        for report in doctor.diagnose(root=project, manuscript="manuscript.md"):
            assert report.detail.strip(), f"{report.name} reported an empty detail"

    def test_a_missing_manuscript_is_a_problem_with_a_fix(self, tmp_path: Path):
        reports = doctor.diagnose(root=tmp_path, manuscript="nope.md")
        broken = doctor.problems(reports)
        assert [report.name for report in broken] == ["manuscript"]
        # The fix has to name the mistake, not restate the symptom: a user who
        # passed the wrong path already knows the file was not found.
        assert "--root" in broken[0].fix
        assert "does not exist" in broken[0].detail

    def test_the_fix_names_a_command_that_actually_runs(self, tmp_path: Path):
        """A fix line is a command the reader will paste, so it has to parse.

        The first version of this message said
        `citevouch doctor paper/manuscript.md`, and `doctor` takes no positional
        argument: pasting it produces `error: unrecognized arguments`.  Advice
        that fails when followed is worse than silence, because the reader
        concludes the tool is broken rather than the sentence.
        """
        reports = doctor.diagnose(root=tmp_path, manuscript="nope.md")
        broken = doctor.problems(reports)
        assert broken and broken[0].fix, "there is no fix line to check"
        command = re.search(r"`(citevouch [^`]+)`", broken[0].fix)
        assert command is not None, f"the fix names no command: {broken[0].fix!r}"
        argv = command.group(1).split()[1:]
        parsed = build_parser().parse_args(argv)
        assert parsed.command == "doctor"
        assert parsed.manuscript.endswith("paper/manuscript.md"), (
            f"the documented command would not look where the fix says: {parsed.manuscript}"
        )

    def test_a_project_without_a_manifest_is_still_fine(self, tmp_path: Path):
        (tmp_path / "manuscript.md").write_text("# t\n", encoding="utf-8")
        reports = doctor.diagnose(root=tmp_path, manuscript="manuscript.md")
        manifest = next(report for report in reports if report.name == "manifest")
        # Passing every source with --source is a supported way to work, so a
        # missing manifest is a fact, not a failure.
        assert manifest.ok
        assert "--source" in manifest.detail

    def test_an_old_interpreter_is_refused(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(doctor, "MIN_PYTHON", (99, 0))
        report = doctor._python()
        assert not report.ok
        assert "Upgrade the interpreter" in report.fix

    def test_no_extractor_at_all_is_a_problem(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(doctor, "which", lambda _name: None)
        # A None entry in sys.modules makes `import pypdf` raise ImportError,
        # which is exactly what an uninstalled library does. Patching
        # __import__ instead breaks pytest's own machinery while it formats a
        # failure, so a broken install turns into an internal error rather than
        # a test result.
        monkeypatch.setitem(sys.modules, "pypdf", None)
        report = doctor._pdftotext()
        assert not report.ok
        assert "pip install pypdf" in report.fix

    def test_pypdf_alone_is_enough(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(doctor, "which", lambda _name: None)
        report = doctor._pdftotext()
        # pypdf is installed in the test environment, so poppler is optional.
        assert report.ok
        assert "not needed" in report.detail

    def test_a_read_only_cache_is_reported_but_not_blamed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        def refuse(*_args, **_kwargs):
            raise OSError(13, "Permission denied")

        monkeypatch.setattr(Path, "mkdir", refuse)
        report = doctor._cache(tmp_path)
        # Correctness does not depend on the cache; only speed does. Calling a
        # slow-but-correct install "FAILED" sends people looking for a bug.
        assert report.ok
        assert "re-extract" in report.detail


class TestHowItReads:
    def test_the_table_marks_each_check(self, project: Path, capsys):
        doctor.render(doctor.diagnose(root=project, manuscript="manuscript.md"))
        out = capsys.readouterr().out
        assert "[ok  ] python" in out
        assert "Everything this tool needs is on this machine" in out

    def test_a_failure_lists_what_to_do(self, tmp_path: Path, capsys):
        doctor.render(doctor.diagnose(root=tmp_path, manuscript="nope.md"))
        out = capsys.readouterr().out
        assert "[FAIL] manuscript" in out
        assert "-> Pass the path you meant" in out
        assert "1 of" in out and "checks failed" in out

    def test_broken_checks_become_findings_under_their_own_code(self, tmp_path: Path):
        found = doctor.findings(doctor.diagnose(root=tmp_path, manuscript="nope.md"))
        assert [finding.code for finding in found] == ["check-unavailable"]
        assert "manuscript" in found[0].message

    def test_the_code_does_not_borrow_a_source_code_for_a_machine_problem(self, tmp_path: Path):
        """A missing interpreter is not a broken PDF, and GitHub shows the rule.

        The code, not the message, decides the rule line a reader sees in the
        code-scanning tab. `source-unreadable` told them "A source file could
        not be read." above a line saying the cache directory is read-only.
        """
        found = doctor.findings(doctor.diagnose(root=tmp_path, manuscript="nope.md"))
        assert "source-unreadable" not in [finding.code for finding in found]


class TestTheCommand:
    def test_a_good_project_exits_zero(self, project: Path, capsys):
        assert main(["doctor", "--root", str(project)]) == 0
        assert "Everything this tool needs" in capsys.readouterr().out

    def test_a_broken_project_exits_one(self, tmp_path: Path, capsys):
        # 1 rather than 2 on purpose: the machine is broken, which is a result,
        # not a misuse of the command line.
        assert main(["doctor", "--root", str(tmp_path)]) == 1
        assert "[FAIL] manuscript" in capsys.readouterr().out

    def test_json_keeps_the_machine_facts(self, project: Path, capsys):
        main(["doctor", "--root", str(project), "--format", "json"])
        payload = json.loads(capsys.readouterr().out)
        assert payload["tool_version"]
        assert next(check["name"] for check in payload["checks"]) == "python"
        assert all("ok" in check for check in payload["checks"])

    def test_sarif_carries_the_broken_checks(self, tmp_path: Path, capsys):
        main(["doctor", "--root", str(tmp_path), "--format", "sarif"])
        payload = json.loads(capsys.readouterr().out)
        results = payload["runs"][0]["results"]
        assert [entry["ruleId"] for entry in results] == ["check-unavailable"]
        # The rule line a reader sees has to describe the check that failed.
        rules = payload["runs"][0]["tool"]["driver"]["rules"]
        assert [rule["id"] for rule in rules] == ["check-unavailable"]

    def test_json_is_the_format_that_carries_every_check(self, tmp_path: Path, capsys):
        """`findings()` feeds SARIF only; json needs the passing checks too.

        Its docstring used to claim the opposite, which is the kind of sentence
        nothing checks and everybody believes.
        """
        main(["doctor", "--root", str(tmp_path), "--format", "json"])
        payload = json.loads(capsys.readouterr().out)
        assert len(payload["checks"]) > 1
        assert all("ok" in check for check in payload["checks"])

    def test_it_runs_inside_the_repository_demo(self):
        # The demo is the project's own claim that it works; doctor must agree
        # with it, or one of the two is lying.
        demo = Path(__file__).resolve().parent.parent / "demo"
        assert main(["doctor", "--root", str(demo)]) == 0


def test_cache_available_agrees_with_the_report(tmp_path: Path):
    assert doctor.cache_available(tmp_path) is True
    assert (tmp_path / doctor.CACHE_DIRNAME / "cache").is_dir()


def test_a_machine_with_no_pdf_library_still_gets_a_diagnosis(
    monkeypatch: pytest.MonkeyPatch,
):
    """A machine with no PDF library gets a diagnosis, not a traceback."""
    monkeypatch.setattr(doctor, "which", lambda _name: None)
    monkeypatch.setitem(sys.modules, "pypdf", None)
    report = doctor._pypdf()
    assert not report.ok
    assert "not installed" in report.detail
    assert "pip install pypdf" in report.fix


class TestTheExampleInTheReadme:
    """The README shows `doctor` output, so the output has to be real.

    A hand-written diagnostic example is the easiest kind of documentation to
    let rot: nobody runs it, so it keeps describing a tool that used to exist.
    The block is checked against the demo, which is the project's own claim that
    it works.
    """

    def test_the_readme_shows_the_checks_the_tool_performs(self):
        root = Path(__file__).resolve().parent.parent
        for name in ("README.md", "README.zh-CN.md"):
            text = (root / name).read_text(encoding="utf-8")
            blocks = re.findall(r"```text\n(.*?)```", text, re.DOTALL)
            block = next((b for b in blocks if "citevouch doctor" in b), None)
            assert block is not None, f"{name} has no doctor example"
            lines = [line for line in block.splitlines() if line.startswith("[ok  ] ")]
            # Every check the tool performs has to appear, or the documentation
            # is describing a smaller tool than the one being shipped. The name
            # is the first token after the bracketed mark, which contains two
            # spaces of its own and therefore cannot be found by splitting the
            # whole line on whitespace.
            shown = {line[len("[ok  ] ") :].split()[0] for line in lines}
            expected = {
                "python",
                "pypdf",
                "pdftotext",
                "cache",
                "manuscript",
                "manifest",
            }
            assert expected <= shown, f"{name}: the example omits {expected - shown}"

    def test_the_demo_really_produces_the_headline_the_readme_promises(self, capsys):
        demo = Path(__file__).resolve().parent.parent / "demo"
        assert main(["doctor", "--root", str(demo)]) == 0
        out = capsys.readouterr().out
        english = (Path(__file__).resolve().parent.parent / "README.md").read_text(
            encoding="utf-8"
        )
        for sentence in out.strip().splitlines()[-1:]:
            assert sentence in english, f"README does not contain: {sentence!r}"
