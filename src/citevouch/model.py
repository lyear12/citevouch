"""Data model shared by every stage of the pipeline.

Everything here is a plain dataclass so that a ledger is trivially
JSON-serialisable and a test can build one by hand.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

# Severity ordering, low to high.  The CLI exit code is derived from the
# highest severity present, which keeps CI integration boring.
SEVERITIES = ("info", "low", "medium", "high")

# Finding codes.  Stable strings: users grep them, CI filters them, and the
# SARIF rule ids are derived from them, so renaming one is a breaking change.
CODES = {
    "quote-found": "info",
    "quote-moved": "medium",
    "quote-missing": "high",
    # High, not medium. `quote-fuzzy` means "there is text like this nearby and
    # I refused to call it a match" - the reader still has no evidence, so it is
    # not a warning about a claim that holds, it is a claim that does not hold.
    # It also used to be medium plus a hard-coded exit 1 in the CLI, which made
    # `--fail-on` a lie for exactly this one code. Severity is the right place
    # for the rule; a special case in the exit path is not.
    "quote-fuzzy": "high",
    "number-absent-in-quote": "high",
    "source-missing": "high",
    "source-changed": "medium",
    "source-unreadable": "high",
    "bib-key-missing": "high",
    "bib-key-unused": "info",
    "bib-field-empty": "medium",
    "bib-field-malformed": "medium",
    "bib-field-duplicate": "medium",
    "bib-duplicate-key": "high",
    "bib-macro-unknown": "medium",
    "bib-entry-header-unparsed": "medium",
    "bib-unparsed-entry": "high",
    # A bibliography nobody could read is not an empty bibliography, and it is
    # not a small problem: verify has nothing to check any reference against,
    # so every bib-key-missing is suppressed.  Quietest possible run for the
    # worst possible input.
    "bib-unreadable": "high",
    "page-out-of-range": "high",
    "claim-block-unclosed": "high",
    # A claim block that cannot be looked up at all: no source=, no quote, no
    # id, or an id used twice so the second block is dropped.  It is high and
    # not low because the quote in it was never compared to anything - the run
    # reported a number of claims checked that does not include this one, and a
    # green pipeline over an unchecked claim is the exact failure this tool
    # exists to prevent.
    "claim-uncheckable": "high",
    # A page hint that is not a number.  The claim is still located by search,
    # so this is a note about an instruction being ignored, not a rejection.
    "page-unreadable": "medium",
    # A prose marker with no claim block behind it.  Low: it is a reminder that
    # something in the prose asserts a source it does not name, not a claim that
    # was supposed to be checked and was not.
    "claim-without-evidence": "low",
    "ledger-stale": "high",
    # A manuscript holding no claim blocks at all.  Every other code describes a
    # claim that failed; this one describes a run in which no claim was ever
    # looked at, and calling that clean is the one verdict this tool must never
    # give.  A `.tex` manuscript is refused outright for the same reason.  High,
    # because the CI job that would have reported it green is the job somebody
    # is trusting.
    "no-claim-blocks": "high",
}

_SEVERITY_RANK = {name: i for i, name in enumerate(SEVERITIES)}


def _as_page(value: Any) -> int | None:
    """Coerce a ledger ``page`` value to an int page number, or None.

    Hand-edited and half-written ledgers happen, and the one thing that must
    not happen is a type error escaping as exit code 1 - 1 is reserved for
    "findings reached the threshold" and a crash there is indistinguishable
    from a verdict.  ``"3"`` is accepted (JSON has one number type and tooling
    sometimes quotes it); a float is truncated; anything else becomes None,
    which the callers treat as "no page hint" and then report against the
    claim's own text instead of comparing incompatible types.
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if text.lstrip("+-").isdigit():
            return int(text)
        try:  # "3.0" - a quoted float is still a page number
            number = float(text)
        except ValueError:
            return None
        return int(number) if number.is_integer() else None
    return None


# The ledger format this code writes and the highest format it can read.  One
# number, owned here: a future version that changes the ledger shape raises
# SUPPORTED_SCHEMA *and* keeps reading schema 1, so old lockfiles never strand.
SUPPORTED_SCHEMA = 1


def severity_of(code: str) -> str:
    return CODES.get(code, "medium")


def worst(severities: Iterable[str]) -> str:
    best = "info"
    for s in severities:
        if _SEVERITY_RANK.get(s, 0) > _SEVERITY_RANK[best]:
            best = s
    return best


def fingerprint(text: str) -> str:
    """Stable short digest of a normalised string.

    Used for quote fingerprints in the ledger.  Short because it lands in
    human-readable reports and diff output; 16 hex chars of blake2b is far
    more than enough to tell two quotes apart, and this is not a security
    boundary.
    """
    return hashlib.blake2b(text.encode("utf-8"), digest_size=8).hexdigest()


@dataclass(frozen=True)
class Finding:
    """One problem (or confirmation) about one claim or one bib entry."""

    code: str
    message: str
    severity: str = ""
    claim_id: str = ""
    path: str = ""
    line: int = 0

    def __post_init__(self) -> None:
        if not self.severity:
            object.__setattr__(self, "severity", severity_of(self.code))

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
        }
        if self.claim_id:
            out["claim_id"] = self.claim_id
        if self.path:
            out["path"] = self.path
        if self.line:
            out["line"] = self.line
        return out

    def one_line(self) -> str:
        where = self.path or ""
        if where and self.line:
            where = f"{where}:{self.line}"
        head = f"[{self.severity}] {self.code}"
        if where:
            head = f"{head} at {where}"
        if self.claim_id:
            head = f"{head} ({self.claim_id})"
        return f"{head}: {self._message_without_claim_prefix()}"

    def _message_without_claim_prefix(self) -> str:
        """The message, minus a leading ``claim <id>: `` that repeats the head.

        Every finding `verify` produces opens its message with `claim c1: ` so
        that JSON, SARIF and Markdown — which print `message` alone — say which
        claim they are about.  The terminal already prints the id in
        parentheses, so keeping both produced `(c1): claim c1: ...`, which is
        what the README example showed and the tool could not reproduce.
        """
        prefix = f"claim {self.claim_id}: " if self.claim_id else ""
        if prefix and self.message.startswith(prefix):
            return self.message[len(prefix) :]
        return self.message


