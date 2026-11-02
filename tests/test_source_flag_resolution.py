"""`--source` must resolve the way every other path flag resolves.

Seven path flags cross this tool's command line. Six of them accept a path the
way a shell produces it: `--root`, the manuscript argument, `--ledger`, `--bib`,
`-o`, and `--manuscript` on `doctor`. The one that did not was `--source`,
which joined the root unconditionally, so the spelling that worked depended on
which flag it belonged to:

=====================  ==========================================
typed, from above      what happened
=====================  ==========================================
--bib paper/refs.bib   resolves, the bibliography is read
--source paper/page.txt  exit 2: ``source paper\\paper\\page.txt does not exist``
--source page.txt      resolves
=====================  ==========================================

The project is in `paper/`; both paths point at files that are really there.
An author who has just learned `--bib paper/refs.bib` from the error message
types `--source paper/page.txt` and is told the file does not exist.

The same split ran through `draft`'s output guard, which protected the inputs
it had computed with the *other* rule: `draft --source paper/page.txt -o
page.txt --force` protected `paper/paper/page.txt`, wrote proposals over
`paper/page.txt`, and destroyed the source the run had just read a quote from.
"""

from __future__ import annotations

import os
from pathlib import Path

from citevouch.cli import main
from citevouch.scan import _resolve as scan_resolve
from citevouch.sources import _resolve as source_resolve

BIB = "@article{page, title={T}, author={A}, year={2020}, journal={J}, file={page.txt}}\n"
PAGE = "We collected 40,688 examples in the corpus.\n"
MANUSCRIPT = (
    "```claim id=c1 source=page page=1\n"
    "quote: |\n"
    "  We collected 40,688 examples in the corpus.\n"
    "claim: |\n"
    "  We collected 40,688 examples in the corpus.\n"
    "```\n"
)
CITING = "We collected 40,688 examples in the corpus [@page].\n"


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "paper"
    root.mkdir()
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline="\n")
    (root / "refs.bib").write_text(BIB, encoding="utf-8", newline="\n")
    (root / "m.md").write_text(MANUSCRIPT, encoding="utf-8", newline="\n")
    (root / "cites.md").write_text(CITING, encoding="utf-8", newline="\n")
    return root


def _run(argv: list[str], cwd: Path) -> int:
    previous = Path.cwd()
    os.chdir(cwd)
    try:
        return main(argv)
    finally:
        os.chdir(previous)


class TestOneRuleForEveryPathFlag:
    """The helper itself, before any command's use of it."""

    def test_a_path_that_already_works_is_not_rerooted(self, tmp_path: Path) -> None:
        project = _project(tmp_path)
        previous = Path.cwd()
        os.chdir(tmp_path)
        try:
            # `.is_file()` is asked here, while the argument's meaning holds:
            # a relative path means "relative to the process directory", and
            # asking after the chdir back would be asking about another file.
            assert source_resolve(project, "paper/page.txt").is_file()
        finally:
            os.chdir(previous)

    def test_both_names_resolve_the_same_file(self, tmp_path: Path) -> None:
        project = _project(tmp_path)
        previous = Path.cwd()
        os.chdir(tmp_path)
        try:
            as_typed = source_resolve(project, "paper/page.txt").resolve()
            as_rooted = source_resolve(project, "page.txt").resolve()
        finally:
            os.chdir(previous)
        assert as_typed == as_rooted

    def test_the_two_modules_export_one_behaviour(self, tmp_path: Path) -> None:
        """`scan._resolve` forwards to `sources._resolve`; this pins that.

        Six call sites and a dozen tests import the name from `scan`, so it has
        to stay - but two copies of this function is exactly how `--source`
        came to be the odd one out in the first place.  The identity check is
        deliberate: a second copy that happens to agree today is a copy that
        disagrees the next time one of them is fixed, and no behavioural test
        can see that until it has already bitten.
        """
        assert scan_resolve is source_resolve
        project = _project(tmp_path)
        previous = Path.cwd()
        os.chdir(tmp_path)
        try:
            for raw in ("paper/page.txt", "page.txt", "nowhere/none.txt"):
                assert scan_resolve(project, raw) == source_resolve(project, raw)
        finally:
            os.chdir(previous)


