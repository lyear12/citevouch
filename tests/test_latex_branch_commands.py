"""Every conditional command that keeps two branches: the test is metadata.

LaTeX2e and `etoolbox` (loaded by most thesis classes and by `biblatex`) let an
author write a *conditional* that chooses between two pieces of prose.  There
are 29 of them between the two packages, and before this table none was known
to the converter at all.  Measured, with ``B = chr(92)``:

    to_text("X " + B + "ifboolexpr{test}{Yes words}{No words} Y")
    -> 'X testYes wordsNo words Y'

    to_text("X " + B + "ifnumcomp{1}{=}{2}{Yes words}{No words} Y")
    -> 'X 1=2Yes wordsNo words Y'

    to_text("X " + B + "ifdef" + B + "foo{Yes words}{No words} Y")
    -> 'X Yes wordsNo words Y'

The test was pasted into the sentence, the two branches were glued into a word
that appears in neither, and `draft` would offer that sentence to the author to
paste into a claim block.  Every case below now reads
``'X Yes words No words Y'``.

The table is data (name -> number of test groups), so the test that matters
most is the one that walks it: a name added to the table without the right
count is wrong for every document that uses the command.
"""

import pytest

from citevouch import latex
from citevouch.latex import to_text

B = chr(92)
NL = chr(10)

#: ``name: (test groups, call as the author writes it)``.
CONDITIONALS = {
    "ifboolexpr": (1, B + "ifboolexpr{test}{Yes}{No}"),
    "ifboolexpe": (1, B + "ifboolexpe{test}{Yes}{No}"),
    "iftoggle": (1, B + "iftoggle{flag}{Yes}{No}"),
    "ifbool": (1, B + "ifbool{flag}{Yes}{No}"),
    "ifblank": (1, B + "ifblank{s}{Yes}{No}"),
    "ifstrempty": (1, B + "ifstrempty{s}{Yes}{No}"),
    "ifrmnum": (1, B + "ifrmnum{s}{Yes}{No}"),
    "ifnumodd": (1, B + "ifnumodd{1}{Yes}{No}"),
    "ifcsdef": (1, B + "ifcsdef{name}{Yes}{No}"),
    "ifcsundef": (1, B + "ifcsundef{name}{Yes}{No}"),
    "ifcsvoid": (1, B + "ifcsvoid{name}{Yes}{No}"),
    "ifcsempty": (1, B + "ifcsempty{name}{Yes}{No}"),
    "IfFileExists": (1, B + "IfFileExists{sec/intro}{Yes}{No}"),
    "InputIfFileExists": (1, B + "InputIfFileExists{sec/intro}{Yes}{No}"),
    "ifstrequal": (2, B + "ifstrequal{a}{b}{Yes}{No}"),
    "ifnumequal": (2, B + "ifnumequal{1}{2}{Yes}{No}"),
    "ifnumgreater": (2, B + "ifnumgreater{1}{2}{Yes}{No}"),
    "ifnumless": (2, B + "ifnumless{1}{2}{Yes}{No}"),
    "ifinlist": (2, B + "ifinlist{s}{l}{Yes}{No}"),
    "ifnumcomp": (3, B + "ifnumcomp{1}{=}{2}{Yes}{No}"),
    "ifdimcomp": (3, B + "ifdimcomp{1pt}{=}{2pt}{Yes}{No}"),
    "ifthenelse": (1, B + "ifthenelse{1=2}{Yes}{No}"),
}

