"""Turn a manuscript nobody has annotated into claim blocks somebody can review.

A real paper cites a hundred things. `citevouch` wants each of them as a block
naming a file, a page and the exact sentence that proves it, and nobody is going
to type a hundred of those by hand: they quit at the second one. This module
reads the manuscript the author already has, finds every place it cites
something, resolves that key to a file on disk, and writes a *proposal* — a file
of claim blocks with a confidence marker on each one.

Three rules make the result trustworthy rather than impressive:

* **It never edits the manuscript.** It writes the file named by ``-o`` and
  nothing else.
* **It never invents a quote.** A citation key that resolves to no file becomes
  a commented-out TODO that says "no local file", not a guess. Every quote in
  the output is text that was cut out of a real page.
* **Confidence is about the quote, not the claim.** ``high`` means the author's
  own sentence appears verbatim in the source, so the quote is beyond argument.
  ``medium`` means the quote is a real sentence from the most relevant page and
  the author has to decide whether it supports what they wrote. There is no
  third value that means "looks plausible": a passage that was neither found
  nor relevant enough is not emitted at all.

The output is an ordinary manuscript, so ``citevouch scan proposals.md`` reads
it back. That is the point of the loop: the tool grades its own proposals with
the same verifier the author will use.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from . import matching, sources
from .evidence import is_the_manuscript
from .latex import _GAP, CITATION_NAMES, MULTI_CITATION_NAMES
from .model import BibEntry
from .scan import _resolve
from .textnorm import UNDECODED, count_of, normalize, numbers_in, read_text

# Pandoc's bracket form: `[@key]`, `[@a; @b]`, `[-@key]`, `[see @a, p. 3]`.  This
# is what people writing Markdown actually use, so it is the primary dialect.
#
# The bracket can hold more than key after key.  Pandoc's grammar is
# `[prefix @key suffix; @key2 suffix2]`, where the prefix is prose ("see",
# "cf.") and the suffix is a locator ("p. 3", "ch. 2 and p. 4").  Measured on
# the previous pattern, which required the body to be keys separated by
# semicolons: `[@a, p. 3]`, `[see @a]`, `[@a, p. 3; @b, p. 4]` and
# `[-@a, ch. 2]` all matched nothing, so `citation_sites` returned `[]` and
# `draft` told the author no citations were found - in a manuscript that cites
# a source on every paragraph, using the syntax every reference manager emits.
# A page number is how half of real Markdown citations are written.
#
# What must still not match: `[contact me at x@y.com]`, where the `@` is inside
# a word.  Pandoc requires the key to start at a boundary, so the body and the
# key both carry the same lookbehind.
# The key of a `@type{key,` header, used to notice a key the bibliography
# names but never finished defining.  Deliberately loose: this runs on a file
# the parser already refused, so matching too little is the failure mode that
# matters (it would leave the author with the generic sentence).  A key that
# did parse is excluded by the caller, so a loose match cannot invent one.
_BIB_KEY = re.compile(r"@\w+\s*\{\s*([^,\s{}]+)")

_PANDOC = re.compile(r"\[(?P<body>[^\[\]]*(?<![A-Za-z0-9_.:\-])-?@[A-Za-z0-9_.:\-]+[^\[\]]*)\]")
_AT_KEY = re.compile(r"(?<![A-Za-z0-9_.:\-])-?@(?P<key>[A-Za-z0-9_.:\-]+)")
# LaTeX's forms, because much of the audience types Markdown in an editor that
# still has `.tex` habits and half of a draft arrives already using these.
#
# The names come from `latex.py` rather than being typed again here.  When they
# were typed again, this copy fell behind: `latex.py` knew `citeyearpar` and
# this list did not, so `to_text` turned `\citeyearpar{k}` into `[@k]` and
# `draft` then reported "no citations were found" while that marker sat in the
# text it was reading.  A third copy also silently dropped the second source in
# `"Prior work \citep{a} and \citeyearpar{b} agrees."`, and the proposal text a
# reader was invited to paste still contained raw LaTeX.
#
# `_GAP` is imported for the same reason: a space between the command and its
# brace is legal TeX, and the two readers have to agree about which
# whitespace counts and which does not.
_LATEX = re.compile(
    r"\\(?:"
    + "|".join(CITATION_NAMES)
    + r")\*?(?:"
    + _GAP
    + r"\[[^\]]*\])*"
    + _GAP
    + r"\{([^}]*)\}"
)
# A plural citation command takes one brace group per source, so the pattern
# above reads only the first and reports a manuscript citing three sources at
# once as citing one.  The list is biblatex's own; `cites` is natbib's.
_LATEX_MULTI = re.compile(
    r"\\(?:"
    + "|".join(MULTI_CITATION_NAMES)
    + r")\*?(?P<arguments>(?:(?:"
    + _GAP
    + r"\[[^\]]*\])*"
    + _GAP
    + r"\{[^{}]*\})+)"
)
_LATEX_ARGUMENT = re.compile(r"(?:" + _GAP + r"\[[^\]]*\])*" + _GAP + r"\{(?P<keys>[^{}]*)\}")

# A sentence ends at terminal punctuation followed by space, or at the end of a
# paragraph.  `re.split` keeps the text; offsets are recomputed from a scan so
# line numbers stay correct.
#
# Chinese, Japanese and Korean prose puts no space after the full stop, so the
# space branch never fires and one paragraph came back as one sentence: a
# fourteen-hundred-character run that `_is_passage` then refused for being too
# long, leaving `draft` to report "nothing on any page shares enough terms"
# about a paragraph sharing eighteen of them.  The two extra branches break
# after CJK terminal punctuation with nothing consumed, so a closing bracket
# stays with the sentence it closes instead of being deleted.
_CLOSING = "」』】》〉〕｝”’)]"
# `re.escape` because the class holds a `]`: unescaped, it closes the class
# early and the rest of the pattern means something else.
_CLOSING_CLASS = re.escape(_CLOSING)

# Marks that are written tight against the word before them.  `statement_of`
# closes the gap a removed citation leaves, and the first version listed only
# `.,;:!?`: `相关研究指出词汇与构式之间存在互动关系 [@page]。` came out as
# `相关研究指出词汇与构式之间存在互动关系 。`, a space no Chinese writer types.
_NO_SPACE_BEFORE = frozenset(".,;:!?。，、；：！？…" + _CLOSING)
_NO_SPACE_BEFORE_CLASS = re.escape("".join(sorted(_NO_SPACE_BEFORE)))
_WORDS = re.compile(r"[^\W\d_]{2,}")
_SENTENCE_END = re.compile(
    r"(?<=[.!?])[\"'”’)\]]*(?:\s+|$)"
    rf"|(?<=[。！？])(?![{_CLOSING_CLASS}])"
    rf"|(?<=[。！？][{_CLOSING_CLASS}])"
)

# Words that carry no topic.  Deliberately short: a long stoplist would start
# dropping the terms a short sentence depends on.
_STOPWORDS = frozenset(
    """
    a an and are as at be been being by can could did do does for from had has
    have how in into is it its may might more most much must no not of on one
    only or other our out over own same should so some such than that the their
    them then there these they this those through to too under until up very was
    we were what when where which while who why will with would you your
    also both each few many nor off again further once here all any
    """.split()
)

MIN_MEDIUM_TERMS = 3
"""Shared content terms a page needs before its best sentence may be proposed.

