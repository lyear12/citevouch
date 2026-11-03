"""Tests for the regions of an HTML source no reader ever sees.

A `<script>`, `<style>` or comment body is not prose, and neither is the
content of a `<template>`, `<textarea>` or `<iframe>`.  When one leaks into the
page text, a sentence that exists only inside code is certified `quote-found`.
That is the one failure this tool cannot apologise for, so the boundary gets
its own file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from citevouch import sources
from citevouch.cli import main

B3 = "`" * 3
QUOTE = "The method works on every corpus we tried."


def project(tmp_path: Path, html: str) -> Path:
    """A one-claim project whose only source is this HTML."""
    (tmp_path / "page.html").write_text(html, encoding="utf-8", newline="\n")
    (tmp_path / "sources.toml").write_text(
        '[sources]\nweb = "page.html"\n', encoding="utf-8", newline="\n"
    )
    manuscript = tmp_path / "m.md"
    manuscript.write_text(
        f"{B3}claim id=c1 source=web\nquote: |\n  {QUOTE}\n{B3}\n",
        encoding="utf-8",
        newline="\n",
    )
    return manuscript


def verdict(tmp_path: Path, html: str) -> tuple[int, str]:
    manuscript = project(tmp_path, html)
    main(["scan", str(manuscript), "--root", str(tmp_path)])
    return main(["verify", str(manuscript), "--root", str(tmp_path)]), ""


class TestATerminatedRegionLeavesNothingBehind:
    def test_a_closed_script_body_is_not_page_text(self):
        stripped = sources._strip_markup(f"<script>var t='{QUOTE}';</script><p>real</p>")
        assert QUOTE not in stripped
        assert "real" in stripped

    def test_a_closed_comment_is_not_page_text(self):
        stripped = sources._strip_markup(f"<p>a</p><!-- {QUOTE} --><p>b</p>")
        assert QUOTE not in stripped
        assert "a" in stripped and "b" in stripped


class TestAnUnterminatedRegionRunsToTheEnd:
    """A truncated save is the common case, and a browser hides the rest too."""

    def test_an_unclosed_script_body_is_not_page_text(self):
        stripped = sources._strip_markup(f"<p>intro</p><script>var t='{QUOTE}';")
        assert QUOTE not in stripped
        assert "intro" in stripped

    def test_an_unclosed_comment_is_not_page_text(self):
        stripped = sources._strip_markup(f"<p>intro</p><!-- {QUOTE}")
        assert QUOTE not in stripped

    def test_an_unclosed_style_body_is_not_page_text(self):
        stripped = sources._strip_markup(f"<p>intro</p><style>/* {QUOTE}")
        assert QUOTE not in stripped


class TestTheEndTagSpellingIsNotOneSpelling:
    """HTML allows whitespace before the `>` of an end tag."""

    @pytest.mark.parametrize("end", ["</script>", "</script >", "</script\n>", "</SCRIPT>"])
    def test_the_body_goes_away_however_the_tag_is_spelled(self, end: str):
        stripped = sources._strip_markup(f"<p>a</p><script>var t='{QUOTE}';{end}<p>b</p>")
        assert QUOTE not in stripped
        assert "b" in stripped


class TestWhatMustStillBeProse:
    """The refusal must not eat the document either."""

    def test_a_less_than_in_prose_is_still_text(self):
        assert sources._strip_markup("5 < 7 and 8 > 2").strip() == "5 < 7 and 8 > 2"

    def test_an_entity_is_still_decoded(self):
        assert sources._strip_markup("<p>a&amp;b &lt;tag&gt; c</p>").strip() == "a&b <tag> c"

    def test_two_regions_in_a_row_both_go(self):
        stripped = sources._strip_markup("<script>a</script><style>b</style><p>keep</p>")
        assert stripped.strip() == "keep"


class TestTheVerdictOnAProject:
    def test_a_quote_that_only_exists_in_a_script_is_not_verified(self, tmp_path: Path):
        code, _ = verdict(tmp_path, f"<p>intro</p><script>var t='{QUOTE}';</script>")
        assert code == 1

    def test_a_quote_in_the_prose_still_verifies(self, tmp_path: Path):
        code, _ = verdict(tmp_path, f"<script>var x=1;</script><p>{QUOTE}</p>")
        assert code == 0


def test_the_pages_of_a_real_file_hold_no_script(tmp_path: Path):
    """The same thing through the extractor, not just the helper."""
    html = f"<html><body><p>{QUOTE}</p><script>var t = '{QUOTE}';</script></body></html>"
    path = tmp_path / "page.html"
    path.write_text(html, encoding="utf-8", newline="\n")
    pages, problem = sources.extract_pages(path, tmp_path, use_cache=False)
    assert problem is None
    assert pages[0].text.count(QUOTE) == 1


class TestElementsWhoseContentIsNotProse:
    """Elements a browser holds but never paints as document text.

    `<script>` and `<style>` were the first two names in the list, and the
    defect that made them worth listing - a quote that exists only inside code
    being certified `quote-found` - does not care which element it is hiding
    in.  A `<template>` is inert by specification, `<textarea>` content is a
    form value rather than prose, and `<iframe>` content is fallback text for
    browsers that have no `<iframe>`; no reader ever sees any of the three as
    words on the page.
    """

    @pytest.mark.parametrize("tag", ["template", "textarea", "iframe"])
    def test_the_body_is_not_page_text(self, tag: str):
        stripped = sources._strip_markup(f"<p>a</p><{tag}>{QUOTE}</{tag}><p>b</p>")
        assert QUOTE not in stripped
        assert "a" in stripped and "b" in stripped

    @pytest.mark.parametrize("tag", ["template", "textarea", "iframe"])
    def test_an_unclosed_one_does_not_hand_the_rest_to_prose(self, tag: str):
        stripped = sources._strip_markup(f"<p>intro</p><{tag}>{QUOTE}")
        assert QUOTE not in stripped
        assert "intro" in stripped

    def test_the_attributes_are_not_page_text_either(self):
        """`<textarea rows=3 placeholder="...">` must not leave the attributes."""
        stripped = sources._strip_markup(
            f'<textarea rows="3" placeholder="type here">{QUOTE}</textarea><p>after</p>'
        )
        assert QUOTE not in stripped
        assert "placeholder" not in stripped
        assert "after" in stripped


class TestWhatWasDeliberatelyLeftAlone:
    """Two elements that look like the others and are not.

    A list of "elements nobody sees" is a claim about every element, and two of
    the neighbours are counter-examples.  `<noscript>` content *is* shown, in
    the configuration where it is shown, so dropping it would turn a quote a
    no-JS reader can read into `quote-missing` - the failure in the other
    direction, and the one that costs an author a morning.  An `<svg>` may
    carry real `<text>` that a reader sees.  Both stay in the page text, and
    these two tests are the record of that decision being made on purpose.
    """

    def test_noscript_content_is_still_read(self):
        stripped = sources._strip_markup("<p>a</p><noscript>turn on scripts</noscript>")
        assert "turn on scripts" in stripped

    def test_svg_text_is_still_read(self):
        stripped = sources._strip_markup("<svg><text>a figure label</text></svg>")
        assert "a figure label" in stripped


class TestTheVerdictOnAnInertElement:
    """The end-to-end failure: a quote nobody can see comes back verified."""

    def test_a_quote_that_only_exists_in_a_template_is_not_verified(self, tmp_path: Path):
        code, _ = verdict(tmp_path, f"<p>intro</p><template><p>{QUOTE}</p></template>")
        assert code == 1

    def test_a_quote_that_only_exists_in_a_textarea_is_not_verified(self, tmp_path: Path):
        code, _ = verdict(tmp_path, f"<p>intro</p><textarea>{QUOTE}</textarea>")
        assert code == 1

    def test_prose_outside_the_element_still_verifies(self, tmp_path: Path):
        code, _ = verdict(tmp_path, f"<template>x</template><p>{QUOTE}</p>")
        assert code == 0
