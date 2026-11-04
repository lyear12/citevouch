"""Manuscript parsing: find evidence-bearing claims in a Markdown manuscript.

The input dialect is small and explicit on purpose.  A claim is a fenced block
that names its source and carries the verbatim quote:

    ```claim id=c1 source=vaneecke2026cxn page=214
    quote: |
      We train on OntoNotes and the English Web Treebank.
    claim: |
      The grammar is learned from two semantically annotated corpora.
    ```

Anything outside such a block is prose and is only scanned for *unbound*
markers (see :func:`scan_unbound_markers`), which is how the tool can point at
a sentence that claims something without carrying its evidence.

Two lighter forms are accepted because real manuscripts already look like this:

    <!-- claim: c1 source=vaneecke2026cxn page=214
         The grammar is learned from two semantically annotated corpora.
         >> We train on OntoNotes and the English Web Treebank.
    -->

and a table row:

    | c1 | vaneecke2026cxn | 214 | We train on OntoNotes ... | The grammar is learned ... |

All three produce the same :class:`~citevouch.model.Claim`.  A parser that
silently drops malformed blocks would be worse than useless, so every failure
becomes a :class:`~citevouch.model.Finding` instead.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .model import Claim, Finding, fingerprint
from .textnorm import CANON_PATTERN

_FENCE_OPEN = re.compile(r"^```claim\b(?P<attrs>.*)$")
_FENCE_CLOSE = re.compile(r"^```\s*$")
_ANY_FENCE = re.compile(r"^(?P<ticks>`{3,}|~{3,})(?P<info>.*)$")
_HTML_OPEN = re.compile(r"^<!--\s*claim\s*:?\s*(?P<attrs>.*)$")
_HTML_CLOSE = re.compile(r"^\s*-->\s*$")
# A cell ends at an unescaped `|`.  `\|` is the only way GFM lets a pipe sit
# inside a cell, so it has to be one token here; `[^|]+?` read it as a cell
# break and an author who escaped correctly got their quote cut at the
# backslash, with the remainder installed as the `text` column:
#
#     | c1 | paper | 1 | a\|b | t |   ->  quote 'a\', text 'b'
#
# A cell may be empty.  `+?` refused a row whose `text` or `claim` column was
# left blank, and a manuscript holding one such row reported
# `no-claim-blocks ... This file has none` - over a file that had one.  An
# empty quote or an empty source is not a parse failure either: it is a claim
# the author has not finished, and `claim-uncheckable` names it.
# The unescaping is `_unescape_pipe`, applied where the columns are read.
_CELL = r"(?:[^|\\]|\\.)*?"
_TABLE_CLAIM = re.compile(
    r"^\|\s*(?P<id>[A-Za-z0-9_.:-]+)\s*\|\s*(?P<source>" + _CELL + r")\s*\|"
    r"\s*(?P<page>\d+|-)\s*\|\s*(?P<quote>" + _CELL + r")\s*\|"
    r"\s*(?P<text>" + _CELL + r")\s*\|"
)
# What a cell's text is once the cell boundary has been found: the only escape
# GFM defines inside a table is the pipe, and it means the pipe.


def _unescape_pipe(cell: str) -> str:
    """A cell's text once its boundaries are found: `\\|` is the pipe.

    The only escape GFM defines inside a table cell is the pipe, and it means
    the pipe.  Every other backslash stays as written, because a quote may well
    contain one (a Windows path, a LaTeX-ish escape) and rewriting it would be
    editing the author's text rather than reading it.
    """
    return cell.replace("\\|", "|")


# ``value`` comes in two forms, and the difference is the space after ``=``.
#
#   * ``key=value``  - no space, so the token is the value outright, even when
#     the value itself contains ``=`` (``source=a=b`` is the key ``a=b``).
#   * ``key = value`` - space, so a following ``something=`` is the next
#     attribute and not this one's value.  ``source= page=1`` therefore reads as
#     an empty ``source`` plus a separate ``page``, which is the author saying
#     "this key is not finished yet" and earns `claim-uncheckable`.
#
# Without that split the greedy third form swallowed the neighbour: an empty
# ``source=`` took ``page=1`` as its value and the report complained about a key
# nobody had typed.  Values that are themselves ``a=b`` are still written the
# way every other value is: in quotes, or with no space after ``=``.
_ATTR = re.compile(
    r"(?P<tight>[A-Za-z_][A-Za-z0-9_-]*)=(?P<tvalue>\"[^\"]*\"|'[^']*'|\S+)"
    r"|(?P<loose>[A-Za-z_][A-Za-z0-9_-]*)\s*=\s*"
    r"(?P<lvalue>\"[^\"]*\"|'[^']*'|(?![A-Za-z_][A-Za-z0-9_-]*\s*=)\S+)"
)
# A line a human would read as "here begins a claim block", in any of the
# spellings close enough to the real one to be a mistake rather than prose.
# Used only to explain a file that yielded no claims: naming the line that was
# almost right is the difference between "the tool is broken" and "look at line
# 12".  Deliberately permissive - it is a hint generator, never a gate.
_CLAIMISH = re.compile(r"^\s*(?:`{3,}|~{3,}|<!--)\s*[*_]*\s*claim\b", re.IGNORECASE)
# What a line can put in front of a fence without being a comment: a blockquote
# marker, a bullet, a number, an indent, and any mix of them.
_CONTAINER = r"(?:(?:[ \t]*>[ \t]*)|(?:[ \t]*[-*+][ \t]+)|(?:[ \t]*\d+[.)][ \t]+)|(?:[ \t]+))*"
# The openers themselves, with no opinion about what precedes them.  One per
# dialect, because the three dialects are spelled differently and the finding
# has to name the construct the reader actually wrote.
_BARE_CLAIM = re.compile(r"(?:`{3,}|~{3,})\s*[*_]*\s*claim\b", re.IGNORECASE)
_BARE_COMMENT = re.compile(r"<!--\s*claim\s*:?", re.IGNORECASE)
# The table opener is `_TABLE_CLAIM` itself, with its left-margin anchor
# removed.  Reusing the pattern rather than retyping it is the point: a second
# copy of a shape is a second copy that drifts, and the parser and this
# detector must agree about what a claim row is.
_BARE_TABLE = re.compile(_TABLE_CLAIM.pattern[1:])
# A claim fence a container or an indent put out of reach of `_FENCE_OPEN`,
# which only matches at the left margin.  Such a block is not a claim - Markdown
# renders the fence as a code sample wherever it sits - but it is also not
# prose, and staying quiet about it is the one answer that is definitely wrong.
#
# Measured before `claim-block-unread` existed: a manuscript holding one good
# block and one blockquoted block gave `scan` exit 0 with "wrote
# citevouch.lock.json (1 claim)", `check` "1 claim - 1 verified, 0 moved, 0
# missing" and exit 0, and `doctor` two green ticks.  The second block's id
# appeared in no finding and in no ledger row.  The near-miss sentence in
# `scan._no_claim_blocks_finding` names the indented shape correctly, but only
# for a file that produced *zero* claims, so one good block anywhere switched
# it off.
# Each dialect's opener, reachable through the same prefix grammar.
_WRAPPED: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("fence", re.compile(_CONTAINER + _BARE_CLAIM.pattern, re.IGNORECASE)),
    ("comment", re.compile(_CONTAINER + _BARE_COMMENT.pattern, re.IGNORECASE)),
    ("table", re.compile(_CONTAINER + _BARE_TABLE.pattern)),
)
# The two keys that make a body a mapping, and the only two the parser reads a
# value out of.  `numbers:` used to be a third, listed here from the first
# commit although `_claim_from` builds `Claim.numbers` from the quote's own
# digits with `CANON_PATTERN` and never looked at a field.  Because membership
# of this set is also what
# decides "is this body a mapping at all", the dead key cost more than itself:
# a correctly written `>> the quote` followed by `numbers: 1` was read as a
# mapping with no quote in it, and came back as `claim-uncheckable` - silent
# data loss for a block that had done nothing wrong.  Measured before the fix:
# `['>> We collected 40,688 examples.', 'numbers: 1']` -> `('', '', {})`, where
# the same body without the second line gave `('We collected 40,688 examples.',
# '', {})`.  So this set is now exactly `quote` and `claim`: what decides the
# shape is what the shape is for.
_FIELD_KEY = re.compile(r"^\s*(?P<key>quote|claim)\s*:\s*(?P<rest>.*)$")

# Inside a mapping, a `numbers:` line is a sibling key in YAML terms - it really
# does end the quote above it - so it must be consumed there rather than glued
# onto the quote.  Its value is still dropped, because this tool derives the
# numbers from the quote itself; honouring a hand-written list would mean
# deciding what it means when the two disagree, which is a format change.
_BODY_KEY = re.compile(r"^\s*(?P<key>quote|claim|numbers?)\s*:\s*(?P<rest>.*)$")

# The keys a claim may name as attributes.  They are read from the opening line
# (``​```claim id=c1 source=paper``) and, since the fix below, also from the body.
_ATTRIBUTE_KEY = re.compile(r"^\s*(?P<key>id|source|ref|cite|page|marker)\s*:\s*(?P<rest>.*)$")

# The credibility markers the surrounding workflow already uses.  Kept as data
# rather than hard-coded checks so a project can rename them.
# A line that is shaped like a field but names a key this format does not have.
#
# In a `quote: |` block a line at the left margin is a sibling key in YAML
# terms, so it is never continuation text - but only a key this format knows
# was consumed, and every other one took one of two silent paths.  Measured on
# a project whose quote really is on page 2, with the page hint misspelt:
#
#     Page: 1 above `quote:`  -> the hint was dropped, exit 0, no finding
#     Page: 1 below `quote:`  -> it joined the quote, and the run printed
#                                [high] quote-missing "…constructions. Page: 1"
#
# One spelling switched a check off without saying so; the other accused the
# author of quoting a page their source never printed.
_KEYISH = re.compile(r"^\s*(?P<key>[A-Za-z][A-Za-z0-9_-]*)\s*:")

DEFAULT_MARKERS = ("【原文】", "【实测】", "【推测】", "[原文]", "[实测]", "[推测]")


@dataclass
class ParseResult:
    claims: list[Claim]
    findings: list[Finding]
    # 1-based inclusive line spans that belong to a claim block.  Prose checks
    # use them to avoid re-reporting what the block already documents.
    spans: list[tuple[int, int]] = field(default_factory=list)

    @property
    def nothing_to_check(self) -> bool:
        """Whether this parse means the run checked nothing at all.

        A file with no blocks and a file whose only block the parser refused are
        different mistakes, but they have the same consequence: zero claims were
        checked.  The refused block already carries its own finding (a missing
        ``id=``, an unclosed fence), so the reader is told why; a file with no
        blocks at all carries none and needs the ``no-claim-blocks`` sentence
        instead.

        This condition lived as the same expression typed out in two modules -
        ``scan.py`` and ``verify.py`` - which is how a third reader, ``doctor``,
        came to be written without it and to report an empty manuscript as a
        project with nothing wrong.
        """
        return not self.claims and not any(f.code.startswith("claim-") for f in self.findings)


def _unquote(value: str) -> str:
    """Drop one pair of YAML quote marks, but only when they really are a pair.

    A writer who puts the passage in quotes - ``quote: "the sentence"`` - means
    the same value as the bare form, and the marks must not travel into the
    search.  They also must not be removed when they are *content*:
    ``"yes" or "no"`` begins and ends with the same character and is not a
    quoted scalar, so a rule that only compared the ends would silently eat one
    quote mark off each end and search for a quote nobody wrote.  Requiring the
    mark to be absent from the inside keeps this from being wrong; it can only
    fail to strip, and the full value is still searchable as written.
    """
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        inner = value[1:-1]
        if value[0] not in inner:
            return inner
    return value


def _attrs(blob: str) -> dict[str, str]:
    """Parse ``key=value`` attributes; a leading bare token becomes ``id``.

    ``<!-- claim: c1 source=x -->`` is common enough that refusing to read the
    positional id would reject the manuscripts this tool exists to help.
    """
    out: dict[str, str] = {}
    for m in _ATTR.finditer(blob or ""):
        key = m.group("tight") or m.group("loose")
        value = m.group("tvalue") or m.group("lvalue")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        out[key.lower()] = value
    if "id" not in out:
        head = (blob or "").strip().split()
        if head and "=" not in head[0] and head[0] not in (":", "-"):
            token = head[0].lstrip(":")
            if token:
                out["id"] = token
    return out


def _claim_from(
    attrs: dict[str, str],
    quote: str,
    text: str,
    path: str,
    line: int,
    body: dict[str, str] | None = None,
) -> tuple[Claim | None, list[Finding]]:
    """Build the claim, letting the body's attribute lines fill in what is absent.

    ``attrs`` comes from the opening line and wins when both name the same key:
    the fence is where the format is documented, and a reader who wrote it in
    both places meant the one next to ``claim``.
    """
    if body:
        merged = dict(body)
        merged.update(attrs)
        attrs = merged
    findings: list[Finding] = []
    cid = attrs.get("id", "")
    if not cid:
        findings.append(
            Finding(
                code="claim-uncheckable",
                message="claim block has no id= attribute; give it a stable id so the ledger can track it",
                path=path,
                line=line,
            )
        )
        return None, findings
    source = attrs.get("source", "")
    if not source:
        findings.append(
            Finding(
                code="claim-uncheckable",
                message=f"claim {cid} names no source=; the quote cannot be looked up",
                claim_id=cid,
                path=path,
                line=line,
            )
        )
        return None, findings
    quote = quote.strip()
    if not quote:
        findings.append(
            Finding(
                code="claim-uncheckable",
                message=f"claim {cid} carries no verbatim quote; nothing can be verified",
                claim_id=cid,
                path=path,
                line=line,
            )
        )
        return None, findings
    page = None
    raw_page = attrs.get("page", "")
    # `-` is the table dialect's spelling of "no page hint"; list it here so it
    # never reaches the int() below and comes back as a mistake the author did
    # not make.
    if raw_page.strip() == "-":
        raw_page = ""
    if raw_page:
        try:
            page = int(raw_page)
        except ValueError:
            # Not claim-uncheckable: the quote is still located by search, so
            # the claim is verified either way. It is reported because the hint
            # the author wrote is being ignored, and silently ignoring an
            # instruction someone typed is how they come to believe it worked.
            findings.append(
                Finding(
                    code="page-unreadable",
                    message=(
                        f"claim {cid} has a non-numeric page={raw_page!r}; the hint is "
                        "ignored and the quote will be located by search"
                    ),
                    claim_id=cid,
                    path=path,
                    line=line,
                )
            )
    claim = Claim(
        id=cid,
        text=text.strip(),
        source=source,
        quote=quote,
        page=page,
        path=path,
        line=line,
        marker=attrs.get("marker", ""),
        ref=attrs.get("ref", attrs.get("cite", "")),
        # ``CANON_PATTERN``, not ``numbers_in``: a quote is the author's
        # transcription of a sentence, so ``40 688`` typed from a page that
        # prints a grouping space is one number.  The report pattern refuses a
        # bare space on purpose - "2019 2020 2021" is three years - and that
        # rule still holds here, because a group needs one to three digits on
        # the left and exactly three on the right.  Measured before this: a
        # quote typing ``40,688`` against a page printing ``40 688`` was split
        # into ``40`` and ``688`` and both were reported absent from a page
        # that prints the number.
        numbers=tuple(m.group(0) for m in CANON_PATTERN.finditer(quote)),
        quote_fingerprint=fingerprint(quote),
    )
    return claim, findings


def _closes(line: str, ticks: str) -> bool:
    """True when ``line`` closes a fence opened with the run in ``ticks``.

    A fence closes only on a line holding at least as many fence characters
    with nothing after them - the CommonMark rule, and the reason four
    backticks can wrap a sample that itself contains ``` lines. A tilde fence
    is closed by tildes only: the two characters are not interchangeable, and
    treating them as such would let a ``~~~`` block open and a ``` block close.

    ``~~~`` matters because it is the other CommonMark fence and authors use it
    precisely when a sample contains backticks. Ignoring it meant a claim
    written inside a tilde-fenced sample was read as a real claim and reported
    ``quote-found`` - a verified verdict on a specimen that was never meant to
    be checked.
    """
    m = _ANY_FENCE.match(line)
    if not m:
        return False
    run = m.group("ticks")
    return run[0] == ticks[0] and len(run) >= len(ticks) and not m.group("info").strip()


def _unclosed_finding(
    start_line: int,
    opener: str,
    consequence: str,
    path: str,
    claim_id: str = "",
) -> Finding:
    """One shape for "this block never ended", so all three dialects agree.

    ``claim-block-unclosed`` used to be raised only for ```claim fences, which
    made it the one unclosed case that was reported. A ```python block or an
    HTML ``<!-- claim`` without its closer swallowed the rest of the file just
    as quietly, and the run then printed "0 claims" and exited 0 - a green
    verdict over a manuscript whose claim was never read.
    """
    who = f"claim {claim_id}: " if claim_id else ""
    return Finding(
        code="claim-block-unclosed",
        message=(
            f"{who}the {opener} fence opened on line {start_line} is never closed; "
            f"{consequence}"
        ),
        claim_id=claim_id,
        path=path,
        line=start_line,
    )


def _continues_one_line_html(line: str) -> bool:
    """True while ``line`` still belongs to an already-closed ``<!-- claim``.

    The one-line dialect has no terminator of its own, so the block ends the
    way a Markdown paragraph does: at a blank line, or where the next construct
    starts. Erring short here would silently drop the quote; erring long would
    swallow a following claim, so every opener counts as a boundary.
    """
    if not line.strip():
        return False
    if _ANY_FENCE.match(line) or _HTML_OPEN.match(line) or _TABLE_CLAIM.match(line):
        return False
    stripped = line.strip()
    return not stripped.startswith("<!--") and not _HTML_CLOSE.match(line)


def parse_manuscript(text: str, path: str = "manuscript.md") -> ParseResult:
    """Extract every claim block from ``text``.

    Line numbers in findings are 1-based and point at the opening delimiter,
    because that is what an editor's "go to line" does with them.
    """
    claims: list[Claim] = []
    findings: list[Finding] = []
    spans: list[tuple[int, int]] = []
    seen: dict[str, int] = {}
    lines = text.splitlines()

    def accept(claim: Claim | None, more: list[Finding], first: int, last: int) -> None:
        findings.extend(more)
        spans.append((first, last))
        if claim is None:
            return
        if claim.id in seen:
            findings.append(_duplicate_finding(claim, seen, path))
            return
        seen[claim.id] = claim.line
        claims.append(claim)

    i = 0
    while i < len(lines):
        line = lines[i]
        start_line = i + 1

        m = _FENCE_OPEN.match(line)
        if m:
            attrs = _attrs(m.group("attrs"))
            body: list[str] = []
            j = i + 1
            nested_at: int | None = None
            while j < len(lines) and not _FENCE_CLOSE.match(lines[j]):
                if _FENCE_OPEN.match(lines[j]):
                    # A second ```claim line inside this block. Two claim blocks
                    # written back to back with the first closer missing look
                    # exactly like this: the closer the author meant for the
                    # first block is the second block's opener, so the scan
                    # above runs past it and eats the second block's head and
                    # quote into the first block's quote.
                    #
                    # Measured before this split, on a project where both
                    # sentences are on page 1:
                    #
                    #     scan  -> exit 0, "wrote citevouch.lock.json (1 claim)"
                    #     check -> exit 1, [high] quote-missing at :3
                    #              "…sentences ```claim id=c2 sourc… - quote not
                    #               in paper.txt"
                    #
                    # `id=c2` was in the report nowhere and in the ledger
                    # nowhere: the author wrote two claims and one stopped
                    # existing. The one line they got sent them to compare a
                    # quote they never wrote against the PDF.
                    #
                    # Splitting is the reading that loses nothing - both blocks
                    # become claims, and the missing fence is said out loud
                    # below - so split, at the line where it happened.
                    nested_at = j + 1
                    break
                body.append(lines[j])
                j += 1
            closed = j < len(lines) and nested_at is None
            quote, claim_text, in_body, unknown = _split_body(body)
            claim, more = _claim_from(attrs, quote, claim_text, path, start_line, in_body)
            more.extend(_unknown_field_findings(unknown, path, start_line))
            if nested_at is not None:
                more.append(
                    _unclosed_finding(
                        start_line,
                        "```claim",
                        f"a second claim fence on line {nested_at} was read as part of "
                        "this quote; the closing fence is missing - add it, and check "
                        "that both blocks are the claims you meant",
                        path,
                        claim.id if claim is not None else "",
                    )
                )
            if not closed and claim is not None:
                # Everything after this point was read as part of this block, so
                # every later claim in the file is invisible. That is data loss,
                # and it used to be silent: the one claim we did read then failed
                # as `quote-missing`, sending the author to check a PDF instead of
                # the fence. Say the true thing, at the line where it happened.
                more.append(
                    _unclosed_finding(
                        start_line,
                        "```claim",
                        "every claim after it was read as part of this block; add the closing "
                        "fence, or fence the sample with four backticks",
                        path,
                        claim.id,
                    )
                )
            accept(claim, more, start_line, j + 1)
            # Resume at the nested opener so its own claim block is read next;
            # a block that ran to end of file skips past `j`, which is
            # ``len(lines)`` and ends the loop either way.
            i = j + 1 if closed else j
            continue

        opener = _ANY_FENCE.match(line)
        if opener:
            # Some other fenced block: skip it wholesale so prose inside a code
            # sample is never mistaken for a claim.
            #
            # Skipping it silently is only correct when it really is a code
            # sample. Two inputs look identical here and are not: a sample that
            # contains a ```claim line on purpose (correct to ignore), and an
            # author who forgot the closing fence, so their first claim opened
            # inside the code block and the rest of the file was read as code
            # (data loss, reported as "0 claims" and a green exit).
            #
            # The two are told apart by what comes after: a genuine sample
            # closes and parsing resumes; a forgotten closer either never closes,
            # or is closed by the claim's own closing fence, which is to say the
            # swallow ends exactly at a line that was meant to end a claim.
            ticks = opener.group("ticks")
            j = i + 1
            while j < len(lines) and not _closes(lines[j], ticks):
                j += 1
            swallowed = [
                k + 1 for k in range(i + 1, min(j, len(lines))) if _FENCE_OPEN.match(lines[k])
            ]
            # Two questions, and they have different answers.
            #
            # "Did this fence ever close?" A fence that does not close ate the
            # rest of the file, and that is data loss whatever the fence was
            # made of - so an unclosed run is always reported.
            #
            # "Was the ```claim inside it literal sample text?" A three-backtick
            # or three-tilde sample can be closed by the claim's own closing
            # fence, which makes "sample" and "forgotten closer" really look the
            # same. A longer run (~4+), or a tilde fence wrapping backticks,
            # closes on its own terminator only, so the nesting is unambiguous
            # and the run stays silent.
            ambiguous = len(ticks) == 3 and ticks[0] == "`"
            if j >= len(lines):
                findings.append(
                    _unclosed_finding(
                        start_line,
                        ticks,
                        "every claim after it was read as part of the code sample; "
                        "if this was meant to be a sample, fence it with four backticks",
                        path,
                    )
                )
            elif swallowed and ambiguous:
                findings.append(
                    _unclosed_finding(
                        start_line,
                        ticks,
                        "the claim block opened on line "
                        f"{swallowed[0]} was read as part of the code sample, "
                        "so it was never checked; the sample is probably missing "
                        "its closing fence (a sample meant to show ```claim needs "
                        "four backticks, not three)",
                        path,
                    )
                )
            spans.append((start_line, j + 1))
            i = j + 1
            continue

        m = _HTML_OPEN.match(line)
        if m:
            attrs_text = m.group("attrs")
            inline_close = "-->" in attrs_text
            if inline_close:
                # The one-line form, which is the shape both READMEs show:
                #
                #     <!-- claim: c2 source=x page=4 -->
                #     >> The quote this backs.
                #
                # It used to be skipped outright - the branch required that the
                # line carry no `-->` - so an author who copied the documented
                # example got zero claims, "worst severity: info" and exit 0.
                # A documented form that parses to nothing is a false negative
                # over the exact sentence the author asked to be checked.
                head, _, tail = attrs_text.partition("-->")
                attrs = _attrs(head)
                body = [tail.strip()] if tail.strip() else []
                j = i + 1
                while j < len(lines) and _continues_one_line_html(lines[j]):
                    body.append(lines[j])
                    j += 1
                closed = True
            else:
                attrs = _attrs(attrs_text)
                body = []
                j = i + 1
                while j < len(lines) and not _HTML_CLOSE.match(lines[j]):
                    body.append(lines[j])
                    j += 1
                closed = j < len(lines)
            quote, claim_text, in_body, unknown = _split_body(body)
            claim, more = _claim_from(attrs, quote, claim_text, path, start_line, in_body)
            more.extend(_unknown_field_findings(unknown, path, start_line))
            if not closed and claim is not None:
                more.append(
                    _unclosed_finding(
                        start_line,
                        "<!-- claim",
                        "every claim after it was read as part of this block; add the closing "
                        "fence, or fence the sample with four backticks",
                        path,
                        claim.id,
                    )
                )
            accept(claim, more, start_line, j + 1 if not inline_close else j)
            i = j if inline_close else j + 1
            continue

        m = _TABLE_CLAIM.match(line)
        if m:
            attrs = {
                "id": m.group("id"),
                "source": _unescape_pipe(m.group("source")),
                "page": m.group("page"),
            }
            claim, more = _claim_from(
                attrs,
                _unescape_pipe(m.group("quote")),
                _unescape_pipe(m.group("text")),
                path,
                start_line,
            )
            accept(claim, more, start_line, start_line)
            i += 1
            continue

        i += 1

    if claims:
        findings.extend(_unread_findings(lines, spans, path))
    return ParseResult(claims=claims, findings=findings, spans=spans)


def _unread_findings(
    lines: list[str], spans: list[tuple[int, int]], path: str
) -> list[Finding]:
    """Name every claim fence the parser walked past without reading.

    ``claims`` being non-empty is the condition, not a detail.  A file that
    produced no claims at all is already refused loudly - ``scan`` names the
    nearest near miss and says what a claim fence looks like - so a second
    finding would be the same fact in a second vocabulary.  The silence only
    exists where a run *succeeded*: one good block is enough to make every
    other block invisible, and the author is told the run verified their
    claims when it verified some of them.

    A line inside a span is not a skipped block.  Spans cover accepted blocks
    (whose quotes may legitimately mention a fence) and code samples (where a
    ``claim`` line is sample text on purpose), and neither is a claim the
    parser failed to read.
    """
    covered = [False] * (len(lines) + 1)
    for first, last in spans:
        for number in range(max(1, first), min(len(lines), last) + 1):
            covered[number] = True
    found: list[Finding] = []
    for number, line in enumerate(lines, start=1):
        if covered[number]:
            continue
        hit = _unread_opener(line)
        if hit is None:
            continue
        dialect, opener = hit
        # The id is on the line the author wrote, so name it.  A finding that
        # says "line 8" makes the reader count; one that says "claim c2 at
        # line 8" matches the block they are looking for.
        claim_id = _id_from_opener(dialect, line, opener)
        who = f"claim {claim_id}: " if claim_id else ""
        found.append(
            Finding(
                code="claim-block-unread",
                message=(
                    f"{who}line {number} opens a claim block that was not read: "
                    + _UNREAD_REASON[dialect]
                ),
                claim_id=claim_id,
                path=path,
                line=number,
            )
        )
    return found


# Why each dialect was not read, and what to do about it.  The three are one
# defect with three different fixes, so they cannot share one sentence: a fence
# and a table row are moved left, a comment opener has to carry its `<!--` to
# the margin as well, and a reader who pasted a row of pipes should be told
# about pipes rather than about fences.
_UNREAD_REASON = {
    "fence": (
        "the fence is inside a blockquote, a list item or an indent, and a "
        "fence that is not at the left margin is a code sample in Markdown, "
        "not a claim - move it to the left margin to have it checked"
    ),
    "comment": (
        "the `<!-- claim` opener is inside a blockquote, a list item or an "
        "indent, where Markdown renders the block as a code sample rather than "
        "a comment - move the opening line to the left margin to have it "
        "checked"
    ),
    "table": (
        "the table row is inside a blockquote, a list item or an indent, where "
        "Markdown renders it as a code sample rather than a table - move it to "
        "the left margin to have it checked"
    ),
}


def _unread_opener(line: str) -> tuple[str, re.Match[str]] | None:
    """Which dialect this line opens a block with, if any.

    The dialect comes back with the match because the three openers keep their
    id in different places: a fence and a comment carry it as an attribute
    after the opener, a table row carries it in its first cell.
    """
    for dialect, pattern in _WRAPPED:
        m = pattern.match(line)
        if m:
            return dialect, m
    return None


def _id_from_opener(dialect: str, line: str, opener: re.Match[str]) -> str:
    """The id the author wrote on that line, so the finding can name it."""
    if dialect == "table":
        return opener.group("id") or ""
    return _attrs(line[opener.end() :]).get("id", "")


def _split_body(
    body: list[str],
) -> tuple[str, str, dict[str, str], list[tuple[int, str]]]:
    """Split a claim body into (quote, claim, attributes, field lines we did not know).

    Accepts several shapes, tried in order of explicitness:

    * ``quote:`` / ``claim:`` keys, either value possibly a ``|`` block;
    * a line beginning with ``>>`` for the quote and the rest for the claim;
    * the first paragraph as quote, the second as claim;
    * everything as the quote, with an empty claim (still verifiable).

    The third return value holds ``id:``/``source:``/``ref:``/``page:`` lines,
    which used to be appended to the quote.  A block written with its attributes
    one per line under the fence is a YAML mapping, and it was read here as
    quote text: the words were searched as if the author had quoted
    "source: paper" out of their PDF, and the verdict was `quote-missing`
    (high) - an accusation against a passage that is on the page.  Two
    dialects had it (the fence and the HTML comment), and both were silent
    about it, because the quote simply came back longer.

    The fourth return value is the other half of that fix: a line at the left
    margin that reads like a field but names no key this format has.  Measured
    before it existed, on a project whose quote really is on page 2:

        Page: 1  above ``quote:``  -> page hint dropped, exit 0, no finding
        Page: 1  below ``quote:``  -> the line joined the quote, [high]
                                      quote-missing "…constructions. Page: 1"

    So a misspelt attribute either switched a check off without saying so, or
    accused the author of quoting a page their source never printed.  Both are
    reported now, and the line is kept out of the quote, because in a YAML
    block scalar a line at the left margin is a sibling key and never
    continuation text.
    """
    attributes: dict[str, str] = {}
    unknown: list[tuple[int, str]] = []
    if not body:
        return "", "", attributes, unknown
    has_keys = any(_FIELD_KEY.match(raw) for raw in body)
    if has_keys:
        fields: dict[str, list[str]] = {}
        current = ""
        for index, raw in enumerate(body, start=1):
            m = _BODY_KEY.match(raw)
            if m:
                current = m.group("key").lower()
                fields.setdefault(current, [])
                rest = m.group("rest").strip()
                if rest not in ("|", ">", ""):
                    # The inline form takes a YAML quoted scalar, and a reader
                    # who writes `quote: "the passage"` has written the same
                    # value as `quote: the passage`.  `_attrs` above has
                    # stripped those marks from `key="value"` since claims had
                    # attributes; this path never did, so the two quote marks
                    # travelled into the search as content, matched nothing,
                    # and produced a `quote-missing` (high) accuse - the same
                    # failure as a byte-order mark or an invisible directional
                    # mark, in the one place nobody had looked.
                    fields[current].append(_unquote(rest))
                continue
            other = _ATTRIBUTE_KEY.match(raw)
            if other:
                # `source: paper` under the fence is the same statement as
                # `source=paper` on it.  Reading it as quote text is how a
                # correct passage came back as `quote-missing`.
                attributes[other.group("key").lower()] = _unquote(other.group("rest").strip())
                current = ""
                continue
            keyish = _KEYISH.match(raw)
            if keyish is not None and not raw[:1].isspace():
                # A field line whose name this format does not have.  Read as
                # quote text it becomes a false accusation, and skipped in
                # silence it becomes a check the author believes ran.
                unknown.append((index, keyish.group("key")))
                continue
            if current:
                fields.setdefault(current, []).append(raw)
        quote = _dedent(fields.get("quote", []))
        claim = _dedent(fields.get("claim", []))
        return quote.strip(), claim.strip(), attributes, unknown

    if any(raw.strip().startswith(">>") for raw in body):
        quote_lines = [raw.strip()[2:].strip() for raw in body if raw.strip().startswith(">>")]
        claim_lines = [raw for raw in body if not raw.strip().startswith(">>")]
        return _dedent(quote_lines).strip(), _dedent(claim_lines).strip(), attributes, unknown

    paragraphs: list[list[str]] = [[]]
    for raw in body:
        if raw.strip():
            paragraphs[-1].append(raw)
        elif paragraphs[-1]:
            paragraphs.append([])
    paragraphs = [p for p in paragraphs if p]
    if len(paragraphs) >= 2:
        return (
            _dedent(paragraphs[0]).strip(),
            _dedent(paragraphs[1]).strip(),
            attributes,
            unknown,
        )
    only = _dedent(paragraphs[0] if paragraphs else []).strip()
    return only, "", attributes, unknown


def _unknown_field_findings(
    unknown: list[tuple[int, str]], path: str, start_line: int
) -> list[Finding]:
    """Say which line named a field this format does not have.

    The offset is into the block's body, so the number reported is the number
    the editor shows: the body starts on the line after the fence that opened
    it.
    """
    found: list[Finding] = []
    for offset, key in unknown:
        found.append(
            Finding(
                code="claim-field-unknown",
                message=(
                    f"line {start_line + offset} reads like a field ({key!r}), and a claim "
                    "body has no such key - it was neither applied nor searched as part of "
                    "the quote. The body keys are quote, claim, numbers, id, source, ref, "
                    "cite, page and marker"
                ),
                path=path,
                line=start_line + offset,
            )
        )
    return found


def _dedent(lines: list[str]) -> str:
    if not lines:
        return ""
    indents = [len(line) - len(line.lstrip()) for line in lines if line.strip()]
    cut = min(indents) if indents else 0
    return "\n".join(line[cut:] if len(line) >= cut else line for line in lines)


def _duplicate_finding(claim: Claim, seen: dict[str, int], path: str) -> Finding:
    return Finding(
        code="claim-uncheckable",
        message=(
            f"claim id {claim.id!r} is used twice (first at line {seen[claim.id]}); "
            "the ledger cannot track both, so the second is ignored"
        ),
        claim_id=claim.id,
        path=path,
        line=claim.line,
    )


def scan_unbound_markers(
    text: str,
    path: str = "manuscript.md",
    markers: tuple[str, ...] = DEFAULT_MARKERS,
    spans: list[tuple[int, int]] | None = None,
) -> list[Finding]:
    """Find credibility markers that are *not* inside a claim block.

    A sentence marked 【原文】 that carries no machine-checkable quote is the
    single most common way a manuscript looks verified while not being
    verified.  Reporting it is the point of this function.

    ``spans`` comes from :class:`ParseResult`; passing it keeps documented
    claims from being reported as unbound.
    """
    covered = _cover(spans or [])
    findings: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if lineno in covered:
            continue
        for marker in markers:
            if marker in line:
                findings.append(
                    Finding(
                        code="claim-without-evidence",
                        message=(
                            f"the {marker} mark on this line has no claim block, so "
                            "nothing ties it to a page in a local source"
                        ),
                        path=path,
                        line=lineno,
                    )
                )
                break
    return findings


def _cover(spans: list[tuple[int, int]]) -> set[int]:
    covered: set[int] = set()
    for first, last in spans:
        covered.update(range(first, last + 1))
    return covered
