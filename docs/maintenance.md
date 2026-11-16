# How this project maintains itself

`citevouch` is developed by an AI agent against the rules in [../AGENTS.md](../AGENTS.md), checked
by CI, and released by a workflow that decides on its own when to release. This document is the
operational half: who runs what, and which failures stop the line.

## The loop

The loop this project is built around, with every stage marked by whether it **runs today** or is
only an intention:

```
issue  ──►  a person reads it and decides it is worth fixing         ← a person, by design
       ──►  agent reads AGENTS.md + LESSONS.md + code-standards     ← not automated
       ──►  reproduces the report as a failing test                 ← not automated
       ──►  fixes the class, runs the acceptance criteria           ← not automated
       ──►  opens one commit that names the failing case            ← not automated
       ──►  CI: every OS/version pair the interpreter exists on     ← automated
       ──►  green on main ──► auto-release reads Unreleased         ← automated
       ──►  next_version.py picks the number, commits, tags         ← automated
       ──►  release workflow: suite, build, smoke, publish, notes   ← automated
       ──►  nightly: installs the newest wheel, replays the
            documented first run, files an issue if it fails        ← automated
       ──►  retrospective: reads the day's commits, promotes
            lessons that recur                                      ← **not built**
```

### What is automated, and what is not

Automated, and exercised on every change: the test matrix, the sdist suite, the acceptance run, the
version decision, the tag, the release, and the nightly install of the published wheel.

**Not automated, and not to be described as if it were:**

| stage | state today | what that costs |
|---|---|---|
| reading a new issue | nothing consumes it | a report sits until a person points an agent at it |
| reviewing an incoming change | no reviewer runs on a pull request | GitHub reports `main` as unprotected with no rulesets; the review rules are text, not enforcement |
| merging | a person merges, or the agent pushes to `main` | there is no merge bot and no auto-approval |
| the retrospective | `LESSONS.md` still says `reviewed-through: none` | lessons are written by whoever wrote the fix, not harvested afterwards |

The nightly job is named `Nightly dogfood` and does one thing: it installs the newest published wheel
in a clean environment, replays the first commands the documentation shows, and opens an issue when
that stops working. It does not read commits and it does not promote lessons, so anything in this
document that says it does is describing the intention rather than the pipeline.

There is exactly one place where a human is required **by design**: someone has to decide that a
reported issue is worth fixing. Everything after that decision is written down as rules so it can be
mechanical — and most of it is — but written down as a rule is not the same as running.

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

## Which commit a release is about

`workflow_run` reports the SHA whose `Test` run finished green. It does not promise that `main` still
points there: another merge can land while the release job is queued. Checking out `main` by name
would then publish a commit that no run has ever tested, under a number chosen from its changelog -
the ordinary way a green build stops meaning anything.

So the decision job pins its checkout to `github.event.workflow_run.head_sha`, then asks the remote
where `main` is. If the two differ it stands down: the newer commit has its own `Test` run queued or
running, and that run decides. Nothing is tagged, nothing is published, and the step summary names
the two SHAs that disagreed.

The tag still cannot point at the tested SHA itself - the version-bump commit is made after the test
- so `release.yml` checks the next best thing: the candidate is an ancestor of the release tree, and
exactly one commit (the bump) sits between them. Two commits there means something untested slipped
in and the run stops. Both SHAs are printed, so a release can be traced back to the run that approved
it.

### One publisher, and a tag is identified by what it points at

`release.yml` carries `concurrency: group: publisher`. It has three doors - a tag push, a manual
dispatch, and the reusable call from `auto-release.yml` - and without the group two of them could
run at once and race over the same release. The group is deliberately **not** called `auto-release`.
A reusable workflow does not inherit its caller's group, so if the two names matched the caller
would hold the lock and the callee would wait on it: the release would block until the caller
finished, and the caller is waiting for the callee. Two names is what makes the doors exclude each
other without deadlocking the ordinary path.

The tag steps compare *targets*, not names. `git ls-remote --tags refs/tags/vX` exiting zero only
says the name exists, and every run that decided to release that number would have written that same
name; the local `rev-parse` a few lines earlier asks about a tag this run just created, so it cannot
disagree. Both are answers a run gives itself. What settles it is the peeled commit: the local tag is
read as `refs/tags/vX^{commit}`, and the remote is asked for both `refs/tags/vX` and
`refs/tags/vX^{}` (an annotated tag answers on the peeled line, a lightweight one on the plain line,
which is already a commit) and the two commits are compared. A tag at this release's commit is a
re-run and succeeds; a tag at any other commit stops the run and says which commit it found.

