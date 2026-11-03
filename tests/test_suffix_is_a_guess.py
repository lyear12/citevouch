"""A PDF named ``.txt`` is read as text, and the run accuses the quote.

Measured before the fix, on the demo paper copied to ``real.txt``:

* ``extract_pages`` returned **4 pages / 206,870 characters** of mojibake and
  ``problem=None`` - the plain-text reader had decoded the PDF's bytes;
* ``citevouch check`` on a manuscript quoting the paper's own sentence printed
  ``[high] quote-missing ... no passage in the source is close to this quote in
  real.txt`` and exited 1.

The suffix is the author's statement about the format, and the tool reads what
it is told to read.  But this tool *owns* a PDF reader: when the file's own
first bytes say ``%PDF-``, using that reader is strictly more capable than
decoding the same bytes as UTF-8, and it can never turn a true text file into a
false accusation - the worst it can do is refuse honestly.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from citevouch import sources

ROOT = Path(__file__).resolve().parent.parent
DEMO_PDF = ROOT / "demo" / "papers" / "2026_VanEecke-Beuls_CoNLL2026_large-scale-CxG.pdf"
QUOTE = "The resulting grammar consists of a network of 40,688 constructions"


class TestTheBytesKnowBetterThanTheSuffix:
    @pytest.mark.parametrize("suffix", [".txt", ".md", ".text", ".html", ".htm", ".xml"])
    def test_a_pdf_with_a_text_suffix_is_read_by_the_pdf_reader(
        self, tmp_path: Path, suffix: str
    ):
        path = tmp_path / f"paper{suffix}"
        path.write_bytes(DEMO_PDF.read_bytes())
        pages, problem = sources.extract_pages(path, tmp_path, use_cache=False)
        assert problem is None
        assert len(pages) > 5
        # The paper's real prose, not the PDF syntax spelled as characters.
        assert any("construction" in page.text for page in pages)

    def test_the_quote_is_found_again(self, tmp_path: Path):
        # The paper wraps this sentence across two lines, so the words are
        # compared as they appear rather than as one string: what is being
        # tested is that the real prose came out at all, not the line breaks
        # the typesetter chose.
        path = tmp_path / "paper.txt"
        path.write_bytes(DEMO_PDF.read_bytes())
        pages, problem = sources.extract_pages(path, tmp_path, use_cache=False)
        assert problem is None
        assert any(
            "The resulting grammar consists of a network of" in page.text
            and "40,688 constructions" in page.text
            for page in pages
        )

    def test_a_pdf_named_txt_is_not_mojibake(self, tmp_path: Path):
        path = tmp_path / "paper.txt"
        path.write_bytes(DEMO_PDF.read_bytes())
        pages, problem = sources.extract_pages(path, tmp_path, use_cache=False)
        assert problem is None
        text = "".join(page.text for page in pages)
        assert "%PDF-" not in text
        assert len(text) < 200_000


class TestWhatStillReadsAsItDid:
    def test_a_plain_text_file_is_untouched(self, tmp_path: Path):
        path = tmp_path / "notes.txt"
        path.write_text(QUOTE + "\n", encoding="utf-8", newline="\n")
        pages, problem = sources.extract_pages(path, tmp_path, use_cache=False)
        assert problem is None
        assert QUOTE in pages[0].text

    def test_a_real_pdf_is_untouched(self, tmp_path: Path):
        pages, problem = sources.extract_pages(DEMO_PDF, tmp_path, use_cache=False)
        assert problem is None
        assert len(pages) > 5

    def test_text_that_merely_starts_with_the_word_is_refused_not_accused(self, tmp_path: Path):
        # The only file this rule can hurt: text whose first bytes spell the PDF
        # header.  It gets an honest "cannot read this" instead of being handed
        # to the matcher, which is the right direction - a refusal makes the
        # author look, a false `quote-missing` makes them doubt their own quote.
        path = tmp_path / "notes.txt"
        path.write_text("%PDF- is a header, and this is a note about it\n", encoding="utf-8")
        pages, problem = sources.extract_pages(path, tmp_path, use_cache=False)
        assert pages == []
        assert problem is not None
        assert problem.code == "source-unreadable"

    def test_a_pdf_suffixed_file_is_read_the_same_way_either_route(self, tmp_path: Path):
        # Sniffing a file that already says `.pdf` would be work with no effect,
        # and an effect it *could* have is a bug: the header check reads five
        # bytes and the PDF reader is chosen for both inputs, so the pages have
        # to match.  Asserting the equality is what makes "read it again" and
        # "read it only when the suffix disagrees" the same behaviour here.
        sniffed = tmp_path / "disguised.txt"
        sniffed.write_bytes(DEMO_PDF.read_bytes())
        named = tmp_path / "honest.pdf"
        named.write_bytes(DEMO_PDF.read_bytes())
        from_txt, first = sources.extract_pages(sniffed, tmp_path, use_cache=False)
        from_pdf, second = sources.extract_pages(named, tmp_path, use_cache=False)
        assert first is None and second is None
        assert [page.text for page in from_txt] == [page.text for page in from_pdf]

    def test_the_header_must_be_the_start_of_the_file(self, tmp_path: Path):
        # A text file that *mentions* a PDF, or a tar of PDFs, is not a PDF.
        # Searching the whole file for the header would claim it was, and then
        # the PDF reader would refuse a file that used to read fine.
        path = tmp_path / "notes.txt"
        path.write_text(
            "These notes are about a PDF.\n\n%PDF-1.7 is what one starts with.\n",
            encoding="utf-8",
            newline="\n",
        )
        pages, problem = sources.extract_pages(path, tmp_path, use_cache=False)
        assert problem is None
        assert pages[0].text.startswith("These notes")

    def test_a_short_file_is_not_mistaken_for_a_pdf(self, tmp_path: Path):
        # `startswith(b"%PDF")` would accept a five-byte file, and then the PDF
        # reader would be handed something that is not a document.
        path = tmp_path / "tiny.txt"
        path.write_text("%PDF", encoding="utf-8", newline="\n")
        pages, problem = sources.extract_pages(path, tmp_path, use_cache=False)
        assert problem is None
        assert pages[0].text == "%PDF"


class TestTheCacheDoesNotHandBackTheOldReading:
    def test_the_garbage_is_not_reused_from_a_cache_entry(self, tmp_path: Path):
        path = tmp_path / "paper.txt"
        path.write_bytes(DEMO_PDF.read_bytes())
        first, problem = sources.extract_pages(path, tmp_path, use_cache=True)
        assert problem is None
        second, problem = sources.extract_pages(path, tmp_path, use_cache=True)
        assert problem is None
        assert [page.text for page in first] == [page.text for page in second]
        assert second[0].text == first[0].text


def _project(tmp_path: Path) -> Path:
    (tmp_path / "manuscript.md").write_text(
        f"Intro.\n\n```claim id=c1 source=paper page=6\nquote: |\n  {QUOTE}\n```\n",
        encoding="utf-8",
        newline="\n",
    )
    (tmp_path / "sources.toml").write_text(
        '[sources]\npaper = "paper.txt"\n', encoding="utf-8", newline="\n"
    )
    (tmp_path / "paper.txt").write_bytes(DEMO_PDF.read_bytes())
    return tmp_path


class TestTheVerdictOnAProject:
    def test_the_command_finds_the_quote_it_could_not_see(self, tmp_path: Path):
        root = _project(tmp_path)
        done = subprocess.run(
            [sys.executable, "-m", "citevouch", "check", "manuscript.md"],
            cwd=root,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert done.returncode == 0, done.stdout + done.stderr
        assert "quote-found" in done.stdout
        assert "quote-missing" not in done.stdout

    def test_the_ledger_records_a_pdf_reading(self, tmp_path: Path):
        root = _project(tmp_path)
        subprocess.run(
            [sys.executable, "-m", "citevouch", "scan", "manuscript.md"],
            cwd=root,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        ledger = json.loads((root / "citevouch.lock.json").read_text(encoding="utf-8"))
        assert ledger["claims"][0]["page"] == 6