Two shared words is a coincidence: "grammar" and "construction" appear on every
page of a construction-grammar paper.  Three is the weakest number that has ever
been useful in a spot check, and a page that cannot reach it produces no
proposal rather than a plausible one.
"""

MIN_SENTENCE_WORDS = 7
MAX_SENTENCE_WORDS = 70
"""Words a passage needs to be worth reading as evidence, and its ceiling.

Below seven words there is no sentence, only a label or a table cell - the kind
of fragment that "supports" anything.  Above seventy the page text is not a
sentence at all: it is a figure caption, a results table or a wrapped list, and
proposing it would put a block of layout in the manuscript's mouth.

These were forty and four hundred *characters*, which is a length in the unit
English happens to need.  A Chinese sentence has no spaces, so a character
count of a Chinese passage measures something else entirely: measured on this
repository's own Chinese prose, the character rule kept 37% of its sentences
where the word rule keeps 86%, and on English it keeps 84% either way.  The
threshold is about how much there is to assert, so it is counted in what a
reader would call words - a run of letters, or one CJK character.
"""


@dataclass
class Site:
    """One place in the manuscript that cites one key."""

    key: str
    start: int
    end: int
    line: int


@dataclass
class Proposal:
    claim_id: str
    source_key: str
    quote: str
    page: int | None
    statement: str
    confidence: str
    reason: str
    line: int


@dataclass
class Skipped:
    key: str
    reason: str
    line: int


@dataclass
class Draft:
    proposals: list[Proposal] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)
    # Keys that resolved to a file the manifest does not name yet.  The author
    # pastes these into sources.toml; writing them there from here would make
    # the proposal file unreadable until someone checked it.
    needed_sources: dict[str, str] = field(default_factory=dict)
    unreadable: list[Skipped] = field(default_factory=list)
    # True when the text held no citation this command could find at all.
    #
    # The two zeros below this line are not the same zero.  "I read your
    # citations and none of them had a local PDF" is a fact about the machine;
    # "I found no citations" is a fact about the reading, and the second one is
    # almost always the tool's fault rather than the author's - a citation
    # written as a bare `(van eecke 2026)`, or in a file format this command
    # does not parse.  Measured: a manuscript with no markers and a manuscript
    # whose one marker pointed at a missing PDF produced the same stderr line,
    # the same five-line file and the same exit 0, so the author whose markers
    # were simply unrecognised was told to go read proposals that did not exist.
    no_citations: bool = False
    # How many characters of the manuscript were replacement characters.
    #
    # A manuscript saved in GBK reaches this module after
    # ``raw.decode("utf-8", errors="replace")``, so its citation markers are
    # gone: `[` and `@` are swallowed by two-byte pairs and `[@paper]` never
    # appears in the text this command searches.  Measured on a GBK manuscript
    # holding one `[@paper]` citation: ``draft`` exited 0 and said "no citations
    # were found to propose them for (this command reads `[@key]` and
    # `\\cite{key}`)" - true about the text it read, and silent about the fact
    # that made it true.  The author went looking for a citation they had
    # already written.
    undecodable: int = 0


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def citation_sites(text: str) -> list[Site]:
    """Every citation in the text, in the order a reader meets them."""
    sites: list[Site] = []
    for match in _PANDOC.finditer(text):
        for key in _AT_KEY.finditer(match.group("body")):
            sites.append(
                Site(
                    key=key.group("key"),
                    start=match.start(),
                    end=match.end(),
                    line=line_of(text, match.start()),
                )
            )
    for match in _LATEX.finditer(text):
        for raw in match.group(1).split(","):
            key = raw.strip()
            if key:
                sites.append(
                    Site(
                        key=key,
                        start=match.start(),
                        end=match.end(),
                        line=line_of(text, match.start()),
                    )
                )
    for multi in _LATEX_MULTI.finditer(text):
        for argument in _LATEX_ARGUMENT.finditer(multi.group("arguments")):
            for raw in argument.group("keys").split(","):
                key = raw.strip()
                if key:
                    sites.append(
                        Site(
                            key=key,
                            start=multi.start(),
                            end=multi.end(),
                            line=line_of(text, multi.start()),
                        )
                    )
    sites.sort(key=lambda site: site.start)
    return sites


def sentence_at(text: str, start: int) -> tuple[str, int, int]:
    """The sentence around `start`, as ``(text, start, end)``.

    A citation is part of the sentence that cites it, so the claim text is that
    whole sentence with the marker cut out.  Splitting on paragraphs first keeps
    a heading from being glued onto the sentence under it.

    A marker written after the full stop (``usage. [@p]``, which Pandoc accepts
    and which is how a citation typed at the end of a thought comes out) lands
    at the start of the following run of text.  Reading that literally gives
    the *next* sentence, so a manuscript citing ``usage. [@p] They generalize``
    had `draft` propose a quote for ``They generalize`` - the wrong claim, and a
    wrong source behind it.  The test is the text between the run's start and
    the marker: when it holds no words, the marker trails the sentence before
    it, and that sentence is the one the author meant.
    """
    para_start = text.rfind("\n\n", 0, start)
    para_start = 0 if para_start < 0 else para_start + 2
    # A marker can sit in the paragraph after the sentence it cites, so a
    # paragraph holding nothing but the marker looks back one more time.
    while para_start and not _WORDS.search(statement_of(text[para_start:start])):
        previous = text.rfind("\n\n", 0, max(para_start - 2, 0))
        # The document can open with the sentence this marker trails, in which
        # case there is no earlier break to find and the whole text before the
        # marker is the thing to read.
        para_start = previous + 2 if previous >= 0 else 0
    para_end = text.find("\n\n", start)
    para_end = len(text) if para_end < 0 else para_end
    runs: list[tuple[str, int, int]] = []
    cursor = para_start
    for sentence in _SENTENCE_END.split(text[para_start:para_end]):
        if not sentence:
            continue
        begin = text.find(sentence, cursor, para_end)
        if begin < 0:
            begin = cursor
        end = begin + len(sentence)
        cursor = end
        runs.append((sentence, begin, end))
    for index, (sentence, begin, end) in enumerate(runs):
        if not begin <= start < end:
            continue
        # A marker the author typed after the full stop opens the next run.  What
        # decides it is the text between the run's start and the marker: if that
        # prefix holds no words, the marker trails the sentence before it.
        before = statement_of(text[begin:start])
        if not _WORDS.search(before) and index > 0:
            return runs[index - 1]
        return sentence.strip(), begin, end
    return text[para_start:para_end].strip(), para_start, para_end


# A blockquote, a bullet, an ordinal and a heading are four ways of *showing* a
# sentence, and the marker in front of it is typography rather than words:
# nobody reading the rendered page sees a `>` between the author's words.
# `statement_of` read the raw line, so the marker travelled into the `claim:`
# field it asks the author to paste, and the same sentence then stopped matching
# its source verbatim - the page has no `>` either.
#
# Measured on one page holding `We collected 154,391 examples from the corpus.`
# and a manuscript quoting it word for word: plain text gave `confidence: high`
# and one proposal; behind `> `, `- `, `* `, `+ `, `## ` or `1) ` it gave
# `0 claim block(s) proposed` plus "nothing on any page shares enough terms with
# the sentence (3 needed)" - about a sentence the page shares four terms with. A
# false reason attached to a real loss is worse than silence: it sends the
# author to rewrite the sentence that was already right.
#
# `1. ` needs no entry here: `_SENTENCE_END` splits after the full stop, so that
# marker is already outside the text `statement_of` ever sees.
#
# What still must not match, because each one is the sentence's own content:
# `-- x`, `-3 degrees`, `2.5 million`, `#hashtag` (no space after the marker),
# and `a > b` (not at the start of a line). The indent is capped at three
# spaces, like CommonMark: four spaces is a code block, and its text is a
# quotation of Markdown rather than prose.
_CONTAINER_MARKER = re.compile(
    r"(?m)^[ \t]{0,3}(?:(?:>[ \t]?)+|[-*+][ \t]+|\d{1,9}[.)][ \t]+|#{1,6}[ \t]+)+"
)


def statement_of(sentence: str) -> str:
    """The sentence without its citation markers, ready to be a `claim:` line."""
    text = _CONTAINER_MARKER.sub("", sentence)
    text = _PANDOC.sub("", text)
    # The plural commands go first: `\cites{a}{b}` is four brace groups of
    # citation furniture, and `_LATEX` cannot match it at all (`s` is neither
    # `*`, `[` nor `{`), so leaving this out put the raw command in the middle
    # of the sentence the author is asked to paste.  Measured: a Markdown
    # manuscript citing `\cites{page}` produced `claim: |
    # ... construction \cites{page}.` - a sentence no human wrote, in the one
    # field this command exists to propose.
    text = _LATEX_MULTI.sub("", text)
    text = _LATEX.sub("", text)
    text = re.sub(rf"\s+(?=[{_NO_SPACE_BEFORE_CLASS}])", "", text)
    return re.sub(r"\s+", " ", text).strip()


def terms_of(text: str) -> set[str]:
    """Content terms, used to decide which page is about the same subject."""
    folded = normalize(text or "").casefold()
    out = {word for word in re.findall(r"[^\W\d_]{3,}", folded) if word not in _STOPWORDS}
    if matching._has_cjk(folded):
        for run in re.findall(r"[\u3400-\u9fff\uf900-\ufaff]{2,}", folded):
            out.update(run[index : index + 2] for index in range(len(run) - 1))
    out.update(numbers_in(folded))
    return out


def _bib_file(entry: BibEntry) -> str:
    """The path in a bib `file` field, without Zotero's `:path:mime` wrapper."""
    raw = (entry.fields.get("file") or "").strip()
    if not raw:
        return ""
    if raw.startswith(":"):
        parts = raw.split(":")
        return parts[1] if len(parts) > 1 else ""
    return raw


