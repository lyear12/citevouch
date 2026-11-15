# Two ways to bind a review to a manuscript

CV-013 asks for two concrete alternatives rather than a preference, because the choice changes what
the tool is. This page states what is true today with commands that were run, then the two designs,
then the one question the Owner has to answer. Nothing here is implemented: the ledger's shape is
frozen at `schema: 1` until the decision exists.

## What is true today

The ledger records evidence, not attention. Its top-level keys are `schema`, `manuscript`,
`manuscript_sha256`, `generated_at`, `tool_version`, `sources`, `entries`, `bibliographies` and
`claims`; a claim carries `id`, `text`, `source`, `quote`, `page`, `path`, `line`, `marker`, `ref`,
`numbers` and `quote_fingerprint`. `marker` is the manuscript's own credibility label (【原文】 and
its siblings) copied through, not a record that somebody read the claim; there is no field in which
a person could write "I read this one". `quote_fingerprint` is a 16-hex-character blake2b of the
quote and its own docstring in `src/citevouch/model.py` says it "is not a security boundary".

Three measurements matter for the choice.

**The digest binds the whole file, and one edit invalidates all of it.** On a project with one
recorded claim, editing only the claim's prose (leaving the quote byte-identical) makes
`check final.md --use-recorded` exit 1 with one `[high] ledger-stale`, `verified: 0`, `skipped: 1`.
One sentence of ordinary authoring and the run stops evaluating evidence at all. That is the
honest behaviour, and it is the whole cost of the digest.

**`--allow-stale` removes the binding from the judgement.** The same edit with `--allow-stale`
exits 0, reports `[info] quote-found`, `verified: 1`. And when the *quote itself* is edited in the
manuscript - `from the corpus.` becomes `from the entire internet.`, with the source page unchanged
- the recorded pass with `--allow-stale` still exits 0 with `verified: 1`, while the live
`check final.md` on the same tree exits 1 with `[high] quote-missing`. The recorded pass compares
`ledger.claims[*].quote` to the page; it never says whether the quote now printed in the manuscript
is the one that was recorded. So today there is no per-claim content binding at all, only a
whole-file binding that one flag removes.

**The ledger already drops what it does not know.** Adding `"reviewed_by": "alice"` to a claim is
read without complaint (`check --use-recorded` exits 0), and an unknown top-level key is likewise
ignored - but the next `scan` rewrites the file from the manuscript and the key is gone. A review
recorded in the ledger today would survive exactly until the next authoring edit, which is when it
would matter.

## Alternative A - keep the hand-off manual

**Author steps.** Nothing in the manuscript or the ledger changes. The author records in the pull
request, not in a file: the claim ids are pasted into the PR description, the reviewer ticks them,
and `docs/final-manuscript.md` says so. CI keeps running `check --use-recorded` at `--fail-on
medium`. The `--allow-stale` hole is closed by documentation only: the page says the flag exists
for reading an old ledger, not for gating a pull request, and `action.yml` must never pass it.

**Content hash binding.** The whole-file `manuscript_sha256`, unchanged. A per-claim binding is
explicitly not attempted.

**Migration.** None. Every existing ledger keeps working, and no code changes.

**Defaults.** Unchanged. Exit codes, JSON, SARIF and the ledger shape are untouched.

**What it costs.** A review is invisible to a machine: a PR that reverts a claim after review, or
squashes two claims into one, leaves no artefact behind. The only defence is a person reading the
diff, and the tool cannot tell a reviewed manuscript from an unreviewed one. It also leaves the
`--allow-stale` semantic hole in place: `verify --allow-stale` can print `verified` for a quote the
manuscript no longer contains.

**What it buys.** Zero migration, zero schema risk, and no new way for the tool to lie. This is the
alternative that cannot be wrong, only insufficient.

## Alternative B - persist the review, and bind it per claim

**Author steps.** A new verb, `citevouch review`, in two shapes: `citevouch review --list` prints
every unreviewed claim with its line and excerpt, and `citevouch review c1 c3 --note "checked the
figure"` records the decision. `scan` never invents a review; `draft` never proposes one. A claim
whose quote changes becomes unreviewed again, because the thing that was reviewed is the pair
(text, quote), not the id.

**Content hash binding.** Each review stores `claim_sha256` over the exact bytes of the claim's
`text` and `quote`, normalised the way `quote_fingerprint` already normalises its input, plus the
reviewer label as a free string and an ISO timestamp. The binding is checked in the *recorded*
pass: a claim whose `claim_sha256` no longer matches its stored review is reported as unreviewed,
never as reviewed-and-changed. The digest stays a drift detector - a hostile editor who rewrites
the claim and the digest together is out of scope, exactly as `manuscript_sha256` is today.

**Migration.** `SUPPORTED_SCHEMA` goes 1 -> 2 in one release. `Ledger.from_json` keeps reading
schema 1 and treats its claims as unreviewed (which is what they are: no one recorded a review),
so old lockfiles never strand; `scan` writes schema 2 from then on. `--allow-stale` keeps its
current meaning and gains one sentence: it relaxes the whole-file digest, never the per-claim one.

**Defaults.** A new finding code would be needed - most likely `claim-unreviewed` at `medium`,
which is below today's default `--fail-on high`, so no existing project's exit code changes and
`action.yml`'s `--fail-on medium` does not either. Deciding the severity is part of the decision,
not a detail: `medium` means a green run for projects that never opt in, `high` means every existing
project now fails until reviewed. This document does not choose.

**CLI, JSON and SARIF.** Adding a verb does not change any existing one. The JSON gains a `reviews`
section only in schema 2 documents; SARIF gains one rule for the new code, which the existing
`CODES` <-> `SARIF_RULES` <-> README guard already enforces. `check --use-recorded` keeps its exit
contract 0/1/2.

**What it costs.** A schema bump, a migration rule, a new verb, a new finding code, and the
permanent obligation that `scan` not lose what `review` wrote - which today's writer would, since it
rebuilds every claim from the manuscript. It also creates a field that says a human looked, and the
tool cannot verify that a human did: `--note` is a string, not a signature.

**What it buys.** The review becomes an artefact that survives a re-scan, a review can be required
per claim, and the recorded pass stops being able to print `verified` for a quote the manuscript no
longer contains.

## The decision

**Question (one, for the Owner): do we accept a `schema` bump to 2 for a persisted per-claim
review, or do we keep reviews outside the tool?**

Choosing A closes this task with no further work and an entry in `docs/final-manuscript.md` saying
where reviews live. Choosing B closes this task and opens a separate bounded implementation task
(schema 2, `citevouch review`, `claim-unreviewed`, migration tests), which is where the severity
question above gets settled.

Either answer is recorded in `docs/iteration-state.json` as the explicit decision; this task is not
done until the answer exists. While waiting it sits at `needs_owner` with release condition "the
Owner answers A or B in writing", and no other ready task is blocked by it.
