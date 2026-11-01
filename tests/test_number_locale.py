"""A number separated by dots is a number, whichever locale printed it.

An author reads a table that prints 40.688 and types 40,688 into the quote, or
the manuscript says 40,688 and the PDF extraction shows 40.688.  Both spellings
are the same value; before this file existed the tool called the number absent
and reported ``number-absent-in-quote`` at ``high`` - an accusation about a
number printed on the page in front of the reader.  That is the failure this
project treats as the worst it can produce, so the rule is pinned here rather
than left to the comment above ``_THOUSANDS``.
"""

from __future__ import annotations

import io
from contextlib import redirect_stdout

import pytest

from citevouch.cli import main
from citevouch.matching import _canonical_with_map, find_in_pages
from citevouch.sources import PageText
from citevouch.textnorm import REPORT_PATTERN, canonical_number, numbers_in


class TestOneValueWhateverTheSpelling:
    @pytest.mark.parametrize(
        "spelling",
        ["40.688", "40,688", "40 688", "40٬688"],
    )
    def test_a_thousands_separator_is_a_group(self, spelling: str) -> None:
        assert canonical_number(spelling) == "40688"

    def test_two_groups_are_one_number(self) -> None:
        assert canonical_number("1.234.567") == "1234567"

    def test_the_mixed_european_form(self) -> None:
        assert canonical_number("1.000,5") == "1000.5"

    def test_the_mixed_anglophone_form(self) -> None:
        assert canonical_number("1,000.5") == "1000.5"


class TestARealDecimalPointSurvives:
    @pytest.mark.parametrize("spelling", ["48.4", "2.5", "0.5", "0.688"])
    def test_one_digit_after_the_point_is_a_fraction(self, spelling: str) -> None:
        assert canonical_number(spelling) == spelling

    def test_four_decimals_do_not_become_a_group(self) -> None:
        """1.0005 is one and five ten-thousandths, not 1,000 and 5."""
        assert canonical_number("1.0005") == "1.0005"

    def test_a_leading_zero_is_never_a_group(self) -> None:
        assert canonical_number("0.688") == "0.688"


class TestThePatternReadsTheWholeNumber:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("we counted 40.688 entries", ("40.688",)),
            ("we counted 1.234.567 entries", ("1.234.567",)),
            ("it rose 48.4% this year", ("48.4%",)),
            ("in 2026 there were 3", ("2026", "3")),
            ("2019 2020 2021", ("2019", "2020", "2021")),
        ],
    )
    def test_a_dotted_group_does_not_split(self, text: str, expected: tuple[str, ...]) -> None:
        assert numbers_in(text) == expected

    def test_the_written_spelling_is_preserved(self) -> None:
        assert numbers_in("we counted 40.688") == ("40.688",)


class TestTheVerdictIsTheSameOnEitherSpelling:
    """The end-to-end shape: a page in one locale, a quote in the other."""

    @pytest.mark.parametrize(
        ("page", "quote"),
        [
            ("we counted 40.688 entries", "we counted 40,688 entries"),
            ("we counted 40,688 entries", "we counted 40.688 entries"),
            ("we counted 1.234.567 entries", "we counted 1,234,567 entries"),
            ("we counted 1.000,5 entries", "we counted 1,000.5 entries"),
        ],
    )
    def test_the_two_spellings_compare_equal(self, page: str, quote: str) -> None:
        page_numbers = [canonical_number(n) for n in numbers_in(page)]
        quote_numbers = [canonical_number(n) for n in numbers_in(quote)]
        assert quote_numbers == page_numbers


def _page(text: str) -> PageText:
    return PageText(number=1, text=text)


