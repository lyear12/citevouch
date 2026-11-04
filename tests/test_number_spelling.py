"""A page prints `40 688`; the author types `40,688`; that is one number.

Measured before the fix, on a one-claim project whose only page reads
`We collected 40<SEP>688 examples in total.` and whose quote reads
`We collected 40,688 examples in total.`:

===================  =========================================================
SEP                  `citevouch check`
===================  =========================================================
",", ".", U+00A0      exit 0, `quote-found`
" " (ascii space)     exit 1, `number-absent-in-quote`: "the quote says 40,688
                      but page 1 of the source does not contain that number"
U+2009 U+2007 U+202F   exit 1, `quote-fuzzy` at similarity 1.00 and
U+200A                `number-absent-in-quote`
===================  =========================================================

Every one of those pages prints the number.  The first three rows were one
verdict, the last two were an accusation about a figure the reader can see,
and all five were the same sentence.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from citevouch.textnorm import CANON_PATTERN, canonical_number, numbers_in

SEPARATORS = {
    "comma": ",",
    "dot": ".",
    "space": " ",
    "nbsp": "\u00a0",
    "thin": "\u2009",
    "figure": "\u2007",
    "narrow-nbsp": "\u202f",
    "hair": "\u200a",
    "arabic": "\u066c",
}

SENTENCE = "We collected 40{sep}688 examples in total."


def _project(tmp: Path, page_sep: str, quote_sep: str) -> Path:
    (tmp / "page.txt").write_text(SENTENCE.format(sep=page_sep), encoding="utf-8", newline="\n")
    (tmp / "sources.toml").write_text(
        '[sources]\npaper = "page.txt"\n', encoding="utf-8", newline="\n"
    )
    (tmp / "manuscript.md").write_text(
        f"```claim id=c1 source=paper page=1\nquote: {SENTENCE.format(sep=quote_sep)}\n```\n",
        encoding="utf-8",
        newline="\n",
    )
    return tmp


def _check(root: Path):
    from citevouch.cli import main

    return main(["check", str(root / "manuscript.md"), "--root", str(root)])


class TestThePatternReadsAGroupingSpace:
    """`CANON_PATTERN` is what the comparison uses; the report pattern is not."""

    @pytest.mark.parametrize("name", sorted(SEPARATORS))
    def test_every_separator_is_one_number(self, name: str) -> None:
        token = f"40{SEPARATORS[name]}688"
        assert [m.group(0) for m in CANON_PATTERN.finditer(token)] == [token]
        assert canonical_number(token) == "40688"

    @pytest.mark.parametrize("text", ["2019 2020 2021", "pages 219 220"])
    def test_a_year_never_starts_a_group(self, text: str) -> None:
        """Four digits on the left cannot open a thousands group.

        ``pages 219 220`` is the harder half of the same rule: two three-digit
        runs with no separator between them, which a page range prints that
        way after extraction.  ``219`` is a legal left run and ``220`` a legal
        right one, so this *is* read as one number - the test pins that
        deliberately, because the alternative (a rule that refuses every three
        by three) would refuse ``40 688`` too, and the page really does print
        that as forty thousand.
        """
        found = [m.group(0) for m in CANON_PATTERN.finditer(text)]
        if text.startswith("2019"):
            assert found == ["2019", "2020", "2021"]
        else:
            assert found == ["219 220"]

    def test_the_report_pattern_is_untouched(self) -> None:
        """The ledger still records what it always recorded.

        A bare space is not a thousands separator for the report pattern; that
        rule is what keeps ``2019 2020 2021`` three years, and changing it would
        change every ledger already on disk.
        """
        assert numbers_in("2019 2020 2021") == ("2019", "2020", "2021")
        assert numbers_in("40 688") == ("40", "688")
        assert numbers_in("40,688") == ("40,688",)


class TestAVerifiedClaimAcrossSpellings:
    """Every pair of spellings for the same number is the same verdict."""

    @pytest.mark.parametrize("page", sorted(SEPARATORS))
    @pytest.mark.parametrize("quote", ["comma", "space", "thin"])
    def test_the_page_and_the_quote_may_spell_it_differently(
        self, tmp_path: Path, page: str, quote: str
    ) -> None:
        root = _project(tmp_path, SEPARATORS[page], SEPARATORS[quote])
        assert _check(root) == 0, f"page {page!r} / quote {quote!r}"

    @pytest.mark.parametrize("sep", sorted(SEPARATORS))
    def test_the_same_spelling_is_still_one_verdict(self, tmp_path: Path, sep: str) -> None:
        root = _project(tmp_path, SEPARATORS[sep], SEPARATORS[sep])
        assert _check(root) == 0

    def test_a_different_number_is_still_caught(self, tmp_path: Path) -> None:
        """The fix must not make the check blind to a real wrong figure."""
        (tmp_path / "page.txt").write_text(
            "We collected 40 688 examples in total.", encoding="utf-8", newline="\n"
        )
        (tmp_path / "sources.toml").write_text(
            '[sources]\npaper = "page.txt"\n', encoding="utf-8", newline="\n"
        )
        (tmp_path / "manuscript.md").write_text(
            "```claim id=c1 source=paper page=1\n"
            "quote: We collected 80,688 examples in total.\n"
            "```\n",
            encoding="utf-8",
            newline="\n",
        )
        assert _check(tmp_path) == 1


class TestTheNumbersTierAlwaysExplainsItself:
    """A run that says "1 missing" must also say why.

    The numbers tier exists to report a figure the page does not print where
    the quote puts it.  It called itself missing and said nothing at all in one
    measured case - a page printing ``40 688`` against a quote typing
    ``40,688`` - so the author read ``0 verified, 1 missing`` with no sentence
    anywhere explaining it, and could not tell a broken tool from a broken
    quote.  The fix moved that case out of the tier entirely (it is now
    ``canonical``), which means the invariant to pin is the tier's own: if a
    match lands in ``numbers``, one of the two number checks has something to
    say about it.
    """

    @pytest.mark.parametrize(
        ("page", "quote"),
        [
            ("It totals 41 000 items in all.", "it totals 40,688 items in all."),
            ("It totals 41,000 items in all.", "it totals 40,688 items in all."),
            ("We coded 1 000 sentences.", "we coded 2,000 sentences."),
            ("The count is 41\u00a0000 exactly.", "the count is 40,688 exactly."),
        ],
    )
    def test_a_numbers_match_has_a_finding(self, page: str, quote: str) -> None:
        from citevouch.matching import find_in_pages
        from citevouch.sources import PageText
        from citevouch.verify import _number_checks, _number_where_checks

        class _Claim:
            id = "c1"
            path = "manuscript.md"
            line = 1
            numbers = tuple(m.group(0) for m in CANON_PATTERN.finditer(quote))

        pages = [PageText(number=1, text=page)]
        match = find_in_pages(quote, pages)
        assert match.tier == "numbers", match.reason
        said = _number_checks(_Claim(), pages, match.page)
        if not said:
            said = _number_where_checks(_Claim(), match)
        assert said, f"tier numbers said nothing about {quote!r}"
