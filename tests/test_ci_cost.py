"""CV-018: the CI measurement is a measurement, and the proposal says what it is not.

Two things are pinned here.

The tool (`tools/ci_cost.py`) reads per-job timings from the API and prints
elapsed seconds. It must never turn them into a bill: GitHub rounds each job up
to the minute and multiplies by an operating-system factor, so a sum of seconds
is not money, not quota and not "how much is left". The tests below check the
arithmetic it does do (per job, and wall time from first start to last finish)
and the sentence it refuses to stop saying.

The workflow had two copies of the same suite run in the `sdist` job - one to
prove it passes, one more with `-rs` to read the skip reasons. That is a minute
of runner time per push spent measuring something already measured, so the job
now unpacks once and runs once, and the skip step reads the log that run wrote.
The guard is written against the workflow text because there is no way to ask
GitHub "how many times did this job run pytest".
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
TOOL = REPO / "tools" / "ci_cost.py"
WORKFLOW = REPO / ".github" / "workflows" / "test.yml"
DOC = REPO / "docs" / "ci-batching-proposal.md"
MAINTENANCE = REPO / "docs" / "maintenance.md"

sys.path.insert(0, str(REPO / "tools"))
import ci_cost  # noqa: E402


def _job(name: str, start: str, end: str, conclusion: str = "success") -> dict:
    return {
        "name": name,
        "conclusion": conclusion,
        "started_at": start,
        "completed_at": end,
        "labels": ["ubuntu-latest"],
    }


class TestTheArithmeticIsWhatGitHubReports:
    def test_each_job_keeps_its_own_elapsed_time(self) -> None:
        jobs = [
            _job("lint", "2026-11-16T05:00:19Z", "2026-11-16T05:03:29Z"),
            _job("test (ubuntu-latest, 3.13)", "2026-11-16T05:00:19Z", "2026-11-16T05:02:40Z"),
        ]
        measured = ci_cost.measure(jobs)
        elapsed = {row["name"]: row["elapsed_s"] for row in measured["jobs"]}
        assert elapsed["lint"] == 190.0
        assert elapsed["test (ubuntu-latest, 3.13)"] == 141.0
        assert measured["job_elapsed_total_s"] == 331.0

    def test_wall_time_is_first_start_to_last_finish_not_a_sum(self) -> None:
        """Eleven parallel jobs take as long as the slowest, not as long as all
        of them added together - and reporting the sum as the wait would make
        every runner look twice as expensive as it is."""
        jobs = [
            _job("a", "2026-11-16T05:00:00Z", "2026-11-16T05:01:00Z"),
            _job("b", "2026-11-16T05:00:00Z", "2026-11-16T05:04:32Z"),
        ]
        measured = ci_cost.measure(jobs)
        assert measured["job_elapsed_total_s"] == 332.0
        assert measured["wall_s"] == 272.0

    def test_a_job_that_never_started_does_not_become_zero_seconds(self) -> None:
        """A skipped job has no timestamps. Reading that as `0` would add a
        number that means "instant" where the truth is "never ran"."""
        jobs = [
            _job("lint", "2026-11-16T05:00:00Z", "2026-11-16T05:01:00Z"),
            {
                "name": "test (macos-latest, 3.10)",
                "conclusion": "skipped",
                "started_at": "",
                "completed_at": "",
                "labels": ["macos-latest"],
            },
        ]
        measured = ci_cost.measure(jobs)
        by_name = {row["name"]: row for row in measured["jobs"]}
        assert by_name["test (macos-latest, 3.10)"]["elapsed_s"] is None
        assert measured["job_elapsed_total_s"] == 60.0
        assert "?" in ci_cost.report(measured)

    def test_the_measurement_carries_the_sentence_that_says_what_it_is_not(self) -> None:
        measured = ci_cost.measure(
            [_job("lint", "2026-11-16T05:00:00Z", "2026-11-16T05:01:00Z")]
        )
        assert measured["not_a_bill"].startswith("elapsed seconds, not billable minutes")
        assert measured["factors_not_applied"]["windows"] == 2
        assert measured["factors_not_applied"]["macos"] == 10
        printed = ci_cost.report(measured)
        assert "not billable minutes" in printed
        assert "no operating-system multiplier" in printed


class TestItPublishesWhatItMeasured:
    def test_the_table_is_ordered_by_time_so_the_expensive_job_is_first(self) -> None:
        measured = ci_cost.measure(
            [
                _job("cheap", "2026-11-16T05:00:00Z", "2026-11-16T05:00:10Z"),
                _job("expensive", "2026-11-16T05:00:00Z", "2026-11-16T05:04:32Z"),
            ]
        )
        lines = ci_cost.report(measured).splitlines()
        assert "expensive" in lines[2]
        assert "cheap" in lines[3]

    def test_paging_asks_again_until_a_short_page(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """One page is a slice: the API defaults to 30 items, and a run with
        more jobs than that would be measured as if it had thirty."""
        calls: list[str] = []

        def fake_run(argv, **kwargs):
            calls.append(argv[2])
            page = "page=1" if "page=1" in argv[2] else "page=2"
            jobs = (
                [{"name": f"job-{page}", "conclusion": "success"}] if page == "page=1" else []
            )
            if page == "page=1":
                jobs = [{"name": "x", "conclusion": "success"} for _ in range(2)]
            payload = {"jobs": jobs}
            return subprocess.CompletedProcess(argv, 0, json.dumps(payload), "")

        monkeypatch.setattr(ci_cost.subprocess, "run", fake_run)
        found = ci_cost.jobs_of("owner/repo", "1", page_size=2)
        assert len(found) == 2
        assert len(calls) == 2, f"paging stopped early: {calls}"


class TestTheSuiteRunsOnceInTheSdistJob:
    def _sdist(self) -> str:
        parsed = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        return json.dumps(parsed["jobs"]["sdist"])

    def test_the_archive_is_unpacked_and_tested_once(self) -> None:
        text = self._sdist()
        assert text.count("python -m pytest") == 1, (
            "the sdist job runs the suite more than once; the second run measures "
            "nothing the first did not"
        )
        assert "/tmp/unpacked2" not in text, "there is a second unpack again"
        assert "tar xzf" in text and text.count("tar xzf") == 1

    def test_the_skip_step_reads_the_log_instead_of_running_the_suite(self) -> None:
        parsed = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        steps = parsed["jobs"]["sdist"]["steps"]
        skip = next(s for s in steps if "every skip" in str(s.get("name", "")))
        body = str(skip["run"])
        assert "/tmp/sdist.log" in body
        assert "python -m pytest" not in body
        assert "exit 1" in body, "a missing log has to fail, not pass quietly"

    def test_the_skip_reasons_are_still_the_two_the_job_expects(self) -> None:
        """Deduplicating the run must not weaken what the job accepts: the two
        checkout-shaped reasons stay, everything else is still an error."""
        parsed = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        steps = parsed["jobs"]["sdist"]["steps"]
        skip = next(s for s in steps if "every skip" in str(s.get("name", "")))
        body = str(skip["run"])
        assert "not a git checkout" in body
        assert "no sdist in dist/" in body
        assert "::error::the archive's suite skipped for a reason" in body


class TestTheProposalSaysWhatItIsAndWhatItIsNot:
    def _flat(self) -> str:
        assert DOC.is_file(), "docs/ci-batching-proposal.md has to exist"
        return " ".join(DOC.read_text(encoding="utf-8").split())

    def test_it_is_marked_as_a_proposal(self) -> None:
        flat = self._flat()
        assert "**Status: a proposal. Nothing here is in effect.**" in flat

    def test_it_names_three_options_and_one_recommendation(self) -> None:
        flat = self._flat()
        for label in (
            "**Option A - a release train.**",
            "**Option B - release on a schedule.**",
            "**Option C - keep one release per commit.**",
        ):
            assert label in flat, label
        assert "**Recommendation: C, with the reasoning written down**" in flat

    def test_it_refuses_to_be_read_as_a_bill(self) -> None:
        flat = self._flat()
        assert "They are not a bill" in flat or "not a bill" in flat
        assert "operating-system factor" in flat
        assert "It is not a claim that CI is cheap" in flat

    def test_until_the_owner_says_otherwise_the_old_policy_runs(self) -> None:
        flat = self._flat()
        assert "**Until the Owner says otherwise, C stays in effect**" in flat
        assert "no tag is created by hand" in flat

    def test_the_maintenance_page_points_at_it(self) -> None:
        text = MAINTENANCE.read_text(encoding="utf-8")
        assert "ci-batching-proposal.md" in text

    def test_the_numbers_in_it_are_the_numbers_the_tool_printed(self) -> None:
        """A proposal quoting a table nobody can reproduce is a rumour with a
        format. The two totals are the ones `tools/ci_cost.py` reported for run
        43807438040 on this machine, and they are quoted verbatim."""
        flat = self._flat()
        assert "**1952 s**" in flat
        assert "**272 s**" in flat
        assert "43807438040" in flat
