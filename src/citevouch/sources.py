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

from .model import Finding, SourceRef
from .textnorm import fold

CACHE_DIRNAME = ".citevouch"
CACHE_SUBDIR = "cache"
MANIFEST_NAMES = ("sources.toml", "sources.json", "sources.yaml", "sources.yml")


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


def _load_cache(root: str | Path, sha: str) -> list[PageText] | None:
    path = _cache_file(root, sha)
    if not path.exists():
        return None
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if blob.get("schema") != 1:
        return None
    pages = [
        PageText(number=int(p.get("number", i + 1)), text=str(p.get("text", "")))
        for i, p in enumerate(blob.get("pages") or [])
    ]
    return pages or None


def _store_cache(root: str | Path, sha: str, pages: list[PageText]) -> None:
    path = _cache_file(root, sha)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema": 1, "sha256": sha, "pages": [p.to_json() for p in pages]}
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        # A read-only checkout must still work; the cache is an optimisation.
        pass


def _pypdf_pages(path: str | Path) -> list[str] | None:
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:  # noqa: BLE001 - any failure means "cannot read"
                return None
        return [(page.extract_text() or "") for page in reader.pages]
    except Exception:  # noqa: BLE001 - a corrupt PDF is a finding, not a crash
        return None


def _pdftotext_pages(path: str | Path) -> list[str] | None:
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
        return proc.stdout.split("\f")
    return None


def _plain_text_pages(path: str | Path) -> list[str]:
    """Plain text, split on form feeds so a pdftotext dump keeps its pages."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return text.split("\f")


def extract_pages(
    path: str | Path, root: str | Path, use_cache: bool = True
) -> tuple[list[PageText], Finding | None]:
    """Extract one source into pages, with a content-hash cache in between."""
    path = Path(path)
    if not path.exists():
        return [], Finding(
            code="source-missing",
            message=f"source file {path} does not exist",
            path=str(path),
        )
    sha = sha256_file(path)
    if use_cache:
        cached = _load_cache(root, sha)
        if cached is not None:
            return cached, None

    suffix = path.suffix.lower()
    raw: list[str] | None
    if suffix == ".pdf":
        raw = _pypdf_pages(path) or _pdftotext_pages(path)
    elif suffix in (".txt", ".md", ".text"):
        raw = _plain_text_pages(path)
    elif suffix in (".html", ".htm", ".xml"):
        raw = [_strip_markup(Path(path).read_text(encoding="utf-8", errors="replace"))]
    else:
        raw = _pdftotext_pages(path) or _plain_text_pages(path)
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
    _store_cache(root, sha, pages)
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
    comments, and both string quoting styles.  A shape outside that subset
    raises :class:`ValueError`, which the caller treats exactly like a syntax
    error from tomllib — the manifest is skipped and every claim it was meant
    to bind reports ``source-missing``, naming the file it could not read
    rather than binding evidence the author never chose.

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
            raise ValueError(f"unsupported key {key!r}")
        parsed.setdefault(section, {})[key] = _toml_string(value.strip())
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
        if path.exists():
            found[path.stem] = str(path)

    manifest = load_manifest(root)
    for key, value in manifest.items():
        path = Path(value)
        if not path.is_absolute():
            path = root / path
        if path.exists():
            found[key] = str(path)
    return found


def candidate_files(root: str | Path) -> list[str]:
    """Paths (relative, POSIX) of files that could plausibly be a source.

    One walk per run, not one per unresolved claim: a manuscript with ten
    unbound keys would otherwise re-read the whole project ten times, and the
    project is the user's real working directory, which may hold a corpus.
    Skips hidden directories and the tool's own cache.
    """
    root = Path(root)
    if not root.is_dir():
        return []
    found: list[str] = []
    skip_dirs = {".git", ".citevouch", "__pycache__", ".venv", "venv", "node_modules"}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".pdf", ".txt", ".md"}:
            continue
        relative = path.relative_to(root)
        if any(part in skip_dirs for part in relative.parts[:-1]):
            continue
        found.append(relative.as_posix())
    return sorted(found)


def near_misses(key: str, candidates: list[str], limit: int = 3) -> list[str]:
    """Names from ``candidates`` that resemble ``key``, for an error message.

    Suggestions to read, never bindings to use. Printing candidates is what
    lets discovery stay strict: the tool names what it saw, the author decides
    what it means.
    """
    if not key:
        return []
    needle = key.lower()
    scored: list[tuple[int, str]] = []
    for name in candidates:
        stem = Path(name).stem.lower()
        if needle in stem or stem in needle:
            scored.append((abs(len(stem) - len(needle)), name))
    scored.sort()
    return [name for _distance, name in scored[:limit]]


def resolve_source(key: str, known: dict[str, str]) -> str | None:
    """Best-effort lookup of a claim's source key among discovered files."""
    if not key:
        return None
    if key in known:
        return known[key]
    lowered = key.lower()
    for name, path in known.items():
        if name.lower() == lowered:
            return path
    for name, path in known.items():
        if name.lower().startswith(lowered):
            return path
    for name, path in known.items():
        if lowered.startswith(name.lower()):
            return path
    return None
