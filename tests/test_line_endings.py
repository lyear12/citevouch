"""Round 177: a manuscript saved with CRLF must read like the same file saved with LF.

Windows editors write ``\\r\\n``; none of this tool's grammar carries meaning in
the extra byte.  But ``draft`` looks for paragraph breaks by searching for
``\\n\\n``, and a CRLF file has ``\\r\\n\\r\\n``, so the search failed and the
whole manuscript became one paragraph -- the heading above the citation, the
list above it, and the sentence itself all came back as one "sentence".
"""

from __future__ import annotations

import difflib
from pathlib import Path

import pytest

from citevouch import cli, manuscript, sources, textnorm
from citevouch import draft as draft_module

B3 = chr(96) * 3
NL = chr(10)
CR = chr(13)
BS = chr(92)

PAGE = "We collected 154,391 examples from the corpus and evaluated them on 9,800 rolesets."

#: Two paragraphs, the first of which is a heading the author never meant to
#: quote.  The citation sits in the second.
MANUSCRIPT = (
    "## Methods"
    + NL
    + NL
    + "We collected 154,391 examples from the corpus [@page]"
    + NL
    + "in the first year of the project."
    + NL
    + NL
    + "The corpus is described elsewhere."
    + NL
)

BIB = (
    "@article{page,"
    + NL
    + "  author = {A, B},"
    + NL
    + "  title = {T},"
    + NL
    + "  journal = {J},"
    + NL
    + "  year = {2020},"
    + NL
    + "  file = {page.txt}"
    + NL
    + "}"
    + NL
)


def _crlf(text: str) -> str:
    return text.replace(NL, CR + NL)


def _project(root: Path, newline: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "page.txt").write_text(PAGE + NL, encoding="utf-8", newline=newline)
    (root / "m.md").write_text(MANUSCRIPT, encoding="utf-8", newline=newline)
    (root / "refs.bib").write_text(BIB, encoding="utf-8", newline=newline)
    return root


def _draft(root: Path) -> str:
    code = cli.main(
        [
            "draft",
            "m.md",
            "--bib",
            "refs.bib",
            "-o",
            "claims.md",
            "--force",
            "--root",
            str(root),
        ]
    )
    assert code == 0
    return (root / "claims.md").read_text(encoding="utf-8")


class TestTheSameFileSavedTwoWaysIsTheSameFile:
    """The reader's job: one text, however the editor wrote the line ends."""

    def test_read_text_drops_the_carriage_returns(self, tmp_path) -> None:
        path = tmp_path / "m.md"
        path.write_bytes(_crlf(MANUSCRIPT).encode("utf-8"))
        text = textnorm.read_text(path)
        assert CR not in text
        assert text.count(NL) == MANUSCRIPT.count(NL)

    def test_a_lone_carriage_return_is_a_line_break_too(self, tmp_path) -> None:
        path = tmp_path / "old.md"
        path.write_bytes(("first" + CR + "second" + CR).encode("utf-8"))
        assert textnorm.read_text(path) == "first" + NL + "second" + NL

    def test_the_file_on_disk_is_not_rewritten(self, tmp_path) -> None:
        path = tmp_path / "m.md"
        raw = _crlf(MANUSCRIPT).encode("utf-8")
        path.write_bytes(raw)
        textnorm.read_text(path)
        assert path.read_bytes() == raw, "reading is not writing"

    def test_a_bom_and_crlf_together_still_read(self, tmp_path) -> None:
        path = tmp_path / "both.md"
        path.write_bytes(b"\xef\xbb\xbf" + _crlf("hello" + NL).encode("utf-8"))
        assert textnorm.read_text(path) == "hello" + NL


class TestWhatTheAuthorSeesIsTheSameEitherWay:
    def test_draft_writes_the_same_file(self, tmp_path) -> None:
        lf = _draft(_project(tmp_path / "lf", NL))
        crlf = _draft(_project(tmp_path / "crlf", CR + NL))
        diff = list(
            difflib.unified_diff(lf.splitlines(), crlf.splitlines(), "LF", "CRLF", lineterm="")
        )
        assert not diff, "the same manuscript saved two ways produced two drafts:" + "".join(
            NL + line for line in diff
        )

    def test_the_heading_is_not_glued_onto_the_claim(self, tmp_path) -> None:
        written = _draft(_project(tmp_path / "p", CR + NL))
        for line in written.splitlines():
            if line.startswith("  We collected"):
                assert "## Methods" not in line, (
                    "the heading became part of the claim text the author is "
                    "asked to paste; before the fix this line read "
                    "'## Methods We collected 154,391 examples from the corpus ...'"
                )

    def test_the_paragraph_does_not_swallow_the_rest_of_the_document(self, tmp_path) -> None:
        root = _project(tmp_path / "p", CR + NL)
        text = textnorm.read_text(root / "m.md")
        site = next(iter(draft_module.citation_sites(text)))
        sentence, _, _ = draft_module.sentence_at(text, site.start)
        assert "The corpus is described elsewhere" not in sentence