class TestTheMatcherReadsBothSpellings:
    """`canonical` is a verification tier, not a report tier.

    The words match at word boundaries and every number matches by value, so
    the only difference left is the character the locale prints between digit
    groups.  Nothing about that difference is a disagreement about the source.
    """

    @pytest.mark.parametrize(
        ("page", "quote"),
        [
            ("Overall we counted 40.688 entries.", "Overall we counted 40,688 entries."),
            ("Overall we counted 40,688 entries.", "Overall we counted 40.688 entries."),
            ("We coded 1.234.567 sentences.", "We coded 1,234,567 sentences."),
            ("It rose 1.000,5 percent.", "It rose 1,000.5 percent."),
        ],
    )
    def test_the_quote_is_found_when_only_the_separator_differs(
        self, page: str, quote: str
    ) -> None:
        match = find_in_pages(quote, [_page(page)], None)
        assert match.tier == "canonical", match.reason
        assert match.found is True

    def test_the_offset_map_points_back_at_the_number_as_printed(self) -> None:
        """The canonical string is shorter, so its offsets are not the page's.

        This is the property the excerpt depends on, stated where a shifted map
        fails: take a canonicalised number, ask the map where it came from, and
        the page must have the same value printed at that offset.  An identity
        map passes for the first number (nothing shifted yet) and fails for
        every number after it, which is exactly the bug worth catching.
        """
        text = "Table 1.234.567 lists 40.688 rows."
        canon, offsets = _canonical_with_map(text)
        assert canon == "Table 1234567 lists 40688 rows."
        assert len(canon) == len(offsets)

        for token in ("1234567", "40688"):
            at = canon.index(token)
            printed = REPORT_PATTERN.match(text, offsets[at])
            assert printed is not None, f"offset {offsets[at]} is not a number start"
            assert canonical_number(printed.group(0)) == token

    def test_a_quote_after_a_shorter_number_still_shows_itself(self) -> None:
        """Two numbers before the match, so the canonical text is 3 short."""
        page = "Table 1.000 rows. Figure 1.000 lists we counted 40.688 entries."
        match = find_in_pages("we counted 40,688 entries.", [_page(page)], None)
        assert match.tier == "canonical"
        assert "we counted 40.688 entries." in match.context

    def test_the_excerpt_shows_the_quote_as_printed_even_far_into_the_page(self) -> None:
        """Canonicalising shortens the page, so the map has to be asked, not guessed.

        Every ``1.000.000`` above the quote is two characters shorter in
        canonical text, and the words between them mean the map cannot be
        recovered from counting separators.  The quote is longer than the
        excerpt's sixty characters of right margin, so an index that was never
        mapped back cannot accidentally be rescued by the margin: the excerpt
        must end with the quote, in the page's own spelling.
        """
        padding = "As shown in the table below, " * 12
        for _ in range(40):
            padding = padding + "1.000.000 rows "
        page = padding + (
            "and we counted 40.688 entries in the corpus, which is more than "
            "the earlier study reported."
        )
        quote = (
            "and we counted 40,688 entries in the corpus, which is more than "
            "the earlier study reported."
        )
        match = find_in_pages(quote, [_page(page)], None)
        assert match.tier == "canonical"
        assert match.context.rstrip("…").endswith("the earlier study reported.")
        assert "40.688" in match.context
        # The excerpt is a window on the sentence, not a chunk of the page: it
        # reaches sixty characters to either side of the match.  An index that
        # was never mapped back stretches that window by the characters the
        # canonical rewrite saved, and no amount of end-anchoring notices.
        assert len(match.context) <= len(quote) + 130, (
            f"the window is {len(match.context)} characters for a "
            f"{len(quote)}-character quote, so the start index was not mapped back"
        )

    def test_a_genuinely_wrong_figure_is_still_a_numbers_tier(self) -> None:
        match = find_in_pages("we counted 40,699 entries", [_page("we counted 40,688 entries")])
        assert match.tier == "numbers"
        assert match.found is False

    def test_a_quote_with_no_number_never_reaches_this_tier(self) -> None:
        match = find_in_pages("we counted the entries", [_page("we counted the entries")])
        assert match.tier == "exact"


class TestTheCommandLineIsQuietAboutALocale:
    """The whole point: no finding at all when the values agree."""

    def test_check_reports_one_verified_claim(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        (tmp_path / "sources.toml").write_text(
            chr(10).join(["[sources]", 'p = "a.txt"', ""]), encoding="utf-8", newline=chr(10)
        )
        (tmp_path / "a.txt").write_text(
            "Overall we counted 40.688 entries in the corpus." + chr(10),
            encoding="utf-8",
            newline=chr(10),
        )
        (tmp_path / "m.md").write_text(
            chr(10).join(
                [
                    "```claim id=c1 source=p page=1",
                    "quote:",
                    "  Overall we counted 40,688 entries in the corpus.",
                    "```",
                    "",
                ]
            ),
            encoding="utf-8",
            newline=chr(10),
        )

        assert main(["scan", "m.md", "--root", str(tmp_path), "--quiet"]) == 0
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["verify", "m.md", "--root", str(tmp_path)])

        printed = out.getvalue()
        assert code == 0, printed
        assert "quote-found" in printed
        assert "number-absent-in-quote" not in printed
        assert "1 claim — 1 verified, 0 moved, 0 missing" in printed
