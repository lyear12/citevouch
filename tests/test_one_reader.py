"""Round 177 guard: every reader the tool has must flatten line endings.

The bug was fixed in `textnorm.read_text`, which is the one reader.  A future
change that adds a second reader - or that reaches past `read_text` to the
bytes - would bring the same CRLF misreading back for one path only.  This
test reads the package and asserts there is exactly one place that turns
bytes into text, and that it is the one that flattens.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import ClassVar

import citevouch

PACKAGE = Path(citevouch.__file__).parent


def _functions_that_decode() -> list[tuple[str, str]]:
    """Every function in the package whose body turns bytes into a string."""
    found: list[tuple[str, str]] = []
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Call):
                    continue
                target = inner.func
                if isinstance(target, ast.Attribute) and target.attr == "decode":
                    found.append((path.name, node.name))
                    break
                if isinstance(target, ast.Name) and target.id == "_decode_text":
                    found.append((path.name, node.name))
                    break
    return found


class TestThereIsOneReader:
    """No other module in the package turns bytes into text.

    The three names are named rather than counted so that adding a fourth
    fails here with the reason attached.  ``invalid_utf8_share`` is in the list
    because it calls ``.decode`` to *measure* how much of a file is unreadable;
    it returns a number and never hands the decoded text to a reader.
    """

    ALLOWED: ClassVar[frozenset[str]] = frozenset(
        {"_decode_text", "read_text", "invalid_utf8_share"}
    )

    def test_no_module_outside_textnorm_decodes_bytes(self) -> None:
        outside = [
            (module, name)
            for module, name in _functions_that_decode()
            if module != "textnorm.py"
        ]
        assert outside == [], (
            "a second reader turns bytes into text; it must flatten line "
            f"endings the way `read_text` does, or a CRLF file reads one way "
            f"here and another way there: {sorted(outside)}"
        )

    def test_textnorm_decodes_in_exactly_the_expected_functions(self) -> None:
        names = {name for _, name in _functions_that_decode()}
        assert names == self.ALLOWED, (
            f"a new function decodes bytes into text: {sorted(names - self.ALLOWED)}; "
            "it must flatten line endings the way `read_text` does"
        )

    def test_the_one_reader_is_the_one_that_flattens(self) -> None:
        source = (PACKAGE / "textnorm.py").read_text(encoding="utf-8")
        start = source.index("def read_text(")
        end = source.index("\ndef ", start + 1)
        body = source[start:end]
        assert 'replace("\\r\\n", "\\n")' in body
        assert 'replace("\\r", "\\n")' in body
