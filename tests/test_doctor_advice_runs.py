"""Every command this tool prints has to run.

`doctor` closes each failed check with a sentence that names a command.  The
sentence is the whole point of the line: the reader has a problem, the check
says what it is, and the fix says what to type.  Copied and pasted, each of
these used to fail for a reason that had nothing to do with the diagnosis:

    $ citevouch doctor --root . --manuscript paper/m.md
    [FAIL] claims  paper/m.md holds no claim blocks, so every run reports ...
       -> ... `citevouch draft m.md -o claims.md`. A claim block opens ...
    $ citevouch draft m.md -o claims.md
    citevouch: manuscript m.md does not exist

The file was printed as `target.name`, so the directory was gone, and the
`--root` the run itself had been given went missing the same way.  The LaTeX
branch printed `citevouch draft m.tex -o claims.md` and the GBK branch a bare
`citevouch scan`, which is not a command but a usage error.

`draft` had already learned this lesson for its own closing advice - the
`--root` is printed, the path is printed with forward slashes and quoted - so
the fix is not a new rule but the same rule reached from a second place.  That
rule now lives in `citevouch.advice`, and these tests ask the only question
that catches a regression: take the command out of the output and run it.

Every test here runs from the directory *holding* the project, which is where
the two spellings of the path diverge.  From inside `paper/` the typed path
`paper/m.md` does not exist and a command that dropped the directory would
still work by accident.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from citevouch import advice

B3 = "```"
NL = "\n"
QUOTE = "We collected 40,688 examples from the corpus."
PAGE = QUOTE + NL
MANIFEST = '[sources]\npaper = "page.txt"\n'
SRC = Path(__file__).resolve().parents[1] / "src"

ADVICE = re.compile(r"`(citevouch (?:draft|scan|check)[^`]*)`")


def _project(tmp_path: Path, *, body: str, suffix: str = ".md") -> Path:
    """A project in ``paper/``; the caller's working directory is its parent."""
    paper = tmp_path / "paper"
    paper.mkdir()
    (paper / ("page.txt")).write_text(PAGE, encoding="utf-8", newline=NL)
    (paper / "sources.toml").write_text(MANIFEST, encoding="utf-8", newline=NL)
    (paper / f"m{suffix}").write_text(body, encoding="utf-8", newline=NL)
    return paper


def _run(root: Path, monkeypatch: pytest.MonkeyPatch, *argv: str) -> tuple[int, str]:
    """Run ``doctor`` from the directory above the project."""
    monkeypatch.chdir(root.parent)
    from citevouch.cli import main

    code = main(["doctor", *argv])
    return code, ""


def _captured(
    root: Path, monkeypatch: pytest.MonkeyPatch, capsys, *argv: str
) -> tuple[int, str]:
    monkeypatch.chdir(root.parent)
    from citevouch.cli import main

    code = main(["doctor", *argv])
    captured = capsys.readouterr()
    return code, captured.out + captured.err


def _commands(text: str) -> list[str]:
    return ADVICE.findall(text)


