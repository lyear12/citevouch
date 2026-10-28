"""BibTeX parsing: the fields we depend on, and the mistakes we must not hide."""

from __future__ import annotations

from citevouch.bibtex import doi_of, field_findings, normalize_doi, parse_bib, title_of


def test_parses_a_plain_entry():
    result = parse_bib(
        """
@article{smith2026,
  author = {Smith, Jane and Doe, John},
  title  = {A {G}reat Paper},
  journal = {J. Tests},
  year   = {2026},
  doi    = {10.1000/XYZ},
}
"""
    )
    entry = result.entries["smith2026"]
    assert entry.entry_type == "article"
    assert entry.fields["author"] == "Smith, Jane and Doe, John"
    assert entry.fields["year"] == "2026"


def test_quoted_values_and_concatenation():
    result = parse_bib(
        """
@string{jtest = "Journal of Tests"}
@article{a1,
  title = "Part one" # " and two",
  journal = jtest,
  year = 2026
}
"""
    )
    entry = result.entries["a1"]
    assert entry.fields["title"] == "Part one and two"
    assert entry.fields["journal"] == "Journal of Tests"
    assert entry.fields["year"] == "2026"


def test_comment_entries_are_not_citations():
    result = parse_bib(
        """
@comment{this is ignored}
@article{real, title={T}, journal={J}, year={2026}, author={A}}
"""
    )
    assert set(result.entries) == {"real"}


def test_percent_comments_are_stripped_but_escaped_percent_survives():
    result = parse_bib(
        """
@article{a1,
  title = {100\\% done}, % trailing comment
  year = {2026}
}
"""
    )
    assert result.entries["a1"].fields["title"] == "100\\% done"


def test_duplicate_key_is_reported_not_swallowed():
    result = parse_bib(
        """
@article{dup, title={First}, year={2020}}
@article{dup, title={Second}, year={2021}}
"""
    )
    assert result.entries["dup"].fields["title"] == "Second"
    assert [f.code for f in result.findings] == ["bib-duplicate-key"]


def test_entry_without_key_is_reported():
    result = parse_bib("@article{, title={No key}, year={2020}}")
    assert result.entries == {}
    assert result.findings and result.findings[0].code == "bib-key-missing"


def test_line_numbers_point_at_the_entry():
    result = parse_bib(
        "\n\n@article{one, title={T}, year={2020}}\n\n@article{two, title={U}, year={2021}}\n"
    )
    assert result.entries["one"].line == 3
    assert result.entries["two"].line == 5


def test_doi_is_normalised_from_every_common_form():
    for raw in (
        "10.1000/xyz",
        "https://doi.org/10.1000/XYZ",
        "http://dx.doi.org/10.1000/xyz",
        "doi:10.1000/xyz",
    ):
        assert normalize_doi(raw) == "10.1000/xyz"


def test_doi_of_reads_the_field():
    result = parse_bib("@article{a, doi={https://doi.org/10.1/ABC}}")
    assert doi_of(result.entries["a"]) == "10.1/abc"


def test_title_strips_protecting_braces():
    result = parse_bib("@article{a, title={The {DNA} of {C}onstructions}}")
    assert title_of(result.entries["a"]) == "The DNA of Constructions"


def test_empty_required_field_is_a_finding():
    result = parse_bib("@article{a, author={A}, title={T}, journal={J}, year={ }}")
    findings = field_findings(result.entries)
    assert [f.code for f in findings] == ["bib-field-empty"]
    assert "year" in findings[0].message


def test_present_and_filled_required_fields_produce_nothing():
    result = parse_bib("@article{a, author={A}, title={T}, journal={J}, year={2026}}")
    assert field_findings(result.entries) == []


def test_braces_inside_values_do_not_break_the_entry():
    result = parse_bib(
        """
@inproceedings{a,
  title = {Nested {braces {deeply}} here},
  booktitle = {Proc. of {X}},
  year = {2026},
  author = {A}
}
@article{b, title={Second}, year={2026}}
"""
    )
    assert result.entries["a"].fields["title"] == "Nested {braces {deeply}} here"
    assert "b" in result.entries
