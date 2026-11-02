# Backlog

The 30-minute heartbeat reads this file and takes **the top unfinished item** it
can finish and verify in one run. Nothing here is a wish: every entry names the
person who is blocked without it. An entry that cannot answer "who is blocked"
does not belong in this file.

Order is priority, top first. `P0` is a tool that lies; `P1` is a tool nobody can
start using; `P2` is a reader we have not reached; `P3` is that nobody knows yet.

When an item is done, tick it and leave one line saying **why it is now true** —
not what changed, but what proves the change works.

---

## P0 — the tool must not lie

- [x] **A quote that runs across a page break is reported as `quote-missing` (high).**
  A real sentence split between page 6 and page 7 returns `tier=none` from
  `matching.find_in_pages`, because every page is searched alone. An author
  whose sentence happens to straddle a break is told their citation is gone.
  *Who is blocked*: anyone citing a passage near a page boundary — i.e. a large
  fraction of real papers, silently, with no way to tell it from a genuinely
  bad citation.
  *Done when*: adjacent-page pairs are searched as well as single pages, the
  reported page is the page the quote starts on, and `demo/` still says
  4 verified / 1 missing with exit 1. Reverse check: disable the pairing and the
  new test must go red.
  *Note*: this touches matching for every claim. `README.md:20-24`,
  `README.zh-CN.md:15-19` and `tests/test_readme_example.py` pin the demo output
  and must be re-read before shipping.
  **Done — why it is now true:** `matching._page_pairs` stitches every adjacent
  pair with a space between the halves and searches them after every single page
  has missed; `Match.spans_to` names the page it runs onto, and `verify` accepts
  either page as "not moved" and reads the number check on both. Proved by
  `tests/test_cross_page.py` (10) and `tests/test_cross_page_real.py` (3, whose
  premise test fails if the fixture paper ever stops splitting a sentence at
  pages 6-7). Removing the stitching turns 5 tests red. demo/ still says
  4 verified / 1 missing / exit 1, and the two README example blocks and
  `tests/test_readme_example.py` needed no change because no demo quote crosses
  a page break.

- [x] **A number that is on the page, in another sentence, is reported as a
  number the page does not contain.**
  The `numbers` tier matches a quote with every number blanked out, so it knows
  which of the page's numbers sit where the quote's numbers sit — and it threw
  that away. The verifier then asked "is 9,800 anywhere on page 1?", which for a
  quote that borrowed a number from the next sentence answers yes, so the run
  fell back to the summary and printed `the words match page 1 but the numbers
  do not; the quote records 9,800` — about a number printed four lines further
  down the same page. The author who turns the page, sees it, and stops
  trusting the tool is right to.
  *Who is blocked*: any author who condenses two sentences of a source into one
  quote, which is what a literature review does by default.
  *Done when* the page's own numbers at the quote's own positions are what the
  message reports, and the old sentence can no longer be produced.
  **Done — why it is now true:** `Match.page_numbers` carries the numbers the
  page prints under the quote's blank positions, in quote order;
  `verify._number_where_checks` compares them to the quote's own and reports
  `number-not-in-passage` (high) naming both sides. `number-absent-in-quote`
  keeps only the case it is literally true of: the page has no such number at
  all. Proved by `tests/test_number_elsewhere.py` (15), whose premise tests
  check the tier records `('40,688',)` for a blind hit and `()` for an exact
  one. Seven mutations, all red, including "read the page's first N numbers
  instead of the ones under the blanks" and "soften the code to medium" — the
  second matters because a default `--fail-on high` run has to fail on a
  transcribed statistic.
  *Not covered*: `verify.py` is not the only consumer that could have used the
  slot mapping; nothing else does yet.

- [x] **`doctor` reported a `sources.toml` as ok without reading it.**
  The check was `candidate = root / name; if candidate.is_file()`. A manifest
  that would not parse, one whose every key pointed at a path that is not on
  this disk, one that named a directory, and two manifests side by side all
  printed `[ok  ] manifest    sources.toml (N bytes)` and closed with
  "Everything this tool needs is on this machine." — and exited 0. The next
  command then printed `[high] source-missing` on every claim, which is the
  exact failure `doctor` exists to explain, arriving from the command whose
  job was to rule it out. A file's size is not a fact about whether it points
  anywhere.
  *Who is blocked*: anyone whose first move is `doctor` after a run reported
  every quote missing — the one reader who most needs the truth from it.
  *Done when* the manifest check answers whether the files it names resolve,
  not whether the file exists, and `doctor` and `check` tell one story about
  one broken project.
  **Done — why it is now true:** `doctor._manifest` reads the manifest through
  `sources.read_source_table` — the same reader `check` uses — and reports
  three different answers because they need different work: no manifest is ok
  (passing `--source` is supported), an unparsable one is a syntax problem in
  one file, and one naming absent files is a path problem with every missing
  key named. The closing reassurance prints only when nothing is broken.
  `demo/` still reports `2 sources, every one of them present on this machine`
  and exits 0. Proved by `tests/test_doctor.py::TestTheManifestCheck` (10),
  including one test that runs `doctor` and `check` on one broken project and
  requires both to exit 1 mentioning the same missing file. Eight mutations;
  two survived the first run and both were real gaps — truncating the list of
  missing keys to its first element changed nothing because the only test with
  an unusable entry had exactly one, and dropping the byte count changed
  nothing because no test asserted the one fact the message can offer about a
  file whose contents it could not read. Both are red now.
  *Not covered*: nothing runs `doctor` against a Windows network path
  (`\\server\share`), where the OS reports a different errno than a missing
  file; `why_not_a_file` already distinguishes them, but no test exercises the
  doctor line that now surfaces it.

- [x] **`doctor` called a directory "does not exist".**
  The manuscript check was `if target.is_file(): ... else: "does not exist"`,
  so every way a path can fail to be a file collapsed into the one sentence
  that says nothing is there — including a directory the reader can see in
  their file manager. `citevouch check` on the same path said `is a directory,
  not a file`, so the tool argued with itself and the wrong side was the
  command whose job is to explain the other.
  *Who is blocked*: anyone who typed the directory instead of the file inside
  it, which is the most natural way to get `--manuscript` wrong.
  *Done when* `doctor` answers with the same sentence the rest of the tool
  uses, and a directory gets a fix that names the manuscript inside it.
  **Done — why it is now true:** `doctor._project` asks
  `errors.why_not_a_file`, so a directory, an unreachable share and a missing
  file are three sentences with three next steps, and the directory's fix line
  names `<the directory passed>\manuscript.md` rather than the generic
  `--root` advice that would send the reader back to the directory. Proved by
  three tests, one of which runs `check` and `doctor` on one path and requires
  what `doctor` says to be something `check` also said — written against
  agreement rather than against a list of cases. Three mutations; the second,
  "the directory gets the generic fix", survived the first run because that
  advice also ends in `manuscript.md` and nothing asked which directory the
  path came from. Red once the test asserted the path came from the argument.
  *Not covered*: an unreachable Windows share as the manuscript path;
  `why_not_a_file` has its own tests for the raw errno distinction, but
  nothing drives the doctor line that surfaces that text.

- [x] **`doctor` passed a `.tex` manuscript, about the one file `check` refuses.**
  `citevouch check paper.tex` exits 2 and says claim blocks live in Markdown,
  not in a `.tex` file - scanning one records zero claims and reports a clean
  run for a manuscript nothing checked. `doctor --manuscript paper.tex` printed
  `[ok  ] manuscript  paper.tex (69 bytes)`, closed with `Everything this tool
  needs is on this machine.` and exited 0. The reader who does the sensible
  thing - run the diagnostic before trusting the report - was told the machine
  was fine about an input the next command will not read at all.
  *Who is blocked*: anyone writing LaTeX, which is most of this tool's audience,
  on the one command that is supposed to explain a run that found nothing.
  *Done when* `doctor` asks the predicate the scanner asks
  (`latex.looks_like_latex`), says the same reason, and names the `draft` step
  that does work on a `.tex` source.
  **Done - why it is now true:** `doctor._project` checks
  `latex.looks_like_latex(target)` before reporting the manuscript as fine, and
  reports `not ok` with the scanner's own reason plus
  `citevouch draft paper.tex -o claims.md` as the fix. Proved by four tests in
  `tests/test_doctor.py::TestWhatItChecks`, one of which runs `check` and
  `doctor` on one `.tex` path and requires both to say LaTeX; another requires
  a Markdown file mentioning `.tex` in prose not to be mistaken for one. Four
  mutations, all red - and the fourth ("every file is now called LaTeX") was
  caught by `TestTheExampleInTheReadme` rather than by the new tests, which is
  what a test that runs the documented command on the documented example is
  for.
  *Not covered*: `.ltx` and `.latex` are in `latex.SUFFIXES` and so covered by
  the predicate, but no test drives `doctor` on either suffix.

- [x] **`doctor` passed a manuscript holding no claim blocks.**
  A file with no blocks produces `0 claims - 0 verified, 0 moved, 0 missing` with
  `worst severity: info` and exit 0, which `check` reports as `no-claim-blocks`
  (high) and exits 1 on. `doctor` printed `[ok  ] manuscript  manuscript.md
  (76 bytes)`, closed with `Everything this tool needs is on this machine.` and
  exited 0 - the command whose whole job is to explain a silent run was silent
  about the file that makes the run meaningless.
  *Who is blocked*: anyone who has written prose and not yet written claim
  blocks, which is every new user on their first run.
  *Done when* `doctor` asks whether the manuscript holds anything the run can
  check, and says what to do about it.
  **Done - why it is now true:** `doctor._claim_blocks` parses the manuscript
  through `manuscript.parse_manuscript` and reports the count, or
  `none that the parser could read; the next command names why` for a block the
  parser refused, or fails with the `citevouch draft` step. The condition is
  `ParseResult.nothing_to_check`, now one property rather than the same
  expression typed out in `scan.py` and `verify.py` - the duplication is why a
  third reader could be written without meeting it. Proved by six tests in
  `tests/test_doctor.py::TestWhatItChecks`, one of which requires `check` and
  `doctor` to overlap on one empty manuscript. Six mutations, all red; two
  survived the first run and both were real - a fixture with exactly one claim
  block cannot fail a test about counting, and the fixture manuscript itself was
  `# t`, a file with no blocks, so the fixture had been the bug all along.
  *Not covered*: nothing checks that `doctor` and `check` agree about a
  manuscript whose blocks are all inside a fenced example (a file the parser
  treats as having blocks but verifies as nothing).
  **Also fixed:** the `doctor` test fixture was itself a project that could not
  run — it wrote a `sources.toml` naming `a.txt` and never wrote `a.txt`, so
  three tests asserting an ok report were passing only because the check did
  not look.

