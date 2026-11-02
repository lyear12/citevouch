"""Commands that name something other than text must not leave their name in it.

Every command in here fell through to the converter's last branch - "an unknown
command: keep whatever text it wraps, drop the name" - which is the right answer
for a wrapper around a sentence and the wrong one for a command that takes a
counter, a length, a style or a registry key.  Measured before this file existed:

    \\setcounter{page}{3}We collected 40,688 examples.
        -> '3We collected 40,688 examples.'
    \\pagestyle{fancy} This chapter argues so.
        -> 'fancy This chapter argues so.'
    \\setlength{\\parindent}{2em} Indented.
        -> '2em Indented.'
    \\usetikzlibrary{arrows.meta} Body.
        -> 'arrows.meta Body.'

The digit case is the one that costs an author something: `draft` proposes a
claim block whose `claim:` line is the sentence, so the block it wrote read
`3We collected 40,688 examples` - a claim the paper never made, with a number
nobody typed, and the ledger records what the block says.

Each case states the whole converted text rather than a list of forbidden words:
the expected string is the thing a reader would see, and comparing against it
catches a command that drops the wrong number of arguments as well as one that
drops none.
"""

from __future__ import annotations

import io
import os
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from citevouch.cli import main
from citevouch.latex import to_text

BS = chr(92)

#: `spelling: (source, converted)`.  Neither the counter, the length, the style
#: nor the library name may appear in the converted text.
NON_PROSE: dict[str, tuple[str, str]] = {
    "setcounter": (
        BS + "setcounter{page}{3}We collected 40,688 examples.",
        "We collected 40,688 examples.",
    ),
    "addtocounter": (
        BS + "addtocounter{figure}{2}Then we show it.",
        "Then we show it.",
    ),
    "stepcounter": (BS + "stepcounter{figure}Figures advance.", "Figures advance."),
    "refstepcounter": (BS + "refstepcounter{table}Tables advance.", "Tables advance."),
    "setlength": (
        BS + "setlength{" + BS + "parindent}{6pt plus 2pt}Indented.",
        "Indented.",
    ),
    "addtolength": (BS + "addtolength{" + BS + "parindent}{1em}Indented.", "Indented."),
    "settowidth": (
        BS + "settowidth{" + BS + "foo}{wide text}Width is set.",
        "Width is set.",
    ),
    "pagestyle": (BS + "pagestyle{fancy}This chapter argues so.", "This chapter argues so."),
    "thispagestyle": (BS + "thispagestyle{empty}The page is bare.", "The page is bare."),
    "pagenumbering": (BS + "pagenumbering{roman}Pages are numbered.", "Pages are numbered."),
    "markboth": (
        BS + "markboth{left head}{right head}Text continues here.",
        "Text continues here.",
    ),
    "markright": (BS + "markright{running head}Text continues here.", "Text continues here."),
    "addcontentsline": (
        BS + "addcontentsline{toc}{section}{Title here}Body follows.",
        "Body follows.",
    ),
    "usetikzlibrary": (BS + "usetikzlibrary{arrows.meta}Body follows.", "Body follows."),
    "graphicspath": (BS + "graphicspath{{figs/}{imgs/}}Body follows.", "Body follows."),
    "selectlanguage": (BS + "selectlanguage{english}Body follows.", "Body follows."),
    "newcounter": (BS + "newcounter{myctr}Body follows.", "Body follows."),
    "phantom": ("Before" + BS + "phantom{invisible}after.", "Beforeafter."),
    "hphantom": ("Before" + BS + "hphantom{invisible}after.", "Beforeafter."),
    "vphantom": ("Before" + BS + "vphantom{invisible}after.", "Beforeafter."),
    "index": (
        "This is important" + BS + "index{important} indeed.",
        "This is important indeed.",
    ),
    "glossary": (BS + "glossary{term}We define the notion here.", "We define the notion here."),
    "DeclareMathOperator": (
        BS + "DeclareMathOperator{" + BS + "argmax}{arg" + BS + ",max}We maximise.",
        "We maximise.",
    ),
    "rule": ("Text before" + BS + "rule{3cm}{0.4pt}text after.", "Text beforetext after."),
    "citeindextype": (BS + "citeindextype{default}Body follows.", "Body follows."),
    "pdfbookmark": (BS + "pdfbookmark[1]{Bookmark}{bm}Body follows.", "Body follows."),
    "definelabel": (BS + "definelabel{name}{text}Body follows.", "Body follows."),
    "footnotemark": ("Text" + BS + "footnotemark[1] continues.", "Text continues."),
}

