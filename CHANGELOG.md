# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Releases are cut automatically: when CI is green on `main`, `auto-release.yml` reads the
`## [Unreleased]` section below, lets `tools/next_version.py` decide the number, writes it here and
into `pyproject.toml`, commits, tags, and calls `release.yml`. An empty Unreleased section means no
release. `release.yml` refuses to publish if the tag and `pyproject.toml` disagree.

## [Unreleased]

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

[Unreleased]: https://github.com/lyear12/citevouch/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/lyear12/citevouch/releases/tag/v0.3.0
[0.2.2]: https://github.com/lyear12/citevouch/releases/tag/v0.2.2
[0.2.1]: https://github.com/lyear12/citevouch/releases/tag/v0.2.1
[0.2.0]: https://github.com/lyear12/citevouch/releases/tag/v0.2.0
[0.1.0]: https://github.com/lyear12/citevouch/releases/tag/v0.1.0
