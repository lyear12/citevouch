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
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from ._version import __version__
from .errors import UsageError, why_not_a_file
from .model import Finding, SourceRef
from .textnorm import fold, read_text

CACHE_DIRNAME = ".citevouch"
CACHE_SUBDIR = "cache"
# Only the two formats that cost nothing to support. YAML used to be listed here
# and skipped in the loop below, which is the worst of both: the name says
# "supported" and the code says nothing at all. A manifest we cannot read is a
# manifest we should not advertise.
MANIFEST_NAMES = ("sources.toml", "sources.json")


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
    path = _cache_file(root, sha)
    if not path.exists():
        return None
    try:
        blob = json.loads(read_text(path))
    except (OSError, ValueError):
        return None
    if blob.get("schema") != 1:
        return None
    if blob.get("tool") != __version__ or blob.get("extractor") not in accepted:
        # Written by another build, or by a reader that is not the one about to
        # run. Re-extracting costs a second; trusting stale text costs a
        # verdict, and a wrong verdict is the only failure this tool cannot
        # apologise for.
        return None
    pages = [
        PageText(number=int(p.get("number", i + 1)), text=str(p.get("text", "")))
        for i, p in enumerate(blob.get("pages") or [])
    ]
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


def _pypdf_pages(path: str | Path) -> tuple[list[str], str] | None:
    """Pages from pypdf, named with the version whose behaviour they encode."""
    try:
        import pypdf
        from pypdf import PdfReader
    except ImportError:
        return None
    name = f"pypdf-{getattr(pypdf, '__version__', 'unknown')}"
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
        return proc.stdout.split("\f"), "pdftotext"
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


def _no_text_problem(pages: list[PageText], path: Path) -> Finding | None:
    """A file that yielded no text at all, said in the words that fix it.

    Two very different files reach this point looking identical: a scan of a
    printed page, and a PDF built from screenshots.  Neither has a text layer,
    so both extract "successfully" and return empty strings - which the rest of
    the pipeline can only read as "your quote is not in this file".  That is a
    verdict about the author's quote when the fact is about their PDF, and the
    fix it suggests (install pypdf) is already done.  Naming the real problem
    costs one sentence and saves a user who assumes the tool is broken.
    """
    if any(page.text.strip() for page in pages):
        return None
    return Finding(
        code="source-no-text",
        message=(
            f"found no text at all in {path.name} ({len(pages)} page(s)); a scan "
            "has no text layer, and OCR is what turns one into a file that can be "
            "searched (for example `ocrmypdf {0} out.pdf`)".format(path.name)
        ),
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
    if use_cache:
        cached = _load_cache(root, sha, extractor_candidates(suffix))
        if cached is not None:
            # The cache holds pages, not a verdict.  A file with no text and a
            # file whose text was never asked for look the same from here, so
            # the check below has to apply to hits as well as misses; otherwise
            # the first run reports source-no-text and every run after it,
            # reading the same empty pages out of the cache, reports
            # quote-missing instead.
            return cached, _no_text_problem(cached, path)

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
            message=(
                f"could not extract text from {path.name}; install pypdf "
                "(pip install pypdf) or pdftotext and try again"
            ),
            path=str(path),
        )
    pages = [PageText(number=i + 1, text=text) for i, text in enumerate(raw)]
    _store_cache(root, sha, pages, used)
    return pages, _no_text_problem(pages, path)


# Two things this has to get right.  `>` is legal inside a quoted attribute
# value, so `<a title="a > b">` must not end at the first one - a naive
# `<[^>]+>` left `b">` glued to the page text.  And a `<` in prose is not the
# start of a tag: matching every `<...>` turned "5 < 7 and 8 > 2" into "5 2",
# so a sentence an author quoted came back `quote-missing` against a page that
# contains it.  A tag starts with a name character, `/`, `!` or `?`, and that is
# the whole rule.
_TAG = re.compile(r"<(?:[a-zA-Z/!?](?:[^<>\"']|\"[^\"]*\"|'[^']*')*?)>")


