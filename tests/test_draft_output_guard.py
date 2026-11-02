"""`draft -o` must not write over a file the project is read from.

The guard this file tests protected the manuscript and, until now, nothing else,
so ``-o sources.toml --force`` reported success and left the project unable to
resolve a single claim: `check` then answered `[high] source-missing ... the
manifest could not be read: sources.toml could not be read as TOML` for every
claim, and `doctor` failed its manifest check. ``-o citevouch.lock.json
--force`` did the same to the ledger, after which `verify` said the ledger is
not readable JSON - the recorded evidence for the whole manuscript, gone.

Each test names the file, the exit code, and that the file is byte-identical
afterwards. That last part is the point: a guard that refuses after writing is
not a guard.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from citevouch.cli import main

MANUSCRIPT = """\
# A note on construction learning

The grammar was induced from that corpus by hand [@paper].
"""

CHECKED = """\
# The checked manuscript

```claim id=c1 source=paper page=1
quote: |
  The corpus the grammar was induced from contains 154,391 utterances.
claim: |
  The corpus has 154,391 utterances.
```
"""

PAPER = "The corpus the grammar was induced from contains 154,391 utterances.\n"

MANIFEST = '[sources]\npaper = "papers/paper.txt"\n'

BIBLIOGRAPHY = "@article{paper, title = {A title}, year = {2026}}\n"


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "papers").mkdir(parents=True)
    (root / "papers" / "paper.txt").write_text(PAPER, encoding="utf-8", newline="\n")
    (root / "manuscript.md").write_text(MANUSCRIPT, encoding="utf-8", newline="\n")
    (root / "sources.toml").write_text(MANIFEST, encoding="utf-8", newline="\n")
    return root


def _draft(root: Path, output: str, *extra: str) -> int:
    return main(
        [
            "draft",
            str(root / "manuscript.md"),
            "--root",
            str(root),
            "-o",
            output,
            "--force",
            *extra,
        ]
    )


class TestTheInputsItReadsAreProtected:
    def test_the_manifest_is_not_replaced(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        assert _draft(root, "sources.toml") == 2
        assert (root / "sources.toml").read_text(encoding="utf-8") == MANIFEST

    def test_the_other_manifest_name_is_not_created(self, tmp_path: Path) -> None:
        # Nothing is overwritten here, which is why it looked harmless: the
        # project ends up with both manifest names and every claim stops
        # resolving, because two manifests are refused instead of guessed
        # between.
        root = _project(tmp_path)
        assert _draft(root, "sources.json") == 2
        assert not (root / "sources.json").exists()

    def test_a_bibliography_the_run_reads_is_not_replaced(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        (root / "refs.bib").write_text(BIBLIOGRAPHY, encoding="utf-8", newline="\n")
        assert _draft(root, "refs.bib", "--bib", "refs.bib") == 2
        assert (root / "refs.bib").read_text(encoding="utf-8") == BIBLIOGRAPHY

    def test_a_source_the_run_was_given_is_not_replaced(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        (root / "papers" / "extra.txt").write_text(PAPER, encoding="utf-8", newline="\n")
        assert _draft(root, "papers/extra.txt", "--source", "papers/extra.txt") == 2
        assert (root / "papers" / "extra.txt").read_text(encoding="utf-8") == PAPER

    def test_the_ledger_is_not_replaced(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        (root / "checked.md").write_text(CHECKED, encoding="utf-8", newline="\n")
        assert main(["scan", str(root / "checked.md"), "--root", str(root), "--quiet"]) == 0
        recorded = (root / "citevouch.lock.json").read_text(encoding="utf-8")
        assert _draft(root, "citevouch.lock.json") == 2
        assert (root / "citevouch.lock.json").read_text(encoding="utf-8") == recorded


class TestWhatTheMessageSays:
    def test_it_names_the_output_and_another_one_that_works(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root = _project(tmp_path)
        assert _draft(root, "sources.toml") == 2
        shown = capsys.readouterr().err
        assert "sources.toml" in shown
        assert "claims.md" in shown

    def test_the_manifest_message_says_the_file_could_never_be_a_manifest(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # A proposal file is Markdown with HTML comments; it cannot be a TOML
        # table, so writing it there is a mistake about what the destination is,
        # not a near miss at a valid manifest.
        root = _project(tmp_path)
        assert _draft(root, "sources.toml") == 2
        assert "could never be a manifest" in capsys.readouterr().err

    def test_force_does_not_reach_the_guard(self, tmp_path: Path) -> None:
        # --force exists to replace a proposal the author already looked at. It
        # is not a promise that any path is safe, and the guard must not read it
        # as consent.
        root = _project(tmp_path)
        (root / "checked.md").write_text(CHECKED, encoding="utf-8", newline="\n")
        assert main(["scan", str(root / "checked.md"), "--root", str(root), "--quiet"]) == 0
        for output in ("sources.toml", "sources.json", "citevouch.lock.json"):
            assert _draft(root, output) == 2
        assert (root / "sources.toml").read_text(encoding="utf-8") == MANIFEST
        assert not (root / "sources.json").exists()


class TestTheGuardIsTheOnlyThingRefusing:
    def test_claims_md_is_written(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        assert (
            main(
                [
                    "draft",
                    str(root / "manuscript.md"),
                    "--root",
                    str(root),
                    "-o",
                    "claims.md",
                    "--quiet",
                ]
            )
            == 0
        )
        assert (root / "claims.md").is_file()

    def test_scan_still_writes_the_ledger(self, tmp_path: Path) -> None:
        # The guard belongs to draft. scan writes the ledger on purpose, and a
        # guard that leaked into it would leave the tool unable to record
        # anything at all.
        root = _project(tmp_path)
        (root / "checked.md").write_text(CHECKED, encoding="utf-8", newline="\n")
        assert main(["scan", str(root / "checked.md"), "--root", str(root), "--quiet"]) == 0
        assert (root / "citevouch.lock.json").is_file()
