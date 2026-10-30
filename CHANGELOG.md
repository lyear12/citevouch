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

- **`--format markdown` says why the job is red, and `--quiet` still
  hides what it hides.** This is the same defect as the text one above, in the
  writer a reviewer actually reads. `_render` shortened the list before handing
  it to the markdown writer, so `check --quiet --format markdown` on a run that
  exited 1 produced a report with a clean summary, no `### Blocking` section and
  not one word about what failed — in a PR comment, which is the one place
  someone goes to find out why the job is red. The renderer now receives the
  whole list and decides for itself what to leave out, the way the text renderer
  always did, so it can describe the run in the summary while the body still
  obeys `--quiet`. It also gained the two lines the text summary has had since
  v0.18.7: `**worst severity:**`, and, when `--quiet` hid a finding at or above
  `--fail-on`, `**N** findings … were hidden by --quiet; that is why this run
  failed.` Five mutations are caught, including the original one.

## [0.19.11] — 2026-10-30
### Fixed

- **`--format json` now describes the run, and says what `--quiet` left
  out.** Every count in one payload has to be about the same thing. The four
  claim counts came from the verifier and described the run; `summary.findings`
  counted the filtered list; so `--quiet` produced a payload saying
  `verified: 1, missing: 1` next to `findings: 1` with nothing anywhere
  explaining the gap. A consumer adding up the claim counts got two, a consumer
  counting the list got one, and neither was wrong about the same thing. The
  payload now carries `hidden` (top level and under `summary`) whenever
  `--quiet` removed anything, and `summary.findings` counts the run.
- **`worst` is the worst of the run, not of the screen.** It was computed over
  the shortened list, so a run whose only finding was a `low` against
  `--fail-on low` exited 1 while the JSON said `worst: info` - a payload that
  contradicts the exit code it came with.

  The text report had both bugs and was fixed in the release that fixed
  `--quiet`. This writer was not touched by that fix, because the fix went to
  the renderer that prints and nobody asked which other writers are handed the
  same shortened list.
## [0.19.10] — 2026-10-30
### Fixed

- **A SARIF rule's level is now one the schema allows.** Fifteen of the
  twenty-six rules said `"blocking"`, which is not a SARIF 2.1.0 level — the
  schema allows exactly `none`, `note`, `warning` and `error`. A document whose
  `defaultConfiguration.level` is an unknown string fails schema validation,
  and uploading that document is the entire point of `--format sarif`: the
  GitHub action exists to put findings on the pull request as annotations.
  `claim-without-evidence` was wrong in the other direction, saying `warning`
  for a finding `model.CODES` calls `low`, so the same finding was a note in
  the text report and a warning in GitHub.
- **The level has one source instead of two.** `SARIF_RULES` used to be a table
  of `(description, level)` pairs — a second, hand-written copy of a severity
  that already lives in `model.CODES`. It is now a table of descriptions, and
  the level is `_LEVEL[severity_of(code)]`, which is the same expression the
  result's own `level` already used. A rule and its result can no longer
  disagree with each other inside one document.

  Both defects survived sixteen releases because every existing test compared
  the *key sets* of `CODES` and `SARIF_RULES` and never their values — which is
  what a second table looks like when nobody diffs it.
## [0.19.9] — 2026-10-30
### Fixed

- Counts now agree with their nouns and verbs everywhere. Four modules spelled
  "N <noun>" six different ways; two of them spelled it inline and both shipped
  the plural with a count of one: a one-entry bibliography printed "1
  bibliography entries are cited by no claim", and one stray character in a
  `.bib` printed "1 characters at line 1 were between entries and were not
  read". The second sentence has two verbs, and the first attempt at this fix
  changed only the first of them - "1 character ... was between entries and
  were not read" - which is why the tests assert on the whole sentence, and
  why both branches of that reader are covered now. The rules live in
  `textnorm.count_of` / `word_for` / `verb_for` / `is_are`; `report.py` and
  `cli.py` keep their private names as one-line forwards, and a test fails if
  a message module spells a plural with `noun + "s"` again.
## [0.19.8] — 2026-10-30
### Fixed

- A SARIF path is now percent-encoded, so an annotation reaches the file the
  finding is about. `artifactLocation.uri` is a URI, and a file name is not
  one: `draft#2.md` was sent verbatim, which a SARIF reader sees as the
  artifact `draft` plus the fragment `2.md`; `draft%20.md` decoded to
  `draft .md`; `my paper.md` and `论文.md` were not URIs at all. The upload
  stayed green in every case, which is the same silent-loss failure the
  re-rooting in this function was written to prevent - reached, as it turned
  out, by another input. Encoding happens after re-rooting, because
  `relative_to` produces the relative path and encoding first would leave it
  unescaped.
## [0.19.7] — 2026-10-30
### Fixed

