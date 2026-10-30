"""Command line interface.

Five verbs, one job each:

``scan``    record the evidence a manuscript points at
``verify``  re-check a recorded ledger against the files on disk
``check``   scan and verify in one pass (what CI runs)
``report``  re-render an existing ledger as a table
``doctor``  say whether this machine can see anything at all

``init-demo`` is a sixth, and it is the only one that writes a project rather
than reading one; it exists so the first run is not a wall of errors.

Exit codes are the whole CI contract: 0 clean, 1 findings at or above the
threshold, 2 usage error.  Nothing else may be returned — a CI job cannot
distinguish 3 from 1, and a crash dressed up as a finding teaches users to
ignore the tool.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from . import doctor as doctor_module
from . import draft as draft_module
from . import latex as latex_module
from .bibtex import parse_bib
from .errors import CitevouchError, UsageError
from .model import SEVERITIES, SUPPORTED_SCHEMA, BibEntry, Finding, Ledger
from .report import render_json, render_markdown, render_sarif, render_text
from .scan import ScanOptions, _resolve, scan
from .sources import discover_sources
from .verify import VerifyResult, verify

DEFAULT_LEDGER = "citevouch.lock.json"
RANK = {name: i for i, name in enumerate(SEVERITIES)}


def _options(args: argparse.Namespace) -> ScanOptions:
    return ScanOptions(
        manuscript=args.manuscript,
        root=args.root,
        sources=list(args.source or []),
        bib=list(args.bib or []),
        use_cache=not args.no_cache,
    )


def _emit(payload: str, stream=None) -> None:
    (stream or sys.stdout).write(payload)


def _safe_console() -> None:
    """Make the console output survive whatever the author actually wrote.

    Manifests are written in whatever language the author writes in, and this
    tool copies their words into findings.  Two separate problems follow.

    A Windows console on a codepage that cannot represent those words raises
    ``UnicodeEncodeError`` from ``print`` — a crash that has nothing to do with
    the manuscript.  The exit code is the contract a CI job reads, so the run
    has to finish with one; ``errors="replace"`` is lossy but keeps it honest.

    When the output is redirected rather than shown, the locale encoding is
    even less appropriate: a report piped into a file or another process is
    read back by tools that expect UTF-8, and a Chinese finding written as GBK
    is unreadable to them.  Interactive terminals keep their own encoding —
    changing it would garble the screen — but a redirected stream becomes
    UTF-8, which is what every other redirect target assumes.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            if not stream.isatty():
                stream.reconfigure(encoding="utf-8", errors="replace")
            else:
                stream.reconfigure(errors="replace")
        except (AttributeError, ValueError, OSError):  # pragma: no cover - exotic streams
            pass


def _exit_code(findings: list[Finding], fail_on: str) -> int:
    """0 when nothing reaches the threshold, 1 when something does.

    Nothing is special-cased here. ``quote-fuzzy`` used to force exit 1 no
    matter what ``--fail-on`` said, which made the documented contract ("1 when
    something reaches the threshold") false for that one code. The rule moved
    to where the rule belongs: a fuzzy match is a ``high`` severity finding, so
    the threshold decides like it does for everything else. One rule, one place.
    """
    threshold = RANK[fail_on]
    return 1 if any(RANK.get(f.severity, 0) >= threshold for f in findings) else 0


def _ledger_path(args: argparse.Namespace) -> Path:
    path = Path(args.ledger)
    return path if path.is_absolute() else Path(args.root) / path


def _writable_target(path: Path) -> None:
    """Raise ``UsageError`` when ``path`` cannot be a file this tool writes.

    Everything this tool writes goes through :func:`_write_text_lf`, and a path
    that lands on a directory - or under a parent that is a file - reached that
    writer as an ``OSError``: ``PermissionError`` from ``os.replace`` when the
    target is a directory, ``FileExistsError`` from ``mkdir`` when the parent is
    a file. Both escaped ``main()`` as tracebacks and exited 1, which in this
    tool's contract means "findings reached the --fail-on threshold" - a caller
    cannot tell a bad ``--ledger`` from a manuscript that failed its check.

    The read side was already protected: ``_read_ledger`` turns ``OSError`` into
    a usage error. This is the same guard on the write side, so the two halves
    agree about what a bad path means.
    """
    if path.is_dir():
        raise UsageError(f"{path} is a directory, not a file")
    parent = path.parent
    if parent.exists() and not parent.is_dir():
        raise UsageError(f"cannot write {path}: {parent} is a file, not a directory")


