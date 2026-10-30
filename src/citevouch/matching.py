"""Locating a quote inside a source: exact, whitespace-free, number-blind, fuzzy.

Four tiers, tried in order, each strictly weaker than the last:

1. **exact** — the normalised quote appears in the normalised page text *at
   word boundaries*: "in the paper" must not match inside "a bin the papers";
2. **squashed** — the quote appears once *all* whitespace is removed, which
   rescues text an extractor ran together or split across columns.  The
   boundary is gone at this tier by construction, so a minimum length keeps it
   from certifying a coincidence;
3. **numbers** — every number in the quote is masked out on both sides and the
   *words* still match at full length.  This is the tier that separates "you
   typed the statistic wrong" from "the quote is not in this document";
4. **fuzzy** — a sliding token-window comparison, used only to say "the quote
   looks like the source but is not present verbatim", which is reported as a
   medium-severity finding rather than silently accepted.

Neither tier 3 nor tier 4 ever upgrades a claim to verified.  They turn a flat
"not found" into an actionable "these digits differ" / "these words differ".
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from .sources import PageText
from .textnorm import MASK_PATTERN, fold, squash

# A quote must be at least this long before fuzzy matching is allowed to opine.
# Below it, short quotes match too many places for a similarity score to mean
# anything.
MIN_FUZZY_TOKENS = 5
FUZZY_THRESHOLD = 0.82

# The squashed tier has no word boundaries to lean on, so it must clear a
# length floor.  The floor is counted in *characters* but the budget differs by
# script: a Chinese character carries roughly a word's worth of information, so
# six of them is a phrase while six Latin letters is noise.  Chars for CJK, and
# the Latin floor for everything else (see _squash_floor).
MIN_SQUASHED_CHARS = 12
MIN_SQUASHED_CHARS_CJK = 4

# Characters whose presence means "count the CJK floor".  This is a coverage
# question, not a language detector: one CJK character anywhere in the quote is
# enough that a 12-character floor would refuse a phrase a reader would call a
# phrase.
_CJK_RANGES = ((0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF), (0x3040, 0x30FF))


def _has_cjk(text: str) -> bool:
    return any(any(lo <= ord(ch) <= hi for lo, hi in _CJK_RANGES) for ch in text)


def _squash_floor(quote_squashed: str) -> int:
    return MIN_SQUASHED_CHARS_CJK if _has_cjk(quote_squashed) else MIN_SQUASHED_CHARS


# After number-masking, a quote needs at least this many non-placeholder
# characters before its containment counts as "the words match".  Without it,
# a pure-number quote ("48.4%") masks to one placeholder and "matches" any page
# that happens to contain a number anywhere - and the finding that comes out of
# that claims the words matched, which is false.  Twelve is the count that
# cannot be met by "of the and" alone: enough real words to be a sentence.
MIN_MASKED_CHARS = 12

_NUMBER = MASK_PATTERN
_NUMBER_PLACEHOLDER = "\x00"
_TOKEN = re.compile(r"[^\s]+")


def _is_word_char(ch: str) -> bool:
    """Is ``ch`` a letter or digit that a quote must not be cut through?

    ``str.isalnum()`` is the whole rule, and it is the rule because this tool
    reads Chinese as often as English: CJK punctuation (``。：、「``) is not
    alphanumeric, so a quote ending at a full stop matches at the boundary,
    while ``前``/``后`` around it still block a cut through a word.  A
    hand-written ``[0-9A-Za-z\\u00aa-\\uffff]`` class says the opposite - it
    calls every CJK character a word character, which makes the after-boundary
    of "…很小。" impossible and turned every short Chinese quote into a false
    ``quote-missing`` (run by the critic as blocker B2, on this project's own
    bilingual demo).
    """
    return ch.isalnum()


@dataclass
class Match:
    tier: str  # "exact" | "squashed" | "numbers" | "fuzzy" | "none"
    page: int | None = None
    similarity: float = 0.0
    context: str = ""
    reason: str = ""

    @property
    def found(self) -> bool:
        """True only for the tiers that may be called verified."""
        return self.tier in ("exact", "squashed")


def mask_numbers(text: str) -> str:
    """Replace every number with a placeholder so two texts can be compared."""
    return _NUMBER.sub(_NUMBER_PLACEHOLDER, text)


def number_spans(text: str) -> list[tuple[str, int]]:
    """The (token, start) pairs mask_numbers will replace.

    Exposed for the test that pins the two number patterns down: every span
    `numbers_in` may report (REPORT_PATTERN) must be a span the numbers tier
    masks (MASK_PATTERN), or the tier would reason about digits nobody claimed.
    The converse is deliberately not required - MASK additionally swallows a
    space thousands-separator ("1 000") that REPORT refuses to invent, because
    masking too much is harmless and reporting a number nobody wrote is not.
    """
    return [(m.group(0), m.start()) for m in _NUMBER.finditer(text)]


def _bounded_pages(page: PageText, needle: str) -> list[int]:
    """Start offsets of `needle` in the page's folded text at word boundaries.

    A match whose neighbours are letters or digits is a match *inside* words:
    "in the paper" inside "a bin the papers" reads as a quote that exists
    nowhere.  ``_is_word_char`` decides what a word character is, and it uses
    ``str.isalnum`` so the rule holds for CJK text too.

    A side that the needle already ends in punctuation is unconstrained: if the
    quote's last character is ``。`` or ``,``, no text after it can make the
    quote a fragment of a longer word, and CJK prose has no spaces to put
    there.  Requiring a non-word character after a full stop turned every quoted
    Chinese sentence into a squashed-tier match - correct by the letter of the
    old rule, wrong about what the sentence is.
    """
    hits: list[int] = []
    haystack = page.folded
    open_start = not needle or not _is_word_char(needle[0])
    open_end = not needle or not _is_word_char(needle[-1])
    start = haystack.find(needle)
    while start >= 0:
        before_ok = open_start or start == 0 or not _is_word_char(haystack[start - 1])
        end = start + len(needle)
        after_ok = open_end or end >= len(haystack) or not _is_word_char(haystack[end])
        if before_ok and after_ok:
            hits.append(start)
        start = haystack.find(needle, start + 1)
    return hits


def _context(page_text: str, needle_index: int, needle_len: int, width: int = 120) -> str:
    """A one-line excerpt around the hit, folded to a single line."""
    start = max(0, needle_index - width // 2)
    end = min(len(page_text), needle_index + needle_len + width // 2)
    snippet = page_text[start:end].replace("\n", " ")
    snippet = re.sub(r"\s+", " ", snippet).strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(page_text):
        snippet = snippet + "…"
    return snippet


def find_in_pages(
    quote: str,
    pages: list[PageText],
    page_hint: int | None = None,
) -> Match:
    """Locate ``quote`` in ``pages``, preferring ``page_hint`` if it is given.

    The hint is a *preference*, not a filter: manuscripts routinely say "p. 214"
    when the PDF's internal numbering starts at the cover.  When the hinted page
    misses, the search widens to every page and the result reports where it
    actually was, which is what makes drift visible.
    """
    quote_norm = fold(quote)
    if not quote_norm.strip():
        return Match(tier="none", reason="quote is empty")
    quote_squash = squash(quote)

    order: list[int] = []
    if page_hint is not None and 1 <= page_hint <= len(pages):
        order.append(page_hint - 1)
    order.extend(i for i in range(len(pages)) if i not in order)

    # Exact: bounded on both ends (see _bounded_pages), so a quote that exists
    # only as a fragment of other words never counts as present.
    for index in order:
        page = pages[index]
        hits = _bounded_pages(page, quote_norm)
        if hits:
            return Match(
                tier="exact",
                page=page.number,
                similarity=1.0,
                context=_context(page.folded, hits[0], len(quote_norm)),
            )

    for index in order:
        page = pages[index]
        flat = squash(page.text)
        pos = flat.find(quote_squash)
        if quote_squash and pos >= 0:
            if len(quote_squash) < _squash_floor(quote_squash):
                # No boundaries to lean on and too short to be anything else:
                # refuse the tier rather than certify a coincidence.  The
                # exact tier above already tried this quote where it could be
                # trusted; a short quote that only matches unbounded is
                # reported as absent, which is the strict direction.  The
                # floor is smaller for CJK, where a handful of characters is
                # already a phrase.
                return Match(
                    tier="none",
                    reason=(
                        "quote not found at word boundaries; it is too short to "
                        "trust a whitespace-free match"
                    ),
                )
            return Match(
                tier="squashed",
                page=page.number,
                similarity=1.0,
                context=_flat_context(page.text, flat, pos, len(quote_squash)),
                reason="matched only after removing all whitespace",
            )

    # Number-blind comparison: identical words, different digits.  Reported as
    # its own tier so the finding can say "the number is wrong" instead of
    # "the quote is missing", which is the whole difference between a typo and
    # a fabrication.  It requires real words to match: a quote that masks away
    # to (nearly) nothing would otherwise "match" any page holding any number.
    if _NUMBER.search(quote):
        masked_quote = squash(mask_numbers(quote))
        real_chars = masked_quote.replace(_NUMBER_PLACEHOLDER, "")
        if len(real_chars) >= MIN_MASKED_CHARS:
            for index in order:
                page = pages[index]
                flat = squash(mask_numbers(page.text))
                pos = flat.find(masked_quote)
                if pos >= 0:
                    return Match(
                        tier="numbers",
                        page=page.number,
                        # 1.0 is not a comparison, it is the tier's definition:
                        # the masked quote was found verbatim, so every
                        # non-placeholder character matched by construction.
                        # This used to run difflib.SequenceMatcher over those
                        # same two strings and return whatever ratio it got,
                        # which could only ever be 1.0 - a computation that
                        # looked like evidence and could not fail.
                        similarity=1.0,
                        context=_flat_context(page.text, flat, pos, len(masked_quote)),
                        reason=(
                            "the words around the numbers match this page but the numbers "
                            "in the quote differ from the source"
                        ),
                    )

    needle_tokens = _TOKEN.findall(quote_norm)
    if len(needle_tokens) < MIN_FUZZY_TOKENS:
        return Match(tier="none", reason="quote not found (too short for a fuzzy comparison)")

    best = Match(tier="none", reason="quote not found")
    for index in order:
        page = pages[index]
        candidate, score = _best_window(page.folded, needle_tokens)
        if score > best.similarity:
            best = Match(
                tier="fuzzy",
                page=page.number,
                similarity=score,
                context=candidate,
                reason=(
                    "the source has a similar passage but not these words verbatim"
                    if score >= FUZZY_THRESHOLD
                    else "no passage in the source is close to this quote"
                ),
            )
        if score >= 0.995:
            break
    if best.similarity < FUZZY_THRESHOLD:
        return Match(tier="none", reason=best.reason or "quote not found")
    return best


def _flat_context(raw_text: str, flat: str, pos: int, length: int, width: int = 160) -> str:
    """A readable excerpt of `raw_text` around where `flat` matched at `pos`.

    The flattened text has no spaces to anchor against, so the window is placed
    proportionally (`pos / len(flat)` mapped onto `len(raw_text)`) and centred
    on the estimate.  The estimate is honest only to within the whitespace the
    flattening removed, so the window is wide; a reader who needs the exact
    bytes has the page number and the quote.
    """
    frac = pos / max(1, len(flat))
    centre = int(frac * len(raw_text))
    half = width // 2
    start = max(0, centre - half)
    end = min(len(raw_text), centre + half)
    snippet = re.sub(r"\s+", " ", raw_text[start:end]).strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(raw_text):
        snippet = snippet + "…"
    return snippet


def _best_window(text: str, needle_tokens: list[str]) -> tuple[str, float]:
    """Highest-similarity token window of the same length as the needle."""
    tokens = _TOKEN.findall(text)
    width = len(needle_tokens)
    if not tokens or len(tokens) < width:
        return "", 0.0
    matcher = difflib.SequenceMatcher(a=needle_tokens, b=[], autojunk=False)
    best_score = 0.0
    best_start = 0
    # The cheap prefilter drops windows whose first and last tokens appear
    # nowhere in the needle: a window with both ends foreign cannot reach
    # FUZZY_THRESHOLD... except that it can.  SequenceMatcher.ratio() bounds at
    # 2*M/(len(a)+len(b)); with W-2 forced matches that is (W-2)/W, and at
    # W=12 that is 0.833 >= 0.82.  So the skip is only sound while the bound
    # stays under the threshold; for longer needles the bound no longer holds
    # and every window is scored.  The cost is linear in page length either
    # way; pages are small enough to pay it.
    skip_sound = (width - 2) / width < FUZZY_THRESHOLD
    needle_set = set(needle_tokens)
    for start in range(len(tokens) - width + 1):
        if (
            skip_sound
            and tokens[start] not in needle_set
            and tokens[start + width - 1] not in needle_set
        ):
            continue
        window = tokens[start : start + width]
        matcher.set_seq2(window)
        score = matcher.ratio()
        if score > best_score:
            best_score = score
            best_start = start
    return " ".join(tokens[best_start : best_start + width]), best_score


def excerpt(quote: str, limit: int = 90) -> str:
    """A quote shortened for a one-line report."""
    flat = re.sub(r"\s+", " ", quote).strip()
    if len(flat) <= limit:
        return flat
    return flat[: limit - 1].rstrip() + "…"