- A rejected tag push no longer strands the version number in silence.
  `Commit the version bump` pushes to `main` before `Tag it` runs, so a
  push that is refused leaves the version bumped and the Unreleased
  section empty - and re-running the workflow then decides there is
  nothing to release. That is what happened to v0.19.6:
  `! [remote rejected] v0.19.6 -> v0.19.6 (failed)`, with no reason
  given, seconds after the branch push to the same remote succeeded.
  The step now retries three times, then asks the remote whether the
  tag is there anyway (a push can be accepted and still report
  failure), and if it is not, the error names the command that fixes
  it by hand instead of leaving a reader to re-run a workflow that
  cannot help.
## [0.19.6] — 2026-10-30
### Fixed

- A claim block that is missing its `id=` is no longer also described as a
  manuscript with no claim blocks.  `verify` asked the parser only whether it
  produced *claims*, so a block the parser found and refused produced none and
  the file was then called empty - while the parser's own finding, one screen
  up, named the block.  `scan` has checked `parsed.findings` before deciding a
  file is empty since that guard was written; `verify` now does the same, and a
  test runs both passes over one manuscript and compares their codes, because
  `check` runs them in sequence and could never have shown the divergence.
- `quote: "the passage"` is now the same quote as `quote: the passage`.  Claim
  *attributes* have had their YAML quote marks stripped since claims had
  attributes; the claim *body* reader never did.  So a writer who quoted the
  passage in the inline scalar sent the two marks into the search as content,
  matched nothing, and got a `quote-missing` (high) verdict accusing their
  manuscript of a passage the PDF does contain.  Marks are only removed as a
  pair: a value that merely starts and ends with the same mark keeps them, so
  an over-eager fix cannot reintroduce the failure it removes.
## [0.19.5] — 2026-10-30
### Fixed

- A path on a share that is not mounted is no longer called missing.  Windows
  reports an unreachable network path as `ERROR_BAD_NETPATH` (53) and an absent
  file as `ERROR_FILE_NOT_FOUND` (3), and Python maps **both** to `errno.ENOENT`,
  so `Path.exists()` answers "no" to two different questions.  Every sentence
  about a path that was not a file said "does not exist", which sent the author
  looking for a manuscript they never lost and a PDF that was still on the
  share.  `citevouch.errors.why_not_a_file` now reads the raw error and says
  which of the three mistakes happened - a directory, a missing path, or a
  location this machine cannot reach - and `scan`, `verify`, `check`, `report`,
  `draft` and `discover_sources` all route through it.
- `verify` no longer crashes when the recorded manuscript path has become a
  directory.  `exists()` was true for a directory named `m.md`, so `sha256_file`
  raised `PermissionError` and the traceback left `main` with exit 1 - which is
  this tool's word for "the manuscript has findings", so the author read a crash
  as a verdict about their citations.  It is judged with `is_file()` now and
  reported as `ledger-stale`, and the sentence says "is now a directory".
## [0.19.4] — 2026-10-30
### Fixed

- A quote is no longer reported missing because the page carries a character
  nobody can see.  Format characters (Unicode category `Cf`) have no glyph:
  they tell the text engine how to lay a run out, and they sit in the string
  while rendering as nothing.  `normalize` removed five of them by name
  (ZWSP, ZWNJ, ZWJ, ZERO WIDTH NO-BREAK SPACE, SOFT HYPHEN) and left the other
  165, so a source text holding an RLM, an ALM or an RLE/PDF pair inside the
  quoted sentence differed from what the author typed by one invisible
  character - and `quote-missing` at high severity accused the author of not
  quoting a page they were looking at.  Right-to-left text is where this
  arrives in bulk: every Word and InDesign export of Arabic or Hebrew marks
  direction changes with those characters, and a PDF extraction that keeps
  them drops one into the middle of a sentence.  `strip_format` now removes
  the whole category, and `tests/test_invisible.py` verifies the compiled
  class against `unicodedata.category` over all 1,114,112 code points in both
  directions - every `Cf` removed, nothing outside it touched - so a Unicode
  release that adds a format character fails there rather than passing as a
  gap in a hand-typed list.
## [0.19.3] — 2026-10-30
### Fixed

- A source document written entirely in Chinese or Russian, saved as
  UTF-16 without a byte-order mark, is now read correctly instead of
  decoding to replacement characters.  The detector asked whether one
  side of every 16-bit pair was a zero byte, which is true of Latin text
  and false of every other script: a Han character's high byte lies in
  `0x4E`-`0x9F` and a Cyrillic one is `0x04`, so neither document
  contained a single NUL and the test never fired.  The bytes then
  decoded as UTF-8 into text the pipeline treated as real, and every
  quote in the document came back `quote-missing` at high severity -
  accusing the author of not quoting a page whose only problem was how
  the file had been saved.  The judge is now the decoded text rather
  than a byte pattern: `_noise` counts replacement characters and C0
  controls, both of which appear only when bytes were split at the wrong
  boundary, and the little-endian reading is taken when it leaves less of
  either.  Big-endian without a mark is still not guessed, and the
  docstring now says so: swapping a Han character's bytes yields another
  Han character, so for single-script prose the two readings are equally
  clean and equally plausible, and a rule that picked one would be a coin
  flip dressed up as a decision.

