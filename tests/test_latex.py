"""A .tex manuscript is read as the sentences it contains.

Every test here is about the same question: can `draft` find the citation and
the sentence around it in a file written for LaTeX? The quote itself always comes
from the PDF, so a mis-read sentence costs a worse proposal - never a false
verification - but a citation that is not found at all costs the whole feature.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from citevouch import draft, latex

MINIMAL = r"""
\documentclass[11pt]{article}
\usepackage{graphicx}
\newcommand{\frameword}{frame}
\title{A paper nobody reads}
\begin{document}
\maketitle

\section{Introduction}

Construction grammar has a long history in computational linguistics
\citep{smith2026paper}. The corpus we use here is large for the task
\citep[p.~3]{doe2025corpus}.

% This sentence is commented out \citep{ghost2020missing}.
Even so, precision matters \citep{smith2026paper,doe2025corpus}.

\begin{table}
\centering
\begin{tabular}{ll}
Model & F1 \\
\hline
Ours & 90.1 \\
\end{tabular}
\caption{Results we do not cite here.}
\end{table}

\begin{thebibliography}{9}
\bibitem{smith2026paper} Smith, A. (2026). A paper nobody reads.
\end{thebibliography}
\end{document}

After the document: not part of the manuscript \citep{after2020end}.
"""


class TestTheDocumentIsWhatIsBetweenBeginAndEnd:
    def test_the_preamble_is_not_prose(self) -> None:
        text = latex.to_text(MINIMAL)
        assert "documentclass" not in text
        assert "usepackage" not in text
        assert "newcommand" not in text

    def test_what_follows_the_document_is_dropped(self) -> None:
        text = latex.to_text(MINIMAL)
        assert "After the document" not in text
        assert "after2020end" not in text

    def test_the_bibliography_is_dropped(self) -> None:
        """A reference list is not a sentence that cites anything."""
        text = latex.to_text(MINIMAL)
        assert "bibitem" not in text
        assert "Smith, A." not in text

    def test_a_table_is_dropped_whole(self) -> None:
        text = latex.to_text(MINIMAL)
        assert "90.1" not in text
        assert "Ours" not in text


class TestCommentsAndEscapes:
    def test_a_percent_comment_is_removed(self) -> None:
        text = latex.to_text(MINIMAL)
        assert "commented out" not in text
        assert "ghost2020missing" not in text

    def test_an_escaped_percent_is_literal(self) -> None:
        converted = latex.to_text(
            r"\begin{document}A rise of 12.5\% was observed.\end{document}"
        )
        assert "12.5%" in converted

    def test_a_backslash_before_the_percent_does_not_hide_code(self) -> None:
        r"""`\\%` is a line break then a comment, not a literal percent."""
        converted = latex.to_text(
            "\\begin{document}first line \\\\% a comment\nsecond\n\\end{document}"
        )
        assert "a comment" not in converted
        assert "second" in converted


class TestCitationsBecomeTheMarkerTheRestOfTheToolReads:
    def test_a_citation_becomes_a_pandoc_marker(self) -> None:
        text = latex.to_text(MINIMAL)
        assert "[@smith2026paper]" in text
        assert "\\citep" not in text

    def test_several_keys_in_one_command(self) -> None:
        text = latex.to_text(MINIMAL)
        assert "[@smith2026paper; @doe2025corpus]" in text

    def test_an_optional_note_before_the_keys_is_dropped(self) -> None:
        text = latex.to_text(MINIMAL)
        assert "p.~3" not in text
        assert "p. 3]" not in text

    @pytest.mark.parametrize(
        "command",
        [
            "cite",
            "citep",
            "citet",
            "citealp",
            "citealt",
            "citeauthor",
            "citeyear",
            "nocite",
            "parencite",
            "textcite",
            "autocite",
            "footcite",
        ],
    )
    def test_every_citation_command_is_understood(self, command: str) -> None:
        source = f"\\begin{{document}}Text \\{command}{{a2020key}} here.\\end{{document}}"
        assert "[@a2020key]" in latex.to_text(source)

    def test_a_starred_citation_is_understood(self) -> None:
        source = r"\begin{document}Text \citet*{a2020key} here.\end{document}"
        assert "[@a2020key]" in latex.to_text(source)

    def test_the_marker_survives_into_a_sentence_the_tool_can_read(self) -> None:
        """The point of the marker is that `draft` needs no second code path."""
        text = latex.to_text(MINIMAL)
        sites = draft.citation_sites(text)
        keys = [site.key for site in sites]
        assert keys.count("smith2026paper") == 2
        assert "doe2025corpus" in keys
        sentence, _, _ = draft.sentence_at(text, sites[0].start)
        assert "Construction grammar has a long history" in sentence


class TestCommandsThatCarryText:
    def test_a_section_title_becomes_its_own_paragraph(self) -> None:
        """Otherwise the sentence finder glues a heading onto the text below it."""
        text = latex.to_text(MINIMAL)
        assert "Introduction\n\n" in text
        assert "Introduction Construction" not in text

    def test_bold_text_keeps_its_words(self) -> None:
        converted = latex.to_text(
            r"\begin{document}A \textbf{bold claim} follows.\end{document}"
        )
        assert "bold claim" in converted
        assert "textbf" not in converted

    def test_a_label_is_dropped_without_leaving_a_hole(self) -> None:
        converted = latex.to_text(
            r"\begin{document}See the section\label{sec:one} above.\end{document}"
        )
        assert "label" not in converted
        assert "sec:one" not in converted
        assert "See the section above." in converted

    def test_inline_math_loses_its_commands_but_keeps_its_numbers(self) -> None:
        converted = latex.to_text(
            r"\begin{document}We set $\alpha = 0.5$ for all runs.\end{document}"
        )
        assert "alpha" not in converted
        assert "0.5" in converted

    def test_a_tilde_is_a_space(self) -> None:
        converted = latex.to_text(r"\begin{document}see Fig.~3 for the split.\end{document}")
        assert "Fig. 3" in converted


class TestWhatItDoesNotClaimToDo:
    def test_a_braced_group_with_no_command_is_left_alone(self) -> None:
        converted = latex.to_text(r"\begin{document}{plain} text\end{document}")
        assert "plain" in converted

    def test_an_unbalanced_environment_does_not_raise(self) -> None:
        converted = latex.to_text(r"\begin{document}\begin{itemize}\item one")
        assert "one" in converted

    def test_an_unclosed_math_does_not_raise(self) -> None:
        converted = latex.to_text(r"\begin{document}a $\alpha b\end{document}")
        assert isinstance(converted, str)

    def test_looks_like_latex_reads_the_suffix(self) -> None:
        assert latex.looks_like_latex("paper.tex")
        assert latex.looks_like_latex(Path("x/y/PAPER.TEX"))
        assert not latex.looks_like_latex("paper.md")
        assert not latex.looks_like_latex("paper.tex.md")

    def test_the_module_says_it_is_not_a_parser(self) -> None:
        assert "not a TeX parser" in (latex.__doc__ or "")