@dataclass
class SourceRef:
    """One local document that a claim draws on.

    ``key`` is what the manuscript writes in ``source=``; it resolves through
    the sources manifest (``sources.toml`` or ``sources.json``), exactly, with
    a case-insensitive retry. There is no filename-stem fallback: a key that
    does not name a manifest entry is a key the project has not bound.
    """

    key: str
    path: str
    sha256: str = ""
    pages: int = 0

    def to_json(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "path": self.path,
            "sha256": self.sha256,
            "pages": self.pages,
        }


@dataclass
class Claim:
    """A sentence in the manuscript plus the evidence that is supposed to back it.

    ``quote`` is the verbatim passage as it should appear in the source.  It is
    the load-bearing field: the ledger stores its fingerprint, so a later
    verification run can tell "the quote is gone" from "the quote moved".

    ``source`` and ``ref`` are two different namespaces and are deliberately
    kept apart: ``source`` names a *local document* (a PDF on disk), ``ref``
    names a *bibliography entry*.  They often look alike and are often not the
    same string, which is precisely why conflating them produces false
    "key not in bibliography" findings.
    """

    id: str
    text: str
    source: str
    quote: str
    page: int | None = None
    path: str = ""
    line: int = 0
    marker: str = ""
    ref: str = ""
    numbers: tuple[str, ...] = ()
    quote_fingerprint: str = ""

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "text": self.text,
            "source": self.source,
            "quote": self.quote,
            "numbers": list(self.numbers),
        }
        if self.page is not None:
            out["page"] = self.page
        if self.path:
            out["path"] = self.path
        if self.line:
            out["line"] = self.line
        if self.marker:
            out["marker"] = self.marker
        if self.ref:
            out["ref"] = self.ref
        if self.quote_fingerprint:
            out["quote_fingerprint"] = self.quote_fingerprint
        return out


@dataclass
class BibEntry:
    key: str
    entry_type: str
    fields: dict[str, str] = field(default_factory=dict)
    path: str = ""
    line: int = 0

    def to_json(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "type": self.entry_type,
            "fields": dict(self.fields),
            "path": self.path,
            "line": self.line,
        }


@dataclass
class Ledger:
    """The recorded state of one manuscript's evidence.

    Written by ``citevouch scan`` and read by ``citevouch verify``.  Treat it
    as a lockfile: commit it, review its diff, and do not hand-edit it.

    ``schema`` is the ledger format version, and ``SUPPORTED_SCHEMA`` the
    highest one this code can read; :func:`citevouch.cli._read_ledger` refuses
    anything above it rather than half-parsing it.
    """

    schema: int = field(default=SUPPORTED_SCHEMA)
    manuscript: str = ""
    manuscript_sha256: str = ""
    generated_at: str = ""
    tool_version: str = ""
    claims: list[Claim] = field(default_factory=list)
    sources: dict[str, SourceRef] = field(default_factory=dict)
    entries: dict[str, BibEntry] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "manuscript": self.manuscript,
            "manuscript_sha256": self.manuscript_sha256,
            "generated_at": self.generated_at,
            "tool_version": self.tool_version,
            "sources": {k: v.to_json() for k, v in sorted(self.sources.items())},
            "entries": {k: v.to_json() for k, v in sorted(self.entries.items())},
            "claims": [c.to_json() for c in self.claims],
        }

    @classmethod
    def from_json(cls, blob: dict[str, Any]) -> Ledger:
        ledger = cls(
            schema=int(blob.get("schema", 1)),
            manuscript=str(blob.get("manuscript", "")),
            manuscript_sha256=str(blob.get("manuscript_sha256", "")),
            generated_at=str(blob.get("generated_at", "")),
            tool_version=str(blob.get("tool_version", "")),
        )
        for key, raw in (blob.get("sources") or {}).items():
            ledger.sources[key] = SourceRef(
                key=str(raw.get("key", key)),
                path=str(raw.get("path", "")),
                sha256=str(raw.get("sha256", "")),
                pages=int(raw.get("pages", 0) or 0),
            )
        for key, raw in (blob.get("entries") or {}).items():
            ledger.entries[key] = BibEntry(
                key=str(raw.get("key", key)),
                entry_type=str(raw.get("type", "")),
                fields={str(k): str(v) for k, v in (raw.get("fields") or {}).items()},
                path=str(raw.get("path", "")),
                line=int(raw.get("line", 0) or 0),
            )
        for raw in blob.get("claims") or []:
            ledger.claims.append(
                Claim(
                    id=str(raw.get("id", "")),
                    text=str(raw.get("text", "")),
                    source=str(raw.get("source", "")),
                    quote=str(raw.get("quote", "")),
                    page=_as_page(raw.get("page")),
                    path=str(raw.get("path", "")),
                    line=int(raw.get("line", 0) or 0),
                    marker=str(raw.get("marker", "")),
                    ref=str(raw.get("ref", "")),
                    numbers=tuple(raw.get("numbers") or ()),
                    quote_fingerprint=str(raw.get("quote_fingerprint", "")),
                )
            )
        return ledger
