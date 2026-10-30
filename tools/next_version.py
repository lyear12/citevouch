#!/usr/bin/env python
"""Decide the next version from the Unreleased section of the changelog.

The release workflow publishes whatever tag it is given; it is deliberately
ignorant about whether the tag makes sense.  The decision "is there anything to
release, and what number is it" lives here, where it can be tested, instead of
in a shell `if` inside YAML that nobody can run locally.

The rules are the pre-1.0 reading of SemVer that this project already writes in
``docs/maintenance.md``:

* nothing under ``## [Unreleased]``      -> no release (exit code 1, prints nothing)
* only ``Fixed`` / ``Security`` entries   -> patch   (0.1.0 -> 0.1.1)
* anything that adds, changes or removes  -> minor   (0.1.0 -> 0.2.0)

Before 1.0.0 every capability change is a minor bump, because "0.x is the API
still moving" is the promise the README makes.  ``Removed`` and ``Changed`` are
deliberately *not* patch bumps: a user who has pinned ``0.1.*`` should not
silently receive a removed feature.

Usage::

    python tools/next_version.py CHANGELOG.md --current 0.1.0
    python tools/next_version.py CHANGELOG.md --current 0.1.0 --apply --date 2026-10-30
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from pathlib import Path

# Heading -> bump weight.  Higher weight wins when a section has several.
_WEIGHT = {
    "added": 2,
    "changed": 2,
    "removed": 2,
    "deprecated": 2,
    "fixed": 1,
    "security": 1,
}

_UNRELEASED = re.compile(r"^## \[Unreleased\][ \t]*$", re.MULTILINE)
_NEXT_H2 = re.compile(r"^## \[", re.MULTILINE)
_H3 = re.compile(r"^### (?P<name>[A-Za-z]+)\s*$", re.MULTILINE)
_BULLET = re.compile(r"^\s*[-*]\s+\S", re.MULTILINE)
_VERSION = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$")


class ChangelogError(ValueError):
    """The changelog is not shaped the way this script needs it to be."""


def unreleased_body(text: str) -> str:
    """Return the lines between ``## [Unreleased]`` and the next ``## [`` heading."""
    start = _UNRELEASED.search(text)
    if start is None:
        raise ChangelogError("no '## [Unreleased]' heading")
    rest = text[start.end() :]
    nxt = _NEXT_H2.search(rest)
    return rest[: nxt.start()] if nxt else rest


def classify(text: str) -> tuple[str, list[str]]:
    """Return ``(bump, sections)`` where bump is ``none``, ``patch`` or ``minor``.

    A section counts only if it has at least one bullet: an empty ``### Added``
    heading is a leftover, not a claim that something was added.
    """
    body = unreleased_body(text)
    found: list[str] = []
    for block in _split_sections(body):
        name, content = block
        if _BULLET.search(content):
            found.append(name)

    weights = [_WEIGHT.get(name.lower(), 0) for name in found]
    if not found or max(weights, default=0) == 0:
        return "none", found
    return ("minor" if max(weights) >= 2 else "patch"), found


def _split_sections(body: str) -> list[tuple[str, str]]:
    matches = list(_H3.finditer(body))
    out: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        out.append((match.group("name"), body[match.end() : end]))
    return out


def bump_version(current: str, bump: str) -> str:
    parsed = _VERSION.match(current.strip())
    if parsed is None:
        raise ChangelogError(f"{current!r} is not MAJOR.MINOR.PATCH")
    major, minor, patch = (int(parsed.group(k)) for k in ("major", "minor", "patch"))
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    if bump == "none":
        return current
    raise ChangelogError(f"unknown bump {bump!r}")


def apply(text: str, new_version: str, date: str) -> str:
    """Rewrite the changelog: Unreleased becomes ``new_version``, a new empty one is added."""
    start = _UNRELEASED.search(text)
    if start is None:
        raise ChangelogError("no '## [Unreleased]' heading")
    body = unreleased_body(text)
    released = body.strip("\n")
    if not released.strip():
        raise ChangelogError("refusing to release an empty Unreleased section")
    replacement = f"## [Unreleased]\n\n## [{new_version}] — {date}\n{released}\n"
    return text[: start.start()] + replacement + text[start.end() + len(body) :]


def set_pyproject_version(text: str, new_version: str) -> str:
    """Set the version in whichever file this project declares it.

    The declaration moved from a ``version = "..."`` literal in ``pyproject.toml``
    to ``dynamic = ["version"]`` backed by ``src/citevouch/_version.py``. Both
    shapes are accepted here so an old checkout and a new one both release
    correctly - but exactly one of them has to match, because a script that
    silently rewrites nothing is how the version drifted four releases behind
    the tag in the first place.
    """
    replaced, count = re.subn(
        r'(?m)^(?P<indent>\s*)__version__\s*=\s*"[^"]*"',
        lambda m: f'{m.group("indent")}__version__ = "{new_version}"',
        text,
        count=1,
    )
    if count == 1:
        return replaced
    replaced, count = re.subn(
        r'(?m)^(?P<indent>\s*)version\s*=\s*"[^"]*"',
        lambda m: f'{m.group("indent")}version = "{new_version}"',
        text,
        count=1,
    )
    if count != 1:
        raise ChangelogError(
            "could not find a version declaration: expected `__version__ = ` in "
            "src/citevouch/_version.py or a top-level `version = ` in pyproject.toml"
        )
    return replaced


# Any `citevouch@vX.Y.Z`: the install line and the CI example that copies it.
_DOC_PIN = re.compile(r"(citevouch@)v\d+\.\d+\.\d+")


