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
from .errors import why_not_a_file
from .latex import looks_like_latex
from .manuscript import parse_manuscript
from .model import Finding
from .scan import _resolve
from .sources import candidate_files, near_misses, read_source_table
from .textnorm import count_of, read_text

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
    """The things about *this* project, as opposed to about the machine.

    The path is resolved by :func:`citevouch.scan._resolve`, the same helper
    ``scan``, ``verify``, ``check`` and ``draft`` use.  Joining ``root`` to a
    relative path unconditionally made this the one command that read
    ``paper/manuscript.md`` as ``paper/paper/manuscript.md``: with
    ``citevouch check paper/m.md --root paper`` verified and
    ``citevouch doctor --root paper --manuscript paper/m.md`` reporting
    ``paper\\paper\\m.md does not exist``, the command that exists to explain
    a failed run disagreed with the run.  Its own fix line tells the reader to
    pass ``paper/manuscript.md``, so following the advice reproduced it.
    """
    reports: list[Report] = []
    target = _resolve(root, manuscript)
    if target.is_file():
        if looks_like_latex(target):
            # `check` refuses a .tex file with exit 2 and says why: claim blocks
            # live in Markdown, and scanning the .tex would record zero claims
            # and report a clean run for a manuscript nothing checked.  `doctor`
            # said "[ok] manuscript paper.tex (69 bytes)" and exited 0, so the
            # command that exists to explain a run that found nothing was quiet
            # about the one thing that guarantees there is nothing to find.
            bare = target.name
            reports.append(
                Report(
                    name="manuscript",
                    ok=False,
                    detail=(
                        f"{target} is LaTeX, and this tool reads claim blocks, "
                        "which live in Markdown, not in a .tex file"
                    ),
                    fix=(
                        "Propose them first: `citevouch draft "
                        f"{bare} -o claims.md`, then check claims.md. Scanning "
                        "the .tex itself would record zero claims and report a "
                        "clean run for a manuscript nothing checked."
                    ),
                )
            )
            reports.append(_manifest(root))
            reports.append(_claim_sources(target, root))
            return reports
        reports.append(
            Report(
                name="manuscript", ok=True, detail=f"{target} ({target.stat().st_size} bytes)"
            )
        )
        reports.append(_claim_blocks(target))
    else:
        # `does not exist` was the only thing this check could say, so a
        # directory the reader can see in their file manager was reported as
        # absent, while `check` on the same path said `is a directory, not a
        # file`.  Two commands, two stories about one path.  why_not_a_file is
        # the answer the rest of the tool already gives - a directory, an
        # unreachable share and a missing file are three different mistakes
        # with three different next steps.
        what = why_not_a_file(target)
        fix = (
            "Pass the path you meant, e.g. "
            "`citevouch doctor --manuscript paper/manuscript.md`. "
            "`--root` is the project directory, not the manuscript."
        )
        if what == "is a directory, not a file":
            fix = (
                "That is a directory. Pass the manuscript inside it, e.g. "
                "`citevouch doctor --manuscript "
                f"{target / 'manuscript.md'}`."
            )
        reports.append(
            Report(
                name="manuscript",
                ok=False,
                detail=f"{target} {what}",
                fix=fix,
            )
        )

    reports.append(_manifest(root))
    reports.append(_claim_sources(target, root))
    return reports


