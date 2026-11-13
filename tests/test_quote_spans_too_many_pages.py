"""A quote longer than the stitcher reaches is not a quote that is absent.

`_page_runs` reads at most `MAX_STITCHED_PAGES` pages at a time.  A quotation
spanning more breaks than that was never compared against anything - and the
run still said `[high] quote-missing`, which is the sentence that accuses the
author of inventing a quotation.  Measured, on a source of six pages carrying
one sentence quoted verbatim across all six:

    [high] quote-missing at m.md:1 (c1): alpha beta gamma ... - quote not found in paper.txt

while the same words, with the page breaks flattened to spaces, are found by
`str.find`.  That is a verdict about this tool's reach written as a verdict
about the manuscript, which is the one thing this project must never do.

The fix is a third answer, not a better yes/no: `quote-spans-too-many-pages`,
counted as *skipped*.  It claims only what is true - the quote begins on one
page and ends on another, further apart than one run reads - and it names what
would settle it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NL = chr(10)
FF = chr(12)
B3 = chr(96) * 3

WORDS = (
    "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi "
    "omicron pi rho sigma tau upsilon phi chi psi omega"
).split()


def _pages(count: int) -> list[str]:
    """`count` pages whose texts, joined by single spaces, read as one sentence."""
    size = max(1, len(WORDS) // count)
    chunks = [WORDS[i * size : (i + 1) * size] for i in range(count)]
    chunks[-1] = WORDS[(count - 1) * size :]
    return [" ".join(chunk) for chunk in chunks]


def _project(tmp_path: Path, count: int) -> tuple[Path, str]:
    root = tmp_path / "proj"
    root.mkdir()
    pages = _pages(count)
    (root / "paper.txt").write_text(FF.join(pages) + NL, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "paper.txt"' + NL, encoding="utf-8", newline=NL
    )
    quote = " ".join(pages)
    (root / "m.md").write_text(
        B3 + "claim id=c1 source=paper" + NL + "quote: |" + NL + "  " + quote + NL + B3 + NL,
        encoding="utf-8",
        newline=NL,
    )
    return root, quote


def _run(root: Path, *argv: str) -> tuple[int, str]:
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "PYTHONIOENCODING": "utf-8",
    }
    proc = subprocess.run(
        [sys.executable, "-m", "citevouch", *argv],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout + proc.stderr


def _line_with(text: str, marker: str) -> str:
    for line in text.splitlines():
        if marker in line:
            return line
    raise AssertionError(f"no line contains {marker!r}:{NL}{text}")


class TestAQuoteLongerThanTheStitcher:
    @pytest.mark.parametrize("count", [5, 6, 8])
    def test_it_is_not_reported_missing(self, tmp_path: Path, count: int) -> None:
        root, _quote = _project(tmp_path, count)
        code, out = _run(root, "check", "m.md")
        assert code == 1
        assert "quote-spans-too-many-pages" in out, out
        assert "quote-missing" not in out, out
        assert "quote-fuzzy" not in out, out

    def test_it_counts_as_skipped_rather_than_missing(self, tmp_path: Path) -> None:
        """The tally is the sentence most readers read.

        A run that says `1 missing` has told the author their quote is absent,
        whatever the finding above it says; `1 skipped` says the tool did not
        decide.  `source-unreadable` is counted the same way for the same
        reason.
        """
        root, _quote = _project(tmp_path, 6)
        _code, out = _run(root, "check", "m.md")
        summary = _line_with(out, "citevouch:")
        assert "0 missing" in summary, summary
        assert "1 skipped" in summary, summary

    def test_the_message_names_both_ends_and_the_limit(self, tmp_path: Path) -> None:
        from citevouch.matching import MAX_STITCHED_PAGES

        root, _quote = _project(tmp_path, 6)
        _code, out = _run(root, "check", "m.md")
        line = _line_with(out, "quote-spans-too-many-pages")
        assert "begins on page 1" in line, line
        assert "ends on page 6" in line, line
        assert str(MAX_STITCHED_PAGES) in line, line

    def test_it_says_the_quote_was_never_compared(self, tmp_path: Path) -> None:
        """The severity is high, so the sentence has to say why that is fair."""
        root, _quote = _project(tmp_path, 6)
        _code, out = _run(root, "check", "m.md")
        line = _line_with(out, "quote-spans-too-many-pages")
        assert "never compared" in line, line


class TestWhatMustStillSayMissing:
    def test_a_quote_the_source_does_not_hold(self, tmp_path: Path) -> None:
        """The new answer must not become a blanket excuse for anything absent."""
        root, _quote = _project(tmp_path, 6)
        (root / "m.md").write_text(
            B3
            + "claim id=c1 source=paper"
            + NL
            + "quote: |"
            + NL
            + "  This sentence appears in no source file at all, not even partly."
            + NL
            + B3
            + NL,
            encoding="utf-8",
            newline=NL,
        )
        code, out = _run(root, "check", "m.md")
        assert code == 1
        assert "quote-missing" in out, out
        assert "quote-spans-too-many-pages" not in out, out
        assert "1 missing" in _line_with(out, "citevouch:")

    def test_a_quote_that_fits_in_the_limit_is_still_found(self, tmp_path: Path) -> None:
        """Up to the limit the stitcher works, so this tier must not fire."""
        root, _quote = _project(tmp_path, 4)
        code, out = _run(root, "check", "m.md")
        assert code == 0
        assert "quote-found" in out, out
        assert "running onto pages 2, 3 and 4" in out, out
        assert "quote-spans-too-many-pages" not in out, out

    def test_a_single_page_quote_is_untouched(self, tmp_path: Path) -> None:
        root, _quote = _project(tmp_path, 1)
        code, out = _run(root, "check", "m.md")
        assert code == 0
        assert "quote found on page 1" in out, out


class TestTheDetectorItself:
    def test_it_returns_both_ends(self) -> None:
        from citevouch.matching import _whole_document_span
        from citevouch.sources import PageText

        pages = [PageText(number=i + 1, text=t) for i, t in enumerate(_pages(6))]
        quote = " ".join(_pages(6))
        from citevouch.textnorm import fold

        assert _whole_document_span(fold(quote), pages) == (1, 6)

    def test_it_declines_when_the_quote_is_not_there(self) -> None:
        from citevouch.matching import _whole_document_span
        from citevouch.sources import PageText
        from citevouch.textnorm import fold

        pages = [PageText(number=i + 1, text=t) for i, t in enumerate(_pages(6))]
        assert _whole_document_span(fold("nothing on these pages at all"), pages) is None

    def test_it_declines_when_the_quote_fits_the_stitcher(self) -> None:
        """A quote the stitcher did compare keeps its own verdict.

        Without this rule every miss in a long document would be excused as
        "too many page breaks", and the tier would swallow the ordinary
        `quote-missing` - the one sentence this project exists to make honest.
        Eight pages, but the quote only covers two of them, well inside the
        stitcher's reach, so the stitcher has already tried and failed.
        """
        from citevouch.matching import _whole_document_span
        from citevouch.sources import PageText
        from citevouch.textnorm import fold

        pages = [PageText(number=i + 1, text=t) for i, t in enumerate(_pages(4))]
        quote = " ".join(t.text for t in pages[2:4])
        assert _whole_document_span(fold(quote), pages + pages) is None

    def test_it_counts_pages_read_not_page_numbers_printed(self) -> None:
        """The stitcher counts pages of the file, not the numbers in the margin.

        An extractor that leaves gaps in the numbering (a scanned front matter,
        a two-up spread) makes "page 11 minus page 1" a different number from
        "how many pages the stitcher had to join".  The rule has to be written
        in the currency the stitcher spends, or it will excuse a quote the
        stitcher did compare.
        """
        from citevouch.matching import _whole_document_span
        from citevouch.sources import PageText
        from citevouch.textnorm import fold

        numbers = [1, 2, 3, 10, 11]
        texts = _pages(len(numbers))
        pages = [
            PageText(number=number, text=text)
            for number, text in zip(numbers, texts, strict=True)
        ]
        quote = " ".join(texts[:4])
        assert _whole_document_span(fold(quote), pages) is None
        assert _whole_document_span(fold(" ".join(texts)), pages) == (1, 11)
