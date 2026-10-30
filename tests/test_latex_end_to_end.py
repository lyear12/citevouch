"""A .tex manuscript goes all the way through: draft, then check.

`tests/test_latex.py` proves the conversion and `tests/test_draft.py` proves the
proposals; this file proves the seam between them - that `citevouch draft
paper.tex` produces a file `citevouch check` accepts unchanged. A seam is where
this project has historically lost things: `init-demo` used to write a project
its own documented next command rejected, and the two halves were each passing.
"""

from __future__ import annotations

import os
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
