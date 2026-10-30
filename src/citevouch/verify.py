"""Verify: re-check a ledger against the sources as they are now.

This is the half of the tool that earns its place in CI.  ``scan`` recorded
what was true when the author looked; ``verify`` answers, on every later run:

* is each quote still in the page it was recorded from?
* did it move to a different page (a new edition, a shifted layout)?
* did the numbers the manuscript quotes still match the numbers in the source?
* is the recorded manuscript still the one on disk?
* did a source file change since the ledger was written?

The distinction that matters is between "gone" and "moved".  A quote that moved
is usually fine and always worth a look; a quote that is gone is usually a
mistake and always blocks the release.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .bibtex import doi_of, field_findings
from .matching import excerpt, find_in_pages
from .model import Finding, Ledger
from .scan import ScanOptions, _resolve, scan
from .sources import (
    discover_sources,
    extract_pages,
    page_hint_is_valid,
    resolve_source,
    sha256_file,
)
from .textnorm import canonical_number


@dataclass
class VerifyResult:
    findings: list[Finding] = field(default_factory=list)
    checked: int = 0
    verified: int = 0
    moved: int = 0
    missing: int = 0
    skipped: int = 0

    @property
    def ok(self) -> bool:
        return not any(f.severity == "high" for f in self.findings)


def verify(
    ledger: Ledger,
    options: ScanOptions,
    check_manuscript_hash: bool = True,
) -> VerifyResult:
    """Re-check ``ledger`` against the files currently on disk."""
    result = VerifyResult()
    root = Path(options.root)
    manuscript_path = _resolve(root, options.manuscript)

    # The ledger is a claim about a specific text.  If the text changed, the
    # ledger is not wrong, it is stale — and saying so beats silently verifying
    # claims that no longer exist in the manuscript.
    #
    # A missing manuscript is the largest possible change to it, and it used to
    # slip through this guard because the `exists()` half was an `and` rather
    # than its own case: the PDFs all still matched, so `verify` returned a
    # green "1 verified" about a document that was not there.  Deleting the
    # thing under review must never be the way to make the check pass.
    if check_manuscript_hash and ledger.manuscript_sha256:
        if not manuscript_path.exists():
            result.findings.append(
                Finding(
                    code="ledger-stale",
                    message=(
                        f"{manuscript_path.name} recorded by the ledger no longer exists; "
                        "restore it, or point --root/--ledger at the project it belongs to"
                    ),
                    path=str(manuscript_path),
                )
            )
            result.skipped = len(ledger.claims)
            return result
        # The ledger names the document it is about.  If the command-line
        # manuscript is a different file, the hash comparison below is not a
        # drift check at all - it is two unrelated files disagreeing, which
        # would be reported as "your manuscript changed" and send the author
        # looking for an edit that never happened.  Name the real problem.
        recorded_name = Path(ledger.manuscript).name
        if recorded_name and recorded_name != manuscript_path.name:
            result.findings.append(
                Finding(
                    code="ledger-stale",
                    message=(
                        f"ledger describes {recorded_name}, but this check was asked about "
                        f"{manuscript_path.name}; run `citevouch scan` for this document, or "
                        "point --ledger at the right project"
                    ),
                    path=str(manuscript_path),
                )
            )
            result.skipped = len(ledger.claims)
            return result
        current = sha256_file(manuscript_path)
        if current != ledger.manuscript_sha256:
            result.findings.append(
                Finding(
                    code="ledger-stale",
                    message=(
                        f"{manuscript_path.name} changed since the ledger was written; "
                        "run `citevouch scan` to re-record the evidence"
                    ),
                    path=str(manuscript_path),
                )
            )
            result.skipped = len(ledger.claims)
            return result

    known = discover_sources(root, options.sources)
    pages_cache: dict[str, tuple[list, str]] = {}
    # Sources whose text could not be extracted.  Their claims are skipped
    # rather than searched, because searching no pages can only produce a
    # "quote not found" verdict about a PDF nobody managed to read.
    broken_sources: set[str] = set()
    entry_keys = set(ledger.entries)
    used_entries: set[str] = set()

    for claim in ledger.claims:
        result.checked += 1
        # The bibliography key the claim cites is ``ref`` when present, and
        # ``source`` otherwise — a manuscript that names its PDF and its bib
        # entry the same way should not have to write the key twice.
        ref_key = claim.ref or claim.source
        if ref_key in entry_keys:
            used_entries.add(ref_key)

        path = resolve_source(claim.source, known)
        if path is None:
            # The ledger records paths relative to the project root so that a
            # clone on another machine still resolves.  Reading one back has to
            # undo that: ``papers/x.pdf`` means ``<root>/papers/x.pdf`` here.
            requested = ledger.sources.get(claim.source)
            if requested and requested.path:
                recorded = Path(requested.path)
                if not recorded.is_absolute():
                    recorded = root / recorded
                # `is_file`, not `exists`: a directory satisfies exists() and
                # then dies inside sha256_file as PermissionError, which leaves
                # the process at exit 1 - the code that means "findings", not
                # "crash". A directory recorded as a source is a project
                # mistake; it should read as source-missing.
                path = str(recorded) if recorded.is_file() else None
        if path is None:
            result.missing += 1
            result.findings.append(
                Finding(
                    code="source-missing",
                    message=f"claim {claim.id}: source {claim.source!r} cannot be found any more",
                    claim_id=claim.id,
                    path=claim.path,
                    line=claim.line,
                )
            )
            continue

        if path not in pages_cache:
            pages, problem = extract_pages(path, root, use_cache=options.use_cache)
            if problem is not None:
                result.findings.append(problem)
                broken_sources.add(path)
                pages_cache[path] = (
                    [],
                    sha256_file(Path(path)) if Path(path).exists() else "",
                )
            else:
                pages_cache[path] = (pages, sha256_file(Path(path)))
        pages, current_sha = pages_cache[path]

        # Compare the hash before the unreadable-source skip below.  The skip
        # says "I cannot search this file and will not pretend otherwise"; it
        # must not also suppress "and it is not the file you recorded".  A
        # corrupt replacement is the most common shape of that swap, so the
        # ordering decided whether the user ever heard about it.
        recorded = ledger.sources.get(claim.source)
        if (
            recorded is not None
            and recorded.sha256
            and current_sha
            and recorded.sha256 != current_sha
        ):
            result.findings.append(
                Finding(
                    code="source-changed",
                    message=(
                        f"claim {claim.id}: {Path(path).name} is a different file than the "
                        "one the ledger recorded; re-check this quote by hand"
                    ),
                    claim_id=claim.id,
                    path=claim.path,
                    line=claim.line,
                )
            )

        # A source that could not be read has no pages, and searching an empty
        # page list can only say "not found" - a verdict about the author's
        # quote that is really a verdict about the PDF.  Say the one true
        # thing (already said above, as source-unreadable) and skip the claim;
        # a false quote-missing here would point at the wrong problem for the
        # rest of the project's life.
        if not pages and path in broken_sources:
            result.skipped += 1
            continue

        # The hint is judged by the same rule scan uses. A ledger edited by
        # hand, or written by an older build, can reach here with a page the
        # document does not have; handing that to the matcher makes it search
        # page 0, miss, search everywhere, find page 1, and report
        # `quote-moved` - a true sentence about a false premise.
        usable_page = claim.page if page_hint_is_valid(claim.page, len(pages)) else None
        if claim.page is not None and usable_page is None:
            result.findings.append(
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

        match = find_in_pages(claim.quote, pages, usable_page)
        if match.found:
            if usable_page is not None and match.page != usable_page:
                result.moved += 1
                result.findings.append(
                    Finding(
                        code="quote-moved",
                        message=(
                            f"claim {claim.id}: quote is on page {match.page}, "
                            f"the ledger says {usable_page}"
                        ),
                        claim_id=claim.id,
                        path=claim.path,
                        line=claim.line,
                    )
                )
            else:
                result.verified += 1
                result.findings.append(
                    Finding(
                        code="quote-found",
                        message=f"claim {claim.id}: quote found on page {match.page}",
                        claim_id=claim.id,
                        path=claim.path,
                        line=claim.line,
                    )
                )
            result.findings.extend(_number_checks(claim, pages, match.page))
        elif match.tier == "fuzzy":
            result.missing += 1
            result.findings.append(
                Finding(
                    code="quote-fuzzy",
                    message=(
                        f"claim {claim.id}: {match.reason} "
                        f"(closest passage, page {match.page}, similarity {match.similarity:.2f}): "
                        f"{excerpt(match.context)}"
                    ),
                    claim_id=claim.id,
                    path=claim.path,
                    line=claim.line,
                )
            )
            result.findings.extend(_number_checks(claim, pages, match.page))
        elif match.tier == "numbers":
            # The words are right and the digits are not — a typo, not a
            # fabricated quote, so it is reported as a number problem.
            result.missing += 1
            result.findings.append(
                Finding(
                    code="number-absent-in-quote",
                    message=(
                        f"claim {claim.id}: the words match page {match.page} but the numbers "
                        f"do not; the quote records {', '.join(claim.numbers) or 'no numbers'}"
                    ),
                    claim_id=claim.id,
                    path=claim.path,
                    line=claim.line,
                )
            )
            result.findings.extend(_number_checks(claim, pages, match.page))
        else:
            result.missing += 1
            result.findings.append(
                Finding(
                    code="quote-missing",
                    message=(
                        f"claim {claim.id}: {excerpt(claim.quote)} — {match.reason or 'not found'}"
                        f" in {Path(path).name}"
                    ),
                    claim_id=claim.id,
                    path=claim.path,
                    line=claim.line,
                )
            )

    unused = sorted(entry_keys - used_entries)
    if unused:
        # One finding per unused key drowns the real ones: a 40-entry
        # bibliography produces 35 lines of noise that hide the single quote
        # that went missing.  Report the set, not each member.
        shown = ", ".join(unused[:8]) + (f" … (+{len(unused) - 8})" if len(unused) > 8 else "")
        result.findings.append(
            Finding(
                code="bib-key-unused",
                message=f"{len(unused)} bibliography entries are cited by no claim: {shown}",
            )
        )
    for claim in ledger.claims:
        # Without a bibliography in the ledger there is nothing to be missing
        # from; reporting "key not in the bibliography" then is noise that
        # teaches users to ignore the check.
        if not ledger.entries:
            break
        ref_key = claim.ref or claim.source
        if ref_key in ledger.entries:
            continue
        result.findings.append(
            Finding(
                code="bib-key-missing",
                message=(
                    f"claim {claim.id} cites {ref_key!r}, which is not in the "
                    "bibliography the ledger recorded"
                ),
                claim_id=claim.id,
                path=claim.path,
                line=claim.line,
            )
        )
    result.findings.extend(field_findings(ledger.entries))
    return result


def _number_checks(claim, pages, page_number: int | None) -> list[Finding]:
    """Every number quoted by the manuscript must still be on the cited page.

    The check is deliberately narrow: it only sees numbers that appear *inside*
    the quote, so a manuscript may discuss a number without quoting it.  It
    exists to catch a re-typed statistic, which is the failure mode that reads
    as correct for months.
    """
    out: list[Finding] = []
    if not claim.numbers:
        return out
    page = None
    for candidate in pages:
        if candidate.number == page_number:
            page = candidate
            break
    if page is None:
        return out
    present = {canonical_number(t) for t in _numbers(page.text)}
    for raw in claim.numbers:
        if canonical_number(raw) not in present:
            out.append(
                Finding(
                    code="number-absent-in-quote",
                    message=(
                        f"claim {claim.id}: the quote says {raw} but page {page_number} "
                        "of the source does not contain that number"
                    ),
                    claim_id=claim.id,
                    path=claim.path,
                    line=claim.line,
                )
            )
    return out


def _numbers(text: str) -> tuple[str, ...]:
    from .textnorm import numbers_in  # local import keeps the hot path honest

    return numbers_in(text)


def rebuild(options: ScanOptions) -> tuple[Ledger, list[Finding]]:
    """Convenience wrapper so the CLI has one call per verb."""
    return scan(options)


def summarize(result: VerifyResult) -> str:
    parts = [
        f"checked {result.checked}",
        f"verified {result.verified}",
    ]
    if result.moved:
        parts.append(f"moved {result.moved}")
    if result.missing:
        parts.append(f"missing {result.missing}")
    if result.skipped:
        parts.append(f"skipped {result.skipped}")
    return ", ".join(parts)


def doi_index(ledger: Ledger) -> dict[str, str]:
    """Map DOI to cite key, for the optional Crossref cross-check."""
    out: dict[str, str] = {}
    for key, entry in ledger.entries.items():
        doi = doi_of(entry)
        if doi and doi not in out:
            out[doi] = key
    return out
