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
from .textnorm import quote_numbers

_FENCE_OPEN = re.compile(r"^```claim\b(?P<attrs>.*)$")
_FENCE_CLOSE = re.compile(r"^```\s*$")
_ANY_FENCE = re.compile(r"^(?P<ticks>`{3,}|~{3,})(?P<info>.*)$")
_HTML_OPEN = re.compile(r"^<!--\s*claim\s*:?\s*(?P<attrs>.*)$")
_HTML_CLOSE = re.compile(r"^\s*-->\s*$")
# A block starts a new construct and can never be a quote's continuation.
# These two are the ones `_continues_one_line_html` was missing: a heading and
# a thematic break both began blocks in CommonMark, and both were read as the
# quote of the one-line comment above them. The indent is capped at three
# spaces and a heading needs a space after its `#`s, so `#hashtag` stays text;
# a break needs the same character three times with nothing else on the line,
# so `--- and then some words` stays text too.
_ATX_HEADING = re.compile(r"^[ \t]{0,3}#{1,6}(?:[ \t]|$)")
_THEMATIC_BREAK = re.compile(
    r"^[ \t]{0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$"
)
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
# The `page` cell is the one column of a claim row that is not free text, so
# getting its alphabet wrong loses the row instead of misreading it.  It held
# `\d+|-|` once, which read a page number and a "no hint" dash and nothing
# else: a row whose author wrote `1-2` matched no claim at all, and a file
# holding a good row plus that one reported `1 claim - 1 verified` with no line
# mentioning the second.  Alone, the same row made the file look empty:
# `no-claim-blocks ... This file has none`, over a file that holds one.
#
# The fence dialect has answered this value since it was written - `page=1-2`
# reports `page-unreadable ... the hint is ignored and the quote will be
# located by search`, and the claim is verified anyway.  So the cell now admits
# anything that looks like a number or a run of them joined by a dash: a range,
# a backwards range, an open-ended one, and the en/em dashes a word processor
# substitutes.  `int()` still refuses each of them, which is the point - the
# row is read, and the hint the tool cannot apply is the thing it complains
# about.
#
# Deliberately not "any text": a results table's header row
# (`| model | setting | 84 | f1 | note |`) already reads as a claim, and
# widening this cell would make every such row one.
#
# The same argument made the cell too narrow in the other direction.  A page
# hint is prose as often as it is a bare number - `p. 3`, `pp. 3-4`,
# `page 5`, `1,2` - and every one of those deleted the whole row: measured in
# a project whose page held the quote, `check` printed
# `no-claim-blocks ... This file has none`, exit 1, over a file holding one.
# The fence dialect answers all of them the same honest way, so the cell now
# spells out the shapes a hint takes: an optional `p`/`pp`/`page`/`pages`
# prefix with its full stop, then digits with the separators a person writes
# between them (space, comma, dash, en dash, em dash), or a bare dash for "no
# hint", or nothing at all.
#
# A cell holding any other letter is still not a page, which is what keeps a
# results table a results table: its third column is `score`, `f1`, `done` or a
# bare number, and only the bare number was ever read as a claim.
#
# Roman numerals are the same bargain as the bare number, not a new one.  A
# book's front matter is numbered i, ii, iii, so `| c1 | paper | iv | ... |`
# deleted the whole row: measured over a file whose only claim it was, `check`
# printed `no-claim-blocks ... This file has none`, exit 1, while the fence
# dialect answered `page=iv` with `page-unreadable`, medium, and verified the
# quote anyway.  The alphabet is restricted to i, v, x and l and each run has
# to be a canonical numeral, so the words that share those letters stay words:
# `ill` is not a numeral and `mix` is not in the alphabet, and neither matches.
# The price is the price the bare number already charges - a results table whose
# third column is a roman numeral reads as claims - and it is paid on purpose,
# because a deleted row is silence while a read row naming an unfindable source
# is a sentence the author can answer.
_ROMAN_SEPARATORS = r"[ \t]*[-\u2013\u2014,][ \t]*"
_ROMAN_RUN = (
    r"(?=[ivxlIVXL])"
    r"(?:[Xx][Cc]|[Xx][Ll]|[Ll]?[Xx]{0,3})?"
    r"(?:[Ii][Xx]|[Ii][Vv]|[Vv]?[Ii]{0,3})"
)
_PAGE_CELL = (
    r"(?:(?:[Pp]|[Pp][Pp]|[Pp]age|[Pp]ages)[ \t]*\.?[ \t]*)?"
    r"(?:[0-9](?:[0-9\s,\u2013\u2014-]*[0-9\u2013\u2014-])?"
    r"|" + _ROMAN_RUN + r"(?:" + _ROMAN_SEPARATORS + _ROMAN_RUN + r")*)"
    r"|[-\u2013\u2014]|"
)
_TABLE_CLAIM = re.compile(
    r"^\|\s*(?P<id>[A-Za-z0-9_.:-]*)\s*\|\s*(?P<source>" + _CELL + r")\s*\|"
    r"\s*(?P<page>" + _PAGE_CELL + r")\s*\|\s*(?P<quote>" + _CELL + r")\s*\|"
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
# A `key:` spelling on the opening line.  The body of a claim block writes its
# fields with colons - `quote: |`, `id: c1` - so an author who writes the page
# hint one line up the same way is doing what the format taught them, and the
# opening line only understands `key=value`.  Before this pattern the hint was
# parsed away and dropped in silence.
#
# Measured on a two-page source whose quote is on page 1, asking for page 9:
#
#     ```claim id=c1 source=paper page=9    -> [high] page-out-of-range
#     ```claim id=c1 source=paper page: 9   -> [info] quote-found page 1, exit 0
#
# The second block asked about page 9 and got an answer from page 1, with no
# line saying the question had been dropped.  `id: c1` was worse: the bare
# token became the claim's name, so findings said `(id:)` - a name the author
# never wrote - and the ledger recorded it.
#
# Anchored on a token start so a colon inside a value is not a field:
# `source=weird:name` keeps its colon and `10:30` is not a key.  Quoted values
# are blanked before the scan, because `source="a file: 2.txt"` is one value.
_OPENING_COLON_KEY = re.compile(r"(?:^|\s)(?P<key>[A-Za-z][A-Za-z0-9_-]*)\s*:")
_QUOTED = re.compile(r"\"[^\"]*\"|'[^']*'")

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
#: A GFM delimiter row: cells of dashes with optional alignment colons.
#:
#: It decides one thing, and that thing used to be got wrong: the row directly
#: above a delimiter row is the table's *header*, and a header holds column
#: labels.  Measured on a manuscript whose results table had a prose cell in
#: its header:
#:
#:     | model | setting | 84 | We report the mean over five seeds | note |
#:     |-------|---------|----|------------------------------------|------|
#:
#: `check` printed `[info] quote-found at manuscript.md:3 (model): quote found
#: on page 1` - it certified a column label as a verified quotation, because
#: the page happened to print those words.  A header row is now named and not
#: judged.
_DELIMITER_ROW = re.compile(
    r"^[ \t]{0,3}\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*$"
)


def _is_delimiter_row(line: str) -> bool:
    """Whether ``line`` is the delimiter row that makes the row above a header."""
    return _DELIMITER_ROW.match(line) is not None


def _is_header_row(lines: list[str], index: int) -> bool:
    """Whether line ``index`` (0-based) is a table header.

    True only when the line is shaped like a table claim *and* the next line is
    a delimiter row.  The documented header (`| id | source | page | quote |
    claim |`) never reaches here: its third cell is the word `page`, so the
    table-claim pattern already refuses it.

    A delimiter row is not a header.  GFM allows a delimiter cell to be a
    single dash, so `|-|-|-|-|-|` satisfies `_TABLE_CLAIM` with `-` for the id,
    the source and the page; with a claim-shaped row above it this function
    called the delimiter a header, and without one the delimiter was read as a
    claim named `-` that names source `-`.  Measured before the fix, on a table
    whose delimiter is written that way: `[high] source-missing at
    manuscript.md:2 (-): claim - names source='-' but no entry in sources.toml`,
    `2 claims - 1 verified, 0 moved, 1 missing`, exit 1 - over a table that is
    correct.  So the delimiter is refused here, and the caller refuses it as a
    claim too.
    """
    if _is_delimiter_row(lines[index]):
        return False
    if _TABLE_CLAIM.match(lines[index]) is None:
        return False
    return index + 1 < len(lines) and _is_delimiter_row(lines[index + 1])


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
#
# One list, because the opening line and the body are two spellings of the same
# statement: a key this format has is one it has in both places.  The body path
# already refused to drop a field it did not know (`_KEYISH`); the opening line
# read every `key=value` token, kept it in a dict, and then `_claim_from` looked
# up only the six names below - so a misspelt one was parsed, stored and never
# read.  Measured on a project whose quote sits on page 1 and again on page 3:
#
#     ```claim id=c1 source=paper page=3   -> quote-found page 3
#     ```claim id=c1 source=paper pgae=3   -> quote-found page 1, exit 0, no finding
#
# The author asked for page 3, the answer came from page 1, and no line in the
# output said the hint had been ignored.
_KNOWN_ATTRIBUTES: frozenset[str] = frozenset({"id", "source", "ref", "cite", "page", "marker"})
_ATTRIBUTE_KEY = re.compile(
    r"^\s*(?P<key>"
    + "|".join(sorted(map(re.escape, _KNOWN_ATTRIBUTES)))
    + r")\s*:\s*(?P<rest>.*)$"
)

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

# What may stand in front of a credibility mark.  The convention is a *prefix*:
# a line that opens with 【原文】 is an assertion carrying its provenance, and a
# line that merely names the notation is prose about the notation.
#
# The scan used to ask `marker in line`, so it reported both.  Measured on the
# demo's own manuscript, line 3, which only explains the convention:
#
#     > 这份节选保留了原档的【原文】/【实测】/【推测】三级标记约定，只是把
#
# `citevouch scan demo/manuscript.md` accused that sentence of claiming
# something without evidence, next to the two lines (52 and 54) that really do
# carry a bare mark.  A false accusation costs more than a missed one here: the
# reader who opens line 3 to fix it finds a remark about typography.
#
# The alternatives are what Markdown puts in front of a sentence: indentation
# (including the ideographic space), block quotes, bullets, ordered-list
# numbers and emphasis.
_MARKER_DECORATION = re.compile(r"^(?:[ \t\u3000]+|>|[-*+](?=\s)|\d+[.)](?=\s)|\*\*|__|\*|_)+")


@dataclass
class ParseResult:
    claims: list[Claim]
    findings: list[Finding]
    # 1-based inclusive line spans the parser consumed: claim blocks in any
    # dialect, and also plain code fences, because prose inside a sample must
    # not be reported as an unread claim opener.
    spans: list[tuple[int, int]] = field(default_factory=list)
    # The subset of ``spans`` that opened as a claim block - accepted or
    # refused, since both are blocks the author wrote and the file holds.
    #
    # The two lists are not a detail. ``spans`` answers *where may prose not
    # be read* (a ````python` sample is such a place, and a `claim` line
    # inside it is sample text, not a block); ``claim_spans`` answers *how
    # many claim blocks does this file hold*. Counting spans for the second
    # question reported a manuscript with one claim and one ````python`
    # sample as `2 claim blocks - 1 of which this run could not check`, and
    # no finding anywhere explained the second block, because there was no
    # second block.
    claim_spans: list[tuple[int, int]] = field(default_factory=list)

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
        # `claim-table-header` does not belong here. Every other `claim-` code
        # describes a block the author wrote and the parser could not use, so
        # the reader already knows why nothing was checked. A header row is not
        # a block at all, and a file whose only table row is its header checked
        # nothing at all - exactly like an empty file, which exits 1 with
        # `no-claim-blocks`. Counting the header as an explanation made that
        # file exit 0 with `0 claims`, so a CI gate over a manuscript whose
        # header happened to be claim-shaped passed while nothing was verified.
        explained = any(
            f.code.startswith("claim-") and f.code != "claim-table-header"
            for f in self.findings
        )
        return not self.claims and not explained


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
            # `id: c1` is a field written with a colon, not a positional id.
            # Reading it as one made the claim's name the literal `id:`, so the
            # report said `(id:)` and the ledger stored a name nobody wrote.
            if token and not _KEYISH.match(head[0]):
                out["id"] = token
    return out


def _opening_colon_findings(blob: str, path: str, line: int) -> list[Finding]:
    """Name a field on the opening line that is spelled with a colon.

    The body of a claim block is a mapping - ``quote:``, ``id:``, ``page:`` -
    and the opening line is a list of ``key=value`` tokens. Two spellings of
    the same statement in one construct is a format an author will get wrong
    exactly once, in the direction the body taught them.

    Measured on a two-page source whose quote is on page 1:

    ```text
    ```claim id=c1 source=paper page=9    -> [high] page-out-of-range
    ```claim id=c1 source=paper page: 9   -> [info] quote-found page 1, exit 0
    ```

    So this reports; it does not guess. Applying the key would be a format
    decision (is ``page: 9`` a hint or a note?), and a wrong guess is worse
    than the silence this replaces. The sentence names both spellings, since
    the author cannot tell from ``page`` alone whether the key or the
    separator was wrong.
    """
    scanned = _QUOTED.sub(" ", blob or "")
    known = ", ".join(sorted(_KNOWN_ATTRIBUTES))
    found: list[Finding] = []
    seen: set[str] = set()
    for m in _OPENING_COLON_KEY.finditer(scanned):
        key = m.group("key").lower()
        if key in seen:
            continue
        seen.add(key)
        if key in _KNOWN_ATTRIBUTES:
            advice = f"{key}= (not {key}:)"
        else:
            near = _nearest_attribute(key)
            if near is None:
                continue
            advice = f"{key}=, if {near}= was meant"
        found.append(
            Finding(
                code="claim-field-unknown",
                message=(
                    f"this claim block's opening line writes {key}: like a body "
                    f"field, but the opening line only reads key=value; it was "
                    f"ignored, so write {advice} - the attributes are " + known
                ),
                path=path,
                line=line,
            )
        )
    return found


def _unknown_attr_findings(blob: str, path: str, line: int) -> list[Finding]:
    """Name an attribute on the opening line that is spelled like a key we know.

    Two conditions, and both are load-bearing:

    * **It is a near miss.** One edit away - a transposition, a dropped letter,
      another letter - from one of the six keys this format has. That is what
      separates ``pgae=3`` (a typo for ``page``) from ``data-x=3`` (some other
      tool's annotation, or a key from a later format). Reporting every unknown
      token would fire on files that are not claiming anything, and a finding
      nobody can act on is how a real one gets ignored.
    * **The right spelling is absent.** A block that writes ``ref=`` and also
      carries an unrelated ``cite=`` lookalike has not lost a statement: the
      one it needed is right there. Silence is correct there, because the
      output already reads the key the author meant.

    The misspelt key is still *dropped* rather than applied - guessing which
    key an author meant is a format decision, not a reader's call, and a guess
    that is wrong is worse than the silence this replaces.
    """
    written = [
        (m.group("tight") or m.group("loose")).lower() for m in _ATTR.finditer(blob or "")
    ]
    present = set(written)
    found: list[Finding] = []
    seen: set[str] = set()
    for key in written:
        if key in _KNOWN_ATTRIBUTES or key in seen:
            continue
        seen.add(key)
        near = _nearest_attribute(key)
        if near is None or near in present:
            continue
        found.append(
            Finding(
                code="claim-field-unknown",
                message=(
                    f"this claim block writes {key}=, which is not an attribute "
                    f"this format has; it was ignored, and {near}= was not read "
                    "either - the six attributes are " + ", ".join(sorted(_KNOWN_ATTRIBUTES))
                ),
                path=path,
                line=line,
            )
        )
    return found


def _nearest_attribute(key: str) -> str | None:
    """The known key within one edit of ``key``; ``None`` when there is none."""
    best: str | None = None
    best_distance = 2
    for known in sorted(_KNOWN_ATTRIBUTES):
        distance = _edit_distance(key, known)
        if distance < best_distance:
            best, best_distance = known, distance
    return best


def _edit_distance(left: str, right: str) -> int:
    """How many single-letter slips separate the two, transpositions counting one.

    Plain Levenshtein scores a swap as two edits, and ``pgae`` for ``page`` is
    the most common typo there is - the fingers know both letters and hit them
    in the other order. Scoring it two would put the likeliest misspelling of
    the likeliest attribute outside the net, which is the one case this check
    exists for. So a swapped pair costs one, and the cap stays at two.
    """
    if abs(len(left) - len(right)) > 2:
        return 3
    rows = len(left) + 1
    cols = len(right) + 1
    table = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        table[i][0] = i
    for j in range(cols):
        table[0][j] = j
    for i in range(1, rows):
        for j in range(1, cols):
            cost = 0 if left[i - 1] == right[j - 1] else 1
            table[i][j] = min(
                table[i - 1][j] + 1,
                table[i][j - 1] + 1,
                table[i - 1][j - 1] + cost,
            )
            if i > 1 and j > 1 and left[i - 1] == right[j - 2] and left[i - 2] == right[j - 1]:
                table[i][j] = min(table[i][j], table[i - 2][j - 2] + 1)
    return int(table[-1][-1])


#: Attribute spellings that name one thing.  Reading them as alternatives is
#: what makes the format forgiving; *silently* dropping one of two different
#: values is what makes a manuscript say something no run ever applied.
_ALIASED_FIELDS: tuple[tuple[str, str], ...] = (("ref", "cite"),)


def _conflicting_fields(attrs: dict[str, str], path: str, line: int) -> list[Finding]:
    """Name an aliased pair written twice with two different values."""
    out: list[Finding] = []
    for used, also in _ALIASED_FIELDS:
        if used not in attrs or also not in attrs:
            continue
        chosen, dropped = attrs[used], attrs[also]
        if chosen == dropped:
            continue
        out.append(
            Finding(
                code="claim-field-conflict",
                message=(
                    f"this claim block writes both {used}={chosen!r} and "
                    f"{also}={dropped!r}, which are two spellings of one "
                    f"attribute; {used} was used and {also} was dropped - keep "
                    "one of them"
                ),
                path=path,
                line=line,
            )
        )
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
    # Two spellings of one statement, written with different values.  The
    # format accepts both (`ref=` and `cite=`), and the lookup has to pick one -
    # so the pair is a statement the author made twice and the reader applied
    # once.  Measured before this finding existed, with a quote verbatim on
    # page 1 and `refs.bib` holding knuth2020:
    #
    #     ref=phantom cite=knuth2020  ->  [high] bib-key-missing 'phantom'
    #     cite=phantom ref=knuth2020  ->  exit 0, no finding at all
    #
    # One direction accused the author on the strength of a string they may
    # have meant to delete; the other dropped that string without a word.
    findings.extend(_conflicting_fields(attrs, path, line))
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
        # ``quote_numbers``, so this writer and ``Ledger.from_json``'s reader
        # are one function.  They were two copies of the same idea once: this
        # line used ``CANON_PATTERN`` while the reader kept whatever the file
        # held, so a ledger written before 0.22.16 - when a grouping space
        # split one number into two - made the verifier accuse a *verbatim*
        # quote of a number the page does not contain.
        numbers=quote_numbers(quote),
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


# The tag names CommonMark calls block-level.  A line that opens or closes one
# of these starts a block; anything else in angle brackets is inline HTML and
# belongs to the sentence it sits in.  Spelled out because the list is the
# definition: a name missing here is a name whose line gets read as a quote.
_HTML_BLOCK_TAGS = (
    "address article aside base basefont blockquote body caption center col "
    "colgroup dd details dialog dir div dl dt fieldset figcaption figure footer "
    "form frame frameset h1 h2 h3 h4 h5 h6 head header hr html iframe legend li "
    "link main menu menuitem nav noframes ol optgroup option p param search "
    "section summary table tbody td tfoot th thead title tr track ul"
).split()

# CommonMark HTML block type 1 (a raw-text element) and type 6 (one of the
# block-level names above), matched the way CommonMark matches them: at the
# start of the line, after at most three spaces, followed by space, `>`, `/`
# or the end of the line.  ``<DIV>`` counts; ``<divs>`` does not.
_HTML_BLOCK_START = re.compile(
    r"^[ \t]{0,3}(?:"
    r"<(?:script|pre|style|textarea)(?:[ \t>]|$)"
    r"|</?(?:" + "|".join(_HTML_BLOCK_TAGS) + r")(?:[ \t/>]|$)"
    r")",
    re.IGNORECASE,
)

# CommonMark HTML block type 7: a complete open or closing tag alone on a line.
# This is what makes ``<span>`` on its own line a block while ``<span>`` inside
# a sentence is not - the tag has to be the whole line, attributes and all.
_HTML_BLOCK_ALONE = re.compile(
    r"^[ \t]{0,3}(?:"
    r"</[A-Za-z][A-Za-z0-9-]*[ \t]*>"
    r"|<[A-Za-z][A-Za-z0-9-]*(?:[ \t]+[A-Za-z_:][A-Za-z0-9_.:-]*"
    r"(?:[ \t]*=[ \t]*(?:[^ \t\"'=<>`]+|'[^']*'|\"[^\"]*\"))?)*"
    r"[ \t]*/?>"
    r")[ \t]*$"
)


def _starts_an_html_block(line: str) -> bool:
    """True when ``line`` opens an HTML block rather than continuing prose."""
    return bool(_HTML_BLOCK_START.match(line) or _HTML_BLOCK_ALONE.match(line))


def _continues_one_line_html(line: str) -> bool:
    """True while ``line`` still belongs to an already-closed ``<!-- claim``.

    The one-line dialect has no terminator of its own, so the block ends the
    way a Markdown paragraph does: at a blank line, or where the next construct
    starts. Erring short here would silently drop the quote; erring long would
    swallow a following claim, so every opener counts as a boundary.

    A heading and a thematic break were the two constructs missing from that
    list, and both were read as the quote. Measured with a page printing
    ``We collected 40,688 examples from the corpus.`` and a manuscript holding
    one documented claim:

        <!-- claim: c1 source=paper page=1 -->
        ## Methods
        -> [high] quote-missing at manuscript.md:1 (c1): ## Methods — quote not found

        <!-- claim: c1 source=paper page=1 -->
        ---
        -> [high] quote-missing at manuscript.md:1 (c1): --- — quote not found

    Both sentences send the author to their PDF to look for a heading and a
    horizontal rule their source never printed. The claim holds no quote at
    all, and the true finding is ``claim-uncheckable``, which at least points
    at the author's own block.

    HTML was the third family.  A claim comment written directly above a
    ``</div>``, a ``<br>``, an ``<hr>`` or an image was read with that tag as
    its quote, and every one of those produced the same accusation against a
    page that prints none of them.  The rule is CommonMark's, not "anything in
    angle brackets": a block-level tag name starts a block, a complete tag
    alone on a line starts a block, and a tag inside a sentence stays in the
    sentence - ``a <b>bold</b> word`` is prose and ``5 < 7`` is arithmetic.
    """
    if not line.strip():
        return False
    if _ANY_FENCE.match(line) or _HTML_OPEN.match(line) or _TABLE_CLAIM.match(line):
        return False
    if _ATX_HEADING.match(line) or _THEMATIC_BREAK.match(line):
        return False
    if _starts_an_html_block(line):
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
    claim_spans: list[tuple[int, int]] = []
    seen: dict[str, int] = {}
    lines = text.splitlines()

    def accept(claim: Claim | None, more: list[Finding], first: int, last: int) -> None:
        findings.extend(more)
        spans.append((first, last))
        claim_spans.append((first, last))
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
            opened_with = _unknown_attr_findings(m.group("attrs"), path, start_line)
            opened_with.extend(_opening_colon_findings(m.group("attrs"), path, start_line))
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
            more.extend(opened_with)
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
                head = attrs_text
                attrs = _attrs(attrs_text)
                body = []
                j = i + 1
                while j < len(lines) and not _HTML_CLOSE.match(lines[j]):
                    body.append(lines[j])
                    j += 1
                closed = j < len(lines)
            quote, claim_text, in_body, unknown = _split_body(body)
            claim, more = _claim_from(attrs, quote, claim_text, path, start_line, in_body)
            more.extend(_unknown_attr_findings(head, path, start_line))
            more.extend(_opening_colon_findings(head, path, start_line))
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
            if _is_delimiter_row(line):
                # A delimiter row is punctuation between the header and the
                # body of a table, never a claim and never something to
                # explain.  `_is_header_row` refuses it as a header for the
                # same reason.
                i += 1
                continue
            if _is_header_row(lines, i):
                findings.append(_table_header_finding(line, path, start_line))
                i += 1
                continue
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
    return ParseResult(claims=claims, findings=findings, spans=spans, claim_spans=claim_spans)


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
    for index, line in enumerate(lines):
        number = index + 1
        if covered[number]:
            continue
        if _is_delimiter_row(line):
            # A delimiter row satisfies the table-claim pattern (`|-|-|-|-|-|`
            # is a legal GFM delimiter whose cells are all single dashes), so
            # this pass called it a claim block "inside a blockquote, a list
            # item or an indent" - three things it is not.  It is punctuation,
            # and the caller already refuses it as a claim.
            continue
        if _is_header_row(lines, index):
            # Naming the header is `_table_header_finding`'s job, and it does
            # not call the row a claim block.  This pass would say it is one
            # "inside a blockquote, a list item or an indent", which is false.
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


def _table_header_finding(line: str, path: str, line_number: int) -> Finding:
    """Name a table header row that is shaped exactly like a claim row.

    The row is not a claim, so it is not judged: certifying a column label as a
    quotation is the worst thing this tool can do.  It is not silent either,
    because the same shape with different intent - a real claim written above
    the delimiter row - would otherwise disappear without a word.
    """
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    claim_id = cells[0] if cells else ""
    who = f"claim {claim_id}: " if claim_id else ""
    return Finding(
        code="claim-table-header",
        message=(
            f"{who}line {line_number} is the header of the table below it, so its "
            "cells are column labels and were not checked against any source. "
            "A header row sits directly above the `|---|` delimiter row; a row "
            "you meant as a claim belongs under it"
        ),
        claim_id=claim_id,
        path=path,
        line=line_number,
    )


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


def _at_the_margin(raw: str, margin: int) -> bool:
    """Is this line a sibling key of the block, rather than quote content?

    A claim body is a YAML mapping, and the rule that decides which lines are
    keys of it has two halves.  The comment in ``_split_body`` writes both:
    "in a ``quote: |`` block a line at the left margin is a sibling key and
    never continuation text".  Only the second half was implemented - every
    key pattern is anchored on ``^\\s*``, which matches the continuation lines
    too - so an *indented* line of the quote that happened to read
    ``source: ...`` was read as an attribute, and it ended the quote.

    Measured on a block whose first sentence really is on the page and whose
    second sentence is nowhere in the source::

        quote: |
          We collected 154,391 examples from the corpus.
          We also invented a sentence that is nowhere in the paper.
                                                  -> [high] quote-missing

        quote: |
          We collected 154,391 examples from the corpus.
          source: our own dataset
          We also invented a sentence that is nowhere in the paper.
                                                  -> [info] quote-found, exit 0

    One indented field-shaped line turned a fabricated quotation into a
    verified one.  ``page:``, ``id:``, ``ref:``, ``cite:``, ``marker:``,
    ``claim:`` and ``numbers:`` cut it just as cleanly; ``Page:`` (a key this
    format does not have) did not, because ``_KEYISH`` already had this guard.

    ``margin`` is the indentation of the block's own keys, so a claim block
    written one indent into a list item still reads its own ``quote:`` line.
    Anything deeper than that is content: ``quote: |`` collects what is under
    it, and "under it" includes lines that begin with a word and a colon.
    """
    return len(raw) - len(raw.lstrip()) <= margin


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
    # The block's own indentation: the least-indented line that reads as a
    # field.  `quote:` in a list item is written two spaces in, and its content
    # four; both are legitimate, and the margin is what separates them.
    margin = min(
        (len(raw) - len(raw.lstrip()) for raw in body if _FIELD_KEY.match(raw)),
        default=0,
    )
    if has_keys:
        fields: dict[str, list[str]] = {}
        current = ""
        for index, raw in enumerate(body, start=1):
            m = _BODY_KEY.match(raw) if _at_the_margin(raw, margin) else None
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
            other = _ATTRIBUTE_KEY.match(raw) if _at_the_margin(raw, margin) else None
            if other:
                # `source: paper` under the fence is the same statement as
                # `source=paper` on it.  Reading it as quote text is how a
                # correct passage came back as `quote-missing`.
                attributes[other.group("key").lower()] = _unquote(other.group("rest").strip())
                current = ""
                continue
            keyish = _KEYISH.match(raw)
            if keyish is not None and _at_the_margin(raw, margin):
                # A field line whose name this format does not have.  Read as
                # quote text it becomes a false accusation, and skipped in
                # silence it becomes a check the author believes ran.
                #
                # `current` has to be cleared here for the same reason the
                # branch above clears it: a block scalar's lines belong to the
                # key over them, and this key has no owner to collect them.
                # Measured without this line, on a quote verbatim on page 1:
                #
                #     quote: |
                #       We collected 40,688 examples from the corpus.
                #     text: |
                #       我们收集了例句
                #
                #   -> claim.quote == 'We collected 40,688 examples from the
                #      corpus.\n我们收集了例句' and then [high] quote-missing,
                #      in the same run that printed [medium] claim-field-unknown
                #      saying the value was "neither applied nor searched as
                #      part of the quote".  The sentence was false, and the
                #      author had to read both halves to see it.
                unknown.append((index, keyish.group("key")))
                current = ""
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


def _paragraph_above(lines: list[str], first: int, covered: set[int]) -> int | None:
    """Line number of the first line of the paragraph that ends above *first*.

    ``None`` when there is no prose there, or when the paragraph runs into
    another claim block - a mark may head the paragraph beside a block, not
    reach through one.
    """
    index = first - 1
    while index >= 1 and not lines[index - 1].strip():
        index -= 1
    top: int | None = None
    while index >= 1 and lines[index - 1].strip() and index not in covered:
        top = index
        index -= 1
    return top


def _paragraph_below(lines: list[str], last: int, covered: set[int]) -> int | None:
    """Line number of the first line of the paragraph that starts below *last*."""
    index = last + 1
    while index <= len(lines) and not lines[index - 1].strip():
        index += 1
    if index > len(lines) or index in covered:
        return None
    return index


def _bound_mark_lines(
    lines: list[str],
    claims: list[Claim],
    spans: list[tuple[int, int]],
    markers: tuple[str, ...],
) -> set[int]:
    """Lines holding a credibility mark that a neighbouring claim block names.

    A block writes ``marker=【原文】`` to say which mark vouches for the
    assertion it documents, and the mark heads the paragraph next to the block.
    That statement went unread for the whole life of the attribute: measured on

        【原文】PyFCG 3.3 installs cleanly.

        ```claim id=c1 source=a marker=【原文】
        quote: |
          PyFCG 3.3 installs cleanly.
        ```

    the ledger recorded ``marker='【原文】'`` for ``c1`` and ``scan`` printed
    ``[low] claim-without-evidence … the 【原文】 mark on this line has no claim
    block`` about line 1 in the same run.

    Two guards keep this from becoming a way to silence a real finding.  The
    mark has to be the *neighbouring* paragraph's first line, not somewhere
    further up the page, and it has to be wanted by exactly one block: two
    marks either side of one block are two readings of the same sentence, and
    guessing which one it vouches for would hide the other.
    """
    wanted: dict[int, list[str]] = {}
    for claim in claims:
        if not claim.marker or claim.marker not in markers:
            continue
        span = next(
            (s for s in spans if s[0] <= claim.line <= s[1]),
            (claim.line, claim.line),
        )
        covered = _cover(spans)
        candidates = [
            line
            for line in (
                _paragraph_above(lines, span[0], covered),
                _paragraph_below(lines, span[1], covered),
            )
            if line is not None and line not in covered
        ]
        matching = [
            line
            for line in candidates
            if _MARKER_DECORATION.sub("", lines[line - 1], count=1).startswith(claim.marker)
        ]
        if len(matching) == 1:
            wanted.setdefault(matching[0], []).append(claim.id)
    return {line for line, ids in wanted.items() if len(ids) == 1}


def scan_unbound_markers(
    text: str,
    path: str = "manuscript.md",
    markers: tuple[str, ...] = DEFAULT_MARKERS,
    spans: list[tuple[int, int]] | None = None,
    claims: list[Claim] | None = None,
) -> list[Finding]:
    """Find credibility markers that are *not* inside a claim block.

    A sentence marked 【原文】 that carries no machine-checkable quote is the
    single most common way a manuscript looks verified while not being
    verified.  Reporting it is the point of this function.

    ``spans`` comes from :class:`ParseResult`; passing it keeps documented
    claims from being reported as unbound.  ``claims`` does the same for a mark
    a block explicitly names with ``marker=`` — see :func:`_bound_mark_lines`.

    For a mark to count it has to *open* the line, once the Markdown that may
    stand in front of a sentence is set aside — see ``_MARKER_DECORATION``.
    Asking whether the characters appear anywhere in the line reported a
    sentence that only described the convention::

        > 这份节选保留了原档的【原文】/【实测】/【推测】三级标记约定，只是把

    That is a remark about the notation, and the advice the finding would earn
    (bind a claim block to it) is advice to annotate a glossary.  A mark that
    trails a sentence is described here as a miss, deliberately: the convention
    heads the assertion it vouches for.
    """
    covered = _cover(spans or [])
    bound = _bound_mark_lines(text.splitlines(), claims or [], spans or [], markers)
    findings: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if lineno in covered or lineno in bound:
            continue
        opening = _MARKER_DECORATION.sub("", line, count=1)
        for marker in markers:
            if opening.startswith(marker):
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
