"""`draft` must not depend on which directory it was launched from.

Every other command resolves a path once, through `scan._resolve`: a path that
already works is used as typed, and anything else is taken relative to `--root`.
That is what lets `citevouch check paper/m.md --root paper` be the same check as
`cd paper && citevouch check m.md`, which is how people actually type it.

`draft` wrote its proposal correctly either way, and then opened the source file
with the *relative* path it had just recorded - so the resolution happened twice,
the second time against the process directory. From one level above the project
that meant ``./page.txt`` instead of ``<root>/page.txt``, and the proposal said::

    <!-- line 1: paper - source file page.txt does not exist -->

about a file sitting in the project. Measured on one project, nothing changed but
the working directory: 1 proposal from inside, 0 from outside.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from citevouch.cli import main

BIB = "@article{paper, title={X}, year={2020}, author={A}, journal={J}, file={page.txt}}\n"
MANUSCRIPT = "We collected 40,688 examples in the corpus [@paper].\n"
PAGE = "We collected 40,688 examples in the corpus.\n"


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "paper"
    root.mkdir()
    (root / "m.md").write_text(MANUSCRIPT, encoding="utf-8", newline="\n")
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline="\n")
    (root / "refs.bib").write_text(BIB, encoding="utf-8", newline="\n")
    return root


def _run(argv: list[str], cwd: Path) -> int:
    previous = Path.cwd()
    os.chdir(cwd)
    try:
        return main(argv)
    finally:
        os.chdir(previous)


class TestTheSameProjectAnswersTheSameWayFromEitherSide:
    """Both spellings are the same project, so both must produce a proposal."""

    def test_launched_from_inside_the_project(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        code = _run(
            ["draft", "m.md", "-o", "out.md", "--root", ".", "--bib", "refs.bib", "--quiet"],
            root,
        )
        assert code == 0
        written = (root / "out.md").read_text(encoding="utf-8")
        assert "```claim" in written, written
        assert "does not exist" not in written, written

    def test_launched_from_above_the_project(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        code = _run(
            [
                "draft",
                "paper/m.md",
                "-o",
                "out.md",
                "--root",
                "paper",
                "--bib",
                "paper/refs.bib",
                "--quiet",
            ],
            tmp_path,
        )
        assert code == 0
        written = (root / "out.md").read_text(encoding="utf-8")
        assert "```claim" in written, written
        assert "does not exist" not in written, written

    def test_the_two_proposals_are_the_same_file(self, tmp_path: Path) -> None:
        """The comparison, not the two halves: one command, two directories."""
        root = _project(tmp_path)
        assert (
            _run(
                [
                    "draft",
                    "m.md",
                    "-o",
                    "inside.md",
                    "--root",
                    ".",
                    "--bib",
                    "refs.bib",
                    "--quiet",
                ],
                root,
            )
            == 0
        )
        assert (
            _run(
                [
                    "draft",
                    "paper/m.md",
                    "-o",
                    "outside.md",
                    "--root",
                    "paper",
                    "--bib",
                    "paper/refs.bib",
                    "--quiet",
                ],
                tmp_path,
            )
            == 0
        )
        inside = (root / "inside.md").read_text(encoding="utf-8").replace("inside.md", "OUT")
        outside = (root / "outside.md").read_text(encoding="utf-8").replace("outside.md", "OUT")
        assert inside == outside


class TestTheManifestPathIsReadFromEitherSideToo:
    """The manifest answer went through the same second resolution."""

    def test_a_key_the_manifest_binds_is_proposed_from_above(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        (root / "sources.toml").write_text(
            '[sources]\npaper = "page.txt"\n', encoding="utf-8", newline="\n"
        )
        code = _run(
            ["draft", "paper/m.md", "-o", "out.md", "--root", "paper", "--quiet"],
            tmp_path,
        )
        assert code == 0
        written = (root / "out.md").read_text(encoding="utf-8")
        assert "```claim" in written, written

    def test_a_source_under_a_subdirectory_still_opens(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        papers = root / "papers"
        papers.mkdir()
        (root / "page.txt").rename(papers / "page.txt")
        (root / "refs.bib").write_text(
            BIB.replace("page.txt", "papers/page.txt"), encoding="utf-8", newline="\n"
        )
        code = _run(
            [
                "draft",
                "paper/m.md",
                "-o",
                "out.md",
                "--root",
                "paper",
                "--bib",
                "paper/refs.bib",
                "--quiet",
            ],
            tmp_path,
        )
        assert code == 0
        written = (root / "out.md").read_text(encoding="utf-8")
        assert "```claim" in written, written


class TestThePathThatIsRecordedIsStillRelativeToTheRoot:
    """Resolving for the read must not change what the proposal records."""

    def test_sources_toml_line_is_relative_to_the_project(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _run(
            [
                "draft",
                "paper/m.md",
                "-o",
                "out.md",
                "--root",
                "paper",
                "--bib",
                "paper/refs.bib",
                "--quiet",
            ],
            tmp_path,
        )
        written = (root / "out.md").read_text(encoding="utf-8")
        assert 'paper = "page.txt"' in written, written
        assert str(tmp_path) not in written, written

    def test_the_claim_names_the_source_by_key_not_by_path(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _run(
            [
                "draft",
                "paper/m.md",
                "-o",
                "out.md",
                "--root",
                "paper",
                "--bib",
                "paper/refs.bib",
                "--quiet",
            ],
            tmp_path,
        )
        written = (root / "out.md").read_text(encoding="utf-8")
        assert "source=paper" in written, written


@pytest.mark.parametrize("placement", ["page.txt", "papers/page.txt"])
def test_both_placements_produce_a_claim(tmp_path: Path, placement: str) -> None:
    root = _project(tmp_path)
    if "/" in placement:
        (root / "papers").mkdir()
        (root / "page.txt").rename(root / placement)
        (root / "refs.bib").write_text(
            BIB.replace("page.txt", placement), encoding="utf-8", newline="\n"
        )
    code = _run(
        [
            "draft",
            "paper/m.md",
            "-o",
            "out.md",
            "--root",
            "paper",
            "--bib",
            "paper/refs.bib",
            "--quiet",
        ],
        tmp_path,
    )
    assert code == 0
    assert "```claim" in (root / "out.md").read_text(encoding="utf-8")
