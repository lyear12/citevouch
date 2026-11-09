"""One bibliography file must have one spelling in the ledger.

`sources.toml`'s paths and the ledger's own `bibliographies` list are recorded
root-relative with forward slashes, so a ledger written on Windows resolves on
the Linux job that runs the same commit.  The bibliography *entries* were not:
they went through a line that handed ``parse_bib`` the path exactly as the
shell spelled it, so the same project produced two ledgers depending on where
the command was typed::

    scan proj/manuscript.md --root proj --bib proj/sub/refs.bib
      entries['knuth2020'].path = 'proj\\\\sub\\\\refs.bib'
      bibliographies            = ['sub/refs.bib']
    cd proj && scan manuscript.md --root . --bib sub/refs.bib
      entries['knuth2020'].path = 'sub\\\\refs.bib'

Two spellings of one file inside one ledger.  Whichever shell the author used,
the other one reads a path it did not write, and every finding built on that
entry (``bib-field-empty`` and friends) names it back to them.
"""

from __future__ import annotations

import json
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
# Two required fields and one empty one, so `bib-field-empty` has something to say.
BIB = "@book{knuth2020,\n  title = {The Art of Computer Programming},\n  author = {Knuth, Donald},\n  year = {},\n}\n"
MANUSCRIPT = (
    "```claim id=c1 source=paper page=1 ref=knuth2020\n"
    "quote: |\n"
    "  We collected 154,391 examples from the corpus.\n"
    "```\n"
)


def _run(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "citevouch", *args],
        cwd=cwd,
        env=ENV,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _project(tmp_path: Path) -> Path:
    """A project with the bibliography one directory down, as a paper repo has it."""
    project = tmp_path / "proj"
    (project / "sub").mkdir(parents=True)
    (project / "page.txt").write_text(PAGE, encoding="utf-8")
    (project / "sub" / "refs.bib").write_text(BIB, encoding="utf-8")
    (project / "sources.toml").write_text('[sources]\npaper = "page.txt"\n', encoding="utf-8")
    (project / "manuscript.md").write_text(MANUSCRIPT, encoding="utf-8")
    return project


def _entries(project: Path) -> dict[str, dict[str, object]]:
    blob = json.loads((project / "citevouch.lock.json").read_text(encoding="utf-8"))
    return blob["entries"]


def _bib_fields(proc: subprocess.CompletedProcess[str]) -> list[str]:
    return [line for line in proc.stdout.splitlines() if "bib-field-empty" in line]


def test_the_recorded_path_is_relative_to_the_root(tmp_path: Path) -> None:
    project = _project(tmp_path)
    assert (
        _run(
            project, "scan", "manuscript.md", "--root", ".", "--bib", "sub/refs.bib"
        ).returncode
        == 0
    )

    path = _entries(project)["knuth2020"]["path"]
    assert path == "sub/refs.bib", path


def test_two_shells_on_one_project_write_one_ledger(tmp_path: Path) -> None:
    """The bug, exactly: the same project scanned from two directories."""
    project = _project(tmp_path)
    _run(project, "scan", "manuscript.md", "--root", ".", "--bib", "sub/refs.bib")
    from_inside = _entries(project)

    _run(tmp_path, "scan", "proj/manuscript.md", "--root", "proj", "--bib", "proj/sub/refs.bib")
    from_parent = _entries(project)

    assert from_inside == from_parent


def test_the_two_spellings_of_one_file_agree(tmp_path: Path) -> None:
    """A ledger that disagrees with itself about a file is the same bug, quieter."""
    project = _project(tmp_path)
    _run(tmp_path, "scan", "proj/manuscript.md", "--root", "proj", "--bib", "proj/sub/refs.bib")

    blob = json.loads((project / "citevouch.lock.json").read_text(encoding="utf-8"))
    recorded = blob["entries"]["knuth2020"]["path"]
    listed = blob["bibliographies"][0]
    assert recorded == listed, (recorded, listed)


