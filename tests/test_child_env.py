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
    """True if the dict has a `**` entry that comes from the environment."""
    for key, value in zip(node.keys, node.values, strict=True):
        if key is not None:
            continue  # an ordinary `name: value` entry, not an expansion
        if "environ" in ast.unparse(value):
            return True
    return False


def _functions(tree: ast.Module) -> dict[str, list[ast.expr]]:
    """Every value each function in this file returns."""
    found: dict[str, list[ast.expr]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            found[node.name] = [
                inner.value
                for inner in ast.walk(node)
                if isinstance(inner, ast.Return) and inner.value
            ]
    return found


def _bindings(tree: ast.Module) -> dict[str, list[ast.expr]]:
    """Every value ever assigned to each plain name in this file."""
    found: dict[str, list[ast.expr]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                found.setdefault(target.id, []).append(node.value)
    return found


def _inherits(
    node: ast.expr, bound: dict[str, list[ast.expr]], returned: dict[str, list[ast.expr]]
) -> bool:
    """True if this value can carry the real environment into the child.

    Four spellings reach the same idea: a dict literal that expands the
    environment, a name bound to one, a call to a function in this file that
    returns one, and any expression that mentions `environ` at all.  "Can"
    rather than "does" because a name is resolved file-wide: the same
    variable is reused for several children, and proving each use separately
    would mean modelling control flow.  A guard that guesses wrong in the
    permissive direction lets a real defect through; one that guesses wrong
    in the strict direction fails the build on correct code, which is why the
    permissive reading is the one to take when a name has several bindings.
    """
    if isinstance(node, ast.Dict):
        return _expands_os_environ(node)
    if isinstance(node, ast.Name):
        values = bound.get(node.id, [])
        return any(_inherits(value, bound, returned) for value in values)
    if isinstance(node, ast.Call):
        if "environ" in ast.unparse(node):
            return True
        name = getattr(node.func, "id", None)
        return any(_inherits(value, bound, returned) for value in returned.get(name or "", []))
    if isinstance(node, ast.BoolOp):
        return any(_inherits(value, bound, returned) for value in node.values)
    if isinstance(node, ast.BinOp):
        return any(_inherits(side, bound, returned) for side in (node.left, node.right))
    if isinstance(node, ast.IfExp):
        return any(_inherits(side, bound, returned) for side in (node.body, node.orelse))
    return False


def _replacing_envs(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    bound = _bindings(tree)
    returned = _functions(tree)
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg != "env":
                continue
            if not _inherits(keyword.value, bound, returned):
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


def test_the_guard_follows_a_name_to_its_literal(tmp_path: Path) -> None:
    """`env=env` over a two-key literal is the same defect, one step out.

    The first version of this guard read only `env={...}` literals, so a
    helper that assigned the dict to a name and passed the name walked
    straight past it - and that is what happened: four assertions died on
    Windows 3.10 while the Linux and macOS cells stayed green.  A guard that
    recognises one spelling protects that spelling.
    """
    source = tmp_path / "child.py"
    source.write_text(
        "def go():"
        + chr(10)
        + '    env = {"PYTHONPATH": "src"}'
        + chr(10)
        + "    run(env=env)"
        + chr(10),
        encoding="utf-8",
    )
    assert _replacing_envs(source) == [3]


def test_a_name_that_inherits_is_not_flagged(tmp_path: Path) -> None:
    """The widening must not turn every helper into an offender."""
    source = tmp_path / "child.py"
    source.write_text(
        "def build():"
        + chr(10)
        + '    base = {**os.environ, "PYTHONPATH": "src"}'
        + chr(10)
        + "    return base"
        + chr(10)
        + chr(10)
        + "def go():"
        + chr(10)
        + "    run(env=build())"
        + chr(10),
        encoding="utf-8",
    )
    assert _replacing_envs(source) == []


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
