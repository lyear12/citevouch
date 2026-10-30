"""An extra dependency that nothing imports is a feature announcement.

`pyproject.toml` shipped `xlsx = ["openpyxl>=3.1"]` for several releases. No
module in `src/` imported openpyxl. Anyone who read the metadata, installed the
extra and waited for spreadsheet support got a successful install and no
feature, which is the most expensive kind of wrong: it costs nothing to fix and
nothing reports it.

The check is mechanical for the same reason the version guard is: a rule that
lives only in a document is a rule nobody runs.

Nothing here imports `tomllib`. It arrived in 3.11, this package supports 3.10,
and a test file that cannot be collected on a supported interpreter is a gate
with a hole in it - which is how the `sources.toml` reader broke on 3.10 while
the suite stayed green on 3.14.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SECTION = re.compile(r"^\[project\.optional-dependencies\]$")
TABLE = re.compile(r"^\[(?P<name>[^\]]+)\]$")
ENTRY = re.compile(r"^(?P<key>[A-Za-z0-9_.-]+)\s*=\s*\[(?P<list>.*)\]$")
STRING = re.compile(r'"([^"]*)"')


def extras() -> dict[str, list[str]]:
    """Read `[project.optional-dependencies]` without a TOML reader.

    Only the shape this project uses is understood: a table of names mapping to
    arrays of quoted requirement strings. Anything else in the section is
    reported as unreadable rather than silently ignored, because the whole point
    of this file is that a declaration nobody reads is a declaration nobody
    honours.
    """
    found: dict[str, list[str]] = {}
    inside = False
    for line in (ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        table = TABLE.match(stripped)
        if table is not None:
            inside = SECTION.match(stripped) is not None
            continue
        if not inside or not stripped or stripped.startswith("#"):
            continue
        entry = ENTRY.match(stripped)
        assert entry is not None, f"unreadable line in optional-dependencies: {line!r}"
        found[entry.group("key")] = STRING.findall(entry.group("list"))
    return found


def imported_names() -> set[str]:
    """Every top-level module name imported anywhere under ``src/``."""
    names: set[str] = set()
    for path in (ROOT / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(
            r"^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)", text, re.MULTILINE
        ):
            names.add(match.group(1))
    return names


def test_the_reader_finds_the_pyproject_section() -> None:
    # A parser that returns {} would make the two tests below pass forever.
    assert "dev" in extras(), "the optional-dependencies table was not found"


def test_the_only_extra_is_the_one_a_contributor_installs() -> None:
    assert set(extras()) <= {"dev"}, (
        "an extra exists that is not the developer's; either the code that uses "
        f"it is missing, or the extra is: {sorted(extras())}"
    )


def test_every_name_an_extra_promises_is_actually_imported() -> None:
    """`dev` is exempt because pytest and ruff are run, not imported.

    They are exempt by name, not by luck: if a second run-only extra appears,
    this test fails until someone decides which category it is in.
    """
    used = imported_names()
    for extra, requirements in extras().items():
        if extra == "dev":
            continue
        for requirement in requirements:
            module = re.split(r"[<>=!\[ ]", requirement, maxsplit=1)[0]
            module = module.replace("-", "_")
            assert module in used, (
                f"the {extra!r} extra requires {requirement!r}, but nothing "
                "under src/ imports it - the extra advertises a feature the "
                "tool does not have"
            )


def test_the_readme_does_not_advertise_the_removed_extra() -> None:
    for name in ("README.md", "README.zh-CN.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "citevouch[xlsx]" not in text, f"{name} still offers the xlsx extra"
