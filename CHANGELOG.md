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

- A `<` in prose is no longer treated as the start of a tag.
  `_strip_markup` matched every `<...>`, so "5 < 7 and 8 > 2" came back as
  "5 2" and a manuscript quoting that sentence against an html source reported
  `quote-missing` on a page that contains it. A tag now has to start with a
  name character, `/`, `!` or `?`.

## [0.10.1] — 2026-10-30
### Fixed

- A `>` inside a quoted attribute value no longer ends a tag early.
  `_strip_markup` matched `<[^>]+>`, so `<a title="a > b">click</a>` left `b">`
  in the page text and a manuscript quoting that sentence reported
  `quote-missing` against a page that contains it. The pattern now skips over
  quoted attribute values.
## [0.10.0] — 2026-10-30
### Fixed

- A quoted key in `sources.toml` binds on Python 3.10 instead of being dropped.
  `"knuth:2019" = "papers/k.pdf"` is valid TOML - it is the only way a
  BibTeX-style key with a colon can be written - and `tomllib` binds it on
  3.11+. The fallback reader dropped the line, so one project verified on 3.11
  and reported `source-missing` on 3.10. The quotes are syntax, so the name is
  now kept; only a key this line-based reader genuinely cannot spell (`=`, `#`,
  brackets, its own quotes) is still dropped.
- Markup documents are reduced to the text a reader would see. `_strip_markup`
  removed tags but left entities in place, so a page containing `A&amp;B` was
  searched for `A&amp;B` and a manuscript quoting `A&B` reported
  `quote-missing`. Entities are decoded after the tags are gone, not before:
  decoding first would let `&lt;tag&gt;` be eaten by the tag regex.

### Changed

- The lint job refuses a suite that skipped. The shell tests can only skip on a
  Windows machine with no bash, but a skip is a test that did not run, and a
  suite that shrinks silently is a gate that opens itself. Skips now fail the
  job with the skipped tests named, and on Linux and macOS a missing bash is a
  failure rather than a skip.
- `tools/check_repo_rules.py` also compares the formatted-file count a `Run:`
  line claims against what `ruff format --check` actually printed. The first
  such number this repository wrote was wrong, in the same commit that added the
  check for the previous wrong number: a quantity nobody measures is a quantity
  somebody guesses.
## [0.9.0] — 2026-10-30
### Fixed

- The release-notes step no longer kills a release whose tag does not exist yet.
  `git describe --tags --abbrev=0 "${tag}^"` fails on a tag that is not there, and
  the step runs under `set -eo pipefail`, so `workflow_dispatch` for an untagged
  version — the documented way to release by hand, and the documented recovery
  path — died before `gh release create` while the build and the wheel smoke test
  had already been paid for. The notes now live in `tools/release_notes.sh`,
  which falls back to `HEAD` in that case and can be run by a test instead of
  being reasoned about inside YAML. The workflow invokes it as
  `bash tools/release_notes.sh`, because the index cannot carry the executable
  bit here and a fresh checkout on a Linux runner lands at 644.
- A quoted key in `sources.toml` no longer takes the whole manifest down on
  Python 3.10. `"vaneecke2026cxn" = "papers/x.pdf"` is valid TOML that `tomllib`
  binds on 3.11+, but the fallback reader raised, and a raise is treated as an
  unreadable manifest — every other key stopped binding and every claim reported
  `source-missing`. A key outside the subset now drops one line, which is the
  same treatment a value outside it already got.
- The extraction cache records the reader that actually produced the text rather
  than the one the suffix predicted. A PDF whose pypdf read fails is read by
  `pdftotext`, and the entry used to claim `pypdf-<version>` anyway, so upgrading
  poppler never invalidated it.
- `tools/next_version.py` no longer deletes whatever follows the link block when
  it rebuilds that block. `update_links` returned `text[: start] + block` and
  stopped there, so an `--apply` run would have dropped any section written
  below the links.
- The nightly job can no longer pick a pre-release as the latest release.
  `-k3,3n` reads `1.0.0-rc1` as `1.0.0` and falls back to a whole-line comparison
  in which `-` sorts above `0`, so `v1.0.0-rc1` beat `v0.8.0`. Pre-release tags
  are now filtered out before the sort.

### Changed