def _write_text_lf(path: Path, text: str) -> None:
    """Write UTF-8 with LF endings on every platform.

    ``Path.write_text`` opens in text mode with universal newlines, so on
    Windows every ``\n`` came out as ``\r\n``. For a lockfile that is committed
    and reviewed in diffs that is a real defect rather than a nuisance: a clean
    checkout on Linux and a scan on Windows disagree about every byte, git
    prints "CRLF will be replaced by LF" after each run, and the file the tool
    reads back is not the file it wrote. The repository promises LF
    (``.gitattributes``), so the writer promises it too.

    A path that cannot be written is a usage error rather than an exception:
    see :func:`_writable_target` for why the difference matters to a caller.
    """
    _writable_target(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    except OSError as exc:
        raise UsageError(f"cannot write {path}: {exc}") from exc


def _write_ledger(ledger: Ledger, path: Path) -> None:
    # Checked on the final name as well as the temporary one: a directory only
    # fails at ``replace`` time, after the work is done and the tree is dirty.
    _writable_target(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    _write_text_lf(tmp, json.dumps(ledger.to_json(), indent=2, ensure_ascii=False) + "\n")
    try:
        tmp.replace(path)
    except OSError as exc:
        raise UsageError(f"cannot write {path}: {exc}") from exc


def _read_ledger(path: Path) -> Ledger:
    if not path.exists():
        raise UsageError(f"no ledger at {path}; run `citevouch scan` first")
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UsageError(f"ledger {path} is not readable JSON: {exc}") from exc
    if not isinstance(blob, dict) or "claims" not in blob:
        raise UsageError(f"ledger {path} is not a citevouch ledger")
    # The ledger is a lockfile, and a schema number is how it says so. Reading
    # a future ledger with today's parser would half-parse it: fields the next
    # version added or renamed would come back empty, and "source-missing" on a
    # half-read claim is the false verdict this tool exists to avoid. Refuse
    # the file instead, and say which tool can read it.
    try:
        schema = int(blob.get("schema", 1))
    except (TypeError, ValueError):
        raise UsageError(
            f"ledger {path} has a non-numeric schema {blob.get('schema')!r}"
        ) from None
    if schema > SUPPORTED_SCHEMA:
        raise UsageError(
            f"ledger {path} is schema {schema}, newer than this citevouch "
            f"(understands up to {SUPPORTED_SCHEMA}); upgrade citevouch to read it"
        )
    if schema < 1:
        # Schema numbers are 1-based. 0 or a negative means the field was
        # written by something that is not this tool, and guessing which
        # generation of neither is not a service to anyone.
        raise UsageError(
            f"ledger {path} has schema {schema}; schemas start at 1, so this file "
            "was not written by citevouch - re-record it with `citevouch scan`"
        )
    return Ledger.from_json(blob)


def cmd_scan(args: argparse.Namespace) -> int:
    ledger, findings = scan(_options(args))
    out = _ledger_path(args)
    if not args.dry_run:
        _write_ledger(ledger, out)
    payload = _render(findings, ledger, args)
    _emit(payload)
    if not args.dry_run and (args.quiet is False):
        _emit(f"citevouch: wrote {out} ({_count(len(ledger.claims), 'claim')})\n", sys.stderr)
    elif args.dry_run:
        _emit(
            f"citevouch: dry run, {_count(len(ledger.claims), 'claim')} not written\n",
            sys.stderr,
        )
    return _exit_code(findings, args.fail_on)


def cmd_verify(args: argparse.Namespace) -> int:
    ledger = _read_ledger(_ledger_path(args))
    result = verify(ledger, _options(args), check_manuscript_hash=not args.allow_stale)
    _emit(_render(result.findings, ledger, args, result))
    return _exit_code(result.findings, args.fail_on)


def cmd_check(args: argparse.Namespace) -> int:
    """Scan and verify without writing, so CI never mutates the checkout."""
    options = _options(args)
    ledger_path = _ledger_path(args)
    if args.use_recorded:
        ledger = _read_ledger(ledger_path)
        result = verify(ledger, options, check_manuscript_hash=not args.allow_stale)
    else:
        ledger, scan_findings = scan(options)
        result = verify(ledger, options, check_manuscript_hash=False)
        # Scan findings come first: a claim that could not be bound to a source
        # explains why the verification below it says nothing about that claim.
        # One finding per (code, claim) pair, because the same unreadable PDF is
        # discovered by the scan pass and again by the verify pass, and a reader
        # shown the identical line twice learns nothing and trusts the list less.
        combined = scan_findings + result.findings
        seen: set[tuple[str, str]] = set()
        result.findings = [
            f
            for f in combined
            if not ((f.code, f.claim_id) in seen or seen.add((f.code, f.claim_id)))
        ]
    _emit(_render(result.findings, ledger, args, result))
    return _exit_code(result.findings, args.fail_on)


def _count(count: int, noun: str) -> str:
    """Write "1 claim" or "5 claims"; the message is read by people."""
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def cmd_draft(args: argparse.Namespace) -> int:
    """Propose claim blocks for a manuscript that has none.

    This is the only command that writes a file the project did not already
    have, so the rules are strict: the output path is named by the user, an
    existing file is never overwritten, and the manuscript itself is opened
    read-only.  Exit 0 always - a proposal is not a verdict, and a manuscript
    with nothing to propose is a fact about the manuscript, not an error.

    ``--output`` resolves the same way every other path in this tool does,
    against ``--root``, and then it is checked against the manuscript.  Both
    halves are load-bearing.  Resolving it against the process working
    directory made ``-o claims.md`` mean a different file depending on where
    the command was typed, while the manuscript, the bibliography, the sources
    and the ledger were all read relative to the root - two path rules in one
    command.  And without the comparison, ``-o manuscript.md --force`` replaced
    the author's paper with a file of proposals: when nothing could be
    proposed, the paper became nine lines of comment and the command still
    exited 0 saying it had written the manuscript.

    The output is joined to the root unconditionally, which is where it
    departs from :func:`citevouch.scan._resolve`.  That helper prefers a
    relative path that already exists, because for an input the file on disk
    is the authority.  For an output the opposite is true: it would make the
    destination depend on whether some unrelated file of the same name happens
    to be sitting in the directory the command was typed in, so
    ``draft paper.md --root proj -o claims.md`` would overwrite that bystander
    and write nothing under ``proj``.
    """
    root = Path(args.root)
    manuscript = _resolve(root, args.manuscript)
    if not manuscript.is_file():
        raise UsageError(f"manuscript {manuscript} does not exist")
    output = Path(args.output)
    if not output.is_absolute():
        output = root / output
    if output.resolve() == manuscript.resolve():
        raise UsageError(
            f"{output} is the manuscript this command is reading; "
            "choose another -o (claims.md is the default). Writing proposals "
            "over their source would destroy the paper they were read from, "
            "which --force cannot make safe"
        )
    if output.exists() and not args.force:
        raise UsageError(
            f"{output} already exists; pass --force to replace it, or choose another -o"
        )

    bib: dict[str, BibEntry] = {}
    for raw in args.bib:
        bib_path = _resolve(root, raw)
        if not bib_path.is_file():
            raise UsageError(f"bib file {bib_path} does not exist")
        parsed = parse_bib(
            bib_path.read_text(encoding="utf-8", errors="replace"), str(bib_path)
        )
        bib.update(parsed.entries)

    text = manuscript.read_text(encoding="utf-8", errors="replace")
    converted = latex_module.looks_like_latex(manuscript)
    if converted:
        text = latex_module.to_text(text)
    result = draft_module.draft(
        text,
        bib=bib,
        known=discover_sources(root, args.source),
        root=root,
    )
    text = draft_module.render(result, manuscript.name, converted=converted)
    _write_text_lf(output, text)
    if not args.quiet:
        _emit(f"citevouch: {draft_module.summarize(result)}\n", sys.stderr)
        if result.needed_sources:
            _emit(
                f"citevouch: {len(result.needed_sources)} key(s) need a line in "
                "sources.toml before this file can be scanned\n",
                sys.stderr,
            )
        _emit(
            f"citevouch: wrote {output}; read it, then "
            f"`citevouch check {output}` to see what it got wrong\n",
            sys.stderr,
        )
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Report whether this machine and this project can be checked at all.

    The exit code is 1 for a broken machine and 0 for a working one, and that
    is the only place in the tool where 1 does not mean "findings". A user with
    a broken install needs a failing exit code for the same reason CI does: a
    command that always returns 0 cannot be put in a script, and this is the
    command a support thread will ask them to paste.
    """
    reports = doctor_module.diagnose(root=args.root, manuscript=args.manuscript)
    broken = doctor_module.problems(reports)
    if args.format == "json":
        payload = json.dumps(
            {
                "tool_version": __version__,
                "root": args.root,
                "checks": [
                    {"name": r.name, "ok": r.ok, "detail": r.detail, "fix": r.fix}
                    for r in reports
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        _emit(payload + "\n")
    elif args.format == "sarif":
        _emit(render_sarif(doctor_module.findings(reports), __version__, args.root))
    else:
        doctor_module.render(reports)
    return 1 if broken else 0


def cmd_report(args: argparse.Namespace) -> int:
    ledger = _read_ledger(_ledger_path(args))
    lines = [
        f"# citevouch ledger — {ledger.manuscript}",
        "",
        f"- records: {_count(len(ledger.claims), 'claim')} against "
        f"{_count(len(ledger.sources), 'source')}",
        f"- bibliography: {_count(len(ledger.entries), 'entry')}",
        f"- written by citevouch {ledger.tool_version} at {ledger.generated_at}",
        "",
        "| claim | source | page | quote |",
        "|---|---|---|---|",
    ]
    for claim in ledger.claims:
        quote = claim.quote.replace("|", "\\|").replace("\n", " ")
        if len(quote) > 80:
            quote = quote[:79] + "…"
        # `claim.page or '—'` rendered page 0 as an em dash: the author asked
        # what the ledger says and got a dash meaning "nothing". Only None is
        # "no page"; a 0 is a number the reader is entitled to see, and one
        # worth seeing.
        page_cell = "—" if claim.page is None else claim.page
        lines.append(f"| `{claim.id}` | {claim.source} | {page_cell} | {quote} |")
    _emit("\n".join(lines) + "\n")
    return 0


DEMO_SOURCE = """A Study of Sentence Length
==========================

Abstract

This note reports the size of the corpus used in the experiment and the
distribution of sentence lengths across its two genres. The corpus contains
154,391 sentences in total, of which 12,004 contain a relative clause.
"""

DEMO_MANUSCRIPT = """# A note on corpus size

```claim id=corpus-size source=demo_source page=1
quote: |
  The corpus contains 154,391 sentences in total, of which 12,004 contain a
  relative clause.
claim: |
  The corpus holds 154,391 sentences, 12,004 of them with a relative clause.
```
"""


def cmd_init_demo(args: argparse.Namespace) -> int:
    """Scaffold a project that passes, so the first run is not a wall of errors.

    Every tool that starts with an empty screen asks its user to guess the
    format.  `init-demo` writes the files the format consists of, records the
    ledger, then runs the verifier over them so the first thing the user sees is
    a green summary and the shape of a correct claim block.

    Recording is part of scaffolding, not a second step the user has to
    discover: `verify` reads a ledger, so a scaffold that stops before writing
    one hands the user a project where the documented next command fails with
    "no ledger".  That exact failure reached the README, the acceptance job and
    the release smoke test before it was fixed here.
    """
    target = Path(args.directory)
    # A path that is a file is not an empty directory, and letting `iterdir`
    # discover that raises NotADirectoryError out of a command whose whole
    # contract is "0, 1, or 2". The check is here rather than in an except
    # clause because the useful sentence - this is a file - is already known.
    if target.exists() and not target.is_dir():
        _emit(f"citevouch: {target} is a file, not a directory\n", sys.stderr)
        return 2
    if target.exists() and any(target.iterdir()):
        _emit(f"citevouch: {target} is not empty; refusing to overwrite\n", sys.stderr)
        return 2
    target.mkdir(parents=True, exist_ok=True)
    manuscript = target / "manuscript.md"
    _write_text_lf(manuscript, DEMO_MANUSCRIPT)
    _write_text_lf(target / "sources.toml", '[sources]\ndemo_source = "demo_source.txt"\n')
    _write_text_lf(target / "demo_source.txt", DEMO_SOURCE)
    _emit(
        f"citevouch: wrote {manuscript}, sources.toml, demo_source.txt\n",
    )
    recorded = main(["scan", str(manuscript), "--root", str(target), "--quiet"])
    if recorded != 0:
        return recorded
    result = main(["verify", str(manuscript), "--root", str(target)])
    if result == 0:
        _emit(
            "\nNext: replace demo_source.txt with a real PDF, point sources.toml at it,"
            " and run `citevouch scan` to record the new evidence.\n"
        )
    return result


def _render(
    findings: list[Finding],
    ledger: Ledger,
    args: argparse.Namespace,
    result: VerifyResult | None = None,
) -> str:
    fmt = args.format
    if args.quiet:
        # `--quiet` means "I only want the things that are wrong", and that
        # sentence is format-independent. It used to be honoured by the text
        # renderer alone, so `--quiet --format sarif` uploaded the info-level
        # findings into code scanning and the flag did nothing where it was
        # most likely to be used (a CI gate).
        findings = [f for f in findings if f.severity not in ("info", "low")]
    if fmt == "json":
        return render_json(findings, ledger, result)
    if fmt == "sarif":
        return render_sarif(findings, __version__, args.root)
    if fmt == "markdown":
        return render_markdown(findings, result)
    return render_text(findings, result, show_info=not args.quiet)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="citevouch",
        description=(
            "Bind every claim in a manuscript to the page of the local source that "
            "proves it, and fail CI when that evidence drifts."
        ),
    )
    parser.add_argument("--version", action="version", version=f"citevouch {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("manuscript", help="path to the manuscript (Markdown)")
        p.add_argument("--root", default=".", help="project root (default: .)")
        p.add_argument(
            "--ledger",
            default=DEFAULT_LEDGER,
            help=f"ledger path (default: {DEFAULT_LEDGER})",
        )
        p.add_argument(
            "--source",
            action="append",
            default=[],
            help="extra source file (repeatable)",
        )
        p.add_argument(
            "--bib", action="append", default=[], help="bibliography file (repeatable)"
        )
        p.add_argument("--no-cache", action="store_true", help="ignore the extraction cache")
        p.add_argument(
            "--format",
            choices=("text", "json", "sarif", "markdown"),
            default="text",
            help="output format",
        )
        p.add_argument("--quiet", action="store_true", help="hide info-level lines")
        p.add_argument(
            "--fail-on",
            choices=SEVERITIES,
            default="high",
            help="lowest severity that makes the command exit 1 (default: high)",
        )
        p.add_argument(
            "--allow-stale",
            action="store_true",
            help="do not fail when the manuscript changed since the ledger",
        )

    p_scan = sub.add_parser("scan", help="record the evidence a manuscript points at")
    common(p_scan)
    p_scan.add_argument(
        "--dry-run", action="store_true", help="report without writing the ledger"
    )
    p_scan.set_defaults(func=cmd_scan)

    p_verify = sub.add_parser("verify", help="re-check a ledger against the files on disk")
    common(p_verify)
    p_verify.set_defaults(func=cmd_verify)

    p_check = sub.add_parser("check", help="scan + verify in one pass (for CI)")
    common(p_check)
    p_check.add_argument(
        "--use-recorded",
        action="store_true",
        help="verify the committed ledger instead of re-scanning the manuscript",
    )
    p_check.set_defaults(func=cmd_check)

    p_report = sub.add_parser("report", help="print a ledger as a table")
    p_report.add_argument("--root", default=".")
    p_report.add_argument("--ledger", default=DEFAULT_LEDGER)
    p_report.set_defaults(func=cmd_report)

    p_demo = sub.add_parser(
        "init-demo", help="write a small working example project and check it"
    )
    p_demo.add_argument("directory", help="directory to create (must be empty or absent)")
    p_demo.set_defaults(func=cmd_init_demo)

    p_doctor = sub.add_parser(
        "doctor",
        help="check that this machine can read PDFs at all (run it when nothing is found)",
    )
    # Deliberately not `common()`: doctor takes no ledger, no bibliography and
    # no --fail-on, because it is the command you run when the project is
    # suspect. Offering flags it cannot honour would suggest it reads the
    # project more deeply than it does.
    p_doctor.add_argument("--root", default=".", help="project directory (default: .)")
    p_doctor.add_argument(
        "--manuscript",
        default="manuscript.md",
        help="manuscript path relative to --root (default: manuscript.md)",
    )
    p_doctor.add_argument(
        "--format",
        choices=("text", "json", "sarif"),
        default="text",
        help="output format",
    )
    p_doctor.set_defaults(func=cmd_doctor)

    p_draft = sub.add_parser(
        "draft",
        help="propose claim blocks for a manuscript that cites things but proves nothing",
    )
    p_draft.add_argument("manuscript", help="the manuscript to read (never written to)")
    p_draft.add_argument(
        "-o",
        "--output",
        default="claims.md",
        help="where to write the proposals, relative to --root (default: claims.md)",
    )
    p_draft.add_argument("--root", default=".", help="project root (default: .)")
    p_draft.add_argument(
        "--source",
        action="append",
        default=[],
        help="extra source file (repeatable)",
    )
    p_draft.add_argument(
        "--bib", action="append", default=[], help="bibliography file (repeatable)"
    )
    p_draft.add_argument(
        "--force",
        action="store_true",
        help="replace the output file if it already exists",
    )
    p_draft.add_argument("--quiet", action="store_true", help="hide the summary")
    p_draft.set_defaults(func=cmd_draft)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _safe_console()
    try:
        return int(args.func(args))
    except UsageError as exc:
        _emit(f"citevouch: {exc}\n", sys.stderr)
        return 2
    except CitevouchError as exc:  # pragma: no cover - base class, kept for order
        _emit(f"citevouch: {exc}\n", sys.stderr)
        return 2
    except BrokenPipeError:  # pragma: no cover - `| head` in a pipeline
        return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