- `check` names every unreadable source instead of only the first.  It
  merges the scan and verify passes and drops repeats by `(code,
  claim_id)`, but `source-no-text` is true of a *file* and carries no
  claim id, so three scanned PDFs collapsed into whichever arrived
  first - a reviewer OCRs `a.pdf`, re-runs, and meets `b.pdf` as though
  it had just appeared.  The path is part of the key now.

- `verify` no longer tells an author that a well-formed claim block "is
  not one the parser accepts".  That sentence belongs to a manuscript
  with no blocks; on an empty ledger it was reused for a file whose
  blocks are fine and whose *recording* is stale, sending the reader to
  edit a line that needed no edit.  The empty-ledger path now asks
  `parse_manuscript` first and says "the ledger recorded none; run
  `citevouch scan`" when the blocks are there.
## [0.19.2] — 2026-10-30
### Fixed

- A number written in another script's digits is now the same number as
  its ASCII form.  An author reading a paper printed in Cairo types
  `40688`; the PDF's extraction says `٤٠٦٨٨`.  NFKC folds the
  full-width forms but not Arabic-Indic, Persian or Devanagari digits, so
  the quote differed from the page by one character, missed the exact and
  squashed tiers, and landed in the numbers tier - the tier that exists to
  report a typo.  The tool therefore said `number-absent-in-quote` about a
  number printed on the page in front of the author.  `normalize` now folds
  every decimal digit to ASCII with `unicodedata.decimal`, and
  `canonical_number` accepts the Arabic thousands (U+066C), decimal
  (U+066B) and percent (U+066A) signs, so `40٬688` and `40,688` still
  agree.  A genuinely different number still reaches the numbers tier:
  `40699` against `40688` is still a number problem, not a missing quote.
## [0.19.1] — 2026-10-30
### Fixed

- A source that was read successfully and held no text at all is now
  reported as `source-no-text` (high) instead of being searched and
  reported as `quote-missing`.  A scan has no text layer, so `pypdf` and
  `pdftotext` both return empty pages for it - not a failure either can
  admit to - and the matcher then said the author's quote was not in the
  file.  That sentence is about their PDF, and the fix it used to suggest
  (install pypdf) was already done.  The new finding names the file, the
  page count and OCR.  It is judged in one place for both paths, because
  the cache stores pages rather than verdicts: had only the extraction
  path judged, the first run would be diagnosed and every run after it
  would read the same empty pages out of the cache and blame the quotes.
## [0.19.0] — 2026-10-30
### Added

- `bib-unreadable` (high): a bibliography the parser could read *no*
  entries out of is reported, instead of leaving the run green.
  `verify` skips `bib-key-missing` entirely when the ledger recorded no
  entries, so before this a completely unreadable bibliography produced
  a quieter report than one missing a single key — the wrong way round
  for a tool whose job is to fail on what nobody checked.

### Fixed

- Files are decoded by what they say they are, not assumed to be
  UTF-8.  Notepad's "Unicode" save and Excel's text export both write
  UTF-16; read as UTF-8 that becomes one replacement character and a
  NUL between every letter, which the rest of the pipeline treats as
  text.  A bibliography saved that way parsed to zero entries and the
  run finished with exit 0 and a *medium* finding about an unparsed
  header.  `read_text` now honours UTF-8/16/32 byte-order marks and
  falls back to the NUL pattern a 16-bit-per-character file has, since
  the mark-less spellings (`UTF-16-LE`) are just as easy to produce.
  Every file this tool reads goes through that one function.
- `textnorm.read_text` carried a `try: ... except OSError: raise`, which
  reads like error handling and is exactly nothing.  Removed; the
  callers that do care catch `OSError` themselves.
## [0.18.10] — 2026-10-30
### Fixed

- `tools/check_repo_rules.py` stopped reading the number it exists to
  check.  `_FORMATTED_LINE` matched `ruff format`, and the project's
  acceptance criteria had long since moved to `sh tools/format_check.sh`
  (which counts tracked files, so an untracked scratch file cannot
  change the answer).  From that commit on, every `Run:` line quoted
  the count in the new spelling, and the checker returned an empty
  list whether the number was right, wrong, or absent - so a commit in
  this same session reported 73 formatted files where the real count
  was 74, and passed.  Both spellings are now matched, and a test
  fails if either stops being read.
## [0.18.9] — 2026-10-30
### Fixed

- A manuscript, bibliography or ledger saved with a UTF-8 byte-order mark
  was read as if it began with a character no one can type.  Every
  reader in this tool treats the first line as syntax, so a BOM in
  front of the first `claim` fence hid a block that was closed one
  line below it and reported `claim-block-unclosed` plus
  `no-claim-blocks`; a BOM in front of the first `@article{` reported
  an unparsed header and then `bib-key-missing` (high) for a key
  sitting in that file; a BOM on the ledger made `verify` exit 2 with
  `Unexpected UTF-8 BOM`.  Windows Notepad, Excel and PowerShell's
  `>` all write one by default, so this is the ordinary shape of a
  file from those tools, not a corrupt one.  All reads now go through
  `textnorm.read_text`, which drops the mark at the boundary; it
  carries no information the pipeline uses, so removing it is lossless.