The failure text ends in a repair command, because the bump commit is already on `main` by then: the
Unreleased section is empty, so re-running the workflow decides there is nothing to release. The
number would be stranded with nothing in the log saying so.

### A published asset is identified by its bytes

The release job creates the GitHub release with `continue-on-error`, then a second step repairs the
two ways that can fail: the release exists but is still a draft, or the upload was interrupted after
the release was created. That repair path used to end in `gh release upload --clobber`, which
replaces an asset of the same name without looking at it. An interrupted release resumed after a
rebuild produces exactly one asset name with two different sets of bytes, so the "-clobber" was a
licence to publish a build no run had chosen, silently.

The repair step now reads `gh release view --json assets`, which reports a `digest` per asset, and
compares it against `sha256sum` of the file this run built:

| what GitHub reports for that name | what the step does |
|---|---|
| nothing (name absent) | uploads it |
| the same `sha256:` digest | leaves it alone and says so |
| a different digest | stops the run, names both digests, and gives the `gh release delete-asset` command |
| no digest recorded | stops the run - "I cannot tell whether these are the same bytes" is not a yes |

Only the artefacts that are already right are skipped; whatever is missing is still attached, so a
half-finished upload still finishes.

### Rebuilding must give the same bytes

The digest guard above only works if one tree has one set of bytes. It did not:
`python -m build` stamps every archive member with the wall clock, and
`tarfile.open(..., "w:gz")` writes the current time into the sdist's gzip
header as well. Measured, two builds two seconds apart produced different wheel
and sdist digests while every extracted member was byte-for-byte equal - so a
resumed release could never have matched what was already published, and the
honest refusal to overwrite would have become a permanent block.

`tools/normalise_artifacts.py` rewrites both archives to one timestamp after
the build. The epoch is `SOURCE_DATE_EPOCH` if set, else the `HEAD` commit time,
else `0`; contents are never touched, only mtimes, ownership and the gzip
header. The build step in `release.yml` calls it before the smoke test, so the
wheel that gets installed is the wheel whose digest is published.

The tests do not trust a same-second comparison: one reads the gzip header's
own `mtime`, and another moves the epoch by a second and requires the digest to
change - a normaliser whose epoch never reaches the bytes normalises nothing.

### The release says which commit produced which bytes

A tag names a commit and a release page lists files. Neither says which commit produced those files,
and until v0.24.7 nothing did: a person holding a downloaded wheel could learn the tag and no more,
and a resumed release could only *assume* its rebuild was the same build.

`tools/release_candidate.py` writes `dist/release-candidate.json` before the smoke test, so the
record is uploaded with the artefacts it describes. It carries `version`, `tag`, `candidate` (the
tested commit), `source_sha`, `release_sha` and, for every file in `dist` except itself, its
`sha256` and size. The record deliberately cannot describe itself - writing a digest into a file
changes that digest - and `check` demands the file separately rather than silently skipping an
unrecorded one.

The last step of the workflow downloads what the release actually serves (`gh release download`)
and runs `check` against that directory. That is the only place in the pipeline where the published
thing is read rather than written, so it is the only place that can notice an upload which reported
success and stored something else.

Two properties are load-bearing rather than tidy. The record is deterministic - sorted keys, sorted
artefacts, no timestamp - because the recovery step's digest guard refuses to replace a published
asset whose bytes differ, and an honest re-run of the same tag therefore has to produce a
byte-identical record. And the record is metadata, not a lock: it says what one run built, and
`check` says whether the bytes in front of you are still those bytes. It does not say who is
allowed to publish, and it does not authenticate a file against a hostile editor who controls both
the file and the record.

Run it by hand against any directory of artefacts:

```console
python tools/release_candidate.py check dist
python tools/release_candidate.py show dist release_sha
```


### A release that already exists is read, not rebuilt

Re-running the release for a tag that is already out used to rebuild the artefacts and hope the
bytes matched. That hope only became load-bearing when the recovery step started refusing to
replace a published asset whose digest differs: an honest re-run now has to produce byte-identical
output, and a toolchain update or a different Python patch release quietly makes that false.

So the step before `Build` asks the release what it already serves. `gh release download` fills
`dist/`, and `tools/release_candidate.py reuse` answers one question: are these bytes the ones this
release is about to produce? It refuses unless the record names **this** version, **this** tag and,
when the caller knows it, **this** tested commit - a record from another release passes `check` and
is still the wrong release - and then it hands over to `check`, which re-hashes every file. Only
then does `reusable=true` skip the build.

Two details are deliberate rather than incidental. A download that fails is not an error: a tag
with no release yet is the first-release path, and the step records `reusable=false` and lets the
build run. And when the build is skipped the record step is skipped too, because a directory
downloaded from the release already carries the record of the run that built it; rewriting it would
attribute those bytes to a run that built nothing.