- [x] **`docs/metrics.md` does not exist.**
  Nobody can tell whether any of this works.
  *Who is blocked*: the maintainer, i.e. me — without a written record every
  claim about progress is a memory.
  *Done when*: the file exists with star/fork/watcher/issue counts, publish
  download counts, and one dated row per heartbeat that actually changed
  something.
  **Done — why it is now true:** `docs/metrics.md` carries the three `gh api`
  invocations that produce every number in it, the first dated row (0 stars,
  0 forks, 0 issues, 6 downloads across 16 releases, PyPI 404), and the three
  pre-committed readings of a month with no movement, each with a different
  next step so the decision is not made by whoever is most tired that day.

- [x] **A damaged lockfile crashed every verb that reads one, and a crash exits 1.**
  *Found and fixed 2026-11-02.*
  `Ledger.from_json` trusted every field — `raw.get(...)` on each list element,
  `int(...)` on each count — so a lockfile edited by hand or truncated by a bad
  merge raised `AttributeError`/`TypeError`/`ValueError` out of `main`. An
  uncaught exception exits **1**, which in this tool means "findings reached the
  threshold": a crash was indistinguishable from a verdict against the manuscript.
  *Who is blocked*: anyone who has resolved a `.lock.json` merge conflict by hand,
  and anyone whose editor or script rewrote the file — the two things a lockfile
  in version control invites.
  *Done when*: every shape this code cannot read in full produces exit 2 with a
  message naming the section, the key and the file.
  **Done — why it is now true:** `_object`, `_section`, `_whole` and `_texts` in
  `model.py` refuse non-objects, non-object sections, non-whole-number counts and
  non-string lists; `cli._read_ledger` wraps the result so the message carries the
  path. Twenty damaged shapes times three verbs was sixty crashes before and zero
  after, each measured. `claims: null` is refused rather than read as an empty
  ledger, and `fields: []` is refused rather than coerced to `{}` — a half-read
  entry reports `bib-field-missing` about a title that is in the file. The other
  side is proved too: `claims: []`, a missing `tool_version`, `page: "7"` and a
  missing `fields` all still read, and one test round-trips a real `scan` output
  through `from_json` and requires the two to be equal, because a guard that
  refuses what the writer produces would be worse than the crash. Nine
  mutations, eight red; the survivor is equivalent (the type guard makes the old
  coercion unreachable), which is why that guard has its own parametrised case.
  *Not covered*: nothing exercises a schema-1 ledger written by an older build
  that carries a field this version no longer writes; `_read_ledger` has no
  downgrade path and now says so rather than half-reading. The twenty shapes are
  hand-written JSON rather than a real ledger corrupted at byte offsets — a
  truncation landing mid-number is a JSON parse error, which already exited 2 and
  has its own test.

- [x] **A lockfile of balanced brackets still exited 1, because `json.loads` is recursive.**
  *Found and fixed 2026-11-02, the same day as the entry above.*
  `_read_ledger` guarded `json.loads` with `except (OSError, ValueError)` —
  what malformed JSON raises. A file of twenty thousand nested arrays is not
  malformed, and the same call raised `RecursionError: Stack overflow (used
  2912 kB) while decoding a JSON array from a unicode string`. `RecursionError`
  is a `RuntimeError`, so it left `main` untouched and the interpreter exited
  **1**: the identical false verdict as the twenty damaged shapes above,
  arriving through the parser instead of through a key.
  *Who is blocked*: the same reader as the entry above, through a path the
  shape guards cannot see — the guard enumerated damaged *values*, and this file
  decodes to no value at all.
  *Done when*: a nest the parser cannot survive is refused the way a syntax
  error is, with a message that says why.
  **Done — why it is now true:** `cli._read_ledger` catches `RecursionError`
  and raises `UsageError` saying the file nests too deeply for the standard
  library parser, which no citevouch ledger does. Measured before on one file:
  `RC=1` with a stderr traceback ending at `json/decoder.py, line 361, in
  raw_decode`; after: exit 2 at both 20000 and 200000 nesting. Five tests in
  `tests/test_damaged_ledger.py::TestANestDeepEnoughToBreakTheParser`, one of
  which subprocesses the real CLI so a traceback reaching stderr fails the test
  directly, and one that brackets the depth (2000 decodes, 20000 does not)
  instead of pinning a number that belongs to the platform's stack limit.
  *Not covered*: no test at the exact depth where this interpreter gives up, for
  the reason just given. Nothing measures what a slower machine's stack does
  between 2000 and 20000.

- [x] **`doctor` described a file with two claim blocks as a file with one.**
  *Found and fixed 2026-11-02.*
  `_claim_blocks` reported `count_of(len(parsed.claims), "claim block")`, and
  `parsed.claims` holds the blocks the parser *accepted*. A manuscript with one
  good block and one that forgot `id=` reported `[ok  ] claims      1 claim
  block`; `parsed.spans` held two. The same file makes `check` print `[high]
  claim-uncheckable` at the refused line and `1 claim - 1 verified`, so both
  counts were already in the run — they describe different nouns, the file and
  the run, and the check whose purpose is to stop false statements was printing
  the second as if it were the first.

  *Who is blocked*: an author whose manuscript has one block the parser refused
  reads `1 claim block`, believes the file holds one, and never learns that a
  second one is being skipped. The `check` run names the line, so this is not a
  silent failure — it is a wrong count in the command the author runs *first*,
  which is what makes them stop reading the second command's output.

  *Done when*: the count matches the file, and a reader who sees a smaller
  number from the next command is told why before they have to ask.

  **Done — why it is now true:** `_claim_blocks` compares `len(parsed.spans)`
  with `len(parsed.claims)` and reports `2 claim blocks, 1 of which the parser
  could read; the next command names the rest` when they differ, keeping the
  terse `2 claim blocks` when every block was read. Measured on four shapes: a
  clean file says `1 claim block`, a file with one refused block says the split,
  a file whose only block was refused keeps `none that the parser could read;
  the next command names why`, and a file with no blocks still fails. Five tests
  in `tests/test_doctor.py::TestTheCountIsWhatTheFileHolds`; three mutations all
  red — the shipped line, the sentence without its "N of which" half, and the
  long sentence applied to files that do not need it.

  *Not covered*: nothing checks that `doctor` and `check` agree about how many
  blocks a file holds; the two counts are deliberately different numbers, and
  only the difference is asserted.

- [x] **`draft` proposed a block whose id the manuscript already used.**
  The command names each proposal after its citation key and tells the
  author to copy the blocks in. A manuscript that already held
  `id=paper` and one more sentence citing `[@paper]` got a proposal also
  labelled `paper`; appending it - the only thing the tool tells you to
  do - produced `[high] claim-uncheckable ... the second is ignored`, and
  the ignored block was the newest one in the file.
  *Who is blocked*: anyone adding a second claim about a paper they have
  already quoted, which is the normal shape of a literature review.
  *Done when* `draft` names its proposals so that no id collides with the
  manuscript it just read.
  **Done - why it is now true:** `draft()` takes `taken_ids` and
  `cmd_draft` fills it from `parse_manuscript(text)`, so the ids the
  manuscript holds seed the set `_claim_id` de-duplicates against; the
  second proposal for one key becomes `paper-2`. Proved by eight tests in
  `tests/test_draft_claim_ids.py`, the load-bearing one appending the
  proposal to the manuscript and asserting `check` exits 0 - a duplicate
  id is only a problem through the verdict it produces. Four mutations,
  all red: ignoring `taken_ids`, letting it replace the de-duplication,
  passing `None` from the command, and reading only the first existing id.
  *Not covered*: an id that collides only with an HTML-comment claim block
  is untested here, because the parser is the thing under test in that
  shape; `_existing_claim_ids` reads whatever the parser accepts.
  **Also fixed:** the fixture that proved it. A one-block manuscript cannot
  fail a test about a collision with the *second* id, which is why the
  surviving mutation above had to be found by the harness rather than by
  reading the tests.