def resolve(
    key: str,
    known: dict[str, str],
    bib: dict[str, BibEntry],
    root,
) -> tuple[str | None, str | None]:
    """Where the file for `key` is, and whether the manifest needs a line for it.

    Returns ``(path, manifest_line_needs)``.  The second element is the key to
    write into `sources.toml` when the manifest does not already name it; it is
    ``None`` when the binding already exists, so the proposal needs no setup.

    Order matters and is the reverse of guesswork: an explicit manifest entry,
    then the author's own `file` field in the bibliography, then a file whose
    stem is exactly the citation key.  No prefix matching and no similarity
    scoring, for the reason the resolver lost them: a key bound to the wrong
    paper produces confident nonsense.
    """
    bound = sources.resolve_source(key, known)
    if bound:
        return bound, None
    entry = bib.get(key)
    if entry is not None:
        candidate = _bib_file(entry)
        if candidate:
            # `entry.path` is recorded relative to the project root, not
            # to the shell that ran the command, so it has to be joined
            # back to the root before it names a directory.  Measured
            # before this: a `file = {paper.pdf}` beside `sub/refs.bib`
            # resolved from inside the project and not from one level
            # above it, which made `draft` a command whose answer
            # depended on where it was typed - the same defect the
            # `-o` guard above was written for.
            base = Path(root) / Path(entry.path).parent if entry.path else Path(root)
            for folder in (base, Path(root)):
                path = folder / candidate
                if path.is_file():
                    return _relative(path, root), key
    for path in sources.candidate_files(root):
        if path.rsplit("/", 1)[-1].rsplit(".", 1)[0] == key:
            return path, key
    return None, None


