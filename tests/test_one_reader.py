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

    The names are named rather than counted so that adding a sixth fails here
    with the reason attached.  ``invalid_utf8_share`` is in the list because it
    calls ``.decode`` to *measure* how much of a file is unreadable; it returns a
    number and never hands the decoded text to a reader.  ``declared_charset``
    only looks at ASCII tag bytes, and ``declared_reading`` is a step of
    ``_decode_text`` - both are pinned by the test below.
    """

    ALLOWED: ClassVar[frozenset[str]] = frozenset(
        {
            "_decode_text",
            "read_text",
            "invalid_utf8_share",
            "declared_charset",
            "declared_reading",
        }
    )

    def test_the_declaration_helpers_are_inside_the_one_reader(self) -> None:
        """``declared_reading`` decodes, but it is a step of ``_decode_text``.

        It is here rather than in the list above without a reason: a function
        that returns text and is called by something other than the one reader
        would be a second reader, and the CRLF bug this file guards against
        would come back through it.  So the two call sites are pinned - the
        reader, and a refusal that only asks whether the answer is ``None``.
        """
        source = (PACKAGE / "textnorm.py").read_text(encoding="utf-8")
        start = source.index("def _decode_text(")
        end = source.index("\ndef read_text(", start)
        assert "declared_reading(raw)" in source[start:end]

        sources = (PACKAGE / "sources.py").read_text(encoding="utf-8")
        uses = [
            line.strip()
            for line in sources.splitlines()
            if "declared_reading(" in line and "import" not in line
        ]
        assert uses == ["if declared_reading(raw) is not None:"], (
            "sources.py must only ask whether the declaration decoded, never "
            f"use the text it returned unflattened: {uses}"
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
