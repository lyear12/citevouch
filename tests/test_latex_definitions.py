"""A macro body is a template, not a sentence.

`\\newcommand{\\knuthcite}{\\citep{knuth}}` is a rule about how a later call is
written out.  It was handled as "drop one argument", so the body stayed in the
stream and was read as prose: a paper that never cites Knuth got a `[@knuth]`
in its text, and `\\newcommand{\\seecite}[1]{see \\citep{#1}}` recorded a
citation to the key `#1` while turning the real call `\\seecite{knuth}` into a
bare word - the tool invented one citation and lost another in the same step.
"""

from __future__ import annotations

import pytest

from citevouch.draft import citation_sites
from citevouch.latex import included_files, to_text

B = chr(92)

BODIES = {
    "newcommand": B + "newcommand{" + B + "knuthcite}{" + B + "citep{knuth}}",
    "renewcommand": B + "renewcommand{" + B + "knuthcite}{" + B + "citep{knuth}}",
    "providecommand": B + "providecommand{" + B + "knuthcite}{" + B + "citep{knuth}}",
    "DeclareRobustCommand": (
        B + "DeclareRobustCommand{" + B + "knuthcite}{" + B + "citep{knuth}}"
    ),
    "def": B + "def" + B + "knuthcite{" + B + "citep{knuth}}",
    "gdef": B + "gdef" + B + "knuthcite{" + B + "citep{knuth}}",
    "edef": B + "edef" + B + "knuthcite{" + B + "citep{knuth}}",
    "xdef": B + "xdef" + B + "knuthcite{" + B + "citep{knuth}}",
}


class TestTheBodyIsNotProse:
    @pytest.mark.parametrize("spelling", sorted(BODIES))
    def test_a_body_carrying_a_citation_does_not_join_the_text(self, spelling: str) -> None:
        text = to_text(BODIES[spelling] + " We show the method works here.")

        assert "@knuth" not in text
        assert text.strip() == "We show the method works here."

    @pytest.mark.parametrize("spelling", sorted(BODIES))
    def test_a_body_carrying_a_citation_is_not_read_as_one(self, spelling: str) -> None:
        assert citation_sites(to_text(BODIES[spelling])) == []

    def test_the_sentence_around_a_definition_survives(self) -> None:
        text = to_text(
            "Before the definition. " + BODIES["newcommand"] + " After the definition."
        )

        assert text.strip() == "Before the definition. After the definition."


class TestTheCallSiteIsLeftAlone:
    def test_a_macro_with_a_parameter_records_no_citation_to_the_hole(self) -> None:
        tex = (
            B
            + "newcommand{\\seecite}[1]{see "
            + B
            + "citep{#1} for details} We show the method works "
            + B
            + "seecite{knuth} here."
        )

        text = to_text(tex)

        assert "#1" not in text
        assert citation_sites(text) == []
        # The tool does not expand macros, so the argument stays as the word the
        # author typed.  That is a missing citation, not an invented one.
        assert "knuth" in text

    def test_a_two_argument_macro_keeps_its_optional_argument_out(self) -> None:
        tex = (
            B
            + "renewcommand{"
            + B
            + "pcite}[2][]{"
            + B
            + "citep[#1]{#2}} Then "
            + B
            + "pcite{x}{texbook} applies."
        )

        text = to_text(tex)

        assert "[2]" not in text
        assert "[@" not in text
        assert text.strip() == "Then xtexbook applies."


class TestEnvironmentsAndTheorems:
    def test_both_bodies_of_an_environment_definition_are_dropped(self) -> None:
        tex = (
            B
            + "newenvironment{myenv}[1]{"
            + B
            + "begin{quote}"
            + B
            + "citep{#1}}{"
            + B
            + "end{quote}} Then it applies."
        )

        text = to_text(tex)

        assert text.strip() == "Then it applies."
        assert citation_sites(text) == []

    def test_a_redefined_environment_does_not_keep_its_old_body(self) -> None:
        tex = (
            B + "renewenvironment{myenv}{" + B + "citep{a}}{" + B + "citep{b}} Then it applies."
        )

        text = to_text(tex)

        assert "@a" not in text
        assert "@b" not in text
        assert text.strip() == "Then it applies."

    def test_a_theorem_declaration_keeps_its_three_arguments_out(self) -> None:
        tex = B + "newtheorem{thm}{Theorem}[section] We show the method works here."

        text = to_text(tex)

        assert "thmTheorem" not in text
        assert "[section]" not in text
        assert text.strip() == "We show the method works here."


class TestTheFileNamesInsideABody:
    def test_a_body_does_not_name_a_file(self) -> None:
        assert included_files(B + "newcommand{" + B + "inc}{" + B + "input{sec/x}}") == []

    def test_a_parameter_hole_is_not_a_file_name(self) -> None:
        assert included_files(B + "newcommand{" + B + "inc}[1]{" + B + "input{#1}}") == []

    def test_a_real_include_beside_a_definition_is_still_reported(self) -> None:
        tex = B + "input{sec/real} " + B + "newcommand{" + B + "x}{" + B + "input{sec/ghost}}"

        assert included_files(tex) == ["sec/real"]

    def test_a_low_level_definition_does_not_hide_the_next_include(self) -> None:
        tex = B + "def" + B + "myinc#1{" + B + "input{#1}}" + chr(10) + B + "input{sec/two}"

        assert included_files(tex) == ["sec/two"]


class TestTheCommandThatReadsLatex:
    def test_draft_writes_no_proposal_for_a_key_only_the_body_names(self, tmp_path) -> None:
        from citevouch.cli import main

        project = tmp_path / "p"
        project.mkdir()
        (project / "page.txt").write_text(
            "We show the method works here.\n", encoding="utf-8", newline="\n"
        )
        (project / "refs.bib").write_text(
            "@article{knuth, title={Literate Programming}}\n",
            encoding="utf-8",
            newline="\n",
        )
        (project / "m.tex").write_text(
            chr(10).join(
                [
                    B + "begin{document}",
                    B + "newcommand{" + B + "knuthcite}{" + B + "citep{knuth}}",
                    "We show the method works here.",
                    B + "end{document}",
                    "",
                ]
            ),
            encoding="utf-8",
            newline="\n",
        )

        code = main(
            [
                "draft",
                str(project / "m.tex"),
                "--root",
                str(project),
                "--bib",
                str(project / "refs.bib"),
                "-o",
                "claims.md",
            ]
        )

        assert code == 0
        written = (project / "claims.md").read_text(encoding="utf-8")
        assert "source=knuth" not in written
        assert "knuth" not in written
