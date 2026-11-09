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

import re
from dataclasses import dataclass, field
from pathlib import Path

from .bibtex import field_findings, parse_bib
from .errors import why_not_a_file
from .manuscript import ParseResult, parse_manuscript, scan_unbound_markers
from .matching import excerpt, find_in_pages
from .model import Finding, Ledger
from .scan import ScanOptions, _no_claim_blocks_finding, _resolve, recorded_path
from .sources import (
    SourceTable,
    explain_unresolved,
    extract_pages,
    page_hint_is_valid,
    read_source_table,
    resolve_source,
    sha256_file,
)
from .textnorm import (
    CANON_PATTERN,
    canonical_number,
    count_of,
    is_are,
    numbers_in,
    read_text,
)


@dataclass
class VerifyResult:
    findings: list[Finding] = field(default_factory=list)
    checked: int = 0
    verified: int = 0
    moved: int = 0
    missing: int = 0
    skipped: int = 0
    # Claim blocks the parser found and refused, so the ledger never recorded
    # them.  This is not a fourth arrow in the tally: the block has no claim to
    # count, which is exactly why it went missing from the line.  It is the
    # difference between "the file holds one claim" and "the file holds two
    # blocks, one of which this run could not check", and only the second
    # sentence is true.  Measured before this field existed, on a manuscript
    # holding one accepted claim and one block with no ``source=``:
    #
    #     citevouch: 1 claim — 1 verified, 0 moved, 0 missing
    #
    # with two blocks in the file and a `[high] claim-uncheckable` line naming
    # the second one.  The run was red, so nothing was hidden *from the exit
    # code*; what was wrong is that the arithmetic sentence described a smaller
    # document than the one that had just been read.
    unrecorded: int = 0

    @property
    def ok(self) -> bool:
        return not any(f.severity == "high" for f in self.findings)

    @property
    def blocks(self) -> int:
        """How many claim blocks the manuscript holds, as the reader sees it.

        ``checked`` counts claims in the ledger; this counts blocks in the
        file.  They differ by exactly ``unrecorded``, because a block the
        parser refused produces a finding instead of a claim.
        """
        return self.checked + self.unrecorded


