"""``\\input`` has two spellings, and only one of them used to be handled.

Plain TeX writes ``\\input sec/intro``; LaTeX writes ``\\input{sec/intro}``.
The converter knew the braced form on both sides - it dropped the argument from
the prose and reported the file as included - and knew the bare form on neither:
the path was left glued into the sentence (`We show this in sec_intro and
continue the argument here.`) while `included_files` returned `[]`, so a paper
split across files got a clean zero that named neither the missing half nor the
stray word.  These tests hold both spellings to the same answer.
"""

from __future__ import annotations

import contextlib
import io
from pathlib import Path

from citevouch import latex
from citevouch.cli import main

SOURCE = "The method was shown to work on the corpus by previous studies.\n"


def _draft(root: Path, tex: str) -> tuple[int, str]:
    """Run ``draft`` on a .tex file and return (exit code, everything printed)."""
    (root / "paper.tex").write_text(tex, encoding="utf-8", newline="\n")
    (root / "page.txt").write_text(SOURCE, encoding="utf-8", newline="\n")
    out = root / "claims.md"
    buffer = io.StringIO()
    argv = [
        "draft",
        "paper.tex",
        "--root",
        str(root),
        "--source",
        str(root / "page.txt"),
        "-o",
        str(out),
        "--force",
    ]
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        code = main(argv)
    printed = buffer.getvalue()
    if out.is_file():
        printed += out.read_text(encoding="utf-8")
    return code, printed


class TestTheBareFormIsNotProse:
    def test_the_file_name_does_not_survive_in_the_sentence(self) -> None:
        text = latex.to_text("We show this in \\input sec_intro and continue here.")
        assert "sec_intro" not in text
        assert "We show this in and continue here." in text

    def test_the_braced_form_behaves_the_same_way(self) -> None:
        text = latex.to_text("We show this in \\input{sec_intro} and continue here.")
        assert "sec_intro" not in text
        assert "We show this in and continue here." in text

    def test_a_bare_input_with_nothing_after_it_does_not_crash(self) -> None:
        assert "input" not in latex.to_text("A \\input").lower()


class TestTheBareFormIsReported:
    def test_a_bare_input_is_named(self) -> None:
        assert latex.included_files("Text \\input sec/intro more.") == ["sec/intro"]

    def test_the_two_spellings_are_reported_in_the_order_written(self) -> None:
        tex = "\\input first/one and \\input{second/two} and \\input third/three \n"
        assert latex.included_files(tex) == ["first/one", "second/two", "third/three"]

    def test_a_bare_name_ends_where_tex_ends_it(self) -> None:
        """``.`` is part of the name to TeX, so it is part of the name here.

        ``\\input third/three.tex`` has to keep its extension.  The price is
        that a sentence ending in a bare ``\\input`` swallows the full stop -
        which is what TeX does too, and is why the name is reported rather than
        silently dropped.
        """
        assert latex.included_files("\\input third/three.tex\n") == ["third/three.tex"]

    def test_a_file_named_twice_is_named_once(self) -> None:
        assert latex.included_files("\\input a/b and \\input {a/b}") == ["a/b"]

    def test_a_path_inside_verbatim_is_not_an_include(self) -> None:
        assert latex.included_files("\\verb|\\input fake/one|") == []

    def test_a_path_inside_a_comment_is_not_an_include(self) -> None:
        assert latex.included_files("% \\input commented/two\nText.") == []


class TestTheDraftSaysWhichHalfItDidNotRead:
    def test_the_statement_does_not_carry_the_file_name(self, tmp_path: Path) -> None:
        code, printed = _draft(
            tmp_path,
            "The method was shown to work on the corpus by previous studies "
            "\\input sec/intro and then some more words follow here.\n",
        )
        assert code == 0
        assert "sec_intro" not in printed

    def test_the_output_names_the_file_it_did_not_open(self, tmp_path: Path) -> None:
        code, printed = _draft(
            tmp_path,
            "The method was shown to work on the corpus by previous studies. "
            "\\input sec/intro\n",
        )
        assert code == 0
        assert "pulls text in from" in printed
        assert "sec/intro" in printed


def test_the_braced_form_still_reaches_the_same_note(tmp_path: Path) -> None:
    """The spelling that always worked keeps working, through the real entry point."""
    code, printed = _draft(
        tmp_path,
        "The method was shown to work on the corpus by previous studies. \\input{sec/intro}\n",
    )
    assert code == 0
    assert "pulls text in from" in printed
    assert "sec/intro" in printed