- [x] **A mistyped `--root` was accepted, and four verbs then answered about a
  directory that is not the project.**
  Every relative path on the command line is resolved against `--root`, and
  nothing ever checked the root. In a project at `proj/`:
  `scan proj/m.md --root nowhere` **created** `nowhere/` and wrote a ledger into
  it (`citevouch: wrote nowhere\citevouch.lock.json (1 claim)`);
  `doctor --manuscript proj/m.md --root nowhere` made
  `nowhere/.citevouch/cache` in order to test it; `draft proj/m.md -o q.md
  --root nowhere` exited 0 and wrote the proposals there; and `check proj/m.md
  --root nowhere` resolved the manuscript (a path that exists as given is never
  re-rooted), so the run looked like it had read the project, and then reported
  `[high] source-missing ... no entry in sources.toml` — about the one thing the
  author had already got right, with that manifest sitting next to the
  manuscript the whole time.
  *Who is blocked*: anyone who types a root that is one character off, which is
  how roots are typed. Three of the four outcomes leave files behind in a
  directory the author never asked for; the fourth is a false sentence about
  their project, and it is the one that costs trust.
  *Done when* a root that is not a directory is refused once, before any verb
  runs, with exit 2 and a sentence the author can act on — and nothing is
  created on the way to that answer.
  **Done — why it is now true:** `main()` calls `cli._project_root(args.root)`
  before dispatch, so the value is checked while it is still one value rather
  than five times downstream. All six verbs that take a root now exit 2 with
  `--root nowhere does not exist; it has to be the directory the project lives
  in, because every relative path on this command line is resolved against it.
  For a project in the working directory, drop --root: that is the default`, and
  `find nowhere` afterwards returns nothing. A root that is a **file** says
  `is a file, not a directory` and not `does not exist`; an unreachable share
  keeps `why_not_a_file`'s own `cannot be reached (the network path is not
  available from here)` sentence. Four mutations, all red: the guard never
  called, a missing root allowed through, a file root reported as missing, and
  the message dropping the default-root advice.
  *Not covered*: a root that is a symlink to a directory is accepted, because
  `is_dir()` follows links and so does every other path decision in this tool.

- [x] **A source that cannot be read gives the same advice four times, and three of the four are wrong.**

  `source-unreadable` said `could not extract text from {name}; install pypdf (pip install pypdf)
  or pdftotext and try again` for every file that yielded nothing: a download that stopped half
  way, a text file somebody saved as `.pdf`, an empty file, and a machine with no reader at all.
  On a machine where `doctor` had just printed `[ok  ] pypdf 6.16.1 (reads PDFs in-process)`, that
  advice is a correction the author has already made.

  **Who is blocked:** anyone whose citation fails to verify because the PDF is damaged, which is
  exactly the person who is already confused about why their quote is not being found.

  **Done when:** the message names the reader that refused the file and quotes it.

  **Done - why it is now true:** `_why_both_refused` re-opens the file with both readers on the
  failure path and the message carries their words - `PdfStreamError: Stream has ended
  unexpectedly`, `pdftotext: Syntax Error: Couldn't read xref table`. Measured: a real PDF cut to
  40,000 bytes, a text file saved as `.pdf`, and a zero-byte `.pdf` now produce three distinct
  sentences, where before they produced one identical false one. The no-reader case still names
  both ways to get a reader, because that one *is* about the machine. The success path never asks:
  a test counts the calls and asserts zero. Six mutations, all red.

  *Not covered:* a file that makes `pdftotext` hang; the 180-second timeout is checked by reading
  the call, not by driving it.
- [x] **A damaged extraction cache exits 1, which is the code that means "a finding".**

  `.citevouch/cache/<sha>.json` is scratch - it holds the text some reader produced for these exact
  bytes, so it can always be recomputed. `_load_cache` trusted the shapes it read, so a file holding
  `{"pages": 5}`, `{"pages": [null]}`, a page whose `number` was `"x"`, or a JSON root that was a
  list reached the interpreter and exited **1** with a traceback - `TypeError: 'int' object is not
  iterable`, `AttributeError: 'NoneType' object has no attribute 'get'`, `ValueError: invalid
  literal for int()`.

  **Who is blocked:** anybody whose cache directory survived a half-finished merge or a hand edit -
  the one file in a project that most invites both, because it looks disposable. They get a crash
  wearing the exit code that means "your manuscript failed".

  **Done when:** a shape the cache does not recognise is a miss, and the run still answers.

  **Done - why it is now true:** `_load_cache` checks the root, the `pages` list, each page, the page
  number (`bool` is an `int` to `isinstance` and is not a page number; a number below 1 cannot have
  come from this tool) and the page text, and returns `None` - "re-extract me" - for any of them.
  Measured: thirteen damaged shapes now re-extract and still report `quote-found`, exit 0, and no
  output line mentions the cache; a *recognised* shape is still used, which is why the fix is not
  "stop caching" - three tests fail if the cache stops being read. Eight mutations red; the eighth
  (removing `isinstance(blob, dict)`) survived until the fixtures stopped going through `_shape()`
  and started writing raw JSON at the root.

  *Not covered:* the `sha256` field inside a cache file is never re-checked against the file's
  name, so valid-looking pages filed under the wrong hash are used as if they were right.

- [x] **`--bib` was accepted and ignored by the two verbs that never read one.**

  `scan` parses each `.bib` and records its entries into the ledger; that is why it is a separate
  command. `verify` and `check --use-recorded` check the manuscript's keys against
  `ledger.entries` and never open a `.bib`. Both verbs accepted `--bib` anyway, because the flag
  comes from the shared option group:

      citevouch check m.md --root . --use-recorded --bib nowhere.bib   ->  0
      citevouch verify m.md --root . --bib nowhere.bib                ->  0

  Exit **0** for a path that does not exist, and the same for a directory. `action.yml` always
  passes `--use-recorded`, so on every pull request of every repository using the action the flag
  was decoration whose entire purpose was to make the run able to fail.

  *Who is blocked*: anyone who wires `--bib refs.bib` into their CI job, sees a green run, and
  concludes their bibliography is being checked. Nothing they can add to `refs.bib` will ever change
  that run's verdict.

  *Done when*: the two verbs either read the flag or refuse it, and saying so is not something the
  author has to work out from the source.

  **Done - why it is now true:** the flag cannot be honoured here at all, so it is refused with
  exit 2 rather than validated - a correct path is *still* not read, so checking existence would
  only convert a silent no-op into a `file not found` for typos and leave the real case untouched.
  The message names both working alternatives: `citevouch scan --bib <file>` to record the
  bibliography, and "drop `--use-recorded`" for a single-pass `check --bib <file>`. Measured after
  the fix: `check --use-recorded --bib nowhere.bib` and `verify --bib nowhere.bib` both exit 2 with
  the same sentence, a directory gets that sentence rather than a complaint about the path, and the
  four commands that *do* read a bibliography (`scan --bib`, `check --bib`, `scan`/`check` with no
  flag, `draft --bib`) are unchanged. Six mutations, all red: `verify` not refusing, the recorded
  path not refusing, an empty flag refused too, the path validated instead of the flag, the message
  naming no command, and `check` without `--use-recorded` refusing as well. The test that pins the
  design refuses a bibliography that **is** there, because a path-validation fix would pass a test
  about a missing one.
  `tests/test_bib_flag_refusal.py`, `README.md` and `README.zh-CN.md` under "Use it in CI".

  *Not covered*: `draft` still accepts `--bib` and needs it, so nothing checks that the flag list of
  one verb matches what that verb does; the guard is written per verb, by hand.

- [x] **`doctor` passed a project where every claim names a source key nobody binds.**
  `doctor` asked whether `sources.toml` maps each key to a file that is on disk.
  It never asked whether the keys the *claims* name are bound at all. A project
  whose manifest binds `other` and whose only claim names `source=paper` got
  seven `[ok  ]` lines, exit **0**, and the closing sentence `Everything this
  tool needs is on this machine. If quotes are still reported missing, the
  source files are the place to look.` - while `check` on the same project
  printed `[high] source-missing ... claim c1 names source='paper' but no entry
  in sources.toml` and exited 1. The reader is sent to look at source files that
  are all present, correctly spelled, and filed under a different name.
  *Who is blocked*: anyone who renamed a key in `sources.toml`, or wrote the
  claim block from memory, and then ran `doctor` to find out why nothing
  verifies. That is the exact moment the command exists for.
  *Done when* `doctor` says whether the keys the manuscript names are bound,
  names the ones that are not, and does not repeat a cause another line owns.
  **Done - why it is now true:** `doctor._claim_sources` parses the manuscript
  with the same `parse_manuscript` the other readers use, takes the keys from
  `parsed.claims`, and asks `read_source_table` whether each one binds. Unbound
  keys are reported with `near_misses` over `candidate_files`, so the author sees
  the file that is probably the one they meant. Measured after the fix:
  `[FAIL] sources  1 source key named by a claim is bound to nothing: 'paper' is
  named by a claim, and no entry in the manifest binds it` and exit 1, while
  `doctor --root demo` still exits 0 with `[ok  ] sources  2 source keys, every
  one of them bound to a file`. Three states are deliberately left to the lines
  that own them: a manifest that will not parse gives `not checked, because the
  manifest could not be read`; a key whose file is missing gives `1 source key,
  of which 1 key cannot be used; the manifest line above names it`; a manuscript
  naming no keys gives `no claim names a source`. Seven mutations, all red - one
  anchor was wrong on the first pass because `table.manifest_problem` appears
  twice in the file, and a mutation that hits the other occurrence tests nothing,
  which is the same failure mode as a test that asserts nothing.
  `tests/test_claim_sources_check.py` compares `doctor` against `check` on the
  same projects rather than remembering what each prints, so rewording either
  message cannot quietly break the agreement it is testing.
  `tests/test_claim_sources_check.py`, `README.md`, `README.zh-CN.md`.

  *Not covered*: a project with two manifests, where the `manifest` line fails
  and this line still reports the keys; no fixture for it, and the behaviour
  reads correct rather than measured. And `test_a_markdown_manuscript_is_not_
  mistaken_for_latex` in `tests/test_doctor.py` had to grow a manifest of its own
  - it reused `GOOD`, whose claim names `source=a`, so the new line was right to
  complain about a project that test had been calling sound.

- [x] **`doctor` rejoined a manuscript path that already worked, so it read a
  different file than `check` did.**

  Four verbs resolve a relative manuscript path through `scan._resolve`, whose
  rule is "a path that exists as typed is never re-rooted". `doctor` joined
  `root` to the string unconditionally. From the directory above a project:

      citevouch check paper/m.md --root paper                 -> 1 verified, exit 0
      citevouch doctor --root paper --manuscript paper/m.md    -> exit 1,
          [FAIL] manuscript  paper\paper\m.md does not exist

  The command a reader runs *because* a report looked empty was the one command
  that could not find the file the report was about.

  *Who is blocked*: anyone who keeps the manuscript in a subdirectory and types
  the path they can see - which is the path `doctor`'s own fix line recommends.
  Following that advice reproduced the failure, because the advised shape was
  the one that had just been rejoined.

  *Done when*: the two commands read one file from one argument pair.

  **Done - why it is now true:** `doctor._project` calls `scan._resolve`, the
  same helper the other four verbs call. Measured after the fix, from the
  directory above the project: `doctor --root paper --manuscript paper/m.md`
  exits 0 printing `paper\m.md (99 bytes)`, the same file `check paper/m.md
  --root paper` verifies; `--manuscript m.md` and an absolute path reach the
  same `Path(...).resolve()`. Three mutations, all red, six tests each: rejoin
  the root, resolve without consulting the file on disk, and hand the joined
  path back to the resolver. `tests/test_doctor_resolves_paths.py` runs with
  the working directory one level above the project, because from inside it the
  two readings agree by accident - the first draft of the file did exactly that
  and proved nothing until it chdir'd up.

  *Not covered*: a Windows UNC `--root`. `_resolve` calls `Path.exists()`, which
  is the same call that already reports an unreachable share as missing
  everywhere else, so the new path cannot be better than the old one there.
  Changing it means changing `_resolve` for all six verbs, which is a design
  change rather than a fix.

