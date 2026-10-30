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
from pathlib import Path

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

    Digits from every script are folded to ASCII.  NFKC already does this for
    the full-width forms, but *not* for Arabic-Indic, Persian or Devanagari
    digits - ٤ is a normal character to the normaliser, not a compatibility
    variant of 4.  Left alone, an author who quotes a Cairo-press paper in
    ASCII digits against a page whose extraction says ٤٠٦٨٨ gets a text that
    differs in one character, falls through the exact and squashed tiers, and
    lands in the numbers tier - so the tool reports "the words match but the
    numbers differ" about a number that is printed on the page.  That reading
    of the two files is correct and the verdict is wrong, which is the worst
    combination this tool can produce.
    """
    if not text:
        return ""
    out = unicodedata.normalize("NFKC", text)
    out = "".join(_EQUIV.get(ch, ch) for ch in out)
    out = _ascii_digits(out)
    out = _HYPHEN_BREAK.sub("", out)
    out = _WS.sub(" ", out)
    return out.strip()


def _ascii_digits(text: str) -> str:
    """Every decimal digit in any script becomes its ASCII digit.

    `str.isdecimal` is true exactly for the characters `unicodedata.decimal`
    can read, so this needs no table and picks up scripts added later.
    """
    if text.isascii():
        return text
    return "".join(
        str(value) if (value := unicodedata.decimal(ch, None)) is not None else ch
        for ch in text
    )


def fold(text: str) -> str:
    """Normalised and case-folded, the form actually compared in indexes."""
    return normalize(text).casefold()


def squash(text: str) -> str:
    """Normalised with *all* whitespace removed.

    Used as a last-resort match for text that a PDF extractor ran together
    (common with narrow columns and table cells).
    """
    return re.sub(r"\s+", "", fold(text))


# Two number patterns, on purpose, and one test that pins their relation.
#
# REPORT_PATTERN is what a manuscript *asserts*: `numbers_in` and therefore
# `Claim.numbers` and the ledger. A space is not a thousands separator there -
# "2019 2020 2021" is three years, not the garbage tokens "2019 202",
# "0 202", "1" that a space-tolerant scan produces. The ledger must never
# record a number nobody wrote.
#
# MASK_PATTERN additionally accepts a space (and a non-breaking space) between
# digit triples, and exists only to blank digits out when comparing words in
# the numbers tier. Two documents agreeing except on digits must match even
# when one wrote "1,000" and the other's PDF extraction shows "1 000"; there,
# over-masking is harmless because the masked span is discarded either way.
#
# Both patterns accept the Arabic thousands, decimal and percent signs, and
# `\d` already matches every script's decimal digits in Python 3.  A paper
# printed in Cairo writes 4٬0688 with those signs; an author quoting it types
# ASCII digits.  Without this, the words match, the numbers are read as
# "40688" against "٤٠" and "٦٨٨", and the tool reports that the source does not
# contain a number that is printed on the page in front of them - the same
# false accusation the cross-page rule exists to avoid.
_THOUSANDS = "[,\\u00a0\\u066c]"
_DECIMAL = "[.\\u066b]"
REPORT_PATTERN = re.compile(rf"\d+(?:{_THOUSANDS}\d{{3}})*(?:{_DECIMAL}\d+)?[%\u066a]?")
MASK_PATTERN = re.compile(rf"\d+(?:[, \u00a0\u066c]\d{{3}})*(?:{_DECIMAL}\d+)?[%\u066a]?")


def numbers_in(text: str) -> tuple[str, ...]:
    """Every number the text asserts, in order, as written.

    Handles thousands separators, decimals and percent signs, so "40,688",
    "48.4%" and "154,391" come back verbatim.  Year-like values are kept: a
    manuscript that says 2019 and a source that says 2018 is exactly the kind
    of drift this tool exists to catch.  A bare space is not a separator here -
    see the REPORT/MASK split above.
    """
    if not text:
        return ()
    return tuple(m.group(0) for m in REPORT_PATTERN.finditer(text))


def canonical_number(token: str) -> str:
    r"""One spelling per number, so the same value compares equal.

    Three things get normalised, and the first is not an optimisation: digits
    from any script are folded to ASCII.  `\d` matches ٤ and ４ as readily as
    4, so `numbers_in` hands back whichever spelling the document used - and
    without this step a quote written in ASCII digits and a source printed in
    Arabic-Indic ones are two different numbers.  The tool then reports
    `number-absent-in-quote` about a number the author can see on the page,
    which is the one accusation it must never make by mistake.

    `unicodedata.decimal` is the mapping: it returns the value of every
    character in Unicode category Nd and nothing else, so no table is needed
    and a future script needs no change here.
    """
    digits = "".join(
        str(value) if (value := unicodedata.decimal(ch, None)) is not None else ch
        for ch in token
    )
    return (
        digits.replace(",", "")
        .replace("\u00a0", "")
        .replace("\u066c", "")
        .replace("\u066b", ".")
        .replace("\u066a", "")
        .replace("%", "")
        .replace(" ", "")
        .strip()
    )


#: One UTF-8 byte-order mark, as it arrives after decoding.
_BOM = "\ufeff"

#: Byte-order marks as they arrive *before* decoding, longest first, with the
#: codec each one names.  Decoding with the named codec consumes the mark, so
#: the result never starts with it.
_BYTE_BOMS = (
    (b"\x00\x00\xfe\xff", "utf-32"),
    (b"\xff\xfe\x00\x00", "utf-32"),
    (b"\xef\xbb\xbf", "utf-8"),
    (b"\xff\xfe", "utf-16"),
    (b"\xfe\xff", "utf-16"),
)


def _strip_bom(text: str) -> str:
    return text[1:] if text.startswith(_BOM) else text


def _decode_text(raw: bytes) -> str:
    """Decode text bytes the way the program that wrote them meant them.

    Files reach this tool from editors, not from a protocol.  On Windows the
    default "Unicode" save in Notepad is UTF-16, and Excel exports UTF-16 too;
    a byte-order mark is how they say so.  Decoding those bytes as UTF-8 does
    not fail loudly - it produces one replacement character and then a NUL
    between every letter, which the rest of the pipeline treats as text:

    * a bibliography saved that way parsed to zero entries, and since the
      report only names entries it read, the run finished with exit 0 and a
      medium finding about an "unparsed header" - quieter than the missing-key
      error It would have raised if the file had been read correctly.

    With no mark to go on, a NUL byte is the tell: no text file this tool reads
    contains one, and a file of 16-bit code units is mostly NULs on one side of
    every pair.  The threshold is deliberately high, because guessing wrong on
    a genuinely binary file only replaces one kind of noise with another.
    """
    for mark, codec in _BYTE_BOMS:
        if raw.startswith(mark):
            return _strip_bom(raw.decode(codec, errors="replace"))
    head = raw[:4096]
    if b"\x00" in head:
        pairs = len(head) // 2
        if pairs:
            if head[1::2].count(0) > pairs * 0.6:
                return _strip_bom(raw.decode("utf-16-le", errors="replace"))
            if head[0::2].count(0) > pairs * 0.6:
                return _strip_bom(raw.decode("utf-16-be", errors="replace"))
    return _strip_bom(raw.decode("utf-8", errors="replace"))


def read_text(path: Path | str) -> str:
    """Read a text file for this tool, without its byte-order mark.

    Notepad, Excel and PowerShell's ``>`` all write a UTF-8 BOM by default, and
    a BOM is not whitespace: it is a real character at the start of the file.
    Every reader that treats the first line as syntax then fails on a file the
    author believes is fine, and reports it as something else:

    * a manuscript beginning with ``\ufeff`` hid a well-formed claim block, so
      the run reported ``claim-block-unclosed`` and ``no-claim-blocks`` for a
      file whose block was closed on the line below it;
    * a bibliography beginning with one reported an unparsed header at line 1
      and then ``bib-key-missing`` for a key sitting in that file.

    The BOM carries no information the rest of the pipeline uses - it only says
    "this file is UTF-8" - so removing it at the boundary is lossless.  It is
    removed here rather than at each call site because the call sites are the
    four ways this bug came back.
    """
    return _decode_text(Path(path).read_bytes())