def _relative(path: Path, root) -> str:
    """A POSIX path relative to the project, or the absolute one if it escapes.

    Everything this file writes is meant to be committed and read on another
    machine, so a path is recorded the way the ledger records one: relative to
    the root, with forward slashes. An absolute Windows path in a proposal block
    is unusable to the reader and would be pasted into `sources.toml` verbatim.
    """
    try:
        return path.resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return path.as_posix()


_HYPHEN_BREAK = re.compile(r"(?<=[a-z])-\s*\n\s*(?=[a-z])")
"""A word split across a line break, which is not the same as a hyphen."""


def _reflow(page_text: str) -> str:
    """One flowing line per page, with wrapped words rejoined.

    PDF text arrives wrapped at the column, so "the net-\nwork" is one word and
    "frame-\nevoking" is one hyphenated word.  Splitting sentences without
    reflowing first produces candidates that end mid-word and quotes that look
    machine-mangled in the manuscript, which is the fastest way to make an
    author distrust the whole file.
    """
    return re.sub(r"\s+", " ", _HYPHEN_BREAK.sub("", page_text)).strip()


_PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n[ \t]*")


def _sentences_of(page_text: str) -> list[str]:
    """Sentences, respecting the paragraph breaks the page actually has.

    A heading has no full stop, so splitting on punctuation alone glues it to
    the first sentence under it: a section title, its rule of ``====`` and a
    perfectly good sentence become one string, and that string is then refused
    for containing a table rule. Paragraphs are therefore split first - a title
    on its own line is its own paragraph - and sentences only inside each one.
    """
    sentences: list[str] = []
    for paragraph in _PARAGRAPH_BREAK.split(page_text):
        for sentence in _SENTENCE_END.split(_reflow(paragraph)):
            stripped = sentence.strip()
            if stripped:
                sentences.append(stripped)
    return sentences


