"""Lexical states BibTeX shares between the comment stripper and the scanner.

One implementation, on purpose.  The comment stripper and the entry scanner must
agree on what is inside a string and what closes an entry, or a ``%`` that one
of them treats as text the other treats as comment - and that disagreement is
how one stray brace once swallowed thirty-eight entries (LESSONS.md), and how a
later "fix" re-broke the first one by deciding quote-ness for only one of the
two passes.  Two functions disagreeing about a state machine is a standing
invitation to diverge; they advance one machine here.

One machine, one idea: ``brace`` counts how deep we are inside ``{...}``, and
``in_quote`` says we are inside a double-quoted value at the entry's own level.
A field value in braces is scanned by this same machine (``opaque``): only the
brace nesting decides where it ends, quotes inside it are text.  The entry's
own delimiter - ``{`` or ``(`` - is what ``closed`` reports at the end.

The rules, and the real file shape each one exists for:

* ``%`` outside every entry is a comment.
* ``%`` inside ``{...}`` (a field value, or the whole body of a
  ``@comment``/``@string``/``@preamble``) is ordinary text:
  ``note = {78.5% above CRF}``, ``@comment{ was 50% of it }``.
* ``%`` at a normal entry's own level, outside quotes, is a comment:
  ``year = 2020, % added later``.
* ``%`` inside a double-quoted value at that same level is text:
  ``note = "78.5% above CRF"``.  A deliberate departure from classic BibTeX
  (which would call it a comment and truncate the entry); Zotero/JabRef
  exports put real data in those quotes, and the tool must never read a
  percent as an instruction.
* A backslash escapes exactly the character after it, so ``\\{`` is a literal
  brace that never moves the count.
* A ``(``/``)`` inside ``{...}`` never closes a paren-delimited entry.
"""

from __future__ import annotations

CLOSE_OF = {"{": "}", "(": ")"}

# Entry types whose entire body is opaque text: only the brace nesting decides
# where they end, so their closing delimiter survives whatever the body holds.
OPAQUE_TYPES = frozenset({"comment", "preamble", "string"})


class Lex:
    """The one lexical state machine of a BibTeX entry (or an opaque ``{...}``).

    Construct it at the opening delimiter with ``brace=1`` for a normal entry
    (``Lex("{")`` / ``Lex("(")``) or as a fresh opaque span for a field value
    (``Lex("{", opaque=True)`` starting at depth 0).  ``advance`` returns the
    index to continue from and whether the span closed.
    """

    __slots__ = ("brace", "close_ch", "delim", "in_quote", "opaque")

    def __init__(self, delim: str = "{", *, opaque: bool = False) -> None:
        if delim not in CLOSE_OF:
            raise ValueError(f"unknown delimiter {delim!r}")
        self.delim = delim
        self.close_ch = CLOSE_OF[delim]
        self.opaque = opaque
        # A normal entry starts with its delimiter already open; an opaque
        # field-value span is created before its `{` is fed in, at depth 0.
        self.brace = 1
        self.in_quote = False

    def advance(self, text: str, i: int) -> tuple[int, bool]:
        """Consume the character at ``i``; return (next index, span closed?).

        The caller stores the returned index and asks again from there; it must
        not advance on its own, or an escape that swallows a delimiter will
        still be counted.
        """
        ch = text[i]
        if ch == "\\":
            return i + 2, False  # escapes the next character, whatever it is
        if self.opaque:
            if ch == "{":
                self.brace += 1
            elif ch == "}":
                self.brace -= 1
                if self.brace == 0:
                    return i + 1, True
            return i + 1, False
        # normal entry body
        if ch == '"' and self.brace == 1 and not self.in_quote:
            self.in_quote = True
            return i + 1, False
        if self.in_quote:
            if ch == '"':
                self.in_quote = False
            return i + 1, False
        if ch == "{":
            self.brace += 1
        elif self.delim == "{":
            if ch == "}":
                self.brace -= 1
                if self.brace == 0:
                    return i + 1, True
        else:  # paren-delimited entry: `)` closes only outside brace groups
            if ch == "}":
                self.brace -= 1
            elif ch == ")" and self.brace == 1:
                return i + 1, True
        return i + 1, False

    def comment_here(self, ch: str) -> bool:
        """Is ``%`` a comment right now?

        Only at a normal entry's own level (brace 1, outside quotes, not
        opaque).  Between entries the caller handles it before a Lex exists.
        """
        return ch == "%" and not self.in_quote and not self.opaque and self.brace == 1
