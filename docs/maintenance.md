# How this project maintains itself

`citevouch` is developed by an AI agent against the rules in [../AGENTS.md](../AGENTS.md), checked
by CI, and released by pushing a tag. This document is the operational half: who runs what, and
which failures stop the line.

## The loop

```
issue  ──►  agent reads AGENTS.md + LESSONS.md + docs/code-standards.md
       ──►  reproduces the report as a failing test
       ──►  fixes the class, runs the acceptance criteria
       ──►  opens one commit that names the failing case
       ──►  CI: tests on every OS/version pair where the interpreter exists (8 cells)
       ──►  tag v0.x.y  ──►  release workflow builds, publishes, signs nothing (pure Python)
       ──►  nightly: the day's commits are reviewed, lessons that recur are promoted
```

There is exactly one place where a human is required: someone has to decide that a reported issue is
worth fixing. Everything after that — reproducing it as a test, the fix, the commit, the version
bump, the release — is mechanical enough to be a rule.

## What CI enforces

| job | fails when |
|---|---|
| `test` | any test fails, on any of the matrix cells |
| `lint` | `ruff check` or `ruff format --check` reports a difference |
| `acceptance` | the documented first run (`init-demo`) or the demo project stops producing its expected result |
| `release` | the tag does not match `pyproject.toml` |

The `acceptance` job is the important one. It runs the same command a new user runs, from a directory
that contains nothing, and asserts on the exit code. A tool that only works in its own checkout is a
tool that does not work.

## What stops a merge

Any of these, and the change does not go in that day:

- a test that was changed to pass instead of code that was changed to be right (the commit must say
  why the old assertion was wrong);
- a new finding code with no test that produces it;
- a green demo run, because the deliberate `quote-missing` disappearing means matching got sloppy;
- a network call anywhere in `src/citevouch`;
- an exit code other than 0, 1, 2;
- a change to `citevouch.lock.json`'s shape without a `schema` bump.

## Nightly review

Each night the day's commits are read back with three questions:

1. What had to be fixed again? → becomes a lesson if it recurs three times.
2. What should not have merged? → becomes a rule in the code standards.
3. What was verified too thinly? → becomes a test, and the commit message that overstated it is
   noted in `LESSONS.md` as evidence.

The review writes to [../LESSONS.md](../LESSONS.md) under a `reviewed-through` marker at the top of
the file, so an interrupted review resumes instead of starting over.

## Version policy

- `0.1.x` — fixes only. No new finding codes, no ledger shape change.
- `0.2.x` — new codes and capability. Additive; an old ledger still verifies.
- `1.0.0` — the finding codes and the ledger schema are treated as stable API.

A release is a tag. `release.yml` publishes to PyPI, attaches the sdist and wheel, and copies the
release notes from the commit range. If the tag and `pyproject.toml` disagree, the release fails
before publishing, not after.

## Reporting a problem

Open an issue with:

- the command you ran and its exit code;
- the finding codes you got and the ones you expected;
- if possible, a three-line manuscript and a small source file that reproduces it.

A reproducible report is worth twenty paragraphs, because the first thing the agent does is turn it
into a test — and a report that cannot become a test cannot be fixed.