def _follow(command: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a command exactly as printed, from the directory it was printed in.

    The program name is replaced by this interpreter running the module, because
    the console script is not installed on every machine that runs these tests.
    Every other word is passed through unchanged - that is the part being
    tested, and `shlex.split` is what a shell would do to the quoting.
    """
    parts = shlex.split(command)
    assert parts[0] == "citevouch", command
    return subprocess.run(
        [sys.executable, "-m", "citevouch", *parts[1:]],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONPATH": str(SRC), "PYTHONIOENCODING": "utf-8"},
    )


class TestTheAdviceRuns:
    def test_no_claim_blocks_in_a_subdirectory(self, tmp_path, monkeypatch, capsys):
        paper = _project(tmp_path, body="# t\n\nJust prose, no claim blocks.\n")
        code, out = _captured(
            paper, monkeypatch, capsys, "--root", ".", "--manuscript", "paper/m.md"
        )
        assert code == 1, out
        printed = _commands(out)
        assert printed, out
        # The path keeps the directory the run was given.
        assert printed[0] == "citevouch draft paper/m.md -o claims.md", printed
        followed = _follow(printed[0], paper.parent)
        assert followed.returncode == 0, followed.stderr
        assert "does not exist" not in (followed.stdout + followed.stderr)

    def test_the_root_travels_with_the_command(self, tmp_path, monkeypatch, capsys):
        paper = _project(tmp_path, body="# t\n\nJust prose, no claim blocks.\n")
        code, out = _captured(
            paper, monkeypatch, capsys, "--root", "paper", "--manuscript", "m.md"
        )
        assert code == 1, out
        printed = _commands(out)
        assert printed[0] == "citevouch draft paper/m.md -o claims.md --root paper", printed
        followed = _follow(printed[0], paper.parent)
        assert followed.returncode == 0, followed.stderr
        assert "does not exist" not in (followed.stdout + followed.stderr)

    def test_a_latex_manuscript_in_a_subdirectory(self, tmp_path, monkeypatch, capsys):
        paper = _project(
            tmp_path,
            body="\\documentclass{article}\n\\begin{document}\nHi.\n\\end{document}\n",
            suffix=".tex",
        )
        code, out = _captured(
            paper, monkeypatch, capsys, "--root", ".", "--manuscript", "paper/m.tex"
        )
        assert code == 1, out
        printed = _commands(out)
        assert printed[0] == "citevouch draft paper/m.tex -o claims.md", printed
        followed = _follow(printed[0], paper.parent)
        assert followed.returncode == 0, followed.stderr
        assert "does not exist" not in (followed.stdout + followed.stderr)

    def test_the_scan_named_for_an_unbound_key_runs(self, tmp_path, monkeypatch, capsys):
        body = f"# t\n\n{B3}claim id=c1 source=ghost page=1\nquote: |\n  {QUOTE}\n{B3}\n"
        paper = _project(tmp_path, body=body)
        code, out = _captured(
            paper, monkeypatch, capsys, "--root", ".", "--manuscript", "paper/m.md"
        )
        assert code == 1, out
        printed = _commands(out)
        assert any(command.startswith("citevouch scan ") for command in printed), printed
        scan = next(command for command in printed if command.startswith("citevouch scan "))
        assert scan == "citevouch scan paper/m.md", scan
        followed = _follow(scan, paper.parent)
        # `scan` fails on the unbound key - that is the thing the reader is being
        # told to fix - but it has to reach that verdict rather than a usage error.
        assert followed.returncode == 1, followed.stdout + followed.stderr
        assert "source-missing" in (followed.stdout + followed.stderr)

    def test_the_scan_named_for_an_unbound_key_keeps_the_root(
        self, tmp_path, monkeypatch, capsys
    ):
        """A run from above the project has to print the `--root` it used.

        The manuscript is written as a relative path inside the project, so
        without `--root paper` the same command looks for `paper/paper/m.md`.
        """
        body = f"# t\n\n{B3}claim id=c1 source=ghost page=1\nquote: |\n  {QUOTE}\n{B3}\n"
        paper = _project(tmp_path, body=body)
        code, out = _captured(
            paper, monkeypatch, capsys, "--root", "paper", "--manuscript", "m.md"
        )
        assert code == 1, out
        printed = _commands(out)
        assert "citevouch scan paper/m.md --root paper" in printed, printed
        followed = _follow("citevouch scan paper/m.md --root paper", paper.parent)
        assert followed.returncode == 1, followed.stdout + followed.stderr
        assert "source-missing" in (followed.stdout + followed.stderr)

    def test_the_check_named_for_a_refused_block_keeps_the_root(
        self, tmp_path, monkeypatch, capsys
    ):
        body = f"# t\n\n{B3}claim id=c1 page=1\nquote: |\n  {QUOTE}\n{B3}\n"
        paper = _project(tmp_path, body=body)
        code, out = _captured(
            paper, monkeypatch, capsys, "--root", "paper", "--manuscript", "m.md"
        )
        assert code == 1, out
        printed = _commands(out)
        assert "citevouch check paper/m.md --root paper" in printed, printed
        followed = _follow("citevouch check paper/m.md --root paper", paper.parent)
        # The refused block is the thing being reported, so this command exits 1 -
        # but on `claim-uncheckable`, not on a usage error.
        assert followed.returncode == 1, followed.stdout + followed.stderr
        assert "claim-uncheckable" in (followed.stdout + followed.stderr)

    def test_the_scan_named_for_an_unreadable_source_names_the_file(
        self, tmp_path, monkeypatch, capsys
    ):
        """The extraction line's `scan` used to be two bare words.

        It is printed one line under a message that names the source file, so
        the reader copies a command with no manuscript in it and gets argparse
        text back.
        """
        paper = tmp_path / "paper"
        paper.mkdir()
        (paper / "page.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 60)
        (paper / "sources.toml").write_text(
            '[sources]\npaper = "page.png"\n', encoding="utf-8", newline=NL
        )
        (paper / "m.md").write_text(
            f"# t\n\n{B3}claim id=c1 source=paper page=1\nquote: |\n  {QUOTE}\n{B3}\n",
            encoding="utf-8",
            newline=NL,
        )
        code, out = _captured(
            paper, monkeypatch, capsys, "--root", "paper", "--manuscript", "m.md"
        )
        assert code == 1, out
        printed = _commands(out)
        assert "citevouch scan paper/m.md --root paper" in printed, printed
        followed = _follow("citevouch scan paper/m.md --root paper", paper.parent)
        # `source-not-text` is medium, so `scan` succeeds on it by design - the
        # point is that the command reached that verdict and named the file,
        # rather than dying on a missing manuscript argument.
        assert followed.returncode == 0, followed.stdout + followed.stderr
        assert "source-not-text" in (followed.stdout + followed.stderr)
        assert "wrote" in followed.stderr, followed.stderr


class TestTheSharedBuilderIsTheOneUsed:
    def test_doctor_and_cli_agree_on_one_quoting_rule(self):
        """Two copies of a quoting rule is how one of them ended up unquoted."""
        from citevouch import cli

        assert cli.shell_word is advice.shell_word
        assert cli._shell_word is advice.shell_word

    def test_a_root_with_a_space_is_quoted(self):
        command = advice.citevouch_command("draft", "paper/m.md", *advice.root_words("my proj"))
        assert command == "citevouch draft paper/m.md --root 'my proj'", command

    def test_a_root_of_dot_adds_nothing(self):
        assert advice.root_words(".") == []
        assert advice.root_words("") == []

    def test_a_backslash_is_quoted_because_on_windows_it_is_a_separator(self):
        assert advice.shell_word("C:" + chr(92) + "work" + chr(92) + "proj") == (
            "'C:" + chr(92) + "work" + chr(92) + "proj'"
        )

    def test_an_empty_value_is_quoted_rather_than_vanishing(self):
        assert advice.shell_word("") == "''"


class TestTheCommandsThatWereAlreadyRight:
    def test_the_short_form_survives_for_a_run_inside_the_project(
        self, tmp_path, monkeypatch, capsys
    ):
        paper = _project(tmp_path, body="# t\n\nJust prose, no claim blocks.\n")
        # A run inside the project: root defaults to "." and the advice stays short.
        monkeypatch.chdir(paper)
        from citevouch.cli import main

        code = main(["doctor", "--manuscript", "m.md"])
        out = capsys.readouterr()
        assert code == 1, out.out
        printed = _commands(out.out + out.err)
        assert printed[0] == "citevouch draft m.md -o claims.md", printed
        # Printed inside the project, so it is followed inside the project.  The
        # short form is the correct one there, and printing `--root .` would be
        # two words of noise on every run.
        followed = _follow(printed[0], paper)
        assert followed.returncode == 0, followed.stderr

    def test_draft_still_names_a_check_that_runs(self, tmp_path, monkeypatch, capsys):
        """The advice `draft` prints was already right; the refactor must not move it."""
        paper = _project(
            tmp_path,
            body="# t\n\nWe collected 40,688 examples from the corpus [@paper].\n",
        )
        monkeypatch.chdir(paper)
        from citevouch.cli import main

        main(["draft", "m.md", "-o", "claims.md"])
        captured = capsys.readouterr()
        text = captured.out + captured.err
        printed = [
            command for command in _commands(text) if command.startswith("citevouch check ")
        ]
        assert printed, text
        assert printed[-1] == "citevouch check claims.md", printed
