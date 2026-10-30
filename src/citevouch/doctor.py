"""Answer "why did it find nothing" before the user has to ask.

The first failure a new user meets is not an error message. It is a run that
finishes and says every quote is missing, because the PDF could not be read at
all, or because the file it pointed at is not the file it recorded. There is
nothing in that output to tell them which, and the honest response to a tool
that reports six failures on a paper you know is correct is to stop using it.

``doctor`` exists to be the one command that is allowed to be reassuring. It
checks the things that silently remove the tool's ability to see anything:

* is there an extractor at all, and which one (``pypdf`` in-process, or the
  ``pdftotext`` binary);
* can the cache directory be written (a read-only cache is not an error, but it
  turns every run into a full re-extraction and nobody would know);
* is the interpreter one the package claims to support;
* does the project it was pointed at have the files it says it has.

Every line is a fact plus what it means. A check that cannot pass is reported
as a problem with the command that would fix it, never as a bare "FAILED" — the
user already knows something is wrong, which is why they are here.

Exit codes match the rest of the tool: 0 when nothing is broken, 1 when
something is. It is deliberately not 2 for a project with problems — a project
with problems is the normal case, not a usage error.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from shutil import which

from . import __version__
from .model import Finding

# The versions this package claims to run on, kept next to the check that
# enforces them rather than only in pyproject, so the two cannot drift apart
# silently in the direction that matters: a user on an older interpreter gets
# told, instead of getting a traceback about a symbol that does not exist.
MIN_PYTHON = (3, 10)

CACHE_DIRNAME = ".citevouch"


@dataclass
class Report:
    """One check and what it means."""

    name: str
    ok: bool
    detail: str
    # What the user should do next.  Present only when the check failed; a
    # suggestion attached to a passing check is noise that trains people to
    # stop reading the column.
    fix: str = ""


def _pypdf() -> Report:
    try:
        import pypdf

        version = getattr(pypdf, "__version__", "unknown")
    except ImportError:
        return Report(
            name="pypdf",
            ok=False,
            detail="not installed",
            fix=(
                "PDFs cannot be read in-process. Install it with "
                "`pip install pypdf`, or put the `pdftotext` binary on PATH."
            ),
        )
    return Report(name="pypdf", ok=True, detail=f"{version} (reads PDFs in-process)")


def _shorten(value: str, limit: int = 64) -> str:
    """Elide the middle of a long path so the table stays readable.

    A bundled toolchain can sit behind ninety characters of directories, and a
    diagnostic whose longest line is a path nobody reads pushes the line that
    matters off the screen. The middle is elided rather than the tail because
    the tail is the file name, which is the part being reported; the ellipsis is
    explicit so the reader knows the path is not the whole one.
    """
    if len(value) <= limit:
        return value
    head = limit // 3
    tail = limit - head - 1
    return f"{value[:head]}…{value[-tail:]}"


def _pdftotext() -> Report:
    found = which("pdftotext")
    if found is None:
        # Not a failure on its own: pypdf covers the common case, and a machine
        # without poppler is a machine with one fewer way to read a PDF, not a
        # broken install.
        try:
            import pypdf  # noqa: F401

            return Report(
                name="pdftotext",
                ok=True,
                detail="not on PATH (not needed; pypdf is installed)",
            )
        except ImportError:
            return Report(
                name="pdftotext",
                ok=False,
                detail="not on PATH, and pypdf is not installed either",
                fix=(
                    "There is no way to read a PDF right now. Install one of "
                    "them: `pip install pypdf`, or a poppler package that "
                    "provides `pdftotext`."
                ),
            )
    return Report(name="pdftotext", ok=True, detail=f"{_shorten(found)} (fallback extractor)")


def _python() -> Report:
    have = sys.version_info[:2]
    if have < MIN_PYTHON:
        return Report(
            name="python",
            ok=False,
            detail=f"{have[0]}.{have[1]} is older than {MIN_PYTHON[0]}.{MIN_PYTHON[1]}",
            fix=(
                f"citevouch {__version__} needs Python "
                f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer; older interpreters "
                "are missing the standard-library pieces it reads manifests "
                "with. Upgrade the interpreter, not the package."
            ),
        )
    return Report(name="python", ok=True, detail=f"{have[0]}.{have[1]}")


def _cache(root: Path) -> Report:
    directory = root / CACHE_DIRNAME / "cache"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".doctor-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as problem:
        # A read-only cache changes nothing about correctness - every run just
        # re-extracts. Say that plainly: the alternative is a user who reads
        # "FAILED" and believes the tool is broken when it is only slow.
        return Report(
            name="cache",
            ok=True,
            detail=f"{directory} is not writable ({problem.strerror}); every run will re-extract",
        )
    return Report(name="cache", ok=True, detail=f"{directory} is writable")


def _project(root: Path, manuscript: str) -> list[Report]:
    """The things about *this* project, as opposed to about the machine."""
    reports: list[Report] = []
    path = Path(manuscript)
    target = path if path.is_absolute() else root / path
    if target.is_file():
        reports.append(
            Report(
                name="manuscript", ok=True, detail=f"{target} ({target.stat().st_size} bytes)"
            )
        )
    else:
        reports.append(
            Report(
                name="manuscript",
                ok=False,
                detail=f"{target} does not exist",
                fix=(
                    "Pass the path you meant, e.g. "
                    "`citevouch doctor --manuscript paper/manuscript.md`. "
                    "`--root` is the project directory, not the manuscript."
                ),
            )
        )

    for name in ("sources.toml", "sources.json"):
        candidate = root / name
        if candidate.is_file():
            reports.append(
                Report(
                    name="manifest",
                    ok=True,
                    detail=f"{candidate} ({candidate.stat().st_size} bytes)",
                )
            )
            break
    else:
        # Not a failure: a project may pass every source on the command line.
        reports.append(
            Report(
                name="manifest",
                ok=True,
                detail="no sources.toml (fine if every claim uses --source)",
            )
        )
    return reports


def diagnose(root: str | Path = ".", manuscript: str = "manuscript.md") -> list[Report]:
    """Every check, in the order a person would hit them."""
    base = Path(root)
    reports = [_python(), _pypdf(), _pdftotext(), _cache(base)]
    reports.extend(_project(base, manuscript))
    return reports


def problems(reports: list[Report]) -> list[Report]:
    return [report for report in reports if not report.ok]


def render(reports: list[Report], stream=None) -> None:
    """Print one line per check, then one sentence about what to do."""
    out = stream or sys.stdout
    width = max(len(report.name) for report in reports)
    for report in reports:
        mark = "ok  " if report.ok else "FAIL"
        print(f"[{mark}] {report.name.ljust(width)}  {report.detail}", file=out)
        if not report.ok and report.fix:
            print(f"       {' ' * width}  -> {report.fix}", file=out)

    broken = problems(reports)
    print(file=out)
    if not broken:
        print(
            "Everything this tool needs is on this machine. "
            "If quotes are still reported missing, the source files are the place to look.",
            file=out,
        )
        return
    print(
        f"{len(broken)} of {len(reports)} checks failed. "
        "Nothing that reports quotes as missing is reliable until these are fixed:",
        file=out,
    )
    for report in broken:
        print(f"  - {report.name}: {report.detail}", file=out)


def findings(reports: list[Report]) -> list[Finding]:
    """The broken checks, as findings, so ``--format json`` has something to say.

    ``source-unreadable`` is the closest existing code and it is the honest one:
    a machine that cannot read a PDF is a machine whose every quote would be
    reported unreadable. Reusing it keeps the code inventory from growing a
    second vocabulary for the same problem.
    """
    return [
        Finding(
            code="source-unreadable",
            message=f"{report.name}: {report.detail}",
        )
        for report in problems(reports)
    ]


def cache_available(root: str | Path = ".") -> bool:
    """Is the extraction cache usable here? Exposed for tests and for ``scan``."""
    directory = Path(root) / CACHE_DIRNAME / "cache"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / f".probe-{os.getpid()}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError:
        return False
    return True
