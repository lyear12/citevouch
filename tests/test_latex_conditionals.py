"""A conditional is not prose, and a dead branch is not text.

Three shapes were measured before this file existed:

* ``\\iffalse \\citep{hidden} \\input{ghost/sec} \\fi`` converted to
  ``[@hidden]`` and reported ``ghost/sec`` as a file the paper reads, so `draft`
  proposed a claim for a citation the author had turned off and the include list
  named a file nothing would ever open.
* ``\\iftrue \\citep{shown} \\fi`` pasted the marker's own name where the
  fallthrough could not drop it, because a command with a body keeps its body.
* ``\\ifthenelse{1=2}{\\citep{no}}{\\citep{yes}}`` left the test glued to the
  first branch, the same defect as the counter arguments fixed in 0.19.77.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest

from citevouch.cli import main
from citevouch.draft import citation_sites
from citevouch.latex import included_files, to_text

B = chr(92)

#: Bodies TeX never reads, described by the code that opens them.
DEAD = {
    "iffalse": f"{B}iffalse {B}citep{{hidden}} {B}fi",
    "if0": f"{B}if0 {B}citep{{hidden}} {B}fi",
    "nested two deep": (
        f"{B}iffalse {B}citep{{dead-one}} {B}iftrue {B}citep{{dead-two}} {B}fi {B}fi"
    ),
    "one of two blocks": (f"{B}iffalse {B}citep{{one}} {B}fi {B}iffalse {B}citep{{two}} {B}fi"),
}

#: Bodies that do run, and whose marker must not become a word.
#:
#: Every name here takes no operand before its body.  ``\ifnum``, ``\ifdim``,
#: ``\ifodd``, ``\ifx``, ``\ifcat`` and ``\ifcase`` are the other half of the
#: family and are *not* in this dictionary: their operands are TeX tokens
#: (``1>0``, ``\a\b``), and dropping the operands needs a token-level parser
#: rather than a command table.  `TestTheConditionalsThatTakeOperands` records
#: what they still do, so the limitation is written down rather than assumed
#: away.
LIVE = {
    "iftrue": f"{B}iftrue {B}citep{{shown}} {B}fi",
    "if1": f"{B}if1 {B}citep{{shown}} {B}fi",
    "ifdefined": f"{B}ifdefined{B}foo {B}citep{{shown}} {B}fi",
    "nested inside a live block": (f"{B}iftrue {B}iftrue {B}citep{{shown}} {B}fi {B}fi"),
}


@pytest.mark.parametrize("label", sorted(DEAD))
class TestDeadTextIsNotText:
    def test_the_citation_is_not_a_citation(self, label: str) -> None:
        converted = to_text(f"Before. {DEAD[label]} After.")
        assert [site.key for site in citation_sites(converted)] == []

    def test_the_sentence_around_it_survives(self, label: str) -> None:
        assert to_text(f"Before. {DEAD[label]} After.") == "Before. After.\n"

    def test_a_file_named_inside_is_not_a_file_the_paper_reads(self, label: str) -> None:
        text = f"Before. {B}iffalse {B}input{{ghost/sec}} {B}fi After."
        assert included_files(text) == []


@pytest.mark.parametrize("label", sorted(LIVE))
class TestALiveConditionalKeepsItsBody:
    def test_the_body_is_converted(self, label: str) -> None:
        assert "[@shown]" in to_text(f"Before. {LIVE[label]} After.")

    def test_the_marker_is_not_a_word(self, label: str) -> None:
        assert to_text(f"Before. {LIVE[label]} After.") == "Before. [@shown] After.\n"


class TestAnElseInsideADeadBlockIsLive:
    TEXT = f"A. {B}iffalse {B}citep{{dead}} {B}else {B}citep{{live}} {B}fi B."

    def test_the_body_after_else_is_converted(self) -> None:
        converted = to_text(self.TEXT)
        assert [site.key for site in citation_sites(converted)] == ["live"]

    def test_the_dead_half_still_contributes_nothing(self) -> None:
        assert "dead" not in to_text(self.TEXT)


class TestAnElseInsideALiveBlockIsAChoice:
    """The conversion cannot decide, so it keeps the branch it met first."""

    def test_the_first_branch_is_the_one_that_stays(self) -> None:
        text = f"A. {B}iftrue {B}citep{{first}} {B}else {B}citep{{second}} {B}fi B."
        converted = to_text(text)
        assert [site.key for site in citation_sites(converted)] == ["first"]


class TestTheBranchesOfIfThenElse:
    def test_the_test_is_not_pasted_into_the_sentence(self) -> None:
        text = f"A. {B}ifthenelse{{1=2}}{{{B}citep{{no}}}}{{{B}citep{{yes}}}} B."
        assert "1=2" not in to_text(text)

    def test_both_branches_are_text_the_author_wrote(self) -> None:
        text = f"A. {B}ifthenelse{{1=2}}{{{B}citep{{no}}}}{{{B}citep{{yes}}}} B."
        assert to_text(text) == "A. [@no][@yes] B.\n"

    def test_a_missing_second_branch_is_not_an_error(self) -> None:
        text = f"A. {B}ifthenelse{{1=2}}{{{B}citep{{only}}}} B."
        assert to_text(text) == "A. [@only] B.\n"


class TestTheConditionalsThatTakeOperands:
    """The other half of the family, kept as it was and written down here.

    These read operands before their body: ``\\ifnum1>0``, ``\\ifdim 1pt>2pt``,
    ``\\ifodd\\value{page}``, ``\\ifx\\a\\b``, ``\\ifcat\\a\\b``.  Dropping those
    operands needs a token-level scan rather than a command table, so the
    converter counts these names for nesting and otherwise leaves them alone -
    which means the operand is still pasted into the sentence.  That is a known
    limitation, not a claim that these commands are handled.
    """

    OPERAND: ClassVar[dict[str, str]] = {
        "ifnum": f"{B}ifnum1>0 {B}citep{{shown}} {B}fi",
        "ifdim": f"{B}ifdim1pt>2pt {B}citep{{shown}} {B}fi",
    }

    @pytest.mark.parametrize("label", sorted(OPERAND))
    def test_the_body_is_still_converted(self, label: str) -> None:
        # The half that matters for correctness of a quote: the live body is
        # read, so a citation inside a branch is not silently dropped.
        assert "[@shown]" in to_text(f"Before. {self.OPERAND[label]} After.")

    @pytest.mark.parametrize("label", sorted(OPERAND))
    def test_the_operand_is_still_a_word_and_that_is_the_limitation(self, label: str) -> None:
        converted = to_text(f"Before. {self.OPERAND[label]} After.")
        assert converted != "Before. [@shown] After.\n"

    def test_a_dead_operand_conditional_is_not_treated_as_dead(self) -> None:
        # `\ifnum` never appears in the act-on sets, so its body is never cut -
        # a citation inside is reported rather than invented, which is the
        # safer of the two wrong answers.
        assert "[@maybe]" in to_text(f"A. {B}ifnum1>0 {B}citep{{maybe}} {B}fi B.")


class TestTheUnclosedCase:
    def test_an_unclosed_if_false_takes_the_rest_of_the_file(self) -> None:
        # TeX does the same: an unterminated conditional swallows what follows
        # rather than reporting an error, so the converter must not invent text
        # the compiler never typesets.
        assert to_text(f"A. {B}iffalse {B}citep{{after}}") == "A.\n"

    def test_an_unclosed_live_conditional_still_converts_its_body(self) -> None:
        assert "[@kept]" in to_text(f"A. {B}iftrue {B}citep{{kept}}")


class TestTheTwoReadersAgreeAboutWhichTextIsReal:
    def test_a_dead_branch_names_no_files_and_contributes_no_citations(self) -> None:
        text = (
            f"{B}iffalse {B}input{{ghost/a}} {B}citep{{dead}} {B}fi "
            f"{B}input{{real/b}} {B}citep{{live}}"
        )
        converted = to_text(text)
        assert included_files(text) == ["real/b"]
        assert [site.key for site in citation_sites(converted)] == ["live"]

    def test_the_live_half_is_not_hidden_by_the_dead_one(self) -> None:
        text = f"{B}iffalse {B}input{{ghost}} {B}fi {B}input{{real}}"
        assert included_files(text) == ["real"]


MANUSCRIPT = (
    f"We report the count in the main text {B}citep{{page}}.\n"
    f"{B}iffalse\n"
    f"We reported a different count {B}citep{{ghost}}.\n"
    f"{B}fi\n"
)

PAGE = "We report the count in the main text.\n"

BIB = (
    "@article{page, title={T}, author={A}, journal={J}, year={2020}}\n"
    "@article{ghost, title={G}, author={B}, journal={J}, year={2021}}\n"
)


class TestTheDraftDoesNotInheritTheDeadCitation:
    def test_no_proposal_is_written_for_it(self, tmp_path: Path) -> None:
        project = tmp_path / "p"
        project.mkdir()
        (project / "m.md").write_text(MANUSCRIPT, encoding="utf-8", newline="\n")
        (project / "page.txt").write_text(PAGE, encoding="utf-8", newline="\n")
        (project / "sources.toml").write_text(
            '[sources]\npage = "page.txt"\n', encoding="utf-8", newline="\n"
        )
        (tmp_path / "refs.bib").write_text(BIB, encoding="utf-8", newline="\n")
        code = main(
            [
                "draft",
                str(project / "m.md"),
                "--root",
                str(project),
                "--bib",
                str(tmp_path / "refs.bib"),
                "-o",
                str(tmp_path / "out.md"),
                "--force",
            ]
        )
        assert code == 0
        written = (tmp_path / "out.md").read_text(encoding="utf-8")
        assert "source=page" in written
        assert "source=ghost" not in written
