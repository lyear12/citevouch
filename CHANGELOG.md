# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Releases are cut automatically: when CI is green on `main`, `auto-release.yml` reads the
`## [Unreleased]` section below, lets `tools/next_version.py` decide the number, writes it here and
into `src/citevouch/_version.py` (the single place a version is written), commits, tags, and calls
`release.yml`. An empty Unreleased section means no release. `release.yml` refuses to publish if the
tag and that file disagree.

## [Unreleased]

### Fixed

- A quoted value in a brace-delimited entry can hold a literal `%`
  (`title = "A study of 78% of cases"`). The brace scanner began comment
  scanning inside quoted values, cut the line there, lost the entry's closing
  brace and read the rest of the bibliography as garbage - one stray `%` made
  every following entry vanish behind a single misleading `bib-unparsed-entry`.
  Quote state is now decided by the same lexer that decides brace depth.
- Chinese quotes are found. The word-boundary class was a hand-written
  `[0-9A-Za-zª-￿]`, which calls every CJK character a word
  character, so a quote could only end at a boundary if a space followed it -
  and Chinese prose does not put spaces there. Every short Chinese quote became
  a false `quote-missing` (high), which is the loudest possible way to be
  wrong about an author's evidence. Boundaries now use `str.isalnum()`, the
  squashed-tier length floor is script-aware (4 for CJK, 12 otherwise), and a
  quote that itself begins or ends with punctuation is not required to have a
  word boundary on that side.
- `numbers_in("2019 2020 2021")` returned `('2019 202','0 202','1')`: the
  pattern treated a bare space as a thousands separator, inventing numbers and
  writing them into the ledger, where they were later compared against the
  source. Only `,` and NBSP separate thousands now, and a test asserts that
  every reported number survives masking.
- Deleting the manuscript made `verify` pass. The hash guard was spelled
  `exists() and ...`, so a missing file skipped the comparison and every
  surviving PDF still matched: the command reported "verified" and exited 0
  about a document that was not on disk. A missing manuscript is now
  `ledger-stale` (high), as is a ledger recorded for a different document.
- A hand-edited ledger crashes out of the exit-code contract: `page` was read
  as whatever JSON held, so a quoted `"1"` reached a numeric comparison and the
  `TypeError` escaped as an uncaught traceback - exit code 1, which in this
  tool means "findings reached the threshold". Pages are coerced through one
  function, and a ledger whose `schema` is below 1 is refused as not ours.
- An unreadable source no longer manufactures `quote-missing`. A PDF nobody
  could extract has no pages, and searching no pages can only answer "not
  found" - a verdict about the file dressed as a verdict about the author, and
  repeated once per pass. Unreadable sources report `source-unreadable` once,
  their claims are skipped, and `check` no longer prints the same fact twice.
- A fuzzy match now fails the run on its own. AGENTS.md has always said a
  fuzzy match "must never exit 0 on its own"; `quote-fuzzy` is medium and the
  default threshold is high, so it did. The rule was in the table and not in
  the code.
- `report` no longer re-iterates an already-consumed findings generator when
  computing the worst severity, and `--quiet` now applies to JSON, SARIF and
  Markdown output instead of only text.
- `__version__` said `0.1.0` for four releases while the wheels were `0.4.1`:
  `citevouch --version`, the SARIF driver version and every ledger's
  `tool_version` were wrong, because the release tool rewrote `pyproject.toml`
  and nothing rewrote the literal in `__init__.py`. The version now lives in
  `src/citevouch/_version.py` and `pyproject.toml` reads it dynamically; a test
  fails if a second copy appears anywhere in `src/`.

### Changed

- `source=` must resolve through `sources.toml` or `--source`; discovery no
  longer claims a filename-similarity fallback it never had. Binding a claim to
  a PDF because the names share a prefix is exactly the guessing this tool
  exists to refuse, so instead of binding, the `source-missing` message lists
  the near misses on disk for the author to pick from. The candidate list is
  built by one directory walk per run and only when a key fails to resolve -
  ten unbound claims in a project holding a corpus should not mean ten walks.

- An entry whose delimiters never close (a `{` inside a `@comment`, an unclosed
  quoted value) silently swallowed every entry after it and reported nothing.
  `parse_bib` now emits `bib-unparsed-entry` (high) naming the line - the module
  had always promised to report what it cannot parse; this was the one hole that
  remained, and silence there means a false `bib-key-missing` downstream.
- Text stranded between entries by an early-closing brace (a genuinely escaped
  `\{` ends a value where depth says so) is reported as unread rather than
  discarded along with the fields it held.
