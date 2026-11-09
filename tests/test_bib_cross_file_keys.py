"""Two `--bib` files that define the same key.

`bib-duplicate-key` fires when one file defines a key twice.  Two files each
defining it once produced no finding at all: `scan` merged the mappings with
`dict.update`, so the later file silently replaced the earlier one and the run
stayed green.  That is the same mistake with a different boundary, and the
author's evidence for the claim is now whichever file happened to be passed
last - which the command line decides, not the author.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENV = {
    **os.environ,
    "PYTHONPATH": str(ROOT / "src"),
    "PYTHONIOENCODING": "utf-8",
}

PAGE = "We collected 154,391 examples from the corpus.\n"
MANIFEST = '[sources]\npaper = "page.txt"\n'

MANUSCRIPT = """```claim id=c1 source=paper page=1 ref=knuth2020
quote: |
  We collected 154,391 examples from the corpus.
```
"""

KNUTH_BOOK = """@book{knuth2020,
  author = {Knuth, Donald},
  title = {The Art of Computer Programming},
  publisher = {Addison-Wesley},
  year = {2020}
}
"""

KNUTH_ARTICLE = """@article{knuth2020,
  author = {Someone, Else},
  title = {A Completely Different Paper},
  journal = {Some Journal},
  year = {1999}
}
"""

LAMPORT = """@book{lamport1994,
  author = {Lamport, Leslie},
  title = {LaTeX: A Document Preparation System},
  publisher = {Addison-Wesley},
  year = {1994}
}
"""


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "citevouch", *args],
        cwd=root,
        env=ENV,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _project(tmp_path: Path, bibs: dict[str, str]) -> Path:
    root = tmp_path / f"case{len(list(tmp_path.iterdir()))}"
    root.mkdir(parents=True)
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline="\n")
    (root / "sources.toml").write_text(MANIFEST, encoding="utf-8", newline="\n")
    (root / "manuscript.md").write_text(MANUSCRIPT, encoding="utf-8", newline="\n")
    for name, body in bibs.items():
        (root / name).write_text(body, encoding="utf-8", newline="\n")
    return root


def _bib_flags(bibs: dict[str, str]) -> list[str]:
    flags: list[str] = []
    for name in bibs:
        flags += ["--bib", name]
    return flags


def _scan(root: Path, bibs: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return _run(root, "scan", "manuscript.md", "--root", ".", *_bib_flags(bibs))


def _recorded(root: Path) -> subprocess.CompletedProcess[str]:
    return _run(root, "check", "manuscript.md", "--root", ".", "--use-recorded")


def _live(root: Path, bibs: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return _run(root, "check", "manuscript.md", "--root", ".", *_bib_flags(bibs))


def _duplicates(proc: subprocess.CompletedProcess[str]) -> list[str]:
    return [
        line
        for line in proc.stdout.splitlines()
        if line.startswith("[") and " bib-duplicate-key " in line
    ]


class TestTwoFilesDefiningOneKey:
    def test_the_clash_is_reported(self, tmp_path: Path) -> None:
        bibs = {"a.bib": KNUTH_BOOK, "b.bib": KNUTH_ARTICLE}
        root = _project(tmp_path, bibs)

        scan = _scan(root, bibs)

        assert scan.returncode == 1, scan.stdout
        duplicates = _duplicates(scan)
        assert len(duplicates) == 1, scan.stdout

    def test_the_sentence_names_both_files(self, tmp_path: Path) -> None:
        bibs = {"a.bib": KNUTH_BOOK, "b.bib": KNUTH_ARTICLE}
        root = _project(tmp_path, bibs)

        scan = _scan(root, bibs)

        line = _duplicates(scan)[0]
        assert "a.bib" in line
        assert "b.bib" in line
        assert "knuth2020" in line

    def test_it_is_high(self, tmp_path: Path) -> None:
        bibs = {"a.bib": KNUTH_BOOK, "b.bib": KNUTH_ARTICLE}
        root = _project(tmp_path, bibs)

        scan = _scan(root, bibs)

        assert "[high] bib-duplicate-key" in scan.stdout

    def test_the_recorded_pass_says_it_too(self, tmp_path: Path) -> None:
        bibs = {"a.bib": KNUTH_BOOK, "b.bib": KNUTH_ARTICLE}
        root = _project(tmp_path, bibs)
        assert _scan(root, bibs).returncode == 1

        recorded = _recorded(root)

        assert recorded.returncode == 1, recorded.stdout
        assert _duplicates(recorded), recorded.stdout

    def test_the_live_pass_says_it_too(self, tmp_path: Path) -> None:
        bibs = {"a.bib": KNUTH_BOOK, "b.bib": KNUTH_ARTICLE}
        root = _project(tmp_path, bibs)

        live = _live(root, bibs)

        assert live.returncode == 1, live.stdout
        assert _duplicates(live), live.stdout

    def test_the_order_on_the_command_line_does_not_hide_it(self, tmp_path: Path) -> None:
        one = _project(tmp_path, {"a.bib": KNUTH_BOOK, "b.bib": KNUTH_ARTICLE})
        two = _project(tmp_path, {"b.bib": KNUTH_ARTICLE, "a.bib": KNUTH_BOOK})

        first = _scan(one, {"a.bib": KNUTH_BOOK, "b.bib": KNUTH_ARTICLE})
        second = _scan(two, {"b.bib": KNUTH_ARTICLE, "a.bib": KNUTH_BOOK})

        assert _duplicates(first)
        assert _duplicates(second)


class TestThreeFiles:
    def test_every_clash_is_reported(self, tmp_path: Path) -> None:
        bibs = {
            "a.bib": KNUTH_BOOK,
            "b.bib": KNUTH_ARTICLE,
            "c.bib": LAMPORT.replace("lamport1994", "knuth2020"),
        }
        root = _project(tmp_path, bibs)

        scan = _scan(root, bibs)

        # The first clash is between a.bib and b.bib; the second is between the
        # winner so far and c.bib.
        assert len(_duplicates(scan)) == 2, scan.stdout


class TestWhatMustNotChange:
    def test_two_files_with_different_keys_are_silent(self, tmp_path: Path) -> None:
        bibs = {"a.bib": KNUTH_BOOK, "b.bib": LAMPORT}
        root = _project(tmp_path, bibs)

        scan = _scan(root, bibs)

        assert scan.returncode == 0, scan.stdout
        assert not _duplicates(scan)

    def test_one_file_with_one_entry_is_silent(self, tmp_path: Path) -> None:
        bibs = {"a.bib": KNUTH_BOOK}
        root = _project(tmp_path, bibs)

        scan = _scan(root, bibs)

        assert scan.returncode == 0, scan.stdout
        assert not _duplicates(scan)

    def test_a_key_twice_in_one_file_is_reported_once(self, tmp_path: Path) -> None:
        bibs = {"a.bib": KNUTH_BOOK + KNUTH_ARTICLE}
        root = _project(tmp_path, bibs)

        scan = _scan(root, bibs)

        assert len(_duplicates(scan)) == 1, scan.stdout

    def test_the_same_file_named_twice_is_not_a_clash(self, tmp_path: Path) -> None:
        # `--bib a.bib --bib a.bib` names one file, twice.  Nothing is
        # overwritten: both passes read the same bytes and produce the same
        # entry.  Reporting it as a clash would teach the author to distrust a
        # finding that is about the command line, not about the bibliography.
        bibs = {"a.bib": KNUTH_BOOK}
        root = _project(tmp_path, bibs)

        scan = _run(
            root, "scan", "manuscript.md", "--root", ".", "--bib", "a.bib", "--bib", "a.bib"
        )

        assert scan.returncode == 0, scan.stdout
        assert not _duplicates(scan), scan.stdout

    def test_the_later_file_still_wins(self, tmp_path: Path) -> None:
        # Reporting the clash must not change which entry the run judged, or
        # the verdict would depend on the fix rather than on the evidence.
        bibs = {"a.bib": KNUTH_BOOK, "b.bib": KNUTH_ARTICLE}
        root = _project(tmp_path, bibs)

        assert _scan(root, bibs).returncode == 1

        recorded = _recorded(root)

        assert "quote-found" in recorded.stdout


class TestTheSubsetOfWorkThatMatters:
    @pytest.mark.parametrize(
        ("first", "second"),
        [
            (KNUTH_BOOK, KNUTH_ARTICLE),
            (KNUTH_ARTICLE, KNUTH_BOOK),
        ],
    )
    def test_a_clash_of_two_different_works_is_always_reported(
        self, tmp_path: Path, first: str, second: str
    ) -> None:
        # Two entries that disagree about the title are two different works;
        # the author has to pick one.
        bibs = {"a.bib": first, "b.bib": second}
        root = _project(tmp_path, bibs)

        scan = _scan(root, bibs)

        assert _duplicates(scan), scan.stdout
