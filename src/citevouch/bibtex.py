"""A small, forgiving BibTeX reader.

Deliberately not a full BibTeX implementation: this tool needs entry keys, the
fields a manuscript is allowed to name, and reliable line numbers for
reporting.  It handles the constructs that appear in real `.bib` files drawn
from Zotero/JabRef/Google Scholar exports - `@type{key, field = {value}, ...}`,
quoted values, `@string` macros, `#` concatenation, `@comment`, `@preamble`,
and paren-delimited entries - and reports anything it cannot parse instead of
silently dropping it, because a dropped entry would produce a false "missing
citation" later.

The lexical states (`%` comment vs text, `"` string, what closes an entry) live
in ONE machine, :class:`citevouch.biblex.Lex`, shared by the comment stripper
and the scanner.  They used to be two machines; each repair of one silently
re-broke the other (LESSONS.md).  Likewise one entry regex (`ENTRY_HEAD`) is
shared by both passes - the parser cannot disagree with the stripper about
where an entry starts, because then a `%` the stripper trusted the parser
silently lost.

Every stop the parser makes is a Finding:

* an entry whose delimiter never closes ends the parse with `bib-unparsed-entry`
  (high) naming the line;
* a field that cannot be read produces `bib-field-malformed` (medium) and the
  scanner resumes at the next plausible field instead of abandoning the entry;
* an `@` header whose type is not a word (`@in-book{`) is `bib-entry-header-unparsed`
  (medium) and its body is consumed with the report, not dropped;
* text stranded between entries by an early-closing brace is reported, not
  discarded.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, field

from .biblex import OPAQUE_TYPES, Lex
from .model import BibEntry, Finding

# One definition of "an entry starts here", shared by the comment stripper and
# the parser.  The type token is deliberately permissive (`@in-book`, `@misc2`)
# so the stripper tracks the body; the parser then reports types that are not
# plain letters as unusable instead of mis-tokenising the file around them.
ENTRY_HEAD = re.compile(r"@(?P<type>[A-Za-z][A-Za-z0-9_-]*)\s*(?P<open>[{(])")

_KEY = re.compile(r"\s*(?P<key>[^,\s{}()]*)\s*,?")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_:+.\-]*|[0-9]+")
_FIELD_HEAD = re.compile(r"\s*,?\s*([A-Za-z_][A-Za-z0-9_\-]*)\s*=\s*")
# A comma followed by `name =` is where a field can start; used to resume after
# a malformed fragment instead of dropping the rest of the entry.
_NEXT_FIELD = re.compile(r",\s*[A-Za-z_][A-Za-z0-9_\-]*\s*=")
_STRING_DEF = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_\-]*)\s*=\s*")

# BibTeX ignores these entry types; they must never be reported as citations.
_NON_ENTRIES = set(OPAQUE_TYPES)


@dataclass
class BibResult:
    entries: dict[str, BibEntry] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    strings: dict[str, str] = field(default_factory=dict)


def _advance_from(lex: Lex, text: str, i: int) -> tuple[int, bool]:
    """Run ``lex`` over ``text`` starting at ``i`` until the span closes.

    Returns (index just past the closing delimiter, closed?).  ``i`` must point
    at the first character AFTER the opening delimiter; the Lex was constructed
    for that delimiter.
    """
    n = len(text)
    while i < n:
        i, closed = lex.advance(text, i)
        if closed:
            return i, True
    return n, False


def _strip_comments(text: str) -> str:
    """Blank out ``%`` comments that are not field text, preserving lines.

    Which ``%`` are comments is entirely :class:`~citevouch.biblex.Lex`'s
    answer (`comment_here`): between entries and at a normal entry's field
    level, yes; inside a quoted value, inside ``{...}``, or inside a
    ``@comment``/``@string``/``@preamble`` body, no.  The states carry across
    line boundaries - a quoted value can contain a newline, and a string
    opened before one must still be holding the next line's `%`.
    """
    out = []
    lex: Lex | None = None  # the entry we are inside of, if any
    for line in text.splitlines():
        cut = len(line)
        idx = 0
        while idx < len(line):
            if lex is None:
                m = ENTRY_HEAD.match(line, idx)
                if m:
                    lex = Lex(
                        m.group("open"),
                        opaque=m.group("type").lower() in OPAQUE_TYPES,
                    )
                    idx = m.end("open")
                    continue
                if line[idx] == "%":
                    cut = idx
                    break
                idx += 1
                continue
            ch = line[idx]
            if lex.comment_here(ch):
                cut = idx
                break
            idx, closed = lex.advance(line, idx)
            if closed:
                lex = None
        out.append(line[:cut])
    return "\n".join(out)


def _read_field_value(
    text: str, start: int, strings: dict[str, str], missing: list[str]
) -> tuple[str, int, bool]:
    """Read one field value, honouring ``#`` concatenation and macros.

    Returns (value, next position, complete?).  ``complete`` is False when the
    value ran off the end of the text mid-delimiter, which the caller turns
    into a finding; macros that are no `@string` defines go into ``missing``.
    Spans are read with :class:`~citevouch.biblex.Lex`: a braced value is
    opaque text (quotes inside it carry no state), a quoted value honours
    escapes and cannot end on a comma.
    """
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
            end, closed = _advance_from(Lex("{", opaque=True), text, i + 1)
            parts.append(text[i + 1 : end - 1])
            i = end
            if not closed:
                return "".join(parts), i, False
        elif ch == '"':
            # A quoted value: the one machine's escape rule, but its own
            # end condition (the first unescaped `"`).  `Lex(opaque=True)`
            # is the wrong tool here - it never looks at quotes at all - so
            # the scan is spelled out rather than borrowed into a mode it
            # does not have.
            j = i + 1
            found = False
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == '"':
                    found = True
                    break
                j += 1
            parts.append(text[i + 1 : j])
            i = j + 1 if found else n
            if not found:
                return "".join(parts), i, False
        else:
            m = _IDENT.match(text, i)
            if not m:
                break
            token = m.group(0)
            if token.lower() in strings:
                parts.append(strings[token.lower()])
            elif token.isdigit():
                # A bare number is a value of its own (`year = 2026`); it is
                # never a macro, and never worth a finding.
                parts.append(token)
            else:
                missing.append(token)
                parts.append(token)
            i = m.end()
        while i < n and text[i] in " \t\r\n":
            i += 1
        if i < n and text[i] == "#":
            i += 1
            continue
        break
    return "".join(parts), i, True


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

    def report(code: str, message: str, line: int) -> None:
        findings.append(Finding(code=code, message=message, path=path, line=line))

    i = 0
    n = len(text)
    while i < n:
        m = ENTRY_HEAD.search(text, i)
        if m is None:
            remainder = text[i:].strip()
            if remainder:
                report(
                    "bib-entry-header-unparsed",
                    f"{len(remainder)} characters at line {line_of(i)} were between "
                    f"entries and were not read: {remainder[:60]!r}. Usually an "
                    "escaped brace or a missing close-brace closed the previous "
                    "entry too early.",
                    line_of(i),
                )
            break
        if m.start() > i and text[i : m.start()].strip():
            gap = text[i : m.start()].strip()
            report(
                "bib-entry-header-unparsed",
                f"{len(gap)} characters at line {line_of(i)} were between entries "
                f"and were not read: {gap[:60]!r}. Usually an escaped brace or a "
                "missing close-brace closed the previous entry too early.",
                line_of(i),
            )

        etype_raw = m.group("type")
        etype = etype_raw.lower()
        open_ch = m.group("open")
        opaque = etype in OPAQUE_TYPES
        body_start = m.end("open")
        body_end, closed = _advance_from(Lex(open_ch, opaque=opaque), text, body_start)
        entry_line = line_of(m.start())

        if not etype_raw.isalpha():
            # `@in-book{...}`: real BibTeX reads the type up to the delimiter,
            # hyphens included, and then warns "unknown type" - the entry's
            # body must be consumed with that verdict, or the next entry's
            # text would be blamed for a brace that never opened.
            if closed:
                report(
                    "bib-entry-header-unparsed",
                    f"@{etype_raw} at line {entry_line} is not a usable entry type "
                    "(letters only; hyphens and dots break BibTeX too); the entry "
                    "was skipped",
                    entry_line,
                )
                i = body_end
                continue
            report(
                "bib-entry-header-unparsed",
                f"@{etype_raw} at line {entry_line} is not a usable entry type and "
                "never closes; the rest of the file was not read",
                entry_line,
            )
            break

        if not closed:
            report(
                "bib-unparsed-entry",
                f"@{etype} opened at line {entry_line} never closes its {open_ch!r}; "
                "the entries after it could not be read. Check for a missing "
                "closing brace or a brace inside a quoted value.",
                entry_line,
            )
            break

        body = text[body_start : body_end - 1]
        i = body_end

        if etype in _NON_ENTRIES:
            if etype == "string":
                sm = _STRING_DEF.match(body)
                if sm:
                    value, _pos, _ok = _read_field_value(body, sm.end(), strings, [])
                    strings[sm.group(1).lower()] = _clean(value)
            continue

        km = _KEY.match(body)
        key = km.group("key") if km else ""
        if not key:
            report(
                "bib-key-missing",
                f"@{etype} entry at line {entry_line} has no cite key",
                entry_line,
            )
            continue

        fields: dict[str, str] = {}
        pos = km.end() if km else 0
        body_len = len(body)
        while pos < body_len:
            fm = _FIELD_HEAD.match(body, pos)
            if not fm:
                # A fragment we cannot read as `name = value`.  Resume at the
                # next field if the text offers one; otherwise record the
                # leftover and stop.  Silence here is what let a whole entry's
                # year disappear behind one typo without a word.
                remainder = body[pos:].strip(" ,\t\r\n")
                if not remainder:
                    break
                anchor = _NEXT_FIELD.search(body, pos)
                if anchor is None:
                    report(
                        "bib-field-malformed",
                        f"{key}: text after the last readable field was not a "
                        f"field: {remainder[:60]!r}",
                        entry_line,
                    )
                    break
                report(
                    "bib-field-malformed",
                    f"{key}: could not read {body[pos : anchor.start()].strip()[:60]!r} "
                    "as a field; resumed at the next one",
                    entry_line,
                )
                pos = anchor.start() + 1  # resume at the field name after the comma
                continue
            name = fm.group(1).lower()
            missing: list[str] = []
            value, next_pos, ok = _read_field_value(body, fm.end(), strings, missing)
            for macro in missing:
                report(
                    "bib-macro-unknown",
                    f"{key}: field {name!r} uses the macro {macro!r}, which no "
                    "@string defines; the name was kept as literal text",
                    entry_line,
                )
            if not ok:
                report(
                    "bib-field-malformed",
                    f"{key}: field {name!r} never closes its value",
                    entry_line,
                )
            if name in fields:
                report(
                    "bib-field-duplicate",
                    f"{key}: field {name!r} given twice (BibTeX field names are "
                    "case-insensitive); the first value was kept",
                    entry_line,
                )
            else:
                fields[name] = _clean(value)
            if next_pos <= fm.end():
                break
            pos = next_pos
        if key in entries:
            report(
                "bib-duplicate-key",
                f"cite key {key!r} appears more than once; the later entry wins",
                entry_line,
            )
        entries[key] = BibEntry(
            key=key, entry_type=etype, fields=fields, path=path, line=entry_line
        )
    if not entries and text.strip():
        # A file with content in it that yielded no entries at all is a
        # different failure from a file with one bad entry, and it has to be
        # reported as one.  Downstream, an empty bibliography is not "no
        # bibliography": verify skips bib-key-missing entirely when the ledger
        # recorded no entries, so a bibliography nobody could read produced a
        # *quieter* run than one missing a single key.  That is the shape of
        # bug this project exists to refuse - a green run over input that was
        # never read - and a medium finding about an unparsed header does not
        # name it.
        findings.append(
            Finding(
                code="bib-unreadable",
                message=(
                    f"not one entry could be read from {path}, so every reference "
                    "in the manuscript is unchecked against a bibliography that "
                    "is effectively empty. Often the file is not the encoding it "
                    "claims: a UTF-16 save read as UTF-8 gives a replacement "
                    "character and a NUL between every letter."
                ),
                path=path,
                line=1,
            )
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
    """Report required fields that are empty or absent.

    A present-but-empty ``year = {}`` is worse than a missing one - it looks
    filled in to every tool that only checks for the key - so both are reported,
    with different wording.  A missing required field is usually a hand-rolled
    entry or one whose rest was lost to a malformed fragment, and a bibliography
    that is silent about it undercuts every claim built on the entry.
    """
    out: list[Finding] = []
    for key, entry in entries.items():
        for name in REQUIRED_FIELDS.get(entry.entry_type, ()):
            if name in entry.fields:
                if not entry.fields[name].strip():
                    out.append(
                        Finding(
                            code="bib-field-empty",
                            message=f"{key}: field {name!r} exists but is empty",
                            path=entry.path,
                            line=entry.line,
                        )
                    )
            else:
                out.append(
                    Finding(
                        code="bib-field-empty",
                        message=(
                            f"{key}: required field {name!r} for @{entry.entry_type} is missing"
                        ),
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