class TestTheFlagsAgreeWithEachOther:
    """Run the same project through every command that takes `--source`."""

    def test_scan_accepts_the_typed_spelling(self, tmp_path: Path) -> None:
        _project(tmp_path)
        code = _run(
            ["scan", "paper/m.md", "--root", "paper", "--source", "paper/page.txt"],
            tmp_path,
        )
        assert code == 0

    def test_scan_accepts_the_rooted_spelling(self, tmp_path: Path) -> None:
        _project(tmp_path)
        code = _run(
            ["scan", "paper/m.md", "--root", "paper", "--source", "page.txt"],
            tmp_path,
        )
        assert code == 0

    def test_the_two_spellings_record_the_same_ledger(self, tmp_path: Path) -> None:
        """The ledger is the durable artefact; two spellings, one file.

        Comparing the ledger rather than each command's exit code is what makes
        this a test about the path rule instead of about two exit codes that
        happened to be 0.
        """
        project = _project(tmp_path)
        _run(["scan", "paper/m.md", "--root", "paper", "--source", "paper/page.txt"], tmp_path)
        typed = (project / "citevouch.lock.json").read_text(encoding="utf-8")
        (project / "citevouch.lock.json").unlink()
        _run(["scan", "paper/m.md", "--root", "paper", "--source", "page.txt"], tmp_path)
        rooted = (project / "citevouch.lock.json").read_text(encoding="utf-8")
        assert typed == rooted

    def test_check_accepts_the_typed_spelling(self, tmp_path: Path) -> None:
        _project(tmp_path)
        code = _run(
            ["check", "paper/m.md", "--root", "paper", "--source", "paper/page.txt"],
            tmp_path,
        )
        assert code == 0

    def test_draft_accepts_the_typed_spelling(self, tmp_path: Path) -> None:
        project = _project(tmp_path)
        code = _run(
            [
                "draft",
                "paper/cites.md",
                "--root",
                "paper",
                "--source",
                "paper/page.txt",
                "-o",
                "out.md",
            ],
            tmp_path,
        )
        assert code == 0
        written = (project / "out.md").read_text(encoding="utf-8")
        assert "```claim id=page source=page" in written

    def test_a_directory_is_still_refused_under_either_spelling(self, tmp_path: Path) -> None:
        project = _project(tmp_path)
        (project / "adir").mkdir()
        for spelling in ("paper/adir", "adir"):
            code = _run(
                ["scan", "paper/m.md", "--root", "paper", "--source", spelling],
                tmp_path,
            )
            assert code == 2, spelling


class TestTheOutputGuardNamesTheSameFileAsTheReader:
    """`draft -o` refused some inputs and missed the rest.

    The guard computes the files it protects; the reader computes the files it
    opens. They used different rules, so ``--source paper/page.txt -o page.txt
    --force`` protected ``paper/paper/page.txt`` (not a file) and wrote over
    ``paper/page.txt`` (the source the run had just read).
    """

    def test_the_typed_spelling_is_protected_from_the_output(self, tmp_path: Path) -> None:
        project = _project(tmp_path)
        before = (project / "page.txt").read_bytes()
        code = _run(
            [
                "draft",
                "paper/cites.md",
                "--root",
                "paper",
                "--source",
                "paper/page.txt",
                "-o",
                "page.txt",
                "--force",
            ],
            tmp_path,
        )
        assert code == 2
        assert (project / "page.txt").read_bytes() == before

    def test_the_rooted_spelling_is_protected_too(self, tmp_path: Path) -> None:
        project = _project(tmp_path)
        before = (project / "page.txt").read_bytes()
        code = _run(
            [
                "draft",
                "paper/cites.md",
                "--root",
                "paper",
                "--source",
                "page.txt",
                "-o",
                "page.txt",
                "--force",
            ],
            tmp_path,
        )
        assert code == 2
        assert (project / "page.txt").read_bytes() == before

    def test_the_message_names_the_file_it_would_have_written(self, tmp_path: Path) -> None:
        _project(tmp_path)
        code = _run(
            [
                "draft",
                "paper/cites.md",
                "--root",
                "paper",
                "--source",
                "paper/page.txt",
                "-o",
                "page.txt",
                "--force",
            ],
            tmp_path,
        )
        assert code == 2

    def test_an_unrelated_output_is_still_written(self, tmp_path: Path) -> None:
        """The guard must refuse the input, not every output."""
        project = _project(tmp_path)
        code = _run(
            [
                "draft",
                "paper/cites.md",
                "--root",
                "paper",
                "--source",
                "paper/page.txt",
                "-o",
                "proposals.md",
            ],
            tmp_path,
        )
        assert code == 0
        assert (project / "proposals.md").is_file()
