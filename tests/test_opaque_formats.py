"""Tests for the opaque-format refusal."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from citevouch import sources
from citevouch.cli import main

B3 = "`" * 3
QUOTE = "The method works on every corpus."
MANUSCRIPT = f"{B3}claim id=c1 source=paper page=1\nquote: |\n  {QUOTE}\n{B3}\n"


def docx(path: Path) -> Path:
    """A real zip: the bytes a Word document starts with."""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "word/document.xml",
            f"<w:document><w:body><w:p><w:r><w:t>{QUOTE}</w:t></w:r></w:p></w:body></w:document>",
        )
    return path


def run(root: Path, *argv: str) -> tuple[int, str]:
    import contextlib
    import io

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        code = main(list(argv))
    return code, buffer.getvalue()


class TestTheFileSaysWhatItIs:
    """The suffix is a guess; the first bytes are the file's own answer."""

    def test_a_zip_with_an_unknown_suffix_is_not_read_as_text(self, tmp_path: Path):
        source = docx(tmp_path / "paper.docx")
        pages, problem = sources.extract_pages(source, tmp_path)
        assert pages == []
        assert problem is not None
        assert problem.code == "source-not-text"
        assert "zip archive" in problem.message

    def test_the_message_says_what_it_is_and_what_to_do(self, tmp_path: Path):
        source = docx(tmp_path / "paper.docx")
        _, problem = sources.extract_pages(source, tmp_path)
        assert problem is not None
        assert "a .docx, .odt, .epub or .xlsx" in problem.message
        assert "soffice --convert-to pdf paper.docx" in problem.message

    def test_the_other_magics_are_named(self, tmp_path: Path):
        cases = {
            "old.doc": b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 40,
            "shot.png": b"\x89PNG\r\n\x1a\n" + b"\x00" * 40,
            "photo.jpg": b"\xff\xd8\xff\xe0" + b"\x00" * 40,
            "pack.gz": b"\x1f\x8b\x08" + b"\x00" * 40,
            "prose.rtf": b"{\\rtf1 " + QUOTE.encode("ascii"),
        }
        expected = {
            "old.doc": "OLE compound file",
            "shot.png": "PNG image",
            "photo.jpg": "JPEG image",
            "pack.gz": "gzip stream",
            "prose.rtf": "RTF",
        }
        for name, raw in cases.items():
            path = tmp_path / name
            path.write_bytes(raw)
            _, problem = sources.extract_pages(path, tmp_path)
            assert problem is not None, name
            assert problem.code == "source-not-text", name
            assert expected[name] in problem.message, (name, problem.message)


class TestWhatStillReadsAsText:
    """A sniff that fires on a text file would be worse than none."""

    def test_a_plain_file_with_an_unknown_suffix_still_reads(self, tmp_path: Path):
        path = tmp_path / "notes.xyz"
        path.write_text(QUOTE + "\n", encoding="utf-8", newline="\n")
        pages, problem = sources.extract_pages(path, tmp_path)
        assert problem is None
        assert QUOTE in pages[0].text

    def test_a_known_suffix_is_never_sniffed(self, tmp_path: Path):
        # A .txt whose bytes begin with a magic is the author stating the
        # format; the tool reads what it was told to read.
        path = tmp_path / "zips.txt"
        path.write_bytes(b"PK\x03\x04 this is text that happens to start with PK\n")
        pages, problem = sources.extract_pages(path, tmp_path)
        assert problem is None
        assert "happens to start" in pages[0].text

    def test_a_real_pdf_is_untouched(self, tmp_path: Path):
        pages, problem = sources.extract_pages(
            Path(__file__).resolve().parent.parent
            / "demo"
            / "papers"
            / "2026_VanEecke-Beuls_CoNLL2026_large-scale-CxG.pdf",
            tmp_path,
        )
        assert problem is None
        assert len(pages) > 5


class TestTheCacheDoesNotOutliveTheVerdict:
    def test_a_second_run_says_the_same_thing(self, tmp_path: Path):
        source = docx(tmp_path / "paper.docx")
        first = sources.extract_pages(source, tmp_path)
        second = sources.extract_pages(source, tmp_path)
        assert (first[0], first[1].code) == (second[0], second[1].code)

    def test_no_cache_entry_is_written_for_it(self, tmp_path: Path):
        source = docx(tmp_path / "paper.docx")
        sources.extract_pages(source, tmp_path)
        cache = sources.cache_root(tmp_path)
        assert list(cache.glob("*.json")) == []

    def test_a_poisoned_entry_from_an_older_run_does_not_win(self, tmp_path: Path):
        """The refusal has to be decided above the cache, not beside it.

        A cache written before this check existed holds the zip's bytes spelled
        as characters.  If the sniff ran after the lookup, that entry would
        answer for the file forever and the author would go on being told their
        quote is not in the document.
        """
        source = docx(tmp_path / "paper.docx")
        sha = sources.sha256_file(source)
        poisoned = sources.cache_root(tmp_path)
        poisoned.mkdir(parents=True, exist_ok=True)
        (poisoned / f"{sha}.json").write_text(
            json.dumps(
                {
                    "schema": 1,
                    "sha256": sha,
                    "tool": "0.0.0",
                    "extractor": "plain",
                    "pages": [{"number": 1, "text": "PK the zip bytes as characters"}],
                }
            ),
            encoding="utf-8",
            newline="\n",
        )
        pages, problem = sources.extract_pages(source, tmp_path)
        assert pages == []
        assert problem is not None and problem.code == "source-not-text"


class TestTheVerdictOnAProject:
    def test_check_reports_it_rather_than_a_missing_quote(self, tmp_path: Path):
        docx(tmp_path / "paper.docx")
        (tmp_path / "sources.toml").write_text(
            '[sources]\npaper = "paper.docx"\n', encoding="utf-8", newline="\n"
        )
        (tmp_path / "m.md").write_text(MANUSCRIPT, encoding="utf-8", newline="\n")
        code, out = run(tmp_path, "check", "m.md", "--root", str(tmp_path))
        assert code == 0, out
        assert "source-not-text" in out, out
        assert "quote-missing" not in out, out
        assert "quote not found in paper.docx" not in out, out