## [0.18.8] — 2026-10-30
### Fixed

- `citevouch report` built a table with one column too many for any claim
  whose quote already held an escaped pipe.  `_cell` escaped `|` and not the
  backslash in front of it, so a quote holding an escaped pipe ended up with two
  backslashes followed by a live column break.  A table's shape is read from its
  first row, which is why one such claim silently reshaped every row after it.
- The same table could end a truncated cell with a lone backslash.  The quote
  was escaped first and cut afterwards, so the cut could land between the
  backslash and the pipe it escaped, leaving a backslash that swallowed the
  ellipsis marking the cut.  The quote is now cut before it is escaped.
## [0.18.7] — 2026-10-30
### Fixed

- `check --quiet --fail-on low` exited 1 while printing `worst severity: info`
  and not one finding.  `_render` filtered the finding list for `--quiet` and
  then handed the filtered list to the text renderer, which computes the
  summary line from what it can see.  The summary now describes the run rather
  than the screen, and when `--quiet` hid the finding that failed the run it
  says so in as many words: `1 finding at or above --fail-on low was hidden by
  --quiet; that is why this run failed`.
- `--quiet`'s help said it hides "info-level lines" while it has hidden
  `info` and `low` since it was written.  The help now says both, and says the
  verdict is unchanged.
## [0.18.6] — 2026-10-30
### Fixed

- The markdown report chose its two headings from severity alone: every `high`
  finding went under `### Blocking` and everything else under `### Other`.  But
  the threshold that actually fails a run is `--fail-on`, so at
  `--fail-on medium` the report filed the only reason for a red build under
  Other.  Somebody reading the report *because* they do not trust a bare exit
  code was pointed at the wrong section.  The renderer now takes `fail_on` and
  the two headings are decided by the same rule the exit code uses, so they
  cannot disagree.
## [0.18.5] — 2026-10-30
### Fixed

- The markdown report said `**1** claims` for a one-claim manuscript, and every
  section printed at most 50 findings while the heading above it counted all of
  them, so sixty findings produced fifty visible bullets under
  `### Blocking (60)` with nothing anywhere saying ten were missing.  The
  summary now uses the package's plural helper, and the report names what it
  truncated (`Truncated: 10 more under Blocking.`) instead of relying on the
  reader noticing.  The old truncation test used 250 findings, above every cap,
  and so never reached the band where the two caps disagreed.
## [0.18.4] — 2026-10-30
### Fixed

- `citevouch report` printed `0 entrys`, and left a `|` inside a claim id or a
  source key unescaped.  The table therefore gained a column and every row below
  it shifted.  The quote was escaped from the first version, which is what made
  the row look finished: whoever wrote it knew about the pipe and stopped at one
  cell.  Both now go through one `_cell` helper, and `_count` takes the plural
  it should print instead of appending an `s` to whatever noun it was given.
  `report` had no test before this, which is why two defects in eleven lines of
  formatting survived four releases.
## [0.18.3] — 2026-10-30
### Fixed

- A message about a path is now true about that path. `--bib <a directory>` reported
  `bib file adir does not exist`, which is false: the judgement was `is_file()` and the sentence
  said `exists()`. It now says `is a directory, not a file`, in both places that word it (`scan`
  and `draft`). `sources.py` had already made this distinction for source files, so this is the
  same defect as any other guard that learned a rule at one site and not at its neighbours.
- `--source <a path that is not a file>` is a usage error (exit 2) instead of being dropped from the
  source map in silence. Silence read as "no key needed this", so the claim the caller meant to bind
  reported `source-missing` and the author went looking for a PDF that was on disk the whole time.
## [0.18.2] — 2026-10-30
### Fixed

- A path this tool cannot write to is now a usage error (exit 2) instead of a traceback that exits 1.
  `scan --ledger <a directory>` died in `os.replace` with `PermissionError`, and
  `--ledger <a file>/x.json` died in `mkdir` with `FileExistsError`; both escaped `main()` as
  tracebacks. Exit 1 is this tool's code for "findings reached the `--fail-on` threshold", so a CI
  job could not tell a mistyped `--ledger` from a paper whose quotes were wrong. The read side
  already did this (`_read_ledger` turns `OSError` into a usage error); the write side now matches,
  through one `_writable_target` guard on every write path, plus an `OSError` barrier so a full disk
  or a locked file reads as a refused write rather than a crash. The guard also runs on the final
  ledger name before the `<name>.tmp` staging file is created, so a refusal leaves nothing behind.
## [0.18.1] — 2026-10-30
### Fixed

- `draft` could write its proposals over the manuscript it was reading. `-o manuscript.md --force`
  replaced the author's paper with the proposal file, and when nothing could be proposed that file
  was nine lines of comment: the paper was destroyed and the command exited 0 saying it had written
  the manuscript. The output path is now compared with the manuscript (through `Path.resolve`, so
  `sub/../manuscript.md` and other spellings are caught too) and a collision is a usage error,
  because `--force` cannot make destroying the input safe.
