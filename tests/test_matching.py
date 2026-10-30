"""Matching decides whether a quote is in a source.  Its tiers are the product."""

from __future__ import annotations

from citevouch.matching import (
    MIN_FUZZY_TOKENS,
    PageText,
    _bounded_pages,
    excerpt,
    find_in_pages,
)


def _pages(*texts: str) -> list[PageText]:
    from citevouch.textnorm import fold

    return [PageText(number=i + 1, text=t, folded=fold(t)) for i, t in enumerate(texts)]


def test_exact_match_is_reported_on_the_right_page():
    pages = _pages("Opening words.", "We train on two corpora here.", "Closing words.")
    match = find_in_pages("We train on two corpora here.", pages)
    assert match.tier == "exact"
    assert match.page == 2
    assert match.found


def test_whitespace_and_case_differences_still_match_exactly():
    pages = _pages("We train on\n\ttwo   corpora.")
    match = find_in_pages("We  train on two corpora.", pages)
    assert match.tier == "exact"


def test_line_break_hyphen_is_folded_away():
    pages = _pages("the con-\nstruction inventory")
    match = find_in_pages("the construction inventory", pages)
    assert match.tier == "exact"


def test_smart_quotes_do_not_break_a_match():
    pages = _pages("a \u201cquoted\u201d phrase in the text")
    match = find_in_pages('a "quoted" phrase in the text', pages)
    assert match.tier == "exact"


def test_squashed_tier_ignores_word_boundaries():
    # PDFs that lose spaces entirely are common enough to be worth a tier.
    pages = _pages("Wetrainontwocorpora.")
    match = find_in_pages("We train on two corpora.", pages)
    assert match.tier == "squashed"


def test_page_hint_is_a_preference_not_a_filter():
    pages = _pages("The quote lives here.", "Not here.", "Also not here.")
    match = find_in_pages("The quote lives here.", pages, page_hint=3)
    assert match.found
    assert match.page == 1


def test_page_hint_wins_when_the_quote_appears_twice():
    pages = _pages("Repeated sentence.", "Repeated sentence.")
    match = find_in_pages("Repeated sentence.", pages, page_hint=2)
    assert match.page == 2


def test_quote_that_is_absent_is_not_matched():
    pages = _pages("A completely different sentence.")
    match = find_in_pages("The quote that is missing.", pages)
    assert not match.found
    assert match.tier == "none"
    assert match.reason


def test_missing_quote_does_not_claim_a_page():
    pages = _pages("Something else entirely.")
    match = find_in_pages("nothing like this text", pages)
    assert match.page is None


def test_fuzzy_tier_locates_but_never_verifies():
    pages = _pages(
        "We train the grammar induction model on two semantically annotated corpora."
    )
    match = find_in_pages(
        "We train the grammar induction system on two semantically annotated corpora.",
        pages,
    )
    # Fuzzy is a weaker claim than exact and must never count as verified.
    assert match.tier == "fuzzy"
    assert match.similarity >= 0.82
    assert not match.found


def test_fuzzy_never_upgrades_a_short_quote():
    # A two-word quote that merely resembles something must not be accepted:
    # short quotes are where a fuzzy match produces false confidence.
    pages = _pages("two corpora")
    match = find_in_pages("three corpora", pages)
    assert not match.found


def test_fuzzy_threshold_constant_is_used():
    assert 0.5 < MIN_FUZZY_TOKENS <= 12


def test_empty_pages_are_not_matched():
    match = find_in_pages("any quote here", _pages("", ""))
    assert not match.found


def test_quote_longer_than_the_page_is_not_matched():
    pages = _pages("short")
    assert not find_in_pages("a much longer quote than the page", pages).found


def test_excerpt_truncates_and_marks_the_cut():
    text = "word " * 60
    out = excerpt(text, limit=30)
    assert len(out) <= 33
    assert out.endswith("\u2026")


def test_excerpt_keeps_short_text_untouched():
    assert excerpt("short quote", limit=30) == "short quote"


class TestPunctuationEndsAreUnconstrained:
    """A side that is already punctuation cannot be part of a longer word.

    This is the one deliberate loosening in the exact tier.  It exists because
    CJK prose does not put spaces after a full stop, so ``...很小。`` would
    otherwise never satisfy "followed by a non-word character" and every quoted
    Chinese sentence would drop to the squashed tier.  The tests below pin the
    loosening in both directions: it must let a real sentence through, and it
    must not turn "quote followed by more letters" into a match.
    """

    def test_a_quote_ending_in_a_full_stop_matches_before_letters(self):
        page = PageText(1, "构式网络很小。后面还有别的", "构式网络很小。后面还有别的")
        found = _bounded_pages(page, "构式网络很小。")
        assert found, "a full stop must not need a space after it to bound the match"

    def test_a_quote_ending_in_a_comma_matches_before_letters(self):
        page = PageText(1, "see below, and then the rest", "see below, and then the rest")
        assert _bounded_pages(page, "see below,")

    def test_a_quote_starting_with_punctuation_needs_no_space_before(self):
        page = PageText(1, "text(see below) more", "text(see below) more")
        assert _bounded_pages(page, "(see below)")

    def test_the_loosening_does_not_apply_to_a_word_ending(self):
        # "in the paper" ends in a letter, so the old rule still holds.
        page = PageText(1, "as seen in the papers today", "as seen in the papers today")
        assert _bounded_pages(page, "in the paper") == []

    def test_the_loosening_does_not_apply_to_a_word_start(self):
        page = PageText(1, "a bin the paper today", "a bin the paper today")
        assert _bounded_pages(page, "in the paper") == []
