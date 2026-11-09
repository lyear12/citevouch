"""Data model shared by every stage of the pipeline.

Everything here is a plain dataclass so that a ledger is trivially
JSON-serialisable and a test can build one by hand.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from .errors import UsageError
from .textnorm import quote_numbers

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
    # High, like the code above, and for the same reason: the author writes a
    # sentence whose words are the page's and whose number is another
    # sentence's.  That is a transcribed number, not a formatting difference,
    # and it is the exact error this tool exists to catch - a default
    # `--fail-on high` run has to fail on it.  Splitting it from
    # `number-absent-in-quote` is not a severity change: it is the difference
    # between "that number is nowhere on this page" and "that number is four
    # lines further down", and only one of those is true of a swapped number.
    "number-not-in-passage": "high",
    # High for the same reason as the two above, and it is the same mistake in
    # a different place: the quote is right, the sentence that restates it is
    # not.  `claim.numbers` has always held the quote's numbers, so a claim
    # could say 80,688 where its own quote says 40,688 and verify - measured,
    # that was exit 0.  A mistyped statistic reads as correct for months, and
    # it is the one error the author most wants a machine to find, so it
    # cannot depend on the reader noticing.
    "claim-number-differs": "high",
    "source-missing": "high",
    "source-changed": "medium",
    "source-unreadable": "high",
    "source-no-text": "high",
    "source-is-manuscript": "high",
    "source-not-text": "medium",
    "source-encoding": "high",
    # High for the same reason `source-encoding` is: the author believes this
    # quote was checked against the page, and it was not.  It is the
    # manuscript-side half of that defect - a manuscript saved in GBK parses
    # (the fences and attributes are ASCII) with only the quoted words coming
    # out as replacement characters, so every claim in it used to be answered
    # `quote-missing`, an accusation about a sentence nobody had read.
    "claim-not-decoded": "high",
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
    # A claim fence inside a blockquote, a list item or an indent.  Markdown
    # renders that as a code sample, so the parser is right not to read it -
    # but the run must not be silent about it either.  High, and not `low`,
    # because the two readings of this line have opposite consequences for the
    # author: as a sample it is fine, and as a claim it was never checked while
    # the run reported a number of claims that reads like a total.  A finding
    # that says "check whether you meant this" is cheap; a green run over a
    # claim nobody read is the failure this tool exists to prevent.
    # A misspelt body field is not a refused claim: the quote is still found and
    # compared, so nothing is unchecked that the reader is told was checked.  What
    # is lost is the instruction the field carried, which is what makes this the
    # same severity as `page-unreadable` - a hint that is not being applied.
    "claim-field-unknown": "medium",
    # Two spellings of one attribute written with two different values.  The
    # run applies one and drops the other, so the manuscript says something no
    # check ever saw - the same shape as a misspelt body field, and the same
    # severity: the quote is still compared, what is lost is an instruction.
    "claim-field-conflict": "medium",
    "claim-block-unread": "high",
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
    # A check `doctor` could not pass: no PDF library, an interpreter older than
    # the package supports, a cache directory nobody can write to, a project
    # without the files it says it has.  High, because every one of them ends
    # the same way - a run that reports quotes as missing when the truth is that
    # nothing could be read - and the user is about to conclude the tool is
    # wrong about their paper.
    #
    # This code exists because `source-unreadable` was the wrong word for it.
    # doctor used to reuse that code, which made GitHub display a missing
    # interpreter as "A source file could not be read."; the message was right
    # and the rule above it was about a different thing.  One vocabulary per
    # problem, and "this machine cannot run the checker" is not "this PDF is
    # broken".
    "check-unavailable": "high",
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


# --- Reading a lockfile that may not be one ------------------------------
#
# ``from_json`` used to trust every field: ``raw.get(...)`` on each list element
# and ``int(...)`` on each count.  A hand-edited or truncated lockfile then
# raised AttributeError, TypeError or ValueError straight out of ``main`` - and
# since the interpreter exits 1 on an uncaught exception, those crashes were
# indistinguishable from "findings reached the threshold".  Measured on twelve
# damaged shapes: eighteen crashes across ``report``, ``verify`` and
# ``check --use-recorded``.
#
# The rule is the one ``cli._read_ledger`` already applies to the schema number:
# a file this code cannot read in full is refused, not half-parsed, because a
# half-read claim comes back with empty fields and "source-missing" on it is the
# false verdict this tool exists to avoid.  These helpers are that refusal.


def _object(raw: Any, where: str) -> dict[str, Any]:
    """One ledger element, which must be a JSON object."""
    if not isinstance(raw, dict):
        raise UsageError(f"ledger {where} must be an object, not {type(raw).__name__}")
    return raw


def _section(blob: dict[str, Any], name: str) -> dict[str, Any]:
    """One named ledger section, which must be a JSON object."""
    value = blob.get(name)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise UsageError(
            f"ledger {name} must be an object keyed by name, not {type(value).__name__}"
        )
    return value


def _fields(entry: dict[str, Any], where: str) -> dict[str, str]:
    """A bibliography entry's fields, which must be an object of strings."""
    value = entry.get("fields")
    if value is None:
        return {}
    # ``or {}`` would have turned ``fields: []`` into an empty mapping, which is
    # the silent half-read this whole section exists to prevent: an entry with
    # no title then reports ``bib-field-missing`` about a title that is there.
    if not isinstance(value, dict):
        raise UsageError(
            f"ledger {where}.fields must be an object mapping field names to "
            f"values, not {type(value).__name__}"
        )
    return {str(k): str(v) for k, v in value.items()}


