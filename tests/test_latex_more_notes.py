"""More names than three behave like ``\\footnote``, and the rest of the page proves it.

``\\footnote``, ``\\footnotetext`` and ``\\marginpar`` were moved out of the
sentence they hang on in an earlier round, because keeping them inline produced
words no paper contains::

    The method works\\footnote{See \\citep{fn} for the proof.}, and we show it.
      -> 'The method worksSee [@fn] for the proof., and we show it.'

The list was three names long.  Measured on the tree this test was written
against, every one of the commands below still glued its body into the sentence,
and every one of them is a note a reader is meant to read somewhere else::

    The method works\\thanks{We thank the annotators.}, and we show it.
      -> 'The method worksWe thank the annotators., and we show it.'
    The method works\\tnotetext{See the appendix.}, and we show it.
      -> 'The method worksSee the appendix., and we show it.'
    ... the same for \\marginnote, \\sidenote, \\endnote and \\authornote.

``worksWe`` is in no paper.  `draft` reads sentences out of the converted text,
so the sentence it offers the author is that string, and the claim built on it
is a claim about a sentence nobody wrote - the failure the earlier round exists
to prevent, one name-list short.
"""

from __future__ import annotations

import pytest

from citevouch.draft import citation_sites
from citevouch.latex import to_text

B = chr(92)

#: Note commands from the LaTeX kernel and the packages that add their own.
#:
#: Every one is a note the reader reads somewhere other than the sentence the
#: note hangs on, which is the whole reason ``\\footnote`` is handled.
NOTES = {
    "thanks": f"{B}thanks",
    "tnotetext": f"{B}tnotetext",
    "marginnote": f"{B}marginnote",
    "sidenote": f"{B}sidenote",
    "sidenotetext": f"{B}sidenotetext",
    "endnote": f"{B}endnote",
    "footnote": f"{B}footnote",
    "marginpar": f"{B}marginpar",
}

#: Commands that wrap words which *are* the sentence, and must stay inline.
INLINE = {
    "textbf": f"{B}textbf",
    "emph": f"{B}emph",
    "textsc": f"{B}textsc",
}


@pytest.mark.parametrize("label", sorted(NOTES))
class TestTheSentenceAroundTheNoteIsTheSentenceWithoutIt:
    def test_the_note_does_not_glue_to_the_word_before_it(self, label: str) -> None:
        converted = to_text(f"The method works{NOTES[label]}{{A note.}}, and we show it.")
        assert "worksA" not in converted

    def test_the_sentence_is_whole(self, label: str) -> None:
        converted = to_text(f"The method works{NOTES[label]}{{A note.}}, and we show it.")
        assert "The method works, and we show it." in converted

    def test_the_note_keeps_its_words(self, label: str) -> None:
        converted = to_text(f"The method works{NOTES[label]}{{A note.}}, and we show it.")
        assert "A note." in converted

    def test_it_is_not_left_in_place_to_break_the_sentence(self, label: str) -> None:
        converted = to_text(f"The method works{NOTES[label]}{{A note.}}, and we show it.")
        assert "\n\n," not in converted


class TestTheStarrySpelling:
    def test_a_starred_thanks_is_the_same_note(self) -> None:
        converted = to_text(f"The method works{B}thanks*{{A note.}}, and we show it.")
        assert "The method works, and we show it." in converted
        assert "A note." in converted
        assert "*A note" not in converted


class TestACitationInsideTheseNotesStillCounts:
    @pytest.mark.parametrize("label", sorted(NOTES))
    def test_the_site_is_reported(self, label: str) -> None:
        text = f"The method works{NOTES[label]}{{See {B}citep{{fn}} for the proof.}} and we."
        assert [site.key for site in citation_sites(to_text(text))] == ["fn"]


@pytest.mark.parametrize("label", sorted(INLINE))
class TestWhatWrapsTheWordsOfTheSentenceStaysInline:
    def test_it_is_still_one_sentence(self, label: str) -> None:
        converted = to_text(f"The method {INLINE[label]}{{works}} well.")
        assert "The method works well." in converted
        assert "\n\n" not in converted


class TestThePageIsWhatDraftReads:
    def test_no_word_of_a_note_reaches_the_middle_of_a_sentence(self) -> None:
        text = (
            "We trained on 40,688 examples"
            + B
            + "tnotetext{The split is described in Appendix A.}"
            + " and evaluated on 9,800 rolesets."
        )
        converted = to_text(text)
        assert "40,688 examples and evaluated on 9,800 rolesets." in converted
        assert "examplesThe split" not in converted
