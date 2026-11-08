# Lessons from merged work

<!-- reviewed-through: none (pre-1.0, no nightly review yet) -->

`citevouch` is written, reviewed and released by agents. Each night the day's commits are reviewed
for what had to be fixed again, what should not have merged, and what was verified too thinly. What
we learned is kept here. Read this before changing code.

Each lesson is a rule, then why, then the evidence. "Seen" counts the separate days a review found
it. A lesson seen on three or more separate days moves into [docs/code-standards.md](docs/code-standards.md).

This file starts from the lessons that were already paid for during the first build of the tool,
before any nightly review existed. The evidence below is real: each entry names the file or the
command output that produced it.

## Reading this file

Oldest first: the lessons from the first build are at the top and each new one is appended, so the
bottom of this file is the most recent thing learned. When a lesson stops being possible — because
the code moved or the rule became a test — delete it and say which test replaced it. A lesson that
no longer maps to code is worse than no lesson, because the next agent will follow it somewhere it
does not apply.

---

## Fix the class, not the sample

**Rule.** When a bug shows up in one place, find the other places with the same shape before
writing the fix, and fix them in the same commit.

**Why.** A bug found by a real manuscript is a sample of a class. Fixing the sample means the next
manuscript finds the class again, and the fix cost is paid twice.

**Evidence.** A real 39-entry bibliography parsed as **one entry**. The cause was `_strip_comments`
treating every `%` as a comment even inside a field value: `note = {… 78.5%, 高于 CRF 基线 4.5 个
百分点}` was truncated at the `%`, which ate the closing brace, which swallowed every entry after
it. The sample fix would have been "escape the percent". The class fix — decide comment-ness by
brace depth and quote state, not by the character — is what shipped. Seen 1.

---

## A test that passes for the wrong reason is worse than no test

**Rule.** After writing a test, break the code on purpose and confirm the test goes red. If it
stays green, the test is measuring something else.

**Why.** The suite is the only thing standing between an agent and a confident wrong change. A test
that cannot fail is worse than a missing test because it also silences the suspicion that something
is unverified.

**Evidence.** `test_whitespace_collapses_to_single_spaces` asserted `normalize("a   b\t\tc\r\nd")
== "a b c"`. The implementation returned `"a b c d"` — and the implementation was right, because
`\r\n` is a line break and the words on either side are two words. The test had been written from
a guess about the output rather than from a decision about the behavior. The fix was to correct the
test, not the code, and to say in the test name that a line break becomes a space. Seen 1.

---

## The path the user types is the path that exists

**Rule.** When a flag takes both a `--root` and a path, do not join them blindly. If the path
already resolves from the working directory, use it as given.

**Why.** `citevouch check demo/manuscript.md --root demo` is not a mistake a user makes once; it is
what everyone types, because the root is for *sources* and the manuscript path is for *the
manuscript*. Re-rooting it produces `demo/demo/manuscript.md` and an error message that blames the
user for a path they can see in their own shell.

**Evidence.** The first real end-to-end run failed with
`citevouch: manuscript demo\demo\manuscript.md does not exist`. The rule now in `scan._resolve`:
"A path that exists as given is never re-rooted: the file on disk is the authority." Seen 1.

---

## Two names that look alike are two namespaces

**Rule.** When two identifiers are routinely equal but conceptually distinct, keep them in separate
fields even though it feels redundant. Then default one from the other, never merge them.

**Why.** Conflating them produces findings that are technically true and practically wrong, and
those are the findings that make users stop reading output.

**Evidence.** A claim wrote `source=vaneecke2026cxn` (the local PDF) and the bibliography key was
`vaneecke2026learning` (the entry). The checker reported five `bib-key-missing` findings at `high`
severity for a manuscript that cited correctly. `Claim.ref` now exists separately, defaults from
nothing, and matching uses `claim.ref or claim.source`. Seen 1.

---

## Report a class once, not once per member

**Rule.** A finding that can fire thirty times in one run is one line with a count and a sample. A
finding that fires once is its own line.

**Why.** Output is a budget. Spending it on thirty-seven lines about an unused bibliography means
the one line about the missing quote scrolls off the terminal.

**Evidence.** The first run against the real bibliography emitted 37 `bib-key-unused` lines and
buried the single `quote-missing` that mattered. It is now one line:
`37 bibliography entries are cited by no claim: aboumikhael2025c2xg, beuls2021frame, … (+29)`.
Seen 1.

---

## Verification and recording are different verbs, and mixing them hides failures

**Rule.** The command that writes the lockfile may report problems but must not be the only place a
problem is reported. The command that re-checks must be runnable against an unchanged tree and still
mean something.

**Why.** If `scan` is the only thing that reports "the quote is not there", then every user learns
that a green `scan` means correct, when it means *recorded*.

**Evidence.** `scan` originally produced `quote-found` findings, which made the lockfile writer look
like a verifier. `verify` now owns every match finding; `scan` owns only what it can see without
re-reading evidence (parse errors, unbound markers, page hints out of range). `tests/test_scan_verify.py`
asserts the split. Seen 1.

---

## Deliberate red is a feature of the fixture, not a bug in the tool

**Rule.** Keep at least one failing case in the committed demo, and assert on which case fails.

**Why.** Everyone can make a checker that says yes. The regression that matters is the one where the
checker must still say no after becoming more permissive.

**Evidence.** `demo/manuscript.md` backs its `fcg-editor` claim with the wrong paper on purpose. Four
claims verify, that one returns `quote-missing` at `high`, and the run exits 1. `AGENTS.md` tells
every agent this must stay true. Seen 1.

---

## An error message that names the fix is worth ten that describe the failure

**Rule.** Usage errors end with the command to run next.

**Why.** A pre-1.0 tool has no users who have read the source. The message is the documentation.

**Evidence.** `no ledger at citevouch.lock.json; run \`citevouch scan\` first` and
`manuscript.md changed since the ledger was written; run \`citevouch scan\` to re-record the
evidence` both carry their own next step. Seen 1.

---

## A dependency you did not declare is a platform you did not port to

**Rule.** When the package claims `requires-python = ">=3.10"`, every stdlib import that is newer
than 3.10 needs a fallback or a test that runs the fallback, and the local interpreter is not
evidence of either.

**Why.** The developer machine runs one Python. A support floor that is only exercised on the
newest interpreter is a claim, not a property. The failure is doubly quiet here: the missing
`tomllib` was caught with a bare `except ImportError: continue`, so instead of an error the
manifest was dropped and every claim came back `source-missing` — a plausible-looking verdict
produced by a code path that never ran.

**Evidence.** Run 40718071365: all six 3.10 and 3.13 jobs on Windows passed, both 3.10 jobs on
Linux and macOS failed, and the 3.12 jobs passed — which looks like a flaky platform and is
actually a version. Log lines: `[high] source-missing at m.md:1 (c1): claim c1 names source='p' but
no file matches it` and `KeyError: 'smith2026cxn'`. The fix is `_mini_toml` in
`sources.py`, plus `test_the_manifest_subset_reads_sources_toml_without_tomllib`, which runs the
fallback on 3.14 so the next breakage is not invisible until CI. Seen 1.

---

## A step that has never passed is not a step that passes

**Rule.** When a job fails, read the whole job, not the first failing step. A green step above a
red one may itself be new.

**Why.** The acceptance job hid two independent defects behind one failure. Fixing the first
revealed the second, and each looked like "the same broken job" from the outside. The second one —
the offline step needing pytest, which the job never installed — had never run to success in the
job's lifetime, so its absence from the dependency list had never cost anything before.

**Evidence.** Run 40719079624: `init-demo succeeds` and `the demo still says no to the wrong paper`
both passed on Linux (`demo acceptance OK: {'checked': 5, 'verified': 4, 'moved': 0,
'missing': 1, ...}`), and the job still went red on `offline` with
`/opt/hostedtoolcache/Python/3.12.15/x64/bin/python: No module named pytest`. Run 40719532303 is
the first green acceptance. Seen 1.

---

## A workflow is code, and it is the least reviewed code in the repository

**Rule.** Assertions inside a CI step get the same treatment as assertions in a test: no heredocs
inside YAML block scalars, no assumptions about the working directory a previous step left behind,
and a failure message that says what the expected value was.

**Why.** The acceptance assertion was a `<<'PY'` heredoc nested in a literal block, quoted
f-strings inside YAML quoting, and a `cd` into a temp directory two steps earlier. None of it
failed at authoring time, because nothing runs a workflow until it runs on GitHub. The cost of a
wrong assertion here is worse than in a test: it fails in the one place that gates a release.

**Evidence.** The first version of `the demo still says no to the wrong paper` passed a
`claim_id` list through an f-string with escaped quotes inside a YAML block; it was replaced by a
single-line `python -c` with an explicit expected value in the error message. The `init-demo`
step also called `verify` without recording a ledger first and reported
`no ledger at citevouch.lock.json; run \`citevouch scan\` first`. Seen 1.

---

## A scaffold that stops one step short is a broken first run

**Rule.** When the documented first command produces a project, the documented second command must
succeed on it. Write the acceptance criterion as the pair, not as the first one alone.

**Why.** The same missing `scan` reached four places: the acceptance job, the release smoke test,
the README's 60-second section, and `init-demo`'s own idea of "done". Each was fixed separately
before anyone noticed they were one bug, because each looked like a workflow or a documentation
problem rather than a defect in the command. The class is "the scaffold and the consumer disagree
about what state the project is in", and it belongs to whoever writes the scaffold.

**Evidence.** `citevouch init-demo my-paper && cd my-paper && citevouch verify manuscript.md`
printed `citevouch: no ledger at citevouch.lock.json; run \`citevouch scan\` first` and exited 2 —
the README's own example, failing. `cmd_init_demo` now records the ledger and then verifies, and
`test_init_demo_writes_a_project_that_the_documented_next_command_accepts` runs the pair. Seen 1.

---

## A report and an exit code that answer different questions

**Rule.** Anything that highlights what is wrong takes its threshold from the same value the
exit code takes.  A summary is not allowed to have its own opinion about what matters.

**Why.** `render_markdown` split findings into `### Blocking` and `### Other` by severity:
everything `high` blocking, everything else not.  The run fails when a finding reaches
`--fail-on`, which is `high` by default and therefore agreed with the report in every case
anybody tried.  At `--fail-on medium` the two disagree, and the report puts the entire
reason for a red build under Other.  The person reading that report is reading it because
they do not trust the exit code alone; sending them to the wrong section is worse than
sending them nowhere.

This is the third variant of one defect in this file: a second thing that describes the
same fact and is computed by a different rule.  The first two were the plural typed into a
template while the package had a helper, and truncation counted at one level while it
happened at two.

**Evidence.** `citevouch check --format markdown --fail-on medium` exited 1 with the only
cause under `### Other (1)` before this change, and `--fail-on high` versus `--fail-on
info` produced identical headings.  The unit tests of the renderer could not catch it
because they call `render_markdown` directly and never exercise `main` - the reverse
verification of the *caller* stayed green until `TestTheReportAgreesWithTheExitCode` went
through the command line.  Seen 3.

---
## A report that stops listing has to say where it stopped

**Rule.** When output is capped, the cap is stated in the output itself, at the level where it
applied, and a test covers the band between the caps and not only the case above all of them.

**Why.** `render_markdown` capped the list at 200 and each section at 50, then printed "and N more"
by comparing the total against the first cap alone.  Sixty findings rendered fifty bullets under a
heading reading `### Blocking (60)` and said nothing about the other ten.  Nobody noticed because
the one truncation test used 250 findings - above both caps - so the middle band, where the two
numbers disagree, had no test at all.  A truncated report and a complete one look identical to the
reader; the count in the heading is what they trust.

**Evidence.** `tests/test_report.py::test_markdown_marks_truncation` used `range(250)` and asserted
`"more" in out`.  It passed throughout.  Now
`test_a_section_that_stops_early_says_how_many_it_dropped` uses 60 and
`test_both_caps_are_reported_when_both_bite` uses 260.  Seen 1.

---
## A command with no test is a command nobody has run

**Rule.** Every CLI verb gets at least one test that runs it end to end and asserts the exit code.

**Why.** `init-demo` was the one verb with no test, and it was the one verb that was wrong in three
different ways (no ledger, no test coverage of the refusal path, and a "wrote ..." message that
described files it had not finished making useful). Coverage is not the goal; the goal is that a
verb whose job is "leave the user in a working state" has somebody checking what state it leaves.

**Evidence.** `grep -rn "init-demo\|init_demo" tests/` returned nothing before this commit.  Now
`test_init_demo_writes_a_project_that_the_documented_next_command_accepts` and
`test_init_demo_refuses_a_directory_that_already_has_something`.

**Seen 2.** The first version of this lesson made the same mistake inside its own evidence: it said
`tests/test_cli.py` covered "scan, verify, check, report, formats, exit codes, and error paths".
`report` had no test at all.  It printed `0 entrys` and left a `|` in a claim id unescaped, and both
survived four releases because the sentence listing what was covered had been written from memory
rather than from `grep`.  A claim about coverage is a measurement; measure it.

---

## A matrix cell that cannot run is not a passing cell

**Rule.** Every cell in the build matrix has to be one a runner can actually satisfy. If a cell is
repeatedly queued rather than run, the platform combination does not exist — remove it and say so in
a comment, do not wait for it.

**Why.** `macos-latest` is arm64 and CPython has no macOS arm64 build for 3.10. That cell never ran:
first it failed with `Version 3.10 was not found in the local cache`, then, after the interpreter
setup was pinned differently, it sat in the queue for the life of the run and was cancelled. Both
outcomes read as infrastructure noise, so both hide the same thing — the combination was never
tested, while the badge and the docs went on saying "3 OS × 3 Python versions".

**Evidence.** Run 40718071365: `[high] source-missing ...` and `assert 1 == 0` at
`tests/test_cli.py:36` on `macos-latest, 3.10`, preceded by `Version 3.10 was not found in the
local cache`. Runs 40723774939 and 40725206004: the same cell `queued` from 16:13 and 16:21 until
cancelled, while `macos-latest` 3.12 and 3.13 started within seconds. Excluded in the matrix with
the reason written next to the exclusion. Seen 3.

---

## continue-on-error is not "ignore this, it is fine" - it is "check the outcome"

**Rule.** A step with `continue-on-error: true` needs a later step that reads `steps.<id>.outcome`
and says, in the run summary, which of the two things happened. Otherwise the flag does not mean
"allowed to fail", it means "failure is invisible".

**Why.** The first release reported success and the PyPI step reported success, while PyPI had in
fact rejected the upload: no trusted publisher is registered for the repository, so the OIDC token
had no claim set to match. The run said green, the step said green, and `pip install citevouch`
returned 404. A release pipeline whose only observable difference between published and not
published is a green check mark is a pipeline that cannot be trusted about the one thing it does.

**Evidence.** Run 40728041391, step 9: `##[end-action id=__pypa_gh-action-pypi-publish.__self;
outcome=failure;conclusion=failure]` while the job's own conclusion was `success`. `curl
https://pypi.org/pypi/citevouch/json` -> 404. The step now carries `id: pypi` and the summary step
branches on `steps.pypi.outcome`, naming the missing trusted publisher. Seen 1.

---

## A removal announced in one file is not a removal

**Rule.** When a behaviour is deleted, `grep` for the behaviour, not for the
name you gave it in the docstring. The function that performed it is usually
called something else, and it usually lives one layer below the place the
comment talks about.

**Why.** A round of review found that discovery bound a claim to a file when
the claim's key was a prefix of a real key. The fix written was to the
`discover_sources` docstring plus one test of `discover_sources` - and the
CHANGELOG said the guessing was gone. It was not: the two prefix loops were in
`resolve_source`, which `discover_sources` calls, and the diff had not opened
that function. The announced removal was a false statement in the changelog, in
a commit whose entire subject was "stop inferring bindings", and it survived
two further reviews because both read the diff and neither re-ran the case. A
claim naming `vaneecke2026cxnWRONGSUFFIX` - a key that exists in no manifest
anywhere - still bound to the CoNLL paper and still produced `quote-found` at
exit 0.

The reason this class repeats is structural: a docstring is where you look up
the behaviour, so it is where you patch the belief. The code that holds the
belief is one call away and has no reason to appear in the same hunk.

**Evidence.** Third review, N1. `grep -rn "startswith" src/citevouch/` returned
the two live loops in `resolve_source` after the commit that claimed to delete
them; `grep -rn "resolve_source" tests/` was empty, which is the second half of
the same fact - the function no inference was supposed to happen in had no test
at all. `tests/test_critic_round3.py::TestNoInferenceByPrefix` now covers it,
including the end-to-end case where the typo must reach the reader as
`source-missing`. Seen 1.

---

## A version number is the one thing you cannot withdraw

**Rule.** Decide versions in code with tests, not in a shell `if` inside YAML. `tools/next_version.py`
is the only thing allowed to pick a number, and its table is the version policy written once.

**Why.** A package published to a registry under a wrong number cannot be deleted, only superseded,
and every user who pinned it keeps the mistake. The changelog already said what changed; the only
real decision left is whether a `Changed` entry may ride in on a patch. It may not, and that belongs
in a table with a test per row rather than in a run's shell output at 3am.

**Evidence.** Before this, the only thing connecting a changelog entry to a number was a person
reading it. The release workflow refuses a tag that disagrees with `pyproject.toml`, which catches a
typo, not a wrong judgement — `0.1.1` containing a removed feature is a perfectly consistent pair of
files. Seen 1.

---

## A workflow that can release must also be able to say "not today"

**Rule.** The automatic path needs a first-class "nothing to do" outcome, with an exit code and a
summary line, distinct from failure. `next_version.py` exits 1 for "no entries", the workflow turns
that into a notice and a green run, and only a nonzero exit that is not 1 fails.

**Why.** The common case is that four pushes in a day contain one release and three non-releases.
If "nothing to do" reads as failure, the workflow is red most of the time, and a permanently red
workflow is one people stop reading — which is how the PyPI failure went unnoticed in the first
place.

**Evidence.** The first attempt at this file would have failed the run on an empty Unreleased
section. `test_cli_says_nothing_to_release_and_exits_one` pins the exit code, and the workflow's
`if [ "$status" -eq 1 ]` branch is the only place that mapping is allowed to be spelled. Seen 1.

---

## A tag is the artifact; building "wherever this run happened to start" is not

**Rule.** When one workflow hands a version to another, the release must check out the object named
by that version — the tag — not whatever commit the trigger left in the working directory. Assert
`pyproject.toml == tag` *after* that checkout, so the assertion proves the pairing rather than
luckily matching.

**Why.** `auto-release` bumps the version, commits, tags, and calls `release.yml`. But a reusable
workflow's `checkout` lands on `github.sha` — the commit that started the whole chain, which is the
one *before* the bump. Without re-checkout, release builds the previous code, the tag/code agreement
check passes only because it is comparing the new number to the old file and failing — so it caught
itself, which is good — but the moment that check is loosened, a numbered release of stale code ships
silently. The safe thing is to build the tag itself, so "tag matches pyproject" is true by
construction.

**Evidence.** Run 40730668174: `decide` committed `b100b92 Release 0.2.0` and tagged `v0.2.0`, then
the called `release` failed at `Tag and pyproject must agree` — its checkout was `f342af0`, still
declaring 0.1.0, while it was asked to publish 0.2.0. Because `main` still pointed at the bump, the
release was re-cut by hand (workflow_dispatch, version 0.2.0, from b100b92) and `gh release view
v0.2.0` now lists both artefacts. The fix adds a `Build the tag...` step before the agreement check.
Seen 1.

---

## A confident comment about an API's behaviour is a bug report waiting to happen

**Rule.** When a comment states what an external API does, it needs the request that proves it, not
the belief that produced it. "X is ignored when Y" sentences in YAML are the most dangerous kind,
because nobody argues with a comment on first read.

**Why.** `gh release create --target "$tag"` failed 0.2.1's publication with
`Release.target_commitish is invalid`. The line above it read: "When the tag does exist, --target
is ignored in favour of it, which is what we want." It had never been executed - the dispatch
re-cut of 0.2.0 took the *no-tag* branch, so the tag branch had never reached the API. Every step
before it passed, so the comment's claim looked corroborated right up to the step that disproved it.

**Evidence.** Run 40818189710: every step green through Smoke-test and Publish, then
`HTTP 422 ... Release.target_commitish is invalid`, then the `|| gh release upload` fallback printed
its own confusing `release not found` under it. Both are fixed: the flag only on the create-tag
path, and the fallback demoted to a named step gated on `steps.create.outcome == 'failure'`, so the
second error cannot be printed unless the first happened. Seen 1.

---

## The acceptance list is the gate; CI's commands belong in it verbatim

**Rule.** Every check CI runs must appear in AGENTS.md's acceptance block spelled exactly as CI
spells it. An agent works the list, not the workflow files, and a check missing from the list is a
check that will not be run.

**Why.** The lint job runs `ruff check .` **and** `ruff format --check .`. The acceptance block
listed pytest, install, and init-demo - no lint line at all. So a change whose tests were written
through a heredoc, unformatted, passed every item on the list and still turned CI red: `check` is
clean on that file, only `format --check` rejects it. The list let an agent be honest and complete
and fail the gate anyway, which is the one thing an acceptance list is not allowed to do.

**Evidence.** Run 40819203256 on bb35ad1: lint failed with `1 file would be reformatted` pointing
at the heredoc-appended tests in `tests/test_next_version.py`, and auto-release correctly skipped -
the gate did its job, the list had not. Reproduced locally: `ruff check .` passes, `ruff format
--check .` fails. Both halves are in the acceptance list now, in AGENTS.md and
docs/code-standards.md. Seen 1.

---

## A test that reads state it does not own races the repository

**Rule.** A test may compute its fixtures, but it may not read the repository's living files and
assert what their *current content* implies. Copy the shape into the test; guard the real files only
with assertions that stay true under every legal change to them.

**Why.** `test_apply_on_the_real_changelog_keeps_links_consistent` read the real CHANGELOG.md,
injected a `### Fixed` entry, and asserted the result was a patch bump - while forgetting that the
file it was reading is the queue the release pipeline drains, and the day it legitimately held an
`Added`, "patch" became "minor" by design. The test of the release machinery broke the release it
guarded, on all three OSes, at the exact moment the project had its first real feature entry. The
repository changes under a test that reads it; the test is not wrong then, it is a race.

**How to recognise it.** The failure is unconditional and delayed, not flaky: green for weeks, then red on a change that is correct. That shape reads as a real regression to whoever sees it first, which is why it survives review.

**Evidence.** Run 40842840982 (push 8f3129a, the changelog catch-up): all eight matrix cells red on
`assert '## [0.2.3] — 2026-11-01' in ...` while the tool correctly printed `0.3.0` and `bump: minor
(from Added, Fixed)`. Meanwhile auto-release had already consumed that Unreleased section into
v0.3.0 - with regenerated links and re-pointed README pins - so the repository was correct and the
test was the only thing broken. Now the test builds its own stale-block changelog in `tmp_path`, and
the guard that does read the real files asserts only an invariant that survives every release:
pyproject's version has a heading and a link. Seen 1.

---

## A rewrite of a fix is a second chance to make the original mistake

**Rule.** When repairing a class of silent failure, write the "well-formed input
stays silent" test first and run it on the finished code - the new silence is as
dangerous as the old one, and rewrites are where it hides.

**Why.** The critic round found that the `%`-comment rule (fixed once for braces,
LESSONS "Fix the class, not the sample") had been re-broken in the very commit
that fixed five sibling silences: the rewritten comment scanner applied the old
`depth == 0` test inside entries too, so `note = "78.5% above CRF"` in a
paren-delimited entry still cut the line. An agent mid-refactor carries the
previous fix's assumptions forward without noticing they stopped applying.

**Evidence.** `tests/test_critic_round1.py::test_paren_entry_percent_survives_and_next_entry_is_read`
and `::test_wellformed_bibliography_stays_silent` failed on the first draft of
the fix itself, before it was committed; both pass now, and the 39-entry real
bibliography parses to 39 entries with zero findings. Seen 1.

---

## A comment describing an absent fallback is worse than no comment

**Rule.** When you find a docstring promising a behaviour, check whether the code
does it before you rely on the docstring - and when it does not, delete the
promise rather than writing the feature to match it, unless a test already
depends on it.

**Why.** `discover_sources` had a docstring describing four resolution steps:
`--source` paths, the manifest, "any file whose stem equals the key", then "the
longest stem the key starts with". The body implemented two. The two missing
steps were not a forgotten feature, they were a bad idea that had been written
down as though it shipped: binding a claim to a PDF because the filenames share
a prefix is the exact inference this tool refuses to make, because a wrong
automatic binding produces a confident `quote-found` against the wrong paper and
the author never learns the page number came from somewhere else. The comment
was load-bearing in a second way too - a reader repairing the module would have
"restored" the fallback, and the bug it introduced would have looked like a
feature. Now the docstring says what is excluded and why, and `source-missing`
names the near misses on disk so the fix is a paste without the tool deciding.

**Evidence.** Found while writing the round-2 regression tests: four new tests
failed with `source-missing` because they bound `source=src` and wrote
`src.txt`, expecting the documented stem match. The code was right and the
documentation was fiction; `load_manifest`'s docstring carried the same claim
("falling back to filename-stem resolution is almost always right") and so did
`_mini_toml`'s. All three now describe the behaviour that exists. Seen 1.

---

## The rule you write in the contract is not in force until something executes it

**Rule.** When the project states a rule about its own code - in AGENTS.md, in a
docstring, in a review checklist - either a test or a script enforces it, or it
is a wish.

**Why.** AGENTS.md rule 2 said a fuzzy match "must never exit 0 on its own". It
was true of the severity table (`quote-fuzzy` is medium) and false of the
programme, because the default `--fail-on` is `high`: the tool reported a claim
it had just said it could not verify, and returned success. Separately, every
rule in the repository's own contributor contract (the three evidence sections
in a commit message; lessons seen three times must be promoted into the standards
document) sat in prose with nothing reading it - the promotion debt had already
accumulated when the script was finally written. A rule with no executor is a
rule that holds only where someone remembered it.

**Evidence.** `citevouch verify` on a fuzzy-matched claim exited 0 at the
default threshold. The first fix was a single early return in `_exit_code`, and
that was the second version of the same mistake: it made the rule true by
special-casing one code in the exit path, so `--fail-on` still did not mean what
three documents said it meant. The fix that holds is the boring one - make
`quote-fuzzy` a `high` finding and let the threshold do its job. The regression
test is `tests/test_critic_round2.py::test_a_fuzzy_match_fails_even_at_fail_on_high`.
`tools/check_repo_rules.py` (added in 0.3.0) found a real promotion debt on its
first run. Seen 2.

---

## A severity table is a contract with the exit code, so nothing may bypass it

**Rule.** The exit code is computed from severities and the `--fail-on`
threshold. If a finding needs to fail a run, its severity goes up. There is no
third place to decide.

**Why.** `quote-fuzzy` was `medium` *and* had an unconditional `return 1` in
`_exit_code`. Both halves were defensible alone and incoherent together: the
table said the finding was a warning, the programme treated it as a failure, the
README told users `--fail-on` was the only knob, and a user who lowered the
threshold to `info` got a failure from a code the documentation called medium.
Two places to decide one thing is a bug report you have not filed yet.

**Evidence.** `citevouch check --fail-on high` on a fuzzy-matched claim failed,
while an unrelated `medium` finding in the same run did not; the README promised
`--fail-on` alone decides. The special case is gone and the severity is `high`,
so the documented rule and the executed rule are the same sentence. Seen 1.

---

## A silently dropped element is worse than a reported one

**Rule.** When a reader cannot consume something, it says so. Never `continue`
past a structure that changes what the rest of the file means.

