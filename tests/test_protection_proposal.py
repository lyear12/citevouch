"""CV-019: pin the settings proposal to the repository it describes."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "branch-protection-proposal.md"
WORKFLOW = REPO / ".github" / "workflows" / "test.yml"
MAINTENANCE = REPO / "docs" / "maintenance.md"


def _flat() -> str:
    assert DOC.is_file(), "docs/branch-protection-proposal.md has to exist"
    return " ".join(DOC.read_text(encoding="utf-8").split())


def _jobs() -> dict:
    parsed = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return parsed["jobs"]


def _reported_names() -> list[str]:
    """The job names GitHub actually shows, expanded from the matrix."""
    names: list[str] = []
    for job in _jobs().values():
        template = job.get("name", "")
        matrix = job.get("strategy", {}).get("matrix", {})
        if "${{" not in template:
            names.append(template)
            continue
        combos: list[dict] = [{}]
        for key, values in matrix.items():
            if key == "exclude":
                continue
            combos = [{**combo, key: value} for combo in combos for value in values]
        excluded = matrix.get("exclude", [])
        for combo in combos:
            if any(all(combo.get(k) == v for k, v in rule.items()) for rule in excluded):
                continue
            rendered = template
            for key, value in combo.items():
                rendered = rendered.replace("${{ matrix." + key + " }}", value)
            names.append(rendered)
    return names


def test_the_page_exists_and_names_the_decision_it_is_waiting_for() -> None:
    flat = _flat()
    assert "Status: a proposal waiting for one Owner decision." in flat
    assert "Nothing in this document has been applied" in flat
    # Exactly one question, and it has to be answerable with a letter.
    assert flat.count("Question (one, for the Owner):") == 1
    for letter in ("Answer A", "Answer B", "Answer C"):
        assert letter in flat, letter


def test_the_recorded_state_is_the_state_measured_today() -> None:
    """A proposal that quotes the wrong current state proposes the wrong change."""
    flat = _flat()
    assert '"protected":false' in flat.replace(" ", ""), (
        "the page has to quote the measured protection answer, not a remembered one"
    )
    assert "Branch not protected" in flat
    assert '"status":"404"' in flat.replace(" ", "")
    assert '"rulesets"' not in flat or "\n[]" in flat or "[]" in flat
    assert re.search(r"collaborators --jq 'length'", flat)
    # The measured collaborator count has to be stated, and it is one.
    assert "exactly one collaborator" in flat
    assert "`admin`" in flat


def test_the_required_checks_are_real_jobs_of_this_workflow() -> None:
    """A required check that names a job GitHub never reports blocks every merge.

    Checking three familiar names was not enough: the earlier version of this
    test passed while the page named `test (windows-latest, 3.11)`, a cell that
    does not exist. Every job name the page prints in backticks has to be a job
    GitHub actually reports.
    """
    names = set(_reported_names())
    flat = _flat()
    for must_exist in (
        "lint",
        "test (ubuntu-latest, 3.10)",
        "test (windows-latest, 3.12)",
    ):
        assert must_exist in names, (must_exist, names)
        assert must_exist in flat, must_exist

    # Every `test (...)` cell the page mentions must be one the workflow reports.
    mentioned = set(re.findall(r"`(test \([^`]+\))`", flat))
    assert mentioned, "the page has to name the matrix cells it talks about"
    unknown = sorted(mentioned - names)
    assert not unknown, f"the page names cells this workflow never reports: {unknown}"

    # And the three jobs it recommends requiring must all appear as such.
    for required in ("`lint`", "`test (ubuntu-latest, 3.10)`", "`test (windows-latest, 3.12)`"):
        assert required in flat, required


def test_the_page_lists_the_matrix_it_actually_has() -> None:
    names = _reported_names()
    flat = _flat()
    matrix = [name for name in names if name.startswith("test (")]
    assert len(matrix) == 8, matrix
    for name in matrix:
        assert name in flat, name
    # The page's own list must not be longer than the workflow's.
    listed = set(re.findall(r"`(test \([^`]+\))`", flat))
    assert listed <= set(names), sorted(listed - set(names))
    # The excluded cell is explained, not silently missing.
    assert "macos" in flat and "3.10" in flat
    assert "arm64" in flat or "no CPython 3.10 build exists" in flat


def test_the_page_refuses_to_call_a_checkout_protected_while_it_is_not() -> None:
    flat = _flat()
    forbidden = (
        "main is protected",
        "the branch is protected",
        "required checks gate every commit",
        "nothing reaches main without",
    )
    lower = flat.lower()
    for phrase in forbidden:
        assert phrase not in lower, phrase
    # And it must say the required-check mechanism does not stop a direct push.
    assert "Required status checks gate merges, not pushes" in flat


def test_the_page_states_the_two_blockers_that_make_b_hard() -> None:
    flat = _flat()
    assert "one approving review" in flat
    assert "cannot be satisfied by the author" in flat
    assert "bypass" in flat.lower(), "the release-token question has to be named"
    assert "`auto-release.yml` pushes its bump commit directly to `main`" in flat


def test_the_acceptance_is_a_readback_and_not_a_click() -> None:
    flat = _flat()
    assert "read the setting back from the API" in flat
    assert "gh api repos/lyear12/citevouch/branches/main" in flat
    assert "A settings page screenshot proves nothing" in flat


def test_the_page_does_not_promise_that_the_change_is_safe() -> None:
    flat = _flat()
    for forbidden in (
        "will make main safe",
        "cannot introduce a bad commit",
        "guarantees that every commit",
    ):
        assert forbidden not in flat.lower(), forbidden
    # It has to keep the one thing B cannot fix on its own visible.
    assert "a second GitHub account" in flat


def test_the_maintenance_page_points_at_the_proposal() -> None:
    text = MAINTENANCE.read_text(encoding="utf-8")
    assert "docs/branch-protection-proposal.md" in text, (
        "a reader who asks 'is main protected?' has to be able to find the answer"
    )


def test_control_the_repository_is_readable() -> None:
    """A trivial green, so a broken fixture cannot masquerade as a passing suite."""
    assert (REPO / "pyproject.toml").is_file()
    parsed = subprocess.run(
        [sys.executable, "-c", "print('ok')"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert parsed.returncode == 0 and parsed.stdout.strip() == "ok"
