"""The archive ships every tracked file the suite reads, or says why not.

Releasing 0.16.1 produced a source archive that claimed `graft tests` and then
unpacked into 56 failures and 3 errors, because `tests/` was shipped without the
files those tests read: `tools/`, `.pre-commit-hooks.yaml`, `action.yml`,
`.github/workflows/`, `docs/img/`, `demo/papers/`.  From inside the repository
nothing looks wrong - the repository has every file.

This test is the outside view.  It walks the tests, collects every path literal
they name through this module's ``ROOT``, and asks whether the sdist carries it.
It is not a list of filenames to keep in sync: a new test that reads a new
directory fails here until the manifest grows the rule that covers it.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"

# Paths a test names that the archive is not expected to carry, with the reason.
# Every entry is a destination rather than a source: the release workflow's own
# outputs, and directories a test creates while it runs.
NOT_SHIPPED = {
    "dist",  # built by the release workflow, never committed
    "build",  # setuptools scratch, never committed
    ".git",  # the archive is what somebody unpacks when they have no clone
}


def _sdist_names() -> set[str]:
    """Every member of the archive we would publish right now, relative to its root."""
    dist = ROOT / "dist"
    archives = sorted(dist.glob("*.tar.gz"))
    if not archives:
        pytest.skip("no sdist in dist/: run `python -m build --sdist` first")
    with tarfile.open(archives[-1]) as tar:
        names = tar.getnames()
    roots = {name.split("/")[0] for name in names}
    assert len(roots) == 1, f"one top-level directory expected, found {sorted(roots)}"
    prefix = roots.pop() + "/"
    return {name[len(prefix) :] for name in names if name.startswith(prefix)}


def _strings_in(path: Path) -> list[str]:
    """String constants in one test file, ignoring docstrings.

    Docstrings are prose about the code and name paths that are not read; a
    test that mentions ``tools/next_version.py`` while explaining history must
    not force that file into the archive.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr):
                value = body[0].value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    docstrings.add(id(value))
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


