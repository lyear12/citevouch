"""A definition command with a star, and the xparse commands with three groups.

Two defects, both in ``latex._definition_end``, both measured before the fix.
``B`` is a backslash.

**1. A starred spelling swallowed the rest of the document.** ``B +
"newcommand*{B + "x}{y}`` puts a ``*`` where the code expected a brace, so
``_group_end`` answered -1 and the function returned ``len(text)``.  Measured:
``"A. " + B + "newcommand*{B + "x}{y} The grammar is large."`` converted to
``'A.'`` -- 32 characters gone, and no finding said so.  Six spellings take the
star this way: ``newcommand``, ``renewcommand``, ``providecommand``,
``DeclareRobustCommand``, ``newenvironment``, ``renewenvironment``.

**2. The xparse document commands take three groups, not two.** Name, argument
specification, body.  The generic path consumed two, so the *body* stayed in the
prose.  Measured: ``B + "NewDocumentCommand{B + "seecite}{m}{see B +
"citep{#1}}`` contributed the words ``see [@#1]`` to the text, and
``draft.citation_sites`` reported a citation to the key ``#1`` -- a source the
paper never cites, offered to the author to paste into a claim block.
"""

import pytest

from citevouch import draft, latex
from citevouch.latex import to_text

B = chr(92)
NL = chr(10)
TAIL = "The grammar is large."

#: The six definition commands that accept a star.
STARRED = [
    ("newcommand", "{" + B + "x}{y}"),
    ("renewcommand", "{" + B + "x}{y}"),
    ("providecommand", "{" + B + "x}{y}"),
    ("DeclareRobustCommand", "{" + B + "x}{y}"),
    ("newenvironment", "{e}{a}{b}"),
    ("renewenvironment", "{e}{a}{b}"),
]

#: The four xparse commands: name, argument specification, body.
DOCUMENT_COMMANDS = [
    "DeclareDocumentCommand",
    "NewDocumentCommand",
    "RenewDocumentCommand",
    "ProvideDocumentCommand",
]


class TestAStarDoesNotSwallowTheDocument:
    @pytest.mark.parametrize("name,arguments", STARRED)
    def test_the_text_after_the_definition_survives(self, name, arguments):
        converted = to_text("A. " + B + name + "*" + arguments + " " + TAIL)
        assert converted == "A. " + TAIL + NL

    @pytest.mark.parametrize("name,arguments", STARRED)
    def test_the_plain_spelling_still_works(self, name, arguments):
        converted = to_text("A. " + B + name + arguments + " " + TAIL)
        assert converted == "A. " + TAIL + NL

    def test_a_space_between_the_star_and_the_brace_is_allowed(self):
        converted = to_text("A. " + B + "newcommand* {" + B + "x}{y} " + TAIL)
        assert converted == "A. " + TAIL + NL

    def test_a_starred_definition_in_the_middle_keeps_both_sides(self):
        converted = to_text(
            "We collected 40,688 examples. "
            + B
            + "newcommand*{"
            + B
            + "seecite}[1]{see "
            + B
            + "citep{#1}} The grammar is large."
        )
        assert converted == "We collected 40,688 examples. The grammar is large." + NL


class TestTheXparseBodyIsNotProse:
    @pytest.mark.parametrize("name", DOCUMENT_COMMANDS)
    @pytest.mark.parametrize("star", ["", "*"])
    def test_the_body_is_cut_out(self, name, star):
        converted = to_text("A. " + B + name + star + "{" + B + "x}{m}{Body #1} " + TAIL)
        assert converted == "A. " + TAIL + NL

    @pytest.mark.parametrize("name", DOCUMENT_COMMANDS)
    def test_the_body_makes_no_citation(self, name):
        """`draft` offered `#1` as a source key the paper never cites."""
        text = (
            "We report the numbers. "
            + B
            + name
            + "{"
            + B
            + "seecite}{m}{see "
            + B
            + "citep{#1}} Prior work."
        )
        assert "[@#1]" not in to_text(text)
        assert "#1" not in [site.key for site in draft.citation_sites(to_text(text))]

    def test_a_body_that_names_a_file_is_not_an_include(self):
        text = B + "NewDocumentCommand{" + B + "x}{m}{" + B + "input{#1}}"
        assert latex.included_files(text) == []


class TestWhatMustNotChange:
    def test_a_definition_still_leaves_no_brace_behind(self):
        converted = to_text("A. " + B + "newcommand{" + B + "x}{body} " + TAIL)
        assert converted == "A. " + TAIL + NL
        assert "body" not in converted

    def test_the_etoolbox_spelling_takes_two_groups(self):
        """`\\newcommandx{\\x}[1]{Body #1}`: count then body, no specification."""
        converted = to_text("A. " + B + "newcommandx{" + B + "x}[1]{Body #1} " + TAIL)
        assert converted == "A. " + TAIL + NL

    def test_a_low_level_definition_still_works(self):
        converted = to_text("A. " + B + "def" + B + "q#1{#1} " + TAIL)
        assert converted == "A. " + TAIL + NL

    def test_a_theorem_declaration_still_works(self):
        converted = to_text("A. " + B + "newtheorem{thm}{Theorem} " + TAIL)
        assert converted == "A. " + TAIL + NL

    def test_an_ordinary_command_beside_the_definition_still_reads(self):
        converted = to_text("A. " + B + "newcommand*{" + B + "x}{y} " + B + "emph{kept words}.")
        assert converted == "A. kept words." + NL


class TestTheTwoSpellingsAreToldApart:
    """`\\newcommandx` takes a count and a body; xparse takes a spec too."""

    def test_an_etoolbox_definition_leaves_the_next_group_alone(self):
        # If `newcommandx` were read as xparse, the second loop would
        # consume `{Other words}` as the macro body and the words would
        # vanish from the page.
        converted = to_text(
            "A. " + B + "newcommandx{" + B + "x}[1]{Body #1}{Other words} " + TAIL
        )
        assert "Other words" in converted
        assert converted == "A. Other words " + TAIL + NL

    def test_an_xparse_definition_does_leave_its_body_alone(self):
        # The same input shape, one loop later: xparse's third group is
        # the body, so a group after it belongs to the page.
        converted = to_text(
            "A. " + B + "NewDocumentCommand{" + B + "x}{m}{Body #1}{Other words} " + TAIL
        )
        assert converted == "A. Other words " + TAIL + NL


class TestAnUnreadableDefinitionKeepsThePage:
    """A definition cut short is not a definition of the rest of the file."""

    def test_a_name_with_no_braces_keeps_what_follows(self):
        converted = to_text("A. " + B + "newcommand " + TAIL)
        assert TAIL in converted

    def test_a_theorem_with_no_group_keeps_what_follows(self):
        converted = to_text("A. " + B + "newtheorem " + TAIL)
        assert TAIL in converted

    def test_a_low_level_definition_with_no_brace_keeps_what_follows(self):
        converted = to_text("A. " + B + "def " + TAIL)
        assert TAIL in converted

    def test_a_definition_that_ends_the_file_is_not_an_error(self):
        converted = to_text("A. " + B + "newcommand")
        assert converted == "A." + NL