class TestTheVerdictsAreTheSameEitherWay:
    def _check(self, root: Path) -> tuple[int, str]:
        code = cli.main(["check", "m.md", "--root", str(root), "--bib", "refs.bib"])
        return code, ""

    def test_check_agrees(self, tmp_path, capsys) -> None:
        codes = {}
        for name, newline in (("lf", NL), ("crlf", CR + NL)):
            _project(tmp_path / name, newline)
        for name, _newline in (("lf", NL), ("crlf", CR + NL)):
            code, _ = self._check(tmp_path / name)
            codes[name] = code
        assert codes["lf"] == codes["crlf"]

    def test_a_crlf_source_page_is_found(self, tmp_path) -> None:
        root = tmp_path / "p"
        root.mkdir()
        (root / "page.txt").write_bytes((PAGE + NL).replace(NL, CR + NL).encode("utf-8"))
        pages, problem = sources.extract_pages(root / "page.txt", root, use_cache=False)
        assert problem is None
        assert pages, "a CRLF page is still a page"
        assert CR not in pages[0].text
        assert PAGE in pages[0].text

    def test_a_crlf_bibliography_parses_the_same(self, tmp_path) -> None:
        from citevouch.bibtex import parse_bib

        lf = parse_bib(BIB).entries
        crlf = parse_bib(_crlf(BIB)).entries
        assert lf.keys() == crlf.keys()
        assert lf["page"].fields == crlf["page"].fields


class TestTheClaimBlockDialectIsUnaffected:
    BLOCK = (
        "Intro prose."
        + NL
        + NL
        + B3
        + "claim id=c1 source=page page=1"
        + NL
        + "quote: |"
        + NL
        + "  "
        + PAGE
        + NL
        + B3
        + NL
    )

    @pytest.mark.parametrize("newline", [NL, CR + NL])
    def test_the_block_is_read(self, tmp_path, newline: str) -> None:
        path = tmp_path / "m.md"
        path.write_text(self.BLOCK, encoding="utf-8", newline=newline)
        parsed = manuscript.parse_manuscript(textnorm.read_text(path), "m.md")
        assert len(parsed.claims) == 1
        assert parsed.claims[0].quote == PAGE
        assert parsed.findings == []


class TestTheLatexPathIsTheSameEitherWay:
    def test_a_crlf_tex_file_drafts_the_same(self, tmp_path) -> None:
        tex = (
            BS
            + "section{Methods}"
            + NL
            + NL
            + "We collected 154,391 examples from the corpus "
            + BS
            + "citep{page}."
            + NL
        )
        written = {}
        for name, newline in (("lf", NL), ("crlf", CR + NL)):
            root = tmp_path / name
            root.mkdir()
            (root / "page.txt").write_text(PAGE + NL, encoding="utf-8", newline=NL)
            (root / "refs.bib").write_text(BIB, encoding="utf-8", newline=NL)
            (root / "paper.tex").write_text(tex, encoding="utf-8", newline=newline)
            code = cli.main(
                [
                    "draft",
                    "paper.tex",
                    "--bib",
                    "refs.bib",
                    "-o",
                    "claims.md",
                    "--force",
                    "--root",
                    str(root),
                ]
            )
            assert code == 0
            written[name] = (root / "claims.md").read_text(encoding="utf-8")
        assert written["lf"] == written["crlf"]


def test_nothing_in_the_src_package_reads_bytes_and_keeps_carriage_returns() -> None:
    """The guard: one reader, so the second path cannot be forgotten."""
    source = (Path(cli.__file__).parent / "textnorm.py").read_text(encoding="utf-8")
    assert 'replace("\\r\\n", "\\n")' in source