- `draft -o` resolved against the process working directory while the manuscript, bibliography,
  sources and ledger all resolved against `--root`, so the same command line wrote to different
  files depending on where it was typed. It is now joined to the root unconditionally. Unconditionally
  and not through the shared `_resolve` helper, because that helper prefers a relative path that
  already exists - right for an input, where the file on disk is the authority, and wrong for an
  output, where it let an unrelated `claims.md` sitting in the current directory capture the write
  while `--root` got nothing.
- The `draft` help called the manuscript "never modified" and both READMEs said the proposal file is
  written "next to it". Neither was true of the code. The first is now "never written to" (also
  true of `--output` colliding with it), and the READMEs say the file lands under `--root`.
## [0.18.0] — 2026-10-30
### Added

- `no-claim-blocks` (high): a run that read a manuscript holding no claim blocks now says so instead
  of reporting `0 claims — 0 verified, 0 moved, 0 missing` with `worst severity: info` and exit 0.
  That summary is the shape of a passing gate, and over such a file it was a verdict about nothing -
  the same failure `.tex` input had before v0.17.1, reached through Markdown instead of an
  extension. It now exits 1 and names the closest thing to a claim block it could find: a
  near-miss fence opening with four or more backticks, a capitalised `Claim`, or a file with no
  claim-shaped line at all (where the message points at `citevouch draft`, the command that writes
  real ones). A file whose only block is *broken* still reports the actual defect
  (`claim-uncheckable`, `claim-block-unclosed`) and not this one on top - one fact, one vocabulary.
  `verify` reaches the same verdict over a ledger that recorded no claims, because an empty ledger
  written by an older version is a false green that already reached disk.

### Fixed

- `verify` returned exit 0 over a committed ledger whose `claims` list was empty, printing the same
  `0 claims` / `worst severity: info` summary. Reading the recording back does not make that verdict
  true; it only means the false green was written before it was read.
## [0.17.1] — 2026-10-30
### Fixed

- `scan`, `verify` and `check` accepted a `.tex` manuscript and reported `0 claims — 0 verified, 0
  moved, 0 missing` with exit 0. There are no claim blocks in a `.tex` file, so that clean summary
  was a verdict about nothing - the one answer this tool exists to never give - and it is easy to
  reach by accident, because `draft` does take `.tex`. Scanning one is now refused with exit 2 and a
  message naming `citevouch draft`, which is the command that turns a `.tex` manuscript into claim
  blocks.
- The `Seen N.` counter in `LESSONS.md` had to end in a period, so `Seen 2 - the first was ...` was
  read as "this lesson was never seen", and the gate that promotes a lesson seen on three separate
  days stayed silent about it. The marker now accepts either shape, and a lesson that says `Seen`
  without a readable number is reported instead of skipped. Widening it surfaced a real debt the
  narrow pattern had been hiding: a lesson already at `Seen 3` had never been promoted, and is now a
  rule in `docs/code-standards.md`.
## [0.17.0] — 2026-10-30
### Added

- A quote that runs across a page break is verified from either of the two pages it touches, and
  its numbers may sit on either half. Both behaviours were promised in the changelog and neither had
  a test: reverting the page rule or the number rule left the whole suite green, and the number one
  reports `number-absent-in-quote` - a `high` finding - about a digit the author can read on the
  next page with their own eyes. `tests/test_cross_page.py` now has a
  `TestTheVerifierAgreesWithTheMatcher` class that runs `scan` and `verify` over a real two-page
  source.

### Fixed

- `citevouch doctor`'s "the manuscript is not there" message suggested
  `citevouch doctor paper/manuscript.md`, but `doctor` takes no positional argument: pasting the
  advice produces `error: unrecognized arguments`. It now names
  `citevouch doctor --manuscript paper/manuscript.md`, and a test parses the command out of the fix
  line and runs it through the real parser, so advice that cannot be followed fails the suite.
- `citevouch draft` on a `.tex` manuscript wrote `<!-- line N -->` line numbers counted against the
  LaTeX-converted text, which drops the preamble, the comments and every unmodelled environment.
  The reader looking for line 1 of a file whose line 1 is `% a comment` is sent to the wrong place.
  The proposals file now says which document the numbers count, and only for input that was
  converted.
## [0.16.5] — 2026-10-30
### Fixed

- The `citevouch` action documents `ledger` as "relative to the repository root" and passed the value
  through unchanged, while the CLI resolves a relative `--ledger` against `--root`. The two agree
  only when the project sits at the top of the repository: with `root: paper` the action looked for
  `paper/citevouch.lock.json` and reported `no ledger at paper/citevouch.lock.json` about a file
  sitting in the repository. The action now resolves the ledger against the workspace before calling
  the CLI, and one test runs the real CLI over the documented layout to prove the two agree.
## [0.16.4] — 2026-10-30
### Fixed

- `tests/test_child_env.py` walked `tests/` only, so it could not see `tools/make_figures.py` doing the very thing it exists to prevent: the figure generator's first version replaced the environment, lost `PATH`, and drew a picture of a broken installation. The scan now covers `tools/` as well.
## [0.16.3] — 2026-10-30
### Fixed

