"""Tests for the evidence the first critic round demanded.

Every case here was a silent failure: the parser dropped data, the matcher
matched what it should not, or a bad page hint turned into a false verdict.
The contract of the fix is that each of them now *speaks* - a Finding with the
right code, or a refusal - so most assertions below are on findings rather
than on values.
"""

from __future__ import annotations

from citevouch.bibtex import field_findings, parse_bib
from citevouch.matching import find_in_pages
from citevouch.scan import ScanOptions, scan
from citevouch.sources import PageText
from citevouch.textnorm import fold, numbers_in


def _pages(*texts: str) -> list[PageText]:
    return [PageText(number=i + 1, text=t, folded=fold(t)) for i, t in enumerate(texts)]


# --------------------------------------------------------------------------
# bibtex: never drop in silence


def test_unclosed_entry_is_reported_and_stops_the_parse():
    result = parse_bib("@article{a, title={oops\n@article{b, title={Second}, year={2021}}")
    codes = [f.code for f in result.findings]
    assert "bib-unparsed-entry" in codes
    assert list(result.entries) == []  # a and b both unreadable; the finding says so


def test_brace_in_a_comment_cannot_swallow_the_file_without_a_word():
    result = parse_bib(
        "@comment{ TODO: finish the {brace mess\n"
        "@article{real, title={T}, author={A}, journal={J}, year={2020}}\n"
    )
    assert any(f.code == "bib-unparsed-entry" for f in result.findings)


def test_text_between_entries_is_flagged_not_dropped():
    """An escaped brace closes the value where BibTeX says so; what comes
    after the early close must speak up, because its fields would otherwise
    vanish into nothing."""
    result = parse_bib(
        r"@article{a, note = {escaped \{brace here}}, title={T}, author={A}, year={2020}}"
    )
    codes = [f.code for f in result.findings]
    assert "bib-entry-header-unparsed" in codes
    lost = next(f for f in result.findings if f.code == "bib-entry-header-unparsed")
    assert "title" in lost.message  # the unread remainder is quoted in the message


def test_paren_entry_percent_survives_and_next_entry_is_read():
    result = parse_bib(
        '@article(a, note = "78.5% above CRF", title = {T}, year = {2020})\n'
        "@article(b, title={Second}, author={B}, journal={J}, year={2021})\n"
    )
    assert result.findings == []
    assert sorted(result.entries) == ["a", "b"]
    assert result.entries["a"].fields["note"] == "78.5% above CRF"


def test_malformed_field_reports_and_recovers_the_later_fields():
    result = parse_bib(
        "@article{k, title = {T}, 99 = {oops}, year = {2020}, author = {A}, journal = {J}}"
    )
    assert any(f.code == "bib-field-malformed" for f in result.findings)
    fields = result.entries["k"].fields
    assert fields["year"] == "2020"
    assert fields["author"] == "A"


def test_missing_required_field_is_said_loudly():
    result = parse_bib("@article{k, title={T}}")
    codes = [(f.code, f.message) for f in field_findings(result.entries)]
    assert any(code == "bib-field-empty" and "author" in message for code, message in codes)
    assert any("missing" in message for _, message in codes)


def test_bare_number_year_is_still_read():
    result = parse_bib("@article{a1, title = {T}, year = 2026, author={A}, journal={J}}")
    assert result.entries["a1"].fields["year"] == "2026"


def test_forward_reference_to_a_string_macro_is_reported():
    result = parse_bib(
        "@article{a, journal = jtest, title={T}, author={A}, year={2020}}\n"
        '@string{jtest = "Journal of Tests"}\n'
    )
    assert any(f.code == "bib-macro-unknown" for f in result.findings)


def test_defined_macro_still_expands_without_finding():
    result = parse_bib(
        '@string{jtest = "Journal of Tests"}\n'
        "@article{a, journal = jtest, title={T}, author={A}, year={2020}}\n"
    )
    assert result.entries["a"].fields["journal"] == "Journal of Tests"
    assert result.findings == []


def test_case_duplicate_field_is_reported_and_first_wins():
    result = parse_bib(
        "@article{a, Title={First}, title={Second}, author={A}, journal={J}, year={2020}}"
    )
    assert result.entries["a"].fields["title"] == "First"
    assert any(f.code == "bib-field-duplicate" for f in result.findings)


