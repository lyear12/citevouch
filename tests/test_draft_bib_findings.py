"""`draft --bib` when the bibliography cannot be read.

Measured before this existed, with an unclosed entry in `refs.bib`:

    $ citevouch draft paper.md --bib refs.bib -o claims.md
    citevouch: 0 claim block(s) proposed (0 verbatim), 1 citation(s) left as comments
    $ grep Not -A3 claims.md
    Not proposed:

    <!-- line 1: knuth2020 - no local file: not in sources.toml, no `file`
    field in the bibliography, and no file named after the key -->

The `.bib` holds `file = {page.txt}` on line 5.  The entry never closed, so
`parse_bib` produced no entry for the key, and `draft` read "no entry" as "the
bibliography says nothing" - the same false sentence the `scan` path was fixed
for, in the one command that reads the file purely to answer that question.
`draft` also dropped every parse finding on the floor, so the author was never
told the file was unreadable at all.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = {
    **os.environ,
    "PYTHONPATH": str(ROOT / "src"),
    "PYTHONIOENCODING": "utf-8",
}

PAGE = "We collected 154,391 examples from the corpus.\n"
MANIFEST = '[sources]\npaper = "page.txt"\n'
PAPER = "We collected 154,391 examples from the corpus \\citep{knuth2020}.\n"

GOOD_BIB = """@book{knuth2020,
  author = {Knuth, Donald},
  title = {The Art of Computer Programming},
  publisher = {Addison-Wesley},
  year = {2020},
  file = {page.txt}
}
"""

# `file = {page.txt}` is there; the entry just never closes.
UNCLOSED_BIB = """@book{knuth2020,
  author = {Knuth, Donald},
  title = {The Art of Computer Programming},
  file = {page.txt}
"""

DUPLICATE_BIB = """@book{knuth2020,
  author = {Knuth, Donald},
  title = {The Art of Computer Programming},
  year = {2020},
  file = {page.txt}
}
@article{knuth2020,
  author = {Someone, Else},
  title = {A Different Paper},
  year = {1999},
  file = {page.txt}
}
"""

BINARY_BIB = "\x01\x02\x03 not a bib at all \x04\n"


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "citevouch", *args],
        cwd=root,
        env=ENV,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _project(tmp_path: Path, bib: str) -> Path:
    root = tmp_path / f"case{len(list(tmp_path.iterdir()))}"
    root.mkdir(parents=True)
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline="\n")
    (root / "sources.toml").write_text(MANIFEST, encoding="utf-8", newline="\n")
    (root / "paper.md").write_text(PAPER, encoding="utf-8", newline="\n")
    (root / "refs.bib").write_text(bib, encoding="utf-8", newline="\n")
    return root


def _draft(root: Path) -> subprocess.CompletedProcess[str]:
    return _run(
        root,
        "draft",
        "paper.md",
        "--root",
        ".",
        "-o",
        "claims.md",
        "--bib",
        "refs.bib",
    )


def _written(root: Path) -> str:
    return (root / "claims.md").read_text(encoding="utf-8")


class TestTheParseFindingsReachTheAuthor:
    def test_an_unclosed_entry_is_reported(self, tmp_path: Path) -> None:
        root = _project(tmp_path, UNCLOSED_BIB)

        drafted = _draft(root)

        assert "bib-unparsed-entry" in drafted.stderr, drafted.stderr

    def test_an_unreadable_file_is_reported(self, tmp_path: Path) -> None:
        root = _project(tmp_path, BINARY_BIB)

        drafted = _draft(root)

        assert "bib-unreadable" in drafted.stderr, drafted.stderr

    def test_a_duplicate_key_is_reported(self, tmp_path: Path) -> None:
        root = _project(tmp_path, DUPLICATE_BIB)

        drafted = _draft(root)

        assert "bib-duplicate-key" in drafted.stderr, drafted.stderr

    def test_a_clean_bibliography_says_nothing(self, tmp_path: Path) -> None:
        root = _project(tmp_path, GOOD_BIB)

        drafted = _draft(root)

        assert "bib-" not in drafted.stderr, drafted.stderr

    def test_the_line_names_the_file_and_the_place(self, tmp_path: Path) -> None:
        root = _project(tmp_path, UNCLOSED_BIB)

        drafted = _draft(root)

        line = next(row for row in drafted.stderr.splitlines() if "bib-unparsed-entry" in row)
        assert "refs.bib" in line
        assert ":1" in line


class TestTheSentenceAboutTheEntry:
    def test_it_does_not_claim_the_bibliography_is_silent(self, tmp_path: Path) -> None:
        # The `.bib` holds `file = {page.txt}`.  Saying there is no `file` field
        # sends the author to look at the field they are staring at.
        root = _project(tmp_path, UNCLOSED_BIB)

        _draft(root)

        written = _written(root)
        assert "no `file` field in the bibliography" not in written, written

    def test_it_says_the_bibliography_could_not_be_read(self, tmp_path: Path) -> None:
        root = _project(tmp_path, UNCLOSED_BIB)

        _draft(root)

        written = _written(root)
        assert "could not be fully read" in written, written

    def test_it_still_names_the_missing_file_case(self, tmp_path: Path) -> None:
        # A readable bibliography whose `file` field points at nothing keeps
        # the specific sentence: this is not the generic fallback.
        root = _project(tmp_path, GOOD_BIB.replace("page.txt", "gone.txt"))

        _draft(root)

        written = _written(root)
        assert "gone.txt" in written, written
        assert "no `file` field in the bibliography" not in written

    def test_a_readable_bibliography_with_no_entry_keeps_the_generic_sentence(
        self, tmp_path: Path
    ) -> None:
        root = _project(tmp_path, GOOD_BIB)
        (root / "paper.md").write_text(
            "We collected 154,391 examples from the corpus \\citep{lamport1994}.\n",
            encoding="utf-8",
            newline="\n",
        )

        _draft(root)

        written = _written(root)
        assert "no `file` field in the bibliography" in written, written


class TestWhatMustNotChange:
    def test_a_good_bibliography_still_proposes(self, tmp_path: Path) -> None:
        root = _project(tmp_path, GOOD_BIB)

        _draft(root)

        written = _written(root)
        assert "1 claim block(s) proposed" in written
        assert "```claim id=knuth2020 source=knuth2020 page=1" in written

    def test_the_run_still_writes_its_file(self, tmp_path: Path) -> None:
        root = _project(tmp_path, UNCLOSED_BIB)

        drafted = _draft(root)

        assert drafted.returncode == 0, drafted.stderr
        assert (root / "claims.md").is_file()


NO_FILE_FIELD_BIB = """@book{knuth2020,
  author = {Knuth, Donald},
  title = {The Art of Computer Programming},
  publisher = {Addison-Wesley},
  year = {2020}
}
"""

SECOND_BIB = """@article{knuth2020,
  author = {Someone, Else},
  title = {A Different Paper},
  year = {1999},
  file = {page.txt}
}
"""


def _draft_with(root: Path, *bibs: str) -> subprocess.CompletedProcess[str]:
    argv = ["draft", "paper.md", "--root", ".", "-o", "claims.md"]
    for bib in bibs:
        argv += ["--bib", bib]
    return _run(root, *argv)


class TestAClashBetweenTwoFilesReachesTheAuthor:
    def test_draft_says_two_files_define_one_key(self, tmp_path: Path) -> None:
        # `merge_entries` reports a key defined in two `--bib` files.  `draft`
        # reads the same files; it has to say the same thing.
        root = _project(tmp_path, GOOD_BIB)
        (root / "second.bib").write_text(SECOND_BIB, encoding="utf-8", newline="\n")

        drafted = _draft_with(root, "refs.bib", "second.bib")

        assert "bib-duplicate-key" in drafted.stderr, drafted.stderr
        line = next(row for row in drafted.stderr.splitlines() if "bib-duplicate-key" in row)
        assert "'knuth2020'" in line or "knuth2020" in line


class TestAKeyThatParsedIsNotAnUnparsedKey:
    def test_a_parsed_entry_without_a_file_field_keeps_the_generic_sentence(
        self, tmp_path: Path
    ) -> None:
        # `knuth2020` parses fine and simply has no `file` field.  It is a key
        # the bibliography answered for, so "the bibliography could not be
        # fully read" would be false about it.
        root = _project(tmp_path, NO_FILE_FIELD_BIB)

        _draft(root)

        written = _written(root)
        assert "could not be fully read" not in written, written
        assert "no `file` field in the bibliography" in written, written

    def test_the_message_names_the_key_it_could_not_place(self, tmp_path: Path) -> None:
        # Without the key the author cannot tell which citation the sentence
        # is about; the run may mention several.
        root = _project(tmp_path, UNCLOSED_BIB)

        _draft(root)

        written = _written(root)
        # The comment already carries the key as its prefix, so looking for the
        # name anywhere would pass even when the sentence drops it.  What has
        # to be true is that the *sentence* names the key it could not place.
        assert "parsed for 'knuth2020'" in written, written