- The `citevouch` GitHub action declared a `python-version` input, passed it to
  the install step as `PYTHON_VERSION`, and never read it: a caller pinning
  `python-version: "3.10"` ran on whatever interpreter the runner happened to
  provide, with no warning. A `actions/setup-python` step now honours it, and
  three tests make the class visible - every declared input must be read by a
  step that can act on it, and every `env:` key on a shell step must appear in
  that step's body. The test that was supposed to cover this had a comment
  describing the wiring it never checked.
## [0.16.2] — 2026-10-30
### Fixed

- `tools/check_repo_rules.py` no longer assumes one suite per commit. A commit
  that builds a source archive measures two: the repository's suite and the
  archive's own, and both numbers are true. `--passed` is now repeatable and the
  rule is "every `N passed` was measured in this run" rather than "every
  `N passed` equals the first one" - the first rule caught an honest message,
  which teaches the next agent to write fewer measurements.
- `tools/check_repo_rules.py` compares measured counts against the `Run:`
  section only, not the whole commit body. A body explains what changed and
  quotes the numbers that came before it; held against the whole body, the gate
  would require a commit to stop explaining itself. The section AGENTS.md
  designates for evidence is the one that gets policed.
- The source archive now carries every file its own test suite reads. `MANIFEST.in`
  said `graft tests` and shipped `tests/` without `tools/`, `.pre-commit-hooks.yaml`,
  `action.yml`, `.github/`, `docs/img/`, or `demo/papers/`. Unpacking the published
  `citevouch-0.16.1.tar.gz` and running `pytest` gave **56 failures and 3 errors**;
  the demo alone reported five `source-missing` findings, which reads as a broken
  tool rather than a partial archive. The demo now ships whole, papers included.
  `tests/test_sdist_contents.py` reads the suite with `ast`, collects every path it
  names, and fails if the archive is missing one - a rule, not a list of names, so
  a new test that reads a new directory is covered by the same rule.
- Two tests that count tracked files now skip themselves in a tree with no `.git`
  and say why. The script they exercise already answered an unpacked archive
  correctly (exit 2, "no tracked files to check; is this a checkout?"); the tests
  were demanding a count that has no meaning there. `test.yml` gained an `sdist`
  job that unpacks the archive, runs its suite, and requires every skip it
  reports to be about the unpacked checkout (`not a git checkout`, `no sdist in
  dist/`) rather than about the code. A fixed skip count was the first version
  and it was wrong twice over: it hard-coded a number nobody had measured, and
  it would have refused the honest skips the archive test added. A suite that
  goes quiet is the failure mode, and "each skip says why" names that failure
  instead of guessing at its size.
- `test.yml`'s lint job builds the archive before running the suite, and names
  `setuptools` in its install step. Two real failures on the first run of the
  `sdist` job: the lint job refuses any skip, so the archive-reading test had
  to find a `dist/` there; and `python -m build --no-isolation` needs the build
  backend installed, which an editable install does not leave behind (it builds
  inside its own isolated environment) - `Cannot import 'setuptools.build_meta'`.
  The lint job is the "no skips" job, so it is the last job that may skip.
- `tests/test_sdist_contents.py` skips instead of crashing outside a checkout.
  It ships inside the archive it describes, so unpacking that archive runs it
  where `git ls-files` answers 128. Comparing the manifest against an index
  that does not exist is not a manifest failure, so it says so and the sdist
  job counts it.
- This workflow's lint job measures the archive's suite as well as the
  repository's, because a commit that builds an archive can honestly cite both
  numbers and a gate that cannot measure one of them must either reject the
  honest message or wave it through. Rejecting teaches the next agent to write
  less evidence; waving through is what the gate exists to prevent. It caught
  this very commit: `says 508 passed, the suites measured 515` on run
  41065479029.
## [0.16.1] — 2026-10-30
### Fixed

- `scan` now records the manuscript path relative to `--root`, the way it has
  always recorded source paths. Before this, `scan demo/manuscript.md --root
  demo` and `cd demo && scan manuscript.md` wrote two different ledgers for one
  project, so a committed ledger could only be regenerated from one directory.
  `demo/citevouch.lock.json` is re-recorded; existing ledgers keep working,
  because `verify` only ever reads the file name out of that field.
- `tools/next_version.py` now finds the documents to re-pin by pattern
  (`PIN_GLOBS`, `--pins-root`) instead of taking one `--readme` path per file.
  The hand-kept list missed `docs/launch/`, whose two files quote the install
  line; the first release after they landed bumped the READMEs and not them,
  and the tagged commit failed its own suite, leaving a tag with no release
  under it. `tests/test_next_version.py` now fails if a markdown file carries a
  pin that `PIN_GLOBS` does not cover.
## [0.16.0] — 2026-10-30
### Added

- Two figures at the top of both READMEs, generated from the demo by
  `tools/make_figures.py`: the terminal output of a real `verify` run, and
  the page that run is talking about with the quoted sentence highlighted.
  `docs/img/verify.txt` holds the same lines and `tests/test_figures.py`
  compares them against a fresh run, so a picture of software that no longer
  exists fails the suite instead of shipping.