- A malformed field no longer abandons the rest of its entry: the scanner
  resumes at the next `name =` and reports what it skipped
  (`bib-field-malformed`, medium).
- Required fields that are *missing* (not just present-but-empty) are reported
  by `field_findings`.
- `%` at field-brace depth inside a paren-delimited entry
  (`@article(a, note = "78.5% ...")`) is literal text, matching the rule braces
  already followed; comment-ness is decided by depth *and* quote state now.
- `@` headers that are not usable entries (`@in-book{...}`) are reported as
  skipped instead of stepped over; `bib-macro-unknown` fires when a field uses
  a `@string` no definition reaches; duplicate fields (case-insensitive) are
  reported with the first value kept.
- `matching`: the exact tier no longer matches across word boundaries ("in the
  paper" inside "a bin the papers" is no longer a quote); the squashed tier
  gained a minimum length; the numbers tier requires real words to survive
  masking and scores similarity on the unmasked text, so a pure-number quote can
  no longer "match" any page holding any number; `1 000` and `1,000` mask
  alike; squashed/numbers contexts show the matched region, not the page head.
- `number_spans` and `numbers_in` share one exported pattern
  (`textnorm.NUMBER_PATTERN`); masking spans and asserted spans can no longer
  drift apart.
- A page hint of 0 or below is `page-out-of-range` like an over-long one: the
  matcher ignores such hints, so the honest `quote-found` came out as a false
  `quote-moved`.
- The `_best_window` prefilter is bounded honestly: for needles longer than 10
  tokens every window is scored, because the skip rule's similarity bound
  (W-2)/W provably exceeds the threshold there.

## [0.4.1] — 2026-10-29
### Fixed

- The nightly dogfood picks the newest release by version number instead of
  GitHub's "latest" pointer — which follows creation date, so re-cutting an old
  release (as happened for real when the v0.2.1 artefacts were backfilled)
  pointed the nightly at a superseded wheel and would have reported it as
  fresh. Reading a stale pointer to test staleness defeats the check.
## [0.4.0] — 2026-10-29
### Added

- A nightly workflow installs the wheel from the latest GitHub release in a
  clean environment and replays the README's first commands, opening (or
  refreshing) a labeled issue when the published artefact no longer does what
  the documentation shows.

### Fixed

- The release machinery's own test stopped reading the live CHANGELOG.md. It
  asserted the next bump would be a patch while the file legitimately held an
  `Added`, so the gate turned red on every OS the moment the changelog described
  a feature — the machinery was fine, the test was racing it. The check now
  owns its fixture; a separate invariant test guards the real files with
  assertions that survive every release.
## [0.3.0] — 2026-10-29
### Added

- The lint job now runs `tools/check_repo_rules.py`, which decides the project's
  own mechanical rules: every non-release commit carries the
  `Run:` / `Not tried:` / `Broken by hand:` evidence sections, and every lesson
  marked `Seen` three or more times in LESSONS.md has been promoted into
  docs/code-standards.md. Rules the project states about itself stop being
  prose.

### Fixed

- The release bump regenerates CHANGELOG.md's link-definition block from the
  file's own release headings. It had drifted the way every human-kept version
  does: three releases after 0.1.0, the footer still compared "unreleased" to
  v0.1.0 and linked only that version.
- `verify` refuses a ledger whose `schema` is newer than the code understands,
  instead of half-parsing it: a field renamed by a future version would read
  back empty and produce a confident `source-missing` — the false verdict this
  tool exists to avoid. A ledger with no `schema` key still reads (the default),
  and the refusal names the fix (`upgrade citevouch`).
- The README's Status section claimed 0.2.0 was "the first schema-affecting
  change". It was not — the ledger schema has never moved — and it implied a
  guard (`verify` rejects unknown schemas) that did not exist until the fix
  above made it true.
## [0.2.2] — 2026-10-29
### Fixed

