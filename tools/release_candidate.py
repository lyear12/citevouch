"""Record which commit produced which bytes, and write the record next to them.

The release workflow already knows three commits: the tested one (whose Test run
went green), the source one and the release one (the bump commit the tag points
at). It also knows the version. What it did not have was any durable statement
tying those identities to the actual files, so a later run - or a person holding
the downloaded wheel - could only take the tag's word for it.

This tool writes that statement into `dist/release-candidate.json` and checks it
afterwards. Two properties make it worth the file:

* the record is uploaded as a release asset, so it travels with the bytes. Anyone
  who downloads a release gets the digests of everything else in it, and
  `check` recomputes them.
* a resumed run can *compare* instead of guessing. Before this, "the rebuild is
  the same build" was an assumption; now it is a number in a file that either
  matches or does not.

It is deliberately not a lock, a lease or a claim about who is allowed to
publish. It is a witness: it says what one run built, and `check` says whether
the bytes in front of you are still those bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

SCHEMA = 1
RECORD = "release-candidate.json"
REQUIRED = ("schema", "version", "tag", "candidate", "source_sha", "release_sha", "artifacts")


def _dump(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def digest_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifacts_in(dist: Path) -> list[dict]:
    """Every regular file in `dist`, sorted, excluding the record itself.

    The record cannot carry its own digest, so it is the one file this list
    cannot describe - and it is also the one file whose absence would make the
    whole exercise pointless, which is why `check` demands it separately.
    """
    found: list[dict] = []
    for path in sorted(dist.iterdir()):
        if not path.is_file() or path.name == RECORD:
            continue
        found.append(
            {
                "name": path.name,
                "sha256": digest_of(path),
                "size": path.stat().st_size,
            }
        )
    return found


def write(
    dist: Path,
    *,
    version: str,
    tag: str,
    candidate: str,
    source_sha: str,
    release_sha: str,
) -> Path:
    artifacts = artifacts_in(dist)
    if not artifacts:
        raise SystemExit(f"no artefacts in {dist}; there is nothing to record")
    payload = {
        "schema": SCHEMA,
        "version": version,
        "tag": tag,
        "candidate": candidate,
        "source_sha": source_sha,
        "release_sha": release_sha,
        "artifacts": artifacts,
    }
    target = dist / RECORD
    target.write_text(_dump(payload), encoding="utf-8", newline="\n")
    return target


def _load(dist: Path) -> dict:
    path = dist / RECORD
    if not path.is_file():
        raise SystemExit(
            f"{path} is missing; this directory carries no record of what built it"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise SystemExit(f"{path} is not readable JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"{path} is a {type(payload).__name__}, not a record")
    for key in REQUIRED:
        if key not in payload:
            raise SystemExit(f"{path} has no {key!r}; it does not say what it describes")
    if payload["schema"] != SCHEMA:
        raise SystemExit(f"{path} is schema {payload['schema']}, this tool reads {SCHEMA}")
    return payload


def check(dist: Path) -> list[str]:
    """Everything wrong with `dist`, as sentences. Empty means it is intact."""
    payload = _load(dist)
    problems: list[str] = []
    recorded = {}
    for entry in payload["artifacts"]:
        if not isinstance(entry, dict) or "name" not in entry:
            problems.append(f"a recorded artefact is not an object with a name: {entry!r}")
            continue
        recorded[entry["name"]] = entry
    present = {path.name for path in dist.iterdir() if path.is_file() and path.name != RECORD}
    for name, entry in sorted(recorded.items()):
        path = dist / name
        if not path.is_file():
            problems.append(f"the record names {name}, which is not here")
            continue
        actual = digest_of(path)
        if actual != entry.get("sha256"):
            problems.append(f"{name} is {actual} but the record says {entry.get('sha256')}")
        size = path.stat().st_size
        if size != entry.get("size"):
            problems.append(f"{name} is {size} bytes but the record says {entry.get('size')}")
    for name in sorted(present - set(recorded)):
        problems.append(
            f"{name} is here but the record does not name it, so nothing can vouch for it"
        )
    return problems


def describe(dist: Path) -> dict:
    """The record, plus the identities a human needs to read it."""
    return _load(dist)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)

    record = commands.add_parser(
        "write", help="write the record for the artefacts in a directory"
    )
    record.add_argument("dist", type=Path)
    record.add_argument("--version", required=True)
    record.add_argument("--tag", required=True)
    record.add_argument(
        "--candidate", default="", help="the tested commit, empty for a tag push"
    )
    record.add_argument("--source-sha", required=True)
    record.add_argument("--release-sha", required=True)

    verify = commands.add_parser("check", help="recompute every digest and report what differs")
    verify.add_argument("dist", type=Path)

    show = commands.add_parser("show", help="print one field of the record")
    show.add_argument("dist", type=Path)
    show.add_argument("field", choices=list(REQUIRED))

    args = parser.parse_args(argv)

    if args.command == "write":
        target = write(
            args.dist,
            version=args.version,
            tag=args.tag,
            candidate=args.candidate,
            source_sha=args.source_sha,
            release_sha=args.release_sha,
        )
        payload = json.loads(target.read_text(encoding="utf-8"))
        for entry in payload["artifacts"]:
            print(f"{entry['name']}  sha256:{entry['sha256']}  {entry['size']} bytes")
        print(f"recorded {len(payload['artifacts'])} artefact(s) in {target}")
        return 0

    if args.command == "check":
        problems = check(args.dist)
        if problems:
            for problem in problems:
                print(f"::error::{problem}")
            return 1
        payload = _load(args.dist)
        print(
            f"{args.dist} matches its record: version {payload['version']}, "
            f"{len(payload['artifacts'])} artefact(s), release {payload['release_sha']}"
        )
        return 0

    payload = describe(args.dist)
    field = payload[args.field]
    if isinstance(field, (list, dict)):
        print(json.dumps(field, sort_keys=True))
    else:
        print(field)
    return 0


if __name__ == "__main__":
    sys.exit(main())
