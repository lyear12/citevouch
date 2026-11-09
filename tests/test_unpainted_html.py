"""Tests for the text of an HTML element the browser never paints.

`<script>`, `<style>` and the other inert elements are removed by tag name, and
that list was the whole rule.  But a browser can also be told to paint nothing
about an element it does hold, and then the words inside are still in the file
and still not on the page:

    <div style="display:none">We collected 40,688 examples.</div>
    <p hidden>We collected 40,688 examples.</p>

Measured before this file existed: a one-claim project whose only source held
the sentence inside a `display:none` div answered

    [info] quote-found at m.md:1 (c1): quote found on page 1

with exit 0, and the same for `visibility:hidden`, for the `hidden` attribute,
for an `aria-hidden` span, for `<title>`, for a `<datalist>` option and for an
ordinary `<p>` (the control).  The first three are the bug.  The rest are the
answer the tool should keep giving, and the classes below say why.  Certifying
words no reader can see is the one failure this tool cannot apologise for, and
it does not care which mechanism hid them, exactly as it did not care whether
the code hid in a `<script>` or a `<template>`.

Four neighbours are deliberately left alone, and their tests say so out loud,
because a list of "things nobody sees" is a claim about everything not on it:

* `aria-hidden="true"` is for assistive technology.  It says a screen reader
  should skip the element; it does not stop the browser painting it, so a
  sighted reader sees those words.  Dropping it would turn a quote a reader can
  see into `quote-missing` - the expensive direction.
* `<title>` is printed by the browser in the tab and the window bar.  It is not
  page prose, and it is not invisible either, so it stays.
* `<datalist>`'s `<option>`s are painted the moment a reader opens the list, and
  `hidden="until-found"` is painted the moment the page is searched.  Both are
  reachable words, so both stay - the same reasoning that keeps `<noscript>` out
  of the inert list.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from citevouch import sources
from citevouch.cli import main

NL = chr(10)
B3 = "`" * 3
QUOTE = "We collected 40,688 examples from the corpus."


def project(tmp_path: Path, html: str) -> Path:
    """A one-claim project whose only source is this HTML."""
    (tmp_path / "page.html").write_text(html, encoding="utf-8", newline=NL)
    (tmp_path / "sources.toml").write_text(
        "[sources]" + NL + 'web = "page.html"' + NL, encoding="utf-8", newline=NL
    )
    manuscript = tmp_path / "m.md"
    manuscript.write_text(
        B3 + "claim id=c1 source=web" + NL + "quote: |" + NL + "  " + QUOTE + NL + B3 + NL,
        encoding="utf-8",
        newline=NL,
    )
    return manuscript


def verdict(tmp_path: Path, html: str) -> int:
    manuscript = project(tmp_path, html)
    main(["scan", str(manuscript), "--root", str(tmp_path)])
    return main(["verify", str(manuscript), "--root", str(tmp_path)])


class TestAnElementTheBrowserDoesNotPaint:
    """Three ways to say "paint nothing here", all of them binding."""

    @pytest.mark.parametrize(
        "style",
        [
            "display:none",
            "display: none",
            "DISPLAY: NONE",
            "color:red; display:none",
            "display:none; color:red",
            "visibility:hidden",
            "visibility: hidden",
        ],
    )
    def test_a_style_that_hides_the_element_takes_its_text(self, style: str):
        stripped = sources._strip_markup(
            f'<p>before</p><div style="{style}">{QUOTE}</div><p>after</p>'
        )
        assert QUOTE not in stripped
        assert "before" in stripped and "after" in stripped

    @pytest.mark.parametrize("attribute", ["hidden", 'hidden=""', 'hidden="hidden"', "HIDDEN"])
    def test_the_hidden_attribute_takes_its_text(self, attribute: str):
        stripped = sources._strip_markup(f"<p>before</p><p {attribute}>{QUOTE}</p><p>after</p>")
        assert QUOTE not in stripped
        assert "before" in stripped and "after" in stripped

    def test_the_attribute_value_may_use_single_quotes(self):
        stripped = sources._strip_markup(f"<div style='display:none'>{QUOTE}</div><p>after</p>")
        assert QUOTE not in stripped
        assert "after" in stripped

    def test_an_unquoted_attribute_value_is_read_too(self):
        stripped = sources._strip_markup(f"<div style=display:none>{QUOTE}</div><p>after</p>")
        assert QUOTE not in stripped
        assert "after" in stripped


class TestTheWholeElementGoesNotJustItsText:
    """The element's subtree is unpainted, so nesting inside it goes too."""

    def test_a_nested_element_inside_the_hidden_one_is_dropped(self):
        stripped = sources._strip_markup(
            f'<div style="display:none"><p>{QUOTE}</p><div>and more</div></div><p>after</p>'
        )
        assert QUOTE not in stripped
        assert "and more" not in stripped
        assert "after" in stripped

    def test_a_sibling_inside_the_hidden_element_does_not_escape(self):
        """The bug a naive "first closing tag" rule leaves behind."""
        stripped = sources._strip_markup(
            f'<div style="display:none"><div>inner</div>{QUOTE}</div><p>after</p>'
        )
        assert "inner" not in stripped
        assert QUOTE not in stripped
        assert "after" in stripped

    def test_the_text_after_the_hidden_element_is_kept(self):
        stripped = sources._strip_markup(
            f'<div style="display:none">{QUOTE}</div><p>kept sentence</p>'
        )
        assert QUOTE not in stripped
        assert "kept sentence" in stripped

    def test_an_unclosed_hidden_element_runs_to_the_end(self):
        """A truncated save loses the rest, which is what a browser shows."""
        stripped = sources._strip_markup(f'<p>intro</p><div style="display:none">{QUOTE}')
        assert QUOTE not in stripped
        assert "intro" in stripped