- The automatic release path now actually creates the GitHub release. `target_commitish` accepts a
  branch or a commit, never a tag name, and the workflow passed the tag — so the first fully
  automatic release (0.2.1) tagged itself, built, smoke-tested and passed every check, then died
  with `Release.target_commitish is invalid`. The flag is now used only on the path that has to
  create the tag, and a failed create resolves to exactly one of two outcomes: the release already
  exists (re-attach and go green) or it does not (stay red with the API's own error visible).
- `auto-release` re-points `citevouch@vX.Y.Z` install pins in README.md as part of the bump commit.
  The document told people to install `@v0.1.0` for two releases after that stopped being the
  newest version, because a machine was writing version numbers into files a human still pinned.
## [0.2.1] — 2026-10-29
### Fixed

- The release workflow now builds the commit the version tag points at. Called from the automatic
  path, it checked out the commit the triggering event had seen — the one *before* the version bump —
  so a release cut by the machine would have shipped the new number around the previous release's
  code.
- `v0.2.0` itself nearly became that bug's first victim: the bump and tag were created
  automatically, the called release failed on the version agreement check, and the GitHub release
  did not exist until it was re-cut by hand from the tagged commit while `main` still pointed at it.
## [0.2.0] — 2026-10-28
### Changed

- A release that could not publish to PyPI now says so in the run summary instead of reporting a
  green step. PyPI publication is still not configured for this repository, so `pip install
  citevouch` does not work yet; install the tag from GitHub until it is.
- `init-demo` now records the ledger as part of scaffolding, so the `verify` command the README
  tells you to run next actually works. It used to leave you without a ledger and exit 2.
- The test matrix no longer claims `macos-latest` × Python 3.10. That cell never ran: there is no
  macOS arm64 build of 3.10, so it sat queued and then failed.

### Fixed

- `sources.toml` is read on Python 3.10, where `tomllib` does not exist. Before this, every claim
  on 3.10 turned into `source-missing`.
- The sdist ships `tests/conftest.py`, so `pytest` works from the archive, and no longer carries
  `__pycache__`.
- A source path is recorded in the ledger relative to `--root` and with forward slashes, so a
  ledger committed on Windows verifies on Linux.
- The acceptance job installs `pytest` instead of assuming a test runner is present.
## [0.1.0] — 2026-10-29

The first release. Everything below was built and verified against a real 39-entry bibliography and
two real PDFs before the version number was written down.

### Added

- **Claim blocks in three dialects** — fenced ````claim` blocks, HTML comments, and table rows, so
  a claim survives whichever editor the author uses.
- **`scan`** — records a manuscript's claims, the SHA-256 of every source, the page each quote was
  found on, and a fingerprint of the quote itself into `citevouch.lock.json`.
- **`verify`** — re-reads the sources and reports `quote-found`, `quote-moved`, `quote-fuzzy`,
  `quote-missing`, `source-changed`, `source-missing`, `source-unreadable`, `page-out-of-range`,
  `number-absent-in-quote`, `ledger-stale`.
- **`check`** — scan and verify in one pass, with `--use-recorded` for CI so the job never mutates
  the checkout.
- **`report`** — re-renders a committed ledger as a table without touching the sources.
- **`init-demo`** — writes a working example project, records its ledger, and verifies it, so the
  first command a new user runs ends in a summary rather than a list of parse errors, and the
  next command the README shows already has something to read.
- **BibTeX reader** — comments, `@string` macros, `#` concatenation, nested braces, quoted values,
  duplicate keys, empty required fields. No dependency on an external BibTeX library.
- **Three text extractors** — `pypdf`, `pdftotext`, and plain text, with an on-disk content-addressed
  cache under `.citevouch/cache/`.
- **Four output formats** — text, JSON (with real verifier counts), SARIF 2.1.0 for GitHub code
  scanning, and Markdown for pull-request comments.
- **Exit-code contract** — 0 clean, 1 findings at or above `--fail-on`, 2 usage error.

### Deliberate limitations

- **Fuzzy matches never count as verified.** `quote-fuzzy` is `medium` and requires a human, by
  design: a paraphrase is not a quote.
- **Page numbers are hints, never filters.** A PDF re-flowed by a different tool keeps its text and
  loses its pagination, so matching is by text with the page as a preference.
- **No network.** DOI resolution is out of scope; the tool answers "is this sentence on that page",
  and a different class of tool answers "does this paper exist".
- **No writing beyond the ledger and the cache.** The tool never edits a manuscript.

[Unreleased]: https://github.com/lyear12/citevouch/compare/v0.4.1...HEAD
[0.4.1]: https://github.com/lyear12/citevouch/releases/tag/v0.4.1
[0.4.0]: https://github.com/lyear12/citevouch/releases/tag/v0.4.0
[0.3.0]: https://github.com/lyear12/citevouch/releases/tag/v0.3.0
[0.2.2]: https://github.com/lyear12/citevouch/releases/tag/v0.2.2
[0.2.1]: https://github.com/lyear12/citevouch/releases/tag/v0.2.1
[0.2.0]: https://github.com/lyear12/citevouch/releases/tag/v0.2.0
[0.1.0]: https://github.com/lyear12/citevouch/releases/tag/v0.1.0
