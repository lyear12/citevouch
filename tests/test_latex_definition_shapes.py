r"""A definition written in the body used to give its template to the paper.

``B`` is a backslash.  Every case below was measured on the tree before the fix,
and none of the spellings was in any table, so all of them fell through to the
unknown-command branch: that branch drops the command's name and keeps every
argument, which is right for a command whose arguments are prose and wrong for a
definition, whose arguments are a template.

The failures came in three groups, all of them the same bug.

**1. A template became a sentence, and ``draft`` invented a citation.**
``B + "NewDocumentEnvironment{aside}{m}{The corpus for the study of grammar has
" + B + "citep{phantom2020}.}{}"`` converted to ``asidemThe corpus for the study
of grammar has [@phantom2020].`` -- the environment's name and its argument
specification, glued to the front of the first ``\begin{aside}`` body.  Because
the template holds a citation, ``draft`` proposed a claim block citing
``phantom2020`` and quoting a page it had found by keyword overlap: the tool
invented evidence and invited the author to paste it.

**2. A settings command offered its settings as a word.**
``B + "setmainfont{Times New Roman}"`` left ``Times New Roman`` in the prose.  A
preamble is dropped whole, so this only bites a document that writes the setting
in the body -- but a font name glued into a sentence is exactly the kind of token
``draft`` matches against a page.

**3. ``included_files`` read the template as a file list.**
It reads the raw source, so ``B + "NewDocumentEnvironment{box}{m}{" + B +
"input{ghost/sec}}{}"`` reported ``ghost/sec`` as a file the paper pulls in: a
warning about a document that does not exist, in the one place the tool tells the
author to look.
"""

import pytest

from citevouch import draft
from citevouch.latex import included_files, to_text

B = chr(92)
NL = chr(10)
TAIL = "The grammar is large."

#: xparse environment definitions: name, specification, begin text, end text.
XPARSE_ENVIRONMENTS = [
    "NewDocumentEnvironment",
    "RenewDocumentEnvironment",
    "ProvideDocumentEnvironment",
    "DeclareDocumentEnvironment",
]

#: The xparse command spellings that must expand inside an ``\edef``.
EXPANDABLE_COMMANDS = [
    "NewExpandableDocumentCommand",
    "DeclareExpandableDocumentCommand",
]

#: etoolbox's environment forms, with their optional count and default.
ETOOLBOX_ENVIRONMENTS = ["newenvironmentx", "renewenvironmentx"]

#: etoolbox's two-group environment form.
ETOOLBOX_ENVIRONMENTS_SHORT = ["NewEnviron", "RenewEnviron"]

#: tcolorbox: the short command form and the environment form.
TCOLORBOX_COMMANDS = ["newtcolorbox", "NewTColorBox"]
TCOLORBOX_ENVIRONMENTS = ["NewTCBEnvironment", "NewTCBEnv"]

#: A definition whose arguments are all settings.
SETTINGS = [
    ("sisetup", "{detect-all}"),
    ("geometry", "{margin=2cm}"),
    ("lstset", "{language=Python}"),
    ("tikzset", "{mystyle/.style={draw}}"),
    ("pgfplotsset", "{compat=1.18}"),
    ("setmainfont", "{Times New Roman}"),
    ("setsansfont", "{Arial}"),
    ("setmonofont", "{Consolas}"),
    ("setCJKfamilyfont", "{song}{SimSun}"),
    ("definecolor", "{myblue}{RGB}{1,2,3}"),
    ("colorlet", "{myblue}{blue!20}"),
    ("addbibresource", "{refs.bib}"),
    ("numberwithin", "{equation}{section}"),
    ("allowdisplaybreaks", "[4]"),
    ("setlist", "{enumerate}{label=(" + B + "arabic*)}"),
    ("crefname", "{figure}{figure}{figures}"),
    ("Crefname", "{figure}{Figure}{Figures}"),
    ("floatname", "{algorithm}{Algorithm}"),
    ("newfloat", "{algorithm}{htbp}{loa}{Algorithm}"),
    ("DeclareFontFamily", "{T1}{cmr}{}"),
]


