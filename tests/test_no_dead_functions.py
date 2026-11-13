"""A name nothing reads is a promise the docstring makes and the tool does not keep.

Four dead functions shipped first: ``verify.doi_index`` ("for the optional
Crossref cross-check", which does not exist), ``verify.rebuild`` ("so the CLI has
one call per verb", which it does not use), ``verify.summarize`` (a second copy
of the sentence a run prints, unreachable while ``report.py`` writes the real
one), and ``sources._odd_bindings`` (the plural sentence for a manifest whose
values are not paths - the live code writes that sentence per key and never
called this).

Then three dead module-level names shipped while this test was green, because it
only asked about functions: ``matching.LIMIT_PROBE_CHARS`` (a constant whose
whole comment described a design that was abandoned before it landed, and whose
neighbour's docstring says that design cannot work), ``matching._TOKEN`` (the
whitespace tokeniser the CJK rewrite replaced), and ``sources.SourceText`` (a
class nothing constructs, carrying a ``ref()`` method that promised a
``SourceRef`` no run ever built).  A comment is not a weaker claim than a
docstring: both describe an implementation, and the reader believes both.

The defect is not the dead bytes.  It is that each of those names describes a
capability a reader will look for and not find, and the way it got there is
that nothing ran it.  This test asks the only question that catches it: is the
name reachable from anywhere in the repository?

Resolution is per module, not per name, because that is the difference between
noticing and not: ``draft.summarize`` is a real call and ``verify.summarize`` is
not, and a scan of attribute names alone counts them as one use.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "src" / "citevouch"
CORPUS = (ROOT / "src", ROOT / "tests", ROOT / "tools")


KINDS = ("functions", "constants", "classes")


def _module_level_names(tree: ast.Module) -> dict[str, set[str]]:
    """Module-level functions, assigned constants and classes, by kind.

    Constants matter as much as functions here: a comment above an unused
    constant is a description of code that is not there, and nothing in the
    repository runs it to find out.  Classes matter for the same reason - an
    unconstructed class is a type annotation other code may believe exists.
    """
    found: dict[str, set[str]] = {"functions": set(), "constants": set(), "classes": set()}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if not node.name.startswith("__"):
                found["functions"].add(node.name)
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("__"):
                found["classes"].add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and not target.id.startswith("__"):
                    found["constants"].add(target.id)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and not node.target.id.startswith("__"):
                found["constants"].add(node.target.id)
    return found


def _package_modules() -> dict[str, dict[str, set[str]]]:
    """Map module name (``citevouch.verify``) to its module-level names, by kind."""
    modules: dict[str, dict[str, set[str]]] = {}
    for path in sorted(PACKAGE.glob("*.py")):
        name = f"citevouch.{path.stem}" if path.stem != "__init__" else "citevouch"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules[name] = _module_level_names(tree)
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


def _uses(module: str, path: Path) -> set[tuple[str, str]]:
    """The ``(module, name)`` pairs this file *reads*.

    Three separate holes had to be closed before this could see a dead constant.

    **Only a load counts.**  An assignment target is the name being defined, not
    a reader of it, and counting it made every constant its own alibi: a module
    that said ``LEFT_OVER = 50`` and never read it looked used.  Functions and
    classes escaped that only because Python does not spell their definition as
    a name, which is why this hole went unnoticed for three versions.

    **A name imported by name belongs to the module it came from.**  ``from
    .draft import summarize`` followed by ``summarize()`` is a use of
    ``draft.summarize`` and says nothing about ``verify.summarize``.

    **A bare name read inside a package module is that module's own name.**  That
    is how a module reads its own constants - ``matching`` uses
    ``MAX_STITCHED_PAGES`` without qualifying it - and it is why a name is never
    credited to a module that did not import it.  Tests and tools read names they
    imported; anything else there is a local variable and credits nobody.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    aliases = _aliases(tree, module)
    qualified: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            target = aliases.get(node.id)
            if target is not None and target.count(".") >= 2:
                holder, _, symbol = target.rpartition(".")
                qualified.add((holder, symbol))
            elif module.startswith("citevouch"):
                qualified.add((module, node.id))
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            target = aliases.get(node.value.id)
            if target is not None:
                qualified.add((target, node.attr))
    return qualified


def _reachable() -> set[tuple[str, str]]:
    """Every ``(module, name)`` pair something in the repository reads."""
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
            qualified |= _uses(module, path)
    return qualified


