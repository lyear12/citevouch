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
from collections.abc import Sequence
from pathlib import Path

REQUIRED_SECTIONS = ("Run:", "Not tried:", "Broken by hand:")

# Machine-written release bumps carry the sections in their template; the
# subject line is stable because tools/next_version's caller owns it.
_RELEASE_SUBJECT = re.compile(r"^Release \d+\.\d+\.\d+$")

# The marker is written by hand, so it comes in more than one shape:
# "Seen 3." is the canonical form, "Seen 2 - the first was ..." is what
# an author writes when the evidence needs a clause. Requiring the period
# made the gate read the second shape as "this lesson was never seen" and
# stay silent - a counting rule that silently undercounts is worse than no
# rule, because the count is the only thing that promotes a lesson.
_SEEN = re.compile(r"Seen (\d+)(?:\.|\s|$)")
# A lesson that says "Seen" but carries no readable number is a broken
# marker, not an unseen lesson: report it rather than skip it.
_SEEN_WORD = re.compile(r"\bSeen\b")
_LESSON_HEADING = re.compile(r"^## (?P<title>.+?)\s*$", re.MULTILINE)
_PASSED = re.compile(r"\b(\d+)\s+passed\b")
# A format check reports a file count, and a `Run:` line quotes it the same way
# it quotes the test count.  The first such number this repository wrote was
# wrong - 47 files when ruff printed 46 - in the very commit that added the
# check for the previous wrong number.  A quantity nobody measures is a
# quantity somebody guesses.
#
# The command was `ruff format --check .` then and is `sh tools/format_check.sh`
# now, so both are matched.  See `formatted_count_mismatches` for what happened
# in between: the guard kept passing while reading nothing.
_FORMATTED_LINE = re.compile(r"ruff format|format_check")
_FORMATTED_COUNT = re.compile(r"\b(\d+)\s+files?\b")


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


def _run_section(body: str) -> str:
    """The text from ``Run:`` up to the next evidence section.

    Measurements live there and nowhere else. A commit body is also prose, and
    prose about a past measurement quotes its number: "the commit before this
    one measured 508 and 501" is a true sentence about history, not a claim
    about this run. Held against the whole body, the gate would demand that a
    commit never explain what it changed - so the scope is the one section
    AGENTS.md designates for evidence.
    """
    start = body.find(REQUIRED_SECTIONS[0])
    if start < 0:
        return ""
    rest = body[start + len(REQUIRED_SECTIONS[0]) :]
    ends = [rest.find(section) for section in REQUIRED_SECTIONS[1:] if section in rest]
    return rest[: min(ends)] if ends else rest


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


def passed_count_mismatches(notes: str, actual: int, others: Sequence[int] = ()) -> list[str]:
    """Claims of ``N passed`` in ``notes`` that disagree with ``actual``.

    AGENTS.md asks every commit to say what was run.  A number in that section
    is a measurement, and a wrong measurement is the most expensive kind of
    wrong sentence: the next agent reads "317 passed" as evidence the suite is
    that much bigger than it is, and cannot tell a stale number from a lie
    without running it.  Both rounds of review that caught this found the same
    thing — the author believed the number.

    Only ``<number> passed`` is read.  Other shapes (``-k "not network"``
    filters, ``3.1s``) are left alone: a checker that guesses is a checker
    people learn to route around.

    A commit may measure more than one suite - the repository's, and the one
    inside the source archive it just built - so the rule is not "every count
    equals this one".  It is "every count is one of the numbers this run
    measured".  A commit that quotes only the right number passes; one that
    quotes a number nobody measured fails, which is the thing worth catching.
    """
    allowed = {actual, *others}
    bad: list[str] = []
    for claim in _PASSED.finditer(notes):
        claimed = int(claim.group(1))
        if claimed not in allowed:
            measured = ", ".join(str(number) for number in sorted(allowed))
            bad.append(f"says {claimed} passed, the suites measured {measured}")
    return bad


def formatted_count_mismatches(notes: str, actual: int) -> list[str]:
    """Claims of ``N files`` on a format-check line that disagree with ``actual``.

    Only lines that name the command which produces the number are read: a bare
    ``N files`` could be about anything, and this checker is not allowed to
    guess - the same rule :func:`passed_count_mismatches` follows.

    Both spellings of that command count.  The guard was written against
    ``ruff format``, and then the project's own acceptance criteria moved to
    ``sh tools/format_check.sh`` (which counts tracked files, so that an
    untracked scratch file cannot change the answer).  From that commit on,
    every ``Run:`` line in this repository quoted the count in the new spelling
    and this function read none of them: it returned ``[]`` whether the number
    was right, wrong, or absent.  A guard that stops matching the thing it
    guards keeps reporting success, which is worse than having no guard at all,
    because the green is read as evidence.  The same list therefore has to be
    updated whenever the command changes - that is the cost of matching on a
    command name rather than on the shape of the number.
    """
    bad: list[str] = []
    for line in notes.splitlines():
        if not _FORMATTED_LINE.search(line):
            continue
        for count in _FORMATTED_COUNT.finditer(line):
            claimed = int(count.group(1))
            if claimed != actual:
                bad.append(f"says {claimed} formatted files, ruff reports {actual}")
    return bad


