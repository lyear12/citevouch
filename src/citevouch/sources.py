"""Source documents: resolving them, extracting their text, caching the result.

Extraction is the slowest and least deterministic part of the pipeline, so it
is done once and cached by content hash.  A cache keyed by hash means editing
a PDF invalidates exactly that PDF and nothing else, and two manuscripts that
share a corpus share the cache.

The cache lives under ``.citevouch/cache`` next to the ledger.  It is
disposable: deleting it costs time, never correctness.
"""

from __future__ import annotations

import hashlib
import html
import json
import logging
import os
import re
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from shutil import which

from ._version import __version__
from .errors import UsageError, why_not_a_file
from .model import Finding, SourceRef
from .textnorm import (
    _noise,
    count_of,
    declared_reading,
    fold,
    invalid_utf8_share,
    proven_codec,
    read_text,
)

CACHE_DIRNAME = ".citevouch"
CACHE_SUBDIR = "cache"

#: The suffixes this tool has a reader for.  Everything else falls through to
#: "try pdftotext, then read it as text", which is a guess - and a guess worth
#: checking against the file's own first bytes (see ``_opaque_format``).
_KNOWN_SUFFIXES = frozenset({".txt", ".md", ".text", ".html", ".htm", ".xml", ".pdf"})
# Only the two formats that cost nothing to support. YAML used to be listed here
# and skipped in the loop below, which is the worst of both: the name says
# "supported" and the code says nothing at all. A manifest we cannot read is a
# manifest we should not advertise.
MANIFEST_NAMES = ("sources.toml", "sources.json")


def _resolve(root: Path, raw: str) -> Path:
    """Resolve ``raw`` against ``root``, but accept a path that already works.

    ``citevouch check demo/manuscript.md --root demo`` is what people type, and
    joining it blindly would look for ``demo/demo/manuscript.md``.  A path that
    exists as given is never re-rooted: the file on disk is the authority.

    This lives here rather than in :mod:`citevouch.scan` because ``--source``
    is one of its callers and ``scan`` imports this module.  It was written for
    the manuscript flag, and every path flag inherited it except the one that
    could not import it: measured, with the project in ``paper/`` and the
    command typed from one level above, ``--bib paper/refs.bib`` resolved and
    ``--source paper/page.txt`` was refused with ``source paper\\paper\\page.txt
    does not exist``.  One flag asking for a different spelling than the other
    six is a spelling the author has to learn from the error message.
    """
    path = Path(raw)
    if path.is_absolute():
        return path
    if path.exists():
        return path
    return Path(root) / path


@dataclass
class PageText:
    number: int
    text: str
    folded: str = ""

    def __post_init__(self) -> None:
        if not self.folded:
            self.folded = fold(self.text)

    def to_json(self) -> dict:
        return {"number": self.number, "text": self.text}


@dataclass
class SourceText:
    key: str
    path: str
    pages: list[PageText] = field(default_factory=list)
    sha256: str = ""

    @property
    def page_count(self) -> int:
        return len(self.pages)

    def ref(self) -> SourceRef:
        return SourceRef(
            key=self.key, path=self.path, sha256=self.sha256, pages=len(self.pages)
        )


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cache_root(root: str | Path) -> Path:
    return Path(root) / CACHE_DIRNAME / CACHE_SUBDIR


def _cache_file(root: str | Path, sha: str) -> Path:
    return cache_root(root) / f"{sha}.json"


def extractor_candidates(suffix: str) -> tuple[str, ...]:
    """The readers that could produce this file's text, best first.

    A cache keyed only by the source's own hash is a cache that never notices
    the *reader* changing. Upgrading pypdf can change the text a page yields -
    and a ledger verified against the old text would go on saying
    ``quote-found`` about a page that no longer contains the quote. So the
    reader is part of the cache key.

    Both ends are named. This function says which readers *could* run, which is
    all a cache lookup can know before extracting; ``extract_pages`` records
    the one that actually ran, and a hit requires the recorded name to be one
    of these. Recording the prediction instead was a real bug: pypdf is present
    but cannot read a given PDF, pdftotext does the work, and the entry says
    "pypdf" - so upgrading poppler never invalidates it.

    The pypdf name carries its version because that is the library whose
    extraction we are trusting; "pdftotext" does not, because asking its
    version would mean spawning a process on every run, and the binary is
    rarely upgraded in place.

    ``extract_pages`` passes the suffix it decided to read the file *as*, which
    is not always the suffix the file carries: a PDF named ``.txt`` is read by
    the PDF readers, so its cache entry is stored under their names.  That is
    what stops the mojibake an earlier run cached as "plain" from being handed
    back after the fix.
    """
    suffix = suffix.lower()
    if suffix in (".txt", ".md", ".text"):
        return ("plain",)
    if suffix in (".html", ".htm", ".xml"):
        return ("markup",)
    if suffix == ".pdf":
        try:
            import pypdf

            return (f"pypdf-{getattr(pypdf, '__version__', 'unknown')}", "pdftotext")
        except ImportError:
            return ("pdftotext",)
    return ("pdftotext", "plain")


def _load_cache(root: str | Path, sha: str, accepted: tuple[str, ...]) -> list[PageText] | None:
    """The cached pages for this file, or ``None`` to extract it again.

    Every reason to mistrust the file ends the same way - ``None``, a cache
    miss, one more extraction. That is the opposite of what ``Ledger.from_json``
    does with a damaged ledger, and the difference is worth stating: a ledger is
    *the record* of what the author claimed against which source, and it cannot
    be recomputed from anything else, so a shape it does not recognise is
    refused out loud. A cache is *a hint* about what some reader produced for
    these exact bytes - the bytes are still here, so the hint can simply be
    dropped and the fact recomputed. Refusing here would turn a scratch file
    into a finding about the author's evidence.

    What must not happen is the third option: raising. Before this, a cache
    directory holding ``{"pages": 5}``, ``{"pages": [null]}`` or a page with a
    non-numeric ``number`` reached the interpreter and exited **1** - the code
    that means "findings at or above --fail-on" - with a traceback. Measured:
    ``TypeError: 'int' object is not iterable``, ``AttributeError: 'NoneType'
    object has no attribute 'get'``, ``ValueError: invalid literal for int()``.
    """
    path = _cache_file(root, sha)
    if not path.exists():
        return None
    try:
        blob = json.loads(read_text(path))
    except (OSError, ValueError):
        return None
    if not isinstance(blob, dict):
        return None
    if blob.get("schema") != 1:
        return None
    if blob.get("tool") != __version__ or blob.get("extractor") not in accepted:
        # Written by another build, or by a reader that is not the one about to
        # run. Re-extracting costs a second; trusting stale text costs a
        # verdict, and a wrong verdict is the only failure this tool cannot
        # apologise for.
        return None
    raw_pages = blob.get("pages")
    if not isinstance(raw_pages, list):
        return None
    pages: list[PageText] = []
    for index, raw in enumerate(raw_pages):
        if not isinstance(raw, dict):
            return None
        number = raw.get("number", index + 1)
        text = raw.get("text", "")
        # bool is an int to isinstance and is not a page number; a page number
        # below one cannot have come from this tool and would index nothing.
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            return None
        if not isinstance(text, str):
            return None
        pages.append(PageText(number=number, text=text))
    return pages or None


