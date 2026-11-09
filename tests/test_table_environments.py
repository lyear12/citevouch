"""A table is not prose, whatever package draws it.

``_DROP_ENVIRONMENT`` held ``tabular`` and ``tabular*`` and nothing else, so a
paper using ``tabularx`` - the package most journals tell authors to use for a
table that fills the text width - had its whole table read as sentences.  The
column specification leaked first (``{lX}`` came out as the word ``lX``), then
every cell, then a citation written to label a row became a citation of the
paper's argument.

Measured before the fix, converting::

    \\begin{tabularx}{\\linewidth}{lX}
    Baseline & 90,000 \\\\

gave ``lX\\nBaseline & 90,000``.  Through ``draft`` that produced::

    0 claim block(s) proposed (0 verbatim), 1 citation(s) left as comments
    <!-- line 9: knuth2020 - nothing on any page shares enough terms with the
         sentence (3 needed) -->

The sentence it could not match was ``Baseline \\citep{knuth2020} & 90,000`` -
a row of a table, assembled out of a column spec and two ampersands.  With
``tabular`` the same table was dropped and the run said "no citations were
found", which is the truth: a table is not a sentence that cites anything.
"""

from __future__ import annotations

import pytest

from citevouch import latex

BS = chr(92)
NL = chr(10)

#: Text-mode table environments: their body is a grid of cells a reader sees as
#: data, not as a sentence the author is asserting.  Every name here is a real
#: package.  ``array`` and the ``matrix`` family are deliberately *not* here -
#: they live inside math mode, where a number is part of the formula and the
#: converter keeps it on purpose (see ``TestMathIsLeftAlone``).
TABLE_ENVIRONMENTS = (
    "tabularx",
    "xltabular",
    "tabulary",
    "longtable",
    "tabu",
    "longtabu",
    "supertabular",
)

#: The ones whose argument list is itself typesetting rather than text.
WITH_COLUMN_SPEC = TABLE_ENVIRONMENTS


def _document(body: str) -> str:
    return BS + "begin{document}" + NL + body + NL + BS + "end{document}" + NL


def _table(environment: str, spec: str = "{lX}") -> str:
    opening = BS + "begin{" + environment + "}{" + BS + "linewidth}" + spec
    return NL.join(
        [
            opening,
            "Baseline " + BS + "citep{knuth2020} & 90,000 " + BS * 2,
            BS + "end{" + environment + "}",
        ]
    )


class TestTheBodyIsNotProse:
    @pytest.mark.parametrize("environment", TABLE_ENVIRONMENTS)
    def test_the_cells_do_not_reach_the_text(self, environment: str) -> None:
        text = latex.to_text(_document(_table(environment)))
        assert "90,000" not in text
        assert "Baseline" not in text

    @pytest.mark.parametrize("environment", TABLE_ENVIRONMENTS)
    def test_the_column_specification_is_not_a_word(self, environment: str) -> None:
        """`{lX}` is how wide the columns are; it is not prose."""
        text = latex.to_text(_document(_table(environment)))
        assert "lX" not in text

    @pytest.mark.parametrize("environment", TABLE_ENVIRONMENTS)
    def test_a_citation_in_a_cell_cites_nothing(self, environment: str) -> None:
        """A key in a table labels a row; it does not support the sentence."""
        text = latex.to_text(_document(_table(environment)))
        assert "[@knuth2020]" not in text
        assert "knuth2020" not in text

    def test_the_prose_around_the_table_survives(self) -> None:
        body = NL.join(
            [
                "The total below is important.",
                _table("tabularx"),
                "After the total.",
            ]
        )
        text = latex.to_text(_document(body))
        assert "The total below is important." in text
        assert "After the total." in text


class TestWhatWasAlreadyDroppedStaysDropped:
    @pytest.mark.parametrize("environment", ["tabular", "tabular*"])
    def test_the_two_names_that_were_there(self, environment: str) -> None:
        spec = "" if environment == "tabular*" else "{ll}"
        body = NL.join(
            [
                BS + "begin{" + environment + "}{" + BS + "linewidth}" + spec,
                "Ours & 90.1 " + BS * 2,
                BS + "end{" + environment + "}",
            ]
        )
        text = latex.to_text(_document(body))
        assert "90.1" not in text
        assert "Ours" not in text

    def test_a_nested_tabular_inside_a_table_environment(self) -> None:
        inner = NL.join(
            [
                BS + "begin{tabularx}{" + BS + "linewidth}{lX}",
                BS + "begin{tabular}{ll}",
                "Inner & 40,688 " + BS * 2,
                BS + "end{tabular}",
                BS + "end{tabularx}",
            ]
        )
        text = latex.to_text(_document(inner))
        assert "40,688" not in text
        assert "Inner" not in text

    def test_an_unclosed_table_environment_does_not_raise(self) -> None:
        text = latex.to_text(
            _document(BS + "begin{longtable}{ll}" + NL + "Baseline & 90,000 " + BS * 2)
        )
        assert "90,000" not in text

    def test_a_table_nested_in_the_same_environment_is_counted(self) -> None:
        """One ``\\\\end{tabularx}`` closes the inner table, not the outer one.

        The skipper counts openers and closers of the *same* name, so a nested
        table of the same package must not end the outer one early and hand
        everything after it back to the prose reader.
        """
        outer = NL.join(
            [
                BS + "begin{tabularx}{" + BS + "linewidth}{lX}",
                BS + "begin{tabularx}{" + BS + "linewidth}{l}",
                "Inner & 40,688 " + BS * 2,
                BS + "end{tabularx}",
                "Outer & 90,000 " + BS * 2,
                BS + "end{tabularx}",
                "After the table.",
            ]
        )
        text = latex.to_text(_document(outer))
        assert "40,688" not in text
        assert "90,000" not in text
        assert "Outer" not in text
        assert "After the table." in text


class TestAnExecutedEnvironmentStillReportsItsIncludes:
    """Dropping the *text* is not the same as claiming the file was not read.

    TeX draws a table, so an ``\\input`` inside one really does pull a file in.
    ``tests/test_literal_environment_includes.py`` pins that for the names that
    were already dropped; these are the new ones.
    """

    @pytest.mark.parametrize("environment", TABLE_ENVIRONMENTS)
    def test_the_include_is_still_named(self, environment: str) -> None:
        body = NL.join(
            [
                BS + "begin{" + environment + "}{lX}",
                BS + "input{chapters/real} & " + BS * 2,
                BS + "end{" + environment + "}",
            ]
        )
        assert latex.included_files(_document(body)) == ["chapters/real"]


class TestMathIsLeftAlone:
    """A displayed formula keeps its numbers; a table row does not.

    The two look alike in a source file - both are ``&``-and-``\\\\`` grids - but
    a reader sees the numbers in a formula as part of the formula, and does not
    see the numbers in a table row as a statement the author is making.  This
    is a decision, not an oversight, so it is written down as tests: both the
    formula environments and the grid environments that live inside math mode.
    """

    @pytest.mark.parametrize(
        "environment",
        [
            "equation",
            "equation*",
            "align",
            "align*",
            "gather",
            "gather*",
            "array",
            "matrix",
            "pmatrix",
            "bmatrix",
        ],
    )
    def test_a_formula_keeps_its_number(self, environment: str) -> None:
        body = NL.join(
            [
                BS + "begin{" + environment + "}{cc}",
                "x = 40,688 & y " + BS * 2,
                BS + "end{" + environment + "}",
            ]
        )
        assert "40,688" in latex.to_text(_document(body))