**Why.** Two separate defects had the same shape. An unclosed ```claim fence
made the parser read every following claim as part of that block, so a
manuscript lost claims silently and the survivor failed as `quote-missing` -
pointing at the PDF when the typo was three backticks. And `load_manifest`
walked a list of manifest names with `else: continue`, so `sources.yaml` was
advertised in the tuple and ignored by the loop: a project could ship a manifest
the tool never opened. In both cases the tool knew enough to say the true thing
and chose silence.

**Evidence.** `parse_manuscript` on a file with a missing closing fence returned
one claim and zero findings; `sources.py` listed four manifest names and handled
two. Both are now reported (`claim-block-unclosed`, and the list only names the
formats that work). Seen 1.

---

## 0 is falsy, and a page number is allowed to be 0

**Rule.** Test `is None`, never truthiness, for any value a user typed and that
has a real zero.

**Why.** `report` rendered the page cell as `claim.page or '—'`. A ledger
carrying `page: 0` - a mistake, but a *recorded* one - displayed as an em dash,
which reads as "no page recorded". The author checking what the ledger says got
a different answer from the one that was there. This is cheap to fix and
expensive to notice: nothing crashes, and the wrong answer looks like a design.

**Evidence.** A hand-edited ledger with `page: 0` printed `| c1 | p | — |`
before the fix and `| c1 | p | 0 |` after. Seen 1.

---

## A file the tool both writes and reads is written the way it is committed

**Rule.** Use `newline="\n"` (or `os.linesep`-free bytes) for anything this
project produces and then reads back. Never let the platform pick.

**Why.** `_write_ledger` used `Path.write_text`, which opens in text mode with
universal newlines. On Windows that turned every `\n` into `\r\n`, so the
lockfile landed on disk in one encoding and in the repository in another, git
printed "CRLF will be replaced by LF" after every scan, and a colleague cloning
on Linux and running `verify` saw a byte-different file from the one the author
recorded. The lockfile exists to be read in a diff. A writer that only agrees
with the committer by accident is a writer that will disagree on the day it
matters.

**Evidence.** `git diff demo/citevouch.lock.json` after a plain
`citevouch scan` on Windows showed 11 changed lines that were not changed;
`tests/test_critic_round4.py::test_the_ledger_is_written_with_lf_endings_on_every_platform`
fails if `\r\n` appears in a freshly written ledger. Seen 1.

---

## A guard that lists the files it protects protects only those files

**Rule.** A test that keeps documents honest has to decide which files are
documents by scanning for them, not by naming the three that came to mind. When
a file type is added to the repository, the guard has to already be looking
there.

**Why.** `test_no_document_says_the_version_lives_in_pyproject` (in
`tests/test_critic_round3.py`) was written to stop a file from sending an agent
to edit a version that lives somewhere else. It scanned `AGENTS.md`, the two
READMEs and `docs/*.md`, and it matched a list of two known-wrong phrasings. The
version then moved to `src/citevouch/_version.py`, and the header of
`auto-release.yml` and `release.yml` went on saying the release step "writes it
into CHANGELOG.md and pyproject.toml" for two releases. Both defects are the
same defect: the guard encoded what someone had thought of, so it could only
ever catch what someone had already thought of. A list of known-bad strings is
a record of past bugs, not a rule.

The fix is in the same file: scan `.github/workflows/*.yml` as well, and for any
line mentioning `pyproject.toml`, require it to also say what `pyproject.toml`
actually does (`declares`, `reads it`, `dynamic`, `attr`). Adding a fourth
wrong phrasing no longer buys silence; a sentence that is wrong in a new way
still fails.

**Evidence.** `grep -n "pyproject" .github/workflows/*.yml` after v0.6.0 showed
two stale header comments that the guard had been passing over since v0.5.0.
Seen 1.

---

## Silence is a verdict, and a verdict needs to say which claim it is about

**Rule.** When the pipeline skips a claim, the reason is a finding at the
severity that says whether the run may pass. A skip that produces no finding is
a pass, and a pass about a claim that was never compared to anything is the
exact failure this tool exists to prevent.

**Why.** A claim block missing `source=`, or repeating an id, was reported as
`claim-without-evidence` at `low`. The severity was chosen for the *other* user
of that code — a bare `【原文】` marker in prose, where "you did not bind this"
genuinely is advice and not an error. Reusing it for a malformed claim block
made both quiet, and the default `--fail-on high` let a run go green while the
claim's quote had never been looked up. The two cases need different codes
because they need different fixes: bind a marker, repair a block.

**Evidence.** `citevouch check` on a manuscript whose only claim has no
`source=` returned `0 claims`, `worst severity: info`, exit 0 before this
change. Seen 1.

---

## The unambiguous form of a question is worth designing for, not guessing at

**Rule.** When two inputs are genuinely indistinguishable, report the one that
loses data, and make the safe form structurally different rather than asking
people to be careful.

**Why.** `` ``` `` opened around a claim block and never closed produces the same
text as a code sample that legitimately contains a `` ```claim `` line: in both,
the swallow ends exactly at a line meant to end a claim. Guessing "sample" loses
the file's claims silently; guessing "forgot the fence" reports a fence someone
deliberately nested. The tie is broken toward the loss, and the escape hatch is
a **four-backtick** outer fence, where CommonMark nesting is unambiguous and the
closing run can only be the longer one. That is a rule a person can apply
without knowing which interpretation the tool picked.

**Evidence.** The fifth review found `` ```python `` left open swallowing a
claim and exiting 0; the fourth fixed only the `` ```claim `` path and left this
one. Seen 2.

## A measurement that can come back empty must be treated as a failure, not a zero

**Rule.** When a script derives a number by parsing another tool's output, an
empty parse is a hard error. Check that the parse produced something before you
compare it with anything, and make the silent path fail loudly.

**Why.** `passed=$(... | grep -oE '[0-9]+ passed' ... | cut -d' ' -f1)` reads
"nothing matched" and "the suite passed zero tests" as the same value, so a
change to the command's verbosity turns a working gate into a gate that fails
every commit with a confident, wrong accusation. The failure is indistinguishable
from the check doing its job, which is exactly the shape of bug this project
exists to catch in manuscripts.

**Evidence.** The `_passed` rule added in the fifth review broke its own first
CI run: `pyproject.toml` already sets `addopts = "-q"`, so the step's
`pytest -q` was really `-qq`, which drops the summary line. Run 41015105068's
lint job printed `the suite reports 0 passing tests` next to
`Answer the fifth review ... says 288 passed, the suite reports 0`. Seen 1.

## A documented form that parses to nothing is a false negative with a spec

**Rule.** Every input shape you show a user must be covered by a test that reads
that shape from the document. Example code in a README is the least-tested and
most-copied code in the project; if it is wrong, the users who read carefully
are the users who get the wrong answer.

**Why.** `<!-- claim: c2 source=x page=4 -->` on one line was the literal
example in both READMEs. The parser's HTML branch was guarded by
`and "-->" not in line`, so a single-line comment was skipped by the *same
condition* that existed to detect a multi-line one — an author who copied the
example got `0 claims`, `worst severity: info`, and exit 0 from a check that
never looked at their quote. Documentation that disagrees with the code is a bug
in both; which one is wrong is decided by which one the user trusted.

**Evidence.** Sixth review, major-1. The fix moved the branch to `if m:` and
split on `-->` first. Seen 1.

## A fence is defined by its own character, not by the length of the run

**Rule.** A `~~~` block is closed by tildes, a backtick block by backticks, and
the count only has to be at least the opener's. Treating the two characters as
interchangeable silently converts "sample" into "claim".

**Why.** `~~~` is the CommonMark fence authors reach for *because* a sample
contains backticks. Not recognising it was worse than not recognising a pad: a
`claim` written inside a tilde-fenced sample was read as a real claim, verified
against a source, and reported `quote-found` — a positive verdict on a specimen
that was never meant to be checked. A false negative costs a re-read; a false
positive in the "found it" direction costs the tool's premise.

**Evidence.** Sixth review, major-2: `_ANY_FENCE` matched backticks only, and
`tests/test_critic_round5.py::test_a_claim_inside_a_tilde_fenced_sample_is_not_a_claim`
fails without `~{3,}` in the pattern. Seen 1.

## Tolerance for a value is not tolerance for a file

**Rule.** A parser that only supports a subset must distinguish "this file is
structurally broken" from "this file contains something I do not represent".
Broken files fail whole; unrepresentable *keys and values* drop themselves.

**Why.** `_mini_toml` raised on `enabled = true`, and its only caller treats a
raise as "unreadable manifest" — so on Python 3.10 one boolean unbound every key
in `sources.toml`, while 3.11+ handed the same file to `tomllib` and bound them
all. The bug was invisible on the development interpreter by construction: the
fallback only runs where the real parser is absent. A support floor is not a
claim about `pyproject.toml`; it is a claim about every path that runs there.

**Evidence.** Sixth review, major-3, for values; seventh review, major-2, for
keys — the value branch was fixed and the key branch beside it was not, because
the fix was written against the reported input rather than against the
distinction. Seen 2.

## A cache keyed by the input forgets that the reader changed

**Rule.** If a cached value depends on who produced it, the producer's identity
belongs in the key. Content-hash keys cover "the input changed"; they say
nothing about "the code that read the input changed".

**Why.** The extraction cache stored pages under the source's SHA-256 alone.
Upgrading `pypdf` changes what a page yields — that is what upgrading a PDF
extractor is — and the ledger would go on reporting `quote-found` from text the
current reader would never produce. It is the same failure the tool exists to
find, one level down: a claim that is still "verified" because nobody re-checked
what "verified" was against.

**Evidence.** Sixth review, minor-1. `tests/test_critic_round5.py::test_a_cache_written_by_another_reader_is_not_trusted`
rewrites the cached `extractor` and asserts a re-extraction. Seen 1.

## The notes for a release are the commits since the last one

**Rule.** Anything that summarises "what changed in this release" must be
computed over a range with a known start. `git log -n N` is not a range; it is
however much history happens to fit in a constant.

**Why.** The release notes were `git log --pretty=format:'- %s' -n 40 HEAD`, so
each release described the previous releases' work plus a dozen `Release x.y.z`
subjects of its own — and `docs/maintenance.md` claimed the notes came "from the
commit range", which made the document the only false thing in the file. A
release note that lists everything is a release note that tells you nothing
about the release.

**Evidence.** Sixth review, minor-2; `test_the_release_notes_come_from_the_range_since_the_previous_tag`
asserts `git describe --tags` and the absence of `-n 40`. Seen 1.

## A step that cannot run for one input is a step that runs for none

**Rule.** A shell step in a workflow must be exercised in every state it can be
reached in, and the states that are hard to reach are the ones the step exists
for. If the only way to test it is to run it, move it out of YAML into a script
a test can call.

**Why.** The release-notes step began with `git describe --tags --abbrev=0
"${tag}^"`, which fails when the tag does not exist — and that is precisely the
`workflow_dispatch` path documented as the way to release by hand and the way to
recover a release that broke. Under `set -eo pipefail` the failure killed the
job after the build and the wheel smoke test had already run, so the expensive
half succeeded and the cheap half was unreachable. Nothing could catch it: the
step lived in YAML, and the test that claimed to cover it asserted on the YAML
text.

**Evidence.** Seventh review, major-1. `tools/release_notes.sh` now takes the
tag, falls back to `HEAD` when it is untagged, and
`tests/test_critic_round6.py::test_the_release_notes_script_survives_a_tag_that_does_not_exist`
runs it. Seen 1.

## A rebuild that returns the new head forgets the rest of the file

**Rule.** Any function that rebuilds one section of a document must return
`before + new + after`. Returning `before + new` is not "replacing a section";
it is truncating the file at that point.

**Why.** `update_links` returned `text[: section.start()] + block`. It looked
right in every test because the link block is the last thing in the CHANGELOG
those tests used — the tests did not put anything after it, so the missing tail
was invisible. This is the shape of bug that survives automated releases: the
first run that appends a section below the links silently deletes it, and the
commit is authored by a bot at 3am.

**Evidence.** Seventh review, minor-4.
`tests/test_critic_round6.py::test_rebuilding_the_links_keeps_what_follows_them`
appends a section and asserts it survives. Seen 1.

## A sort that has not been shown a pre-release is a sort that has not been tested

**Rule.** Ordering versions with `sort -t. -k1,1n` treats the patch field as a
number, so `1.0.0-rc1` ties with `1.0.0` and the tie is broken by a whole-line
comparison in which `-` (0x2D) sorts above `0` (0x30). Filter the shapes you do
not mean before you sort the ones you do.

**Why.** The nightly job picks the version to dogfood out of
`gh release list`. Every release so far was a plain `x.y.z`, so the tie never
happened; the first `1.0.0-rc1` would have been selected over `0.8.0` and the
nightly would have replayed a pre-release while reporting that it replayed the
latest release. `sort -V` does not fix this — it also orders `1.0.0-rc1` above
`0.8.0` — so the fix is a filter, not a better comparator.

**Evidence.** Seventh review, minor-5.
`tests/test_critic_round6.py::test_a_prerelease_never_wins_the_nightly` pipes
`v1.0.0-rc1` and `v0.8.0` through the workflow's own pipeline. Seen 1.

## A file that exists on PATH is not a program that runs

**Rule.** When a test invokes an external interpreter, make the test ask that
interpreter to run something before trusting it. `shutil.which("bash")` answers
"there is a file with this name"; it says nothing about whether the file can do
the job.

**Why.** Three tests ran `bash --noprofile --norc -eo pipefail tools/...` and
passed on this machine. On the Windows runners they failed with `assert 1 == 0`
and stdout full of UTF-16: `C:\Windows\System32\bash.exe` is the WSL stub,
which answers every command with "Windows Subsystem for Linux has no installed
distributions" and exits 1. The same class of mistake as assuming `python`
means the interpreter you meant, one layer further out: the tests were correct
about the script and wrong about the shell.

**Evidence.** The seventh review's fix introduced these tests, and the first
Windows run after pushing them went red - `test_the_release_notes_script_...`
and `test_a_prerelease_never_wins_the_nightly`, all three on windows-latest.
`_bash()` now probes each candidate with `echo ok` and skips with a named reason
when none of them can run. Seen 1.

## A script the index stores at 644 is a script that only runs where mode does not matter

**Rule.** If a shell script must be executed, call it through its interpreter
(`bash tools/x.sh`), not by path. The executable bit lives in the index; a
checkout that does not carry it cannot run the file, and the failure is
"Permission denied" on exactly the machine you cannot test locally.

**Why.** `tools/release_notes.sh` was created on Windows, where every file with
a shebang looks executable to the shell, and committed at mode 100644. The
release workflow called `tools/release_notes.sh "$tag"`, which works here and is
a hard failure on a Linux runner. Both facts - the mode and the invocation -
were invisible from the machine that wrote them.

**Evidence.** Seventh review, major-1, fixed in the same commit as the fallback;
`tests/test_critic_round6.py::test_the_script_is_invoked_through_an_interpreter`
asserts the workflow says `bash tools/release_notes.sh` and not the bare path.
Seen 1.

## A subset parser must bind what the real one binds, or say it cannot

**Rule.** When a fallback reader exists so that an old interpreter keeps working,
the test of that reader is not "it does not crash". It is "the same input binds
the same way". Any input the fallback silently skips is a project judged by
which interpreter happens to be installed.

**Why.** `_mini_toml` dropped quoted keys, and a quoted key is the only way to
write a BibTeX-style key with a colon in TOML - `"knuth:2019" = "papers/k.pdf"`.
`tomllib` binds it on 3.11+. So one manifest verified on 3.11 and reported
`source-missing` on 3.10, and 3.10 is in the CI matrix, so it would have arrived
as one red cell that reads like a platform flake. The previous review had fixed
exactly this for values and the fix was written against the reported input
rather than against the distinction, which is why the key branch beside it
survived.

**Evidence.** Eighth review, major-1: `tomllib.loads` binds the key, the
fallback returned `{}`, and the two disagreed on `check`. The distinguishing
case is now in `tests/test_critic_round6.py::test_a_quoted_key_binds_instead_of_vanishing`
and in the parser-agreement test's fixture. Seen 2.

## A gate that can be satisfied by doing nothing will be

**Rule.** If a test can pass by not running, something has to notice that it did
not run. `pytest.skip` on a machine where the prerequisite is guaranteed is not
portability; it is a green light for a suite that shrank.

**Why.** The shell tests skip when no bash answers a probe, which is a real
situation on a Windows runner and an impossible one on Linux or macOS. A skip
reports as a passing suite, so the tests could vanish on the runner and nothing
would say so - the only thing that would have caught it was the `N passed`
comparison, a side effect of a check written for a different reason. Portability
is the probe; the gate is what happens when the probe fails.

**Evidence.** Eighth review, minor-1; the lint job now fails on
`[0-9]+ skipped`, and `_bash()` calls `pytest.fail` off Windows
(`tests/test_critic_round7.py::test_no_non_windows_machine_may_skip_the_shell_tests`).
Seen 1.

## A number nobody measures is a number somebody guesses

**Rule.** Every quantity quoted in a commit message must be produced by a command
that ran, and if the message is checked mechanically for one number it will be
checked for the others. Writing down a number you did not just read is how a
message becomes fiction that is impossible to distinguish from staleness.

**Why.** The commit that added `--passed` - a check for a wrong test count -
claimed "47 files" for `ruff format --check`, which printed 46, twice in a row,
in the same paragraph that argued for measuring things. The wrongness is not the
point; the point is that the argument was made and then skipped for the number
one line over.

**Evidence.** Eighth review, minor-3. `tools/check_repo_rules.py` now compares
`N files` on a `ruff format` line, and
`tests/test_critic_round7.py::test_a_wrong_file_count_in_a_real_commit_fails_the_gate`
runs `main` end to end rather than asserting the flag exists. Seen 1.

## An acceptance list that names one platform's path is an acceptance list for one platform

**Rule.** When a document gives a command that differs by platform, write every
variant out. A path a reader has to translate is a step a reader skips.

**Why.** `AGENTS.md` said `.venv/bin/pip install -e .` while
`docs/code-standards.md` said `.venv/Scripts/pip install -e .` — two documents,
one of which is wrong on every Windows checkout, and the one that is wrong is
the one agents read first. The cost is not the failed command; it is that a
reader learns the acceptance list is approximate.

**Evidence.** Sixth review, minor-3. Both documents now carry both spellings.
Seen 1.

## A quote is not missing until you have looked everywhere a reader would look

**Rule.** Before reporting evidence as absent, check that the search covered the
shapes an author would call "on the page": text that runs over a fold, a form
feed, a column break. An absence is a claim about the world; make sure the world
you searched is the one they live in.

**Why.** `find_in_pages` searched one page at a time. A sentence that starts at
the bottom of page 6 and ends at the top of page 7 exists in the PDF, exists on
paper, and matched nothing — so the tool reported `quote-missing`, which is
`high`, which is the same severity as a citation that was invented. The failure
was not that a feature was absent; it was that the tool said something false
about the user's work, in the direction that costs them the most: it told them
their evidence had vanished. Worse, it was silent about why — the message said
"no passage in the source is close to this quote", which is technically true of
each page considered alone and completely misleading about the document.

**Evidence.** Found while building the backlog for the continuous-improvement
loop, before any user reported it. First probe was wrong: it passed a `PageText`
whose `folded` field was already falsy, so `__post_init__` never re-folded, and
half the "short quotes never match" conclusion it produced was an artefact of
that mistake — which is why the second probe compares a split sentence against
the same sentence whole. `tests/test_cross_page.py` (10 tests) pins the
mechanism, `tests/test_cross_page_real.py` (3 tests) pins the premise on a real
paper, and disabling the stitching turns five of them red. Seen 1.

## A diagnostic is the only place a tool is allowed to be reassuring

**Rule.** When a tool's ordinary output is a list of the user's supposed
mistakes, give them one command whose job is to say "the machine is fine, and
here is what I checked". Put a fix on every failed line, and do not cry wolf:
a check that fails on a healthy install is worse than no check at all, because
it teaches the user that the diagnostic is noise too.

**Why.** `citevouch`'s failure mode is not an error message. It is a clean run
that says every quote is missing because no PDF extractor is installed — and
nothing in that output distinguishes "your citations are wrong" from "I cannot
read PDFs". The honest response to six failures on a paper you know is correct
is to uninstall, and the tool gave no reason not to. `doctor` exists to be the
opposite of that output: it checks the six things that silently remove the
ability to see anything, prints one line per check, and attaches the command
that fixes each failure.

**Evidence.** Two things had to be built into the design rather than added
later: a read-only cache is reported as *not a failure* (correctness does not
depend on it, only speed), and a `pdftotext` that is absent while `pypdf` is
present is reported as *not needed*. Both are cases where the naive version
prints `FAILED` on a working install. `tests/test_doctor.py` (20 tests) pins a
broken machine, a healthy one, and — because documentation rot is the same
defect in a slower form — that the README's example contains every check the
tool actually performs. Seen 1.

## An advertised capability is code, not configuration

**Rule.** If `pyproject.toml` (or a README, or a table) names a feature, some
module has to implement it. When the two disagree, the metadata is wrong by
default: a user reading it has no way to tell a plan from a product.

**Why.** `xlsx = ["openpyxl>=3.1"]` sat in the extras table for several releases
while nothing under `src/` imported openpyxl. `pip install "citevouch[xlsx]"`
succeeded, changed nothing, and implied spreadsheet support in the same file that
declares every dependency the tool actually has. Nobody reported it because the
failure is invisible on both sides: the metadata looks populated and the install
looks fine.

**Evidence.** Found by reading `pyproject.toml` while writing the backlog, not by
using the tool — which is the tell: a defect nobody hits is one nobody will ever
report. `tests/test_extras.py` now parses the extras table and cross-checks each
requirement against the imports under `src/`; putting the old line back turns two
tests red. The parser deliberately does not use `tomllib`: it arrived in 3.11,
this package supports 3.10, and a guard that cannot be collected on a supported
interpreter is a guard with the same hole it was built to close. Seen 1.

## A file nobody runs is a file nobody has read

**Rule.** When a repository grows a second kind of executable artefact — YAML an
external runner consumes, a hook file, a shell script a workflow calls — give it
a test that executes it and reads back what it did. Reading the file and
asserting that it contains the right substrings is not a test of the file; it is
a test of your ability to scan text.

**Why.** `action.yml` is not imported by anything, so nothing in the suite would
notice if an input were declared and never forwarded, if a path with a space
split into three arguments, or if exit 2 were reported as a clean manuscript.
All three are invisible to a type checker and to a reviewer who reads the YAML
top to bottom, because the YAML is correct — the shell inside it is what is
wrong.

**Evidence.** `tests/test_action.py` runs each composite step's `run:` body with
a stub `citevouch` and a stub `python` on PATH, records their argument vectors,
and asserts on them. It found two real defects in the first draft, both
invisible when reading the file. The SARIF path was assembled from
`${{ runner.temp }}` copied into a hand-named environment variable, while
GitHub already exports `RUNNER_TEMP` to every step: the file landed wherever
`/tmp` happened to point, and the expression could not be exercised without a
runner. And both READMEs showed the three-line `pip install` form only, so a
shipped action nobody documents is a feature that exists for the maintainer
alone - the test that reads the docs found that, not a reader. Seen 1.

## A pinned version has one spelling, or the release tool cannot find it

**Rule.** When a machine rewrites version numbers in documents, it can only
rewrite the shapes it knows. Either spell every copy the way the tool matches,
or leave the number out - and make the disagreement a test failure rather than
something a reader has to notice.

**Why.** The release commit after the action landed bumped the `pip install`
pins from `v0.11.0` to `v0.12.0` and left the four new `uses:
lyear12/citevouch@v0.11.0` lines exactly where they were, because the tool
matches `citevouch@vX.Y.Z` and those lines do match. The rebase then produced a
README showing two different versions of the same tool three lines apart, which
is not a typo a reader can resolve: it reads as "the action is older than the
package", and both lines are copy-pasteable.

**Evidence.** `tests/test_readme_example.py::TestThePinsAgree` compares every pin
against `_version.py` and fails on any `vX.Y.Z` in either README that is not a
pin the release tool would rewrite. Both checks are red against the rebased
tree and green after the pins were moved by hand. The general lesson is the one
worth keeping: an automated rewrite and a hand-written example will drift, so
the drift has to be an assertion, not an observation.
## A dependency the tests import is a dependency the install step must install

**Rule.** When a test imports a package, that package belongs in the extras the
CI installs, and the install step belongs in the repository - not in a list of
names copied into each job. Name the extra, not its members.

**Why.** `tests/test_action.py` reads `action.yml` with `yaml`, and every job ran
`pip install -e . pytest ruff`. On this machine PyYAML was already present, so
the suite passed 385 times locally; on GitHub's runners every one of the ten
jobs failed collection with `ModuleNotFoundError: No module named 'yaml'` before
running a single test. A dependency used and not declared is the same defect as
a feature declared and not built, seen from the other side, and it is invisible
from the only machine the developer looks at.

**Evidence.** Run 41046307783 on `b5a07ad` is red in all ten jobs with the same
import error. The fix is three characters of promise (`PyYAML>=6.0` in the `dev`
extra) and one habit changed (`pip install -e ".[dev]"` in both workflows), and
two checks keep it fixed:
`tests/test_extras.py::test_every_run_only_dependency_is_used_by_a_command`
walks the extra and refuses a member that nothing imports or invokes, and
`::test_every_workflow_installs_the_dev_extra` refuses a workflow that installs
the package without it. Both are red against the old install line. Seen 1.

## A candidate list is only as good as the filter in front of it

**Rule.** When a command proposes something for a person to read, the ranking is
the easy half. The filter that decides what may be proposed at all is the part
that decides whether the output is usable, and it has to be built from outputs
of the real command on the real inputs, not from a description of it.

**Why.** `draft` first ranked every sentence on every page of a real paper by
shared terms, and the top results were a printed results table from page 13
(`A Grammar Report ---- ... All cxns: 40,688 ... 225`) and a figure caption
whose words were split across the column wrap. Both are text, both were
"relevant", both would have been pasted into a manuscript as evidence. The
ranking was not wrong: it did exactly what it was asked. The mistake was having
no answer to "may this be quoted at all", and that question cannot be answered
without looking at what a PDF page actually contains.

**Evidence.** Running the first draft of the command on
`demo/papers/2026_VanEecke-Beuls_CoNLL2026_large-scale-CxG.pdf` produced the
table and the caption. `_is_passage` (length window, digit density, letter
ratio, label:value runs) and `_reflow` (rejoin words split by the column wrap)
were written against that output, not against imagined bad input, and
`tests/test_draft.py::TestWhatMayBeQuoted` pins each one. The third case came
the same way: a section heading has no full stop, so splitting on punctuation
glued a title, its `====` rule and the sentence below it into one string, and
the filter then rejected the whole thing - `_sentences_of` now splits on
paragraph breaks first. Seen 1.

## A measurement of the working tree is a measurement of one machine

**Rule.** When a number from a local command is written into a commit message or
held to by a gate, the command has to read the set of inputs every clone has -
the tracked files - not whatever is lying in the directory the author happens to
be sitting in. A number whose inputs differ per machine is not a measurement; it
is a coincidence that usually repeats.

**Why.** `ruff format --check .` walks the working tree. On the machine writing a
change that is `N files`; in CI's checkout of the same commit it is `N-1`,
because an untracked draft exists in the first and not the second. Three
releases in a row quoted a file count that was only true locally, and each time
the gate caught the discrepancy after the commit was already pushed - the check
worked, which is exactly why repeating it three times was wasteful. The fix is
not a better guess but a narrower input: `git ls-files` is the same set on every
clone, so the count in a message is one the reader can reproduce.

**Evidence.** `tools/format_check.sh` measures the tracked files and the lint
job runs it in both places (`ruff check .` and `sh tools/format_check.sh`), so
the local number and CI's number are the same command over the same input.
`tests/test_format_check.py::test_an_untracked_file_does_not_change_the_count`
writes a draft into a two-file repository and asserts the count stays at two;
`::test_a_checkout_with_nothing_in_it_is_not_a_clean_checkout` pins the other
half - no files is exit 2, not "0 files already formatted", because an empty
checkout read as clean is the same mistake as reading zero passing tests out of
a suppressed summary line. Seen 3. Counting the two earlier wrong numbers
(`N passed` 317 vs 273, `N files` 47 vs 46).

## A process that inherits nothing starts as a different machine

**Rule.** `subprocess.run(..., env=...)` replaces the environment. Any dict
handed to `env=` in this repository starts from `dict(os.environ)` and only
adds to it, and `tests/test_child_env.py` refuses the literal form so the rule
does not depend on remembering it.

**Why.** The defect is silent where it is written and loud where it is not. On
Linux the child starts anyway and the test passes; on Windows the interpreter
aborts in `_Py_HashRandomization_Init` before `main()` runs, so the failure
arrives as `assert 1 == 0` on a job in a matrix cell the author was not
thinking about, carrying no mention of the environment at all. The same three
lines were written twice - once in `tests/test_critic_round2.py`, found by a red
`3.10` job, and again in `tests/test_precommit.py`, found the same way months of
commits later. A rule written only in a lesson is a rule the next author has not
read; the guard is what makes it hold.

**Evidence.** CI run 41049992854: nine of ten jobs green, `test
(windows-latest, 3.10)` red, `Fatal Python error: _Py_HashRandomization_Init:
failed to get random numbers to initialize Python`. Every affected call site now
builds its environment with `_env(...)` or `dict(os.environ)`;
`tests/test_child_env.py::test_the_detector_recognises_both_shapes` pins both
shapes so a guard that matches nothing cannot look like a clean repository.
Seen 2.

## A check that stays green when you disable the feature is checking the wrong thing

**Rule.** A test for a step that *transforms* its input — a converter, a
normalizer, a rewriter — must assert something only that step can produce. Do
the reverse check before believing the test: disable the step, watch it go red,
put it back. A test that was never seen red is a test that was never seen doing
anything.

**Why.** The fallback makes the assertion true by a second route. `draft` grew a
LaTeX reader, but `draft` already matched `\cite{key}` directly — it had to,
or a stray citation in a Markdown file would be invisible. So "the citation is
found" was true with the converter switched off, and so was "the proposal file
has a claim block". Two versions of that test passed on a `if False:`. The
converter's real job is not finding keys; it is removing the things that would
otherwise land in the `claim:` line — `\documentclass`, `\section`, `~`,
`\citep{...}` — so those absences, and the count of proposals, are what the
test has to assert. `Seen` is not incremented for this one: it is the first time
the defect is written down, and the reverse check is now part of the acceptance
list rather than a habit of the author.

**Evidence.** `tests/test_latex_end_to_end.py`, first two versions: with
`if latex_module.looks_like_latex(manuscript):` replaced by `if False:`, both
reported `5 passed`. The same file now fails on that substitution with
`assert 'This is large for the task at hand.' in [...]`, where the statement had
become `This is large for the task at hand~.` and the document preamble was
sitting inside the `claim:` line. Seen 1.

## A figure of your own output is a claim, and claims get stale

**Rule.** An image in a README that shows program output is a statement about
the program, so something has to compare it. Generate the figure from a real run
and write the same text beside it as a plain file; a test reruns the program and
compares. A hand-made mock-up is not allowed to sit where a screenshot should be,
and a screenshot with no comparison is a mock-up that was true once.

**Why.** A PNG cannot be diffed, so nothing in a normal test suite notices when
it stops being accurate. The failure is worse than a missing figure: a reader
trusts a picture more than prose, runs the command, gets different output, and
concludes the tool is broken rather than the picture is old. The second half of
the rule is the sidecar - the picture and the text have to come from the same
run, or someone will edit whichever is convenient and the other one will keep
lying.

**Evidence.** `docs/img/verify.png` is rendered from `citevouch verify
manuscript.md` inside `demo/`; `docs/img/verify.txt` holds the identical lines;
`tests/test_figures.py` runs the demo again and asserts they match. The first
version of `tools/make_figures.py` passed `env={"PYTHONPATH": ...}`, which wiped
`PATH`, lost `pdftotext`, and drew a picture of a broken install - caught only
because the picture was read before it was committed. Seen 1.

## The edge of a picture is where you stop checking

**Rule.** Crop a figure to something with a defensible boundary - whole text
lines, not whole pixels, and not "the block that contains the thing I want" -
and assert the boundary held. A fixed pixel height, or a bbox that looked right
once, will slice a line in half and nobody will notice, because the middle of an
image is what you look at.

**Why.** Three crops of the same page were wrong in three different ways before
one was right: a fixed height cut the sentence in half; a two-column page's first
matching block left the right-hand column's paragraph chopped mid-word; snapping
to overlapping bboxes pulled in a line whose box was tall for its own reasons (a
footnote superscript) and sliced it at the top edge. Each looked plausible at a
glance. The fix was to stop guessing geometry and snap to the page's own line
boxes, then assert the resulting height is small enough to be an excerpt - which
is the property the figure needs, not the number that happened to come out.

**Evidence.** `tools/make_figures.py::page_excerpt`, and
`tests/test_figures.py::test_the_page_figure_is_an_excerpt_not_a_whole_page`,
which fails if the crop grows back into a whole-page screenshot. Seen 1.

---

## A file that records a command records the argument, not the intention

**Rule.** When something is written into a committed artefact, store it in the
form the artefact needs to be read from anywhere - relative to a declared root,
with a separator that is the same on every platform - and never the string the
user happened to type. If two ways of naming the same file produce two different
files, the tool has a bug even when both outputs are correct.

**Why.** `scan` stored source paths through `_ledger_path(root, path)` from the
first version, so a ledger survived a clone onto Linux. It stored the
*manuscript* path as `str(options.manuscript)` - whatever the user typed. So
`scan demo/manuscript.md --root demo` wrote `"manuscript": "demo/manuscript.md"`
and `cd demo && scan manuscript.md` wrote `"manuscript": "manuscript.md"`. Both
are true sentences about the same project; only one of them can be in the file.
The consequence was not cosmetic: `demo/citevouch.lock.json` could only be
regenerated from one working directory, which is why it sat at tool_version
0.5.0 through eleven releases without anyone being able to ask whether it was
still what this version writes. The half that was fixed in round 4 (sources) and
the half that was not (the manuscript) looked identical in review, because the
fix had been reported as "the ledger records portable paths" rather than
"every path in the ledger goes through one function".

**Evidence.** `src/citevouch/scan.py`, the `manuscript=` field of `Ledger`;
`tests/test_scan_verify.py::test_the_ledger_names_the_manuscript_the_same_way_from_any_directory`
and `tests/test_demo_fixture.py::test_the_committed_ledger_is_one_this_version_would_write`,
which re-scans `demo/` and requires the committed lockfile to match field for
field except `generated_at` and `tool_version`. Seen 2. The first was
`test_the_ledger_records_a_portable_path`, and it only ever checked sources.

---

## A tag that fails its own gate has already been spent

**Rule.** Everything a release step can change has to be rewritten by the same
step, found by a rule rather than by a list. When a release fails after the tag
is pushed, the tag is gone: repair the tree, then either move the tag by hand or
burn the number - do not "re-run the workflow and hope", because no workflow can
un-publish a tag.

**Why.** `tools/next_version.py` took `--readme PATH`, repeatable, and
`auto-release.yml` passed the two files it knew about. Then `docs/launch/`
arrived: two files quoting the install line, both carrying `citevouch@v0.16.0`.
The bump rewrote the READMEs and not them, the release job ran the suite on the
*tag*, the new `tests/test_launch.py` pin guard failed, and the run died after
the tag had been created - `origin/main` moved to `Release 0.16.1` with
`_version.py` at 0.16.1, while `gh release list` still showed 0.16.0 as latest
and no assets existed for the number. The guard was right; the plumber was
wrong, and the plumbing was a hand-kept list of three names.

**Evidence.** `tools/next_version.py`'s `PIN_GLOBS` and `pin_documents()`;
`--pins-root .` in `auto-release.yml` with `docs` in its `git add`;
`tests/test_next_version.py::test_the_pinned_documents_are_the_ones_that_actually_carry_pins`,
which walks the repository for markdown that carries a pin and fails if
`PIN_GLOBS` does not cover it (verified by dropping a stray pin into a new
`stray.md`, which turned it red). The tag `v0.16.1` was repaired by moving the
release commit onto a tree whose pins already said 0.16.1 and force-updating the
tag, because nothing had been published under it. Seen 1.

## The archive claims to ship a suite, so it ships what the suite reads

**Rule.** If `MANIFEST.in` grants `tests/`, it also grants every file those tests
open - by rule, not by name. `graft tests` is a promise about inputs, not just
about test files.

**Why.** `citevouch-0.16.1.tar.gz` was published with `graft tests` and without
`tools/`, `.pre-commit-hooks.yaml`, `action.yml`, `.github/`, `docs/img/` and
`demo/papers/`. Unpacking the released archive and running its own suite gave
**56 failures and 3 errors** - 27 after the first repair, 2 after the second.
The demo was worst: without its papers `demo/manuscript.md` reports five
`source-missing` findings, every claim red, for a reason that is about the
archive rather than the manuscript. Nobody notices this from the repository,
because the repository has every file. The release workflow smoked-tested the
wheel and never looked at the tarball.

**Evidence.** `tests/test_sdist_contents.py` walks the suite with `ast` -
including paths built as `ROOT / "tools" / "x.py"`, which is how tests name most
files and which a scan for slashes in string constants misses entirely (it found
14 paths instead of 44). Verified by restoring the old `MANIFEST.in` and
rebuilding: three tests go red. `test.yml`'s `sdist` job unpacks the published
archive and requires exactly two skips. Seen 1.

## A check that can only be satisfied by writing less is a check that costs you evidence

**Rule.** When a gate compares a message against a measurement, the message
may contain more than one measurement. Accept any number this run measured;
reject any number it did not.

**Why.** The commit that shipped the sdist fix measured two suites - the
repository's (508 passed) and the one inside the archive it had just built
(501 passed, 2 skipped) - because both numbers were the point. The gate read
every `<n> passed` and required all of them to equal the first argument, so the
second number was reported as a lie. The honest fixes were to delete a
measurement or to weaken the gate. Both are worse than teaching the gate that a
commit can measure twice: a message with fewer numbers is a message with less
evidence, and the whole reason `Run:` exists is that the next agent cannot run
the old tree.

**Evidence.** `tools/check_repo_rules.py`'s `--passed` is now `action="append"`,
and `passed_count_mismatches(notes, actual, others=())` accepts any member of
`{actual, *others}`. `tests/test_check_repo_rules.py` has three cases: two true
numbers pass, one unmeasured number fails, one number still has to be right.
Seen 1.

## A job that forbids skips is the last job that may skip

**Rule.** When one job in a workflow is the place that refuses a skip, that
job must build everything an honest skip would need before it runs the suite.

**Why.** The `sdist` test skips when there is no archive to read, which is
right everywhere and wrong in the lint job, whose next step fails on any
`skipped` line at all. On its first run that job failed with four skips - two
because there was no `dist/`, two more because the archive test itself had
just been taught to skip. The rule was not too strict, it was placed in a job
that had not been given the inputs to satisfy it.

**Evidence.** `test.yml`: the `repository rules` step now runs `python -m build
--sdist --no-isolation` before pytest and fails loudly if the build does. Seen 1.

## `--no-isolation` builds fail where `pip install -e .` succeeded

**Rule.** If a job runs `python -m build --no-isolation`, it must name the build
backend in its own install step. An editable install says nothing about what
is importable afterwards.

**Why.** `pip install -e .` builds inside an isolated environment that is
thrown away, so it proves the backend can be fetched, not that it is present.
The `sdist` job failed its very first run with `BackendUnavailable: Cannot import` followed by
`No module named setuptools`, right after a green editable install in the
step above that read like a green light.

**Evidence.** Both jobs that build now install `build setuptools` by name;
`Cannot import 'setuptools.build_meta'` is in the log of run 41063081151. Seen 1.

## A guard that slices the file at the wrong place checks nothing

**Rule.** When a test reads a configuration file as text and asserts something
about one section of it, assert that the section it found is not empty, and
count how many sections it checked. Then break the thing it guards and watch
it go red.

**Why.** A new test sliced each job out of `test.yml` with
`workflow.find` with a newline and two spaces as the needle. Every job's own body is indented four spaces,
so the first newline-plus-two-spaces is three characters into the job: the
block came back empty, and an empty block satisfies every `for line in
block` assertion. It reported green while the file still said exactly what the
fix was meant to remove. The reverse check caught it - that is what reverse
checks are for, and it is why they belong in the change rather than in a later
review.

**Evidence.** `tests/test_critic_round7.py::_job_block` now returns 4,806 and
2,783 characters for the two jobs it is asked about, asserts a
`--no-isolation` build is inside each, and the caller asserts it checked two
jobs. Removing `setuptools` from the install line turns it red with
`lint: runs a --no-isolation build but never installs setuptools`. Seen 1.

## An input nobody reads is worse than a missing input

**Rule.** Every declared input has to be read by a step whose body can honour it.
In a composite action that means the `${{ inputs.x }}` expression appears in a
`with:` or `run:` that acts on it - not merely in an `env:` block. Then break the
wiring and watch the guard go red, because "the input is mentioned somewhere" is
the assertion that let this ship.

**Why.** `action.yml` declared `python-version`, piped it into the install step's
`environment`, and no shell line ever read it. A caller writing
`with: python-version: "3.10"` got a 3.12 runner and no warning: the option was
advertised, forwarded, and inert. The test that should have caught it had the
comment "`python-version` is consumed by the install step, not the run step" and
then discarded the name from the expected set - a sentence describing an
implementation that did not exist, protecting the one input that was broken.

**Evidence.** The fix adds a `uses: actions/setup-python@v5` step reading
`${{ inputs.python-version }}`. Three guards now cover the class:
`test_the_python_version_input_chooses_the_interpreter` (the expression must
reach a setup-python step's `with:`), `test_every_input_is_read_by_some_step`
(every declared input appears as `inputs.<name>` in some step's `with`/`env`/`run`),
and `test_a_shell_step_is_never_handed_an_env_var_it_ignores` (every `env:` key is
referenced in its own step's body, allowing `${KEY:-default}` and `$KEY`).
Restoring the old `action.yml` turns the first and third red; the old test stayed
green. Seen 1.

## A guard that names its own files protects only the files it named

**Rule.** When a guard scans a set of paths, the set is part of the guard. If it
walks one directory because that is where the mistake was first seen, it will
miss the second place the same mistake is written — and it will report success
the whole time.

**Why.** A green guard is read as "this defect is not here." That reading costs
nothing to produce and is expensive to disprove, because the next person has to
suspect the guard itself before they suspect the code.

**Evidence.** `tests/test_child_env.py` exists because
`subprocess.run(..., env={...})` replaces the environment, removes `SYSTEMROOT`
on Windows, and aborts CPython before it can say what happened. It was written
after the same defect appeared twice in `tests/`, so it scanned `tests/`. Then
`tools/make_figures.py` — which renders the README figures by running the demo —
did it again: the first version handed `env={"PYTHONPATH": ...}` to the demo, lost
`PATH`, lost `pdftotext`, and drew a picture of a broken installation. The guard
was green the entire time, because `tools/` was not on its list. Seen 1.

## Two paths that are "relative to the root" have to name the same root

**Rule.** When one tool takes a document path and a root path, and another layer
of that tool documents both as "relative to the repository root", the two must
resolve against the same directory. A layer that resolves one against the root
and forwards the other unchanged is correct exactly when the root is the
repository root, which is the one layout that never fails in testing.

**Why.** The disagreement is invisible in the default case, so the authors of
both layers test with the default and both see green. It surfaces only for the
user who puts the manuscript in a subdirectory — the layout the option exists
to serve.

**Evidence.** `action.yml` documents `ledger` as "relative to the repository
root"; `src/citevouch/cli.py:_ledger_path` reads it against `--root`. With
`root: paper` and the ledger committed at the top of the repository, the action
ran `check --root paper --ledger citevouch.lock.json`, the CLI looked in
`paper/`, and the job failed with `no ledger at paper/citevouch.lock.json` — a
message about a file that was in the repository, telling the reader to run
`citevouch scan`, which would have written it to the wrong place too. The action
now makes the ledger absolute against the workspace. The test that would have
caught it is not an argument assertion: it runs the real CLI over the documented
layout. Seen 1.

## A promise in the changelog is a promise the suite has to be able to break

**Rule.** When the changelog states that a behaviour is guaranteed — "a ledger
pointing at either page counts as verified", "numbers on either half count as
present" — there must be a test that fails when that behaviour is removed. A
sentence in a document is not a commitment; a test that goes red is.

**Why.** The two are written at different times by different states of mind. The
changelog entry is written when the feature works and the author is pleased; the
test is written when the author is tired and the suite is green. The gap between
them is exactly the size of the disagreement a later reader will hit, and it is
invisible from both ends, because both look finished.

**Evidence.** The cross-page change shipped with a changelog paragraph naming
two halves — a ledger pointing at either page is not `quote-moved`, and a number
carried by either half is not `number-absent-in-quote`. Neither half had a test.
Reverting either rule left **518 tests green**. The second one is not a missing
nicety: it reports a `high` finding, the same severity as a fabricated citation,
about a number the author can read on the next page. A regression there would
have shipped silently and the changelog would have said it could not happen.
Seen 1.

## Advice that fails when followed is worse than silence

**Rule.** When a diagnostic prints a command for the reader to run, that command
must parse and do what the sentence says it does. Test it by parsing the string
out of the message and running it through the real argument parser, not by
matching a substring.

**Why.** The reader who pastes it and gets `error: unrecognized arguments` has
no way to tell a typo in the advice from a broken tool, and the tool is the one
asking to be trusted about citations. The cost of the check is four lines; the
cost of getting it wrong is that every other message becomes suspect.

**Evidence.** `citevouch doctor`'s "the manuscript is not there" fix said
`citevouch doctor paper/manuscript.md`. The command has no positional argument —
it takes `--manuscript` — so following the advice exits 2. `tests/test_doctor.py`
now extracts the backticked command with `re.search(r"`(citevouch [^`]+)`", ...)`
and calls `build_parser().parse_args(...)` on it, and asserts the parsed
`manuscript` is the path the message promised. Seen 1.

## The confident summary of nothing is the worst output a checker can produce

**Rule.** Before a command reports a verdict, it must establish that it read
something. "0 claims, 0 verified, 0 missing" is only good news when the input
was a format the command understands; when it was not, the summary is a verdict
about nothing and it must be refused, not printed.

**Why.** A checker's whole value is that green means checked. Every other
failure mode of this tool - a missing PDF, a wrong page, a fabricated quote -
produces a visible complaint that a human eventually reads. This one produces
the shape of success, and the reader has no signal at all that nothing was
looked at. It is also the easiest false green to reach by accident, because the
neighbouring command accepts the format: `citevouch draft paper.tex` works, so
`citevouch check paper.tex` is the next thing anyone tries.

**Evidence.** `check paper.tex --root .` exited 0 and printed
`0 claims — 0 verified, 0 moved, 0 missing` with `worst severity: info`. The
`.tex` file held a citation and a real number; none of it was out of scope, it
was simply a format `scan` does not read. `src/citevouch/scan.py` now raises
`UsageError` when `looks_like_latex(manuscript_path)`, and the message names
`citevouch draft`, because refusing without a next step is a different way of
wasting the reader's afternoon. Seen 1.

## A hand-written marker is a format, and a format needs a parser that fails closed

**Rule.** When a human writes a machine-read marker, spell out every shape it
takes and make an unrecognised shape an error. Do not let "the pattern did not
match" quietly mean "this item does not have that property".

**Why.** The two readings are indistinguishable at the point of use and produce
opposite decisions: a marker that cannot be parsed is an item that needs
attention, while a missing marker is an item that is fine. Silently reading the
first as the second turns the enforcing gate into the thing it was written to
prevent, and nothing anywhere says so.

**Evidence.** `tools/check_repo_rules.py` counted lessons with
`re.compile(r"Seen (\d+)\.")`. Two of the 72 lessons are written
`Seen 2 - the first was ...`, without the period, and were therefore counted as
never seen. Widening the pattern to `Seen (\d+)(?:\.|\s|$)` and adding a
fail-closed "says Seen but names no number" branch immediately turned the gate
red: a lesson already at `Seen 3` had never been promoted. The hole was hiding a
real debt for as long as it existed. Seen 1.

## A green summary of nothing is the worst thing a checker can print

**Rule.** When the input makes the check impossible to run, say that. Never let
the absence of things to check produce the same output as everything passing.
And when you close that hole for one way of reaching it, grep for the other
ways: a file extension is a shape, not the class.

**Why.** Every other finding in this tool describes something that was looked at
and failed. "Nothing was looked at" has the same summary line - `0 claims - 0
verified, 0 moved, 0 missing`, `worst severity: info` - because the summary
counts claims, and zero is a number the reader is used to seeing from a clean
run. The two outputs are identical and the exit codes were identical, so a CI
job went green over a document no claim in which had ever been read.

**Evidence.** v0.17.1 refused `.tex` manuscripts for exactly this reason,
quoting "Scanning the .tex would record zero claims and report a clean run for a
manuscript nothing checked" - and the fix tested the suffix. A Markdown file
with no claim blocks did the same thing two releases later, and so did a
Markdown file whose blocks were written with four backticks or a capitalised
`Claim`; the second and third are worse, because the author believes they wrote
a claim block. `tests/test_scan_verify.py` had the bug written down as an
expectation (`assert findings == []` over a prose-only manuscript), which is how
it survived review: a test that asserts the wrong behaviour is a lock, not a
detector. Seen 1.

## An absolute path in the tests hides which base the relative ones use

**Rule.** When a command takes a path, test it with a relative path and from a
directory that is not the project root. A test suite whose invocations are all
absolute is a suite that has never asked the question "relative to what?".

**Why.** An absolute path is the one spelling that makes the question
unaskable. `draft` resolved `--output` against the process working directory
while it resolved the manuscript, the bibliography, the sources and the ledger
against `--root` - two path rules inside one command - and every test in
`tests/test_draft.py` passed `-o str(root / "claims.md")`. The suite was
thorough: it checked that the output is a manuscript the verifier accepts, that
it is written with line feeds, that an existing output is not clobbered without
`--force`, that the manuscript is never modified. All of those are true and all
of them are true for absolute paths only. The same absolute-path habit also hid
that `-o` could name the manuscript itself, which with `--force` destroyed it.

**Evidence.** `draft paper.md --root proj -o claims.md` run from another
directory wrote `claims.md` into that directory and nothing under `proj`; run
with an unrelated `claims.md` already sitting there, it wrote into that file
instead. Both exited 0. `draft manuscript.md --root . -o manuscript.md
--force` replaced the paper with nine lines of comment and exited 0. The three
guards and their four tests are in
`tests/test_draft.py::TestTheOutputPathCannotCostYouThePaper`, and each of the
three reverts was checked to turn a test red. Seen 1.

## An exit code that means two things means nothing

**Rule.** A crash and a verdict must never share an exit code. If a command can
fail because its arguments were wrong, that failure has to leave through the
same door as every other usage error - not as an exception that happens to exit
1 like a failing check does.

**Why.** This tool's whole contract is a small set of exit codes, and 1 is the
most load-bearing of them: findings reached the `--fail-on` threshold. A
traceback also exits 1. So `citevouch scan --ledger some/directory` looked to a
caller exactly like `citevouch scan` over a manuscript whose quotes were wrong,
and the only difference was a stack trace on stderr that a CI log buries under
two hundred lines. The read path had already learned this - `_read_ledger`
catches `OSError` and raises a usage error - and the write path had not, which
is the same defect shape as "the guard lists tests/ and the next bug lands in
tools/": the rule was applied where the bug was first seen, not to the class it
belongs to.

**Evidence.** `scan --ledger <a directory>` raised
`PermissionError: [WinError 5] ... 'dir.tmp' -> 'dir'` from `os.replace`, and
`--ledger <a file>/x.json` raised `FileExistsError: [WinError 183] ... 's.txt'`
from `mkdir`; both exited 1. `verify --ledger <a directory>` exited 2 over the
same path, because the read side was already guarded - the two halves of one
command disagreed about what a bad path means. Seen 1.

## A message about a path has to be true about that path

**Rule.** When a finding or an error names a path, the sentence has to describe
the condition that was actually tested. If the judgement is `is_file()`, the
sentence may not say `exists()`; it has to say which of the two failed.

**Why.** Both sentences send the reader somewhere, and they send them to
different places. "Does not exist" sends them to look for a missing download, a
wrong directory, a typo. "Is a directory" sends them to look at what they
passed. When the words and the test disagree, the reader does the first when the
second is true, finds the file sitting exactly where they left it, and concludes
the tool is broken. That is a worse outcome than a vaguer message, because it
spends the reader's trust on a defect that is real.

**Evidence.** `scan` and `draft` both reported `bib file adir does not exist`
for a directory, because the test was `is_file()` and the string was written
from memory. `sources.py` had already been fixed for exactly this -
`what = "is a directory, not a file" if path.is_dir() else "does not exist"` -
and the fix did not travel to the two places that reused the pattern. The same
review found `--source <a directory>` being dropped from the source map in
silence, which produces the same wasted search two steps later: the claim
reports `source-missing` for a file that is present. Seen 1.

## A summary of what was printed is not a summary of what happened

**Rule.** When a flag hides output, the summary keeps describing the whole
run.  If hiding took away the reason the run failed, say that in the output.

**Why.** `check --fail-on low --quiet` printed

    citevouch: 1 claim — 1 verified, 0 moved, 0 missing
    worst severity: info

and exited 1.  The reader of that CI log has one line saying nothing is wrong
and one exit code saying the opposite, and no way to find out which.  The
filter was correct and the exit code was correct; only the sentence that
explains them was computed over the wrong list.

**Evidence.** `_render` filtered for `--quiet` before calling
`render_text`, which computes `worst severity` from its argument.  Unit tests
of the renderer could not catch this because the filter lived in the caller;
the end-to-end test added with this fix is the one that fails when the filter
moves back.  Seen 1.

## Escaping one character is not escaping the string

**Rule.** When text is made safe for a markup context, every character the
markup treats specially has to be handled in one pass, and any length limit
has to be applied before escaping, not after.

**Why.** `_cell` escaped the pipe and stopped, so a quote that already held a
backslash before a pipe turned into an escaped backslash followed by a live
column break — a table one column wider than its header, which silently
misaligns every row after it.  Then the same cell was escaped first and
truncated second, so the cut could fall between the backslash and the pipe,
leaving a lone backslash at the end of the cell where it escaped the
ellipsis instead of the pipe.  Both are the same mistake: treating the
escape as a substitution instead of as a transformation of the whole string.

**Evidence.** `citevouch report` on a ledger whose quote held an escaped pipe
emitted a six-separator row in a four-column table; a quote with the pipe at
cell offset 78 emitted a cell ending in a bare backslash.  Three mutations
are red: escaping only the pipe, escaping before cutting, and not cutting.
Seen 1.

## A mark you cannot see is still the first character

**Rule.** Read outside text through one function that normalises the encoding boundary, and make that function the only thing that touches a file.  A byte-order mark is not whitespace and not metadata: after decoding it is a real character at offset 0, and any reader that treats its first line as syntax fails on it.

**Why.** The failure never looks like an encoding problem.  Each reader reports the consequence in the language of its own domain — an unclosed fence, an unparsed header, a key that does not exist — and every one of those sentences sends the author to a place the problem is not.  A reader who is told their claim block never closes will check the block, find it closed, and conclude the tool is broken.

**Evidence.** Windows Notepad, Excel's CSV export and PowerShell's `>` all write a UTF-8 BOM by default.  Four readers were affected: `scan` reported `claim-block-unclosed` and `no-claim-blocks` for a well-formed manuscript; `parse_bib` reported `bib-entry-header-unparsed` and then `bib-key-missing` (high) for a key that was in the file; `_read_ledger` refused the repository's own recorded evidence with `Unexpected UTF-8 BOM`; `_load_cache` treated a marked cache entry as a miss.  The fix is one function, `textnorm.read_text`, and four call sites routed through it.  Three mutations are red: not stripping the mark, and re-introducing a raw read at each of two call sites.  Seen 1.

## A guard that stops matching its subject reports nothing to fix

**Rule.** When a guard recognises its subject by name - a command, a file extension, a marker word - changing that name elsewhere in the repository is changing the guard.  Commit the two together, and leave a test that fails when the name stops being recognised.

**Why.** The guard's silence reads as a pass.  Nothing distinguishes "the number is right" from "I did not find a number", so a stale name turns the check into a function that always returns `[]` while appearing in every gate output as a line that ran.  It is strictly worse than no check at all: an absent check is visibly absent.

**Evidence.** `_FORMATTED_LINE = re.compile(r"ruff format")` was written when that was the command.  The command became `sh tools/format_check.sh`; the pattern did not, and `formatted_count_mismatches` returned `[]` for a correct count, a wrong count, and no count.  A commit in the same session therefore claimed 73 formatted files where `sh tools/format_check.sh` reported 74, and `check_repo_rules --formatted 74` passed it.  The same shape is in `_PASSED` (it reads the words "N passed") and in `_SEEN_WORD`, which is why both carry a "only this shape is read" note.  Two tests are red when the pattern is narrowed back to `ruff format`.  Seen 1.

## A quiet result is not the same result on every input

**Rule.** When a check can come back empty, decide what empty means before the input arrives. A parser that returns no results has to distinguish "there was nothing to read" from "I could not read what was there", and the second one must be louder than any per-item failure it suppresses.

**Why.** Empty propagates as success. Every consumer of the empty result has its own reason to stay quiet - a loop over zero items reports nothing, a lookup table with no rows finds no misses, a summary prints "0 problems" - so the silence compounds downstream, and it compounds *most* on the worst input. The reader sees a green run and cannot tell whether the tool checked everything and found nothing wrong, or checked nothing at all.

**Evidence.** A bibliography saved as UTF-16 (Notepad's "Unicode", Excel's export) read as UTF-8 became one replacement character and a NUL between every letter. `parse_bib` found no entries, `verify` skips `bib-key-missing` entirely when the ledger recorded no entries, and the run finished with exit 0 and a single *medium* finding about an unparsed header - quieter than the same project with one missing key, which is high. Two fixes, because the input was wrong in two separate ways: `read_text` decodes by the byte-order mark and falls back to the NUL pattern, and `parse_bib` reports `bib-unreadable` (high) when a file with content in it yields nothing. Three mutations are red. Seen 1.

## A reader that cannot fail is a reader whose silence means nothing

**Rule.** When two different files produce the same successful return value, the caller cannot tell them apart, and it will report the wrong one. Give the reader a way to say "I succeeded and there was nothing there", and make every consumer of that value handle it — the extraction path and the cache path are the same decision, not two.

**Why.** An empty result travels. It passes through every layer that loops over it, and each layer has its own reason to stay quiet: the matcher searches nothing and reports "not found", the summary counts zero, the report prints green. The silence compounds towards the worst input, and the message that surfaces is in the vocabulary of the *last* layer rather than the first — the author is told their quote is not in the file, when the fact is that the file has no text.

**Evidence.** `pypdf` and `pdftotext` both return successfully for an image-only PDF: `[(page.extract_text() or "") for page in reader.pages]` is a list of empty strings, which is not `None`, so `extract_pages` returned `(pages, None)` and `verify` went on to search. A three-page scan therefore read `[high] quote-missing ... quote not found in scan.pdf`, with a fix line telling the author to install pypdf — which was installed. The new `source-no-text` names the file, the page count and OCR. The cache matters as much as the extraction: it stores pages, not verdicts, so had only the extraction path judged, run 1 would diagnose the scan and runs 2..n would read the same empty pages from the cache and go back to blaming the quotes. The probe that found it (write a PDF with drawing commands only, then `check`) is three lines and none of the 619 existing tests did it, because every fixture PDF was made by printing text. Three mutations are red: extraction silent, cache silent, and an emptiness test that only asks whether the list is non-empty. Seen 1.

## A normaliser that folds one kind of digit folds only the ones it was shown

**Rule.** When two texts are compared after normalisation, every spelling of a character the domain can produce must normalise to the same thing. Enumerate the spellings from the domain, not from the test fixture that happened to be at hand — and if a standard library function claims to normalise, read what it actually covers before trusting it with a whole category.

**Why.** The failure is not an exception; it is a *tier change*. The quote misses `exact`, misses `squashed` because one character differs, and falls into the tier that exists to say "the words match but the digits do not". So the tool kept working, kept finding the page, kept naming the right passage — and reported the one thing it must never report by accident: that a number printed on the page is not on the page. A crash would have been cheaper.

**Evidence.** An author reading a paper printed in Cairo types `40688`; the PDF's extraction says `٤٠٦٨٨`. `unicodedata.normalize("NFKC", …)` folds the full-width `４０６８８` to `40688` and leaves Arabic-Indic, Persian and Devanagari digits untouched, because they are ordinary characters rather than compatibility variants — so `normalize` was correct for the case anyone had tried and wrong for three scripts nobody had. `find_in_pages` returned `tier=numbers` for `٤٠٦٨٨` against `40688` and `exact` the other way, and `verify` then printed `number-absent-in-quote`: "the words match page 1 but the numbers do not". `_ascii_digits` now folds every `unicodedata.decimal` character, which needs no table and picks up scripts added later; `canonical_number` also accepts U+066C/U+066B/U+066A, the Arabic thousands/decimal/percent signs, so `40٬688` and `40,688` agree. Both mutations are red: drop the call from `normalize` and the matcher test fails; drop the folding from `canonical_number` and the comparison test fails. The case that must keep failing still does: `40699` against `40688` stays in the numbers tier. Seen 1.

## A byte pattern is a fact about an alphabet, not about an encoding

**Rule.** When deciding how to decode a file, judge the *decoded* text, not the bytes. A pattern that
holds for one script holds for the alphabet it grew up in; ask "what does a wrong reading look like"
and count that, because it looks the same in every script.

**Why.** The NUL heuristic is a good test that is wrong for most of the world. It asks whether one
side of every 16-bit pair is a zero byte, which is true of Latin text and false of every script whose
characters have a low byte order — a Han character's high byte is `0x4E`-`0x9F`, a Cyrillic one is
`0x04`. So a document written entirely in Chinese or Russian contains no NULs at all and the detector
never fires, which is the worst shape a detector can have: it is right often enough to look correct,
and its failures cluster on one kind of user.

**Evidence.** A UTf-16-LE file without a mark, holding `构式网络很小，训练语料合计 154,391 句`, decoded as
UTF-8 to replacement characters; every claim quoting it came back `quote-missing` at high severity,
which is a finding that accuses the author of not quoting a page whose only problem was the save
dialog. `_noise` now counts replacement characters and C0 controls — both appear only when bytes were
split at the wrong boundary, in every script — and the decoder takes the little-endian reading when it
leaves less of either. Big-endian without a mark is still refused rather than guessed: swap a Han
character's bytes and you get another Han character, so for single-script prose the two readings are
equally clean and a rule that picked one would be a coin flip; `test_big_endian_without_a_mark_is_admitted_not_guessed`
pins that limit so an improvement to it has to change the docstring too. Both mutations are red. Seen 1.

## A character you cannot see is still a character the comparison sees

**Rule.** When two strings are compared after normalisation, remove every code point that renders as
nothing, and define "renders as nothing" by Unicode category rather than by a list of the ones that
have caused trouble so far. A format character is an instruction to the layout engine: it is in the
string, it is invisible on the page, and a reader cannot tell it is there.

**Why.** The failure looks exactly like the digit problem and is worse. It is not a crash and it is
not a near miss; it is a *verdict*. The author quotes a sentence they can see, the PDF's extracted
text carries the exporter's directional mark in the middle of it, the two strings differ by one
character, the quote falls through the exact and squashed tiers, and the run reports `quote-missing`
at high severity. Everyone who reads that report has been told something false about their own work,
and nothing in it mentions directionality, so the only available next step is to doubt the tool.

**Evidence.** `_EQUIV` removed five format characters by name — ZWSP, ZWNJ, ZWJ, ZERO WIDTH NO-BREAK
SPACE, SOFT HYPHEN — and left the other 165. Inserting an RLM between two words of a source page made
`find_in_pages` return `tier="none"`; so did ALM, WORD JOINER, all four isolates, LRE/RLE/PDF/LRO/RLO
and the Mongolian vowel separator. All of them are in Word and InDesign exports of Arabic and Hebrew,
and `تشير البيانات إلى أن البنية تشمل الجمل` against a page carrying `U+202B … U+202C` is a correct quote
reported as missing. `strip_format` now removes category `Cf` wholesale; `tests/test_invisible.py`
verifies the compiled class against `unicodedata.category` over all 1,114,112 code points in **both**
directions, because a class that is too narrow misses characters and a class that is too wide silently
changes what a quote says. The ranges are written out rather than computed per import — walking
Unicode costs about 100 ms, which is real money in a pre-commit hook — and that trade is only safe
because the test re-derives the category every run. Three mutations are red: drop the call from
`normalize`, narrow the range to ZWSP alone, widen it into the general punctuation block. Seen 1.

## Two different absences arrive as the same errno

**Rule.** When a path is not a file, say *which* way it is not one — a directory, a missing path, or
a location this machine cannot reach — and get the third answer from the raw error rather than from
`Path.exists()`. `exists()` collapses every `OSError` into a boolean, so the two questions "does the
author still have this file?" and "can I see the share it lives on?" come back as the same `False`
and the sentence that follows is a guess dressed as a fact.

**Why.** The sentence is what the author acts on. "Does not exist" about an unreachable share sends
them looking for a manuscript they never lost; the errand is impossible to complete, and the only
conclusion available at the end of it is that the tool is broken. A wrong sentence is worse than a
vague one because it is followed. This is the same failure as the directory sentence and the same
failure as the bibliography that parsed to zero entries: the operation succeeded, produced the
degenerate value, and the words attributed that value to the wrong subject.

**Evidence.** `os.stat` on `\\server\share\paper.md` with the share down raises `OSError` with
`winerror=53` (`ERROR_BAD_NETPATH`) while an absent path raises `winerror=3`
(`ERROR_FILE_NOT_FOUND`); Python maps both to `errno.ENOENT`, so `Path.exists()` cannot tell them
apart. Six call sites wrote "does not exist" — `scan.py` for the manuscript and for the bibliography,
`cli.py` for the same two, `sources.py` twice, and `verify.py`'s `ledger-stale` — and each was
faithfully reporting the only thing the boolean could tell it. `why_not_a_file` now reads
`winerror`/`errno` and answers with one of three sentences, and every site routes through it. The
first version of the `ledger-stale` rewrite spliced the predicate into a sentence that already had a
verb and produced `cannot be opened (cannot be reached (the network path is not available from
here))`; a rewritten `_gone_sentence` keeps one set of brackets, and a test asserts
`gone.count("(") == 0` so the nesting cannot come back. A second crash was hiding behind the first:
a directory named `m.md` satisfies `exists()`, so `sha256_file` raised `PermissionError` and the
traceback left `main` with exit 1 — the exit code that means "the manuscript has findings". Four
mutations are red: empty the `winerror` table, empty the `errno` table, put `verify` back on
`exists()`, and splice the fragment back in. Seen 1.

## Two readers of the same format disagreed, and only one of them was tested

**Rule.** When one file format has two readers - attributes here, a block body
there - give them one function for shared syntax and test the value each one
produces, not just the fact that it produced something. A syntax detail that one
reader honours and the other ignores is invisible in a passing test suite,
because every test writes the form the honoured reader expects.

**Why.** Two failures in this repository share this shape, and both were found in
the same probe after eleven rounds of review. `_attrs` stripped the YAML quote
marks off `key="value"` from the first commit; `_split_body` never stripped them
off an inline `quote: "..."`. A writer who quoted the passage got `quote-missing`
at high severity - an accusation that their PDF does not contain a sentence it
contains - for a file that was correct in every way a reader could see.
`scan` decided a file was empty by checking `parsed.findings`; `verify` decided
it by checking `parsed.claims`, so a block missing its `id=` was reported twice:
the parser's true sentence and the emptiness guard's false one. A reader who
believes the second edits a block that needed no edit.

**Evidence.** `parse_manuscript` on `quote: "We train on two corpora."` returned
`'"We train on two corpora."'` - marks included - while the same text as an
attribute returned the value alone. Five shapes were measured before the fix
(plain, double, single, `|` block, `>` folded): two of the five carried the
marks into the search. A ` ```claim source=p ` block produced
`claim-uncheckable` from the library and `claim-uncheckable` plus
`no-claim-blocks` from the command line, because `check` runs `scan` then
`verify` and each pass has its own emptiness branch. The quote fix is deliberately
conservative: marks are stripped only when the mark does not appear inside the
value, so `"yes" or "no"` is content and keeps both marks, while a lone `"` is
left alone. Three mutations are red - put `verify` back on `parsed.claims`,
stop calling `_unquote`, and drop the inside-check that makes `_unquote`
conservative. Seen 1.

## A step that cannot be re-run has to say what to do instead

Every step in a release workflow should be assumed re-runnable, and the one
that is not must fail loudly enough to be fixed by hand.

**Rule.** When step N commits something that makes step N+1 impossible to
retry - here, pushing the version bump empties the changelog section that
decides whether to release at all - step N+1 may not fail with the remote's
own words. It retries, then asks the remote for the state it wanted, and if
the state is not there it prints the command that establishes it. A bare
`exit 1` tells a reader to re-run the workflow, which is the one thing that
cannot work.

**Why.** The failure and its reason live in different places: the remote
says `(failed)` and nothing else, and the reason a re-run cannot help is two
steps up in the same file. Whoever reads the red X has the log and not the
file. An error message is the only place those two can meet.

**Evidence.** `v0.19.6` was bumped and committed to `main` as `977dbd5`,
and then `git push origin v0.19.6` was rejected with
`! [remote rejected] v0.19.6 -> v0.19.6 (failed)` and no reason, seconds
after `git push origin HEAD:main` to the same remote succeeded. The
repository has no tag ruleset (`gh api repos/lyear12/citevouch/rulesets`
returns `[]` and `.../tags/protection` is 404), so the rejection was
transient and one retry would have absorbed it. It was recovered by tagging
from a workstation, which is exactly what the new message now spells out.
The guards in `tests/test_tag_push.py` run the step's shell body against a
stub `git`: dropping the retry loop, dropping the `ls-remote` check, and
deleting the explanation from the error each turn one of them red. Seen 1.

## The gate that counts tracked files will pass before the file is tracked

A newly written file is invisible to the measurement that governs it, and it
is invisible exactly while the author is running the gate.

**Rule.** When the number in a commit message comes from `git ls-files`, run
the counting command after `git add`, not before. The check passing before a
file is staged is not evidence about the commit; it is evidence about the
tree that will not be committed. The same goes the other way: a file added
after the gate ran has never been judged by it.

**Why.** `tools/format_check.sh` measures the index because that is the only
input every clone shares - but the index is also the one input that is still
changing while a change is being written. So the guard is correct and the
order of the two commands decides whether it saw the work. Nothing in the
output says which files it skipped, because the whole point of measuring the
index is to not see the rest.

**Evidence.** `tests/test_tag_push.py` was written, the full suite was run
(750 passed), `sh tools/format_check.sh` reported `79 files already
formatted` - and the file was not among them, so the 80th was never
formatted. The commit went out, and ten CI jobs failed on
`test_it_reports_the_number_of_tracked_files_ruff_accepts` with the real
count: `unformatted: File would be reformatted --> tests\test_tag_push.py`.
Re-running `git add` first and then `python -m ruff format` gives 80, which
is what CI agrees with. This is the second time this exact step has cost a
round: the same thing happened to `tests/test_no_claims.py` in the release
that introduced `no-claim-blocks`. Seen 2.

**Third time, 2026-11-01, and not about a new file.** `fbbd832` ran the
suite, then edited `docs/backlog.md`, then pushed. Every count in the
message was honest and every file was tracked - the tree simply changed
after it was measured. Eleven CI jobs failed on
`tests/test_critic_round3.py`, whose rule is that a doc line mentioning
`pyproject.toml` has to say what it is read for. Promoted into
[docs/code-standards.md](docs/code-standards.md) acceptance rule 10, where
it now reads as a rule about *when* the gate is run rather than about what
it reads. Seen 3.

## A path and a URI are two different strings wearing the same characters

`artifactLocation.uri` is a URI. Every other path this tool handles is a file
name. They disagree on exactly the characters that appear in real paper
directories: `#` starts a fragment, `%` starts a percent-escape, a space is not
allowed, and anything above U+007F is not a URI at all.

The function that builds it was written to fix a *different* silent loss: an
absolute local path matched no repository artifact, so GitHub dropped the
annotation and the run stayed green. It re-rooted the path and stopped there,
and the encoding half was never written - so `draft#2.md` became the artifact
`draft` plus the fragment `2.md`, `draft%20.md` became `draft .md`, and
`论文.md` was not a URI. Same failure, same invisibility: nothing errored, the
upload succeeded, the annotation was just somewhere else or nowhere.

Two lessons, because both halves cost something to see:

1. **A fix aimed at one way of losing data does not cover the others.** The
   docstring described the failure mode precisely and still missed it, because
   it reasoned "absolute paths are wrong, relative paths are right" and never
   asked what a *path* is not allowed to contain. When a field has a
   specified format, the question is not "does my value look like the values I
   have seen" but "is my value valid in this format at all".
2. **Encode last.** The natural fix - encode the string at the top - leaves
   the branch that returns `relative_to(...).as_posix()` unencoded, because
   that path is computed later. The reverse-verification for "encode before
   re-rooting" is what proves the order matters; without it the fix looks
   correct and one branch is still broken.

Evidence: `_probe_uri.py` over six file names (`m.md`, `my paper.md`, `论文.md`,
`draft#2.md`, `draft%20.md`, `odd"name.md`) printed the URI for each before and
after; `tests/test_report.py::TestTheSarifUriIsAUri` asserts the round trip
(`unquote(uri) == name`) rather than a literal, so the encoding cannot drift
from what a reader would decode. Seen 1.

## There are two of every branch, and the test only covers the branch you were looking at

**Rule.** When a defect has N code paths that produce it, the fix is not done
until N tests fail without it. Enumerate the branches first and write the paths
down; "I fixed the bug" means "I fixed every site the bug can be produced at",
and the count of sites is a fact you measure, not a feeling.

**Why.** A reader with two ways to report the same finding looks like one piece
of logic, because it prints one message. The message text is written twice, and
the second copy is invisible from the first one - you find it by grepping for
the sentence you just changed, not by reading the function you just opened.

**What it cost.** The bibliography reader reports stray text in two places: after
the last entry, and between two entries. The probe that found the defect - one
stray character after a single entry - only walked the first path. The fix
changed both, but the test covered one, and the first reverse-verification
printed `GREEN (guard is not guarding)` for the other. Had that check been
skipped, half the fix would have been a claim rather than a change.

**How it was caught.** The reverse verification ran each branch separately and
reported GREEN for the uncovered one. The useful signal was not "a mutation
survived" but *which* mutation survived: the branch name in the case label is
what pointed at the untested path.

Evidence: `_rev_counts.py` reported `bibtex stray plural (old inline message):
GREEN (guard is not guarding)`; `tests/test_counts.py` then gained
`test_stray_text_between_two_entries_counts_the_same_way` and
`test_text_between_two_entries_is_plural_for_several`, and re-running the same
five mutations printed RED for all five. Seen 2 (the same shape as the
`--formatted` line matcher that stopped matching its subject, and the
`_no_text_problem` call that was added to the extraction path but not the cache
path).

## A sentence has more than one word that agrees with the count

**Rule.** When a count drives a message, every agreeing word in that message is
part of the fix, not just the first one. Fix the sentence, then read it out loud
with the count set to 1.

**Why.** English agreement is spread out: "1 character was between entries and
was not read" has the verb twice and the noun once, while "3 characters were
between entries and were not read" has them all in the plural. Changing the
number and the first noun produces a sentence that looks repaired at the top and
contradicts itself at the bottom.

**What it cost.** One extra round trip. The first version of this fix changed
`characters` to `count_of(...)` and `were` to `verb_for(...)` for the first
clause only; the probe printed `1 character ... was between entries and were not
read`, which reads worse than the original because the disagreement is now
inside one sentence.

**How it was caught.** Running the command and reading the output, which is
different from running the tests and reading the exit code. The test written
afterwards asserts on `"were" not in line`, which is the assertion that would
have failed on the half-fix.

Evidence: the probe output `1 char -> 1 character at line 1 was between entries
and were not read` before the second edit, and `... and was not read` after it;
`tests/test_counts.py::TestTheBibliographyReaderAgreesWithItsCount` asserts the
absence of the plural verb, not just the presence of the singular one. Seen 1.

## A second table of the same fact is a table nobody diffs

**Rule.** When two data structures carry the same fact, one of them must be
deleted. A derived value is allowed to be written twice in two reports — but it
must be computed once, from one source, in both places.

**Why.** Two tables can be compared by a test, and the test that gets written
is the one that is easy to write: the key sets. `set(CODES) == set(SARIF_RULES)`
is true, cheap, and says nothing about whether the two tables *agree*. Every
entry could carry a different level in each and the assertion would still pass.
The values are the part that matters and the part nobody diffs by hand.

**Evidence.** `src/citevouch/report.py` carried `SARIF_RULES` as
`{code: (description, level)}` while `src/citevouch/model.py:CODES` already held
a severity for every one of those codes, and `_LEVEL` already translated a
severity into a SARIF level for the *results*. So the document derived a result
level correctly and a rule level from a hand-written copy, and the two
disagreed in two ways:

* fifteen rules said `"blocking"` — not a level the SARIF 2.1.0 schema allows;
* `claim-without-evidence` said `warning` about a code `CODES` calls `low`.

Neither was visible from the outside because nothing read a level back. The
probe that found it printed the table next to `severity_of(code)` and marked the
rows that disagreed; the fix deleted the second column. Restoring either
behaviour — the hand-written `"blocking"`, or `"low": "warning"` in `_LEVEL` —
turns `tests/test_report.py::TestTheSarifLevelIsALevel` red, and so does making
the result level stop matching the rule level.

Seen 1.

## Fixing a bug in one writer does not fix the bug

**Rule.** When a bug is in a value that several writers receive, grep for every
caller before the fix is called done. A fix is not a fix until you know which
other readers are handed the same argument.

**Why.** The renderer you were reading when the bug was reported is the one you
fix. The other writers take the same list and are usually written months apart,
so nothing reminds you they exist. They do not even look wrong: each one is
internally consistent with itself, and only disagrees with the exit code.

**Evidence.** `--quiet` used to filter the findings in the text renderer alone,
so `--quiet --format sarif` uploaded info-level findings to code scanning. That
was found and fixed by moving the filter up into `_render`, where every format
sees it - but the fix stopped there, because the visible symptom was text.
Months later the same filter turned out to break `--format json` differently:
the payload's four claim counts describe the run, `summary.findings` counted the
filtered list, and `worst` was computed over the filtered list too. So
`--quiet` produced `verified: 1, missing: 1` beside `findings: 1` and a
`worst: info` on a run that exited 1. Nothing was ever wrong with any single
line; the file was wrong as a whole, which no line-level test can see.

The probe that found it did not test the filter. It ran one input through each
`--format` and compared the parts of the object to each other - do the claim
counts add up to `checked`, does the listed length plus anything-hidden equal
the run, does `worst` agree with the exit code. Restoring any of the old
behaviours - `findings: len(findings)`, `worst` over the short list, dropping
the `hidden` field, or the CLI not passing `everything=` - turns
`tests/test_report.py::TestTheJsonDescribesTheRunAndSaysWhatItLeftOut` red.

The third occurrence was `--format markdown`, and it is the one that shows why
this keeps happening. The JSON fix moved the filter up into `_render`, a single
place every format passes through - and that made the markdown writer worse, not
better, because now `_render` shortened the list before markdown saw it and
markdown had no way to describe a run it was never shown. The repair is not
"filter in `_render`" and it is not "filter in each writer"; it is that every
writer which prints a summary line gets the whole list and filters for itself,
and the only two left in the upstream `if` are the two that print no summary at
all. Upstream was the tempting place to fix this, and it was the wrong place
twice running.

Seen 3. Promoted to `docs/code-standards.md`.

## A file format with includes has a second half you did not read

**Rule.** If a reader claims to understand a format that can point at other
files, it has to say which files it did not follow. Not following them is a
scope decision and is fine; returning a clean zero either way is not.

**Why.** `citevouch draft paper.tex` reads one file. A LaTeX paper that keeps
its chapters in `\input{sec/intro}` - the shape of every Overleaf project
and most submissions - keeps its citations in the parts. On such a paper the
command proposed `0 claim block(s)` and exited 0. The output was correct about
the one file it opened and wrong about the paper: it reads as "this manuscript
has no citations", which is a verdict, when the truth is "I never opened the
half that does", which is a scope note. This project has now met this shape
five times - a `.tex` read as markdown, a manuscript with no claim blocks, a
bibliography no decoder could read, a scan with no text layer, a chatty
citation with no verbatim sentence - and every repair was the same sentence in
a different tense: an empty result has to name what made it empty.

**Evidence.** `tests/test_latex_end_to_end.py::TestASplitPaperIsNotASilentZero`
asserts the names appear for a split paper and that a document holding its own
text gets no such note. Three mutations turn it red: `render` ignoring
`included`, `cmd_draft` never collecting the names, and the finder skipping
`strip_comments` so a commented-out `\input` counts as a file that was not
read. Following the includes is deliberately not done here - that is a design
change, and the note is what makes the design's limit visible instead of
silent.

Seen 1.

## A code borrowed from a neighbour is a word the reader sees and you do not

**Rule.** A finding code is not an internal label. It is the sentence a reader
sees above the message - in the SARIF rule table, in the README severity table,
in the exit-code conversation. Reusing a neighbouring code to keep the
inventory small is only honest when the neighbour is true; when it is merely
close, the reader is told about a different problem than the one they have.

**Why.** `doctor` reports a machine that cannot check anything: an interpreter
below the supported version, no PDF library, a cache directory nobody can
write, a project without the files it claims. All of them were emitted as
`source-unreadable`, with a docstring arguing that one vocabulary per problem
beats two and that "a machine that cannot read a PDF is a machine whose every
quote would be reported unreadable." That reasoning is about the
*consequence*; the field is about the *cause*. In `--format text` nobody
noticed, because the message carries the fact: "cache: not writable; every run
will re-extract". In SARIF the rule line comes from the code, so the code
scanning tab displayed

    A source file could not be read.
    cache: not writable; every run will re-extract

and the second line correctly diagnoses a problem the first line does not
name. The choice was made against a rendering the author never looks at, which
is why "does it read well in the terminal" could not catch it.

**Evidence.** Emitting all four failures through `doctor.findings()` and
reading the SARIF `ruleId` and the rule text showed every one of them under "A
source file could not be read."
`tests/test_doctor.py::TestHowItReads::test_the_code_does_not_borrow_a_source_code_for_a_machine_problem`
and `TestTheCommand::test_sarif_carries_the_broken_checks` hold the new
`check-unavailable` code in place, and the four symmetry guards (`CODES`,
`SARIF_RULES`, both README tables) go red at once if a code is added to one
and not the others. Seen 1.

## An entry that was dropped cannot be described, so describe it before you drop it

A message about a project file has to be true about that file. When four
different situations produce the same sentence, the reader is told the one
thing that is wrong least often, and the fix they attempt is the one that
cannot help. Keep the failures you cannot use, with the reason, until the
sentence that names them has been written.

**Why.** `sources.toml` naming `p = "gone.txt"` produced, per claim,
`claim c1 names source='p' but no entry in sources.toml and no --source path
resolves it; add it to sources.toml`. The author had the entry. Re-reading
the manifest is the one action that cannot fix it, and it is the action the
sentence names. The mechanism was upstream and invisible:
`discover_sources` walked the manifest with `if path.is_file():` and no
`else`, so the entry was already gone by the time the message was built, and
"no manifest", "no such key", "key names a file that is not there" and
"manifest will not parse" all arrived as `{}`. A function that returns only
what succeeded cannot support a message about what failed; the information
is destroyed one stack frame before it is needed.

**Why it survived being read.** The same function had two tests, four lines
apart, reaching opposite conclusions about the same judgement: a directory
passed to `--source` must be refused, while a directory named in the
manifest is ignored. Both were written as expected behaviour and both
passed. The half that was wrong was the half that did nothing - dropping an
entry produces no output, so there was nothing to read and nothing to doubt.
A behaviour that leaves no trace is not reviewed; it is only inherited.

**Evidence.** Five manifest shapes against one fixture - valid, absent,
broken TOML, empty string, key naming a missing file, key naming a
directory - produced two distinct sentences instead of five, and the two
wrong ones both said "no entry in sources.toml".
`tests/test_manifest_message.py` now asserts the sentence for each cause,
and `test_critic_round3.py`'s manifest half no longer disagrees with its
`--source` half. Four mutations - dropping the entry, ignoring the table in
the message, not passing the table in, and not reporting an unparseable
manifest - are all red. Seen 1.

---

## A compatibility shim that returns less than the real function is a shim the next caller picks

**Rule.** A wrapper kept "so callers do not change shape" must return something the caller cannot get wrong. If the real function returns a record precisely because the flat return lost the information needed to explain a failure, then the flat wrapper is not a compatibility layer - it is a way back to the bug, under a friendlier name. Delete it once the last caller is gone, and say in the surviving function's docstring that it existed and why it went.

**Why.** Dead code is harmless when it is unreachable. This was reachable: it was imported by name in two test files, so it read as live API, and it was the shorter name for the common case. A caller adding one more consumer of `src/citevouch/sources.py:read_source_table` has no reason to look at the other function's docstring, and the flat mapping it returns is exactly the shape that made `scan` tell authors "no entry in sources.toml" about a manifest entry that was right there.

**Evidence.** `discover_sources` was kept when `read_source_table` was introduced, on the reasoning that the three commands could keep their old shape. Within two rounds all three - `src/citevouch/scan.py`'s `_missing_source_message`, `src/citevouch/verify.py`'s per-claim message and `src/citevouch/draft.py`'s `_why_no_file` - asked for the table instead, because the mapping alone cannot say why an entry failed. `grep -rn discover_sources src/` then returned only its own definition and a docstring reference: no callers, while `tests/test_critic_round3.py` and `tests/test_manifest_message.py` still imported it, which is what kept it looking alive. Removing it changed no behaviour and no test needed a new assertion; one test kept only `assert "other" not in found`, an assertion that cannot tell a dropped entry from a kept one, and now asserts the failure is recorded. Seen 1.

---

## A pattern that ends in an unbounded token will eat the neighbour

**Rule.** When a pattern matches an unbounded token (\S+, `.+`, `[^ ]+`) right after an optional `=`, ask what happens when the value is *empty*.  The token class that made the parser permissive is the same one that makes it swallow the next field, and the grammar alone cannot tell the two cases apart - the author's spacing does.  So let the spacing decide: no space after `=` means the token is the value, a space means a following `key=` starts a new attribute.

**Why.** The failure is not a crash and not a wrong count.  It is a sentence about a different part of the project.  The claim gets bound to a source named `page=1`, `sources.toml` has no such key, and the report sends the author to the manifest - the one file that is correct.  Nothing in the message mentions the empty `source=` in front of them.

**Evidence.** `src/citevouch/manuscript.py:_attrs` matched `(?P<value>"[^"]*"|'[^']*'|\S+)`, so `claim id=c1 source= page=1` produced `{"source": "page=1"}` and `verify` reported `claim c1 names source='page=1' but no entry in sources.toml`.  The fix splits the alternation on the space after `=` and keeps the greedy reading for the tight form, so `source=a=b` still means the key `a=b`.  Three mutations are red and each fails only its own half: the old greedy pattern, removing the lookahead from the spaced form, and refusing unquoted values in the tight form.  The first attempt used a single lookahead for both spellings and silently broke `source=a=b` - which is why both spellings are now pinned by a test.  Seen 1.

## Two sources can name one key, and the loser is always silent

**Rule.** When two independent inputs can bind the same name, refuse the collision and say which two things collided. Do not let the later one win on the theory that order is obvious - the order is obvious to whoever wrote the loop, and invisible to whoever runs the command.

**Why.** A key bound twice does not fail loudly, it fails as a finding about something else. The claim is searched for in one of the two files; the other file, the one the caller was trying to use, is reported as not containing the quote. Every word of that finding is true about the file it names, and the reader is sent to fix the wrong thing: they re-check their quote, then their page number, then whether the PDF is the right edition.

**How to apply.** Resolve both paths before comparing them, so that naming the same file twice is not a collision. Say the key and both paths in the message. And keep the quiet path quiet: `--source papers/x.pdf` against a manifest entry that already points there must still work, or the refusal becomes the new reason people stop using the flag.

**Evidence.** Measured 2026-10-31: a manifest entry `dup = "p.txt"` plus `--source dup.txt` printed only `[high] quote-missing ... quote not found in p.txt`; two `--source` flags on `a/x.txt` and `b/x.txt` did the same. Three mutations (drop the manifest check, drop the flag check, compare paths as text instead of resolving them) each turned the new tests red. Seen 1.

---

## Two files that each claim the same role cannot be ranked, only refused

**Rule.** When a lookup can find more than one thing that occupies the same
position, refuse and name every candidate. Do not read the first and stay
silent about the rest: the file that was not read is not merely unused, it is
evidence the author will consult to reconstruct what happened. A refusal can
also be the only message that admits the losing file exists.

**Why.** The tool resolved keys against `sources.toml` and reported every
disagreement as though the checkout had one manifest. In a tree that held a
stale `sources.json` beside the live TOML, the JSON could hold the answer and
still never appear in any sentence: the author reads a message about a file
that is not the one being read, edits it, and the run does not change. The
sentence is not wrong about a path, it is wrong about *which* paths exist.

**How to apply.** Enumerate the candidates before opening either, decide the
refusal at that point, and let the message name all of them by the names the
reader would see in their file manager. Keep the single-candidate path
byte-identical to what it was: a refusal that costs the working case is a new
outage in place of an old silence.

**Evidence.** Measured 2026-10-31: with `sources.toml` pointing at
`wrong.txt` and `sources.json` at `p.txt`, `check` printed
`[high] quote-missing ... quote not found in wrong.txt`, and swapping the two
contents flipped the result - the ranking was a fact about `MANIFEST_NAMES`,
not about the files. Three mutations (hard-code the name back, forget
`manifest_name`, restore the ranking) each turned the new tests red. Seen 1.
---

## A command you print is a command someone will run

**Rule.** When a message contains a command, treat the message as a test
case: copy the command out of the output and run it in the state the reader
will be in. The path in a *finding* is for machines - a basename reads the
same on every checkout - but the path in *advice* is for the person holding
the file, and it has to be the path they typed. When the advice tells them to
write a file, make sure the output name differs from the input name for every
input the advice can name.

**Why.** Advice that fails is worse than silence, because it spends the
reader's trust twice: they learn the tool is wrong *and* they learn to stop
reading its suggestions. Both faults here were invisible to the test suite
because every test asserted on the finding's `path` and none executed the
sentence. A guard that reads a string is not a guard that runs it.

**How to apply.** Extract the command with a regex in the test, assert its
*shape* (right directory, different output), and - where the tool can be
invoked in-process - actually invoke it and require the documented exit code.
Keep the machine-facing and human-facing forms in one function so the day one
changes, the other is in the same review.

**Evidence.** Measured 2026-10-31 on 0.19.20: `check paper/m.md --root .`
printed `citevouch draft m.md -o claims.md`; running it gave
`citevouch: manuscript m.md does not exist` and exit 2. With the manuscript
itself named `claims.md`, the printed advice was
`citevouch draft claims.md -o claims.md`, which `draft` refuses on purpose
(writing proposals over their source), exit 2. Both are now covered by
`tests/test_no_claims.py::TestTheAdviceCanBeFollowed`; three mutations
(basename in the advice, output name always `claims.md`, callers not passing
the typed path) each turned exactly one test red. Seen 2 - the second was
the same sentence, one flag later: `check m.md --root paper` printed `citevouch
draft m.md -o claims.md`, and running that answered `manuscript m.md does not
exist` because a relative path and its `--root` are one fact in two pieces. The
first fix moved the string from basename to typed path and stopped there, which
is why the rule above says *shape*: the shape of a path includes the base it
was resolved against. The regression test now executes the printed command
instead of pattern-matching it, because a string match cannot see a missing
flag. Seen 2.

## A delimiter has to be chosen after looking at the content

**Rule.** When you wrap a string in a delimiter that can also appear inside
it, the delimiter must be chosen by inspecting the string, not by writing it
first in the source. And when the string also has to survive an escaping
step, wrap *after* escaping is finished - never escape a fragment and then
build a larger thing around it.

**Why.** A CommonMark code span closes on the first run of backticks as long
as its opening run. ``_cell('`' + claim.id + '`')`` therefore closed early on
an id holding a backtick, and the row lost a cell. The fix is not a longer
constant: how long is long enough is a property of the *value*, so the
delimiter cannot be a literal.

**How to apply.** Ask what varies with the input before choosing a wrapper.
If the answer is "the delimiter", make it a function of the value; then
hand the finished string to the escaper, so the two rules do not have to be
reasoned about together. Test the rule against the string (does the closing
run exceed every interior run?) rather than through a renderer, unless the
renderer is a real dependency.

**Evidence.** Measured 2026-10-31 on 0.19.22:
`citevouch report` with `id=c`1` printed
`| `c`1` | s | 1 | The corpus contains 154,391 utterances. |` and a GitHub
preview renders it as `<code>c</code>1`, one cell short. After the fix the
same row is `| ``c`1`` | s | 1 | ... |`. Three mutations (wrap the escaped
id again, always use one backtick, never pad) each turned the new tests red.
Seen 1.

## A test that supplies the argument the hook does not is testing itself

**Rule.** When a test exercises an entry point defined in a data file, build
the invocation out of that file's fields. Never let the test add a piece the
file forgot. If you find yourself writing `entry + " manuscript.md"`, the
file has already stopped being the subject.

**Why.** `.pre-commit-hooks.yaml` said `entry: citevouch check` with
`pass_filenames: false` and no `args:`. pre-commit runs precisely that: no
argument. `check` takes the manuscript positionally, so the hook exited 2 on
an argparse error - no claim read, every commit refused, and the message
blamed the author's arguments. The suite covered the hook "as behaviour",
and its helper had a default of `extra: str = "manuscript.md"`. The tests
ran the command the author wished the hook ran, so the defect could not
appear in the one place it was guaranteed to matter.

**How to apply.** A default that fills in a required input is the bug, not
the convenience: delete it and let the composition read `args`,
`pass_filenames` and `entry` from the file. Then the honest assertion is
structural - the command can run at all - which is the half the old test
was missing, since it only asserted that *no* filenames were passed.

**Evidence.** Measured 2026-10-31 on 0.19.23: running the hook's entry with
no argument printed `citevouch check: error: the following arguments are
required: manuscript` and exited 2, while `tests/test_precommit.py` reported
13 passing. Changing the helper's default to `""` turned two tests red
immediately, and restoring `args:` turned them green. Three mutations of the
repaired file - drop `args`, make `args` flags only, turn filenames back on
- each turned the suite red. Seen 1.

## A message that quotes the counterexample is arguing against itself

**Rule.** When a message names a rule, check the sample it prints against
that rule. If the sample satisfies it, the message is not imprecise - it is
self-refuting, and the reader concludes the tool is broken rather than the
file.

**Why.** The `no-claim-blocks` message had three branches: too many
backticks, wrong case, and "everything else". Everything else got the
generic sentence "claim fences are three backticks followed by the word
`claim`", then the near-miss line was appended. For an indented example -
the shape a README uses to document the syntax - that line is
`` ```claim id=example `` , which is precisely three backticks followed by
the word `claim`. The one distinguishing fact, the indent, was measured by
neither the detector nor the message.

**How to apply.** Give the fallback branch nothing to explain. Enumerate the
distinguishing features where the near miss is detected, and keep the
generic sentence for the case that has no distinguishing feature at all -
then assert, in a test, both that the specific reason appears and that the
generic sentence does not.

**Evidence.** Measured 2026-10-31 on 0.19.24: a README-style manuscript with
one 4-space-indented sample printed "line 5 reads like a claim block but is
not one the parser accepts (claim fences are three backticks followed by the
word `claim`)" and then the line ```claim id=example source=a - which is
that. After the fix it says "it is indented by 4 space(s), and an indented
fence is a code sample in Markdown". Three mutations (drop the branch, keep
the branch but never test it, measure the indent from the stripped line so
it is always 0) each turned the new test red. Seen 1.

---

## Text a document does not read as prose has to leave every pass that reads prose

**Rule.** A masking pass that restores what it hid has only solved the
problem it was written for. Whatever runs after it sees the restored text, so
either every later pass also knows about the construct, or the pass that
restores is the wrong place to stop.

**Why.** `strip_comments` hid `verbatim` bodies, scanned for `%`, and put
them back - correct for its own job, because the `%` inside `50\verb|%|` is
a character. But the text it returns is read by `_CITE` and by `_convert`, so
`\verb|\citep{a1}|` came out as a real `[@a1]`: the tool recorded a citation
the author only *illustrated*. A restore that happens too early is
indistinguishable from no masking at all, and it is worse than no masking
because the code reads as if the case were handled.

**How to apply.** When the value is restored, ask who reads the restored
value and whether each of them can be fooled by it. Hide the construct from
every pass that reads prose, put it back only at the end, and keep the
command and its delimiters intact while hiding the body: the last pass has to
recognise the construct in order to take it apart.

**Evidence.** Measured 2026-10-31 on 0.19.25. `\verb|\citep{a1}|`,
`\verb*|...|`, `\lstinline|...|`, `\lstinline[language=TeX]|...|` and
`\mintinline{tex}|...|` each produced a verified citation. `50\verb|%| of it
\citep{real2020}` lost everything after the `%` including the real citation,
because the `%` was read as a comment. `%` inside a `verbatim` environment ate
the `\end{verbatim}`, so `to_text` returned an empty document and every
citation after it vanished. `included_files` reported a
`\verb|\input{sec/ghost}|` as a file the tool could not read. Three
mutations (no environment masking, no inline masking in `to_text`, bodies
restored as nothing) each turned a new test red; the test that had been there
for the environment case asserted only that `to_text` returned a string.
Seen 1.
## A tier named after a conclusion has to actually measure that conclusion

**Rule.** When a layer's name or message states a fact ("the numbers do not
match"), compute that fact. A layer that knows only that the *literal*
comparison failed knows nothing about the reason, and the reason is what the
reader acts on.

**Why.** The tier that reports `number-absent-in-quote` proved nothing about
the numbers. It masked every number out of both sides, found the remaining
words equal, and concluded the numbers must therefore differ. That inference
holds only if "the literal comparison failed" implies "the values differ",
and the whole point of a normalising tool is that it does not: `40.688` and
`40,688` are one value spelling itself two ways. The message then told an
author that a number they had copied off the page was not on the page, which
is the one accusation this tool must never make falsely. The test suite could
not have caught it by accident either: every existing case for that tier used
numbers that really did differ, so the mask-and-assume shortcut agreed with
the truth on every input anyone had tried.

**How to apply.** For each branch, ask what it *knows* versus what it
*claims*. A claim that generalises over a comparison the branch never ran
belongs in its own tier with its own comparison, not in the message of the
branch that failed for another reason. And when a new spelling of a value
enters the normaliser, the branch that reports on that value has to be
re-tested with two spellings of one value, not only with two different values.

**Evidence.** Measured 2026-11-01 on 0.19.26. Page `Overall we counted 40.688
entries in the corpus.` against quote `Overall we counted 40,688 entries in
the corpus.` gave `[high] number-absent-in-quote` and exit 1, with the masked
text on both sides identical (`Overall we counted \x00 entries in the
corpus.`). `41,000` against `40,688` was indistinguishable from it. Adding a
`canonical` tier - both sides with every number rewritten to one spelling -
made the first `quote-found` and left the second `number-absent-in-quote`.
Five mutations were tried; three turned red at once, and the two that stayed
green were green because their test asserted the excerpt still *contained*
the quote, which a sixty-character margin buys back after a wrong offset.
Tightening the test to assert the window's width as well turned both red.
Seen 1.

## A word boundary is not a number boundary

**Rule.** A comparison that decides "is this text present on that page" must
know where the *values* in it start and end, not only where its words do.
Before certifying a match, ask whether the matched span cuts a number in half.

**Why.** `_is_word_char` is `str.isalnum`, which is the right rule for words
and blind to numbers: `.` `,` `٫` are neither letters nor digits, so a quote
ending at `40` before `.688` ends on a non-word character and the boundary rule
says "clean word end". The page says `40.688`; the claim says `40`; the tool
reported `exact`, similarity `1.0`, verified. Five shapes did it — `40.`,
`40`, `40,`, `We used Python 3.` against `3.10.2`, and `The value is 406`
against `40688`.

**How to apply.** Take the spans from the same pattern that decides what a
number is everywhere else (`REPORT_PATTERN`), so the guard and the report can
never disagree about where a number starts and ends. Refuse a match only when
it lands *strictly* inside a span: ending exactly at the number's end, or
stopping before it begins, is honest. And when adding the guard to a tier,
prove the tier can be reached — the canonical tier got one too, and an
exhaustive sweep of 453 canonical matches over five pages showed it could never
fire, because canonical text spells every number as one unbroken run with no
separator to be cut at. An unreachable guard cannot be tested, so it is a
claim of protection with no evidence behind it; it was removed and the reason
written where the guard had been.

**Evidence.** Measured 2026-11-01 on 0.19.27. Page `The value is 40.688 in the
table.` against quote `The value is 40.` gave `tier=exact found=True`; after the
guard the same pair gives `tier=none found=False` while
`The value is 40.688` still matches `exact` and `The value is 40,688` matches
`canonical`. Six mutations of the guard; five turned red immediately, and the
sixth — the canonical `end` computed from the last matched character rather
than the character after the match — stayed green until the test asserted on
the excerpt's trailing ellipsis instead of on the excerpt's width. That is the
same lesson as the canonical tier's offset map, one level down: an assertion
about "contains" is an assertion about a window, not about the boundary.
Seen 1.

## An ambiguity the input cannot settle has to be carried, not resolved

**Rule.** When the extracted text genuinely supports two readings and nothing in
the bytes distinguishes them, do not pick one and call the other a mismatch.
Make the comparison accept both — in the direction that cannot invent evidence.

**Why.** A hyphen at a line end means typeset hyphenation in one paper and a
compound word broken across lines in the next.

    "the subsequent pro-\ncessing is assumed"    -> pro + cessing   (typeset)
    "a sequence of high-\ndimensional vectors"   -> high-dimensional (compound)

The extracted bytes of those two lines are the same shape. `normalize` joins,
which is right for the first and destroys a character of the second; an author
quoting the page as it is printed writes `high-dimensional` and got
`quote-missing` at high severity for a sentence that is on the page. That is the
worst thing this tool can say, and it was saying it about ordinary pages: 312
occurrences in a 20-page sample of real linguistics PDFs.

**How to apply.** Let the quote be tried in both spellings against the page as
the extractor settled it. Never strip the hard hyphens from the page as well:
`re-cover`/`recover`, `re-sign`/`resign`, `co-op`/`coop` are real pairs of real
words, and blinding both sides certifies a quote the page does not support.
The relaxation must be one-directional, and a mutation that makes it symmetric
must be the one the tests kill. The same reasoning governs the tier's test
suite: the four "different word" cases only exercise the direction if the quote
*and* the page carry a hard hyphen, so the first version of those tests passed
with the page blinded too — the guard was doing the work, not the tests.

**Evidence.** Measured 2026-11-01. Page `input in the form of a sequence of
high-\ndimensional vectors` against quote `a sequence of high-dimensional
vectors` gave `tier=none found=False` on 0.19.28; after the `hyphen` tier the
same pair gives `tier=hyphen found=True` while `They had to re-cover the roof.`
still refuses `they had to recover the roof`. Eight mutations, all red: tier
never runs, tier does not count as found, quote not blinded, **page blinded
too**, boundary check removed, number-slice guard removed, reason says nothing,
tier mislabelled. The page-blinding mutation stayed green on the first pass —
the tests that were supposed to enforce the direction only ran when the *quote*
carried a hyphen, so they never exercised the case where the direction matters.
Seen 1.

## A relaxation that removes both sides is a relaxation of the question

**Rule.** When you widen a comparison because two spellings might mean the same
thing, widen **exactly one** side, and keep the other side as the evidence. If
both sides get relaxed, you are no longer asking "could these be the same
statement" - you are asking "would they be the same if neither had said
anything", and every distinction the input carried has been deleted.

**Why.** The `hyphen` tier in 0.19.29 was written to stop `high-dimensional`
being refused against a page whose extraction said `highdimensional`. It removed
hyphens from the quote, then searched the page - which `normalize` had already
had the hyphens removed from, because joining the line break is exactly the
guess that caused the problem. Both sides arrived hyphen-free. So:

    page says  "we recover the sofa"    quote says  "we re-cover the sofa"   -> certified
    page says  "they will resign soon"  quote says  "they will re-sign soon" -> certified
    page says  "they reform the law"    quote says  "they re-form the law"   -> certified
    page says  "coop the birds"         quote says  "co-op the birds"        -> certified

Four real pairs of real words, four claims the page does not support. The
comment above the code said "the page is never stripped of hard hyphens, so a
page reading `re-cover` still cannot satisfy a quote reading `recover`" - which
was true of `_hyphen_blind` and false of the call site, because the call site
searched `page.folded`, the already-joined text. **The parity I documented was a
property of the helper, not of the comparison**, and no test I wrote asked the
question the comment answered.

**How to apply.** Ask which side holds the evidence and only ever relax the
side that is the *claim*. Here the page is the evidence; the quote is what must
be checked against it. The fix was to stop deleting anything and instead build
the page's *second reading* - `fold_keeping_hyphen`, the same normalisation with
the line-break hyphen kept - so the comparison reads:

    quote: "high-dimensional"  (as the author wrote it, untouched)
    page:  "high-dimensional"  (kept hyphen)   -> found
    quote: "re-cover"          (untouched)
    page:  "recover"           (no line break, so nothing to keep) -> refused

When two sides must agree, put the relaxation where it cannot delete the
distinction, and write the negative test as a **pair of real words** rather
than a synthetic string. `("the abcd-ef layer", "the abc-def layer")` is a test
that only fails when the code is symmetrically wrong; `("we recover the sofa",
"we re-cover the sofa")` is a test that fails when the code is wrong at all.

**Evidence.** Measured 2026-11-01 on 0.19.29. Auditing the tier I had shipped an
hour earlier: page `we recover the sofa` certified quote `we re-cover the sofa`
at tier `hyphen`, similarity 1.0; same for `resign`/`re-sign`,
`reform`/`re-form`, `coop`/`co-op`, and `man eating`/`man-eating`. After the
rewrite all six are `tier=none found=False` while
`high-\ndimensional` still matches a `high-dimensional` quote and
`pro-\cessing` still reaches `exact` as `processing`. Nine mutations, all
red, including one that restores the old behaviour verbatim
(`_HYPHEN_BREAK.sub("", out)` unconditionally) and one that makes the tier
search `page.folded` again. The mutation that matters most is the one that
would have caught this the first time: *quote is stripped instead of the page*.
Seen 1.

## When two paths must report the same thing, assert that they agree, not what they say

`check` scanned, then removed duplicate findings. `check --use-recorded` ran
the same verifier and printed its output unmodified. So one tree produced two
`number-absent-in-quote` lines in CI and one on the developer's laptop, for the
same claim and the same number: the `numbers` tier says "the words match but
the numbers do not" and the per-number check says "the quote says 40,688 but
page 1 does not contain that number". Both sentences are true and saying both
is not an error in either one - the error is that only one of the two callers
knew they were the same fact.

The fix is a shared `_deconflict`, and the fix is not the lesson. The lesson is
the test:

```python
fresh = codes(root, recorded=False)
recorded = codes(root, recorded=True)
assert [c for c in recorded if c[0] != "source-changed"] == fresh
```

Comparing the two paths **to each other** catches a divergence between them
without knowing in advance which finding was duplicated. Every test I would
have written from the bug report - "one `number-absent-in-quote` line in
recorded mode" - hardcodes an expected count and stays green the moment the
count changes for an unrelated reason. This one describes the property the bug
violated: *the same tree must be reported the same way*. It is also the only
assertion that would have failed on the day the bug was introduced rather than
the day it was noticed.

**Corollary, learned in the same session:** the dedup key was `(code, claim,
path)` and a comment justified the `path`. Deleting the `path` from the key
survived every test in the suite - the justification had never been tested, so
the comment was the only thing holding it up. Writing the test for the
documented reason ("two unreadable sources are two facts, not one fact twice")
killed that mutation immediately. A comment explaining why a key has a field is
not a test that the field is needed.

**Evidence.** 2026-11-01, found by comparing `check` against `check
--use-recorded` on the same project after replacing a source file. Recorded
mode printed three findings for two facts; fresh mode printed one for the same
evidence. Mutation A (recorded path skips the dedup) red on both new tests;
mutation B (key loses the path) green until
`test_the_path_is_part_of_what_makes_a_finding_duplicate` was written, then
red. The recorded path is the one `action.yml` uses, so this divergence reached
pull requests first. Seen 1.

## When a fact is a set, report the set, not its members

**Rule.** If one construct can produce several findings of the same code, and
every one of them carries the same line and the same path, they must be
aggregated where they are produced - not emitted one per member and left for a
downstream pass to sort out.

**Why.** `parse_bib` reports every finding for an entry at the line that entry
opens on. Three doubled fields (`title`, `year`, `author`) in one entry became
three findings sharing `(code, claim, path, line)`, and the duplicate pass -
which exists for a different reason, to stop the numbers tier and the
per-number check saying the same thing twice - kept the first and dropped the
other two. The author fixed `title`, re-ran, and met `year` for the first time,
then `author` after that. Nothing was ever misreported and no line said
anything untrue; the report simply took three runs to read once, and nothing in
it suggested that.

This is the inverse of the deduplication lesson and they have to be held
together. There, a pass that merged too much was fixed by giving the key more
dimensions. Here, the same pass merging findings that were only *positionally*
similar is a sign the producer is emitting the wrong shape. A deduplicator
cannot tell "these are one fact stated twice" from "these are two facts that
happen to share a coordinate"; only the producer knows.

**How to apply.** Report the set, the way `bib-key-unused` does. The tell that
you have this bug: a count in the message ("N findings") that the tool prints
once but that a reader experiences one at a time. Test it by asserting the
count of findings **and** the completeness of the surviving message - a test
that only checks `len(found) == 1` passes when the aggregate names one field
out of three.

**Evidence.** 2026-11-01, found by systematically checking every
`report(...)` call site for codes that can fire more than once per line: 13 call
sites in `bibtex.py`, all of them sharing `entry_line` for the same entry.
Measured before the fix: three doubled fields, `raw: 3`, `dedup: 1`. After:
`raw: 1`, naming `'author', 'title', 'year'`. Five mutations, five red - report
each again; name only the first; count values instead of fields; always say
"fields"; hoist the aggregation out of the per-entry loop. Seen 1.

## Fix the shape, not the instance

**Rule.** When you find that a finding-producing code collapses because
several findings share a coordinate, do not patch that code. Enumerate every
code in the module and ask the same question of each. The bug is in the
reporting shape, and the shape is shared.

**Why.** `bib-field-duplicate` was fixed by aggregating the doubled field
names per entry, and the fix was written up as a lesson about sets. The very
same module had `bib-macro-unknown` fifteen lines away with the identical
defect: a field using two undefined macros reported only the first, and two
fields each using one reported only the first field. Both were verified to hit
`raw: 2 / dedup: 1` before the fix. The first fix took one code from broken to
correct and left its twin broken in the same file, in the same function, under
the same `entry_line`.

The tell is that the previous lesson's How-to-apply already said what to do -
"report the set" - and it was applied to the finding in hand rather than to
the class of finding. A rule about a *shape* that is applied to one *instance*
buys one instance.

**How to apply.** After fixing a reporting-shape bug, grep the module for every
call site of the reporting function and classify each one by whether it can
fire more than once with the same `(code, path, line)`. In `bibtex.py` that was
13 call sites; the two that could were adjacent. The classification question is
mechanical, and it is much cheaper than the round trip through CI, a release,
and a user noticing.

**Second correction, same rule, one round later.** This lesson was written
after fixing `bib-macro-unknown`, and the commit that carried it said
`bib-field-malformed` was left alone because it could not fire twice. That was
checked by reading the code, not by running it: an entry with `badone,` then a
good field then `badtwo,` produces two fragments on the same line, and the
duplicate pass hid the second. **"I could not construct the input" and "the
input cannot be constructed" are different claims, and only one of them can be
settled by reading.** The third site is now fixed. The enumeration the rule
asks for has to be done by exercising each call site, not by scanning for
plausible ones.

**Evidence.** 2026-11-02, one round after the `bib-field-duplicate` fix, in the
same file. Measured: `journal = jalpha # jbeta` gave `raw: 2, dedup: 1` (only
`jalpha` survived); `journal = jalpha # jbeta` plus `publisher = pgamma` gave
`raw: 2, dedup: 1` (only the `journal` line survived). Fixed to one finding per
entry naming every field and macro. Five mutations: report per macro again,
report per field, name only the first macro, count the raw list instead of the
deduplicated set, and hardcode the plural - all red. A sixth mutation I wrote
first was an equivalent mutant (it recomputed a set that was already a set) and
proved nothing; distinguishing an equivalent mutant from a surviving one is
part of running them. Seen 1.

## A fix that makes the number of findings depend on the number of fields has one more field to be wrong about

`field_findings` reported a required field per finding. Every finding about an
entry carries that entry's opening line, and the duplicate pass keys on
`(code, claim_id, path, line)` - so an `@article` with only a `note` field
produced four findings and the author saw one. This is the fifth site in the
same file with the same shape, and the reason it stayed hidden is worth
recording: it is the only one whose count depends on the **entry type**.
`duplicate`, `macro-unknown` and `malformed` produce a bounded number of
findings per entry under any input. This one produces as many as
`REQUIRED_FIELDS[type]` is long, and the collapse only becomes visible at two
or more - which is exactly what an entry with a single typo does not have.

**Rule.** When a finding's cardinality is data-dependent rather than
structural, report the collection in one finding. The tell is a `for` loop
whose body appends a `Finding` at a fixed line: if the loop can run twice, the
second one is already lost.

**Why splitting "missing" from "present but empty" into two findings also
failed.** They are one coordinate: same code, same entry, same line. Two
findings there are two findings the duplicate pass will reduce to one, no
matter how different the repairs are. A message with two clauses is the shape
that survives.

**How to apply.** Enumerate the call sites by running each one, not by reading
for plausible ones - the previous lesson entry says this and this round added
a fifth site anyway. After aggregating, count: `raw` and `dedup` must be equal
for every entry shape, because if they differ the author is missing a line.
That assertion is the test, and it is the one that would have caught all five.

**Evidence.** 2026-11-02. Measured before: two entries missing four required
fields each gave `raw: 8, dedup: 2`, and the survivors were the two `author`
lines. A mixed entry (`author = {}`, no `journal`, no `year`) gave
`raw: 2, dedup: 1` after the first attempt at this fix, which is how the
split-findings version was caught before it shipped. Two mutations, both red:
report one finding per field again, and name only the first field in the
aggregated message. Seen 1.

## When two findings about one fact share a key, the first one written is the one that survives

The duplicate pass keeps the first finding it sees for a key and drops the rest, which is right for two producers saying the same thing and wrong for two sentences saying different amounts about the same thing. The `numbers` tier appended a summary - "the words match page 1 but the numbers do not; the quote records 11,111, 22,222" - and *then* the per-number findings. Both carried the claim's code and line, so the summary won and the author was never told which number was wrong. The specific sentence existed, was correct, and was discarded every time.

**Rule.** Order matters when the same key can be reached twice: write the most specific finding first and let the general one be the fallback, not the reverse. A summary that survives in place of a detail is worse than no summary, because it looks like the tool looked.

**Why a test did not catch it.** Each producer was tested alone, and each alone is correct. The defect only exists in the join, which is where dedup lives - so the test has to run both and read the surviving line, not count the lines.

**How to apply.** After adding any `result.findings.extend(...)` next to a `result.findings.append(...)` for the same claim, ask which one the dedup keeps and whether that is the one a person needs.

**Evidence.** 2026-11-01. Measured before the fix: the raw output listed the summary first (`the words match page 1 but the numbers do not; the quote records 11,111, 22,222`) and the specific line second (`the quote says 22,222 but page 1 of the source does not contain that number`); after dedup only the first remained. Two mutations, both red: name only the first absent number, and drop the specific list so the summary wins. Seen 1.

## Six instances of one shape is a request for a guard, not a seventh fix

The duplicate pass keys on `(code, claim_id, path, line)`. Six separate producers were emitting two findings under one key, and each was found the same way: run something, count the lines, notice the count was lower than the number of mistakes. Four in `bibtex.py` over three releases, two in `verify.py` in the next one. Fixing them one heartbeat at a time was fixing instances; the shape was still unguarded after the sixth, because nothing anywhere asserted the invariant the fixes were all about.

**Rule.** After the second fix of the same shape, write the assertion that would have caught both, before looking for a third. The assertion is usually cheaper than the fixes were: here it is one comparison - build a project carrying every known shape, then require the producer count to equal the writer count - and it needs to know nothing about any message.

**Why counting is the right invariant.** Each individual fix was verified by a test that read the surviving message and checked it named all its members. That test is right about the fix and blind to the next one: it only fails if *that* message loses a member. The count comparison fails for any site, including sites that do not exist yet, because it measures the property the dedup pass is supposed to have rather than the wording of any particular finding.

**How to apply.** When several producers can reach one report, assert the total, not the parts - and include a second test that asserts the fixture really does exercise every shape, or the count comparison quietly passes over a project that triggers none of them.

**Evidence.** 2026-11-01. `tests/test_one_finding_per_fact.py` builds one project carrying all six shapes and requires `len(set(keys)) == len(raw)`; eight mutations across the six sites are all red, including the two that had never been mutation-tested as a group. Seen 1.

## A question the code can answer exactly must not be answered by a different question

The `numbers` tier finds a quote by blanking every number on both sides and comparing the text. That comparison knows, at the moment it succeeds, which of the page's numbers fell into the positions the quote's numbers occupy. The verifier did not ask it. It re-read the page, collected every number on it into a set, and asked "is the quote's number anywhere here?" - a different question, with a different answer, and the one it answered was the forgiving one. A quote that borrowed a number from the very next sentence therefore reached the fallback and was told `the numbers do not` about a number four lines down the same page.

**Rule.** When one stage computes a precise relation and a later stage needs it, carry the relation. Do not let the later stage re-derive a weaker one from the raw input. The weaker question is not a simplification - it is a different question, and it will be answered confidently in cases where the precise one would have said something else.

**Why this is worth a lesson of its own.** Every check in this project is "does the artifact agree with the page", and the failure mode that matters is a *false accusation*: telling an author their quote is wrong when it is not. A weaker re-derivation does not fail loudly; it produces a sentence that is grammatically perfect, cites a real code, and is simply not true of the file the author is looking at. The author's only recourse is to stop believing the tool.

**How to apply.** After a match succeeds, ask what the matching pass learned on the way that the caller is now guessing at. If the answer is a value - an offset, a page list, a slot mapping - put it on the result object even when only one caller needs it. Then write the test that would fail if the caller guessed instead: here, one page printing the quote's number in another sentence must not be reported as a page that lacks it.

**Evidence.** 2026-11-01. Measured before the fix: page `We collected 40,688 examples for training. The held-out set of 9,800 rolesets was annotated separately.`, quote `We collected 9,800 examples for training.` gave `[high] number-absent-in-quote ... the words match page 1 but the numbers do not; the quote records 9,800`, exit 1 - while `9,800` is printed on page 1. The tier had computed `page_numbers == ('40,688',)` and dropped it. Seven mutations, all red: record nothing, read the page's first N numbers instead of the ones under the blanks, name every number rather than the ones that differ, disable the new code, restore the old sentence, and soften the severity. Seen 1.


## A mutation that survives is a claim about the code, not only about the tests

The `pasted` tier began as two mechanisms: fold the page's line breaks to `- `, and then collapse the remaining hyphen-space pairs on both sides while carrying an offset map so the excerpt could still point at the printed page. Four of seven mutations survived - including "stop collapsing the space" and "ignore the offset map". The reflex reading is "the tests are too weak". The right reading was that the second mechanism was dead: because `fold_pasted` already rewrites the page's line breaks to the same `- ` shape the reader's clipboard produces, both sides of the comparison are character-identical, so there is no space left to collapse and no offset to remap.

**Rule.** When a mutation survives, first ask whether the code it disabled does anything. Delete the mechanism and re-run the whole mutation set; if every mutation is now red, the survivor was never a missing test. Only write the missing test when the mechanism turns out to be load-bearing and merely unobserved.

**Why this is not the usual "write more tests".** A surviving mutation has two possible causes with opposite remedies: an unobserved behaviour, or an unexercised mechanism. Writing tests for the second case cements the redundancy - the suite then fails if a later reader removes code that no input needs, which is exactly the wrong pressure. The second case is cheaper to settle than the first, too: delete, re-run, read the answers.

**How to apply.** Keep the mutation list as one script so it can be re-run in one command. When a mutation survives, delete the mechanism it targets, run the full list again, and only then decide which of the two cases you are in. Record the outcome either way; here the deletion removed `_unspaced`, its `_PASTED_GAP` pattern and an offset remapping, and the seven mutations went from four survivors to none.

**Evidence.** 2026-11-02. First run over `tests/test_pasted_tier.py`: 3 red, 4 green. After deleting the collapse-and-remap mechanism and simplifying the tier to compare `fold_pasted(page.text)` against the quote directly: 7 red, 0 green, `survivors: none`. The deletion also removed the only reason the excerpt needed an offset map, so a later reader cannot reintroduce half of it. Seen 1.

## A feature nobody exercises is a feature nobody has run

`draft` shipped in 0.14.0 and had tests. Every one of them wrote the citation marker before the full stop - `usage [@p].` - because that is the shape the tests were written around. Pandoc also accepts `usage. [@p]`, which is what comes out when a citation is added at the end of a finished sentence, and for that shape the sentence splitter returned the *next* sentence (or `[@p].` when there was none). `draft` then proposed a quote for a sentence the author never cited and backed it with that paper's file. Over the 71 usable papers in a real corpus it proposed nothing at all for the common shape, and 46 of 46 once the splitter was fixed.

**Rule.** Before believing a feature works, run it on real input in every spelling the surrounding format allows - not just the one the tests were born with. A green suite measures the shapes it contains.

**Why the tests did not catch it.** They were not wrong; they were narrow in a way that is invisible from inside the file. Each test picked a plausible manuscript, and all of them happened to pick the same placement because that is how the author of the tests writes. Nothing in the suite asserted "every accepted placement behaves the same", so a placement nobody typed was a behaviour nobody checked - and the failure is not a crash but a confident, wrong answer.

**How to apply.** When a feature reads a syntax that has several accepted spellings, enumerate the spellings from the format's documentation and make each one a test case before adding a fourth. For this project the list is short and worth keeping written down: marker before the full stop, after it, alone on its line, in its own paragraph, at the start of the document, and the LaTeX forms.

**Evidence.** 2026-11-02. Before: over 71 usable PDFs, `draft` proposed 0 claim blocks for the `sentence. [@p]` shape and reported `nothing on any page shares enough terms with the sentence (3 needed)` for all 47 that had a sentence. After: 46 proposals, 46 accepted by `check`, 0 rejected, 1 paper with no proposal. Five mutations, all red: the prefix rule never runs, the paragraph lookback never runs, the lookback always walks back, the prefix is measured from the paragraph, and a marker-only run counts as a sentence again. Seen 1.

## A field that is populated is not a field that is compared

``Claim`` has carried ``text`` since the first version, and ``verify`` has carried a number check since shortly after; the two never met.  ``claim.numbers`` is built from the quote, so every comparison used the quote against the page and nothing ever compared the claim against the quote.  A run whose claim said ``80,688`` and whose quote said ``40,688`` printed ``[info] quote-found``, ``worst severity: info`` and exited 0.

**Rule.** For every field on a parsed record, name the code that reads it.  A field with no reader is either dead - delete it - or a comparison that was never written.  Adding the field is the half of the job that feels like work; wiring it into a decision is the half that produces the verdict.

**Why reading the type is not enough.** ``Claim.text`` looks used: it is in the dataclass, it is on the ledger, it round-trips through json, and ``report`` prints the excerpt that contains it.  All of that is transport.  The defect is invisible to every question of the shape "is this field handled" and visible only to "what compares it", which is why it survived a mutation-tested verifier and 1053 tests.

**How to apply.** ``grep -n "claim.text" src/`` is the whole investigation.  Run it for each field of each record type after adding one, and treat a hit that only serialises as a miss.  Then write the end-to-end test that fails when the comparison is removed - here, a claim one keystroke from its quote must exit 1.

**Evidence.** 2026-11-02.  Before: page ``We collected 40,688 examples in the corpus.``, quote exact, claim ``We collected 80,688 examples.`` -> ``1 claim - 1 verified``, exit 0.  After: ``[high] claim-number-differs at m.md:1 (c1): the claim says 80,688 but its quote says 40,688``, exit 1.  Eight mutations, all red, including the two that survived the first pass (drop the length guard, and let an agreeing number be measured against its neighbour) - both were real gaps, not dead code.  Seen 1.

## Four guards that overlap are one guard and three decorations

``claim-number-differs`` shipped with four conditions that had to hold before it
would report anything: the pair is one keystroke apart, neither number is a year,
at least one is written as a quantity, and the claim's number is not printed
anywhere on the cited page.  Six tests covered the behaviour and all six passed -
and then every single guard survived deletion.  The year shape also named a
quantity; the quantity shape also failed the year test; the page shape was
satisfied by two of the other three.  A mutation run reported ``survivors: none``
only after each shape was rebuilt so exactly one guard stood between it and a
false accusation.

**Rule.** One test per guard, and each test's input must fail on that guard alone.
A guard whose removal no test notices is not defended by the tests that cover the
feature - it is defended by nothing, and it will be deleted by the next person who
reads it as redundant.

**Why the obvious test cannot do this.** The natural way to test a rule with four
guards is one test per bad outcome, and every such input trips whichever guards it
happens to trip.  Coverage looks complete because the outcome is covered; the
guards are not.  Attribution needs input built from the guards' definitions - for
the year guard, a pair that is one keystroke apart, four characters, written with
separators and absent from the page, so only the year test can stop it.

**How to apply.** Delete each guard on its own and require the suite to go red.
When one survives, do not add an assertion to the existing test - construct the
shape that isolates that guard.  Where no such shape exists, prove the reachability
question rather than guessing: enumerating the 650,806 spellings the number grammar
can produce is what showed the length guard was not dead after all, because exactly
one quantity - ``1%`` - canonicalises to a single character.

**Evidence.** 2026-11-02.  First mutation run on the shipped rule: year guard,
quantity guard, page guard and length guard all green, only ``near miss never
fires`` red.  After building four isolating shapes plus a positive control: five of
five red.  The length guard's reachability was settled by exhaustive enumeration,
not by reading the code, which is what kept a live guard from being deleted on the
strength of an argument.  Seen 1.

## Two zeros are one zero until you write down which is which

``draft`` summarised every run as ``N claim block(s) proposed (M verbatim), K citation(s)
left as comments``.  A manuscript with no citations at all produced ``0 ... (0 verbatim), 0
citation(s) left as comments``, and so did a manuscript whose single citation pointed at a
file that was not on this machine.  The second zero is about the machine and is the author's
problem to fix; the first is about the reading and is almost always ours, because a citation
written ``(Van Eecke 2026)`` is invisible to a parser that only knows ``[@key]`` and
``\cite{key}``.  Both runs then gave the same advice: open the file and see what it got wrong.

**Rule.** When two different causes can collapse into the same count, the count is not a
summary - it is a coincidence.  Carry the cause, not just the tally, and let every printed
sentence that depends on it know which cause it is describing.

**Why the arithmetic hides it.** ``0 + 0 == 0`` is true for both, so every downstream total,
rate and ratio agrees with itself.  The defect is invisible to any check written against the
numbers and visible only to a check written against the sentence the numbers produce.  That is
why it survived the tests: they asserted ``proposed == 0``, which was correct in both worlds.

**How to apply.** For each zero a command can print, name the two inputs that produce it and
ask whether the next sentence the user reads would be true in both.  Then write the test as a
difference between the two runs, not as a property of either - here, one test that the no-
citation run does not print the advice, paired with one that the missing-file run still does.

**Evidence.** 2026-11-02.  Before: ``draft`` on a marker-free draft and on a draft whose one
marker pointed at ``hempel2020nowhere`` both printed ``0 claim block(s) proposed (0 verbatim),
0 citation(s) left as comments`` and both exited 0.  After: the first prints ``no citations
were found to propose them for (this command reads `[@key]` and `\cite{key}`)`` and replaces
the advice; the second is unchanged.  Four mutations, all red.  Seen 1.

## A check that asks whether the input exists has not asked whether the input is any good

`doctor` reported `[ok  ] manifest    sources.toml (148 bytes)` and closed with "Everything this
tool needs is on this machine."  The check was `candidate = root / name; if candidate.is_file()`.
A manifest that would not parse, one whose every key pointed at a path that is not on this disk,
one that named a directory, and two manifests sitting side by side all produced that same line and
exit 0 -- and the next command printed `[high] source-missing` on every claim, which is the exact
failure `doctor` exists to explain.  A file's size is not a fact about whether it points anywhere.

**Rule.** When a check's subject is "can this project run?", the question is not whether the inputs
exist but whether they resolve.  Existence is the cheapest possible stand-in for the real question
and it is wrong in the one direction that matters: it goes green on exactly the inputs that look
fine and are not.

**Why the earlier version survived.** Nothing that ran agreed with the next command.  The check was
tested against projects where the file was absent, which is the case the stand-in does get right;
the failure modes all have the manifest present and its contents useless.  The strongest signal
available was "run `doctor` on the same broken project the other tests run `check` on, and require
the two commands to disagree about nothing" -- and that comparison did not exist until this round.

**How to apply.** For every check that answers a question about a file, write down what the *next*
command does with that file, then write one test that runs both on one broken project, and require
the story to agree.  Then check the check's own fixture: ours named `a.txt` in `sources.toml` and
never wrote `a.txt`, so three "everything is fine" tests were passing only because the check did
not look.

**Evidence.** 2026-11-02.  Before: four distinct broken projects each printed `[ok  ] manifest` and
exited 0.  After: they print `[FAIL] manifest` with the reason (unparsable TOML, two manifests, a
directory, or the missing keys named) and exit 1, while `--root demo` still reports `2 sources,
every one of them present on this machine` and exits 0.  Eight mutations; one of them -- truncating
the list of missing keys to its first element -- survived the first run because the only test with
an unusable entry had exactly one of them, and a length-one list cannot fail a test about lists.
A second survived because nothing asserted the byte count the message exists to offer about a file
whose contents it could not read.  Both red after adding the two shapes.  Seen 1.

## A sentence about the wrong noun is a false sentence

`doctor` reported `[FAIL] manuscript  <path> does not exist` for a path that is a directory. The
check was `if target.is_file(): ... else: "does not exist"`, so every way a path can fail to be a
file collapsed into the one that says nothing is there. `citevouch check` on the same path said
`is a directory, not a file`. Two commands, two stories about one path, and the false one came
from the command that exists to explain the other.

**Rule.** `not is_file()` is not a diagnosis. It is true of a directory, a broken symlink, a
Windows share that is not mounted, and a file the process may not stat - four situations whose
next steps share nothing. If the tool already has a function that turns a path into a sentence,
that function is the answer; reaching for `exists()` beside it is how the tool ends up arguing
with itself.

**Why the tests missed it.** The manual test asked the question the check was written for: a
missing manuscript is a file that is not there, and `does not exist` is true of it. Nothing ran
the two commands on one path and compared the stories. That comparison is the only test that
covers every failing shape at once, because it is written against agreement rather than against a
list of cases - and every case this file has ever produced came from a shape nobody enumerated.

**How to apply.** When a command explains another command's failure, write one test that breaks a
project in one way and runs both, and require them to mention the same thing. Do not write it as
"`doctor` says X"; write it as "what `doctor` says is in what `check` said". Then check the fix
line, not just the detail: our first version branched to a directory-specific fix but the test
passed without the branch, because the generic fix also ends in `manuscript.md` and nothing asked
which directory the path belonged to. A fix that names a path the reader did not pass is only
slightly better than no fix.

**Evidence.** 2026-11-02.  Before: `doctor --root _dk --manuscript adir` printed `[FAIL] manuscript
_dk\adir does not exist` and `check _dk/adir` printed `manuscript _dk\adir is a directory, not a
file`. After: both say `is a directory, not a file`, the fix line names `_dk\adir\manuscript.md`,
and exit is 1. Three mutations; the second - "the directory gets the generic fix" - survived the
first run for exactly the reason above, and went red once the test asserted the path came from the
argument. Seen 1.

## `doctor` is not allowed to be more optimistic than the command it explains

`check paper.tex` refused the file with exit 2 and said claim blocks live in Markdown, not in a `.tex`
file. `doctor --manuscript paper.tex` printed `[ok  ] manuscript  paper.tex (69 bytes)`, closed with
"Everything this tool needs is on this machine." and exited 0. The reader who does the sensible thing
- run the diagnostic before trusting the report - was told the machine was fine about an input the
next command will not read at all.

**Rule.** A diagnostic may only be optimistic about things the work command agrees with. Every check
in `doctor` either reports a fact that is true regardless of the manuscript (an extractor exists, the
cache is writable, the interpreter is new enough) or a fact the next command also tests. When it
answers a question the work command also answers, both must use the same predicate - not two
implementations that happen to agree today.

**Why this keeps happening.** `doctor` was written before the scanner learned to refuse `.tex`, and
nothing connected them afterwards. The two checks were built months apart by the same agent and share
no code, so the later refusal never reached the earlier report. Three rounds of this file have now
ended the same way - manifest existence, directory-as-manuscript, `.tex`-as-manuscript - and every
one was found by running both commands on one input rather than by reviewing either.

**How to apply.** For each line `doctor` prints, ask "does the command it is explaining say something
about this too?", and if so import that command's predicate instead of re-deciding. Then write the
test as agreement: break one input, run both, require the words to overlap. A test that asserts what
`doctor` says is a test of today's wording; a test that asserts what it says is among what `check`
said covers the shapes nobody listed.

**Evidence.** 2026-11-02.  Before: `doctor --root _dt --manuscript paper.tex` printed `[ok  ]
manuscript  _dt\paper.tex (69 bytes)` and exited 0, while `check _dt/paper.tex` exited 2 with
`manuscript ... is LaTeX, and citevouch reads claim blocks`. After: `[FAIL] manuscript ... is LaTeX,
and this tool reads claim blocks, which live in Markdown, not in a .tex file`, exit 1, with a fix
that names `citevouch draft paper.tex -o claims.md`. Four mutations, all red. Seen 1.

## A diagnostic's list of checks is a claim about what can go wrong

`doctor` printed six lines and closed with "Everything this tool needs is on this
machine." A manuscript with no claim blocks passed all six, and the next command
reported `no-claim-blocks` (high) with exit 1. The one file whose emptiness makes the
whole run meaningless was the one thing the diagnostic never looked at.

**Rule.** When a command exists to explain a silent failure, every way that failure
can arrive silently belongs in its list. Not the ways that are hard to check - the
ways that produce no output at all. And the list must be written by asking "what
makes the next command find nothing?", not "what does the machine need?".

**Why this kept happening.** Four rounds in a row fixed the same shape in this one
file: is the file there, does the manifest name files that are there, is the file
Markdown, does the file hold anything. Each time the check answered a narrower
question than the sentence printed above it. `doctor` was written from the machine
side - extractor, cache, interpreter - and the project side was bolted on later,
so it inherited the machine side's optimism without its completeness.

**How to apply.** Enumerate the silent failures from the work command's side: run it
on every empty-ish input you can build and list what each one prints and returns.
Then require `doctor` to say something about each. Import the predicate rather than
restating the condition - the reason `doctor` missed this is that `scan` and
`verify` both had the condition typed out separately, so a third reader could be
written without ever meeting it. It is `ParseResult.nothing_to_check` now.

**Evidence.** 2026-11-02. Before: `doctor --root _dn --manuscript manuscript.md`
printed `[ok  ] manuscript  _dn\manuscript.md (76 bytes)` and the closing
reassurance, exit 0, while `check _dn/manuscript.md --root _dn` printed `[high]
no-claim-blocks` and exited 1. After: `[FAIL] claims  _dn\manuscript.md holds no
claim blocks, so every run will report 0 claims checked and exit 0`, exit 1, with
the `citevouch draft` fix. Six mutations, all red. The test fixture's own manuscript
was `# t` - a file with no blocks - which is why this went unnoticed: the fixture
was the bug. Seen 1.

## A lockfile is an input, and an input is untrusted even when your own tool wrote it

`Ledger.from_json` trusted every field. A lockfile edited by hand, truncated by a
bad merge, or written against a shape this version no longer writes raised
`AttributeError`, `TypeError` or `ValueError` straight out of `main`. Twenty
damaged shapes were run through `report`, `verify` and `check --use-recorded`:
sixty crashes, and every one exited **1** — which in this tool means "findings
reached the threshold".

**Rule.** A file the tool wrote is still a file the user can edit, version control
can merge, and another build can write. Parse it the way you parse anything else
you did not create in this process. The question is not "who produced this?" but
"what is the worst a truthful reader can be handed?".

**Why the reasoning was already in the file and still not applied.** `_read_ledger`
had refused a too-new *schema number* since the first release, in words that fit
the crash exactly: "Reading a future ledger with today's parser would half-parse
it: fields the next version added or renamed would come back empty, and
`source-missing` on a half-read claim is the false verdict this tool exists to
avoid." The same sentence covers a null element in `claims` and a string where a
count belongs. Schema versioning was seen as *the* compatibility question, so the
shape of the file never came up — and the guard covered the one case that had a
number attached to it.

**How to apply.** Two questions, in this order. First: which exit code does this
failure produce, and does that code already mean something else? A crash exits 1 for
free, and 1 is the answer this tool gives to "should this manuscript be blocked", so
a crash is a verdict the author did not earn. Second: enumerate the shapes, not the
cause — write a table of hand-built damaged values (`null`, `"x"`, `5`, `[]`, a float
where an int belongs, a string where a list belongs) and run every verb that reads
the file over every one. Hand-writing the table found twenty shapes that reading the
parser had not suggested.

**Where refusing is wrong.** Two shapes needed a narrower rule than "must look like
what we write". `claims: null` is refused rather than read as an empty ledger —
"nothing to verify" is a clean run for a manuscript whose evidence was thrown away.
But `claims: []`, a missing `tool_version`, a `page` written as `"7"` and a missing
`fields` all still read: a guard that refuses a file the *writer* produces would be
worse than the crash it replaced. So the suite round-trips a real `scan` output
through `from_json` and asserts the two are equal. A guard is only correct if you
have also measured that it lets the legitimate input through — the negative cases
prove it fires, and only the round trip proves it does not fire at the wrong time.

**Evidence.** 2026-11-02, before and after, measured on the same twenty shapes
through the three verbs. Before: `claims: [null]` → `AttributeError: 'NoneType'
object has no attribute 'get'`, exit 1; `entries: {"k": {"fields": 5}}` →
`AttributeError: 'int' object has no attribute 'items'`, exit 1; `claims: [{"id":
"c1", "numbers": 5}]` → `TypeError: 'int' object is not iterable`, exit 1. After:
each one prints `citevouch: citevouch.lock.json: ledger claims[0] must be an
object, not NoneType` and exits 2. Nine mutations, eight red; the survivor is
equivalent — the type guard above it makes the old coercion unreachable, which is
why that guard carries its own parametrised case. `tests/test_damaged_ledger.py`,
126 tests, released as 0.19.48. Seen 1.

## The handler catches the exception the author predicted, not the one the parser raises

`_read_ledger` wrapped `json.loads` in `except (OSError, ValueError)` because that
is what malformed JSON raises. A lockfile of twenty thousand nested brackets is not
malformed — every bracket is balanced — and the same call raised
`RecursionError: Stack overflow (used 2912 kB) while decoding a JSON array from a
unicode string`. `RecursionError` is a `RuntimeError`, not a `ValueError`, so it
left `main` untouched and the interpreter exited **1**: the identical false verdict
as the twenty damaged shapes fixed one release earlier, arriving through the parser
instead of through a key.

**Rule.** When you guard a call into someone else's parser, ask what that call can
raise — not what the input you have in mind makes it raise. `json.loads` has three
distinguishable failure modes (syntax → `ValueError`, decoding → `UnicodeDecodeError`,
depth → `RecursionError`) and the handler named one of them. A broad `except Exception`
would have hidden the traceback the tool needs; naming the exceptions means the list
has to be complete.

**Why the shape guard did not prevent this.** The same round that added `_object`,
`_section`, `_whole` and `_texts` made every *value* safe to read, and I checked that
by enumerating damaged values. None of them was a file that decodes to a value at all.
The two failures look unrelated — one is "an element is a string where an object
belongs", the other is "the file is too deep to parse" — and they are the same bug in
different layers: an input this code cannot read in full, reaching the interpreter as
an uncaught exception instead of as a refusal.

**How to apply.** For every third-party parse, mutate the *input bytes* one axis at a
time (truncated, unbalanced, balanced-but-deep, wrong encoding, empty) and watch the
exit code, not the traceback. Here the axis that mattered was "valid JSON, unusable
depth" — invisible to a table of damaged Python values, obvious to a table of damaged
files.

**The false red.** The first mutation run reported both mutants red. They were not:
the harness spawned `pytest` in a subprocess with a hand-built environment and got
`No module named pytest`, which is a non-zero exit, which the harness called RED. A
verification that cannot tell "the guard failed" from "the harness failed" verifies
nothing — the same defect as a test that cannot fail, one level up. The harness now
raises when its own run is broken instead of scoring it.

**Evidence.** 2026-11-02. Before, on the same file: `RC=1`, stderr ending
`File "C:\Python314\Lib\json\decoder.py", line 361, in raw_decode` /
`RecursionError: Stack overflow`. After: `citevouch: ledger ... is not readable JSON:
it nests too deeply for the standard library parser, which no citevouch ledger does`,
exit 2, at both 20000 and 200000. Five tests in `tests/test_damaged_ledger.py`
(`TestANestDeepEnoughToBreakTheParser`), one of which subprocesses the real CLI to
assert no traceback reaches stderr. Two mutations, both red once the harness stopped
lying. Released as 0.19.49. Seen 1.

## A count must count what the reader can see, not what the code happened to accept

**Rule.** When a message reports *how many* of something are in a file, count the
things the file holds - not the subset the current parser accepted. If those two
numbers can differ, the message has to say so and explain the gap.

**Why this keeps happening.** Two counts sit next to each other in `ParseResult`:
`claims` (what parsed) and `spans` (what was seen). The whole tool is written from
the first one, because everything downstream works on claims it can reason about,
so `len(parsed.claims)` looks like *the* count of claim blocks. It is the count of
claim blocks this run could use. For a report to the author those are different
facts, and the difference is exactly the thing the author needs to know.

**How to apply.** Before writing `count_of(len(...), noun)` into a message, ask what
the reader will compare it against: the file they are looking at, or the run that
just finished. If they will look at the file, count the file. And when the two
numbers can differ, print both and name the reason - `2 claim blocks, 1 of which
the parser could read; the next command names the rest` - because a bare count that
disagrees with the next command's count is worse than either number alone.

**Evidence.** 2026-11-02. A manuscript with one good block and one that forgot
`id=` reported `[ok  ] claims      1 claim block` from `doctor`, while `check` on
the same file reported `[high] claim-uncheckable` at the refused line and
`1 claim - 1 verified`. Measured `parsed.claims=1, parsed.spans=2`. After the fix:
`2 claim blocks, 1 of which the parser could read; the next command names the
rest`, and a clean two-block file still says `2 claim blocks`. Five tests in
`tests/test_doctor.py` (`TestTheCountIsWhatTheFileHolds`); three mutations, all red
- the shipped line, the sentence without its explanatory half, and the sentence
applied to files that do not need it. Released as 0.19.50. Seen 1.

## A block a tool tells you to paste must be pasteable

**Rule.** When a command emits something the user is instructed to combine with
an existing artifact, every name in the emitted piece has to be unique against
the artifact it will be combined with. The tool knows the artifact - it just read
it - so a collision it hands over is a collision it created.

**Why this one is easy to miss.** `draft` reads the manuscript for citations and
never looked at the manuscript's claim blocks, because a block is not a citation
and the function that collects citations has no business collecting blocks. Each
half is right on its own: `_claim_id(key, used)` de-duplicates against the ids
*it* handed out, which is a complete set of its own output and an empty set
against the file. The defect lives in the seam between two correct functions,
and the instruction that crosses the seam - "read it, then `citevouch check
proposals.md`" - is what makes the seam load-bearing.

**How to apply.** For any command whose output is meant to be merged, ask what
the merge target already contains and seed the generator with it. Then test the
merge, not the pieces: the assertion that matters is placing the output into the
target and running the command that judges the combination. A test that compares
the emitted id against a literal cannot see this - it passes for the wrong id too.

**The other direction.** Seeding a set is not the same as using it. `used_ids =
set(taken_ids or ())` must still *grow* inside the loop, or two citations of one
key start colliding with each other in a file that has no blocks at all - which
is the case that used to work, so the regression would look like a new bug in a
different command. One test seeds the set and asks for two proposals; a mutation
that keeps the seed but drops the loop fails it.

**Evidence.** 2026-11-02. A manuscript holding `id=paper` plus one more sentence
citing `[@paper]` got a proposal labelled `paper`; appending it - the only thing
`draft` tells you to do - produced `[high] claim-uncheckable ... claim id 'paper'
is used twice (first at line 3); the ledger cannot track both, so the second is
ignored`, and the ignored block was the one just added. After the fix the proposal
is `paper-2` and `check` on the merged file exits 0. `tests/test_draft_claim_ids.py`
(8 tests); four mutations, all red, including one that reads only the first
existing id - invisible on a one-block fixture, which is why the fixture now holds
two blocks and the colliding key is the second one. Seen 1.

---

## A guard against overwriting your inputs protects every input, not the one you were thinking about

**Rule.** When a command writes to a path the user names, the guard has to compare
that path against every file the run reads - and against the names it would read
if they existed. A guard that protects one of them is a guard against one mistake.

**Why this keeps happening.** `draft` learned to refuse `-o manuscript.md` after an
author's paper was replaced with proposals, and the fix was written as "is the
output the manuscript". That sentence is about one file, and it reads as complete
because the danger it describes is vivid. The other inputs - the manifest that
says which file backs each key, the bibliography, the ledger that holds what every
quote was checked against - are named inside the function that reads them, not in
the argument list, so they are invisible from the place where outputs are
approved.

**How to apply.** Enumerate the inputs from the code that opens them, not from the
command's help text: every path argument, every default path the other commands
read, and every name that would change the meaning of the project if it appeared.
Then assert on the file's bytes after the refusal - a guard that returns the right
exit code after writing is not a guard. When a name does not exist yet, ask
whether *creating* it changes what the project means: `sources.json` beside a live
`sources.toml` overwrites nothing and makes every claim unresolvable, because two
manifests are refused rather than guessed between.

**The other direction.** Do not let the guard leak into the commands that must
write those files. `scan` writes the ledger on purpose; a version of this rule
that refused every writer would leave the tool unable to record anything at all.

**Evidence.** Measured before the fix, in a project where `check` said `1 claim -
1 verified`: `-o sources.toml --force` exited 0 and printed `wrote sources.toml`,
then `check` said `[high] source-missing ... the manifest could not be read:
sources.toml could not be read as TOML` and `doctor` said `2 of 6 checks failed`.
`-o citevouch.lock.json --force` exited 0, then `verify` said `ledger
citevouch.lock.json is not readable JSON`. `-o refs.bib --force` with `--bib
refs.bib` and `-o papers/p2.txt --force` with `--source papers/p2.txt` both wrote
through. Three mutations, all red - the guard not called at all, only the existing
manifest protected, and the ledger dropped from the list.

Seen 1.

## An argument every command resolves against is validated once, where it is still one value

**Rule.** A flag that other paths are resolved against is an input like any other, and it is
checked before the first command runs - not by each command, and not by whatever writes the
first file. If the value is wrong, every verb's answer is about the wrong thing, and no verb can
tell.

**Why this keeps happening.** `--root` was read as a convenience default rather than as data:
every verb did `Path(args.root) / something`, and a path that does not exist still joins happily.
Nothing in the codebase *looked* at a root, so nothing was the place to check one - which is how
one typo produced four different failures at once: `scan` created the directory and wrote into
it, `doctor` created a cache in it, `draft` wrote proposals into it, and `check` reported the
manifest missing while that manifest sat next to the manuscript. The first three are side
effects; the fourth is a false sentence, which is the one this repository treats as the real
defect. A guard inside `cmd_check` would have fixed exactly one of the four.

**How to apply.** Ask which arguments are *prefixes* - roots, base directories, output
directories - as opposed to leaf paths. Prefixes are validated once, in `main()`, before dispatch
(`_project_root`), and the check is on the whole value, not on each later use. Then ask what the
same mistake does to the verbs that write: if the answer is "creates something in the wrong
place", the guard must be earlier than the write, not inside it. Note the exceptions honestly:
`init-demo` takes a directory to create and has no `--root`, so the call is guarded by
`hasattr(args, "root")` rather than being unconditional.

**Evidence.** Before: `scan proj/m.md --root nowhere` → `citevouch: wrote
nowhere\citevouch.lock.json (1 claim)`, and `nowhere/citevouch.lock.json` existed afterwards;
`doctor --manuscript proj/m.md --root nowhere` → `nowhere/.citevouch/cache` created;
`draft proj/m.md -o q.md --root nowhere` → RC=0 and `nowhere/q.md` written;
`check proj/m.md --root nowhere` → `[high] source-missing ... no entry in sources.toml` in a
project whose `sources.toml` was beside the manuscript. After: all six verbs exit 2 with
`--root nowhere does not exist ...`, and `find nowhere` → nothing. Four mutations red: the guard
never called, a missing root allowed through, a file root reported as missing, and the message
dropping the default-root advice. `tests/test_root_guard.py`.

Seen 1.

## An error message that lists cures is a diagnosis with the names filled in

The four ways a source file can yield no text are one machine problem and three file problems, and
the tool had one sentence for all four. `could not extract text from paper.pdf; install pypdf
(pip install pypdf) or pdftotext and try again` - printed on a machine where `citevouch doctor` had,
one command earlier, reported `[ok  ] pypdf 6.16.1 (reads PDFs in-process)`.

The sentence is not wrong about the machine. It is wrong about *which problem this is*, and the
correction it offers is one the author has already performed, so the only thing left to do with it
is disbelieve the tool.

**Why the facts were available and still lost.** Both readers had said the true sentence and both
were told to throw it away. `_pypdf_pages` turns every exception into `None`; `_pdftotext_pages`
does the same with any non-zero exit. That is the right contract for a *verdict* - a corrupt PDF is
a finding, not a crash - and the wrong contract for a *message*, which is why the four causes
collapsed into one. `except Exception: return None` is a correct policy that deletes the only
evidence the caller needs.

**How to apply.** When a function's failure return type carries no reason, ask who needs the reason
and whether they can afford to ask again. Here the failure path can: `_why_both_refused` re-opens
the file with both readers and quotes them (`PdfStreamError: Stream has ended unexpectedly`;
`pdftotext: Syntax Error: Couldn't read xref table`), and the success path never calls it - there is
a test that counts the calls on a successful read and asserts zero. Threading a reason *out*
instead would have meant a return type change in five places or module-level mutable state, and
mutable module state leaks one file's reason into the next file's message inside a single `check`
run. Prefer re-deriving a fact over caching it in a place that outlives one call.

**The near miss worth remembering.** The first version of the fix was right and the first version
of its tests was too weak: a message carrying one true reader's sentence still differed from the
old false one, so every end-to-end test passed while `pdftotext is not asked what it saw` survived
the mutation run. The fix is a test that drives the second reader directly with a stubbed
`subprocess.run`, rather than depending on which binaries the machine happens to have.

**Evidence.** Before, four files - a real PDF cut to 40,000 bytes, a text file named `.pdf`, a
zero-byte `.pdf`, and a 16-byte stub - all produced the identical `install pypdf ...` sentence and
none of them differed from each other. After, three distinct messages naming the reader and its
words, and the no-reader case names both ways to get one. Six mutations, all red after adding the
direct-reader tests: the old one-sentence message, the readers never asked, the machine always
blamed, the failure path asking even when it succeeds, pypdf not asked, pdftotext not asked.
`tests/test_unreadable_reason.py`.

Seen 1.

## Scratch data and durable data fail in opposite directions

The extraction cache and the ledger are both JSON files this tool writes into a project, and they
must not be handled the same way. `Ledger.from_json` refuses a shape it does not recognise, loudly,
with the file named - because a ledger is *the record* of what the author claimed against which
source, and nothing else can reconstruct it. The cache is *a hint* about what some reader produced
for these exact bytes; the bytes are still in the project, so the hint can be thrown away and the
fact recomputed.

Both were written the same way instead: trust the shape, read it. The cache then exited **1** with
a traceback on `{"pages": 5}` - and 1 is the code that means "findings at or above --fail-on", so a
scratch file could manufacture the one signal the tool exists to produce.

**Why it survived the ledger round.** The previous fix added shape guards to the file that keeps a
project's evidence, which is the file that *looks* important. The cache directory sits next to it,
is written by the same code, is JSON as well, and is the one an author is most likely to corrupt by
hand or by half-finished merge - precisely because it looks disposable. "Untrusted input" was
scoped to the input that felt load-bearing.

**How to apply.** For every file the tool reads, ask which of the two it is: can the value be
recomputed from something still present? If yes, an unrecognised shape is a miss, silence, and one
more read; if no, it is a refusal with the file named. Then apply the guard to *all* of them - the
list is "every file we read", not "every file that matters".

**The test that nearly hid it.** Seven of eight mutations were caught immediately. The eighth -
removing `isinstance(blob, dict)` - survived, because every damaged fixture was built by
`_shape(**extra)` and so was always an object at the root. A cache whose root is `[]`, `null`,
`"x"` or `5` needed fixtures written as raw JSON strings, which is now its own parameterised class.

**Evidence.** Before: `{"pages": 5}` → `TypeError: 'int' object is not iterable`, exit 1;
`{"pages": [null]}` → `AttributeError: 'NoneType' object has no attribute 'get'`, exit 1;
`{"pages": [{"number": "x"}]}` → `ValueError: invalid literal for int() with base 10: 'x'`, exit 1.
After: all of those plus a list/null/string/number root re-extract and verify, exit 0, and no
finding mentions the cache. Eight mutations red: the root shape trusted, the pages shape trusted, a
non-object page trusted, any page number accepted, a bool page number accepted, a page numbered
from zero accepted, the page text coerced, and the cache never read.
`tests/test_damaged_cache.py`.

Seen 1.

## A flag a command cannot honour is a lie told in the help text

`--bib` is declared by every verb because every verb shares `common()`. But only `scan` reads a
bibliography: it parses the entries and writes them *into the ledger*, which is the whole reason
`scan` is a separate command. `verify` and `check --use-recorded` check the manuscript's keys
against `ledger.entries`; they never open a `.bib`.

They accepted the flag anyway. Measured:

    citevouch check m.md --root . --use-recorded --bib nowhere.bib   ->  0
    citevouch verify  m.md --root . --bib nowhere.bib                ->  0

Exit **0** for a path that does not exist. `action.yml` always passes `--use-recorded`, so on every
pull request in every repository using the action, `--bib` was decoration whose entire purpose was
to make the run able to fail.

**Why validating the path is the weaker fix.** The obvious repair is to check that the file exists,
which is what `--source` does on the same path. But a *correct* path is still not read, so the author
who edits `refs.bib` and sees nothing happen is told nothing - and that is the same defect wearing a
better error message. The flag cannot be honoured here at all, so it is refused, and the message
names the two commands that can honour it.

**How to apply.** A flag is a promise about what the command does with it. When options are shared
through a helper, ask for each one: on *this* path, does the value reach anything? An option that
changes no behaviour on a path is worse than an unsupported option, because a missing option is an
error at the parser and an ignored one is a green run. Then check the defaults of the caller that
matters - here, `action.yml`, where the broken path was the *only* path.

**The test that had to state the general claim.** Refusing `nowhere.bib` would have been caught by a
path-validation fix too, so the test that pins the design asserts the refusal happens for a
bibliography that *is* present. The four controls on the other side - `scan --bib`,
`check --bib`, `check --use-recorded` with no flag, `draft --bib` - are there because the cheapest
wrong fix is a broad one.

**Evidence.** Before: the two commands above exit 0 and print `quote-found`. After: both exit 2 with
`--bib is not read by this command: it checks the bibliography recorded in citevouch.lock.json ...`
and name `citevouch scan --bib` and "drop --use-recorded". Six mutations red: `verify` not refusing,
the recorded path not refusing, an empty flag refused too, the path validated instead of the flag,
the message naming no command, and `check` without `--use-recorded` refusing as well.
`tests/test_bib_flag_refusal.py`.

Seen 1.

## A diagnostic that checks the manifest has not checked the manuscript

`doctor` asked whether `sources.toml` names files that exist. It never asked
whether the keys the *claims* name are bound at all. A project whose manifest
binds `other` and whose only claim names `source=paper` got seven `[ok  ]`
lines, exit **0**, and the closing sentence "Everything this tool needs is on
this machine. If quotes are still reported missing, the source files are the
place to look." — while `check` on the same project printed `[high]
source-missing ... claim c1 names source='paper' but no entry in sources.toml`
and exited 1. The reader is sent to look at source files that are all present,
all correctly spelled, and simply filed under a different name.

**Rule.** A check owns one noun, and the noun has to be the one a failing run
actually complains about. `manifest` owns "the file each key maps to is on
disk". `claims` owns "the manuscript holds blocks". Neither owns "the key this
block names is bound", and that is the noun `check` prints once per claim.

**Why this kept happening.** Five rounds fixed this same shape in one file: the
manifest check asked whether the file existed but not whether it pointed
anywhere (0.19.44), the manuscript check called a directory absent (0.19.45), a
`.tex` file got a clean bill (0.19.46), a file with no claim blocks got a clean
bill (0.19.47), and this one. Each check was written from the side of the part
of the project the author had just been thinking about, and the decisive
question was always one noun further along.

**How to apply.** Enumerate the nouns `check` prints failures about, then ask
for each one which `doctor` line answers it. Where there is no line, that is the
check. When the new line overlaps an old one, decide which line owns the cause
and make the other one defer — this check says "not checked, because the
manifest could not be read" for a broken manifest, and "of which 1 key cannot be
used; the manifest line above names it" for a key whose file is missing, rather
than printing a second, independent-looking complaint about one cause.

**Evidence.** 2026-11-02. Before: `doctor --root _ku --manuscript manuscript.md`
printed seven `[ok  ]` lines and the reassurance, exit 0; `check
_ku/manuscript.md --root _ku` printed `[high] source-missing at manuscript.md:3
(c1)` and exited 1. After: `[FAIL] sources  1 source key named by a claim is
bound to nothing: 'paper' is named by a claim, and no entry in the manifest binds
it`, exit 1. Seven mutations, all red — one anchor was wrong on the first pass
(`table.manifest_problem` appears twice in the file, and the mutation hit the
wrong one), which is the same failure mode as a test that asserts nothing. The
test file compares `doctor` against `check` on the same projects rather than
remembering both messages, so rewording either one cannot quietly break the
agreement it is testing. Seen 1.

## 141. A block whose values are attributes is not a block whose values are text

**Rule.** When a reader supports several shapes of one input, every shape has to
be checked against the field it lands in - not only against whether it parses.

**Why this keeps happening.** `_split_body` knew about `quote:` and `claim:` and
treated every other line as a continuation of the current field. Its own
docstring said "everything as the quote, with an empty claim (still
verifiable)", which is true and reads like a complete answer. What it did not
say is that a line reading `source: paper` is a *statement*, and the function
had no vocabulary for statements - so it fell through to the only branch it had.
The header line ` id=c1 source=paper ` was parsed by a different function
(`_attrs`) that does have that vocabulary, and the two sat forty lines apart,
each correct on its own.

**How to apply.** For each shape a reader accepts, write the input the shape is
*for* and assert on the field, not on the parse succeeding. Here that meant
`quote: |` followed by `ref: paper2026` and an assertion on `claim.quote`; the
parse succeeded both before and after the fix, and only the quote length told
them apart. And when a format has two surfaces that carry the same keys - the
opening line and the body - one of them has to be declared to win, because a
rule nobody wrote down is a coin toss the author loses silently.

**The other direction.** The fix names six keys. Everything else still lands in
the quote, on purpose: a quote that grew is visible in a verdict, and a quote
that silently shrank is visible nowhere. A widening reader is a data-loss
machine, and this one is deliberately narrow.

**Evidence.** Before: `[high] quote-missing at m.md:3 (c1): We collected 40,688
examples in the corpus. ref: paper2026 - quote not found in page.txt`, exit 1,
on a page that holds that sentence and both dialects alike. After: `[info]
quote-found`, exit 0. Five mutations - attributes quoted again, fence-only
lookup, body-beats-fence, every key treated as an attribute, attribute line
dropped - five red, `survivors: none`.

Seen 1.

## A redirected stream is not where a log record goes

**Rule.** When the thing you are testing is a *log record*, assert on log
records. `redirect_stderr` only sees a stream; logging resolves its stream from
a handler, and pytest installs one on the root logger before your test runs. A
test that reads `sys.stderr` and expects to find a library's warning passes
whether or not the code under test logs anything at all.

**Why.** The fix was "stop pypdf printing warnings on stderr". The obvious test
is a subprocess or a `redirect_stderr` around `main()`, and both look decisive:
they show the console. But the console is exactly what a log handler takes away.
The first draft had six tests including one that asserted `err == ""`, and **two
of the five mutations survived** — "the pypdf read is not silenced" and "the
reason reader is not silenced" both left every test green, because nothing in
the file was counting records.

The fix was to install a collecting handler on the `pypdf` logger, raise its
level to `DEBUG` so the handler could see what a real caller would, and assert
the record list was empty. All five mutations went red immediately.

**How to apply.**
1. Ask what the *observation* is. A stream is one way to observe a record; a
   handler is the other, and it is the only one that works under pytest.
2. Both failure directions need a test: the warning must be gone **and** an
   unrelated warning must still arrive. The second is what catches
   `logging.disable()` — a global mute passes the first test perfectly.
3. A test that reads state it just set is not comparing anything. The
   "level is restored" test first read the level it was about to restore, so
   "restored to `ERROR`" and "never restored" were the same observation; it
   had to set the level to a known value first.
4. After the mutation run, read the survivors as *questions about the tests*,
   not about the code. Both survivors here were correct code and blind tests.

**Evidence.** Before: `check` on a project with one unreadable PDF wrote
`invalid pdf header: b'not a'` / `EOF marker not found` twice to stderr around
one `source-unreadable` finding, and `--format json` still emitted valid JSON to
stdout — so the noise was invisible to anything reading stdout and unavoidable
for a human. After: stderr is zero bytes for the same run. Reverse verification:
5 mutations, 5 red, `survivors: none`. First draft: 6 tests green, 2 mutations
survived. Seen 1.

## A path rule that five verbs share must not be re-implemented by the sixth

**Rule.** One path, one resolver.  If a command needs to turn a relative path
into a file, it calls the helper the other commands call; it does not join
`root` to the string itself and hope the results agree.

**Why.** `scan`, `verify`, `check` and `draft` all go through
`citevouch.scan._resolve`, whose rule is "a relative path that exists as typed
is never re-rooted".  That rule exists for the reader: `--root demo` is for the
manifest, the ledger and the sources, and `demo/manuscript.md` is what people
type.  `doctor` joined unconditionally, which is a different function with the
same name in the reader's head.  Measured from the directory above a project:

    citevouch check paper/m.md --root paper                 -> 1 verified, exit 0
    citevouch doctor --root paper --manuscript paper/m.md    -> exit 1,
        "[FAIL] manuscript  paper\\paper\\m.md does not exist"

The command that exists to explain a run that found nothing was reading a file
that did not exist and saying so, in a report the reader had opened *because*
the previous command found nothing.

**How to apply.** When adding a verb, do not decide how a path becomes a file;
look up the decision and call it.  Then write the test from the outside: run
the new command and an old one on the same argument pair and assert they name
one file (`Path(named).resolve()` sets, not string equality - commands print
different amounts of the path).  A test that only runs one command cannot see
this defect at all, no matter how many assertions it makes.

**The piece that made it survive.** The fix line under the failure told the
reader to pass `paper/manuscript.md`.  Following the advice reproduced the
failure.  Advice printed next to an error is part of the error: it has to be
executable in the same invocation shape that produced it.

**Reverse verification.** Three mutations - rejoin the root, resolve
unconditionally, hand the joined path back to the resolver - all red, six tests
each.  The first draft of the test file failed for a different reason worth
recording: it ran with the working directory inside the project, where the two
readings agree by accident, so it proved nothing until the fixture chdir'd one
level up.

Seen 1.

## A path that crosses two layers of resolution fails at the second one

**Rule.** When a value is produced for one purpose and then used for another,
write down which layer owns the interpretation.  A path relative to the project
root is an *output* for a manifest and an *input* for an open call; passing it
straight from one to the other assumes the two layers agree, and they only
agree when the working directory happens to be the root.

**Why this happens.** Both halves are correct on their own.  `draft.resolve`
returns `page.txt` because that is what `sources.toml` must say, and the
docstring says so.  `extract_pages` opens what it is handed because every other
caller hands it a real path.  The defect lives in the line joining them, which
belongs to neither file's author.  Measured, same project, only the working
directory differing:

    cd paper  && citevouch draft paper/m.md --root paper --bib paper/refs.bib
        -> 1 claim block(s) proposed (1 verbatim)
    cd ..     && citevouch draft paper/m.md --root paper --bib paper/refs.bib
        -> 0 claim block(s) proposed (0 verbatim), 1 citation(s) left as comments
           <!-- line 1: paper - source file page.txt does not exist -->

The file it said did not exist was `paper/page.txt`, present the whole time.

**How to apply.** For every value that crosses from "what we record" to "what we
open", ask where the second layer resolves it.  Here the answer already existed:
`scan._resolve` is the rule five commands share, and the sixth should call it
rather than restate it.  Then test from the far side.  A test that runs inside
the project cannot see this defect, because inside the project both readings
name the same file by accident - the fixture has to `chdir` one level up, and
the assertion has to compare two runs against each other, not each run against
its own expectations.

**The second half of the same fix.** The message that explained the failure was
also generated at the wrong layer.  `_why_no_file` knew the two reasons
`sources.toml` can give and summarised everything else as `no `file` field in
the bibliography` - false in the one case the author is looking at, because the
field is on the screen.  A summary that is correct only when it is not needed is
not a summary.  The answer has to come from the file that holds the field.

**Reverse verification.** Four mutations - open the recorded path instead of the
resolved one, skip the bibliography branch, drop the path from its message, stop
passing the bibliography at the call site - all red, 4 to 7 tests each.

Seen 1.

## The flag that resolves its own path will be the flag with its own spelling

**Rule.** When several flags take a path, they take it the same way.  A user
who has learned the rule from one flag applies it to the next one, and the
error message they get back is the only evidence they have about which flag
they are holding.  A per-flag rule is not a detail; it is a spelling test
nobody was told about.

**Why this kept happening.** ``--source`` joined ``--root`` unconditionally
while six other flags accepted a path that already works.  Both readings are
defensible on their own - ``--source`` names a file inside the project, so
why not read it that way - and the disagreement only shows up from a working
directory where they differ.  Measured, project in ``paper/``, typed from one
level above:

    --bib paper/refs.bib      resolves, the bibliography is read
    --source paper/page.txt   exit 2: source paper\paper\page.txt does not exist
    --source page.txt         resolves

Both paths point at files that are really there.  The message even contains
the doubled segment, so the author can see the rule but not know it applies
to one flag out of seven.

**Why one function is not enough.** The rule existed, in ``scan._resolve``,
and six commands called it.  ``--source`` could not, because
``sources.py`` is imported by ``scan.py`` and not the other way round - the
one caller that needed it was the one place it could not be reached from.
Living in the wrong module is how a shared rule becomes a private copy.  The
fix moved the implementation down to the module everyone imports and left
``scan._resolve`` as an assignment, not a wrapper: two functions that agree
today are two functions that disagree after the next fix, and no behavioural
test can see the disagreement until it has already bitten.  The test asserts
``scan._resolve is sources._resolve`` for exactly that reason.

**How to apply.** Enumerate the path flags and run one project through all of
them from a directory where the two readings differ.  The count is the point:
one odd flag out of seven is invisible in any test that exercises a single
command.  Then check the guards, because they compute the same names by the
same rule and drift the same way - ``draft``'s ``-o`` guard was protecting
``paper/paper/page.txt``, which is not a file, while writing over
``paper/page.txt``, which the run had just read a quote out of.  A guard that
names a different file than the reader opens is not a weaker guard; it is a
guard for a different run.

**Reverse verification.** Four mutations - join the root unconditionally in
``--source`` again, drop the already-works branch, restore the guard's own
root join, give ``scan`` its own copy of the rule - all red.  The last one is
the useful one: it survived a first attempt because the mutation script's
anchor was a wrapper body that had just been replaced by an assignment, so the
script reported the mutation as missing rather than as surviving.  A mutation
check that cannot tell 'the code changed shape' from 'the test is weak' has to
say so, not pass.

Seen 1.

---

## When a key is in the file and the reader says it is not, check what the value is

**Rule.** A reader that keeps some entries and drops the others has to say which
ones it dropped and why.  Silence about a dropped entry is a sentence about the
file that is not true - and worse than a sentence, because it is the sentence
the author has already checked.

**Why this keeps happening.** The drop was one `isinstance` in a dict
comprehension: `{str(k): str(v) for k, v in mapping.items() if isinstance(v, str)}`.
Every entry that did not fit the type went missing at exactly the place the code
was most careful about - the same function whose docstring explains that
`unusable` exists because an earlier version dropped entries and then told the
author "no entry in sources.toml" about the entry the author had got right.  The
reasoning was written down in the file and the defect sat directly opposite it:
the docstring enumerated the *file missing* cause and the *directory* cause, and
the value-shape cause was not on the list, so nothing was looking for it.

**How to apply.** For every mapping a reader consumes, ask two questions rather
than one.  First: "what if the key is absent?" - the well-worn case.  Second:
"what if the key is present and the value is the wrong shape?" - and answer it
for each shape the source format allows, not for the one you imagined.  TOML
admits strings, integers, floats, booleans, arrays and tables, so a manifest
reader needs six answers; `page = 5` reaches none of the paths written for the
string case.  Then check whether the same file is read by a second parser: this
project has `tomllib` on 3.11+ and a hand-written subset parser for 3.10, and
they disagreed - one dropped the value at the key/value layer, the other kept it
and discarded it one layer up.  A file that binds a key on one interpreter and
loses it on another is the same bug in two shapes.

**The other direction.** Do not turn this into "refuse any file that is not all
strings".  A boolean in `sources.toml` is a typo in one value, not a reason to
reject a manifest whose other keys are fine, and an empty file really does have
no entries - "add it to sources.toml" is the right sentence there.  The split is
between a key the manifest holds with the wrong shape (name it, quote it, keep
the rest) and a manifest that cannot be read as a manifest at all (`sources = 5`
is not a table, so `manifest_problem` owns it).  Two buckets, because the
author's next move differs: edit a value, or replace the file.

**Evidence.** Before: eight shapes - integer, float, boolean, array, inline
table, `sources = 5`, `sources = "page.txt"`, empty file - all produced
`claim c1 names source='page' but no entry in sources.toml and no --source path
resolves it; add it to sources.toml`, with `found={}`, `unusable={}` and
`manifest_problem=None`.  On 3.10 the same manifest reached the reader as
`{'sources': {}}`, and `sources = "page.txt"` reached it as
`{'': {'sources': 'page.txt'}}`.  After: the first five reach `unusable` with
`the 'sources' key holds ... not a table of keys to paths` for the last two, and
the empty file keeps the old advice.  Five mutations - stop carrying odd keys
out of the parser, stop collecting non-string values, ignore the odd keys in the
table, read a non-table `sources` key as absent, silence the subset reader - all
red, no survivors.

Seen 1.

## 147. When one file has two readers, the readers must refuse the same files

**Rule.** A configuration format read by more than one parser - a real one
where the interpreter has it and a fallback where it does not - is one format
only if both parsers accept the same files and reject the same files with the
same words. A check written inside one parser answers for that parser alone, so
shared refusals belong before the split, not inside either branch.

**Why this keeps happening.** The subset parser was written to get the manifest
working on 3.10, and every guard it has was added in response to a 3.10
symptom. Meanwhile `tomllib` was the reference, so the shapes the subset was
*lenient* about never showed up as failures anywhere: `page = "a.txt"` twice is
a hard error on 3.11 and a quiet last-one-wins on 3.10, and the only way to see
it is to run both readers over the same bytes and compare. A project's colour
therefore depended on which Python CI happened to install.

**How to apply.**

1. Enumerate the spellings that are legal in the format but not in the subset,
   and the ones the subset tolerates but the format forbids. Compare the two
   readers over that list rather than testing either alone.
2. Put the refusals in one pre-scan that runs before the split, so the sentence
   is written once. A refusal inside the subset cannot fire on the 3.11 path,
   which is the path most contributors develop on.
3. Have the test assert the two readers *agree* - same return value, or the same
   message - not that each behaves correctly by its own standard. Two
   independently-correct parsers can still disagree about one file.

**The other direction.** Agreement does not mean identical dictionaries. A
non-string value is dropped from one table and kept in the other, and that is
fine because both then say the same thing about the key: it is not bound to a
file. Pin the agreement at the level callers read (here `read_source_table`'s
`found` / `unusable` / `manifest_problem`), not at the parser's internal shape.

**Evidence.** Before: `sources = { page = "a.txt" }` bound `page` on `tomllib`
and produced no table in the subset; `pa.ge = "a.txt"` bound nothing on
`tomllib` and `pa.ge` in the subset; a repeated key was a hard error on one and
last-one-wins on the other; `[sources]` twice was a hard error on one and a
merge on the other. After the pre-scan: 11 manifest shapes produce identical
`(found, unusable, manifest_problem)` from both readers, and the four refused
shapes produce byte-identical messages. Six mutations - restore the inline
table, restore the dotted key, stop refusing a repeated key, stop refusing a
reopened table, skip the pre-scan on the `tomllib` path, skip it on the subset
path - all red, no survivors. The `tomllib`-skip mutation first reported ANCHOR
MISSING, which is the mutation tool failing rather than the guard holding; it
was retargeted at the real call site and then went red.

Seen 1.

## 148. A guard written to fix a false answer can refuse a true one

**Rule.** When a guard exists because two readers disagreed about one file, the
guard must cover exactly the part of the file that disagreement was about. Scope
it to the subject, not to the format: a pre-scan over a whole TOML document sees
tables the tool never reads and refuses files that both readers answer the same
way - which turns "these two disagree" into "nobody may use either".

**Why this keeps happening.** The four spellings that started this were found by
diffing two parsers over one file, so the natural next move is to walk the file
and reject everything different. But the diff was about ``sources``: a dotted key
under ``[other]`` is a nested table to both readers and binds no source to
either, so it never appears in a diff of the answer. A guard that scans wider
than the question cannot tell a real disagreement from a file that merely
carries more than the tool needs - and manifests carry more, because people keep
other tables in the same file.

**How to apply.**

1. Write down what the guard is *about*. Here it is "what does ``sources``
   resolve to", not "is this legal TOML".
2. For each rejected spelling, ask which of the two readers, if either, would
   answer the question differently. If neither would, the spelling is not a
   disagreement and refusing it is the guard's own false positive.
3. Test the negative direction as hard as the positive one: a manifest with an
   unrelated table must still read, and still bind the real source. A guard with
   only "rejects the bad shapes" tests can grow without bound and stay green.

**The other direction.** Narrowing is not the fix for a guard that misses a
shape. The scope is the *file region* the question is about; the *set of
refused spellings* inside that region is still every one the readers disagree
about, and a new one belongs in the guard rather than in a reviewer's memory.

**Evidence.** Before narrowing: ``[sources]\npage = "a.txt"\n[other]\npa.ge =
"dir/x"`` produced ``found={}`` and ``manifest_problem`` naming a dotted key
under ``[other]``, while ``tomllib`` read ``{'sources': {'page': 'a.txt'},
'other': {'pa': {'ge': 'dir/x'}}}`` - the same bindings the subset produces.
After: five unrelated-table shapes read cleanly and ``page`` still binds, while
the root inline table and a dotted key under ``[sources]`` are still refused by
both readers.  Six mutations - restore the inline table, restore the dotted key,
stop refusing a repeated key, stop refusing a reopened table, widen the scan to
the whole file again, refuse every inline table anywhere - all red, no
survivors.  The widening mutation is caught by the new class alone, which is the
point: the tests that predate it stayed green through the regression.

Seen 1.

## A refusal is only shared if both readers reach it

**Rule:** when one file has two readers, any check that decides what the file
*means* has to live somewhere both of them run, and it has to talk only about
the file's meaning - not about every line that happens to look strange.

**Why this keeps happening.** `sources.toml` is read by `tomllib` on 3.11+ and by
a line-based subset on 3.10. Each reader was written on its own terms, and each
was individually defensible: the subset drops a key it cannot spell rather than
binding a name tomllib would spell differently. That is a correct thing for the
subset to do *on its own*. The bug is the pair - on 3.13 the key binds and the
claim resolves, on 3.10 the line vanishes and the claim reports
`source-missing` for a manifest the author wrote correctly. The CI matrix runs
3.10, 3.12 and 3.13, so the same commit is green or red depending on which cell
you look at. Five spellings sat in that gap at once: a multi-line value, a
trailing comma, a quoted key holding `=#[]'"`, two assignments on a line, and
(release before) a root inline table or dotted key.

**How to apply.** Put the refusal in a pre-scan both readers call, and give it
one sentence each - a check written inside the subset can only ever speak for
the subset. Then ask what the check is *about*: only the spellings that change
what `sources` means belong in it. A dotted key under `[other]` binds no source
in either reader, so refusing it rejects a manifest both readers answer the same
way; that was this pre-scan's first version, and it was the regression. Test
both directions - the shapes that must be refused *twice*, and the shapes that
must still be read *once*.

**Evidence.** Before: `read_source_table` on `[sources] page = """a.txt"""`
gave `found=['page']` on tomllib and `unusable=['page']` on the subset; the same
for a trailing comma, a quoted `"pa#ge"`, and `a=b = "x.pdf"`. After: nine
shapes compared at that level, `differing tables: 0 of 9`. Five mutations of the
new guards - including one that survived at first because the guard it disabled
was masked by a neighbouring one, and one that only became reachable once the
inline-table exemption was added - all RED, survivors: none. The older test
`test_a_key_this_reader_cannot_spell_is_dropped_and_the_rest_survives` pinned
the divergence as the intended behaviour; it now asserts the shared refusal.

## A guard on one reader is not a guard on the format

**Rule:** when one file format has two parsers, fix the format's answer, not the
parser's. Check the other parser before you call it done - not after someone
reports it.

**Why this keeps happening.** `sources.toml` and `sources.json` are read in the
same loop of `read_source_table`, and the loop looks symmetric: both branches
produce a `mapping`, both fall into the same `isinstance(mapping, dict)` test.
But the TOML branch grew a set of guards across three releases - a non-table
`sources` key, values that are not strings, five spellings only one reader could
follow - while the JSON branch still carried the original one-liner
`blob.get("sources", blob) if isinstance(blob, dict) else {}`. So `5`, `[]`,
`"page"` and `true` at the root were read as *an empty manifest with no problem*,
and every claim was told `no entry in sources.json` about a file it was looking
at. That is precisely the wrong answer 0.19.66 fixed for TOML, still live one
branch below it. The `{"sources": null}` case was the same shape: falling through
produced the truthful "binds nothing", so nothing raised, and the advice - "add
it to sources.json" - led the author to add a second key beside the broken one.

**How to apply.** Grep the format's name, not the parser's: every place a
manifest is read should be reachable by one search, and if a fix touches one
branch of an `if` that has two, read the other branch in full. Then ask the
mutation question of the *sentence* as well as the branch - a test that only
asserts `manifest_problem is not None` passes for `holds nothing usable` and for
`holds list`, and only one of those lets an author tell a typo from a file that
is not a manifest.

**Evidence.** Before: `sources.json` holding `["a.txt"]`, `5`, `"page"` or `true`
gave `found=[]` with `manifest_problem` empty, and `check` printed
`claim c1 names source='page' but no entry in sources.json and no --source path
resolves it` for all four. After: `holds list`, `holds int`, `holds str`,
`holds bool`, and the null key has its own sentence. Four mutations - including
"the root shape is named without its type", which survived the first round
because the test asserted only the shape - all RED, survivors: none.

## When a comment describes a safety property, the lie is load-bearing

**Rule.** A docstring that says what protects the reader must name the code that
protects them, or it must not say it protects them at all. `Claim`'s note said
the ledger stores the quote's fingerprint "so a later verification run can tell
'the quote is gone' from 'the quote moved'". No code reads that field back:
`quote-moved` is decided from the page numbers the current run found.

**Why this one is worse than the usual stale comment.** Every other entry in
this family costs a reader some time. This one costs them their judgement about
whether to trust `--allow-stale`. A reader who believes the fingerprint catches
edits will run `check --use-recorded --allow-stale` on a manuscript they have
since edited and read `quote-found` as "the evidence still supports this" -
when what happened is that the new text was checked against the page for the
first time, with no record of the old text anywhere in the decision.

**How to apply.** When a comment names a mechanism, open the file that would
have to contain the mechanism. If the only hits are the field's definition and
its serialiser, the comment is describing a plan. Write down what the field is
*for* (here: keeping the passage out of two places) and what the property
actually is (here: an edited quote is compared like any other).

**How to keep it true.** A docstring claim gets a test that reads the docstring
and a test that reads the code it names. `tests/test_claim_docstring.py` has
three: the sentence, the single producer, and a scan that fails if any module
other than `model.py` mentions the field without writing it - which is what a
comparison would look like.

**Evidence.** `grep -rn "quote_fingerprint" src/` before the fix: six hits, all
in `model.py` and one in `manuscript.py:264` (`quote_fingerprint=fingerprint(quote)`).
`verify.py`, `report.py`, `scan.py` and `cli.py`: zero. Measured behaviour -
editing a quote to `alpha beta` and running `check --use-recorded --allow-stale`
gave `[info] quote-found ... 1 claim - 1 verified`, exit 0. Three mutations of
the new docstring (restore the claim, drop the field's purpose, drop the
property that matters) all turned the tests red.

Seen 1.

## A test that compares two runs of a clocked artefact is a coin flip

**Rule.** When a test compares two artefacts produced by separate runs, find
out what each run writes about *itself* before comparing them. A ledger records
`generated_at`; two ledgers written a second apart differ, and the test that
compares them is not testing the path rule it was written for.

**Why it was not caught.** The test ran on three operating systems, three
Python versions and an unpacked sdist, and the whole matrix was green for days.
Two `scan` calls on a small fixture finish in the same second... until the
machine is loaded, and then one of the eleven jobs fails with a diff of two
files that look identical. Flakiness hides in the one field nobody looks at
because it is boring, and the failure names the test rather than the cause.

**How to apply.** Ask what the artefact carries about the run: a timestamp, a
hostname, a tool version, a duration. Then decide, explicitly, whether that
field belongs in the comparison. Here it does not, and the normaliser that
drops it gets its own tests - one showing it removes only the clock, one
showing the real writer still stamps one - so the next field that starts
varying fails a test that says so instead of making this one flaky again.

**Evidence.** The sdist job at 2026-11-02T14:54:18Z: `1 failed, 1529 passed,
7 skipped`, `assert '{\n  "schema...  }\n  ]\n}\n' == '{\n  "schema...
}\n  ]\n}\n'`. Three mutations: keep the clock in the comparison -> red;
make the normaliser drop everything -> red; make `scan` stop stamping a time ->
red (the last one only after the mutation was aimed at `scan.py` rather than at
the test's own assertion, which the first attempt got wrong).

Seen 1.

## A command with two spellings, supported in one, fails twice at once

**Rule.** When a command can be written more than one way, both spellings must
reach the same handler for *every* consequence of that command - here: the
argument must leave the prose, and the argument must be reported as a file this
tool did not read. Implementing one spelling means the other is not "partly
supported"; it is silently mis-supported, and it does damage in two directions
at the same time.

**Why this is worse than a missing feature.** `\input sec/intro` (plain TeX,
no braces) was invisible in two places that each looked correct on their own:

- `to_text` did not drop the argument, so the path stayed in the sentence -
  `We show this in sec_intro and continue the argument here.` That sentence is
  the "claim" text `draft` puts in front of the author, so the proposal was
  built on a sentence the paper does not contain.
- `included_files` did not see it, so the "this document pulls text in from"
  note listed nothing. The author was told the tool had read the whole paper
  while a section - its citations included - was never opened.

Each half produces an output that is internally consistent: the prose reads
like prose, and the note reads like a complete list. Nothing in the run says
"one of these is wrong", which is why a single end-to-end check of the braced
form would never have found it.

**How to apply.** For any command the tool parses, list its spellings from the
TeX (or TOML, or YAML) grammar rather than from memory: braces are optional
here, `\include` and `\includeonly` are separate commands, `\verb` and
comments must not count. Then check *both* consequences for each spelling.
Where the two spellings differ in an edge case - a bare name runs to the next
whitespace, so it swallows a trailing full stop - write that down in a test
named after the difference rather than smoothing it over.

**Evidence.** A two-line `.tex`. Before: `to_text` returned `'We show this in
sec_intro and continue the argument here.\n'` and `included_files()` returned
`[]`. After: `'We show this in and continue the argument here.\n'` and
`['sec/intro']`. Three mutations: leave the bare form in the prose -> red; skip
it when reporting -> red; make the bare pattern only match braces -> red. The
first mutation reported `ANCHOR MISSING` on the first attempt because the
quoted anchor started three lines into the branch; a mutation script that
cannot find its anchor has verified nothing, and must be fixed before its
verdict is read.

Seen 1.

## "Keep whatever it wraps" is only true when the first thing it wraps is prose

**Rule.** A command that is in neither the keep-list nor the drop-list does not
keep prose - it keeps *everything after the name*, which for a command whose
first argument is a colour, a URL, a width or a scale factor means the argument
is pasted against the sentence. Ten LaTeX commands were in that hole at once:
`\textcolor`, `\colorbox`, `\fcolorbox`, `\scalebox`, `\resizebox`,
`\parbox`, `\makebox`, `\framebox`, `\hyperlink`, `\href`.

**Why the two sets did not catch it.** Both existing lists were accurate - every
member was classified correctly. The bug lived in the *third* path, the
fallthrough that names no set and therefore has no member to be wrong. A
classification of the commands anyone thought of cannot cover the commands
nobody did, and the fallthrough reads like a sensible default ("drop the
command, keep the text").

**How to apply.** For a converter, the fallthrough is a claim about the
grammar, not about the text. Make it as narrow as the grammar allows: here, the
safe default is "drop the name and keep the braced groups", which is a different
block of code from "keep the raw slice". Then enumerate the argument shapes the
tool cannot model (colour, URL, length, factor) and give each one its own
handling, because a word glued to a colour is not a typo an author can spot -
it is a word that was never on the page.

**The count is part of the shape.** `\fcolorbox` and `\resizebox` take two
non-prose arguments before the text; the other eight take one. A skip of
"one" compiles and runs and is wrong for exactly two commands, so the number
belongs in a table rather than in the loop's body, and each count needs a test.

**Evidence.** Before: `\textcolor{blue}{blue}` -> `blueblue`,
`\href{http://x}{shown}` -> `http://xshown`, `\scalebox{2}{big}` -> `2big`,
`\parbox{3cm}{boxed}` -> `3cmboxed`, `\hyperlink{target}{linked}` ->
`targetlinked`, `\resizebox{1cm}{!}{resized}` -> `1cm!resized`. After: each
yields only the wrapped words. Four mutations: skip the new branch -> 13 tests
red; say every command takes one argument -> 2 red; treat the optional argument
as the first -> 2 red (only after a `\parbox[t]{3cm}{}` test existed - the first
version of the suite could not see it); keep the last argument raw instead of
converting it -> 1 red (the anchor needed widening, because the call appears
twice in the file).

Seen 1.

## When the name of a file is prose, the file was not read

**Rule.** A LaTeX command that names a file has to do two things at once: keep
the name out of the prose, and put it in the list of files this module did not
read. Doing neither is the worst combination, because the sentence looks
complete and the warning list looks empty.

**Why this keeps happening.** `to_text` and `included_files` are two functions
over the same input, and each has its own idea of which commands matter.
`to_text` classifies commands into "keep the argument" and "drop the argument",
and anything in neither falls through to "keep whatever it wraps, drop the
name". That fallback is correct for `\textbf` and wrong for every command whose
first argument is a path or a colour. `included_files` has a hand-written list
of three commands, so a command outside that list is invisible to it while it
is visible to the converter. Measured on seven commands - `\subfile`,
`\import`, `\subimport`, `\includestandalone`, `\includepdf`,
`\lstinputlisting`, `\verbatiminput` - every one left its path in the sentence
and reported nothing.

**How to apply.** When a converter has a fallthrough, enumerate the commands
that reach it and ask of each one: is its argument prose? The fallback is not a
default, it is a claim that the wrapped text is the sentence. And when two
functions read the same file, walk the same command list through both - a test
that only checks the prose passes while the report stays silent.

**Evidence.** `\subfile{sec/intro}` converted to `'sec/intro'` with
`included_files` returning `[]`; after the fix, `'A B'` and
`['sec/intro', 'chapters/one', 'two', ...]`. Four mutations (name in the prose,
file never reported, only the first argument of `\import`, name dropped but
argument kept) are all red. Seen 1.

## A macro body is a template, and a template is not a sentence

**Rule.** When a converter decides what text to keep, a definition command's
body has to go with the name. `\newcommand{\x}{\citep{knuth}}` does not
cite Knuth; it says what a later call will become. Leaving the body in the
stream makes the converter read a promise as evidence.

**Why this was easy to miss.** `\newcommand` and friends were already in
`_DROP_ARGUMENT`, which is a set of commands that take one non-prose
argument. That is true of `\ref` and `\label` and false of a
definition, which takes a name, an optional count, an optional default and a
body. The command was in the right set for the wrong reason, so nothing
looked wrong: only the first brace group was dropped and the rest fell
through as prose.

**Both directions at once.** A body naming a key invented a citation
(`\knuthcite` put a `[@knuth]` into a paper that never cites Knuth, and
`draft` offered a `sources.toml` line for it). A body naming a parameter
lost one: `\seecite` recorded a citation to the key `#1` while every
real call `\seecite{knuth}` became a bare word. So the two failure modes
of this tool - a false accusation and a silent pass - came out of the same
line of code, and fixing only the text would have left `included_files`
reporting a file called `#1`.

**How to apply.** For each command in a drop set, write down how many
arguments it has and which of them are prose. A set whose name says
`Argument` (singular) may not hold a command with four. When a definition's
body can itself contain the commands being read (`\input`, `\citep`),
cut the body before those commands are matched anywhere, not just in the
converter - `_without_definitions` runs the same cut over the raw source for
exactly that reason.

**Evidence.** Before: `\newcommand{\knuthcite}{\citep{knuth}}` converted to
`'[@knuth]'`, and `citation_sites` returned `['knuth']` for a document with
no citation. `\newcommand{\inc}[1]{\input{#1}}` made
`included_files` return `['#1']`. After: both return nothing, a real include
beside a definition is still reported, and 26 new tests cover the eight
definition spellings, the three argument shapes, environments and theorems.
Five mutations (body back as prose, raw source not cut, environment keeps
its second body, low-level definition stops at the name, theorem keeps its
printed name) are all red. Seen 1.

## A command whose arguments are all metadata has no prose to keep

**Rule.** The converter's fallthrough says "an unknown command: keep whatever
text it wraps, drop the name". That sentence is a claim about the command's
arguments, and it is only true when one of them is prose. Before adding a
command to the keep-list by leaving it out, ask what each argument *is* - a
counter name, a length, a style, a registry key and a file name are all not
text, and every one of them becomes a word in the sentence if you keep it.

**Why this keeps happening.** The fallthrough is the right default, because
there are thousands of LaTeX commands and most of them wrap text: `\enquote`,
`\textsl`, `\foreignblock`. So a new command does not look broken - it looks
like the hundreds that work. What makes this one different is that the argument
is *visible metadata*: `2em`, `fancy`, `arrows.meta`, `3`. A stray `2em` in a
sentence is ugly; a stray `3` is a number, and a number is what `draft` proposes
a claim for and what the verifier then compares against the page.

**Both directions at once.** The same fallthrough both adds words that are not
in the paper and, when the argument is the only copy of a real word, removes
nothing but rearranges what the reader sees. `\setcounter{page}{3}We collected`
becomes `3We collected` - the sentence is intact, its first character is not.
A fix that only looks for missing or extra words cannot see this.

**How to apply.** For every command you add a rule for, name the argument count
as data (`_DROP_ALL_ARGUMENTS[command] = 2`) rather than writing an `if` for it,
so the count is visible next to the name. Then write the test as the *whole*
converted sentence, not as a list of forbidden tokens: a forbidden-token test
passes when the handler drops the wrong number of arguments, because the token
it looks for may be gone while a different argument is still glued on.
`\multicolumn{2}{c}{wide text}` passed a "no `{2}` in the output" assertion
while producing `cwide text`.

**Evidence.** Measured before this fix: `\setcounter{page}{3}We collected 40,688
examples.` converted to `3We collected 40,688 examples.`; `\pagestyle{fancy}
This chapter argues so.` to `fancy This chapter argues so.`;
`\setlength{\parindent}{2em} Indented.` to `2em Indented.`;
`\usetikzlibrary{arrows.meta} Body.` to `arrows.meta Body.`;
`\multicolumn{2}{c}{wide text} continues.` to `cwide text continues.`; and
`\newcommandx{\x}[1]{Body #1} Body follows.` to `[1]Body #1 Body follows.`.
An end-to-end `draft` run on
`\setcounter{page}{3}We collected 40,688 examples in total, as \citep{page}
reports.` wrote a claim block whose `claim:` line began `3We`. Five mutations are
red: fall back to the fallthrough, drop only the first argument, drop one for
every command, keep both `\texorpdfstring` arguments, and stop recognising the
xparse definition spellings. Seen 1.

## A conditional is syntax, and syntax the tool ignores becomes words

**Rule.** Three LaTeX conditionals were handled as if they were ordinary
commands, and each failed in a different direction: `\iffalse`, whose
body TeX never reads, was converted as prose - so a commented-out citation became
a real one; `\iftrue`, whose body *is* text, had its marker pasted into the
sentence, because the unknown-command fallthrough keeps a body and drops only the
name; and `\ifthenelse{test}{yes}{no}` kept the test, which is the same
defect as the metadata arguments fixed one release earlier. The lesson is not
"handle conditionals". It is that a converter has two kinds of input - what the
author wrote, and what the compiler typesets - and any command that decides
which parts of the file are typeset has to be decided, not passed through.

**Why this keeps happening.** Every one of these commands is a *marker* in the
author's source: short, unremarkable, and surrounded by words that are clearly
prose, so the converted output reads fine to a human and fine to a diff. The
damage is only visible in what the machine then says about the text: a citation
that is not in the paper, a file that is not read, a sentence with `1=2` stapled
to the front. The tool produces those sentences, so the bug surfaces in `draft`
proposals and in `check` messages rather than in the converter's own output.

**How to apply.** For any command that selects text, ask two questions in this
order: does the selection change *which* text is real, and does the selection
leave a token behind that a reader would not see? If the first answer is yes,
the body must be cut or kept by the converter - the two readers (`to_text` and
`included_files`) have to agree, so the cut belongs in a helper both call. If
the second is yes, the marker is metadata and belongs with the counters and
lengths. Then write the test as the whole converted sentence: `\ifnum1>0`
passed a "the body was converted" assertion while still pasting `1>0`.

**The half you cannot do is worth a test of its own.** The operand-taking
conditionals (`\ifnum`, `\ifdim`, `\ifodd`, `\ifx`,
`\ifcat`, `\ifcase`) need a token scan to find where their operands
end; a table of names cannot do it. They are counted for nesting and otherwise
left alone, and `TestTheConditionalsThatTakeOperands` asserts both halves of
that: the body is still converted, and the operand is still a word. A limitation
written as a passing test is a fact about the code; one written only in a
comment is a plan.

**Evidence.** Measured before the fix: `\iffalse \citep{hidden}
\input{ghost/sec} \fi` -> `[@hidden]`, includes `['ghost/sec']`;
`\ifdefined\foo \citep{shown} \fi` -> `ifdefined [@shown]`;
`\ifthenelse{1=2}{\citep{no}}{\citep{yes}}` -> `1=2[@no][@yes]`.
Six mutations are red: a dead branch converted as prose, a live branch losing its
body, the include reader not cutting dead branches, the `\else` inside a dead
block staying dead, the `\ifthenelse` test pasted back, and an unclosed live
conditional dropped. Seen 1.

## A note is a sentence, and a sentence spliced in the middle is a word the paper never wrote

**Rule.** `\footnote`, `\footnotetext` and `\marginpar` were inline
commands - the converter kept their argument and joined it to the words on
either side. `The method works\footnote{See \citep{fn} for the proof.}, and
we ...` converted to `The method worksSee [@fn] for the proof., and we ...`. The
string `worksSee` is in no paper, and `draft` proposed exactly that string as
the claim text, so the proposal rested on a sentence nobody wrote. A command
whose argument is a sentence of its own has to be separated, not inlined.

**Why the first fix was wrong too.** Giving the note its own paragraph *where it
was written* fixed `worksSee` and broke the sentence differently::

    'The method works\n\nSee [@fn] for the proof.\n\n, and we show it.'

The comma now starts a paragraph. A sentence that is interrupted has no single
place to put the interruption back; the only position that keeps the main
sentence whole is after it. So the bodies move to the end of the converted text,
which is where a reader of a paper sees them anyway.

**How to apply.** When a construct does not belong in the flow of a sentence,
the question is not "where does it go" but "what must stay whole". Here it was
the main sentence, and every in-place position fails at some punctuation. Then
check that the move does not drop what the body carries: the body is still
converted, so a citation inside a note is still a citation, and a note inside a
dead conditional is still dead. Nine mutations are red, including two that
survived the first pass - a body moved without being converted, and a
conditional branch that forgot to pass the collector down. Both looked covered
because the tests asserted the words survived, not that the body was read.

**Evidence.** Before: `'The method worksSee [@fn] for the proof., and we show
it on 40,688 examples.'`; the `draft` proposal carried `The method worksSee for
the proof., and we show it on 40,688 examples.` as its `claim:` text. After:
`'The method works, and we show it.\n\nSee [@fn] for the proof.\n'`. 26 tests in
`tests/test_latex_notes.py`; seven mutations, none surviving. Seen 1.
## A rule about punctuation is a rule about one writing system until you write down which

**Rule.** When a boundary is decided by punctuation, or a size by characters,
ask what the rule assumes about the space *after* the mark and about what one
character *is* in the text it will actually meet.  If the answer is "a Latin
sentence", write that down, or make the rule count something a reader of either
script would agree with.

**Why this keeps happening.** `_SENTENCE_END` read
`(?<=[.!?。！？])[\"'”’)\]]*(?:\s+|$)`.  The CJK full stops were already in the
character class - somebody had thought about Chinese - but the branch after them
requires whitespace or end-of-string, and Chinese puts nothing after a full
stop.  The mark was known; the habit it comes with was not.  In the same
function the floor and ceiling were characters: 40 and 400.  A character is a
letter in English and a syllable in Chinese, so the same two numbers describe
two different lengths and only one of them was measured.

**How to apply.** For each threshold, name the unit in the constant's name
(`MIN_SENTENCE_WORDS`, not `MIN_SENTENCE`), because a bare number in a shared
module reads as unitless.  Write the test with a sentence from the script the
rule was *not* written for, and assert the sentence boundary, not the constant.
Measure the change on real prose in both scripts before choosing the number:
the character window kept 37% of Chinese sentences, the word window keeps 86%,
and the word window keeps the same 84% of English ones, which is what makes it
a fix rather than a trade.

**The false reason is the real damage.** The refused paragraph did not produce a
crash or an empty file; it produced
`nothing on any page shares enough terms with the sentence (3 needed)` - a
sentence about a comparison that never ran, on a paragraph that shared eighteen
terms with the page.  A missed feature leaves a hole; a wrong reason fills it
with the wrong thing.

**Evidence.** `_sentences_of("第一句话。第二句话。第三句话。")` returned 1 run
after the fix 3; `draft` on a Chinese manuscript wrote `0 claim block(s)
proposed` with the terms reason, after the fix 1 block with 12 shared terms; the
settled window is `MIN_SENTENCE_WORDS = 7` / `MAX_SENTENCE_WORDS = 70`;
four mutations of the fix (latin-only splitter, one CJK branch instead of two,
count characters as words, restore the character window) are all red, 1 to 9
tests each.

Seen 1.
## The second mark set is the one you forgot, and the first one still passes its own test

**Rule.** When code names a set of punctuation marks - closing marks, stops,
space-taking marks - that set is a claim about every writing system the input
may arrive in.  Give it a name, test a mark from each script the tool claims to
handle, and check whether the same set is written out a second time somewhere
else.

**Why this keeps happening.** `statement_of` closed the gap a removed citation
leaves with `re.sub(r"\s+([.,;:!?])", r"\1", text)`.  The five Latin marks are
correct and the test for them passed.  They are also not the only marks a
citation can sit before, and the same file had already grown
`_SENTENCE_END` a week earlier with a CJK branch precisely because the same
assumption - that a sentence ends the way English ends one - had hidden a real
defect.  Fixing the splitter did not fix the *other* copy of the assumption,
because the two live forty lines apart and neither mentions the other.

**How to apply.** Name the set (`_NO_SPACE_BEFORE`) so it reads as a claim, put
it next to the other named sets in the file, and build the class from it with
`re.escape` so a `]` in the set cannot end the class early.  Write the test as a
loop over *every* member grouped by script, not one representative: the first
version of this test would have passed with the four CJK stops alone and left
the closing brackets broken.

**The same question from the other side.** The gap is a leftover, not a mark's
own spacing: `我们 [@p] 认为` must keep its space, because that space is between
two words and closing it up would run them together.  A fix that removed
"whitespace around punctuation" wholesale would pass the CJK test and corrupt
the Chinese sentence it was written for.

**Evidence.** `相关研究指出词汇与构式之间存在互动关系 [@page]。` gave
`相关研究指出词汇与构式之间存在互动关系 。` before the fix and the closed-up
sentence after; `他说：“好 [@p]。”` gave `他说：“好 。”` before; 12 tests in
`tests/test_cjk_statement_space.py`; four mutations (five Latin marks again,
stops only without the closing marks, keep every space, collapse all spaces)
are red with 3 to 9 tests each.

Seen 1.
## A converter's fallthrough is a claim about every command it has never seen

**Rule.** When the unknown-command branch says "drop the name, keep what it
wraps", ask which commands a document in the tool's own target language uses
that wrap nothing.  Those need names too, and the list is a claim about the
ecosystem, not about LaTeX.

**Why this keeps happening.** This file already had three tables - command
names whose arguments are prose, names whose first argument is skipped, names
whose arguments all go - and every entry in them came from a European paper.
The Chinese LaTeX stacks (`ctex`, `xeCJK`, `CJKutf8`) name fonts, point sizes,
line spreads and registry codes, and none of them appears in a mainland
European document, so none of them was ever met.  `\zihao{5}` therefore fell
through to "keep what it wraps" and `5` became the first word of the sentence.

**How to apply.** For each language the project claims to support, take that
language's standard LaTeX class and find the commands whose arguments are
fonts, sizes, spacing and registry codes - for Chinese that is `ctexart` plus
`xeCJK`, and the answer is fifteen names.  Test them where they appear: at the
left margin, in the middle of a sentence, inside a group, and followed by a
citation.  A command at the start of a paragraph is the shape that hurts most,
because the argument lands immediately before the first word the author wrote.

**What makes this one expensive.** The damage is not a crash and not a missing
citation; it is a *plausible* claim text.  `5 相关研究指出...` reads like a
sentence that begins with a number, so the author who pastes it into the
manuscript gets a claim block that scans, quotes correctly and cites the right
page - built on words nobody wrote.

**Evidence.** `{\zihao{5} 我们展示该方法。}` converted to
`5 我们展示该方法。` before and `我们展示该方法。` after; `\CTEXsetup[...]{section}`
gave `[format=]section`, `\ctexset{...}` gave `section/format=`,
`\setCJKmainfont{SimSun}` gave the font name; a `ctexart` draft went from
`claim: 5 相关研究...` to `claim: 相关研究...`; 18 tests in
`tests/test_latex_ctex_commands.py`; seven mutations, none surviving, 1 to 5
tests red each.

Seen 1.
## A character predicate is a claim about an alphabet

**Rule.** When a scanner decides where a word ends, `str.isalpha()` is not a
test for 'a letter of the language this file is written in' - it is a test
for 'a letter in some script', and it is true for Chinese, Japanese, Korean,
Cyrillic and Greek. In a language whose prose has no spaces, that turns the
rest of the line into part of the word.

**Why this keeps happening.** `\noindent` and `\par` are correct in a European
manuscript and always look right in the tests that were written for one. The
bug needs a document in the target language of this tool's *users* but not
of its *tests*, and the symptom is the opposite of a crash: the prose is
gone, so `draft` proposes nothing and `check` reports a clean run.

**How to apply.** Ask of each scanner: what is the alphabet here, and where is
it written down? TeX's own answer is ASCII letters, so this project writes
`[A-Za-z]` instead of asking Python. Then find every place that scans the same
thing - the converter, the conditional reader, the inclusion reader - because
a scanner is usually copied, and the copy is the site you forgot. Test with a
sentence in the target language glued to the command with no space, and test
what a digit does too: `\item1.` must keep its `1`.

**The tell.** If a converter has a test that passes a space between every
command and its text, that test is measuring the test's own habit.

**Evidence.** `\noindent我们展示该方法。` converted to `。` before and to the
whole sentence after; a four-line `ctexart` document went from `'。\n。\n。\n\n。\n。\n'` to its own prose; 28 tests in
`tests/test_latex_cjk_control_words.py`; three mutations, none surviving - the
digit mutation only turned red after `\item1.` became a test.

Seen 1.

## A word separator is a property of the script

**Rule.** The whitespace-delimited token is one way to write a language, not a
universal unit of text. A counter built on it returns one token for a whole
Chinese sentence, so every threshold stated in tokens silently becomes a
different threshold - or, here, an unreachable one.

**Why this keeps happening.** Splitting on whitespace is the obvious regex, it
is correct for English, and its failure mode has no exception and no wrong
text: the fuzzy tier simply answered "too short for a fuzzy comparison" about
a 40-character quote whose every character had just been compared. The report
was wrong about *why*, which is the harder kind of wrong to notice - the
tier's answer (`none`) was also what a healthy refusal looks like.

**How to apply.** Ask what a token is, then ask which of the thresholds in this
module are stated in that unit, because renaming is the cheap part and the
floor is the expensive part: `MIN_FUZZY_TOKENS` meant "five words" and now
means "five characters" for Chinese, so it has to be re-measured rather than
trusted. Measure it on prose in the target scripts, in both directions the
floor separates (a one-character typo must land above it, two unrelated
sentences must land below). Then check the *output* of the tier too: a window
of single characters joined with spaces prints `相 关 研 究` back to an author
who wrote prose.

**The tell.** If a length constant has no unit in its name, the unit is
whatever the module's oldest test happened to be written in.

**Evidence.** On the same page with one character altered,
`相关研究指出词汇与构式之间存在互动關聯，...` went from
`tier='none' reason='quote not found (too short for a fuzzy comparison)'` to
`tier='fuzzy' similarity=0.947`. Measured on 60 harvested sentences: typo
similarity min 0.667, 95% at least 0.857; two unrelated sentences at most
0.333. `tests/test_fuzzy_cjk_tokens.py` has 18 tests; five mutations -
whitespace tokenizer, character buffered instead of emitted, windows joined
with spaces, floor bypassed, page side uncounted - all red, the second only
after a no-space `构式used` case was added.

Seen 1.

## A character set says which characters are the same, not which ones belong

**Rule.** Normalising a family of marks into one character answers "are these
the same mark". It does not answer "is this mark part of the text". A quote in
quotation marks and the same quote bare are the same words and different
strings, and only the second question can tell you that.

**Why this keeps happening.** The two questions live in one function because
one function is where the marks already were. `_EQUIV` was written to make the
curly and straight quotes compare equal, which is right, and it was the only
place quotes appeared, so nobody asked the second question: the code was doing
the whole job it had been given, and the job it had been given was half of the
job that was needed. The failure is loud and self-contradicting - `[high]
quote-fuzzy ... not these words verbatim (closest passage, page 1, similarity
1.00)` - and it fires on the exact shape a humanities manuscript uses on every
page to introduce a quotation.

**How to apply.** When a normaliser maps a set of characters to one, ask of
each member whether it is *equivalent* or *decorative*; equivalence goes in the
normaliser, decoration needs a stripper of its own. Then make the stripper
conservative in three ways, because a mark can also be text (a book title's
`《》`): peel only on a matched pair, stop when what is left is empty, and
accept the second reading only when it produces a *stronger* verdict - a weaker
verdict about text the author did not write is not an improvement on the
verdict about the text they did.

**The tell.** A dictionary that maps eleven characters to one is a statement
that those eleven are interchangeable; if any of them can also mean something
in the text, that statement is only true for the comparison it was written for.

**Evidence.** On a page holding the sentence bare, `bare` came back
`tier='exact'`, and the same sentence in straight quotes, curly quotes, single
quotes, `「」` and `《》` all came back `tier='fuzzy' similarity=1.000` at high
severity. After the retry they are all `tier='exact'`. 25 tests in
`tests/test_wrapped_quotes.py`; six mutations, five red - no retry, peel one
layer only, peel an empty pair to nothing, drop the CJK pairs, peel the page
instead of the quote - and the sixth recorded here because it is equivalent on
the whole suite rather than merely untested: when the bare text does not match
either, the two readings agree, so no input separates them.

Seen 1.

## A table of names retyped in a second place is a table that will be
incomplete in the second place

**Rule.** When two readers have to recognise the same family of syntax, they
must share one table. Writing the names out twice does not create a second
opinion, it creates a second chance to forget one.

**Why this keeps happening.** Each pattern was written by someone reading the
format it parses, which is the right way to write it and the wrong way to keep
it right. `latex.py` lists the citation commands it converts; `draft.py` lists
the citation commands it can find in Markdown that has not been converted yet.
They were written at different times for different readers, both correctly, and
they diverged - `latex.py` gained `parencite` and `textcite` while `draft.py`
never did, and neither had the plural forms, because a plural command's shape is
different and neither author had met one.

**How to apply.** Put the names in a module both readers import, next to the
pattern that uses them, and test them **as a list**: one test per name, driven by
the table, so a name dropped from the table is a failing test rather than a
silently smaller table. If two tables cannot be merged yet, write a test that
asserts they are equal - a comment saying "keep these in sync" is not a
mechanism.

**The tell.** A `re.compile` whose alternatives are a hand-written `|` list of
domain names, in a file that has a sibling file with a similar list.

**Evidence.** `\cites{a}{b}` came out as `'ab'` with no citation site at all:
the pattern stopped at `cite`, and `s` is neither `*` nor `[` nor `{`, so the
command fell to the generic rule that drops a name and keeps the arguments.
`\fullcite`, `\parencite`, `\textcite`, `\autocite`, `\footcite`,
`\smartcite` and `\supercite` were missing from the same table, and the same
seven were missing from `draft.py`'s table. 44 tests now, one per name in each
file, plus eleven mutations across the two. Shipped in 0.19.86.

Seen 1.

## A recogniser that knows part of the syntax reports absence, not refusal

Rule: when a pattern matches a *subset* of the syntax it claims to read, the
missing cases do not fail - they fall through to whatever the surrounding code
does with "no match". Write down the grammar you are recognising, and write a
test for every production in it.

Why this keeps happening: a narrower pattern is invisible because the code
around it is correct. `citation_sites` returned `[]`, `draft` said "no
citations were found", and every layer agreed. Nothing raised, nothing was
half-parsed, and the message the author got described the *result* of the miss
rather than the miss. Measured: `[@a, p. 3]`, `[see @a]`, `[-@a, ch. 2]` and
`[@a, p. 3; @b, p. 4]` all matched nothing, so a manuscript citing a source in
every paragraph was told it cites nothing.

Pandoc's grammar is `[prefix @key suffix; @key2 suffix2]` - the bracket holds
prose and a locator, not only keys. I had implemented `[@key]` and `[@a; @b]`,
which are the two shapes a hand-written test happens to use when the author of
the test is also the author of the pattern.

How to apply: read the *format's* grammar, not your own examples of it. For
every production, ask which one of your inputs produces it; if the answer is
"none", that production is untested and probably unimplemented. Then check the
boundary the other way: what must not match. Adding a looser body pattern needs
a lookbehind on the `@`, or `[contact me at x@y.com]` becomes a citation.

The same pattern, read twice: `citation_sites` *finds* with it and
`statement_of` *deletes* with it. Every way of finding is a way of deleting, so
a command added to one and not the other leaves the command in the sentence
handed back as the author's own words. Adding `_LATEX_MULTI` to the finder last
round and not to the stripper is how `claim: | ... \cites{a}{b}.` reached
a proposal file. Deleting prose is worse than inventing a key: a wrong key is
visible in the ledger, a missing clause is not.

Evidence: `src/citevouch/draft.py:_PANDOC` and `_AT_KEY` before and after the
lookbehind; `statement_of` without the `_LATEX_MULTI` line; 50 tests across
`tests/test_pandoc_locators.py` and `tests/test_pandoc_brackets.py`; five
mutations in `_mut_pandoc.py`, two of which survived the first round because
the recogniser had boundary guards and the stripper was never asked about a
bracket that holds no citation.

Seen 1.

## A sentence about another command's exit code is a sentence nothing runs

**Rule.** If a message says what a *different* command will do, it is a claim
with no test behind it.  Either it names a code (so a reader can look it up) or
it says what this command found - never what the run will exit with.

**Why this one is worth keeping.**  `doctor`'s claims line read, from the day
the check shipped in 0.19.47:

    <file> holds no claim blocks, so every run will report 0 claims checked
    and exit 0

`check`, `verify` and `scan` had all reported `no-claim-blocks` and exited 1
since that same release.  The sentence was written by the commit that *fixed*
the silent green run, and it describes the behaviour that commit removed.  It
was wrong from its first release and stayed wrong for forty releases, because
no test ever read it and no reader who trusted it had a reason to check.

That is the expensive part: `doctor` is the command you run when a report looks
empty, and this was the line telling you the emptiness was normal.

**How to apply.**

- When you write a message that describes *another* command, name the thing
  rather than predicting its fate: "reports `no-claim-blocks` and exits 1" can
  be checked against `check`; "will report 0 claims checked and exit 0" is a
  promise nobody will notice breaking.
- Predicting failure is the safe direction.  A reader told the run fails goes
  and looks, and finds either the failure or a pleasant surprise.  Predicting
  success silences a reader, which is why the guard scans for `exit 0` only.
- Write the guard as a scan over the messages a reader can see, not over the
  one sentence that was wrong.  The next such sentence will be somewhere else,
  written by someone fixing the behaviour it fails to describe.
- Docstrings and comments are exempt on purpose: they quote history ("this used
  to exit 0") and that is a legitimate use of the old wording.

**Evidence.**  Before: `[FAIL] claims  m.md holds no claim blocks, so every run
will report 0 claims checked and exit 0`, while `citevouch check m.md --root .`
printed `[high] no-claim-blocks ...` and exited 1.  After: `... reports no-claim-blocks and exits 1: nothing in this project is
ever checked`.
Two mutations reproduce the failure - the old detail text, and a plausible
`exit 0` promise pasted into an unrelated message in `sources.py` - and both
turn `tests/test_no_predicted_exit.py` red.

Seen 1.

## A file you cannot read is not a file with no words in it

**Rule.** A reader that does not recognise a format must say so.  Never let a
fallback that happens to produce bytes stand in for "I read this document".

**Why.** A `.docx` is a zip.  Both PDF extractors refused it, and the plain-text
fallback decoded the zip into 120 characters of valid-looking nonsense and
returned them as page 1.  Nothing crashed: the run produced a well-formed
report that said `[high] quote-missing ... quote not found in paper.docx`.  The
author reads that as "my quote is wrong"; the truth is "your file is not the
kind of file I read".  The damage lands on the person who did nothing wrong,
which is the same shape as the `source-no-text` bug and the `no-claim-blocks`
bug: a tool whose silence or whose confident wrong answer describes the user's
work instead of its own limits.

**How to apply.** A fallback needs a precondition, not just a signature.  Ask
the file what it is (the first sixteen bytes) and refuse where the suffix was a
guess.  Keep the author's own statement of format authoritative - a `.txt` that
begins with `PK` is a text file because they said so, and the cache must not be
allowed to answer for a verdict: the refusal goes above the lookup, or the
diagnosis appears once and never again.

**Evidence.** Before: `sources.toml` pointing at a real `.docx` produced
`[high] quote-missing ... there is no passage in real.docx close to this quote`
and the run read as a citation failure.  After: `[medium] source-not-text at
real.docx: paper.docx is a Microsoft Word document - a zip archive, not
text - and citevouch reads PDF, HTML and plain text.  Convert it first, for
example `soffice --convert-to pdf paper.docx``, with `1 claim — 0 verified, 0
moved, 0 missing, 1 skipped` and exit 0 (`--fail-on high`).
`tests/test_opaque_formats.py` fails on four mutations: the suffix boundary
removed, the byte sniff removed, the zip magic changed, and the sniff moved
below the cache.

Seen 1.

## A region nobody renders is not a region that is absent

**Rule.** When a file format has places where nothing is shown to a reader -
script bodies, style sheets, comments - the reader of that format must remove
them by the format's rules, not by the one spelling the author happened to use.
And "never closed" has to mean "to the end", because that is what the format
says too.

**Why.** The HTML reader removed `<script>...</script>` with a regex that
required the end tag spelled exactly. HTML also allows `</script >` and
`</script\n>`, and a truncated file has no end tag at all. In every one of
those cases the body stayed in the page text. A sentence that exists only
inside JavaScript then came back `[info] quote-found ... quote found on page 1`
- a verified claim whose evidence is source code that nobody reading the
document would ever see. Two holes, one direction: the strict spelling is a
false negative that turns into a false positive once the leak is the quote
itself.

**How to apply.** The dangerous direction is not "we lost a page", it is "we
found evidence where there is none". So for every kind of region the format
marks as unrendered, ask both questions: which spellings does the format allow
for the end marker, and what does the format say when it never appears? For
raw-text elements the answer to the second is "it swallows the rest of the
document", which makes the safe default the same as the correct one. Also worth
noting where the tests go: a helper-level test on the stripper is not enough
because the verdict is produced by the extractor, so the file asserts both.

**Evidence.** Before, this project verified a quote that appears only in a
`<script>` body:

    <p>intro</p><script>var t='The method works on every corpus we tried.';</script >

produced `1 claim - 1 verified, 0 moved, 0 missing`, exit 0. `</script >`,
`</script\n>`, an unterminated `<script>` and an unterminated `<!--` all leaked
the same way. After: `tests/test_unrendered_regions.py` (15 tests) goes red on
five mutations - the exact-spelling end tag, an unterminated region stopping at
the opener, comments not being a region, an unterminated comment stopping at the
opener, and `style` dropped from the region list.

Seen 1.

## Advice is derived from the input, not from the case the check was written for

`source-no-text` was written for a scanned PDF and its one message ended with
`ocrmypdf <file> out.pdf`.  The same function answered for every format, so an
empty `empty.txt`, a whitespace-only `blank.md`, `<article/>` and
`<html><body></body></html>` all received that sentence.  Measured before the
fix: `found no text at all in empty.txt (1 page(s)); a scan has no text layer,
and OCR is what turns one into a file that can be searched (for example
\`ocrmypdf empty.txt out.pdf\`)`.  None of it can work - a text file has no text
layer, and OCR does not untag a document.

- Rule: when a message tells the reader what to do next, that advice has to be
  chosen from the input the reader actually has.  A single sentence for a class
  of inputs is advice written for one member of the class.
- Why: the tool's answer was right (there is no text) and the next step was
  wrong, so the reader runs a command that cannot help and concludes the tool is
  confused.  A correct verdict with wrong advice costs the reader a round trip.
- How to apply: pass the discriminating fact (here the suffix) all the way to
  where the sentence is built, including on the cache-hit path, and assert per
  input that each one reaches *its own* branch.  "No OCR" is not enough - the
  markup sentence has no OCR either, so a text file that fell into the markup
  branch passed the first version of the test.  Seen 1.

## A diagnostic that counts the inputs has not opened them

`citevouch doctor` reported every one of its eight checks `[ok]` and exited 0 on
three projects where `citevouch check` on the same tree exited 1.  Measured, all
three: a truncated `%PDF-1.4` file -> `check` exits 1 with `[high]
source-unreadable`; a scan with no text layer -> `[high] source-no-text`; a zip
renamed `.docx` -> `[medium] source-not-text`.  `doctor` saw `sources` bound to a
file that exists and stopped there, because the check it had was `is_file()`.

- Rule: a diagnostic whose subject is a file's *contents* has to open the file.
  Existence, a parseable manifest and a bound key are statements about the run's
  bookkeeping, not about whether the tool can read anything.
- Why: `doctor` is what a reader runs *instead of* the command that fails.  A
  green answer to a question it never asked is the one lie a diagnostic cannot
  afford, because the whole reason the reader is there is that they no longer
  trust the other command.
- How to apply: give the new check its own noun (here `extraction`), run it
  through the same cache the real run uses, and let it *stand aside* with
  `ok=True` when an earlier check already owns the failure - five lines that say
  the same unreadable file is one problem described five times.  Assert the
  standing-aside branches by building them (`monkeypatch` the extractor to return
  `source-missing`), because a branch no test can reach is the same thing as an
  untested branch.  Seen 1.

## A list of exceptions is a claim about every name not on it

Rule: when a reader removes the parts of a document that are not prose, the list of parts is
the whole design. Write down why each absent neighbour was left out, next to the list.

Why: the HTML reader dropped `<script>`, `<style>` and comments. `<template>` content is inert
by specification, `<textarea>` content is a form value, `<iframe>` content is fallback text -
none is painted as words on the page, all three were read as page text, and a sentence that
lived only inside one came back `[info] quote-found` with exit 0. The test file for exactly
this failure (`tests/test_unrendered_regions.py`) already existed and covered two of the five
names; the defect was invisible because nobody had asked which names were *not* there.

How to apply: a deletion list needs two comments - what is on it, and what is deliberately off
it and why. The second one is the one that stops the next round from being a one-line patch.
`<noscript>` is off the list because a browser does show it when scripting is off; `<svg>` is
off because it may carry real `<text>`. Both are now tests, because a decision nobody wrote
down is a decision the next change will silently reverse.

Seen 1.

## A delimiter is punctuation, and punctuation does not delete what it wraps

Rule: when a format marks a region with delimiters, the delimiters come off and the region
stays. A reader that removes the region has decided the content is not text, and that decision
needs its own reason.

Why: `<![CDATA[ ... ]]>` means "nothing in here is markup", and it is how a feed, a JATS article
and an OAI-PMH record deliver prose. The generic tag stripper matched it as one tag - `<`
followed by `!` is exactly what a doctype looks like - so a source reading `We collected
<![CDATA[9,800]]> rolesets.` extracted as `We collected roleset` and the claim quoting that
sentence came back `[high] quote-missing` with the source file named. The author goes looking
for a copy-paste mistake, and the file on disk has the sentence in it.

How to apply: unwrap before you strip. Keep an unterminated region's content (a truncated save
should lose the delimiters, not the document). And strip the unwrapped body again afterwards,
because the two things CDATA carries in the wild are a literal string (`a < b`) and an HTML
fragment a feed will render - one must survive tag removal, the other must not, and the tag
rule already tells them apart.

Seen 1.

## A recording holds what the writer understood, not what the reader lost

Rule: when a command reads a record instead of the source, ask what the record has no room
for, and make that command recover it - or say it did not. The record is a summary of a
particular reader's understanding; everything that reader rejected is absent by construction.

Why: `scan` writes a ledger of the claim blocks it accepted. A block with no `id=`, an id used
twice, or a fence that is never closed has no evidence to record, so it has no row. `verify`
and `check --use-recorded` walk the ledger, so on a manuscript holding one good claim and one
block missing its `id=` they reported `[info] quote-found`, `1 claim - 1 verified`, exit 0 -
while `scan` on the same tree exited 1 naming `manuscript.md:9`. `action.yml` runs
`check --use-recorded`, so the CI job a contributor actually sees was the green one.

How to apply: a verb that reads a record may re-read the source only when the record proves it
describes that exact text. Here that proof is the manuscript digest the ledger already stores,
which is why the recovery lives behind the hash comparison and `--allow-stale` turns it off: a
finding about a paragraph the ledger never recorded would be a verdict about a document this
run has not read. And recover *everything* the record dropped, not the first example of it -
reporting one refused block out of two leaves the second block exactly as invisible as both
were before.

Seen 1.

## A delimiter scan that stops at the first closer cannot tell one block from two

Rule: when a construct is delimited by a pair of marks, treat a second opening mark found
inside the body as evidence that the pair does not match, not as body text. Report the
mismatch and keep both constructs; never let one of them be absorbed into the other.

Why: two claim blocks written back to back with the first closing fence missing produced a
scan that ran from the first opener to the *second* block's closer. The second block's opener
and quote became the first block's quote. Measured on a two-block manuscript whose sentences
were both on page 1: `scan` exited 0 and wrote a ledger holding `['c1']`, while `check` exited
1 with `[high] quote-missing at manuscript.md:3 (c1): ... ```` ```claim id=c2 sourc ```
- a quote the author never wrote. `id=c2` appeared in no finding and in no ledger row: the
author wrote two claims and one silently stopped existing, and the line they were sent pointed
at a quote they had not written.

How to apply: the reading that loses nothing is the only safe default. Here that meant
stopping the body scan at the nested opener, emitting `claim-block-unclosed` on the first
block naming the line where the second fence begins, and resuming the parse at that line so
the second block becomes a claim too. Choose the decomposition that keeps every construct
visible, then say out loud which mark is missing - an absorbed block is invisible in both the
report and the record, so no later command can recover it.

Seen 1.

## Two formats that document one shape must refuse the same files

Rule: when two file formats share one contract, write the checks against the contract
and run them where both readers reach them.  A check inside one reader speaks for that
reader alone, and the project then answers differently depending on which format and
which interpreter the user happened to pick.

Why: `sources.json` takes its mapping at the top level, so `sources.toml` with
`paper = "page.txt"` and no `[sources]` header looks like a manifest to one format and
like nothing at all to the other.  Measured: `check` told the author `no entry in
sources.toml ... add it to sources.toml` about a key three lines above the header it
asked for, and `doctor` said `[ok] sources.toml (19 bytes), 0 sources` and exited 0.
The first version of the fix lived in `read_manifest`, reading the parsed dict - which
on 3.11 is tomllib's and on 3.10 is the subset's, and the subset files those keys under
a bucket named `""`.  The same flat file was refused on one interpreter and silent on
the other, which is the defect the pre-scan exists to prevent.

How to apply: put the refusal in `_refuse_shapes_only_one_reader_follows`, on the text,
so both parsers reach it, and make the sentence the same one.  Then check the narrow
side: a key literally called `sources` and a dotted name each already have a more
precise sentence, and the first draft of this rule shadowed three assertions in
`tests/test_manifest_value_shapes.py` by firing before them.  A refusal that hides a
better refusal is a worse message with the same exit code.

Seen 1.

## A function nothing calls is a docstring claiming a feature

Rule: when a function has a docstring saying what it is for, some test must reach it
or it must not exist.  A function only a future reader will find is a promise the tool
cannot keep, and the docstring is where the promise is written.

Why: `verify.doi_index` was documented as the map for "the optional Crossref
cross-check".  There is no Crossref cross-check, and `AGENTS.md` says one would belong
in a separate optional command rather than inside `scan`/`verify`/`check` - so the
docstring described a design the repository had explicitly declined, and nothing ran it
to say so.  `verify.rebuild` said it existed "so the CLI has one call per verb" and the
CLI imports `verify` directly.  `verify.summarize` was a second copy of the sentence
`report.py` writes.  `sources._odd_bindings` pluralised a manifest's bad keys into one
sentence while the live code writes that sentence per key.  Measured with an AST scan of
`src/`, `tests/` and `tools/`: all four names appear nowhere.  Deleting them took
`verify.py` from 90% to 96% line coverage and changed no test - which is exactly the
problem: nothing was running them.

How to apply: resolve per module, not per name.  `draft.summarize` is a real call and
`verify.summarize` is not; a scan that collects attribute names alone counts them as one
use and finds nothing.  `tests/test_no_dead_functions.py` does the per-module version and
carries a liveness test of its own, because a resolver that reaches nothing makes the
guard green and meaningless.

Seen 1.

## A suffix is what the author meant; the first bytes are what the file is

Rule: when a reader is chosen from the file's extension, read the
extension as a claim and spend five bytes checking the one case where
being wrong is expensive - a format this tool has a dedicated reader for
arriving under a name that routes it to the fallback.

Why: `paper.txt` holding a PDF was read by the plain-text path, which
succeeded: 4 pages and 206,870 characters of mojibake, `problem=None`.
Nothing downstream could tell that from text, so the run reported
`quote-missing ... no passage in the source is close to this quote` about
a page that does contain the quote. The author's mistake was a file name;
the accusation was about their evidence. A suffix is one word the author
typed, and it is the only thing standing between a good reader and a bad
one.

The fix is not to disbelieve every suffix - a `.txt` that really is text
must read the same as it always did, and this tool never overrides a
suffix it has no better reader for. It sniffs exactly the case it can
improve: `%PDF-` in the first five bytes, any name. If the check is
wrong, the file reaches the PDF reader, which refuses out loud with
`source-unreadable` - a sentence about the file rather than about the
quote, which is the direction that costs the author least.

How to apply: read the fixed number of bytes, not the whole file, and
compare them to the whole magic (`== b"%PDF-"`, not
`.startswith(b"%PDF")`, which accepts a five-byte file); a header that
appears later in the file is a file *about* a PDF. And when the reader
changes, the cache key has to change with it - the entry is stored under
the reader that ran, so a run that cached mojibake as `plain` cannot hand
it back after the fix.

Seen 1.

## An exemption is a claim about intent, and the wrong name is exactly

where intent and file disagree.

Rule: when a rule is skipped because "the author told us", name the
input that made the statement, and handle the case where the
statement and the file disagree. If the skip has no such case, the
skip is a guess wearing the author's name.

Why: `_KNOWN_SUFFIXES` exempts `.txt`, `.md`, `.text`, `.html`,
`.htm`, `.xml` and `.pdf` from the header sniff, on the ground that
the suffix is the author stating the format. v0.22.0 shipped that
argument and v0.22.1 then found the case it does not cover: a
`.docx` saved as `paper.txt`. The suffix was wrong, the plain
reader succeeded on the zip, and the run answered the author's own
quote with `[high] quote-missing ... quote not found in real.txt`.
The exemption existed for a good reason - a note reading
`PK\x03\x04 is the four bytes a zip begins with` is prose - and
that reason was still true in the case that broke. Both are
measurable: 47 replacement characters and C0 controls in 196
characters for the zip, 2 in 73 for the note. The difference is in
what came out of the reader, which is the thing the exemption never
looked at.

How to apply: judge the output of the exemption, not just the input
that granted it. Here that means the noise score
`textnorm._decode_text` already trusts, plus the file's own header
to confirm the format the noise suggests - the score alone would
refuse a PDF whose extractor left a control character, and the
header alone would refuse the note about `PK`. And exempt the
reader that already answered for the file: a PDF's bytes were
checked against the header before extraction, so its pages are not
re-litigated afterwards.

Seen 1.
## A second table of names is a table that will be short

`draft.py` needed to recognise LaTeX citation commands, and `latex.py`
already knew them. Rather than import the names, `draft.py` typed its own
copy — and the copy fell behind: `latex.py` listed `citeyearpar`, `draft.py`
did not. The visible result was the worst of the three possible shapes.
`to_text` converted `\citeyearpar{k}` into a `[@k]` marker, and `draft` then
reported "no citations were found" while that marker sat in the very text it
was reading. In a mixed sentence, `Prior work \citep{a} and
\citeyearpar{b} agrees.`, `draft` found only `a`, dropped `b` without a word,
and handed the author `Prior work and \citeyearpar{b} agrees.` as the
sentence to paste into their manuscript.

Two more names were missing for a different reason: natbib's capitalised
forms. `\Citet` and friends are what an author writes when a citation opens a
sentence, so they are the *first* citation any reader of the paper meets.
Neither reader knew them at all: the key became a bare word on the page and
the manuscript was reported as citing nothing.

How to apply: when a module already owns a list of names, the second module
imports it, even when the import is one line deeper than retyping. A copied
list is wrong in the direction that is silent — it recognises *most* of the
input, so nothing crashes and the missing name looks like a document that
simply did not cite that source. Where two readers must agree about a
pattern, export the table (and the whitespace rule with it) and build both
patterns from it, then assert the two agree on a shared set of inputs rather
than each agreeing with itself.

Seen 1.

## A measurement that includes what the tool declined measures a different set

Rule: when a gate hands a tool a list of files, the number it prints must be
the number the tool *judged*, not the number the gate named. Ask the tool what
it did.

Why: `tools/format_check.sh` counted every tracked `*.py`, `*.md` and `*.toml`
and handed all three to `ruff format --check`. Ruff has no TOML formatter, so
it declined those files without complaint and printed `2 files already
formatted` where the script had counted 3. Every commit message in this
repository quotes that count, so the quote drifted by the number of tracked
TOML files - and the drift was invisible until the lint job compared the two
and said `says 147 formatted files, ruff reports 146`.

The second half of the same discovery: the script never checked that ruff had
said anything at all. A tree whose only tracked file was a `*.toml` printed
nothing and exited 0, so a gate that judged zero files reported success. A
summary line that is missing is not a summary line that agrees.

How to apply: parse the tool's own summary instead of recomputing it, and make
disagreement and silence both loud. A count that cannot be quoted should stop
the commit rather than be rounded to something that looks right.

What makes this one worth remembering: the gap was already written down. The
test file carried `declined = 2` with a comment explaining exactly which files
ruff refused. A comment describing a gap keeps it, and the next person reads
it as a specification rather than a defect. Removing the two TOML files from
the count is a two-character change; writing it down instead was a decision to
keep the mismatch.

Seen 1.

## A scratch file that is deleted after the commit is already in the commit

Rule: write the commit message to a path the index already refuses, or remove
it before `git add`. The order is `git add -A`, then commit, then delete - and
the delete is what makes it safe to write again, not what makes it safe to add.

Why: `cat > _msg.tmp` then `git add -A && git commit -F _msg.tmp && rm -f
_msg.tmp` is the shape used hundreds of times in this repository. When the
`rm` is the last command instead of the second, the file is inside the commit
that quotes it, so the tree carries a copy of the text describing it. That
happened three times with `.txt`, and `.gitignore` grew a line each time; the
third time was `.tmp`, which the ignore file had never heard of.

How to apply: ignore the family, not the instance - a pattern like `_msg.*`
covers the next extension somebody reaches for - and prefer a message file
outside the work tree (`/tmp/msg.txt`) when the shell allows it.

Seen 3.

## A file with one readable block is not a file that was read

Rule: any parser that skips a construct is silent only about the constructs it
understands to be skipped. When a file produces *some* results, every other
construct in it has to be accounted for - the "nothing found" path does not run.

Why: `citevouch` skipped claim fences that sat inside a blockquote, a list item
or an indent, which is correct (Markdown renders those as code samples), and it
had a good near-miss sentence for that shape. But `scan` printed that sentence
only when the manuscript yielded zero claims. One properly fenced block anywhere
else switched the whole accounting off: `scan` wrote `citevouch.lock.json
(1 claim)` and exited 0, `check` printed `1 claim — 1 verified, 0 moved,
0 missing`, and the second block's id was in no finding and in no ledger row.
Measured on a project whose `page.txt` held the sentence both blocks quoted.

The lesson generalises past this parser. A "did I find anything at all" branch
and a "did I account for everything" branch look like the same check and are
not: the first only runs on total failure, so the worse case - partial success -
falls through the gap the first one leaves open. Partial recognition reads like
a total, because the report says a number and never says what it is not
counting.

How to apply: after the parse loop, walk the input again for constructs that
match the shape of what you accept but were not accepted, and report them
per line - unless they are inside a region you deliberately skipped, which is
why the check has to know the spans you consumed rather than re-deriving them
from the text. Then keep the two branches from firing together: a file with no
claims at all gets the "nothing here" finding, not both.

## A count that sums what you read is not a count of what is there

Rule: when a check prints how many of something the input contains, the number
must come from the input. Summing the items your parser handled - accepted
plus refused plus skipped-partly - gives a total that moves whenever your
parser gets better at failing, and never moves for the thing it failed to see.

Why: `citevouch doctor`'s `claims` line printed how many claim blocks a
manuscript holds, computed from `len(parsed.spans)` and `len(parsed.claims)`.
Those two sets cover the blocks the parser consumed and the ones it accepted;
a fence it walked past because a blockquote or an indent put it out of reach
is in neither. Measured on a file with one good block and one blockquoted
block: `doctor` printed `[ok  ] claims      1 claim block`, and it went
unnoticed for a release because the *other* two numbers had been made to agree
earlier and the sentence only ever printed the smaller.

The general shape: a count built from your own bookkeeping is a count of your
bookkeeping. It drifts by exactly the size of the category you have not modelled
yet, and adding the next category is a change to the total rather than a
correction to a wrong one, so nothing looks like a bug when it happens.

How to apply: compare the printed number against an independent count of the
input - here, one finding per fence the parser did not read makes that count
available without a second parser. When the two disagree, the printed number is
the one that is wrong, even when the disagreement is small and even when the
check's own verdict is unaffected. And when a check delegates the *explanation*
of a fault to the next command, that is never a licence to delegate the
*arithmetic*.

## A guard written for one dialect licenses the others

**Rule.** When a format has more than one way to write the same construct, a detector
for a mistake in that construct must enumerate every way, from one table, and must say
which way it found. Fixing the dialect that the bug report happened to use is not fixing
the defect; it is fixing one third of it and making the remaining two thirds harder to
see, because the tool now appears to look.

**Why.** `claim-block-unread` (0.22.5) reported a claim fence that a blockquote, a list
item or an indent had put out of Markdown's reach. It matched `_BARE_CLAIM` - three
backticks or tildes and the word `claim` - and nothing else. The format has three
openers. Measured on one project holding a good fenced block plus one wrapped block,
`scan` and `check` each exited **0** with a ledger of `['c1']` for a wrapped comment, a
wrapped comment in a blockquote, a wrapped table row and a blockquoted table row; the
second block's id was in no finding and in no ledger row, and `check` called those runs a
verification. The five shapes, side by side, are in the CHANGELOG for 0.22.7.

The failure is not that the author forgot the other dialects. It is that a fix which
covers a third of the inputs *raises* the cost of the remaining two thirds: before the
detector existed, a wrapped block looked exactly like a block the tool had not been asked
about. Afterwards the author has been told the tool looks for wrapped blocks, so silence
reads as "none here".

**How to apply.** Put the openers in one table keyed by dialect, iterate it, and put the
per-dialect reason in a second table so the finding names the construct the reader
actually wrote - "move it to the left margin" is the whole fix for a fence and half a fix
for a table row. Derive each opener from the parser's own pattern (`_TABLE_CLAIM.pattern[1:]`
here, with its left-margin anchor removed) instead of retyping the shape, so the parser
and the detector cannot drift about what counts as the construct. Then write the test as
a table too, one case per dialect, and assert the sentences differ: a test that passes
when all three findings share one generic message is a test that will let the next dialect
be added silently.

*Seen 1.*

## A sentence about where to look is not a sentence about what is there

**Rule.** When a message explains *why nothing matched*, the matcher it uses has to be the one
the parser uses. A second, hand-written "roughly like a claim block" pattern is a second answer
to the same question, and it will be right about fewer files.

**Why.** `scan._no_claim_blocks_finding` explains a zero-claim run with `_CLAIMISH`, whose
`^\s*` prefix cannot cross a `>` or a `- `. A manuscript holding only blockquoted or listed
claim blocks therefore matched nothing, and the tool printed

> a claim block opens with three backticks, the word `claim`, then `id=` and `source=`. This
> file has none.

over a file whose first line was `> ```claim id=c2 source=paper page=1`. Measured: three files,
one per dialect, all three said it, all three with `line 0`. The parser already had `_WRAPPED`,
a table of exactly those shapes; the zero-claim path was written before it and never learned.

**How to apply.** Route the explanation through the parser's own table (`_unread_opener`) rather
than through a second regex, so a dialect added to the parser is a dialect the message knows
about. When the message names a construct, take the noun from the table entry the line actually
matched, not from the branch the code happens to be in - the indent branch called an indented
comment a fence for exactly that reason. And when several lines share the defect, print the
count: naming one line sends the author back for a second run.

**Seen 1.**

## An escape is the author being correct, and correct is the case that must not lose

**Rule.** When a format defines an escape, the reader must un-escape it before anything
else looks at the text. A delimiter scan that does not know the escape reports a
boundary that is not there.

**Why.** GFM's only escape inside a table cell is a backslash before the pipe. The table
dialect matched each column with `[^|]+?`, which stops at any pipe, so the row
`| c1 | paper | 1 | a\|b | t |` came back as quote `a\` and text `b`: the
quote was cut at the backslash and the rest of it was installed as the next column.
Written the way Markdown says is wrong, with a bare pipe, the same row gave quote `a`
and text `b` - so the spelling that obeyed the spec was the one that lost data, and the
spelling that broke it kept more. End to end the correctly escaped quote came back
`[high] quote-fuzzy ... similarity 1.00` and exited 1.

The same pattern also required one character per cell, so a row with a blank column
matched no dialect and was reported as `no-claim-blocks ... This file has none`. That
is the second half of the lesson: refusing a shape is a decision about what a file
means, and the safe refusal is the one that still names the thing it refused.

**How to apply.** Build the cell (or the token, or the field) as a pair - "one ordinary
character, or one backslash plus anything" - rather than as "anything but the
delimiter", then remove exactly the escape the format defines. Do not strip backslashes
in general: a quote may hold a Windows path or a LaTeX-ish sequence, and rewriting
those is editing the author's text instead of reading it. And give the empty case its
own meaning rather than letting it fall out of the pattern - here the meaning is
`claim-uncheckable`, because a blank column is a claim somebody has not finished.
Seen 1.

## The syntax that recognises a command and the syntax that consumes its argument must be the same syntax

**Rule.** When a scanner decides "this is command X, here comes its argument" and a later
step decides "here is where that argument ends", both must answer the same question the
same way. If one of them is written against the grammar and the other against the
spelling that happened to be in front of it, the gap is not a corner case - it is every
input the grammar allows and the spelling does not.

**Why.** `latex.py` recognised `\input {sec/intro}` as a file-inclusion command, because
`_INCLUDE_COMMAND` and `_BARE_INPUT` both carry `\s*` after the name. The step that then
consumed the argument, `_skip_optional_args`, skipped only `*` and `[..]` - so it looked
at the space, found no brace group, and left the command's arguments to the fallthrough
that keeps text. Measured across the six argument tables against the 104 commands whose
arguments must not reach the prose: **85 of them pasted the argument into the sentence**
when one space stood between. `\input {sec/intro}` became
`... examples. sec/intro The end.` - a file path read as two words of the paper, and,
because the part it named was never read, every citation inside that part missing too.
The same grammar hole hit `\textcolor {blue}{blue}` -> `blueblue`,
`\setcounter {page}{3}` -> `page` and `3` in the sentence, and `\footnote {note}` ->
`note}` in the body.

What makes it worth remembering is the shape of the mistake, not its size: the file had
already been fixed once for this exact family. A command-table entry was added, the
recogniser was widened, tests were written - and every one of them used the touching
spelling, so the fix moved the boundary of what is *recognised* without moving the
boundary of what is *consumed*. Two rules for one grammar drift apart exactly when the
second one is only ever exercised by inputs the first one accepts.

**How to apply.** When you teach a scanner a new command or a new argument shape, find
the function that consumes that argument and change it in the same commit; then write the
test with the spelling a human types, which is usually the spaced one, and the touching
one beside it. And when skipping filler before an argument, hold it *pending* rather than
swallowing it - spend it only if the argument actually arrives, because a command used as
a switch (`\bfseries`) has no argument and the space after it separates two words. The
pending form is what let `\footnotemark[1]` keep both its bracket and the space after it,
while `\input {x}` still found its brace.

Seen 1.

## Two pieces of prose placed flush produce a word that is in neither of them

**Rule.** When two pieces of text are alternatives that both belong to the
document, join them with a space; touching an alternative to its neighbour is
not a shorter spelling, it is a new token.

**Why.** `\ifthenelse{test}{yes}{no}` cannot be decided here, and both branches
are text the author wrote, so `latex._convert` keeps both. It kept them flush:
`\ifthenelse{1=2}{We report five}{We report these} results.` measured as
`We report fiveWe report these results.` — `fiveWe` is a token in neither
branch, and it lands in the sentence `draft` shows the author to paste into a
claim block. The same defect turned two citations into one run:
`\ifthenelse{1=2}{\citep{no}}{\citep{yes}}` came out as `[@no][@yes]`. The
branch was right in principle and wrong in punctuation, which is the shape this
repository keeps meeting: a fix that added the missing text without asking what
separates it from the text beside it.

**How to apply.** Replace flush concatenation of alternatives with one space.
Do not test a leading space instead of the separator: `to_text` collapses runs
of spaces (`re.sub(r"[ \t]+", " ", text)`), so an extra space before the first
branch is an equivalent mutant, and a mutation loop will report it as a
survivor that means nothing. Test the observable: no token spans the join, and
two citations stay two citations.

**Seen 1.**

## A table of names without their arity is a table of the one command you met

**Rule.** When a table exists to say "this command's arguments are metadata, not
prose", the unit of the table is not the command name — it is the command name
*and how many of its arguments the metadata occupies*. Two facts were missing
from `_BRANCH_COMMAND`, and both were needed before the table could be right:
which commands keep two branches of author prose at all (29 of them, between
`etoolbox` and LaTeX2e), and how many brace groups hold the test before those
branches (`\ifnumcomp` three, `\ifstrequal` two, `\iftoggle` one, and
`\ifdef\foo{yes}{no}` a bare control sequence instead of a group). A
`frozenset` cannot say the second fact, which is why the table was a set of one
name for two months: it answered "is this command special" and never
"how much of it is metadata".

**Why.** Measured before the fix (`B` = backslash):

```
to_text("X " + B + "ifboolexpr{test}{Yes words}{No words} Y")        -> 'X testYes wordsNo words Y'
to_text("X " + B + "ifnumcomp{1}{=}{2}{Yes words}{No words} Y")      -> 'X 1=2Yes wordsNo words Y'
to_text("X " + B + "ifdef" + B + "foo{Yes words}{No words} Y")       -> 'X Yes wordsNo words Y'
to_text("X " + B + "IfFileExists{sec/intro}{Yes words}{No words} Y") -> 'X sec/introYes wordsNo words Y'
```

Three failures at once in each line: the test was pasted into the sentence, the
two branches were glued into a word that is in neither of them, and `draft`
would offer that sentence to the author inside a `claim:` block. The full suite
did not change by a single test when the fix landed — 2300 passed before and
after — which is the second half of this lesson: a table nobody tests does not
announce the commands it forgot, it announces nothing at all. The count of
names a table covers is not the count of names the format has.

**How to apply.** Write the table as data whose value is the arity, then write
the test that walks the table itself (one case per entry), so a name added
without its count fails immediately. Add a second test that the table and the
test file's own list name the same commands: a name in one and not the other is
a name nobody checked. When a character has to be compared in more than one
place, spell it once in a module constant (`BACKSLASH = chr(92)`) — this file
mismatched that quoting layer twice while writing this very fix.

**Seen 1.**
## A reader that cannot follow the syntax must not consume it

**Rule.** When a parser hits a construct it cannot read to the end, it stops where
it started reading. It never answers "end of input", and it never silently
deletes the text it did not understand. Leaking the source into the output is
recoverable, because an author can see it. Deleting the source is not.

**Why.** `latex._definition_end` answered `len(text)` whenever the group it
expected was missing. A star was enough to trigger it: `\newcommand*{\x}{y}` puts
a `*` where the code expected a brace, `_group_end` answered `-1`, and the
definition ate the rest of the file. Measured on
`A. \newcommand*{\x}{y} The grammar is large.`: the converted text was `A.`, 32
characters gone, and no finding mentioned it. Six spellings take the star, and
three different "no group" paths (`\newcommand`, `\newtheorem`, `\def`) took the
same exit. The one failure mode a converter can produce which its user cannot
detect is a *short* output. A wrong word is visible on the page; a missing
paragraph is visible only to whoever remembers writing it.

It is the same shape as an earlier lesson in this file: `_balanced` returning
`len(text)` for an unbalanced expression. Two functions, two files, one answer.
The answer is wrong both times because "I cannot parse this" and "there is
nothing after this" are different facts, and only one of them is about the input.

**How to apply.** Separate the two facts. When a lookahead fails, return the
position the reader was at, not the length of the text, and give the helper its
own name (`_unreadable`) so the next reader sees the decision instead of a bare
`len(text)`. Then test the malformed spellings, not just the well-formed ones:
the well-formed ones were already covered, and that is why the deletion survived
for two releases. The tests that catch this are the ones that assert the *tail*
of the document is still there — `assert TAIL in converted` — because an
assertion about the beginning passes whether or not everything after it vanished.

**Seen 2.** The two sightings were an unclosed expression in
`textnorm._balanced` and a missing brace group in `latex._definition_end`.

## A reader that knows only its own key table has two silent paths, and one of them accuses the author

A claim body is a small key-value format: `quote`, `claim`, `numbers`, and the
attributes `id`, `source`, `ref`, `cite`, `page`, `marker`. Anything else shaped
like a key had no code path at all, so it fell through to whichever branch was
next — and which branch that was depended on where in the body the line sat.

Measured on one project whose quote really is on page 2, with the page hint
misspelt:

- `Page: 1` above `quote:` → the hint vanished, the claim was located by search,
  `[info] quote-found`, **exit 0**. Spelling it `page:` on the same project
  prints `[medium] quote-moved`. The typo turned a check off and nothing said so.
- `Page: 1` below `quote:` → the line joined the quote, the passage searched for
  ended in `Page: 1`, and the run printed `[high] quote-missing … The resulting
  grammar consists of a network of 40,688 constructions. Page: 1 — quote not
  found in page.txt`, **exit 1**. The tool's most serious sentence, printed
  because the author capitalised a key.

**Rule.** When a reader has a fixed vocabulary of keys, a line that *looks* like
a key is a third case: not a known field, and not prose either. Say both facts —
"this is a field, and I do not have that key" — and keep it out of the content.
Dropping it silently hides an instruction the author believes took effect;
passing it through as content invents an accusation they never made.

**Why.** A left-margin line inside a `quote: |` block is a sibling key in YAML
terms, so treating it as continuation text misreads the format the author is
writing in — and the misreading is invisible, because a quote that grew still
looks like a quote. The two paths fail in opposite directions, which is exactly
why neither can serve as the fallback for the other.

**How to apply.** Derive "looks like a key" from syntax (`^\s*name\s*:`), not
from a list of the keys you happen to know; then decide by position, because an
indented line is content and a left-margin one is not. Report the line number the
editor shows, and name the key. Pick the severity of the *loss*, not of the
finding: here the quote is still checked, so the loss is a hint that was not
applied — the same loss as `page-unreadable`, hence medium.

**Seen 1.**


## A success claim is about the outcome, not about the call returning zero

**Rule.** When a step recovers a half-finished operation, the thing it must
check is the operation's *outcome*, not whether the artefact it was building
exists. "The release exists" and "the release is published" are two different
facts; a recovery that asks only the first one reports success on a release
nobody can see. Read the outcome from the system that owns it (the API's
`isDraft`, the ledger's contents, the file's bytes), not from the step that just
succeeded at something adjacent.

**Why.** `gh release create` is three API calls — create a draft, upload the
assets, publish — and the composite command hides the seam. v0.22.14 died
between the first and the third: the create call answered `HTTP 502`, the draft
existed anyway, and the recovery step found it, attached the artefacts, and
exited zero. Every step was green and the release was invisible. A run that
fails is recoverable by a reader; a run that lies is not, because there is
nothing to read.

**How to apply.** After a recovery, ask the owning system for the final state
and fail if it is not what the step claims (`isDraft` again after publishing, a
re-read of the file, a re-parse of the ledger). Do the repairs in the order that
leaves a worse state on failure — attach the assets before publishing, so a
failure leaves a draft rather than an empty published release. And test the step
against a stub where "exists" and "is complete" are *separate* state, because a
stub that flips both together cannot express the bug.

**Seen 1.**


## A question answered by three tables is answered three ways

A page printing `40 688` and a claim typing `40,688` were compared by three
functions, each with its own notion of what a number is:

- `REPORT_PATTERN` — what a manuscript asserts. Refuses a bare space between
  digit triples, on purpose: "2019 2020 2021" is three years, not twenty
  million.
- `MASK_PATTERN` — what the numbers tier blanks out. Accepts an ASCII space and
  a non-breaking space, but not the thin, figure, narrow and hair spaces.
- `canonical_number` — what a value is compared by. Stripped only those same
  two characters.

So the same fact got three verdicts. With a bare space on the page the run
said `number-absent-in-quote` — about a figure printed right there. With a
non-breaking space it exited 0 saying `0 verified, 1 missing` and produced
**no finding at all**, so nothing anywhere explained the missing count. With a
thin space it said `quote-fuzzy` at "similarity 1.00" *and* the same false
number accusation. `fold()` had already declared every one of those characters
a space; only the number layer disagreed.

The fix was not to make three tables agree but to give the question one owner:
`CANON_PATTERN`, consulted by the canonical tier, by the page-side number
collection and by the claim's recorded numbers. A space counts only as a
thousands group — one to three digits, then exactly three — which is why
"2019 2020 2021" still reads as three numbers after the change.

Rule: when two functions must agree about a fact, give the fact one function
and have both call it. Two copies of an answer are a promise to keep them in
sync that nothing enforces, and the divergence surfaces as a verdict about the
author's document rather than as an error in the tool.

Why it happened: each layer was written to solve a *different* problem —
asserting, masking, comparing — and each solved it correctly on its own. The
bug lived in the seam, where "correct on its own" is not the property that
matters.

How to apply: before adding a second reader for a fact the tool already reads,
ask which one decides. If neither does, that is the bug. And when a run
reports "1 missing", make sure one of the checks it ran produced a sentence:
a count with no finding is a verdict the author cannot act on or even
understand.

Seen 1.

## A field with one producer is a cache, and a cache read as fact is a lie waiting for the producer to change

`Claim.numbers` is written by one function, from a string that sits in the same
JSON object: the claim's own `quote`. It is a derived field. It was stored in
the ledger, and `Ledger.from_json` read it back as though it were an
independent observation.

0.22.16 changed what "one number" means — `40 688` with a grouping space became
`40688` instead of `40` and `688`. A ledger committed before that change still
holds the old split, so a build that re-read the file compared `40` and `688`
against a page it now reads as `40688` and reported:

    [high] number-absent-in-quote ... the quote says 40 and 688 but page 1 of
    the source does not contain those numbers

about a quote that is *character for character* the page it accuses. Only the
tool's idea of where a number ends had changed.

Rule: a value that one function computes from something else present in the
same record is not evidence about the world — it is that function's previous
answer. Re-derive it on read; keep the stored copy only to check its shape.
A stale copy can only be older than its source, never better informed than it,
so trusting it converts an improvement in the tool into an accusation against
the author.

Why it is not leniency: the comparison still starts from the text the author
actually wrote, and a re-typed number is still absent from the page and still
`high`. What the tool refuses to do is compare a value against a *different*
function's older reading of it and then report the difference as the author's
error. A shape no writer ever produced (`numbers: 5`, `numbers: [1]`) is still
a damaged ledger and still refuses to load.

How to apply: when a stored field has exactly one producer and its input is in
the same record, the field is a cache. Ask what happens on the day the producer
changes. If the answer is "old records start failing", the reader must recompute
and the stored value is only a shape assertion. The tell is a CHANGELOG line
that says "re-run the command after upgrading" — that is the tool admitting the
reader trusts a copy, and no user should have to re-run anything to stop being
wrongly accused.

Seen 1.

## A fallback that decides what to check must not decide what to call it

**Rule.** When a lookup falls back from one name to another, the fallback may
choose the subject of the check; the message the reader sees must say which
name was actually used, and why.  "I looked this up as X because you wrote no
Y" is a sentence the reader can act on; "you cite X" is a sentence about
something they never wrote.

**Why.** `citevouch`'s `Claim` keeps two namespaces apart on purpose - `source`
names a local PDF, `ref` names a bibliography entry - and even says in its
docstring that conflating them produces false "key not in bibliography"
findings.  Then `verify.py` did `ref_key = claim.ref or claim.source` and wrote
`claim c1 cites 'paper', which is not in the bibliography the ledger recorded`
for a claim that writes only `source=paper`.  Measured on a project with a
`refs.bib` holding `knuth2020`: nothing in that manuscript cites `paper`, and
the one-line repair the sentence invites - adding `paper` to the bibliography -
is worse than the fault it fixes, because it puts a file name in a list of
publications.  The verdict was right the whole time and never changed severity;
only the words were wrong.  That is the expensive shape: a correct verdict with
a sentence that sends the reader to the wrong file.

**How to apply.** For every fallback `a or b`, ask what the finding, log line
or error message will print when `a` is empty.  If it prints `b` in the voice
of `a`, the reader cannot tell which branch fired, and the advice attached to
it will fit the wrong one.  Keep the fallback (a project that names its PDF and
its entry the same way should not have to write the key twice) and branch the
message instead.  Pin both branches in one test file, because a fix that only
rewords the fallback case can leave the named case describing the same lookup
twice.

Seen 1.

## A choice between two spellings is still a statement, and dropping the loser deletes it

`ref=` and `cite=` are two spellings of one claim attribute.  The parser reads
`attrs.get("ref", attrs.get("cite", ""))`, so a claim that writes both has said
one thing twice, and the run applies exactly one of the two.  Measured with
`refs.bib` holding `knuth2020` and a quote verbatim on page 1:

    ref=phantom cite=knuth2020   ->  exit 1
        [high] bib-key-missing at m.md:1 (c1): claim c1 cites 'phantom',
        which is not in the bibliography the ledger recorded
    cite=phantom ref=knuth2020   ->  exit 0, no finding at all

The two directions are not the same defect.  One accuses the author on the
strength of a value they may have meant to delete; the other deletes it in
silence.  What they share is that a statement written in the manuscript was
never applied and never mentioned - the shape the misspelt `Page: 1` field had
before 0.22.14.

**Rule.** When a format accepts two spellings of one attribute, writing both
is a question the reader has to answer.  Answer it out loud: name both values
and say which one was used.  Accepting the pair quietly is not tolerance, it
is a lost sentence.

**Why.** An alias table makes the reader *permissive*, and permissive readers
look correct from the outside.  The failure is invisible in every test that
writes one spelling, which is every test that was written by the same person
who wrote the table.

**How to apply.** For every `a.get(x) or a.get(y)`, ask what the finding says
when both are present and differ.  If the answer is "nothing", the sentence is
being deleted.  When the two spellings are on different lines (fence and body
here), the merge that fills in the missing key is the other place the pair
disappears - check the merged dict, not just the parsed one.

Seen 1.

## A decoder that cannot fail has decided that every file is text

`textnorm._decode_text` ended in ```raw.decode("utf-8", errors="replace")```.  The line is there so the tool never crashes on a file it cannot read, and the price is that it can no longer tell "this is text" from "I gave up": anything at all becomes a string, and a string is what the rest of the program asks for.

A page saved in GBK decoded to 54 characters of plausible mojibake with **one** replacement character in it.  The check that exists to notice a bad reading counts those characters and wants `max(4, len // 50)` - four.  Big5 gave two, Shift-JIS three, a cp1252 em dash one.  So the page was searched, found to contain nothing, and the author was told:

    [high] quote-missing at manuscript.md:1 (c1): 我们收集了 40,688 个例句，并检验它们的分布。
    — quote not found in page.txt

Rule: when a function is written so that it cannot fail, ask what it returns instead of failing, and whether the caller can tell that answer from a real one.  If it cannot, the failure has not been handled - it has been renamed.

Why: the fallback was not a mistake.  Without it, one odd byte anywhere stops the run, which is worse for everyone whose files are fine.  The mistake was believing that "the text decoded" is evidence about the file, when the decoder had been built to say that about every byte sequence it was given.

How to apply: the test that separates a reading from a guess is a stricter attempt that is *allowed to throw*, and it must run before the forgiving one, not after.  Here that is ```raw.decode("utf-8")``` with no handler - success proves the file is UTF-8, and failure proves only that it is something else, which is the answer the tool needed to hear.  Two exemptions survived this reasoning and both were decided by measurement, not by taste: a file that names its own encoding is never refused (a UTF-16 page of Chinese scores 0.33 on the same scale and reads perfectly), and a bibliography is not judged at all (a GBK `.bib` scores 0.11-0.24, a cp1252 French page 0.085 - no line separates them).  A threshold that cannot separate the groups it was invented for is not a guard, it is a coin.

Seen 1.

## A fallback that compares two readings has not asked whether either one is right

`textnorm._decode_text` had a fallback for UTF-16 without a byte-order mark: if the UTF-8 reading was noisy, decode as UTF-16-LE and keep whichever scored *less* noise.  The comparison is sound for a file that is genuinely one or the other, and it says nothing at all about a file that is neither.  A GBK manuscript is neither.  Read as UTF-8 it is noisy in proportion to how much prose it holds - 40 noise characters in 138 - and read as UTF-16 it is noisy too, just slightly less.  So the fallback took the wrong one, and the whole manuscript became `'탑뾾쫎...'`: fences, `quote:` keys, attribute syntax, everything.

The author was then told:

    [high] no-claim-blocks at manuscript.md:2: manuscript.md contains no claim
    blocks, so nothing was checked: a claim block opens with three backticks, the
    word `claim`, then `id=` and `source=`. This file has none.

Their manuscript had a claim block.  Worse, the code that fix replaced had been *better*: `raw.decode("utf-8", errors="replace")` kept every fence and turned only the Chinese lines into replacement characters, so the block was still there to be found.  The fix that was written to stop a false accusation introduced a bigger one.

Rule: when a fallback chooses between two readings, ask what a *correct* file of the winning kind would score, and require that.  "Less noise than the alternative" is a relation between two guesses; "zero noise" is a fact about one of them.  Here the fact is that byte pairs which came from a real character cannot decode to a control or a replacement character, so every genuine UTF-16-LE document scores exactly zero - measured zero in all twelve shapes - while an 8-bit file read that way scored something in 558 of 600 random samples, and in every single one that also held ASCII.

Why: a comparison always produces a winner.  A test produces an answer, and sometimes the answer is "not this".  The fallback could not say "not this" because it was written as a preference, so the presence of any winner was read as evidence that there was a right one.

How to apply: two conditions, because neither is sufficient and each was kept by a case the other one failed.  The zero-noise test alone admits cp1251 Russian and Shift-JIS Russian, which do read cleanly as UTF-16; the share test alone (`noise * 10 >= length`) is beaten by short genuine UTF-16 documents, where a tenth of the file is a small number.  Also check the fix against the code it replaces: if the new behaviour is worse for some input the old one handled, the fallback has moved the failure rather than fixed it.  Nineteen mutations were run against the guard family in this session; the two that survived the first round were both cases where no test held a file that was neither kind - which is the only kind that matters to a comparison.

Seen 1.


## A name list is a claim about every name not on it

`\footnote`, `\footnotetext` and `\marginpar` were moved out of the sentence they
hang on in an earlier round. The reason was measured and written down: keeping a
note inline glues its words onto the word before it, so

```
The method works\footnote{See \citep{fn} for the proof.}, and we show it.
  -> 'The method worksSee [@fn] for the proof., and we show it.'
```

`worksSee` is in no paper, and `draft` reads sentences out of the converted text
and offers one to the author as the claim to paste. The fix was a set of three
names. What was never asked is what the other names in the same family do.

Measured on the tree that fix left behind, four releases later:

```
The method works\thanks{We thank the annotators.}, and we show it.
  -> 'The method worksWe thank the annotators., and we show it.'
The method works\tnotetext{See the appendix.}, and we show it.
  -> 'The method worksSee the appendix., and we show it.'
```

and the same for `\marginnote`, `\sidenote`, `\endnote`. One of those is in every
funded paper ever written, written mid-sentence inside `\author`.

The rule: a name on a list like this is a claim that the name belongs on it; a
name missing from it is a claim that the words are part of the sentence. Only the
first kind of claim is ever checked, and it is checked by a test written at the
same moment by the same hand.

Why it matters here rather than as a style note: the failure is silent in both
directions. Nothing crashes, nothing warns, and the produced sentence is
grammatical-looking - `worksWe` reads as a typo a reader would blame on the
author. The tool's whole job is to say what is on the page; a converter that
invents words makes every downstream verdict a verdict about a text that does not
exist.

How to apply: when a fix is a list of names, ask what the list is a *sample of*.
For LaTeX commands the sample is every command whose argument is prose a reader
reads elsewhere - notes, thanks, table notes, margin notes - and the neighbouring
names are found by asking what the package family is, not by waiting for a user
to report the next one. The same shape appeared with the citation commands, the
file-inclusion commands and the 28 metadata commands: each fix started as the
names one paper happened to use.

Seen 2 (the citation table, and this).

## A quotation of a command is not the command, wherever the quotation lives

`included_files` reads the raw `.tex` source, and the raw source contains the
listing that *demonstrates* the syntax. A name written inside a literal
environment is an example. It was reported as a file the document pulls in:

```
\begin{lstlisting}
\input{chapters/intro}
\end{lstlisting}
```

produced `<!-- This document pulls text in from chapters/intro, which
`citevouch draft` does not read -->` - a false sentence in the one comment the
tool tells the author to check. The tool had already learned this for `\verb`
(five earlier fixes), and had not asked whether the same shape lives in block
form.

**Rule.** When a reader is shown a command, the command does not run. That has
to hold for every construct whose content is shown, not only the inline one that
was measured first.

**Why it happens.** The two questions "is a `%` here a character" and "is a
command here executed" look like the same question and are not. They agree on
`verbatim`, `lstlisting`, `minted` and `filecontents`, so one set seemed enough;
they disagree on the `comment` package's environment, where a `%` starts a real
comment and everything is still skipped. A shared set would have made one of the
two answers wrong, and the wrong answer would have been silent.

**How to apply.** For every construct that quotes text, ask both questions
separately and write down where the answers differ. Then measure the boundary
from both directions: a name inside must not be reported, and a name outside the
very next line must still be. A set that is only tested from the inside can be
"fixed" by making it swallow the whole document.

Seen 1.

## A reader that preserves what its grammar cannot see has decided that the difference matters

Windows editors write `\r\n`; this tool reads five grammars - claim fences,
attribute lines, paragraph breaks, BibTeX fields, Markdown - and not one of them
gives the carriage return a meaning. `read_text` kept it anyway, because
keeping bytes is what a reader is supposed to do.

The cost was not symmetric. A reader that strips a character its grammar cannot
see loses nothing it can use; a reader that keeps one hands every downstream
splitter a separator it does not recognise. `draft` splits paragraphs on `\n\n`,
found none in `\r\n\r\n`, and treated the whole manuscript as one paragraph. Two
files that differ only in how an editor saved them produced different claim
text:

    -  We collected 154,391 examples from the corpus, and we evaluated them on 9,800 rolesets.
    +  ## Methods We collected 154,391 examples from the corpus, and we evaluated them on 9,800 rolesets.

The author was handed a sentence nobody wrote, offered for pasting into the
manuscript, and the confidence dropped from `high` to `medium` because the
heading's words diluted the terms it shared with the page. The `.tex` path was
fine, because the LaTeX converter rebuilds the text instead of passing it
through - which is the tell: a bug on one input path and not another is a bug in
the shared reader, not in the consumer that noticed.

**How to apply.** For every file format you read, ask which characters the
grammar gives meaning to. A character outside that set is not data you are
preserving faithfully by keeping it - it is an unrecognised separator that will
silently divide nothing. Flatten it at the one place that turns bytes into text,
so a second reader cannot be added without meeting the same rule. And when a
difference between two inputs must not matter, assert that the *outputs* are
equal, not that each one is individually plausible: both drafts looked fine on
their own.

Seen 1.

## A token the parser kept and never read was a value the author wrote and the tool dropped

`_attrs` reads every `key=value` on a claim block's fence line into a dict. Six
names in that dict are ever consulted. A seventh is stored, and then the block
runs without it while every line of output is written as though it ran with it.

Measured on a project that prints the same sentence on page 1 and on page 3:

    ```claim id=c1 source=paper page=3   -> quote-found page 3
    ```claim id=c1 source=paper pgae=3   -> quote-found page 1, exit 0, no finding

The author asked for page 3 and was answered from page 1. Nothing said the hint
had been ignored - and the difference is not "the tool was lenient", it is "the
tool answered a different question than the one it was asked".

The body of the same block had refused this since the `Page: 1` fix, because a
left-margin line that reads like a field is visibly not continuation text and
someone had to decide what it was. The fence line never needed that decision:
`_attrs` consumes the whole line, agrees that these are attributes, and then
the reader's own key list is the only thing standing between a typo and
silence. A parse that succeeds is not a parse that was understood.

Two conditions made the report usable, and both had to be argued rather than
assumed:
- a near miss, so `data-x=` from some other tool is not accused of being a typo;
- the right spelling absent, so a block carrying both `page=3` and an unrelated
  `pgae=1` is left quiet - nothing was lost there, and a finding about a
  statement that was honoured is a false positive.

Transpositions cost one edit, not two. Plain Levenshtein scores a swap as two,
which would have put `pgae` for `page` - the most common typo in the language -
outside a distance-of-one net. The metric has to match the mistake, not the
textbook.

Seen 1.

## A mark that names a notation is not a mark that uses it

`scan_unbound_markers` asked whether a marker's characters appeared anywhere in
a line and reported the line if they did. That question cannot tell an
assertion from a discussion of the notation:

    > 这份节选保留了原档的【原文】/【实测】/【推测】三级标记约定，只是把

That is the demo's own manuscript, line 3. `citevouch scan demo/manuscript.md`
accused it of making a claim with no evidence on the page, three lines above
the first claim block, and the advice the finding earns — bind a claim block to
it — is advice to annotate a glossary. The two lines that really carry a bare
mark (52 and 54) were reported too, so the list looked right and was one third
wrong.

**The rule**: a convention that marks provenance marks it at the *head* of what
it vouches for. Once the Markdown that may stand in front of a sentence is set
aside — indentation including the ideographic space, `>`, bullets, ordered-list
numbers, emphasis — the mark either opens the line or it is a word in a
sentence. The scan now asks that instead.

**Why the miss is acceptable and the false positive is not**: a mark that
trails its sentence is no longer reported. That is a deliberate cost. A missed
nudge leaves the author where they were; a false accusation sends them to line
3 to annotate a glossary, and a tool that does that twice is a tool whose
output gets skimmed.

**How to apply**: when a check is `needle in line`, ask what else that line
could be. Here the answer was "a sentence about the needle". Adding a position
test costs one regex; not adding it costs every reader's attention on the first
false line.

Seen 1.

## An attribute the parser stores is a promise some reader will use it

`marker=` appeared on the opening line of a claim block in the first commit. It was
parsed, kept on `Claim.marker`, written into `citevouch.lock.json`, read back out of
it - and no code ever asked it a question.  The ledger therefore knew which mark
vouched for which block while `scan` printed, about the same line, that no block
tied the mark to anything:

    [low] claim-without-evidence at m.md:1: the 【原文】 mark on this line has no
    claim block, so nothing ties it to a page in a local source

Both statements were true of the implementation and only one of them was true of
the document.  A stored field is not a decision: it is an IOU that some reader
will settle.  When you add one, add the reader in the same commit, or list the
field among the ones deliberately kept for the writer's benefit and say why.

**How to apply.** For each field the parser keeps, ask what would print
differently if it were empty - and, if nothing would, ask whether it belongs in
the format at all.  `grep -c` the field name across `src/` before believing it is
read: four hits (the set of known keys, the writer, the JSON writer, the JSON
reader) is a field that goes round in a circle.  The reader here also had to be
narrow: the binding silences a finding, so it may only fire for the paragraph
beside the block, and only when exactly one block wants that mark - a fix that
silences too much is the same defect wearing the opposite coat.

Seen 1.

## A number that counts what you recorded is not a number that counts what you read

`citevouch: 1 claim — 1 verified, 0 moved, 0 missing` is the last line of every run, and it
was built from `ledger.claims`. The ledger holds the blocks the parser *accepted*. A block
with no `source=` is refused: it produces a `[high] claim-uncheckable` finding and no claim,
so it is invisible to a sentence that counts claims, and the sentence describes a smaller
document than the one just read.

Measured, on a manuscript holding one accepted claim and one block with no `source=`:

```
[high] claim-uncheckable at manuscript.md:6 (c2): claim c2 names no source=; the quote cannot be looked up
[info] quote-found at manuscript.md:1 (c1): quote found on page 1
citevouch: 1 claim — 1 verified, 0 moved, 0 missing
```

Two blocks were in the file. The run was red, so no failure was hidden from the exit code —
the lie is in what the reader learns about their own document.

**The tell** is the noun. The sentence said "claims" and the file holds "blocks". Those are
two different populations whenever some input is rejected, and the writer, which only ever
sees the surviving population, cannot tell that they differ. Ask the reader that saw the
rejections — here, the parser's span list, one subtraction, `len(spans) - len(claims)`.

**Do not special-case one refusal.** A counter bumped at each refusal site is three chances
to forget and three places to keep in step. The difference between "found" and "recorded" is
one number for one question, and it happens to be exactly the blocks nobody could check.

**Getting the other formats right is not a copy of the first.** The CLI has three writers
(text, JSON, Markdown) and two of them went red only after tests were written for them: the
mutation run found `--format json` and `--format markdown` both silently unchanged, because a
clause present in one writer is a fact about that writer. A tool whose report has three
formats has three chances to describe a document it did not read.

**The other direction is a real error too.** An unclosed fence is a reading problem, not a
missing block: the parser still yields a claim for it, so counting it as "not checked" would
claim the tool skipped a block it actually checked. Only *refused* blocks belong in the gap.

Why it matters: the summary line is the one sentence a reader quotes into a review, a commit
message, or a status update. It is also the one sentence a test is least likely to read,
because it is not a finding — nothing crashes, nothing exits differently, and the numbers
look arithmetic.

Seen 1.

## A list that answers one question will be wrong for the next question asked of it

`ParseResult.spans` was built to answer a specific question: which line ranges must not be searched
for prose? That question needs a *wide* answer. A manuscript may show a fenced ` ```python ` block
whose body contains the word `claim`, or a `` ```claim `` fence inside a sample; if those ranges are
not marked as consumed, the prose scanner reports the sample's own body as a claim block the parser
failed to read. Widening the list is the correct fix for that question, and it was fixed that way
twice.

Then a new question arrived: how many claim blocks does this file hold? The cheap answer was the
same list. It is wrong in exactly the direction the earlier fix made it wrong. One real claim plus
one Python sample printed:

```text
citevouch: 1 claim — 1 verified, 0 moved, 0 missing
2 claim blocks — 1 of which this run could not check
```

There was one block. Nothing was reported as a finding, because the second "block" was not a block —
so no test that reads findings could see the lie. `doctor` said the same thing in its own words, and
`doctor` is the command the README tells a confused author to run first.

The tell is not the number. The tell is the direction of the error. `spans` was widened on purpose to
stop false *accusations*; reusing it for a *count* turned the same widening into a false *claim of
coverage*. Whenever a collector is deliberately generous, ask what it was generous *for* — a structure
that over-counts in service of "do not accuse" will over-count in any other role too.

The repair is not to narrow the list. Narrowing it breaks the thing it was widened for, and the test
that protects that purpose (`test_the_wider_list_still_covers_the_sample_for_prose_checks`) is the one
that would have to fail first. The repair is a second list with the narrower rule, produced at the same
place, so both questions are answered by a collector built for them.

How to apply: when you add a count or a total, name the question it answers and check that the
collection was gathered for that question. If two call sites share a collector and one of them needed
it generous, the other one needs its own.

Seen 1.

## A gate that runs in one shell must be exercised in the shell that runs it

`tools/format_check.sh` printed nothing and exited 1 on this machine while the underlying `ruff`
command, run by hand on the same file list, printed `170 files already formatted` and exited 0. The
five tests that run the gate went red with `AssertionError: (1, '', '')` — a failure with no text to
read, which is the most expensive kind.

The script contained `[ "$status" -eq 123 ] && status=1` under `set -eu`. Under the `sh` that ships
with this shell that line terminated the script before the summary was written. Under Git Bash, and on
the Linux and macOS CI runners, the same line is fine. This is why CI had been green for months while
the local gate could not pass: the gate is the one script whose *result* is trusted without reading its
output, so a silently-red gate and a green gate look the same to a person in a hurry.

The part worth remembering is what the bisect found. The `&&` line was not fatal on its own. It became
fatal when the comment above it contained a period: `# ends with a period.` failed, `# a,` passed,
`# a b` passed. Five runs of each setting reproduced it. "The shell has a bug" is true and useless;
"the shell has a bug that a comment can trigger" is the observation that makes the next person stop
guessing and measure.

Two rules come out of it. First: a script that is a gate has to be run under the shell that will run
it, and its *exit code plus its output* both have to be checked — an exit code alone cannot tell
"nothing to report" from "stopped early". Second: a compound command used as a statement is a claim
that the shell's `set -e` semantics are the ones you learned, and the portable alternative (`if ... ;
then ... ; fi`) costs two lines and asserts nothing about the shell.

How to apply: when a gate fails with no output, do not read the gate as a logic problem — reproduce it
in a two-line script under the same interpreter first. If a comment changes the result, the failure is
in the environment, and the fix goes in the script shape, not in the reasoning.

Seen 1.
