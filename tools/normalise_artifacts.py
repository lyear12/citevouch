"""Rewrite the build's artefacts so the same inputs give the same bytes.

The release repair step refuses to replace a published asset whose digest
differs from the one this run built, which is correct - and, without this
script, it also makes a resumed release impossible. `python -m build` stamps
every archive member with the wall clock, so two builds of one tree differ in
their bytes while their contents are identical: measured here, the wheel and
the sdist both changed digest across a two-second gap with every extracted file
byte-for-byte equal.

`SOURCE_DATE_EPOCH` fixes the wheel (zip members carry a mod time and setuptools
honours the variable) but not the sdist: setuptools writes `PKG-INFO`,
`setup.cfg` and the `*.egg-info` files at build time, and the tar picks up those
files' current mtimes. So this script normalises both archives to one timestamp
and leaves every byte of every member's content alone.

Usage: tools/normalise_artifacts.py <dist-dir> [--epoch SECONDS]

The default epoch is `SOURCE_DATE_EPOCH` from the environment, then the commit
time of `HEAD`, then 0 - in that order, because a released artefact should be
reproducible from the repository alone and a checkout that cannot ask git is
still better served by a fixed number than by the clock.
"""

from __future__ import annotations

import argparse
import gzip
import io
import os
import subprocess
import sys
import tarfile
import time
import zipfile
from pathlib import Path

FALLBACK_EPOCH = 0


def epoch_from_environment() -> int | None:
    raw = os.environ.get("SOURCE_DATE_EPOCH", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def epoch_from_git() -> int | None:
    try:
        done = subprocess.run(
            ["git", "log", "-1", "--format=%ct", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if done.returncode != 0:
        return None
    raw = done.stdout.strip()
    return int(raw) if raw.isdigit() else None


def resolve_epoch(explicit: int | None) -> int:
    if explicit is not None:
        return explicit
    for candidate in (epoch_from_environment(), epoch_from_git()):
        if candidate is not None:
            return candidate
    return FALLBACK_EPOCH


def _zip_time(epoch: int) -> tuple[int, int, int, int, int, int]:
    """The oldest instant a zip can express is 1980-01-01; the format has no 1970."""
    moment = time.gmtime(max(epoch, 315532800))
    return (
        moment.tm_year,
        moment.tm_mon,
        moment.tm_mday,
        moment.tm_hour,
        moment.tm_min,
        moment.tm_sec,
    )


def normalise_wheel(path: Path, epoch: int) -> int:
    """Rewrite one wheel's member timestamps. Returns the number of members."""
    stamp = _zip_time(epoch)
    with zipfile.ZipFile(path) as source:
        members = [(info, source.read(info.filename)) for info in source.infolist()]
    # Zip files are rewritten whole: `zipfile` has no in-place metadata edit,
    # and rebuilding is safe because the payloads were read into memory first.
    tmp = path.with_suffix(path.suffix + ".normalising")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for info, payload in members:
            fresh = zipfile.ZipInfo(info.filename, date_time=stamp)
            fresh.compress_type = info.compress_type
            fresh.external_attr = info.external_attr
            fresh.create_system = info.create_system
            target.writestr(fresh, payload)
    tmp.replace(path)
    return len(members)


def normalise_sdist(path: Path, epoch: int) -> int:
    """Rewrite one sdist's member mtimes and owners. Returns the member count."""
    with tarfile.open(path, "r:gz") as source:
        members = [(member, source.extractfile(member)) for member in source.getmembers()]
        payloads = [
            (member, handle.read() if handle is not None else None)
            for member, handle in members
        ]
    tmp = path.with_suffix(path.suffix + ".normalising")
    # The gzip *header* carries a timestamp of its own, and `tarfile`'s "w:gz"
    # writes the current time there - so normalising only the members still
    # produced a different digest on every build. Compressing explicitly is the
    # only way to pin it.
    with open(tmp, "wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=epoch, compresslevel=9) as gz:
            with tarfile.open(fileobj=gz, mode="w", format=tarfile.GNU_FORMAT) as target:
                for member, payload in payloads:
                    member.mtime = epoch
                    # Uid/gid/uname are also facts about the builder, not the build.
                    member.uid = member.gid = 0
                    member.uname = member.gname = ""
                    if payload is None:
                        target.addfile(member)
                    else:
                        target.addfile(member, io.BytesIO(payload))
    tmp.replace(path)
    return len(payloads)


def normalise(dist: Path, epoch: int) -> list[tuple[str, int]]:
    """Normalise every wheel and sdist in `dist`. Returns (name, members) rows."""
    touched: list[tuple[str, int]] = []
    if not dist.is_dir():
        raise SystemExit(f"{dist} is not a directory")
    for path in sorted(dist.iterdir()):
        if path.suffix == ".whl" and path.is_file():
            touched.append((path.name, normalise_wheel(path, epoch)))
        elif path.name.endswith(".tar.gz") and path.is_file():
            touched.append((path.name, normalise_sdist(path, epoch)))
    return touched


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dist", type=Path, help="the directory `python -m build` wrote to")
    parser.add_argument(
        "--epoch",
        type=int,
        default=None,
        help="timestamp to stamp on every member (default: SOURCE_DATE_EPOCH, then HEAD's commit time)",
    )
    args = parser.parse_args(argv)
    epoch = resolve_epoch(args.epoch)
    touched = normalise(args.dist, epoch)
    if not touched:
        print(f"no artefacts in {args.dist}", file=sys.stderr)
        return 1
    for name, members in touched:
        print(f"{name}: {members} member(s) stamped {epoch}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