def set_doc_pins(text: str, new_version: str) -> tuple[str, int]:
    """Point every pinned install example at the version being released.

    Releases are cut by a machine now, so a hand-kept tag in a document is
    stale the moment the machine works - the README told people to install
    ``@v0.1.0`` two releases after that stopped being the newest version. The
    release names the version in every file it touches, and the pins are one of
    those files. Zero matches is fine, not an error: once PyPI is configured the
    pins go away, and the script must not be the reason they come back.
    """
    return _DOC_PIN.subn(rf"\g<1>v{new_version}", text)


REPO_URL = "https://github.com/lyear12/citevouch"

# Every document in this repository that may carry an install pin.
#
# `--readme` used to take one path per file and the caller listed the files it
# remembered. That worked until `docs/launch/` arrived: the launch copy quotes
# the install line, both pins there went stale the moment the first release
# happened after those files existed, and the *tagged* commit failed its own
# test suite - the tag was pushed, the release died, and the number was spent
# (see LESSONS.md, "A tag that fails its own gate has already been spent").
#
# A glob is the same mistake one level up unless the glob is the contract, so
# this tuple is the contract: `tests/test_next_version.py` fails if a markdown
# file carries a pin that these patterns do not cover.
PIN_GLOBS = (
    "README.md",
    "README.zh-CN.md",
    "docs/**/*.md",
)


def pin_documents(root: Path) -> list[Path]:
    """Every document under ``root`` that may carry an install pin.

    Sorted, because two runs of the release workflow must produce the same
    commit: an unordered glob makes the diff depend on the filesystem.
    """
    found: set[Path] = set()
    for pattern in PIN_GLOBS:
        for path in root.glob(pattern):
            if path.is_file():
                found.add(path)
    return sorted(found)


_LINK_SECTION = re.compile(r"^\[[^\]]+\]: \S+\n(?:\[[^\]]+\]: \S+\n)*", re.MULTILINE)
_RELEASE_HEADING = re.compile(r"^## \[(\d+\.\d+\.\d+)\]", re.MULTILINE)


def update_links(text: str, new_version: str, repo: str = REPO_URL) -> str:
    """Regenerate the changelog's link definitions from its own headings.

    Keep a Changelog renders `[0.2.2]` through a definitions block at the foot
    of the file, and a human-kept block goes stale the way every other
    human-kept version in this repository did: the file gained three releases
    while its footer still compared "unreleased" to v0.1.0 and linked only
    that one version. The headings are the ground truth - every `## [X.Y.Z]`
    is a release that exists - so the block is rebuilt from them on every
    release, which is the only moment it could ever be wrong to rebuild it.
    """
    releases = _RELEASE_HEADING.findall(text)
    lines = [f"[Unreleased]: {repo}/compare/v{new_version}...HEAD"]
    lines += [f"[{v}]: {repo}/releases/tag/v{v}" for v in releases]
    block = "\n".join(lines) + "\n"
    section = _LINK_SECTION.search(text)
    if section is None:
        return text.rstrip() + "\n\n" + block
    # Whatever follows the definitions block is somebody else's text - an
    # acknowledgements section, a licensing note, anything the changelog
    # grew below the links. Dropping it here would delete content from the
    # repository inside an automatic release commit, which is the worst
    # place to lose a sentence nobody is watching.
    return text[: section.start()] + block + text[section.end() :]


def _today() -> str:
    return _dt.date.today().isoformat()


def _write_lf(path: Path, text: str) -> None:
    """Write ``text`` with newlines that are the ones the caller meant.

    ``Path.write_text`` does not take a ``newline`` argument, so on Windows it
    translates every ``\\n`` to ``\\r\\n``.  The files this script rewrites are
    committed and read back by the release workflow, so a local ``--apply``
    would otherwise leave the whole file different from the version control
    copy for no reason other than the platform it ran on.
    """
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("changelog", type=Path)
    parser.add_argument("--current", required=True, help="current version, e.g. 0.1.0")
    parser.add_argument("--apply", action="store_true", help="rewrite the changelog in place")
    parser.add_argument(
        "--pyproject",
        type=Path,
        help=(
            "file holding the version declaration: src/citevouch/_version.py "
            "(current) or pyproject.toml (older checkouts)"
        ),
    )
    # Every markdown file that may carry a pin, by pattern. Naming files one at
    # a time is how `docs/launch/` was missed: the caller listed what it
    # remembered, and a tag was spent proving it.
    parser.add_argument(
        "--pins-root",
        type=Path,
        help=(
            "re-point citevouch@vX.Y.Z install pins in every document under this "
            "root that may carry one (README.md, README.zh-CN.md, docs/**/*.md)"
        ),
    )
    parser.add_argument("--date", default=_today())
    parser.add_argument(
        "--bump", choices=["none", "patch", "minor"], help="override the decision"
    )
    args = parser.parse_args(argv)

    text = args.changelog.read_text(encoding="utf-8")
    bump, sections = classify(text)
    if args.bump:
        bump = args.bump
    new_version = bump_version(args.current, bump)

    if bump == "none":
        print("no release: the Unreleased section has no entries", file=sys.stderr)
        return 1

    if args.apply:
        _write_lf(
            args.changelog,
            update_links(apply(text, new_version, args.date), new_version),
        )
        if args.pyproject:
            _write_lf(
                args.pyproject,
                set_pyproject_version(args.pyproject.read_text(encoding="utf-8"), new_version),
            )
        if args.pins_root:
            for doc in pin_documents(args.pins_root):
                current = doc.read_text(encoding="utf-8")
                rewritten, moved = set_doc_pins(current, new_version)
                if moved:
                    _write_lf(doc, rewritten)
                    print(
                        f"{doc}: {moved} install pin(s) moved to v{new_version}",
                        file=sys.stderr,
                    )

    print(new_version)
    print(f"bump: {bump} (from {', '.join(sections) or 'nothing'})", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
