"""`doctor` has to open the sources, not just count them.

The checks before this one ask whether a key is bound and whether the file is
there.  Both pass for a truncated download, a scan, and a `.docx` - and every
one of those makes the run unable to check anything.  Measured before this
check existed: eight `[ok  ]` lines and exit 0 from `doctor` on a project whose
source was a truncated PDF, while `check` on the same tree printed `[high]
source-unreadable ... PdfStreamError: Stream has ended unexpectedly` and exited
1.  The command a reader runs *because* the run looked wrong was the one that
said nothing was wrong.

The three failures are deliberately not one test.  They need three different
commands from the reader (fetch the file again, OCR it, convert it), and the
first version of this check offered the OCR sentence to all three.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from citevouch import doctor, sources
from citevouch.cli import main
from citevouch.model import Finding

BLOCK = "```claim id=c1 source=paper\nquote: |\n  alpha beta gamma\n```\n"
"""One claim naming `paper`, which the manifest binds to each fixture below."""


def _blank_pdf() -> bytes:
    """A one-page PDF that draws a rectangle and sets no text.

    Handwritten rather than produced by a PDF library: pymupdf is not installed
    on CI, and this project's lint job fails on any skipped test.  Same fixture
    as `test_source_no_text.py`, kept separate so neither file's fixture can
    quietly stop being the thing its tests assume.
    """
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>",
    ]
    stream = b"0 0 1 rg 10 10 100 100 re f\n"
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    offsets.append(len(out))
    out += b"4 0 obj\n<< /Length %d >>\nstream\n" % len(stream)
    out += stream + b"endstream\nendobj\n"
    xref = len(out)
    out += b"xref\n0 5\n0000000000 65535 f \n"
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % xref
    return bytes(out)


def project(tmp_path: Path, source: Path) -> Path:
    root = tmp_path / "p"
    root.mkdir()
    (root / "manuscript.md").write_text(BLOCK, encoding="utf-8", newline="\n")
    (root / "sources.toml").write_text(
        f'[sources]\npaper = "{source.name}"\n', encoding="utf-8", newline="\n"
    )
    (root / source.name).write_bytes(source.read_bytes())
    return root


def readable(tmp_path: Path) -> Path:
    source = tmp_path / "page.txt"
    source.write_text("alpha beta gamma\n", encoding="utf-8", newline="\n")
    return project(tmp_path, source)


def truncated_pdf(tmp_path: Path) -> Path:
    source = tmp_path / "cut.pdf"
    source.write_bytes(b"%PDF-1.4\nthis is not really a pdf at all\n")
    return project(tmp_path, source)


def blank_pdf(tmp_path: Path) -> Path:
    source = tmp_path / "scan.pdf"
    source.write_bytes(_blank_pdf())
    return project(tmp_path, source)


def docx(tmp_path: Path) -> Path:
    source = tmp_path / "paper.docx"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr(
            "word/document.xml",
            "<w:document><w:body><w:p><w:r><w:t>alpha beta gamma</w:t>"
            "</w:r></w:p></w:body></w:document>",
        )
    return project(tmp_path, source)


def report(root: Path) -> doctor.Report:
    found = doctor.diagnose(root=root, manuscript="manuscript.md")
    return next(item for item in found if item.name == "extraction")


class TestItSaysWhatItCouldNotRead:
    def test_a_readable_project_passes(self, tmp_path: Path):
        line = report(readable(tmp_path))
        assert line.ok, line.detail
        assert "readable" in line.detail

    def test_a_truncated_pdf_fails_and_names_the_file(self, tmp_path: Path):
        line = report(truncated_pdf(tmp_path))
        assert not line.ok
        assert "cut.pdf" in line.detail
        assert "paper" in line.detail, "the message has to name the key to go with"

    def test_a_scan_fails(self, tmp_path: Path):
        line = report(blank_pdf(tmp_path))
        assert not line.ok
        assert "scan.pdf" in line.detail

    def test_a_docx_fails(self, tmp_path: Path):
        line = report(docx(tmp_path))
        assert not line.ok
        assert "paper.docx" in line.detail

    @pytest.mark.parametrize(
        ("fixture", "expected"),
        [
            ("truncated_pdf", "re-download"),
            ("blank_pdf", "ocrmypdf"),
            ("docx", "soffice --convert-to pdf"),
        ],
    )
    def test_each_failure_carries_the_step_that_fixes_it(
        self, tmp_path: Path, fixture: str, expected: str
    ):
        """The line carries the sentence for *that* format, not a generic one.

        A truncated download, a scan and a word processor file need three
        different commands, and a single "could not be read" would send two of
        the three readers to a tool that cannot help them.  This asserts the
        per-file sentence survives into the doctor line; the sentence itself is
        `sources`'s, and this is the test that proves `doctor` passes it through
        instead of summarising it away.
        """
        makers = {
            "truncated_pdf": truncated_pdf,
            "blank_pdf": blank_pdf,
            "docx": docx,
        }
        assert expected in report(makers[fixture](tmp_path)).detail


class TestTheCommand:
    def test_the_run_exits_one(self, tmp_path: Path, capsys):
        root = blank_pdf(tmp_path)
        assert main(["doctor", "--root", str(root)]) == 1
        assert "[FAIL] extraction" in capsys.readouterr().out

    def test_a_readable_project_exits_zero(self, tmp_path: Path, capsys):
        root = readable(tmp_path)
        assert main(["doctor", "--root", str(root)]) == 0
        out = capsys.readouterr().out
        assert "Everything this tool needs is on this machine" in out

    def test_the_demo_is_readable(self, capsys):
        demo = Path(__file__).resolve().parent.parent / "demo"
        assert main(["doctor", "--root", str(demo)]) == 0
        assert "[ok  ] extraction" in capsys.readouterr().out


class TestItDoesNotBorrowAnotherChecksNoun:
    """One project state, one failing line.

    `sources` owns "a key is bound to nothing" and `manifest` owns "the file it
    names is gone".  Both produce no file to read, so this check cannot say
    anything about them that its neighbours have not already said - and saying
    it twice makes one problem look like two.
    """

    def test_a_key_bound_to_nothing_is_left_to_the_sources_check(self, tmp_path: Path):
        root = readable(tmp_path)
        (root / "sources.toml").write_text(
            '[sources]\nother = "page.txt"\n', encoding="utf-8", newline="\n"
        )
        line = report(root)
        assert line.ok, line.detail
        assert "bound to nothing" in line.detail

    def test_a_file_that_is_gone_is_left_to_the_manifest_check(self, tmp_path: Path):
        root = readable(tmp_path)
        (root / "page.txt").unlink()
        line = report(root)
        assert line.ok, line.detail
        assert "bound to nothing" in line.detail

    def test_a_manuscript_that_cannot_be_read_is_left_to_the_manuscript_check(
        self, tmp_path: Path
    ):
        root = readable(tmp_path)
        line = next(
            item
            for item in doctor.diagnose(root=root, manuscript="nope.md")
            if item.name == "extraction"
        )
        assert line.ok
        assert "manuscript could not be read" in line.detail

    def test_a_file_that_vanishes_mid_run_is_still_left_to_the_manifest_check(
        self, tmp_path: Path, monkeypatch
    ):
        """The `source-missing` branch is a race, so the test has to build it.

        `read_source_table` only returns files that exist, so extraction cannot
        report `source-missing` unless the file goes away between the table read
        and the read.  Reaching that branch by deleting the file for real would
        change what `read_source_table` returns and test the wrong path; this
        stubs the extractor instead, so the check sees exactly the finding it
        would see in the race.

        Before this test the branch was unreachable in every test, which is the
        same thing as untested: removing the `source-missing` skip left the
        whole file green.
        """
        root = readable(tmp_path)
        real = doctor.extract_pages

        def vanished(path, base, use_cache=True):
            if Path(path).name == "page.txt":
                return [], Finding(
                    code="source-missing",
                    message="source file page.txt does not exist",
                    path=str(path),
                )
            return real(path, base, use_cache)

        monkeypatch.setattr(doctor, "extract_pages", vanished)
        line = report(root)
        assert line.ok, line.detail
        assert "does not exist" not in line.detail

    def test_a_manifest_that_will_not_parse_is_reported_once(self, tmp_path: Path):
        root = readable(tmp_path)
        (root / "sources.toml").write_text("[sources\npaper = 1\n", encoding="utf-8")
        line = report(root)
        assert line.ok, line.detail
        assert "manifest could not be read" in line.detail


class TestTheAdvice:
    def test_the_failure_names_the_command_that_rechecks(self, tmp_path: Path):
        """Every failing `doctor` line carries a `->` line with something to run.

        The other checks each end in a command; this one has to as well, or it
        becomes the one failure a reader has no next step for.  The sentence
        cannot be the per-file advice again - that is already printed one line
        above with the real file name in it - so what it names is the rerun.
        """
        line = report(blank_pdf(tmp_path))
        assert "citevouch scan" in line.fix
        assert "ocr" in line.detail.lower()

    def test_it_does_not_repeat_the_per_file_advice(self, tmp_path: Path):
        """The fix line must not print a second, generic OCR command.

        The first draft did, and the result was `ocrmypdf <file> out.pdf` two
        lines below a message that had already named `scan.pdf`.  A reader who
        copies the second one gets a placeholder for a file name.
        """
        line = report(blank_pdf(tmp_path))
        assert "<file>" not in line.fix
        assert line.fix.count("```") % 2 == 0
        assert "ocrmypdf scan.pdf" not in line.fix

    def test_many_failures_are_summarised_rather_than_pasted(self, tmp_path: Path):
        """Five unreadable sources is not five pasted pages.

        Each finding's own message is a paragraph long, so printing all of them
        in the `detail` column makes the table unreadable and pushes the closing
        sentence off the screen.  The count of what was left out has to be said
        out loud - a truncation the reader cannot see is a false total.
        """
        root = tmp_path / "p"
        root.mkdir()
        blocks = []
        manifest = []
        for index in range(5):
            name = f"cut{index}.pdf"
            (root / name).write_bytes(b"%PDF-1.4\nnot a pdf\n")
            manifest.append(f'k{index} = "{name}"')
            blocks.append(
                f"```claim id=c{index} source=k{index}\nquote: |\n  alpha beta gamma\n```\n"
            )
        (root / "manuscript.md").write_text("\n".join(blocks), encoding="utf-8", newline="\n")
        (root / "sources.toml").write_text(
            "[sources]\n" + "\n".join(manifest) + "\n", encoding="utf-8", newline="\n"
        )
        line = report(root)
        assert not line.ok
        assert "more source" in line.detail
        assert "lists in full" in line.detail


class TestTheSecondRunIsCheap:
    def test_the_extraction_goes_through_the_cache(self, tmp_path: Path, monkeypatch):
        """`doctor` now extracts, so it must not re-extract every time.

        The check is worth its cost once; paying it on every invocation would
        make the one command a worried user runs repeatedly the slowest thing in
        the tool.  Counting extractor calls is the assertion that survives a
        cache that is written but never read: writing the entry happens whether
        or not ``use_cache`` is honoured, so asking "did a file appear" proves
        nothing.
        """
        root = readable(tmp_path)
        calls: list[str] = []
        real = sources._plain_text_pages

        def counted(path):
            calls.append(str(path))
            return real(path)

        monkeypatch.setattr(sources, "_plain_text_pages", counted)
        assert report(root).ok
        assert len(calls) == 1
        assert report(root).ok
        assert len(calls) == 1, "the second run re-extracted instead of reading the cache"
