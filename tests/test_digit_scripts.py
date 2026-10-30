"""A number written in another script's digits is the same number.

An author reading a paper printed in Cairo types `40688`; the PDF's
extraction says `٤٠٦٨٨`.  Those are the same number to every human involved and
were two different strings to this tool, which sent the quote through the exact
tier (miss), the squashed tier (miss, one character differs) and into the
numbers tier - whose whole job is to say "the words match but the digits do
not".  The tool was then reporting `number-absent-in-quote` about a number the
author could see on the page.

NFKC does not do this folding: ٤ is an ordinary character to the normaliser,
not a compatibility variant of 4.  `_ascii_digits` does, and it carries no
table - `unicodedata.decimal` knows every decimal digit in Unicode.
"""

from __future__ import annotations

import pytest

from citevouch.matching import find_in_pages
from citevouch.sources import PageText
from citevouch.textnorm import canonical_number, fold, normalize, numbers_in

ARABIC = "\u0648\u0642\u062f \u0628\u0644\u063a \u0627\u0644\u0639\u062f\u062f {} \u062a\u0631\u0643\u064a\u0628\u0627."
HEBREW = "\u05d4\u05de\u05e7\u05d5\u05e8 \u05de\u05db\u05d9\u05dc {} \u05de\u05e9\u05e4\u05d8\u05d9\u05dd."

ARABIC_INDIC = "\u0664\u0660\u0666\u0668\u0668"  # 40688
PERSIAN = "\u06f2\u06f0\u06f1\u06f9"  # 2019
DEVANAGARI = "\u0967\u0968\u0969"  # 123
FULLWIDTH = "\uff11\uff12\uff13"  # 123
BENGALI = "\u09e7\u09e8\u09e9"  # 123


class TestTheNormalFormFoldsTheDigits:
    @pytest.mark.parametrize(
        "foreign, ascii_form",
        [
            (ARABIC_INDIC, "40688"),
            (PERSIAN, "2019"),
            (DEVANAGARI, "123"),
            (FULLWIDTH, "123"),
            (BENGALI, "123"),
        ],
    )
    def test_every_script_reaches_the_same_string(self, foreign, ascii_form):
        assert normalize(foreign) == ascii_form
        assert fold(foreign) == fold(ascii_form)

    def test_ascii_text_is_untouched(self):
        """The fast path must not change anything it was not meant to."""
        text = "40,688 utterances (48.4% of the corpus) at 2.5x speed"
        assert normalize(text) == text

    def test_the_fast_path_is_not_the_rule(self):
        """`isascii()` is an optimisation; the result cannot depend on it."""
        mixed = "the count 40688 \u0664\u0660\u0666\u0668\u0668 and 123"
        assert normalize(mixed) == "the count 40688 40688 and 123"


class TestTheNumbersAreTheSameNumber:
    @pytest.mark.parametrize(
        "foreign, ascii_form",
        [(ARABIC_INDIC, "40688"), (PERSIAN, "2019"), (DEVANAGARI, "123")],
    )
    def test_canonical_number_agrees_across_scripts(self, foreign, ascii_form):
        assert canonical_number(foreign) == canonical_number(ascii_form)

    def test_the_arabic_thousands_and_decimal_signs_are_separators(self):
        """40٬688 and ٤٨٫٤ use U+066C and U+066B, not comma and full stop."""
        assert canonical_number("40\u066c688") == "40688"
        assert canonical_number("48\u066b4") == "48.4"
        assert numbers_in("48\u066b4") == ("48\u066b4",)

    def test_a_number_in_any_script_is_reported_as_written(self):
        """`numbers_in` returns the document's spelling; canonical_number folds."""
        assert numbers_in(ARABIC_INDIC) == (ARABIC_INDIC,)
        assert numbers_in(ARABIC_INDIC) != numbers_in("40688")


class TestTheMatcherSeesOneNumber:
    @pytest.mark.parametrize(
        "page_text, quote_text",
        [
            (ARABIC.format("40688"), ARABIC.format(ARABIC_INDIC)),
            (ARABIC.format(ARABIC_INDIC), ARABIC.format("40688")),
            (HEBREW.format(PERSIAN), HEBREW.format("2019")),
            (ARABIC.format("123"), ARABIC.format(DEVANAGARI)),
        ],
    )
    def test_it_matches_at_the_exact_tier_not_the_numbers_tier(self, page_text, quote_text):
        """The numbers tier is a *finding*. Matching there is the false report."""
        match = find_in_pages(quote_text, [PageText(number=1, text=page_text)], None)
        assert match.tier == "exact", (
            f"the quote was not found at the exact tier ({match.tier}); a quote "
            f"that differs only in the script its digits are written in is the "
            f"same quote, and the numbers tier would report it as one whose "
            f"numbers do not match the source"
        )

    def test_a_genuinely_different_number_still_reaches_the_numbers_tier(self):
        """The fix must not paper over the typo this tier exists to catch."""
        match = find_in_pages(
            ARABIC.format("40699"), [PageText(number=1, text=ARABIC.format("40688"))], None
        )
        assert match.tier == "numbers"
