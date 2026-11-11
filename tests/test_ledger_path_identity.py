"""Which document does the ledger describe?

The stale check compares the ledger's recorded manuscript against the one the
command was asked about.  Comparing *names* answers "is this the same
document" only while two documents cannot share a name - and they can, in two
directories of one project.

Measured before the fix, with a ledger recorded for `sub/m.md`:

    verify m.md --root .                    -> 1, ledger-stale, changed since the ledger was written
    verify m.md --root . --allow-stale      -> 0, [info] quote-found at m.md:1 (c1)

The second line is a green verdict quoting `sub/m.md`'s page for a document the
command was asked about, and it reaches it through the one branch the flag is
allowed to answer.  "Changed since the ledger was written" is also the wrong
sentence: nothing changed, the ledger is about a different file.

The fix compares the paths the way the ledger stores them - relative to the
root, with forward slashes - so a spelling that means the same file (`./m.md`,
`sub/../m.md`) stays quiet while a path that names another file does not.
"""

from __future__ import annotations

import json
from pathlib import Path

from citevouch.cli import main

NL = chr(10)
B3 = chr(96) * 3

GOOD = "The corpus holds 40,688 examples of written English."
ELSEWHERE = "Something else is written on this page entirely."


def _block(claim_id: str, quote: str) -> str:
    return (
        B3
        + f"claim id={claim_id} source=paper page=1"
        + NL
        + "quote: |"
        + NL
        + "  "
        + quote
        + NL
        + B3
        + NL
    )