#: The names whose test is a bare control sequence, not a group.
BARE_TEST = {
    "ifdef": B + "ifdef" + B + "foo{Yes}{No}",
    "ifundef": B + "ifundef" + B + "foo{Yes}{No}",
    "ifdefmacro": B + "ifdefmacro" + B + "foo{Yes}{No}",
    "ifdefparam": B + "ifdefparam" + B + "foo{Yes}{No}",
    "ifdefempty": B + "ifdefempty" + B + "foo{Yes}{No}",
    "ifdefvoid": B + "ifdefvoid" + B + "foo{Yes}{No}",
    "ifdefltxprotect": B + "ifdefltxprotect" + B + "foo{Yes}{No}",
    # `\ifdefstring\f{value}{yes}{no}`: the test is a bare control sequence
    # followed by one group, which is why the table's count for it is 1.
    "ifdefstring": B + "ifdefstring" + B + "f{s}{Yes}{No}",
}


class TestEveryNameInTheTable:
    @pytest.mark.parametrize("name", sorted(CONDITIONALS))
    def test_the_test_is_not_in_the_sentence(self, name: str) -> None:
        groups, call = CONDITIONALS[name]
        converted = to_text("X " + call + " Y")
        assert converted == "X Yes No Y" + NL, (name, groups, converted)

    @pytest.mark.parametrize("name", sorted(BARE_TEST))
    def test_a_bare_test_is_not_in_the_sentence(self, name: str) -> None:
        converted = to_text("X " + BARE_TEST[name] + " Y")
        assert converted == "X Yes No Y" + NL, (name, converted)

    def test_the_table_and_the_names_agree(self) -> None:
        """A name in one collection and not the other is a name nobody checked."""
        assert set(latex._BRANCH_COMMAND) == set(CONDITIONALS) | set(BARE_TEST)
        assert set(latex._BRANCH_BARE_TEST) == set(BARE_TEST)


class TestTheBranchesStayProse:
    def test_the_branches_are_separated(self) -> None:
        converted = to_text("X " + B + "ifboolexpr{test}{We report five}{We report these} Y")
        assert converted == "X We report five We report these Y" + NL

    def test_two_citation_branches_stay_two_citations(self) -> None:
        converted = to_text(
            "X " + B + "ifboolexpr{test}" + "{" + B + "citep{a}}{" + B + "citep{b}} Y"
        )
        assert converted == "X [@a] [@b] Y" + NL

    def test_a_nested_command_inside_a_branch_is_converted(self) -> None:
        converted = to_text(
            "X " + B + "iftoggle{flag}{" + B + "emph{Yes}}{" + B + "emph{No}} Y"
        )
        assert converted == "X Yes No Y" + NL

    def test_an_empty_branch_leaves_no_stray_space_at_the_edges(self) -> None:
        """`to_text` collapsed the space when only one branch is non-empty."""
        assert to_text("X " + B + "ifboolexpr{test}{}{No} Y") == "X No Y" + NL
        assert to_text("X " + B + "ifboolexpr{test}{Yes}{} Y") == "X Yes Y" + NL


class TestWhatMustNotChange:
    def test_a_command_that_is_not_a_conditional_is_untouched(self) -> None:
        assert to_text("X " + B + "textbf{kept} Y") == "X kept Y" + NL

    def test_the_plain_if_commands_still_keep_their_body(self) -> None:
        converted = to_text(B + "iftrue A " + B + "fi")
        assert converted.strip() == "A"

    def test_the_test_inside_a_dead_branch_is_still_dead(self) -> None:
        converted = to_text(B + "iffalse " + B + "ifboolexpr{t}{Yes}{No} " + B + "fi")
        assert "Yes" not in converted


class TestTheSentenceTheAuthorIsShown:
    def test_draft_proposes_the_words_that_are_printed(self) -> None:
        """Both branches are prose the author wrote, so both are kept.

        What must not survive is the test argument, and the two branches must
        not run together: `examplescontains` is a word in neither of them, and
        `draft` would hand it to the author inside a ``claim:`` block.
        """
        sentence = to_text(
            "The corpus " + B + "iftoggle{long}{contains 40,688 examples}"
            "{contains 5.} and that is all."
        ).strip()
        assert sentence == ("The corpus contains 40,688 examples contains 5. and that is all.")
        assert "long" not in sentence
        assert "examplescontains" not in sentence
