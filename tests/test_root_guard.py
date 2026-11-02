"""What a mistyped ``--root`` used to produce.

Every path on the command line is resolved against ``--root``, and the root was
never checked.  In a project at ``proj/``:

============================  ==================================================
``scan proj/m.md --root x``   **created** ``x/`` and wrote a ledger into it
``doctor --root x``           made ``x/.citevouch/cache`` to test it
``draft ... --root x``        wrote its proposals into ``x``
``check proj/m.md --root x``  found the manuscript, then said ``source-missing
                              ... no entry in sources.toml``
============================  ==================================================

The ``check`` line is the worst one, because it is not merely wrong: the
manifest was sitting next to the manuscript the whole time.  The manuscript
resolves because a path that exists as given is never re-rooted, so the run
looks like it read the project - and everything that depended on the root
came back missing.  There is no downstream repair for that: by the time a
message is being written, the run has already answered a question about a
directory that is not the project.

The three verbs that write are the same defect with a side effect: a typo
leaves a phantom project on disk, and the next run against the real one looks
at a ledger nobody asked for.  So the guard is one function, called once,
before any verb sees the value.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from citevouch.cli import main

ROOT = Path(__file__).resolve().parent.parent

MANUSCRIPT = """\
# Paper

```claim id=c1 source=paper page=1
quote: |
  The corpus has 154,391 utterances.
claim: |
  The corpus has 154,391 utterances.
```
"""

PAPER = "The corpus has 154,391 utterances.\n"
MANIFEST = '[sources]\npaper = "papers/paper.txt"\n'


def _project(root):
    root.mkdir(parents=True, exist_ok=True)
    (root / "papers").mkdir(exist_ok=True)
    (root / "papers" / "paper.txt").write_text(PAPER, encoding="utf-8")
    (root / "m.md").write_text(MANUSCRIPT, encoding="utf-8")
    (root / "sources.toml").write_text(MANIFEST, encoding="utf-8")
    return root


class TestTheRootThatIsNotThere:
    def test_a_root_that_does_not_exist_is_a_usage_error(self, tmp_path, capsys):
        project = _project(tmp_path / "proj")
        assert main(["check", str(project / "m.md"), "--root", str(tmp_path / "nope")]) == 2
        assert "does not exist" in capsys.readouterr().err

    def test_it_says_that_a_typo_is_the_default_alternative(self, tmp_path, capsys):
        project = _project(tmp_path / "proj")
        main(["check", str(project / "m.md"), "--root", str(tmp_path / "nope")])
        err = capsys.readouterr().err
        # The overwhelmingly common case is a project in the working directory,
        # where the flag should not have been passed at all.
        assert "drop --root" in err

    def test_a_root_that_is_a_file_says_it_is_a_file(self, tmp_path, capsys):
        project = _project(tmp_path / "proj")
        assert main(["check", str(project / "m.md"), "--root", str(project / "m.md")]) == 2
        err = capsys.readouterr().err
        assert "is a file, not a directory" in err
        # "does not exist" about a file the author can see is the false-sentence
        # failure this repository keeps paying for.
        assert "does not exist" not in err


class TestNothingIsMadeToTestTheRoot:
    """The guard has to run before any verb, or the writer makes the directory first."""

    def _nothing_created(self, tmp_path, capsys, argv, label):
        typo = tmp_path / "nowhere"
        assert main(argv(tmp_path)) == 2
        capsys.readouterr()
        assert not typo.exists(), f"{label} created the typo root"

    def test_scan_does_not_create_the_directory_it_scribbles_in(self, tmp_path, capsys):
        project = _project(tmp_path / "proj")

        def argv(base):
            return ["scan", str(project / "m.md"), "--root", str(base / "nowhere")]

        self._nothing_created(tmp_path, capsys, argv, "scan")

    def test_doctor_does_not_make_a_cache_in_the_typo(self, tmp_path, capsys):
        project = _project(tmp_path / "proj")

        def argv(base):
            return [
                "doctor",
                "--manuscript",
                str(project / "m.md"),
                "--root",
                str(base / "nowhere"),
            ]

        self._nothing_created(tmp_path, capsys, argv, "doctor")

    def test_draft_does_not_write_proposals_into_the_typo(self, tmp_path, capsys):
        project = _project(tmp_path / "proj")

        def argv(base):
            return [
                "draft",
                str(project / "m.md"),
                "-o",
                "claims.md",
                "--root",
                str(base / "nowhere"),
            ]

        self._nothing_created(tmp_path, capsys, argv, "draft")

    def test_every_verb_that_takes_a_root_refuses_the_same_one(self, tmp_path, capsys):
        project = _project(tmp_path / "proj")
        typo = tmp_path / "nowhere"
        m = str(project / "m.md")
        verbs = [
            ["check", m, "--root", str(typo)],
            ["scan", m, "--root", str(typo)],
            ["verify", m, "--root", str(typo)],
            ["report", "--root", str(typo)],
            ["doctor", "--manuscript", m, "--root", str(typo)],
            ["draft", m, "-o", "claims.md", "--root", str(typo)],
        ]
        for argv in verbs:
            assert main(argv) == 2, f"{argv[0]} accepted a root that is not there"
        capsys.readouterr()
        assert not typo.exists()


class TestTheRealRootStillWorks:
    def test_a_correct_root_is_untouched(self, tmp_path, capsys):
        project = _project(tmp_path / "proj")
        assert main(["check", str(project / "m.md"), "--root", str(project)]) == 0
        out = capsys.readouterr().out
        assert "1 claim — 1 verified" in out

    def test_the_default_root_is_the_working_directory(self, tmp_path, capsys, monkeypatch):
        project = _project(tmp_path / "proj")
        monkeypatch.chdir(project)
        assert main(["check", "m.md"]) == 0
        assert "1 claim — 1 verified" in capsys.readouterr().out

    def test_init_demo_has_no_root_and_is_not_affected(self, tmp_path, capsys):
        # It takes a directory to create, so it is the one verb the guard must
        # skip: the directory does not exist yet, which is the point of it.
        assert main(["init-demo", str(tmp_path / "fresh")]) == 0
        assert (tmp_path / "fresh" / "citevouch.lock.json").is_file()

    def test_the_guard_is_reachable_without_the_cli(self, tmp_path, capsys):
        # main() is not the only entry point tests use, so the guard has to be
        # callable on its own - otherwise a test that calls a cmd_* function
        # directly would skip it and see the old behaviour.
        from citevouch.cli import _project_root

        assert _project_root(str(_project(tmp_path / "proj"))) == (tmp_path / "proj")
        assert str(tmp_path / "proj") in str(_project_root(str(tmp_path / "proj")))


class TestTheMessageReachesTheConsole:
    def test_the_process_exits_two_and_prints_no_traceback(self, tmp_path, capsys):
        project = _project(tmp_path / "proj")
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "citevouch",
                "check",
                str(project / "m.md"),
                "--root",
                str(tmp_path / "nowhere"),
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": "src"},
        )
        capsys.readouterr()
        assert completed.returncode == 2
        assert "Traceback (most recent call last)" not in completed.stderr
        assert "--root" in completed.stderr
