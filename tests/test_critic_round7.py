"""The eighth review's findings, pinned."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from citevouch import sources

REPO = Path(__file__).resolve().parent.parent


def _load_rules():
    sys.path.insert(0, str(REPO / "tools"))
    try:
        import check_repo_rules
    finally:
        sys.path.pop(0)
    return check_repo_rules


# --- minor-1: a skip must not be a green run -------------------------------


def test_no_non_windows_machine_may_skip_the_shell_tests():
    """bash exists on every Linux and macOS machine.  A probe that fails there
    is a broken environment, and `pytest.skip` would report it as a suite that
    passed - the gate opening itself exactly where nobody is watching."""
    text = (REPO / "tests" / "test_critic_round6.py").read_text(encoding="utf-8")
    assert 'if os.name != "nt":' in text
    guard = text.index('if os.name != "nt":')
    failure = text.index("pytest.fail(", guard)
    skip = text.index("pytest.skip(", guard)
    assert failure < skip, "fail must be the non-Windows branch, skip the Windows one"


def test_the_lint_job_refuses_a_suite_that_skipped():
    """A count that silently shrinks is worse than a count that fails: the
    first is invisible, the second is a Monday."""
    workflow = (REPO / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")
    assert "[0-9]+ skipped" in workflow
    assert "::error::the suite skipped tests" in workflow


# --- minor-3: every number a message claims is measured --------------------


def test_a_wrong_formatted_count_is_caught():
    rules = _load_rules()
    notes = "Run: ruff format --check . (47 files) already formatted"
    assert rules.formatted_count_mismatches(notes, 46)
    assert rules.formatted_count_mismatches(notes, 47) == []


def test_only_ruff_lines_are_read_for_a_file_count():
    """A bare ``N files`` could be about anything.  A checker that guesses is a
    checker people learn to route around."""
    rules = _load_rules()
    assert rules.formatted_count_mismatches("Run: 12 files touched", 46) == []
    assert rules.formatted_count_mismatches("Run: ruff check . (0 files)", 46) == []


def test_the_workflow_measures_the_file_count_it_holds_messages_to():
    workflow = (REPO / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")
    assert "--formatted" in workflow
    assert "ruff format --check . 2>&1 | grep" in workflow


def _repo_with_message(tmp_path: Path, body: str) -> Path:
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    (tmp_path / "a.txt").write_text("one\n", encoding="utf-8")
    subprocess.run([*git, "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        [*git, "commit", "-q", "-F", "-"], cwd=tmp_path, input=body, text=True, check=True
    )
    return tmp_path


def test_a_wrong_file_count_in_a_real_commit_fails_the_gate(tmp_path: Path):
    """The flag existing is not the check running.  `main` has to reach the
    comparison, or the workflow passes a number nobody reads."""
    rules = _load_rules()
    repo = _repo_with_message(
        tmp_path,
        "Fix a thing\n\nRun: ruff format --check . (47 files)\nNot tried: none.\n"
        "Broken by hand: none.\n",
    )
    assert rules.main(["--repo", str(repo), "--range", "HEAD", "--formatted", "47"]) == 0
    assert rules.main(["--repo", str(repo), "--range", "HEAD", "--formatted", "46"]) == 1


# --- minor-4: markup is reduced to what a reader would see -----------------


def test_entities_are_decoded_after_the_tags_are_gone():
    """Decoding first would turn ``&lt;tag&gt;`` into something the tag regex
    can eat, and the sentence an author quoted would vanish from the page it is
    verified against."""
    # Tags become a space each, so the result is stripped rather than sliced.
    assert sources._strip_markup("<p>a&amp;b &lt;tag&gt; c</p>").strip() == "a&b <tag> c"


def test_a_quote_whose_sentence_holds_an_entity_still_verifies(tmp_path: Path):
    page = tmp_path / "page.html"
    page.write_text(
        "<html><body><p>The corpus holds 154,391 sentences &amp; 440,528 roles.</p>"
        "</body></html>",
        encoding="utf-8",
    )
    pages, problem = sources.extract_pages(page, tmp_path, use_cache=False)
    assert problem is None, problem
    assert "&amp;" not in pages[0].text
    assert "sentences & 440,528 roles" in pages[0].text


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__]))
