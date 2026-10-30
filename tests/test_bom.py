"""A byte-order mark is not part of the text it marks.

Notepad, Excel and PowerShell's `>` all write a UTF-8 BOM by default, so a file
that looks ordinary in every editor starts with a character no one can see.
Every reader in this tool treats its first line as syntax, and a BOM in front
of the first `claim` fence or the first `@article{` makes that line fail to
match — after which the reports describe the *consequence* in the language of
some unrelated fault:

* a manuscript whose claim block was closed one line later was reported as
  `claim-block-unclosed` and `no-claim-blocks`;
* a bibliography holding the key was reported as `bib-key-missing`, a high
  severity finding that says the paper is not cited.

Both sentences send the author somewhere the problem is not.  `read_text` in
`textnorm` removes the mark at the boundary, and every file this tool reads now
goes through it.

There is deliberately no test here for a BOM on a *source* document (a PDF's
extracted text, or a `.txt` corpus).  A mark at the start of searchable running
text is just a character in front of the first word: normalisation drops it and
matching is unaffected either way, so a test for it would pass before the fix
and after it — a test that cannot fail is a record of what the code does, not a
guard over what it must do.  Source reads go through `read_text` for the same
reason the others do (one boundary, one behaviour), not because the BOM was
hurting them.
"""

from __future__ import annotations

from pathlib import Path

from citevouch.cli import main

BOM = b"\xef\xbb\xbf"
NL = chr(10)
GOOD = "We trained on two corpora and counted 40,688 entries." + NL
CLAIM = (
    "```claim id=c1 source=p"
    + NL
    + ">> We trained on two corpora and counted 40,688 entries."
    + NL
    + "```"
    + NL
)
BIB = "@article{paper, author={A}, title={T}, journal={J}, year={2026}}" + NL


def _project(
    tmp_path: Path,
    manuscript: bytes = CLAIM.encode("utf-8"),
    bib: bytes = BIB.encode("utf-8"),
    source: bytes = GOOD.encode("utf-8"),
) -> Path:
    root = tmp_path / "p"
    root.mkdir(parents=True, exist_ok=True)
    (root / "p.txt").write_bytes(source)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'p = "p.txt"' + NL, encoding="utf-8", newline=NL
    )
    (root / "refs.bib").write_bytes(bib)
    (root / "m.md").write_bytes(manuscript)
    return root


def _codes(captured: str) -> list[str]:
    return [line.split()[1] for line in captured.splitlines() if line.startswith("[")]


class TestTheMarkIsNotContent:
    def test_a_manuscript_with_a_bom_is_read_like_one_without(self, tmp_path: Path, capsys):
        plain = _project(tmp_path / "plain")
        assert main(["check", "m.md", "--root", str(plain)]) == 0

        marked = _project(tmp_path / "marked", manuscript=BOM + CLAIM.encode("utf-8"))
        assert main(["check", "m.md", "--root", str(marked)]) == 0
        # capsys accumulates, so read only what the second run printed.
        assert _codes(capsys.readouterr().out)[-1:] == ["quote-found"]

    def test_a_bom_does_not_hide_a_well_formed_claim_block(self, tmp_path: Path, capsys):
        root = _project(tmp_path, manuscript=BOM + CLAIM.encode("utf-8"))
        code = main(["check", "m.md", "--root", str(root)])
        out = capsys.readouterr().out
        assert code == 0
        assert "claim-block-unclosed" not in out
        assert "no-claim-blocks" not in out

    def test_a_bibliography_with_a_bom_parses_like_one_without(self, tmp_path: Path, capsys):
        plain = _project(tmp_path / "plain")
        assert main(["check", "m.md", "--root", str(plain), "--bib", "refs.bib"]) in (0, 1)
        without = capsys.readouterr().out

        marked = _project(tmp_path / "marked", bib=BOM + BIB.encode("utf-8"))
        assert main(["check", "m.md", "--root", str(marked), "--bib", "refs.bib"]) in (0, 1)
        with_mark = capsys.readouterr().out

        # Only the paths differ between the two runs, and those are printed
        # relative to their own root, so the reports must agree exactly.
        assert with_mark == without
        assert "bib-entry-header-unparsed" not in with_mark

    def test_a_ledger_with_a_bom_is_read_rather_than_refused(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        assert main(["scan", "m.md", "--root", str(root)]) == 0
        ledger = root / "citevouch.lock.json"
        ledger.write_bytes(BOM + ledger.read_bytes())
        code = main(["verify", "m.md", "--root", str(root)])
        captured = capsys.readouterr()
        assert code == 0, captured.err
        assert "1 verified" in captured.out

    def test_a_ledger_with_a_bom_does_not_need_a_rescan(self, tmp_path: Path):
        root = _project(tmp_path)
        assert main(["scan", "m.md", "--root", str(root)]) == 0
        ledger = root / "citevouch.lock.json"
        ledger.write_bytes(BOM + ledger.read_bytes())
        # A second scan must find the same work to do, not a different project.
        assert main(["scan", "m.md", "--root", str(root)]) == 0


class TestTheHelperItself:
    def test_a_leading_mark_is_removed(self, tmp_path: Path):
        from citevouch.textnorm import read_text

        path = tmp_path / "x.md"
        path.write_bytes(BOM + b"hello")
        assert read_text(path) == "hello"

    def test_a_mark_in_the_middle_is_left_alone(self, tmp_path: Path):
        from citevouch.textnorm import read_text

        path = tmp_path / "x.md"
        path.write_bytes(("a" + chr(0xFEFF) + "b").encode("utf-8"))
        assert read_text(path) == "a" + chr(0xFEFF) + "b"

    def test_a_file_without_one_is_unchanged(self, tmp_path: Path):
        from citevouch.textnorm import read_text

        path = tmp_path / "x.md"
        path.write_bytes(b"hello")
        assert read_text(path) == "hello"
