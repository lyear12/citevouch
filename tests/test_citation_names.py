"""The citation commands this tool claims to read, read in both readers.

Measured on the tree before the fix, one command at a time:

    \\Citet{knuth1984}        citation_sites -> []      to_text -> 'knuth1984'
    \\citep[p.~3] {knuth}     citation_sites -> []      to_text -> '[p. 3] knuth'
    \\citeyearpar{knuth}      latex.to_text -> '[@knuth]'  draft.citation_sites -> []

The first two are invisible in *both* readers.  The third is worse: `to_text`
knows the name and `draft` did not, so a manuscript was rewritten into a
`[@knuth]` marker and then reported by `draft` as citing nothing - with the
marker sitting in the very text `draft` was reading.  `"Prior work \\citep{a}
and \\citeyearpar{b} agrees."` gave `sites=['a']` and a proposal text of
`'Prior work and \\citeyearpar{b} agrees.'`: one source silently dropped and
raw LaTeX handed to the author as the sentence to paste.

Three things are pinned here, because three different things went wrong:

* every name on the table reaches a site, in both readers;
* a space or a tab before the brace is legal TeX and counts, a newline does
  not (that one is a decision - see `_GAP` - and it is asserted so that
  "fixing" it has to be deliberate);
* there is one name table, not two that can drift.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from citevouch import draft, latex
from citevouch.cli import main

BS = chr(92)
NL = chr(10)

#: Every singular name, spelled once here on purpose.  If a future edit adds a
#: name to `latex.CITATION_NAMES`, the tables test below fails; if it removes
#: one, this list fails.  A third list that is *not* derived would be the same
#: mistake this round fixed - but a list of what is meant to work is not.
CAPITALISED = [
    # natbib spells the capital form by capitalising `cite`.
    "Citet",
    "Citep",
    "Citealp",
    "Citealt",
    "Citeauthor",
    "Citeyear",
    "Citeyearpar",
    # biblatex spells it by capitalising the whole command, and both
    # families have to be here: an author writes the capital one when the
    # citation opens a sentence, which is the citation a reader sees first.
    # Measured before these were listed, `\Autocite{paper}` converted to
    # the bare word `paper`, and `draft` reported that a manuscript citing
    # on its first sentence cited nothing.
    "Autocite",
    "Parencite",
    "Textcite",
    "Footcite",
    "Smartcite",
    "Supercite",
    "Fullcite",
]
LOWERCASE = [
    "cite",
    "citep",
    "citet",
    "citealp",
    "citealt",
    "citeauthor",
    "citeyear",
    "citeyearpar",
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
    # The same capitalisation, one letter later: a plural citation can open
    # a sentence too.
    "Autocites",
    "Parencites",
    "Textcites",
    "Footcites",
    "Smartcites",
    "Supercites",
    "Fullcites",
]


def site_keys(text: str) -> list[str]:
    """The keys `draft` finds in `text`."""
    return [site.key for site in draft.citation_sites(text)]


class TestBothReadersKnowEveryName:
    @pytest.mark.parametrize("name", LOWERCASE + CAPITALISED)
    def test_the_command_reaches_a_site_in_draft(self, name: str) -> None:
        assert site_keys(f"{BS}{name}{{knuth1984}}") == ["knuth1984"]

    @pytest.mark.parametrize("name", LOWERCASE + CAPITALISED)
    def test_the_command_reaches_a_marker_in_latex(self, name: str) -> None:
        assert latex.to_text(f"{BS}{name}{{knuth1984}}") == "[@knuth1984]" + NL

    @pytest.mark.parametrize("name", PLURAL)
    def test_a_plural_command_reaches_every_site(self, name: str) -> None:
        text = f"{BS}{name}{{a}}{{b}}"
        assert site_keys(text) == ["a", "b"]
        assert latex.to_text(text) == "[@a; @b]" + NL


class TestTheSpaceTeXAllows:
    @pytest.mark.parametrize("gap", [" ", "  ", "	"])
    def test_space_or_tab_before_the_brace_still_counts(self, gap: str) -> None:
        text = f"{BS}citep[p.~3]{gap}{{knuth1984}}"
        assert site_keys(text) == ["knuth1984"]
        assert latex.to_text(text) == "[@knuth1984]" + NL

    def test_a_newline_before_the_brace_does_not_count(self) -> None:
        """The exclusion is a decision, not an oversight.

        A newline between a command and its mandatory argument is where a
        *missing* brace finds the next paragraph's brace group.  Reading one
        paragraph's text as another paragraph's citation is the silent wrong
        answer `latex.py` exists to avoid, so the gap stops at a newline - and
        this test is here so that changing it is a deliberate act.
        """
        text = f"{BS}citep[p.~3]{NL}{{knuth1984}}"
        assert site_keys(text) == []
        assert "[@knuth1984]" not in latex.to_text(text)

    @pytest.mark.parametrize("gap", [" ", "  ", "	"])
    def test_a_gap_after_a_plural_command_still_counts(self, gap: str) -> None:
        """The plural pattern has its own gap, in front of the first bracket.

        `\\cites [p.~4]{a}[p.~5]{b}` is legal TeX - the first optional
        argument may be separated from the name - and the plural pattern reads
        it as no citation at all if that gap is dropped.  This test exists
        because the mutation that removes exactly that gap survived every
        other test in the file.
        """
        text = f"{BS}cites{gap}[p.~4]{{a}}[p.~5]{{b}}"
        assert site_keys(text) == ["a", "b"]
        assert latex.to_text(text) == "[@a; @b]" + NL

    def test_the_two_readers_agree_about_every_gap(self) -> None:
        """Same input, same answer - that is the property, not the wording."""
        for gap in ["", " ", "  ", "	", NL]:
            text = f"{BS}citep[p.~3]{gap}{{knuth1984}}"
            draft_says = site_keys(text) != []
            latex_says = "[@knuth1984]" in latex.to_text(text)
            assert draft_says == latex_says, gap


class TestACommandThatIsNotOnTheTable:
    @pytest.mark.parametrize("name", ["mycites", "citepar", "citesx", "citey"])
    def test_a_longer_name_is_not_read_as_a_prefix(self, name: str) -> None:
        assert site_keys(f"{BS}{name}{{a}}{{b}}") == []
        assert site_keys(f"{BS}{name}{{a}}") == []


class TestOneTable:
    def test_the_tables_latex_exports_are_what_draft_uses(self) -> None:
        assert set(latex.CITATION_NAMES) == set(LOWERCASE + CAPITALISED)
        assert set(latex.MULTI_CITATION_NAMES) == set(PLURAL)

    def test_draft_builds_its_patterns_from_those_tables(self) -> None:
        """The copy in `draft.py` is what fell behind, so it must be built.

        Asserting `"Citet" in draft._LATEX.pattern` would pass for a
        hand-written list too, so this asks the pattern about a name that was
        *missing* from the old copy and checks the plural table as well, and
        then reads the source to see that the names are imported rather than
        typed again.
        """
        assert "Citeyearpar" in draft._LATEX.pattern
        assert "fullcites" in draft._LATEX_MULTI.pattern
        text = (Path(draft.__file__)).read_text(encoding="utf-8")
        assert "from .latex import" in text
        assert "CITATION_NAMES" in text
        assert "MULTI_CITATION_NAMES" in text


PAPER = (
    "Construction grammar treats a grammar as a network of constructions, and that"
    " network is learned from usage rather than written down by hand."
)


def _project(tmp_path: Path, sentence: str) -> Path:
    """A one-paper project whose manuscript ends in `sentence`."""
    root = tmp_path / "project"
    (root / "papers").mkdir(parents=True)
    (root / "papers" / "smith2026paper.txt").write_text(PAPER, encoding="utf-8", newline=NL)
    (root / "manuscript.md").write_text(
        "Construction grammar treats a grammar as a network of "
        + "constructions "
        + sentence
        + NL,
        encoding="utf-8",
        newline=NL,
    )
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'smith2026paper = "papers/smith2026paper.txt"' + NL,
        encoding="utf-8",
        newline=NL,
    )
    return root


class TestTheCommandOnARealManuscript:
    """One capitalised citation is the whole paper as far as `draft` is concerned.

    Measured before the fix, `draft` on a manuscript citing with `\\Citet` printed
    `0 claim block(s) proposed: no citations were found to propose them for`
    about a paper that cites on its first sentence.
    """

    def test_it_proposes_a_block_for_a_capitalised_citation(self, tmp_path: Path) -> None:
        root = _project(tmp_path, f"{BS}Citet{{smith2026paper}}.")
        assert (
            main(
                [
                    "draft",
                    str(root / "manuscript.md"),
                    "--root",
                    str(root),
                    "-o",
                    "proposals.md",
                ]
            )
            == 0
        )
        proposed = (root / "proposals.md").read_text(encoding="utf-8")
        assert "```claim" in proposed
        # The sentence the author is invited to paste has no LaTeX in it.
        assert BS + "Citet" not in proposed

    def test_a_space_before_the_brace_also_proposes_a_block(self, tmp_path: Path) -> None:
        root = _project(tmp_path, f"{BS}citep[p.~3] {{smith2026paper}}.")
        assert (
            main(
                [
                    "draft",
                    str(root / "manuscript.md"),
                    "--root",
                    str(root),
                    "-o",
                    "proposals.md",
                ]
            )
            == 0
        )
        assert "```claim" in (root / "proposals.md").read_text(encoding="utf-8")


class TestACitationThatOpensASentence:
    r"""The capital letter exists because the citation comes first.

    ``\autocite{paper} showed the effect.`` and
    ``\Autocite{paper} showed the effect.`` are the same citation with the same
    key; only the author's decision about where the sentence starts differs.
    Measured on the tree before the capitalised biblatex names were listed,
    the second converted to `'paper showed the effect.'` - the key pasted
    into the prose as a word - and `draft` reported that a manuscript citing
    on its first sentence cited nothing at all.  The capitalised natbib
    names had been in the table for a while, so the half that was missing
    was exactly the half whose commands nobody writes mid-sentence.
    """

    @pytest.mark.parametrize(
        "name",
        ["Autocite", "Parencite", "Textcite", "Footcite", "Smartcite", "Supercite", "Fullcite"],
    )
    def test_the_key_does_not_become_a_word(self, name: str) -> None:
        text = f"{BS}{name}{{knuth1984}} showed the effect grows."
        assert site_keys(text) == ["knuth1984"]
        assert latex.to_text(text) == "[@knuth1984] showed the effect grows." + NL

    @pytest.mark.parametrize(
        "name",
        [
            "Autocites",
            "Parencites",
            "Textcites",
            "Footcites",
            "Smartcites",
            "Supercites",
            "Fullcites",
        ],
    )
    def test_a_capitalised_plural_reaches_every_source(self, name: str) -> None:
        text = f"{BS}{name}{{a}}{{b}} showed two effects."
        assert site_keys(text) == ["a", "b"]
        assert latex.to_text(text) == "[@a; @b] showed two effects." + NL

    def test_a_sentence_initial_citation_proposes_a_block(self, tmp_path: Path) -> None:
        root = _project(tmp_path, f"{BS}Autocite{{smith2026paper}}.")
        assert (
            main(
                [
                    "draft",
                    str(root / "manuscript.md"),
                    "--root",
                    str(root),
                    "-o",
                    "proposals.md",
                ]
            )
            == 0
        )
        proposed = (root / "proposals.md").read_text(encoding="utf-8")
        assert "```claim" in proposed
        # The sentence the author is invited to paste has no LaTeX and no
        # bare key in it.
        assert BS + "Autocite" not in proposed
        assert "smith2026paper." not in proposed

    def test_the_capital_and_lowercase_forms_agree(self) -> None:
        """Same command, same answer.  That is the property, not the wording."""
        for lower, capital in [
            ("autocite", "Autocite"),
            ("parencite", "Parencite"),
            ("textcite", "Textcite"),
            ("footcite", "Footcite"),
            ("smartcite", "Smartcite"),
            ("supercite", "Supercite"),
            ("fullcite", "Fullcite"),
        ]:
            l_text = f"{BS}{lower}{{k}} showed it."
            c_text = f"{BS}{capital}{{k}} showed it."
            assert site_keys(l_text) == site_keys(c_text) == ["k"], capital
            assert latex.to_text(l_text) == latex.to_text(c_text), capital


class TestTheSentenceTheAuthorIsShown:
    def test_a_mixed_citation_sentence_loses_both_markers(self) -> None:
        text = f"Prior work {BS}citep{{a}} and {BS}citeyearpar{{b}} agrees."
        assert site_keys(text) == ["a", "b"]
        assert draft.statement_of(text) == "Prior work and agrees."

    def test_a_capitalised_citation_leaves_no_latex_behind(self) -> None:
        text = f"{BS}Citet{{knuth}} showed the effect grows."
        assert draft.statement_of(text) == "showed the effect grows."
