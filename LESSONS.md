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

## A command with no test is a command nobody has run

**Rule.** Every CLI verb gets at least one test that runs it end to end and asserts the exit code.

**Why.** `init-demo` was the one verb with no test, and it was the one verb that was wrong in three
different ways (no ledger, no test coverage of the refusal path, and a "wrote ..." message that
described files it had not finished making useful). Coverage is not the goal; the goal is that a
verb whose job is "leave the user in a working state" has somebody checking what state it leaves.

**Evidence.** `grep -rn "init-demo\|init_demo" tests/` returned nothing before this commit, while
`tests/test_cli.py` covered scan, verify, check, report, formats, exit codes, and error paths.
Now `test_init_demo_writes_a_project_that_the_documented_next_command_accepts` and
`test_init_demo_refuses_a_directory_that_already_has_something`. Seen 1.

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
a suppressed summary line. Seen 3, counting the two earlier wrong numbers
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
field except `generated_at` and `tool_version`. Seen 2 - the first was
`test_the_ledger_records_a_portable_path`, and it only ever checked sources.