def test_unusable_entry_header_is_reported():
    result = parse_bib("@in-book{x, title={T}, author={A}, publisher={P}, year={2020}}")
    assert any(f.code == "bib-entry-header-unparsed" for f in result.findings)
    assert "x" not in result.entries


def test_wellformed_bibliography_stays_silent():
    """The silence case: every report above must not fire on normal input."""
    result = parse_bib(
        "@article{ok, author = {A, B}, title = {T}, journal = {J}, year = {2020}, "
        "doi = {10.1/x}, note = {78.5%, ok}}\n"
    )
    assert result.findings == []
    assert result.entries["ok"].fields["note"] == "78.5%, ok"


# --------------------------------------------------------------------------
# matching: a match that crosses a word is not a match


def test_substring_inside_words_is_not_a_match():
    pages = _pages("a bin the papers are listed")
    match = find_in_pages("in the paper", pages)
    assert not match.found
    assert match.tier == "none"


def test_the_same_words_with_boundaries_do_match():
    pages = _pages("as shown in the paper today")
    assert find_in_pages("in the paper", pages).found


def test_a_quote_that_is_only_numbers_cannot_match_words_away():
    """Masked to a single placeholder, `48.4%` used to "match" any page
    holding any number, and the finding then claimed the words matched."""
    pages = _pages("nothing to do with percentages, but has 1,117,581")
    match = find_in_pages("48.4%", pages)
    assert match.tier == "none"
    assert not match.found


def test_space_thousands_still_reach_the_numbers_tier():
    pages = _pages("We coded 1 000 sentences, exactly.")
    match = find_in_pages("we coded 1,000 sentences", pages)
    assert match.tier == "numbers"
    assert not match.found  # numbers is a report tier, not a verification tier


def test_squashed_tier_refuses_quotes_too_short_to_trust():
    pages = _pages("Wetrainontwocorpora.")
    long_match = find_in_pages("We train on two corpora", pages)
    assert long_match.tier == "squashed"
    short = find_in_pages("two co", pages)
    assert not short.found


def test_numbers_context_shows_the_matched_sentence_not_the_page_head():
    pages = _pages("Header junk. " * 40 + "The inventory totals 41,000 items exactly.")
    match = find_in_pages("the inventory totals 40,688 items", pages)
    assert match.tier == "numbers"
    assert "inventory totals" in match.context


# --------------------------------------------------------------------------
# page hints below 1


def test_page_zero_hint_is_out_of_range(tmp_path):
    (tmp_path / "papers").mkdir()
    (tmp_path / "papers" / "p.txt").write_text("we train on two corpora\n", encoding="utf-8")
    (tmp_path / "sources.toml").write_text('[sources]\np = "papers/p.txt"\n', encoding="utf-8")
    (tmp_path / "m.md").write_text(
        "```claim id=c1 source=p page=0\nquote: |\n  we train on two corpora\n```\n",
        encoding="utf-8",
    )
    _ledger, findings = scan(ScanOptions(manuscript=str(tmp_path / "m.md"), root=str(tmp_path)))
    assert any(f.code == "page-out-of-range" for f in findings)


# --------------------------------------------------------------------------
# the two-number-pattern promise (cross-module)


def test_every_reported_number_is_erased_by_masking():
    """`numbers_in` (REPORT) and `number_spans` (MASK) may differ one way only.

    MASK additionally swallows a space thousands-separator so `1,000` and the
    extracted `1 000` compare alike in the numbers tier; REPORT refuses to
    invent such a number, because `2019 2020 2021` is three years and the
    ledger must never record a statistic nobody wrote.  What must always hold
    is coverage: after masking, no reported number survives anywhere.
    """
    from citevouch.matching import mask_numbers, number_spans

    for text in (
        "40,688 of 48.4% and 1,000 in 2026, with 1,117,581 total",
        "no numbers here",
        "a1b2 plain",
        "3.14 and 3,140 and 3 140",
        "2019 2020 2021",
    ):
        for token in numbers_in(text):
            assert token not in mask_numbers(text), f"{token} survived masking"
        for token, _start in number_spans(text):
            assert token in text

    # the one-way difference, spelled out
    assert numbers_in("2019 2020 2021") == ("2019", "2020", "2021")
    assert any(" " in t for t, _ in number_spans("1 000")), "MASK must span the space"
