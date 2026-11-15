# The final manuscript

This is the workflow this tool exists for, written as the order a writer actually does it. It carries
two decisions that are easy to conflate: whether the sentences are the ones you mean to submit, and
whether the evidence behind them still says what it said. The first one is a person's work. The
second one is a CI job that keeps the first one honest.

Everything below was run against `citevouch 0.26.1` installed into a clean virtual environment from
the published wheel, in a project whose only source is a one-page text file. The commands are
executed by `tests/test_final_manuscript_workflow.py`; if this page and that file disagree, the
suite is red.

## 1. Draft proposals for the manuscript you intend to submit

```bash
citevouch draft final.md --root . -o claims.md
```

`final.md` is the file you would send someone. It is not a scratch copy, and `draft` will not write
over it. The output is a proposals file; the interesting line is the one on stderr:

```text
citevouch: 1 claim block(s) proposed (0 verbatim), 0 citation(s) left as comments
```

`0 verbatim` means nothing was certified: every proposal is a `medium` guess that needs your
judgement. That is the normal shape of a first run.

## 2. Read the proposals

```bash
citevouch check claims.md
```

This answers one question — is the quoted passage on the page the proposal claims — and answers it
without touching the project's ledger, because `check` never records anything. It is not a review:
`check` cannot tell you whether the passage backs the sentence, which is the judgement you are here
to make. Read the `medium` entries yourself and delete the ones you do not accept.

If you want a ledger for the proposals — to compare two drafts of them, say — name a separate one:

```bash
citevouch scan claims.md --ledger claims.lock.json
```

A bare `citevouch scan claims.md` is refused, and the refusal names both documents. It used to
succeed: `scan` wrote whichever document it was pointed at into the ledger it was given, so scanning
the proposals replaced the record of the manuscript the project is about, with nothing on stderr,
and the next `check --use-recorded` reported `[high] ledger-stale` about a manuscript nobody had
touched. The proposals file itself still says which ledger to use, so following its header cannot
land you there either.

## 3. Copy the accepted blocks into `final.md`

Leave the blocks you rejected out of the manuscript entirely; an accepted block that keeps its
`page=` and `source=` is immediately checkable, and a block you half-edited is not.

## 4. Record the evidence

```bash
citevouch scan final.md
```

```text
citevouch: wrote citevouch.lock.json (1 claim)
```

Commit `final.md`, `sources.toml` and `citevouch.lock.json` together. The ledger records a digest of
the manuscript and of every source, which is what lets a later run tell "the evidence moved" from
"the sentence moved".

## 5. Gate the pull request on the recorded evidence

```bash
citevouch check final.md --use-recorded --fail-on medium
```

`--use-recorded` reads the committed ledger instead of re-deriving it, so the job compares the
manuscript against the record rather than against today's copy of the sources. `--fail-on medium` is
what makes it a gate: `source-changed`, `quote-moved` and `quote-fuzzy` are all `medium`, and the CLI
default is `high`.

## What the two edits look like

Editing a sentence that is not a claim is not a failure of the evidence — but the ledger records the
whole manuscript's digest, so the recorded gate says `ledger-stale` and stops. This is by design:
the digest cannot tell a prose edit from a claim edit, so the run refuses to pretend it can. The
recovery is step 4 again.

```text
check final.md --use-recorded --fail-on medium   -> exit 1   [high] ledger-stale
citevouch scan final.md                          -> exit 0   wrote citevouch.lock.json (1 claim)
check final.md --use-recorded --fail-on medium   -> exit 0   1 verified
```

Editing the claim itself is answered by the claim, not by the digest. Asking for a page the source
does not have is reported as `page-out-of-range` rather than quietly answered from page 1:

```text
check final.md   (page=3 of a one-page source)   -> exit 1   [high] page-out-of-range
```

Replacing the source file changes the answer entirely, and only the recorded run can say so, because
only it has the old digest to compare against:

```text
check final.md --use-recorded --fail-on medium   -> exit 1   [medium] source-changed
```

## What this page does not claim

The workflow above proves that the quoted sentences are on the pages they name and that the files
have not changed underneath them. It does not prove that any sentence follows from its quote —
nothing in this tool attempts that, and `README.md` says so in its own section. A green CI job on a
recorded manuscript means the evidence is where you said it was, on the bytes you said it was on.
