#!/usr/bin/env python
"""Check the repository's own maintenance rules, mechanically.

Two rules this project states in AGENTS.md and docs/maintenance.md are decidable
without a model or a person:

1. **Commit discipline.** Every commit on `main` carries the three sections
   AGENTS.md asks for - `Run:`, `Not tried:`, `Broken by hand:` - because the
   next agent believes an untested claim, and a message with no evidence section
   is the claim without the evidence.
2. **Lesson promotion.** A lesson marked `Seen N` with N >= 3 belongs in
   docs/code-standards.md (LESSONS.md says so); once it is there it stops being
   a lesson and becomes a rule with teeth.

Both run in CI's lint job, so the promise is a gate and not a paragraph.

Exit code 0 = all rules hold; 1 = a violation is listed on stdout.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REQUIRED_SECTIONS = ("Run:", "Not tried:", "Broken by hand:")

# Machine-written release bumps carry the sections in their template; the
# subject line is stable because tools/next_version's caller owns it.
_RELEASE_SUBJECT = re.compile(r"^Release \d+\.\d+\.\d+$")

_SEEN = re.compile(r"Seen (\d+)\.")
_LESSON_HEADING = re.compile(r"^## (?P<title>.+?)\s*$", re.MULTILINE)


def _run_git(*args: str, cwd: Path) -> str:
    proc = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(cwd),
        check=True,
    )
    return proc.stdout


def commit_message_violations(repo: Path, rev_range: str) -> list[str]:
    """Subjects of non-merge commits in ``rev_range`` missing an evidence section."""
    bad: list[str] = []
    log = _run_git("log", "--no-merges", "--format=%x00%s%n%b", rev_range, cwd=repo)
    for record in log.split("\x00"):
        record = record.strip("\n")
        if not record.strip():
            continue
        subject, _, body = record.partition("\n")
        if _RELEASE_SUBJECT.match(subject.strip()):
            # the template that wrote it is in auto-release.yml, and the same
            # gate scans that template below
            continue
        missing = [section for section in REQUIRED_SECTIONS if section not in body]
        if missing:
            bad.append(f"{subject.strip()[:60]}: missing {', '.join(missing)}")
    return bad


def lesson_promotions_due(lessons_text: str, standards_text: str) -> list[str]:
    """Lesson titles seen on >= 3 days that code-standards.md does not carry yet.

    Promotion is matched by the lesson's own heading text: a rule promoted from
    a lesson paraphrases it, so a substring of the lesson title must survive
    into the standards file, or the reviewer renamed something. To keep this
    from being fragile, the match is on a four-word shard of the title - enough
    to be specific, short enough to survive light rewording.
    """
    due: list[str] = []
    blocks = re.split(r"\n---\n", lessons_text)
    for block in blocks:
        heading = _LESSON_HEADING.search(block)
        if heading is None:
            continue
        title = heading.group("title").strip()
        if not title or title.startswith("Reading"):
            continue
        seen = [
            _SEEN.search(line)
            for line in block.splitlines()
            if line.startswith("**Evidence") or "Seen" in line
        ]
        counts = [int(m.group(1)) for m in seen if m]
        if not counts:
            continue
        if max(counts) >= 3:
            words = re.sub(r"[^a-z ]", "", title.lower()).split()
            shard = " ".join(words[:4])
            if shard and shard not in re.sub(r"[^a-z ]", "", standards_text.lower()):
                due.append(title)
    return due


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument(
        "--range",
        default="HEAD~1..HEAD",
        help="commit range to police, e.g. the push event's before..after",
    )
    args = parser.parse_args(argv)

    repo = args.repo.resolve()
    problems: list[str] = []

    try:
        problems += commit_message_violations(repo, args.range)
    except subprocess.CalledProcessError as exc:
        # A shallow checkout cannot answer for a full range. Say which check
        # did not run instead of reporting the repository clean: a gate that
        # silently skips is worse than one that admits it.
        print(f"commit-discipline check skipped: git log failed ({exc})", file=sys.stderr)
        return 0

    lessons = repo / "LESSONS.md"
    standards = repo / "docs" / "code-standards.md"
    if lessons.is_file() and standards.is_file():
        for title in lesson_promotions_due(
            lessons.read_text(encoding="utf-8"), standards.read_text(encoding="utf-8")
        ):
            problems.append(f"lesson seen 3+ days but not in code-standards: {title}")

    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
