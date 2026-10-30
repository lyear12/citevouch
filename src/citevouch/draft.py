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
from .model import BibEntry
from .textnorm import normalize, numbers_in

# Pandoc's bracket form: `[@key]`, `[@a; @b]`, `[-@key]`.  This is what people
# writing Markdown actually use, so it is the primary dialect.
_PANDOC = re.compile(r"\[(?P<body>(?:\s*-?@[A-Za-z0-9_.:\-]+[;,])*\s*-?@[A-Za-z0-9_.:\-]+)\]")
_AT_KEY = re.compile(r"-?@(?P<key>[A-Za-z0-9_.:\-]+)")
# LaTeX's forms, because much of the audience types Markdown in an editor that
# still has `.tex` habits and half of a draft arrives already using these.
_LATEX = re.compile(
    r"\\(?:cite|citep|citet|citealp|citealt|citeauthor|citeyear|nocite)"
    r"\*?(?:\[[^\]]*\])*\{([^}]*)\}"
)

# A sentence ends at terminal punctuation followed by space, or at the end of a
# paragraph.  `re.split` keeps the text; offsets are recomputed from a scan so
# line numbers stay correct.
_SENTENCE_END = re.compile(r"(?<=[.!?。！？])[\"'”’)\]]*(?:\s+|$)")

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

MIN_SENTENCE = 40
MAX_SENTENCE = 400
"""Characters a passage needs to be worth reading as evidence, and its ceiling.

Below forty characters there is no sentence, only a label or a table cell - the
kind of fragment that "supports" anything.  Above four hundred the page text is
not a sentence at all: it is a figure caption, a results table or a wrapped
list, and proposing it would put a block of layout in the manuscript's mouth.
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
    sites.sort(key=lambda site: site.start)
    return sites


def sentence_at(text: str, start: int) -> tuple[str, int, int]:
    """The sentence around `start`, as ``(text, start, end)``.

    A citation is part of the sentence that cites it, so the claim text is that
    whole sentence with the marker cut out.  Splitting on paragraphs first keeps
    a heading from being glued onto the sentence under it.
    """
    para_start = text.rfind("\n\n", 0, start)
    para_start = 0 if para_start < 0 else para_start + 2
    para_end = text.find("\n\n", start)
    para_end = len(text) if para_end < 0 else para_end
    cursor = para_start
    for sentence in _SENTENCE_END.split(text[para_start:para_end]):
        if not sentence:
            continue
        begin = text.find(sentence, cursor, para_end)
        if begin < 0:
            begin = cursor
        end = begin + len(sentence)
        cursor = end
        if begin <= start < end:
            return sentence.strip(), begin, end
    return text[para_start:para_end].strip(), para_start, para_end


def statement_of(sentence: str) -> str:
    """The sentence without its citation markers, ready to be a `claim:` line."""
    text = _PANDOC.sub("", sentence)
    text = _LATEX.sub("", text)
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
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
            base = Path(entry.path).parent if entry.path else Path(root)
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


def _is_passage(sentence: str) -> bool:
    """Whether a run of text is a sentence a person would quote.

    Four things disqualify a candidate, and each one was found by running this
    on a real paper rather than by imagining a bad input: a fragment too short
    to assert anything, a block too long to be a sentence, a run that is mostly
    digits and punctuation (a results table), and a run with several
    ``label: value`` pairs in it (a printed report embedded in the page).
    """
    if not MIN_SENTENCE <= len(sentence) <= MAX_SENTENCE:
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
        found = next((page for page in pages if page.number == match.page), None)
        if found is not None:
            verbatim = _verbatim_sentence(found.text, statement)
            if verbatim:
                return (
                    verbatim,
                    found.number,
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


def draft(
    text: str,
    *,
    bib: dict[str, BibEntry],
    known: dict[str, str],
    root,
    page_cache: dict | None = None,
    max_terms: int = 0,
) -> Draft:
    """Read `text` and write down what could be proposed for it."""
    pages_for: dict[str, list] = page_cache if page_cache is not None else {}
    result = Draft()
    used_ids: set[str] = set()
    seen: set[tuple[int, str]] = set()
    proposed_quotes: set[str] = set()
    for site in citation_sites(text):
        sentence, _, _ = sentence_at(text, site.start)
        if (site.start, site.key) in seen:
            continue
        seen.add((site.start, site.key))
        statement = statement_of(sentence)
        path, needs_line = resolve(site.key, known, bib, root)
        if path is None:
            result.skipped.append(
                Skipped(
                    key=site.key,
                    reason="no local file: not in sources.toml, no `file` field in the "
                    "bibliography, and no file named after the key",
                    line=site.line,
                )
            )
            continue
        if needs_line is not None:
            result.needed_sources[site.key] = path
        if path not in pages_for:
            pages, problem = sources.extract_pages(path, root)
            if problem is not None:
                result.unreadable.append(
                    Skipped(key=site.key, reason=problem.message, line=site.line)
                )
                pages_for[path] = []
                continue
            pages_for[path] = pages
        found = propose_quote(statement, pages_for[path])
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
    return (
        f"{proposed} claim block(s) proposed ({high} verbatim), "
        f"{missing} citation(s) left as comments"
    )
