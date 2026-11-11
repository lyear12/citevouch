"""The `file` field of a bibliography entry, as the tools that write it write it.

`draft` looks in a bibliography entry's `file` field for the local copy of the
cited paper.  The field is not free-form: Zotero, Mendeley and JabRef each write
a shape of their own, and all of them are common enough that a tool which reads
only one shape reports "that file is not there" about a file that is there.

Measured before this file existed, with `papers/page.txt` on disk and the entry
pointing at it:

    file = {Full Text PDF:papers/page.txt:application/pdf}
      -> no local file: ... names 'Full Text PDF:papers/page.txt:application/pdf',
         and that file is not there

    file = {papers/page.txt;papers/other.pdf}
      -> no local file: ... names 'papers/page.txt;papers/other.pdf',
         and that file is not there

    file = {:C:\\papers\\page.txt:application/pdf}
      -> no local file: ... names 'C', and that file is not there

The last one is the worst: `_bib_file` split on `:` and took the second piece,
so a Windows absolute path came back as the drive letter.  The message named a
path no human ever wrote.
"""

from __future__ import annotations

from pathlib import Path

from citevouch import draft as draft_module
from citevouch.bibtex import parse_bib
from citevouch.cli import main

NL = chr(10)
BS = chr(92)
PAGE = "We collected 40,688 examples in the corpus." + NL
MANUSCRIPT = "We collected 40,688 examples in the corpus [@paper]." + NL


def _entry(field: str):
    text = "@article{paper, title={X}, year={2020}, author={A}, journal={J}, file={"
    return parse_bib(text + field + "}}" + NL).entries["paper"]


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "papers").mkdir(parents=True)
    (root / "papers" / "page.txt").write_text(PAGE, encoding="utf-8", newline=NL)
    (root / "m.md").write_text(MANUSCRIPT, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'other = "papers/page.txt"' + NL, encoding="utf-8", newline=NL
    )
    return root


def _draft(root: Path, bib: str, *extra: str) -> str:
    (root / "refs.bib").write_text(bib, encoding="utf-8", newline=NL)
    output = root / "proposals.md"
    code = main(
        [
            "draft",
            "m.md",
            "-o",
            str(output),
            "--root",
            str(root),
            "--quiet",
            "--bib",
            "refs.bib",
            *extra,
        ]
    )
    assert code == 0, f"draft exited {code}"
    return output.read_text(encoding="utf-8")


def _skipped(text: str) -> list[str]:
    found = []
    for line in text.splitlines():
        if line.startswith("<!-- line ") and " - " in line:
            found.append(line.split(" - ", 1)[1].removesuffix(" -->"))
    return found


class TestEveryShapeNamesItsPath:
    """The shapes three reference managers actually write."""

    def test_a_plain_path_is_a_path(self) -> None:
        assert draft_module._bib_files(_entry("papers/page.txt")) == ["papers/page.txt"]

    def test_the_old_zotero_shape_is_unwrapped(self) -> None:
        assert draft_module._bib_files(_entry(":papers/page.txt:application/pdf")) == [
            "papers/page.txt"
        ]

    def test_the_zotero_shape_with_a_label_is_unwrapped(self) -> None:
        assert draft_module._bib_files(
            _entry("Full Text PDF:papers/page.txt:application/pdf")
        ) == ["papers/page.txt"]

    def test_a_label_with_spaces_is_still_a_label(self) -> None:
        assert draft_module._bib_files(
            _entry("Submitted Version:papers/page.txt:application/pdf")
        ) == ["papers/page.txt"]

    def test_a_windows_absolute_path_keeps_its_drive(self) -> None:
        absolute = "C:" + BS + "papers" + BS + "page.txt"
        assert draft_module._bib_files(_entry(absolute)) == [absolute]

    def test_a_windows_absolute_path_inside_the_zotero_shape_keeps_its_drive(self) -> None:
        absolute = "C:" + BS + "papers" + BS + "page.txt"
        assert draft_module._bib_files(_entry(":" + absolute + ":application/pdf")) == [
            absolute
        ]

    def test_mendeley_separates_with_semicolons(self) -> None:
        assert draft_module._bib_files(_entry("papers/page.txt;papers/other.pdf")) == [
            "papers/page.txt",
            "papers/other.pdf",
        ]

    def test_two_zotero_attachments_are_two_paths(self) -> None:
        assert draft_module._bib_files(
            _entry("PDF:papers/page.txt:application/pdf;papers/b.pdf:application/pdf")
        ) == ["papers/page.txt", "papers/b.pdf"]

    def test_an_empty_field_names_nothing(self) -> None:
        assert draft_module._bib_files(_entry("")) == []

    def test_a_path_with_a_colon_and_no_mime_is_left_alone(self) -> None:
        # A colon is legal in a file name; only the `label:path:mime` and
        # `path:mime` shapes are unwrapped, and both require a mime-looking tail.
        assert draft_module._bib_files(_entry("papers/a:b.txt")) == ["papers/a:b.txt"]


