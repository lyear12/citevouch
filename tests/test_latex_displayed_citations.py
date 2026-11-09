r"""A ``\verb`` body is printed, not read - but `draft` read it anyway.

TeX prints an inline-verbatim body literally: ``50\verb|%|`` is a percent sign
and ``\verb|\textit{x}|`` is visible backslashes.  The converter therefore drops
each body before the citation patterns run and puts the characters back
afterwards, which is right for the prose.  It was not right for the citation
reader: the restored characters come back in LaTeX spelling, `citation_sites`
recognises that spelling, and the author was told their own example key has no
local file.

Measured before this change, on a manuscript with
``\verb|\citep{ghost2021}|`` beside a real ``\citep{paper}``::

    citevouch: 1 claim block(s) proposed (0 verbatim), 3 citation(s) left as comments
    <!-- line 3: ghost2021 - no local file: not in sources.toml, no `file` field
         in the bibliography, and no file named after the key -->

The sentence that carried the real citation also stopped matching: the example
text beside it travelled into the sentence `draft` compared.

The Markdown half of this defect was fixed by blanking the display before
anything reads it (`display.py`).  The LaTeX half cannot use the same answer,
because the restored characters have to stay - they are what the paper prints.
The converter is the only code that knows where each body landed, so it now
says where, and the mask is applied to exactly those spans.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from citevouch import latex
from citevouch.cli import main

NL = chr(10)
BS = chr(92)

SAMPLE = (
    "We collected forty thousand examples from the corpus of written English "
    "and then filtered them by hand before training the model."
)

INLINE = [
    BS + "verb",
    BS + "verb*",
    BS + "lstinline",
    BS + "mintinline{tex}",
    BS + "lstinline[language=TeX]",
]


def _document(body: str) -> str:
    return (
        BS
        + "documentclass{article}"
        + NL
        + BS
        + "begin{document}"
        + NL
        + body
        + BS
        + "end{document}"
        + NL
    )


def _project(tmp_path: Path, body: str) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    (root / "manuscript.tex").write_text(_document(body), encoding="utf-8", newline=NL)
    (root / "page.txt").write_text(SAMPLE + NL, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    return root


def _draft(tmp_path: Path, body: str) -> str:
    root = _project(tmp_path, body)
    code = main(["draft", str(root / "manuscript.tex"), "--root", str(root)])
    assert code == 0
    return (root / "claims.md").read_text(encoding="utf-8")


def _notes(written: str) -> list[str]:
    return [line for line in written.splitlines() if line.startswith("<!-- line ")]


def _quote(written: str) -> str:
    lines = written.splitlines()
    for index, line in enumerate(lines):
        if line.strip().startswith("quote:"):
            body: list[str] = []
            for following in lines[index + 1 :]:
                if not following.startswith("  "):
                    break
                body.append(following.strip())
            return " ".join(body)
    return ""


class TestAShownCitationIsNotACitationTheAuthorMade:
    """All five inline-verbatim commands print a body; none of them cites.

    The second test below shows the shape this round does *not* fix: a body
    inside the very sentence that cites a real page blanks a hole in that
    sentence, so it stops matching word for word and falls back to the
    medium-confidence passage.  That is the same behaviour Markdown inline code
    has - already measured and recorded in `docs/backlog.md` - and fixing it
    means comparing against the text with holes rather than against the printed
    characters, which is a different change from this one.
    """

    @pytest.mark.parametrize(
        "command",
        INLINE,
        ids=["verb", "verb-star", "lstinline", "mintinline", "lstinline-optional"],
    )
    def test_the_shown_key_is_not_reported_missing(self, tmp_path: Path, command: str) -> None:
        written = _draft(
            tmp_path,
            "The syntax is " + command + r"|\citep{ghost2021}| and that is all." + NL + NL,
        )
        assert "ghost2021" not in written, written

    @pytest.mark.parametrize(
        "command",
        INLINE,
        ids=["verb", "verb-star", "lstinline", "mintinline", "lstinline-optional"],
    )
    def test_the_real_citation_beside_it_is_still_proposed(
        self, tmp_path: Path, command: str
    ) -> None:
        written = _draft(
            tmp_path,
            "We show it as "
            + command
            + r"|\citep{ghost2021}| in "
            + SAMPLE
            + r" \citep{paper}."
            + NL,
        )
        assert "ghost2021" not in written, written
        assert "```claim id=paper" in written, written
        assert "confidence: medium" in written, written

    def test_a_separate_paragraph_keeps_the_verbatim_sentence(self, tmp_path: Path) -> None:
        r"""The example above the sentence does not join it."""
        written = _draft(
            tmp_path,
            "The syntax is "
            + BS
            + r"verb|\citep{ghost2021}| and that is all."
            + NL
            + NL
            + SAMPLE
            + r" \citep{paper}."
            + NL,
        )
        assert "ghost2021" not in written, written
        assert "confidence: high" in written, written
        assert _quote(written) == SAMPLE


class TestWhatThePaperStillPrints:
    r"""A body that is put back must come back as characters, not as nothing.

    This is the half of the defect the mask must not break: the reason the
    converter restores bodies at all is that TeX prints them.
    """

    def test_a_percent_sign_survives(self) -> None:
        converted = latex.to_text(
            BS + "begin{document}We use 50" + BS + "verb|%| of it." + BS + "end{document}"
        )
        assert "50%" in converted

    def test_backslashes_are_visible(self) -> None:
        converted = latex.to_text(
            BS
            + "begin{document}See "
            + BS
            + "verb|"
            + BS
            + "textit{x}| here."
            + BS
            + "end{document}"
        )
        assert BS + "textit{x}" in converted

    def test_the_literal_is_not_part_of_the_claim_sentence(self, tmp_path: Path) -> None:
        r"""The body is printed for a reader, so it is not words of the sentence.

        The mask blanks it here exactly as it blanks a fenced block: `50%` is
        what the page shows, not what the author's sentence says.  That the
        characters survive the converter at all is the test above.
        """
        written = _draft(
            tmp_path,
            "We use 50" + BS + "verb|%| of it in " + SAMPLE + " " + BS + "citep{paper}." + NL,
        )
        assert "```claim id=paper" in written, written
        claim = next(line for line in written.splitlines() if line.startswith("claim:"))
        assert "%" not in claim, written


class TestTheConverterSaysWhereEachBodyLanded:
    """The spans must describe the string the caller gets, not an earlier one."""

    def test_the_spans_are_the_bodies_in_the_result(self) -> None:
        text, displayed = latex.to_text_and_display(
            BS
            + "begin{document}We wrote "
            + BS
            + "verb|"
            + BS
            + "citep{g}| and 50"
            + BS
            + "verb|%| here."
            + BS
            + "end{document}"
        )
        assert [text[start:end] for start, end in displayed] == [
            BS + "citep{g}",
            "%",
        ]

    def test_the_two_functions_agree(self) -> None:
        source = (
            BS
            + "begin{document}We wrote "
            + BS
            + "verb|"
            + BS
            + "citep{g}| here."
            + BS
            + "end{document}"
        )
        assert latex.to_text_and_display(source)[0] == latex.to_text(source)

    def test_a_document_with_no_body_reports_nothing(self) -> None:
        text, displayed = latex.to_text_and_display(
            BS + "begin{document}Plain " + BS + "citep{a} here." + BS + "end{document}"
        )
        assert displayed == []
        assert text == "Plain [@a] here.\n"

    def test_whitespace_collapsing_does_not_move_the_spans(self) -> None:
        r"""A body may sit after the runs of spaces the converter collapses."""
        body = (
            BS
            + "section{A heading}"
            + NL
            + NL
            + NL
            + "We wrote "
            + BS
            + "verb|"
            + BS
            + "citep{g}| here."
            + NL
        )
        text, displayed = latex.to_text_and_display(
            BS + "begin{document}" + body + BS + "end{document}"
        )
        assert [text[start:end] for start, end in displayed] == [BS + "citep{g}"]


class TestWhatTheMaskLeavesAlone:
    """Only the restored bodies are blanked; the prose keeps its citations."""

    def test_a_real_citation_still_produces_a_block(self, tmp_path: Path) -> None:
        written = _draft(tmp_path, SAMPLE + " " + BS + "citep{paper}." + NL)
        assert "```claim" in written
        assert _notes(written) == []
        assert _quote(written) == SAMPLE

    def test_a_missing_real_key_is_still_reported(self, tmp_path: Path) -> None:
        written = _draft(
            tmp_path,
            "We show "
            + BS
            + "verb|"
            + BS
            + "citep{ghost}| how to cite "
            + SAMPLE
            + ". "
            + BS
            + "citep{absent}."
            + NL,
        )
        assert "ghost" not in written.replace("ghost}|", ""), written
        assert any("absent" in note for note in _notes(written)), written