- [x] **`draft` produced no proposals at all when run from one directory up.** *Done 2026-11-02.*
  Who was blocked: anyone who runs the command from the directory containing
  the project, which is where a terminal already is when the project is a
  subdirectory. Same project, only the working directory differing:

      cd paper && citevouch draft paper/m.md --root paper --bib paper/refs.bib
          -> 1 claim block(s) proposed (1 verbatim)
      cd ..    && citevouch draft paper/m.md --root paper --bib paper/refs.bib
          -> 0 claim block(s) proposed (0 verbatim), 1 citation left as a comment
             <!-- line 1: paper - source file page.txt does not exist -->

  The file it said did not exist was `paper/page.txt`. `draft` resolved a key
  to a root-relative path (correct - that is what goes into `sources.toml`) and
  handed it to `extract_pages`, which opens what it is given against the process
  directory. Both halves right, the joining line wrong.

  The same call also produced a false reason. A `.bib` whose entry said
  `file = {gone.txt}` was reported as `no `file` field in the bibliography`,
  because `_why_no_file` only knew the two answers `sources.toml` can give. The
  author can see the field; the report says it is not there.

  *Done when*: the command writes the same proposals from either side, and the
  reason it gives for a missing source comes from the file that holds the field.

  **Done - why it is now true:** the call site opens `_resolve(root, path)` -
  the rule the other five verbs already call - and still records the
  root-relative path in the proposal, so `sources.toml` lines are unchanged.
  `_why_no_file` gained the bibliography branch and unwraps Zotero's
  `:path:mime` first. `tests/test_draft_from_above.py` runs one project from
  both sides and compares the two proposals byte for byte after normalising the
  output name, which is the assertion that would have failed here; four
  mutations, all red (open the recorded path, skip the bibliography branch, drop
  the path from the message, stop passing the bibliography at the call site).
  `tests/test_why_no_file.py` covers the new branch, the two reasons that still
  win over it, and the key that resolves.

  *Not covered*: a Windows UNC `--root`, for the same reason recorded above.
  Also `draft --source` is not exercised from one directory up, so the extra
  binding path has the fix by construction rather than by test.

- [x] **`--source` was the one path flag with its own spelling.** *Done 2026-11-02.*
  Who was blocked: anyone who had just learned the path rule from any of
  the other six flags. Project in `paper/`, command typed from one level
  above:

      --bib paper/refs.bib      resolves, the bibliography is read
      --source paper/page.txt   exit 2: source paper\paper\page.txt does not exist
      --source page.txt         resolves

  Both paths point at files that are really there. `--source` joined
  `--root` unconditionally while `--root`, the manuscript argument,
  `--ledger`, `--bib`, `-o` and `doctor --manuscript` all accept a path that
  already works. The error even shows the doubled segment, so the author can
  read the rule and still not know it applies to one flag out of seven.

  The rule existed, in `scan._resolve`, and six commands called it.
  `--source` could not: `sources.py` is imported by `scan.py` and not the
  other way round, so the one caller that needed it was the one place it
  could not be reached from. That is how a shared rule becomes a private
  copy.

  The same split ran through `draft`'s `-o` guard. It names the inputs a
  write must not overwrite, and computed those names with its own root join
  while `read_source_table` used the shared one: `draft --source
  paper/page.txt -o page.txt --force` protected `paper/paper/page.txt` - not
  a file - and wrote proposals over `paper/page.txt`, the source the run had
  just read a quote out of.

  *Done when*: all seven path flags resolve by one rule, and the guard names
  the same files the reader opens.

  **Done - why it is now true:** the implementation moved to
  `sources._resolve` and `scan._resolve` is now an assignment rather than a
  wrapper - two functions that agree today are two functions that disagree
  after the next fix, and `test_the_two_modules_export_one_behaviour`
  asserts they are the same object, which is the only assertion that can see
  a future fork. `tests/test_source_flag_resolution.py` runs one project
  through `scan`, `check` and `draft` under both spellings and compares the
  ledgers the two spellings record; the guard tests assert the protected
  file's bytes are unchanged. Four mutations, all red (join the root
  unconditionally in `--source` again, drop the already-works branch,
  restore the guard's own root join, give `scan` its own copy of the rule).

  *Not covered*: this closes the `draft --source` gap recorded in the entry
  above - `test_draft_accepts_the_typed_spelling` drives it from one
  directory up. A Windows UNC `--source` is still not exercised, for the
  same reason recorded in the `doctor` entry: it would mean changing
  `_resolve` for all seven callers.

- [x] **`doctor` quoted the reader's errno as a second problem.** *Done 2026-11-02.*
  *Who was blocked*: anyone whose `--manuscript` path was wrong, which is the
  state `doctor` exists to diagnose.  With a missing file the report read

      [FAIL] manuscript  p\manuscript.md does not exist
      [ok  ] sources     could not be read to check them: [Errno 2] No such file or directory: 'p\manuscript.md'

  and with a directory it read `[Errno 13] Permission denied` - a sentence that
  sends the reader to look at permissions on a path whose actual problem is that
  it is a directory at all.  One cause, two vocabularies, and the second one
  invents a fault the first had already ruled out.

  *Done when*: one cause is one line, and the line that stops says only that it
  stopped.

  **Done - why it is now true:** `_claim_sources` returns `not checked, because
  the manuscript could not be read` and leaves the cause to the `manuscript`
  line, which is the form the `manifest` check already used.  The summary count
  stays at one because the `sources` line stays `ok=True` - a second failing
  line would read as "2 of 7 checks failed" for one missing file.
  `tests/test_doctor_states_its_reason.py` asserts the errno and the directory
  name are absent, that the manuscript line still names the cause, that a
  readable manuscript is still checked, and that the count is `1 of 7`.  Three
  mutations, all red (put the errno back, drop the "not checked" reason, count
  the line as a failure).

  *Not covered*: a manuscript that exists and cannot be read for a reason other
  than being a directory - `chmod` does not hold on Windows, so that branch is
  covered by reading the code rather than by a test.

- [x] **A `sources.toml` entry with a value that is not a path was called absent.** *Done 2026-11-02.*
  *Who was blocked*: anyone who typed `page = 5` or left a value unquoted.  The
  manifest named the key, and the claim that needed it was told

      claim c1 names source='page' but no entry in sources.toml and no --source path resolves it; add it to sources.toml

  about the line they were reading.  Eight shapes produced that one sentence: an
  integer, a float, a boolean, an array, an inline table, `sources = 5`,
  `sources = "page.txt"`, and an empty file.

  *Done when*: every shape whose key is in the file is named with the reason,
  and the empty file keeps the old advice.

  *Done - why it is now true*: the first five reach `unusable` and their message
  quotes the manifest that binds them; the two `sources = ...` shapes reach
  `manifest_problem`, because a manifest whose root is not a table of keys to
  paths is not a missing key but an unreadable file; the empty file still says
  there is no entry, because there really is none.  The 3.10 subset parser now
  reports the same keys as `tomllib`, so one manifest cannot bind on 3.12 and
  lie on 3.10 - before, `sources = "page.txt"` reached it as
  `{'': {'sources': 'page.txt'}}`.

  *Not covered*: `sources` holding an array of paths is refused as a non-table
  and nothing asserts that message specifically.

- [x] **`sources.toml` was read two ways, depending on which interpreter ran
  it.**

  *What was wrong*: the manifest has two readers - `tomllib` on 3.11+, and
  `_mini_toml`, the line-based subset, on 3.10.  Four spellings were legal TOML
  that the two answered differently, so one file bound one way on one
  interpreter and another way on the other, and the CI matrix runs 3.10, 3.12
  and 3.13:

  | manifest | `tomllib` | subset |
  |---|---|---|
  | `sources = { page = "a.txt" }` | binds `page` | sees no table |
  | `pa.ge = "a.txt"` | binds nothing at `pa.ge` | binds `pa.ge` |
  | `page = "a.txt"` twice | refuses the file | last one wins |
  | `[sources]` twice | refuses the file | merges the halves |

  *Who is blocked*: anyone on 3.10 whose manifest was written against a 3.11
  reading - the run is red on a file nobody edited between the two.

  *Done when*: both readers refuse the same files with the same sentence, and
  the accepted spellings produce the same bindings from both.

  *Done - why it is now true*: one `_refuse_shapes_only_one_reader_follows`
  pre-scan runs before the split in `_load_toml` and `_mini_toml`, so the
  sentences cannot drift apart and the 3.11 path is guarded too.  11 accepted
  shapes produce identical `(found, unusable, manifest_problem)` from
  `read_source_table` under both readers, and the four refused shapes produce
  byte-identical messages.  Six mutations - restore the inline table, restore
  the dotted key, stop refusing a repeated key, stop refusing a reopened table,
  skip the pre-scan on the `tomllib` path, skip it on the subset path - are all
  red.

  *Not covered*: the comparison runs on one interpreter and swaps the reader by
  calling `_mini_toml` directly, so 3.10 itself is only exercised by the CI
  matrix.  `sources` holding an inline table at the root is refused by the
  pre-scan, not by a TOML-aware check, so a deeply nested inline table is still
  read as one flat value by the subset - and now refused for that reason.

