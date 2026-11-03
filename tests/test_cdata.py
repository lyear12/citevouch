"""Tests for CDATA sections, which is how a feed carries prose.

An `atom.xml` or a JATS article delivers its words inside
`<![CDATA[ ... ]]>` when the producer does not want anything in them parsed.
The generic tag stripper saw that whole section as one tag - `<` followed by
`!` is exactly what a doctype looks like - so it replaced the section with a
space and the words were gone.  A quote that is printed on the page then came
back `[high] quote-missing` with the source file named, which sends an author
looking for a copy-paste mistake that does not exist.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from citevouch import cli, sources

SENTENCE = "The held-out set of 9,800 rolesets was never mentioned anywhere."


class TestTheWordsSurvive:
    """The delimiter is punctuation, not content."""

    def test_a_number_in_cdata_is_still_on_the_page(self):
        text = sources._strip_markup("<p>We collected <![CDATA[9,800]]> rolesets.</p>")
        assert "9,800" in text
        assert "We collected" in text and "rolesets." in text

    def test_a_sentence_in_cdata_is_still_on_the_page(self):
        text = sources._strip_markup(f"<p><![CDATA[{SENTENCE}]]></p>")
        assert SENTENCE in text

    def test_the_delimiters_do_not_reach_the_page(self):
        text = sources._strip_markup(f"<p><![CDATA[{SENTENCE}]]></p>")
        assert "CDATA" not in text
        assert "]]>" not in text

    def test_markup_inside_cdata_is_still_stripped(self):
        """An Atom `type="html"` body is HTML, and a reader does not see tags."""
        text = sources._strip_markup(
            "<content><![CDATA[<p>a <b>bold</b> claim</p>]]></content>"
        )
        assert "a bold claim" in text.replace("  ", " ")
        assert "<p>" not in text and "<b>" not in text

    def test_several_sections_in_one_document(self):
        text = sources._strip_markup(
            "<p><![CDATA[9,800]]> rolesets and <![CDATA[40,688]]> constructions.</p>"
        )
        assert "9,800" in text and "40,688" in text

    def test_a_less_than_inside_cdata_is_text(self):
        """`a < b` must not become a tag, and must not be deleted either."""
        text = sources._strip_markup("<p><![CDATA[we require a < b for every pair]]></p>")
        assert "a < b" in text.replace("  ", " ")

    def test_an_unterminated_section_keeps_what_it_has(self):
        text = sources._strip_markup("<p><![CDATA[the rest of the file is text")
        assert "the rest of the file is text" in text

    def test_a_document_without_cdata_is_untouched(self):
        """The fix must not change what the reader does to ordinary HTML."""
        assert sources._strip_markup("<p>a</p>").strip() == "a"
        assert sources._strip_markup("<p>a &amp; b</p>").strip() == "a & b"


class TestTheVerdict:
    """The end-to-end failure: a quote printed on the page is called missing."""

    def _project(self, tmp_path: Path, body: str) -> int:
        (tmp_path / "src").mkdir(exist_ok=True)
        (tmp_path / "src" / "paper.xml").write_bytes(body.encode("utf-8"))
        (tmp_path / "sources.toml").write_bytes(b'[sources]\npaper = "src/paper.xml"\n')
        (tmp_path / "manuscript.md").write_bytes(
            (
                f"Intro.\n\n```claim id=c1 source=paper page=1\nquote: |\n  {SENTENCE}\n```\n"
            ).encode()
        )
        cwd = Path.cwd()
        import os

        os.chdir(tmp_path)
        try:
            return cli.main(["check", "manuscript.md", "--root", "."])
        finally:
            os.chdir(cwd)

    def test_a_quote_inside_cdata_is_found(self, tmp_path: Path):
        body = f"<article><body><p><![CDATA[{SENTENCE}]]></p></body></article>"
        assert self._project(tmp_path, body) == 0

    def test_a_quote_that_is_not_in_the_file_is_still_missing(self, tmp_path: Path):
        body = "<article><body><p><![CDATA[something else entirely]]></p></body></article>"
        assert self._project(tmp_path, body) == 1


@pytest.mark.parametrize(
    "body",
    [
        '<content type="html"><![CDATA[<p>{s}</p>]]></content>',
        "<description><![CDATA[{s}]]></description>",
        "<p><![CDATA[{s}]]></p>",
    ],
)
def test_the_shapes_a_feed_actually_uses(body: str):
    text = sources._strip_markup(body.format(s=SENTENCE))
    assert SENTENCE in text