- The offline replay in CI no longer carries `-k "not network"`. There is no such
  marker, so it selected every test while reading like a filter that excluded
  something.
## [0.8.0] — 2026-10-30
### Added

- `sources.toml` on Python 3.10 tolerates a non-string value. A manifest holding
  `enabled = true` used to raise in the fallback reader, and the caller treats a
  raise as "unreadable manifest", so one boolean unbound **every** key in the
  file — while 3.11+ handed the same file to `tomllib` and bound them all. An
  unrepresentable value now drops that one key: nothing downstream can consume a
  non-string anyway.
- The extraction cache records the tool version and the extractor that produced
  it. It was keyed by the source's content hash alone, so upgrading `pypdf` — or
  any change in what a page yields — reused text written by a reader that no
  longer exists, and a ledger could keep saying `quote-found` about a page that
  no longer contained the quote. The temp file also carries the pid now, so two
  scans running side by side cannot overwrite each other's half-written cache.
- `~~~` is recognised as a fence. It is the other CommonMark fence, and authors
  reach for it exactly when a sample contains backticks; ignoring it meant a
  claim written inside a tilde-fenced sample was read as a real claim and
  reported `quote-found` — a verified verdict on a specimen nobody meant to
  check. A tilde fence is closed by tildes only.
- The one-line HTML claim form works. `<!-- claim: c2 source=x page=4 -->` on one
  line, followed by `>> quote`, is the shape both READMEs show; the parser
  required that the line carry **no** `-->`, so an author who copied the
  documented example got zero claims, "worst severity: info" and exit 0.

### Fixed

- Release notes describe the release. They were `git log -n 40`, so every release
  listed the previous releases' work and a dozen `Release x.y.z` subjects of its
  own; they are now the range between the previous tag and this one.
- An unclosed fence is reported whatever it is made of. `~~~` and long backtick
  runs were exempted along with the three-backtick sample case, but "this fence
  never closed and ate the rest of the file" is data loss regardless of the
  fence's spelling. Only the question "was the `claim` inside it literal sample
  text?" is genuinely ambiguous, and only for a three-character opener of the
  same kind.
- Every `claim-block-unclosed` message now says how to fix it, and both READMEs
  tell authors to fence a syntax sample with four backticks instead of three.
  The rule was enforced and documented nowhere a manuscript author would look.
- `AGENTS.md` and `docs/code-standards.md` name the venv path each platform
  actually has. `.venv/bin/pip` does not exist on Windows, and a list a reader
  has to translate is a list they skip.
## [0.7.0] — 2026-10-30
### Added

- `claim-uncheckable`. A claim block that cannot be looked up at all — no
  `source=`, no quote, no id, or an id used twice so the second block is
  dropped — was reported as `claim-without-evidence`, which is `low`, which the
  default `--fail-on high` lets through. The pipeline went green on a claim
  whose quote had never been compared to anything. It is now `high` and it has
  its own code, because "a bare marker in prose" and "a claim block that is
  broken on its face" are two different problems with two different fixes, and
  the README had been describing only the first.
- `page-unreadable`. A `page=` hint that is not a number is reported as
  `medium` instead of silently degrading the claim to `low`: the hint is
  ignored and the quote is located by search, so the claim is still checked —
  the author just needs to know their instruction did nothing.
- SARIF paths are re-rooted against `--root` when they can be. GitHub resolves
  `artifactLocation.uri` against the repository, so a finding carrying
  `C:/Users/.../m.md` matched no artifact and its annotation was dropped
  without an error.

### Fixed

- The `N passed` check no longer reads a silent suite as zero passing tests.
  `pyproject.toml` already sets `addopts = "-q"`, so the workflow's
  `pytest -q` was really `-qq`, which suppresses the summary line the count is
  parsed from; the grep then returned the empty string and the gate failed
  every commit with "the suite reports 0". The step now runs the suite plainly,
  fails if the suite fails, and fails separately if the summary line is missing.
