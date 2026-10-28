"""Text normalisation is the foundation; if it is wrong, every finding is wrong."""

from __future__ import annotations

from citevouch.textnorm import (
    canonical_number,
    fold,
    normalize,
    numbers_in,
    squash,
)


def test_smart_quotes_and_dashes_fold_together():
    assert normalize("\u201cquoted\u201d") == '"quoted"'
    assert normalize("a\u2014b") == "a-b"
    assert normalize("a\u2013b") == "a-b"


def test_soft_hyphen_and_zero_width_are_removed():
    assert normalize("con\u00adstruction") == "construction"
    assert normalize("zero\u200bwidth") == "zerowidth"


def test_ligature_is_normalised_not_dropped():
    # NFKC turns the fi ligature into two letters; a solution that merely
    # dropped unknown characters would silently mangle the quote.
    assert normalize("\ufb01le") == "file"


def test_hyphenated_line_break_joins():
    assert normalize("con-\nstruction") == "construction"


def test_hyphen_before_digit_keeps_its_hyphen():
    # "pre-\n1990" is not the word "pre1990"; joining it would create a quote
    # that only exists in the normaliser.
    assert normalize("pre-\n1990") == "pre- 1990"


def test_capitalised_hyphen_across_lines_keeps_hyphen():
    assert normalize("Van Eecke-\nBeuls") == "Van Eecke- Beuls"


def test_whitespace_collapses_to_single_spaces():
    assert normalize("a   b\t\tc\r\nd") == "a b c d"


def test_fold_lowercases_and_normalises():
    assert fold("\u201cHello  WORLD\u201d") == '"hello world"'


def test_squash_removes_all_whitespace():
    assert squash("two  corpora\nhere") == "twocorporahere"


def test_numbers_keep_their_written_form():
    assert numbers_in("154,391 sentences and 48.4% of 40,688") == (
        "154,391",
        "48.4%",
        "40,688",
    )


def test_numbers_without_separators():
    assert numbers_in("in 2026 there were 3") == ("2026", "3")


def test_numbers_in_empty_text_is_empty():
    assert numbers_in("") == ()


def test_canonical_number_strips_separator_and_percent():
    assert canonical_number("1,000") == canonical_number("1000")
    assert canonical_number("48.4%") == "48.4"


def test_normalize_is_idempotent():
    once = normalize("\u201cWe  train\u201d on con-\nstructions")
    assert normalize(once) == once
