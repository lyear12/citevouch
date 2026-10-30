"""The real bibliography this tool was built against.

The reader was written for one person's actual working corpus - 39 entries
exported by hand from a Chinese-language literature database, with the encoding
damage that implies: protected capital letters, a ``%`` inside a field, ``and
others`` author tails, CJK titles, and a comment header three lines deep.

Every synthetic fixture in the rest of the suite was written by whoever was
fixing the reader that day, so on its own it proves the fixes agree with
themselves.  This file is the input that disagreed.
"""

from __future__ import annotations

from pathlib import Path

from citevouch.bibtex import doi_of, normalize_doi, parse_bib, title_of

FIXTURE = Path(__file__).parent / "fixtures" / "real-39.bib"


def _parsed():
    return parse_bib(FIXTURE.read_text(encoding="utf-8"), "real-39.bib")


def test_all_thirty_nine_entries_are_read():
    result = _parsed()
    assert len(result.entries) == 39
    assert result.findings == []


def test_the_keys_are_exactly_the_ones_in_the_file():
    result = _parsed()
    assert "beuls2021frame" in result.entries
    assert "vantrijp2022fcgeditor" in result.entries
    assert "vaneecke2022neural" in result.entries
    assert "cxgsnlp2023" in result.entries


def test_a_percent_sign_inside_a_field_does_not_truncate_the_book():
    """The header comment starts with ``%``, and so does one entry's note.

    A reader that strips ``%`` to end-of-line without tracking whether it is
    inside a quoted value finds one entry and then swallows the rest of the
    file: the field's closing brace is gone, so every following ``@`` is read
    as part of the same entry's value.  This corpus found exactly that.
    """
    text = FIXTURE.read_text(encoding="utf-8")
    assert text.count("@") == 39
    result = parse_bib(text, "real-39.bib")
    assert len(result.entries) == 39


def test_cjk_titles_survive_intact():
    result = _parsed()
    cjk = [
        title_of(entry)
        for entry in result.entries.values()
        if any("\u4e00" <= ch <= "\u9fff" for ch in entry.fields.get("title", ""))
    ]
    assert cjk, "the corpus has Chinese titles; if none are read the fixture is stale"
    for title in cjk:
        assert title.strip() == title


def test_dois_and_titles_come_back_usable():
    result = _parsed()
    entry = result.entries["beuls2021frame"]
    assert title_of(entry).startswith("A Computational Construction Grammar Approach")
    # Not every entry has a DOI; the ones that do must normalize to the same
    # bare form Crossref uses, or a comparison against it can never match.
    with_doi = [e for e in result.entries.values() if doi_of(e)]
    assert with_doi
    for item in with_doi:
        raw = doi_of(item)
        assert normalize_doi(raw) == raw
