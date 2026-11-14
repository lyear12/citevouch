"""Locating a quote inside a source: exact, canonical, hyphen, pasted, squashed, numbers, fuzzy.

Seven tiers, tried in order, each strictly weaker than the last:

1. **exact** — the normalised quote appears in the normalised page text *at
   word boundaries*: "in the paper" must not match inside "a bin the papers";
2. **canonical** — the same comparison, after every number on both sides is
   rewritten in one spelling.  A page printing 40.688 and a quote saying
   40,688 hold one number and one sentence; without this tier the masker in
   tier 6 finds the words, sees different digits, and reports the figure as
   absent - an accusation about a number the reader can see on the page;
3. **hyphen** — the page read the *other* way.  A page that broke
   ``high-dimensional`` at the line end extracts as ``high-\ndimensional``;
   ``normalize`` joins that to ``highdimensional``, while the author who reads
   the page quotes ``high-dimensional``.  Which of the two the page means is
   not in the bytes, so this tier compares the quote against the page with the
   hyphen kept.  The hyphen stays on the page side: deleting it from the quote
   as well certified ``re-cover`` against ``recover``, a claim the page never
   supports;
4. **pasted** — the same reading, one space further out.  A reader who
   selects the region in Acrobat, Word or a browser gets the hyphen *and* a
   space, because the viewer keeps the glyph it drew and turns the line break
   into a space.  An author quoting that paste writes ``exam- ples``, which
   tier 3 still misses by exactly one space.  Measured on 20 real PDFs quoted
   in a reader's own shapes: 90 quotes, 12 not found, 11 of the 12 this one;
5. **squashed** — the quote appears once *all* whitespace is removed, which is
   the only comparison left when an extractor ran words together or cut a
   column in half.  This tier may **not** certify a quote: removing the
   whitespace also removes the difference between one word and two, so
   ``nothing here`` and ``nothinghere`` are the same string and the run cannot
   tell a bad extraction from a moved space.  It reports what it found and the
   caller treats it as a question for a human -- see ``Match.found``;
6. **numbers** — every number in the quote is masked out on both sides
   and the *words* still match at full length while the *values* still differ.
   This is the tier that separates "you typed the statistic wrong" from "the
   quote is not in this document";
7. **fuzzy** — a sliding token-window comparison, used only to say
   "the quote looks like the source but is not present verbatim", which is
   reported as a medium-severity finding rather than silently accepted.

Tiers 2, 3 and 4 count as found: the words match and so do the values, and the
only difference is a separator, or a hyphen plus the break character that the
page's own layout and the reader's clipboard make ambiguous.  Tier 5 does not:
it is the tier that lost the separator entirely, and with it every evidence
that the quote's word boundaries are the page's.  Tiers 6 and 7 never upgrade a
claim to verified - they turn a flat "not found" into an actionable "these
digits differ" / "these words differ".

Every tier that may certify a quote also refuses a match whose span cuts a
number in half (``_cuts_a_number``).  Tier 1's word-boundary rule alone does
not catch it: ``40`` before ``.688`` ends at a character that is not a letter,
so a quote reading ``40`` was certified against a page reading ``40.688``.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Iterator
from dataclasses import dataclass

from .sources import PageText
from .textnorm import (
    CANON_PATTERN,
    MASK_PATTERN,
    REPORT_PATTERN,
    canonical_number,
    fold,
    fold_keeping_hyphen,
    fold_number_forms,
    fold_pasted,
    squash,
    strip_wrapping_quotes,
)

# A quote must be at least this long before fuzzy matching is allowed to opine.
# Below it, short quotes match too many places for a similarity score to mean
# anything.
#
# The unit is the token this module counts below, and a CJK character is one
# token, so for Chinese this is five characters - roughly a two-word phrase.
# Measured on this repository's own Chinese prose (60 sentences, one character
# changed in each): every typo scored at least 0.667 and 95% scored at least
# 0.857, while two unrelated sentences scored at most 0.333.  The same sample
# at five characters: an unrelated pair peaked at 0.4 and a one-character
# typo scores 0.8, so five characters is the shortest length where the score
# still separates a slip from noise.
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


def _is_cjk(char: str) -> bool:
    """Whether one character belongs to a script written without spaces."""
    code = ord(char)
    return any(lo <= code <= hi for lo, hi in _CJK_RANGES)


def _has_cjk(text: str) -> bool:
    return any(_is_cjk(ch) for ch in text)


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
_LATIN_WORD = re.compile(r"[^\W\d_]+")


def _tokens(text: str) -> list[str]:
    """Split `text` into the units fuzzy matching compares.

    Whitespace is how Latin script separates words, and it is not how Chinese,
    Japanese or Korean do: a Chinese sentence is one whitespace-delimited chunk
    however long it is.  Counting chunks therefore made every Chinese quote
    exactly one token, which is below `MIN_FUZZY_TOKENS` for all of them, so
    the fuzzy tier answered "too short for a fuzzy comparison" about a
    40-character quote - a sentence whose every character had just been
    compared.  The tier was unreachable for a third of this tool's audience
    and the message blamed the quote's length.

    A CJK character is one token here, because a character is a morpheme and
    the reader who mistypes one expects the tool to notice; Latin runs stay
    whole words, so the tier means what it always meant in English.
    """
    tokens: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            tokens.extend(_LATIN_WORD.findall("".join(buffer)))
            buffer.clear()

    for char in text:
        if _is_cjk(char):
            flush()
            tokens.append(char)
        elif char.isalnum():
            buffer.append(char)
        else:
            flush()
    flush()
    return tokens


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
    tier: str  # "exact" | "canonical" | "hyphen" | "pasted" | "squashed" | "numbers" | "fuzzy" | "none"
    page: int | None = None
    similarity: float = 0.0
    context: str = ""
    reason: str = ""
    spans_to: int | None = None
    #: For the ``numbers`` tier only: the numbers the page prints where the
    #: quote's numbers would be, in quote order.  Empty for every other tier.
    #:
    #: Without this the caller could only ask "is 9,800 anywhere on page 1?",
    #: and for a quote that swapped a number between sentences the answer is
    #: yes - so the run had nothing true to say and printed "the numbers do
    #: not", about a number sitting in the same page's next sentence.  The
    #: tier already knows the answer: it found the quote by matching the text
    #: with every number blanked out, so the page's numbers are exactly the
    #: ones that fell into the quote's blank positions.
    page_numbers: tuple[str, ...] = ()

    #: Every page the quote touches, first to last, for a quote that runs across
    #: one or more breaks.  ``page`` is ``spanned[0]`` and ``spans_to`` is
    #: ``spanned[-1]``; the middle members are the pages a two-page stitcher
    #: could not see.
    #:
    #: A quote spanning pages 2-4 is *on* page 3 as much as on the ends, so a
    #: ledger pointing at any of the three is not a move, and the numbers check
    #: has to read all three or it reports a figure visible on page 3 as absent.
    spanned: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        """A match on one page spans that page.

        ``spanned`` exists so a caller never has to ask "which pages is this
        quote on?" twice, in two ways.  Every tier that names a page touches at
        least that page, so the field is filled here rather than at seven call
        sites that would each have to remember.
        """
        if not self.spanned and self.page is not None:
            self.spanned = (self.page,)

    @property
    def found(self) -> bool:
        """True only for the tiers that may be called verified.

        ``canonical`` belongs here: the words match at word boundaries and
        every number matches by value, so the only difference left is which
        character the locale prints between digit groups.  A tool that called
        that absent would be reporting a number the author can see on the page.

        ``pasted`` belongs here too: the quote and the page hold the same
        words, and the one difference is a space the clipboard put after a
        hyphen the page also has.

        ``squashed`` is deliberately **not** here, and the reason is the tier's
        own construction rather than its confidence.  Removing all whitespace
        deletes the only thing that separates one word from two, so a page that
        says ``nowhere`` and a quote that says ``now here`` become the same
        string.  Measured on the released behaviour, that pair verified and
        exited 0: a claim about words the source does not contain, certified by
        the tool whose whole purpose is to refuse exactly that.  Nothing in the
        flattened text can tell the two apart -- the extractor that really did
        run words together and the author who moved a space produce identical
        evidence -- so the honest verdict is "this run cannot decide", and that
        is a finding for a human rather than a `quote-found`.
        """
        return self.tier in ("exact", "canonical", "hyphen", "pasted")


def _without_the_placeholder(text: str) -> str:
    """``text`` in its number-comparison spelling, with no placeholder left in it.

    The placeholder is a real character and a source can supply it: NUL bytes
    survive PDF extraction (six pages in the first 250 PDFs of one real corpus
    carry one), and a NUL in the page text then counts as a blanked number.  The
    numbers tier finds the quote by counting placeholders up to the match, so one
    stray NUL before the passage shifted every slot by one and the report named
    the wrong figure: a page printing ``9,801`` in the quoted sentence and ``7``
    further down was reported as printing ``7`` *where the quote says 9,800*,
    which is a sentence about the author's claim that the page contradicts.
    Removing the character here is what makes "a placeholder means a number"
    true rather than merely intended, and it is honest about what a NUL is: not
    a character a reader can see, but an extraction artefact.
    """
    return fold_number_forms(text).replace(_NUMBER_PLACEHOLDER, "")


def mask_numbers(text: str) -> str:
    """Replace every number with a placeholder so two texts can be compared.

    The digits are folded first, so the placeholder count is a count of
    *numbers* and not of the spellings a page happened to use.  Reading the raw
    text instead split a page's fullwidth ``\uff14\uff10\uff0c\uff16\uff18\uff18`` into
    two placeholders while the quote typing ``40,688`` produced one, and the
    numbers tier - whose whole job is to line the quote's numbers up with the
    page's - then compared two lists that were not the same list.  See
    ``textnorm.fold_number_forms``.

    A source's own placeholder characters are removed first, so the count is a
    count of numbers and not one number plus whatever control characters the
    extractor left behind.  See ``_without_the_placeholder``.
    """
    return _NUMBER.sub(_NUMBER_PLACEHOLDER, _without_the_placeholder(text))


def number_spans(text: str) -> list[tuple[str, int]]:
    """The (token, start) pairs mask_numbers will replace.

    Exposed for the test that pins the two number patterns down: every span
    `numbers_in` may report (REPORT_PATTERN) must be a span the numbers tier
    masks (MASK_PATTERN), or the tier would reason about digits nobody claimed.
    The converse is deliberately not required - MASK additionally swallows a
    space thousands-separator ("1 000") that REPORT refuses to invent, because
    masking too much is harmless and reporting a number nobody wrote is not.
    """
    return [(m.group(0), m.start()) for m in _NUMBER.finditer(_without_the_placeholder(text))]


def _numbers_under(text: str, skip: int, want: int) -> tuple[str, ...]:
    """The ``want`` numbers the page prints at a run of ``want`` blanked slots.

    ``mask_numbers`` replaces every number with a one-character placeholder, so
    a masked page holds the page's numbers in order and nothing else does.  The
    slot the ``skip``-th placeholder sits in is the slot the ``want`` slots of
    the matched quote occupied, so the numbers that belong there are the ones
    at those positions.  Reading them out is what lets the report say which
    number the quote put where the page prints a different one - the sentence
    the author can act on, and the one that is true about a page whose other
    sentences hold the number the quote used.
    """
    found = [token for token, _ in number_spans(text)]
    return tuple(found[skip : skip + want]) if want else ()


def _canonical_numbers(text: str) -> str:
    """Rewrite every number in ``text`` in the one spelling ``canonical_number`` picks.

    ``CANON_PATTERN`` rather than ``REPORT_PATTERN`` here, and the choice is
    the whole of a measured bug.  The report pattern refuses a bare space
    between digit triples on purpose ("2019 2020 2021" is three years), so both
    sides of the comparison used to skip over ``40 688`` and leave it as it was.
    But the page is not the only side that decides: a PDF prints ``40 688`` and
    the author types ``40,688``, and the canonical tier - the one tier whose
    entire job is to know that those are one number - saw neither as a number
    and fell through to the numbers tier, which then reported the figure absent
    from a page that prints it.  ``CANON_PATTERN`` accepts only a *grouping*
    space (one to three digits, then exactly three), so a year still cannot
    start one.

    Rewriting is idempotent, so applying it to text that is already canonical
    changes nothing and a page never has to be reasoned about twice.
    """
    return CANON_PATTERN.sub(lambda m: canonical_number(m.group(0)), text)


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
    if not CANON_PATTERN.search(text):
        return text, list(range(len(text)))
    pieces: list[str] = []
    offsets: list[int] = []
    last = 0
    for match in CANON_PATTERN.finditer(text):
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


#: The longest run of pages stitched into one passage, counting the page the
#: quote starts on.  A quote that crosses two breaks needs three.
#:
#: The number is a cost decision.  A source of n pages offers n - length + 1
#: runs of each length, so the work grows with ``MAX_STITCHED_PAGES * len(pages)``
#: and every run re-folds the text it glues together.  Prose running across four
#: page breaks is already unusual; the alternative to a limit is a quadratic
#: blow-up on a 900-page book for a case that does not occur.
#:
#: A quote longer than the limit is never compared page by page, so this run
#: may not call it missing either: ``_whole_document_span`` finds where it
#: begins and where it ends in the whole document, and the claim is reported
#: as ``quote-spans-too-many-pages`` and counted under ``skipped``.  That is
#: what makes the number a correctness parameter rather than a tuning knob;
#: ``tests/test_quote_spans_too_many_pages.py`` says so in a test.
MAX_STITCHED_PAGES = 4


def _number_match(
    page: PageText,
    flat: str,
    pos: int,
    masked_quote: str,
    spanned: tuple[int, ...],
) -> Match:
    """A numbers-tier match, with the figures read out of the page it matched.

    ``page`` is the text the tier matched (a single page, or a run stitched by
    ``_page_runs``), ``flat`` is that text masked and flattened, and ``spanned``
    is every page number it covers.  Kept as one function so the single-page
    pass and the run pass cannot drift apart: the first version of this tier
    built its ``Match`` inline, and a run pass would have been a second copy of
    the same twelve arguments with one of them wrong.
    """
    return Match(
        tier="numbers",
        page=page.number,
        similarity=1.0,
        context=_flat_context(page.text, flat, pos, len(masked_quote)),
        reason=(
            "the words around the numbers match this page but the numbers "
            "in the quote differ from the source"
        ),
        page_numbers=_numbers_under(
            page.text,
            flat.count(_NUMBER_PLACEHOLDER, 0, pos),
            masked_quote.count(_NUMBER_PLACEHOLDER),
        ),
        spans_to=spanned[-1] if len(spanned) > 1 else None,
        spanned=spanned,
    )


def _page_runs(
    pages: list[PageText], page_hint: int | None = None
) -> Iterator[tuple[PageText, int, tuple[int, ...]]]:
    """Every run of adjacent pages, stitched into one readable page.

    (stitched page, number of the last page, every page number in the run)

    A run of length two is a quote crossing one page break; a run of three is a
    quote crossing two.  Stitching only *pairs* was measured to report a
    verbatim three-page quotation as ``quote-missing`` - ``We collected a very
    large number of examples from the corpus and then filtered them by hand``,
    printed across pages 2 to 4, was called "quote not found in page.txt".  A
    reader turning from page 2 to page 4 sees it; only a program reading two
    pages at a time cannot, and the tool's whole promise is that its sentences
    are true.

    The stitched text keeps the *first* page's number, because a reader who
    wants to look at the quote starts reading where the quote starts, and a
    finding that pointed at the last page would send them to text that has the
    end of the sentence and none of the beginning.

    Whitespace is inserted rather than glued: extractors wrap pages at
    different points, some end a page mid-word with no hyphen at all, and a
    quote reassembled from two halves must match the way it reads on paper, not
    the way two extractor buffers happen to abut.

    Length is the outer loop and the hint only breaks ties inside it.  The
    other way round, a hint pointing at an early page made a four-page run that
    merely *contains* the quote win over the three pages the quote actually
    occupies, and the finding said "quote found on page 1 (running onto pages 2,
    3 and 4)" about a sentence that begins on page 2.  Measured, with the hint
    on page 1 and the quote on pages 2-4.  A quote that fits in two pages must
    never be attributed to four for the same reason.
    """
    limit = min(MAX_STITCHED_PAGES, len(pages))
    starts: list[int] = []
    if page_hint is not None and 1 <= page_hint <= len(pages):
        starts.append(page_hint - 1)
    starts.extend(index for index in range(len(pages)) if index not in starts)

    for length in range(2, limit + 1):
        for start in starts:
            run = pages[start : start + length]
            if len(run) < length:
                continue
            body = run[0].text.rstrip()
            for page in run[1:]:
                body += " " + page.text.lstrip()
            numbers = tuple(page.number for page in run)
            yield PageText(number=run[0].number, text=body), numbers[-1], numbers


def _whole_document_span(quote_norm: str, pages: list[PageText]) -> tuple[int, int] | None:
    """Where a quote sits when the whole document is read as one passage.

    The stitcher reads at most ``MAX_STITCHED_PAGES`` pages at a time, so a
    quotation crossing more breaks than that is never compared against
    anything - and until this function existed the run then reported it
    ``quote-missing``, the high-severity sentence that says the author
    fabricated a quotation, while the words sat on those pages in order.
    Measured on a source whose six pages carry one sentence quoted verbatim
    across all six:

        [high] quote-missing ... - quote not found in paper.txt

    The answer to "did this tool simply not read far enough" only exists on the
    path where every tier has already missed, so it is asked here and paid for
    once: join the whole document the way ``_page_runs`` joins a run, look for
    the quote in it, and translate the hit's two ends back into page numbers.
    A probe built from the quote's first and last fifty characters was tried
    first and cannot work: the probe has to fit on one page, and a document
    whose pages are shorter than the probe is exactly the document this
    function is for.

    Returns ``(first, last)`` only when the quote is really in the document and
    really spans more pages than the stitcher reaches.  A quote the stitcher
    did try - one that fits in ``MAX_STITCHED_PAGES`` - keeps its own verdict
    instead of being excused here.

    There is deliberately no separate "is the document even long enough" guard
    in front of the join: with the page numbers handed out by the extractor, a
    document of at most ``MAX_STITCHED_PAGES`` pages cannot span more breaks
    than that, so the span check below is the whole rule.  A second, weaker
    guard written first would be unreachable-or-redundant, and nothing would
    ever fail when it was wrong.
    """
    if not quote_norm.strip():
        return None
    starts: list[int] = []
    pieces: list[str] = []
    offset = 0
    for page in pages:
        starts.append(offset)
        piece = page.folded.strip()
        pieces.append(piece)
        offset += len(piece) + 1
    flat = " ".join(pieces)
    hits = _bounded_in(flat, quote_norm)
    if not hits:
        return None
    begin = hits[0]
    finish = begin + len(quote_norm) - 1

    def index_of(position: int) -> int:
        found = 0
        for index, start in enumerate(starts):
            if start <= position:
                found = index
            else:
                break
        return found

    # The decision is made in the stitcher's currency - how many pages of this
    # list the quote covers - because that is the thing the stitcher counts.
    # Page *numbers* only go into the sentence, where the author reads them.
    # The two differ when an extractor leaves gaps in the numbering, and a rule
    # written in the wrong currency would excuse a quote the stitcher did try.
    first_index, last_index = index_of(begin), index_of(finish)
    if last_index - first_index + 1 <= MAX_STITCHED_PAGES:
        return None
    return pages[first_index].number, pages[last_index].number


def find_in_pages(
    quote: str,
    pages: list[PageText],
    page_hint: int | None = None,
) -> Match:
    """Locate ``quote`` in ``pages``, preferring ``page_hint`` if it is given.

    A quote the author wrapped in quotation marks is tried again without them.
    The marks are the author's way of saying "these are somebody else's words";
    they are not on the page unless the page quoted somebody too, so a verbatim
    sentence in quotes matched no tier and came back ``quote-fuzzy`` at high
    severity - "not these words verbatim (similarity 1.00)", which contradicts
    itself.  Measured on the same page and quote, before this retry existed:

        quote:  \u201cThe method works on every corpus we tried.\u201d
        before: tier='fuzzy' similarity=1.000  -> [high] quote-fuzzy
        after:  tier='exact' similarity=1.000  -> [info] quote-found

    The retry is only *accepted* when it finds the quote: a weaker verdict from
    a text the author did not write is not an improvement on a stronger one
    about the text they did.  So a wrapped quote that is genuinely absent still
    reports what the unwrapped search reported.
    """
    match = _find_in_pages(quote, pages, page_hint)
    if match.found:
        return match
    bare = strip_wrapping_quotes(quote)
    if bare == quote:
        return match
    retried = _find_in_pages(bare, pages, page_hint)
    return retried if retried.found else match


def _find_in_pages(
    quote: str,
    pages: list[PageText],
    page_hint: int | None = None,
) -> Match:
    """The search itself, without the quotation-mark retry.

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
    for joined, end_number, spanned in _page_runs(pages, page_hint):
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
                spanned=spanned,
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
    if CANON_PATTERN.search(quote_norm):
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

    # Hyphen kept: the page broke a compound at the line end.
    #
    #   page:  "... sequence of high-\ndimensional vectors"   (extracted)
    #   page:  "... sequence of highdimensional vectors"       (normalize joins it)
    #   quote: "... sequence of high-dimensional vectors"      (what the page shows)
    #
    # Typeset hyphenation and a compound broken at the line end extract
    # identically, so ``normalize`` has to guess, and it guesses "join".  This
    # tier reads the same bytes the other way and compares the quote against
    # *that*: the quote keeps whatever hyphen the author wrote, and the page
    # keeps the hyphen its line break put there.
    #
    # Relaxing the quote instead - deleting its hyphens and searching a page
    # whose hyphens the join had already deleted - was the first version of
    # this tier and it was backwards.  It certified ``re-cover`` against a page
    # reading ``recover``, ``re-sign`` against ``resign``, ``re-form`` against
    # ``reform`` and ``co-op`` against ``coop``: real pairs of real words, and
    # a claim the page never supports.  Keeping the hyphen on both sides can
    # only compare like with like, so this tier cannot manufacture a word the
    # page did not print.
    for index in order:
        page = pages[index]
        kept = fold_keeping_hyphen(page.text)
        if kept == page.folded:
            # No line-break hyphen on this page, so the second reading is the
            # same string as the first and there is nothing here the tiers
            # above could not already see.
            continue
        spans = _number_spans(kept)
        for hit in _bounded_in(kept, quote_norm):
            # ``kept`` is not ``page.folded``, so the slice check runs on
            # ``kept``'s own coordinates.
            if _cuts_a_number(spans, hit, hit + len(quote_norm)):
                continue
            return Match(
                tier="hyphen",
                page=page.number,
                similarity=1.0,
                context=_context(kept, hit, len(quote_norm)),
                reason=(
                    "the quote is on this page; the page printed the hyphen and "
                    "the extraction joined it at a line break"
                ),
            )

    # Pasted: the reader's clipboard kept the hyphen and dropped in a space.
    #
    #   page:  "... variety of exam-\nples ..."    (extracted)
    #   quote: "... variety of exam- ples ..."     (pasted out of a viewer)
    #
    # Browsers, Acrobat and Word all draw a hyphen at the line end and then
    # hand the selected text over with a space where the break was, because the
    # break is a layout fact and the space is what a human expects.  The author
    # quoting that page therefore writes the hyphen *and* the space, which is
    # neither of the two readings the tiers above compare against: not
    # ``examples`` (tier 1 sees the joined page) and not ``exam-ples`` (tier 3
    # sees the page with a bare hyphen).  The result was a correct quote going
    # to ``fuzzy`` and being reported at high severity - the tool saying words
    # the author copied out of the page are not on it.
    #
    # Only the break character is relaxed here: ``fold_pasted`` turns the line
    # break into a space on the page and the quote already carries whichever
    # character the author's clipboard produced.  The hyphen itself is required
    # on both sides, so ``re-cover`` cannot be certified against ``recover``.
    for index in order:
        page = pages[index]
        pasted = fold_pasted(page.text)
        if pasted == page.folded:
            # This page has no line-break hyphen, so the paste reading is the
            # join reading character for character and the exact tier above
            # already tried this quote against it.  This skip is a speed guard,
            # not a verdict: drop it and the tier gives the same answers.
            continue
        spans = _number_spans(pasted)
        for hit in _bounded_in(pasted, quote_norm):
            if _cuts_a_number(spans, hit, hit + len(quote_norm)):
                continue
            return Match(
                tier="pasted",
                page=page.number,
                similarity=1.0,
                context=_context(pasted, hit, len(quote_norm)),
                reason=(
                    "the quote is on this page; the reader's clipboard kept the "
                    "hyphen at the line end and put a space where the break was"
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
            # 1.0 is not a comparison, it is this tier's definition: the
            # masked quote was found verbatim, so every non-placeholder
            # character matched by construction.  This used to run
            # difflib.SequenceMatcher over those same two strings and return
            # whatever ratio it got, which could only ever be 1.0 - a
            # computation that looked like evidence and could not fail.
            #
            # Two passes, for the reason the exact tier above has a run pass:
            # a quotation can start on page 2 and end on page 4, so the figures
            # it quotes are printed on pages 2, 3 and 4.  Reading one page at a
            # time, a quote whose *middle* page printed a different figure was
            # reported as `quote-missing` - a fabricated quotation - while the
            # very same words with the right figures were found across those
            # same pages.  Measured: pages 2-4 carried the sentence, page 3
            # alone printed a different total, and the tool answered "quote not
            # found in page.txt".  It could see the sentence but not the typo,
            # and it answered the harder question with the answer to the
            # easier one.
            for index in order:
                page = pages[index]
                flat = squash(mask_numbers(page.text))
                pos = flat.find(masked_quote)
                if pos >= 0:
                    return _number_match(page, flat, pos, masked_quote, (page.number,))

            for joined, _end_number, spanned in _page_runs(pages, page_hint):
                flat = squash(mask_numbers(joined.text))
                pos = flat.find(masked_quote)
                if pos >= 0:
                    return _number_match(joined, flat, pos, masked_quote, spanned)

    needle_tokens = _tokens(quote_norm)
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
        # Before saying "not found", ask the one question that can turn this
        # into a true sentence: is the quote simply longer than the number of
        # pages this tool reads at once?  Asked here, at the single point where
        # every tier has already missed, so no verdict that found the quote can
        # be overwritten by it.
        span = _whole_document_span(quote_norm, pages)
        if span is not None:
            first, last = span
            return Match(
                tier="spans",
                page=first,
                similarity=0.0,
                reason=(
                    f"this quote begins on page {first} and ends on page {last}, "
                    f"which is {last - first + 1} pages - more page breaks than "
                    f"this tool reads at once ({MAX_STITCHED_PAGES})"
                ),
                spans_to=last,
            )
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
    tokens = _tokens(text)
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
    window = tokens[best_start : best_start + width]
    # A CJK window is a run of single characters: joining them with spaces
    # would print "构 式 语 法" back to the author, who wrote it as prose.
    # Latin tokens are whole words and are longer than one character, so the
    # length test is also what keeps `_is_cjk` receiving one character.
    joiner = "" if any(len(token) == 1 and _is_cjk(token) for token in window) else " "
    return joiner.join(window), best_score


def excerpt(quote: str, limit: int = 90) -> str:
    """A quote shortened for a one-line report."""
    flat = re.sub(r"\s+", " ", quote).strip()
    if len(flat) <= limit:
        return flat
    return flat[: limit - 1].rstrip() + "…"
