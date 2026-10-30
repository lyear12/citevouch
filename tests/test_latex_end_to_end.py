"""A .tex manuscript goes all the way through: draft, then check.

`tests/test_latex.py` proves the conversion and `tests/test_draft.py` proves the
proposals; this file proves the seam between them - that `citevouch draft
paper.tex` produces a file `citevouch check` accepts unchanged. A seam is where
this project has historically lost things: `init-demo` used to write a project
its own documented next command rejected, and the two halves were each passing.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

TEX = r"""
\documentclass{article}
\begin{document}

\section{Introduction}

The combined corpus contains 154,391 utterances \citep{smith2026cxn}. This is
large for the task at hand~\citep[p.~6]{smith2026cxn}.

\begin{thebibliography}{9}
\bibitem{smith2026cxn} A paper.
\end{thebibliography}
\end{document}
"""


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "citevouch", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={
            **os.environ,
            "PYTHONPATH": str(ROOT / "src"),
            "PYTHONIOENCODING": "utf-8",
        },
        timeout=180,
    )


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    (tmp_path / "papers").mkdir()
    (tmp_path / "papers" / "a.txt").write_text(
        "Introduction\n\n"
        "The combined corpus contains 154,391 utterances, annotated with 440,528\n"
        "roleset instances. This is large for the task at hand, and the split is\n"
        "described in the appendix.\n",
        encoding="utf-8",
        newline="\n",
    )
    (tmp_path / "sources.toml").write_text(
        '[sources]\nsmith2026cxn = "papers/a.txt"\n', encoding="utf-8", newline="\n"
    )
    (tmp_path / "paper.tex").write_text(TEX, encoding="utf-8", newline="\n")
    return tmp_path


def test_draft_reads_a_tex_manuscript(project: Path) -> None:
    done = _run(["draft", "paper.tex", "-o", "claims.md"], project)
    assert done.returncode == 0, done.stdout + done.stderr
    written = (project / "claims.md").read_text(encoding="utf-8")
    assert "```claim" in written
    assert "smith2026cxn" in written


def test_the_statement_is_the_sentence_and_not_the_preamble(project: Path) -> None:
    """What separates a converted manuscript from a raw file.

    `_LATEX` in `draft.py` matches `\\citep{key}` on its own, so finding the
    citation proves nothing about the conversion. What the conversion buys is
    the *statement*: without it the sentence walker runs over raw TeX, the
    second sentence keeps its `~` and its `[p.~6]` argument, and the claim line
    opens with `\\documentclass{article} \\usepackage{graphicx} ...`. Neither
    shape is a claim anybody can check, so both are asserted here and disabling
    the conversion turns this red.
    """
    _run(["draft", "paper.tex", "-o", "claims.md"], project)
    written = (project / "claims.md").read_text(encoding="utf-8")
    blocks = written.count("```claim")
    assert blocks == 2, written
    statements = [
        line.strip()
        for line in written.splitlines()
        if line.startswith("  The combined corpus") or line.startswith("  This is large")
    ]
    assert "This is large for the task at hand." in statements, written
    for line in statements:
        assert "\\documentclass" not in line
        assert "\\section" not in line
        assert "usepackage" not in line
        assert "~" not in line
        assert "\\citep" not in line


def test_the_proposal_survives_the_next_command(project: Path) -> None:
    """The one thing that matters: check accepts what draft wrote."""
    _run(["draft", "paper.tex", "-o", "claims.md"], project)
    checked = _run(["check", "claims.md", "--root", "."], project)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "quote-found" in checked.stdout


def test_a_tex_citation_is_found_even_with_no_local_paper(tmp_path: Path) -> None:
    """A key with no local file is reported, not silently dropped.

    This is a floor, not a proof that the conversion ran: `_LATEX` in
    `draft.py` matches `\\citep{key}` directly, so this test stays green with
    the conversion disabled. It exists because the other end-to-end tests all
    have a readable paper behind them, and the interesting failure mode for a
    citation with nothing behind it is silence rather than a wrong answer.
    """
    (tmp_path / "paper.tex").write_text(
        "\\begin{document}Prose \\citep{a2020key} more.\\end{document}",
        encoding="utf-8",
        newline="\n",
    )
    done = _run(["draft", "paper.tex", "-o", "out.md"], tmp_path)
    assert done.returncode == 0, done.stdout + done.stderr
    written = (tmp_path / "out.md").read_text(encoding="utf-8")
    assert "a2020key" in written
    assert "no local file" in written


def test_a_markdown_manuscript_is_untouched_by_the_latex_path(project: Path) -> None:
    (project / "paper.md").write_text(
        "The corpus contains 154,391 utterances annotated with roleset instances "
        "[@smith2026cxn].\n",
        encoding="utf-8",
        newline="\n",
    )
    done = _run(["draft", "paper.md", "-o", "md.md"], project)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "```claim" in (project / "md.md").read_text(encoding="utf-8")


class TestTheLineNumbersSayWhatTheyCount:
    """A `.tex` manuscript is converted before `draft` sees it.

    Every line number in the proposals file is therefore an index into a text
    the author does not have open.  The first version wrote `<!-- line 1 -->`
    for a sentence on line 8 of a file whose first five lines are comments,
    which sends the reader to look at a comment and concludes the tool is
    confused.  The fix is a comment saying which document the numbers count;
    this test is what keeps that comment alive.
    """

    TEX_WITH_PREAMBLE = r"""% a comment