def _converted(name, arguments):
    return to_text("A. " + B + name + arguments + " " + TAIL)


class TestTheTemplateIsNotProse:
    @pytest.mark.parametrize("name", XPARSE_ENVIRONMENTS)
    def test_an_xparse_environment_definition_is_cut_out(self, name):
        arguments = "{box}{m}{See " + B + "citep{phantom}.}{}"
        assert _converted(name, arguments) == "A. " + TAIL + NL

    @pytest.mark.parametrize("name", EXPANDABLE_COMMANDS)
    def test_an_expandable_command_definition_is_cut_out(self, name):
        arguments = "{" + B + "x}{m}{See " + B + "citep{phantom}.}"
        assert _converted(name, arguments) == "A. " + TAIL + NL

    @pytest.mark.parametrize("name", ETOOLBOX_ENVIRONMENTS)
    def test_an_etoolbox_environment_definition_is_cut_out(self, name):
        arguments = "{box}[2][1]{See " + B + "citep{phantom}.}{}"
        assert _converted(name, arguments) == "A. " + TAIL + NL

    @pytest.mark.parametrize("name", ETOOLBOX_ENVIRONMENTS_SHORT)
    def test_the_short_etoolbox_environment_is_cut_out(self, name):
        arguments = "{box}{See " + B + "citep{phantom}.}"
        assert _converted(name, arguments) == "A. " + TAIL + NL

    @pytest.mark.parametrize("name", TCOLORBOX_COMMANDS)
    def test_a_tcolorbox_definition_is_cut_out(self, name):
        arguments = "{mybox}[1]{colback=white,title=#1}"
        assert _converted(name, arguments) == "A. " + TAIL + NL

    @pytest.mark.parametrize("name", TCOLORBOX_ENVIRONMENTS)
    def test_a_tcolorbox_environment_is_cut_out(self, name):
        arguments = "{b}{See " + B + "citep{phantom}.}"
        assert _converted(name, arguments) == "A. " + TAIL + NL

    def test_a_column_type_is_cut_out(self):
        arguments = "{L}[1]{>{" + B + "raggedright}p{#1}}"
        assert _converted("newcolumntype", arguments) == "A. " + TAIL + NL

    def test_a_caption_format_is_cut_out(self):
        assert _converted("DeclareCaptionFormat", "{m}{#1#2#3}") == "A. " + TAIL + NL

    def test_a_theorem_style_is_cut_out(self):
        arguments = "{m}{}{}{}{}{}{}{}{}"
        assert _converted("newtheoremstyle", arguments) == "A. " + TAIL + NL


class TestASettingsCommandIsNotProse:
    @pytest.mark.parametrize("name,arguments", SETTINGS)
    def test_the_settings_do_not_reach_the_text(self, name, arguments):
        assert _converted(name, arguments) == "A. " + TAIL + NL


class TestTheFileListDoesNotHoldATemplate:
    @pytest.mark.parametrize(
        "name,arguments",
        [
            ("NewDocumentEnvironment", "{box}{m}{" + B + "input{ghost/sec}}{}"),
            ("newenvironmentx", "{box}[2][1]{" + B + "input{ghost/sec}}{}"),
            ("NewEnviron", "{box}{" + B + "input{ghost/sec}}"),
            ("newtcolorbox", "{mybox}[1]{" + B + "input{ghost/sec}}"),
        ],
    )
    def test_a_template_include_is_not_a_file(self, name, arguments):
        assert included_files(B + name + arguments) == []

    def test_a_real_include_is_still_reported(self):
        tex = B + "NewEnviron{box}{body}" + B + "input{real/sec}"
        assert included_files(tex) == ["real/sec"]

    def test_a_real_include_before_a_template_is_still_reported(self):
        tex = (
            B
            + "input{first/sec}"
            + B
            + "NewDocumentEnvironment{box}{m}{"
            + B
            + "input{ghost/sec}}{}"
        )
        assert included_files(tex) == ["first/sec"]


