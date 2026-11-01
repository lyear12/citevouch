"""Undefined macros in one entry are one finding, naming all of them.

Same shape as the doubled fields, found the same way: `parse_bib` reports
every finding for an entry at the line that entry opens on, so a per-macro
finding loop and a per-field finding loop both produced findings that the
downstream duplicate pass - keyed on ``(code, claim, path, line)`` - collapsed
to one.  A field using two undefined macros showed only the first; two fields
each using one showed only the first field.

The fix is the same as well: the set is the fact.
"""

from __future__ import annotations

from citevouch.bibtex import parse_bib
from citevouch.cli import _deconflict


def _entry(body: str) -> str:
    return "@article{m,\n" + body + "\n}\n"


def _macro_findings(body: str):
    result = parse_bib(_entry(body))
    return [f for f in result.findings if f.code == "bib-macro-unknown"]


class TestOneFindingPerEntry:
    def test_two_macros_in_one_field_are_one_finding(self):
        found = _macro_findings("  journal = jalpha # jbeta,\n  year = {2020},")
        assert len(found) == 1

    def test_the_finding_names_both_macros(self):
        found = _macro_findings("  journal = jalpha # jbeta,\n  year = {2020},")
        assert "'jalpha'" in found[0].message
        assert "'jbeta'" in found[0].message

    def test_two_fields_with_macros_are_still_one_finding(self):
        found = _macro_findings(
            "  journal = jalpha # jbeta,\n  publisher = pgamma,\n  year = {2020},"
        )
        assert len(found) == 1

    def test_that_finding_names_both_fields_and_all_three_macros(self):
        found = _macro_findings(
            "  journal = jalpha # jbeta,\n  publisher = pgamma,\n  year = {2020},"
        )
        message = found[0].message
        assert "'journal'" in message
        assert "'publisher'" in message
        for macro in ("jalpha", "jbeta", "pgamma"):
            assert f"'{macro}'" in message

    def test_the_counts_are_the_real_counts(self):
        found = _macro_findings(
            "  journal = jalpha # jbeta,\n  publisher = pgamma,\n  year = {2020},"
        )
        assert "3 undefined macros in 2 fields" in found[0].message

    def test_one_macro_in_one_field_is_singular(self):
        found = _macro_findings("  journal = jalpha,\n  year = {2020},")
        assert "1 undefined macro in 1 field" in found[0].message
        assert "macros" not in found[0].message.split("(")[0]
        assert "fields" not in found[0].message.split("(")[0]


class TestNothingIsLostOnTheWayOut:
    def test_the_duplicate_pass_keeps_the_aggregate_intact(self):
        result = parse_bib(
            _entry("  journal = jalpha # jbeta,\n  publisher = pgamma,\n  year = {2020},")
        )
        kept = _deconflict(result.findings)
        found = [f for f in kept if f.code == "bib-macro-unknown"]
        assert len(found) == 1
        assert "'pgamma'" in found[0].message

    def test_two_entries_are_two_findings(self):
        text = (
            "@article{m, journal = jalpha, author = {A}, year = {2020}}\n"
            "@article{n, journal = jbeta, author = {A}, year = {2020}}\n"
        )
        result = parse_bib(text)
        found = [f for f in result.findings if f.code == "bib-macro-unknown"]
        assert len(found) == 2
        assert {f.line for f in found} == {1, 2}


class TestTheOrdinaryCases:
    def test_a_defined_macro_is_silent(self):
        result = parse_bib(
            '@string{jtest = "Journal of Tests"}\n'
            "@article{a, journal = jtest, title = {T}, author = {A}, year = {2020}}\n"
        )
        assert [f for f in result.findings if f.code == "bib-macro-unknown"] == []

    def test_a_duplicated_macro_name_counts_once(self):
        """`jalpha # jalpha` is one undefined macro, not two."""
        found = _macro_findings("  journal = jalpha # jalpha,\n  year = {2020},")
        assert len(found) == 1
        assert "1 undefined macro" in found[0].message
