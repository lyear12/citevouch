"""A key with no local file is told which of the three ways it has none.

`draft` looks for a file for a citation key in exactly three places: an entry in
`sources.toml`, the `file` field of the bibliography entry, and a file on disk
named exactly after the key.  When none of them resolves, the proposal carries a
commented-out line saying so - and that line is the whole reason the author knows
what to do next.

It said one sentence for every case: "no local file: not in sources.toml, no
`file` field in the bibliography, and no file named after the key".  Two of the
three cases got a better answer before this file existed: `sources.toml` naming a
file that has moved was already reported accurately, because `explain_unresolved`
knows about it.  The bibliography did not, and the same lie came back one file
over.  Measured, with `file={gone.txt}` in the entry and no such file on disk::

    <!-- line 1: paper - no local file: not in sources.toml, no `file` field in
    the bibliography, and no file named after the key -->

The author opens the .bib, sees the field named right there, and reads the rest
of the report differently from then on.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from citevouch import draft as draft_module
from citevouch.cli import main
from citevouch.sources import read_source_table

PAGE = "We collected 40,688 examples in the corpus.\n"
MANUSCRIPT = "We collected 40,688 examples in the corpus [@paper].\n"


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    (root / "m.md").write_text(MANUSCRIPT, encoding="utf-8", newline="\n")
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline="\n")
    return root


def _draft(root: Path, *extra: str) -> str:
    """Run the command and return the proposal it wrote."""
    output = root / "proposals.md"
    code = main(["draft", "m.md", "-o", str(output), "--root", str(root), "--quiet", *extra])
    assert code == 0, f"draft exited {code}"
    return output.read_text(encoding="utf-8")


def _skipped(text: str) -> list[str]:
    """The `line N: key - reason` comments, with the fixed prefix removed."""
    found = []
    for line in text.splitlines():
        if line.startswith("<!-- line ") and " - " in line:
            found.append(line.split(" - ", 1)[1].removesuffix(" -->"))
    return found


class TestTheBibliographyOwnsItsOwnField:
    """A `file` field that names a missing path is not a missing field."""

    def test_a_moved_file_is_named_instead_of_denied(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        (root / "refs.bib").write_text(
            "@article{paper, title={X}, year={2020}, author={A},"
            " journal={J}, file={gone.txt}}\n",
            encoding="utf-8",
            newline="\n",
        )
        written = _draft(root, "--bib", "refs.bib")
        reasons = _skipped(written)
        assert len(reasons) == 1
        assert "file` field" not in reasons[0].replace("`file` field for", "")
        assert "'gone.txt'" in reasons[0], reasons[0]
        assert "is not there" in reasons[0], reasons[0]

    def test_the_sentence_does_not_say_the_field_is_absent(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        (root / "refs.bib").write_text(
            "@article{paper, title={X}, year={2020}, author={A},"
            " journal={J}, file={gone.txt}}\n",
            encoding="utf-8",
            newline="\n",
        )
        written = _draft(root, "--bib", "refs.bib")
        assert "no `file` field in the bibliography" not in written

    def test_a_zotero_wrapped_path_is_unwrapped_before_it_is_named(
        self, tmp_path: Path
    ) -> None:
        root = _project(tmp_path)
        (root / "refs.bib").write_text(
            "@article{paper, title={X}, year={2020}, author={A},"
            " journal={J}, file={:papers/gone.pdf:application/pdf}}\n",
            encoding="utf-8",
            newline="\n",
        )
        written = _draft(root, "--bib", "refs.bib")
        reasons = _skipped(written)
        assert len(reasons) == 1
        assert "'papers/gone.pdf'" in reasons[0], reasons[0]
        assert ":application" not in reasons[0], reasons[0]


class TestTheOtherTwoWaysStillSayWhatTheyAlwaysSaid:
    """The new branch must not steal the cases that already had a better answer."""

    def test_a_key_with_nothing_anywhere_keeps_the_summary(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        written = _draft(root)
        reasons = _skipped(written)
        assert len(reasons) == 1
        assert reasons[0] == (
            "no local file: not in sources.toml, no `file` field in the "
            "bibliography, and no file named after the key"
        )

    def test_a_manifest_that_names_a_missing_file_still_wins(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        (root / "sources.toml").write_text(
            '[sources]\npaper = "gone.txt"\n', encoding="utf-8", newline="\n"
        )
        written = _draft(root)
        reasons = _skipped(written)
        assert len(reasons) == 1
        assert "sources.toml maps 'paper' to 'gone.txt'" in reasons[0], reasons[0]

    def test_a_manifest_problem_is_still_named_before_the_bibliography(
        self, tmp_path: Path
    ) -> None:
        root = _project(tmp_path)
        (root / "sources.toml").write_text("[sources\n", encoding="utf-8", newline="\n")
        (root / "refs.bib").write_text(
            "@article{paper, title={X}, year={2020}, author={A},"
            " journal={J}, file={gone.txt}}\n",
            encoding="utf-8",
            newline="\n",
        )
        written = _draft(root, "--bib", "refs.bib")
        reasons = _skipped(written)
        assert len(reasons) == 1
        assert "the manifest could not be read" in reasons[0], reasons[0]


class TestAKeyThatResolvesIsLeftAlone:
    """The reason is only asked for when nothing resolved."""

    def test_a_key_the_manifest_binds_is_proposed(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        (root / "sources.toml").write_text(
            '[sources]\npaper = "page.txt"\n', encoding="utf-8", newline="\n"
        )
        written = _draft(root)
        assert "no local file" not in written
        assert "```claim" in written

    def test_a_key_the_bibliography_binds_is_proposed(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        (root / "refs.bib").write_text(
            "@article{paper, title={X}, year={2020}, author={A},"
            " journal={J}, file={page.txt}}\n",
            encoding="utf-8",
            newline="\n",
        )
        written = _draft(root, "--bib", "refs.bib")
        assert "no local file" not in written
        assert "```claim" in written


class TestTheReasonItself:
    """Direct calls, so the branch is pinned where it lives."""

    def test_the_bibliography_branch_names_the_field_and_the_path(self, tmp_path: Path) -> None:
        from citevouch.model import BibEntry

        bib = {
            "paper": BibEntry(
                key="paper",
                entry_type="article",
                fields={"file": "gone.txt"},
                path="refs.bib",
                line=1,
            )
        }
        reason = draft_module._why_no_file("paper", None, bib)
        assert "'gone.txt'" in reason
        assert "`file` field" in reason

    def test_no_bibliography_entry_and_no_manifest_is_the_summary(self, tmp_path: Path) -> None:
        assert draft_module._why_no_file("paper", None, {}) == (
            "no local file: not in sources.toml, no `file` field in the "
            "bibliography, and no file named after the key"
        )

    def test_an_entry_without_a_file_field_is_the_summary(self) -> None:
        from citevouch.model import BibEntry

        bib = {
            "paper": BibEntry(
                key="paper",
                entry_type="article",
                fields={},
                path="refs.bib",
                line=1,
            )
        }
        assert draft_module._why_no_file("paper", None, bib) == (
            "no local file: not in sources.toml, no `file` field in the "
            "bibliography, and no file named after the key"
        )

    def test_the_manifest_answer_is_preferred_when_both_are_wrong(self, tmp_path: Path) -> None:
        from citevouch.model import BibEntry

        root = _project(tmp_path)
        (root / "sources.toml").write_text(
            '[sources]\npaper = "gone.txt"\n', encoding="utf-8", newline="\n"
        )
        table = read_source_table(root)
        bib = {
            "paper": BibEntry(
                key="paper",
                entry_type="article",
                fields={"file": "also-gone.txt"},
                path="refs.bib",
                line=1,
            )
        }
        reason = draft_module._why_no_file("paper", table, bib)
        assert "sources.toml maps 'paper' to 'gone.txt'" in reason
        assert "also-gone.txt" not in reason


class TestTheCallSitePassesTheBibliography:
    """The branch is unreachable if the command does not hand over the bib."""

    def test_the_command_reaches_the_new_branch(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        (root / "refs.bib").write_text(
            "@article{paper, title={X}, year={2020}, author={A},"
            " journal={J}, file={gone.txt}}\n",
            encoding="utf-8",
            newline="\n",
        )
        written = _draft(root, "--bib", "refs.bib")
        assert "'gone.txt'" in written
        assert "no `file` field in the bibliography" not in written


@pytest.mark.parametrize("field", ["file = {gone.txt}", "file = {:gone.pdf:pdf}"])
def test_the_author_is_not_told_the_field_is_missing(tmp_path: Path, field: str) -> None:
    root = _project(tmp_path)
    (root / "refs.bib").write_text(
        f"@article{{paper, title={{X}}, year={{2020}}, author={{A}},"
        f" journal={{J}}, {field}}}\n",
        encoding="utf-8",
        newline="\n",
    )
    written = _draft(root, "--bib", "refs.bib")
    assert "no `file` field in the bibliography" not in written