#: Commands whose leading arguments are not prose and whose last one is.
LEADING: dict[str, tuple[str, str]] = {
    "multicolumn": (BS + "multicolumn{2}{c}{wide text} continues.", "wide text continues."),
    "foreignlanguage": (
        BS + "foreignlanguage{german}{Ein Satz.} Body follows.",
        "Ein Satz. Body follows.",
    ),
    "href": (BS + "href{http://example.com}{shown text}", "shown text"),
    "parbox": (BS + "parbox[t]{3cm}{boxed}", "boxed"),
    "fcolorbox": (BS + "fcolorbox{red}{white}{two}", "two"),
    "resizebox": (BS + "resizebox{1cm}{!}{resized}", "resized"),
}


class TestTheNameNeverReachesTheProse:
    @pytest.mark.parametrize("name", sorted(NON_PROSE))
    def test_the_converted_text_is_the_sentence_and_nothing_else(self, name: str) -> None:
        source, expected = NON_PROSE[name]
        assert to_text(source).strip() == expected

    def test_the_setcounter_digit_is_not_the_first_character_of_the_sentence(self) -> None:
        # The defect this file was opened for: `draft` proposes the sentence as
        # the claim, so a stray `3` became the claim's first character.
        out = to_text(BS + "setcounter{page}{3}We collected 40,688 examples.")
        assert out.strip() == "We collected 40,688 examples."

    @pytest.mark.parametrize("name", sorted(LEADING))
    def test_only_the_leading_arguments_are_dropped(self, name: str) -> None:
        source, expected = LEADING[name]
        assert to_text(source).strip() == expected

    def test_texorpdfstring_says_the_words_once(self) -> None:
        # `\texorpdfstring{TeX text}{PDF text}` carries the same words twice;
        # keeping both said them twice, once in a form no reader sees.
        out = to_text(BS + "texorpdfstring{TeX text}{PDF text} Body.")
        assert out.strip() == "TeX text Body."

    def test_a_definition_spelled_the_xparse_way_is_still_a_definition(self) -> None:
        tex = BS + "newcommandx{" + BS + "x}[1]{Body #1} Body follows."
        out = to_text(tex)
        assert "#1" not in out
        assert out.strip() == "Body follows."


class TestTheSentenceSurvivesTheCleanup:
    def test_the_words_around_a_counter_are_untouched(self) -> None:
        tex = (
            "Our corpus is described below. "
            + BS
            + "setcounter{page}{3}"
            + "We collected 40,688 examples in total."
        )
        out = to_text(tex)
        assert "3We" not in out
        assert "We collected 40,688 examples in total." in out

    def test_a_command_with_no_arguments_is_left_alone(self) -> None:
        # The guard must not swallow the word after a command that takes none.
        out = to_text("Para one." + BS + "bigskip Para two.")
        assert out.strip() == "Para one. Para two."


class TestTheDraftDoesNotInheritTheNumber:
    def test_the_proposed_claim_starts_where_the_sentence_starts(self) -> None:
        root = Path(tempfile.mkdtemp())
        try:
            (root / "page.txt").write_text(
                "We collected 40,688 examples in total, as the report says.\n",
                encoding="utf-8",
            )
            (root / "refs.bib").write_text(
                "@article{page, title={T}, author={A}, year={2026}, journal={J}}\n",
                encoding="utf-8",
            )
            (root / "paper.tex").write_text(
                BS
                + "setcounter{page}{3}"
                + "We collected 40,688 examples in total, as "
                + BS
                + "citep{page} reports.",
                encoding="utf-8",
            )
            out, err = io.StringIO(), io.StringIO()
            previous = os.getcwd()
            try:
                os.chdir(root)
                with redirect_stdout(out), redirect_stderr(err):
                    code = main(
                        [
                            "draft",
                            "paper.tex",
                            "--root",
                            ".",
                            "--bib",
                            "refs.bib",
                            "-o",
                            "claims.md",
                        ]
                    )
            finally:
                os.chdir(previous)
            assert code == 0
            written = (root / "claims.md").read_text(encoding="utf-8")
            claim_body = written.split("```claim", 1)[-1]
            assert "3We" not in claim_body
            assert "We collected 40,688 examples" in claim_body
        finally:
            for path in sorted(root.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                else:
                    path.rmdir()
            root.rmdir()
