"""Fragment a third shape: the doubled fields, the undefined macros, this.

Each of the three reporting sites in `parse_bib` that can fire more than once
for one entry was fixed separately, one round at a time, because the fix for
the first was written down as a rule about sets and then applied to the
finding in hand rather than to the class of finding.  The third one was left
behind deliberately in a commit message that said it was unreachable; it is
not - `bib-field-malformed` fires once per unreadable fragment, and an entry
with a bad field, a good field, and another bad field produces two.

This file is the check that the third one is actually closed.
"""

from __future__ import annotations

from citevouch.bibtex import parse_bib
from citevouch.cli import _deconflict


def _entry(body: str) -> str:
    return "@article{m,\n" + body + "\n}\n"


def _malformed(text: str):
    result = parse_bib(text)
    return [f for f in result.findings if f.code == "bib-field-malformed"]


class TestTwoFragmentsAreOneFinding:
    def test_two_bad_fields_separated_by_a_good_one_are_one_finding(self):
        found = _malformed(_entry("  badone,\n  year = {2020},\n  badtwo,\n  author = {C},"))
        assert len(found) == 1

    def test_that_finding_names_both_fragments(self):
        found = _malformed(_entry("  badone,\n  year = {2020},\n  badtwo,\n  author = {C},"))
        message = found[0].message
        assert "badone" in message
        assert "badtwo" in message

    def test_the_count_is_the_number_of_fragments(self):
        found = _malformed(_entry("  badone,\n  year = {2020},\n  badtwo,\n  author = {C},"))
        assert "2 fragments" in found[0].message

    def test_a_single_fragment_is_singular(self):
        found = _malformed(_entry("  year = {2020},\n  badtwo,\n  author = {C},"))
        assert "1 fragment" in found[0].message
        assert "fragments" not in found[0].message


class TestTheReadingStopsWhereItShould:
    def test_the_readable_fields_are_still_read(self):
        result = parse_bib(_entry("  badone,\n  year = {2020},\n  badtwo,\n  author = {C},"))
        assert result.entries["m"].fields["year"] == "2020"
        assert result.entries["m"].fields["author"] == "C"

    def test_text_after_the_last_field_is_reported_as_a_fragment(self):
        """The other branch: nothing to resume at, so the tail is the fragment."""
        found = _malformed(_entry("  title = {T},\n  author = {A},\n  tail,"))
        assert len(found) == 1
        assert "tail" in found[0].message

    def test_a_tail_and_an_earlier_fragment_are_one_finding(self):
        found = _malformed(_entry("  badone,\n  year = {2020},\n  author = {A},\n  tail,"))
        assert len(found) == 1
        assert "badone" in found[0].message
        assert "tail" in found[0].message


class TestTheDuplicatePassKeepsIt:
    def test_the_pass_that_hid_this_does_not_hide_it(self):
        result = parse_bib(_entry("  badone,\n  year = {2020},\n  badtwo,\n  author = {C},"))
        kept = _deconflict(result.findings)
        found = [f for f in kept if f.code == "bib-field-malformed"]
        assert len(found) == 1
        assert "badtwo" in found[0].message


class TestTheOrdinaryCase:
    def test_a_clean_entry_reports_nothing(self):
        assert _malformed(_entry("  title = {T},\n  author = {A},\n  year = {2020},")) == []
