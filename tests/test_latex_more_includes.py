"""Seven more file-inclusion commands pasted their path into the prose.

`\\input` and `\\include` were handled; these were not:

    \\subfile{sec/intro}       -> 'sec/intro' in the text, nothing reported
    \\import{chapters/}{one}   -> 'chapters/one' in the text, nothing reported
    \\includepdf{pages/p1.pdf} -> 'pages/p1.pdf'
    \\lstinputlisting{c.py}   -> 'c.py'
    \\verbatiminput{d.txt}    -> 'd.txt'
    \\includestandalone{f}    -> 'f'
    \\subimport{}{two}        -> 'two'

A paper split across files keeps its citations in the parts, so `draft` was
proposing claims built on sentences with a file path in them while telling the
author that nothing had been left out.  Both halves of that had to change, which
is why every test here checks the text and the report together.
"""

from __future__ import annotations

import contextlib
import io
from pathlib import Path

import pytest

from citevouch import latex
from citevouch.cli import main

INCLUDING = [
    (r"A \subfile{sec/intro} B", "sec/intro"),
    (r"A \import{chapters/}{one} B", "chapters/one"),
    (r"A \subimport{}{two} B", "two"),
    (r"A \includestandalone{figs/chart} B", "figs/chart"),
    (r"A \includepdf{pages/p1.pdf} B", "pages/p1.pdf"),
    (r"A \lstinputlisting{code/s1.py} B", "code/s1.py"),
    (r"A \verbatiminput{data/t.txt} B", "data/t.txt"),
]


class TestTheNameLeavesTheProse:
    @pytest.mark.parametrize(("source", "name"), INCLUDING)
    def test_the_path_is_not_in_the_sentence(self, source: str, name: str) -> None:
        converted = latex.to_text(source)
        assert name not in converted
        assert converted.split() == ["A", "B"]

    @pytest.mark.parametrize(("source", "name"), INCLUDING)
    def test_the_file_is_reported(self, source: str, name: str) -> None:
        assert latex.included_files(source) == [name]


class TestTheArgumentsThatAreNotProseAreSkippedWhole:
    def test_import_joins_its_two_arguments(self) -> None:
        assert latex.included_files(r"\import{chapters/}{one}") == ["chapters/one"]

    def test_subimport_with_an_empty_directory(self) -> None:
        assert latex.included_files(r"\subimport{}{two}") == ["two"]

    def test_an_optional_argument_before_the_name(self) -> None:
        assert latex.included_files(r"\includepdf[pages=1]{p1.pdf}") == ["p1.pdf"]

    def test_two_optional_arguments_before_the_name(self) -> None:
        source = r"\lstinputlisting[language=Python,firstline=2]{s.py}"
        assert latex.included_files(source) == ["s.py"]

    def test_a_deep_path_survives(self) -> None:
        assert latex.included_files(r"\subfile{sub/deep/one}") == ["sub/deep/one"]


class TestTheFormsThatAreNotProse:
    def test_a_verbatim_example_is_not_an_include(self) -> None:
        assert latex.included_files(r"\verb|\subfile{fake}|") == []

    def test_a_comment_is_not_an_include(self) -> None:
        assert latex.included_files("% \\subfile{commented}\nText.") == []

    def test_the_text_inside_verbatim_is_kept(self) -> None:
        assert "\\subfile{fake}" in latex.to_text(r"A \verb|\subfile{fake}| B")


class TestTheOlderCommandsStillWork:
    def test_the_three_original_forms_are_still_reported(self) -> None:
        source = r"\input{a} \include{b} \includeonly{c}"
        assert latex.included_files(source) == ["a", "b", "c"]

    def test_everything_is_reported_in_source_order(self) -> None:
        source = r"\subfile{one} \input{two} \import{dir/}{three} \include{four}"
        assert latex.included_files(source) == ["one", "two", "dir/three", "four"]

    def test_a_file_named_by_two_commands_is_named_once(self) -> None:
        assert latex.included_files(r"\subfile{x} \input{x}") == ["x"]


class TestTheDraftSaysWhichHalfItDidNotRead:
    def test_a_subfile_is_named_in_the_note(self, tmp_path: Path) -> None:
        (tmp_path / "paper.tex").write_text(
            "The method was shown to work on the corpus by previous studies "
            "\\citep{page}. \\subfile{sec/intro}\n",
            encoding="utf-8",
            newline="\n",
        )
        (tmp_path / "page.txt").write_text(
            "The method was shown to work on the corpus by previous studies\n",
            encoding="utf-8",
            newline="\n",
        )
        out = tmp_path / "claims.md"
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            code = main(
                [
                    "draft",
                    "paper.tex",
                    "--root",
                    str(tmp_path),
                    "--source",
                    str(tmp_path / "page.txt"),
                    "-o",
                    str(out),
                    "--force",
                ]
            )
        assert code == 0
        written = out.read_text(encoding="utf-8")
        assert "pulls text in from" in written
        assert "sec/intro" in written
        # The note has to name it; the claim body must not carry it.
        assert "```claim" in written, written
        claim_block = written.split("```claim", 1)[-1]
        assert "sec/intro" not in claim_block