The fallback is rebuild, not fail. If anything about the published directory is unreadable or
unexpected, the release builds again - with normalised timestamps it produces the same bytes, and if
it does not, the digest guard stops before replacing anything. Reuse is an optimisation with a
correct slow path, which is why it may be wrong in the cautious direction and still be safe.

## What CI enforces

| job | fails when |
|---|---|
| `test` | any test fails, on any of the matrix cells |
| `lint` | `ruff check` or `ruff format --check` reports a difference |
| `acceptance` | the documented first run (`init-demo`) or the demo project stops producing its expected result |
| `auto-release` | the changelog says release but the decided version changes no files, the tag points at a different commit than this release, or `main` moved past the tested SHA |
| `release` | the tag does not match `src/citevouch/_version.py`, the suite is red, more than one commit landed after the tested SHA, the built wheel cannot scaffold a project and verify it, the artefacts are not reproducible from the tree; the published assets are not what a downloaded directory actually contains, or the release already publishes an asset with a different digest than this run built |

The `acceptance` job is the important one. It runs the same command a new user runs, from a directory
that contains nothing, and asserts on the exit code. A tool that only works in its own checkout is a
tool that does not work.

**What a run costs, and what that number is not.** `python tools/ci_cost.py --run <id>` prints each
job's elapsed time and the wall time of the run, read from the API. Those are seconds: GitHub bills a
job after rounding up to the minute and multiplying by an operating-system factor, so the table is not
a bill, not a quota forecast and not a price. [docs/ci-batching-proposal.md](ci-batching-proposal.md)
records one measurement and the three options for spending less; while the release policy stays
one-release-per-commit, nothing in that page is in effect.

## What stops a merge

The list below is what this project enforces *in review and in CI*. It is not a
branch setting: `main` accepts a direct push from any collaborator and has no
required status checks (`gh api repos/lyear12/citevouch/branches/main` returns
`"protected": false`). What actually gates a release is the `Test` workflow
running after the push and `auto-release` refusing to publish on a red run.
[docs/branch-protection-proposal.md](branch-protection-proposal.md) records the
measured settings, the two honest ways to change them, and the one Owner
decision that is waiting.

Any of these, and the change does not go in that day:

- a test that was changed to pass instead of code that was changed to be right (the commit must say
  why the old assertion was wrong);
- a new finding code with no test that produces it;
- a green demo run, because the deliberate `quote-missing` disappearing means matching got sloppy;
- a network call anywhere in `src/citevouch`;
- an exit code other than 0, 1, 2;
- a change to `citevouch.lock.json`'s shape without a `schema` bump.

## The retrospective (not yet automated)

The three questions are the point of the loop, which is why they live in their own section instead
of in the pipeline above: nothing runs them yet. When a retrospective does happen — a person doing
it, or an agent asked to — it asks:

1. What had to be fixed again? → becomes a lesson if it recurs three times.
2. What should not have merged? → becomes a rule in the code standards.
3. What was verified too thinly? → becomes a test, and the commit message that overstated it is
   noted in `LESSONS.md` as evidence.

A run writes to [../LESSONS.md](../LESSONS.md) under a `reviewed-through` marker at the top of the
file, so an interrupted one resumes instead of starting over. That marker currently reads `none`,
which is the honest statement of how much of this has happened: every lesson in the file was written
by the change that produced it, and none has been harvested from a day's commits after the fact.

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
the right one. It builds and attaches the sdist and wheel and copies the release notes from the range
between the previous tag and this one; a separate workflow, `publish.yml`, uploads those same bytes to
PyPI. If the tag and `src/citevouch/_version.py` disagree, the release fails before publishing, not after.

### Why publishing is its own workflow

`pip install citevouch` does not work yet, and no commit can change that: publishing needs a *trusted
publisher* registered on PyPI against this repository, which is an account action. But the entry had a
second problem, and it is the one that mattered: for a while the click-path said to register
`release.yml`, and PyPI would never have accepted that name.

PyPI's own troubleshooting page says it directly:

> Reusable workflows cannot currently be used as the workflow in a Trusted Publisher. This is a
> practical limitation, and is being tracked in warehouse#11096.
> — <https://docs.pypi.org/trusted-publishers/troubleshooting/>

`release.yml` is a reusable workflow: `auto-release.yml` reaches it through `workflow_call`, so its runs
report two different identities. Run `43395199793` recorded both, and the exchange failed:

```
workflow_ref     = .../auto-release.yml@refs/heads/main
job_workflow_ref = .../release.yml@refs/heads/main
invalid-publisher: valid token, but no corresponding publisher
(Publisher with matching claims was not found)
```

