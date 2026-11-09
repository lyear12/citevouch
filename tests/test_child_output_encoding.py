"""A test that reads a child's output has to say which bytes it is reading.

The defect this guards against was found on a red Windows job, not by reading
the code.  `tests/test_table_blank_cells.py` ran the command in a child process
and compared its output against a summary line containing an em dash, without
pinning an encoding on either end.  The child wrote with the Windows code page,
the parent decoded with the locale, and the two sides of the comparison held
different bytes:

    assert '1 claim ? 1 verified' in '... citevouch: 1 claim - 1 verified ...'

It passed on the development machine because its locale and code page are both
UTF-8, and failed on all three `windows-latest` jobs, which skipped the release.
The product code was never wrong; only the test that watched it was reading a
byte sequence it had assumed was text.

The rule is per *file*, not per function, and that is the whole point.  The first
version of this guard walked one function at a time, so it did not see the
defect at all: the child was spawned in a helper called `_run` and the em dash
was asserted in a test method two functions away.  A guard that cannot look
across the seam between a helper and its caller cannot guard a seam - and a
seam is exactly where this defect lived.

So: if a test file spawns a child whose stdout it reads back as text, and the
same file contains a non-ASCII string literal inside an assertion, then every
text-reading child in that file must pin an encoding.  ASCII-only files are
left alone - `git ls-files` output compared against a path needs no encoding
and should not be forced to grow one - and a non-ASCII literal in a fixture the
test *writes* is input, not an expectation, so it does not count either.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"

CAPTURING = frozenset({"run", "check_output", "Popen", "call", "check_call"})
"""The subprocess entry points whose output a test can read back."""


def _called_name(node: ast.Call) -> str | None:
    target = node.func
    if isinstance(target, ast.Attribute):
        return target.attr
    if isinstance(target, ast.Name):
        return target.id
    return None


def _keywords(node: ast.Call) -> set[str]:
    return {keyword.arg for keyword in node.keywords if keyword.arg}


def _reads_text(node: ast.Call) -> bool:
    names = _keywords(node)
    return "text" in names or "universal_newlines" in names


def _pins_an_encoding(node: ast.Call) -> bool:
    return "encoding" in _keywords(node)


def _is_child(node: ast.Call) -> bool:
    return _called_name(node) in CAPTURING


def _non_ascii_literals(node: ast.AST) -> list[str]:
    return [
        inner.value
        for inner in ast.walk(node)
        if isinstance(inner, ast.Constant)
        and isinstance(inner.value, str)
        and any(ord(ch) > 127 for ch in inner.value)
    ]


def _asserted_non_ascii(tree: ast.Module) -> list[str]:
    """Non-ASCII text on the right-hand side of an assertion, anywhere in a file."""
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue
        found.extend(_non_ascii_literals(node.test))
    return found


def _unpinned_child_reads(tree: ast.Module) -> list[int]:
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and _is_child(node)
        and _reads_text(node)
        and not _pins_an_encoding(node)
    ]


def _offenders_in(path: Path) -> list[str]:
    """The unpinned child reads in a file that also asserts on non-ASCII text."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    expectations = _asserted_non_ascii(tree)
    if not expectations:
        return []
    unpinned = _unpinned_child_reads(tree)
    return [f"{path.name}:{line}" for line in unpinned]


class TestAFileThatAssertsOnNonAsciiPinsItsEncoding:
    def test_no_file_reads_a_child_as_text_without_an_encoding(self) -> None:
        offenders: list[str] = []
        for path in sorted(TESTS.glob("*.py")):
            offenders.extend(_offenders_in(path))
        assert offenders == [], (
            "these files read a child's output as text without pinning an "
            "encoding while asserting on non-ASCII text somewhere in the same "
            "file; on Windows the child writes in the code page and the parent "
            "decodes in the locale, so the comparison can differ by bytes: "
            + ", ".join(offenders)
        )

    def test_the_scan_reaches_the_files_it_is_meant_to_reach(self) -> None:
        """A guard whose file list is a guess protects only the guess."""
        scanned = sorted(path.name for path in TESTS.glob("*.py"))
        assert "test_table_blank_cells.py" in scanned
        assert len(scanned) > 40

    def test_it_calls_a_pinned_read_pinned(self) -> None:
        """The rule must be able to say yes, or it only ever says no."""
        tree = ast.parse(
            'subprocess.run(["x"], text=True, encoding="utf-8", capture_output=True)'
        )
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and _is_child(node) and _reads_text(node)
        ]
        assert len(calls) == 1
        assert _pins_an_encoding(calls[0])

    def test_it_calls_an_unpinned_read_unpinned(self) -> None:
        tree = ast.parse('subprocess.run(["x"], text=True, capture_output=True)')
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and _is_child(node) and _reads_text(node)
        ]
        assert len(calls) == 1
        assert not _pins_an_encoding(calls[0])

    def test_a_helper_and_its_caller_are_judged_together(self) -> None:
        """The seam the first version of this guard could not see."""
        tree = ast.parse(
            "def _run(root):\n"
            '    return subprocess.run(["x"], text=True, capture_output=True)\n'
            "\n"
            "def test_it():\n"
            '    assert "1 claim - 1 verified" in _run(1)\n'.replace("-", "\u2014")
        )
        assert _asserted_non_ascii(tree) != []
        assert _unpinned_child_reads(tree) == [2]

    def test_a_fixture_the_test_writes_is_not_an_expectation(self) -> None:
        """Non-ASCII input is not a claim about the child's bytes."""
        tree = ast.parse(
            "def test_it():\n"
            '    (root / "m.md").write_text("\u4e2d\u6587", encoding="utf-8")\n'
            '    assert "ok" in _run(root)\n'
        )
        assert _asserted_non_ascii(tree) == []
        assert _unpinned_child_reads(tree) == []
