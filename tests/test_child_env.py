"""A child process gets the environment, not a replacement for it.

`subprocess.run(..., env={...})` replaces the whole environment. On Windows that
takes `SYSTEMROOT` away and CPython aborts before it can report anything:

    Fatal Python error: _Py_HashRandomization_Init: failed to get random
    numbers to initialize Python

The failure lands on whichever test spawned the child, as `assert 1 == 0`, and
the message says nothing about the environment - so the same defect has now been
written twice, in `test_critic_round2.py` and again in `test_precommit.py`, each
time found by a red Windows job rather than by reading the code.

The rule: a dict handed to `env=` must carry `**os.environ`. These tests read
the sources with `ast`, so prose that mentions the pattern is not matched and a
real one cannot hide behind a comment.

The scan covers `tools/` as well as `tests/`, because it was written over
`tests/` alone and `tools/make_figures.py` then did exactly this: the first
version of the figure generator handed `env={"PYTHONPATH": ...}` to the demo run,
which on Windows removed `PATH`, lost `pdftotext`, and drew a picture of a broken
installation. A guard whose list of files is a guess protects only the guess.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"


SCANNED = (TESTS, ROOT / "tools")


def _sources() -> list[Path]:
    """Every Python file this repository runs by hand or in CI."""
    found: list[Path] = []
    for directory in SCANNED:
        found.extend(sorted(directory.glob("*.py")))
    return found


def _expands_os_environ(node: ast.Dict) -> bool:
    """True if the dict has a `**` entry that comes from os.environ."""
    for key, value in zip(node.keys, node.values, strict=True):
        if key is not None:
            continue  # an ordinary `name: value` entry, not an expansion
        source = ast.unparse(value)
        if "os.environ" in source:
            return True
    return False


def _replacing_envs(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg != "env" or not isinstance(keyword.value, ast.Dict):
                continue
            if not _expands_os_environ(keyword.value):
                lines.append(keyword.value.lineno)
    return sorted(lines)


def test_the_scan_finds_the_files_it_is_meant_to_scan() -> None:
    """A guard over an empty list passes forever."""
    sources = _sources()
    assert len(sources) > 15, len(sources)
    assert (TESTS / "test_precommit.py") in sources
    assert (ROOT / "tools" / "make_figures.py") in sources, (
        "the file that actually made this mistake is not in the scan"
    )


def test_the_detector_recognises_both_shapes() -> None:
    """Without this, a guard that never matches anything looks like a clean repo."""
    good = ast.parse('run(x, env={**os.environ, "A": "1"})').body[0]
    bad = ast.parse('run(x, env={"PYTHONPATH": "src"})').body[0]
    assert _expands_os_environ(good.value.keywords[0].value) is True
    assert _expands_os_environ(bad.value.keywords[0].value) is False


def test_nothing_replaces_the_environment_with_a_literal() -> None:
    """`tests/` and `tools/` alike: the same `env=` kills a child in both."""
    offenders = [
        f"{path.name}:{line}"
        for path in _sources()
        for line in _replacing_envs(path)
        if path.name != Path(__file__).name
    ]
    assert offenders == [], (
        "a dict handed to env= without **os.environ replaces the environment; "
        f"on Windows it removes SYSTEMROOT and the child never starts: {offenders}"
    )


def test_the_helper_starts_from_the_real_environment() -> None:
    """The whole point is inheritance, so prove the inheritance happens."""
    source = (TESTS / "test_precommit.py").read_text(encoding="utf-8")
    body = source[source.index("def _env(") :]
    body = body[: body.index("\n\n\n")]
    assert "dict(os.environ)" in body
    assert "update(" in body
