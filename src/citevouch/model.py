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
    "quote-fuzzy": "medium",
    "number-absent": "high",
    "number-absent-in-quote": "high",
    "source-missing": "high",
    "source-changed": "medium",
    "source-unreadable": "high",
    "bib-key-missing": "high",
    "bib-key-unused": "info",
    "bib-field-empty": "medium",
    "bib-duplicate-key": "high",
    "bib-doi-mismatch": "medium",
    "page-out-of-range": "high",
    "claim-without-evidence": "low",
    "ledger-stale": "high",
}

_SEVERITY_RANK = {name: i for i, name in enumerate(SEVERITIES)}


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
        return f"{head}: {self.message}"


@dataclass
class SourceRef:
    """One local document that a claim draws on.

    ``key`` is what the manuscript writes in ``source=``; it resolves via the
    sources manifest (``sources.toml``/``sources.json``) or by filename stem.
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
    """

    schema: int = 1
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
                    page=raw.get("page"),
                    path=str(raw.get("path", "")),
                    line=int(raw.get("line", 0) or 0),
                    marker=str(raw.get("marker", "")),
                    ref=str(raw.get("ref", "")),
                    numbers=tuple(raw.get("numbers") or ()),
                    quote_fingerprint=str(raw.get("quote_fingerprint", "")),
                )
            )
        return ledger
