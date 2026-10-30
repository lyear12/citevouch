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
_HTML_OPEN = re.compile(r"^<!--\s*claim\s*:?\s*(?P<attrs>.*)$")
_HTML_CLOSE = re.compile(r"^\s*-->\s*$")
_TABLE_CLAIM = re.compile(
    r"^\|\s*(?P<id>[A-Za-z0-9_.:-]+)\s*\|\s*(?P<source>[^|]+?)\s*\|"
    r"\s*(?P<page>\d+|-)\s*\|\s*(?P<quote>[^|]+?)\s*\|\s*(?P<text>[^|]+?)\s*\|"
)
_ATTR = re.compile(r"(?P<key>[A-Za-z_][A-Za-z0-9_-]*)\s*=\s*(?P<value>\"[^\"]*\"|'[^']*'|\S+)")
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
                code="claim-without-evidence",
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
                code="claim-without-evidence",
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
                code="claim-without-evidence",
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
            findings.append(
                Finding(
                    code="claim-without-evidence",
                    message=f"claim {cid} has a non-numeric page={raw_page!r}; it will be located by search instead",
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
                    Finding(
                        code="claim-block-unclosed",
                        message=(
                            f"claim {claim.id}: the ```claim fence opened on line "
                            f"{start_line} is never closed; every claim after it was "
                            "read as part of this block"
                        ),
                        claim_id=claim.id,
                        path=path,
                        line=start_line,
                    )
                )
            accept(claim, more, start_line, j + 1)
            i = j + 1
            continue

        if line.startswith("```"):
            # Some other fenced block: skip it wholesale so prose inside a code
            # sample is never mistaken for a claim.
            j = i + 1
            while j < len(lines) and not _FENCE_CLOSE.match(lines[j]):
                j += 1
            i = j + 1
            continue

        m = _HTML_OPEN.match(line)
        if m and "-->" not in line:
            attrs = _attrs(m.group("attrs"))
            body = []
            j = i + 1
            while j < len(lines) and not _HTML_CLOSE.match(lines[j]):
                body.append(lines[j])
                j += 1
            quote, claim_text = _split_body(body)
            claim, more = _claim_from(attrs, quote, claim_text, path, start_line)
            accept(claim, more, start_line, j + 1)
            i = j + 1
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
        code="claim-without-evidence",
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
