# Notes for coding agents

You are working on `citevouch`, a small Python tool that binds claims in a manuscript to the
pages of local source files and fails CI when that evidence drifts. This file is the contract.
Read it before you change anything, and read [LESSONS.md](LESSONS.md) before you change anything
twice.

## What the tool is for

A claim is a sentence plus the verbatim quote that proves it plus the file the quote lives in.
Everything else in the repository exists to keep that triple honest. If a change makes the triple
easier to record but easier to fake, it is the wrong change.

## Ground rules

1. **The quote is the anchor; the page number is a hint.** Never make a page number load-bearing.
   PDFs re-flow, scans shift by one page, and a checker that trusts the page number reports drift
   that is not there and misses drift that is.
2. **Fuzzy is never verified.** `quote-fuzzy` exists so a human looks. It must never set
   `result.verified`, never be reported as `quote-found`, and never exit 0 on its own.
3. **No network.** Every code path in `src/citevouch` runs offline against local files. A check
   that needs Crossref belongs in a separate optional command, never in `scan`/`verify`/`check`.
4. **Exit codes are the contract.** 0 clean, 1 findings at or above `--fail-on`, 2 usage error.
   Do not invent 3. Do not raise where a finding is the honest answer.
5. **One finding per class where the class is common.** A 40-entry bibliography with 37 uncited
   entries is one line. A single missing quote is its own line. Findings users learn to scroll past
   are findings that no longer protect anything.
6. **The ledger is a lockfile.** `citevouch.lock.json` is committed, reviewed in diffs, and never
   hand-edited. Every change to its shape needs a `schema` bump and a migration path.
7. **Silence is a feature.** A run with nothing wrong prints the summary and exits 0. Do not add
   progress bars, banners, or "tip:" lines to the happy path.

## Where things live

| path | responsibility |
|---|---|
| `src/citevouch/model.py` | dataclasses, finding codes, severities, ledger JSON |
| `src/citevouch/textnorm.py` | normalization, whitespace and hyphenation folding, number extraction |
| `src/citevouch/manuscript.py` | the three claim dialects, unbound-marker scan |
| `src/citevouch/bibtex.py` | a self-contained BibTeX reader (comment, macro, concat, nesting) |
| `src/citevouch/sources.py` | locating sources, text extraction, on-disk cache |
| `src/citevouch/matching.py` | exact / squashed / fuzzy matching over pages |
| `src/citevouch/scan.py` | manuscript → ledger |
| `src/citevouch/verify.py` | ledger + files on disk → findings |
| `src/citevouch/report.py` | text, JSON, SARIF, Markdown renderers |
| `src/citevouch/cli.py` | argument parsing, exit codes, `init-demo` |
| `tools/next_version.py` | reads `## [Unreleased]`, decides the next version, rewrites the changelog |
| `.github/workflows/test.yml` | the gate: 8 matrix cells, lint, acceptance, offline |
| `.github/workflows/auto-release.yml` | green main → decides a version → commits, tags, calls release |
| `.github/workflows/release.yml` | tag → suite, build, clean-venv smoke test, publish, release notes |

A behavior change that crosses two of these rows is usually a design change. Say so in the commit.

## How a release happens

You do not tag releases and you do not bump the version in `pyproject.toml`. You write what changed
under `## [Unreleased]` in `CHANGELOG.md`, using a Keep-a-Changelog heading (`Added`, `Changed`,
`Fixed`, `Security`, `Removed`, `Deprecated`), and you leave the numbers alone. When the change lands
and CI is green on `main`, `auto-release.yml` runs `tools/next_version.py`, which reads what you
wrote and picks the number: `Fixed`/`Security` alone is a patch, anything else is a minor, an empty
section is no release at all.

Two consequences worth knowing before you write the entry:

- **The section you choose is the version you ship.** A `Changed` entry makes `0.2.0`; putting a
  behaviour change under `Fixed` to keep the number small is how a pinned `0.1.*` breaks.
- **A heading the script does not recognise releases nothing.** If you invent a heading, the work
  sits in Unreleased and no version comes out. Use the six names above.

## Acceptance criteria

A change is done when all of the following hold. Run them; do not assume.

```bash
python -m pytest -q                                  # all tests
python -m ruff check . && python -m ruff format --check .  # exactly CI's lint job, both halves
python -m venv .venv && .venv/bin/pip install -e .   # the package installs
python -m citevouch init-demo /tmp/x && cd /tmp/x && python -m citevouch verify manuscript.md  # the documented first run works
```

and, for anything touching matching, extraction, or normalization:

```bash
PYTHONPATH=src python -m citevouch verify demo/manuscript.md --root demo
```

`demo/manuscript.md` is a real project built from a real PDF pair. Four of its five claims must
verify and the fifth (`fcg-editor`) must fail with `quote-missing` — it is deliberately backed by
the wrong paper, and it is the regression test that the tool can still say no. If that claim ever
starts passing, matching has become too permissive.

For any new finding code:

- add it to `CODES` in `model.py` with a severity, and to `SARIF_RULES` in `report.py`;
  `tests/test_report.py::test_every_code_has_a_sarif_rule` enforces the pair;
- add a test that produces it and a test that shows the clean case stays silent;
- update the severity table in `README.md`.

## Commits

The message says what was wrong and how you know the fix is right. "Fix bug" is not a message.
Write the evidence: the failing case, the new test, the command you ran. If you could not check
something, say which part you could not check — an untested claim in a commit message is worse
than no commit message, because the next agent believes it.

## When you are unsure

Prefer the stricter reading. A false positive makes a user read one finding; a false negative makes
them ship a wrong number. The tool's whole reason to exist is the second failure.