- [x] **The two readers of `sources.toml` disagreed about five spellings, so
  one manifest bound on 3.12 and reported `source-missing` on 3.10.**
  *Who is blocked*: anyone on Python 3.10, which is the floor the README
  states, writing a manifest any of those five ways. The key binds under
  `tomllib` and vanishes under the subset, so the same commit is green on the
  3.12 and 3.13 CI cells and red on 3.10 - a project judged by whichever
  interpreter happens to be installed, and a `source-missing` verdict on a
  manifest the author wrote correctly.
  *Done when*: both readers refuse the same files with the same sentence, and
  a manifest they can both read binds the same sources.
  **Done - why it is now true:** `_refuse_shapes_only_one_reader_follows` is
  called by `_load_toml` and `_mini_toml` before either parses, and holds five
  refusals: a value written across lines, a line ending in a comma, an
  unspellable key under `[sources]`, two assignments on one line, and the
  inline-table and dotted-key shapes refused since 0.19.67. Measured at the
  `read_source_table` level, nine shapes across both readers give
  `differing tables: 0 of 9`; each refusal produces the identical sentence on
  either side. Five mutations of the new guards, all RED.
  *Not covered*: the pre-scan is line-based, so a manifest whose meaning both
  readers agree on but whose layout neither was written to expect is refused
  rather than read - refusing a readable file is this code's failure mode, and
  the tests for the shapes that must still be read are the guard against it.
  This scan's first version refused `[other] pa.ge = "dir/x"`, which is how
  that failure was found.

- [x] **A `sources.json` whose root is not an object read as an empty manifest,
  so every claim was told `no entry in sources.json` about a file it was
  looking at.**
  *Who is blocked*: anyone who hand-writes `sources.json` - the README offers
  it as an alternative to `sources.toml` - and gets one character wrong
  (`[` instead of `{`, or a bare `"page"`). The old branch read every non-object
  root as `{}` and reported no problem, so the only feedback was
  `add it to sources.json` about a key they had already written. `{"sources":
  null}` was the same shape one level in.
  *Done when*: a root that is not an object, and a `sources` key whose value is
  null, are both named as problems, and the message says what the file actually
  holds.
  *Done - why it is now true:* the JSON branch of `read_source_table` now
  checks `isinstance(blob, dict)` before reading, and checks `mapping is None`
  after. Measured: `[]`, `5`, `"page"`, `true` give `holds list`, `holds int`,
  `holds str`, `holds bool`; `{"sources": null}` gives its own sentence; `{}`
  still reads as an empty manifest with no problem, because a project
  mid-setup has one. Four mutations RED, including "the root shape is named
  without its type", which survived the first round because the test asserted
  only that a problem existed.
  *Not covered*: a duplicated key inside a JSON manifest - `json.loads` keeps
  the last one silently, and no decision has been made about refusing it.


- [x] **`Claim`'s docstring promised a check that does not exist: it said the
  ledger stores the quote's fingerprint so a later run can tell "the quote is
  gone" from "the quote moved".** *Done 2026-11-02.*
  *Who is blocked*: anyone deciding whether to trust `--allow-stale`. The note
  is the only place that claim is made, and a reader who believes it will run
  `check --use-recorded --allow-stale` on a manuscript they have since edited
  and read `quote-found` as confirmation that the recorded evidence still
  covers the new text. It does not: the new text is checked against the page
  for the first time, with no record of the old text anywhere in the decision.
  *Done when*: the note says what the field is for, the property that actually
  holds is written down, and a test fails if the mechanism it names ever stops
  existing.
  *Done - why it is now true*: `grep -rn "quote_fingerprint" src/` before the
  fix returned six hits - five in `model.py` (definition, `to_json`,
  `from_json`) and one in `manuscript.py:264`
  (`quote_fingerprint=fingerprint(quote)`). `verify.py`, `report.py`,
  `scan.py` and `cli.py` returned nothing, so no verdict ever consults it.
  Measured: with the quote rewritten to `alpha beta` (not on the page, but
  weaker than the original passage), `check --use-recorded --allow-stale`
  printed `[info] quote-found ... 1 claim - 1 verified` and exited 0.
  The note now reads "a record, not a decider", names what the digest is for
  (keeping the passage out of two places), and states the property that does
  hold: an edited quote is compared against the source like any other.
  `tests/test_claim_docstring.py` holds three of those claims - the sentence,
  the single producer, and a scan that fails if any module outside `model.py`
  mentions the field without writing it. Three mutations of the new docstring
  (restore the promise, drop the field's purpose, drop the property that
  matters) each turned the tests red.
  *Not covered*: nothing tests a reader that would consult the digest, because
  there is none - that is the finding, not a gap in the tests.

- [x] **A test compared two ledgers byte for byte, so a clock decided whether
  the project was green.** *Done 2026-11-02.*
  *Who is blocked*: anyone whose change is the one that lands on the wrong side
  of a second boundary. The sdist job at 2026-11-02T14:54:18Z reported
  `1 failed, 1529 passed, 7 skipped` and a diff of two `citevouch.lock.json`
  files that looked identical - so the person reading it goes looking for a
  path bug in a commit that has none, and the eleven green cells before that
  taught them the suite was stable.
  *Done when*: the comparison leaves the run's own clock out, and the way it
  leaves it out is itself tested.
  *Done - why it is now true*: `_without_the_clock` normalises `generated_at`
  before the two ledgers are compared. Two new tests hold it: one fails if the
  clock stays in the comparison (two ledgers written in different seconds must
  normalise equal) and one fails if the normaliser hides anything but the clock
  (a differing `tool_version` must not normalise away); a third asserts an
  ordinary `scan` still stamps a time, so removing the field from the
  comparison cannot silently become removing it from the file. Mutating the
  normaliser both ways and mutating `scan.py`'s timestamp writer all turn the
  file red. Shipped in 0.19.72.
  *Not covered*: nothing reproduces the original failure by timing - the two
  scans cannot be made to straddle a second on purpose, so the old behaviour is
  established by reading the field, not by waiting for it.

- [x] **`\input sec/intro` was left in the prose and reported as no include.**

  *What was wrong.* `\input` has two spellings. LaTeX writes
  `\input{sec/intro}`; plain TeX writes `\input sec/intro`. `latex.py` handled
  the braced form on both sides - `to_text` dropped the argument, and
  `included_files()` named the file - and handled the bare form on neither.
  Measured on a two-line `.tex`: `to_text` returned

  ```
  We show this in sec_intro and continue the argument here.
  ```

  and `included_files()` returned `[]`. So one spelling produced two wrong
  answers that each looked fine alone: the path became part of the sentence
  `draft` proposes as the claim text, and the "this document pulls text in
  from" note listed nothing, telling an author with a split paper that the tool
  had read all of it.

  *Who is blocked.* Anyone writing plain-TeX-style `\input` (common in older
  linguistics and NLP papers, and the form people type by hand) who runs
  `citevouch draft paper.tex`: the proposals are built on sentences the paper
  does not contain, and the note that would have warned them is empty.

  *Done when.* Both spellings drop the argument from the prose, both appear in
  the include note in source order, and a path inside `\verb|...|` or a comment
  counts in neither.

  *Done - why it is now true.* `src/citevouch/latex.py` gained
  `_BARE_INPUT = re.compile(r"\\input\s+(?P<name>[^\s{}%\\]+)")`, a branch in the
  `_DROP_ARGUMENT` handling that consumes the bare argument, and an
  `included_files()` that unions both patterns and sorts by position (they
  cannot overlap: `_INCLUDE` requires `{` where `_BARE_INPUT` requires
  whitespace). After: `to_text` returns `'We show this in and continue the
  argument here.'` and `included_files()` returns `['sec/intro']`.
  `tests/test_latex_bare_input.py` (12 tests) holds it, including the ordering
  test, the `\verb` and comment exclusions, a bare `\input` with nothing after
  it, and two end-to-end `draft` runs. Three mutations - leave the bare form in
  the prose, skip it when reporting, make the bare pattern only match braces -
  are all red. Shipped in 0.19.73.

  *Not covered*: a file name containing a brace (TeX cannot express that
  either); case-insensitive suffix matching for `\input Foo.TEX`, which the
  braced form has never done either.

- [x] **Ten LaTeX commands pasted their first argument into the prose.**

  *What was wrong.* `\textcolor{red}{small}` takes a colour and then the text.
  Ten such commands were in neither `_KEEP_ARGUMENT` nor `_DROP_ARGUMENT`, so
  they fell through to the branch that drops the name and keeps everything
  after it. Measured:

  ```
  \textcolor{blue}{blue}      -> 'blueblue'
  \href{http://x}{shown}      -> 'http://xshown'
  \scalebox{2}{big}           -> '2big'
  \parbox{3cm}{boxed}         -> '3cmboxed'
  \hyperlink{target}{linked}  -> 'targetlinked'
  \resizebox{1cm}{!}{resized} -> '1cm!resized'
  ```

  That text is what `draft` writes into the `claim:` field it asks the author
  to paste, so the proposal was built on a sentence the paper does not contain.

  *Who is blocked.* Anyone whose paper uses colour, hyperlinks, or sized boxes -
  i.e. most papers built from a template - who runs `citevouch draft` on the
  `.tex`. The braced-argument commands that were classified correctly hid the
  problem: `\raisebox{1pt}{lifted}` behaved, so the converter looked like it
  understood two-argument commands.

  *Done when.* Every one of the ten yields only the wrapped words, the two
  commands that take two non-prose arguments skip both, and the kept argument is
  still converted as prose (`\textcolor{blue}{\textbf{blue}}` -> `blue`, not
  `\textbf{blue}`).

  *Done - why it is now true.* `src/citevouch/latex.py` gained a
  `_SKIP_FIRST_ARGUMENT` set with an explicit per-command argument count, and a
  branch that skips `N` groups (passing over `[...]` as it goes) then converts
  the last one. `\makebox`/`\framebox` moved into `_KEEP_ARGUMENT`, where they
  belong - their `[width]` is optional and their text argument is prose.
  `tests/test_latex_argument_commands.py` (19 tests) covers each command, the
  two-argument pair, `\parbox[t]{3cm}{}`, `\textcolor[RGB]{}{}`, an argument-less
  command, and one end-to-end `draft` run asserting the colour does not reach
  the `claim:` text. Four mutations are red: skip the new branch (13 tests),
  say every command takes one argument (2), treat the optional argument as the
  first (2), keep the last argument raw (1). Shipped in 0.19.74.

  *Not covered*: a command whose text argument is missing entirely is handled by
  falling through to the next word, which is asserted for `\textcolor` but not
  enumerated across all ten names.

## P1 — nobody can start using it