def _strip_markup(text: str) -> str:
    """Reduce a markup document to the text a reader would actually see.

    Entities are decoded *after* the tags are removed, not before: decoding
    first would turn ``&lt;tag&gt;`` into something the tag regex can eat, and
    the quote an author wrote would vanish from the page it is verified
    against.
    """
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", text)
    text = _TAG.sub(" ", text)
    text = html.unescape(text)
    text = re.sub(r"&nbsp;?", " ", text)
    return re.sub(r"[ \t]+", " ", text)


# --------------------------------------------------------------------------
# Resolving a claim's source= to a file


def _mini_toml(text: str) -> dict:
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
    parsed: dict[str, dict[str, str]] = {}
    section = ""
    for raw in text.splitlines():
        line = _strip_toml_comment(raw).strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip()
            if not name or "." in name or name.startswith("["):
                raise ValueError(f"unsupported table header {line!r}")
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
        text_value = _toml_string_or_none(value.strip())
        if text_value is None:
            # A non-string value (true, 3.5, [a, b], {..}) is not a path, so
            # it is dropped rather than allowed to take the whole manifest
            # with it. tomllib accepts these files on 3.11+, so raising here
            # would be a 3.10-only refusal of a manifest 3.11 binds fine.
            continue
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


def _load_toml(text: str) -> dict:
    """Use the real parser when the interpreter has one, the subset otherwise."""
    try:
        import tomllib  # 3.11+, absent on 3.10
    except ImportError:
        return _mini_toml(text)
    return tomllib.loads(text)


def read_manifest(root: str | Path) -> tuple[dict[str, str], str | None]:
    """Read the ``sources`` manifest, and say why it could not be read.

    The second element is ``None`` when a manifest was found and parsed, and a
    sentence naming the problem when one exists but is not readable.  It used to
    be dropped on the floor: the caller got ``{}`` either way, so "this project
    has no manifest" and "this project's manifest is broken" arrived as the same
    value and the per-claim message below could only guess which one it was.
    """
    root = Path(root)
    for name in MANIFEST_NAMES:
        path = root / name
        if not path.exists():
            continue
        try:
            text = read_text(path)
            if name.endswith(".json"):
                blob = json.loads(text)
                mapping = blob.get("sources", blob) if isinstance(blob, dict) else {}
            elif name.endswith(".toml"):
                blob = _load_toml(text)
                mapping = blob.get("sources", {}) if isinstance(blob, dict) else {}
            else:
                continue
        except (OSError, ValueError) as exc:
            return (
                {},
                f"{name} could not be read as {'JSON' if name.endswith('.json') else 'TOML'} ({exc})",
            )
        if isinstance(mapping, dict):
            return {str(k): str(v) for k, v in mapping.items() if isinstance(v, str)}, None
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
        path = Path(raw)
        if not path.is_absolute():
            path = root / path
        if not path.is_file():
            # Refused rather than skipped. ``--source`` names a file the
            # caller wants bound to a key; dropping it silently means the
            # claim it was meant for reports ``source-missing``, and the
            # author goes looking for a missing PDF that is not missing.
            what = why_not_a_file(path)
            raise UsageError(f"source {path} {what}")
        found[path.stem] = str(path)

    manifest, problem = read_manifest(root)
    unusable: dict[str, str] = {}
    for key, value in manifest.items():
        path = Path(value)
        if not path.is_absolute():
            path = root / path
        if path.is_file():
            found[key] = str(path)
        else:
            # The value is what the author wrote, so quoting it back is more
            # useful than describing the joined path they never typed.
            unusable[key] = (
                f"sources.toml maps {key!r} to {value!r}, but {value!r} {why_not_a_file(path)}"
            )
    return SourceTable(found=found, unusable=unusable, manifest_problem=problem)


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