class TestWhatIsStillPainted:
    """A style that paints, and an attribute that is not about painting."""

    @pytest.mark.parametrize(
        "style",
        [
            "display:block",
            "display:inline",
            "visibility:visible",
            "color:red",
            "display:none-ish",
        ],
    )
    def test_an_ordinary_style_leaves_the_text_alone(self, style: str):
        stripped = sources._strip_markup(f'<div style="{style}">{QUOTE}</div>')
        assert QUOTE in stripped

    def test_aria_hidden_is_not_hidden_from_a_reader(self):
        """`aria-hidden` speaks to assistive tech; the text is still painted."""
        stripped = sources._strip_markup(f"<span aria-hidden='true'>{QUOTE}</span>")
        assert QUOTE in stripped

    def test_the_title_is_left_alone(self):
        """Printed in the tab and the window bar, so not invisible either."""
        stripped = sources._strip_markup(f"<html><head><title>{QUOTE}</title></head></html>")
        assert QUOTE in stripped

    def test_a_datalist_option_is_left_alone(self):
        """Painted when the reader opens the list, so a reader can reach it."""
        stripped = sources._strip_markup(
            f"<p>before</p><datalist><option>{QUOTE}</option></datalist>"
        )
        assert QUOTE in stripped

    def test_a_hidden_element_that_html_will_reveal_on_search_is_kept(self):
        """`hidden="until-found"` is rendered when a reader searches the page."""
        stripped = sources._strip_markup(f'<div hidden="until-found">{QUOTE}</div>')
        assert QUOTE in stripped

    def test_the_words_of_the_style_attribute_are_not_page_text(self):
        stripped = sources._strip_markup('<p style="display:none">kept?</p>')
        assert "display" not in stripped
        assert "kept?" not in stripped

    @pytest.mark.parametrize(
        "tag",
        [
            '<div title="hidden">',
            '<div data-hidden="true">',
            '<div class="hidden">',
            '<div id="hidden">',
            '<div aria-label="hidden">',
        ],
    )
    def test_the_word_hidden_in_an_attribute_is_not_the_attribute(self, tag: str):
        """A `\\bhidden\\b` search found the word in five places that are not it.

        Measured while writing this: `title="hidden"` dropped the element's
        whole subtree, so a sentence a sighted reader sees on the page came
        back `quote-missing`.  An attribute is a name at the start of a token,
        and reading it that way is the difference between the two.
        """
        stripped = sources._strip_markup(f"<p>before</p>{tag}{QUOTE}</div><p>after</p>")
        assert QUOTE in stripped
        assert "before" in stripped and "after" in stripped

    def test_a_void_element_that_is_hidden_hides_nothing_else(self):
        """`<img hidden>` has no end tag; searching for one ate the document."""
        stripped = sources._strip_markup(f'<p>before</p><img hidden src="x.png"><p>{QUOTE}</p>')
        assert QUOTE in stripped
        assert "before" in stripped


class TestTheVerdictOnAProject:
    """The end-to-end failure: a quote nobody can see comes back verified."""

    @pytest.mark.parametrize(
        "fragment",
        [
            f'<div style="display:none">{QUOTE}</div>',
            f'<div style="visibility:hidden">{QUOTE}</div>',
            f"<p hidden>{QUOTE}</p>",
        ],
    )
    def test_a_quote_that_only_exists_behind_a_style_is_not_verified(
        self, tmp_path: Path, fragment: str
    ):
        code = verdict(tmp_path, f"<p>an unrelated sentence</p>{fragment}")
        assert code == 1

    def test_prose_outside_the_hidden_element_still_verifies(self, tmp_path: Path):
        code = verdict(tmp_path, f'<div style="display:none">x</div><p>{QUOTE}</p>')
        assert code == 0