def test_the_finding_names_a_path_the_reader_can_open(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _run(tmp_path, "scan", "proj/manuscript.md", "--root", "proj", "--bib", "proj/sub/refs.bib")

    recorded = _entries(project)["knuth2020"]["path"]
    assert (project / recorded).is_file(), recorded
    assert "\\" not in recorded, recorded


def test_the_live_run_names_the_same_path(tmp_path: Path) -> None:
    project = _project(tmp_path)
    live = _run(project, "check", "manuscript.md", "--root", ".", "--bib", "sub/refs.bib")

    [line] = _bib_fields(live)
    assert " at sub/refs.bib:" in line, line
    assert "\\" not in line, line


def test_the_recorded_run_names_the_same_path(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _run(project, "scan", "manuscript.md", "--root", ".", "--bib", "sub/refs.bib")
    recorded = _run(project, "check", "manuscript.md", "--root", ".", "--use-recorded")

    [line] = _bib_fields(recorded)
    assert " at sub/refs.bib:" in line, line
    assert "\\" not in line, line


def test_a_bibliography_outside_the_root_is_not_given_a_fake_relative_path(
    tmp_path: Path,
) -> None:
    """Outside the root there is no honest relative spelling, and the tool says so."""
    project = _project(tmp_path)
    outside = tmp_path / "outside.bib"
    outside.write_text(BIB, encoding="utf-8")

    _run(project, "scan", "manuscript.md", "--root", ".", "--bib", "../outside.bib")
    recorded = _entries(project)["knuth2020"]["path"]

    # The ledger's paths are read against the root, so that is where this one
    # has to point.  It cannot be made relative to the root, and inventing a
    # relative spelling would move the finding onto some other file.
    assert (project / recorded).is_file(), recorded
    assert "sub/refs.bib" not in recorded, recorded


def test_the_ledger_still_round_trips(tmp_path: Path) -> None:
    from citevouch.model import Ledger

    project = _project(tmp_path)
    _run(project, "scan", "manuscript.md", "--root", ".", "--bib", "sub/refs.bib")

    written = json.loads((project / "citevouch.lock.json").read_text(encoding="utf-8"))
    assert json.loads(json.dumps(Ledger.from_json(written).to_json())) == written


def test_draft_still_reads_the_bibliography(tmp_path: Path) -> None:
    """`draft --bib` owns the same line; a path change must not break it."""
    project = _project(tmp_path)
    (project / "proposals.md").write_text("", encoding="utf-8")
    proc = _run(
        project,
        "draft",
        "manuscript.md",
        "--root",
        ".",
        "--bib",
        "sub/refs.bib",
        "-o",
        "proposals.md",
        "--force",
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr


def _with_source_beside_the_bib(project: Path) -> None:
    """A `file` field that only resolves against the bibliography's own folder."""
    (project / "sub" / "paper.txt").write_text(PAGE, encoding="utf-8")
    (project / "sub" / "refs.bib").write_text(
        "@book{knuth2020,\n"
        "  title = {The Art},\n"
        "  author = {Knuth, Donald},\n"
        "  year = {1968},\n"
        "  file = {paper.txt},\n"
        "}\n",
        encoding="utf-8",
    )
    (project / "manuscript.md").write_text(
        "Prior work [@knuth2020] collected a large corpus of examples.\n", encoding="utf-8"
    )


def test_draft_finds_a_source_beside_the_bibliography_from_either_shell(tmp_path: Path) -> None:
    """The recorded path is root-relative, so the join has to be too.

    This is the half of the change that bites back: moving the entry's path from
    "the shell's spelling" to "the root's spelling" is only correct if every
    reader joins it to the root.  `draft` looked beside `entry.path` and would
    have found the file from one directory and not from the other.
    """
    project = _project(tmp_path)
    _with_source_beside_the_bib(project)

    from_inside = _run(
        project, "draft", "manuscript.md", "--root", ".", "--bib", "sub/refs.bib", "-o", "a.md"
    )
    from_parent = _run(
        tmp_path,
        "draft",
        "proj/manuscript.md",
        "--root",
        "proj",
        "--bib",
        "proj/sub/refs.bib",
        "-o",
        "b.md",
    )

    assert from_inside.returncode == 0, from_inside.stdout + from_inside.stderr
    assert from_parent.returncode == 0, from_parent.stdout + from_parent.stderr
    inside = (project / "a.md").read_text(encoding="utf-8")
    parent = (project / "b.md").read_text(encoding="utf-8")
    assert 'knuth2020 = "sub/paper.txt"' in inside, inside
    assert 'knuth2020 = "sub/paper.txt"' in parent, parent


def test_a_broken_bibliography_names_the_portable_path(tmp_path: Path) -> None:
    """The failures recorded about a bibliography carry the same spelling."""
    project = _project(tmp_path)
    (project / "sub" / "refs.bib").write_text("\x01\x02 not a bib \x03\n", encoding="utf-8")
    proc = _run(project, "scan", "manuscript.md", "--root", ".", "--bib", "sub/refs.bib")

    assert proc.returncode == 1
    [line] = [ln for ln in proc.stdout.splitlines() if "bib-unreadable" in ln]
    assert " at sub/refs.bib:" in line, line
    assert "\\" not in line, line


def test_the_recorded_pass_names_a_parse_failure_the_same_way(tmp_path: Path) -> None:
    """`bib-field-malformed` is produced by the re-read, not by the ledger.

    The ledger keeps entries, not parse findings, so this line can only come
    from `verify`'s own `parse_bib` call - which is the second spelling of the
    path that a recorded run can print.
    """
    project = _project(tmp_path)
    (project / "sub" / "refs.bib").write_text(
        "@book{knuth2020,\n"
        "  title = {The Art},\n"
        "  author = {Knuth, Donald},\n"
        "  year = {1968},\n"
        "  publisher = {Addison},\n"
        "  not a field at all\n"
        "}\n",
        encoding="utf-8",
    )
    _run(project, "scan", "manuscript.md", "--root", ".", "--bib", "sub/refs.bib")
    recorded = _run(project, "check", "manuscript.md", "--root", ".", "--use-recorded")

    [line] = [ln for ln in recorded.stdout.splitlines() if "bib-field-malformed" in ln]
    assert " at sub/refs.bib:" in line, line
    assert "\\" not in line, line


@pytest.mark.parametrize("bib", ["sub/refs.bib", "./sub/refs.bib", "sub//refs.bib"])
def test_the_spelling_the_author_typed_does_not_reach_the_ledger(
    tmp_path: Path, bib: str
) -> None:
    project = _project(tmp_path)
    _run(project, "scan", "manuscript.md", "--root", ".", "--bib", bib)

    assert _entries(project)["knuth2020"]["path"] == "sub/refs.bib"