def _store_cache(root: str | Path, sha: str, pages: list[PageText], extractor: str) -> None:
    path = _cache_file(root, sha)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": 1,
            "sha256": sha,
            "tool": __version__,
            "extractor": extractor,
            "pages": [p.to_json() for p in pages],
        }
        # The pid keeps two scans running side by side from writing over each
        # other's half-finished temp file.
        tmp = path.with_suffix(f".json.{os.getpid()}.tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
        os.replace(tmp, path)
    except OSError:
        # A read-only checkout must still work; the cache is an optimisation.
        pass


@contextmanager
def _quiet_pypdf() -> Iterator[None]:
    """Silence the log lines pypdf writes about a file we already handle.

    pypdf reports a damaged file twice: once by logging
    (``pypdf._reader`` warns "invalid pdf header: b'not a'" and "EOF marker not
    found") and once by raising.  We catch the exception and turn it into a
    finding that says the same thing with more detail, so the log lines are a
    worse copy of a fact the author already gets - and they land on stderr,
    next to a run that exits 1, where nobody looks for them.  Measured before
    this: one unreadable source printed four lines of pypdf's warnings around
    the single line citevouch wrote.

    A context manager rather than a process-wide setting keeps the suppression
    to the reads that expect trouble; anything else keeps pypdf's logging.
    """
    quiet = logging.getLogger("pypdf")
    previous = quiet.level
    quiet.setLevel(logging.ERROR)
    try:
        yield
    finally:
        quiet.setLevel(previous)


def _pypdf_pages(path: str | Path) -> tuple[list[str], str] | None:
    """Pages from pypdf, named with the version whose behaviour they encode."""
    try:
        import pypdf
        from pypdf import PdfReader
    except ImportError:
        return None
    name = f"pypdf-{getattr(pypdf, '__version__', 'unknown')}"
    with _quiet_pypdf():
        try:
            reader = PdfReader(str(path))
            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception:  # noqa: BLE001 - any failure means "cannot read"
                    return None
            return [(page.extract_text() or "") for page in reader.pages], name
        except Exception:  # noqa: BLE001 - a corrupt PDF is a finding, not a crash
            return None


def _pdftotext_pages(path: str | Path) -> tuple[list[str], str] | None:
    """Fallback extractor, used when pypdf is unavailable or fails."""
    for argv in (
        ["pdftotext", "-layout", str(path), "-"],
        ["pdftotext", str(path), "-"],
    ):
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
                errors="replace",
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if proc.returncode != 0 or not proc.stdout.strip():
            continue
        # pdftotext separates pages with a form feed.
        return proc.stdout.split(""), "pdftotext"
    return None


def _pypdf_importable() -> bool:
    try:
        import pypdf  # noqa: F401
    except ImportError:
        return False
    return True


def _why_both_refused(path: Path) -> list[str]:
    """What each reader said about this file, ignoring "not installed".

    Two nested guards, each with one job: ``_pypdf_importable`` asks whether
    pypdf is *installed*, which is a fact about the machine, and the ``try``
    below asks whether it could open *this file*, which is a fact about the
    file.  Collapsing them - as the original did - loses the second fact and
    leaves "install pypdf" as the only sentence available.
    """
    said: list[str] = []
    if _pypdf_importable():
        with _quiet_pypdf():
            try:
                from pypdf import PdfReader

                PdfReader(str(path))
            except Exception as exc:  # noqa: BLE001 - the sentence is the whole point
                said.append(f"{type(exc).__name__}: {exc}".rstrip(": "))
    if which("pdftotext") is not None:
        try:
            proc = subprocess.run(
                ["pdftotext", "-layout", str(path), "-"],
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
                errors="replace",
            )
        except (OSError, subprocess.SubprocessError) as exc:
            said.append(f"pdftotext: {type(exc).__name__}: {exc}".rstrip(": "))
        else:
            lines = (proc.stderr or "").strip().splitlines()
            if lines:
                said.append(f"pdftotext: {lines[0]}")
    return said


#: The first bytes of a file, and the words that name what they are.  A file
#: whose suffix this tool does not recognise is read as plain text, which is the
#: right guess for ``notes.txt`` and the wrong one for ``paper.docx``: a .docx is
#: a zip, so the read succeeds and returns the archive's bytes spelled as
#: characters.  Those pages are not empty, so nothing downstream can tell them
#: from text, and the run ends in ``quote-missing`` against the author's quote.
_OPAQUE_MAGIC: tuple[tuple[bytes, str, str], ...] = (
    (
        b"PK\x03\x04",
        "a zip archive",
        "a .docx, .odt, .epub or .xlsx - a document another program would open",
    ),
    (
        b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",
        "an OLE compound file",
        "a legacy Word, Excel or PowerPoint document (the .doc family)",
    ),
    (b"\x89PNG\r\n\x1a\n", "a PNG image", "an image, which has no text to quote"),
    (b"\xff\xd8\xff", "a JPEG image", "an image, which has no text to quote"),
    (b"GIF8", "a GIF image", "an image, which has no text to quote"),
    (b"\x1f\x8b", "a gzip stream", "a compressed file"),
    (b"BZh", "a bzip2 stream", "a compressed file"),
    (b"\xfd7zXZ", "an xz stream", "a compressed file"),
    (b"{\\rtf", "RTF", "rich text, which this tool does not parse"),
)


def _looks_like_pdf(path: Path) -> bool:
    """Whether the file opens with the PDF header, whatever it is named.

    The suffix is the author's statement about the format and this tool reads
    what it is told to read - but a PDF has its own reader here, so using it on
    a file that *is* a PDF is strictly more capable than decoding the same
    bytes as UTF-8.  Measured before this: the demo paper copied to
    ``real.txt`` extracted as 4 pages / 206,870 characters of mojibake, and a
    claim quoting the paper's own sentence came back ``quote-missing ... no
    passage in the source is close to this quote in real.txt``.  The suffix was
    right about the author's intent and wrong about the file.
    """
    try:
        with path.open("rb") as handle:
            return handle.read(5) == b"%PDF-"
    except OSError:
        return False


def _opaque_format(path: Path) -> tuple[str, str] | None:
    """What this file's own bytes say it is, when it is not text at all.

    Scoped to the suffixes this tool *guesses* at: a ``.pdf`` has its own
    readers and never needs this, and a suffix the tool knows is the author
    stating the format, so the guess this guards against has not been made.
    Only an unrecognised suffix falls through to "read it as text", and a guess
    that produces 2,544 characters of PNG for a word processor to search is
    worse than no guess at all.
    """
    try:
        with path.open("rb") as handle:
            head = handle.read(16)
    except OSError:
        return None
    for magic, name, what in _OPAQUE_MAGIC:
        if head.startswith(magic):
            return name, what
    return None


def _plain_text_pages(path: str | Path) -> list[str] | None:
    """Plain text, split on form feeds so a pdftotext dump keeps its pages."""
    try:
        text = read_text(path)
    except OSError:
        return None
    return text.split("\f")


def _markup_pages(path: str | Path) -> list[str] | None:
    """One page of tag-stripped text, or ``None`` when the file is unreadable."""
    try:
        text = read_text(path)
    except OSError:
        return None
    return [_strip_markup(text)]


def _not_text_finding(path: Path, name: str, what: str) -> Finding:
    """The sentence for a file whose bytes are a document, not words."""
    return Finding(
        code="source-not-text",
        message=(
            f"{path.name} is {name} - {what} - and citevouch reads PDF, "
            "HTML and plain text.  Convert it first, for example "
            f"`soffice --convert-to pdf {path.name}`, and point the "
            "claim at the converted file"
        ),
        path=str(path),
    )


#: How much of a text file may fail to decode before it is refused outright.
#:
#: A text file is read as UTF-8, and a file that is not UTF-8 still decodes:
#: ``errors="replace"`` turns every undecodable byte into one replacement
#: character and hands the rest through.  The result is a page of text the
#: matcher searches and does not find the author's sentence in, which comes
#: back as ``quote-missing`` - a high finding about their quote, when the fact
#: is about the file's encoding.
#:
#: Measured for this threshold, as the share of bytes that cannot start a
#: UTF-8 character: GBK 0.56, Big5 0.42, Shift-JIS 0.49, a long GBK page 0.68
#: - all of them unreadable in fact, all of them under the noise score that
#: was supposed to catch them (``max(4, len // 50)``: one to three replacement
#: characters, never four).  On the other side: cp1252 French prose 0.08, a
#: cp1252 em dash 0.03, one stray byte in English 0.02.  Those files are
#: mostly readable and their author would rather have the run than a refusal,
#: so the line sits in the gap, well clear of both groups.
MAX_UNDECODABLE_SHARE = 0.25

#: The suffixes whose bytes go through the plain-text reader.
_TEXT_SUFFIXES = (".txt", ".md", ".text", ".html", ".htm", ".xml")


def encoding_problem(path: Path, suffix: str) -> Finding | None:
    """Refuse a text file whose bytes are not text this tool can decode.

    Only the suffixes the plain-text reader owns are judged.  A PDF or a zip
    has its own reader and its own sentinels, and the plain reader never sees
    it.  A bibliography is not judged either, and the reason is measured, not
    assumed: a Chinese .bib is mostly ASCII - entry types, keys, field names,
    braces - so a GBK one scores 0.11 to 0.24 where a GBK page scores 0.62,
    and a line low enough to catch the bibliography would be cleared by a
    cp1252 French page (0.085) by a hair.  Two files that close cannot be told
    apart by this number, so the bibliography keeps its own finding.

    The check sits above the cache for the same reason the opaque-format check
    does: a run before this existed could have stored the replacement-character
    reading as pages, and a cache hit hands those pages back without ever
    looking at the bytes again.
    """
    if suffix not in _TEXT_SUFFIXES:
        return None
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if proven_codec(raw) is not None:
        # The file names its own encoding.  Refusing it would replace a
        # reading that works with a sentence about bytes, which is the
        # failure this check exists to remove, pointing the other way.
        return None
    if declared_reading(raw) is not None:
        # The document says which encoding it is in and those bytes decode
        # cleanly with it, so the reader can read this file and refusing it
        # would be the same mistake as above in a document-shaped spelling.
        # Measured before this existed: a 244-byte GBK page whose ASCII header
        # diluted the byte share to 0.168 slipped under the threshold, was
        # decoded with errors="replace", and its verbatim sentence came back
        # `[high] quote-missing`.
        return None
    share = invalid_utf8_share(raw)
    if share < MAX_UNDECODABLE_SHARE:
        return None
    return Finding(
        code="source-encoding",
        message=(
            f"{path.name} is not UTF-8: {share:.0%} of its bytes cannot be read "
            "as UTF-8, which is the only text encoding this tool reads.  Nothing "
            "in it was read.  Convert it first, for example "
            f"`iconv -f <its encoding> -t utf-8 {path.name} > utf8.txt`, and "
            "point citevouch at the converted file"
        ),
        path=str(path),
    )


def _noisy_format_problem(pages: list[PageText], path: Path, suffix: str) -> Finding | None:
    """A file read as text whose text is not text, because its name was wrong.

    A suffix this tool knows is the author stating the format, and it is
    normally right, so its bytes are not sniffed: a note beginning
    ``PK\\x03\\x04 is the four bytes a zip begins with`` is prose, and
    refusing it would trade a good reading for a guess.  What that argument
    forgot is the file that is a zip *and* is named ``.txt`` or ``.html`` -
    a .docx saved under the wrong name - and there the UTF-8 reading
    succeeds too:
    measured, a two-file docx gave 196 characters of mojibake with 47
    replacement characters and C0 controls, and the run answered the
    author's quote with ``quote-missing``.

    So the judgement is made on the text that came out, not on the bytes
    that went in: the same noise score ``_decode_text`` already uses to
    decide an encoding was wrong.  Below that score nothing is refused,
    which is what keeps the note about PK readable; above it the header
    only has to confirm what the noise already said.
    """
    # A PDF is not judged here: its bytes were already checked against the
    # PDF header, so an extraction that produced pages produced them from a
    # PDF, and its pages are allowed to carry a stray control character.
    if suffix == ".pdf":
        return None
    joined = "".join(page.text for page in pages)
    if _noise(joined) < max(4, len(joined) // 50):
        return None
    opaque = _opaque_format(path)
    if opaque is None:
        return None
    return _not_text_finding(path, *opaque)


def _no_text_problem(pages: list[PageText], path: Path, suffix: str = ".pdf") -> Finding | None:
    """A file that yielded no text at all, said in the words that fix it.

    Two very different files reach this point looking identical: a scan of a
    printed page, and a PDF built from screenshots.  Neither has a text layer,
    so both extract "successfully" and return empty strings - which the rest of
    the pipeline can only read as "your quote is not in this file".  That is a
    verdict about the author's quote when the fact is about their PDF, and the
    fix it suggests (install pypdf) is already done.  Naming the real problem
    costs one sentence and saves a user who assumes the tool is broken.

    The advice depends on the format, though.  An empty ``.txt`` was told to
    run ``ocrmypdf page.txt out.pdf``: there is no text layer in a text file,
    and no OCR can put words in a file that has none - the author's problem is
    the file, and the sentence sent them to install a tool for it.
    """
    if any(page.text.strip() for page in pages):
        return None
    if suffix in (".html", ".htm", ".xml"):
        advice = (
            "the markup holds no visible text - every word is inside a tag, a "
            "script, a style sheet, a template or a comment"
        )
    elif suffix in (".txt", ".md", ".text"):
        advice = "the file is empty, or holds nothing but whitespace"
    else:
        advice = (
            "a scan has no text layer, and OCR is what turns one into a file "
            "that can be searched (for example "
            f"`ocrmypdf {path.name} out.pdf`)"
        )
    return Finding(
        code="source-no-text",
        message=f"found no text at all in {path.name} ({len(pages)} page(s)); {advice}",
        path=str(path),
    )


def extract_pages(
    path: str | Path, root: str | Path, use_cache: bool = True
) -> tuple[list[PageText], Finding | None]:
    """Extract one source into pages, with a content-hash cache in between."""
    path = Path(path)
    if not path.is_file():
        # Two different mistakes, two different sentences. A directory is
        # present and is not a source; saying "does not exist" about something
        # the author can see in their file manager sends them looking for the
        # wrong problem.
        what = why_not_a_file(path)
        return [], Finding(
            code="source-missing",
            message=f"source file {path} {what}",
            path=str(path),
        )
    sha = sha256_file(path)
    suffix = path.suffix.lower()
    if suffix not in _KNOWN_SUFFIXES:
        # Sniffed above the cache on purpose.  A cache hit hands back pages of
        # text, so a file whose first run stored the bytes of a zip as
        # characters would keep reporting this verdict's absence from the cache
        # for as long as the file sat there.  This is the one branch where the
        # suffix is a guess, which is exactly where a wrong guess becomes a
        # verdict about the author's quote.
        opaque = _opaque_format(path)
        if opaque is not None:
            return [], _not_text_finding(path, *opaque)
    if suffix != ".pdf" and _looks_like_pdf(path):
        # The file is a PDF and says so in its first five bytes; only its name
        # disagrees.  Reading it as whatever the name claims produced 206,870
        # characters of mojibake from the demo paper, which downstream cannot
        # tell from text - so the run accused the author's quote instead of
        # naming the file.  Reading it with the PDF reader can only help: it
        # either yields the paper's own words or refuses, and a refusal is a
        # sentence about the file rather than about the quote.
        suffix = ".pdf"
    # Before the cache, for the same reason the opaque check is: the run that
    # first met this file decoded it with replacement characters and stored
    # the result as pages, and every later run would read those pages back
    # without ever looking at the bytes again.
    undecodable = encoding_problem(path, suffix)
    if undecodable is not None:
        return [], undecodable
    if use_cache:
        cached = _load_cache(root, sha, extractor_candidates(suffix))
        if cached is not None:
            # The cache holds pages, not a verdict.  A file with no text and a
            # file whose text was never asked for look the same from here, so
            # the check below has to apply to hits as well as misses; otherwise
            # the first run reports source-no-text and every run after it,
            # reading the same empty pages out of the cache, reports
            # quote-missing instead.
            # A cache holds pages, not a verdict, so a file whose first run
            # stored a zip's bytes as characters has to be judged again here;
            # otherwise every run after the first keeps searching the mojibake.
            problem = _no_text_problem(cached, path, suffix) or _noisy_format_problem(
                cached, path, suffix
            )
            return cached, problem

    # Whichever reader answers is the one recorded. Naming it from the suffix
    # alone would claim pypdf for files only pdftotext could open, and then
    # upgrading poppler would never invalidate the cache entry.
    raw: list[str] | None = None
    used = "unknown"
    if suffix in (".txt", ".md", ".text"):
        raw, used = _plain_text_pages(path), "plain"
    elif suffix in (".html", ".htm", ".xml"):
        raw, used = _markup_pages(path), "markup"
    elif suffix == ".pdf":
        # No plain-text fallback for a PDF. Reading one as UTF-8 yields pages of
        # binary noise, which is not "unreadable" as far as the rest of the
        # pipeline can tell: it would search the noise, find nothing, and report
        # quote-missing against the author's quote.
        found = _pypdf_pages(path) or _pdftotext_pages(path)
        if found is not None:
            raw, used = found
    else:
        found = _pdftotext_pages(path)
        if found is not None:
            raw, used = found
        else:
            raw, used = _plain_text_pages(path), "plain"
    if raw is None:
        return [], Finding(
            code="source-unreadable",
            message=_unreadable_message(path),
            path=str(path),
        )
    pages = [PageText(number=i + 1, text=text) for i, text in enumerate(raw)]
    _store_cache(root, sha, pages, used)
    problem = _no_text_problem(pages, path, suffix) or _noisy_format_problem(
        pages, path, suffix
    )
    return pages, problem


def _unreadable_message(path: Path) -> str:
    """Why this file yielded nothing, in the words of whoever refused it.

    Every file that reaches this point has one of four problems, and only one
    of them is about the machine: the readers are missing.  The other three -
    a truncated download, a file that is not a PDF at all, an empty file - are
    about the file, and each is fixed by something the author does to the file
    rather than to their Python.  Saying "install pypdf" for all four is the
    same mistake ``source-no-text`` was added to fix: a verdict about the
    author's evidence when the fact is about their toolchain.

    The readers are the ones that know.  pypdf raises ``EmptyFileError`` or
    ``PdfStreamError: Stream has ended unexpectedly``; poppler prints ``invalid
    pdf header`` or ``EOF marker not found``.  Both sentences were thrown away
    by the extractors above, which have to return ``None`` and nothing else so
    that a corrupt PDF stays a finding instead of a crash.  Rather than thread
    a reason out through every layer - mutable module state would leak one
    file's reason into the next file's message - this asks the readers once
    more, here, where the only thing wanted is the sentence.  It runs only on
    the failure path, which is the one path where spending the extra read is
    worth a true message.
    """
    installed: list[str] = []
    if _pypdf_importable():
        installed.append("pypdf")
    if which("pdftotext") is not None:
        installed.append("pdftotext")
    if not installed:
        return (
            f"could not read {path.name}: no PDF reader is installed. Install "
            "one with `pip install pypdf`, or put the `pdftotext` binary on "
            "PATH, and try again"
        )
    said = _why_both_refused(path)
    if not said:
        return (
            f"could not extract text from {path.name}, and neither reader said "
            "why; `citevouch doctor` reports what this machine can read"
        )
    return (
        f"could not read {path.name}: it is not a document this tool can open "
        f"({'; '.join(said)}). A truncated download, a file saved with the "
        "wrong extension, and an empty file all look like this; re-download it "
        "and check the copy is complete"
    )


# Two things this has to get right.  `>` is legal inside a quoted attribute
# value, so `<a title="a > b">` must not end at the first one - a naive
# `<[^>]+>` left `b">` glued to the page text.  And a `<` in prose is not the
# start of a tag: matching every `<...>` turned "5 < 7 and 8 > 2" into "5 2",
# so a sentence an author quoted came back `quote-missing` against a page that
# contains it.  A tag starts with a name character, `/`, `!` or `?`, and that is
# the whole rule.
_TAG = re.compile(r"<(?:[a-zA-Z/!?](?:[^<>\"']|\"[^\"]*\"|'[^']*')*?)>")


#: Elements a browser holds but never paints as page text.
#:
#: `<script>` and `<style>` were the first two names, and the defect that made
#: them worth listing - a quote that exists only inside code certified as
#: `quote-found` - is indifferent to which element it is hiding in.
#: `<template>` content is inert by specification, `<textarea>` content is a
#: form value rather than prose, and `<iframe>` content is fallback text for
#: browsers that cannot show the frame, so a sentence in any of the three came
#: back verified against a page no reader can see it on.
#:
#: `<noscript>` is deliberately absent: it is the one element whose content a
#: browser *does* show, in the configuration where it shows it, so removing it
#: would turn a quote a no-JS reader can read into `quote-missing`. `svg` is
#: absent too, because an SVG may carry real `<text>`.
_UNRENDERED_TAGS = ("script", "style", "template", "textarea", "iframe")

#: Where a region the browser never paints as words starts.
#:
#: ``(?is)`` is at the front because a global flag may not appear mid-pattern
#: (`re.error: global flags not at the start of the expression`), and the
#: comment alternative below it needs only the tag branch, not dot-matching.
_NOTHING_RENDERED_HERE = re.compile(
    rf"(?is)<({'|'.join(_UNRENDERED_TAGS)})\b(?:[^<>\"']|\"[^\"]*\"|'[^']*')*>|<!--"
)
_CLOSED = {tag: re.compile(rf"(?is)</{tag}\s*>") for tag in _UNRENDERED_TAGS}


def _without_unrendered(text: str) -> str:
    """Drop the regions of an HTML file no reader ever sees.

    A `<script>`, `<style>`, `<template>`, `<textarea>` or `<iframe>` body is
    not prose, and neither is a comment.  The old rule gave up in two places
    and the page text kept the code:

    * the end tag had to be spelled `</script>`, but HTML allows `</script >`
      and `</script\\n>`, so a formatter that writes either one left the whole
      body on the page - and a sentence that exists only inside a script was
      then certified as `quote-found`, the one failure this tool cannot
      apologise for;
    * an unterminated `<script>` (a truncated save) and an unterminated `<!--`
      matched nothing at all, so everything after them was read as prose.

    Unterminated means "to the end of the file", which is what a browser does
    too: a raw-text element that never closes swallows the rest of the
    document.
    """
    out: list[str] = []
    index = 0
    while True:
        opener = _NOTHING_RENDERED_HERE.search(text, index)
        if opener is None:
            out.append(text[index:])
            return "".join(out)
        out.append(text[index : opener.start()])
        out.append(" ")
        if opener.group(1) is None:
            close = text.find("-->", opener.end())
            index = len(text) if close < 0 else close + 3
        else:
            end = _CLOSED[opener.group(1).lower()].search(text, opener.end())
            index = len(text) if end is None else end.end()


#: What an attribute may hold before it ends the tag.
#:
#: `>` is legal inside a quoted attribute value, so a tag scanner that stops at
#: the first one cuts `<div title="a > b">` in half.  Named once here because
#: four patterns below need it.
_ATTRIBUTE_TAIL = """[^<>"']|"[^"]*"|'[^']*'"""

#: Any opening tag, with its name captured.
_OPENING_TAG = re.compile(rf"(?is)<([a-zA-Z][^\s/>]*)(?:{_ATTRIBUTE_TAIL})*>")

#: The name of an opening tag, whatever follows it.
_TAG_NAME = re.compile(r"<\s*([a-zA-Z][^\s/>]*)")

#: Elements with no content at all, so hiding one hides nothing else.
_VOID_ELEMENTS = frozenset(
    "area base br col embed hr img input link meta param source track wbr".split()
)


def _unquote(value: str) -> str:
    """An attribute value without the quotes it was written in."""
    if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
        return value[1:-1]
    return value


#: One attribute of an opening tag: its name and, when written, its value.
#:
#: A value may be double-quoted, single-quoted or bare, and an attribute may
#: have no value at all (`<p hidden>`).  Bare values cannot contain `>`, `/`
#: or whitespace, which is what ends them.
_ATTRIBUTE = re.compile(r"""(?is)([^\s=/>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]*)))?""")


def _attributes(tag: str) -> dict[str, str | None]:
    """The attributes of one opening tag, keyed by their lower-case name.

    Written as a tokeniser rather than a `\bhidden\b` search because the
    search found the word in places that are not attributes: `title="hidden"`
    and `aria-hidden="true"` both dropped the element they appeared on, and
    the sentence a sighted reader can see on the page came back
    `quote-missing` - the failure in the direction that costs an author a
    morning.  An attribute name starts where the previous value ends.
    """
    name = _TAG_NAME.match(tag)
    if name is None:
        return {}
    found: dict[str, str | None] = {}
    index = name.end()
    while True:
        match = _ATTRIBUTE.search(tag, index)
        if match is None:
            return found
        index = match.end()
        key = match.group(1).lower()
        if key == "/":
            # The `/>` that closes a self-closing tag is not an attribute.
            return found
        value = match.group(2)
        if value is None:
            value = match.group(3)
        if value is None:
            value = match.group(4)
        found.setdefault(key, value)


def _style_hides(value: str) -> bool:
    """Whether these declarations stop the browser painting the element.

    Two properties do it.  ``display: none`` removes the element and its whole
    subtree from the layout; ``visibility: hidden`` keeps the box and paints
    nothing in it.  Both cases are the same defect here: words in the file that
    no reader sees, certified as a quote on the page.

    Nothing else counts.  ``color: white``, ``font-size: 0`` and
    ``opacity: 0`` are all ways an author *can* hide text, and every one of
    them is also a way an author paints text that is meant to be read (an
    overlay, a printed stylesheet, a hover state), so treating them as hidden
    trades a false `quote-found` for a false `quote-missing` - the more
    expensive direction in a tool whose job is to help an author find evidence.
    """
    for declaration in value.split(";"):
        name, colon, text = declaration.partition(":")
        if not colon:
            continue
        name = name.strip().lower()
        text = text.strip().lower()
        if text.endswith("!important"):
            text = text[: -len("!important")].strip()
        if name == "display" and text == "none":
            return True
        if name == "visibility" and text in ("hidden", "collapse"):
            return True
    return False


def _paints_nothing(tag: str) -> str | None:
    """The element's name when the browser will paint none of its content.

    Reads the tag the way a browser decides: a `style` attribute that hides
    it, or the `hidden` attribute.  The one value of `hidden` that does not
    hide anything is `until-found`, which means "keep this out of the layout
    until the reader searches for a word in it" - the browser then paints it,
    so a quote inside it is a quote a reader can be shown.
    """
    name = _TAG_NAME.match(tag)
    if name is None:
        return None
    element = name.group(1).lower()
    attributes = _attributes(tag)
    style = attributes.get("style")
    if style is not None and _style_hides(style):
        return element
    if "hidden" in attributes:
        value = (attributes["hidden"] or "").strip().lower()
        if value != "until-found":
            return element
    return None


def _end_of_element(text: str, start: int, name: str) -> int:
    """Where this element's content stops being inside it.

    Counting, not searching: `<div style="display:none"><div>x</div>tail</div>`
    has a `</div>` that closes the *inner* element, and a scanner that stops at
    the first one would hand `tail` - which the browser does not paint either -
    back to the page text.  A tag that never closes means "to the end of the
    file", which is what a browser does with a truncated document.
    """
    pattern = re.compile(rf"(?is)<(/?)\s*{re.escape(name)}(?:{_ATTRIBUTE_TAIL})*/?>")
    depth = 1
    index = start
    while True:
        found = pattern.search(text, index)
        if found is None:
            return len(text)
        index = found.end()
        if found.group(1):
            depth -= 1
            if depth == 0:
                return index
        elif not found.group(0).rstrip().endswith("/>"):
            depth += 1


def _without_unpainted(text: str) -> str:
    """Drop the elements the document tells the browser not to paint.

    `<script>` and its neighbours are hidden by their *name*, and that list was
    the whole rule.  A browser can also be told to paint nothing about an
    element it does hold, and then the words inside are in the file and not on
    the page:

        <div style="display:none">We collected 40,688 examples.</div>
        <p hidden>We collected 40,688 examples.</p>

    Measured before this existed, all seven shapes - `display:none`,
    `visibility:hidden`, the `hidden` attribute, `aria-hidden`, a `<title>`, a
    `<datalist>` option and an ordinary `<p>` - came back `[info] quote-found`
    with exit 0 from a one-claim project whose only source was that file.  The
    first three are the bug this function fixes.  The last four are the answer
    the tool should keep giving, because a reader *can* reach those words:
    `aria-hidden` speaks to assistive technology rather than to the painter, a
    `<title>` is printed in the tab and the window bar, a `<datalist>` option is
    painted when the reader opens the list (the same reasoning that keeps
    `noscript` out of `_UNRENDERED_TAGS`), and `hidden="until-found"` is painted
    as soon as the page is searched.  Dropping any of them would flip a real
    quote into `quote-missing`, which is the more expensive error.

    Runs after `_without_unrendered`, which has already taken the raw-text
    elements out: a `<script>` inside a hidden `<div>` is gone by the time this
    reaches the `<div>`, and one pass over the remainder is enough.
    """
    out: list[str] = []
    index = 0
    while True:
        found = _OPENING_TAG.search(text, index)
        if found is None:
            out.append(text[index:])
            return "".join(out)
        out.append(text[index : found.start()])
        element = _paints_nothing(found.group(0))
        if element is None:
            out.append(found.group(0))
            index = found.end()
            continue
        out.append(" ")
        if element in _VOID_ELEMENTS:
            # `<img hidden src="...">` has no content to hide, and looking for
            # its end tag would run to the end of the document and swallow a
            # page whose images the author marked decorative.
            index = found.end()
        else:
            index = _end_of_element(text, found.end(), element)


#: Where a CDATA section starts and ends.
_CDATA = re.compile(r"<!\[CDATA\[(?P<body>.*?)\]\]>", re.DOTALL)


def _without_cdata(text: str) -> str:
    """Replace CDATA delimiters with the characters they wrap.

    `<![CDATA[ ... ]]>` means "nothing in here is markup", and a feed, a JATS
    article and an OAI-PMH record all deliver their prose inside one.  The tag
    stripper read the whole section as a single tag - `<` followed by `!` is
    exactly what a doctype looks like - so the words were dropped and the
    delimiters took their place on the page.  A quote printed on the page then
    came back `quote-missing` with the source file named, sending the author to
    look for a copy-paste mistake that was not there.

    The body is *kept as text and then still stripped of tags*, because the two
    things CDATA is used for in the wild are one literal string (`a < b`,
    preserved by the tag rule: a tag starts with a letter, `/`, `!` or `?`) and
    an HTML fragment an Atom feed will render (whose tags the reader does not
    see).  An unterminated section keeps everything it has: a truncated save
    should lose the delimiters, not the document.
    """
    out: list[str] = []
    index = 0
    while True:
        opener = _CDATA.search(text, index)
        if opener is None:
            rest = text[index:]
            marker = rest.find("<![CDATA[")
            if marker < 0:
                out.append(rest)
                return "".join(out)
            out.append(rest[:marker])
            out.append(rest[marker + len("<![CDATA[") :])
            return "".join(out)
        out.append(text[index : opener.start()])
        out.append(opener.group("body"))
        index = opener.end()


def _strip_markup(text: str) -> str:
    """Reduce a markup document to the text a reader would actually see.

    Entities are decoded *after* the tags are removed, not before: decoding
    first would turn ``&lt;tag&gt;`` into something the tag regex can eat, and
    the quote an author wrote would vanish from the page it is verified
    against.
    """
    text = _without_cdata(text)
    text = _without_unrendered(text)
    text = _without_unpainted(text)
    text = _TAG.sub(" ", text)
    text = html.unescape(text)
    text = re.sub(r"&nbsp;?", " ", text)
    return re.sub(r"[ \t]+", " ", text)


# --------------------------------------------------------------------------
# Resolving a claim's source= to a file


def _unspellable(name: str) -> bool:
    """Whether this line-based reader cannot name the key tomllib would see.

    A quoted key is a name once the quotes come off - ``"knuth:2019"`` is how
    TOML spells a key that carries a colon.  A name that still holds ``=``,
    ``#``, brackets or its own quotes is one this reader splits on, so it can
    only drop the line: tomllib binds the key, the subset binds nothing, and a
    claim naming it resolves on 3.12 while reporting source-missing on 3.10.
    """
    quoted = len(name) >= 2 and name[0] in "\"'" and name[-1] == name[0]
    inner = name[1:-1] if quoted else name
    return not inner or any(char in inner for char in "=#[]\"'")


#: The characters TOML allows in a key written without quotes.
_BARE_KEY = re.compile(r"[A-Za-z0-9_-]+")


def _bare_key_is_not_a_key(name: str) -> bool:
    """Whether this unquoted key would be refused by a real TOML parser.

    A bare key is ``A-Z``, ``a-z``, ``0-9``, ``_`` and ``-`` and nothing else;
    every other character has to be quoted.  The line-based subset splits on
    ``=`` and strips, so it binds ``wang力``, ``smith/2020`` and ``smith 2020``
    as happily as ``paper`` - and the same manifest that reads on 3.10 is not
    TOML at all on 3.12, where it is reported as an unreadable file rather
    than as one entry.  Both readings are wrong about the same bytes, and
    which one an author gets depends on the interpreter they happen to run.

    A quoted key is not this question: ``"wang力"`` is legal TOML and the
    quotes come off, which is why the message below offers that spelling.

    A dotted key is not this question either.  ``smith.2020`` is legal TOML -
    it names a nested table - and the caller has a sentence of its own for
    that shape, which is the one an author can act on.  Saying "quote it"
    about a dotted key would replace the right answer with a near miss.
    """
    quoted = len(name) >= 2 and name[0] in "\"'" and name[-1] == name[0]
    if quoted or "." in name:
        return False
    return _BARE_KEY.fullmatch(name) is None


def _refuse_shapes_only_one_reader_follows(text: str) -> None:
    """Refuse the spellings the parsers would answer differently.

    Both are legal TOML that tomllib reads one way and this line-based subset
    reads another, and a manifest that binds on 3.12 while failing on 3.10 is
    the same manifest judged by whichever interpreter happens to be installed:

    * ``sources = { page = "a.txt" }`` - an inline table.  tomllib binds every
      source in it; the subset can only see one flat name.
    * ``pa.ge = "a.txt"`` - a dotted key.  tomllib reads a nested table and
      binds nothing at ``pa.ge``; the subset would bind one source called
      ``pa.ge``.
    * ``[sources]`` written twice - tomllib refuses the file; the subset merged
      the two halves into one table, so a project could pass on 3.10 with a
      manifest no 3.12 would accept.
    * ``page = "a.txt"`` written twice - tomllib refuses the file; the subset
      kept the last value, so which file a claim resolved to depended on the
      order of two lines a 3.11 interpreter would not have allowed at all.
    * ``paper = "a.txt"`` with no table header at all - tomllib binds nothing,
      the subset files it under a bucket named ``""``, and the JSON reader
      accepts exactly that shape as its normal form.  Both readers must refuse
      it, or the same manifest binds through one format and not the other.

    Both readers refuse the file, with the same sentence, so no interpreter
    reads it as something different.  Refusing here rather than in each parser
    is what makes the sentence the same one: a check written inside the subset
    can only ever speak for the subset.

    Only the places that can change what ``sources`` means are checked.  A
    dotted key under ``[other]`` is read as a nested table by both readers and
    binds no source either way, so refusing it would reject a manifest that
    answers the same question the same way - and a manifest may carry other
    tables nobody here reads.  The first version of this function checked the
    whole file and refused exactly that manifest.

    The accepted spellings are already in the README: a ``[sources]`` table
    with one `key = "path"` line per source, and the key quoted - ``"pa.ge"`` -
    when it is meant as a flat name containing a dot.
    """
    section = ""
    declared: set[str] = set()
    seen: set[tuple[str, str]] = set()
    for raw in text.splitlines():
        line = _strip_toml_comment(raw).strip()
        if not line:
            continue
        if line.startswith("["):
            name = line.strip("[]").strip()
            if name in declared:
                raise ValueError(f"[{name}] is declared twice; each table may appear once")
            declared.add(name)
            section = name
            continue
        key, sep, value = line.partition("=")
        if not sep:
            continue
        name = key.strip()
        stripped = value.strip()
        if stripped[:1] != "{" and stripped[:1] not in ('"', "'") and "=" in stripped:
            # `a=b = "x.pdf"` is two assignments on one line: tomllib refuses the
            # file, this reader binds `a` to a value it cannot read as a path.
            # One manifest, one interpreter accepts it and one does not.  An
            # inline table - `x = { y = 1 }` - holds its second `=`, so it is
            # excluded: this reader cannot follow the table either way, and a
            # table it does not read binds no source.
            raise ValueError("a line holds two '=' signs; write one `key = \"path\"` per line")
        if section == "sources" and _unspellable(name):
            raise ValueError(
                f"{name} names a source this reader cannot spell; a key here "
                "may not contain quotes, '=', '#', or brackets"
            )
        if section == "sources" and _bare_key_is_not_a_key(name):
            # A bare key TOML would refuse.  tomllib answers "this file is not
            # TOML" and the run reports the manifest as unreadable; the subset
            # below answers "here is one source" and the same project verifies.
            # Measured on `[sources]` + `wang力 = "page.txt"`, then on the same
            # line with `smith/2020`, `smith+2020`, `smith 2020`, `smith:2020`,
            # `smith@2020` and `papér`: tomllib refused every one of them and
            # the subset bound every one of them.
            raise ValueError(
                f"{name} is not a bare TOML key; quote it - "
                f'"{name}" - to bind one source under that name'
            )
        if stripped[:3] in ('"""', "'''"):
            # A multi-line string.  tomllib joins the continuation lines into
            # one value; this reader sees each of them as its own line and
            # raises on the first, which kills the whole manifest.  Refusing the
            # file with a sentence beats refusing it by accident.
            raise ValueError(
                "a value is written across lines; put it on one line - "
                '`key = "path"` - because one of the two readers of this file '
                "is line-based"
            )
        if stripped.endswith(","):
            # tomllib reads a file with no trailing comma and refuses one with,
            # so the whole manifest is legal or not on that character; the
            # subset drops the comma and binds the key.  Same file: readable and
            # unreadable.
            raise ValueError(
                "a line ends with a comma; TOML wants one `key = value` per "
                "line and no separator between them"
            )
        if not section and name == "sources" and value.strip().startswith("{"):
            raise ValueError(
                "the 'sources' table is written inline; write it as a [sources] "
                'table with one `key = "path"` line per source'
            )
        plain = len(name) < 2 or name[0] not in "\"'" or name[-1] != name[0]
        if section == "sources" and "." in name and plain:
            raise ValueError(
                f"{name!r} is a dotted key, which names a nested table in TOML; "
                f'quote it - "{name}" - to bind one source called {name!r}'
            )
        if (section, name) in seen:
            where = f"[{section}]" if section else "the top level"
            raise ValueError(f"'{name}' is given twice in {where}; each key may appear once")
        seen.add((section, name))
    # A dotted name is nested-table syntax to both readers and binds no
    # source either way, so it is not evidence of a flat manifest.
    stray = sorted(name for _, name in seen if name != "sources" and "." not in name)
    if not declared and stray:
        # Keys at the top level and no table header at all.  The JSON reader
        # accepts exactly this shape - ``{"page": "a.txt"}`` is the form the
        # docstring documents - so the same keys bind in ``sources.json`` and
        # bind nothing in ``sources.toml``, and nothing said so.
        #
        # Measured on a project whose only claim names ``paper``, with
        # ``paper = "page.txt"`` at the top of sources.toml:
        #
        #   check  -> [high] source-missing ... "no entry in sources.toml"
        #             about a key that is in that file, three lines above the
        #             manifest header the message asks for
        #   doctor -> [ok  ] manifest sources.toml (19 bytes), 0 sources, every
        #             one of them present on this machine
        #
        # "0 sources, ok" is the shape this module exists to stop: a file with
        # content reported as a file with none.  This check lives here rather
        # than in the caller because a check inside one reader speaks for one
        # reader - the subset files those keys under a bucket named ``""``, so
        # a check written against the parsed dict would refuse on 3.11 and stay
        # silent on 3.10.  Written on the text, both readers reach it.
        #
        # A file with no keys at all is not refused: an empty manifest is a
        # supported way to start, and `seen` is what tells the two apart.
        #
        # A key literally called `sources` is excluded too, and that exclusion
        # is not decoration: `sources = 5` and `sources = "page.txt"` are
        # already refused by the reader's own check, which names the key and
        # what it holds - a better sentence than this one.  Measured: without
        # the exclusion this rule fired first and replaced three of
        # `tests/test_manifest_value_shapes.py`'s assertions with a message
        # about a `[sources]` table the author does not want to add.
        raise ValueError(
            f"{count_of(len(stray), 'key')} at the top level and no [sources] "
            f"table ({', '.join(repr(k) for k in stray)}); a TOML manifest "
            "maps source keys to paths inside [sources] - add the header above "
            "them, or move them to sources.json, where the top level is the "
            "table"
        )


def _mini_toml(text: str, odd: list[str] | None = None) -> dict:
    """Parse the slice of TOML a sources manifest actually uses.

    Python 3.10 has no :mod:`tomllib`, and ``sources.toml`` is the format the
    README tells people to write.  A support floor that only holds if the user
    writes JSON is not a support floor, so the small subset is read here rather
    than dropping 3.10: ``[section]`` headers, ``key = "value"`` pairs, ``#``
    comments, and both string quoting styles.

    Structural errors - a broken table header, a line that is not ``key =
    value`` - raise :class:`ValueError`, which the caller treats exactly like a
    syntax error from tomllib: the manifest is skipped and every claim it was
    meant to bind reports ``source-missing`` naming the file rather than
    binding evidence the author never chose.

    A *value* outside that subset - ``enabled = true``, ``[1, 2]`` - is not a
    path, so it is dropped and the rest of the manifest still binds. Raising
    there would be a 3.10-only refusal of a file 3.11 accepts, and a total one:
    every other key binds nothing once the manifest is gone.

    A *quoted key* is a third case, and dropping it was the bug. It is not
    unrepresentable: it is representable once the quotes come off. A BibTeX
    style key holding a colon has to be quoted in TOML, and dropping such a key
    made one project bind on 3.11 and report ``source-missing`` on 3.10 - the
    same manifest judged by which interpreter happened to be installed. The
    quotes are syntax, so the name is kept. Only a key that cannot be spelled
    here at all - one carrying ``=``, ``#``, brackets, or its own quotes - is
    dropped, because binding a key differently than tomllib would is worse than
    not binding it.

    This is not a TOML parser and must not grow into one.  If a manifest ever
    needs dates, arrays, or nested tables, the answer is to require 3.11, not to
    add features here.
    """
    _refuse_shapes_only_one_reader_follows(text)
    parsed: dict[str, dict[str, str]] = {}
    section = ""
    declared: set[str] = set()
    seen: set[tuple[str, str]] = set()
    for raw in text.splitlines():
        line = _strip_toml_comment(raw).strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip()
            if not name or "." in name or name.startswith("["):
                raise ValueError(f"unsupported table header {line!r}")
            if name in declared:
                # tomllib refuses this - ``Cannot declare ('sources',) twice`` -
                # and merging the two halves here would bind a file that
                # interpreter never saw.  A manifest read two ways is one
                # manifest and one answer, so refuse the file this side too.
                raise ValueError(f"{line} is declared twice; each table may appear once")
            declared.add(name)
            section = name
            parsed.setdefault(section, {})
            continue
        key, sep, value = line.partition("=")
        if not sep:
            raise ValueError(f"expected key = value, got {line!r}")
        key = key.strip()
        if len(key) >= 2 and key[0] in "\"'" and key[-1] == key[0]:
            # "knuth:2019" is how a BibTeX-style key with a colon has to be
            # written in TOML. The quotes are syntax, not part of the name.
            # Dropping the whole key here used to make one manifest bind on
            # 3.11 and report source-missing on 3.10.
            key = key[1:-1]
        if not key or any(char in key for char in "=#[]\"'"):
            # Unrepresentable in this subset: a key that still carries quotes,
            # or one of the characters this line-based reader splits on.
            # Binding it differently than tomllib would is worse than dropping
            # it, so this is the only case that drops.
            continue
        if section == "" and key == "sources":
            # ``sources = "page.txt"`` at the top level, where the format wants
            # a ``[sources]`` table. tomllib returns a string here and this
            # reader would otherwise find no section at all - two different
            # answers about one file. Both are refusals of the same manifest,
            # so both raise, and the sentence says which shape was expected.
            raise ValueError(
                f"the 'sources' key holds {value.strip()!r}, not a table of keys to paths"
            )
        text_value = _toml_string_or_none(value.strip())
        if text_value is None:
            # A non-string value (true, 3.5, [a, b], {..}) is not a path, so
            # it is dropped rather than allowed to take the whole manifest
            # with it. tomllib accepts these files on 3.11+, so raising here
            # would be a 3.10-only refusal of a manifest 3.11 binds fine.
            #
            # Dropped from ``found``, but not from the reader's knowledge of
            # it: the key stays, so ``read_manifest`` can say the manifest
            # names it and the value is not a path. Passing it out is what
            # keeps 3.10 and 3.11 telling the same story - a reader that
            # reported the key here and nothing there would make the same
            # manifest bind on one interpreter and lie on the other.
            if odd is not None and section == "sources":
                odd.append(key)
            continue
        if (section, key) in seen:
            # tomllib: ``Cannot overwrite a value``.  Last-one-wins here would
            # bind the key to a path the other reader refuses to name at all,
            # so a project could be green on 3.10 and red on 3.12 for the same
            # file - and the green one is the answer nobody re-examines.
            where = f"[{section}]" if section else "the top level"
            raise ValueError(f"'{key}' is given twice in {where}; each key may appear once")
        seen.add((section, key))
        parsed.setdefault(section, {})[key] = text_value
    return parsed


def _strip_toml_comment(line: str) -> str:
    """Drop a ``#`` comment, but not one inside a quoted value."""
    quote = ""
    for index, char in enumerate(line):
        if quote:
            if char == quote and line[index - 1] != "\\":
                quote = ""
        elif char in "\"'":
            quote = char
        elif char == "#":
            return line[:index]
    return line


def _toml_string_or_none(value: str) -> str | None:
    """Read a quoted TOML string, or ``None`` when the value is not one."""
    if len(value) < 2 or value[0] not in "\"'" or value[-1] != value[0]:
        return None
    if value[:3] == value[0] * 3:
        # A multi-line string is outside the subset. Handing it back verbatim
        # would return a "path" still wearing its own quotes - a wrong answer
        # that never raises, which is worse than a dropped key.
        return None
    return _toml_string(value)


def _toml_string(value: str) -> str:
    """Read a single- or double-quoted TOML string."""
    if len(value) < 2 or value[0] not in "\"'" or value[-1] != value[0]:
        raise ValueError(f"unsupported value {value!r}")
    body = value[1:-1]
    if value[0] == "'":
        return body
    out: list[str] = []
    index = 0
    while index < len(body):
        char = body[index]
        if char == "\\" and index + 1 < len(body):
            escape = body[index + 1]
            out.append(
                {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}.get(escape, escape)
            )
            index += 2
            continue
        out.append(char)
        index += 1
    return "".join(out)


def _load_toml(text: str, odd: list[str] | None = None) -> dict:
    """Use the real parser when the interpreter has one, the subset otherwise.

    ``odd`` is how the two agree about a key whose value is not a string: the
    subset drops such a key while parsing, so it has to say so on the way past,
    and this branch says so by looking at the parsed table.  Without it the same
    manifest refused on 3.10 and silently misread on 3.11.
    """
    _refuse_shapes_only_one_reader_follows(text)
    try:
        import tomllib  # 3.11+, absent on 3.10
    except ImportError:
        return _mini_toml(text, odd)
    blob = tomllib.loads(text)
    if isinstance(blob, dict) and "sources" in blob:
        section = blob["sources"]
        if not isinstance(section, dict):
            raise ValueError(
                f"the 'sources' key holds {section!r}, not a table of keys to paths"
            )
        if odd is not None:
            odd.extend(str(key) for key, value in section.items() if not isinstance(value, str))
    return blob


def read_manifest(
    root: str | Path, odd: dict[str, str] | None = None
) -> tuple[dict[str, str], str | None]:
    """Read the ``sources`` manifest, and say why it could not be read.

    The second element is ``None`` when a manifest was found and parsed, and a
    sentence naming the problem when one exists but is not readable.  It used to
    be dropped on the floor: the caller got ``{}`` either way, so "this project
    has no manifest" and "this project's manifest is broken" arrived as the same
    value and the per-claim message below could only guess which one it was.

    ``odd`` is where a key whose value is not a path goes - ``enabled = true``,
    ``ratio = 3.5``, ``tags = []``.  Such a key is neither bound nor a parse
    failure, so neither return value can carry it: passing a dict here is how a
    caller learns "the manifest names that key and its value is not a path".
    Measured before this existed: eight such manifests all told the author "no
    entry in sources.toml" about a line they were reading, which is the exact
    sentence ``unusable`` was created to stop.
    """
    root = Path(root)
    used = [name for name in MANIFEST_NAMES if (root / name).exists()]
    if len(used) > 1:
        # Both files are here and there is no way to tell which one the
        # author meant.  The loop below used to read whichever came first
        # and never mention the other, so a project that kept a stale
        # ``sources.json`` beside its live ``sources.toml`` was resolved
        # against one of them at random - and the losing file was invisible
        # in every message, including the one telling the author to go and
        # add an entry they had already added.
        return (
            {},
            "both "
            + " and ".join(used)
            + " exist, and only one of them is read; "
            + "delete the one you are not using, or merge them",
        )
    for name in used:
        path = root / name
        wrong: list[str] = []
        try:
            text = read_text(path)
            if name.endswith(".json"):
                blob = json.loads(text)
                if not isinstance(blob, dict):
                    # `5`, `[]`, `"x"`, `true` at the root.  The old code read
                    # this as an empty manifest and reported no problem, so
                    # every claim was told "no entry in sources.json" about a
                    # file it was plainly looking at - the same wrong answer
                    # 0.19.66 fixed for the TOML path.  Measured before: a list
                    # root gave `found=[]` with `manifest_problem` empty.
                    return (
                        {},
                        f"{name} holds {type(blob).__name__}, not an object "
                        "mapping source keys to paths",
                    )
                mapping = blob.get("sources", blob)
                if mapping is None:
                    # `{"sources": null}`: the key is there and holds nothing.
                    # Reporting nothing makes the file look absent, and the
                    # advice every claim gets - "add it to sources.json" - is
                    # followed by adding a second key beside the broken one.
                    return (
                        {},
                        f"{name} has a 'sources' key whose value is null; "
                        "write it as an object of source keys to paths",
                    )
            elif name.endswith(".toml"):
                blob = _load_toml(text, wrong)
                mapping = blob.get("sources", {}) if isinstance(blob, dict) else {}
            else:
                continue
        except (OSError, ValueError) as exc:
            return (
                {},
                f"{name} could not be read as {'JSON' if name.endswith('.json') else 'TOML'} ({exc})",
            )
        if isinstance(mapping, dict):
            for key, value in mapping.items():
                if not isinstance(value, str) and odd is not None:
                    odd[str(key)] = name
            for key in wrong:
                if odd is not None:
                    odd[str(key)] = name
            # A key that does have a path still binds.  An earlier version let
            # one boolean take the whole manifest with it; refusing the file
            # here would be that bug wearing a different hat.
            return {str(k): str(v) for k, v in mapping.items() if isinstance(v, str)}, None
        if mapping:
            return (
                {},
                f"{name} has a 'sources' key that is not a table of keys to paths",
            )
    return {}, None


def load_manifest(root: str | Path) -> dict[str, str]:
    """Read a ``sources`` manifest mapping claim source keys to file paths.

    Only the two shapes that cost nothing to support are supported:

    * ``sources.json`` — ``{"vaneecke2026": "papers/2026.pdf"}``
    * ``sources.toml`` — ``[sources]`` table, same mapping

    ``sources.toml`` works on 3.10 as well as 3.11+: see :func:`_mini_toml` for
    why a subset is parsed there.  A malformed manifest yields an empty mapping
    rather than an error — use :func:`read_manifest` when the difference between
    "no manifest" and "unreadable manifest" has to reach the reader.
    """
    return read_manifest(root)[0]


@dataclass(frozen=True)
class SourceTable:
    """What the manifest and ``--source`` together bind, and what they could not.

    ``unusable`` maps a key the manifest *does* name to the sentence explaining
    why that entry cannot be used.  It exists because the previous version threw
    those entries away inside a mapping-only helper that no longer exists, and
    then reported, per claim, "no entry in sources.toml" — a false sentence
    about a project whose ``sources.toml`` was the one thing it had done right.
    """

    found: dict[str, str] = field(default_factory=dict)
    unusable: dict[str, str] = field(default_factory=dict)
    manifest_problem: str | None = None
    manifest_name: str | None = None


def read_source_table(root: str | Path, extra: list[str] | None = None) -> SourceTable:
    """Resolve every key, and keep the ones that failed along with their reason.

    ``found`` is the mapping the rest of the tool searches.  The other two
    fields exist because merging the failures into one bucket made the message
    lie:

    * ``unusable`` — the manifest names ``p`` and ``p`` is a directory, or the
      file has been moved away.  The code this replaced dropped the entry, and
      the claim that needed it was then told "no entry in sources.toml", which
      is exactly the thing the author had got right.  They go read the
      manifest, find their line, and conclude the tool is broken.
    * ``manifest_problem`` — a manifest exists but could not be parsed.  Same
      lie, one level up: the project does have an entry, and no re-reading of it
      will help.

    There used to be a second name for the first field alone, ``discover_sources``,
    kept "so callers do not change shape".  It outlived its last caller by three
    commands - every one of them was rewritten to ask for the whole table - and a
    mapping-only view is precisely the thing that loses the information the
    messages need.  Leaving it around left the next caller a way to reintroduce
    the bug by picking the tidier name.

    ``--source`` stays a hard error rather than a recorded failure: it is a
    string on the command line, so a bad one is a typo the caller can fix in
    place, not project state that a later reader has to be warned about.

    Guessing is deliberately absent. An earlier docstring promised "any file
    under ``root`` whose stem equals the key, then the longest stem the key
    starts with" and the code never had it. That was a comment describing a
    wish, and the wish was a bad one: binding a claim to a PDF because the
    filenames share a prefix yields a confident ``quote-found`` against the
    wrong paper, which is worse than ``source-missing``, which at least says
    so. If a key should resolve, the project says what it means in
    ``sources.toml``. :func:`near_misses` supplies candidates for the message,
    so the author picks instead of the tool guessing.
    """
    root = Path(root)
    found: dict[str, str] = {}
    for raw in extra or []:
        # ``--source`` is resolved by the same rule as every other path on the
        # command line.  It used to join the root unconditionally, which made
        # it the one flag where ``--source paper/page.txt --root paper`` meant
        # ``paper/paper/page.txt``; measured, that call exited 2 while the
        # identical ``--bib paper/refs.bib`` worked.
        path = _resolve(root, raw)
        if not path.is_file():
            # Refused rather than skipped. ``--source`` names a file the
            # caller wants bound to a key; dropping it silently means the
            # claim it was meant for reports ``source-missing``, and the
            # author goes looking for a missing PDF that is not missing.
            what = why_not_a_file(path)
            raise UsageError(f"source {path} {what}")
        earlier = found.get(path.stem)
        if earlier is not None and Path(earlier).resolve() != path.resolve():
            # Two ``--source`` flags land on the same key. Last-one-wins here
            # is the same defect as last-one-wins against the manifest, only
            # closer: the claim is searched for in the file the caller named
            # second, and the first one is reported as not containing it.
            raise UsageError(
                f"source key {path.stem!r} is bound twice by --source, to "
                f"{earlier!r} and to {str(path)!r}; name the files differently "
                "or pass only the one you mean"
            )
        found[path.stem] = str(path)

    odd: dict[str, str] = {}
    manifest, problem = read_manifest(root, odd)
    unusable: dict[str, str] = {}
    for key, name in odd.items():
        # The manifest names this key and the value beside it is not a path.
        # It used to vanish inside the reader, and the claim that needed it was
        # told "no entry in sources.toml" - about a line the author was looking
        # at, which is the sentence ``unusable`` exists to prevent.
        unusable[key] = (
            f"{name} binds {key!r} to something that is not a path in quotes; "
            "a number, a boolean, a list and a nested table are all not a file, "
            f"so {name} binds nothing to it"
        )
    for key, value in manifest.items():
        path = Path(value)
        if not path.is_absolute():
            path = root / path
        if path.is_file():
            previous = found.get(key)
            if previous is not None and Path(previous).resolve() != path.resolve():
                # Two sources name the same key and point at different files.
                # The older resolver let the manifest overwrite the flag, so a
                # caller who passed ``--source`` to replace one stale entry got
                # no error and no effect: the quote was searched for in the file
                # they had just tried to stop using. Refusing is not deciding
                # which side wins; it is declining to guess between two files
                # the caller can see and we cannot rank.
                raise UsageError(
                    f"source key {key!r} is bound twice, to {previous!r} by "
                    f"--source and to {str(path)!r} by {root / 'sources.toml'}; "
                    "drop one of them, or rename the file so only one binding "
                    "is left"
                )
            found[key] = str(path)
        else:
            # The value is what the author wrote, so quoting it back is more
            # useful than describing the joined path they never typed.
            unusable[key] = (
                f"sources.toml maps {key!r} to {value!r}, but {value!r} {why_not_a_file(path)}"
            )
    return SourceTable(
        found=found,
        unusable=unusable,
        manifest_problem=problem,
        manifest_name=_manifest_name(root),
    )


def _manifest_name(root: Path) -> str | None:
    """Which manifest file is on disk, if any.

    Kept separate from the parse so the name survives a manifest that
    will not parse: the message for a broken `sources.json` should still
    name `sources.json` rather than the TOML file the README uses.
    """
    for name in MANIFEST_NAMES:
        if (root / name).exists():
            return name
    return None


def explain_unresolved(key: str, table: SourceTable) -> str | None:
    """The reason ``key`` did not resolve, when the table knows one.

    ``None`` means the table has nothing to add: no manifest, the manifest does
    not mention the key, or the key simply is not there.  That is the caller's
    cue to fall back to its own sentence and its own near-miss list.

    Both readers of the manifest use this, which is the point.  ``scan`` and
    ``verify`` were telling different stories about the same broken project -
    one named the entry and its value, the other said the source "cannot be
    found any more" - because each built its message from whatever its own copy
    of the mapping had left behind.
    """
    if key in table.unusable:
        return table.unusable[key]
    if table.manifest_problem:
        return f"the manifest could not be read: {table.manifest_problem}"
    return None


def page_hint_is_valid(page: int | None, page_count: int) -> bool:
    """Whether ``page`` names a page this document actually has.

    One rule, used by both ``scan`` and ``verify``. They used to disagree: scan
    rejected ``page: 0`` as ``page-out-of-range``, and verify - which is the
    half that a reader runs, and the half ``check --use-recorded`` trusts -
    passed the same 0 to the matcher, got page 1 back, and reported
    ``quote-moved``: "quote is on page 1, the ledger says 0". The finding was
    true and the diagnosis was wrong, so the author went hunting for a
    restructuring that never happened. A hint that is not a page is not a page
    hint.

    ``page_count == 0`` means the document yielded no pages; that is a problem
    with the file, reported elsewhere, and not something this predicate can
    judge, so it says yes and lets the caller decide.
    """
    if page is None or page_count <= 0:
        return True
    return 1 <= page <= page_count


# The extensions a suggestion may point at. A manuscript is a markdown file
# too, so `.md` used to be in this set and `near_misses("readme", ...)` offered
# `README.md`: the one line of the error message a user acts on, pointing at a
# file that could never hold the quote.
SOURCE_SUFFIXES = frozenset({".pdf", ".txt"})


def candidate_files(root: str | Path) -> list[str]:
    """Paths (relative, POSIX) of files that could plausibly be a source.

    One walk per run, not one per unresolved claim: a manuscript with ten
    unbound keys would otherwise re-read the whole project ten times, and the
    project is the user's real working directory, which may hold a corpus.
    Skips hidden directories and the tool's own cache.

    Only the extensions this tool can actually read are collected. Asking for a
    key and being offered `README.md` is worse than being offered nothing: the
    suggestion is the one piece of the error message a user acts on, and it has
    to be plausible to be useful.
    """
    root = Path(root)
    if not root.is_dir():
        return []
    found: list[str] = []
    skip_dirs = {".git", ".citevouch", "__pycache__", ".venv", "venv", "node_modules"}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        relative = path.relative_to(root)
        if any(part in skip_dirs for part in relative.parts[:-1]):
            continue
        found.append(relative.as_posix())
    return sorted(found)


# Split on anything that is not alphanumeric, and again between letters and
# digits: ``vaneecke2026cxn`` should offer the ``vaneecke`` and the ``2026`` it
# shares with a file named ``2026_VanEecke-Beuls_CoNLL2026_...``.
_SPLIT = re.compile(r"[^a-z0-9]+|(?<=[a-z])(?=[0-9])|(?<=[0-9])(?=[a-z])")


def _tokens(text: str) -> set[str]:
    return {part for part in _SPLIT.split(text.lower()) if part}


def near_misses(key: str, candidates: list[str], limit: int = 3) -> list[str]:
    """Names from ``candidates`` that share tokens with ``key``, for a message.

    Suggestions to read, never bindings to use. Printing candidates is what
    lets discovery stay strict: the tool names what it saw, the author decides
    what it means.

    Matching is by whole tokens, not substring. A real project's key is
    ``vaneecke2026cxn`` and its file is
    ``2026_VanEecke-Beuls_CoNLL2026_large-scale-CxG.pdf``; neither name
    contains the other, so a substring test reported no candidates at all and
    the strict resolver's error message was the unhelpful kind. Tokens find the
    ``vaneecke`` the two do share.
    """
    if not key:
        return []
    want = _tokens(key)
    if not want:
        return []
    scored: list[tuple[int, str]] = []
    for name in candidates:
        have = _tokens(Path(name).stem)
        shared = want & have
        if shared:
            # More shared tokens first; on a tie, the name that is not wildly
            # longer, since a short file is likelier to be the one intended.
            scored.append((-len(shared), abs(len(have) - len(want)), name))
    scored.sort()
    return [name for _shared, _spread, name in scored[:limit]]


def resolve_source(key: str, known: dict[str, str]) -> str | None:
    """Look up a claim's source key. Exact, or differing only in case.

    Prefix matching used to live here: a claim naming ``vaneecke2026`` bound
    itself to whatever key started with that string, and so did a claim naming
    ``vaneecke2026cxnWRONGSUFFIX`` - a key that exists in no manifest anywhere.
    A typo therefore resolved to a real PDF and produced a confident
    ``quote-found`` on the wrong paper, which is worse than reporting that the
    key is unknown: the author never learns the page number it just cited came
    from a document they did not name.

    Exact-or-case-insensitive is the whole rule. If a project wants a shorter
    name, the manifest can map one: ``[sources]`` exists for exactly that.
    """
    if not key:
        return None
    if key in known:
        return known[key]
    lowered = key.lower()
    for name, path in known.items():
        if name.lower() == lowered:
            return path
    return None
