# Code standards

These are the rules a change to `citevouch` has to satisfy before it merges. They are rules, not
suggestions, and each one exists because of something that already went wrong — the history is in
[../LESSONS.md](../LESSONS.md).

If a rule cannot be satisfied, say which one and why in the pull request. That is a conversation;
quietly breaking the rule is not.

## What a change contains

| rule | what it means here |
|---|---|
| Do only what the goal needs | A bug fix does not refactor its neighbors. A refactor does not change behavior. If both are needed, that is two commits. |
| Fix the class, not the sample | When a finding or a parse error shows up in one place, search the other modules for the same shape and fix them together. |
| A fix covers every sibling of the bug | If a number check fails on `48.4%`, ask what it does with `1,117,581` and with `e0269708` before writing the fix. |
| The change holds on the whole path | A matching change must hold for `scan`, for `verify`, and for `check --use-recorded`. A change that only holds when the cache is cold is not a fix. |
| Everything built on the change is re-derived | If the ledger schema changes, the demo ledger is regenerated in the same commit. A stale checked-in ledger is a broken build. |
| A failed read is unknown, not empty | When a PDF cannot be read, report `source-unreadable` and skip its claims. Never fall back to "no pages, therefore no match, therefore missing". |
| Values of another format come from that format | Page numbers come from the extractor, bibliography fields from the BibTeX reader. Do not recompute a page number in `verify`. |
| Nothing that can block runs under a lock somebody needs | The extraction cache is written by atomic replace, after the work, outside any loop that holds state. |
| A default never overwrites what the user set | `--ledger`, `--root`, `--fail-on` fill in only when absent. `sources.toml` wins over discovery, never the reverse. |
| Check the boundaries the change touches | Empty manuscript, one claim, a source with one page, a quote longer than its page, a page hint of 0 and of 10^6. |

## Findings

- A new code goes in `CODES` (`model.py`) **and** `SARIF_RULES` (`report.py`). A test enforces the
  pair; do not satisfy it by adding the SARIF rule without a description.
- Severity is decided by "what happens if a user ignores this". Wrong output = `high`. Needs a look
  = `medium`. Worth knowing = `info`. `low` is for things the tool cannot judge.
- A finding message says what is wrong and what to do. "Invalid claim" is not a message.
- One finding per member only when occurrences are rare. Thirty occurrences is one line.

## Tests

- No network. Any test that would need it is a test of the wrong layer.
- Real inputs: real BibTeX from the demo project, real extracted PDF text, real JSON from
  `to_json()`. Avoid synthesizing a dict that the parser would never produce.
- Test behavior, not implementation. Assert on findings, exit codes, and ledger content. Do not
  assert on private helper names.
- A test that fails on `main` is a bug that is happening now, not a known issue.
- Every new finding code needs two tests: one that produces it, one that shows the clean case stays
  silent.
- Break the code on purpose once and confirm the new test goes red. A test that cannot fail is worse
  than no test.
- Tests do not touch the user's machine: no writes outside `tmp_path`, no reading of
  `~/Desktop` or any other user directory.

## Acceptance criteria

A change is not done until all of these have been run and passed. Run them; do not assume.

1. **A test that fails without the change.** Name it in the commit message.
2. **The full suite**, not just the touched file:
   ```bash
   python -m pytest -q
   ```
3. **The package still installs and the entry point resolves:**
   ```bash
   python -m venv .venv && .venv/Scripts/pip install -e . && .venv/Scripts/citevouch --version
   ```
4. **The documented first run works from a clean directory**, including the command the README
   shows next:
   ```bash
   cd "$(mktemp -d)" && python -m citevouch init-demo cv-acceptance \
     && cd cv-acceptance && python -m citevouch verify manuscript.md
   ```
   Expected: `1 claim — 1 verified`, exit 0. A scaffold that leaves the user on a project where
   the next documented command fails is a broken first run, not a scaffold plus a missing step.
5. **The real demo still says exactly what it should:**
   ```bash
   PYTHONPATH=src python -m citevouch verify demo/manuscript.md --root demo
   ```
   Expected: 5 claims, 4 verified, 0 moved, 1 missing (`fcg-editor`), worst severity `high`, exit 1.
   A run that is greener than this means matching got more permissive — treat it as a failure.
6. **Offline.** If the machine has no network, everything above still passes. Verify this by
   reading the diff for `urllib`, `requests`, `http`, `socket`.

## Commits

- The subject says what was wrong. The body says how you know the fix is right.
- Name the failing case, the test that now covers it, and the command you ran.
- If something was not checked, say which part. An untested claim in a commit message is worse than
  none, because the next agent believes it.
- Do not amend a pushed commit to hide an intermediate failure. The failure is the useful part.
