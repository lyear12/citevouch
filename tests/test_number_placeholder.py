"""The character that stands for a number was a character a page can contain.

The matcher finds a quote containing numbers by blanking every number out and
comparing the blanks, and the blank it writes is ``"\\x00"``.  The numbers tier
then has to answer a second question - *which* number did the page print at that
spot - and it answers it by counting blanks: the blanks before the match say how
many numbers the page printed earlier, and the blanks inside the match say how
many belong to the passage.  ``_numbers_under`` is that count.

That arithmetic assumes a blank means a number.  A NUL byte in the page text
breaks the assumption silently: PDF extraction does keep them - six pages among
the first 250 PDFs of one real corpus carry a NUL - and a NUL anywhere before
the match added one to the count, shifting every slot by one number.  On a page
reading::

    A footnote says 9,800 somewhere.\\x00We collected 9,801 examples from the
    corpus. Then 7 more.

and a manuscript quoting ``We collected 9,800 examples from the corpus.`` the
run printed::

    [high] number-not-in-passage at m.md:1 (c1): the quote says 9,800 where
    page 1 prints 7; that number is on the page, but not in this passage

The page prints ``9,801`` in the very sentence the quote came from; the ``7`` is
two sentences later.  The same page without the NUL reported ``9,801``.  So the
verdict depended on a character no reader can see, and it accused the author of
misstating a figure they had copied correctly.

The fix is small on purpose: the placeholder is removed from the text before it
is masked (``matching._without_the_placeholder``), so a blank is written only
where a number was.  A NUL is an extraction artefact, not something the page
says, and the masker already folds away other characters that are not text.

These tests pin the count, both ends of the end-to-end verdict, and the things
that must not change: one blank per number, ``2019 2020 2021`` still three
numbers, and a bare space still a thousands group at most once.
"""

from __future__ import annotations

import contextlib
import io
from pathlib import Path

from citevouch.cli import main
from citevouch.matching import _numbers_under, mask_numbers, number_spans
from citevouch.textnorm import numbers_in, quote_numbers

#: A page that prints the quote's number, but one NUL earlier than the passage.
NUL_PAGE = (
    "A footnote says 9,800 somewhere.\x00"
    "We collected 9,801 examples from the corpus. Then 7 more.\n"
)
#: The same page with the artefact removed.  It is the reference answer.
CLEAN_PAGE = NUL_PAGE.replace("\x00", "")
#: The quote whose number is on the page, in the sentence it came from.
QUOTE = "We collected 9,800 examples from the corpus."


def _project(tmp_path: Path, page: str, quote: str = QUOTE) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "page.txt").write_bytes(page.encode("utf-8"))
    (tmp_path / "sources.toml").write_text(
        '[sources]\npaper = "page.txt"\n', encoding="utf-8", newline="\n"
    )
    (tmp_path / "m.md").write_text(
        f"```claim id=c1 source=paper\nquote: |\n  {quote}\n```\n",
        encoding="utf-8",
        newline="\n",
    )
    return tmp_path


def _run(root: Path) -> tuple[str, int]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = main(["check", "m.md", "--root", str(root)])
    return buf.getvalue(), code


class TestABlankMeansANumber:
    """The masker writes a blank for a number, and for nothing else."""

    def test_a_nul_is_not_a_number(self):
        assert mask_numbers("a\x00b") == "ab"

    def test_a_nul_does_not_add_a_blank(self):
        assert mask_numbers("\x00\x00 40,688").count("\x00") == 1

    def test_the_page_with_the_artefact_masks_the_same_way(self):
        assert mask_numbers(NUL_PAGE) == mask_numbers(CLEAN_PAGE)

    def test_the_spans_are_the_same_spans(self):
        assert number_spans(NUL_PAGE) == number_spans(CLEAN_PAGE)

    def test_the_spans_still_say_what_the_numbers_are(self):
        assert [token for token, _ in number_spans(CLEAN_PAGE)] == [
            "9,800",
            "9,801",
            "7",
        ]


class TestTheCountLandsOnTheRightNumber:
    """``_numbers_under`` is the reader the numbers tier reports from."""

    def test_the_passage_gets_its_own_number(self):
        assert _numbers_under(CLEAN_PAGE, 1, 1) == ("9,801",)

    def test_the_artefact_does_not_shift_the_count(self):
        assert _numbers_under(NUL_PAGE, 1, 1) == _numbers_under(CLEAN_PAGE, 1, 1)

    def test_the_first_number_is_still_the_first(self):
        assert _numbers_under(NUL_PAGE, 0, 1) == ("9,800",)

    def test_the_last_number_is_still_the_last(self):
        assert _numbers_under(NUL_PAGE, 2, 1) == ("7",)

    def test_a_count_past_the_end_returns_nothing(self):
        assert _numbers_under(NUL_PAGE, 3, 1) == ()


class TestTheVerdictDoesNotDependOnAnInvisibleCharacter:
    """Same page, same quote, one NUL apart: the same sentence must come out."""

    def test_it_names_the_number_the_page_prints(self, tmp_path):
        out, code = _run(_project(tmp_path, NUL_PAGE))
        assert code == 1
        assert "number-not-in-passage" in out
        assert "prints 9,801" in out
        assert "prints 7" not in out

    def test_the_clean_page_says_the_same_thing(self, tmp_path):
        out, code = _run(_project(tmp_path, CLEAN_PAGE))
        assert code == 1
        assert "prints 9,801" in out

    def test_the_two_pages_produce_the_same_report(self, tmp_path):
        first = _run(_project(tmp_path / "a", NUL_PAGE))
        second = _run(_project(tmp_path / "b", CLEAN_PAGE))
        assert first == second

    def test_a_number_the_page_lacks_is_still_reported(self, tmp_path):
        page = "We collected 9,802 examples from the corpus.\x00 Then 7 more.\n"
        out, code = _run(_project(tmp_path, page))
        assert code == 1
        assert "number-absent-in-quote" in out
        assert "the quote says 9,800" in out


class TestWhatTheMaskerMustNotChange:
    """Removing one character must not change how numbers are counted."""

    def test_a_fullwidth_number_is_still_one_number(self):
        assert mask_numbers("\uff14\uff10\uff0c\uff16\uff18\uff18").count("\x00") == 1

    def test_three_years_are_still_three_numbers(self):
        assert numbers_in("2019 2020 2021") == ("2019", "2020", "2021")

    def test_a_bare_space_is_still_a_thousands_group(self):
        assert mask_numbers("1 000").count("\x00") == 1

    def test_the_quote_reader_is_untouched(self):
        assert quote_numbers("40 688") == ("40 688",)

    def test_no_numbers_means_no_blanks(self):
        assert mask_numbers("the grammar is large") == "the grammar is large"

    def test_a_nul_inside_a_number_joins_the_digits(self):
        """Measured, and the charitable direction: one number, not two.

        Removing an artefact that fell inside a number leaves the digits
        adjacent, so the page is read as printing one number.  The other
        reading - two numbers, ``40`` and ``688`` - would accuse a manuscript
        quoting ``40,688`` of a figure the page does not print, and this tool
        does not accuse on the strength of an extraction artefact.
        """
        assert mask_numbers("40\x00688").count("\x00") == 1
        assert [token for token, _ in number_spans("40\x00688")] == ["40688"]
