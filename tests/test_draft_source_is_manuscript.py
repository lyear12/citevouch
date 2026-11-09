"""`draft` must not propose a claim whose source is the manuscript itself.

`scan` and `verify` refuse a source that is the manuscript being checked: the
sentence in the block would be on that "page" only because the manuscript is
there.  `draft` reads the same files to answer the same question, and before
this it answered it wrongly in the most expensive way available - it wrote a
block the author was told to paste, and pasting it turned a working project
into a `[high] source-is-manuscript` failure.  A command that manufactures the
finding is worse than the silence it replaced, because what it writes is the
thing the author trusts.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = {
    **os.environ,
    "PYTHONPATH": str(ROOT / "src"),
    "PYTHONIOENCODING": "utf-8",
}

# Built with `chr(10)` and `chr(92)` rather than a triple-quoted literal: the
# citation command is LaTeX, and a backslash in a normal string is an invalid
# escape sequence - a warning today, a refusal later.
PAPER = (
    "# Paper"
    + chr(10)
    + chr(10)
    + "We collected precisely 987,654 examples under a blue moon "
    + chr(92)
    + "citep{knuth2020}."
    + chr(10)
)

# The page has to share enough terms with the sentence for a proposal to be
# possible at all - `draft` refuses a passage that shares fewer than three, and
# a fixture below that threshold would make these tests pass for the wrong
# reason.
PAGE = "We collected precisely 987,654 examples under a blue moon.\n"
MANIFEST_BIB = '[sources]\npaper = "page.txt"\n'
MANIFEST_SELF = '[sources]\nknuth2020 = "paper.md"\n'
BIB_WITH_FILE = """\
@article{knuth2020,
  title = {A Real Paper},
  file = {paper.md},
  year = {2020}
}
"""
BIB_WITHOUT_FILE = """\
@article{knuth2020,
  title = {A Real Paper},
  year = {2020}
}
"""


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "citevouch", *args],
        cwd=root,
        env=ENV,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _project(tmp_path: Path, manifesto: str | None = None, bib: str | None = None) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    (root / "paper.md").write_text(PAPER, encoding="utf-8", newline="\n")
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline="\n")
    if manifesto is not None:
        (root / "sources.toml").write_text(manifesto, encoding="utf-8", newline="\n")
    if bib is not None:
        (root / "refs.bib").write_text(bib, encoding="utf-8", newline="\n")
    return root


def _draft(root: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return _run(root, "draft", "paper.md", "--root", ".", "-o", "claims.md", *extra)


def _written(root: Path) -> str:
    return (root / "claims.md").read_text(encoding="utf-8")


class TestAManifestThatBindsTheKeyToTheManuscript:
    def test_no_block_is_proposed(self, tmp_path: Path) -> None:
        root = _project(tmp_path, MANIFEST_SELF)
        assert _draft(root).returncode == 0
        assert "```claim" not in _written(root)

    def test_the_note_says_which_file_is_the_problem(self, tmp_path: Path) -> None:
        root = _project(tmp_path, MANIFEST_SELF)
        _draft(root)
        written = _written(root)
        assert "line 3: knuth2020" in written
        assert "is this manuscript" in written
        assert "point the key at the source paper" in written

    def test_the_block_it_used_to_write_is_one_check_rejects(self, tmp_path: Path) -> None:
        """This is the reason the refusal exists, written down as a test.

        The block below is what `draft` produced before the guard: it quotes a
        sentence out of the manuscript and names that same file as the source.
        Pasting it - which is the only thing the command tells an author to do -
        turns a working project into a `[high] source-is-manuscript` failure.
        """
        root = _project(tmp_path, MANIFEST_SELF)
        (root / "paper.md").write_text(
            PAPER
            + "\n```claim id=knuth2020 source=knuth2020 page=1\n"
            + "quote: |\n  We collected precisely 987,654 examples under a blue moon.\n"
            + "claim: |\n  We collected precisely 987,654 examples under a blue moon.\n"
            + "```\n",
            encoding="utf-8",
            newline="\n",
        )
        proc = _run(root, "check", "paper.md", "--root", ".")
        assert proc.returncode == 1, (proc.stdout, proc.stderr)
        assert "source-is-manuscript" in proc.stdout


class TestABibliographyFileFieldThatNamesTheManuscript:
    def test_no_block_is_proposed(self, tmp_path: Path) -> None:
        root = _project(tmp_path, MANIFEST_BIB, BIB_WITH_FILE)
        assert _draft(root, "--bib", "refs.bib").returncode == 0
        written = _written(root)
        assert "```claim" not in written
        assert "line 3: knuth2020" in written
        assert "is this manuscript" in written

    def test_it_does_not_also_tell_the_author_to_add_the_line(self, tmp_path: Path) -> None:
        """A key resolved from the bibliography needs no `sources.toml` line.

        The renderer prints "add these lines to the [sources] table" whenever
        ``result.needed_sources`` is non-empty, so recording a refused key there
        would put that advice directly above a note saying the file it points at
        cannot be used.  The `file = {paper.md}` route is the one that reaches
        `needed_sources` at all - a manifest-bound key is bound already - so it
        is the case that can see the difference.
        """
        root = _project(tmp_path, MANIFEST_BIB, BIB_WITH_FILE)
        _draft(root, "--bib", "refs.bib")
        assert "resolved to a file but are not in" not in _written(root)


class TestWhatMustStillBeProposed:
    def test_a_real_page_is_untouched(self, tmp_path: Path) -> None:
        root = _project(tmp_path, '[sources]\nknuth2020 = "page.txt"\n')
        assert _draft(root).returncode == 0
        written = _written(root)
        assert "```claim" in written
        assert "source=knuth2020" in written

    def test_a_bibliography_pointing_at_a_real_page_still_works(self, tmp_path: Path) -> None:
        bib = BIB_WITH_FILE.replace("paper.md", "page.txt")
        root = _project(tmp_path, MANIFEST_BIB, bib)
        assert _draft(root, "--bib", "refs.bib").returncode == 0
        assert "```claim" in _written(root)

    def test_a_copy_of_the_manuscript_is_refused_too(self, tmp_path: Path) -> None:
        """Same text under another name has exactly the same problem."""
        root = _project(tmp_path)
        (root / "copy.md").write_text(PAPER, encoding="utf-8", newline="\n")
        (root / "sources.toml").write_text(
            '[sources]\nknuth2020 = "copy.md"\n', encoding="utf-8", newline="\n"
        )
        assert _draft(root).returncode == 0
        written = _written(root)
        assert "```claim" not in written
        assert "is this manuscript" in written

    def test_the_path_alone_is_enough_when_the_digest_is_empty(self, tmp_path: Path) -> None:
        """`is_the_manuscript` must answer without a digest.

        The command always has one, but the function is the seam both passes
        share and its docstring promises the path comparison stands on its own.
        Through the CLI a missing digest is masked by the path also matching,
        so calling it directly is the only place that promise is observable.
        """
        from citevouch.evidence import is_the_manuscript

        manuscript = tmp_path / "paper.md"
        manuscript.write_text("x", encoding="utf-8", newline="\n")
        assert is_the_manuscript(manuscript, manuscript) is True
        assert is_the_manuscript(str(manuscript), manuscript) is True

    def test_a_key_with_no_file_still_gets_the_old_sentence(self, tmp_path: Path) -> None:
        """The new refusal must not swallow the case it does not cover."""
        root = _project(tmp_path, MANIFEST_BIB, BIB_WITHOUT_FILE)
        _draft(root, "--bib", "refs.bib")
        written = _written(root)
        assert "no local file" in written
        assert "is this manuscript" not in written
