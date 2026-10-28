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
from .manuscript import parse_manuscript, scan_unbound_markers
from .model import Finding, Ledger, SourceRef
from .sources import (
    discover_sources,
    extract_pages,
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

    findings: list[Finding] = []
    text = manuscript_path.read_text(encoding="utf-8", errors="replace")
    parsed = parse_manuscript(text, path=manuscript_path.name)
    findings.extend(parsed.findings)
    # A credibility marker outside a claim block is the most common way a
    # manuscript looks verified while nothing can be checked.  Passing the
    # claim spans keeps documented claims from being reported as unbound.
    findings.extend(scan_unbound_markers(text, path=manuscript_path.name, spans=parsed.spans))

    known = discover_sources(root, options.sources)
    ledger = Ledger(
        manuscript=str(options.manuscript),
        manuscript_sha256=sha256_file(manuscript_path),
        generated_at=options.now
        or _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        tool_version=__version__,
    )

    page_cache: dict[str, tuple[list, SourceRef | None]] = {}
    for claim in parsed.claims:
        path = resolve_source(claim.source, known)
        if path is None:
            findings.append(
                Finding(
                    code="source-missing",
                    message=(
                        f"claim {claim.id} names source={claim.source!r} but no file "
                        "matches it; add it to sources.toml or pass --source"
                    ),
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
        # at scan time, when the author still remembers what they meant.
        if claim.page is not None and pages and claim.page > len(pages):
            findings.append(
                Finding(
                    code="page-out-of-range",
                    message=(
                        f"claim {claim.id} points at page {claim.page} but "
                        f"{Path(path).name} has only {len(pages)} pages"
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
                    message=f"bib file {bib_path} does not exist",
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
