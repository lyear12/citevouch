"""Text normalisation used for quote matching.

PDF extraction is messy in ways that are irrelevant to whether a quote is
faithful: line breaks fall mid-sentence, words get hyphenated across a line
break, ligatures arrive as single glyphs, and smart quotes differ between the
manuscript and the extraction.  Normalising both sides collapses all of that
without weakening the check, because the check is about *words*, not layout.

The functions here are pure and total: every input returns a string, so a
caller never has to guess whether normalisation succeeded.
"""

from __future__ import annotations

import re
import unicodedata

# Characters that different tools render differently but mean the same thing.
_EQUIV = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201a": "'",
    "\u201b": "'",
    "\u2032": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u201e": '"',
    "\u201f": '"',
    "\u2033": '"',
    "\u00ab": '"',
    "\u00bb": '"',
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u2015": "-",
    "\u2212": "-",
    "\u00a0": " ",
    "\u2007": " ",
    "\u202f": " ",
    "\u2009": " ",
    "\u200a": " ",
    "\u200b": "",
    "\u200c": "",
    "\u200d": "",
    "\ufeff": "",
    "\u00ad": "",
}

# Hyphenation at a line break: "con-\n struction" -> "construction".  Only a
# lowercase-before/lowercase-after pair is joined, because "pre-\n1990" and
# "Van Eecke-\nBeuls" must keep their hyphen.
_HYPHEN_BREAK = re.compile(r"(?<=[a-z])-\s*\n\s*(?=[a-z])")

_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Normalise for comparison; the result is single-spaced and lowercased-free.

    Case is *not* folded here.  Case folding is decided by the matcher, because
    a report wants to show the original case while an index wants the fold.
    """
    if not text:
        return ""
    out = unicodedata.normalize("NFKC", text)
    out = "".join(_EQUIV.get(ch, ch) for ch in out)
    out = _HYPHEN_BREAK.sub("", out)
    out = _WS.sub(" ", out)
    return out.strip()


def fold(text: str) -> str:
    """Normalised and case-folded, the form actually compared in indexes."""
    return normalize(text).casefold()


def squash(text: str) -> str:
    """Normalised with *all* whitespace removed.

    Used as a last-resort match for text that a PDF extractor ran together
    (common with narrow columns and table cells).
    """
    return re.sub(r"\s+", "", fold(text))


def numbers_in(text: str) -> tuple[str, ...]:
    """Every number the text asserts, in order, as written.

    Handles thousands separators, decimals, percent signs and ranges, so
    "40,688", "48.4%" and "154,391" come back verbatim.  Year-like values are
    kept: a manuscript that says 2019 and a source that says 2018 is exactly
    the kind of drift this tool exists to catch.
    """
    if not text:
        return ()
    pattern = re.compile(r"\d+(?:[,\u00a0]\d{3})*(?:\.\d+)?%?")
    return tuple(m.group(0) for m in pattern.finditer(text))


def canonical_number(token: str) -> str:
    """Strip separators and percent so 1,000 / 1000 / 1 000 compare equal."""
    return token.replace(",", "").replace("\u00a0", "").replace("%", "").strip()
