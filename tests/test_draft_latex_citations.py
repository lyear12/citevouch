"""`citation_sites` reads the same citation commands the converter does.

`draft`'s Markdown reader also understands LaTeX quotations, because a draft
often arrives half-converted.  Its pattern listed the natbib names and stopped:
biblatex's `\\parencite`, `\\textcite`, `\\autocite`, `\\footcite`,
`\\smartcite`, `\\supercite` and `\\fullcite` produced no site at all, so a
manuscript citing with biblatex was reported as citing nothing - `draft` said
"0 citation(s) found" about a paper full of them.  The plural commands were
missing from both patterns, and for those the converter's fix reads the first
group only unless the pattern says otherwise.

Measured against `citation_sites` on the raw text, before this change:

    \\cite{a}       sites=['a']      \\parencite{a}   sites=[]
    \\textcite{a}   sites=[]         \\autocite{a}    sites=[]
    \\fullcite{a}   sites=[]         \\cites{a}{b}    sites=[]
    \\textcites{a}{b}  sites=[]

and after: `\\cite`/`\\citep`/`\\parencite`/`\\textcite`/`\\autocite`/
`\\footcite`/`\\smartcite`/`\\supercite`/`\\fullcite` each give `['a']`, and
`\\cites`/`\\parencites`/`\\textcites` give `['a', 'b']`.
"""

from __future__ import annotations

import pytest

from citevouch.draft import citation_sites

BS = chr(92)
SENTENCE = " We show the method."

SINGULAR = [
    "cite",
    "citep",
    "citet",
    "citealp",
    "citealt",
    "citeauthor",
    "citeyear",
    "nocite",
    "parencite",
    "textcite",
    "autocite",
    "footcite",
    "smartcite",
    "supercite",
    "fullcite",
]

PLURAL = [
    "cites",
    "citeps",
    "citets",
    "citealps",
    "citealts",
    "parencites",
    "textcites",
    "autocites",
    "footcites",
    "smartcites",
    "supercites",
    "fullcites",
]


class TestTheBiblatexNames:
    @pytest.mark.parametrize("name", SINGULAR)
    def test_one_group_is_one_citation(self, name: str) -> None:
        sites = citation_sites(BS + name + "{key}" + SENTENCE)
        assert [site.key for site in sites] == ["key"]

    @pytest.mark.parametrize("name", PLURAL)
    def test_two_groups_are_two_citations(self, name: str) -> None:
        sites = citation_sites(BS + name + "{one}{two}" + SENTENCE)
        assert [site.key for site in sites] == ["one", "two"]


class TestTheShapesThePatternsShare:
    def test_an_optional_argument_is_not_a_key(self) -> None:
        sites = citation_sites(BS + "parencite[see][p.~3]{key}" + SENTENCE)
        assert [site.key for site in sites] == ["key"]

    def test_each_group_of_a_plural_command_has_its_own_arguments(self) -> None:
        sites = citation_sites(BS + "cites[see]{one}[p.~4]{two}" + SENTENCE)
        assert [site.key for site in sites] == ["one", "two"]

    def test_an_optional_argument_may_hold_braces(self) -> None:
        # A pattern that looks for `{...}` without skipping the `[...]` before
        # it reads `{\em x}` as a key group and reports `\em x` as a citation.
        sites = citation_sites(BS + "cites[see {\\em x}]{one}{two}" + SENTENCE)
        assert [site.key for site in sites] == ["one", "two"]

    def test_a_comma_separated_group_is_several_keys(self) -> None:
        sites = citation_sites(BS + "citep{one,two}" + SENTENCE)
        assert [site.key for site in sites] == ["one", "two"]

    def test_a_multi_key_group_inside_a_plural_command(self) -> None:
        sites = citation_sites(BS + "cites{one,two}{three}" + SENTENCE)
        assert [site.key for site in sites] == ["one", "two", "three"]

    def test_the_span_covers_the_whole_command(self) -> None:
        text = BS + "textcites{one}{two}" + SENTENCE
        site = citation_sites(text)[0]
        assert text[site.start : site.end] == text[: -len(SENTENCE)]


class TestWhatIsNotACitation:
    def test_a_plural_command_with_no_keys_is_nothing(self) -> None:
        assert citation_sites(BS + "cites" + SENTENCE) == []

    def test_a_singular_command_with_no_keys_is_nothing(self) -> None:
        assert citation_sites(BS + "parencite" + SENTENCE) == []

    def test_a_command_name_that_only_ends_in_cites(self) -> None:
        assert citation_sites(BS + "mycites{a}{b}" + SENTENCE) == []
