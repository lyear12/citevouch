#!/usr/bin/env python
"""Measure what one CI run cost in elapsed time, and say what that is not.

GitHub reports a start and an end per job.  Two numbers can be derived from
those and nothing else: how long each job ran, and how long the run took from
the first job starting to the last one finishing.  Both are *elapsed* time.

They are not a bill.  GitHub bills a job after rounding it up to a whole
minute and multiplying by an operating-system factor (Linux 1, Windows 2,
macOS 10 on the hosted runners), and the free allowance is consumed in those
units, not in seconds.  A sum of elapsed seconds therefore cannot be converted
into money, quota or "how much is left" without the factors and the rounding,
and quoting one as if it were a bill is how a measurement becomes a rumour.
This tool prints the factors it did *not* apply so nobody has to guess.

    python tools/ci_cost.py --repo lyear12/citevouch --run 43807438040
    python tools/ci_cost.py --run 43807438040 --json

Requires `gh` on PATH (the tool only reads; no network from `src/`).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys

# Stated so the report can say what was left out.  These are the hosted-runner
# multipliers GitHub documents; they are recorded here as a fact about the
# platform, never applied to a number this tool prints.
OS_FACTORS = {"linux": 1, "windows": 2, "macos": 10}
NOT_A_BILL = (
    "elapsed seconds, not billable minutes: no round-up to the minute, no "
    "operating-system multiplier, no free allowance, no price"
)


def _instant(text: str) -> _dt.datetime | None:
    if not text:
        return None
    return _dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def jobs_of(repo: str, run_id: str, *, page_size: int = 100) -> list[dict]:
    """Every job of one run, as the API reports it (read-only, via `gh`)."""
    job_list: list[dict] = []
    page = 1
    while True:
        out = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{repo}/actions/runs/{run_id}/jobs?per_page={page_size}&page={page}",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        ).stdout
        payload = json.loads(out)
        batch = payload.get("jobs", [])
        job_list.extend(batch)
        if len(batch) < page_size:
            return job_list
        page += 1


def measure(job_list: list[dict]) -> dict:
    """Elapsed per job, and the wall time of the run as a whole."""
    rows = []
    for job in job_list:
        started = _instant(job.get("started_at", ""))
        finished = _instant(job.get("completed_at", ""))
        elapsed = None
        if started is not None and finished is not None:
            elapsed = (finished - started).total_seconds()
        rows.append(
            {
                "name": job.get("name", "?"),
                "conclusion": job.get("conclusion"),
                "elapsed_s": elapsed,
                "runner_os": (job.get("labels") or [""])[0],
            }
        )
    started_all = [_instant(j.get("started_at", "")) for j in job_list]
    finished_all = [_instant(j.get("completed_at", "")) for j in job_list]
    real_starts = [t for t in started_all if t is not None]
    real_finishes = [t for t in finished_all if t is not None]
    wall = None
    if real_starts and real_finishes:
        wall = (max(real_finishes) - min(real_starts)).total_seconds()
    elapsed_total = sum(r["elapsed_s"] for r in rows if r["elapsed_s"] is not None)
    return {
        "jobs": rows,
        "job_count": len(rows),
        "job_elapsed_total_s": elapsed_total,
        "wall_s": wall,
        "not_a_bill": NOT_A_BILL,
        "factors_not_applied": OS_FACTORS,
    }


def report(data: dict) -> str:
    lines = [
        f"{'job':<52}{'conclusion':<12}{'elapsed':>10}",
        "-" * 74,
    ]
    for row in sorted(data["jobs"], key=lambda r: -(r["elapsed_s"] or 0)):
        elapsed = "?" if row["elapsed_s"] is None else f"{row['elapsed_s']:.0f}s"
        lines.append(f"{row['name'][:50]:<52}{str(row['conclusion'])[:10]:<12}{elapsed:>10}")
    lines.append("-" * 74)
    lines.append(
        f"{data['job_count']} job(s): {data['job_elapsed_total_s']:.0f}s of job time, "
        f"{data['wall_s']:.0f}s of wall time"
    )
    lines.append(data["not_a_bill"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default="lyear12/citevouch")
    parser.add_argument("--run", required=True, help="the run id, as `gh run list` prints it")
    parser.add_argument(
        "--json", action="store_true", help="print the measurement, not a table"
    )
    parser.add_argument("--out", help="also write the measurement to this path")
    args = parser.parse_args(argv)

    data = measure(jobs_of(args.repo, args.run))
    data["run"] = args.run
    data["repo"] = args.repo
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
    print(json.dumps(data, indent=2, sort_keys=True) if args.json else report(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