# A page rendered from a PDF contains more than sentences: table rows, figure
# labels, running heads, the journal's name in the margin.  All of them are
# "text" and none of them is evidence.
_NON_SENTENCE = re.compile(r"(?:\S+\s*:\s*\S.*){3,}|\|\s*-{2,}|={3,}|-{4,}")

# One CJK character is one word: the writing system has no spaces to count
# between, and a reader counts characters as syllables.  Everything else is
# counted as runs of letters, which is what a word is in a spaced script.
_CJK = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF\u3040-\u30FF\uAC00-\uD7AF]")
_LETTER_RUN = re.compile(r"[^\W\d_]+")


def _words(text: str) -> int:
    """How many words `text` holds, in either kind of script."""
    return len(_CJK.findall(text)) + len(_LETTER_RUN.findall(_CJK.sub(" ", text)))


def _is_passage(sentence: str) -> bool:
    """Whether a run of text is a sentence a person would quote.

    Four things disqualify a candidate, and each one was found by running this
    on a real paper rather than by imagining a bad input: a fragment too short
    to assert anything, a block too long to be a sentence, a run that is mostly
    digits and punctuation (a results table), and a run with several
    ``label: value`` pairs in it (a printed report embedded in the page).
    """
    if not MIN_SENTENCE_WORDS <= _words(sentence) <= MAX_SENTENCE_WORDS:
        return False
    if _NON_SENTENCE.search(sentence):
        return False
    letters = sum(1 for char in sentence if char.isalpha())
    if letters / len(sentence) < 0.6:
        return False
    return len(numbers_in(sentence)) <= 4


def propose_quote(
    statement: str, pages: list, page_hint: int | None = None
) -> tuple[str, int | None, str, str] | None:
    """A quote for `statement`, the page it is on, a confidence and a reason.

    First the author's own sentence is looked up verbatim: when a paper is
    quoting a paper, the sentence really is in the source and the quote needs no
    judgement at all.  Failing that, the most relevant page is chosen by shared
    content terms and its best-matching sentence is proposed - a real sentence,
    from the right page, that the author still has to read before trusting it.
    """
    match = matching.find_in_pages(statement, pages, page_hint=page_hint)
    if match.found and match.page is not None:
        # The matcher can see a sentence that runs over a page break, so the
        # verbatim search has to look at the same text it looked at.  Asking
        # only `match.page` means asking the first page of the run, whose own
        # sentences do not contain a sentence that ends on the next page: the
        # verbatim branch then missed, and the proposal fell back to the
        # medium-confidence path, which quoted the half of the sentence that
        # did fit on one page.  Measured on a sentence printed across pages 2
        # and 3: `1 claim block(s) proposed (0 verbatim)` and `confidence:
        # medium`, where the same sentence wholly on one page gave `1 verbatim`
        # and `confidence: high`.
        covering = [page for page in pages if page.number in match.spanned]
        joined = " ".join(page.text.strip() for page in covering).strip()
        verbatim = _verbatim_sentence(joined, statement)
        if verbatim:
            return (
                verbatim,
                match.page,
                "high",
                "the manuscript's sentence appears verbatim in the source",
            )
    wanted = terms_of(statement)
    if not wanted:
        return None
    best: tuple[int, int, int, str, int] | None = None
    for page in pages:
        for position, sentence in enumerate(_sentences_of(page.text)):
            if not _is_passage(sentence):
                continue
            shared = len(wanted & terms_of(sentence))
            if shared < MIN_MEDIUM_TERMS:
                continue
            # Most shared terms win; ties go to the earlier page, then to the
            # earlier sentence.  Length is not a tiebreak: preferring the longer
            # of two equally relevant sentences prefers the one with more room
            # to be a table.
            rank = (-shared, page.number, position)
            if best is None or rank < best[:3]:
                best = (rank[0], rank[1], rank[2], sentence, page.number)
    if best is None:
        return None
    shared = -best[0]
    quote = best[3]
    number = best[4]
    return (
        quote,
        number,
        "medium",
        f"the best sentence on the most relevant page ({shared} shared terms); "
        "read it before trusting the claim",
    )


def _verbatim_sentence(page_text: str, statement: str) -> str:
    """The source's own wording of `statement`, if it is there to be found.

    The manuscript's sentence and the source's sentence differ in whitespace and
    punctuation at least, so they are compared folded and then recovered from
    the page by length rather than by an exact string search.
    """
    wanted = statement.strip()
    if not wanted:
        return ""
    for sentence in _sentences_of(page_text):
        if normalize(sentence) == normalize(wanted):
            return sentence
    squashed = re.sub(r"\s+", "", normalize(wanted))
    for sentence in _sentences_of(page_text):
        if re.sub(r"\s+", "", normalize(sentence)) == squashed:
            return sentence
    return ""


