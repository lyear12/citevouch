"""The file a "convert it first" sentence names has to be a file.

Four sentences in this tool tell the reader to convert something and print the
command to do it.  Each of them printed ``path.name``, so a source at
``sources/paper.docx`` produced::

    sources/paper.docx is a zip archive - a .docx, .odt, .epub or .xlsx - ...
    Convert it first, for example `soffice --convert-to pdf paper.docx`, ...

``paper.docx`` is not a file where the reader is standing.  The sentence says
"convert it first" and then hands over a command that answers
``Error: source file paper.docx does not exist``, so the fix the tool found is
the fix the reader cannot apply.  Measured for all four before this existed:

* ``source-not-text`` - ``soffice --convert-to pdf paper.docx``
* ``source-encoding`` - ``iconv ... paper.txt > utf8.txt``
* ``source-no-text`` - ``ocrmypdf scan.pdf out.pdf``
* ``claim-not-decoded`` - ``iconv ... m.md > utf8.md``

``doctor`` had already been taught this for its own advice, in
``tests/test_doctor_advice_runs.py``: take the command out of the output and
run it.  These tests ask the same question of the four conversion sentences,
and they ask it from the directory *above* the project, because that is where
the two spellings of the path differ.  From inside ``sources/`` a command that
dropped the directory would still work by accident.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest

from citevouch import sources
from citevouch.cli import main

B3 = "```"
NL = "\n"
QUOTE = "We collected 40,688 examples from the corpus."
SRC = Path(__file__).resolve().parents[1] / "src"

#: Any word in a printed command that looks like a path we handed in.
CONVERT = re.compile(r"`([^`]*conver[tT][^`]*)`|`([^`]*iconv[^`]*)`|`([^`]*ocrmypdf[^`]*)`")
ICONV = re.compile(r"`(iconv[^`]*)`")


def _project(tmp_path: Path) -> Path:
    """A project in ``proj/`` whose sources live in ``proj/sources/``."""
    proj = tmp_path / "proj"
    (proj / "sources").mkdir(parents=True)
    (proj / "sources" / "page.txt").write_text(QUOTE + NL, encoding="utf-8", newline=NL)
    (proj / "sources.toml").write_text(
        '[sources]\npaper = "sources/page.txt"\n', encoding="utf-8", newline=NL
    )
    return proj


def _docx(path: Path) -> Path:
    """The smallest file whose first bytes say ``zip archive``."""
    import zipfile

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", "<w:document/>")
    return path


def _gbk(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("gbk"))
    return path


def _run(root: Path, monkeypatch: pytest.MonkeyPatch, capsys, *argv: str):
    monkeypatch.chdir(root.parent)
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out + captured.err


def _printed(text: str) -> list[str]:
    """Every conversion command in the output, unquoted of its backticks."""
    found: list[str] = []
    for match in CONVERT.finditer(text):
        word = next(group for group in match.groups() if group)
        found.append(word.strip())
    return found


def _command_words(command: str) -> list[str]:
    """The words a shell would pass, minus the program name."""
    return shlex.split(command)


def _names_a_file_here(command: str, cwd: Path) -> bool:
    """Does every path-shaped word in this command exist under ``cwd``?

    The tools themselves are not installed on every machine that runs these
    tests, so this asks the question the reader would ask before typing: the
    file the command names has to be a file.  Words that are not paths
    (``--convert-to``, ``utf-8``, ``out.pdf``, the tool's own name) are
    skipped by only looking at words that look like the inputs we planted.
    """
    for word in _command_words(command):
        if word.startswith("-") or word in {"soffice", "iconv", "ocrmypdf"}:
            continue
        if word in {"utf8.txt", "utf8.md", "out.pdf", "paper.pdf"}:
            continue
        candidate = Path(word)
        if candidate.suffix in {".docx", ".txt", ".md", ".pdf"}:
            return (cwd / candidate).is_file()
    return False


class TestTheSourceToConvert:
    """``sources/`` is where the two spellings of one file differ."""

    def test_a_zip_in_a_subdirectory_is_named_with_its_directory(self, tmp_path):
        proj = _project(tmp_path)
        source = _docx(proj / "sources" / "paper.docx")
        pages, problem = sources.extract_pages(source, proj)
        assert pages == []
        assert problem is not None
        assert problem.code == "source-not-text"
        assert "sources/paper.docx" in problem.message
        printed = _printed(problem.message)
        assert printed, problem.message
        assert _names_a_file_here(printed[0], proj), (printed[0], problem.message)

    def test_the_end_to_end_run_names_it_the_same_way(self, tmp_path, monkeypatch, capsys):
        proj = _project(tmp_path)
        _docx(proj / "sources" / "paper.docx")
        (proj / "sources.toml").write_text(
            '[sources]\npaper = "sources/paper.docx"\n', encoding="utf-8", newline=NL
        )
        (proj / "m.md").write_text(
            f"{B3}claim id=c1 source=paper{NL}quote: |{NL}  {QUOTE}{NL}{B3}{NL}",
            encoding="utf-8",
            newline=NL,
        )
        code, out = _run(proj, monkeypatch, capsys, "check", "m.md", "--root", proj.name)
        # A file this tool cannot read is a medium finding, not a verdict on the
        # author's quote: exit stays 0 at the default --fail-on.
        assert code == 0, out
        assert "source-not-text" in out, out
        printed = _printed(out)
        assert printed, out
        assert _names_a_file_here(printed[0], proj), (printed[0], out)
        # Exactly the list entry, quoted: not the bare name the finding used to
        # print, which named a file that is not where the reader is standing.
        assert "`soffice --convert-to pdf sources/paper.docx`" in out, out

    def test_a_text_file_that_is_not_utf8_is_named_with_its_directory(self, tmp_path):
        proj = _project(tmp_path)
        source = _gbk(proj / "sources" / "gbk.txt", "我们收集了 40,688 个例子。" * 12)
        pages, problem = sources.extract_pages(source, proj)
        assert pages == []
        assert problem is not None
        assert problem.code == "source-encoding"
        assert "sources/gbk.txt" in problem.message
        printed = _printed(problem.message)
        assert printed, problem.message
        assert _names_a_file_here(printed[0], proj), (printed[0], problem.message)


class TestTheScanThatHasNoText:
    def test_a_scan_in_a_subdirectory_is_named_with_its_directory(self, tmp_path):
        proj = _project(tmp_path)
        page = proj / "sources" / "scan.pdf"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_bytes(b"%PDF-1.4\n" + b"\x00" * 200)
        problem = sources._no_text_problem(
            [sources.PageText(number=1, text="")], page, ".pdf", proj
        )
        assert problem is not None
        assert problem.code == "source-no-text"
        assert "sources/scan.pdf" in problem.message
        printed = _printed(problem.message)
        assert printed, problem.message
        assert _names_a_file_here(printed[0], proj), (printed[0], problem.message)


class TestTheManuscriptThatWasNeverDecoded:
    def test_check_names_the_manuscript_with_its_directory(self, tmp_path, monkeypatch, capsys):
        proj = _project(tmp_path)
        # The quote itself is Chinese, so a GBK manuscript read as UTF-8 loses
        # characters *inside the quotation* - which is what this finding is
        # about.  An ASCII quote survives the wrong decoder byte for byte.
        sentence = "我们收集了四万零六百八十八个例子。"
        (proj / "sources" / "page.txt").write_text(sentence + NL, encoding="utf-8", newline=NL)
        paper = proj / "paper"
        paper.mkdir()
        block = f"{B3}claim id=c1 source=paper{NL}quote: |{NL}  {sentence}{NL}{B3}{NL}"
        (paper / "m.md").write_bytes(block.encode("gbk"))
        code, out = _run(proj, monkeypatch, capsys, "check", "paper/m.md", "--root", proj.name)
        assert code == 1, out
        assert "claim-not-decoded" in out, out
        # Both halves of the sentence name the file: the clause that says what
        # is wrong, and the command that fixes it.
        assert "paper/m.md cannot be read as UTF-8" in out, out
        printed = _printed(out)
        assert printed, out
        assert _names_a_file_here(printed[0], proj), (printed[0], out)

    def test_draft_names_the_manuscript_with_its_directory(self, tmp_path, monkeypatch, capsys):
        proj = _project(tmp_path)
        sentence = "我们收集了四万零六百八十八个例子。"
        (proj / "sources" / "page.txt").write_text(sentence + NL, encoding="utf-8", newline=NL)
        paper = proj / "paper"
        paper.mkdir()
        text = f"{sentence} [@paper]{NL}"
        (paper / "m.md").write_bytes(text.encode("gbk"))
        _code, _out = _run(
            proj,
            monkeypatch,
            capsys,
            "draft",
            "paper/m.md",
            "--root",
            proj.name,
            "-o",
            "claims.md",
        )
        # The note about the undecoded manuscript goes into the file it writes,
        # which is where the author reads it, so that is where this asks.
        written = (proj / "claims.md").read_text(encoding="utf-8")
        assert "iconv" in written, written[:600]
        printed = _printed(written)
        assert printed, written[:600]
        assert _names_a_file_here(printed[0], proj), (printed[0], written[:600])
        assert "`iconv -f GBK -t utf-8 paper/m.md > utf8.md`" in written, written[:600]

    def test_a_manuscript_with_a_space_is_quoted_in_the_note(
        self, tmp_path, monkeypatch, capsys
    ):
        proj = _project(tmp_path)
        sentence = "我们收集了四万零六百八十八个例子。"
        (proj / "sources" / "page.txt").write_text(sentence + NL, encoding="utf-8", newline=NL)
        paper = proj / "paper"
        paper.mkdir()
        text = f"{sentence} [@paper]{NL}"
        _gbk(paper / "my paper.md", text)
        _code, _out = _run(
            proj,
            monkeypatch,
            capsys,
            "draft",
            "paper/my paper.md",
            "--root",
            proj.name,
            "-o",
            "claims.md",
        )
        written = (proj / "claims.md").read_text(encoding="utf-8")
        # A command is only runnable if its words survive the shell.  Dropping
        # the quoting turns ``paper/my paper.md`` into two arguments and the
        # reader gets ``iconv: extra operand``, which is a different sentence
        # about a different problem.  This asks the command itself, not any
        # older sentence that happens to quote the same name.
        assert "`iconv -f GBK -t utf-8 'paper/my paper.md' > utf8.md`" in written, written[:900]

    def test_the_never_decoded_note_quotes_the_manuscript(self, tmp_path, monkeypatch, capsys):
        """The other note: the file has no citations at all, so nothing is proposed.

        Both notes print the same ``iconv`` command, and they are built in two
        different places, so one test cannot stand for the other.
        """
        proj = _project(tmp_path)
        sentence = "我们收集了四万零六百八十八个例子。"
        (proj / "sources" / "page.txt").write_text(sentence + NL, encoding="utf-8", newline=NL)
        paper = proj / "paper"
        paper.mkdir()
        _gbk(paper / "my paper.md", sentence + NL)
        _code, _out = _run(
            proj,
            monkeypatch,
            capsys,
            "draft",
            "paper/my paper.md",
            "--root",
            proj.name,
            "-o",
            "claims.md",
        )
        written = (proj / "claims.md").read_text(encoding="utf-8")
        assert "never decoded" in written, written[:900]
        assert "`iconv -f GBK -t utf-8 'paper/my paper.md' > utf8.md`" in written, written[:900]


class TestWhatMustNotChange:
    def test_a_source_at_the_root_is_still_named_without_a_directory(self, tmp_path):
        source = _docx(tmp_path / "paper.docx")
        _pages, problem = sources.extract_pages(source, tmp_path)
        assert problem is not None
        assert "`soffice --convert-to pdf paper.docx`" in problem.message

    def test_a_caller_with_no_root_keeps_the_path_it_was_given(self):
        problem = sources._no_text_problem(
            [sources.PageText(number=1, text="")], Path("scan.pdf"), ".pdf"
        )
        assert problem is not None
        assert "`ocrmypdf scan.pdf out.pdf`" in problem.message

    def test_a_path_with_a_space_is_quoted(self, tmp_path):
        proj = _project(tmp_path)
        source = _docx(proj / "sources" / "my paper.docx")
        _pages, problem = sources.extract_pages(source, proj)
        assert problem is not None
        # A path with a space splits into two arguments unless it is quoted;
        # the sentence and the command have to agree on which string is the file.
        assert "`soffice --convert-to pdf 'sources/my paper.docx'`" in problem.message
