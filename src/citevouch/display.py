"""Blank out the parts of a manuscript that are *displayed* rather than written.

Markdown has four ways to show a passage instead of writing it: a fenced block,
a code span, an HTML comment, and an indented block.  A `[@key]` inside one is a
specimen of the syntax, not a place the author cites that key, and the markers
themselves are not words in the sentence around them.

Measured on a manuscript whose page prints `SAMPLE` word for word, with `ghost`
a key that has no local file:

* every one of the six shapes below made `draft` write ``line 2: ghost - no
  local file: not in sources.toml, no `file` field in the bibliography, and no
  file named after the key`` - an author told their own example has a missing
  paper;
* the fenced and commented shapes also dropped the enclosing paragraph from
  ``1 claim block(s) proposed (1 verbatim)`` to ``0 claim block(s) proposed
  (0 verbatim)``, because ```` ``` ```` and `<!--` travelled into the sentence
  `draft` compared with the page.

The masked text keeps every offset and every newline, so a position found in it
is the same position in the manuscript and line numbers do not move.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

NL = "\n"

#: A fence line, CommonMark's up-to-three-space indent included.
_FENCE_LINE = re.compile(r"^[ \t]{0,3}(?P<ticks>`{3,}|~{3,})(?P<info>.*)$")

#: A line indented enough to be a code block rather than a paragraph.
_INDENTED_LINE = re.compile(r"^(?: {4}|\t)")

#: One run of backticks, which is what a code span is delimited by.
_BACKTICK_RUN = re.compile(r"`+")

_COMMENT_START = "<!--"
_COMMENT_END = "-->"


def _lines_of(text: str) -> list[tuple[int, str]]:
    """Every line with the offset it starts at.

    ``str.splitlines`` is not used: it also splits on form feeds and Unicode
    line separators, neither of which is a line break in a Markdown file, and
    the offsets have to match the text the caller is holding.
    """
    out: list[tuple[int, str]] = []
    start = 0
    while True:
        end = text.find(NL, start)
        if end < 0:
            out.append((start, text[start:]))
            return out
        out.append((start, text[start:end]))
        start = end + 1


def _closes(line: str, ticks: str) -> bool:
    """True when ``line`` closes a fence opened with ``ticks``.

    The same rule `manuscript._closes` applies: at least as many of the same
    character, with nothing after them.  A tilde fence is closed by tildes.
    """
    match = _FENCE_LINE.match(line)
    if not match:
        return False
    run = match.group("ticks")
    return run[0] == ticks[0] and len(run) >= len(ticks) and not match.group("info").strip()


def _line_spans(text: str) -> list[tuple[int, int]]:
    """The spans of fenced blocks and indented blocks, in file order."""
    spans: list[tuple[int, int]] = []
    lines = _lines_of(text)
    index = 0
    while index < len(lines):
        start, line = lines[index]
        opener = _FENCE_LINE.match(line)
        if opener:
            ticks = opener.group("ticks")
            close = index + 1
            while close < len(lines) and not _closes(lines[close][1], ticks):
                close += 1
            if close >= len(lines):
                # An unclosed fence runs to the end of the file in CommonMark,
                # and the parser says so separately; here it is still displayed.
                spans.append((start, len(text)))
                return spans
            spans.append((start, lines[close][0] + len(lines[close][1])))
            index = close + 1
            continue
        # `manuscript` and `_CONTAINER_MARKER` already take the CommonMark
        # stance that four spaces is a code block; a block also has to start a
        # paragraph, or an indented continuation line of a list item would be
        # read as sample text and its prose would vanish from the run.
        if _INDENTED_LINE.match(line) and (index == 0 or not lines[index - 1][1].strip()):
            close = index
            while close < len(lines) and (
                not lines[close][1].strip() or _INDENTED_LINE.match(lines[close][1])
            ):
                close += 1
            end = lines[close - 1][0] + len(lines[close - 1][1]) if close else start
            spans.append((start, end))
            index = close
            continue
        index += 1
    return spans


def _comment_spans(text: str) -> list[tuple[int, int]]:
    """Every HTML comment, whole.  An unterminated one runs to the end."""
    spans: list[tuple[int, int]] = []
    index = 0
    while True:
        start = text.find(_COMMENT_START, index)
        if start < 0:
            return spans
        end = text.find(_COMMENT_END, start + len(_COMMENT_START))
        end = len(text) if end < 0 else end + len(_COMMENT_END)
        spans.append((start, end))
        index = end


def _code_span_spans(text: str) -> list[tuple[int, int]]:
    """Every code span, delimiters included.

    A span closes on a run of exactly as many backticks as opened it, which is
    CommonMark's rule and the one that lets ``a `[@k]` b`` be displayed while
    an unmatched backtick stays an ordinary character.
    """
    runs = [(match.start(), match.end()) for match in _BACKTICK_RUN.finditer(text)]
    spans: list[tuple[int, int]] = []
    index = 0
    while index < len(runs):
        start, end = runs[index]
        length = end - start
        for following in range(index + 1, len(runs)):
            other = runs[following]
            if other[1] - other[0] == length:
                spans.append((start, other[1]))
                index = following + 1
                break
        else:
            index += 1
    return spans


def display_spans(text: str) -> list[tuple[int, int]]:
    """Every region of ``text`` that a Markdown reader sees as a specimen."""
    spans = _line_spans(text)
    spans.extend(_comment_spans(text))
    spans.extend(_code_span_spans(text))
    return spans


def blank(text: str, spans: Iterable[tuple[int, int]]) -> str:
    """``text`` with every region in ``spans`` blanked, offsets unchanged."""
    out = list(text)
    for start, end in spans:
        for index in range(max(0, start), min(end, len(out))):
            if out[index] not in (NL, "\r"):
                out[index] = " "
    return "".join(out)


def mask(text: str) -> str:
    """``text`` with every displayed region blanked, offsets unchanged."""
    spans = display_spans(text)
    if not spans:
        return text
    return blank(text, spans)