def _lessons(lessons_text: str) -> list[tuple[str, str]]:
    """Every lesson as `(title, body)`, split on the headings rather than on `---`.

    The first version split the file on `\\n---\\n` and took the first heading in
    each piece. That held while every lesson ended with a separator, and then
    stopped holding: lessons appended later had none, so thirty-five of them
    landed in one piece, `_LESSON_HEADING.search` found only the first title,
    and `max(counts)` took the largest Seen number in the whole piece and
    attributed it to that first title. Every other lesson in the piece was never
    examined at all, and the one that was got a count belonging to a neighbour.

    A separator is a thing a person can forget to type. A heading is the lesson.
    """
    matches = list(_LESSON_HEADING.finditer(lessons_text))
    lessons: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(lessons_text)
        lessons.append((match.group("title").strip(), lessons_text[match.start() : end]))
    return lessons


def lesson_promotions_due(lessons_text: str, standards_text: str) -> list[str]:
    """Lesson titles seen on >= 3 days that code-standards.md does not carry yet.

    Promotion is matched by the lesson's own heading text: a rule promoted from
    a lesson paraphrases it, so a substring of the lesson title must survive
    into the standards file, or the reviewer renamed something. To keep this
    from being fragile, the match is on a four-word shard of the title - enough
    to be specific, short enough to survive light rewording.
    """
    unreadable: list[str] = []
    due: list[str] = []
    for title, block in _lessons(lessons_text):
        if not title or title.startswith("Reading"):
            continue
        seen = [
            _SEEN.search(line)
            for line in block.splitlines()
            if line.startswith("**Evidence") or "Seen" in line
        ]
        counts = [int(m.group(1)) for m in seen if m]
        if not counts:
            broken = [
                line
                for line in block.splitlines()
                if _SEEN_WORD.search(line) and not _SEEN.search(line)
            ]
            if broken:
                unreadable.append(f"{title}: {broken[0].strip()[:60]}")
            continue
        if max(counts) >= 3:
            words = re.sub(r"[^a-z ]", "", title.lower()).split()
            shard = " ".join(words[:4])
            if shard and shard not in re.sub(r"[^a-z ]", "", standards_text.lower()):
                due.append(title)
    return due + [f"unparseable Seen marker in {item}" for item in unreadable]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument(
        "--range",
        default="HEAD~1..HEAD",
        help="commit range to police, e.g. the push event's before..after",
    )
    parser.add_argument(
        "--formatted",
        type=int,
        default=None,
        help=(
            "how many files `ruff format --check .` reported in this job; a "
            "`Run:` line claiming a different number is listed. Omit where ruff "
            "did not run."
        ),
    )
    parser.add_argument(
        "--passed",
        type=int,
        action="append",
        default=None,
        help=(
            "how many tests a suite reported in this job; repeatable, because a "
            "commit may measure more than one. A `Run:` line claiming a number "
            "nobody measured is listed. Omit where no suite ran."
        ),
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

    if args.passed is not None or args.formatted is not None:
        # Only the head commit.  The suite has just run in this job, so its
        # size is a fact the message can be held against - but only for the
        # message being written now.  A number in a commit that is already
        # published cannot be corrected, so policing the whole range would
        # make the gate permanently red for history nobody can retract, and a
        # gate that can never be satisfied is a gate people delete.
        try:
            log = _run_git("log", "--no-merges", "-1", "--format=%x00%s%n%b", "HEAD", cwd=repo)
        except subprocess.CalledProcessError:
            log = ""
        for record in log.split("\x00"):
            if not record.strip("\n"):
                continue
            subject, _, body = record.strip("\n").partition("\n")
            if _RELEASE_SUBJECT.match(subject.strip()):
                continue
            mismatches: list[str] = []
            measured = _run_section(body)
            if args.passed is not None:
                mismatches += passed_count_mismatches(measured, args.passed[0], args.passed[1:])
            if args.formatted is not None:
                mismatches += formatted_count_mismatches(measured, args.formatted)
            for mismatch in mismatches:
                problems.append(f"{subject.strip()[:60]}: {mismatch}")

    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