def _unrecorded(parsed: ParseResult) -> int:
    """How many claim blocks the parser saw but could not record.

    One subtraction for one question, so `scan`, `verify` and the recorded
    paths cannot drift apart: every claim block the parser opened, minus every
    claim it could put in the ledger.  An unclosed fence is not one of these —
    it still yields a claim, which is why it is counted and checked like any
    other.

    ``parsed.claim_spans``, not ``parsed.spans``.  The wider list also holds
    plain code fences, because a `claim` line inside a sample is sample text
    and must not be reported as an unread opener.  Counting those as blocks
    made the summary line say a file held two claim blocks when one of them
    was a````python`` sample, and no finding anywhere explained the extra one,
    because there was no extra one.
    """
    return max(0, len(parsed.claim_spans) - len(parsed.claims))


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
    fresh: bool = False,
) -> VerifyResult:
    """Re-check ``ledger`` against the files currently on disk.

    ``fresh`` says the ledger was built from this exact text moments ago, in
    this same run (the live ``check``).  The refusals then describe a document
    this run has already read, so the block count may be derived from a fresh
    parse - but the findings must not be re-added, because ``scan`` returned
    them a line earlier.
    """
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

    # The ledger records the claims the parser *accepted*.  A block it refused -
    # no `id=`, an id used twice, a fence that is never closed - has no evidence
    # to record, so it is absent from the ledger, and the verification pass
    # below walks the ledger and therefore never learns the block existed.
    #
    # `scan` reports those refusals and exits 1.  `action.yml` runs
    # `check --use-recorded` on every pull request, which is this pass and
    # nothing else.  Measured on a manuscript holding one accepted claim and a
    # second block missing its `id=`:
    #
    #     scan                  -> 1, [high] claim-uncheckable at manuscript.md:9
    #     check --use-recorded  -> 0, [info] quote-found at manuscript.md:3
    #     verify                -> 0
    #
    # A contributor who pastes a second claim block and forgets its `id=` gets a
    # green tick, and the only command that would say otherwise is one the job
    # does not run.
    #
    # Re-deriving the refusals here is sound only when the ledger is known to
    # describe this exact text, which is what the hash comparison above
    # established: the text is byte-identical to the text `scan` parsed, so
    # these are the same findings `scan` produced.  With `--allow-stale` the
    # ledger may be about a different draft, and a finding about a paragraph it
    # never recorded would be a verdict about a document this run has not read.
    parsed = None
    if check_manuscript_hash and ledger.manuscript_sha256:
        try:
            text = read_text(manuscript_path)
        except OSError:
            text = ""
        parsed = parse_manuscript(text, manuscript_path.name)
        result.findings.extend(parsed.findings)
        # A credibility mark - 【原文】 and its siblings - that no claim block
        # covers is the shape this tool exists to catch: the manuscript reads
        # as evidence-backed while nothing on that line can be checked.  `scan`
        # asks `scan_unbound_markers` for it; this pass re-parsed the same bytes
        # and then never asked, so `action.yml` - which runs exactly this
        # command - reported a marked sentence as a green build.  Measured on a
        # manuscript holding a marked sentence and an unrelated claim block:
        #
        #     scan                  -> [low] claim-without-evidence at manuscript.md:1
        #     check --use-recorded  -> [info] quote-found at manuscript.md:3 (c1)
        #
        # The spans and the claims are the parse's own, so a mark that a block
        # covers stays quiet for exactly the reason `scan` keeps it quiet.
        result.findings.extend(
            scan_unbound_markers(
                text,
                path=manuscript_path.name,
                spans=parsed.spans,
                claims=parsed.claims,
            )
        )
        # Blocks the parser found and refused.  A refused block yields a
        # finding and no claim, so it is invisible to the loop below, which
        # walks `ledger.claims`.  Counting the difference here - rather than
        # asking each refusal site to bump a counter - keeps one number for one
        # question: every span the parser could see, minus every claim it could
        # record.  An unclosed fence is not one of these: it still produces a
        # claim, so it is counted and checked like any other.
        result.unrecorded = _unrecorded(parsed)
    elif fresh:
        # The live `check` built this ledger from the text on disk one line
        # earlier, so the parse describes the document this run is reporting
        # on.  Only the count is taken: `scan` already returned the findings,
        # and extending them here would print every refusal twice.
        try:
            fresh_text = read_text(manuscript_path)
        except OSError:
            fresh_text = None
        if fresh_text is not None:
            result.unrecorded = _unrecorded(parse_manuscript(fresh_text, manuscript_path.name))

    # A ledger that recorded no claims is the recording of a run that checked
    # nothing, and reading it back produces the same shape as the manuscript
    # with no claim blocks: `0 claims - 0 verified`, worst `info`, exit 0.  The
    # recording does not make that verdict true - it only means the false green
    # reached disk first.  An empty ledger can also arrive from an older
    # version of this tool, so the guard belongs here and not only in `scan`.
    if not ledger.claims:
        if parsed is None:
            try:
                text = read_text(manuscript_path)
            except OSError:
                text = ""
            parsed = parse_manuscript(text, manuscript_path.name)
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
        elif parsed.nothing_to_check:
            result.findings.append(
                _no_claim_blocks_finding(
                    text,
                    manuscript_path.name,
                    typed=options.manuscript,
                    root=options.root,
                )
            )
        elif parsed is not None and parsed.findings and not result.findings:
            # A block the parser found and refused is not the same thing as a
            # file with no blocks, and `scan` has said so since the emptiness
            # guard was written.  This branch asked the parser only whether it
            # produced claims, so a block missing its `id=` produced zero claims
            # and was then described as "no claim blocks", which is false: the
            # parser's own finding, one screen up, names the block.  Report the
            # reasons the parser gave rather than a summary of the outcome.
            #
            # The findings above are already in `result` when the hash guard
            # could run; the condition keeps this branch for the case where the
            # ledger carried no digest and the parse happened just now.
            result.findings.extend(parsed.findings)
        return result

    table: SourceTable = read_source_table(root, options.sources)
    known = table.found
    pages_cache: dict[str, tuple[list, str]] = {}
    # Sources whose text could not be extracted.  Their claims are skipped
    # rather than searched, because searching no pages can only produce a
    # "quote not found" verdict about a PDF nobody managed to read.
    broken_sources: set[str] = set()
    # `scan` reports what it could not read from a bibliography, and those
    # findings used to live only in that one run's output: the ledger records
    # the *entries*, so a file that yielded none left no trace, and the
    # recorded pass below saw an empty mapping and said nothing at all.
    # Measured on a project whose refs.bib is a binary:
    #
    #     scan                  -> 1, [high] bib-unreadable
    #     check --use-recorded  -> 0, [info] quote-found
    #
    # The findings are re-derived here rather than copied into the ledger,
    # because they describe a file this run can still open.
    #
    # The gate is `fresh`, not the manuscript's digest.  A bibliography that
    # cannot be read is a fact about the bibliography, not about whether the
    # manuscript moved on: `--allow-stale` says "the ledger describes an older
    # draft", and the missing `refs.bib` is missing either way.  The recorded
    # source checks (`source-missing`, `source-changed`) run under
    # `--allow-stale` for the same reason.  `fresh` is the one case that must
    # stay quiet: there `scan` returned these findings a line earlier.
    if not fresh:
        for recorded_bib in ledger.bibliographies:
            bib_path = _resolve(root, recorded_bib)
            if not bib_path.is_file():
                result.findings.append(
                    Finding(
                        code="source-missing",
                        message=f"bib file {bib_path} {why_not_a_file(bib_path)}",
                        path=str(bib_path),
                    )
                )
                continue
            try:
                bib_text = read_text(bib_path)
            except OSError as exc:
                result.findings.append(
                    Finding(
                        code="source-missing",
                        message=f"bib file {bib_path} cannot be read: {exc}",
                        path=str(bib_path),
                    )
                )
                continue
            result.findings.extend(parse_bib(bib_text, recorded_path(root, bib_path)).findings)

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
            # The same table that failed to resolve the key can say why. Saying
            # nothing here was a second opinion about the same project: scan
            # named the manifest entry and the value it held, while this line
            # reported "cannot be found any more" - which is true of the file
            # and silent about the entry the author has to go and edit.
            reason = explain_unresolved(claim.source, table)
            message = (
                f"claim {claim.id} cannot be resolved: {reason}"
                if reason
                else f"claim {claim.id}: source {claim.source!r} cannot be found any more"
            )
            result.findings.append(
                Finding(
                    code="source-missing",
                    message=message,
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
            # The quote is confirmed to be the page's own text here, which is
            # the only point where comparing the claim against it means
            # something: everywhere else the quote itself is in doubt.
            result.findings.extend(_claim_number_checks(claim, pages, match))
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
            # The specific sentence first, because the duplicate pass keeps the
            # first of two findings that share a code and a line.  The summary
            # below says only that some number differs; `_number_checks` names
            # which one, which is the sentence the author can act on.  Emitted
            # last, the summary won and the answer was dropped - measured, this
            # branch printed "the numbers do not" and nothing else.
            specific = _number_checks(claim, pages, match.page)
            result.findings.extend(specific)
            if not specific:
                # Nothing is missing *from the page*, and the old sentence here
                # said so anyway: "the words match page 1 but the numbers do
                # not".  For a quote that swapped a number between two
                # sentences the number is on page 1 - four lines down - so that
                # sentence was false about a page the author can read, which is
                # the one thing this tool must never be.  The tier knows the
                # answer: it matched the text with every number blanked out, so
                # the numbers that fell into those blanks are the page's own.
                result.findings.extend(_number_where_checks(claim, match))
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
                message=f"{count_of(len(unused), 'bibliography entry', 'bibliography entries')}"
                f" {is_are(len(unused))} cited by no claim: {shown}",
            )
        )
    for claim in ledger.claims:
        # Without a bibliography in the ledger there is nothing to be missing
        # from; reporting "key not in the bibliography" then is noise that
        # teaches users to ignore the check.
        if not ledger.entries:
            break
        # The key is looked up in two namespaces: `ref` when the author wrote
        # one, and `source` otherwise, because a project that names its PDF and
        # its bibliography entry the same way should not have to write the key
        # twice.  The fallback decides *what is checked*; it must not decide
        # *what the message calls it*.  Writing `cites 'paper'` for a claim
        # that never mentions a bibliography key tells the author they cited
        # something they did not write, and the fix that sentence invites -
        # adding `paper` to refs.bib - puts the PDF's name in the bibliography.
        # Measured before: `claim c1 cites 'paper', which is not in the
        # bibliography the ledger recorded` for a claim writing `source=paper`
        # and no `ref=`.
        ref_key = claim.ref or claim.source
        if ref_key in ledger.entries:
            continue
        message = (
            f"claim {claim.id} cites {ref_key!r}, which is not in the "
            "bibliography the ledger recorded"
            if claim.ref
            else f"claim {claim.id} names no `ref=`, so it was looked up as "
            f"{ref_key!r} - the name of its source file - and the bibliography "
            "the ledger recorded has no such entry. Write `ref=<key>` for the "
            "entry this quote comes from"
        )
        result.findings.append(
            Finding(
                code="bib-key-missing",
                message=message,
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
            present.update(canonical_number(t) for t in _page_numbers(candidate.text))
    if not present:
        return out
    absent = [raw for raw in claim.numbers if canonical_number(raw) not in present]
    if absent:
        where = "page " + str(page_number)
        if spans_to is not None:
            where += f" or {spans_to}"
        # One claim yields every one of its findings at the claim's own line, so
        # the duplicate pass kept the first wrong number and hid the rest: the
        # author corrected it, ran again, and met the second.  Measured before
        # this: a claim with two wrong numbers gave `raw: 2, dedup: 1`.
        if len(absent) == 1:
            listed = absent[0]
            tail = "that number"
        else:
            listed = ", ".join(absent[:-1]) + f" and {absent[-1]}"
            tail = "those numbers"
        out.append(
            Finding(
                code="number-absent-in-quote",
                message=(
                    f"claim {claim.id}: the quote says {listed} but {where} "
                    f"of the source does not contain {tail}"
                ),
                claim_id=claim.id,
                path=claim.path,
                line=claim.line,
            )
        )
    return out


def _is_year(raw: str) -> bool:
    """Is this number a calendar year rather than a count?

    A claim restating a quote may legitimately name a second work, and two
    different years are almost always one character apart - 2010 and 2011,
    1995 and 1999.  Without this guard the rule accused every such sentence.
    Measured on 174 adjacent real sentences: one-keystroke differences fired on
    38.5% of them, and every single flag was a year or a small integer.
    """
    digits = re.sub(r"\D", "", raw)
    return len(digits) == 4 and 1500 <= int(digits) <= 2100


def _is_quantity(raw: str) -> bool:
    """Is this number written the way a copied count is written?

    Separators, decimals and percent signs are how a quantity that somebody
    types from a page appears; `1`, `2`, `4` are ordinals and section numbers,
    and they are one keystroke apart from each other constantly.
    """
    return (
        any(mark in raw for mark in (",", ".", "\u00a0", "\u066c", "\u066b", " ")) or "%" in raw
    )


def _near_miss(a: str, b: str) -> bool:
    """Are two numbers one keystroke apart?

    Same length and exactly one character different, which is the shape of a
    number typed from memory: 80,688 where the page says 40,688.  Anything
    looser reports numbers that are merely different - a year the author
    supplied, a total they derived - and this project does not accuse an
    author of an error it cannot point at.
    """
    if len(a) != len(b):
        return False
    # strict=False is safe here because the lengths are equal one line above,
    # and saying so keeps the linter reading the guard rather than guessing.
    return sum(x != y for x, y in zip(a, b, strict=False)) == 1


def _claim_number_checks(claim, pages=None, match=None) -> list[Finding]:
    """Numbers the claim states but the quote spells differently.

    A claim restates its quote in the author's own words, and the commonest
    way that goes wrong is a digit: the quote says 40,688 and the claim, typed
    later, says 80,688.  Nothing compared the two - ``claim.numbers`` holds
    the quote's numbers, because those are what the page has to contain, so a
    claim could disagree with its own quote and still verify.

    The rule is deliberately narrow, because the cost of a false accusation is
    higher than the cost of a miss: failing a correct claim teaches the author
    to stop reading the report.  A number is reported only when all of these
    hold.

    * It is one keystroke from a number in the quote.
    * Both numbers carry at least three digits, neither is a year, and at
      least one is written as a quantity (separator, decimal, percent).  This
      is what separates a copied count from a year the author added or an
      ordinal; measured on 788 adjacent real sentences, the version without
      these guards flagged 38.5% of them, all of it noise.
    * The page does not print it anywhere.  A claim may describe a different
      fact that the same page states elsewhere - ``10,000`` beside a quote
      saying ``50,000`` was flagged until the page was asked - and if the
      number is on the page, the author read it somewhere.

    The last guard needs the pages, so it only applies when they are given;
    the unit tests that check the wording pass them.
    """
    quote_numbers = [(canonical_number(n), n) for n in claim.numbers]
    if not quote_numbers:
        return []
    on_page: set[str] | None = None
    if pages is not None:
        wanted = {match.page} if match is not None and match.page else set()
        on_page = set()
        for page in pages:
            if wanted and page.number not in wanted:
                continue
            on_page.update(canonical_number(n) for n in _page_numbers(page.text))
    slips: list[tuple[str, str]] = []
    for stated in numbers_in(claim.text):
        mine = canonical_number(stated)
        if any(mine == canon for canon, _ in quote_numbers):
            continue
        if on_page is not None and mine in on_page:
            continue
        # The guards below are about the *pair*, not about the claim's number
        # taken alone: `48.5%` is a quantity even when the quote's `40,688` is
        # the one being compared, and the two must be judged together or the
        # rule lets in exactly the short integers it was written to exclude.
        for canon, raw in quote_numbers:
            if not _near_miss(mine, canon):
                continue
            # The length guard looks redundant and is not.  Exhaustively
            # enumerating the spellings the number grammar can produce
            # (650,806 of them) leaves exactly one quantity whose canonical
            # form is shorter than three characters: `1%`, which canonicalises
            # to `1`.  So `1%` against `2%` passes every other guard, and this
            # line is the only thing that refuses it - a single-digit percent
            # is far likelier to be two different measurements than a typo.
            # Without the guard that pair is reported; measured, see
            # tests/test_claim_numbers.py.
            if len(canon) < 3 or _is_year(raw) or _is_year(stated):
                continue
            if not (_is_quantity(stated) or _is_quantity(raw)):
                continue
            # Report the quote's own spelling: the author is going to look
            # the number up, and `40,688` is what the page prints while
            # `40688` is only what the comparison uses.
            slips.append((stated, raw))
            break
    if not slips:
        return []
    said = " and ".join(mine for mine, _ in slips)
    printed = " and ".join(theirs for _, theirs in slips)
    return [
        Finding(
            code="claim-number-differs",
            message=(
                f"claim {claim.id}: the claim says {said} but its quote says "
                f"{printed}; a restatement with a different digit was typed from "
                "memory, not copied"
            ),
            claim_id=claim.id,
            path=claim.path,
            line=claim.line,
        )
    ]


def _number_where_checks(claim, match) -> list[Finding]:
    """Numbers that are on the page, but not in the passage the quote names.

    The ``numbers`` tier matched the quote with every number blanked out, so
    the numbers that filled those blanks are the page's own numbers at exactly
    the positions the quote fills with its own.  Comparing the two lists is a
    fact the page states directly; asking "does 9,800 appear anywhere on page
    1" is not, and answering it "yes" is what produced this function.

    A quote that swaps a number between two sentences used to reach the summary
    and be told "the words match page 1 but the numbers do not" - about a
    number printed four lines further down the same page.  That sentence is
    false about a page the author can read, which is the one thing this tool
    must never be, so the two situations get two codes: ``number-absent-in-
    quote`` when the page has no such number at all, and this one when it has
    it somewhere else.
    """
    if not claim.numbers or not match.page_numbers:
        return []
    pairs = [
        (mine, theirs)
        # strict=False on purpose: `claim.numbers` comes from REPORT_PATTERN
        # and `match.page_numbers` from MASK_PATTERN, and the two disagree
        # about whether a bare space groups thousands.  When they do, the
        # shorter list wins and the numbers past its end are simply not
        # compared - the honest answer for a position the page's own text
        # cannot be aligned to.
        for mine, theirs in zip(claim.numbers, match.page_numbers, strict=False)
        if canonical_number(mine) != canonical_number(theirs)
    ]
    if not pairs:
        return []
    said = " and ".join(mine for mine, _ in pairs)
    printed = " and ".join(theirs for _, theirs in pairs)
    if len(pairs) == 1:
        # One number, one sentence: naming the passage is the whole message.
        # The count is only worth printing when it is not one, which is why it
        # lives inside this branch instead of trailing every message.
        tail = "that number is on the page, but not in this passage"
    else:
        tail = (
            f"those {len(pairs)} numbers are on the page, but not in this passage "
            f"({count_of(len(pairs), 'number')} differ)"
        )
    return [
        Finding(
            code="number-not-in-passage",
            message=(
                f"claim {claim.id}: the quote says {said} where page {match.page} "
                f"prints {printed}; {tail}"
            ),
            claim_id=claim.id,
            path=claim.path,
            line=claim.line,
        )
    ]


def _page_numbers(text: str) -> tuple[str, ...]:
    """Every number a page prints, with grouped digits read as one number.

    ``numbers_in`` is the report pattern, and it refuses a bare space between
    digit triples on purpose - "2019 2020 2021" is three years.  A page,
    though, prints ``40 688`` for forty thousand because that is its house
    style, and comparing a quote's ``40,688`` against that page by the report
    pattern alone says the page does not contain the number.  Measured: a page
    printing ``40 688`` and a quote typing ``40,688`` produced
    ``number-absent-in-quote`` about a figure the reader can see with their own
    eyes.

    ``CANON_PATTERN`` accepts a space only as a thousands group - one to three
    digits, then exactly three - so a year still cannot start one, and this
    agrees with the answer the canonical tier gives.
    """
    return tuple(match.group(0) for match in CANON_PATTERN.finditer(text))
