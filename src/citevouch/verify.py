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
from .errors import why_not_a_file
from .manuscript import parse_manuscript
from .matching import excerpt, find_in_pages
from .model import Finding, Ledger
from .scan import ScanOptions, _no_claim_blocks_finding, _resolve, scan
from .sources import (
    discover_sources,
    extract_pages,
    page_hint_is_valid,
    resolve_source,
    sha256_file,
)
from .textnorm import canonical_number, read_text


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


def _gone_sentence(path: Path) -> str:
    """Say why the recorded manuscript cannot be opened.

    ``why_not_a_file`` answers a different question - what is wrong with a path
    that should have been a file - and its answers are predicates ("is a
    directory, not a file").  Here the sentence needs a verb, because the
    ledger sentence reads "m.md recorded by the ledger <answer>": the plain
    "does not exist" fits, the "cannot be reached" answer does not, and a
    directory needs "is a directory where a file was recorded".  Rewriting the
    sentence rather than splicing a fragment keeps both call sites readable.
    """
    if path.is_dir():
        return "is now a directory"
    if why_not_a_file(path).startswith("cannot be reached"):
        return "cannot be opened: the network path is not available from here"
    return "no longer exists"


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
        # `is_file`, not `exists`: a directory named `m.md` passes `exists()`
        # and then `sha256_file` raises PermissionError, which leaves `main`
        # as a traceback with exit 1 - and 1 is this tool's word for "the
        # manuscript has findings".  A path that is not a readable file is not
        # a manuscript, whichever way it fails to be one.
        if not manuscript_path.is_file():
            result.findings.append(
                Finding(
                    code="ledger-stale",
                    message=(
                        f"{manuscript_path.name} recorded by the ledger "
                        f"{_gone_sentence(manuscript_path)}; "
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

    # A ledger that recorded no claims is the recording of a run that checked
    # nothing, and reading it back produces the same shape as the manuscript
    # with no claim blocks: `0 claims - 0 verified`, worst `info`, exit 0.  The
    # recording does not make that verdict true - it only means the false green
    # reached disk first.  An empty ledger can also arrive from an older
    # version of this tool, so the guard belongs here and not only in `scan`.
    if not ledger.claims:
        try:
            text = read_text(manuscript_path)
        except OSError:
            text = ""
        # The near-miss sentence in `_no_claim_blocks_finding` says a line
        # "reads like a claim block but is not one the parser accepts", which is
        # the right thing to tell someone who is looking at a manuscript with no
        # blocks.  Here the file may hold perfectly good blocks that the ledger
        # never recorded - an empty ledger can arrive from an older version of
        # this tool - and then that sentence names a fault on the line that is
        # not faulty, while the real cause (the recording, not the text) goes
        # unsaid.  Ask the parser before borrowing its words.
        parsed = parse_manuscript(text, manuscript_path.name)
        if parsed.claims:
            result.findings.append(
                Finding(
                    code="no-claim-blocks",
                    message=(
                        f"{manuscript_path.name} has {len(parsed.claims)} claim block(s), but "
                        "the ledger recorded none; run `citevouch scan` to record them - "
                        "this run checked nothing"
                    ),
                    path=str(manuscript_path),
                )
            )
        elif not any(f.code.startswith("claim-") for f in parsed.findings):
            result.findings.append(_no_claim_blocks_finding(text, manuscript_path.name))
        else:
            # A block the parser found and refused is not the same thing as a
            # file with no blocks, and `scan` has said so since the emptiness
            # guard was written.  This branch asked the parser only whether it
            # produced claims, so a block missing its `id=` produced zero claims
            # and was then described as "no claim blocks", which is false: the
            # parser's own finding, one screen up, names the block.  Report the
            # reasons the parser gave rather than a summary of the outcome.
            result.findings.extend(parsed.findings)
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
            # A quote that runs across a break is on both pages it touches, so
            # a ledger pointing at either one is not a move.  Calling it one
            # would teach the author to edit a number that was already right.
            on_the_recorded_page = usable_page is None or usable_page in (
                match.page,
                match.spans_to,
            )
            if not on_the_recorded_page:
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
                where = f"page {match.page}"
                if match.spans_to is not None:
                    # Say the quote runs onto the next page.  The author is
                    # about to look it up, and a reader told only "page 6"
                    # who finds the sentence ending there and continuing on
                    # page 7 has been told a half-truth by a tool whose whole
                    # promise is that its sentences are true.
                    where += f" (running onto page {match.spans_to})"
                result.findings.append(
                    Finding(
                        code="quote-found",
                        message=f"claim {claim.id}: quote found on {where}",
                        claim_id=claim.id,
                        path=claim.path,
                        line=claim.line,
                    )
                )
            result.findings.extend(_number_checks(claim, pages, match.page, match.spans_to))
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


def _number_checks(
    claim, pages, page_number: int | None, spans_to: int | None = None
) -> list[Finding]:
    """Every number quoted by the manuscript must still be on the cited page.

    The check is deliberately narrow: it only sees numbers that appear *inside*
    the quote, so a manuscript may discuss a number without quoting it.  It
    exists to catch a re-typed statistic, which is the failure mode that reads
    as correct for months.

    A quote that runs onto the next page can carry its numbers on either half,
    so both pages are read.  Checking only the first half would report a number
    absent that the author can see with their own eyes on page 7.
    """
    out: list[Finding] = []
    if not claim.numbers:
        return out
    numbers_pages = [page_number] if spans_to is None else [page_number, spans_to]
    wanted = [n for n in numbers_pages if n is not None]
    present: set[str] = set()
    for candidate in pages:
        if candidate.number in wanted:
            present.update(canonical_number(t) for t in _numbers(candidate.text))
    if not present:
        return out
    for raw in claim.numbers:
        if canonical_number(raw) not in present:
            where = "page " + str(page_number)
            if spans_to is not None:
                where += f" or {spans_to}"
            out.append(
                Finding(
                    code="number-absent-in-quote",
                    message=(
                        f"claim {claim.id}: the quote says {raw} but {where} "
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