class TestTheSecondCandidateIsTried:
    """`resolve` must walk every path the field names, not just the first."""

    def test_the_second_of_two_files_is_found(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        (root / "refs.bib").write_text(
            "@article{paper, title={X}, year={2020}, author={A}, journal={J},"
            " file={papers/other.pdf;papers/page.txt}}" + NL,
            encoding="utf-8",
            newline=NL,
        )
        bib = parse_bib((root / "refs.bib").read_text(encoding="utf-8")).entries
        path, needs_line = draft_module.resolve("paper", {}, bib, root)
        assert path is not None and path.endswith("papers/page.txt")
        assert needs_line == "paper"

    def test_a_labelled_zotero_field_resolves(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        (root / "refs.bib").write_text(
            "@article{paper, title={X}, year={2020}, author={A}, journal={J},"
            " file={Full Text PDF:papers/page.txt:application/pdf}}" + NL,
            encoding="utf-8",
            newline=NL,
        )
        bib = parse_bib((root / "refs.bib").read_text(encoding="utf-8")).entries
        path, needs_line = draft_module.resolve("paper", {}, bib, root)
        assert path is not None and path.endswith("papers/page.txt")
        assert needs_line == "paper"


class TestTheSentenceNamesWhatItCouldNotFind:
    """When nothing resolves, the answer names every path that was tried."""

    def test_a_labelled_field_is_not_reported_as_one_long_name(self) -> None:
        entry = _entry("Full Text PDF:papers/gone.pdf:application/pdf")
        sentence = draft_module._why_no_file("paper", None, {"paper": entry})
        assert "'papers/gone.pdf'" in sentence, sentence
        assert "Full Text PDF" not in sentence, sentence
        assert "application/pdf" not in sentence, sentence

    def test_two_candidates_are_both_named(self) -> None:
        entry = _entry("papers/gone.pdf;papers/also-gone.pdf")
        sentence = draft_module._why_no_file("paper", None, {"paper": entry})
        assert "'papers/gone.pdf'" in sentence, sentence
        assert "'papers/also-gone.pdf'" in sentence, sentence

    def test_a_windows_path_is_not_reported_as_its_drive(self) -> None:
        absolute = "C:" + BS + "papers" + BS + "gone.pdf"
        entry = _entry(absolute)
        sentence = draft_module._why_no_file("paper", None, {"paper": entry})
        assert repr(absolute) in sentence, sentence
        assert "names 'C'" not in sentence, sentence


class TestTheVerdictOnAProject:
    """End to end: a Zotero-labelled field over a file that is right there."""

    def test_the_claim_is_proposed(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        written = _draft(
            root,
            "@article{paper, title={X}, year={2020}, author={A}, journal={J},"
            " file={Full Text PDF:papers/page.txt:application/pdf}}" + NL,
        )
        assert "0 claim block(s) proposed" not in written, written
        assert _skipped(written) == [], _skipped(written)

    def test_a_missing_file_is_still_reported(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        written = _draft(
            root,
            "@article{paper, title={X}, year={2020}, author={A}, journal={J},"
            " file={Full Text PDF:papers/gone.pdf:application/pdf}}" + NL,
        )
        reasons = _skipped(written)
        assert len(reasons) == 1, reasons
        assert "'papers/gone.pdf'" in reasons[0], reasons[0]
        assert "is not there" in reasons[0], reasons[0]
