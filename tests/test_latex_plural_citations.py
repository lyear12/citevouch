"""The plural citation commands take one brace group per source.

Every other citation command carries its keys in a single group, so `_CITE`
looks for a command name, optional `[...]` arguments, and one `{...}`.  The
plural forms end in `s`, which is neither `*` nor `[` nor `{`, so the pattern
stopped matching right after `cite` and the command fell through to the generic
rule for an unknown command: drop the name, keep the arguments.  The keys became
bare words in the prose and the citation was lost - a manuscript that cited
three sources in one parenthesis was reported as citing none of them.

Measured before the plural pattern existed:

    \\cites{a}{b}                -> 'ab'          sites=[]
    \\parencites{a}{b}           -> 'ab'          sites=[]
    \\textcites{a}{b}{c}         -> 'abc'         sites=[]
    \\cites[1][2]{a}[3][4]{b}    -> '[1][2]a...'  sites=[]
    \\citep{a}                   -> '[@a]'        sites=['a']

and after:

    \\cites{a}{b}                -> '[@a; @b]'    sites=['a', 'b']
    \\textcites{a}{b}{c}         -> '[@a; @b; @c]' sites=['a', 'b', 'c']

`fullcite` is singular and was missing from `_CITE` entirely: it produced `'a'`
and no site at all.
"""

from __future__ import annotations

import pytest

from citevouch.draft import citation_sites
from citevouch.latex import to_text

BS = chr(92)

#: Every plural command biblatex and natbib define, with the number of keys it
#: is given here.  One entry per name, so a name dropped from the pattern is a
#: failing test rather than a silently smaller table.
PLURAL = {
    "cites": 2,
    "citeps": 2,
    "citets": 2,
    "citealps": 2,
    "citealts": 2,
    "parencites": 2,
    "textcites": 2,
    "autocites": 2,
    "footcites": 2,
    "smartcites": 2,
    "supercites": 2,
    "fullcites": 2,
}

SENTENCE = "\u6211\u4eec\u5c55\u793a\u8be5\u65b9\u6cd5\u3002"


class TestEveryPluralCommandIsRead:
    @pytest.mark.parametrize("name", sorted(PLURAL))
    def test_the_keys_become_a_marker(self, name: str) -> None:
        count = PLURAL[name]
        groups = "".join("{" + chr(ord("a") + index) + "}" for index in range(count))
        text = to_text(BS + name + groups + SENTENCE)
        assert text == "[@a; @b]" + SENTENCE + "\n"

    @pytest.mark.parametrize("name", sorted(PLURAL))
    def test_the_keys_are_citations(self, name: str) -> None:
        groups = "".join("{" + chr(ord("a") + index) + "}" for index in range(PLURAL[name]))
        sites = citation_sites(to_text(BS + name + groups + SENTENCE))
        assert [site.key for site in sites] == ["a", "b"]


class TestTheArgumentsBetweenTheGroups:
    def test_each_group_keeps_its_own_optional_arguments(self) -> None:
        text = to_text(BS + "cites[see][p.~3]{a}[p.~4]{b}" + SENTENCE)
        assert text == "[@a; @b]" + SENTENCE + "\n"

    def test_an_optional_argument_may_hold_braces(self) -> None:
        # `[see {\\em x}]` is legal natbib: the bracket closes the optional
        # argument, not the first brace it meets.  A pattern that stops at `]`
        # or that reads the `{` inside the bracket as the key group gets `a`
        # right only by accident.
        text = to_text(BS + "cites[see {x}]{a}{b}" + SENTENCE)
        assert text == "[@a; @b]" + SENTENCE + "\n"

    def test_a_group_that_holds_several_keys_is_read_as_several(self) -> None:
        text = to_text(BS + "cites{a,b}{c}" + SENTENCE)
        assert text == "[@a; @b; @c]" + SENTENCE + "\n"

    def test_a_starred_plural_command_still_works(self) -> None:
        text = to_text(BS + "parencites*{a}{b}" + SENTENCE)
        assert text == "[@a; @b]" + SENTENCE + "\n"

    def test_three_groups(self) -> None:
        text = to_text(BS + "textcites{a}{b}{c}" + SENTENCE)
        assert text == "[@a; @b; @c]" + SENTENCE + "\n"

    def test_a_group_holding_several_comma_separated_keys(self) -> None:
        text = to_text(BS + "cites{a,b}{c}" + SENTENCE)
        assert text == "[@a; @b; @c]" + SENTENCE + "\n"


class TestEveryKeyReachesTheMarker:
    def test_two_sources_are_two_marks(self) -> None:
        text = to_text(BS + "cites{knuth1984}{lamport1994}" + SENTENCE)
        assert text == "[@knuth1984; @lamport1994]" + SENTENCE + "\n"

    def test_the_marker_is_the_whole_citation(self) -> None:
        # Dropping either key would still leave a well-formed marker, so the
        # count is what separates "both cited" from "one cited".
        text = to_text(BS + "textcites{a}{b}{c}" + SENTENCE)
        assert text.count("@") == 3


class TestTheSingularFormsAreUnchanged:
    @pytest.mark.parametrize(
        "name", ["cite", "citep", "citet", "citealp", "citealt", "citeauthor", "nocite"]
    )
    def test_one_group_is_still_one_marker(self, name: str) -> None:
        assert to_text(BS + name + "{a}" + SENTENCE) == "[@a]" + SENTENCE + "\n"

    def test_fullcite_is_singular_and_was_missing(self) -> None:
        assert to_text(BS + "fullcite{a}" + SENTENCE) == "[@a]" + SENTENCE + "\n"

    def test_a_comma_separated_key_list_still_works(self) -> None:
        assert to_text(BS + "citep{a,b}" + SENTENCE) == "[@a; @b]" + SENTENCE + "\n"

    def test_a_cite_that_is_not_a_command_name(self) -> None:
        text = to_text(BS + "mycites{a}{b}" + SENTENCE)
        assert "[@" not in text


class TestTheProseIsNotPolluted:
    def test_the_key_does_not_survive_as_a_word(self) -> None:
        # The key belongs inside the marker and nowhere else: `[@knuth1984]` is
        # the citation, a bare `knuth1984` in the prose is the failure.
        text = to_text(BS + "parencites{knuth1984}{lamport1994}" + SENTENCE)
        assert text == "[@knuth1984; @lamport1994]" + SENTENCE + "\n"
        assert text.count("knuth1984") == 1

    def test_an_empty_plural_command_says_nothing(self) -> None:
        assert to_text(BS + "cites" + SENTENCE) == SENTENCE + "\n"
