"""The required-field findings must name every field in one line each time.

The duplicate pass keys findings on ``(code, claim_id, path, line)``, and every
finding about a bibliography entry carries that entry's opening line.  Reported
one field per finding, an entry missing four required fields produced four
findings of which exactly one survived - so the author fixed ``author``, ran
again, and met ``title``.  A check that has to be run four times to be read is
four times as likely to be run once.

Splitting "missing" and "present but empty" into two findings per entry failed
the same way for the same reason: same code, same entry, same line, so the
second one was dropped.  They are one message with two clauses, because they
are one coordinate.

These tests are about the shape of the report, not about which fields an
``@article`` needs: that list is ``REQUIRED_FIELDS`` and it is not in question
here.
"""

from __future__ import annotations

from citevouch.bibtex import field_findings, parse_bib
from citevouch.cli import _deconflict


def _findings(text: str):
    result = parse_bib(text, "refs.bib")
    return result.findings + field_findings(result.entries)


def _empty(text: str) -> list[str]:
    return [f.message for f in _findings(text) if f.code == "bib-field-empty"]


class TestOneEntryIsOneFinding:
    def test_four_missing_fields_are_one_finding(self):
        assert len(_empty("@article{a, note={x}}\n")) == 1

    def test_the_one_finding_names_all_four(self):
        message = _empty("@article{a, note={x}}\n")[0]
        for name in ("author", "title", "journal", "year"):
            assert name in message

    def test_the_duplicate_pass_does_not_remove_anything(self):
        found = [
            f
            for f in _findings("@article{a, note={x}}\n@book{b, note={y}}\n")
            if f.code == "bib-field-empty"
        ]
        assert len(found) == 2
        assert len(_deconflict(found)) == 2

    def test_each_entry_is_still_its_own_finding(self):
        lines = sorted(
            f.line
            for f in _findings("@article{a, note={x}}\n@book{b, note={y}}\n")
            if f.code == "bib-field-empty"
        )
        assert lines == [1, 2]


class TestMissingAndEmptyShareOneMessage:
    def test_they_are_one_finding(self):
        assert len(_empty("@article{a, author={}, title={T}}\n")) == 1

    def test_the_one_finding_says_both_things(self):
        message = _empty("@article{a, author={}, title={T}}\n")[0]
        assert "missing" in message
        assert "present but empty" in message
        assert "'author'" in message
        assert "'journal'" in message and "'year'" in message

    def test_the_duplicate_pass_keeps_it(self):
        found = [
            f
            for f in _findings("@article{a, author={}, title={T}}\n")
            if f.code == "bib-field-empty"
        ]
        assert len(_deconflict(found)) == 1


class TestTheWordingSurvivesEverySize:
    def test_a_single_missing_field_reads_as_one(self):
        message = _empty("@article{a, author={A}, title={T}, journal={J}}\n")[0]
        assert "1 required field missing" in message
        assert "fields" not in message

    def test_two_missing_fields_are_joined_with_and(self):
        message = _empty("@article{a, author={A}, title={T}}\n")[0]
        assert "'journal' and 'year'" in message

    def test_an_empty_field_alone_says_so(self):
        message = _empty("@article{a, author={}, title={T}, journal={J}, year={2020}}\n")[0]
        assert "present but empty" in message
        assert "missing" not in message


class TestTheEntryKeepsItsOwnFields:
    def test_a_complete_entry_reports_nothing(self):
        assert _empty("@article{a, author={A}, title={T}, journal={J}, year={2020}}\n") == []

    def test_an_unknown_type_is_not_held_to_a_list(self):
        assert _empty("@misc{a, note={x}}\n") == []
