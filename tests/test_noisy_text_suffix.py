"""A known text suffix is the author's statement, until the text is not text.

A ``.docx`` saved as ``real.txt`` is a zip, and the plain reader succeeds on
it: measured, a two-entry archive gave 196 characters of mojibake with 47
replacement characters and C0 controls, and ``citevouch check`` answered the
author's quote with ``quote-missing`` - a verdict about their sentence when the
fact was about the file's name.

The suffix still gets the benefit of the doubt, because a note that begins
``PK\\x03\\x04 is the four bytes a zip begins with`` is prose.  What decides is
the text that came out: the same noise score ``textnorm._decode_text`` already
uses to decide an encoding was wrong.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from citevouch import sources, textnorm
from citevouch.cli import main

B3 = "`" * 3
QUOTE = "The method works on every corpus."
MANUSCRIPT = f"{B3}claim id=c1 source=paper page=1\nquote: |\n  {QUOTE}\n{B3}\n"


def zip_saved_as(path: Path) -> Path:
    """A document archive written under a name that claims it is text."""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", f"<w:document>{QUOTE}</w:document>")
        archive.writestr("word/styles.xml", "<w:styles/>")
    return path


def note_about_a_magic_number(path: Path) -> Path:
    """Prose that opens with the bytes a zip begins with."""
    path.write_bytes(
        b"PK\x03\x04 is the four bytes a zip begins with, and a text editor "
        b"will show them to you as PK and two characters you cannot type.\n"
    )
    return path


def run(root: Path, *argv: str) -> tuple[int, str]:
    import contextlib
    import io

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        code = main(list(argv))
    return code, buffer.getvalue()


def project(tmp_path: Path, source_name: str, body: bytes | None = None) -> Path:
    """A one-claim project whose source is named by the test."""
    root = tmp_path / "project"
    (root / "src").mkdir(parents=True)
    target = root / "src" / source_name
    if body is None:
        zip_saved_as(target)
    else:
        target.write_bytes(body)
    (root / "sources.toml").write_text(
        f'[sources]\npaper = "src/{source_name}"\n', encoding="utf-8", newline="\n"
    )
    (root / "manuscript.md").write_text(MANUSCRIPT, encoding="utf-8", newline="\n")
    return root


class TestADocumentSavedUnderATextName:
    """The noise is what says the suffix was wrong."""

    def test_a_zip_named_txt_is_not_read_as_text(self, tmp_path: Path):
        path = zip_saved_as(tmp_path / "real.txt")
        _, problem = sources.extract_pages(path, tmp_path)
        assert problem is not None
        assert problem.code == "source-not-text"
        assert "zip archive" in problem.message
        assert "soffice --convert-to pdf real.txt" in problem.message

    def test_the_same_bytes_under_the_same_four_names(self, tmp_path: Path):
        for name in ("real.txt", "real.md", "real.text"):
            path = zip_saved_as(tmp_path / name)
            _, problem = sources.extract_pages(path, tmp_path)
            assert problem is not None, name
            assert problem.code == "source-not-text", name

    def test_a_note_about_the_zip_magic_bytes_still_reads(self, tmp_path: Path):
        path = note_about_a_magic_number(tmp_path / "zips.txt")
        pages, problem = sources.extract_pages(path, tmp_path)
        assert problem is None
        assert "four bytes a zip begins with" in pages[0].text

    def test_a_readable_page_is_not_refused(self, tmp_path: Path):
        """Markup goes through the same judge, and honest pages pass it."""
        path = tmp_path / "page.html"
        path.write_text("<html><body><p>Prose.</p></body></html>", encoding="utf-8")
        _, problem = sources.extract_pages(path, tmp_path)
        assert problem is None

    def test_a_zip_named_html_is_refused_too(self, tmp_path: Path):
        """The suffix was a guess the markdown reader also makes."""
        path = zip_saved_as(tmp_path / "real.html")
        _, problem = sources.extract_pages(path, tmp_path)
        assert problem is not None
        assert problem.code == "source-not-text"

    def test_a_pdf_is_not_judged_by_its_noise(self, tmp_path: Path):
        """The PDF readers already answered for this file, so this rule stays out.

        The bytes here are a zip, so a rule without the PDF exemption would
        answer ``source-not-text`` about a file the author named as a PDF and
        the PDF readers had already refused on their own terms.
        """
        path = zip_saved_as(tmp_path / "paper.pdf")
        noisy = [sources.PageText(number=1, text=chr(0) * 40 + "The method works.")]
        assert sources._noisy_format_problem(noisy, path, ".pdf") is None
        assert sources._noisy_format_problem(noisy, path, ".txt") is not None

    def test_the_score_that_decides_is_the_one_the_codec_fallback_trusts(self, tmp_path: Path):
        """The measurement, restated in the test so it cannot drift silently."""
        path = zip_saved_as(tmp_path / "real.txt")
        pages, _ = sources.extract_pages(path, tmp_path, use_cache=False)
        joined = "".join(page.text for page in pages)
        assert textnorm._noise(joined) >= max(4, len(joined) // 50)

        note = note_about_a_magic_number(tmp_path / "zips.txt")
        pages, _ = sources.extract_pages(note, tmp_path, use_cache=False)
        joined = "".join(page.text for page in pages)
        assert textnorm._noise(joined) < max(4, len(joined) // 50)


class TestTheCacheDoesNotOutliveTheVerdict:
    """A cache holds pages, not a verdict."""

    def test_a_poisoned_cache_entry_does_not_hand_the_zip_back(self, tmp_path: Path):
        path = zip_saved_as(tmp_path / "real.txt")
        digest = sources.sha256_file(path)
        cache = sources.cache_root(tmp_path) / f"{digest}.json"
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(
            json.dumps(
                {
                    "schema": 1,
                    "extractor": "plain",
                    "pages": [{"number": 1, "text": "PK the zip bytes as characters"}],
                }
            ),
            encoding="utf-8",
            newline="\n",
        )
        _, problem = sources.extract_pages(path, tmp_path)
        assert problem is not None
        assert problem.code == "source-not-text"

    def test_the_second_run_says_the_same_thing(self, tmp_path: Path):
        path = zip_saved_as(tmp_path / "real.txt")
        first = sources.extract_pages(path, tmp_path)[1]
        second = sources.extract_pages(path, tmp_path)[1]
        assert first is not None and second is not None
        assert first.code == second.code == "source-not-text"


class TestTheVerdictOnAProject:
    """What the author sees."""

    def test_the_command_names_the_format_and_not_the_quote(self, tmp_path: Path):
        root = project(tmp_path, "real.txt")
        code, out = run(root, "check", "manuscript.md", "--root", str(root))
        assert "source-not-text" in out
        assert "quote-missing" not in out
        assert code == 0

    def test_a_text_file_that_really_is_text_is_still_green(self, tmp_path: Path):
        root = project(tmp_path, "real.txt", body=QUOTE.encode() + b"\n")
        code, out = run(root, "check", "manuscript.md", "--root", str(root))
        assert "source-not-text" not in out
        assert code == 0
