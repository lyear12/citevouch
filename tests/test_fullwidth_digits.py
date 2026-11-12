"""One page, one sentence: two answers that could not both be right.

A page printed ``４０，６８８`` - the fullwidth spelling of forty thousand six
hundred and eighty-eight - and a manuscript quoted it as ``40,688``.  Both
spellings denote one value, and the matcher said so: it compares *folded*
text, and NFKC turns the fullwidth digits and comma into the ASCII ones, so the
quote was found on the page and the run printed ``[info] quote-found``.

The number readers, though, were reading a different string.  ``_page_numbers``
scanned the page's **raw** text with ``CANON_PATTERN``, whose thousands
separators are ``,`` and a few spaces - the fullwidth comma is not among them -
so the page's one number came back as two, ``４０`` and ``６８８``.  Folded, those
are ``40`` and ``688``, and neither equals the quote's ``40688``.  The same run
therefore also printed::

    [high] number-absent-in-quote at m.md:3 (c1): the quote says 40,688 but
    page 1 of the source does not contain that number

about a number the reader can see, on the page, in the sentence the tool had
just certified.  One sentence, one page, two opposite verdicts, and one of them
was the accusation this project exists to get right.

The fix is a shared reading rather than two private ones: ``textnorm.fold_number_forms``
folds every character that *is* a digit or a group separator and changes nothing
about layout, and every number reader - ``quote_numbers``, ``numbers_in``,
``matching.mask_numbers``, ``matching.number_spans``, ``verify._page_numbers`` -
now reads through it.  ``fold`` itself would have been too much: it collapses
whitespace, and a collapsed line break turns two numbers into one.

These tests pin the shared reading, the end-to-end silence it buys, and the two
things it must not break: a bare space is still a thousands group at most once
(so ``2019 2020 2021`` is three years), and the whitespace offsets the number
spans carry are unchanged.
"""

from __future__ import annotations

import contextlib
import io
from pathlib import Path

import pytest

from citevouch import textnorm
from citevouch.cli import main
from citevouch.matching import find_in_pages, mask_numbers, number_spans
from citevouch.sources import PageText
from citevouch.textnorm import quote_numbers
from citevouch.verify import _page_numbers

#: ``４０，６８８`` - fullwidth digits and a fullwidth comma.
FULL = "\uff14\uff10\uff0c\uff16\uff18\uff18"
#: ``٤٠٬٦٨٨`` - Arabic-Indic digits with the Arabic thousands separator.
ARABIC = "\u0664\u0660\u066c\u0666\u0668\u0668"
ASCII = "40,688"
QUOTE = f"We collected {ASCII} examples from the corpus."


def _project(tmp_path: Path, page: str, quote: str) -> Path:
    (tmp_path / "page.txt").write_text(page, encoding="utf-8", newline="\n")
    (tmp_path / "sources.toml").write_text(
        '[sources]\npage = "page.txt"\n', encoding="utf-8", newline="\n"
    )
    (tmp_path / "m.md").write_text(
        f"```claim id=c1 source=page page=1\nquote: |\n  {quote}\nclaim: |\n  {quote}\n```\n",
        encoding="utf-8",
        newline="\n",
    )
    return tmp_path


def _run(root: Path) -> tuple[str, int]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = main(["check", "m.md", "--root", str(root)])
    return buf.getvalue(), code


class TestTheReadersAgreeOnTheNumber:
    """Every number reader sees the value; the spelling is not the value."""

    def test_the_separator_pattern_reads_it_as_one_number(self):
        assert _page_numbers(FULL) == (ASCII,)

    def test_the_quote_reader_reads_it_as_one_number(self):
        assert quote_numbers(FULL) == (ASCII,)

    def test_the_report_reader_reads_it_as_one_number(self):
        assert textnorm.numbers_in(FULL) == (ASCII,)

    def test_the_masker_reads_it_as_one_number(self):
        masked = mask_numbers(FULL)
        assert masked.count("\x00") == 1
        assert "\uff0c" not in masked

    def test_the_span_reader_reads_it_as_one_number(self):
        assert number_spans(FULL) == [(ASCII, 0)]

    def test_the_readers_agree_with_each_other(self):
        assert (
            _page_numbers(FULL)
            == quote_numbers(FULL)
            == textnorm.numbers_in(FULL)
            == tuple(token for token, _ in number_spans(FULL))
        )

    def test_the_arabic_indic_separator_is_a_separator_too(self):
        # NFKC leaves Arabic-Indic digits as they are - they are not a
        # compatibility spelling of ASCII - so the readers keep the page's
        # spelling and compare it by value instead.  Both readers must still
        # agree about where the number starts and stops.
        assert quote_numbers(ARABIC) == (ARABIC,)
        assert _page_numbers(ARABIC) == (ARABIC,)
        assert quote_numbers(ARABIC) == _page_numbers(ARABIC)
        assert textnorm.canonical_number(ARABIC) == textnorm.canonical_number(ASCII)