def _claim_id(key: str, used: set[str]) -> str:
    base = re.sub(r"[^A-Za-z0-9_-]+", "-", key).strip("-") or "claim"
    candidate = base
    while candidate in used:
        candidate = f"{base}-{len(used) + 1}"
    used.add(candidate)
    return candidate


def _why_no_file(
    key: str,
    table: sources.SourceTable | None,
    bib: dict[str, BibEntry] | None = None,
    bib_unreadable: set[str] | None = None,
) -> str:
    """Say which of the three ways a key can have no local file actually happened.

    The sentence used to be one string for every case: "no local file: not in
    sources.toml, no `file` field in the bibliography, and no file named after
    the key".  It reads as a summary of what was searched, and it is a lie in
    the case that matters most - a key whose `sources.toml` line is there but
    points at a file that has moved.  The author is told the manifest does not
    mention their key while they are looking at the line that mentions it.

    The table knows better for two of the cases, and both readers of the
    manifest should say the same thing about the same project.

    The bibliography knows better for a third, and it was the same lie one file
    over: a key whose `file` field names a path that has moved was reported as
    having no `file` field at all.  Measured before this branch existed, with
    `file={gone.txt}` in the entry and nothing else on disk::

        line 1: paper - no local file: not in sources.toml, no `file` field in
        the bibliography, and no file named after the key

    The author opens the .bib, sees the field, and stops trusting the report.
    """
    if table is not None:
        reason = sources.explain_unresolved(key, table)
        if reason:
            return f"no local file: {reason}"
    entry = (bib or {}).get(key)
    if entry is not None:
        named = _bib_file(entry)
        if named:
            return (
                f"no local file: the `file` field for {key!r} in the bibliography "
                f"names {named!r}, and that file is not there"
            )
    if bib_unreadable and key in bib_unreadable:
        # The citation key is in the file, the entry is not.  Saying the
        # bibliography has no `file` field sends the author to look at the
        # field they are staring at.
        return (
            "no local file: the bibliography could not be fully read, so no "
            f"entry was parsed for {key!r} - fix the entry and run this again"
        )
    return (
        "no local file: not in sources.toml, no `file` field in the "
        "bibliography, and no file named after the key"
    )


def _bib_keys_without_entries(paths: Sequence[Path], bib: dict[str, BibEntry]) -> set[str]:
    """Keys the bibliography names but no parsed entry answers for.

    A file that does not fully parse still *names* keys - in the entry header,
    in a `file` field - while producing no entry for them.  ``draft`` then has
    a citation key it cannot resolve and, without this set, cannot tell "the
    bibliography never mentioned it" from "the bibliography never made it that
    far".  Measured before this existed, with an unclosed entry holding
    ``file = {page.txt}``::

        <!-- line 1: knuth2020 - no local file: not in sources.toml, no `file`
        field in the bibliography, and no file named after the key -->

    The author opens the `.bib`, sees the field on line 5, and stops trusting
    the report.  Only keys already absent from ``bib`` are returned: a key that
    did parse has an answer and does not need this.
    """
    out: set[str] = set()
    for path in paths:
        try:
            text = read_text(path)
        except OSError:
            continue
        for match in _BIB_KEY.finditer(text):
            key = match.group(1)
            if key not in bib:
                out.add(key)
    return out