def _project(tmp_path: Path) -> Path:
    """A project whose two directories each hold a `m.md`."""
    (tmp_path / "sub").mkdir()
    (tmp_path / "page.txt").write_text("Preface" + NL + GOOD + NL, encoding="utf-8", newline=NL)
    (tmp_path / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    (tmp_path / "sub" / "m.md").write_text(_block("c1", GOOD), encoding="utf-8", newline=NL)
    (tmp_path / "m.md").write_text(_block("zzz", ELSEWHERE), encoding="utf-8", newline=NL)
    return tmp_path


def _record(root: Path) -> None:
    assert main(["scan", "sub/m.md", "--root", str(root)]) == 0


class TestTheSameNameInAnotherDirectory:
    """`m.md` and `sub/m.md` are two documents that one name cannot tell apart."""

    def test_the_ledger_recorded_the_other_one(self, tmp_path: Path):
        root = _project(tmp_path)
        _record(root)
        blob = json.loads((root / "citevouch.lock.json").read_text(encoding="utf-8"))
        assert blob["manuscript"] == "sub/m.md"

    def test_verify_refuses_it_without_the_flag(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        _record(root)
        capsys.readouterr()
        code = main(["verify", "m.md", "--root", str(root)])
        out = capsys.readouterr().out
        assert code == 1, out
        assert "ledger-stale" in out
        assert "ledger describes sub/m.md" in out

    def test_verify_refuses_it_with_the_flag(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        _record(root)
        capsys.readouterr()
        code = main(["verify", "m.md", "--root", str(root), "--allow-stale"])
        out = capsys.readouterr().out
        assert code == 1, out
        assert "ledger-stale" in out
        assert "quote-found" not in out
        assert "1 verified" not in out

    def test_check_use_recorded_refuses_it_with_the_flag(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        _record(root)
        capsys.readouterr()
        code = main(["check", "m.md", "--root", str(root), "--use-recorded", "--allow-stale"])
        out = capsys.readouterr().out
        assert code == 1, out
        assert "quote-found" not in out

    def test_it_does_not_accuse_the_author_of_an_edit(self, tmp_path: Path, capsys):
        """Nothing changed - the ledger is about a different file."""
        root = _project(tmp_path)
        _record(root)
        capsys.readouterr()
        code = main(["verify", "m.md", "--root", str(root), "--allow-stale"])
        out = capsys.readouterr().out
        assert code == 1, out
        assert "changed since the ledger was written" not in out

    def test_the_document_it_does_describe_is_still_fine(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        _record(root)
        capsys.readouterr()
        code = main(["verify", "sub/m.md", "--root", str(root)])
        out = capsys.readouterr().out
        assert code == 0, out
        assert "quote-found" in out


class TestTheSameDocumentSpelledTwoWays:
    """The comparison must not buy correctness with false accusations."""

    def test_the_dotted_spelling_is_the_same_document(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        _record(root)
        capsys.readouterr()
        code = main(["verify", "./sub/m.md", "--root", str(root)])
        out = capsys.readouterr().out
        assert code == 0, out
        assert "ledger-stale" not in out

    def test_a_detour_through_the_parent_is_the_same_document(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        _record(root)
        capsys.readouterr()
        code = main(["verify", "sub/../sub/m.md", "--root", str(root)])
        out = capsys.readouterr().out
        assert code == 0, out
        assert "ledger-stale" not in out

    def test_an_absolute_path_is_the_same_document(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        _record(root)
        capsys.readouterr()
        code = main(["verify", str(root / "sub" / "m.md"), "--root", str(root)])
        out = capsys.readouterr().out
        assert code == 0, out
        assert "ledger-stale" not in out


class TestTheLiveCheckHasNoLedgerToDisagreeWith:
    """`check` without `--use-recorded` scans and verifies in one run.

    The ledger it compares against was written from this exact file seconds
    earlier, so the identity guard can never be the reason a fresh run fails.
    It was: an earlier version of the guard asked the filesystem first and the
    two `resolve()` calls disagreed, so `check` reported
    `ledger describes manuscript.md, but this check was asked about
    manuscript.md` - two identical names, called different documents.
    """

    def test_the_live_check_verifies_its_own_scan(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        capsys.readouterr()
        code = main(["check", "sub/m.md", "--root", str(root)])
        out = capsys.readouterr().out
        assert code == 0, out
        assert "quote-found" in out
        assert "ledger-stale" not in out

    def test_it_is_red_for_the_quote_and_not_for_the_ledger(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        capsys.readouterr()
        code = main(["check", "m.md", "--root", str(root)])
        out = capsys.readouterr().out
        # `m.md` quotes a sentence this project's only source does not carry,
        # so the run is red - but for the quote, not for the ledger.
        assert code == 1, out
        assert "quote-missing" in out
        assert "ledger-stale" not in out

    def test_the_dotted_spelling_checks_live(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        capsys.readouterr()
        code = main(["check", "./sub/m.md", "--root", str(root)])
        out = capsys.readouterr().out
        assert code == 0, out
        assert "ledger-stale" not in out


class TestAManuscriptOutsideTheRoot:
    """`recorded_path` cannot make an outside path relative - but it can be exact.

    It used to keep the caller's spelling, so one file had as many ledger
    spellings as there were ways to type it.  Measured: a ledger recorded from
    `C:\\...\\papers\\m.md`, then asked about the same file spelled
    `..\\papers\\m.md` from inside the project:

        verify ..\\papers\\m.md --root proj  -> 1, ledger-stale
        "ledger describes C:\\\\...\\\\papers\\\\m.md, but this check was asked about
         C:\\\\...\\\\proj\\\\..\\\\papers\\\\m.md"
    """

    def _outside(self, tmp_path: Path) -> tuple[Path, Path]:
        project = tmp_path / "project"
        project.mkdir()
        _project(project)
        papers = tmp_path / "papers"
        papers.mkdir()
        paper = papers / "m.md"
        paper.write_text(_block("c1", GOOD), encoding="utf-8", newline=NL)
        return project, paper

    def test_the_ledger_stores_an_exact_path(self, tmp_path: Path):
        project, paper = self._outside(tmp_path)
        assert main(["scan", str(paper), "--root", str(project)]) == 0
        blob = json.loads((project / "citevouch.lock.json").read_text(encoding="utf-8"))
        recorded = blob["manuscript"]
        assert recorded == str(paper.resolve()), recorded

    def test_a_relative_spelling_of_it_is_the_same_document(self, tmp_path: Path, capsys):
        project, paper = self._outside(tmp_path)
        assert main(["scan", str(paper), "--root", str(project)]) == 0
        capsys.readouterr()
        spelling = str(Path("..") / "papers" / "m.md")
        # Typed from inside the project, which is where an author stands.
        code = main(["verify", spelling, "--root", str(project)])
        out = capsys.readouterr().out
        assert code == 0, out
        assert "ledger-stale" not in out

    def test_the_scanning_spelling_still_works(self, tmp_path: Path, capsys):
        project, paper = self._outside(tmp_path)
        assert main(["scan", str(paper), "--root", str(project)]) == 0
        capsys.readouterr()
        code = main(["check", str(paper), "--root", str(project), "--use-recorded"])
        out = capsys.readouterr().out
        assert code == 0, out
        assert "ledger-stale" not in out

    def test_a_different_outside_document_is_still_refused(self, tmp_path: Path, capsys):
        project, paper = self._outside(tmp_path)
        assert main(["scan", str(paper), "--root", str(project)]) == 0
        other = tmp_path / "papers" / "other.md"
        other.write_text(_block("zzz", ELSEWHERE), encoding="utf-8", newline=NL)
        capsys.readouterr()
        code = main(["verify", str(other), "--root", str(project)])
        out = capsys.readouterr().out
        assert code == 1, out
        assert "ledger-stale" in out