- [x] **`draft` proposed a quote for the sentence after the one the author cited.** *Done 2026-11-02.*
  Who was blocked: anyone whose manuscript writes the marker after the full stop (`usage. [@p]`, the shape you get by adding a citation to a finished sentence). `sentence_at` returned the next run of text, so `draft` looked for a passage matching a sentence the author never cited and backed it with that paper's file. Not a crash: a confident proposal pointing at the wrong claim.
  Done when: every accepted placement of a citation marker resolves to the sentence the author cited.
  Done, why it is now true: the splitter reads the text between a run's start and the marker; when that prefix holds no words the marker trails the sentence before it, and a paragraph containing nothing but markers looks back one paragraph. Measured over the 71 usable papers in the construction-grammar corpus with the `sentence. [@p]` shape: 0 proposals before, 46 of 46 proposals accepted by `check` after, 0 rejected. Five mutations, all red.
  Not covered: a marker in a footnote or a caption is not attributed to the sentence it annotates; nothing in the corpus exercised that shape.

- [x] **`citevouch draft` does not exist.**
  A real manuscript needs 100+ hand-written `claim` blocks. Anyone who is not
  already obsessive quits at the second one.
  *Who is blocked*: every prospective user with an existing manuscript.
  *Done when*: `citevouch draft paper.md --bib refs.bib -o proposals.md` turns
  an existing manuscript into reviewable claim blocks (sentence split → pick
  candidates → resolve source via manifest key, bib `file` field, or same-named
  bib key → locate the passage → emit `<!-- confidence: ... -->`), never edits
  the manuscript, always exits 0, and says "no local file" rather than guessing.
  Reverse check: each new test red before, green after.
  *Done*: `draft` exists with `-o/--force/--bib/--source/--root`; it
  resolves a key through the manifest, a bib `file` field (Zotero
  `:path:mime` unwrapped) or a file named after the key, and records the
  path relative to the root so the proposal is committable. Three things
  were only found by running it on the real papers: quotes taken out of a
  results table (`_is_passage`), words split by the column wrap
  (`_reflow`), and a heading glued to the sentence below it because a
  title has no full stop (paragraph-aware `_sentences_of`). Two citations
  of the same paper also used to get the same quote twice, which reads as
  a tool that never looked at the second one; the second is now a comment.
  418 tests; `tests/test_draft.py` covers each of those.

- [x] **`citevouch doctor` does not exist.**
  The first failure a new user hits is "it installed but found nothing", and
  there is no way to ask why.
  *Who is blocked*: anyone whose first run produces `quote-missing`.
  *Done when*: it reports pypdf presence/version, whether `pdftotext` is on
  PATH, whether the cache directory is writable, and the Python version, each
  with a plain "what this means" line, exit 0.
  **Done — why it is now true:** `src/citevouch/doctor.py` runs six checks
  (interpreter, pypdf, `pdftotext`, cache writability, manuscript, manifest) and
  prints a `fix:` line under every failure that names the command which would
  resolve it; `--format json|sarif` carry the same facts. `tests/test_doctor.py`
  (20 tests) covers a broken machine, a healthy one, and the README example, so
  the documented output cannot describe a smaller tool than the shipped one.
  Exit is 1 for a broken machine and 0 otherwise.

- [x] **No `action.yml`.**
  The Marketplace is the only place people look for "a check I can add to CI".
  *Who is blocked*: anyone who would use this if it were one line of YAML.
  *Done when*: a composite action takes `manuscript`/`root`/`fail-on`, runs
  `check --use-recorded --format sarif`, and a test asserts the inputs are
  actually forwarded rather than declared and ignored.
  **Done — why it is now true:** `action.yml` is a composite action with six
  inputs (manuscript required, root, ledger, fail-on, format, python-version),
  two outputs (`sarif`, `exit-code`) and two steps: install from the ref the
  caller pinned the action to, then run `check --use-recorded` with every value
  passed through the environment rather than spliced into the script. Exit 2 is
  re-raised as a failure so a missing ledger cannot look like a clean
  manuscript. `tests/test_action.py` executes each step's shell with a stub
  `citevouch` on PATH and reads back the argument vector, so the file is tested
  as behaviour rather than as YAML text.

- [x] **No `.pre-commit-hooks.yaml`.**
  *Who is blocked*: anyone who gates their repo before pushing rather than in CI.
  *Done when*: one hook id runs `citevouch check` and its `files` pattern covers
  manuscripts.
  **Done — why it is now true:** `.pre-commit-hooks.yaml` carries two ids,
  `citevouch` (runs `check`, writes nothing) and `citevouch-record` (runs
  `scan`, writes the ledger), because one hook cannot both gate and re-record
  without turning "the PDF changed under me" into "the ledger now agrees" —
  which is the single failure this tool exists to catch. `files` is
  `\.(md|markdown|tex)$`, `pass_filenames: false` because the command reads the
  manuscript named in the config rather than the list pre-commit hands it.
  Proved by `tests/test_precommit.py` (13), which resolves each `entry` through
  a stub console script on PATH and asserts a clean project exits 0 and a
  drifted source exits 1 — the file is tested as behaviour, not as YAML.

- [x] **`draft -o` could write proposals over a file the project is read from.**
  The command refused `-o manuscript.md` and compared its output against nothing
  else, so `-o sources.toml --force` reported success and left a project that had
  just said `1 claim - 1 verified` unable to resolve any claim.
  *Who is blocked*: anyone who follows the advice the tool prints. The command
  ends by naming the file it wrote and telling the author to run `check` on it; a
  tired reader who types the file they were just reading about - the manifest, the
  bibliography they passed with `--bib`, the ledger - replaces the project's map
  with proposals and has no way back.
  *Done when*: every file the run reads is compared against the output, the
  refusal exits 2 and names a path that works, and the protected files are
  byte-identical afterwards. Reverse check: remove the guard and the new tests go
  red.
  **Done — why it is now true:** `cmd_draft` calls
  `_refuse_an_output_that_is_an_input`, which resolves the output once and
  compares it against both manifest names, each `--bib` path, each `--source`
  path, and the ledger. Both manifest names, not just the one that exists:
  `sources.json` beside a live `sources.toml` overwrites nothing and still breaks
  the project, because two manifests are refused rather than guessed between.
  `tests/test_draft_output_guard.py` (10 tests) asserts exit 2 and reads each
  protected file back byte for byte, including the ledger after a real `scan`.
  Three mutations, all red - the guard not called at all, only the existing
  manifest protected, and the ledger dropped from the list.
  *Not covered*: a `--bib` or `--source` path that does not exist yet is not
  protected, because the command already refuses a missing input before the guard
  runs, so the two never meet.

- [x] **`pyproject.toml` declares an `xlsx` extra that no code uses.**
  `openpyxl` is offered as an optional dependency and nothing imports it. That
  is a promise to users and a false one.
  *Who is blocked*: anyone who installs the extra and finds it does nothing.
  *Done when*: the extra is gone, and `LESSONS.md` carries the lesson that an
  advertised capability is code, not configuration.
  **Done — why it is now true:** the extra is removed and `tests/test_extras.py`
  reads `[project.optional-dependencies]` with a small parser of its own (no
  `tomllib`, which would have made the guard uncollectable on 3.10) and fails if
  any extra names a module that nothing under `src/` imports. Putting the old
  line back turns two tests red.

- [ ] **PyPI has no `citevouch`.** `https://pypi.org/pypi/citevouch/json` → 404.
  *Who is blocked*: every stranger. `pip install citevouch` is the whole
  onboarding for this class of tool.
  *Done when*: either the trusted publisher is registered (needs the owner's
  PyPI account — a human step, not a code step) or `docs/maintenance.md`
  carries the exact click-path so the human step takes one minute.
  **Half done — the click-path is written, the account action is not.**
  `docs/maintenance.md` now carries the five fields to enter
  (project `citevouch`, owner `lyear12`, repo `citevouch`, workflow
  `release.yml`, environment **empty**), why the environment must stay empty
  (`release.yml` pins no `environment:`, so naming one makes the OIDC subject
  disagree and the publish fails instead of skipping), and the two commands that
  prove it worked. What is left is a sign-in I cannot perform. The workflow
  already reports which of the two outcomes happened, so the state is visible in
  every release run rather than inferred from a 404.
  *Guarded 2026-11-01.* The two facts the click-path depends on are now read
  out of the files themselves instead of being asserted in prose in one place
  and true by luck in another: `tests/test_pypi_trust.py` fails if the job or
  the publish step ever pins an `environment:`, if `id-token: write` goes
  away, or if the documented project/owner/repository/workflow stops matching
  `pyproject.toml` declares the name and `release.yml` names the workflow. Nine
  mutations, nine red. This is the
  only way to protect a step that no test can perform — the file is checked
  for the owner, so the owner's one minute cannot be wasted by a stale form.

## P2 — the audience writes LaTeX

- [x] **No LaTeX input.**
  Linguists and NLP researchers draft in `.tex` / Overleaf, where `\cite{key}`
  already states the binding the tool wants.
  *Who is blocked*: essentially the entire target audience.
  *Done when*: `draft --from-latex paper.tex --bib refs.bib` strips `%`
  comments, reads `\cite`/`\citep`/`\citet`, takes the enclosing sentence, and
  writes a sidecar `claims.md` that `scan`/`verify` accept unchanged. Synthetic
  fixtures only — this machine has no usable `.tex` corpus.
  *Done*: `src/citevouch/latex.py` converts the document body into the same
  plain text the Markdown path reads, and `draft` calls it when the manuscript
  suffix is `.tex`/`.ltx`/`.latex` — no new flag, because a flag would let the two
  paths disagree. Why it is right: the converter is a character walker, not a
  pile of regexes — `\%` inside a comment is still a comment, a `\label{}` leaves
  no hole where it stood, and `$\alpha = 0.5$` becomes `0.5` rather than
  disappearing with the number in it. Why I believe it: 34 unit tests and 5
  end-to-end ones, and the end-to-end test was first written *wrong* — turning
  the conversion off left it green, because `draft` has its own raw `\cite`
  fallback. It now asserts two claim blocks and the absence of
  `\documentclass`/`~`/`\citep` in every statement, which does go red when the
  conversion is disabled.