- A non-claim fence that is never closed no longer swallows the rest of the
  file in silence. ` ```python ` left open, and the first claim inside it
  opened inside the code sample, after which every remaining claim was read as
  sample text: `claims[]` came back as "0 claims" and the run exited 0. The
  same hole existed in the HTML dialect (`<!-- claim:` with no `-->`), in both
  directions. Both are now `claim-block-unclosed`, which names the line the
  fence opened on. A sample wrapped in **four** backticks stays silent: that is
  the one form where nesting is unambiguous, and guessing wrong there would
  punish the correct way to quote a fence.
- `tools/next_version.py --apply` writes LF on Windows. `Path.write_text` has
  no `newline` argument, so a local `--apply` rewrote the whole file as CRLF
  and every line showed as changed for no reason but the platform.
- The repository-rules check now reads the `N passed` in the head commit's
  message and compares it with the number the suite just reported. Two review
  rounds caught the author quoting a test count that was not the suite's size;
  a wrong measurement is the most expensive kind of wrong sentence, because
  the next reader cannot tell it from a stale one.
- The reader's real input is now a fixture. `tests/fixtures/real-39.bib` is
  the 39-entry bibliography this tool was written against, with the `%` inside
  a field, the CJK titles and the `and others` tails that broke the first
  version. Synthetic fixtures prove a fix agrees with itself; this one is the
  input that disagreed.
## [0.6.1] — 2026-10-30
### Fixed

- The guard that keeps documents from describing the version as living in
  `pyproject.toml` now fails closed, and it covers the workflows. It used to
  match a list of known-wrong sentences in `AGENTS.md`, the two READMEs and
  `docs/` only, so the headers of `auto-release.yml` and `release.yml` went on
  saying the release step "writes it into CHANGELOG.md and pyproject.toml" for
  the two releases after the version moved to `src/citevouch/_version.py`. The
  test now checks any line that mentions `pyproject.toml` for a statement of
  what it actually does, and it scans `.github/workflows/*.yml` too - the guard
  had been excluding the files it was never pointed at.

## [0.6.0] — 2026-10-30
### Fixed

- A source recorded as a directory is reported, not fatal. `verify` read a
  ledger path back with `exists()`, which is true for a directory, and the next
  line tried to hash it: `PermissionError: [Errno 13]`, traceback, and a
  process that exited 1 - the code that means "there are findings", so a CI job
  could not tell a crash from a verdict. It now reads `source-missing`, which
  is what a directory is. `extract_pages` makes the same two mistakes two
  different sentences: a directory is not the same problem as a file that is
  gone, and saying "does not exist" about something the user can see sends them
  looking in the wrong place.
- An unclosed ```claim fence no longer eats the rest of the file in silence.
  Every claim after the missing fence was read as part of the block above it,
  so `claims[]` came back shorter than the manuscript and the one claim that
  did survive failed as `quote-missing` - a diagnosis that sends the author to
  check a PDF when the real typo is three backticks. The parser now reports
  `claim-block-unclosed` at the line where the fence opened.
- `-` in the table dialect's page column means "no page hint" and is no longer
  reported as a non-numeric page the author typed.
- `report` prints page 0 instead of an em dash. The cell used
  `claim.page or '—'`, and `0` is falsy: the one number the reader was asking
  about was the one the report replaced with a symbol meaning "nothing".
- `quote-fuzzy` is a `high` severity finding, and the exit path no longer has a
  special case for it. The code was `medium` with a hardcoded `return 1` in
  `_exit_code`, which made the three sentences that describe `--fail-on` false
  for one code only. Severity decides; `--fail-on` decides; nothing else does.
- `source-changed` is reported before the unreadable-source skip. Replacing a
  source file with something that cannot be parsed used to report only
  `source-unreadable`, so the reader went looking for a download problem when
  the file had simply been swapped.
- `number-absent` and `bib-doi-mismatch` are gone from `CODES` and from
  `SARIF_RULES`. Neither was ever produced by any code path. A finding code is
  a promise that the tool can report it; two codes that cannot occur teach the
  reader to trust a vocabulary that is partly fictional.
- `sources.yaml` and `sources.yml` are no longer listed as manifest names.
  `load_manifest` skipped both with a bare `continue`, so the name advertised a
  format the code ignored.
- `SourceRef`'s docstring no longer describes a filename-stem fallback that was
  removed a round earlier.

### Changed

- Every file `citevouch` writes is written with LF endings explicitly. On
  Windows `Path.write_text` turned each `
` into `
`, so the committed
  lockfile and the one on disk differed by every byte, git warned on each run,
  and a scan on one platform and a clone on another could not agree. The
  repository already promised LF in `.gitattributes`; the writer now does too.

### Added

- `SOURCE_SUFFIXES` in `sources.py`, and the near-miss suggestion list uses it.
  `.md` was in the set, so a key that could not be resolved could be told the
  answer was `README.md` - a file that could never hold the quote. A
  suggestion pointing at the wrong kind of file is worse than no suggestion.
## [0.5.0] — 2026-10-30
### Fixed

- A claim whose source key is a prefix, or a superset, of a real key no longer
  binds to that key's file. The prefix rule was written out of
  `discover_sources`' docstring in the previous round, but the two loops lived
  in `resolve_source`, one level below discovery, and they were never deleted:
  a claim naming `vaneecke2026cxnWRONGSUFFIX`, a key that exists in no manifest
  anywhere, silently bound itself to `2026_VanEecke-Beuls_CoNLL2026_...pdf` and
  `check` reported `quote-found` with exit 0. A typo now reports
  `source-missing` and names the files it thinks you meant.
- The suggestion list in that message works on real filenames. Matching was by
  substring, and `vaneecke2026cxn` and
  `2026_VanEecke-Beuls_CoNLL2026_large-scale-CxG` contain neither the other, so
  the candidates came back empty - a strict resolver whose error message was a
  dead end. Tokens, split at letter/digit boundaries, find the `vaneecke` and
  the `2026` the two names actually share.
- `verify` applies the same page rule as `scan`. A ledger edited to say
  `page: 0`, or one written by an older build, was passed to the matcher, which
  searched page 0, missed, searched everywhere, found page 1, and reported
  `quote-moved`: "quote is on page 1, the ledger says 0". The sentence was true
  and the diagnosis was wrong, so the author went looking for a restructuring
  that had not happened. `--use-recorded` reads ledgers it did not write, which
  is exactly the path that reaches here.
- A directory passed to `--source`, or listed in `sources.toml`, is ignored
  instead of raising `PermissionError` out of `scan`. `init-demo` on a path that
  is a file says "is a file, not a directory" and exits 2 instead of raising
  `NotADirectoryError`. Both used to escape the 0/1/2 exit contract as a
  traceback, which a caller cannot tell apart from a crash.
- `AGENTS.md` and `docs/maintenance.md` no longer send an agent to bump the
  version in `pyproject.toml`, which has not held a version since it moved to
  `src/citevouch/_version.py`. `AGENTS.md` now names the file, and a test fails
  if any document again describes the version as living in `pyproject.toml`:
  a stale instruction is executed by the next agent, so it is a bug, not a typo.

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

### Added

- `tests/test_critic_round3.py`: one or more tests per finding above, including
  the end-to-end case where a mistyped source key reaches the reader as
  `source-missing` instead of a confident `quote-found` on the wrong paper.

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

[Unreleased]: https://github.com/lyear12/citevouch/compare/v0.10.1...HEAD
[0.10.1]: https://github.com/lyear12/citevouch/releases/tag/v0.10.1
[0.10.0]: https://github.com/lyear12/citevouch/releases/tag/v0.10.0
[0.9.0]: https://github.com/lyear12/citevouch/releases/tag/v0.9.0
[0.8.0]: https://github.com/lyear12/citevouch/releases/tag/v0.8.0
[0.7.0]: https://github.com/lyear12/citevouch/releases/tag/v0.7.0
[0.6.1]: https://github.com/lyear12/citevouch/releases/tag/v0.6.1
[0.6.0]: https://github.com/lyear12/citevouch/releases/tag/v0.6.0
[0.5.0]: https://github.com/lyear12/citevouch/releases/tag/v0.5.0
[0.4.1]: https://github.com/lyear12/citevouch/releases/tag/v0.4.1
[0.4.0]: https://github.com/lyear12/citevouch/releases/tag/v0.4.0
[0.3.0]: https://github.com/lyear12/citevouch/releases/tag/v0.3.0
[0.2.2]: https://github.com/lyear12/citevouch/releases/tag/v0.2.2
[0.2.1]: https://github.com/lyear12/citevouch/releases/tag/v0.2.1
[0.2.0]: https://github.com/lyear12/citevouch/releases/tag/v0.2.0
[0.1.0]: https://github.com/lyear12/citevouch/releases/tag/v0.1.0