### Fixed

- The Chinese README kept an untranslated English paragraph in the middle of its
  opening section. Rewriting that paragraph is how the second figure got in;
  the figure is not why it was wrong.
## [0.15.0] — 2026-10-30
### Added

- LaTeX manuscripts. `draft` converts a `.tex` file before reading it, so
  `citevouch draft paper.tex --bib refs.bib` works with no extra flag: `%`
  comments and `thebibliography` are dropped, `\cite`/`\citep`/`\textcite` and
  friends become the same `[@key]` markers the Markdown path uses, a section
  title becomes its own paragraph so it cannot be glued onto the sentence
  below it, and `[p.~3]` notes are dropped because the page always comes from
  the PDF. It is a converter, not a TeX parser: macros that generate text,
  `\input`, and environments whose body is not prose are read as prose or
  skipped — which costs a weaker proposal, never a false pass, since the quote in
  a claim block always comes from the source file.
## [0.14.0] — 2026-10-30
### Added

- `.pre-commit-hooks.yaml`: two hooks, `citevouch` (checks, writes nothing)
  and `citevouch-record` (rescans and writes the ledger). They are separate
  ids because a hook that re-records on every commit turns "the PDF changed
  under me" into "the ledger now agrees", which is the one failure this tool
  exists to catch.

- `citevouch draft`: turns an existing manuscript into reviewable claim
  blocks. It finds every Pandoc (`[@key]`) and LaTeX (`\cite{key}`)
  citation, takes the sentence around it as the claim, resolves the key to
  a local file (manifest, the bibliography's `file` field, or a file named
  after the key), and proposes a real passage from the most relevant page
  with its page number, marked `<!-- confidence: high|medium -->`. It never
  edits the manuscript, never proposes text it did not read, never invents
  a citation, and always exits 0: whatever it could not do is written into
  the file as a comment. Hand-writing the first hundred blocks was the
  largest barrier between this tool and a real manuscript.

### Fixed

- The file count quoted in a `Run:` line is now measured over the tracked
  files (`tools/format_check.sh`) instead of the working tree. `ruff format
  --check .` counts untracked drafts, so the number it printed was only true
  on the machine that printed it: three releases in a row quoted a count that
  disagreed with CI, and the gate caught each one after the fact. `xargs`
  reports a child's exit 1 as 123, which the script maps back to 1 - the gate
  only reads "zero or not", but a person reading a red build reads the number.

- `tests/test_precommit.py` and `tests/test_critic_round2.py` hand `env=`
  a dict that starts from `os.environ`. A dict there replaces the whole
  environment rather than extending it; on Windows that removes `SYSTEMROOT`
  and CPython dies before it can report anything, which surfaced as
  `assert 1 == 0` on `test (windows-latest, 3.10)`. `tests/test_child_env.py`
  now walks every call with `ast` and refuses a literal `env=` dict, so the
  same defect cannot be written a third time.
## [0.13.0] — 2026-10-30
### Added

- A pin that disagrees with `_version.py` now fails the suite.
  `tests/test_readme_example.py::TestThePinsAgree` reads every
  `citevouch@vX.Y.Z` in both READMEs and rejects any other `vX.Y.Z` the release
  tool cannot rewrite. The release that followed the action landed bumped the
  `pip install` pins and left the four new `uses:` lines at the previous
  version, so one README showed two versions of the same tool three lines
  apart.

- `action.yml`: a composite action that installs the tag it is pinned to and
  runs `check --use-recorded`, with `manuscript`, `root`, `ledger`, `fail-on`,
  `format` and `python-version` as inputs and `sarif` / `exit-code` as outputs.
  The Marketplace entry is the only place people look for "a check I can add to
  CI", and until now they had to assemble it from three shell lines.
  `tests/test_action.py` runs each step's shell against a stub `citevouch` on
  PATH and asserts every declared input reaches the command line, that a path
  with a space stays one argument, that exits 0 and 1 pass through unchanged,
  and that exit 2 is reported as "could not run" rather than as a verdict.

### Fixed

- The CI jobs now install `-e ".[dev]"` instead of naming `pytest` and `ruff`
  by hand, and the `dev` extra declares PyYAML. `tests/test_action.py` imports
  yaml to read `action.yml`, so every job on all three operating systems failed
  collection with `ModuleNotFoundError: No module named 'yaml'`: a dependency the
  tests use but the extra does not promise is the same defect as a feature
  declared and not built. `tests/test_extras.py::test_every_run_only_dependency_is_used_by_a_command`
  now walks the `dev` extra and fails when a member is neither imported under
  `tests/`/`src/`/`tools/` nor named by a workflow.
## [0.12.0] — 2026-10-30
### Removed

- The `xlsx` extra is gone. `pyproject.toml` declared `xlsx = ["openpyxl>=3.1"]`
  and nothing under `src/` imported openpyxl, so installing the extra changed
  nothing and the packaging metadata advertised a capability the tool does not
  have. `tests/test_extras.py` reads the table and fails when any extra names a
  module that no module under `src/` imports, so the next one cannot be declared
  without being built.