def _joined_paths(path: Path) -> list[str]:
    """Directory-relative paths built with ``/`` on something, as text.

    Most tests do not write ``"tools/next_version.py"``; they write
    ``ROOT / "tools" / "next_version.py"``, which is three string constants in
    the tree and one path at runtime.  Reading only constants containing a slash
    therefore missed almost every file the suite reads - the first version of
    this module found 14 paths where the suite names more than 30.

    A ``/`` chain is flattened to its constant operands.  A non-constant first
    operand (``ROOT``, ``REPO``, ``Path(...)``) is dropped, leaving a path
    relative to whatever that root was; a chain that starts with a string is
    kept whole.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        parts: list[str] = []
        cursor: ast.expr = node
        while isinstance(cursor, ast.BinOp) and isinstance(cursor.op, ast.Div):
            right = cursor.right
            if isinstance(right, ast.Constant) and isinstance(right.value, str):
                parts.append(right.value)
            else:
                parts = []
                break
            cursor = cursor.left
        if not parts:
            continue
        if isinstance(cursor, ast.Constant) and isinstance(cursor.value, str):
            parts.append(cursor.value)
        parts.reverse()
        found.append("/".join(part.strip("/") for part in parts if part.strip("/")))
    return [text for text in found if text]


_PATHLIKE = re.compile(r"^(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+$")


def _tracked_files() -> set[str]:
    """Paths the index carries, or skip: an unpacked archive has no index.

    This module is shipped inside the archive it describes, so unpacking it
    runs these tests where `git ls-files` answers 128.  That is not a failure
    of the manifest - there is nothing to compare the manifest against - so it
    skips, loudly, and the job that unpacks the archive counts the skips.
    """
    try:
        listed = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError) as problem:
        pytest.skip(f"not a git checkout ({problem}): there is no index to compare")
    return set(listed.stdout.split())


def _referenced_paths() -> set[str]:
    """Tracked repository paths that the suite names, as archive-relative paths."""
    tracked = sorted(_tracked_files())
    tracked_set = set(tracked)
    # A path the suite builds by joining may name a directory rather than a
    # tracked file (`.github/workflows`), so both the exact path and every
    # tracked file beneath it count as references.
    by_directory: dict[str, list[str]] = {}
    for path in tracked:
        pieces = path.split("/")
        for index in range(1, len(pieces)):
            by_directory.setdefault("/".join(pieces[:index]), []).append(path)
    found: set[str] = set()
    for test_file in sorted(TESTS.glob("test_*.py")):
        candidates: list[str] = []
        for text in _strings_in(test_file):
            candidates.extend(re.split(r"[\s\"'(),]+", text))
        candidates.extend(_joined_paths(test_file))
        for candidate in candidates:
            candidate = candidate.strip()
            if not candidate or not _PATHLIKE.match(candidate) or "/" not in candidate:
                continue
            if candidate.split("/")[0] in NOT_SHIPPED:
                continue
            if candidate in tracked_set:
                found.add(candidate)
            elif candidate in by_directory:
                found.update(by_directory[candidate])
    return found


def test_every_tracked_path_the_suite_names_is_in_the_archive() -> None:
    shipped = _sdist_names()
    missing = sorted(path for path in _referenced_paths() if path not in shipped)
    assert not missing, (
        "the source archive does not carry files its own tests read: "
        f"{missing}. Add a rule to MANIFEST.in that covers them - a rule, not a "
        "list: the next test that reads a new directory must be covered by the "
        "same rule."
    )


def test_the_walk_finds_something() -> None:
    """A scan that finds nothing passes every assertion about what it found."""
    referenced = _referenced_paths()
    assert len(referenced) >= 20, (
        f"only {len(referenced)} tracked paths found in the suite; the scan is "
        "probably broken, not the manifest"
    )
    assert any(path.startswith("tools/") for path in referenced)
    assert any(path.startswith("tests/") for path in referenced)


def test_the_archive_carries_the_files_this_module_needs() -> None:
    """The three gaps that made 0.16.1's archive unusable, named individually.

    ``test_every_tracked_path_the_suite_names_is_in_the_archive`` covers these
    only if a test happens to name them, so they are checked by name too: these
    are the shapes that broke once and would break silently again.
    """
    shipped = _sdist_names()
    required = [
        "MANIFEST.in",
        "action.yml",
        ".pre-commit-hooks.yaml",
        "demo/manuscript.md",
        "demo/sources.toml",
        "demo/citevouch.lock.json",
        "tools/next_version.py",
        "tools/check_repo_rules.py",
        "tools/format_check.sh",
    ]
    missing = [name for name in required if name not in shipped]
    assert not missing, f"the archive is missing {missing}"


def test_the_demo_is_shipped_whole_or_not_at_all() -> None:
    """Half a demo reads as a broken tool.

    Without its papers, ``demo/manuscript.md`` reports five ``source-missing``
    findings - every claim red, for a reason that is about the archive rather
    than about the manuscript.
    """
    shipped = _sdist_names()
    papers = sorted(name for name in shipped if name.startswith("demo/papers/"))
    assert "demo/manuscript.md" in shipped
    assert len([p for p in papers if p.endswith(".pdf")]) == 2, (
        "the demo ships with its two papers or it does not ship: found "
        f"{[p for p in papers if p.endswith('.pdf')]}"
    )


def test_no_bytecode_or_scratch_directories_ride_along() -> None:
    shipped = _sdist_names()
    junk = [
        name
        for name in shipped
        if "__pycache__" in name
        or name.endswith((".pyc", ".pyo"))
        or "/.pytest_cache/" in f"/{name}/"
        or name.startswith(".citevouch/")
    ]
    assert not junk, f"the archive carries build residue: {junk[:10]}"


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
