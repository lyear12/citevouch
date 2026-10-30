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

from citevouch.sources import PageText, _no_text_problem, extract_pages

ROOT = Path(__file__).resolve().parent.parent


def _blank_pdf(path: Path, pages: int = 2) -> None:
    """A PDF with a page shape but no text layer, which is what a scan is.

    Written by hand on purpose.  Building one with a PDF library would make
    this file skip wherever that library is not installed, and the lint job
    refuses skips for exactly that reason: a skipped test proves nothing, and
    it proves it silently.  A page whose content stream draws a rectangle and
    sets no text is a few hundred bytes of PDF syntax, and needs nothing but
    `write_bytes`.
    """
    body: list[tuple[int, bytes]] = []
    kids: list[int] = []
    next_id = 3
    for _ in range(pages):
        page_id, content_id = next_id, next_id + 1
        next_id += 2
        kids.append(page_id)
        page = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {content_id} 0 R >>"
        )
        body.append((page_id, page.encode()))
        stream = b"0 0 0 RG 1 w 72 72 468 648 re S\n"
        head = b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
        body.append((content_id, head + stream + b"endstream"))
    kids_list = " ".join(f"{k} 0 R" for k in kids)
    body.append((2, f"<< /Type /Pages /Count {pages} /Kids [{kids_list}] >>".encode()))
    body.append((1, b"<< /Type /Catalog /Pages 2 0 R >>"))
    body.sort()

    out = b"%PDF-1.4\n"
    offsets: dict[int, int] = {}
    for num, payload in body:
        offsets[num] = len(out)
        out += f"{num} 0 obj\n".encode() + payload + b"\nendobj\n"
    xref = len(out)
    highest = max(n for n, _ in body)
    out += f"xref\n0 {highest + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for num in range(1, highest + 1):
        out += f"{offsets[num]:010d} 00000 n \n".encode()
    trailer = f"trailer\n<< /Size {highest + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    out += trailer.encode()
    path.write_bytes(out)


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

    def test_one_word_anywhere_is_enough(self):
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

    def test_every_unreadable_source_is_named_not_just_the_first(self, tmp_path):
        """This finding is about a file, not about a claim.

        `check` merges the scan pass and the verify pass and drops repeats by
        (code, claim).  `source-no-text` carries no claim id, so for three
        unreadable PDFs that key collapsed all three into whichever arrived
        first: the reviewer OCRs a.pdf, re-runs, and meets b.pdf as though it
        had just appeared.  The path belongs in the key.
        """
        root = tmp_path
        for name in ("a", "b", "c"):
            _blank_pdf(root / f"{name}.pdf")
        nl = chr(10)
        blocks = "".join(
            f"```claim id=c{name} source=s{name} page=1{nl}"
            f">> The resulting grammar consists of 40,688 entries.{nl}"
            f"```{nl}"
            for name in ("a", "b", "c")
        )
        (root / "manuscript.md").write_text(blocks, encoding="utf-8", newline=nl)
        (root / "sources.toml").write_text(
            "[sources]"
            + nl
            + "".join(f's{name} = "{name}.pdf"{nl}' for name in ("a", "b", "c")),
            encoding="utf-8",
            newline=nl,
        )

        proc = _run("check", "manuscript.md", "--root", str(root), root=root)
        assert proc.returncode == 1
        for name in ("a.pdf", "b.pdf", "c.pdf"):
            assert name in proc.stdout, f"{name} was never mentioned in the report"
        assert proc.stdout.count("source-no-text") == 3
        assert "3 skipped" in proc.stdout
