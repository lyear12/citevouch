# Two ideas for spending less CI time, one of which needs a decision

**Status: a proposal. Nothing here is in effect.**

Everything below is measured on this repository with `tools/ci_cost.py`, which
reads the timings GitHub reports per job. Read the numbers as *elapsed* time.
They are not a bill: GitHub bills a job after rounding up to the whole minute
and multiplying by an operating-system factor (Linux 1, Windows 2, macOS 10 on
the hosted runners), and the free allowance is consumed in those units. A sum of
seconds cannot be turned into money, quota or "how much is left" without those
factors, and this document does not have them.

## What a run costs today

Run `43807438040` (`Test`, pushed 2026-11-16, all eleven jobs green):

| job | elapsed |
|---|---|
| `sdist (the archive as published, unpacked and tested)` | 272 s |
| `test (windows-latest, 3.13)` | 231 s |
| `test (windows-latest, 3.12)` | 206 s |
| `test (windows-latest, 3.10)` | 204 s |
| `lint` | 190 s |
| `test (macos-latest, 3.12)` | 175 s |
| `acceptance (the documented first run)` | 146 s |
| `test (ubuntu-latest, 3.13)` | 141 s |
| `test (macos-latest, 3.13)` | 139 s |
| `test (ubuntu-latest, 3.12)` | 134 s |
| `test (ubuntu-latest, 3.10)` | 114 s |

Eleven jobs, **1952 s** of job time, **272 s** of wall time. The wall time is
what a person waits; the job time is what the machines spend. They differ by a
factor of seven because almost everything runs in parallel.

The same suite is executed twelve times per run: eight matrix cells, once in
`lint` (which refuses to skip), once more inside `lint` for the unpacked
archive, once in `sdist`, and once more in `acceptance` behind a dead proxy.

## Idea 1 (done, this change) - stop measuring the same thing twice

The `sdist` job used to unpack the archive twice and run the whole suite in each
copy: once to prove it passes, then again with `-rs` to read the skip reasons.
The second run measured nothing the first had not, and the suite takes about a
minute. It is now one unpack and one `pytest -rs`; the skip classification reads
the log that run wrote, and fails if there is no log to read.

That is one suite execution removed from every push. It is a small win, it needs
no decision, and it changes nothing about what the job proves.

## Idea 2 (needs a decision) - batch releases instead of one tag per commit

`auto-release.yml` runs on every green `Test` on `main`. When the
`## [Unreleased]` section has entries it bumps the version, tags, and calls
`release.yml`; when it is empty it does nothing and says so. In practice that
means a tag and a full release pipeline every time a commit lands with a
changelog entry - which is most of them, since every change in this repository
is supposed to carry an entry.

The cost is not the tag; it is the `release` job: a full suite, a build, a wheel
smoke test in a clean directory, a PyPI attempt that fails on `invalid-publisher`
until the publisher is registered, a `gh release` round trip, a digest
re-verification of what was published, and now a `publish.yml` run that decides
whether it has anything to do. That is roughly a `Test` run's worth of work per
release, and there have been 300-plus of them.

Three options, stated with what each one costs:

**Option A - a release train.** `auto-release` keeps its trigger, but instead of
releasing on every green run it releases only when the previous release is at
least N hours old (say 12), collecting every entry that accumulated. One tag,
one pipeline, the changelog names everything that shipped together. Cost: a fix
that lands at 13:00 might ship at 01:00, and `v0.X.Y` no longer means "the
commit that landed at 13:00". It also needs a durable record of "when did we last
release", which is a new thing to get wrong.

**Option B - release on a schedule.** A nightly job at a fixed hour decides
whether to release, using the same `tools/next_version.py` logic. Even easier to
reason about; a bad commit sits on `main` for up to a day before anybody can
`pip install` a fix, which is worse for a tool whose whole purpose is to be run
in somebody's CI.

**Option C - keep one release per commit.** What happens today. Every green
commit that changes the changelog becomes an installable version within minutes,
which is the property that makes the CI-gate story work: the version a reader
gets is the version whose tests passed. Cost: the release pipeline runs on every
push, and the "release" tab becomes a list of near-identical versions.

**Recommendation: C, with the reasoning written down** - not because the pipeline
is free, but because the release rate is a *symptom* of the change rate, and this
repository is currently changing several times a day on purpose. Batching would
hide that, not reduce it. If the change rate falls, the cost falls with it and
nobody has to revisit this. If the cost becomes a real problem, A is the option
to take; B trades away the property that a fix can be installed the same day.

**Until the Owner says otherwise, C stays in effect** and the existing policy is
followed exactly: the version comes from `## [Unreleased]`, an empty section
means no release, and no tag is created by hand.

## What this proposal is not

It is not a claim that CI is cheap. It is not a bill, a quota forecast or a
budget. It does not know the operating-system factors apply to this account, nor
whether a free allowance is still in play, and it does not compute any of them.
The one number it is confident about is the count of jobs and the per-job
elapsed seconds, because those are printed by the API rather than derived.