def draft(
    text: str,
    *,
    bib: dict[str, BibEntry],
    known: dict[str, str],
    root,
    table: sources.SourceTable | None = None,
    page_cache: dict | None = None,
    max_terms: int = 0,
    taken_ids: set[str] | None = None,
    bib_unreadable: set[str] | None = None,
    manuscript: str = "",
    manuscript_digest: str = "",
    # Whether reading the manuscript this tool's way had to replace a byte.
    # It travels beside the text because the sentences judged below came out
    # of that read: in a lossless file a replacement character is one the
    # author wrote, and a paper about encodings is full of them.
    manuscript_lost: bool = False,
) -> Draft:
    """Read `text` and write down what could be proposed for it.

    ``taken_ids`` is the set of claim ids the manuscript already uses, and it is
    not optional in spirit: `draft` proposes blocks for a file that is about to
    be read next to the original, and a proposal whose id the manuscript already
    has produces a file where `check` reports `claim-uncheckable` - "claim id
    'paper' is used twice ... the second is ignored" - so the block the author
    just pasted is silently not the one being checked.  Measured before this
    parameter existed: a manuscript holding `id=paper` and one uncited-looking
    sentence got a proposal also named `paper`, and appending it (the only thing
    the tool tells you to do) turned a working project into a high-severity
    one.  The author copies one block; the tool must not hand them a collision.
    """
    pages_for: dict[str, list] = page_cache if page_cache is not None else {}
    result = Draft()
    used_ids: set[str] = set(taken_ids or ())
    seen: set[tuple[int, str]] = set()
    proposed_quotes: set[str] = set()
    sites = citation_sites(text)
    result.no_citations = not sites
    # Only a reading that lost bytes explains missing characters; in a lossless
    # file every replacement character is the author's, so nothing here is a
    # decoding problem and the summary must not call it one.
    result.undecodable = text.count(UNDECODED) if manuscript_lost else 0
    for site in sites:
        sentence, _, _ = sentence_at(text, site.start)
        if (site.start, site.key) in seen:
            continue
        seen.add((site.start, site.key))
        # A sentence whose own characters were never decoded cannot be compared
        # with a page, and pretending otherwise produces a fact about the page
        # that is really a fact about the file.  Measured on a GBK manuscript
        # whose `[@paper]` survived the damage: `draft` proposed nothing and
        # wrote `nothing on any page shares enough terms with the sentence (3
        # needed)` - a true sentence about a comparison nobody should have run,
        # because the sentence it compared was 96 replacement characters.  The
        # page was never the problem, so it is not named.
        undecoded = sentence.count(UNDECODED) if manuscript_lost else 0
        if undecoded:
            name = Path(manuscript).name if manuscript else "the manuscript"
            result.skipped.append(
                Skipped(
                    key=site.key,
                    reason=(
                        f"the sentence this cites was never decoded: "
                        f"{count_of(undecoded, 'character')} of it are replacement "
                        f"characters, so no page was searched for it - {name} is not "
                        "UTF-8. Convert it first, for example "
                        f"`iconv -f GBK -t utf-8 {name} > utf8.md`"
                    ),
                    line=site.line,
                )
            )
            continue
        statement = statement_of(sentence)
        path, needs_line = resolve(site.key, known, bib, root)
        if path is None:
            result.skipped.append(
                Skipped(
                    key=site.key,
                    reason=_why_no_file(site.key, table, bib, bib_unreadable),
                    line=site.line,
                )
            )
            continue
        # The file this key resolved to is the manuscript we are reading, or a
        # byte-for-byte copy of it.  Measured before this branch existed: a
        # manifest mapping the key to `paper.md` produced a block quoting a
        # sentence out of `paper.md`, and pasting it - the only thing this
        # command tells an author to do - made `check` report
        # `[high] source-is-manuscript`.  `scan` and `verify` both refuse this
        # file already; a command that manufactures the finding is worse than
        # the silence it replaced, because the author trusts what it writes.
        if is_the_manuscript(_resolve(Path(root), path), manuscript, manuscript_digest):
            result.skipped.append(
                Skipped(
                    key=site.key,
                    reason=(
                        f"the file for {site.key} is this manuscript, so it cannot be "
                        "the evidence for its own sentences - point the key at the "
                        "source paper"
                    ),
                    line=site.line,
                )
            )
            continue
        if needs_line is not None:
            result.needed_sources[site.key] = path
        # `path` is what the proposal will write into `sources.toml`, so it is
        # relative to the project root: `page.txt` means `<root>/page.txt`.
        # `extract_pages` opens what it is given against the process directory,
        # so from one level above the project - `citevouch draft paper/m.md
        # --root paper` - it looked for `./page.txt`, found nothing, and the
        # proposal said `source file page.txt does not exist` about a file
        # sitting right there.  Measured before this line existed, same project,
        # only the working directory differing: 1 proposal from inside, 0 from
        # outside.  `_resolve` is the one rule the other five commands use.
        source = _resolve(Path(root), path)
        if source not in pages_for:
            pages, problem = sources.extract_pages(source, root)
            if problem is not None:
                result.unreadable.append(
                    Skipped(key=site.key, reason=problem.message, line=site.line)
                )
                pages_for[source] = []
                continue
            pages_for[source] = pages
        found = propose_quote(statement, pages_for[source])
        if found is None:
            result.skipped.append(
                Skipped(
                    key=site.key,
                    reason="nothing on any page shares enough terms with the sentence "
                    f"({MIN_MEDIUM_TERMS} needed)",
                    line=site.line,
                )
            )
            continue
        quote, page, confidence, reason = found
        # Two citations of the same paper often want the same sentence. Writing
        # it twice produces a file an author has to prune by hand and, worse,
        # reads as a tool that did not look at the second claim at all.
        if quote in proposed_quotes:
            result.skipped.append(
                Skipped(
                    key=site.key,
                    reason="the best available passage is already proposed for an "
                    "earlier citation; the source has nothing more specific to say "
                    "about this sentence",
                    line=site.line,
                )
            )
            continue
        proposed_quotes.add(quote)
        result.proposals.append(
            Proposal(
                claim_id=_claim_id(site.key, used_ids),
                source_key=site.key,
                quote=quote,
                page=page,
                statement=statement,
                confidence=confidence,
                reason=reason,
                line=site.line,
            )
        )
    return result


