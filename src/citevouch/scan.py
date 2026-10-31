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
from .errors import UsageError, why_not_a_file
from .latex import looks_like_latex
from .manuscript import _CLAIMISH, parse_manuscript, scan_unbound_markers
from .model import Finding, Ledger, SourceRef
from .sources import (
    SourceTable,
    candidate_files,
    extract_pages,
    near_misses,
    page_hint_is_valid,
    read_source_table,
    resolve_source,
    sha256_file,
)
from .textnorm import read_text


@dataclass
class ScanOptions:
    manuscript: str
    root: str = "."
    sources: list[str] = field(default_factory=list)
    bib: list[str] = field(default_factory=list)
    use_cache: bool = True
    now: str = ""


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


def _draft_advice(typed: str, name: str, root: str = ".") -> str:
    """The command that would propose claim blocks for ``typed``.

    Three things made the sentence this replaces un-runnable, and all of them
    are about the string being copied into a shell verbatim:

    * ``path`` is the *basename* everywhere in this module, because a finding
      must read the same on every machine.  Advice is not a finding: a reader
      who checked ``paper/m.md`` and copied ``citevouch draft m.md`` got
      ``manuscript m.md does not exist``, an exit 2, and a command that never
      mentioned the directory they were looking at.  So the advice names the
      manuscript the way the reader typed it.
    * ``-o claims.md`` is refused by ``draft`` when the manuscript *is*
      ``claims.md``, which is exactly the state a reader reaches after
      following the advice once.  The output name therefore has to differ from
      the input name; ``proposals.md`` is the next name that does.
    * A path only means what it meant alongside the ``--root`` it was resolved
      against.  ``check m.md --root paper`` reads ``paper/m.md``, so the
      command it printed - without the flag - resolved ``m.md`` against the
      current directory instead and reported ``manuscript m.md does not exist``.
      The advice repeats the root whenever the caller named one, so the pair
      keeps meaning what it meant.  The default is printed as nothing, because
      ``--root .`` in advice is noise and the plain sentence is pinned by tests
      and by the README.
    """
    output = "claims.md" if name != "claims.md" else "proposals.md"
    where = "" if root in ("", ".") else f" --root {root}"
    return f"`citevouch draft {typed}{where} -o {output}`"


def _no_claim_blocks_finding(
    text: str, path: str, typed: str | None = None, root: str = "."
) -> Finding:
    """Report a manuscript that produced no claim blocks at all.

    The message tries to be useful in the order the reader needs it: what
    happened, the closest thing to a claim block in the file (usually a
    near miss - a capitalised ``Claim``, four backticks, a stray indent), and
    the command that would write correct blocks for them.

    ``typed`` is the manuscript string as the caller's command line carried it,
    used only for the suggested command (see :func:`_draft_advice`), together
    with ``root``, the ``--root`` it was read against; the finding's own
    ``path`` stays the basename so that a report of the same project reads
    identically wherever it is checked out.

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
            f"already written, {_draft_advice(typed or path, path, root)} proposes "
            "blocks for them."
        )
    else:
        raw = lines[near - 1]
        line = raw.strip()
        ticks = len(line) - len(line.lstrip("`~"))
        indent = len(raw) - len(raw.lstrip())
        # Name the near miss precisely.  "Four backticks", "a capital C" and
        # "an indent" are the three ways to write something that reads like a
        # claim block and is not one, and telling the author which they did is
        # the whole value of this message.  The indent case used to fall
        # through to the generic sentence, which then quoted a line that
        # matched the rule it had just described - the message contradicted
        # itself in front of the reader.  The sample is indented rather than
        # backtick-quoted on purpose: a fenced line inside backticks renders as
        # a longer fence.
        if ticks > 3:
            why = f"it opens with {ticks} backticks and a claim fence has three"
        elif "claim" not in line:
            why = "the keyword is spelled in a case the parser does not accept"
        elif indent:
            why = (
                f"it is indented by {indent} space(s), and an indented fence is a "
                "code sample in Markdown, not a claim: start it at the left margin"
            )
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


def _manifest_name(table: SourceTable | None) -> str:
    """The manifest file the project has, for a sentence that tells the author to edit it.

    `sources.toml` is the default only because it is the one the README
    walks through. When the project keeps its keys in `sources.json` instead,
    telling the author to add the entry to `sources.toml` sends them to a
    file that is not in their checkout; they either create it and end up
    with two manifests, or conclude the tool read a different project.
    """
    if table is not None and table.manifest_name:
        return table.manifest_name
    return "sources.toml"


def _missing_source_message(
    key: str, candidates: list[str], claim_id: str, table: SourceTable | None = None
) -> str:
    """Say the key cannot be resolved, and name what was probably meant.

    The candidates are printed, not used.  A tool that binds a claim to a PDF
    on a filename hunch can produce a confident ``quote-found`` about the
    wrong paper, and the author would never learn the page number it cited was
    from something else.  Naming the near misses keeps the fix to one paste
    while leaving the decision where it belongs.

    ``table`` carries the two failures that are not "no entry": a key the
    manifest names whose file cannot be used, and a manifest nobody could parse.
    Both used to reach the reader as "no entry in sources.toml", which is a
    sentence about the one thing the author had already got right.
    """
    if table is not None:
        if key in table.unusable:
            return f"claim {claim_id} cannot be resolved: {table.unusable[key]}"
        if table.manifest_problem:
            return (
                f"claim {claim_id} names source={key!r}, and no --source path "
                f"resolves it, because the manifest could not be read: "
                f"{table.manifest_problem}"
            )
    # Name the manifest the project actually has. A project that keeps its
    # keys in `sources.json` was told to go and add the entry to
    # `sources.toml`, a file that does not exist in their checkout.
    named = _manifest_name(table)
    base = (
        f"claim {claim_id} names source={key!r} but no entry in {named} "
        f"and no --source path resolves it; add it to {named}"
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
        raise UsageError(f"manuscript {manuscript_path} {why_not_a_file(manuscript_path)}")
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
    text = read_text(manuscript_path)
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
        findings.append(
            _no_claim_blocks_finding(
                text, manuscript_path.name, typed=options.manuscript, root=options.root
            )
        )
    # A credibility marker outside a claim block is the most common way a
    # manuscript looks verified while nothing can be checked.  Passing the
    # claim spans keeps documented claims from being reported as unbound.
    findings.extend(scan_unbound_markers(text, path=manuscript_path.name, spans=parsed.spans))

    table = read_source_table(root, options.sources)
    known = table.found
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
                    message=_missing_source_message(claim.source, candidates, claim.id, table),
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
                    message=(f"bib file {bib_path} {why_not_a_file(bib_path)}"),
                    path=str(bib_path),
                )
            )
            continue
        result = parse_bib(read_text(bib_path), str(bib_path))
        findings.extend(result.findings)
        ledger.entries.update(result.entries)

    return ledger, findings
