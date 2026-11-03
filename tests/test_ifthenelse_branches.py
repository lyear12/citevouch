"""The two branches of ``\\ifthenelse`` are two pieces of prose, not one word.

Measured before the fix, with ``B = chr(92)``:

    to_text("A. " + B + "ifthenelse{1=2}{Alpha words}{Beta words} B.")
    -> 'A. Alpha wordsBeta words B.'

    to_text("Prior " + B + "ifthenelse{1=2}{We report either five results}"
            "{We report these results} in this paper.")
    -> 'Prior We report either five resultsWe report these results in this paper.'

``resultsWe`` is a token that is in neither branch, and the second sentence is
the one ``draft`` offers the author to paste into a claim block.  Each branch is
a whole piece of prose and at most one of them is ever typeset, so a space is
the honest separator: it is what a reader would see if either branch were taken,
and it is what keeps two citations two citations.
"""

from citevouch import draft
from citevouch.latex import to_text

B = chr(92)
NL = chr(10)


class TestTheBranchesAreSeparate:
    def test_two_prose_branches_do_not_form_one_word(self) -> None:
        text = f"A. {B}ifthenelse{{1=2}}{{Alpha words}}{{Beta words}} B."
        assert to_text(text) == "A. Alpha words Beta words B." + NL

    def test_the_words_of_the_first_branch_are_not_glued_to_the_second(self) -> None:
        text = f"A. {B}ifthenelse{{1=2}}{{We report five}}{{We report these}} results."
        converted = to_text(text)
        assert "fiveWe" not in converted
        assert converted == "A. We report five We report these results." + NL

    def test_two_citations_stay_two_citations(self) -> None:
        text = f"A. {B}ifthenelse{{1=2}}{{{B}citep{{no}}}}{{{B}citep{{yes}}}} B."
        assert to_text(text) == "A. [@no] [@yes] B." + NL

    def test_the_space_is_one_space_whatever_the_whitespace_between(self) -> None:
        tight = f"A. {B}ifthenelse{{1=2}}{{Alpha}}{{Beta}} B."
        spaced = f"A. {B}ifthenelse {{1=2}} {{Alpha}} {{Beta}} B."
        assert to_text(tight) == to_text(spaced)


class TestWhatMustNotChange:
    def test_one_branch_gains_no_trailing_space(self) -> None:
        text = f"A. {B}ifthenelse{{1=2}}{{{B}citep{{only}}}} B."
        assert to_text(text) == "A. [@only] B." + NL

    def test_an_ordinary_command_is_untouched(self) -> None:
        text = f"A. {B}emph{{kept words}} B."
        assert to_text(text) == "A. kept words B." + NL

    def test_the_test_is_still_not_in_the_sentence(self) -> None:
        text = f"A. {B}ifthenelse{{1=2}}{{Alpha}}{{Beta}} B."
        assert "1=2" not in to_text(text)


class TestTheSentenceTheAuthorIsShown:
    def test_the_statement_has_no_glued_token(self) -> None:
        # `draft` reads the converted text, so this runs the converter first:
        # handing raw LaTeX to `statement_of` would only show that it does not
        # speak LaTeX, which is not the claim under test.
        sentence = to_text(
            "Prior work "
            + B
            + "ifthenelse{1=2}{We report either five results}"
            + "{We report these results} in this paper."
        )
        statement = draft.statement_of(sentence.strip())
        assert "fiveWe" not in statement
        assert "resultsWe" not in statement
        assert (
            statement
            == "Prior work We report either five results We report these results in this paper."
        )