def _block(proposal: Proposal) -> list[str]:
    body = proposal.quote.splitlines() or [""]
    claim_body = proposal.statement.splitlines() or [""]
    page = f" page={proposal.page}" if proposal.page is not None else ""
    lines = [
        f"<!-- confidence: {proposal.confidence} - {proposal.reason} -->",
        f"```claim id={proposal.claim_id} source={proposal.source_key}{page}",
        "quote: |",
    ]
    lines.extend(f"  {line}" for line in body)
    lines.append("claim: |")
    lines.extend(f"  {line}" for line in claim_body)
    lines.append("```")
    return lines


def render(
    result: Draft,
    manuscript_name: str = "manuscript.md",
    converted: bool = False,
    included: Sequence[str] = (),
) -> str:
    """The proposals file, which is also an ordinary manuscript.

    ``converted`` says the text this ran on was produced by ``latex.to_text``,
    which drops the preamble, the comments and every environment it does not
    model.  The line numbers in the "Not proposed" block are counted against
    that text, so on a ``.tex`` manuscript they point at the wrong line of the
    file the author is holding.  Saying so costs one comment line; not saying so
    sends the reader to look at a line that holds something else.

    ``included`` names the files an ``\\input`` or ``\\include`` pulls in, which this
    command does not read.  A paper split across files keeps its citations in
    the parts, so without this line the output is a clean zero that says
    nothing about the half of the paper it never opened.
    """
    proposed = len(result.proposals)
    high = sum(1 for proposal in result.proposals if proposal.confidence == "high")
    out: list[str] = [
        f"<!-- Generated by `citevouch draft` from {manuscript_name}. -->",
        "<!--",
        f"  {proposed} claim block(s) proposed: {high} quoting the sentence verbatim,",
        f"  {proposed - high} proposing a passage from the most relevant page.",
        "  Nothing here has been checked by anything but the verifier - run",
        "  `citevouch scan` on this file and read the medium entries before",
        "  copying any of them into the real manuscript.",
        "-->",
    ]
    if result.no_citations:
        # Nothing to propose and no way to tell the author why from the counts
        # alone: zero proposals with zero skipped citations means this command
        # never found a citation, not that it found unusable ones.
        if result.undecodable:
            # Two different reasons produce the same zero, and only one of them
            # is about the author's markers.  A GBK file read as UTF-8 has its
            # `[` and `@` eaten by two-byte pairs, so it arrives here with no
            # citations at all - and telling that author "your citations were
            # written in an unsupported form" sends them to rewrite a line that
            # was already correct.
            out.append(
                "<!-- No citations were found because this file was never "
                f"decoded: {result.undecodable} character(s) of it are "
                "replacement characters, which is what a decoder writes where "
                "it could not read a byte. Convert the file to UTF-8 first, for "
                "example `iconv -f GBK -t utf-8 " + manuscript_name + " > "
                "utf8.md`, and run this command on the converted file. -->"
            )
        else:
            out.append(
                "<!-- No citations were found in the text, so there was nothing to "
                "propose. This command reads two forms: Pandoc's `[@key]` and "
                "LaTeX's `\\cite{key}`. A citation written any other way - "
                "`(Van Eecke 2026)`, a bare `@key` without brackets, a reference "
                "typed by hand - is invisible to it. -->"
            )
    if included:
        out.append(
            "<!-- This document pulls text in from "
            + ", ".join(included)
            + ", which `citevouch draft` does not read: any"
            + " citation in those files is missing from the blocks below. -->"
        )
    if converted:
        out.append(
            "<!-- Line numbers below count the LaTeX-converted text, not "
            f"{manuscript_name}: the preamble, comments and unmodelled "
            "environments were dropped before this ran. -->"
        )
    out.append("")
    if result.needed_sources:
        out.extend(
            [
                "The keys below resolved to a file but are not in `sources.toml`.",
                "Add these lines to the `[sources]` table, or pass them with",
                "`--source`, before scanning this file:",
                "",
                "```toml",
                "[sources]",
            ]
        )
        out.extend(f'{key} = "{path}"' for key, path in sorted(result.needed_sources.items()))
        out.extend(["```", ""])
    for proposal in result.proposals:
        out.extend(_block(proposal))
        out.append("")
    if result.skipped or result.unreadable:
        out.append("Not proposed:")
        out.append("")
        for item in result.skipped + result.unreadable:
            out.append(f"<!-- line {item.line}: {item.key} - {item.reason} -->")
        out.append("")
    return "\n".join(out)


def summarize(result: Draft) -> str:
    proposed = len(result.proposals)
    high = sum(1 for proposal in result.proposals if proposal.confidence == "high")
    missing = len(result.skipped) + len(result.unreadable)
    if result.no_citations:
        if result.undecodable:
            return (
                "0 claim block(s) proposed: this file was never decoded "
                f"({result.undecodable} character(s) of it are replacement "
                "characters), so no citation in it could be found - convert it "
                "to UTF-8 first"
            )
        return (
            "0 claim block(s) proposed: no citations were found to propose them "
            "for (this command reads `[@key]` and `\\cite{key}`)"
        )
    return (
        f"{proposed} claim block(s) proposed ({high} verbatim), "
        f"{missing} citation(s) left as comments"
    )
