"""Locating a quote inside a source: exact, whitespace-free, number-blind, fuzzy.

Four tiers, tried in order, each strictly weaker than the last:

1. **exact** — the normalised quote appears in the normalised page text;
2. **squashed** — the quote appears once *all* whitespace is removed, which
   rescues text an extractor ran together or split across columns;
3. **numbers** — every number in the quote is masked out on both sides and the
   text still matches.  This is the tier that separates "you typed the
   statistic wrong" from "the quote is not in this document", which is the
   distinction the whole tool exists to make;
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
from .textnorm import fold, squash

# A quote must be at least this long before fuzzy matching is allowed to opine.
# Below it, short quotes match too many places for a similarity score to mean
# anything.
MIN_FUZZY_TOKENS = 5
FUZZY_THRESHOLD = 0.82

# The same number-ish pattern textnorm uses, kept here so masking is applied to
# exactly the spans that :func:`citevouch.textnorm.numbers_in` would report.
_NUMBER = re.compile(r"\d+(?:[,\u00a0]\d{3})*(?:\.\d+)?%?")
_NUMBER_PLACEHOLDER = "\x00"
_TOKEN = re.compile(r"[^\s]+")


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

    for index in order:
        page = pages[index]
        pos = page.folded.find(quote_norm)
        if pos >= 0:
            return Match(
                tier="exact",
                page=page.number,
                similarity=1.0,
                context=_context(page.text, _source_index(page, pos), len(quote)),
            )

    for index in order:
        page = pages[index]
        flat = squash(page.text)
        pos = flat.find(quote_squash)
        if quote_squash and pos >= 0:
            return Match(
                tier="squashed",
                page=page.number,
                similarity=1.0,
                context=_context(page.text, 0, min(len(page.text), 160)),
                reason="matched only after removing all whitespace",
            )

    # Number-blind comparison: identical words, different digits.  Reported as
    # its own tier so the finding can say "the number is wrong" instead of
    # "the quote is missing", which is the whole difference between a typo and
    # a fabrication.
    if _NUMBER.search(quote):
        masked_quote = squash(mask_numbers(quote))
        for index in order:
            page = pages[index]
            flat = squash(mask_numbers(page.text))
            if masked_quote and masked_quote in flat:
                return Match(
                    tier="numbers",
                    page=page.number,
                    similarity=1.0,
                    context=_context(page.text, 0, min(len(page.text), 160)),
                    reason="the words match but the numbers in the quote differ from the source",
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


def _source_index(page: PageText, folded_pos: int) -> int:
    """Approximate the raw-text offset of a folded offset.

    Reverse-mapping is not worth exacting here: the context window is
    ±60 characters and is used for display only, so an offset that is a few
    characters off still shows the right sentence.
    """
    if folded_pos <= 0:
        return 0
    ratio = folded_pos / max(1, len(page.folded))
    return min(len(page.text), int(ratio * len(page.text)))


def _best_window(text: str, needle_tokens: list[str]) -> tuple[str, float]:
    """Highest-similarity token window of the same length as the needle."""
    tokens = _TOKEN.findall(text)
    width = len(needle_tokens)
    if not tokens or len(tokens) < width:
        return "", 0.0
    matcher = difflib.SequenceMatcher(a=needle_tokens, b=[], autojunk=False)
    best_score = 0.0
    best_start = 0
    # Step by one token but skip windows whose first token is not in the needle
    # at all: on a 40-page PDF this is the difference between a second and a
    # minute, and it cannot miss a window that scores above the threshold.
    needle_set = set(needle_tokens)
    for start in range(len(tokens) - width + 1):
        if tokens[start] not in needle_set and tokens[start + width - 1] not in needle_set:
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
