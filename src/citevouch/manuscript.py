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
from .textnorm import numbers_in

_FENCE_OPEN = re.compile(r"^```claim\b(?P<attrs>.*)$")
_FENCE_CLOSE = re.compile(r"^```\s*$")
_ANY_FENCE = re.compile(r"^(?P<ticks>`{3,}|~{3,})(?P<info>.*)$")
_HTML_OPEN = re.compile(r"^<!--\s*claim\s*:?\s*(?P<attrs>.*)$")
_HTML_CLOSE = re.compile(r"^\s*-->\s*$")
_TABLE_CLAIM = re.compile(
    r"^\|\s*(?P<id>[A-Za-z0-9_.:-]+)\s*\|\s*(?P<source>[^|]+?)\s*\|"
    r"\s*(?P<page>\d+|-)\s*\|\s*(?P<quote>[^|]+?)\s*\|\s*(?P<text>[^|]+?)\s*\|"
)
_ATTR = re.compile(r"(?P<key>[A-Za-z_][A-Za-z0-9_-]*)\s*=\s*(?P<value>\"[^\"]*\"|'[^']*'|\S+)")
# A line a human would read as "here begins a claim block", in any of the
# spellings close enough to the real one to be a mistake rather than prose.
# Used only to explain a file that yielded no claims: naming the line that was
# almost right is the difference between "the tool is broken" and "look at line
# 12".  Deliberately permissive - it is a hint generator, never a gate.
_CLAIMISH = re.compile(r"^\s*(?:`{3,}|~{3,}|<!--)\s*[*_]*\s*claim\b", re.IGNORECASE)
_FIELD_KEY = re.compile(r"^\s*(?P<key>quote|claim|numbers?)\s*:\s*(?P<rest>.*)$")

# The credibility markers the surrounding workflow already uses.  Kept as data
# rather than hard-coded checks so a project can rename them.
DEFAULT_MARKERS = ("【原文】", "【实测】", "【推测】", "[原文]", "[实测]", "[推测]")


@dataclass
class ParseResult:
    claims: list[Claim]
    findings: list[Finding]
    # 1-based inclusive line spans that belong to a claim block.  Prose checks
    # use them to avoid re-reporting what the block already documents.
    spans: list[tuple[int, int]] = field(default_factory=list)


def _attrs(blob: str) -> dict[str, str]:
    """Parse ``key=value`` attributes; a leading bare token becomes ``id``.

    ``<!-- claim: c1 source=x -->`` is common enough that refusing to read the
    positional id would reject the manuscripts this tool exists to help.
    """
    out: dict[str, str] = {}
    for m in _ATTR.finditer(blob or ""):
        value = m.group("value")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        out[m.group("key").lower()] = value
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
) -> tuple[Claim | None, list[Finding]]:
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
        numbers=numbers_in(quote),
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
            while j < len(lines) and not _FENCE_CLOSE.match(lines[j]):
                body.append(lines[j])
                j += 1
            closed = j < len(lines)
            quote, claim_text = _split_body(body)
            claim, more = _claim_from(attrs, quote, claim_text, path, start_line)
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
            i = j + 1
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
            quote, claim_text = _split_body(body)
            claim, more = _claim_from(attrs, quote, claim_text, path, start_line)
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
                "source": m.group("source"),
                "page": m.group("page"),
            }
            claim, more = _claim_from(
                attrs, m.group("quote"), m.group("text"), path, start_line
            )
            accept(claim, more, start_line, start_line)
            i += 1
            continue

        i += 1
    return ParseResult(claims=claims, findings=findings, spans=spans)


def _split_body(body: list[str]) -> tuple[str, str]:
    """Split a claim body into (quote, claim).

    Accepts several shapes, tried in order of explicitness:

    * ``quote:`` / ``claim:`` keys, either value possibly a ``|`` block;
    * a line beginning with ``>>`` for the quote and the rest for the claim;
    * the first paragraph as quote, the second as claim;
    * everything as the quote, with an empty claim (still verifiable).
    """
    if not body:
        return "", ""
    has_keys = any(_FIELD_KEY.match(raw) for raw in body)
    if has_keys:
        fields: dict[str, list[str]] = {}
        current = ""
        for raw in body:
            m = _FIELD_KEY.match(raw)
            if m:
                current = m.group("key").lower()
                fields.setdefault(current, [])
                rest = m.group("rest").strip()
                if rest not in ("|", ">", ""):
                    fields[current].append(rest)
                continue
            if current:
                fields.setdefault(current, []).append(raw)
        quote = _dedent(fields.get("quote", []))
        claim = _dedent(fields.get("claim", []))
        return quote.strip(), claim.strip()

    if any(raw.strip().startswith(">>") for raw in body):
        quote_lines = [raw.strip()[2:].strip() for raw in body if raw.strip().startswith(">>")]
        claim_lines = [raw for raw in body if not raw.strip().startswith(">>")]
        return _dedent(quote_lines).strip(), _dedent(claim_lines).strip()

    paragraphs: list[list[str]] = [[]]
    for raw in body:
        if raw.strip():
            paragraphs[-1].append(raw)
        elif paragraphs[-1]:
            paragraphs.append([])
    paragraphs = [p for p in paragraphs if p]
    if len(paragraphs) >= 2:
        return _dedent(paragraphs[0]).strip(), _dedent(paragraphs[1]).strip()
    only = _dedent(paragraphs[0] if paragraphs else []).strip()
    return only, ""


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
