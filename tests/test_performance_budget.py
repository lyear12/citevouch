"""CV-017: the performance measurement has to be a measurement, not a mood.

These tests do not assert "fast". A timing in milliseconds is a fact about the
machine, and a number asserted absolutely in CI is the classic flaky test. What
they assert instead:

* the three stages are measured and reported separately, with the context that
  makes a number meaningful (tool version, interpreter, reader, cache state,
  page count, claim count);
* the shape of the curve is what the implementation claims - a cache hit is
  much cheaper than a cold extraction, a quote that is on the page is much
  cheaper than one that is not, and per-page cost stays roughly flat as pages
  grow (linear, not quadratic);
* a whole-manuscript fixture stays inside a ceiling so generous that only a
  complexity regression can cross it.

The numbers this machine measured are recorded in ``docs/performance.md`` and are
re-measured by ``tools/benchmark.py``, not by this file.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TOOL = REPO / "tools" / "benchmark.py"
DOC = REPO / "docs" / "performance.md"
ENV = {
    **{k: v for k, v in __import__("os").environ.items()},
    "PYTHONPATH": str(REPO / "src"),
    "PYTHONIOENCODING": "utf-8",
}


def _run(*extra: str, timeout: int = 900) -> tuple[int, str, str]:
    done = subprocess.run(
        [sys.executable, str(TOOL), *extra],
        cwd=REPO,
        env=ENV,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return done.returncode, done.stdout, done.stderr


@pytest.fixture(scope="module")
def measured(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """One real measurement, shared by every test in the module."""
    out = tmp_path_factory.mktemp("perf") / "benchmark.json"
    code, _stdout, stderr = _run(
        "--json", "--out", str(out), "--repeat", "1", "--warm-repeat", "2"
    )
    if code != 0:
        pytest.fail(f"the benchmark did not run, so nothing was measured: {stderr[-2000:]}")
    return json.loads(out.read_text(encoding="utf-8"))


def test_every_number_carries_the_context_that_makes_it_mean_something(
    measured: dict,
) -> None:
    assert measured["schema"] == 1
    with_it = measured["measured_with"]
    assert with_it["citevouch"], "a timing without a version describes an unnamed tool"
    assert with_it["python"], "a timing without an interpreter describes an unnamed machine"
    assert with_it["reader"].startswith(("pypdf-", "pdftotext")), with_it["reader"]
    assert "cold" in with_it["cache"] and "warm" in with_it["cache"], with_it["cache"]
    fixtures = measured["fixtures"]
    assert fixtures["pdf_pages"] > 0 and fixtures["pdf_chars"] > 0
    assert fixtures["manuscript_pages"] > 0 and fixtures["manuscript_claims"] > 0


def test_the_three_stages_are_measured_separately(measured: dict) -> None:
    stages = measured["stages"]
    assert set(stages) == {"extraction_cold", "extraction_warm", "normalisation", "matching"}
    assert set(stages["matching"]) >= {
        "verbatim_200",
        "absent_85",
        "long_8000",
        "repetitive_108k",
    }
    for stats in (
        stages["extraction_cold"],
        stages["normalisation"],
        *stages["matching"].values(),
    ):
        assert stats["repeat"] >= 1
        assert stats["min_ms"] <= stats["median_ms"] <= stats["max_ms"]


def test_a_cache_hit_is_closer_to_normalisation_than_to_a_cold_read(measured: dict) -> None:
    """The cache exists to skip the reader; if it did not, it would be decoration."""
    cold = measured["stages"]["extraction_cold"]["median_ms"]
    warm = measured["stages"]["extraction_warm"]["median_ms"]
    assert warm > 0
    assert cold / warm >= 3.0, (
        f"a cached extraction took {warm} ms against {cold} ms cold, which is not a cache"
    )


def test_a_quote_on_the_page_is_much_cheaper_than_one_that_is_not(measured: dict) -> None:
    """A hit stops at the tier that found it; a miss runs every tier."""
    hit = measured["manuscript"]["claims_on_the_page"]["median_ms"]
    miss = measured["manuscript"]["claims_absent"]["median_ms"]
    assert hit > 0 and miss > 0
    assert miss / hit >= 10.0, (
        f"an absent claim cost {miss} ms against {hit} ms for one that is on the page; "
        "the early tiers are supposed to short-circuit"
    )


def test_per_page_cost_stays_flat_as_pages_grow(measured: dict) -> None:
    """Linear, not quadratic. The matcher scans pages independently."""
    rows = measured["scaling"]["pages"]
    assert len(rows) >= 4
    per_page = [row["median_ms"] / row["pages"] for row in rows]
    smallest, largest = min(per_page), max(per_page)
    assert largest / smallest <= 6.0, (
        f"per-page cost ranged from {smallest:.2f} to {largest:.2f} ms across "
        f"{[row['pages'] for row in rows]} pages, which is not a linear scan"
    )


def test_a_longer_quote_costs_correspondingly_more(measured: dict) -> None:
    """The cost tracks quote length, and the report says so with real lengths.

    Ordering alone is not enough: two identical quotes timed a few milliseconds
    apart will occasionally order themselves by noise, and the earlier version of
    this test accepted that as evidence.  What is asserted instead is that the
    recorded length axis is real (the lengths differ) and that the timing grows by
    a margin noise cannot produce.
    """
    rows = measured["scaling"]["quote"]
    assert len(rows) >= 3
    lengths = [row["quote_chars"] for row in rows]
    assert lengths == sorted(lengths) and lengths[0] < lengths[-1], lengths
    assert lengths[-1] >= 4 * lengths[0], (
        f"the quote lengths {lengths} are too close together to say anything about scaling"
    )
    first, last = rows[0]["median_ms"], rows[-1]["median_ms"]
    assert last > first, "a longer quote was not slower, so the axis measured nothing"
    assert last / first >= 2.0, (
        f"a {lengths[-1] // lengths[0]}x longer quote cost only {last / first:.2f}x the time "
        f"({first:.2f} -> {last:.2f} ms), which is not the comparison cost tracking length"
    )


def test_a_whole_manuscript_finishes_inside_a_ceiling_only_a_regression_can_cross(
    measured: dict,
) -> None:
    """Thirty claims over a hundred pages. Generous on purpose: this is a tripwire."""
    worst = measured["manuscript"]["claims_absent"]["median_ms"]
    assert worst < 120_000, (
        f"30 claims over 100 pages took {worst / 1000:.1f} s, which is not a slow machine, "
        "it is a different complexity class"
    )


def test_the_tool_prints_a_table_when_it_is_not_asked_for_json() -> None:
    code, stdout, stderr = _run("--repeat", "1", "--warm-repeat", "1")
    assert code == 0, stderr[-2000:]
    assert "stage 1 - extraction" in stdout
    assert "stage 2 - normalisation" in stdout
    assert "stage 3 - matching" in stdout
    assert "ms/page" in stdout, "the report has to show a per-page cost, not only a total"


def test_the_page_states_what_the_numbers_cannot_say() -> None:
    assert DOC.is_file(), "docs/performance.md has to exist"
    flat = " ".join(DOC.read_text(encoding="utf-8").split())
    assert "median" in flat.lower()
    assert "this machine" in flat.lower(), "a timing is a fact about the machine"
    # No promise that a synthetic manuscript is a typical paper.
    for forbidden in (
        "typical paper takes",
        "typical manuscript takes",
        "average user waits",
        "no performance problem",
    ):
        assert forbidden not in flat.lower()
    assert "synthetic" in flat.lower() or "not a measurement of your paper" in flat.lower()
    assert "timeout" in flat.lower(), "the page has to say what a timeout does and does not do"
    assert DOC.read_text(encoding="utf-8").count("tools/benchmark.py") >= 1
