"""Locating a quote inside a source: exact, canonical, squashed, numbers, fuzzy.

Five tiers, tried in order, each strictly weaker than the last:

1. **exact** — the normalised quote appears in the normalised page text *at
   word boundaries*: "in the paper" must not match inside "a bin the papers";
2. **canonical** — the same comparison, after every number on both sides is
   rewritten in one spelling.  A page printing 40.688 and a quote saying
   40,688 hold one number and one sentence; without this tier the masker in
   tier 4 finds the words, sees different digits, and reports the figure as
   absent - an accusation about a number the reader can see on the page;
3. **squashed** — the quote appears once *all* whitespace is removed, which
   rescues text an extractor ran together or split across columns.  The
   boundary is gone at this tier by construction, so a minimum length keeps it
   from certifying a coincidence;
4. **numbers** — every number in the quote is masked out on both sides and the
   *words* still match at full length while the *values* still differ.  This
   is the tier that separates "you typed the statistic wrong" from "the quote
   is not in this document";
5. **fuzzy** — a sliding token-window comparison, used only to say "the quote
   looks like the source but is not present verbatim", which is reported as a
   medium-severity finding rather than silently accepted.

Tier 2 counts as found: the words match and so do the values, only the
separator differs.  Tiers 4 and 5 never upgrade a claim to verified - they
turn a flat "not found" into an actionable "these digits differ" / "these
words differ".

Every tier that may certify a quote also refuses a match whose span cuts a
number in half (``_cuts_a_number``).  Tier 1's word-boundary rule alone does
not catch it: ``40`` before ``.688`` ends at a character that is not a letter,
so a quote reading ``40`` was certified against a page reading ``40.688``.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from .sources import PageText
from .textnorm import MASK_PATTERN, REPORT_PATTERN, canonical_number, fold, squash

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
    tier: str  # "exact" | "canonical" | "squashed" | "numbers" | "fuzzy" | "none"
    page: int | None = None
    similarity: float = 0.0
    context: str = ""
    reason: str = ""
    spans_to: int | None = None

    @property
    def found(self) -> bool:
        """True only for the tiers that may be called verified.

        ``canonical`` belongs here: the words match at word boundaries and
        every number matches by value, so the only difference left is which
        character the locale prints between digit groups.  A tool that called
        that absent would be reporting a number the author can see on the page.
        """
        return self.tier in ("exact", "canonical", "squashed")


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


def _canonical_numbers(text: str) -> str:
    """Rewrite every number in ``text`` in the one spelling ``canonical_number`` picks.

    ``REPORT_PATTERN`` rather than ``MASK_PATTERN`` on purpose: the quote side
    has to agree with what the ledger recorded, and the ledger records
    ``numbers_in``, which is the report pattern.  Where the two patterns
    disagree - a bare space between digit triples - neither side sees a number
    there and both texts stay as they were, which is the safe direction.

    Rewriting is idempotent, so applying it to text that is already canonical
    changes nothing and a page never has to be reasoned about twice.
    """
    return REPORT_PATTERN.sub(lambda m: canonical_number(m.group(0)), text)


def _canonical_with_map(text: str) -> tuple[str, list[int]]:
    """Canonicalised text, plus the original offset of every character in it.

    The map exists because the caller needs both answers: *where* the quote
    matched (in canonical text) and *what* to show the reader around it (in
    the text as printed).  Rewriting 40.688 as 40688 shortens the string, so a
    canonical offset is not an original offset - and a context excerpt sliced
    with a shifted index shows a sentence nobody wrote.

    Inside a rewritten number every character maps to the number's first
    original character: a match never starts mid-number at a word boundary
    unless the quote itself starts mid-number, which ``_bounded_in`` refuses.
    """
    if not REPORT_PATTERN.search(text):
        return text, list(range(len(text)))
    pieces: list[str] = []
    offsets: list[int] = []
    last = 0
    for match in REPORT_PATTERN.finditer(text):
        pieces.append(text[last : match.start()])
        offsets.extend(range(last, match.start()))
        rewritten = canonical_number(match.group(0))
        pieces.append(rewritten)
        offsets.extend([match.start()] * len(rewritten))
        last = match.end()
    pieces.append(text[last:])
    offsets.extend(range(last, len(text)))
    return "".join(pieces), offsets


def _bounded_in(haystack: str, needle: str) -> list[int]:
    """Start offsets of ``needle`` in ``haystack`` at word boundaries.

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


def _bounded_pages(page: PageText, needle: str) -> list[int]:
    """``_bounded_in`` over one page's folded text."""
    return _bounded_in(page.folded, needle)


def _number_spans(text: str) -> list[tuple[int, int]]:
    """Where each number sits in ``text``, as half-open spans."""
    return [match.span() for match in REPORT_PATTERN.finditer(text)]


def _cuts_a_number(spans: list[tuple[int, int]], start: int, end: int) -> bool:
    """Does ``text[start:end]`` end or start inside a number?

    ``_is_word_char`` is ``str.isalnum``, so ``40`` sitting before ``.688``
    ends at a character that is not a letter and passes the word-boundary
    rule: a quote reading ``The value is 40.`` was certified, at similarity
    1.0, against a page reading ``The value is 40.688``.  That is the worst
    thing this tool can do - it says a claim is proven when the number in it
    is a truncation of the real one - and it is a hole the boundary rule
    cannot close, because ``.`` really is not part of a word.

    A match is honest when it ends exactly where the number ends, or before
    the number begins.  Landing anywhere strictly inside one is a slice.
    """
    for number_start, number_end in spans:
        if number_start < end < number_end:
            return True
        if number_start < start < number_end:
            return True
    return False


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