def _unreachable() -> list[str]:
    """Every module-level name of every kind that nothing in the corpus reads."""
    modules = _package_modules()
    names = _reachable()
    dead: list[str] = []
    for module, kinds in sorted(modules.items()):
        for kind in KINDS:
            for name in sorted(kinds[kind]):
                if (module, name) in names:
                    continue
                dead.append(f"{module}.{name} ({kind[:-1]})")
    return dead


def test_no_module_level_name_is_unreachable() -> None:
    dead = _unreachable()
    assert dead == [], (
        "these names are named nowhere in src/, tests/ or tools/ - each one is a "
        "docstring or comment describing a feature the tool does not have: " + ", ".join(dead)
    )


def test_the_scan_can_see_a_function_that_is_used() -> None:
    """The guard above must not pass because the scan reached nothing.

    Without this, a resolver that returns empty sets makes both tests green and
    the first one stops meaning anything.
    """
    names = _reachable()
    assert ("citevouch.verify", "verify") in names
    assert ("citevouch.model", "Finding") in names
    assert len(names) > 500, "the corpus scan resolved almost nothing"


def test_the_scan_can_see_a_constant_that_is_used() -> None:
    """And it must see the two kinds it only just learned about.

    ``MAX_STITCHED_PAGES`` is read by ``matching.py`` itself and by two test
    modules, so a resolver that quietly returned nothing for constants would
    report it dead while this file was green.
    """
    modules = _package_modules()
    assert "MAX_STITCHED_PAGES" in modules["citevouch.matching"]["constants"]
    assert "PageText" in modules["citevouch.sources"]["classes"]
    assert "extract_pages" in modules["citevouch.sources"]["functions"]


def test_module_level_names_collects_every_kind() -> None:
    """Parse a sample that has one of each, including both constant spellings.

    The two constant spellings are separate branches below, and the annotated
    one is the rarer of the two - so it is the one a later edit would forget.
    """
    sample = ast.parse(
        "def f(): pass"
        + chr(10)
        + "async def g(): pass"
        + chr(10)
        + "class C: pass"
        + chr(10)
        + "PLAIN = 1"
        + chr(10)
        + "TYPED: int = 2"
        + chr(10)
        + "__all__ = []"
        + chr(10)
        + "__hidden__ = 3"
    )
    found = _module_level_names(sample)
    assert found["functions"] == {"f", "g"}
    assert found["classes"] == {"C"}
    assert found["constants"] == {"PLAIN", "TYPED"}, found["constants"]


def test_defining_a_name_is_not_reading_it(tmp_path: Path) -> None:
    """The hole that let a dead constant pass: its own definition counted."""
    source = tmp_path / "sample.py"
    source.write_text(
        "LEFT_OVER = 50" + chr(10) + "print(REALLY_READ)" + chr(10),
        encoding="utf-8",
        newline=chr(10),
    )
    read = _uses("citevouch.sample", source)
    assert ("citevouch.sample", "REALLY_READ") in read
    assert ("citevouch.sample", "LEFT_OVER") not in read, "an assignment target is not a reader"


def test_a_name_read_in_another_module_is_still_dead_here(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolution is per module, and this is the test that says so.

    ``draft.summarize`` was a real call while ``verify.summarize`` was dead; a
    guard that matched on the bare name would have called both live.  Synthesised
    here because the repository no longer has a pair to point at.
    """
    modules = {
        "citevouch.alpha": {"functions": {"shared"}, "constants": set(), "classes": set()},
        "citevouch.beta": {"functions": {"shared"}, "constants": set(), "classes": set()},
    }
    monkeypatch.setattr("test_no_dead_functions._package_modules", lambda: modules)
    monkeypatch.setattr(
        "test_no_dead_functions._reachable",
        lambda: {("citevouch.beta", "shared")},
    )
    dead = _unreachable()
    assert dead == ["citevouch.alpha.shared (function)"], dead


def test_a_constant_nothing_reads_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """The guard has to fail for a constant, not only for a function.

    Feeding it a synthetic package module is the only way to test that without
    committing a dead constant; the point being proved is that the ``(constant)``
    kind is really walked, which is what the three names above needed.
    """
    modules = _package_modules()
    modules["citevouch.matching"]["constants"].add("NEVER_READ_ANYWHERE")
    monkeypatch.setattr("test_no_dead_functions._package_modules", lambda: modules)
    dead = _unreachable()
    assert any("NEVER_READ_ANYWHERE" in entry for entry in dead), dead
    assert any("constant" in entry for entry in dead), dead