def _claim_sources(target: Path, root: Path) -> Report:
    """Do the source keys this manuscript names actually bind to a file?

    The four checks above answer "is there a manifest", "is it readable", "are
    the files it names here", and "does the manuscript hold blocks".  All of
    them can pass while every claim in the file names a key nobody binds, and
    that is the one failure ``doctor`` exists to explain: ``check`` then prints
    ``source-missing`` once per claim and exits 1, and the reader is told the
    machine is fine and that "the source files are the place to look" — while
    the file they would go and look at is already present, correctly spelled,
    and simply filed under a different name in the manifest.

    Measured before this check existed: a project whose ``sources.toml`` binds
    ``other = "other.txt"`` and whose one claim names ``source=paper`` got
    seven ``[ok  ]`` lines and exit 0 from ``doctor``, and ``[high]
    source-missing ... claim c1 names source='paper' but no entry in
    sources.toml`` from ``check``.

    ``--source`` is deliberately not an input here: ``doctor`` does not accept
    it, because it is the command you run when the project is suspect, and a
    diagnosis that depended on repeating the flags you got wrong would be a
    diagnosis of a different command.
    """
    try:
        text = read_text(target)
    except OSError:
        # The `manuscript` check above already failed and said why in the terms
        # the author can act on ("does not exist", "is a directory").  Quoting
        # the errno here reads as a second, independent problem: the reader who
        # greps the report for `[FAIL]` lines sees one, and the reader who reads
        # every line sees two symptoms of one cause with two different
        # vocabularies.  This check owns "are the keys bound", which cannot be
        # asked of a file that is not there.
        return Report(
            name="sources",
            ok=True,
            detail="not checked, because the manuscript could not be read",
        )
    parsed = parse_manuscript(text, target.name)
    named = sorted({claim.source for claim in parsed.claims if claim.source})
    if not named:
        # The `claims` check owns "this file holds nothing"; saying it twice
        # would make one problem look like two.
        return Report(name="sources", ok=True, detail="no claim names a source")

    table = read_source_table(root)
    if table.manifest_problem:
        # The `manifest` check owns this failure and already printed the parser
        # message.  Repeating it here would make one problem look like two.
        return Report(
            name="sources",
            ok=True,
            detail="not checked, because the manifest could not be read",
        )
    unbound = [key for key in named if key not in table.found and key not in table.unusable]
    if not unbound:
        # Two ways to get here.  Either every key binds, or a key the manifest
        # names cannot be used (the file moved, or it is a directory) - and the
        # `manifest` check above already reported that with the value the author
        # typed.  The first version of this check folded both into one line, so
        # for the second kind it printed "1 source key, every one of them bound
        # to a file" one line below the check that had just said the file is not
        # there: a false sentence about the one project state this command
        # exists to describe.  Naming the second kind without claiming health is
        # the honest middle - the run still exits 1 on the manifest line, and
        # this line does not pretend to a second, independent problem.
        if table.unusable:
            held = [key for key in named if key in table.unusable]
            which = "it" if len(held) == 1 else "them"
            return Report(
                name="sources",
                ok=True,
                detail=(
                    f"{count_of(len(named), 'source key')}, of which "
                    f"{count_of(len(held), 'key')} cannot be used; the manifest "
                    f"line above names {which}"
                ),
            )
        return Report(
            name="sources",
            ok=True,
            detail=f"{count_of(len(named), 'source key')}, every one of them bound to a file",
        )

    candidates = candidate_files(root)
    parts: list[str] = []
    for key in unbound:
        offers = near_misses(key, candidates)
        sentence = f"{key!r} is named by a claim, and no entry in the manifest binds it"
        if offers:
            sentence += f"; the files nearest it on disk are {', '.join(offers)}"
        parts.append(sentence)
    verb = "is" if len(unbound) == 1 else "are"
    return Report(
        name="sources",
        ok=False,
        detail=(
            f"{count_of(len(unbound), 'source key')} named by a claim {verb} "
            "bound to nothing: " + "; ".join(parts)
        ),
        fix=(
            "Add each of those keys to sources.toml, or change the claim to the "
            "key the manifest already uses, and run `citevouch scan` afterwards "
            "so the ledger records the new paths."
        ),
    )


def _claim_blocks(target: Path) -> Report:
    """Does this manuscript hold anything the run could check?

    A file with no claim blocks produces ``0 claims — 0 verified, 0 moved,
    0 missing`` with ``worst severity: info`` and exit 0, which reads as a clean
    run of a check that never happened.  ``check`` reports it as
    ``no-claim-blocks`` (high) and exits 1, and ``verify`` does the same for a
    ledger that recorded none.  ``doctor`` printed ``[ok  ] manuscript ...`` and
    exited 0, so the command a reader runs *because* the report looked empty was
    the one telling them nothing was wrong.

    The condition is ``ParseResult.nothing_to_check`` - the same property both
    other readers use - rather than a third copy of ``no claims and no finding
    that starts with 'claim-'``.  Two readers already had that expression typed
    out separately; that is how this one came to be written without it.

    A block the parser refused is *not* reported as a problem here.  It has its
    own finding naming the line and the fault, and ``doctor`` exists to explain
    silence, not to pre-empt a message the next command will print in more
    detail.  It is still *counted*, though: ``parsed.claims`` holds the blocks
    the parser accepted while ``parsed.spans`` holds the ones it saw, and a file
    with one good block and one that forgot ``id=`` contains two.  Reporting the
    accepted count alone said "1 claim block" about that file - a false statement
    in the one check whose job is to stop false statements.
    """
    try:
        parsed = parse_manuscript(read_text(target), path=target.name)
    except OSError as problem:
        return Report(
            name="claims",
            ok=False,
            detail=f"{target} could not be read ({problem.strerror})",
            fix="Check the file's permissions, or pass a manuscript this tool can open.",
        )
    if parsed.claims:
        seen, read = len(parsed.spans), len(parsed.claims)
        if read == seen:
            return Report(
                name="claims",
                ok=True,
                detail=count_of(read, "claim block"),
            )
        return Report(
            name="claims",
            ok=True,
            detail=(
                f"{count_of(seen, 'claim block')}, {read} of which the parser "
                "could read; the next command names the rest"
            ),
        )
    if not parsed.nothing_to_check:
        # The parser found something and refused it.  That is a finding, not a
        # silence, and `check` will name the line.
        return Report(
            name="claims",
            ok=True,
            detail="none that the parser could read; the next command names why",
        )
    return Report(
        name="claims",
        ok=False,
        detail=(
            f"{target} holds no claim blocks, so every run will report "
            "0 claims checked and exit 0"
        ),
        fix=(
            "Write them by hand, or propose them from the citations already in "
            "the file: `citevouch draft "
            f"{target.name} -o claims.md`. A claim block opens with three "
            "backticks, the word `claim`, then `id=` and `source=`."
        ),
    )