No value typed into the form could have fixed that, because the token described a workflow that is not
the file being registered.

So publishing lives in `publish.yml`, which nothing calls:

| workflow | job | what it does |
|---|---|---|
| `release.yml` | `release` | builds the wheel and sdist, attaches them to the GitHub release, records and re-reads their digests |
| `publish.yml` | `publish` | downloads the release's assets, checks them against the candidate record, uploads those bytes to PyPI |

`publish.yml` runs after `Auto release` completes (`workflow_run`) and can also be started by hand:

```console
$ gh workflow run publish.yml -f tag=v0.32.0
```

The trigger names `Auto release` and not `Release`, which is worth explaining because the obvious guess
is wrong. `release.yml` is reusable, so it has no runs of its own - `gh run list` over this repository's
100 most recent runs returns `Auto release` 49, `Test` 48, `Nightly dogfood` 3, and `Release` **zero**.
Run 43793698436 shows where a release actually lives: the jobs `publish the tag / build and publish` sit
*inside* an `Auto release` run. Naming `Release` in a `workflow_run` trigger therefore matches nothing,
which is exactly what the first version of `publish.yml` did.

The tag comes from the release, not from the tree. A `workflow_run` payload names the commit that
**started** the watched run, which is the commit before the version bump, so reading
`src/citevouch/_version.py` at that commit answers with the previous release's number. The first
production run of this workflow (43801727572) did exactly that: it announced `v0.32.1` and then tried to
publish it from a tree that still said `0.32.0`. The release that was just created is the only thing that
knows its own tag, so the tag is read from `gh release view`.

Most `Auto release` runs decide there is nothing to release, and every one of them still starts this
workflow. Retrying a version PyPI will never accept is neither useful nor honest, so the gate first reads
the watched run's own conclusion through the API (the `publish the tag` job) and stops quietly when that
run published no tag. Then it checks whether that tag has a GitHub release and whether PyPI already serves
it. Any "nothing to do" answer prints which one it is and exits green, because a workflow that goes red
every half hour is a workflow everyone learns to ignore. Asking for `actions: read` is what makes the
first check possible.

What is measured now: run 43801727572 was started by `workflow_run` on a run that was itself started by
`workflow_run`, and it reached the publish step, so the chain does fire. It failed with
`invalid-publisher` - `workflow_ref` and `job_workflow_ref` both read
`.github/workflows/publish.yml@refs/heads/main`, which is the identity the form has to match. Registering
the publisher is the remaining step, and the manual `gh workflow run` door is still the one for a tag
older than this workflow.

### The click-path

1. Sign in at <https://pypi.org/manage/account/publishing/>.
2. **Add a new pending publisher** with exactly these values:

   | field | value |
   |---|---|
   | PyPI Project Name | `citevouch` |
   | Owner | `lyear12` |
   | Repository name | `citevouch` |
   | Workflow name | `publish.yml` |
   | Environment name | *(leave empty)* |

3. Save. Nothing else: `publish.yml` declares `permissions: id-token: write` and pins no `environment:`,
   so an environment name here would make the OIDC subject disagree and the publish would fail rather
   than silently skip.
4. Run `gh workflow run publish.yml -f tag=v0.32.0` (or wait for the next release).

The run's summary tells the four outcomes apart, because they need four different responses:

- `Published 0.32.0 to PyPI.` — done.
- `Nothing was uploaded` — either that tag has no release yet, or PyPI already serves it; the step above
  the summary says which, and neither needs anyone to do anything.
- `invalid-publisher` — the form does not match this workflow's identity; re-read the table above. This is
  the one that asks the Owner to act.
- `invalid-payload` or `invalid-token` — the token exchange itself failed, which is about that run and
  not about the form; re-running is the response.

To check whether it worked without publishing again:

```console
$ curl -s -o /dev/null -w '%{http_code}\n' https://pypi.org/pypi/citevouch/json
404        # before the first publish (expected today)
200        # after publish.yml has succeeded once
$ pip download --no-deps citevouch -d /tmp/x && ls /tmp/x
```

`404` here is not a failure of the project; it is the absence of a distribution, which is what a
pending publisher is for. The GitHub release carries the same wheel and sdist either way, so
`pip install <url of the attached wheel>` works before PyPI is set up.

## Reporting a problem

Open an issue with:

- the command you ran and its exit code;
- the finding codes you got and the ones you expected;
- if possible, a three-line manuscript and a small source file that reproduces it.

A reproducible report is worth twenty paragraphs, because the first thing the agent does is turn it
into a test — and a report that cannot become a test cannot be fixed.
