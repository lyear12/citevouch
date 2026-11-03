"""Two brackets that are not citations, seen by both readers.

`citation_sites` and `statement_of` read the same text through the same
pattern, and a pattern that is too loose fails differently in each: the first
invents a key, the second silently deletes the prose.  These were the two
mutations that survived the first round of reverse verification, because the
recogniser had boundary guards while the stripper was never asked about a
bracket holding no citation at all.

Measured on the loose versions:

    statement_of("Write to me at [contact me at x@y.com] today.")
      body guard removed      -> 'Write to me at  today.'   the address is gone
      whole bracket stripped  -> 'Write to me at  today.'   so is '[see note]'

Deleting words from a sentence the tool hands back as the author's own is worse
than inventing a key: nobody can see that it happened.
"""

from __future__ import annotations

import pytest

from citevouch.draft import citation_sites, statement_of

#: Brackets that hold an `@` or a word but cite nothing.
NOT_CITATIONS = [
    "Write to me at [contact me at x@y.com] today.",
    "The note [see the appendix] explains this.",
    "See reference [3] and appendix [B].",
    "A list [one; two; three] of things.",
    "An empty pair [] in the middle.",
    "Nested [[double]] brackets here.",
]


class TestTheSentenceKeepsItsWords:
    @pytest.mark.parametrize("sentence", NOT_CITATIONS)
    def test_nothing_is_deleted_from_a_sentence_without_a_citation(self, sentence: str) -> None:
        assert statement_of(sentence) == sentence

    @pytest.mark.parametrize("sentence", NOT_CITATIONS)
    def test_no_key_is_invented(self, sentence: str) -> None:
        assert citation_sites(sentence) == []


class TestACitationBesideThemStillWorks:
    def test_the_citation_goes_and_the_rest_stays(self) -> None:
        # The double space the cut leaves behind is collapsed, which is why
        # the expected value has one.
        assert statement_of("The note [see @a, p. 3] explains [3] this.") == (
            "The note explains [3] this."
        )

    def test_the_address_is_not_a_key_and_the_citation_is(self) -> None:
        found = citation_sites("Mail x@y.com about [@a, p. 3] today.")
        assert [site.key for site in found] == ["a"]


class TestTheOnlyBracketRemovedIsTheCitation:
    def test_a_numbered_reference_is_not_a_citation_marker(self) -> None:
        # `[3]` is how a numeric style writes a citation, and this tool does
        # not read that style - but `draft` must not delete it either.  The
        # sentence it returns is text the author will paste.
        assert statement_of("As shown in [3] and [@a] we agree.") == (
            "As shown in [3] and we agree."
        )
