"""One entry with several doubled fields is one finding, not one per field.

Every finding for one bibliography entry carries that entry's opening line,
because `parse_bib` reports positions by the line the entry starts at.  The
downstream duplicate pass keys on ``(code, claim, path, line)``, so three
findings about three different doubled fields in one entry collapsed to one:
the author fixed ``title``, re-ran, and met ``year`` for the first time.  A
report that has to be run three times to be read once is not a report.

The fix is the one ``bib-key-unused`` already uses: when a fact is a set,
report the set.
"""

from __future__ import annotations

from citevouch.bibtex import parse_bib
from citevouch.cli import _deconflict


def _doubles(body: str) -> str:
    return "@article{x,\n" + body + "\n}\n"


class TestTheSetIsTheFact:
    def test_three_doubled_fields_are_one_finding(self):
        result = parse_bib(
            _doubles(
                "  title = {One},\n"
                "  title = {Two},\n"
                "  year = {2020},\n"
                "  year = {2021},\n"
                "  author = {A},\n"
                "  author = {B},"
            )
        )
        found = [f for f in result.findings if f.code == "bib-field-duplicate"]
        assert len(found) == 1

    def test_that_finding_names_every_doubled_field(self):
        result = parse_bib(
            _doubles(
                "  title = {One},\n"
                "  title = {Two},\n"
                "  year = {2020},\n"
                "  year = {2021},\n"
                "  author = {A},\n"
                "  author = {B},"
            )
        )
        message = next(f.message for f in result.findings if f.code == "bib-field-duplicate")
        assert "'author'" in message
        assert "'title'" in message
        assert "'year'" in message

    def test_the_count_is_the_number_of_doubled_fields(self):
        result = parse_bib(
            _doubles("  title = {One},\n  title = {Two},\n  year = {2020},\n  year = {2021},")
        )
        message = next(f.message for f in result.findings if f.code == "bib-field-duplicate")
        assert "2 fields given twice" in message

    def test_one_doubled_field_is_still_singular(self):
        result = parse_bib(_doubles("  title = {One},\n  title = {Two},"))
        message = next(f.message for f in result.findings if f.code == "bib-field-duplicate")
        assert "1 field given twice" in message
        assert "fields given twice" not in message

    def test_the_first_value_of_each_field_still_wins(self):
        result = parse_bib(
            _doubles("  title = {One},\n  title = {Two},\n  year = {2020},\n  year = {2021},")
        )
        assert result.entries["x"].fields["title"] == "One"
        assert result.entries["x"].fields["year"] == "2020"


class TestNothingIsLostOnTheWayOut:
    def test_the_duplicate_pass_does_not_remove_the_aggregate(self):
        """The pass that hid this bug is the one that must not hide it again."""
        result = parse_bib(
            _doubles(
                "  title = {One},\n"
                "  title = {Two},\n"
                "  year = {2020},\n"
                "  year = {2021},\n"
                "  author = {A},\n"
                "  author = {B},"
            )
        )
        kept = _deconflict(result.findings)
        found = [f for f in kept if f.code == "bib-field-duplicate"]
        assert len(found) == 1
        assert "'title'" in found[0].message
        assert "'year'" in found[0].message
        assert "'author'" in found[0].message

    def test_two_entries_each_with_a_doubled_field_are_two_findings(self):
        """Aggregation is per entry: a set does not span entries."""
        text = (
            "@article{x, title = {One}, title = {Two}, author = {A}, year = {2020}}\n"
            "@article{y, title = {One}, title = {Two}, author = {A}, year = {2020}}\n"
        )
        result = parse_bib(text)
        found = [f for f in result.findings if f.code == "bib-field-duplicate"]
        assert len(found) == 2
        assert {f.line for f in found} == {1, 2}


class TestTheOrdinaryCaseIsStillSilent:
    def test_a_clean_entry_reports_nothing(self):
        result = parse_bib(
            "@article{a, title = {T}, author = {A}, journal = {J}, year = {2020}}"
        )
        assert result.findings == []

    def test_a_field_that_differs_only_by_case_is_still_a_duplicate(self):
        result = parse_bib(
            "@article{a, Title = {First}, title = {Second}, author = {A}, year = {2020}}"
        )
        found = [f for f in result.findings if f.code == "bib-field-duplicate"]
        assert len(found) == 1
        assert "'title'" in found[0].message
