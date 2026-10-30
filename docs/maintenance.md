# How this project maintains itself

`citevouch` is developed by an AI agent against the rules in [../AGENTS.md](../AGENTS.md), checked
by CI, and released by a workflow that decides on its own when to release. This document is the
operational half: who runs what, and which failures stop the line.

## The loop

```
issue  ──►  agent reads AGENTS.md + LESSONS.md + docs/code-standards.md
       ──►  reproduces the report as a failing test
       ──►  fixes the class, runs the acceptance criteria
       ──►  opens one commit that names the failing case
       ──►  CI: tests on every OS/version pair where the interpreter exists (8 cells)
       ──►  green on main  ──►  auto-release reads CHANGELOG's Unreleased section
       ──►  tools/next_version.py picks the number, writes it, commits, tags
       ──►  release workflow: suite, build, clean-venv smoke test, publish, release notes
       ──►  nightly: the day's commits are reviewed, lessons that recur are promoted
```

There is exactly one place where a human is required: someone has to decide that a reported issue is
worth fixing. Everything after that — reproducing it as a test, the fix, the commit, the version
bump, the tag, the release — is mechanical enough to be a rule.

## What decides a version

`tools/next_version.py` reads `## [Unreleased]` in `CHANGELOG.md` and applies one table:

| Unreleased contains | bump | why |
|---|---|---|
| nothing | no release | an empty section is not a release, and the workflow says so and stops |
| only `Fixed` / `Security` | patch | behaviour people rely on stopped being wrong |
| any `Added` / `Changed` / `Removed` / `Deprecated` | minor | before 1.0, "0.x is moving" is the promise; a pinned `0.1.*` must not lose a feature |
| a section name this table does not know | no release | an unrecognised name is a mistake in the changelog, not a licence to ship |

The workflow does not ask whether releasing is a good idea. If the changelog says something
changed, something changed, and the release is the thing that tells users. What guards the release
is not a person's judgement but `release.yml`, which runs the whole suite on the exact commit before
it publishes anything.

## What CI enforces

| job | fails when |
|---|---|
| `test` | any test fails, on any of the matrix cells |
| `lint` | `ruff check` or `ruff format --check` reports a difference |
| `acceptance` | the documented first run (`init-demo`) or the demo project stops producing its expected result |
| `auto-release` | the changelog says release but the decided version changes no files, or the tag already exists |
| `release` | the tag does not match `src/citevouch/_version.py`, or the suite is red, or the built wheel cannot scaffold a project and verify it |

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

The numbers in that table are the version policy; the table in "What decides a version" is how the
policy is executed. They have to agree: when `0.1.x` is declared fixes-only, a `Changed` entry in
the changelog must produce `0.2.0`, and `tools/next_version.py` is where that promise is enforced
rather than remembered.

A release is a tag, and since the auto-release workflow exists, usually nobody types it. The release
workflow still accepts a hand-pushed tag and a `workflow_dispatch` with an explicit version, because
the machine that decides versions can be wrong and the fix for a wrong version is a person pushing
the right one. It attaches the sdist and wheel, publishes to PyPI when a trusted publisher is
configured, and copies the release notes from the range between the previous tag and this one. If the tag and
`src/citevouch/_version.py` disagree, the release fails before publishing, not after.

### The one thing a workflow cannot do for itself

`pip install citevouch` does not work yet, and no commit can change that. Publishing needs a
*trusted publisher* registered on PyPI against this repository, which is an account action. The
release workflow is already written for it and will start publishing on the next tag once the entry
exists — `release.yml` prints `PyPI: published.` or `PyPI: **not published** (the trusted publisher
is not registered for this repository yet)` into the run summary so the state is never guessed at.

The click-path (about a minute, done once):

1. Sign in at <https://pypi.org/manage/account/publishing/>.
2. **Add a new pending publisher** with exactly these values:

   | field | value |
   |---|---|
   | PyPI Project Name | `citevouch` |
   | Owner | `lyear12` |
   | Repository name | `citevouch` |
   | Workflow name | `release.yml` |
   | Environment name | *(leave empty)* |

3. Save. Nothing else: `release.yml` already declares `permissions: id-token: write`, and the
   publish step pins no `environment:`, so an environment name here would make the OIDC subject
   disagree and the publish would fail rather than silently skip.

To check whether it worked without cutting a release:

```console
$ curl -s -o /dev/null -w '%{http_code}
' https://pypi.org/pypi/citevouch/json
404        # before the first publish (expected today)
200        # after the next tag has published
$ pip download --no-deps citevouch -d /tmp/x && ls /tmp/x
```

`404` here is not a failure of the project; it is the absence of a distribution, which is what a
pending publisher is for.

## Reporting a problem

Open an issue with:

- the command you ran and its exit code;
- the finding codes you got and the ones you expected;
- if possible, a three-line manuscript and a small source file that reproduces it.

A reproducible report is worth twenty paragraphs, because the first thing the agent does is turn it
into a test — and a report that cannot become a test cannot be fixed.
