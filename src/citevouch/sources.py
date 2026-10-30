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
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from ._version import __version__
from .model import Finding, SourceRef
from .textnorm import fold

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
        blob = json.loads(path.read_text(encoding="utf-8"))
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
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return text.split("\f")


def _markup_pages(path: str | Path) -> list[str] | None:
    """One page of tag-stripped text, or ``None`` when the file is unreadable."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return [_strip_markup(text)]


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
        what = "is a directory, not a file" if path.is_dir() else "does not exist"
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
            return cached, None

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
    return pages, None


_TAG = re.compile(r"<[^>]+>")


def _strip_markup(text: str) -> str:
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", text)
    text = _TAG.sub(" ", text)
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

    A *key* or a *value* outside that subset is a different thing. tomllib
    accepts ``enabled = true`` and ``"quoted" = "x"`` on 3.11+, so refusing the
    whole manifest over either would be a 3.10-only failure - and a total one,
    since every other key binds nothing once the manifest is gone. Both
    therefore drop the one line: the rest of the manifest still binds. Nothing
    downstream can consume a non-string anyway: a path is a path, and a key
    this subset cannot spell is a key it cannot promise to bind identically on
    every interpreter.

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
        if not key or key[0] in "\"'":
            # A quoted key means the same thing as a bare one, but this subset
            # does not carry the distinction, and raising here would take the
            # whole manifest down with it - the exact failure this function's
            # docstring describes. Dropping the key is the same treatment a
            # value outside the subset already gets: tomllib binds it on 3.11+,
            # so a 3.10-only refusal of a file 3.11 accepts is the bug.
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


def load_manifest(root: str | Path) -> dict[str, str]:
    """Read a ``sources`` manifest mapping claim source keys to file paths.

    Only the two shapes that cost nothing to support are supported:

    * ``sources.json`` — ``{"vaneecke2026": "papers/2026.pdf"}``
    * ``sources.toml`` — ``[sources]`` table, same mapping

    ``sources.toml`` works on 3.10 as well as 3.11+: see :func:`_mini_toml` for
    why a subset is parsed there.  A malformed manifest yields an empty mapping
    rather than an error — the project then reports ``source-missing`` per
    claim, which names the problem instead of half-solving it.
    """
    root = Path(root)
    for name in MANIFEST_NAMES:
        path = root / name
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8")
            if name.endswith(".json"):
                blob = json.loads(text)
                mapping = blob.get("sources", blob) if isinstance(blob, dict) else {}
            elif name.endswith(".toml"):
                blob = _load_toml(text)
                mapping = blob.get("sources", {}) if isinstance(blob, dict) else {}
            else:
                continue
        except (OSError, ValueError):
            continue
        if isinstance(mapping, dict):
            return {str(k): str(v) for k, v in mapping.items() if isinstance(v, str)}
    return {}


def discover_sources(root: str | Path, extra: list[str] | None = None) -> dict[str, str]:
    """Map claim source keys to files, and only to files someone named.

    Two sources, in this order: ``extra`` paths from ``--source``, then the
    project's manifest.

    Deliberately excluded: guessing. An earlier version of this docstring
    promised a third step — "any file under ``root`` whose stem equals the
    key, then the longest stem the key starts with" — and the code never had
    it. That was a comment describing a wish, and the wish was a bad one.
    Binding a claim to a PDF because the filenames share a prefix is the exact
    inference this tool exists to refuse: a wrong automatic binding yields a
    confident ``quote-found`` against the wrong paper, which is worse than
    ``source-missing``, which at least says so. If a key should resolve, the
    project says what it means in ``sources.toml``.

    A missing key is still easy to fix: :func:`near_misses` supplies candidates
    for the error message, so the author picks instead of the tool guessing.
    """
    root = Path(root)
    found: dict[str, str] = {}
    for raw in extra or []:
        path = Path(raw)
        if not path.is_absolute():
            path = root / path
        if path.is_file():
            found[path.stem] = str(path)

    manifest = load_manifest(root)
    for key, value in manifest.items():
        path = Path(value)
        if not path.is_absolute():
            path = root / path
        if path.is_file():
            found[key] = str(path)
    return found


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