## P3 — nobody knows it exists

- [x] **No image anywhere in the README.**
  Both READMEs are prose from top to bottom; a visitor has to read to learn
  anything.
  *Who is blocked*: anyone arriving from a search result.
  *Done when*: `docs/img/` holds a figure above the fold in both READMEs.
  **Done, except the GIF - why it is now true:** both READMEs open with
  `docs/img/verify.png`, the real output of a `verify` run over `demo/`, and
  follow the fifth claim with `docs/img/page.png`: the page that claim is talking
  about, the quoted sentence highlighted. Side by side they make the whole idea
  ("this sentence, that page") legible without reading a paragraph. Both are
  generated by `tools/make_figures.py`; `docs/img/verify.txt` holds the same
  lines and `tests/test_figures.py` reruns the demo and compares them, so the
  picture fails the suite when it stops being a picture of this program, and
  `docs/img/README.md` records where the excerpt came from and under what
  licence. The crop had to be snapped to whole text lines: a two-column page
  has two paragraph shapes side by side, so both a fixed height and
  "the block containing it" left a half-line sliced off at the edge.
  The GIF is deliberately not done - a recording has to stay legible at README
  width, and a blurred GIF is worse than two sharp stills. It stays open below.

- [x] **No launch material.**
  *Who is blocked*: the owner, who cannot post without text.
  *Done when*: `docs/launch/` holds `show-hn.md`, `v2ex.md`, `xiaohongshu.md`,
  `douyin-30s.md`. Publishing is the owner's decision; preparing it is not.
  **Done, and here is what each file is for:** `show-hn.md` and `v2ex.md` are the
  two that would actually bring people who will run it, so they carry finished
  copy, a claim block the reader can paste, the install line, and the two
  questions those audiences always ask (why not Zotero; my publisher wants
  LaTeX). `xiaohongshu.md` is two notes whose text never contains a command -
  the audience there is graduate students, not engineers, and "pip install" in
  the body kills the post. `douyin-30s.md` is a 30-second shot list for a video
  that is honestly not going to convert anyone: its own notes say so, and say
  that if there is one shot to take, it is the other two platforms. Every file
  ends with posting notes rather than ending at the copy, because the useful
  part is the part that stops a post from being a gimmick - do not lead with
  "an agent wrote this", do not put a link in the body of a Xiaohongshu note,
  run the demo yourself before quoting its output.

- [ ] **No video anywhere.** Deliberate for now, not forgotten: see the note in
  the figure entry above. A recording has to stay legible at README width, and a
  blurred GIF is worse than the two sharp stills that are there. Revisit if the
  README ever gets a full-width section where a 12-second loop can be seen at
  its real size.

## P4 — inputs nobody tried

These are not features. They are the shapes of input a real user's machine
produces, listed because each one is a place where the tool can come back green
without having read anything. Every entry here was found by asking "what file
would a person actually have on disk", not by reading the code.

- [x] **A file saved in a desktop encoding.** Notepad's "Unicode" and Excel's
  text export write UTF-16. Read as UTF-8 that becomes replacement characters
  and NULs, and the run finished green. Fixed in v0.19.0: `read_text` honours
  the byte-order marks and the NUL pattern, and `parse_bib` reports
  `bib-unreadable` (high) when a non-empty file yields no entries.

- [x] **A PDF that is a scan.** `pypdf` and `pdftotext` both return nothing for
  an image-only PDF, so every quote in it is `quote-missing` (high) - loud, but
  it reads as "your quote is not there", and the actual answer is "this file has
  no text layer". *Done in v0.19.1:* `source-no-text` (high) names the file, the
  page count and OCR. The interesting part was where the verdict is produced:
  both extractors return *successfully* with a list of empty strings, so the
  check cannot live in an except clause. It also has to run on the cache-hit
  path, because the cache stores pages rather than verdicts - judging only the
  extraction path would diagnose the first run and let every later run read the
  same empty pages back out and blame the quotes again. Three mutations are red.
  The fixture is a PDF written by hand (a page whose content stream draws a
  rectangle and sets no text) rather than one built with `pymupdf`, which is what
  the first version did: that library is not installed on CI, so the tests
  skipped, and the lint job fails on any skip.

- [ ] **A right-to-left manuscript: two producers, two different defects.**
  *Measured 2026-11-01 on real RTL PDFs. Needs a design, so not done in one
  run.* The earlier note asked whether extraction *reorders* runs on an RTL
  page. It does not do one thing: it does one of two things depending on how the
  file was made, and neither is visible from the manuscript.

  **Producer A - pymupdf `insert_htmlbox`** (HarfBuzz shaping; this is what a
  browser print-to-PDF does). `pypdf` 6.16.1 returns **each Hebrew word as its
  own reversal, word order preserved**:

  ```
  on the page : נטען כי המשתתפים קיבלו 40,688 דוגמאות במילון.
  pypdf says  : ןעטנ  יכ  םיפתתשמה  ולביק 40,688 תואמגוד  ןולימב .
  ```

  Every word is exactly its reverse (all four checked), the number `40,688` and
  the LTR line on the same page are untouched, and `pymupdf.get_text()` on the
  same file returns correct logical order - so the reversal is in the pypdf
  path, not the file. **Consequence**: a correct Hebrew quote is reported
  `[high] quote-missing`.

  **Producer B - LibreOffice 26, a real word processor.** No reversal at all:
  the words come back in the right order and the correct forms. But it **drops
  the space between a Hebrew word and an adjacent number**, and the loss is the
  extractor's, not the file's - the PDF holds a space glyph at x=427 with the
  number starting at x=379, and `pymupdf` reads `קיבלו40,688` from the same
  bytes. **Consequence**: an author who quotes just the number (`40,688`), the
  most quotable thing on the page, gets `[high] number-absent-in-quote` and
  `quote-missing`, while quoting the whole clause works via the whitespace-free
  tier. The LTR control from the same pipeline reads `We collected 40,688
  examples` and matches `40,688` at `exact`, so this is specific to the run
  boundary next to an RTL word.

  Two separate bugs, one root cause: both are the extractor joining or reversing
  text across a **bidi run boundary**, and the tool trusts the string it got.
  `pdftotext` is no fallback for either - on producer A it returns only
  `".  40,688"`, and on producer B only `'40,688    .'` with every Hebrew word
  gone.

  *Done when* there is a decision, not a patch, because the honest fixes differ
  in what the tool promises: (a) detect visual order and un-reverse runs before
  matching (needs script-run analysis, and will silently damage a genuinely
  palindromic or mixed-script quote); (b) prefer an extractor that emits logical
  order and name the extractor in the finding (`pymupdf` is not a dependency and
  `src/` may not grow one without a decision); or (c) keep the extraction and
  make a `quote-missing` on a page whose text fails a bidi sanity check say the
  page may be RTL, so the author is not told they are wrong. **Option (b)
  addresses producer A but not B** - LibreOffice is already logical-order and
  still loses the space - so (b) alone is no longer sufficient, which is what
  changed today. Who is blocked: every author writing Arabic or Hebrew, on at
  least two of the pipelines they actually use.

  Under `AGENTS.md` this is the "need a design change" case: three behaviours
  with different promises, and I am not choosing between them alone.

  *Partly worked around 2026-11-01, corrected the same day.* The `hyphen` tier
  (0.19.29) was built for a defect the same exploration turned up, and it
  removes one of the two failure modes an RTL page hits. It had to be rewritten
  first: it stripped hyphens from the quote and searched a page whose hyphens
  the join had already stripped, so `re-cover`/`recover`, `re-sign`/`resign`,
  `re-form`/`reform` and `co-op`/`coop` were all certified. It now keeps the
  page's line-break hyphen (`textnorm.fold_keeping_hyphen`) and leaves the
  quote untouched, so nothing is deleted from either side. Producer B loses the
  space between an RTL word and the next token, and an author who quotes that
  gap goes to the `squashed` tier - which strips all whitespace and does not
  care - so the quote is found. Producer A reverses every word in place, and no
  tier can help: the letters themselves are wrong, not their spacing. What is
  still open is what the **finding** says when a page is RTL and the quote does
  not match: today it says "no passage in the source is close to this quote",
  which is a verdict about the author's sentence. That sentence is the
  remaining work, and it is still option (c) and still a design decision.

- [x] **A manuscript over a network path.** `\\server\share\paper.md` on
  Windows, or a file that disappears mid-run.  *Done 2026-10-31.* Windows reports an
  unreachable share as `ERROR_BAD_NETPATH` (53) and an absent file as
  `ERROR_FILE_NOT_FOUND` (3), and Python maps **both** to `errno.ENOENT` - so
  `Path.exists()` answers "no" to two different questions and every sentence about
  such a path said "does not exist".  `citevouch.errors.why_not_a_file` now reads
  the raw error and names the actual mistake (a directory, a missing path, a
  location this machine cannot reach); `scan`, `verify`, `check`, `report`, `draft`
  and `discover_sources` all route through it.  The same pass found a crash: a
  directory named `m.md` satisfied `exists()`, so `sha256_file` raised
  `PermissionError` and the traceback left `main` with exit 1 - the code that means
  "the manuscript has findings".  *Not covered:* a file that disappears **between**
  the extraction and the hash comparison, which no test can schedule; the sentence
  in that window is whatever the failing call reports, which is now the three-way
  one rather than "does not exist".