## [0.11.0] — 2026-10-30
### Added

- `citevouch doctor` reports whether this machine can read a PDF at all, and
  which check failed in the way that produced the symptom. The failure that
  sends people away from this tool is not an error message: a run finishes and
  says every quote is missing because no extractor is installed, and nothing in
  that output says so. `doctor` checks the interpreter, `pypdf`, `pdftotext`,
  cache writability, the manuscript and the manifest, prints one line per check
  with a `fix:` line under every failure, and exits `1` for a broken machine --
  the one place where `1` means "your machine", not "your manuscript".
## [0.10.3] — 2026-10-30
### Fixed

- A quote that runs across a page break is no longer reported as missing.
  Every page used to be searched on its own, so a sentence that starts at the
  bottom of page 6 and ends at the top of page 7 matched nothing and came back
  as `quote-missing` — `high`, the same severity as a fabricated citation. That
  is the worst thing this tool can do: not lack a feature, but tell an author
  their evidence is gone when it is on the next page. Adjacent pages are now
  also searched stitched together, the reported page is the one the quote
  starts on, and the finding says which page it runs onto. A ledger pointing at
  either of the two pages is counted as verified rather than `quote-moved`, and
  the number check reads both pages so a statistic carried in the second half
  is not reported absent.
## [0.10.2] — 2026-10-30
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

[Unreleased]: https://github.com/lyear12/citevouch/compare/v0.19.11...HEAD
[0.19.11]: https://github.com/lyear12/citevouch/releases/tag/v0.19.11
[0.19.10]: https://github.com/lyear12/citevouch/releases/tag/v0.19.10
[0.19.9]: https://github.com/lyear12/citevouch/releases/tag/v0.19.9
[0.19.8]: https://github.com/lyear12/citevouch/releases/tag/v0.19.8
[0.19.7]: https://github.com/lyear12/citevouch/releases/tag/v0.19.7
[0.19.6]: https://github.com/lyear12/citevouch/releases/tag/v0.19.6
[0.19.5]: https://github.com/lyear12/citevouch/releases/tag/v0.19.5
[0.19.4]: https://github.com/lyear12/citevouch/releases/tag/v0.19.4
[0.19.3]: https://github.com/lyear12/citevouch/releases/tag/v0.19.3
[0.19.2]: https://github.com/lyear12/citevouch/releases/tag/v0.19.2
[0.19.1]: https://github.com/lyear12/citevouch/releases/tag/v0.19.1
[0.19.0]: https://github.com/lyear12/citevouch/releases/tag/v0.19.0
[0.18.10]: https://github.com/lyear12/citevouch/releases/tag/v0.18.10
[0.18.9]: https://github.com/lyear12/citevouch/releases/tag/v0.18.9
[0.18.8]: https://github.com/lyear12/citevouch/releases/tag/v0.18.8
[0.18.7]: https://github.com/lyear12/citevouch/releases/tag/v0.18.7
[0.18.6]: https://github.com/lyear12/citevouch/releases/tag/v0.18.6
[0.18.5]: https://github.com/lyear12/citevouch/releases/tag/v0.18.5
[0.18.4]: https://github.com/lyear12/citevouch/releases/tag/v0.18.4
[0.18.3]: https://github.com/lyear12/citevouch/releases/tag/v0.18.3
[0.18.2]: https://github.com/lyear12/citevouch/releases/tag/v0.18.2
[0.18.1]: https://github.com/lyear12/citevouch/releases/tag/v0.18.1
[0.18.0]: https://github.com/lyear12/citevouch/releases/tag/v0.18.0
[0.17.1]: https://github.com/lyear12/citevouch/releases/tag/v0.17.1
[0.17.0]: https://github.com/lyear12/citevouch/releases/tag/v0.17.0
[0.16.5]: https://github.com/lyear12/citevouch/releases/tag/v0.16.5
[0.16.4]: https://github.com/lyear12/citevouch/releases/tag/v0.16.4
[0.16.3]: https://github.com/lyear12/citevouch/releases/tag/v0.16.3
[0.16.2]: https://github.com/lyear12/citevouch/releases/tag/v0.16.2
[0.16.1]: https://github.com/lyear12/citevouch/releases/tag/v0.16.1
[0.16.0]: https://github.com/lyear12/citevouch/releases/tag/v0.16.0
[0.15.0]: https://github.com/lyear12/citevouch/releases/tag/v0.15.0
[0.14.0]: https://github.com/lyear12/citevouch/releases/tag/v0.14.0
[0.13.0]: https://github.com/lyear12/citevouch/releases/tag/v0.13.0
[0.12.0]: https://github.com/lyear12/citevouch/releases/tag/v0.12.0
[0.11.0]: https://github.com/lyear12/citevouch/releases/tag/v0.11.0
[0.10.3]: https://github.com/lyear12/citevouch/releases/tag/v0.10.3
[0.10.2]: https://github.com/lyear12/citevouch/releases/tag/v0.10.2
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
