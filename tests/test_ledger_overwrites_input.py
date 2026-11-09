"""`scan --ledger` must not be able to write the ledger over an input.

`draft -o` has refused an output that names a file the project reads since
v0.19.52, because a proposal written over `sources.toml` leaves every claim
unable to resolve.  `scan --ledger` had no such guard, and the ledger is the one
file this tool is *meant* to write - so the flag looks like an output flag and
nothing about it looks dangerous.  Measured, on a project with one claim:

    $ citevouch scan paper.md --root . --ledger paper.md
    citevouch: wrote paper.md (1 claim)          ->  exit 0

The manuscript was 97 bytes of Markdown and 753 bytes of JSON afterwards.  The
same call with `--ledger sources.toml` replaced the manifest and with
`--ledger page.txt` replaced the page the quote came from.  Each exited 0 and
each said what it had written, so the run reported success while deleting the
evidence it had just recorded.

Every test asserts the file's bytes, not only the exit code: a guard that
refuses after writing is not a guard.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from citevouch.cli import main

PAGE = "We collected 154,391 examples from the corpus.\n"
MANIFEST = '[sources]\npaper = "page.txt"\n'
PAPER = """\
# A note on construction learning

```claim id=c1 source=paper page=1
quote: |
  We collected 154,391 examples from the corpus.
claim: |
  The corpus has 154,391 examples.
```
"""
BIBLIOGRAPHY = "@article{knuth2020, title = {A title}, year = {2026}}\n"


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline="\n")
    (root / "sources.toml").write_text(MANIFEST, encoding="utf-8", newline="\n")
    (root / "paper.md").write_text(PAPER, encoding="utf-8", newline="\n")
    (root / "refs.bib").write_text(BIBLIOGRAPHY, encoding="utf-8", newline="\n")
    return root


def _scan(root: Path, *extra: str) -> int:
    return main(["scan", str(root / "paper.md"), "--root", str(root), *extra])


class TestTheFilesTheRunReadsAreNotReplaced:
    def test_the_manuscript_is_not_replaced(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        assert _scan(root, "--ledger", "paper.md") == 2
        assert (root / "paper.md").read_text(encoding="utf-8") == PAPER

    def test_the_manifest_is_not_replaced(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        assert _scan(root, "--ledger", "sources.toml") == 2
        assert (root / "sources.toml").read_text(encoding="utf-8") == MANIFEST

    def test_the_page_a_quote_comes_from_is_not_replaced(self, tmp_path: Path) -> None:
        # Bound by the manifest rather than named on the command line, so a
        # guard built only from flags would miss it - which is exactly how the
        # same defect reached `draft -o`.
        root = _project(tmp_path)
        assert _scan(root, "--ledger", "page.txt") == 2
        assert (root / "page.txt").read_text(encoding="utf-8") == PAGE

    def test_a_bibliography_named_on_the_command_line_is_not_replaced(
        self, tmp_path: Path
    ) -> None:
        root = _project(tmp_path)
        assert _scan(root, "--bib", "refs.bib", "--ledger", "refs.bib") == 2
        assert (root / "refs.bib").read_text(encoding="utf-8") == BIBLIOGRAPHY

    def test_a_source_named_on_the_command_line_is_not_replaced(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        (root / "extra.txt").write_text(PAGE, encoding="utf-8", newline="\n")
        assert _scan(root, "--source", "extra.txt", "--ledger", "extra.txt") == 2
        assert (root / "extra.txt").read_text(encoding="utf-8") == PAGE

    @pytest.mark.parametrize("spelling", ["page.txt", "./page.txt"])
    def test_the_spelling_of_the_path_does_not_matter(
        self, tmp_path: Path, spelling: str
    ) -> None:
        root = _project(tmp_path)
        assert _scan(root, "--ledger", spelling) == 2
        assert (root / "page.txt").read_text(encoding="utf-8") == PAGE

    def test_a_path_that_only_resolves_to_the_input_is_still_refused(
        self, tmp_path: Path
    ) -> None:
        # ``Path`` throws away a leading ``./``, so the spelling test above
        # cannot tell a comparison that resolves from one that compares text.
        # ``..`` survives normalisation, so this names one file two ways.
        root = _project(tmp_path)
        assert _scan(root, "--ledger", "elsewhere/../page.txt") == 2
        assert (root / "page.txt").read_text(encoding="utf-8") == PAGE


class TestWhatTheMessageSays:
    def test_it_names_the_ledger_and_the_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root = _project(tmp_path)
        assert _scan(root, "--ledger", "paper.md") == 2
        shown = capsys.readouterr().err
        assert "paper.md" in shown
        assert "--ledger" in shown

    def test_it_names_the_binding_not_only_the_path(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # The author never typed `page.txt` anywhere, so a message that only
        # echoed the path leaves them asking where it came from.
        root = _project(tmp_path)
        assert _scan(root, "--ledger", "page.txt") == 2
        shown = capsys.readouterr().err
        assert "sources.toml" in shown


class TestTheLedgerIsStillWrittenWhereItBelongs:
    def test_the_default_location_still_works(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        assert _scan(root) == 0
        assert (root / "citevouch.lock.json").is_file()

    def test_another_file_name_still_works(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        assert _scan(root, "--ledger", "evidence/other.json") == 0
        assert (root / "evidence" / "other.json").is_file()

    def test_a_dry_run_writes_nothing_and_is_not_refused(self, tmp_path: Path) -> None:
        # Nothing is written, so there is nothing to protect against.
        root = _project(tmp_path)
        assert _scan(root, "--dry-run", "--ledger", "paper.md") == 0
        assert (root / "paper.md").read_text(encoding="utf-8") == PAPER
