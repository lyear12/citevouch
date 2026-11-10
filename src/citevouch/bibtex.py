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
from .textnorm import count_of, verb_for

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
    # Where each definition was written.  `parse_bib_group` needs it because a
    # finding carries the coordinate a reader follows: two macros that disagree
    # between the same two files both used to be reported at line 1 of the
    # later file, `_deconflict` keys on (code, claim, path, line) and kept the
    # first, so the author fixed `j`, re-ran, and met `n`.  Measured: two
    # conflicts in, one finding out.
    string_lines: dict[str, int] = field(default_factory=dict)


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


def parse_bib(
    text: str, path: str = "refs.bib", known_strings: dict[str, str] | None = None
) -> BibResult:
    findings: list[Finding] = []
    entries: dict[str, BibEntry] = {}
    # `--bib` takes more than one file and the shape that needs it - a shared
    # `macros.bib` beside the `refs.bib` that uses its `@string`s - used to do
    # nothing at all: each file was parsed alone, so `journal = acm` in
    # `refs.bib` was reported as an undefined macro while the definition sat
    # on line 1 of the other file, and the message named the one thing that
    # was not true ("no @string defines them").  Measured for all three
    # orders: macros first, refs first, refs alone - all the same complaint.
    # The group of files is one bibliography, so the strings travel with it.
    strings: dict[str, str] = dict(known_strings) if known_strings else {}
    # `@string` / `@preamble` / `@comment` are read, not lost.  Counted so the
    # "no entries here" finding can say what the file does hold instead of
    # claiming nobody could read it.
    definitions = 0
    string_lines: dict[str, int] = {}
    text = _strip_comments(text)
    line_starts = [0] + [i + 1 for i, ch in enumerate(text) if ch == "\n"]

    def line_of(pos: int) -> int:
        return bisect.bisect_right(line_starts, pos)

    # Repeated fields are collected per entry and reported once, the way
    # `bib-key-unused` reports a set rather than each member.  Reporting each
    # one separately looked right and was not: every finding for one entry
    # carries that entry's opening line, so downstream deduplication - which
    # keys on (code, claim, path, line) - kept the first and dropped the rest.
    # A bibliography with three doubled fields in one entry produced one line;
    # the author fixed it, re-ran, and met the second.  The set is the fact.
    repeated: dict[str, list[str]] = {}

    # Undefined macros have the same shape and the same fix.  Grouped by the
    # field that used them, so the message still says which field to look at.
    unknown_macros: dict[str, dict[str, list[str]]] = {}

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
                    f"{count_of(len(remainder), 'character')} at line {line_of(i)} "
                    f"{verb_for(len(remainder))} between entries and "
                    f"{verb_for(len(remainder))} not read: {remainder[:60]!r}. Usually an "
                    "escaped brace or a missing close-brace closed the previous "
                    "entry too early.",
                    line_of(i),
                )
            break
        if m.start() > i and text[i : m.start()].strip():
            gap = text[i : m.start()].strip()
            report(
                "bib-entry-header-unparsed",
                f"{count_of(len(gap), 'character')} at line {line_of(i)} "
                f"{verb_for(len(gap))} between entries "
                f"and {verb_for(len(gap))} not read: {gap[:60]!r}. Usually an escaped brace or a "
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
            definitions += 1
            if etype == "string":
                sm = _STRING_DEF.match(body)
                if sm:
                    value, _pos, _ok = _read_field_value(body, sm.end(), strings, [])
                    name = sm.group(1).lower()
                    strings[name] = _clean(value)
                    string_lines[name] = entry_line
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
        malformed: list[str] = []
        while pos < body_len:
            fm = _FIELD_HEAD.match(body, pos)
            if not fm:
                # A fragment we cannot read as `name = value`.  Resume at the
                # next field if the text offers one; otherwise record the
                # leftover and stop.  Silence here is what let a whole entry's
                # year disappear behind one typo without a word.
                #
                # Collected rather than reported, for the reason the doubled
                # fields and the undefined macros are: every finding for an
                # entry carries the entry's line, so the duplicate pass would
                # keep the first fragment and hide the rest.
                remainder = body[pos:].strip(" ,\t\r\n")
                if not remainder:
                    break
                anchor = _NEXT_FIELD.search(body, pos)
                if anchor is None:
                    malformed.append(
                        f"the text after the last readable field, {remainder[:60]!r}"
                    )
                    break
                malformed.append(f"{body[pos : anchor.start()].strip()[:60]!r}")
                pos = anchor.start() + 1  # resume at the field name after the comma
                continue
            name = fm.group(1).lower()
            missing: list[str] = []
            value, next_pos, ok = _read_field_value(body, fm.end(), strings, missing)
            if missing:
                # Same shape as the doubled fields below: one finding per macro
                # shared this entry's line, so the duplicate pass kept the first
                # and the author never learned about the rest.  Grouped by
                # field so the message can still say which one used it.
                unknown_macros.setdefault(key, {}).setdefault(name, []).extend(missing)
            if not ok:
                malformed.append(f"field {name!r} never closes its value")
            if name in fields:
                repeated.setdefault(key, []).append(name)
            else:
                fields[name] = _clean(value)
            if next_pos <= fm.end():
                break
            pos = next_pos
        doubled = repeated.pop(key, [])
        if doubled:
            names = ", ".join(repr(name) for name in sorted(doubled))
            report(
                "bib-field-duplicate",
                f"{key}: {count_of(len(doubled), 'field')} given twice ({names}); "
                "BibTeX field names are case-insensitive, so the first value of "
                "each was kept",
                entry_line,
            )
        if malformed:
            parts = "; ".join(malformed)
            report(
                "bib-field-malformed",
                f"{key}: {count_of(len(malformed), 'fragment')} "
                f"could not be read as a field: {parts}",
                entry_line,
            )
        used_unknown = unknown_macros.pop(key, {})
        if used_unknown:
            # One finding for the entry, naming every field and every macro.
            # Grouping by field looked tidier and lost data for the same reason
            # the per-macro loop did: findings for one entry share its line, so
            # the duplicate pass kept the first field and hid the others.
            parts = []
            total = 0
            for field_name in sorted(used_unknown):
                macros = sorted(set(used_unknown[field_name]))
                total += len(macros)
                names = ", ".join(repr(macro) for macro in macros)
                parts.append(f"{field_name!r} uses {names}")
            report(
                "bib-macro-unknown",
                f"{key}: {count_of(total, 'undefined macro', 'undefined macros')} "
                f"in {count_of(len(parts), 'field')} ({'; '.join(parts)}); no "
                "@string defines them, so each name was kept as literal text",
                entry_line,
            )
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
        #
        # But "no entries" is answered by two different facts, and this branch
        # used to assert the worse one for both.  A file whose every byte was
        # read and which happens to hold only definitions - a shared
        # `@string` macro file sitting beside the entries, which is what
        # multiple `--bib` flags are for - was reported as unreadable prose in
        # a wrong encoding.  Measured, with `macros.bib` holding two `@string`
        # definitions and `refs.bib` answering every key::
        #
        #     $ citevouch check manuscript.md --root . \
        #           --bib macros.bib --bib refs.bib
        #     [high] bib-unreadable at macros.bib:1: not one entry could be
        #            read from macros.bib ... Often the file is not the
        #            encoding it claims: a UTF-16 save read as UTF-8 ...
        #     exit 1
        #
        # The file is ASCII, it parsed completely, both macros came through,
        # and no reference in the manuscript went unanswered.  The author is
        # sent to change an encoding that is already right, at the severity
        # that stops a build.
        #
        # So the question is not "were there entries" but "is there text this
        # parse could not account for".  An unparsed header is exactly that
        # answer, and it is already known here.
        # Text this parse could not account for comes in exactly two shapes: a
        # gap between entries that would not parse, and an entry that never
        # closes (which also makes everything after it unread).  Either one
        # means the file lost something; definitions alone do not.
        unaccounted = any(
            finding.code in ("bib-entry-header-unparsed", "bib-unparsed-entry")
            for finding in findings
        )
        if unaccounted:
            findings.append(
                Finding(
                    code="bib-unreadable",
                    message=(
                        f"not one entry could be read from {path}, so every reference "
                        "in the manuscript is unchecked against a bibliography that "
                        "is effectively empty."
                        + (
                            f" {count_of(definitions, 'definition')} did parse, so the "
                            "text named above is what stopped the entries from being read."
                            if definitions
                            else ""
                        )
                        + " Often the file is not the encoding it claims: a UTF-16 "
                        "save read as UTF-8 gives a replacement character and a NUL "
                        "between every letter."
                    ),
                    path=path,
                    line=1,
                )
            )
        else:
            findings.append(
                Finding(
                    code="bib-no-entries",
                    message=(
                        f"{path} holds {count_of(definitions, 'definition')} and no "
                        "entries, so no citation key can be answered from it. A file "
                        "that only defines @string macros is meant to be passed next "
                        "to one that holds the entries: `--bib macros.bib --bib "
                        "refs.bib`."
                    ),
                    path=path,
                    line=1,
                )
            )
    return BibResult(
        entries=entries,
        findings=findings,
        strings=strings,
        string_lines=string_lines,
    )


def parse_bib_group(files: list[tuple[str, str]]) -> list[BibResult]:
    """Parse a `--bib` group as one bibliography, in either order.

    `(text, recorded_path)` pairs, in the order the flags were given.  A file
    that defines only `@string`s is useful precisely because another file in
    the group uses them, and which one was named first is not a fact about the
    bibliography.  So the group is read twice: the first pass collects every
    definition, the second parses each file against all of them and is the
    pass whose findings, entries and strings are returned.

    Reading each file alone was the bug this exists to stop - `macros.bib`
    beside `refs.bib` reported `journal = acm` as an undefined macro for all
    three orders (macros first, refs first, refs alone), with the definition
    on line 1 of the other file.

    Two files that define one macro *differently* are a different fact and now
    get their own finding.  Measured before it existed, on `a.bib` defining
    `j = "Journal A"` and `c.bib` defining `j = "Journal C"`:

        a.bib c.bib e.bib -> journal = 'Journal C'   (no finding)
        c.bib a.bib e.bib -> journal = 'Journal A'   (no finding)

    So which work the entry named depended on the order of two flags and
    nothing said so.  `bib-duplicate-key` already refuses that shape for
    entries; a macro is the same fact one level up, so the message says what
    the entry resolved to and that the group disagreed.

    The finding names the line each side wrote, and hangs off the file that
    won: two macros that disagree between the same two files are two things to
    fix, and a coordinate shared between them hides the second one.
    """
    known: dict[str, str] = {}
    where: dict[str, tuple[str, str, int]] = {}
    conflicts: list[tuple[str, Finding]] = []
    for text, path in files:
        parsed = parse_bib(text, path)
        for name, value in parsed.strings.items():
            line = parsed.string_lines.get(name, 1)
            if name in known:
                if known[name] == value:
                    continue
                earlier_path, earlier_value, earlier_line = where[name]
                conflicts.append(
                    (
                        path,
                        Finding(
                            code="bib-macro-redefined",
                            message=(
                                f"@string {name!r} is defined as "
                                f"{earlier_value!r} in {earlier_path} line "
                                f"{earlier_line} and as {value!r} in {path} line "
                                f"{line}; the definition from {path} is the one "
                                "used, so which work a field built from this "
                                "macro names depends on the order of the --bib "
                                "flags"
                            ),
                            path=path,
                            line=line,
                        ),
                    )
                )
            where[name] = (path, value, line)
            known[name] = value
    parsed = [parse_bib(text, path, known) for text, path in files]
    by_path = {path: result for result, (text, path) in zip(parsed, files, strict=True)}
    for path, finding in conflicts:
        # Each conflict hangs off the file that won it, at the line that file
        # wrote the definition.  Attaching every conflict to the first result at
        # line 1 - which is what this did while the shape was new - put two
        # different macros on one coordinate, and `_deconflict` keys on
        # (code, claim, path, line): the author was told about `j`, fixed it,
        # re-ran, and met `n`.  Measured: two conflicts in, one finding out.
        by_path.get(path, parsed[0]).findings.append(finding)
    return parsed


REQUIRED_FIELDS = {
    "article": ("author", "title", "journal", "year"),
    "book": ("author", "title", "publisher", "year"),
    "inproceedings": ("author", "title", "booktitle", "year"),
    "incollection": ("author", "title", "booktitle", "year"),
    "phdthesis": ("author", "title", "school", "year"),
    "mastersthesis": ("author", "title", "school", "year"),
    "techreport": ("author", "title", "institution", "year"),
}


def merge_entries(into: dict[str, BibEntry], entries: dict[str, BibEntry]) -> list[Finding]:
    """Merge ``entries`` into ``into``, reporting a key that both sides define.

    ``parse_bib`` reports a key defined twice *inside one file*.  Two files
    each defining it once produced no finding at all, because the merge was
    ``dict.update``: the later file silently replaced the earlier one, so which
    entry a claim was judged against depended on the order of the ``--bib``
    flags.  That order is an accident of the command line, not a statement
    about the work.

    Measured before this existed, with ``a.bib`` defining ``knuth2020`` as a
    book and ``b.bib`` defining the same key as a different article::

        $ citevouch scan manuscript.md --bib a.bib --bib b.bib
        (no finding, exit 0, and the ledger kept b.bib's entry)

    The finding is keyed to the file that won, so two clashes against two
    different files stay two findings rather than collapsing into one.  The
    later entry still wins - reporting the clash must not change the verdict,
    or the fix would decide the answer instead of the evidence.
    """
    findings: list[Finding] = []
    for key, entry in entries.items():
        earlier = into.get(key)
        if earlier is not None and earlier.path != entry.path:
            findings.append(
                Finding(
                    code="bib-duplicate-key",
                    message=(
                        f"cite key {key!r} is defined in {earlier.path} and again "
                        f"in {entry.path}; the entry from {entry.path} is the one "
                        "that was kept, so which work this claim rests on depends "
                        "on the order of the --bib flags"
                    ),
                    path=entry.path,
                    line=entry.line,
                )
            )
        into[key] = entry
    return findings


def field_findings(entries: dict[str, BibEntry]) -> list[Finding]:
    """Report required fields that are empty or absent.

    A present-but-empty ``year = {}`` is worse than a missing one - it looks
    filled in to every tool that only checks for the key - so both are reported,
    with different wording.  A missing required field is usually a hand-rolled
    entry or one whose rest was lost to a malformed fragment, and a bibliography
    that is silent about it undercuts every claim built on the entry.

    One entry yields one line, so the duplicate pass keys every finding about it
    to the same coordinate.  Reported field by field, an entry missing four
    required fields produced four findings of which one survived: the author
    filled that one in, ran again, and met the next.  Measured before this:
    ``raw: 8, dedup: 2`` for two entries missing four fields each.  The parts
    are named inside one message instead, the way the doubled fields and the
    undefined macros already are.
    """
    out: list[Finding] = []
    for key, entry in entries.items():
        missing: list[str] = []
        empty: list[str] = []
        for name in REQUIRED_FIELDS.get(entry.entry_type, ()):
            if name in entry.fields:
                if not entry.fields[name].strip():
                    empty.append(name)
            else:
                missing.append(name)
        parts: list[str] = []
        if missing:
            parts.append(
                f"{count_of(len(missing), 'required field')} missing: {_names(missing)}"
            )
        if empty:
            parts.append(
                f"{count_of(len(empty), 'required field')} present but empty: {_names(empty)}"
            )
        if parts:
            out.append(
                Finding(
                    code="bib-field-empty",
                    message=f"{key}: {'; '.join(parts)}",
                    path=entry.path,
                    line=entry.line,
                )
            )
    return out


def _names(fields: list[str]) -> str:
    """``'author', 'title' and 'year'`` - quoted, because they are field names."""
    quoted = [repr(name) for name in fields]
    if len(quoted) == 1:
        return quoted[0]
    return ", ".join(quoted[:-1]) + f" and {quoted[-1]}"


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
