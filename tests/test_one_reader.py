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
    only looks at ASCII tag bytes, ``declared_reading`` is a step of
    ``_decode_text`` and ``_lost`` is the strict-decode probe that answers the
    same question a different way - all three are pinned by the test below.
    ``read_text`` and ``_decode_text`` are not in the list because they no
    longer decode anything: each is its ``..._and_loss`` twin with the flag
    dropped, and ``test_the_two_readers_are_one_authority`` holds that down.
    """

    ALLOWED: ClassVar[frozenset[str]] = frozenset(
        {
            "_decode_text_and_loss",
            "_lost",
            "invalid_utf8_share",
            "declared_charset",
            "declared_reading",
        }
    )

    def test_the_declaration_helpers_are_inside_the_one_reader(self) -> None:
        """``declared_reading`` decodes, but it is a step of the decoder.

        It is here rather than in the list above without a reason: a function
        that returns text and is called by something other than the one reader
        would be a second reader, and the CRLF bug this file guards against
        would come back through it.  So the two call sites are pinned - the
        reader, and a refusal that only asks whether the answer is ``None``.
        """
        source = (PACKAGE / "textnorm.py").read_text(encoding="utf-8")
        start = source.index("def _decode_text_and_loss(")
        end = source.index("\ndef _decode_text(", start)
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
        start = source.index("def read_text_and_loss(")
        end = source.index("\ndef ", start + 1)
        body = source[start:end]
        assert 'replace("\\r\\n", "\\n")' in body
        assert 'replace("\\r", "\\n")' in body

    def test_the_two_readers_are_one_authority(self) -> None:
        """``read_text`` must be ``read_text_and_loss`` with the flag dropped.

        Two names for one reader is only safe while one of them is a call into
        the other.  A copy of the flattening in both places is the shape of the
        bug this file exists for: the two drift, and the path that reads through
        the older copy keeps the misreading.  Measured, the drift is one edit
        away - the same body appears twice, so "fix it in the reader" fixes
        whichever one the editor had open.
        """
        source = (PACKAGE / "textnorm.py").read_text(encoding="utf-8")
        start = source.index("def read_text(path")
        end = source.index("\ndef ", start + 1)
        body = source[start:end]
        assert "read_text_and_loss(path)[0]" in body
        assert "replace(" not in body, (
            "read_text flattens line endings itself; the flattening belongs in "
            "read_text_and_loss, or the two readings can drift apart"
        )
