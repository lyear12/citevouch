"""Which sentence does a citation marker belong to?

`draft` proposes a quote for the sentence that cites it.  A marker typed after
the full stop - `usage. [@p]` - belongs to the sentence *before* it, and reading
it literally gave `draft` the next sentence instead: wrong claim, wrong source.
These tests pin the placement rule for every shape a real manuscript uses.
"""

import pytest

from citevouch.draft import citation_sites, sentence_at, statement_of

NL = "\n"


def claim_for(text: str, key: str = "p") -> str:
    """The claim text `draft` would attach to `key`'s marker."""
    for site in citation_sites(text):
        if site.key == key:
            sentence, _, _ = sentence_at(text, site.start)
            return statement_of(sentence)
    raise AssertionError(f"no citation site for {key!r} in {text!r}")


class TestTheMarkerBelongsToTheSentenceItFollows:
    def test_a_marker_before_the_full_stop(self):
        text = "Constructions are learned from usage [@p]. They generalize over time." + NL
        assert claim_for(text) == "Constructions are learned from usage."

    def test_a_marker_after_the_full_stop(self):
        text = "Constructions are learned from usage. [@p] They generalize over time." + NL
        assert claim_for(text) == "Constructions are learned from usage."

    def test_a_marker_last_in_the_manuscript(self):
        text = "Constructions are learned from usage. [@p]" + NL
        assert claim_for(text) == "Constructions are learned from usage."

    def test_a_marker_alone_in_its_own_paragraph(self):
        text = "Constructions are learned from usage." + NL + NL + "[@p]" + NL
        assert claim_for(text) == "Constructions are learned from usage."

    @pytest.mark.parametrize(
        "text",
        [
            "One claim [@a]. Then a second claim [@b]. Then a third one here." + NL,
            "One claim. [@a] Then a second claim. [@b] Then a third one here." + NL,
        ],
    )
    def test_two_markers_keep_their_own_sentences(self, text):
        assert claim_for(text, "a") == "One claim."
        assert claim_for(text, "b") == "Then a second claim."


class TestTheOrdinaryShapesAreUnchanged:
    def test_a_marker_inside_its_sentence(self):
        text = "A later sentence [@q] ends the paragraph here." + NL
        assert claim_for(text, "q") == "A later sentence ends the paragraph here."

    def test_a_marker_that_opens_the_document(self):
        text = "[@p] A claim that opens the document." + NL
        assert claim_for(text) == "A claim that opens the document."

    def test_the_latex_form(self):
        text = "The method extends the framework " + chr(92) + "citep{p}." + NL
        assert claim_for(text) == "The method extends the framework."


class TestTheWrongSentenceIsNotSilentlyProposed:
    def test_the_next_sentence_never_becomes_the_claim(self):
        # The failure this file exists for: a marker after the full stop used to
        # make `draft` propose a quote for "They generalize over time." - a
        # sentence the author never cited - and back it with the wrong source.
        text = "Constructions are learned from usage. [@p] They generalize over time." + NL
        assert claim_for(text) != "They generalize over time."