% another comment
% a third comment
% a fourth comment
\documentclass{article}
\usepackage{graphicx}
\begin{document}

The combined corpus contains 154,391 utterances \citep{smith2026cxn} and
nobody has a file for the other key \citep{absent2025}.

\end{document}
"""

    def test_the_output_says_the_numbers_count_the_converted_text(self, tmp_path: Path):
        (tmp_path / "paper.tex").write_text(self.TEX_WITH_PREAMBLE, encoding="utf-8")
        proc = _run(
            ["draft", "paper.tex", "-o", "claims.md", "--force"],
            tmp_path,
        )
        assert proc.returncode == 0, proc.stderr
        written = (tmp_path / "claims.md").read_text(encoding="utf-8")
        assert "Not proposed:" in written, f"the fixture produced no skip to label:\n{written}"
        assert "Line numbers below count the LaTeX-converted text" in written, (
            "the file reports line numbers for a document the author cannot open"
        )
        assert "not paper.tex" in written

    def test_a_markdown_manuscript_gets_no_such_note(self, tmp_path: Path):
        (tmp_path / "paper.md").write_text(
            "# t\n\nA sentence citing [@smith2026cxn] here.\n", encoding="utf-8"
        )
        proc = _run(["draft", "paper.md", "-o", "claims.md", "--force"], tmp_path)
        assert proc.returncode == 0, proc.stderr
        written = (tmp_path / "claims.md").read_text(encoding="utf-8")
        assert "LaTeX-converted" not in written, (
            "markdown is not converted, so the note would be a lie"
        )


class TestALatexManuscriptIsRefusedNotQuietlyPassed:
    """`draft` accepts .tex, so a person reasonably tries `check` on one too.

    There are no claim blocks in a .tex file, so the old behaviour was to
    read zero claims and report `0 claims - 0 verified, 0 moved, 0 missing`
    with exit 0: the one verdict this tool exists to never give.
    """

    def test_scanning_a_tex_manuscript_is_refused(self, tmp_path: Path) -> None:
        paper = tmp_path / "paper.tex"
        paper.write_text(self.SOURCE, encoding="utf-8")
        proc = _run(["check", "paper.tex"], tmp_path)
        assert proc.returncode == 2
        assert "is LaTeX" in proc.stderr
        assert "citevouch draft" in proc.stderr

    def test_the_refusal_names_the_command_that_does_work(self, tmp_path: Path) -> None:
        paper = tmp_path / "paper.tex"
        paper.write_text(self.SOURCE, encoding="utf-8")
        proc = _run(["check", "paper.tex"], tmp_path)
        command = re.search(r"`(citevouch draft [^`]+)`", proc.stderr)
        assert command is not None, proc.stderr
        assert command.group(1).endswith("-o claims.md"), command.group(1)

    def test_a_markdown_manuscript_is_not_refused(self, tmp_path: Path) -> None:
        manuscript = tmp_path / "manuscript.md"
        manuscript.write_text("Just prose, no claim blocks." + chr(10), encoding="utf-8")
        proc = _run(["check", "manuscript.md"], tmp_path)
        assert "is LaTeX" not in proc.stderr

    SOURCE = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "The corpus contains 154,391 utterances \\citep{smith2026cxn}.\n"
        "\\end{document}\n"
    )


class TestASplitPaperIsNotASilentZero:
    r"""A paper that keeps its text in \input files is the normal shape.

    This command reads one file.  Following the includes is a design change
    nobody has asked for; saying which files it did not read is not, and it is
    the difference between `0 claim block(s) proposed` and `0 claim block(s)
    proposed, and here is the half of the paper I never opened`.
    """

    def _draft(self, project: Path, name: str, source: str) -> str:
        (project / name).write_text(source, encoding="utf-8", newline="\n")
        finished = _run(["draft", name, "--root", ".", "-o", "out.md", "--force"], project)
        assert finished.returncode == 0, finished.stderr
        return (project / "out.md").read_text(encoding="utf-8")

    def test_the_files_it_could_not_read_are_named(self, project: Path) -> None:
        text = self._draft(
            project,
            "split.tex",
            r"""\documentclass{article}

\begin{document}
\input{sec/intro}
\include{sec/body}
\end{document}
""",
        )
        assert "pulls text in from" in text
        assert "sec/intro" in text
        assert "sec/body" in text

    def test_a_document_that_holds_its_own_text_gets_no_such_note(self, project: Path) -> None:
        text = self._draft(
            project,
            "whole.tex",
            r"""\documentclass{article}

\begin{document}
The combined corpus contains 154,391 utterances \citep{smith2026cxn}.
\end{document}
""",
        )
        assert "pulls text in from" not in text

    def test_a_commented_out_input_is_not_a_file_it_failed_to_read(self, project: Path) -> None:
        text = self._draft(
            project,
            "commented.tex",
            r"""\documentclass{article}

% \input{sec/never}
\begin{document}
Text.
\end{document}
""",
        )
        assert "sec/never" not in text
