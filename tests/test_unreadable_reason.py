"""A file the tool cannot read, said in the words of whoever refused it.

`extract_pages` has to turn every exception from a reader into `None`: a corrupt
PDF is a finding, not a crash.  What it must not do is keep only the fact that
both readers failed, because then one sentence has to cover four different
problems and it can only be the least useful one.  Before this file existed the
sentence was always "install pypdf (pip install pypdf) or pdftotext and try
again", printed on a machine where `citevouch doctor` had just reported

    [ok  ] pypdf       6.16.1 (reads PDFs in-process)

Measured then, on four files that reach the same branch:

    truncated.pdf  a real PDF cut to 40,000 bytes   install pypdf ...
    renamed.pdf    a text file named .pdf           install pypdf ...
    empty.pdf      zero bytes                       install pypdf ...
    missing.pdf    a tenth of a real PDF            install pypdf ...

The readers knew the difference and said so - pypdf raises `EmptyFileError` or
`PdfStreamError: Stream has ended unexpectedly`, poppler prints `invalid pdf
header` or `EOF marker not found`.  Each of those sentences was one frame away
from the message that needed it.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from citevouch import sources

REAL_PDF = Path(__file__).resolve().parent.parent / "demo" / "papers"


def _a_real_pdf() -> Path:
    found = sorted(REAL_PDF.glob("*.pdf"))
    if not found:
        pytest.fail("no demo PDF to truncate: this test cannot be skipped here")
    return found[0]


def _truncated(tmp_path: Path) -> Path:
    """A real PDF with most of its bytes missing - what a killed download leaves."""
    raw = _a_real_pdf().read_bytes()
    path = tmp_path / "truncated.pdf"
    path.write_bytes(raw[: len(raw) // 6])
    return path


def _not_a_pdf(tmp_path: Path) -> Path:
    """A text file somebody saved with the wrong extension."""
    path = tmp_path / "renamed.pdf"
    path.write_text("this is a note, not a paper\n", encoding="utf-8")
    return path


def _empty(tmp_path: Path) -> Path:
    path = tmp_path / "empty.pdf"
    path.write_bytes(b"")
    return path


class TestTheMessageNamesTheReader:
    def test_a_truncated_pdf_says_the_stream_ended(self, tmp_path: Path):
        _pages, problem = sources.extract_pages(_truncated(tmp_path), tmp_path)
        assert problem is not None
        assert problem.code == "source-unreadable"
        assert "Stream has ended unexpectedly" in problem.message

    def test_a_file_that_is_not_a_pdf_names_what_the_reader_saw(self, tmp_path: Path):
        _pages, problem = sources.extract_pages(_not_a_pdf(tmp_path), tmp_path)
        assert problem is not None
        assert "PdfStreamError" in problem.message or "not a PDF" in problem.message

    def test_an_empty_file_says_it_is_empty(self, tmp_path: Path):
        _pages, problem = sources.extract_pages(_empty(tmp_path), tmp_path)
        assert problem is not None
        assert "empty" in problem.message.lower()

    def test_the_three_files_do_not_get_the_same_message(self, tmp_path: Path):
        """The defect this replaces was not a wrong sentence but one sentence.

        A single message for four causes is only visible when two causes are
        compared, so this compares them.
        """
        messages = {
            name: sources.extract_pages(path, tmp_path)[1].message
            for name, path in (
                ("truncated", _truncated(tmp_path)),
                ("renamed", _not_a_pdf(tmp_path)),
                ("empty", _empty(tmp_path)),
            )
        }
        assert len(set(messages.values())) == 3, messages

    def test_the_message_does_not_send_a_reader_to_install_what_is_installed(
        self, tmp_path: Path
    ):
        """`doctor` reports pypdf as present, so the advice has to be about the
        file.  This asserts the sentence agrees with `doctor` on the machine the
        test is running on, rather than hard-coding either answer."""
        imported = sources._pypdf_importable()
        _pages, problem = sources.extract_pages(_empty(tmp_path), tmp_path)
        assert problem is not None
        if imported:
            assert "no PDF reader is installed" not in problem.message


class TestTheNoReaderCase:
    def test_it_says_there_is_no_reader_and_names_both_ways_to_get_one(
        self, tmp_path: Path, monkeypatch
    ):
        monkeypatch.setattr(sources, "_pypdf_importable", lambda: False)
        monkeypatch.setattr(sources, "which", lambda _name: None)
        path = tmp_path / "paper.pdf"
        path.write_bytes(b"%PDF-1.4 nothing")
        _pages, problem = sources.extract_pages(path, tmp_path)
        assert problem is not None
        assert "no PDF reader is installed" in problem.message
        assert "pip install pypdf" in problem.message
        assert "pdftotext" in problem.message

    def test_one_reader_is_enough_to_stop_blaming_the_machine(
        self, tmp_path: Path, monkeypatch
    ):
        monkeypatch.setattr(sources, "_pypdf_importable", lambda: True)
        monkeypatch.setattr(sources, "which", lambda _name: None)
        path = tmp_path / "paper.pdf"
        path.write_bytes(b"%PDF-1.4 nothing")
        _pages, problem = sources.extract_pages(path, tmp_path)
        assert problem is not None
        assert "no PDF reader is installed" not in problem.message


class TestBothReadersAreAsked:
    """The two readers fail for different reasons, which is the point.

    When pypdf says "Stream has ended unexpectedly" and poppler says "Couldn't
    read xref table", the author learns the shape of the damage: a download that
    stopped part way.  Asking one of them and stopping there would have passed
    every end-to-end test above, because a message holding one true sentence is
    still not the old false one.  These tests drive the two readers directly so
    that each one's contribution is checked on its own, without depending on
    which binaries this machine has.
    """

    def test_the_sentence_carries_what_both_readers_said(self, tmp_path: Path, monkeypatch):
        path = tmp_path / "paper.pdf"
        path.write_bytes(b"%PDF-1.4 broken")

        class Done:
            stderr = "Syntax Error: Couldn't read xref table\n"

        monkeypatch.setattr(sources, "_pypdf_importable", lambda: False)
        monkeypatch.setattr(sources, "which", lambda _name: "/usr/bin/pdftotext")
        monkeypatch.setattr(sources.subprocess, "run", lambda *a, **k: Done())

        assert sources._why_both_refused(path) == [
            "pdftotext: Syntax Error: Couldn't read xref table"
        ]

    def test_a_reader_that_says_nothing_adds_nothing(self, tmp_path: Path, monkeypatch):
        path = tmp_path / "paper.pdf"
        path.write_bytes(b"%PDF-1.4 broken")

        class Done:
            stderr = ""

        monkeypatch.setattr(sources, "_pypdf_importable", lambda: False)
        monkeypatch.setattr(sources, "which", lambda _name: "/usr/bin/pdftotext")
        monkeypatch.setattr(sources.subprocess, "run", lambda *a, **k: Done())

        assert sources._why_both_refused(path) == []

    def test_the_message_quotes_the_reader_that_was_asked(self, tmp_path: Path, monkeypatch):
        path = tmp_path / "paper.pdf"
        path.write_bytes(b"%PDF-1.4 broken")

        class Done:
            stderr = "EOF marker not found\n"

        monkeypatch.setattr(sources, "_pypdf_importable", lambda: False)
        monkeypatch.setattr(sources, "which", lambda _name: "/usr/bin/pdftotext")
        monkeypatch.setattr(sources.subprocess, "run", lambda *a, **k: Done())

        message = sources._unreadable_message(path)
        assert "pdftotext: EOF marker not found" in message
        assert "no PDF reader is installed" not in message


class TestTheReadersStillAnswerWithPages:
    def test_a_readable_pdf_is_not_affected(self, tmp_path: Path):
        readable = tmp_path / "ok.pdf"
        shutil.copyfile(_a_real_pdf(), readable)
        pages, problem = sources.extract_pages(readable, tmp_path)
        assert problem is None, problem
        assert pages and any(page.text.strip() for page in pages)

    def test_a_plain_text_file_never_reaches_the_message(self, tmp_path: Path):
        path = tmp_path / "notes.txt"
        path.write_text("alpha beta gamma\n", encoding="utf-8", newline="\n")
        pages, problem = sources.extract_pages(path, tmp_path)
        assert problem is None
        assert [page.text for page in pages] == ["alpha beta gamma\n"]


class TestTheFailurePathIsTheOnlyOneThatPays:
    def test_a_readable_pdf_does_not_ask_the_readers_twice(self, tmp_path: Path, monkeypatch):
        """Asking again is how the message stays stateless, and it costs a second
        read.  That cost is only acceptable on the failure path, so this counts
        the calls on a successful one."""
        asked: list[str] = []

        def counted(path):
            asked.append(str(path))
            return []

        monkeypatch.setattr(sources, "_why_both_refused", counted)
        readable = tmp_path / "ok.pdf"
        shutil.copyfile(_a_real_pdf(), readable)
        pages, problem = sources.extract_pages(readable, tmp_path, use_cache=False)
        assert problem is None and pages
        assert asked == [], (
            "a successful extraction must not ask the readers to explain "
            "themselves; asking twice is only for the message about a failure"
        )
