"""`draft`'s closing advice has to be a command that works.

Measured before this existed, from the directory above the project:

    $ citevouch draft proj/paper.md --root proj -o claims.md --bib proj/refs.bib
    citevouch: wrote claims.md; read it, then `citevouch check claims.md` to
    see what it got wrong
    $ citevouch check claims.md
    [high] source-missing at claims.md:11 (knuth2020): claim knuth2020 names
    source='knuth2020' but no entry in sources.toml ...

The second command exits 1 on a project where `draft` had just proposed a
verbatim quote from a page it had itself read.  The advice omitted the `--root`
that made the first command work, so the check ran against the current
directory instead of the project - and `check` is the command `draft` exists to
feed, so the last thing a new user reads is a false accusation.

The same `--root` omission applies to every argument the advice quotes, so the
advice is now built from the values the run actually used (see
`cli._check_advice`), and a test walks the whole sentence out of the output and
runs it.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = {
    **os.environ,
    "PYTHONPATH": str(ROOT / "src"),
    "PYTHONIOENCODING": "utf-8",
}

PAGE = "We collected 154,391 examples from the corpus.\n"
BIB = """@book{knuth2020,
  author = {Knuth, Donald},
  title = {The Art of Computer Programming},
  year = {2020},
  file = {page.txt}
}
"""
PAPER = "We collected 154,391 examples from the corpus \\citep{knuth2020}.\n"


def _run(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "citevouch", *args],
        cwd=cwd,
        env=ENV,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _project(base: Path) -> Path:
    proj = base / "proj"
    proj.mkdir()
    (proj / "page.txt").write_text(PAGE, encoding="utf-8", newline="\n")
    (proj / "sources.toml").write_text(
        '[sources]\npaper = "page.txt"\nknuth2020 = "page.txt"\n',
        encoding="utf-8",
        newline="\n",
    )
    (proj / "paper.md").write_text(PAPER, encoding="utf-8", newline="\n")
    (proj / "refs.bib").write_text(BIB, encoding="utf-8", newline="\n")
    return proj


def _advice(proc: subprocess.CompletedProcess[str]) -> str:
    """The whole command the run told the author to type next."""
    for line in proc.stderr.splitlines():
        if "read it, then `" in line:
            start = line.index("read it, then `") + len("read it, then `")
            return line[start : line.index("`", start)]
    return ""


def _run_as_written(cwd: Path, advice: str) -> subprocess.CompletedProcess[str]:
    parts = shlex.split(advice)
    assert parts[0] == "citevouch", advice
    return _run(cwd, *parts[1:])


class TestTheAdviceRunsFromWhereItWasPrinted:
    def test_the_command_it_names_exits_zero(self, tmp_path: Path) -> None:
        _project(tmp_path)

        drafted = _run(
            tmp_path,
            "draft",
            "proj/paper.md",
            "--root",
            "proj",
            "-o",
            "claims.md",
            "--bib",
            "proj/refs.bib",
        )
        assert drafted.returncode == 0, drafted.stderr

        advice = _advice(drafted)
        assert advice, drafted.stderr
        followed = _run_as_written(tmp_path, advice)

        assert followed.returncode == 0, (
            f"the advice was {advice!r}\nfollowing it: {followed.stdout}{followed.stderr}"
        )
        assert "1 claim — 1 verified" in followed.stdout, followed.stdout

    def test_it_keeps_the_root_it_was_given(self, tmp_path: Path) -> None:
        # The `--root` is what made the first command work, so it has to be in
        # the second one.  Without it the check reads the current directory.
        _project(tmp_path)

        drafted = _run(
            tmp_path,
            "draft",
            "proj/paper.md",
            "--root",
            "proj",
            "-o",
            "claims.md",
            "--bib",
            "proj/refs.bib",
        )

        advice = _advice(drafted)
        assert "--root proj" in advice, advice

    def test_running_inside_the_project_needs_no_root(self, tmp_path: Path) -> None:
        # When `--root` is `.` there is nothing to add: the advice stays short
        # and still runs.
        proj = _project(tmp_path)

        drafted = _run(
            proj,
            "draft",
            "paper.md",
            "--root",
            ".",
            "-o",
            "claims.md",
            "--bib",
            "refs.bib",
        )

        advice = _advice(drafted)
        assert advice == "citevouch check claims.md", advice
        followed = _run_as_written(proj, advice)
        assert followed.returncode == 0, followed.stdout + followed.stderr

    def test_a_ledger_path_is_named_too(self, tmp_path: Path) -> None:
        # `check` with `--use-recorded` needs the ledger, and the default is
        # not where this run wrote it.
        _project(tmp_path)

        drafted = _run(
            tmp_path,
            "draft",
            "proj/paper.md",
            "--root",
            "proj",
            "-o",
            "claims.md",
            "--bib",
            "proj/refs.bib",
        )

        advice = _advice(drafted)
        followed = _run_as_written(tmp_path, advice)
        assert "Traceback" not in followed.stderr, followed.stderr

    def test_a_path_with_a_space_stays_one_argument(self, tmp_path: Path) -> None:
        # An unquoted path would turn the advice into two arguments and fail
        # for a reason that has nothing to do with the draft.
        _project(tmp_path)

        drafted = _run(
            tmp_path,
            "draft",
            "proj/paper.md",
            "--root",
            "proj",
            "-o",
            "my claims.md",
            "--bib",
            "proj/refs.bib",
        )
        assert drafted.returncode == 0, drafted.stderr

        advice = _advice(drafted)
        assert advice, drafted.stderr
        assert "my claims.md" in advice, advice
        # One argument with a space in it, not two: the quoted form splits back
        # into the same number of words a shell would see.
        assert "'proj/my claims.md'" in advice, advice
        followed = _run_as_written(tmp_path, advice)
        assert followed.returncode == 0, followed.stdout + followed.stderr
        assert "1 claim — 1 verified" in followed.stdout, followed.stdout

    def test_a_single_quote_in_the_name_is_escaped(self, tmp_path: Path) -> None:
        # `author's claims.md` closed and reopened inside the quotes is the
        # only way a POSIX shell can carry an apostrophe inside a quoted word.
        _project(tmp_path)

        drafted = _run(
            tmp_path,
            "draft",
            "proj/paper.md",
            "--root",
            "proj",
            "-o",
            "author's claims.md",
            "--bib",
            "proj/refs.bib",
        )
        assert drafted.returncode == 0, drafted.stderr

        advice = _advice(drafted)
        assert advice, drafted.stderr
        followed = _run_as_written(tmp_path, advice)
        assert followed.returncode == 0, (
            f"the advice was {advice!r}\nfollowing it: {followed.stdout}{followed.stderr}"
        )
        assert "1 claim — 1 verified" in followed.stdout, followed.stdout