class TestWhatStillWorks:
    """The shapes that were already in a table when the leak was measured."""

    @pytest.mark.parametrize(
        "name,arguments",
        [
            ("newcommand", "{" + B + "x}{y}"),
            ("renewcommand", "{" + B + "x}{y}"),
            ("providecommand", "{" + B + "x}{y}"),
            ("DeclareRobustCommand", "{" + B + "x}{y}"),
            ("newcommandx", "{" + B + "x}[1]{Body #1}"),
            ("newenvironment", "{e}{a}{b}"),
            ("renewenvironment", "{e}{a}{b}"),
            ("newtheorem", "{thm}{Theorem}[section]"),
            ("NewDocumentCommand", "{" + B + "x}{m}{Body #1}"),
            ("RenewDocumentCommand", "{" + B + "x}{m}{Body #1}"),
            ("def", B + "x#1{y}"),
            ("DeclareMathOperator", "{" + B + "argmax}{arg max}"),
            ("captionsetup", "{format=plain}"),
            ("hypersetup", "{colorlinks=true}"),
            ("usetikzlibrary", "{arrows}"),
            ("zihao", "{5}"),
        ],
    )
    def test_the_definition_is_cut_out(self, name, arguments):
        assert _converted(name, arguments) == "A. " + TAIL + NL

    def test_a_star_is_still_spent(self):
        assert _converted("newcommand", "*{" + B + "x}{y}") == "A. " + TAIL + NL

    def test_a_definition_this_reader_cannot_follow_keeps_the_prose(self):
        assert to_text("A. " + B + "newcommand " + TAIL) == "A. " + TAIL + NL

    def test_the_body_of_a_command_that_is_not_a_definition_survives(self):
        assert to_text("A. " + B + "textbf{real words}.") == "A. real words." + NL


class TestDraftDoesNotInventACitation:
    def test_the_template_citation_is_not_a_citation(self, tmp_path):
        tex = (
            B
            + "begin{document}"
            + NL
            + B
            + "NewDocumentEnvironment{aside}{m}{The corpus for the study of grammar has "
            + B
            + "citep{phantom2020}.}{}"
            + NL
            + "The corpus for the study of grammar is large."
            + NL
            + B
            + "end{document}"
            + NL
        )
        text = to_text(tex)
        assert "phantom2020" not in text
        assert draft.citation_sites(text) == []

    def test_the_sentence_the_author_wrote_survives_extraction(self):
        tex = (
            B
            + "NewEnviron{aside}{We collected 154,391 examples.}"
            + "We collected 154,391 examples."
            + NL
        )
        assert to_text(tex) == "We collected 154,391 examples." + NL

    def test_a_setting_that_takes_one_group_leaves_the_next_one_alone(self):
        # The count in the table is a number, and both directions are wrong:
        # one fewer leaves the setting in the prose, one more eats the sentence
        # that follows.  This is the second direction.
        assert _converted("geometry", "{margin=2cm}{real words}") == (
            "A. real words " + TAIL + NL
        )

    def test_a_setting_name_this_table_does_not_know_keeps_its_argument(self):
        # The drop table is consulted by name.  A misspelt name is not dropped,
        # which is the right answer: the argument then shows up in the prose
        # where the author can see it, instead of disappearing silently.
        assert _converted("geometryX", "{margin=2cm}") == ("A. margin=2cm " + TAIL + NL)

    def test_a_theorem_declaration_spends_its_settings_group(self):
        # `\\declaretheorem[name=Theorem]{thm}`: the settings come before the
        # name, so a reader that starts at the name finds a bracket and gives
        # up, leaving the settings in the prose.
        assert _converted("declaretheorem", "[name=Theorem]{thm}") == ("A. " + TAIL + NL)