def _manifest(root: Path) -> Report:
    """Does the manifest name files that are actually here?

    This check used to stop at ``candidate.is_file()``: a ``sources.toml`` that
    parses to nothing, or one that maps every key to a path that is not on this
    disk, was reported as ``[ok] manifest sources.toml (148 bytes)`` and the
    closing line said "Everything this tool needs is on this machine."  The
    next command then printed, per claim, ``source-missing`` — which is the
    exact failure ``doctor`` exists to explain, arriving from the command whose
    job was to rule it out.  A file's size is not a fact about whether it
    points anywhere.

    The three answers are deliberately different, because they need different
    work from the reader: no manifest at all is a supported way to work (pass
    ``--source``), a manifest that will not parse is a syntax problem in one
    file, and a manifest that names absent files is a path problem in this
    project.  Only the last two are failures.
    """
    table = read_source_table(root)
    if table.manifest_name is None:
        # Not a failure: a project may pass every source on the command line.
        return Report(
            name="manifest",
            ok=True,
            detail="no sources.toml (fine if every claim uses --source)",
        )

    path = root / table.manifest_name
    size = path.stat().st_size if path.is_file() else 0
    named = len(table.found) + len(table.unusable)
    if table.manifest_problem:
        return Report(
            name="manifest",
            ok=False,
            detail=f"{path} ({size} bytes) cannot be used: {table.manifest_problem}",
            fix=(
                "Fix that file, or delete it and pass each source with "
                "`--source <file>`; until it parses, every claim that names a "
                "key in it reports `source-missing`."
            ),
        )
    if table.unusable:
        listed = "; ".join(table.unusable[key] for key in sorted(table.unusable))
        # "names 1 source, and 1 one of them is not here" was the first draft:
        # count_of is for "N <noun>", not for a bare pronoun, and a number in
        # front of "one" reads like a typo. Two whole sentences instead.
        if len(table.unusable) == 1:
            sentence = (
                f"{path} ({size} bytes) names {count_of(named, 'source')}, and it is not here"
            )
        else:
            sentence = (
                f"{path} ({size} bytes) names {count_of(named, 'source')}, and "
                f"{len(table.unusable)} of them are not here"
            )
        return Report(
            name="manifest",
            ok=False,
            detail=f"{sentence}: {listed}",
            fix=(
                "Open that file and correct the paths, or move the missing files "
                "back; the paths are relative to the project root, not to this "
                "shell. Run `citevouch scan` afterwards, because the recorded "
                "ledger still holds the old paths."
            ),
        )
    return Report(
        name="manifest",
        ok=True,
        detail=(
            f"{path} ({size} bytes), {count_of(named, 'source')}, "
            "every one of them present on this machine"
        ),
    )


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
    """The broken checks, as findings, so ``--format sarif`` has something to say.

    Only the SARIF branch uses this; ``--format json`` carries every check,
    passing or not, because a machine-readable diagnosis is worth having
    whether or not anything is wrong.

    The code is ``check-unavailable`` and not ``source-unreadable``.  It used to
    be the latter, on the theory that one vocabulary per problem beats two - but
    SARIF is what a reader sees in the GitHub code-scanning tab, and the rule
    line above each result comes from the code, not from the message.  So a
    three-year-old interpreter and a read-only cache directory were both
    displayed under "A source file could not be read.", which is not what
    either of them is.  The message was always right; the word above it was
    borrowed from a neighbouring problem.
    """
    return [
        Finding(
            code="check-unavailable",
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