- [x] **A `sources.toml` entry whose file cannot be used.** *Done 2026-10-31.*
  Four situations - no manifest, a manifest without the key, a key whose file is
  gone or is a directory, and a manifest that will not parse - all produced the
  same sentence, `claim c1 names source='p' but no entry in sources.toml ...
  add it to sources.toml`, and in three of the four the entry **was** in the
  manifest.  The author re-read the one file they had got right.  The mechanism
  was one line: `discover_sources` filtered the manifest with
  `if path.is_file():` and no `else`, so the failures were destroyed before the
  message that needed them was built.  `read_source_table` now returns the
  bindings, the unusable keys with a sentence each, and the reason a manifest
  could not be parsed; `discover_sources` and `load_manifest` keep their old
  return shapes, so no caller changes.  Two tests in
  `tests/test_critic_round3.py` had recorded opposite conclusions about the same
  judgement - a directory given to `--source` is refused, a directory named in
  the manifest is ignored - and the ignored half is what hid this, because
  dropping an entry produces nothing to read.  *Done when* the sentence names
  the cause: `sources.toml maps 'p' to 'gone.txt', but 'gone.txt' does not
  exist`, `'.' is a directory, not a file`, `the manifest could not be read:
  sources.toml could not be read as TOML (...)`.  *Also done:* `verify` told a
  different story about the same project - `source 'p' cannot be found any
  more` - because each reader built its own sentence from its own copy of the
  mapping.  Both now ask `sources.explain_unresolved`, and a key nobody named
  keeps the old sentence because there is nothing better to say.  *Also done:*
  `draft` was a third opinion, saying `no local file: not in sources.toml, no
  'file' field in the bibliography, and no file named after the key` - three
  searches, one of which had in fact succeeded.  It now asks the same
  function.  Its resolution order is unchanged and correct: a manifest entry,
  then the bibliography's `file` field, then a file whose stem is the key, so
  only a key that resolves *nowhere* reaches the sentence at all.  *Also
  covered (second pass, same day):* a key bound twice. A `--source` flag that
  bound one key against a `sources.toml` entry for the same key resolved to the
  manifest, silently; two `--source` flags whose files share a stem resolved to
  the second one, silently. In both cases the quote was then searched for in
  the file the caller had just tried to stop using, and the finding said the
  quote was missing. `read_source_table` now raises `UsageError` when two
  different files claim one key, and stays quiet when the two paths resolve to
  the same file - so `--source papers/x.pdf` on a manifest entry that already
  points there is still fine. Refusing is not the same as deciding which side
  wins: both files are visible to the caller and neither is to the tool.

- [x] **Two `sources` manifests on disk, and the name a message uses.**
  *Done 2026-10-31.* Same shape as the key-bound-twice entry above, one level
  up: two files that each claim the role of "the manifest" cannot be ranked,
  only refused. `read_manifest` returned whichever name came first in
  `MANIFEST_NAMES` and never mentioned the other, so a tree holding a stale
  `sources.json` beside its live `sources.toml` was resolved against one of
  them at random - swapping the two files' contents flipped which one
  decided - and the losing file was invisible in every message, including the
  one telling the author to add an entry they had already added. It now
  enumerates the candidates before opening either and refuses with both names
  and a choice (delete one, or merge), because which manifest is
  authoritative is a fact the checkout knows and the tool does not. The
  second half is the same defect one level down: the per-claim sentence
  hard-coded `sources.toml` in both halves, so a project keeping its keys in
  `sources.json` was told `no entry in sources.toml ... add it to
  sources.toml` - a file not in their checkout, and creating it is exactly
  what produces the refusal above. `SourceTable` now carries
  `manifest_name`; `scan._manifest_name` falls back to `sources.toml` only
  when no manifest was found at all, because that is the file the README
  teaches you to make. *Verified by:* `tests/test_manifest_message.py`
  `TestTwoManifestsAreRefusedInsteadOfRanked` (4 tests) and
  `TestTheSentenceNamesTheManifestTheProjectHas` (3 tests); three mutations
  each red - hard-code the name back in `scan`, drop `manifest_name` from the
  table, restore the ranking. *Not covered:* two manifests that agree
  key-for-key are refused too, deliberately - the tool cannot tell "same
  answer twice" from "one is stale" without reading both, and reading both
  is the ranking this removes.

- [x] **An empty attribute binds the claim to the attribute beside it.** *Done 2026-10-31.*
  ` ```claim id=c1 source= page=1 ` parsed as `source="page=1"`, so a block
  whose author had written `source=` and stopped to think was bound to a key
  nobody had typed.  `sources.toml` had no such key, and the finding read
  `claim c1 names source='page=1' but no entry in sources.toml ... add it to
  sources.toml` - a sentence about the manifest, which was correct, for a
  typo in the block.  The attribute pattern in
  `src/citevouch/manuscript.py:_attrs` ended in an unbounded token, so an
  empty value took the next word.  *Done when* an empty attribute is empty:
  the pattern now splits on the author's spacing - no space after `=` makes
  the token the value outright (so `source=a=b` still means the key `a=b`),
  a space means a following `key=` starts the next attribute, so
  `source= page=1` earns `claim-uncheckable`.  *Verified by* three mutations
  that each fail only their own half, and by keeping the `a=b` spelling
  pinned: the first fix used one lookahead for both spellings and broke it.

- [x] **Advice the tool prints that the tool refuses.** Two commands in one
  sentence, both un-runnable: `no-claim-blocks` named the manuscript by
  basename (right for a finding's `path`, wrong for a shell), and it always
  suggested `-o claims.md`, so a `claims.md` with no blocks was told to write
  onto itself. *Done when* the advice carries the path the reader typed and
  picks an output name that differs from it. *Verified by*
  `tests/test_no_claims.py::TestTheAdviceCanBeFollowed` (4 tests; three
  mutations - basename, fixed output name, callers not passing the typed
  path - each turned exactly one test red) and by running both printed
  commands for real: exit 0 on a subdirectory manuscript and on a
  self-named `claims.md`. *Not covered*: only the `no-claim-blocks` advice is
  guarded; `draft`'s own "read it, then check it" line and the `.tex`
  refusal still print the path they were handed, which is right for both
  because neither drops a directory.

- [x] **The advice from `no-claim-blocks` did not carry `--root`.** *Done
  2026-10-31, one flag after the first attempt.* `check m.md --root paper`
  reads `paper/m.md` and printed `citevouch draft m.md -o claims.md`; pasted
  back it answered `manuscript m.md does not exist`, exit 2. *Done when* the
  advice repeats the root whenever the caller named one, and the default
  sentence stays byte-identical. *Verified by*
  `tests/test_no_claims.py::TestTheAdviceCanBeFollowed`, which now **executes**
  the printed command through `main()` from the directory the reader stands
  in instead of pattern-matching it, plus two mutations (drop the root,
  always print it) that each turned exactly one test red. *Not covered*: an
  absolute `--root` on another drive is repeated verbatim - correct, long,
  and unasserted.

- [x] **A claim id holding a backtick broke the `report` table.** *Done
  2026-10-31.* The id column wrapped the id in backticks after escaping it,
  so an id containing one closed the code span early and the row came out a
  cell short. *Done when* the delimiter is chosen from the content and the
  row keeps its column count. *Verified by*
  `tests/test_cli.py::TestAClaimIdIsRenderedAsItsOwnCodeSpan` (five tests,
  four of them against `_code` directly and one end-to-end through `main()`),
  plus three mutations - wrap the escaped id again, always use one backtick,
  never pad - that each turned them red. *Not covered*: an actual GitHub
  table render; the rule checked is CommonMark's closure rule, read from the
  spec rather than observed on github.com.

- [x] **The pre-commit hooks cannot run.**
  *Who is blocked*: anyone who gates their repository before pushing instead
  of in CI - the reader this hook exists for.
  *Done when*: running each hook's `entry` with exactly the arguments
  pre-commit would supply exits 0 on a clean project and 1 on a drifted one.
  **Done - why it is now true:** `.pre-commit-hooks.yaml` names
  `args: [manuscript.md]` on both ids and keeps `pass_filenames: false`,
  because `files:` matches every Markdown file in the repository (README
  included) and `check` takes exactly one. `tests/test_precommit.py` (16)
  composes the command from the file's `entry`, `args` and `pass_filenames`
  and runs it, so the file is tested as the thing pre-commit executes rather
  than as YAML plus a default the test supplies.
  *Not covered*: pre-commit itself was not installed and run; the harness
  reproduces its invocation rule, not its environment construction. A
  repository whose manuscript is not `manuscript.md` must edit `args`.

## P4 - messages that contradict themselves

- [x] **The `no-claim-blocks` message quoted a line that met its own rule.**
  *Who is blocked*: the author whose README shows the syntax - the exact
  person the message exists to teach.
  *Done when*: an indented example gets a reason that is true of that indent,
  and a left-margin block still gets the generic sentence.
  **Done - why it is now true:** `src/citevouch/scan.py` measures the indent
  from the raw line and, when there is one, says the fence is indented by N
  spaces and that an indented fence is a Markdown code sample. Proved by
  `tests/test_no_claims.py` (2 new), which asserts the specific phrase is
  present and the generic one is absent, plus the control case. Three
  mutations each turned it red.
  *Not covered*: list items and blockquotes are still reported as "this file
  has none" rather than by their marker. That is not a false statement -
  `\- ` and `> ` really do not open a fence - so it is left alone rather
  than given a branch it does not need.

---

## P4 - an example the tool reads as the thing it demonstrates

- [x] **A LaTeX paper that shows its citation syntax was read as citing.**
  *Who is blocked*: every LaTeX author whose paper documents what
  `\citep` looks like - a code sample in the appendix, a README, a
  tutorial section. They get a verified citation for a key that appears only
  in the example.
  *Done when*: an inline verbatim body never reaches the citation pattern or
  the converter, a `%` inside one does not start a comment, and a
  `verbatim` environment's `%` does not eat the `\end{verbatim}`.
  **Done - why it is now true:** `src/citevouch/latex.py` masks verbatim
  bodies before comments are stripped, hides them again from `_CITE` and from
  `_convert`, and restores the literal characters at the very end of
  `to_text`, so `50\verb|%|` still prints a percent sign. `included_files`
  uses the same masked text. Proved by
  `tests/test_latex.py::TestATeXExampleIsNotACitation` (7 tests, one
  parametrised over `\verb*`, `\lstinline`, `\mintinline{tex}` and
  `\lstinline[language=TeX]`). Three mutations (no environment masking,
  no inline masking in `to_text`, bodies restored as nothing) each turned a
  test red.
  *Not covered*: `tabular` and `tikzpicture` still honour `%` - they are
  dropped from the output anyway, and pretending otherwise would only break
  for a document that nests one inside a verbatim block. `\verb` with an
  unbalanced delimiter inside a line is left alone rather than guessed at.
