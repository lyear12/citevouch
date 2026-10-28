"""A small, forgiving BibTeX reader.

Deliberately not a full BibTeX implementation: this tool needs entry keys, the
fields a manuscript is allowed to name, and reliable line numbers for
reporting.  It handles the constructs that appear in real `.bib` files drawn
from Zotero/JabRef/Google Scholar exports — `@type{key, field = {value}, ...}`,
`@string` macros, `#` concatenation, `@comment`, `@preamble` — and reports
anything it cannot parse instead of silently dropping it, because a dropped
entry would produce a false "missing citation" later.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, field

from .model import BibEntry, Finding

_ENTRY_START = re.compile(r"@(?P<type>[A-Za-z]+)\s*(?P<open>[{(])")
_KEY = re.compile(r"\s*(?P<key>[^,\s{}()]*)\s*,?")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_:+.\-]*|[0-9]+")
_FIELD_HEAD = re.compile(r"\s*,?\s*([A-Za-z_][A-Za-z0-9_\-]*)\s*=\s*")
_STRING_DEF = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_\-]*)\s*=\s*")

# BibTeX ignores these entry types; they must never be reported as citations.
_NON_ENTRIES = {"comment", "preamble", "string"}


@dataclass
class BibResult:
    entries: dict[str, BibEntry] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    strings: dict[str, str] = field(default_factory=dict)


def _strip_comments(text: str) -> str:
    """Remove ``%`` comments that are outside entry bodies, preserving lines.

    BibTeX only has comments *between* entries; a ``%`` inside a field value is
    ordinary text.  Stripping it there silently truncates the value — and when
    the truncation eats a closing brace, it swallows every entry after it, which
    looks exactly like "the bibliography has one entry".  So brace depth decides.
    """
    out = []
    depth = 0
    for line in text.splitlines():
        cut = len(line)
        idx = 0
        in_quote = False
        while idx < len(line):
            ch = line[idx]
            if ch == "\\":
                idx += 2
                continue
            if ch == '"':
                in_quote = not in_quote
            elif not in_quote and ch == "{":
                depth += 1
            elif not in_quote and ch == "}":
                depth = max(0, depth - 1)
            elif ch == "%" and depth == 0:
                cut = idx
                break
            idx += 1
        out.append(line[:cut])
    return "\n".join(out)


def _balanced(text: str, start: int, open_ch: str, close_ch: str) -> int:
    """Index just past the delimiter that closes the one at ``start``."""
    depth = 0
    i = start
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return len(text)


def _quoted(text: str, start: int) -> int:
    """Index just past the closing double quote, honouring ``\\"`` escapes."""
    i = start + 1
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == '"':
            return i + 1
        i += 1
    return len(text)


def _read_field_value(text: str, start: int, strings: dict[str, str]) -> tuple[str, int]:
    """Read one field value, honouring ``#`` concatenation and macros."""
    parts: list[str] = []
    i = start
    n = len(text)
    while i < n:
        while i < n and text[i] in " \t\r\n":
            i += 1
        if i >= n:
            break
        ch = text[i]
        if ch == "{":
            end = _balanced(text, i, "{", "}")
            parts.append(text[i + 1 : end - 1])
            i = end
        elif ch == '"':
            end = _quoted(text, i)
            parts.append(text[i + 1 : end - 1])
            i = end
        else:
            m = _IDENT.match(text, i)
            if not m:
                break
            token = m.group(0)
            parts.append(strings.get(token.lower(), token))
            i = m.end()
        while i < n and text[i] in " \t\r\n":
            i += 1
        if i < n and text[i] == "#":
            i += 1
            continue
        break
    return "".join(parts), i


def _clean(value: str) -> str:
    value = value.replace("\n", " ").replace("\r", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def parse_bib(text: str, path: str = "refs.bib") -> BibResult:
    findings: list[Finding] = []
    entries: dict[str, BibEntry] = {}
    strings: dict[str, str] = {}
    text = _strip_comments(text)
    line_starts = [0] + [i + 1 for i, ch in enumerate(text) if ch == "\n"]

    def line_of(pos: int) -> int:
        return bisect.bisect_right(line_starts, pos)

    i = 0
    n = len(text)
    while i < n:
        at = text.find("@", i)
        if at < 0:
            break
        m = _ENTRY_START.match(text, at)
        if not m:
            i = at + 1
            continue
        etype = m.group("type").lower()
        open_ch = m.group("open")
        close_ch = "}" if open_ch == "{" else ")"
        body_start = m.end()
        body_end = _balanced(text, m.start("open"), open_ch, close_ch)
        body = text[body_start : body_end - 1]
        i = max(body_end, at + 1)

        if etype in _NON_ENTRIES:
            if etype == "string":
                sm = _STRING_DEF.match(body)
                if sm:
                    value, _ = _read_field_value(body, sm.end(), strings)
                    strings[sm.group(1).lower()] = _clean(value)
            continue

        km = _KEY.match(body)
        key = km.group("key") if km else ""
        if not key:
            findings.append(
                Finding(
                    code="bib-key-missing",
                    message=f"@{etype} entry at this position has no cite key",
                    path=path,
                    line=line_of(at),
                )
            )
            continue

        fields: dict[str, str] = {}
        pos = km.end() if km else 0
        while pos < len(body):
            fm = _FIELD_HEAD.match(body, pos)
            if not fm:
                break
            value, pos = _read_field_value(body, fm.end(), strings)
            fields[fm.group(1).lower()] = _clean(value)
        if key in entries:
            findings.append(
                Finding(
                    code="bib-duplicate-key",
                    message=f"cite key {key!r} appears more than once; the later entry wins",
                    path=path,
                    line=line_of(at),
                )
            )
        entries[key] = BibEntry(
            key=key, entry_type=etype, fields=fields, path=path, line=line_of(at)
        )
    return BibResult(entries=entries, findings=findings, strings=strings)


REQUIRED_FIELDS = {
    "article": ("author", "title", "journal", "year"),
    "book": ("author", "title", "publisher", "year"),
    "inproceedings": ("author", "title", "booktitle", "year"),
    "incollection": ("author", "title", "booktitle", "year"),
    "phdthesis": ("author", "title", "school", "year"),
    "mastersthesis": ("author", "title", "school", "year"),
    "techreport": ("author", "title", "institution", "year"),
}


def field_findings(entries: dict[str, BibEntry]) -> list[Finding]:
    """Report entries whose required fields are present but empty.

    A present-but-empty ``year = {}`` is worse than a missing one: it looks
    filled in to every tool that only checks for the key.
    """
    out: list[Finding] = []
    for key, entry in entries.items():
        for name in REQUIRED_FIELDS.get(entry.entry_type, ()):
            if name in entry.fields and not entry.fields[name].strip():
                out.append(
                    Finding(
                        code="bib-field-empty",
                        message=f"{key}: field {name!r} exists but is empty",
                        path=entry.path,
                        line=entry.line,
                    )
                )
    return out


def normalize_doi(value: str) -> str:
    """Bare, lowercased DOI: URLs, ``doi:`` prefixes and case all collapse."""
    return (
        re.sub(
            r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)",
            "",
            value.strip(),
            flags=re.IGNORECASE,
        )
        .strip()
        .lower()
    )


def doi_of(entry: BibEntry) -> str:
    return normalize_doi(entry.fields.get("doi", ""))


def title_of(entry: BibEntry) -> str:
    return _clean(re.sub(r"[{}]", "", entry.fields.get("title", "")))
