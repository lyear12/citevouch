"""SARIF for a run that --quiet emptied and --fail-on still failed.

The document GitHub code scanning receives is the one nobody re-reads: it
uploads, it parses, and it is empty.  A run that exits 1 while handing CI a
document saying "no findings" is the same defect the text, Markdown and JSON
writers each had once - the writer that was not asked.

Measured before the fix, on a manuscript holding one good claim and one
credibility mark with no claim block::

    check --fail-on low --quiet --format text    -> 1 finding ... hidden by --quiet
    check --fail-on low --quiet --format markdown-> **1** finding ... hidden
    check --fail-on low --quiet --format json    -> findings: [], hidden: 2, worst: low
    check --fail-on low --quiet --format sarif   -> results: [], no invocations at all

The first two say why the run failed.  JSON says how many were left out and how
bad the worst one was, which is enough to work it out.  SARIF said nothing: the
only trace of the failure was the exit code of the job that uploaded it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from citevouch.model import Finding
from citevouch.report import render_sarif

ROOT = Path(__file__).resolve().parent.parent
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"}
NL = "\n"

PAGE = "We collected 154,391 examples from the corpus." + NL
MANIFEST = "[sources]" + NL + 'paper = "page.txt"' + NL
BOUND = (
    "```claim id=c1 source=paper page=1"
    + NL
    + "quote: |"
    + NL
    + "  We collected 154,391 examples from the corpus."
    + NL
    + "```"
    + NL
)
# A claim of the weakest kind, with no block to tie it to a page: `low`.
MARKED = (
    "\u3010\u63a8\u6d4b\u3011 The corpus is larger than the one used in the 2019 paper." + NL
)


def _project(root: Path) -> None:
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(MANIFEST, encoding="utf-8", newline=NL)
    (root / "manuscript.md").write_text(MARKED + NL + BOUND, encoding="utf-8", newline=NL)


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "citevouch", *args, "--root", str(root)],
        cwd=ROOT,
        env=ENV,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _check(root: Path, *flags: str) -> subprocess.CompletedProcess[str]:
    return _run(root, "check", "manuscript.md", *flags)


def _sarif(proc: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(proc.stdout)


def _invocations(proc: subprocess.CompletedProcess[str]) -> list[dict]:
    return _sarif(proc)["runs"][0].get("invocations") or []


def _notifications(proc: subprocess.CompletedProcess[str]) -> list[dict]:
    return [
        note
        for call in _invocations(proc)
        for note in (call.get("toolExecutionNotifications") or [])
    ]


class TestTheDocumentSaysWhyTheRunFailed:
    """The only writer that could hand CI an empty document and no reason."""

    @pytest.mark.parametrize("fail_on", ["low", "info"])
    def test_an_empty_result_set_carries_the_reason(self, tmp_path: Path, fail_on: str) -> None:
        _project(tmp_path)
        proc = _check(tmp_path, "--fail-on", fail_on, "--quiet", "--format", "sarif")
        assert proc.returncode == 1
        # `--quiet` still does its job: nothing at info or low reaches results.
        assert _sarif(proc)["runs"][0]["results"] == []
        notes = _notifications(proc)
        assert len(notes) == 1, "an empty document with no notification says nothing"
        text = notes[0]["message"]["text"]
        assert "hidden by" in text and "--quiet" in text
        assert "that is why this run failed" in text
        assert notes[0]["level"] == "error"

    def test_the_invocation_says_the_run_did_not_succeed(self, tmp_path: Path) -> None:
        _project(tmp_path)
        proc = _check(tmp_path, "--fail-on", "low", "--quiet", "--format", "sarif")
        calls = _invocations(proc)
        assert len(calls) == 1
        assert calls[0]["executionSuccessful"] is False

    def test_the_notification_counts_every_hidden_failure(self, tmp_path: Path) -> None:
        (tmp_path / "page.txt").write_text(PAGE, encoding="utf-8", newline=NL)
        (tmp_path / "sources.toml").write_text(MANIFEST, encoding="utf-8", newline=NL)
        (tmp_path / "manuscript.md").write_text(
            MARKED + NL + MARKED.replace("2019 paper", "2018 paper") + NL + BOUND,
            encoding="utf-8",
            newline=NL,
        )
        proc = _check(tmp_path, "--fail-on", "low", "--quiet", "--format", "sarif")
        assert proc.returncode == 1
        text = _notifications(proc)[0]["message"]["text"]
        assert text.startswith("2 "), text


class TestWhatMustNotChange:
    """The document for every run that was not emptied is the one it was."""

    def test_a_loud_failing_run_still_lists_its_results(self, tmp_path: Path) -> None:
        _project(tmp_path)
        proc = _check(tmp_path, "--fail-on", "low", "--format", "sarif")
        assert proc.returncode == 1
        codes = [r["ruleId"] for r in _sarif(proc)["runs"][0]["results"]]
        assert "claim-without-evidence" in codes
        # Nothing was hidden, so there is nothing to explain.
        assert _invocations(proc) == []

    def test_a_passing_quiet_run_stays_green_and_silent(self, tmp_path: Path) -> None:
        _project(tmp_path)
        proc = _check(tmp_path, "--fail-on", "high", "--quiet", "--format", "sarif")
        assert proc.returncode == 0
        assert _sarif(proc)["runs"][0]["results"] == []
        assert _invocations(proc) == []

    def test_the_renderer_without_the_new_arguments_is_unchanged(self) -> None:
        # Every direct caller keeps working; the key is absent, not empty.
        doc = json.loads(render_sarif([Finding(code="quote-missing", message="x")]))
        assert "invocations" not in doc["runs"][0]

    def test_hidden_findings_that_do_not_fail_the_run_are_not_a_failure(self) -> None:
        # `--quiet` hides info and low; at `--fail-on high` neither one is the
        # reason for anything, so the document must not claim a failure.
        low = Finding(code="claim-without-evidence", message="x", severity="low")
        doc = json.loads(render_sarif([], everything=[low], fail_on="high"))
        assert "invocations" not in doc["runs"][0]


class TestTheRendererItself:
    def test_it_reports_only_the_findings_it_was_handed(self) -> None:
        shown = [Finding(code="quote-missing", message="x", severity="high")]
        hidden = [Finding(code="claim-without-evidence", message="y", severity="low")]
        doc = json.loads(render_sarif(shown, everything=shown + hidden, fail_on="low"))
        results = doc["runs"][0]["results"]
        assert [r["ruleId"] for r in results] == ["quote-missing"]
        assert doc["runs"][0]["invocations"][0]["executionSuccessful"] is False

    def test_the_same_object_twice_is_one_finding_not_two(self) -> None:
        # `everything` is the full list and `findings` a subset of it, so the
        # subtraction has to be by identity: a project with two identical
        # findings must not read as one hidden.
        twice = Finding(code="quote-missing", message="x", severity="high")
        low = Finding(code="claim-without-evidence", message="y", severity="low")
        doc = json.loads(render_sarif([twice], everything=[twice, twice, low], fail_on="high"))
        assert "invocations" not in doc["runs"][0]


class TestTheWritersAgree:
    """Three writers, one run, one story about why it is red."""

    def test_every_writer_names_the_hidden_failure(self, tmp_path: Path) -> None:
        _project(tmp_path)
        text = _check(tmp_path, "--fail-on", "low", "--quiet")
        markdown = _check(tmp_path, "--fail-on", "low", "--quiet", "--format", "markdown")
        sarif = _check(tmp_path, "--fail-on", "low", "--quiet", "--format", "sarif")
        assert "hidden by --quiet" in text.stdout
        assert "hidden by `--quiet`" in markdown.stdout
        note = _notifications(sarif)[0]["message"]["text"]
        assert "hidden by" in note and "`--quiet`" in note


class TestTheJsonSaysItToo:
    """The fourth writer: `hidden` and `worst` left the reader to infer it."""

    def test_the_payload_names_the_failing_hidden_count(self, tmp_path: Path) -> None:
        _project(tmp_path)
        proc = _check(tmp_path, "--fail-on", "low", "--quiet", "--format", "json")
        assert proc.returncode == 1
        payload = json.loads(proc.stdout)
        assert payload["findings"] == []
        assert payload["failing_hidden"] == 1
        assert payload["fail_on"] == "low"

    def test_the_threshold_it_names_is_the_one_on_the_command_line(
        self, tmp_path: Path
    ) -> None:
        _project(tmp_path)
        proc = _check(tmp_path, "--fail-on", "info", "--quiet", "--format", "json")
        payload = json.loads(proc.stdout)
        assert payload["fail_on"] == "info"
        assert payload["failing_hidden"] == 2

    def test_a_quiet_run_that_passed_gains_no_keys(self, tmp_path: Path) -> None:
        _project(tmp_path)
        proc = _check(tmp_path, "--fail-on", "high", "--quiet", "--format", "json")
        assert proc.returncode == 0
        payload = json.loads(proc.stdout)
        assert "failing_hidden" not in payload
        assert "fail_on" not in payload

    def test_a_loud_run_gains_no_keys(self, tmp_path: Path) -> None:
        _project(tmp_path)
        proc = _check(tmp_path, "--fail-on", "low", "--format", "json")
        payload = json.loads(proc.stdout)
        assert "hidden" not in payload
        assert "failing_hidden" not in payload

    def test_the_renderer_without_the_new_argument_is_unchanged(self) -> None:
        from citevouch.report import render_json

        low = Finding(code="claim-without-evidence", message="x", severity="low")
        payload = json.loads(render_json([], everything=[low]))
        assert payload["hidden"] == 1
        # `fail_on` defaults to `high`, and a low finding does not reach it.
        assert "failing_hidden" not in payload

    def test_four_writers_tell_one_story(self, tmp_path: Path) -> None:
        _project(tmp_path)
        text = _check(tmp_path, "--fail-on", "low", "--quiet")
        markdown = _check(tmp_path, "--fail-on", "low", "--quiet", "--format", "markdown")
        payload = json.loads(
            _check(tmp_path, "--fail-on", "low", "--quiet", "--format", "json").stdout
        )
        sarif = _check(tmp_path, "--fail-on", "low", "--quiet", "--format", "sarif")
        assert "hidden by --quiet" in text.stdout
        assert "hidden by `--quiet`" in markdown.stdout
        assert payload["failing_hidden"] == 1
        note = _notifications(sarif)[0]["message"]["text"]
        assert "hidden by" in note

    def test_the_subtraction_is_by_identity_not_by_position(self) -> None:
        # `findings` is a subset of `run`, not a prefix of it: `--quiet` drops
        # by severity, and severity has nothing to do with order.  A writer
        # that subtracts by counting hands back the wrong members as soon as a
        # low finding comes first - which is exactly the shape of every run
        # that has a low finding at all.
        from citevouch.report import render_json

        low = Finding(code="claim-without-evidence", message="low", severity="low")
        high = Finding(code="quote-missing", message="high", severity="high")
        payload = json.loads(render_json([high], everything=[low, high], fail_on="low"))
        assert payload["hidden"] == 1
        assert payload["failing_hidden"] == 1

    def test_a_duplicated_finding_is_not_a_hidden_one(self) -> None:
        from citevouch.report import render_json

        twice = Finding(code="quote-missing", message="x", severity="high")
        payload = json.loads(render_json([twice], everything=[twice, twice], fail_on="high"))
        assert "hidden" not in payload
        assert "failing_hidden" not in payload