class TestTheSentenceThatWasCalledBothFoundAndAbsent:
    """The end-to-end run that used to contradict itself in two lines."""

    @pytest.mark.parametrize(
        ("page", "quote"),
        [
            (f"We collected {FULL} examples from the corpus.", QUOTE),
            (QUOTE, f"We collected {FULL} examples from the corpus."),
            (
                f"We collected {FULL} examples from the corpus.",
                f"We collected {FULL} examples from the corpus.",
            ),
        ],
    )
    def test_one_value_written_two_ways_is_one_verdict(self, tmp_path, page, quote):
        out, code = _run(_project(tmp_path, page, quote))
        assert "quote-found" in out
        assert "number-absent-in-quote" not in out
        assert "quote-missing" not in out
        assert code == 0

    def test_the_arabic_indic_spelling_is_the_same_number(self, tmp_path):
        page = f"We collected {ARABIC} examples from the corpus."
        out, code = _run(_project(tmp_path, page, QUOTE))
        assert "quote-found" in out
        assert "number-absent-in-quote" not in out
        assert code == 0

    def test_a_page_that_really_lacks_the_number_still_says_so(self, tmp_path):
        page = f"We collected {FULL} examples from the corpus."
        out, code = _run(
            _project(tmp_path, page, "We collected 9,800 examples from the corpus.")
        )
        assert "number-absent-in-quote" in out
        assert "9,800" in out
        assert code == 1


class TestTheNumbersTierStillKnowsWhereTheNumberIs:
    """The tier that matches numbers by position kept working through the fold."""

    def test_the_tier_records_the_number_the_page_prints(self):
        page = PageText(number=1, text=f"We collected {FULL} examples for training.")
        match = find_in_pages("We collected 9,800 examples for training.", [page])
        assert match is not None
        assert match.page_numbers == (ASCII,)

    def test_the_folded_number_is_what_the_tier_quotes_back(self):
        page = PageText(number=1, text=f"We collected {FULL} examples for training.")
        match = find_in_pages("We collected 9,800 examples for training.", [page])
        assert match is not None
        assert match.page_numbers == (ASCII,)

    def test_a_number_in_another_sentence_is_named_as_elsewhere(self, tmp_path):
        page = (
            f"We collected {FULL} examples for training. "
            "The held-out set of \uff19\uff0c\uff18\uff10\uff10 rolesets was annotated separately."
        )
        out, code = _run(_project(tmp_path, page, "We collected 9,800 examples for training."))
        assert "number-not-in-passage" in out
        assert "9,800" in out
        assert ASCII in out
        assert code == 1


class TestWhatTheSharedReadingMustNotChange:
    """Folding digits is not folding layout."""

    def test_a_line_break_is_not_collapsed(self):
        assert textnorm.fold_number_forms("a\nb  40 688") == "a\nb  40 688"

    def test_a_line_break_keeps_two_numbers_apart(self):
        # ``fold`` would turn this newline into a space and make one number of
        # two, which is exactly why the readers use ``fold_number_forms`` instead.
        assert _page_numbers("We collected 40\n688 examples") == ("40", "688")
        assert _page_numbers("We collected 40 688 examples") == ("40 688",)
        assert mask_numbers("40\n688").count("\x00") == 2
        assert mask_numbers("40 688").count("\x00") == 1

    def test_the_offsets_do_not_move(self):
        (token, start) = number_spans(f"{FULL} and more")[0]
        assert start == 0
        assert token == ASCII

    def test_three_years_are_three_numbers(self):
        assert textnorm.numbers_in("2019 2020 2021") == ("2019", "2020", "2021")

    def test_a_bare_space_is_still_a_thousands_group(self):
        assert mask_numbers("1 000").count("\x00") == 1
        assert [token for token, _ in number_spans("1 000")] == ["1 000"]

    def test_the_quote_reader_keeps_the_wide_separator_rule(self):
        # ``quote_numbers`` reads with ``CANON_PATTERN`` (a space may join a
        # thousands group) and ``numbers_in`` with ``REPORT_PATTERN`` (it may
        # not, because "2019 2020 2021" is three years).  The two must stay
        # distinguishable: sharing the fold is not the same as sharing the
        # pattern.
        assert quote_numbers("40 688") == ("40 688",)
        assert textnorm.numbers_in("40 688") == ("40", "688")

    def test_a_zero_width_space_inside_a_number_is_not_a_separator(self):
        # A PDF that breaks a line inside a number leaves a zero-width space
        # behind; without ``strip_format`` the reader would see ``40`` and
        # ``688`` - the same split the fullwidth comma caused.
        glued = "40\u200b,688"
        assert textnorm.fold_number_forms(glued) == ASCII
        assert _page_numbers(glued) == (ASCII,)

    def test_an_empty_string_stays_empty(self):
        assert textnorm.fold_number_forms("") == ""

    def test_text_without_digits_is_returned_unchanged(self):
        assert textnorm.fold_number_forms("The grammar is large.") == "The grammar is large."
