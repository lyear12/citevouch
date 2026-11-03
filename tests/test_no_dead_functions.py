"""A function nothing calls is a feature the docstring promises and the tool lacks.

Four such functions shipped: ``verify.doi_index`` ("for the optional Crossref
cross-check", which does not exist), ``verify.rebuild`` ("so the CLI has one call
per verb", which it does not use), ``verify.summarize`` (a second copy of the
sentence a run prints, unreachable while ``report.py`` writes the real one), and
``sources._odd_bindings`` (the plural sentence for a manifest whose values are
not paths - the live code writes that sentence per key and never called this).

The defect is not the dead bytes.  It is that each of those docstrings describes
a capability a reader will look for and not find, and the way it got there is
that nothing ran it.  This test asks the only question that catches it: is the
name reachable from anywhere in the repository?

Resolution is per module, not per name, because that is the difference between
noticing and not: ``draft.summarize`` is a real call and ``verify.summarize`` is
not, and a scan of attribute names alone counts them as one use.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "src" / "citevouch"
CORPUS = (ROOT / "src", ROOT / "tests", ROOT / "tools")


def _package_modules() -> dict[str, set[str]]:
    """Map module name (``citevouch.verify``) to its module-level function names."""
    modules: dict[str, set[str]] = {}
    for path in sorted(PACKAGE.glob("*.py")):
        name = f"citevouch.{path.stem}" if path.stem != "__init__" else "citevouch"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules[name] = {
            node.name
            for node in tree.body
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            and not node.name.startswith("__")
        }
    return modules


def _aliases(tree: ast.Module, module: str) -> dict[str, str]:
    """Local names this file binds to package modules (``verify``, ``draft_module``)."""
    out: dict[str, str] = {}
    package = module.rsplit(".", 1)[0] if "." in module else module
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            source = node.module or ""
            if node.level:
                base = package
                source = f"{base}.{source}" if source else base
            for imported in node.names:
                target = f"{source}.{imported.name}" if source else imported.name
                if target.startswith("citevouch"):
                    out[imported.asname or imported.name] = target
        elif isinstance(node, ast.Import):
            for imported in node.names:
                if imported.name.startswith("citevouch"):
                    out[imported.asname or imported.name.split(".")[0]] = imported.name
    return out


def _uses(module: str, path: Path) -> tuple[set[str], set[tuple[str, str]]]:
    """Bare names and ``(module, name)`` attribute references this file makes."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    aliases = _aliases(tree, module)
    bare: set[str] = set()
    qualified: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            bare.add(node.id)
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            target = aliases.get(node.value.id)
            if target is not None:
                qualified.add((target, node.attr))
    return bare, qualified


def _reachable() -> dict[str, set[str]]:
    """Every function name something in the repository names."""
    bare: set[str] = set()
    qualified: set[tuple[str, str]] = set()
    for folder in CORPUS:
        for path in folder.rglob("*.py"):
            if any(part in {".venv", "__pycache__", "build", "dist"} for part in path.parts):
                continue
            relative = (
                path.relative_to(ROOT / "src") if path.is_relative_to(ROOT / "src") else path
            )
            if path.is_relative_to(ROOT / "src"):
                stem = Path(relative).with_suffix("")
                parts = list(stem.parts)
                if parts[0] == "citevouch":
                    module = "citevouch" if len(parts) == 1 else ".".join(parts)
                else:  # pragma: no cover - not expected
                    module = ".".join(parts)
            else:
                module = ""
            found_bare, found_qualified = _uses(module, path)
            bare |= found_bare
            qualified |= found_qualified
    return {"bare": bare, "qualified": qualified}


def test_no_module_level_function_is_unreachable() -> None:
    modules = _package_modules()
    names = _reachable()
    dead: list[str] = []
    for module, functions in sorted(modules.items()):
        for function in sorted(functions):
            if (module, function) in names["qualified"]:
                continue
            if function in names["bare"]:
                continue
            dead.append(f"{module}.{function}")
    assert dead == [], (
        "these functions are named nowhere in src/, tests/ or tools/ - each one "
        "is a docstring describing a feature the tool does not have: " + ", ".join(dead)
    )


def test_the_scan_can_see_a_function_that_is_used() -> None:
    """The guard above must not pass because the scan reached nothing.

    Without this, a resolver that returns empty sets makes both tests green and
    the first one stops meaning anything.
    """
    names = _reachable()
    assert ("citevouch.verify", "verify") in names["qualified"] or "verify" in names["bare"]
    assert len(names["bare"]) > 50, "the corpus scan found almost nothing"