def _page_pairs(
    pages: list[PageText], page_hint: int | None = None
) -> list[tuple[PageText, int]]:
    """Every adjacent pair of pages, stitched into one readable page.

    The stitched page keeps the *earlier* page's number, because a reader who
    wants to look at the quote starts reading where the quote starts, and a
    finding that pointed at the later page would send them to text that has the
    end of the sentence and none of the beginning.  The second element is the
    number of the page the stitched text runs onto.

    Whitespace is inserted rather than glued: extractors wrap pages at
    different points, some end a page mid-word with no hyphen at all, and a
    quote reassembled from two halves must match the way it reads on paper, not
    the way two extractor buffers happen to abut.

    The hinted page is put first so a manuscript that already points at the
    right page is answered by the first pair tried.
    """
    order: list[int] = []
    if page_hint is not None and 1 <= page_hint <= len(pages) - 1:
        order.append(page_hint - 1)
    order.extend(i for i in range(len(pages) - 1) if i not in order)

    stitched: list[tuple[PageText, int]] = []
    for index in order:
        first, second = pages[index], pages[index + 1]
        text = first.text.rstrip() + " " + second.text.lstrip()
        stitched.append((PageText(number=first.number, text=text), second.number))
    return stitched


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
    # only as a fragment of other words never counts as present.  A match that
    # slices a number is refused for the same reason (see _cuts_a_number):
    # the boundary rule cannot see it, because the character a number is cut
    # at is the separator itself.
    for index in order:
        page = pages[index]
        spans = _number_spans(page.folded)
        hits = [
            hit
            for hit in _bounded_pages(page, quote_norm)
            if not _cuts_a_number(spans, hit, hit + len(quote_norm))
        ]
        if hits:
            return Match(
                tier="exact",
                page=page.number,
                similarity=1.0,
                context=_context(page.folded, hits[0], len(quote_norm)),
            )

    # A sentence that runs off the bottom of one page and onto the top of the
    # next is not a quote that is missing - it is a quote this tool could not
    # see, because until now it only ever read one page at a time.  Tried only
    # after every single page has missed, so a quote that fits on a page is
    # always reported against that page first.
    for joined, end_number in _page_pairs(pages, page_hint):
        spans = _number_spans(joined.folded)
        hits = [
            hit
            for hit in _bounded_pages(joined, quote_norm)
            if not _cuts_a_number(spans, hit, hit + len(quote_norm))
        ]
        if hits:
            return Match(
                tier="exact",
                page=joined.number,
                similarity=1.0,
                context=_context(joined.folded, hits[0], len(quote_norm)),
                reason="the quote crosses a page break",
                spans_to=end_number,
            )

    # Canonical: the same comparison after both sides spell their numbers one
    # way.  A page printing 40.688 and a quote saying 40,688 hold one number;
    # without this tier the numbers tier below finds the words, sees digits
    # that differ, and reports the figure absent.  A separator is a locale's
    # spelling of a value, not a disagreement about it.
    #
    # Tried before squashed so the finding can still say which page the quote
    # is on, and skipped entirely when the quote holds no number - there is
    # then nothing this tier can see that exact did not.
    if REPORT_PATTERN.search(quote_norm):
        quote_canon = _canonical_numbers(quote_norm)
        for index in order:
            page = pages[index]
            canon, offsets = _canonical_with_map(page.folded)
            for hit in _bounded_in(canon, quote_canon):
                start = offsets[hit]
                # The map says where each canonical character *starts* in the
                # printed text, so the end of a match is the start of the
                # character after it.  Reading the last matched character's
                # offset instead would collapse a quote that ends on a
                # number to the number's first character, because every
                # character of a rewritten number maps to the same original
                # position - and that collapsed span then looks exactly like a
                # truncated number, so a legitimate quote ending in "40,688"
                # against a page holding "40.688" would be refused.
                after = hit + len(quote_canon)
                end = offsets[after] if after < len(canon) else len(page.folded)
                # No ``_cuts_a_number`` guard on this tier, unlike exact and
                # squashed.  Canonical text spells every number as one run of
                # digits with no separator inside it, so a match that started
                # or ended inside a number would have no word boundary to lean
                # on and ``_bounded_in`` has already refused it.  A guard here
                # would be unreachable, and a guard no input can reach is one
                # no test can prove - so it would live on as a false claim of
                # protection.
                return Match(
                    tier="canonical",
                    page=page.number,
                    similarity=1.0,
                    context=_context(page.folded, start, max(end - start, 1)),
                    reason=(
                        "the quote is on this page; the numbers are the same "
                        "values written with a different thousands separator"
                    ),
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
            # The same slice check the exact tier makes, on this tier's own
            # view of the text: flattening removes the spaces that separated
            # words, but it leaves the separators inside a number alone, so a
            # quote ending at `406` still lands inside `40688`.
            if _cuts_a_number(_number_spans(flat), pos, pos + len(quote_squash)):
                continue
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
