"""Tests for tools/check_repo_rules.py - the project policing its own rules.

The two checks are pure over text (lesson promotion) and over a git range
(commit discipline), so both are testable without CI. The git test builds a
throwaway repository, because a mock of `git log` would prove the parser
handles a fiction.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "tools" / "check_repo_rules.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_repo_rules", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_repo_rules"] = module
    spec.loader.exec_module(module)
    return module


cr = _load()

GOOD_LESSON = """
---

## A matrix cell that cannot run is not a passing cell

**Rule.** text
**Why.** text
**Evidence.** runs said so. Seen 3.
"""


def test_a_lesson_seen_three_times_is_due_for_promotion():
    due = cr.lesson_promotions_due(GOOD_LESSON, "# Code standards\nnothing here\n")
    assert due == ["A matrix cell that cannot run is not a passing cell"]


def test_promotion_is_satisfied_once_the_shard_lands_in_the_standards():
    standards = (
        "# Code standards\n\n7. **A matrix cell that cannot run is not a passing cell.**\n"
    )
    assert cr.lesson_promotions_due(GOOD_LESSON, standards) == []


def test_a_lesson_seen_twice_is_not_due_yet():
    assert cr.lesson_promotions_due(GOOD_LESSON.replace("Seen 3.", "Seen 2."), "x") == []


def test_the_intro_and_reading_sections_never_count_as_lessons():
    text = """# Lessons

`citevouch` is written... a lesson seen on three or more separate days moves into
docs/code-standards.md.

## Reading this file

Newest first. Seen 1.
"""
    assert cr.lesson_promotions_due(text, "x") == []


def test_several_counts_in_one_block_take_the_maximum():
    text = GOOD_LESSON.replace("Seen 3.", "Seen 1.") + "\nLater review: Seen 4.\n"
    assert len(cr.lesson_promotions_due(text, "nothing")) == 1


# --------------------------------------------------------------------------
# Commit discipline, over a real throwaway repository


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "r"
    repo.mkdir()

    def git(*args: str) -> None:
        subprocess.run(
            ["git", *args], cwd=str(repo), check=True, capture_output=True, text=True
        )

    git("init", "-b", "main")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "tester")
    (repo / "f").write_text("1\n", encoding="utf-8")
    git("add", "f")
    git("commit", "-m", "first\n\nRun: pytest\nNot tried: nothing.\nBroken by hand: none.\n")
    (repo / "f").write_text("2\n", encoding="utf-8")
    git("commit", "-am", "second: no evidence sections at all")
    return repo


def test_a_commit_without_evidence_sections_is_reported(tmp_path: Path):
    repo = _repo(tmp_path)
    bad = cr.commit_message_violations(repo, "HEAD~1..HEAD")
    assert len(bad) == 1
    assert bad[0].startswith("second:")
    assert "Run:" in bad[0] and "Not tried:" in bad[0] and "Broken by hand:" in bad[0]


def test_a_clean_range_reports_nothing(tmp_path: Path):
    repo = _repo(tmp_path)
    # `HEAD..HEAD~1` names commits reachable from HEAD~1 that HEAD cannot
    # see: empty by construction, and legal in a two-commit repository where
    # HEAD~2 would not exist.
    assert cr.commit_message_violations(repo, "HEAD..HEAD~1") == []


def test_release_bumps_are_exempt_because_the_template_carries_the_sections(tmp_path: Path):
    repo = _repo(tmp_path)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "Release 0.3.0\n\nthe bump body"],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    )
    assert cr.commit_message_violations(repo, "HEAD~1..HEAD") == []


def test_the_subject_line_is_a_minimum_but_the_sections_must_be_in_the_body(
    tmp_path: Path,
):
    """A commit that mentions "Run:" only in its subject has not recorded what it ran."""
    repo = _repo(tmp_path)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "fix: Run: it worked"],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    )
    bad = cr.commit_message_violations(repo, "HEAD~1..HEAD")
    assert len(bad) == 1


# --------------------------------------------------------------------------
# The end-to-end command

# --------------------------------------------------------------------------
# This repository's own state passes its own gate

# The one thing the gate exists to catch would be this project leaving a
# `Seen 3` lesson unpromoted - which it has done once already, in the history
# this commit fixes.


def test_the_real_lessons_file_promotes_what_it_owes():
    repo = Path(__file__).resolve().parent.parent
    problems = cr.lesson_promotions_due(
        (repo / "LESSONS.md").read_text(encoding="utf-8"),
        (repo / "docs" / "code-standards.md").read_text(encoding="utf-8"),
    )
    assert problems == [], f"lessons seen 3+ days and not in code standards: {problems}"


def test_main_reports_violations_on_stdout(tmp_path: Path, capsys):
    repo = _repo(tmp_path)
    code = cr.main(["--repo", str(repo), "--range", "HEAD~1..HEAD"])
    assert code == 1
    assert "second:" in capsys.readouterr().out


# --------------------------------------------------------------------------
# One commit, more than one suite


def test_a_message_may_measure_more_than_one_suite():
    """A commit that builds an archive measures two: this tree's suite and the
    archive's own. Both numbers are true, and a checker that accepts only one
    of them turns an honest message into a failing one - so the agent either
    deletes a measurement or learns to write fewer of them, and the second is
    worse than the first."""
    notes = (
        "Run: PYTHONPATH=src python -m pytest (508 passed); "
        "unpacked the archive and ran its suite (501 passed, 2 skipped)"
    )
    assert cr.passed_count_mismatches(notes, 508, (501,)) == []


def test_a_number_nobody_measured_is_still_caught():
    notes = "Run: PYTHONPATH=src python -m pytest (508 passed); (317 passed)"
    problems = cr.passed_count_mismatches(notes, 508, (501,))
    assert problems == ["says 317 passed, the suites measured 501, 508"]


def test_one_number_still_has_to_be_the_right_one():
    assert cr.passed_count_mismatches("Run: pytest (508 passed)", 508) == []
    assert cr.passed_count_mismatches("Run: pytest (317 passed)", 508)
