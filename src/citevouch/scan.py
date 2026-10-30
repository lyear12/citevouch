"""Scan: read a manuscript, resolve its sources, and write the ledger.

Scanning answers "what does this manuscript claim, and where is the evidence?".
It records; :mod:`citevouch.verify` judges.  Keeping the two apart is what lets
``check`` run the pair without reporting the same claim twice, and it is why a
missing source is a finding here but never an exception: a ledger that records
an unbound claim is still useful — it names what is missing.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field, replace
from pathlib import Path

from . import __version__
from .bibtex import parse_bib
from .errors import UsageError
from .latex import looks_like_latex
from .manuscript import _CLAIMISH, parse_manuscript, scan_unbound_markers
from .model import Finding, Ledger, SourceRef
from .sources import (
    candidate_files,
    discover_sources,
    extract_pages,
    near_misses,
    page_hint_is_valid,
    resolve_source,
    sha256_file,
)


@dataclass
class ScanOptions:
    manuscript: str
    root: str = "."
    sources: list[str] = field(default_factory=list)
    bib: list[str] = field(default_factory=list)
    use_cache: bool = True
    now: str = ""


def _why_not_a_file(path: Path) -> str:
    """Say what is wrong with a path that was expected to be a file.

    "does not exist" about a directory is a false sentence, and a false
    sentence sends the reader to look for the wrong problem. `sources.py`
    already words this distinction for source files; these were the two
    places that judged with `is_file()` and explained with `exists()`.
    """
    return "is a directory, not a file" if path.is_dir() else "does not exist"


def _resolve(root: Path, raw: str) -> Path:
    """Resolve ``raw`` against ``root``, but accept a path that already works.

    ``citevouch check demo/manuscript.md --root demo`` is what people type, and
    joining it blindly would look for ``demo/demo/manuscript.md``.  A path that
    exists as given is never re-rooted: the file on disk is the authority.
    """
    path = Path(raw)
    if path.is_absolute():
        return path
    if path.exists():
        return path
    return root / path


def _no_claim_blocks_finding(text: str, path: str) -> Finding:
    """Report a manuscript that produced no claim blocks at all.

    The message tries to be useful in the order the reader needs it: what
    happened, the closest thing to a claim block in the file (usually a
    near miss - a capitalised ``Claim``, four backticks, a stray indent), and
    the command that would write correct blocks for them.

    ``no-claim-blocks`` is the only finding that can be true of a file holding
    no claims, and it is deliberately the *last* thing checked: a manuscript
    whose one block is broken already reports why (``claim-uncheckable``,
    ``claim-block-unclosed``), and adding "and there are no claims either" on
    top would be the same fact said twice in two vocabularies.
    """
    lines = text.splitlines()
    near = next(
        (number for number, line in enumerate(lines, start=1) if _CLAIMISH.match(line)),
        None,
    )
    if near is None:
        detail = (
            "a claim block opens with three backticks, the word `claim`, then "
            "`id=` and `source=`. This file has none. If its citations are "
            f"already written, `citevouch draft {path} -o claims.md` proposes "
            "blocks for them."
        )
    else:
        line = lines[near - 1].strip()
        ticks = len(line) - len(line.lstrip("`~"))
        # Name the near miss precisely.  "Four backticks" and "a capital C" are
        # the two ways to write something that reads like a claim block and is
        # not one, and telling the author which they did is the whole value of
        # this message.  The sample is indented rather than backtick-quoted on
        # purpose: a fenced line inside backticks renders as a longer fence.
        if ticks > 3:
            why = f"it opens with {ticks} backticks and a claim fence has three"
        elif "claim" not in line:
            why = "the keyword is spelled in a case the parser does not accept"
        else:
            why = "claim fences are three backticks followed by the word `claim`"
        detail = (
            f"line {near} reads like a claim block but is not one the parser "
            f"accepts ({why}). The line is:\n    {line[:100]}\n"
            "Nothing in this file was checked."
        )
    return Finding(
        code="no-claim-blocks",
        message=f"{path} contains no claim blocks, so nothing was checked: {detail}",
        path=path,
        # ``Finding`` is frozen, so the line goes in at construction; the hint
        # is the near miss when there is one, and 0 ("no line") when the file
        # simply has no claim-shaped line at all.
        line=near if near is not None else 0,
    )


def _ledger_path(root: Path, path: str | Path) -> str:
    """Store a source path the way a ledger can survive a move.

    An absolute path dies the moment the repository is cloned somewhere else,
    and a Windows path with backslashes does not resolve on the Linux job that
    runs the same ledger.  A path relative to ``root``, with forward slashes,
    is the same string on every platform.  A file outside ``root`` cannot be
    made relative meaningfully; it keeps its absolute form and the ledger is
    simply not portable, which is the honest outcome.
    """
    candidate = Path(path)
    try:
        relative = candidate.resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        return str(path)
    return relative.as_posix()


def _missing_source_message(key: str, candidates: list[str], claim_id: str) -> str:
    """Say the key cannot be resolved, and name what was probably meant.

    The candidates are printed, not used.  A tool that binds a claim to a PDF
    on a filename hunch can produce a confident ``quote-found`` about the
    wrong paper, and the author would never learn the page number it cited was
    from something else.  Naming the near misses keeps the fix to one paste
    while leaving the decision where it belongs.
    """
    base = (
        f"claim {claim_id} names source={key!r} but no entry in sources.toml "
        "and no --source path resolves it; add it to sources.toml"
    )
    close = near_misses(key, candidates)
    if not close:
        return base
    listed = ", ".join(close)
    return f"{base} (near misses on disk: {listed})"


def scan(options: ScanOptions) -> tuple[Ledger, list[Finding]]:
    """Build a ledger for ``options.manuscript``.

    Every finding returned here is about *recording*: an unparseable block, a
    source that cannot be read, a page hint the document cannot have.  Findings
    about whether the evidence still holds come from :mod:`citevouch.verify`.
    """
    root = Path(options.root)
    manuscript_path = _resolve(root, options.manuscript)
    if not manuscript_path.is_file():
        raise UsageError(f"manuscript {manuscript_path} does not exist")
    if looks_like_latex(manuscript_path):
        # A .tex file has no claim blocks, so scanning one reads zero claims and
        # reports a clean run - a green light for a manuscript nothing looked at.
        # That is the one verdict this tool must never give, and it is easy to
        # reach by accident because `draft` does accept .tex. Refuse here, at the
        # step that would have recorded the empty ledger, and name the command
        # that does work on a .tex source.
        raise UsageError(
            f"manuscript {manuscript_path} is LaTeX, and citevouch reads claim "
            "blocks - which live in Markdown, not in a .tex file. Propose them "
            f"first: `citevouch draft {manuscript_path} -o claims.md`, then check "
            "claims.md. Scanning the .tex would record zero claims and report a "
            "clean run for a manuscript nothing checked."
        )

    findings: list[Finding] = []
    text = manuscript_path.read_text(encoding="utf-8", errors="replace")
    parsed = parse_manuscript(text, path=manuscript_path.name)
    findings.extend(parsed.findings)
    # No claim blocks at all.  Every other finding describes a claim that was
    # checked and failed; this one describes a run in which nothing was checked,
    # and the summary line for it says "0 claims - 0 verified, 0 moved, 0
    # missing" with `worst severity: info` and exit 0.  A reader sees a green
    # run of a check that never happened: the CI job goes green, the section of
    # the release checklist is ticked, and the manuscript was never read.  The
    # `.tex` refusal above closes exactly this hole for one file extension; a
    # Markdown file with no blocks - or with blocks written in a dialect the
    # parser does not accept - is the same hole with a different name, so it
    # gets the same answer.
    if not parsed.claims and not any(f.code.startswith("claim-") for f in parsed.findings):
        findings.append(_no_claim_blocks_finding(text, manuscript_path.name))
    # A credibility marker outside a claim block is the most common way a
    # manuscript looks verified while nothing can be checked.  Passing the
    # claim spans keeps documented claims from being reported as unbound.
    findings.extend(scan_unbound_markers(text, path=manuscript_path.name, spans=parsed.spans))

    known = discover_sources(root, options.sources)
    ledger = Ledger(
        # Stored relative to ``root``, like the source paths below, so that
        # `scan demo/manuscript.md --root demo` and `cd demo && scan
        # manuscript.md` write the same ledger.  Recording the string the user
        # typed made the file depend on where they stood, which turned a
        # regenerable fixture into one that only matched one directory.
        manuscript=_ledger_path(root, manuscript_path),
        manuscript_sha256=sha256_file(manuscript_path),
        generated_at=options.now
        or _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        tool_version=__version__,
    )

    page_cache: dict[str, tuple[list, SourceRef | None]] = {}
    # Built once, and only if some claim actually fails to resolve: the walk is
    # over the user's project directory, which may be large.
    candidates: list[str] = []
    for claim in parsed.claims:
        path = resolve_source(claim.source, known)
        if path is None:
            if not candidates:
                candidates = candidate_files(root)
            findings.append(
                Finding(
                    code="source-missing",
                    message=_missing_source_message(claim.source, candidates, claim.id),
                    claim_id=claim.id,
                    path=claim.path,
                    line=claim.line,
                )
            )
            ledger.claims.append(claim)
            continue

        if path not in page_cache:
            pages, problem = extract_pages(path, root, use_cache=options.use_cache)
            if problem is not None:
                findings.append(problem)
                page_cache[path] = ([], None)
            else:
                page_cache[path] = (
                    pages,
                    SourceRef(
                        key=claim.source,
                        path=_ledger_path(root, path),
                        sha256=sha256_file(Path(path)),
                        pages=len(pages),
                    ),
                )
        pages, ref = page_cache[path]
        if ref is not None:
            # Two claims can name the same file under different keys.  The
            # ledger keeps one entry per key, and the key inside the entry must
            # be the one the entry is filed under — a copy that still says
            # "vaneecke2026cxn" under a "vantrijp2022" key makes a reader doubt
            # every other field in the file.
            filed = replace(ref, key=claim.source)
            ledger.sources.setdefault(claim.source, filed)

        # A page hint that cannot exist in the file is a mistake worth catching
        # at scan time, when the author still remembers what they meant.  The
        # lower bound matters as much as the upper: a 0 or negative page is
        # silently ignored by the matcher, which then reports a false
        # `quote-moved` ("found on page 1, the ledger says 0") for a claim
        # whose hint was simply not a page.
        if not page_hint_is_valid(claim.page, len(pages)):
            findings.append(
                Finding(
                    code="page-out-of-range",
                    message=(
                        f"claim {claim.id} points at page {claim.page} but "
                        f"{Path(path).name} has pages 1-{len(pages)}"
                    ),
                    claim_id=claim.id,
                    path=claim.path,
                    line=claim.line,
                )
            )
        ledger.claims.append(claim)

    for raw in options.bib:
        bib_path = _resolve(root, raw)
        if not bib_path.is_file():
            findings.append(
                Finding(
                    code="source-missing",
                    message=(f"bib file {bib_path} {_why_not_a_file(bib_path)}"),
                    path=str(bib_path),
                )
            )
            continue
        result = parse_bib(
            bib_path.read_text(encoding="utf-8", errors="replace"), str(bib_path)
        )
        findings.extend(result.findings)
        ledger.entries.update(result.entries)

    return ledger, findings
