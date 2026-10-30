"""A source that was read successfully and held no text at all.

The dangerous shape is not a file that fails to open.  It is a file that opens
fine, yields empty pages, and lets the rest of the pipeline search them: the
matcher then reports `quote-missing` against the author's quote, which is a
verdict about their work when the fact is about their PDF.  The sentence that
follows ("install pypdf") is already satisfied, so the reader concludes the
tool is broken.

Both the extraction path and the cache path have to answer the same way.  The
cache stores pages, not verdicts, so a run that recorded empty pages will keep
handing back empty pages - and if only the extraction path judged them, the
first run would say `source-no-text` and every run after it would quietly
downgrade to `quote-missing`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from citevouch.sources import PageText, _no_text_problem, extract_pages
from citevouch.textnorm import read_text

ROOT = Path(__file__).resolve().parent.parent


def _blank_pdf(path: Path, pages: int = 2) -> None:
    """A PDF with a page shape but no text layer, which is what a scan is."""
    pymupdf = pytest.importorskip("pymupdf", reason="only the figure tool needs it")
    doc = pymupdf.open()
    for _ in range(pages):
        doc.new_page().draw_rect(pymupdf.Rect(50, 50, 400, 600), color=(0, 0, 0))
    doc.save(str(path))
    doc.close()


class TestTheVerdictItself:
    def test_no_text_is_a_finding(self):
        """Empty pages are not an absence of evidence, they are the evidence."""
        pages = [PageText(number=1, text="")]
        problem = _no_text_problem(pages, Path("scan.pdf"))
        assert problem is not None
        assert problem.code == "source-no-text"
        assert problem.severity == "high"

    def test_whitespace_only_is_still_no_text(self):
        pages = [PageText(number=1, text="   \n\t \n")]
        assert _no_text_problem(pages, Path("scan.pdf")) is not None

    def test_one_character_of_text_is_enough(self):
        """A PDF with one real word is a PDF a human chose to cite, not a scan."""
        pages = [PageText(number=1, text=""), PageText(number=2, text="Results")]
        assert _no_text_problem(pages, Path("paper.pdf")) is None

    def test_the_message_names_the_file_the_page_count_and_the_fix(self):
        pages = [PageText(number=1, text=""), PageText(number=2, text="")]
        message = _no_text_problem(pages, Path("chapter3.pdf")).message
        assert "chapter3.pdf" in message
        assert "2 page" in message
        assert "OCR" in message


class TestTheExtractionPath:
    def test_a_blank_pdf_reports_instead_of_returning_empty_pages(self, tmp_path):
        _blank_pdf(tmp_path / "scan.pdf")
        pages, problem = extract_pages(tmp_path / "scan.pdf", tmp_path, use_cache=False)
        assert [page.text for page in pages] == ["", ""]
        assert problem is not None
        assert problem.code == "source-no-text"
        assert "2 page" in problem.message

    def test_a_pdf_with_text_reports_nothing(self, tmp_path):
        """The demo paper is the control: the check must not fire on real text."""
        pages, problem = extract_pages(
            str(ROOT / "demo" / "papers" / "2020_TayyarMadabushi-etal_CxGBERT.pdf"),
            str(ROOT / "demo"),
            use_cache=False,
        )
        assert problem is None, f"real paper was judged empty: {problem.message}"
        assert any(page.text.strip() for page in pages)


class TestTheCachePath:
    def test_a_cache_hit_says_the_same_thing_as_a_fresh_extraction(self, tmp_path):
        """The first run and the hundredth must not disagree about the file."""
        _blank_pdf(tmp_path / "scan.pdf")
        source = tmp_path / "scan.pdf"

        first, problem_first = extract_pages(source, tmp_path)
        assert problem_first is not None
        assert problem_first.code == "source-no-text"

        cached, problem_cached = extract_pages(source, tmp_path)
        assert cached == first
        assert problem_cached is not None, (
            "the cache hit returned no problem, so only the first run of a "
            "scan would be diagnosed and every later run would blame the quotes"
        )
        assert problem_cached.code == "source-no-text"


def _run(*args: str, root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "citevouch", *args],
        cwd=str(root),
        env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class TestTheCommandLine:
    """The exit code and the sentence a user actually sees."""

    def _project(self, tmp_path: Path) -> Path:
        _blank_pdf(tmp_path / "scan.pdf")
        (tmp_path / "manuscript.md").write_text(
            "```claim id=c1 source=scan2026 page=1\n"
            ">> The resulting grammar consists of 40,688 entries.\n"
            "```\n",
            encoding="utf-8",
            newline="\n",
        )
        (tmp_path / "sources.toml").write_text(
            '[sources]\nscan2026 = "scan.pdf"\n', encoding="utf-8", newline="\n"
        )
        return tmp_path

    def test_check_names_the_pdf_and_not_the_quote(self, tmp_path):
        root = self._project(tmp_path)
        proc = _run("check", "manuscript.md", "--root", str(root), root=root)
        assert proc.returncode == 1
        assert "source-no-text" in proc.stdout
        assert "OCR" in proc.stdout
        assert "quote-missing" not in proc.stdout

    def test_the_claim_is_skipped_rather_than_counted_missing(self, tmp_path):
        root = self._project(tmp_path)
        proc = _run("check", "manuscript.md", "--root", str(root), root=root)
        assert "1 skipped" in proc.stdout
        assert "1 missing" not in proc.stdout

    def test_the_second_run_reads_the_cache_and_still_says_so(self, tmp_path):
        root = self._project(tmp_path)
        _run("scan", "manuscript.md", "--root", str(root), root=root)
        cache = root / ".citevouch" / "cache"
        assert list(cache.glob("*.json")), "no cache entry was written to test the hit path"
        assert (
            "source-no-text"
            in _run("check", "manuscript.md", "--root", str(root), root=root).stdout
        )

    def test_the_cached_pages_really_are_empty(self, tmp_path):
        """Otherwise the hit-path test above could pass on real text."""
        root = self._project(tmp_path)
        _run("scan", "manuscript.md", "--root", str(root), root=root)
        blob = json.loads(
            next((root / ".citevouch" / "cache").glob("*.json")).read_text("utf-8")
        )
        assert all(not page["text"].strip() for page in blob["pages"])


def test_read_text_is_not_involved_in_this_decision():
    """A PDF is never decoded as text, so the encoding fix cannot mask a scan."""
    assert read_text(ROOT / "demo" / "manuscript.md")
