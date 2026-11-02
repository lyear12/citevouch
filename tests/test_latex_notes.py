"""A note is a sentence of its own, not words inside the sentence it hangs on.

Measured before this fix, with the note left inline::

    The method works\\footnote{See \\citep{fn} for the proof.}, and we show it.
      -> 'The method worksSee [@fn] for the proof., and we show it.'

`worksSee` is in no paper, and `draft` proposed that string as the claim's
text, so the proposal rested on a sentence nobody wrote.  The first attempt at
a fix gave the note its own paragraph *in place*, which broke the main sentence
at the comma after the note::

    -> 'The method works\\n\\nSee [@fn] for the proof.\\n\\n, and we show it.'

So the body moves to the end of the converted text: the main sentence survives
whole, the note keeps its words, and a citation inside a note still counts.
"""

from __future__ import annotations

import pytest

from citevouch.draft import _sentences_of, citation_sites
from citevouch.latex import to_text

B = chr(92)

NOTES = {
    "footnote": f"{B}footnote",
    "footnotetext": f"{B}footnotetext",
    "marginpar": f"{B}marginpar",
}


@pytest.mark.parametrize("label", sorted(NOTES))
class TestTheSentenceAroundTheNoteSurvivesWhole:
    def test_no_two_words_are_glued_together(self, label: str) -> None:
        text = f"The method works{NOTES[label]}{{A note.}}, and we show it."
        assert "worksA" not in to_text(text)

    def test_the_sentence_is_the_same_as_the_one_without_the_note(self, label: str) -> None:
        with_note = to_text(f"The method works{NOTES[label]}{{A note.}}, and we show it.")
        without = to_text("The method works, and we show it.")
        assert with_note.startswith(without.strip())

    def test_the_broken_sentence_is_not_left_behind_either(self, label: str) -> None:
        # The in-place version emitted the note as its own paragraph and left
        # the comma to start a new one.
        converted = to_text(f"The method works{NOTES[label]}{{A note.}}, and we show it.")
        assert "\n\n," not in converted


class TestTheNoteKeepsItsWords:
    def test_the_body_is_in_the_converted_text(self) -> None:
        assert "A note." in to_text(f"Text{B}footnote{{A note.}} follows.")

    def test_it_is_separated_from_the_prose_by_a_blank_line(self) -> None:
        converted = to_text(f"The results{B}footnote{{See the appendix.}} are clear.")
        assert "The results are clear." in converted
        assert "\n\nSee the appendix." in converted

    def test_two_notes_stay_two_notes(self) -> None:
        converted = to_text(f"First{B}footnote{{one}} second{B}footnote{{two}} third.")
        assert "First second third." in converted
        assert "\n\none\n" in converted
        assert "\n\ntwo\n" in converted


class TestACitationInsideANoteStillCounts:
    def test_the_site_is_reported(self) -> None:
        text = f"The method works{B}footnote{{See {B}citep{{fn}} for the proof.}} and we."
        assert [site.key for site in citation_sites(to_text(text))] == ["fn"]

    def test_the_note_is_its_own_sentence_for_the_reader(self) -> None:
        text = f"The method works{B}footnote{{See {B}citep{{fn}} for the proof.}}, and we."
        sentences = _sentences_of(to_text(text))
        assert "The method works, and we." in sentences
        assert any("See [@fn] for the proof." in sentence for sentence in sentences)


class TestTheBranchingCasesKeepTheNote:
    def test_a_note_inside_a_live_conditional(self) -> None:
        assert "inner" in to_text(f"A. {B}iftrue {B}footnote{{inner}} {B}fi B.")

    def test_a_note_inside_a_dead_conditional_does_not(self) -> None:
        assert "dead" not in to_text(f"A. {B}iffalse {B}footnote{{dead}} {B}fi B.")

    def test_a_note_inside_an_unclosed_conditional(self) -> None:
        # The unclosed branches take a different call site from the closed ones,
        # and a call site that forgets the list drops the note entirely: the
        # body is removed from the prose and never reaches the note block.
        assert "inner" in to_text(f"A. {B}iftrue {B}footnote{{inner}}")

    def test_a_note_inside_an_else_branch(self) -> None:
        text = f"A. {B}iffalse {B}citep{{dead}} {B}else {B}footnote{{from-else}} {B}fi B."
        assert "from-else" in to_text(text)

    def test_a_note_inside_a_dead_branch_does_not_leak(self) -> None:
        text = f"A. {B}iffalse {B}footnote{{dead-note}} {B}fi B."
        assert "dead-note" not in to_text(text)

    def test_a_note_inside_a_heading(self) -> None:
        assert "tn" in to_text(f"{B}section{{Title{B}footnote{{tn}}}}Body.")

    def test_a_note_nested_in_a_note(self) -> None:
        converted = to_text(f"A{B}footnote{{outer {B}footnote{{inner}} tail}} B.")
        assert "inner" in converted
        assert "outer" in converted


class TestTheNoteIsConvertedWhileItMoves:
    def test_a_citation_inside_a_note_becomes_a_marker(self) -> None:
        # The body is moved, and moving it must not skip the conversion: an
        # unconverted body leaves `\citep{fn}` in the text, which reads as prose
        # and counts as no citation at all.
        converted = to_text(f"Text{B}footnote{{See {B}citep{{fn}} here.}} more.")
        assert f"{B}citep" not in converted
        assert "[@fn]" in converted

    def test_markup_inside_a_note_is_converted_too(self) -> None:
        converted = to_text(f"Text{B}footnote{{{B}textbf{{bold}} note.}} more.")
        assert "bold note." in converted
        assert f"{B}textbf" not in converted


class TestTheOrdinaryCasesAreUntouched:
    def test_an_inline_style_command_still_joins_the_words(self) -> None:
        assert to_text(f"The {B}textbf{{bold}} word.") == "The bold word.\n"

    def test_a_caption_is_still_part_of_its_figure_block(self) -> None:
        converted = to_text(f"{B}begin{{figure}}{B}caption{{The result.}}{B}end{{figure}}Body.")
        assert "The result." in converted
        assert "Body." in converted

    def test_a_document_with_no_notes_ends_with_one_newline(self) -> None:
        assert to_text("Plain sentence here.") == "Plain sentence here.\n"
