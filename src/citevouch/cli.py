"""Command line interface.

Four verbs, one job each:

``scan``    record the evidence a manuscript points at
``verify``  re-check a recorded ledger against the files on disk
``check``   scan and verify in one pass (what CI runs)
``report``  re-render an existing ledger as a table

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
from .errors import CitevouchError, UsageError
from .model import SEVERITIES, SUPPORTED_SCHEMA, Finding, Ledger
from .report import render_json, render_markdown, render_sarif, render_text
from .scan import ScanOptions, scan
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

    ``quote-fuzzy`` is the one code that fails on its own regardless of
    ``--fail-on``. AGENTS.md ground rule 2 says a fuzzy match "must never exit
    0 on its own", and that sentence was true of the severity table and false
    of the code: a quote that is only approximately present was a medium, so
    ``--fail-on high`` (the default) returned success on a claim the tool had
    just said it could not verify. A check whose whole purpose is "a human must
    look at this" cannot report success while nobody has looked.
    """
    threshold = RANK[fail_on]
    if any(f.code == "quote-fuzzy" for f in findings):
        return 1
    return 1 if any(RANK.get(f.severity, 0) >= threshold for f in findings) else 0


def _ledger_path(args: argparse.Namespace) -> Path:
    path = Path(args.ledger)
    return path if path.is_absolute() else Path(args.root) / path


def _write_ledger(ledger: Ledger, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(ledger.to_json(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


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
        lines.append(f"| `{claim.id}` | {claim.source} | {claim.page or '—'} | {quote} |")
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
    if target.exists() and any(target.iterdir()):
        _emit(f"citevouch: {target} is not empty; refusing to overwrite\n", sys.stderr)
        return 2
    target.mkdir(parents=True, exist_ok=True)
    manuscript = target / "manuscript.md"
    manuscript.write_text(DEMO_MANUSCRIPT, encoding="utf-8")
    (target / "sources.toml").write_text(
        '[sources]\ndemo_source = "demo_source.txt"\n', encoding="utf-8"
    )
    (target / "demo_source.txt").write_text(DEMO_SOURCE, encoding="utf-8")
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
        return render_sarif(findings, __version__)
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