def _whole(value: Any, where: str, *, default: int = 0) -> int:
    """A ledger count, which must be a whole number."""
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise UsageError(f"ledger {where} must be a whole number, not {type(value).__name__}")
    if isinstance(value, str):
        text = value.strip()
        if not text.lstrip("+-").isdigit():
            raise UsageError(f"ledger {where} must be a whole number, not {value!r}")
        return int(text)
    if isinstance(value, float) and not value.is_integer():
        raise UsageError(f"ledger {where} must be a whole number, not {value!r}")
    return int(value)


def _texts(value: Any, where: str) -> tuple[str, ...]:
    """A ledger list of strings, such as a claim's numbers."""
    if value is None:
        return ()
    if isinstance(value, str) or not isinstance(value, list | tuple):
        raise UsageError(
            f"ledger {where} must be a list of strings, not {type(value).__name__}"
        )
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise UsageError(
                f"ledger {where} must be a list of strings, but holds {type(item).__name__}"
            )
        out.append(item)
    return tuple(out)


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
    the load-bearing field: it is what every matching tier compares the page
    against, and what ``quote_fingerprint`` digests so the ledger can show that
    a quote changed without storing the passage twice.

    ``quote_fingerprint`` is a record, not a decider: no code reads it back to
    reach a verdict.  ``quote-moved`` is decided from the page numbers this run
    found, so an edited quote is compared to the source like any other, which
    is the property that matters - ``--allow-stale`` lets a changed manuscript
    be checked, and the check has to be of the text that is there now.

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
    # Derived from ``quote`` by ``textnorm.quote_numbers``, never stored as a
    # fact about anything else: the ledger writes it for readers of the file,
    # and ``Ledger.from_json`` recomputes it rather than trusting it.
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
    # Our task: the bibliography files the recorded entries came from.
    #
    # ``entries`` alone cannot tell "the project named no bibliography" from
    # "the project named one and not a single entry could be read from it":
    # both record as an empty mapping.  ``scan`` says ``[high] bib-unreadable``
    # for the second, and used to be the only run that ever did - the finding
    # never reached the ledger, so ``check --use-recorded`` (every pull
    # request, through action.yml) reported a green run for a bibliography
    # nobody had checked anything against.
    bibliographies: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "manuscript": self.manuscript,
            "manuscript_sha256": self.manuscript_sha256,
            "generated_at": self.generated_at,
            "tool_version": self.tool_version,
            "sources": {k: v.to_json() for k, v in sorted(self.sources.items())},
            "entries": {k: v.to_json() for k, v in sorted(self.entries.items())},
            "bibliographies": list(self.bibliographies),
            "claims": [c.to_json() for c in self.claims],
        }

    @classmethod
    def from_json(cls, blob: dict[str, Any]) -> Ledger:
        ledger = cls(
            schema=_whole(blob.get("schema"), "schema", default=SUPPORTED_SCHEMA),
            manuscript=str(blob.get("manuscript", "")),
            manuscript_sha256=str(blob.get("manuscript_sha256", "")),
            generated_at=str(blob.get("generated_at", "")),
            tool_version=str(blob.get("tool_version", "")),
            # A ledger written before this key existed names no bibliography,
            # which is exactly what it recorded: nothing is claimed about one.
            bibliographies=list(_texts(blob.get("bibliographies"), "bibliographies")),
        )
        for key, raw in _section(blob, "sources").items():
            entry = _object(raw, f"sources[{key!r}]")
            ledger.sources[key] = SourceRef(
                key=str(entry.get("key", key)),
                path=str(entry.get("path", "")),
                sha256=str(entry.get("sha256", "")),
                pages=_whole(entry.get("pages"), f"sources[{key!r}].pages"),
            )
        for key, raw in _section(blob, "entries").items():
            entry = _object(raw, f"entries[{key!r}]")
            ledger.entries[key] = BibEntry(
                key=str(entry.get("key", key)),
                entry_type=str(entry.get("type", "")),
                fields=_fields(entry, f"entries[{key!r}]"),
                path=str(entry.get("path", "")),
                line=_whole(entry.get("line"), f"entries[{key!r}].line"),
            )
        claims = blob.get("claims")
        if not isinstance(claims, list):
            # ``claims`` is the one key ``_read_ledger`` requires, so a null or
            # missing one is a damaged file, not an empty ledger.  Reading it as
            # "nothing to verify" would report a clean run for a manuscript
            # whose evidence was thrown away.
            raise UsageError(
                f"ledger claims must be a list of claim objects, not {type(claims).__name__}"
            )
        for index, raw in enumerate(claims):
            entry = _object(raw, f"claims[{index}]")
            quote = str(entry.get("quote", ""))
            # The shape is checked and the value is not trusted.
            #
            # ``numbers`` is a transcription of ``quote`` - ``textnorm.quote_numbers``
            # is the only producer - so the file's copy can only be stale, never
            # more informed than the quote sitting next to it.  Trusting it made
            # a real accusation out of a formatting change: ledgers written
            # before 0.22.16 record ``["40", "688"]`` for a quote that says
            # ``40 688``, because the grouping space used to split the number in
            # two, and verifying such a ledger with this build reported
            # ``[high] number-absent-in-quote`` about a quote that is verbatim
            # the page.  ``check --use-recorded`` is what ``action.yml`` runs,
            # so that landed on every repository that upgraded.
            #
            # Re-deriving is not leniency: a re-typed number is still absent
            # from the page and still high, because the comparison now starts
            # from the quote in the ledger, which is the text the author
            # actually wrote.  A value of the wrong shape stays a damaged file
            # (``_texts`` raises, exit 2) - that is a shape no writer produced,
            # as opposed to a shape an older writer produced.
            _texts(entry.get("numbers"), f"claims[{index}].numbers")
            ledger.claims.append(
                Claim(
                    id=str(entry.get("id", "")),
                    text=str(entry.get("text", "")),
                    source=str(entry.get("source", "")),
                    quote=quote,
                    page=_as_page(entry.get("page")),
                    path=str(entry.get("path", "")),
                    line=_whole(entry.get("line"), f"claims[{index}].line"),
                    marker=str(entry.get("marker", "")),
                    ref=str(entry.get("ref", "")),
                    numbers=quote_numbers(quote),
                    quote_fingerprint=str(entry.get("quote_fingerprint", "")),
                )
            )
        return ledger
