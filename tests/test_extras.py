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


# `dev` is exempt from the "must be imported" rule because its members are run
# rather than imported, but the exemption is by name and each member is checked
# in the other direction below: something in the repository has to use it.
RUN_ONLY = "dev"


def test_every_name_an_extra_promises_is_actually_imported() -> None:
    used = imported_names()
    for extra, requirements in extras().items():
        if extra == RUN_ONLY:
            continue
        for requirement in requirements:
            module = _module_of(requirement)
            assert module in used, (
                f"the {extra!r} extra requires {requirement!r}, but nothing "
                "under src/ imports it - the extra advertises a feature the "
                "tool does not have"
            )


def test_every_run_only_dependency_is_used_by_a_command() -> None:
    """The dev extra is a promise too, just a different one.

    `dev` exists for people who clone this repository, and everything in it has
    to be invoked by something they will run: pytest by the suite, ruff by the
    lint job, PyYAML by `tests/test_action.py`. It declared only pytest and ruff
    while that file imported yaml, so every job on all three operating systems
    failed collection with `ModuleNotFoundError: No module named 'yaml'` - a
    dependency used by the tests but not promised by the extra is the same
    defect as a feature declared and not built, seen from the other side.
    """
    for requirement in extras().get(RUN_ONLY, []):
        module = _module_of(requirement)
        assert _evidence(module), (
            f"the dev extra promises {requirement!r}, but nothing imports "
            f"{module!r} and no workflow names it - a dependency declared "
            "and unused is dead weight, and one used and undeclared breaks "
            "every clean checkout"
        )


# Only a python interpreter arms `-m`; `git commit -m first` and
# `pytest -m fixture` use the same flag for something else entirely, and a
# pattern loose enough to catch those would report a dependency on `first`.
RUN = re.compile(
    r'(?:sys\.executable|"python[0-9.]*"|"py")\s*,\s*"-m"\s*,\s*"([A-Za-z_][A-Za-z0-9_]*)"'
)


def _modules_the_suite_runs() -> dict[str, list[str]]:
    """Every `python -m NAME` the tests invoke, with the files that invoke it.

    A module a test *imports* is caught by the import scan above. One it
    *runs* is not: `tests/test_reproducible_build.py` calls `python -m build`,
    and `build` was not in the `dev` extra, so every clean checkout went red on
    collection while the lint job hid the hole by installing `build` by hand
    before running pytest. A dependency the suite needs and the extra does not
    promise is the same defect as a feature declared and not built.
    """
    found: dict[str, list[str]] = {}
    for path in (ROOT / "tests").rglob("*.py"):
        if path.name == Path(__file__).name:
            continue
        for match in RUN.finditer(path.read_text(encoding="utf-8")):
            found.setdefault(match.group(1), []).append(str(path.relative_to(ROOT)))
    return found


def test_every_module_the_suite_runs_is_promised_by_the_dev_extra() -> None:
    promised = {_module_of(requirement) for requirement in extras().get(RUN_ONLY, [])}
    # pytest runs the suite and is named by every runner; stdlib modules are
    # not installed and not promised, so they are not this test's business.
    allowed = promised | {"pytest", "pip", "citevouch"}
    missing: list[str] = []
    for module, callers in sorted(_modules_the_suite_runs().items()):
        if module in allowed:
            continue
        missing.append(f"{module} (run by {', '.join(sorted(set(callers)))})")
    assert not missing, (
        "the suite runs a module the dev extra does not install, so every clean "
        "checkout fails while a job that pre-installs it stays green:\n" + "\n".join(missing)
    )


def _module_of(requirement: str) -> str:
    """`PyYAML>=6.0` -> `yaml`, `pytest-cov` -> `pytest_cov`."""
    name = re.split(r"[<>=!\\[ ]", requirement, maxsplit=1)[0]
    aliases = {"pyyaml": "yaml"}
    return aliases.get(name.lower(), name.replace("-", "_"))


def _evidence(module: str) -> list[str]:
    """Where `module` is actually used, ignoring this file.

    Two kinds of use count, because a developer dependency can be either: an
    import in Python under `tests/`, `src/` or `tools/`, or a command named in a
    workflow. This file is excluded on purpose - it names every module it talks
    about, so counting its own mentions would make the check pass for any
    requirement at all.
    """
    hits: list[str] = []
    for folder in ("tests", "src", "tools"):
        for path in (ROOT / folder).rglob("*.py"):
            if path == Path(__file__).resolve():
                continue
            text = path.read_text(encoding="utf-8")
            pattern = rf"^\s*(?:from|import)\s+{re.escape(module)}\b"
            if re.search(pattern, text, re.MULTILINE):
                hits.append(f"{path.relative_to(ROOT)}")
    for path in (ROOT / ".github" / "workflows").glob("*.yml"):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if re.search(rf"\b{re.escape(module)}\b", line):
                hits.append(f"{path.relative_to(ROOT)}:{number}")
    return hits


def test_the_readme_does_not_advertise_the_removed_extra() -> None:
    for name in ("README.md", "README.zh-CN.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "citevouch[xlsx]" not in text, f"{name} still offers the xlsx extra"


def test_every_workflow_installs_the_dev_extra() -> None:
    """A workflow that names packages by hand is a list that can fall behind.

    The suite needs whatever `dev` promises; a job that installs `pytest` and
    `ruff` explicitly keeps working until someone adds a third name, and then it
    fails on a clean checkout of every operating system at once. Installing the
    extra is the only form that cannot go stale.
    """
    offenders: list[str] = []
    for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "pip install -e" in line and ".[dev]" not in line:
                offenders.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
    assert not offenders, (
        "a workflow installs the package without the dev extra:\n" + "\n".join(offenders)
    )
