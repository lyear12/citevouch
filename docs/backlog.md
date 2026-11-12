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

- [x] **One number, three spellings, three different verdicts.**
  *Done 2026-11-04.*
  *What was wrong.* A page printing `40 688` against a claim typing `40,688`
  produced `number-absent-in-quote` - an accusation that the source does not
  contain a figure printed on it. A non-breaking space in the same place
  produced exit 0 with `0 verified, 0 moved, 1 missing` and **zero findings**:
  a count nobody explained. A thin space produced `quote-fuzzy` at "similarity
  1.00" *plus* the same false accusation. All three pages `fold()` to identical
  text - those characters are already declared spaces - so every difference was
  inside the tool. Cause: `REPORT_PATTERN`, `MASK_PATTERN` and
  `canonical_number` each had a private rule about what joins digit triples and
  none of them owned the question.
  *Who was blocked.* Anyone quoting a paper typeset by a journal that groups
  digits with a space (very common in European and humanities typesetting) or
  that emits a thin space from its PDF pipeline. They were told their source
  does not print a number it prints.
  *Done when.* All nine spellings verify against all nine, and a genuinely
  different figure still fails.
  *Done - why it is now true.* `CANON_PATTERN` is the one owner of "are these
  two spellings the same value", used by the canonical tier, by the page-side
  number collection and by the claim's recorded numbers; a space counts only as
  a thousands group, so `numbers_in("2019 2020 2021")` is unchanged and pinned
  by a test. `canonical_number` strips every spacing character `fold` treats as
  a space. `tests/test_number_spelling.py` (49 tests) walks the 9x9 matrix
  through the real CLI, pins that a wrong figure still exits 1, and asserts that
  anything landing in the `numbers` tier produced a sentence.
  `_mut_spelling2.py`: 6 mutants, 6 red, no survivors — including "the
  canonical tier reads numbers the old way", "only an ascii space groups
  digits" and "the quote side reads numbers the old way".
  *Not covered.* A ledger written before 0.22.16 still records a spaced group as
  two numbers until `scan` is re-run; the changelog says so rather than the code
  rewriting history. No real PDF that emits thin-space groups was measured -
  the fixtures are hand-written text.

- [x] **29 conditional commands kept their test argument and glued their branches.**
  *Done 2026-11-04.*
  *What was wrong.* `etoolbox` and LaTeX2e between them offer 29 commands that
  choose between two pieces of author prose: `\iftoggle`, `\ifboolexpr`,
  `\ifnumcomp`, `\ifdef`, `\IfFileExists` and 24 more. None was in any table in
  `latex.py`, so all three of their failure modes happened at once - the test was
  pasted into the sentence, the two branches were glued into a word that is in
  neither of them, and `draft` would offer the result to the author inside a
  `claim:` block. Measured (`B` = backslash):
  `to_text("X " + B + "ifnumcomp{1}{=}{2}{Yes words}{No words} Y")` came out as
  `'X 1=2Yes wordsNo words Y'`, and the same shape for `\ifboolexpr`,
  `\ifdef\foo` and `\IfFileExists{sec/intro}`.
  *Who was blocked.* Anyone writing a thesis or an article in the LaTeX dialect
  most templates actually use. `biblatex` alone loads `etoolbox`.
  *Done when.* All 29 convert to `'X Yes No Y'`, the number of test groups is
  data in the table rather than something the handler guesses, and a test walks
  the table so a name added without its count fails.
  *Done - why it is now true.* `_BRANCH_COMMAND` is `dict[str, int]` mapping each
  name to its test-arity (three for `\ifnumcomp`, two for `\ifstrequal`, one for
  `\iftoggle`), `_BRANCH_BARE_TEST` names the seven `\ifdef...` commands whose
  test is a bare control sequence, and the handler steps over each test group
  before the two branch groups. `tests/test_latex_branch_commands.py` walks the
  table (23 group cases, 8 bare cases) and asserts the table and the test's own
  lists name the same commands. Six mutations, all red: table back to
  `ifthenelse` only, bare-test set emptied, every command counted as one group,
  branches joined flush again, the bare token not stepped over, the test always
  consuming exactly one group. Full suite 2339 passed.
  *Not covered.* No real `.tex` document was converted - the fixtures are written
  from the LaTeX2e and etoolbox manuals. `\ifboolexpr` with a nested
  `\notbool{...}` is converted but not asserted; only the plain form is.

- [x] **The skipped-block finding covered one dialect and left the other two silent.**
  *Done 2026-11-04.*
  *What was wrong.* `claim-block-unread` (0.22.5) reported a claim fence that a
  blockquote, a list item or an indent had put out of Markdown's reach. The format
  has three openers - a fence, an `<!-- claim` comment and a table row - and the
  detector matched only the first. Measured on a project holding one good fenced
  block plus one wrapped block, with `sources.toml` mapping `paper = "page.txt"`:
  `scan` and `check` each exited **0** with a ledger of `['c1']` for a wrapped
  comment, a blockquoted comment, an indented table row and a blockquoted table
  row, and the second block's id was in no finding and in no ledger row. `check`
  called those runs a verification.
  *Who was blocked.* Anyone who writes claim blocks as comments or table rows - the
  two dialects the READMEs advertise equally - and wraps one in a list item, which
  is where a claim about a single example naturally goes. They get a green run and
  a verified count that is short by one.
  *Done when.* Every wrapped block is named on the line the author wrote, whatever
  dialect opened it, and the three findings say which construct was found.
  *Done - why it is now true.* `_WRAPPED` is one table of `(dialect, pattern)` with
  an entry per opener, the table opener is `_TABLE_CLAIM.pattern[1:]` rather than a
  retyped copy of it, both call sites read it, and `_UNREAD_REASON` gives each
  dialect its own sentence. `tests/test_skipped_claim_blocks.py` gained
  `TestTheOtherTwoDialectsAreNotSilentEither`: the five shapes measured above are
  parametrized, `scan` and `check --use-recorded` must each exit 1, the three
  messages must be different sentences, a block at the left margin must still
  parse, and a four-backtick sample that shows all three openers must stay quiet.
  Nine tests were red before the patch, 32 pass after it; seven mutations against
  `_WRAPPED`, `_CONTAINER`, `_UNREAD_REASON` and `_id_from_opener` all went red
  with no survivors.
  *Not covered.* The container grammar is the same one a Markdown renderer applies,
  so a table row inside a blockquote has not been compared against a real renderer;
  the fixtures are hand-written.
- [x] **`doctor` counted a manuscript by the blocks it managed to read.**
  *Done 2026-11-04.*
  *What was wrong.* The `claims` line prints how many claim blocks a manuscript
  holds, and it computed that number from `len(parsed.spans)` and
  `len(parsed.claims)` - the blocks the parser consumed and the ones it
  accepted. A fence the parser walked past because a blockquote, a list item or
  an indent put it out of reach is in neither set, and this round had just
  given that fence its own finding. Measured on a project with one good block
  and one blockquoted block: `doctor --manuscript manuscript.md --root .`
  printed `[ok  ] claims      1 claim block` and exited 0, while `check` on the
  same tree printed `[high] claim-block-unread at manuscript.md:8 (c2)` and
  exited 1. The file holds two claim fences.
  *Who was blocked.* Anyone who runs `doctor` because a report looked wrong:
  the one command that exists to explain a run was describing a different file
  from the one it was pointed at, and it said `1 claim block` in the most
  authoritative voice in the output.
  *Done when.* The number on the line is the number of fences the file holds,
  and the sentence says when some of them were not read.
  *Done - why it is now true.* `_claim_blocks` adds the `claim-block-unread`
  findings to `spans` before printing, so the same file now reads `2 claim
  blocks, 1 of which the parser could read; the next command names the rest`,
  and a clean two-block manuscript still reads `2 claim blocks` with no
  qualifier. The check deliberately stays green and `doctor` still exits 0 -
  that division of labour is unchanged from the refused-block case, which has
  its own test. Four tests in
  `tests/test_skipped_claim_blocks.py::TestDoctorAgreesWithTheCommandItExplains`
  pin the count, the qualifier, the no-claims sentence and the clean case; five
  mutants against `doctor.py` were all RED with no survivors.
  *Not covered.* A manuscript holding an unread fence and a refused block
  together is arithmetic nobody pinned: the code would print three fences and
  one read, and no test asserts that combination.
  *Why it went unnoticed.* The other two counts had been made to agree in an
  earlier round, so the sentence only ever printed the smaller of the numbers
  and the missing category had nowhere to show up. A count built out of your
  own bookkeeping drifts by exactly the size of the category you have not
  modelled yet, and adding that category later looks like a change to the total
  rather than a correction of a wrong one.

- [x] **A claim block inside a blockquote, a list item or an indent was
  skipped without a word.** *Done 2026-11-04.*
  *What was wrong.* `parse_manuscript` only matched a claim fence at the left
  margin, which is right: Markdown renders an indented or container-prefixed
  fence as a code sample. What was wrong is that it said nothing. `scan` had a
  good near-miss sentence naming the indent, but that sentence lives in
  `scan._no_claim_blocks_finding` and only runs when `parsed.nothing_to_check`
  - a file that produced **zero** claims. One properly fenced block anywhere in
  the manuscript switched the account off, so a file holding one good block and
  one wrapped block was read as a file holding one block. Measured, on a
  project whose `page.txt` holds the sentence both blocks quote: `scan` wrote
  `citevouch.lock.json (1 claim)` and exited 0; `check` printed `1 claim — 1
  verified, 0 moved, 0 missing` with `worst severity: info` and exited 0;
  `doctor` printed `[ok  ] claims      1 claim block` and `[ok  ] extraction`
  and exited 0. The second block's id was in no finding and in no ledger row.
  The same measured for a bullet (`- ```claim`), an ordinal (`1. ```claim`) and
  a bare two-space indent.
  *Who was blocked.* Any author who wants a claim block inside a list item or a
  quotation of their own draft, and every reviewer reading a green tick over a
  manuscript that was only partly checked. `action.yml` runs
  `check --use-recorded`, so the CI job a contributor sees was the green one.
  *Done when.* The run names each skipped block by line, a file with no claims
  at all still gets `no-claim-blocks` and not both, a fence inside a code sample
  stays silent, and the recorded path agrees with the live one.
  *Done — why it is now true.* `manuscript._unread_findings` walks the file
  after the parse loop for `_WRAPPED_CLAIM` (a fence preceded by a blockquote
  marker, a bullet, an ordinal or an indent, in any mix) outside the spans the
  parser consumed, and reports `claim-block-unread` (high) per line with the
  claim id on that line. Both callers of the parser get it, so `scan`, `check`,
  `check --use-recorded` and `verify` all report it; `tests/test_skipped_claim_blocks.py`
  has 15 tests across the four shapes, the two "must stay silent" shapes (a
  four-backtick sample, a well-formed file), the HTML comment dialect, and the
  three commands. Nine mutants against `manuscript.py` were all RED with no
  survivors. `claim-block-unread` is in `CODES`, in `SARIF_RULES` and in both
  README tables, which `tests/test_readme_example.py` checks in both
  directions.
  *Not covered.* The new pattern accepts `1.` and `1)` but no test pins the
  right-paren spelling specifically; and `tests/test_claim_docstring.py` used to
  assert the fingerprint producer by *line number* (`manuscript.py:264`), which
  failed for a reason that said nothing about fingerprints when this change
  moved the call - it now asserts the file, and still prints the place in the
  failure message.

- [x] **A `.docx` named `paper.txt` was read as text, and the run accused
  the quote.** *Done 2026-11-03.*
  *What was wrong.* v0.22.1 made the reader look at the file's bytes when
  the suffix was a guess, but `.txt`, `.md`, `.text`, `.html`, `.htm`,
  `.xml` and `.pdf` are exempt - the suffix is the author stating the
  format, and a note beginning `PK` is prose. The file saved under the
  wrong name is exactly the case where that statement and the file
  disagree, and the plain reader **succeeds** on it: measured, a two-entry
  zip copied to `real.txt` gave 196 characters of mojibake with 47
  replacement characters and C0 controls, `problem` was `None`, and
  `citevouch check` answered a quote the document contains with
  `[high] quote-missing ... quote not found in real.txt`.
  *Who was blocked.* Anyone whose reference manager exports a `.docx` and
  whose download kept a text name. The words are in the file; the tool
  said they are not.
  *Done when.* A document saved under a text name is refused in the words
  of the format it actually is, a note that merely opens with a magic
  number still reads, the cache cannot hand the mojibake back, and a PDF
  is not re-judged by a rule about text.
  *Done - why it is now true.* `sources._noisy_format_problem` judges what
  came out of the reader with `textnorm._noise` - the score
  `_decode_text` already uses - confirmed by `_opaque_format`'s header, so
  neither signal fires alone. Measured separation: the zip scores 47 in
  196 characters, the `PK` note 2 in 73, against a threshold of
  `max(4, len // 50)`. Both call sites apply it, because a cache holds
  pages and not a verdict; `.pdf` is exempt because its bytes were already
  checked against the header. Eight mutations, none survived, scoped to
  `tests/test_noisy_text_suffix.py` and `tests/test_opaque_formats.py`.
  *Not covered.* No real Word document was read - the fixture is a
  hand-built two-entry zip, which is what Word writes, but styled runs and
  tracked changes are not exercised. A binary file whose UTF-8 reading is
  quieter than 2% noise is still read as text; that is the same trade the
  codec fallback makes, and it is written down here so it is a decision
  rather than an oversight.
- [x] **A PDF named `paper.txt` was decoded as text, and the run accused the
  quote.** *Done 2026-11-03.*
  *What was wrong.* `extract_pages` chose its reader from the suffix alone.
  A source file whose name ends in `.txt`, `.md` or `.html` went to the
  plain-text reader even when its first bytes say `%PDF-`, and that reader
  succeeds on a PDF: the demo paper copied to `real.txt` came back as 4
  pages / 206,870 characters of mojibake with `problem=None`.  Nothing
  downstream can tell those pages from prose, so `citevouch check` answered
  a claim quoting the paper's own sentence with
  `[high] quote-missing ... no passage in the source is close to this quote
  in real.txt`, exit 1.
  *Who was blocked.* Anyone who renamed a download, or whose reference
  manager saved a PDF under a name it also gave a `.txt` sibling.  Their
  quote is on the page, and the tool told them it is not - the one error this
  project exists to refuse to make.
  *Done when.* A PDF under any name reaches the PDF readers, a real text file
  reads exactly as before, and a cached mojibake reading cannot outlive the
  fix.
  *Done - why it is now true.* `sources._looks_like_pdf` reads five bytes and
  compares them to the whole magic; `extract_pages` switches to `.pdf` when
  they match, above the cache lookup and before `extractor_candidates` picks
  the reader names, so the entry is stored under the reader that ran.  The
  end-to-end test asserts `check` prints `quote-found` and no `quote-missing`,
  and a second test asserts the ledger records the page the PDF reader found.
  Four of five mutations are killed; the survivor is
  *a pdf suffix also re-reads the header*, which is not a defect: the check
  runs the reader the suffix already names, and a test pins that both routes
  produce identical pages.
  *Not covered.* A truncated PDF whose header is intact is refused by the
  readers rather than by this branch, and that refusal reaches the author
  the same way.
- [x] **Four functions with docstrings describing features this tool does not
  have.** *Done 2026-11-03.*
  *What was wrong.* An AST scan of `src/`, `tests/` and `tools/` found these four
  names referenced nowhere: `verify.doi_index`, documented as the map "for the
  optional Crossref cross-check" - and there is no Crossref cross-check, because
  `AGENTS.md` says one belongs in a separate optional command rather than inside
  `scan`/`verify`/`check`; `verify.rebuild`, documented as the wrapper "so the CLI
  has one call per verb" while the CLI imports `verify` directly;
  `verify.summarize`, a second copy of the sentence a run prints, unreachable
  while `report.py` writes the real one; and `sources._odd_bindings`, which
  pluralised a manifest's bad keys into one sentence while the live code
  (`sources.py:1271`) writes that sentence per key.
  *Who was blocked.* Anyone reading the source to find the Crossref option, and
  anyone trusting the 90% line coverage of `verify.py` to mean the file was
  exercised.  Deleting the four took it to 96% and changed no test, which is the
  defect stated plainly: nothing was running them.
  *Done when.* The four are gone and a check fails when a package-level function
  is named nowhere.
  *Done - why it is now true.* `tests/test_no_dead_functions.py` resolves each
  package function against every name the repository references, **per module**,
  because the per-name version is the version that misses: `draft.summarize` is a
  real call and `verify.summarize` is not, and a scan collecting attribute names
  alone counts them as one use.  Six mutations are killed (`survivors: none`):
  re-adding each of the four functions, making the resolver stop qualifying
  anything, and making the corpus scan reach nothing.  The last two matter because
  a resolver that returns empty sets makes the guard green and meaningless, so the
  guard file carries its own liveness assertion.
  *Not covered.* Reachability is decided by reading source text, so a function
  reached only through `getattr` would be reported as dead.  None of the four was,
  and the package has no `getattr` dispatch.
- [x] **A `sources.toml` whose keys sit at the top level was read as an empty
  manifest.** *Done 2026-11-03.*
  *What was wrong.* The JSON reader takes its mapping at the top level, so
  ``paper = "page.txt"`` written straight into `sources.toml` with no
  `[sources]` header looks like a manifest to one format and like nothing at all
  to the other. Measured on `/tmp/p155` (one claim naming `paper`, `page.txt`
  holding its sentence): `check` printed `[high] source-missing at
  manuscript.md:3 (c1): claim c1 names source='paper' but no entry in
  sources.toml and no --source path resolves it; add it to sources.toml` - about
  a key that was in the file, three lines above the header the message asked
  for - and `doctor` printed `[ok  ] manifest sources.toml (19 bytes), 0
  sources, every one of them present on this machine` and exited 0. The same
  keys in `sources.json` (`{"paper": "page.txt"}`) bind and exit 0.
  *Who was blocked.* Anyone who switched format, or copied a JSON example into a
  TOML file, and was then told to add the key they had already written.
  *Done when.* Both readers refuse that file, with the same sentence, naming
  the keys and the two ways to fix it.
  *Done - why it is now true.* `_refuse_shapes_only_one_reader_follows` (the
  text pre-scan both readers call first) raises when keys sit at the top level
  and no table header declares them. It is on the text, not on the parsed dict,
  because `_mini_toml` - the 3.10 fallback - files pre-header keys under a
  bucket named `""`: written against the dict the check would refuse on 3.11
  and stay silent on 3.10, which is the interpreter-dependent answer that
  function exists to prevent. A key literally called `sources` (which has the
  reader's own, more precise, `there is a key called "sources" but it holds an
  integer` message) and a dotted name (`pa.ge`, which both readers agree binds
  nothing and which `tests/test_manifest_readers_agree.py` pins as readable) are
  excluded. Both exclusions were forced by real failures, not chosen in advance:
  the first shadowed three assertions in `tests/test_manifest_value_shapes.py`,
  the second broke `test_the_manifest_is_read[a dotted key under no [sources] at
  all]`.
  `tests/test_manifest_top_level.py` (15 tests) drives both readers by name and
  asserts they agree; six mutations are killed (`survivors: none`), two of them
  only after the tests were tightened - `FLAT` had every key stray, so a count
  over `seen` matched a count over `stray`, and `"[sources]" in message` also
  matched the sentence's own "no [sources] table" clause.
  *Not covered.* A manifest that mixes the two spellings (`paper = "a.txt"` at
  the top AND inside `[sources]`) is still refused with the single sentence; the
  message does not say which of the two entries the author probably meant. No
  real third-party `sources.toml` was tried - every fixture is hand-written.
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

- [x] **Seven file-inclusion commands pasted their path into the prose and
  reported nothing.**

  *What was wrong.* `\input` and `\include` were classified; `\subfile`,
  `\import`, `\subimport`, `\includestandalone`, `\includepdf`,
  `\lstinputlisting` and `\verbatiminput` were not, so they hit the same
  fallthrough that produced `blueblue` for `\textcolor`. Measured:

  ```
  \subfile{sec/intro}          -> text 'sec/intro', included_files []
  \import{chapters/}{one}      -> text 'chapters/one', included_files []
  \includepdf{pages/p1.pdf}    -> text 'pages/p1.pdf', included_files []
  \lstinputlisting{code/s1.py} -> text 'code/s1.py', included_files []
  ```

  *Who is blocked.* Anyone whose paper is split across files - which is what
  `\subfile` and the `import` package are for. Two things broke at once: the
  sentence `draft` builds a claim from carried a file path, and the note saying
  which parts of the paper were not read was empty. A paper split across seven
  files looked as if it had been read whole, and every citation in those seven
  files was missing from the report without being named.

  *Done when.* All seven keep their path out of the converted text, all seven
  are reported by `included_files` in source order, `\import`'s two arguments
  are joined into one name, and the older three forms keep working.

  *Done - why it is now true.* `src/citevouch/latex.py` gained
  `_INCLUDE_ARGUMENTS` (command to argument count, two for `import` and
  `subimport`), a converter branch that drops those arguments whole, and
  `_other_includes` which re-reads them from the comment-stripped text so
  `\verb` and `%` stay invisible. `tests/test_latex_more_includes.py` (26 tests)
  covers each command twice (text and report), optional arguments, the two
  invisible forms, the older forms, source order, and one end-to-end `draft`
  run asserting the note names `sec/intro` while the claim block does not. Four
  mutations are red: leave the name in the prose (7 tests), never report the
  file (14), report only the first argument of a two-argument command (5), drop
  only the command name and keep its argument (7). Shipped in 0.19.75.

  *Not covered*: a file name that itself contains a brace, which TeX cannot
  express either; `\includegraphics` is still dropped without being reported,
  because a picture cannot hold a citation.

- [x] **A macro definition's body was read as a sentence, so the tool made up
  one citation and lost another in the same step.**

  *What was wrong.* `\newcommand`, `\renewcommand`,
  `\providecommand`, `\DeclareRobustCommand`, `\def`,
  `\gdef`, `\edef`, `\xdef`, `\newenvironment`,
  `\renewenvironment` and `\newtheorem` were in
  `_DROP_ARGUMENT`, which drops one argument. A definition takes a name, an
  optional count, an optional default and a body, so everything after the
  name was converted as prose. Measured before the fix:
  `\newcommand{\knuthcite}{\citep{knuth}}` produced
  `'[@knuth]'`, and `citation_sites` returned `['knuth']` for a document that
  never cites Knuth, so `draft` offered a `sources.toml` line for the invented
  key. `\newcommand{\seecite}[1]{see \citep{#1} for
  details}` recorded a citation to the key `#1` while every real call
  `\seecite{knuth}` became a bare word: a paper that cites once per
  paragraph was told it cites nothing. `\newcommand{\inc}[1]{\input{#1}}` made
  `included_files` return `['#1']`.

  *Who is blocked.* Every author who defines a shorthand for a citation -
  which is how a paper with twenty citations to one work stays readable - and
  every author whose preamble defines environments or theorem styles with a
  body.

  *Done when.* The body is cut out of the converted text, and out of the raw
  source for readers that do not convert first; a real include beside a
  definition is still reported.

  *Done - why it is now true.* `_definition_end` reads the three argument
  shapes to their end (braced name with optional count and default; the
  low-level `\def\name#1{body}` form whose name is not in
  braces; `\newtheorem{name}{Printed}[within]`), and
  `_without_definitions` runs the same cut over the raw source before
  `included_files` matches anything. `tests/test_latex_definitions.py` has 26
  tests covering the eight definition spellings, the three shapes, both
  environment bodies, the theorem form, the parameter hole, and one end-to-end
  `draft` run asserting no proposal is written for a key only the body names.
  Five mutations are red: read the body as prose again (23 tests), stop cutting
  the raw source (4), keep an environment's second body (1), stop a low-level
  definition at its name (5), keep a theorem's printed name (1). Shipped in
  0.19.76.

  *Not covered*: macros are still not expanded at their call sites, so
  `\seecite{knuth}` is a missing citation rather than a found one -
  fixing that is a feature (a TeX expander), not a defect fix.
- [x] **A command whose arguments are all metadata pasted them into the
  sentence.** Twenty-eight LaTeX commands name a counter, a length, a style, a
  registry key or a file, and the converter's fallthrough ("drop the name, keep
  whatever it wraps") kept every one of them. The worst shape is a number at the
  start of a sentence: `\setcounter{page}{3}We collected 40,688 examples.`
  converted to `3We collected 40,688 examples.`, and that sentence is what
  `draft` writes into a claim block, so the ledger then records a number the
  author never typed.
  *Who is blocked*: every LaTeX author whose preamble style puts a
  `\setcounter`, `\pagestyle` or `\setlength` inside a
  paragraph - which is how most templates that change the page style mid-document
  do it. They get proposals with junk glued to the front and, worse, quotes that
  no longer match the PDF.
  *Done when*: the argument counts are data next to the names, the sentence
  converts byte for byte, and a test fails if the handler drops the wrong number
  of arguments.
  **Done - why it is now true:** `_DROP_ALL_ARGUMENTS` maps each of the
  twenty-eight names to how many arguments it takes and the converter skips them
  whole; `\multicolumn` and `\foreignlanguage` are
  skip-first commands with their text converted, `\texorpdfstring`
  keeps only its first argument, and the xparse `\NewDocumentCommand` family is
  now recognised as definitions. `tests/test_latex_non_prose_arguments.py`
  asserts the **whole converted sentence** for all twenty-eight spellings rather
  than a list of forbidden words, because a forbidden-word test passes when the
  handler drops the wrong number of arguments.
  `\multicolumn{2}{c}{wide text}` passed a "no `{2}` in the output"
  assertion while producing `cwide text`. Five mutations are red: fall back to
  the fallthrough, drop only the first argument, drop exactly one for every
  command, keep both `\texorpdfstring` arguments, and stop
  recognising the xparse definition spellings. 1663 tests pass and the demo
  still reports 5 claims - 4 verified, 0 moved, 1 missing.
  *Not covered*: a macro invocation is still not expanded at its call site, so
  `\seecite{knuth}` remains a missed citation rather than a wrong
  one. That is a feature request, not a defect in this entry.

- [x] **Text TeX never reads was being converted as prose.** `\iffalse` is
  how a LaTeX author comments out a paragraph, and the converter read the body:
  `\iffalse \citep{hidden} \input{ghost/sec} \fi` measured as
  `[@hidden]` in the text and `ghost/sec` in the include list. Two more shapes of
  the same family were wrong in the other direction: `\ifdefined\foo` pasted
  its own name into the sentence, and `\ifthenelse{1=2}{...}{...}` left
  `1=2` at the front of the first branch.
  *Who is blocked*: every author who comments out a paragraph instead of deleting
  it - which is what a draft looks like on the way to a published paper. They get
  a proposal for a citation they turned off, a missing-file warning for a file the
  paper never reads, and claim text with a fragment glued to the front.
  *Done when*: dead text contributes no citations and no files; live text keeps
  its body and loses its marker; and the limitation for the operand-taking
  conditionals is written as a test rather than a comment.
  **Done - why it is now true:** `_conditional_span` finds the matching
  `\fi` by counting nesting, `\iffalse` and `\if0` bodies are cut,
  a `\else` inside one is kept as live text, `\iftrue`/`\if1`/`\ifdefined`
  keep the body and drop the marker, `\ifthenelse` drops only the test, and
  `included_files` runs `_without_false_branches` over the raw source so the two
  readers agree about which text is real. An unterminated conditional follows
  TeX: a dead body takes the rest of the file, a live one is converted to the end.
  `tests/test_latex_conditionals.py` has 36 tests; six mutations are red - a dead
  branch converted as prose, a live branch losing its body, the include reader not
  cutting dead branches, the `\else` inside a dead block staying dead, the
  `\ifthenelse` test pasted back, and an unclosed live conditional dropped.
  1699 tests pass and the demo still reports 5 claims - 4 verified, 0 moved, 1
  missing. Shipped in 0.19.78.
  *Not covered*: `\ifnum`, `\ifdim`, `\ifodd`, `\ifx`,
  `\ifcat` and `\ifcase` take operands before their body, and those
  operands are still words in the sentence. Finding where they end is a
  token-level scan, not a table of names; a half fix that cut the body without
  reading the operand would drop live text. `TestTheConditionalsThatTakeOperands`
  asserts both halves of the current behaviour.

- [x] **A footnote was spliced into the sentence it hangs on.** They were inline
  commands, so the note's words were joined to the words on either side:
  `The method works\footnote{See \citep{fn} for the proof.}, and we ...`
  converted to `The method worksSee [@fn] for the proof., and we ...`. `worksSee`
  is in no paper, and `draft` proposed exactly that string as the claim's text.
  *Who is blocked*: every author who uses a footnote for the citation's proof -
  which is how a footnote is normally used in this literature. The proposal is
  built on a sentence nobody wrote, and the note's own citation is counted as if
  it appeared in the middle of the main clause.
  *Done when*: the main sentence survives whole, the note keeps the author's
  words, and a citation inside a note is still a citation.
  **Done - why it is now true:** the three note commands are their own set
  (`_SEPARATE_ARGUMENT`) instead of being inline, and their bodies are collected
  into a list that `to_text` appends after the prose, converted rather than
  moved raw. `'The method works, and we show it.\n\nSee [@fn] for the proof.\n'`.
  Giving the note its own paragraph *in place* was tried and rejected: it left
  the following comma starting a paragraph (`\n\n, and we show it.`). 26
  tests in `tests/test_latex_notes.py`; seven mutations, none surviving,
  including two that survived the first pass - a body moved without being
  converted, and a conditional branch that forgot to pass the collector down.
  1725 tests pass and the demo still reports 5 claims - 4 verified, 0 moved, 1
  missing. Shipped in 0.19.79.
  *Not covered*: a note inside a heading keeps its words but the heading still
  reads without them; nothing pins where each note lands when a document has
  several, only that each body is present exactly once.

- [x] **Chinese prose was one sentence long, and a passage was measured in
  characters.** CJK scripts put no space after a full stop and the splitter
  required one, so `_sentences_of("第一句话。第二句话。第三句话。")` returned a
  single run. Every consequence followed from that one number:
  `_is_passage` refused the run for exceeding the ceiling, `draft` reported
  `nothing on any page shares enough terms with the sentence (3 needed)` about a
  paragraph sharing eighteen of them, and the whole paragraph became the
  `claim:` text of anything proposed from it. The floor and ceiling were also
  counted in characters, which is a letter in English and a syllable in Chinese.
  *Who is blocked*: every author writing the tool's own headline case in a
  language without spaces between sentences - which is the language half of this
  project's readers write in, and the language this project's own README is
  translated into.
  *Done when*: a Chinese paragraph is split at its full stops, a Chinese
  sentence of ordinary length counts as a passage, and `draft` proposes from
  Chinese prose instead of telling the author no page shares enough terms.
  **Done - why it is now true:** `_SENTENCE_END` has two zero-width branches
  after `。！？`, one for a following character and one for a following closing
  bracket, so nothing is consumed and `「好的。」` stays whole. The window is
  `MIN_SENTENCE_WORDS = 7` / `MAX_SENTENCE_WORDS = 70`, counted by `_words` - a
  run of letters, or one CJK character. Measured on this repository's own prose
  in both scripts: the character window 40..400 kept 37% of Chinese sentences
  (50/134) and 84% of English ones (1797/2140); the word window 7..70 keeps 86%
  (115/134) and 84% (1797/2140), so English is untouched and Chinese stops being
  systematically refused. End to end, a Chinese manuscript now gets one block
  with 12 shared terms where it used to get `0 claim block(s) proposed`.
  `tests/test_chinese_sentences.py` 20 tests; four mutations (latin-only
  splitter, one CJK branch instead of two, count characters as words, restore
  the character window) are red with 1 to 9 tests each. 1745 tests pass and the
  demo still reports 5 claims - 4 verified, 0 moved, 1 missing. Shipped in
  0.19.80.
  *Not covered*: Japanese and Korean were checked with one sentence each, not
  with a corpus - the CJK ranges are the four this repository already uses for
  matching, so Hangul came along without its own measurement; a full stop inside
  an abbreviation (`etc.`) splits a sentence where it should not, in every
  script, and that was true before this change.

- [x] **A citation removed from Chinese prose left a space inside the
  sentence.** `statement_of` closes the gap a marker leaves before a closing
  mark, and the mark class was `.,;:!?`. `相关研究指出词汇与构式之间存在互动关系
  [@page]。` came out as `相关研究指出词汇与构式之间存在互动关系 。`, so the
  `claim:` text `draft` proposed held a space no Chinese writer types and no
  source prints. This was the second copy of the assumption the splitter fix in
  0.19.80 removed; the two lines are forty apart and neither names the other.
  *Who is blocked*: the same authors the splitter fix was for - every Chinese
  manuscript that cites at the end of a sentence, which is where a citation
  normally goes.
  *Done when*: a citation that sits before a CJK mark leaves no space behind, and
  a space that sits between two words is not touched.
  **Done - why it is now true:** the marks are one named set,
  `_NO_SPACE_BEFORE` - the CJK stops, the small marks, the ellipsis and the
  closing brackets plus the Latin five - escaped once into
  `_NO_SPACE_BEFORE_CLASS` so a `]` in the set cannot end the class early.
  `'相关研究指出词汇与构式之间存在互动关系 [@page]。'` gives the closed-up
  sentence; `'我们 [@p] 认为构式承载意义。'` keeps its space; `'他说：“好
  [@p]。”'` gives `他说：“好。”`; `'价格是 [@p] 3.5 万元。'` is unchanged.
  12 tests in `tests/test_cjk_statement_space.py`; four mutations (the five Latin
  marks again, the stops without the closing marks, keep every space, collapse
  every space) are red with 3 to 9 tests each. Shipped in 0.19.81.
  *Not covered*: no Japanese or Korean sample beyond the marks the three scripts
  share; nothing measures how often a citation sits before a closing bracket in
  real Chinese prose, so the bracket half rests on the construction rather than
  on a count.

- [x] **The Chinese LaTeX stacks pasted font names and point sizes into the
  prose.** `\zihao`, `\CJKfamily`, `\CJK`, `\chinese`, `\fontsize`,
  `\linespread`, `\setCJKmainfont` and the `\ctexset`/`\CTEXsetup` family all
  name a font, a size or a registry code, and the converter's fallthrough - drop
  the command, keep what it wraps - kept the argument.  On a `ctexart`
  manuscript `{\zihao{5} 相关研究 ...}` became `5 相关研究 ...`, so `draft`
  proposed a claim whose text opens with the point size; `\ctexset{...}` left
  `section/format=` and `\CTEXsetup[format=...]{section}` left both the bracket
  and the word.
  *Who is blocked*: every thesis written in the `ctex` class - which is the
  standard Chinese class, so this is the default shape of a Chinese LaTeX
  manuscript, not an unusual one.  The damage is not a crash or a lost citation:
  `5 相关研究...` reads like a sentence that begins with a number, so the block
  pasted into the manuscript scans, quotes the right page and cites the right
  key, built on words nobody wrote.
  *Done when*: those fifteen commands leave nothing in the prose, and what
  follows them is untouched.
  **Done - why it is now true:** fifteen names in `_DROP_ALL_ARGUMENTS` with
  their argument counts, measured one at a time: `{\zihao{5} 我们展示该方法。}`
  -> `我们展示该方法。`, `我们 \zihao{5} 展示该方法。` -> `我们 展示该方法。`,
  `\CTEXsetup[format={\Large\bfseries}]{section}` -> nothing,
  `\xeCJKDeclareCharClass{CJK}{4E00}` -> nothing.  A `ctexart` manuscript that
  used to propose `claim: 5 相关研究...` now proposes the sentence the author
  wrote, and still finds the citation inside it.  18 tests in
  `tests/test_latex_ctex_commands.py`; seven mutations (each table entry removed
  in turn) are red with 1 to 5 tests each. Shipped in 0.19.82.
  *Not covered*: no real ctex thesis, so the argument counts come from the ctex
  and xeCJK manuals plus what the converter does with each - a command whose
  signature has an optional argument before the mandatory one would still leak;
  `\zihao{-4}` is covered but `\newCJKfontfamily` is not, because its name
  argument is unbraced and needs the definition machinery.

- [x] **A control word ate the Chinese sentence glued to it.**
  `str.isalpha()` is true for CJK characters, and Chinese prose has no
  spaces, so `\noindent构式语法认为...` was scanned as a single control word whose name was
  `noindent` plus the whole sentence - and the sentence went with the name.
  Measured on a four-line `ctexart` document: what survived was the closing
  punctuation on each line, all four sentences gone.
  *Who is blocked*: every Chinese LaTeX manuscript, which is the default shape
  of one - `\noindent` and `\par` are normally written with no space after them in ctex prose.  The
  damage is silent in the way that matters: `draft` proposes nothing for a
  manuscript full of sentences, and `check` reports a clean run over text that
  was never read.  Neither says anything is wrong, because from inside the tool
  nothing is.
  *Done when*: a control word followed directly by Chinese leaves the Chinese,
  and every reader that scans a control word agrees.
  **Done - why it is now true:** TeX defines a control word as a backslash and
  then ASCII letters, so the scan is now `[A-Za-z]` through `_is_letter()`, in
  all five sites that scan one: the converter, `_without_definitions`,
  `_conditional_span`, `_without_false_branches` and the main loop.  A
  `\noindent` glued to a Chinese sentence now keeps the sentence; a four-line
  `ctexart` document keeps all four lines; `\item1.` keeps its `1` (a digit
  ends a name in TeX too); `\input` glued to Chinese still reports its file;
  a `\fi` glued to Chinese now closes its branch instead of running to the end
  of the file.  24 tests in
  `tests/test_latex_cjk_control_words.py`; three mutations, none surviving.
  Shipped in 0.19.83.
  *Not covered*: no real ctex thesis, so the shapes come from the ctex manual
  plus the converter's own behaviour; the same fix changes Cyrillic and Greek
  prose too, which is right, but no test covers either.

- [x] **A Chinese quote that was a near-miss was reported as absent.**

  **What was wrong.** `src/citevouch/matching.py`'s fuzzy tier - the only tier
  that can say "the source has a passage like this but not these words" -
  counted its comparison units with `_TOKEN = re.compile(r"[^\s]+")`.
  Whitespace is how Latin script separates words and is not how Chinese does,
  so a 40-character Chinese quote was exactly one token, below
  `MIN_FUZZY_TOKENS`, and the tier answered

  ```
  reason='quote not found (too short for a fuzzy comparison)'
  ```

  about a sentence whose every character had just been compared.  One character
  changed in the quote, on a page that holds the passage:

  ```
  quote = 相关研究指出词汇与构式之间存在互动關聯，这种互动可以解释许多...
  before: tier='none'   similarity=0.000
  after:  tier='fuzzy'  similarity=0.947
  ```

  Every slightly-mistranscribed Chinese quote therefore came out as
  `quote-missing` at high severity - the tool telling an author that words
  they copied off the page are not on it.

  **Who is blocked.** Anyone writing a Chinese manuscript, which is the
  audience `draft` was just taught to split into sentences (0.19.80) and whose
  LaTeX stacks were just taught not to leak font names (0.19.82).  The two
  tiers below fuzzy kept working, so this only bit when the quote was not
  verbatim - which is exactly the case the tier exists for, and the case where
  a wrong answer is most expensive.

  **Done when.** A Chinese quote one or two characters off reaches the fuzzy
  tier, its reason says "similar passage" rather than "too short", and the
  excerpt it quotes back is joined as prose.

  **Done - why it is now true.** `_tokens()` counts a CJK character as one
  token and a Latin run as one word; both the needle and the page go through
  it.  `MIN_FUZZY_TOKENS` was re-measured rather than trusted, because its unit
  changed for Chinese from words to characters: on 60 sentences of this
  repository's own Chinese prose, one changed character scores at least 0.667
  and 95% at least 0.857, two unrelated sentences at most 0.333, and at five
  characters an unrelated pair peaks at 0.4 against a typo's 0.8.  The window
  excerpt joins single characters with nothing and Latin tokens with a space.
  18 tests in `tests/test_fuzzy_cjk_tokens.py`; five mutations all red -
  whitespace tokenizer, character buffered into the Latin run instead of
  emitted, windows joined with spaces, floor bypassed, page side counted the
  old way.  Shipped in 0.19.84.

  *Not covered*: no real Chinese manuscript end to end.  The sample is this
  repository's own prose, which is technical writing and may share more
  characters between unrelated sentences than a paper does.  Japanese and
  Korean take the same code path and were not measured separately - the range
  table covers them, which is a claim about coverage rather than about those
  languages' tokenisation.  A quote mixing scripts with no space between them
  is handled (`构式used` is three tokens) but no threshold was measured on it.

- [x] **A quote in quotation marks was reported as not verbatim - at
  similarity 1.00.**

  **What was wrong.** A manuscript introduces somebody else's words with
  quotation marks.  The marks are not on the page unless the page quoted
  somebody too, so a sentence copied out of the source and put in quotes
  matched no tier.  It came back as `quote-fuzzy` at high severity with a
  message that contradicted itself in one line:

  ```
  [high] quote-fuzzy: the source has a similar passage but not these words
  verbatim (closest passage, page 1, similarity 1.00)
  ```

  Similarity 1.00 is verbatim.  Measured on a page holding the sentence bare:

  ```
  bare         tier='exact'
  "bare"       tier='fuzzy' similarity=1.000   rc=1
  “bare”       tier='fuzzy' similarity=1.000   rc=1
  「bare」       tier='fuzzy' similarity=1.000   rc=1
  《bare》       tier='fuzzy' similarity=1.000   rc=1
  ```

  **Who is blocked.** Any author in the humanities, where quoting with marks is
  how the work is written, and any Chinese author, whose manuscripts use
  `「」` and `《》` for the same purpose.  A correct quote
  produced a failing gate - the worst shape a gate can have, because the fix an
  author reaches for is to stop running it.

  **Done when.** A quote wrapped in a matched pair of marks reaches the tier
  that would have found it bare, and a quote that is genuinely absent still
  fails.

  **Done - why it is now true.** `matching.find_in_pages` retries with
  `textnorm.strip_wrapping_quotes(quote)` when the first read finds nothing, and
  accepts the retry **only** when it finds the quote - a weaker verdict about
  text the author did not write is not an improvement on the verdict about the
  text they did.  The stripper peels eleven matched pairs (straight, curly,
  corner, white corner, book title, angle, lenticular, tortoise, halfwidth), and
  never peels down to nothing, because `《》` can be a book title that is
  part of the page.  All five shapes above are `tier='exact'` now, and a wrapped
  absence still exits 1 with `quote-missing`.  25 tests in
  `tests/test_wrapped_quotes.py`; six mutations, five red - no retry, peel one
  layer only, peel an empty pair to nothing, drop the CJK pairs, peel the page
  instead of the quote.  Shipped in 0.19.85.

  *Not covered*: a manuscript that wraps quotes in a pair no table lists (some
  journals use `„ “`) is still reported as a near miss.
  `strip_wrapping_quotes` is only ever applied to the **quote**, never to the
  page, and that is a decision rather than an omission - the page is evidence and
  it is read as written.

- [x] **A manuscript citing three sources in one parenthesis was reported as
  citing none.**

  **What was wrong.** `\cites{a}{b}` and its siblings carry one brace group per
  source.  The citation pattern in `src/citevouch/latex.py` looked for a name,
  optional `[...]` arguments and one `{...}`: it stopped at `cite`, and the `s`
  that follows is neither `*` nor `[` nor `{`.  The command then fell through to
  the generic rule for a command nobody knows - drop the name, keep the
  arguments - so every key was left in the prose as a bare word:

  ```
  \cites{a}{b}                -> 'ab'          sites=[]
  \parencites{a}{b}           -> 'ab'          sites=[]
  \cites[1][2]{a}[3][4]{b}    -> '[1][2]a...'  sites=[]
  \citep{a}                   -> '[@a]'        sites=['a']
  ```

  **Who is blocked.** Authors using biblatex, which is most of the humanities
  and most of `latexmk`-driven templates: `draft` reported "0 citation(s) found"
  about a paper full of them and proposed nothing.  `\fullcite`, `\parencite`,
  `\textcite`, `\autocite`, `\footcite`, `\smartcite` and `\supercite` were
  missing from the same table outright, so those produced no proposal either.

  **Done when.** Every plural command converts to a marker carrying all its
  keys, `citation_sites` reports one site per key, and the singular names all
  resolve.

  **Done - why it is now true.** `_MULTI_CITE` consumes a run of
  `([...])?{...}` groups and `_pandoc_multi` joins every key into one marker;
  the singular table gained the seven biblatex names.  `draft` has its own
  pattern for LaTeX citations in Markdown with the same gap, fixed the same way,
  because a table of names retyped in a second place is a table that will be
  incomplete in the second place.  44 tests over
  `tests/test_latex_plural_citations.py` and `tests/test_draft_latex_citations.py`;
  eleven mutations all red across the two files.  Shipped in 0.19.86.

  *Not covered*: the two patterns are still two tables, so a citation command
  added later has to be added to both.  No manuscript that mixes natbib and
  biblatex plural forms inside one paragraph was tried.

- [x] **A Pandoc citation that carries a page number was read as no citation.**
  *What was wrong*: the bracket recogniser required the body to be keys
  separated by semicolons, so every form carrying a prefix or a locator
  matched nothing. Measured with `citation_sites`: `[@a, p. 3]` -> `[]`,
  `[see @a]` -> `[]`, `[-@a, ch. 2]` -> `[]`, `[@a, p. 3; @b, p. 4]` -> `[]`,
  while `[@a]` -> `['a']` and `[@a; @b]` -> `['a', 'b']` worked. Pandoc's
  grammar is `[prefix @key suffix; @key2 suffix2]`: the bracket holds prose
  and a locator, not only keys, and a page number is how a large share of
  real Markdown citations are written.
  *Who is blocked*: everyone who pastes citations out of a reference manager
  or follows Pandoc's own examples. `draft` answered "no citations were
  found" to a manuscript citing a source in every paragraph, and then
  advised the author to write citations in a form the manuscript was
  already using.
  *Done when*: every production of the bracket grammar names its key, an
  `@` inside a word is still not a key, and the second reader of the same
  pattern deletes exactly what the first one found.
  **Done - why it is now true:** `src/citevouch/draft.py:_PANDOC` reads
  `[prefix @key suffix; ...]`, and both it and `_AT_KEY` carry a lookbehind,
  so `[contact me at x@y.com]` names nothing and nothing is deleted from a
  sentence that holds no citation. `statement_of` strips `_LATEX_MULTI`
  before `_LATEX`: without that line a sentence ending
  `{BS}cites{{a}}{{b}}` reached the proposal file as
  `claim: | ... {BS}cites{{a}}{{b}}.` - a sentence no human wrote, in the one
  field this command exists to propose. Proved by
  `tests/test_pandoc_locators.py` (35 tests) and
  `tests/test_pandoc_brackets.py` (15 tests), which put both readers on the
  brackets that hold no citation. Five mutations, all red: the body must be
  keys only; the key loses its lookbehind; the body loses its lookbehind;
  `_LATEX_MULTI` is not stripped; the whole bracket is stripped instead of
  the citation. Shipped in 0.19.87.

  *Not covered*: no real manuscript exported from a reference manager was run
  through this - the grammar is read from Pandoc's documentation and from the
  forms the tests enumerate. Numeric styles (`[3]`) are still not citations
  here; the tests only pin that they are not deleted.

- [x] **`doctor` told an author that a failing project was fine.**
  *What was wrong*: the claims line read `<file> holds no claim blocks, so
  every run will report 0 claims checked and exit 0`.  Both halves are false -
  `check`, `verify` and `scan` all report `no-claim-blocks` (high) and exit 1 -
  and the sentence was written in 0.19.47 by the commit that added the check,
  so it described the behaviour that change had just removed.  `git log -S`
  finds `920b87e`; checking that commit out and running `check` on a prose-only
  file exits 1, so the sentence was wrong from its first release.
  *Who is blocked*: the author who runs `doctor` because the report looked
  empty - the one reader the line exists for - and is told the emptiness is
  normal and green.
  *Done when*: the line says what happens, and something fails if a message
  grows a prediction of a clean exit again.
  *Done - why it is now true*: `doctor._claim_blocks` now reports
  `reports no-claim-blocks and exits 1: nothing in this project is ever
  checked`.  `tests/test_no_predicted_exit.py` holds three tests about that line
  (it must not promise a clean run; it must name the code and the failure; the
  two commands must agree on the code) and one mechanical test that walks every
  non-docstring string constant in `src/citevouch/*.py` and refuses any match
  for `exit 0`.  Two mutations reproduce the defect: restoring the old detail
  turns the file red, and pasting a plausible `exit 0` promise into an
  unrelated message in `sources.py` is caught by the scan.  Shipped in 0.19.88.
  *Not covered*: only `exit 0` is refused.  A message predicting a failure is
  still unguarded, deliberately - a reader told the run fails goes and looks,
  so a wrong prediction there costs a look, not a silence.  Docstrings and
  comments stay exempt because they quote history on purpose.  No test checks
  that a promise about *another* command's output (as opposed to its exit code)
  is true.

- [x] **A quote that exists only inside a `<script>` was verified.**
  *What was wrong*: the HTML reader removed a `<script>`/`<style>` body only
  when the end tag was spelled exactly `</script>`.  HTML also allows
  `</script >` and `</script\n>`, so a formatter writing either spelling left
  the whole body in the page text — and a sentence living only in JavaScript
  came back `[info] quote-found`, `1 claim - 1 verified`, exit 0.  A truncated
  `<script>` and an unterminated `<!--` matched nothing at all, so everything
  after them was read as prose.
  *Who is blocked*: every reader of the report.  This is a false positive on the
  one axis the tool exists to police, so it is worse than a missed quote -
  `quote-missing` sends an author to look, `quote-found` sends them away.
  *Done when*: no region the format marks as unrendered can reach the page text,
  whatever spelling the producer used.
  *Done — why it is now true*: `sources._without_unrendered` walks the document
  instead of matching one regex, accepts any whitespace before the end tag's
  `>`, treats an unterminated region as running to the end of the file (which is
  what a browser does with a raw-text element), and refuses `<!--` the same way.
  `tests/test_unrendered_regions.py` (15 tests) asserts both levels: the helper,
  and the verdict a real project gets.  Five mutations are red — the exact
  end-tag spelling, an unterminated region stopping at its opener, comments
  dropped from the region list, an unterminated comment stopping at its opener,
  and `style` removed from the list.  Shipped in v0.20.1.
  *Not covered*: `<svg><title>` is still kept, because an SVG may carry real
  `<text>` and the title is not the only place its words can live.  The three
  genuinely inert elements — `<template>`, `<textarea>`, `<iframe>` — were
  added in v0.21.1; see the entry below.  `<noscript>` stays on purpose and is
  now asserted to stay.

- [x] **An empty `.txt` was told to run OCR on it.**
  *What was wrong*: `source-no-text` was written for a scanned PDF and its one
  message ended with `ocrmypdf <file> out.pdf`.  The same function answers for
  every format, so an empty `empty.txt`, a whitespace-only `blank.md`,
  `<article/>` and `<html><body></body></html>` all received that sentence:
  `found no text at all in empty.txt (1 page(s)); a scan has no text layer, and
  OCR is what turns one into a file that can be searched (for example
  `ocrmypdf empty.txt out.pdf`)`.  None of that advice can work — a text file
  has no text layer, and OCR does not untag a document.
  *Who is blocked*: anyone who points a claim at a source that happens to be
  empty or marker-only.  The verdict is right (there is no text) and the next
  step is wrong, so they run a command that cannot help and conclude the tool is
  confused.
  *Done when*: the advice is chosen from the input the reader actually has, and
  each format reaches its own reason on both the extraction and the cache-hit
  path.
  *Done — why it is now true*: `sources._no_text_problem` takes the suffix and
  builds three sentences — markup whose words are all inside tags, a text file
  that is empty or whitespace-only, and the original OCR sentence for a PDF.
  Both call sites pass it.  `tests/test_no_text_advice.py` (9 tests) asserts per
  format that it reaches *its own* branch: asserting only "not OCR" was not
  enough, because the markup sentence has no OCR either, and the first mutation
  draft survived on exactly that.  Five mutations are red — everything OCR,
  suffix dropped from the cache-hit path, suffix dropped from the extraction
  path, a text file given the markup sentence, and the file name removed from
  the OCR advice.  Shipped in v0.20.2.
  *Not covered*: the markup branch says "inside a tag, a script, a style sheet
  or a comment" without naming which one it found, so a reader with a
  JavaScript-only page still has to look.  Naming it would mean the walker
  returning a reason rather than a string, which is a wider change than this.

- [x] **`doctor` reported every check as ok on a project whose sources it had never opened.**
  *What was wrong*: the eight checks asked about the bookkeeping - is there a
  manifest, is the key bound, does the file exist - and none of them asked
  whether the tool can read anything in the file.  Measured on three projects
  where `check` on the same tree exited 1: a truncated `%PDF-1.4` file (the
  check said `[ok  ] sources`, `check` said `[high] source-unreadable`), a scan
  with no text layer (`[high] source-no-text`), and a zip renamed `.docx`
  (`[medium] source-not-text`).  `doctor` printed `8 checks, all ok` and exited
  0 on all three.
  *Who is blocked*: anyone who runs `doctor` instead of the command that fails -
  which is the only reason the command exists.  A green answer to a question it
  never asked is the one lie a diagnostic cannot afford.
  *Done when*: a project whose sources cannot be read gets a failing line from
  `doctor`, naming the file and the step that fixes it, and a project whose
  sources are readable still exits 0.
  *Done — why it is now true*: `doctor._extraction` reads every source a claim
  names through the same cache the real run uses, and reports the first three
  failures with the advice the extractor already produces for each format plus
  a count of the rest, so a truncated PDF is told to be re-downloaded and a
  scan is told about `ocrmypdf`.  It stands aside with `ok=True` when an earlier
  check owns the failure (an unbound key, an unparseable manifest, an unreadable
  manuscript) and skips `source-missing`, which can only be the race between
  reading the table and reading the file.  `tests/test_doctor_extraction.py`
  (19 tests) asserts the verdict, the standing-aside branches built by stubbing
  the extractor, the advice, the truncation count, and - by counting extractor
  calls - that the second run reads the cache.  Six mutations are red: the
  `source-missing` skip, `use_cache=True`, the truncation, the unbound-key
  stand-aside, and both halves of the closing sentence.  Shipped in v0.21.0.
  *Not covered*: the check opens every source the claims name, so a cold cache
  costs about 23 seconds on the 100-paper corpus.  That is once per cache, but
  it is the most expensive thing `doctor` now does and no test asserts any
  bound on it.

- [x] **A quote that lives only inside `<template>`, `<textarea>` or `<iframe>` came back verified.** *Done 2026-11-03.*
  *What was wrong*: `sources._strip_markup` removed `<script>`, `<style>` and
  comment bodies and called that the set of regions no reader sees.  Three
  more elements are never painted as words: `<template>` content is inert by
  specification, `<textarea>` content is a form value, and `<iframe>` content is
  fallback text for browsers that cannot show the frame.  All three reached the
  page text, so a sentence that exists only inside an inert template was
  matched and reported as `[info] quote-found`.  Measured on a two-claim
  project whose only HTML source held one sentence in a `<template>` and one in
  a `<textarea>`: `citevouch check` printed two `quote-found` lines,
  `2 claims — 2 verified, 0 moved, 0 missing`, `worst severity: info`, **exit
  0** — a verified claim about words nobody can see on that page.
  *Who is blocked*: anyone citing a web source built with a template engine, a
  documentation site, or a widget library that ships text in `<template>` tags.
  They get told their quote is on the page when it is in the markup only, which
  is the one failure this tool cannot apologise for: `quote-missing` sends an
  author to look, `quote-found` sends them away.
  *Done when*: no element the format marks as inert can reach the page text,
  and the elements deliberately left in are asserted to stay in.
  *Done — why it is now true*: `sources._UNRENDERED_TAGS` is the single list
  (`script`, `style`, `template`, `textarea`, `iframe`), and both the opener
  pattern and the `_CLOSED` map are built from it, so the next name is a
  one-line change.  `tests/test_unrendered_regions.py` gained
  `TestElementsWhoseContentIsNotProse` (body dropped, attributes dropped,
  unterminated element swallows the rest), `TestTheVerdictOnAnInertElement`
  (a quote only in a `<template>` → exit 1, only in a `<textarea>` → exit 1,
  prose beside the element → exit 0) and `TestWhatWasDeliberatelyLeftAlone`
  (`<noscript>` and `<svg><text>` still read).  Eight mutations are red —
  the list back to two names, each of the three new names removed in turn,
  `noscript` added, `svg` added, the opener pattern hard-coded, the closer map
  hard-coded — `survivors: none`.  Shipped in v0.21.1.
  *Not covered*: `<svg><title>` is still kept (an SVG may carry real `<text>`),
  and nothing asserts it either way.  `<noscript>` and `<svg>` are asserted to
  stay, which is the opposite decision, not a gap.

- [x] **A quote printed inside a CDATA section was reported missing.** *Done 2026-11-03.*
  *What was wrong*: `<![CDATA[ ... ]]>` means "nothing in here is markup", and a
  feed, a JATS article and an OAI-PMH record all deliver prose inside one.
  `_TAG` matched the entire section as a single tag - `<` followed by `!` is
  exactly what a doctype looks like - so the section was replaced with a space
  and its delimiters took its place on the page.  Measured: a source reading
  `We collected <![CDATA[9,800]]> rolesets.` extracted as
  `We collected rolesets.`, and the claim quoting that sentence came back
  `[high] quote-missing at manuscript.md:3 (c1): We collected 9,800 rolesets. —
  quote not found (too short for a fuzzy comparison) in paper.xml`.
  *Who is blocked*: anyone citing an XML source - a preprint server's JATS
  deposit, an Atom feed, an institutional repository's OAI-PMH record.  They are
  told their quote is not in a file that prints it, and the sentence names the
  file, so the natural conclusion is that they copied it wrong.
  *Done when*: the words inside a CDATA section reach the page text, and the
  delimiters do not.
  *Done — why it is now true*: `sources._without_cdata` unwraps every section
  before tag removal, keeps the text of an unterminated one (a truncated save
  should lose the delimiters, not the document), and `_strip_markup` strips the
  unwrapped body again so an Atom `type="html"` fragment does not hand `<p>` to
  the page.  `tests/test_cdata.py` (13 tests) asserts the helper and the
  verdict: a quote inside CDATA verifies (exit 0), a quote not in the file is
  still missing (exit 1), a number and several sections survive, `a < b` inside
  CDATA stays text, and a document with no CDATA is untouched.  Six mutations
  are red - the unwrapper not called, the body thrown away, an unterminated
  section losing its words, the terminator not required, the delimiters kept,
  only the first section unwrapped - `survivors: none`.  Shipped in v0.21.2.
  *Not covered*: no real Atom or JATS file from the author's own corpus; the
  fixtures are hand-written from the format specifications.

- [x] **A claim block the parser refused vanished from the pull-request check.**
  *Done 2026-11-03.*
  *What was wrong*: the ledger records the claims the parser accepted, so a
  block it refused - no `id=`, an id used twice, a fence never closed - has no
  row in it.  `verify` and `check --use-recorded` walk the ledger, so on a
  manuscript holding one good claim and a second block missing its `id=` they
  printed `[info] quote-found` and `1 claim - 1 verified` and exited 0, while
  `scan` on the same tree exited 1 with `[high] claim-uncheckable at
  manuscript.md:9`.  Measured on all three shapes (no-id, duplicate, unclosed).
  *Who is blocked*: every contributor.  `action.yml` runs
  `check --use-recorded`, so the check a pull request shows is the recorded one.
  Pasting a second claim block and forgetting its `id=` produced a green tick,
  and the command that would have said otherwise is the one the job never runs.
  *Done when*: the recorded verbs report what the parser refused, on the same
  tree where `scan` reports it.
  *Done - why it is now true*: `verify` re-parses the manuscript when the
  ledger's digest proves it describes this exact text (`check_manuscript_hash`
  and `ledger.manuscript_sha256`), and adds the parser's findings; the
  empty-ledger branch reuses that parse instead of repeating it.  With
  `--allow-stale` nothing is re-parsed, because a finding about a paragraph the
  ledger never recorded would be a verdict about a document this run has not
  read.  `tests/test_recorded_parse.py` (9 tests) covers the three refused
  shapes, agreement between the two recorded verbs, two refusals named
  individually, a clean project staying green, the live `check` not saying it
  twice, and the `--allow-stale` silence.  Six mutations are red - findings
  never added, parse only for an empty ledger, parse despite a stale ledger,
  parse on the digest alone, only the first refusal reported, parser asked
  about an empty text - `survivors: none`.  Shipped in v0.21.3.
  *Not covered*: the `unclosed` shape changes its *reason* between paths -
  `scan` says `claim-block-unclosed`, the recorded path says `quote-missing`
  with the swallowed tail as the quote.  Both exit 1, so no green build hides
  it, but the two messages name different problems.

- [x] **Two claim blocks that share one closing fence are read as one block.**
  With the first block's closer missing, the body scan ran from the first
  opener to the *second* block's closer, so the second opener and its quote
  became the first block's quote.
  *Who is blocked*: anyone who pastes a second claim block above an existing
  one and forgets the first closer. The second claim stops existing - and it
  is absent from the report *and* from the ledger, so no later command can
  find it again.
  *Done when*: both blocks are claims, the missing fence is reported at the
  line where the second fence begins, and `scan` no longer exits 0 on the
  shape below.
  **Done — why it is now true:** measured on a two-block manuscript whose
  sentences are both on page 1, before the fix: `scan` exited **0** and wrote
  a ledger holding `['c1']`, while `check` exited 1 with
  `[high] quote-missing at manuscript.md:3 (c1): "…sentences ```claim id=c2
  sourc… — quote not in paper.txt"` - a quote the author never wrote. After:
  the scan stops at a nested opener, both ids reach the ledger, the first
  block is reported as `claim-block-unclosed` naming `line 4`, and the quote
  carries no fence line. Proved by `tests/test_nested_fence.py` (8); five
  mutations, all red: nested opener treated as body text, the nested opener
  not reported, the resume line not moved, the split block marked closed, the
  nested line number dropped from the message.
  *Not covered*: a claim block indented inside a markdown list item or a
  blockquote is still silently skipped (no finding, no claim) - same family,
  different round.


- [x] **Three citation commands nobody could see.**

  **What was wrong.** Natbib's capitalised forms (`\Citet`, `\Citep`,
  `\Citeauthor`, `\Citeyear`, `\Citealp`, `\Citealt`, `\Citeyearpar`) were on neither
  reader's name list. They open a sentence, so they are the first
  citation anyone reading the paper meets. `\Citet{knuth1984}` reached the
  page as the bare word `knuth1984`, and `draft` printed `0 claim block(s)
  proposed: no citations were found to propose them for`.
  A space or a tab between the command and its brace is legal TeX and is
  what a reflowed line produces; `\citep[p.~3] {knuth1984}` gave no site
  either, and `to_text` left `[p. 3] knuth1984` as prose.
  `draft.py` retyped the name list instead of importing it, and its copy
  had already lost `citeyearpar`: `\citeyearpar{k}` became `[@k]` in the
  text `draft` was reading and `draft` still said there were no
  citations. `Prior work \citep{a} and \citeyearpar{b} agrees.` gave
  `sites=['a']` and a proposed sentence still carrying raw LaTeX.

  **Who was blocked.** Anybody whose draft arrived half-converted from
  LaTeX and who cited with a capitalised command - which is what natbib
  users write at the start of a sentence.

  **Done when.** Both readers reach a site for every name on the table,
  for a space and a tab before the brace, and agree with each other.

  **Done - why it is now true.** `src/citevouch/latex.py` exports
  `CITATION_NAMES`, `MULTI_CITATION_NAMES` and `_GAP`; `_CITE`,
  `_MULTI_CITE`, `_MULTI_ARGUMENT` and `draft.py`'s `_LATEX`,
  `_LATEX_MULTI`, `_LATEX_ARGUMENT` are all built from them, so a third
  copy cannot drift. `tests/test_citation_names.py` pins each name
  against both readers, the space/tab cases, the deliberate newline
  exclusion, `\mycites{a}{b}` staying unrecognised, the two tables' contents, and two
  end-to-end `draft` runs. Six mutations, all red: deleting the
  capitalised entries, `_GAP` narrowed to nothing, `_GAP` widened to
  include newlines, `_GAP` shrunk to one space, and each of `draft`'s
  two patterns replaced by a hand-typed shorter list. One false red was
  caught on the way: mutating by deleting the set literal left `| ,`
  behind, so the suite failed on a `TypeError` instead of an assertion;
  the mutant was rewritten to substitute a name nobody writes.

  *Not covered*: a citation split across a line break inside the brace
  group (`{knuth
1984}`) is still not a citation, and nothing
  here changes that.

- [x] **The format gate quoted a file count it had never measured.** `tools/format_check.sh` counted every tracked `*.py`, `*.md` and `*.toml` and handed the same three extensions to `ruff format --check`; ruff has no TOML formatter, so it declined those files and printed `2 files already formatted` where the script counted 3. The lint job caught it on commit `3eb0c17`: `says 147 formatted files, ruff reports 146`. The same script accepted silence: a tree whose only tracked file was a `*.toml` printed nothing and exited **0**. **Who was blocked:** every commit message in this repository quotes that count, so the quote was wrong for anyone who tried to reproduce it, and the gate could report success having judged nothing. **Done when:** the count and the judged set are the same set, and both silence and disagreement stop the commit. **Done — why it is now true:** the extension list is `*.py`/`*.md` in both places, the green path refuses an absent summary line (`ruff reported no summary line, so it judged nothing; N file(s) were handed to it`, exit 2) and a summary that disagrees with the count (`ruff judged N of the M file(s) handed to it; the count cannot be quoted`, exit 2). `tests/test_format_check.py` went from 6 to 11 tests. Six mutations against the script went 6/6 RED with no survivors. That sentence then failed on the two macOS runners only, because BSD `wc -l` pads its answer to a fixed width - so `count` is piped through `tr -d ' '` and a test reads the script for it, since a Linux run cannot see the padding and a macOS run cannot see its absence. **Not covered:** the gap had been written down in the test file as `declined = 2` with a comment naming the two TOML files, which is a specification of the defect rather than a guard against it; nothing yet checks that a *future* extension added to the count is also one ruff accepts, beyond this same test failing.
- [x] **A file whose only claim blocks were wrapped said it had none.**
  Today's fix (`claim-block-unread`) covered the case of a good block plus a
  wrapped one. The zero-claim path was still using `_CLAIMISH`, whose `^\s*`
  cannot cross a `>` or a `- `, so a file holding *only* blockquoted, listed or
  indented claim blocks matched nothing and the finding said, over a file whose
  first line was the block:

  > a claim block opens with three backticks, the word `claim`, then `id=` and
  > `source=`. This file has none.

  Measured on three files, one per dialect, each holding exactly one wrapped
  block: all three said it, all three with `line 0`. The same branch also called
  every indented block a fence, so an indented `<!-- claim` line was told that
  "an indented fence is a code sample in Markdown".

  Done when: the zero-claim message names the wrapped blocks, says which dialect
  each was written in, counts them, and carries the line the reader can open.

  Done — why it is now true: the finding is built from `_unread_opener` and
  `_UNREAD_REASON`, the parser's own table, and the indent branch takes its noun
  from the match. Seven mutations, all red: the branch never fires, the generic
  sentence wins, every dialect described as a fence, the count always one, the
  indent sentence always says fence, the other blocks never counted, and the
  finding carries no line.

  *Not covered*: a table row whose cells wrap across a line break is still
  missed - the row pattern is line-based, like the parser's. And `_CONTAINER`
  has never been compared against a real CommonMark renderer; the fixtures are
  hand-written from the rule.

- [x] **A pipe written the only correct way inside a table cell was read as a cell
  boundary, and an empty cell was read as no block at all.**

  *What was wrong.* GFM defines exactly one escape inside a table cell: a backslash
  before the pipe. The table dialect matched each column with `[^|]+?`, which stops at
  any pipe, so an author who escaped correctly had their quote cut at the backslash and
  the rest of it installed as the `text` column. Measured on
  `| c1 | paper | 1 | a\|b | t |`: quote `a\`, text `b`. The same row
  with a bare pipe - the spelling Markdown says is wrong - gave quote `a`, text `b`, so
  the correct spelling was the one that lost data. End to end on a page carrying a
  literal pipe, the correctly escaped quote came back
  `[high] quote-fuzzy ... similarity 1.00` and exited 1.

  The same pattern required at least one character per cell, so a row with a blank
  column matched no dialect: `| c1 | paper | 1 || short |` and `| c1 | paper | 1 | q ||`
  were reported as `[high] no-claim-blocks ... This file has none`, over a file that
  had one - the same false sentence v0.22.8 removed from a different path.

  *Who was blocked.* Anyone whose source page or quote contains a pipe: a table of
  statistics, a regular-expression example, a piece of shell, a phonology
  representation. Writing it correctly was the way to lose text.

  *Done when.* An escaped pipe reaches the claim as a pipe, in all three columns; an
  empty quote or source is named by `claim-uncheckable` rather than by
  `no-claim-blocks`; and the commands report a green run for a project whose only
  table row has an empty `text` column.

  *Done - why it is now true.* `_CELL = r"(?:[^|\\]|\\.)*?"`
  matches one ordinary character or one backslash-plus-anything, for every column, and
  `_unescape_pipe` undoes `\|` and nothing else - every other backslash stays
  as written. `tests/test_table_cell_escapes.py` holds 20 tests over the parser and
  both commands. Seven mutations applied, seven RED, `survivors: []`,
  `broken mutants: []`: the cell ending on an escaped pipe, each column skipping
  `_unescape_pipe` in turn, every backslash stripped instead of just the pipe, the
  empty cell refused again, and only the first escape undone. The source-column
  mutation survived the first pass, which is why
  `test_the_source_cell_is_unescaped_too` exists.

  *Not covered.* A backslash before anything other than a pipe is left as written
  deliberately (a Windows path in a quote must survive); no real Markdown renderer was
  consulted about whether it accepts such an escape, because the fixture is written
  from the GFM spec. A blockquoted table row is still handled by the wrapped-block
  path, not by the table path.

- [x] **A space between a command and its argument sent the argument into the prose.**
  `\\input {sec/intro}` was recognised as an include (the name pattern
  carries `\\s*`) but its argument was consumed by a function that
  skipped only `*` and `[..]`, so the brace group fell through to the branch
  that keeps text. Measured across the six argument tables against the 104
  command names whose arguments must not reach the prose: **85 of them**
  pasted the argument into the sentence when one space stood between.
  `\\input {sec/intro}` became `... examples. sec/intro The end.`,
  `\\textcolor {blue}{blue}` became `blueblue`,
  `\\setcounter {page}{3}` left `page` and `3` in the sentence, and
  `\\footnote {note}` put `note}` in the body.
  *Who was blocked:* anyone writing LaTeX the way the manual writes it - the
  spaced spelling is at least as common as the touching one, and a reader
  whose citations live in `\\input {sec/method}` had them all
  reported missing with a file path quoted as if it were prose.
  *Done when:* every command in those tables consumes its argument under
  either spelling, the switch form still keeps its separating space, and
  `included_files` still names the files. *Done - why it is now true:*
  `_skip_optional_args` holds whitespace pending and spends it only when a
  brace group follows, so `*` and `[..]` (arguments in their own right) keep
  priority. 22 tests in `tests/test_space_before_brace.py`, six mutations, none
  survived. Released as 0.22.10.
  *Not covered:* `\\begin{comment}` was not re-probed for the same
  gap, and no test distinguishes a newline from a space before a brace group
  (both are treated as whitespace, which is what TeX does).
- [x] **The two branches of `\ifthenelse` formed words that are in neither branch.**
  *What was wrong.* `\ifthenelse{test}{yes}{no}` cannot be decided here and both
  branches are the author's text, so the converter keeps both - but it kept
  them touching.
  ```text
  A. \ifthenelse{1=2}{We report five}{We report these} results.
  ```
  came out as `A. We report fiveWe report these results.`. `fiveWe` is a token
  in neither branch, and it is in the sentence `draft` offers the author to
  paste into a claim block. Two citation branches came out as `[@no][@yes]`.
  *Who was blocked.* Anyone drafting from a paper that uses `ifthen
  conditions to build a sentence: the proposal they were shown contained a
  word the paper never prints.
  *Done when.* The branches are separated by one space and no token spans
  the join.
  *Done - why it is now true.* `latex._convert` appends a space before the
  second branch. `tests/test_ifthenelse_branches.py` (8 tests) pins the
  converted sentence, the two-citation case and the `statement_of` the
  author is shown; five mutations were applied and all five went RED
  (flush again, a newline, a comma, a non-breaking space, a loop that stops
  after one branch).
  *Not covered.* An empty branch (`\ifthenelse{1=2}{}{B}`) is not
  covered: the space would then sit against whatever follows the command.
  No real `ifthen` package document was converted; the fixtures are
  hand-written from the documented syntax. A leading space on the first
  branch is unobservable because `to_text` collapses runs of spaces,
  so that mutation is equivalent and was dropped rather than papered over.
### Fixed: a starred definition deleted the rest of the document

- [x] **A starred definition ate the file, and the xparse commands left their
  macro body in the prose.**

  *What was wrong.*

  `_definition_end` translated "the group I expected was not here" into
  `len(text)`. One character was enough to trigger it: `\newcommand*{...}` puts
  a `*` where a brace was expected, `_group_end` answers `-1`, and the
  definition consumed everything after it. Measured on
  `A. \newcommand*{\x}{y} The grammar is large.` the converted text was `A.` — 32
  characters gone, no finding. Six spellings take the star
  (`newcommand`, `renewcommand`, `providecommand`, `DeclareRobustCommand`,
  `newenvironment`, `renewenvironment`). Separately, the four xparse
  `...DocumentCommand` names take three groups (name, argument
  specification, body) and the generic path consumed two, so
  `\NewDocumentCommand{\seecite}{m}{see \citep{#1}}` put `see [@#1]` into the prose and made `draft`
  report a citation to the key `#1` — a source the paper never cites,
  handed to the author to paste into a claim block.

  *Who was blocked.* Any author whose preamble uses the starred spelling,
  which is what `\newcommand*` exists for; and any xparse user, because the invented
  `#1` citation is the one output that could be pasted into a paper.

  *Done when.* The star is skipped, the four xparse names are a separate
  shape, and a definition that cannot be read to its end stops where it
  started reading.

  *Done — why it is now true.* `tests/test_definition_star_and_xparse.py`
  (38 tests) covers the six starred spellings, the four xparse names with
  and without a body group, the etoolbox `...x` spellings staying on the
  generic path (a trailing group after one is kept, after an xparse
  definition it is the body), and four unreadable shapes asserting the
  tail of the document survives. Six mutations, all red: star not skipped,
  space after the star not skipped, xparse on the generic path, xparse body
  left in the prose, etoolbox swept into the xparse set, unreadable
  definition swallowing the rest.

  *Not covered.* No real `.tex` file that defines commands through a
  package; whether any xparse command takes more than three mandatory
  groups.
- [x] **A misspelt field name in a claim body either switched a check off in
  silence or accused the author of quoting a page their source never printed.**
  *Done 2026-11-04.*
  *What was wrong.* `_split_body` recognises a fixed set of body keys
  (`quote`, `claim`, `numbers`, `id`, `source`, `ref`, `cite`, `page`,
  `marker`). A left-margin line shaped like a field but naming anything else
  had no branch of its own, so the branch after it took it — and which branch
  that was depended on where the line sat. Measured on one project whose quote
  really is on page 2, with the page hint misspelt:

  - `Page: 1` above `quote:` — the hint was dropped, the claim was located by
    search, and the run printed `[info] quote-found` and **exited 0**. Writing
    `page: 1` on the same project prints `[medium] quote-moved … the quote is
    on page 2, the ledger says 1`. A typo in a field name turned a check off,
    and no finding anywhere said so.
  - `Page: 1` below `quote:` — the line joined the quote, the passage searched
    for ended in `Page: 1`, and the run printed `[high] quote-missing … The
    resulting grammar consists of a network of 40,688 constructions. Page: 1 —
    quote not found in page.txt` and **exited 1**: the tool's most serious
    sentence, printed because the author capitalised a key.

  *Who was blocked.* Anyone who typed an attribute with a capital letter, a
  plural or a missing colon — which is every author, once. The first shape is
  the dangerous one: it makes a project look clean while one of its checks is
  not running.
  *Done when.* Both paths say the same thing, the line number reported is the
  line the editor shows, the key is named, and the line stays out of the quote.
  *Done — why it is now true.* New `_KEYISH` matches the shape
  (`^\s*[A-Za-z][A-Za-z0-9_-]*\s*:`) rather than a list of known names;
  `_split_body` returns a fourth value listing `(offset, key)`, and
  `_unknown_field_findings` turns each into `claim-field-unknown` (medium)
  carrying `line = start_line + offset`. Both dialects call it. Indented lines
  are still continuation text (`not raw[:1].isspace()`), and a correctly spelt
  key is still silent. Severity is medium because the quote is still located
  and compared — the loss is a hint that was never applied, the same loss as
  `page-unreadable`. `tests/test_unknown_fields.py` has 20 tests; the
  end-to-end ones assert the absence of `quote-missing` and that `--fail-on
  medium` still turns the run red. Six mutations, `survivors: []`.
  *Not covered.* `_KEYISH` accepts only an ASCII name, so a misspelt key in a
  non-Latin script is still treated as prose. That is deliberate — every real
  key is ASCII, and widening the pattern would make ordinary sentences that
  contain a colon start being reported — but it is a shape the code cannot
  see, not a shape it handles.

- [x] **A recovered release stayed a draft while every step reported success.**

  *What was wrong.* `gh release create` attaches assets by creating a *draft*
  release, uploading to it, and then publishing it — three API calls behind one
  command. v0.22.14 died between the first and the third: the create call
  answered `HTTP 502: Server Error` and the draft existed anyway. The
  `Re-attach artefacts if the release already existed` step asks only
  `gh release view "$tag"`, which answers "yes" for a draft. It uploaded the
  wheel and the sdist, exited zero, and the run was green — with a release
  nobody could see. A reader of a red run knows something is wrong; a reader of
  a green run does not, which makes this strictly worse than failing. It was
  published by hand minutes later, which is the human step this project exists
  to not need.

  *Who was blocked.* Anyone who found the repository through the release feed:
  the version was tagged, the artefacts existed, and the release page did not.

  *Done when.* A recovery that finds a draft publishes it, and a run whose last
  API read still says "draft" fails.

  *Done — why it is now true.* The recovery step reads `isDraft` from the API,
  calls `gh release edit "$tag" --draft=false` when it is true, and then reads
  `isDraft` again and exits 1 if it is still true. The assets are attached
  before the publish, so a failure leaves a draft rather than an empty published
  release. `tests/test_release_recovery.py` (7 tests) runs the real shell body
  of the step against a `gh` stub whose *existence* and *draftness* are
  separate state; five mutations are red (`survivors: []`).

  *Not covered / observed later.* The fix was proven end to end by accident:
  the next release's create call also answered 502, and the follow-up run
  entered the recovery with a published release and printed
  `release v0.22.15 is published` — the "already published" path, not the
  "publish the draft" path, which no live run has yet taken. And the underlying
  cause of the 502/500s from `api.github.com/repos/.../releases` is GitHub's,
  not this repository's: four separate calls in ten minutes answered 500 or 502
  and `gh workflow run` failed the same way twice, so a retry is now part of the
  documented recovery rather than a surprise.

- [x] **An upgraded build accused a verbatim quote of a number the page does
  not contain, because the ledger it read was written by the older build.**

  *What was wrong.* 0.22.16 made `40 688` (grouping space) one number instead
  of two, and started recording `Claim.numbers` that way. A ledger committed by
  any earlier build still holds `["40", "688"]`, and `Ledger.from_json` read
  that list as fact. Verifying such a ledger compared the two stale tokens with
  a page the new build reads as `40688` and reported

      [high] number-absent-in-quote ... the quote says 40 and 688 but page 1
      of the source does not contain those numbers

  against a quote that is character for character the page. `action.yml` runs
  `check --use-recorded`, so every repository that upgraded got that verdict on
  its next pull request — the tool's own formatting change, reported as the
  author's error. The 0.22.16 CHANGELOG said to re-run `scan`; a note telling
  the user to re-run something is not a repair when the upgrade is what broke
  them.

  *Who was blocked.* Anyone who upgraded and kept the ledger they had committed
  — which is the documented workflow, because the ledger is meant to be the
  record CI reads.

  *Done when.* The verifier reaches the same verdict about the same quote
  whether the ledger was written by 0.22.15 or 0.22.17, and a genuinely
  re-typed number is still caught.

  *Done — why it is now true.* `Claim.numbers` is derived data: `textnorm.quote_numbers`
  is its only producer and the quote it describes is in the same JSON object,
  so a stored copy can only be older than its source. `Ledger.from_json` now
  re-derives the tuple with `quote_numbers(quote)` and uses the stored list
  only as a shape assertion. Measured before the change: `check --use-recorded`
  on the old shape printed the `[high]` line above and exited 1; after it,
  exits 0 with `quote-found`; `tests/test_old_ledger_numbers.py` (12 tests) pins
  both directions, and six mutations — restoring the trust, deleting the shape
  check, reading quote numbers with `REPORT_PATTERN`, returning nothing from the
  producer, dropping the producer from the writer, and ungrouping the space —
  are all red.

  *Not covered.* A ledger written by a build older than 0.22.16 is reproduced by
  rewriting the field in a fresh `scan` output rather than by checking out the
  old release and running it; the JSON shape is the same but the reproduction
  is a reconstruction. A shape no writer ever produced (`numbers: 5`,
  `numbers: [1]`) still refuses to load.

- [x] **`bib-key-missing` handed the author a bibliography key they never wrote.**
  *Done 2026-11-04.*

  *What was wrong.* A claim writing `source=paper` and no `ref=` was looked up
  under `paper` - the name of its PDF - and the finding said `claim c1 cites
  'paper', which is not in the bibliography the ledger recorded`. Measured on a
  project whose `refs.bib` holds `knuth2020` and whose claim writes only
  `source=paper`: all three verbs (`check --bib`, `verify`,
  `check --use-recorded`) printed that sentence, `[high]`, exit 1.

  *Who was blocked.* Anyone who keeps a bibliography and lets `source=` name
  the PDF. The verdict is correct (a bibliography is present and the claim
  names nothing in it), but the sentence sends them to `refs.bib` to add a file
  name, when the one-line fix is `ref=<key>`.

  *Done when.* The message says which namespace was actually used, and the
  fallback keeps working for a project that names its PDF and its entry the
  same way.

  *Done — why it is now true.* The lookup is unchanged (`ref` when written,
  `source` otherwise) and the message branches: with a `ref=`, `cites
  'phantom'` as before; without one, `names no ref=, so it was looked up as
  'paper' - the name of its source file - ... Write ref=<key>`. Severity is
  still `high`. `tests/test_bib_key_namespace.py` (7 tests) pins both halves in
  one file, and five mutations are red: the fallback branch speaking in the
  `ref` voice, the advice losing the attribute name, the sentence dropping the
  name it looked up, an empty `ref` counting as written, and the fallback
  removed. Both README code tables updated.

  *Not covered.* A bibliography whose entry keys collide with a source key
  belonging to a *different* paper - nothing in the corpus has that shape, and
  the fallback would silently attribute the entry to the wrong claim.

- [x] **Two spellings of one attribute, both written, and neither said so.**
  *Done 2026-11-04.*

  *What was wrong.* `ref=` and `cite=` name the same bibliography entry; the
  lookup reads `ref` and falls back to `cite`.  Writing both with different
  values was silent in both directions, and the directions were different
  defects.  Measured with `refs.bib` holding `knuth2020` and a quote verbatim
  on page 1:

  ```
  ref=phantom cite=knuth2020   ->  exit 1
      [high] bib-key-missing at m.md:1 (c1): claim c1 cites 'phantom',
      which is not in the bibliography the ledger recorded
  cite=phantom ref=knuth2020   ->  exit 0, no finding at all
  ```

  One direction accused the author on the strength of a value they may have
  meant to delete; the other deleted it without a word.  Both left the
  manuscript saying something no run had applied - the shape the misspelt
  `Page: 1` field had before 0.22.14, one attribute over.

  *Who was blocked.* Anyone who renamed a bibliography key and edited one of
  the two spellings, and anyone reading a green run that had silently dropped
  half of what they wrote.

  *Done when.* Both values are named, the run says which one it used, and
  neither direction is silent.

  *Done - why it is now true.* A disagreeing pair is `claim-field-conflict`
  (medium): the quote is still verified, but the finding names both values and
  says which was used and which was dropped.  The lookup order is unchanged,
  so nothing that verified stops verifying.
  `tests/test_field_conflict.py` (15 tests) covers the parser and the command;
  six mutations are red, including one that only removed the attribution from
  the sentence and survived the first round.

  *Not covered.* A pair split across the fence and the body is checked after
  the merge, so it is caught; but nothing reads the pair order in the file, and
  a project that writes `ref=` on the fence and a *different* `cite=` in the
  body still gets the fence value with no note about where the other came from.

- [x] **`doctor` reads a source now; a source it still cannot read says so.** *Done 2026-11-04.*

  What was wrong: a source saved in a desktop encoding was decoded with `errors="replace"`, and the replacement characters were far too few for the noise score to notice - GBK gave one, Big5 two, Shift-JIS three, against a threshold of four.  The mojibake was then searched and the author was told `[high] quote-missing ... quote not found in page.txt` about a sentence printed on that page.

  Who was blocked: anyone whose PDF-to-text step or editor wrote GBK, Big5, Shift-JIS or latin-1.  That is most of a Chinese or Japanese corpus, and the verdict blamed their manuscript.

  Done when: a file whose bytes are not decodable text is named as such, once, at high severity, and its quote is never judged.

  Done - why it is now true: `textnorm.invalid_utf8_share` measures the fraction of bytes that fit no UTF-8 sequence (GBK page 0.62, Big5 0.58, Shift-JIS 0.57 against cp1252 French 0.085 and one stray byte 0.024), and `sources.encoding_problem` refuses a text-suffixed source above 0.25, above the cache, before any page is built.  `tests/test_source_encoding.py` (16 tests); six mutants, `survivors: []` after two had to be earned - the first round survived "a file that names its own encoding is refused anyway" and "every suffix is judged" because nothing in the suite fed a file that is readable *and* past the line.  The demo PDF scores 0.33 on that scale.

  *Not covered*: a bibliography is deliberately not judged - a GBK `.bib` scores 0.11-0.24, which overlaps the range a cp1252 French page occupies, so no line separates them and the guard would refuse files the author can read.  Also not covered: a mostly-ASCII GBK file stays under the line and keeps the old `quote-missing` verdict; auto-detecting the encoding is out of scope, so the message names `iconv` and the author supplies the encoding.
  *A number that was written from the plan instead of from a run*: the 0.22.20 CHANGELOG entry says `(20 tests)`; `pytest --collect-only -q` reports 16 for that file.  The released section is not edited - the tag is spent and rewriting its notes afterwards would make the notes a claim about today rather than about the release.  Recorded here so the next reader trusts the file over the paragraph.

- [x] **A GBK manuscript lost its claim fences, and the tool said the manuscript was empty.** *Done 2026-11-05.*
  *What was wrong*: `textnorm._decode_text` falls back to UTF-16-LE when the UTF-8 reading looks noisy, and kept whichever reading scored less noise.  A manuscript is mostly ASCII - its fences, its `quote:` keys, its attribute syntax - so a GBK manuscript is noisy as UTF-8 only in proportion to its prose, and the UTF-16 reading scored lower.  The whole file became `'탑뾾쫎...'` and the search found no claim blocks in a manuscript that had them:
  ```
  [high] no-claim-blocks at manuscript.md:2: manuscript.md contains no claim blocks,
  so nothing was checked: a claim block opens with three backticks, the word `claim`,
  then `id=` and `source=`. This file has none.
  ```
  Worse than the behaviour it replaced: plain `raw.decode("utf-8", errors="replace")` kept every fence and turned only the Chinese lines into replacement characters, so the block was there to be found.  A fix written to stop one false accusation introduced a larger one.
  *Who was blocked*: anyone whose editor or export wrote the manuscript in GBK, Big5, Shift-JIS or another 8-bit encoding - the largest desktop encoding family, and the one the tool had no way to name.
  *Done when*: an 8-bit manuscript keeps its fences, a genuine UTF-16 document is still decoded, and neither reading is chosen without evidence about that file.
  *Done - why it is now true*: two conditions now have to hold, and each is a fact about one file family.  The UTF-16 reading must score **zero** noise (byte pairs from a real character cannot decode to a control or replacement character, so all twelve genuine UTF-16-LE shapes measured zero, while 8-bit files read that way scored something in 558 of 600 random samples and in every single one that also held ASCII).  And the noise must be at least **a tenth** of the file (a stray byte in a long UTF-8 paper scores one or two characters; every genuine UTF-16-LE CJK document measured 0.17-0.41).  Neither alone suffices: cp1251 Russian reads cleanly as UTF-16 and is stopped only by the share test, and a short genuine UTF-16 document beats the share test and is stopped only by the zero test.  `tests/test_mojibake_fallback.py` (15 tests) pins both halves from both sides; six mutations ran red - the share test dropped, loosened to a fiftieth, the clean test dropped, loosened to "any improvement", the fallback disabled, forced.
  *Not covered*: a real GBK manuscript from an author's disk (the fixtures are written by the test); an 8-bit manuscript with no ASCII at all remains ambiguous and is reported through `source-encoding` rather than decoded; Windows editors beyond GBK, Big5, Shift-JIS, cp1251 and cp1252 were not measured.

- [x] **Five note commands still glued their words into the sentence that cited them.** *Done 2026-11-05.*
  *What was wrong*: `latex._SEPARATE_ARGUMENT` named exactly `footnote`, `footnotetext` and
  `marginpar`. Everything else in the family stayed inline, so a note written mid-sentence
  ended up in the middle of that sentence:
  ```
  The method works\thanks{We thank the annotators.}, and we show it.
    -> 'The method worksWe thank the annotators., and we show it.'
  The method works\tnotetext{See the appendix.}, and we show it.
    -> 'The method worksSee the appendix., and we show it.'
  ```
  Same for `\marginnote`, `\sidenote`, `\sidenotetext`, `\endnote`, and the starred
  `\thanks*` produced `'The method works*We thank the annotators., ...'` because the star
  was not skipped. `draft` reads sentences out of the converted text, so a proposal built on
  `worksWe` is a claim about a sentence nobody wrote. `\thanks` is the one that matters:
  every funded paper carries one, mid-sentence inside `\author`.
  *Who was blocked*: anyone whose `.tex` uses `\thanks` - which is to say most published
  papers - got a `draft` sentence with the acknowledgement spliced into it.
  *Done when*: every note in the family leaves the sentence alone, the star spelling is
  handled, and the inline wrappers that should stay inline still do.
  *Done - why it is now true*: `_SEPARATE_ARGUMENT` is now
  `{footnote, footnotetext, marginpar, thanks, tnotetext, marginnote, sidenote,
  sidenotetext, endnote}` and its docstring records the measured glue plus the rule - a name
  on the list is a claim that the name is a note, a name missing from it is a claim that the
  words belong to the sentence. `tests/test_latex_more_notes.py` pins both halves from both
  directions: each of the six new names splits the sentence into `The method works, and we
  show it.` with the note kept as `A note.`; `\thanks*` no longer leaves a `*` behind; a
  citation inside any of them still reaches `citation_sites`; `\textbf`, `\emph` and
  `\textsc` still keep their argument in place. Eight mutations ran red - the declaration
  back to three names, one per removed name, the star skip deleted, the branch disabled -
  `survivors: none`.
  *Not covered*: a real thesis `.tex` from an author's disk (fixtures are hand-written from
  the kernel and package documentation); starred spellings other than `\thanks*` were not
  measured for the four package commands.

- [x] **A listing that showed `\input` made `draft` name a file the paper never reads.** *Done 2026-11-05.*
  *What was wrong*: `latex.included_files` reads the raw `.tex` source, and the raw source holds the listing that demonstrates the syntax.  A name written inside a literal environment is an example, and it was reported as an include, so `draft` printed this in the one comment it tells the author to check:
  ```
  <!-- This document pulls text in from chapters/intro, which `citevouch draft`
  does not read: any citation in those files is missing from the blocks below. -->
  ```
  Measured for every literal environment, each of which reported `['ghost/sec']`: `verbatim`, `verbatim*`, `lstlisting`, `minted`, `filecontents`, `comment`.  The inline spelling `\verb|\input{ghost/sec}|` was already right.
  *Who was blocked*: anyone who documents `\input` with a listing - which is how a methods chapter explains its own file layout.  The warning is attached to the proposal `draft` hands them, so the first thing a new user reads about their own paper is false.
  *Done when*: a name shown inside a literal environment is not reported, a name outside one still is, and an unclosed environment does not swallow the rest of the document quietly.
  *Done - why it is now true*: `included_files` starts from `_without_literal_bodies(tex)`, which blanks the body of each of the six environments and leaves the delimiters, so nothing that answers "what does this document read" sees the demonstration.  The set is deliberately **not** `_VERBATIM_ENVIRONMENT`: that one answers "is a `%` here a character" and must omit `comment` (a `%` inside a comment environment starts a real comment), while this one answers "is a command here executed" and must include it.  `alltt`, `tabular` and `tikzpicture` stay outside because TeX executes what is inside them.  `tests/test_literal_environment_includes.py` (24 tests) pins all three directions - inside is not reported, outside still is, and each executed environment still is - plus two end-to-end `draft` runs.  Six mutations ran red, `survivors: none`; the one that first survived (end tag not skipped past) found a real gap in the tests and in the code, and both were fixed rather than re-pinned.
  *Not covered*: a real thesis that uses `lstlisting` or `minted` (fixtures hand-written from the kernel and package documentation); a `\begin{...}` written in the body of another literal environment that happens to spell a different one.

- [x] **A CRLF manuscript drafted differently from the same manuscript in LF.** *Done 2026-11-05.*
  **What was wrong.** `textnorm.read_text` kept the carriage returns Windows
  editors write, and `draft` finds the paragraph around a citation by
  searching for `\n\n`. A CRLF file holds `\r\n\r\n`, so the search found
  nothing and the whole manuscript became one paragraph. Measured on two
  files differing only in how they were saved:

  ```
  LF   claim: |
         We collected 154,391 examples from the corpus, and we evaluated them on 9,800 rolesets.
  CRLF claim: |
         ## Methods We collected 154,391 examples from the corpus, and we evaluated them on 9,800 rolesets.
  ```

  The heading was glued onto the sentence, so `draft` offered a sentence
  nobody wrote for pasting into the manuscript, and its confidence fell
  from `high` to `medium`. A `.tex` input was fine because
  `latex.to_text` rebuilds the text - the asymmetry is what pointed at the
  shared reader rather than at `draft`.
  **Who was blocked.** Anyone on Windows who saved their manuscript in the
  default editor, which writes CRLF.
  **Done when.** `read_text` returns one text for both spellings, and the
  drafts are byte-identical.
  **Done - why it is now true.** `read_text` flattens `\r\n` and lone `\r`
  to `\n` after `_decode_text`; nothing is written back. 14 tests in
  `tests/test_line_endings.py` compare the two spellings' drafts with
  `difflib`, pin the CRLF source page and the CRLF bibliography and the
  LaTeX path, and assert the file on disk is unchanged. 3 tests in
  `tests/test_one_reader.py` walk the package with `ast` and fail if a
  module outside `textnorm` starts decoding bytes: adding a decoder to
  `report.py` by hand turned it red. Five mutants, all red, no survivors:
  keep the carriage returns, drop lone-`\r` handling, replace `\r` before
  the pair, delete the break instead of flattening, write the normalised
  text back.
  *Not covered*: a UTF-16 file with CRLF on disk (the bytes reach the same
  flattening but no test writes one); an editor that produces mixed line
  endings inside one file.

- [x] **A misspelt attribute on a claim fence line was parsed, stored and never read.** *Done 2026-11-05.*
  *What was wrong.* `_attrs` reads every `key=value` token on a claim block's opening line into a dict; `_claim_from` consults six names in it. A seventh token was kept and never read, so the claim ran without it and every line of output was written as though it had run with it. Measured on a project that prints the same sentence on page 1 and on page 3:

  ```
  ```claim id=c1 source=paper page=3 -> quote-found page 3
  ```claim id=c1 source=paper pgae=3 -> quote-found page 1, exit 0, no finding
  ```

  *Who was blocked.* Anyone who typed an attribute on the fence line - the place the format is documented and the place most people write them - and got a verdict computed without it. The body of the same block has refused this since the `Page: 1` fix (`claim-field-unknown`); the fence line had no guard.
  *Done when.* Both places report the same code, one finding per misspelt key, with the severity the format already assigns to it.
  *Done - why it is now true.* `_KNOWN_ATTRIBUTES` is one frozenset that both the fence-line check and the `_ATTRIBUTE_KEY` grammar derive from, so the two spellings of an attribute cannot drift apart again. `_unknown_attr_findings` reports a token only when it is one edit from a known key **and** the right spelling is absent; `_edit_distance` counts a transposition as one edit because `pgae` for `page` is the typo the fingers actually make. `tests/test_opening_line_fields.py` (35 tests) covers both dialects, both edit shapes, the quiet cases (`data-x=`, a near miss beside the right spelling) and the severity contract; seven mutations, all red, `survivors: none`. `README.md`, `README.zh-CN.md` and the SARIF rule text all say the code now covers both places.
  *Not covered.* A misspelling that lands on another real word of the same length is invisible to a distance-of-one rule (`pag=` is two edits from `page`); no corpus of real typos was used to calibrate the threshold. Attribute names are ASCII only, so a CJK spelling of one is a syntax error rather than a near miss.

- [x] **A sentence that only described the credibility notation was reported as an unbound claim.** *Done 2026-11-06.*
  **What was wrong.** `scan_unbound_markers` asked whether a marker's characters
  appeared anywhere in a line and reported the line if they did. The demo's own
  manuscript explains the convention at line 3, and `citevouch scan
  demo/manuscript.md` accused that explanation:

  ```
  [low] claim-without-evidence at manuscript.md:3: the 【原文】 mark on this line has no claim block, so nothing ties it to a page in a local source
  ```

  Line 3 is `> 这份节选保留了原档的【原文】/【实测】/【推测】三级标记约定，只是把` — a
  remark about the notation. The advice the finding earns is "bind a claim block
  to it", which here means annotating a glossary. The two lines that really do
  carry a bare mark (52 and 54) were in the same list, so the output looked right
  and was one third wrong.
  *Who was blocked*: nobody was stopped, which is why this sat for so long. It
  costs trust instead: the first finding a new user meets on their own manuscript
  can be one about their typography.
  *Done when*: a mark that opens its line is reported, a mark mentioned inside
  prose is not, and the demo reports exactly its two real ones.
  *Done - why it is now true*: `scan_unbound_markers` sets aside the Markdown that
  may stand in front of a sentence (`_MARKER_DECORATION`: indentation including
  `\u3000`, `>`, bullets, ordered-list numbers, emphasis) and then asks
  `opening.startswith(marker)`. Measured: `scan demo/manuscript.md` now reports
  lines 52 and 54 only. `tests/test_marker_position.py` (31 tests) covers thirteen
  prefixes, the six documented marks, five ways a line merely mentions the
  notation, and the demo file itself. Six mutants ran red, `survivors: none`.
  Five older fixtures wrote the mark mid-sentence and were moved to the prefix
  form - they test dedup, span coverage and custom names, not position.
  *Not covered*: a mark that trails its sentence is now a **miss**, deliberately
  (silence costs a nudge, a false accusation costs the output). No real
  manuscript that mixes both spellings was measured. The `marker=` claim attribute
  was parsed, stored and never read - fixed in the entry below.

- [x] **A claim block's `marker=` named the mark that vouches for it, and nothing read it.** *Done 2026-11-06.*
  **What was wrong.** `marker=` has been parsed off the opening line since the first commit, kept on `Claim.marker`, written into `citevouch.lock.json`, and read back out of it.  Four places, no reader.  A manuscript that wrote the binding got both halves of the contradiction in one run:

      【原文】PyFCG 3.3 installs cleanly.

      ```claim id=c1 source=a marker=【原文】
      quote: |
        PyFCG 3.3 installs cleanly.
      ```

  Measured: the ledger recorded `marker='【原文】'` for `c1`, and `scan` printed `[low] claim-without-evidence at m.md:1: the 【原文】 mark on this line has no claim block, so nothing ties it to a page in a local source` in the same run.  A second shape measured the same: a block below the mark reported the line under it, and a block whose body held `marker: 【原文】` reported the line after it.  `CHANGELOG.md` for 0.22.14 already listed `marker` among the attributes the body reader knows, so the format promised a binding it never applied.
  **Who was blocked.** Anyone using the project's own credibility notation with a claim block: the tool asked them to attach a block to a mark they had already attached, and the fix it implies (delete the mark, or duplicate it into a block) is the opposite of what the format wants.
  **Done when.** A block that names a mark binds the mark beside it, and a block that does not name one binds nothing.
  *Done - why it is now true*: `scan_unbound_markers` takes the parsed claims and skips a line that `_bound_mark_lines` returns.  A mark is bound only when it heads the *neighbouring* paragraph (via `_paragraph_above` / `_paragraph_below`, which stop at a claim block rather than walking through it) and exactly one block wants it - two marks either side of one block are two readings of one sentence, and picking one would hide the other.  The mark is matched with the same `_MARKER_DECORATION` the scan uses, so `- 【原文】` and `> 【原文】` bind like a bare one.  Measured: the six probe shapes now bind, and the demo still reports exactly lines 52 and 54.  `tests/test_marker_attribute.py` (21 tests) covers the three dialects, decorated marks, the caller's marker list, a mark two blocks both want, and the paragraph search stopping at a block.  Nine mutants ran red, `survivors: none` - the first run left four alive, each because no test exercised one guard, which is what added the `TestTheRulesThatKeepItNarrow` class.
  *Not covered*: the table dialect has five fixed columns and no attribute grammar, so a table row cannot name a mark and a mark beside one stays unbound - honest, and pinned by two tests.  No real manuscript using `marker=` was available, so the neighbour rule rests on constructed shapes; the body spelling (`marker: 【原文】`) binds through the same `Claim.marker` but no test separates the two spellings.

- [x] **The summary line counted the claims the ledger held, not the blocks the manuscript held.** *Done 2026-11-07.*
  **What was wrong.** `citevouch: N claims — V verified, M moved, X missing` was built from `ledger.claims`, and the ledger records only the blocks the parser *accepted*. A block with no `source=` is refused: it produces a `[high] claim-uncheckable` finding and no claim, so it reaches neither `verified` nor `missing` nor `skipped`. On a manuscript holding one accepted claim and one block with no `source=` the run printed:

      [high] claim-uncheckable at manuscript.md:6 (c2): claim c2 names no source=; the quote cannot be looked up
      [info] quote-found at manuscript.md:1 (c1): quote found on page 1
      citevouch: 1 claim — 1 verified, 0 moved, 0 missing
      worst severity: high

  Two blocks were in the file. The run was red, so the exit code hid nothing; the sentence hid how much of the manuscript the numbers described. Measured on four shapes: one refused block alone said `0 claims`, one accepted plus one refused said `1 claim`, two accepted plus one refused said `2 claims` - each one block short.
  **Who was blocked.** Anyone reading the last line instead of the findings - which is what a review, a commit message or a status update quotes. A reviewer skimming the summary of a red CI job learned the manuscript had one claim when it had two, and the second one is the interesting one: it is the block nobody could check.
  **Done when.** The numbers describe the document, not the recording.
  *Done - why it is now true*: `VerifyResult` gained `unrecorded` and a `blocks` property (`checked + unrecorded`), filled by one subtraction in `verify._unrecorded(parsed)` = `len(parsed.claim_spans) - len(parsed.claims)` - every block the parser opened, minus every claim it could record.  (This first used `parsed.spans`, which also holds plain code fences; that was wrong and is the entry above.) One subtraction rather than a counter bumped at each refusal site, because a counter in three places is three chances to forget. An **unclosed fence is deliberately not counted**: it still yields a claim, so it is checked like any other and calling it "not checked" would be false in the other direction (pinned by `test_an_unclosed_fence_is_a_reading_problem_not_a_missing_block`). The live `check` builds its ledger from the text and then verifies with `check_manuscript_hash=False`, so it never re-parsed; `verify()` gained `fresh=True`, which takes the count from a parse of that same text without re-adding the findings `scan` already returned. The line grows a second sentence only when there is a gap: `2 claim blocks — 1 of which this run could not check`. `--format json` gains `summary.blocks` and `summary.unrecorded`; `--format markdown` gains the same clause. `tests/test_tally_counts_blocks.py` (14 tests) covers the text line, both other writers, the quiet cases, the unclosed fence and the demo. Nine mutants ran red, `survivors: none` - the first run left the JSON and Markdown mutants alive, which is what added `TestTheOtherTwoFormatsSayItAsWell`.
  *Not covered*: three writers, one clause - a fourth format would need its own test. A manuscript whose refused block is *also* missing its source produces both `source-missing` and the clause and no test separates the two. The JSON `blocks` field is new, so a consumer that already sums `checked` will see two different totals until it reads the field.

- [x] **A code sample in the manuscript was counted as a claim block the run could not check.** *Done 2026-11-08.*
  **What was wrong.** The clause added by the entry above counted `len(parsed.spans) - len(parsed.claims)`.  `ParseResult.spans` is not the list of claim blocks: it is the list of line ranges the prose scanner must not search, and the `_ANY_FENCE` branch adds every plain code fence to it - on purpose, so that a ` ```python ` sample which happens to contain the word `claim` is not reported as an unread opener.  Counting with it made a sample into a block.  Measured on one real claim plus one Python sample:

      citevouch: 1 claim — 1 verified, 0 moved, 0 missing
      2 claim blocks — 1 of which this run could not check
      worst severity: info

  There was one block.  Two samples made it three.  `citevouch doctor` said the same thing in its own words - `2 claim blocks, 1 of which the parser could read; the next command names the rest` - and no command named anything, because the "unread" block was a sample that was never meant to be read.  A `~~~` fence or a four-backtick `claim` fence counted as a block the same way, and neither is read as a claim either, so those two shapes get no finding at all: the only trace of the author's block was a number that was one too high.
  **Who was blocked.** Anyone whose manuscript shows a fenced example - which is most manuscripts that explain a format.  The failure is quiet: exit 0 on a healthy project, with a sentence claiming a block exists that the tool never opened.
  **Done when.** A sample does not change the block count, and a genuinely refused block still does.
  *Done - why it is now true*: `ParseResult` now carries two lists, each named for the question it answers.  `spans` stays wide (what may not be searched for prose - the reason samples are in it) and `claim_spans` is narrow (what `accept()` opened, in all three dialects).  `verify._unrecorded` and `doctor._claim_blocks` both count `claim_spans`.  Measured after the fix: `claim+sample` prints no clause, `claim+two samples` prints no clause, `claim+tilde` prints no clause, `claim+refused` prints `2 claim blocks — 1 of which this run could not check`, `claim+refused+sample` prints the same `2`, and `doctor` reports `1 claim block` for `claim+sample` again.  `tests/test_code_samples_are_not_blocks.py` (29 tests) covers the two-fence counts, the three dialects, four `doctor` shapes, and one test that protects the wide list's original purpose (a ` ```claim ` written inside a sample must not produce `claim-block-unread`).  Six mutants ran red, `survivors: none`.
  *Not covered*: an unclosed fence is still a claim (checked, not counted as unrecorded) - unchanged and deliberately so.  No real manuscript mixing a claim with a `~~~` sample was measured; those fixtures are hand-written.  `alltt` / `tabular` / `tikzpicture` were not revisited - TeX executes them, so they are still not treated as samples.

- [x] **`tools/format_check.sh` exited 1 on this machine, printing nothing.** *Done 2026-11-08.*
  **What was wrong.** The fourth gate printed no output and failed while the underlying `ruff` command, run by hand on the same file list, printed `170 files already formatted` and exited 0.  Five tests in `tests/test_format_check.py` went red with `AssertionError: (1, '', '')`.  Cause: `[ "$status" -eq 123 ] && status=1` under `set -eu` terminated the script before the summary line was written, in the `sh` that ships with this shell (bash 5.3.20 in `sh` mode).  The same line is green under Git Bash and on the Linux and macOS runners, which is why CI stayed green for months while the local gate could not pass.
  **Who was blocked.** Every local run of the gates - and worse, it trained the habit of not reading the gate's output, because the only output was none.
  **Done when.** The gate prints its count and exits 0 on a formatted tree, under the shell that actually runs it.
  *Done - why it is now true.* The line is now an `if`.  Reverse validation: the `HEAD` version of the script exits 1 with empty stdout and stderr, the new one prints `170 files already formatted` and exits 0.  The bisect that found it is worth recording, because it is not a logic error: the `&&` was only fatal when the comment above it contained a period (`# ends with a period.` fails, `# a,` passes, `# a b` passes, five runs each).  So the trigger was a comment, and no amount of reading the logic would have found it.
  *Not covered*: the same `&&`-as-statement idiom was not swept from the other shell scripts on this machine (`tools/release_notes.sh` was not exercised); only `format_check.sh` is run as a gate here.  The underlying `sh` shim is not ours to fix, so the workaround is in our script, and CI cannot regression-test it - the local run is the only place this can be seen, which is why the entry is here and not in a test.

- [x] **A bad `--ledger` path was described as a problem inside the file.**
  *Done 2026-11-08.*
  *What was wrong.* The four verbs that read a ledger parsed the JSON first and
  judged the path second, so a path that could never hold a ledger came back as
  a parse error. Measured on a project whose ledger flag pointed at a
  directory:

  ```text
  $ citevouch report --ledger adir
  citevouch: ledger adir is not readable JSON: [Errno 13] Permission denied: 'adir'
  ```

  There is no JSON to read; `adir` is a directory, and the sentence sent the
  author to the parser where nothing was wrong. A ledger *under a file* was
  worse, because it claimed the ledger was simply absent:

  ```text
  $ citevouch report --ledger manuscript.md/x.json
  citevouch: no ledger at manuscript.md\x.json; run `citevouch scan` first
  ```

  Following that advice produced a third contradictory sentence: `scan` cannot
  create the file either, because its parent is a file. The write side already
  said the true thing (`adir is a directory, not a file`), so one mistake had
  two sentences depending on which direction touched it.
  *Who was blocked.* Anyone who mistyped `--ledger`, which `action.yml` and
  every CI job pass through `check --use-recorded`. The message they got was
  about their JSON, so they would go and look at a file that did not exist.
  *Done when.* Each of the read verbs names the shape of the path, in the same
  words the write side uses, before it says anything about contents or
  existence.
  *Done - why it is now true.* Both directions call one helper,
  `cli._unusable_target(path, verb)`, and the read side asks it before
  `path.exists()`. Measured now: `report --ledger adir` says
  `adir is a directory, not a file`; `report --ledger manuscript.md/x.json`
  says `cannot read manuscript.md\x.json: manuscript.md is a file, not a
  directory`; a ledger that is merely absent still says `no ledger at ...; run
  `citevouch scan` first`; a real syntax error still names the line. All four
  shapes exit 2. `tests/test_ledger_path_shapes.py` holds 14 tests, and seven
  mutants (drop the directory check, drop the parent-is-a-file check, ask after
  the existence test, hard-code the verb, stop sharing the helper, ...) all
  turn the suite red.
  *Not covered.* A ledger on an unreachable network share, and a path whose
  parent is a symlink to a file; both need an environment this runner does not
  have.

- [x] **A claim block's opening line dropped a `key:` spelling in silence** (P0, 2026-11-09).

  *What was wrong.* A claim block is two half-formats: the body is a mapping (`quote: |`, `id: c1`) and the opening line is a list of `key=value` tokens. An author who learned the format from the body wrote the page hint with a colon, and `_ATTR` never looked for one. Measured on a two-page source whose quote is on page 1, asking for page 9:

  ```text
  ```claim id=c1 source=paper page=9    -> [high] page-out-of-range
  ```claim id=c1 source=paper page: 9   -> [info] quote-found page 1, exit 0
  ```

  The second block asked a question about page 9 and the answer came from page 1, with nothing in the output saying the question had been dropped. The same gap in the id path was worse: `id: c1` became the claim's name `id:`, so every finding read `(id:)` and the ledger stored a name the author never wrote.

  *Who was blocked.* Anyone who copied the body syntax upward - which is the direction the format teaches. The run exits 0 with a verified claim backed by the wrong page, and `action.yml` (which runs `check --use-recorded`) reports the PR green.

  *Done when.* A colon-spelled attribute on the opening line produces a finding that names both spellings, `id: c1` stops becoming a claim id, and a colon inside a value is still one value.

  *Done - why it is now true.* `_OPENING_COLON_KEY` / `_QUOTED` / `_opening_colon_findings()` in `src/citevouch/manuscript.py`; called from both dialects (fence at the `opened_with` site, HTML comment at the `_unknown_attr_findings` site); `_attrs()` no longer turns a `key:` token into the id. `tests/test_opening_line_colons.py` (12 tests) covers both dialects, both verbs, the misspelt key, the quoted value and the `source=weird:name` value. Eight mutations all go red; two of them were only caught after the tests were strengthened (the advice text and the quoted-value blanking).

  *Not covered.* Still a report, not a repair: `page: 9` is not applied, because deciding whether it is a hint or a note is a format change. A colon-spelled key that is neither known nor within one edit of a known one is not reported at all - `foo: 1` stays silent, which is the price of not firing on notes.

- [x] **A table claim row with an empty cell made the file look empty.**
  The table dialect is five cells wide (`| id | source | page | quote | claim |`)
  and `_TABLE_CLAIM` required a character in the `id` cell and a digit-or-`-` in
  the `page` cell. A row with either one left blank matched nothing, so it
  belonged to no claim and to no span, and a one-row manuscript was reported as
  holding no claim block at all. Measured on a one-page source whose quote is
  verbatim on page 1:

  ```
  | c1 | paper |  | <quote> | ok |   ->  [high] no-claim-blocks at m.md:
  |  | paper | 1 | <quote> | ok |        m.md contains no claim blocks, so
                                        nothing was checked ... This file has
                                        none.                            exit 1
  ```

  The quietest shape was worse: a blank-`page` row followed by a good row gave
  `1 claim - 1 verified, 0 moved, 0 missing`, exit 0, and no line mentioned the
  row the parser had walked past.

  *Who was blocked.* Anyone who writes a table row before deciding which page
  the quote is on, or who is still numbering their claims. The tool answers "this
  file has no claim blocks" to a file that plainly has one, and offers to run
  `draft` over it - which proposes blocks for text that already has them.

  *Done when.* A blank `id` cell produces `claim-uncheckable` (the sentence the
  fence dialect already gives), a blank `page` cell means "no page hint" (what
  `-` already meant), and a header row is still not a claim.

  *Done - why it is now true.* `_TABLE_CLAIM` in `src/citevouch/manuscript.py`
  now allows both the `id` and `page` cells to be empty; `_claim_from` already
  answered both omissions correctly once the row reached it.
  `tests/test_table_blank_cells.py` (11 tests) covers the four row shapes end to
  end, the parser directly, and the wrapped-row detector. Five mutants, no
  survivors: the id cell required again, the page cell required again, a blank
  id filled with a placeholder, a blank page turned into page 0, and the
  wrapped-row detector retyping the table shape instead of deriving it from
  `_TABLE_CLAIM.pattern` - that last one survived until a wrapped-row test
  existed, which is why the test is in the file.

  *Not covered.* A row with a cell that holds neither a value nor nothing - a
  stray `-` in the `source` column, say - still fails to resolve and reports
  `source-missing`; that is the right finding, not a parse failure. No fixture
  in the corpus writes claim tables at all, so every shape here is one I wrote,
  not one a real manuscript showed.

- [x] **A test read a child's output as bytes it had assumed were text.**
  `tests/test_table_blank_cells.py` spawned the command in a helper and compared
  its stdout with a summary line containing an em dash, pinning an encoding on
  neither end.  The child wrote with the Windows code page and the parent decoded
  with the locale, so the two sides of the comparison held different bytes.
  This machine's locale and code page are both UTF-8, which is exactly why it
  passed here:

  ```
  test (windows-latest, 3.10)  failure
  test (windows-latest, 3.12)  failure
  test (windows-latest, 3.13)  failure
  Auto release 54018dd         skipped

  assert '1 claim \ufffd 1 verified' in '... citevouch: 1 claim - 1 verified ...'
  ```

  The product code was never wrong.  A test that watches a program across a pipe
  has to say which encoding the pipe carries; without that, the assertion is
  about a byte sequence and reads like it is about a sentence.

  *Who was blocked.* The release.  `Test 54018dd` failed on three of eleven jobs,
  `Auto release 54018dd` skipped, so a fix that was correct and fully tested
  locally produced no version at all - and the numbers on the machine that wrote
  it all agreed with each other.

  *Done when.* The failing Windows jobs go green and `v0.22.32` exists.

  *Done - why it is now true.* The child gets `PYTHONIOENCODING=utf-8` and the
  parent decodes with `encoding="utf-8"`; `tests/test_root_guard.py` had the same
  one-line gap and is pinned too.  `tests/test_child_output_encoding.py` walks
  **files, not functions** and requires an encoding on every text-reading child in
  any file that asserts on non-ASCII text.  That scope is the point: the child
  was spawned in `_run` and the em dash asserted two functions away, and the
  first version of this guard walked one function at a time and stayed green
  against the broken file.  The guard is reverse-validated - restore the pre-fix
  test and it goes red.  `Test 9139fc9` is green on all eleven jobs, including
  the three Windows cells, and `v0.22.32` was released by it.

  *Not covered.* The scan is deliberately narrow: an ASCII-only file may still
  read a child without pinning an encoding, and a non-ASCII string a test writes
  into a fixture is input rather than an expectation.  No other Windows-only
  encoding path was hunted - this one was found by a red runner, not by the scan.

- [x] **A bibliography nobody could read was silent on the recorded path.**
  `scan --bib` reports `bib-unreadable`, `bib-unparsed-entry` and
  `bib-entry-header-unparsed`; the ledger stored only the *entries* a
  bibliography yielded, so a file that yielded none recorded as the same empty
  mapping as a project that named no bibliography. `check --use-recorded` then
  saw an empty mapping, took the `if not ledger.entries: break` short cut, and
  said nothing. Measured on a project whose `refs.bib` is a binary:

      scan                  -> 1, [medium] bib-entry-header-unparsed
                                  [high] bib-unreadable
      check --use-recorded  -> 0, [info] quote-found

  *Who is blocked*: every contributor. `action.yml` runs `check --use-recorded`
  on each pull request, so the only run that decides whether a branch is green
  was the one that could not see the problem. The author's own `scan` said one
  thing and their CI said another, and CI is the one they are asked to trust.
  *Done when*: a bibliography that cannot be parsed, or is no longer there,
  produces the same finding on `check --use-recorded` and on `verify` as it
  does on `scan`.
  *Done - why it is now true*: `Ledger.bibliographies` records the files
  `--bib` named (`scan.py`, appended before the file is judged, so a missing
  file is recorded too), `to_json`/`from_json` carry the key (absent reads as
  "no bibliography named", so old ledgers keep their verdict), and
  `verify.py` re-reads each recorded bibliography and extends the findings -
  the same treatment the manuscript already gets when its recorded digest
  matches. A deleted file is reported as `source-missing` by name.
  `--allow-stale` does not silence it (that flag is about the manuscript; a
  missing `refs.bib` is missing either way, which is why `source-missing` and
  `source-changed` already run under it), and `fresh` does, because there
  `scan` returned the same findings one line earlier.
  `tests/test_bibliography_recorded.py` (17 tests) covers the binary file, the
  unclosed entry, the deleted file, the empty file staying quiet, the two verbs
  agreeing, the live run naming the failure exactly once, and the old ledger
  without the key still reading. Nine mutations all turn the suite red -
  including "scan records only the bibliographies it could parse" and "the
  gate is the manuscript digest instead of `fresh`", the two that would have
  left the original bug half-fixed.
  *Not covered*: no real-world `.bib` from a journal export was tried; the
  fixtures are hand-written from the format. A bibliography reached through a
  symlinked parent directory is still untested, as is a network share that
  disappears between the recorded pass and the re-read.

- [x] **A credibility mark with no claim block was invisible on the CI path.**
  `scan` asks `scan_unbound_markers` about every 【原文】 line no claim block
  covers. `verify` re-parses the manuscript to re-derive the claim blocks the
  parser refused (v0.21.3), and then never asked the marker question - so
  `check --use-recorded`, which is all `action.yml` runs on a pull request,
  printed a marked sentence as a green build. Measured on a manuscript holding a
  marked sentence and an unrelated claim block:

  ```
  check                 -> [low] claim-without-evidence at manuscript.md:1
  check --use-recorded  -> [info] quote-found at manuscript.md:3 (c1)
  ```

  *Who was blocked*: every author who marks a sentence 【原文】 and leaves it
  without a claim block - the single most common way a manuscript looks
  verified while nothing on that line can be checked. The one path that never
  said so was the one path every pull request runs.
  *Done when*: `check --use-recorded` reports the same `claim-without-evidence`
  findings as live `check` on the same tree, once each.
  *Done - why it is now true*: `src/citevouch/verify.py` calls
  `scan_unbound_markers(text, path=manuscript_path.name, spans=parsed.spans,
  claims=parsed.claims)` inside the block that already re-parses the manuscript,
  so both paths ask the same question with the same parse. Covered by
  `tests/test_unbound_markers_recorded.py` (13 tests: a mark with no block is
  reported, the two paths agree, two marks are both named, `verify` agrees, a
  block that names the mark silences it, the live run does not say it twice,
  `--allow-stale` says nothing about marks, every default marker reaches the
  recorded pass, a mark inside a fence is not reported). Four mutations, all red:
  the recorded pass never asks, the spans are not passed, the claims are not
  passed, an empty text is scanned.
  *Not covered*: no real manuscript that mixes marks with table-dialect claim
  blocks; the fixtures are hand-written. `--allow-stale` deliberately stays
  silent, because a mark belongs to a paragraph this run has not read.

- [x] **A Markdown container marker was copied into the proposed `claim:` text.**
  A blockquote, a bullet, a heading and a parenthesised ordinal are four ways of
  *showing* a sentence; the marker is typography, and no reader of the rendered
  page sees it. `draft` read the raw line, so `statement_of` returned
  `> The corpus we used contains …`, the marker was copied into the `claim:`
  field the author is told to paste, and the same sentence then failed to match
  its own source verbatim, because the page has no `>` either.
  *Who was blocked*: anyone who writes a citation inside a blockquote, a list
  item or a heading - ordinary Markdown, and the shape a "quotable sentence"
  section usually takes. Measured on one page holding
  `We collected 154,391 examples from the corpus.` quoted word for word, the
  plain paragraph gave `confidence: high` and one proposal, while the same
  sentence behind `> `, `- `, `* `, `+ `, `## ` or `1) ` gave
  `0 claim block(s) proposed` and left this comment in the proposal:

  ```text
  <!-- line 1: paper - nothing on any page shares enough terms with the sentence (3 needed) -->
  ```

  a sentence the page shares four terms with and prints verbatim. The comment
  blames the author's sentence, so the author's next move is to rewrite the one
  thing that was already right.
  *Done when*: a citation in any container is proposed and its confidence is the
  same as in a plain paragraph.
  *Done - why it is now true*: `statement_of` in `src/citevouch/draft.py` now
  runs `_CONTAINER_MARKER` over every line before anything else, so the marker
  never reaches `_PANDOC`, `_LATEX`, the verbatim comparison or the `claim:`
  field. `tests/test_draft_container_prefix.py` (30 tests) covers eleven marker
  spellings, a wrapped blockquote that repeats its marker per line, a
  continuation line of a list item, the end-to-end proposal and confidence for
  six of them, and the six lookalikes that must stay (`-- x`, `-3 degrees`,
  `2.5 million`, `#hashtag`, `a > b`, and a four-space indent, which CommonMark
  reads as a code block). Eight mutations were run against the fix - marker
  never stripped, only one of the four families stripped, first line only, the
  required space dropped, indent unbounded, and a mid-sentence `>` stripped -
  and every one of them turned the suite red.
  *Not covered*: a quotation whose own text really does start with a bullet or a
  `>`. The page cannot distinguish "the author quoted a list" from "the author
  wrote a list item", and stripping is the common case; the four-space rule is
  the one nod to the counterexample. Also untested: containers nested deeper
  than the pattern's repetition covers.

- [x] **A `--quiet` run that failed handed GitHub code scanning an empty document, and no reason.**
  `--quiet` shortens the display; it does not shorten the verdict. A run can
  fail on a finding the display was told to hold back, and then every writer has
  to say why. Three of the four did. The fourth - SARIF, the one `action.yml`
  uploads to code scanning - wrote `results: []` and never mentioned
  `invocations` at all, so code scanning was told that a successful analysis
  found nothing while the job exited 1.
  *Who is blocked*: everyone who wired citevouch into a PR gate with the
  defaults. `action.yml` writes SARIF and passes `--fail-on`; when the author
  also passes `--quiet` (the combination people reach for once the log gets
  noisy), the failure has an exit code and no sentence. A red job whose report
  is empty sends the reader looking for the reason in the wrong place - it is
  the sibling of a green tick over an unchecked claim.
  *Done when*: a failing `--quiet` run's SARIF document states that the run
  failed and why, and a run that hid nothing failing keeps its exact bytes.
  *Done - why it is now true*: `render_sarif` takes `everything` and `fail_on`;
  when `--quiet` held back a finding that reaches the threshold it writes
  `runs[0].invocations[0]` with `executionSuccessful: false` and one
  `toolExecutionNotifications` message naming the count and the threshold
  (`_sarif_invocation` returns `None` otherwise, so the key is absent rather
  than empty). `results` is still only the visible findings, so `--quiet` means
  what it always meant. `render_json` gained `failing_hidden` and `fail_on`,
  written only when non-zero - and adding them exposed that `hidden` was
  computed by subtracting two lengths, which read a duplicated finding as a
  hidden one and made the payload announce a reason over a finding it listed;
  both writers now subtract by identity. Proved by
  `tests/test_sarif_quiet.py` (23 tests, covering the failing shapes, the
  untouched loud/quiet-passing shapes, the renderers called directly, and all
  four writers agreeing) and by 13 mutations, every one red.
  *Not covered*: no real upload to GitHub code scanning, so how that UI renders
  `toolExecutionNotifications` is unverified; a consumer that ignores
  `invocations` still sees an empty result set (the exit code is the only
  signal left, which is the status quo, not a regression); `doctor --format
  sarif` passes no `everything`, so its document never gains the key - it has
  no `--quiet` to explain.

- [x] **One bibliography was recorded with two different paths.**
  `sources.toml`'s paths and the ledger's own `bibliographies` list are recorded
  relative to `--root` with forward slashes, so a ledger written on Windows
  resolves on the Linux job that runs the same commit. The bibliography
  *entries* were not: `scan` handed `parse_bib` the path exactly as the shell
  spelled it.
  *What was wrong*: one project, two shells, two ledgers.

  ```text
  scan proj/manuscript.md --root proj --bib proj/sub/refs.bib
    entries['knuth2020'].path = 'proj\sub\refs.bib'
    bibliographies            = ['sub/refs.bib']
  cd proj && scan manuscript.md --root . --bib sub/refs.bib
    entries['knuth2020'].path = 'sub\refs.bib'
  ```

  Neither agreed with the `sub/refs.bib` the same run wrote into
  `bibliographies`, and every finding built on an entry (`bib-field-empty`,
  `bib-field-malformed`, `bib-unreadable`) named the file back in whichever
  spelling the recording shell used. A commit made on Windows therefore
  produced different finding text, and a different SARIF
  `artifactLocation.uri`, on the Linux job.
  *Who was blocked*: anyone whose CI runs on a different OS from their laptop,
  which is the default for a GitHub project developed on Windows. The finding
  was still *correct* — the entry really was missing its `year` — but the file
  it named is not a file the reader on the other machine can open, and the one
  thing this tool must never do is send an author to a file that does not exist.
  *Done when*: one project scanned from two directories writes one ledger, and
  a finding about a bibliography names a path that resolves against `--root`.
  Both are asserted in `tests/test_bib_path_portable.py` (15 tests).
  *Done - why it is now true*: the recorded path is computed in one place,
  `scan.recorded_path` (renamed from `_ledger_path` — `cli`, `verify` and `scan`
  all need it, and a private name collided with the CLI's own flag resolver for
  `--ledger`). All four call sites that hand a bibliography to the parser use
  it: the recording pass, the live `check --bib`, `verify`'s re-read, and
  `draft --bib`. Eight mutants, none survived: entries keep the shell's
  spelling; the recorded path is absolute; it keeps the platform separator; the
  `bibliographies` list goes back to the native spelling; the recorded pass
  stops normalising; the live run stops normalising; a path outside the root is
  invented into one; and `draft` joins the recorded path to the shell instead
  of the root.
  *The half that bites back*: moving the spelling made `draft` start lying.
  It resolved a bib entry's `file` field against `entry.path`'s folder, which
  only worked while that path was relative to the shell — from one directory
  above the project it silently stopped finding a `paper.txt` sitting beside
  the bibliography. That is the second reason the whole path question is worth
  one function: a path that is relative to the root is only correct if every
  reader joins it to the root, and there were readers in two modules nobody
  thought of as path readers.
  *Not covered*: a real round trip between a Windows and a Linux checkout (the
  ledger was never carried across machines, only the two shells on one);
  bibliographies reached through a symlink or a UNC share; and `draft`'s
  `file`-field fallback still tries the bibliography's folder before the root,
  which is deliberate — Zotero writes paths relative to the `.bib`.

- [x] **A table was prose unless the package was `tabular`.**
  `_DROP_ENVIRONMENT` named `tabular` and `tabular*` only, so the package a
  journal template happened to use decided whether the tool read a table as
  text. `tabularx`, `xltabular`, `tabulary`, `longtable`, `tabu`, `longtabu`
  and `supertabular` fell through to the prose reader: the column
  specification arrived as a word and every cell as a sentence.

  ```text
  \begin{tabularx}{\linewidth}{lX}
  Baseline \citep{knuth2020} & 90,000 \

  to_text -> 'lX
              Baseline [@knuth2020] & 90,000'
  ```

  *Who was blocked*: every author whose publisher asks for a full-width table.
  `draft` reported `0 claim block(s) proposed (0 verbatim), 1 citation(s) left
  as comments` and blamed the page for not containing a sentence that is a row
  of a table, so the one comment the tool asks the author to read was false.
  The same table written with `tabular` was dropped and the run truthfully said
  no citations were found - two verdicts for one paper, chosen by a package
  name.

  *Done when*: no table package's body reaches the converted text, and the
  decision about math grids is written down rather than implied.

  *Done - why it is now true*: all seven names are in `_DROP_ENVIRONMENT`.
  `tests/test_table_environments.py` (44 tests) covers the cells, the column
  spec, a citation in a cell, a table nested in the same environment, an
  unclosed table, the `\input` inside a table, and `TestMathIsLeftAlone`, which
  pins that `array`, the `matrix` family and the display-math environments keep
  their numbers on purpose. Ten mutations: each name removed one at a time,
  only the two original names kept, `array` wrongly added, and the nesting
  counter removed - `survivors: []`, `broken mutants: []`.

  *Not covered*: a real journal `.tex` from a template; fixtures are hand
  written from each package's documented syntax. Tables of *different* packages
  nested inside each other are not covered either - `_skip_environment` counts
  one name at a time.

- [x] **A long table's caption was deleted with its cells.**
  A `table` float keeps `\caption` outside the grid, so dropping `tabular`
  always left the caption alone. `longtable`, `xltabular` and `longtabu` break
  across pages and repeat the caption in a running head, so the caption is
  written *inside* the environment: dropping the body dropped a sentence the
  author wrote and a reader sees.

  ```text
  citevouch: 0 claim block(s) proposed: no citations were found to propose them for
             (this command reads `[@key]` and `\cite{key}`)
  ```

  *Who was blocked*: every author with a table longer than a page - which is
  most empirical papers. The citation printed under the table vanished from the
  tool's view entirely, and the run blamed the paper for having no citations at
  all.

  *Done when*: a caption written inside a long table reaches the converted text
  and its citation can be proposed, while the cells stay out.

  *Done - why it is now true*: `_CAPTIONED_ENVIRONMENT` names the three
  packages; `_captions_inside()` converts `\caption`/`\caption*` between the
  opener and `_skip_environment`'s end, joining several with blank lines, and
  skips any caption that falls inside a `verbatim`/`lstlisting` body nested in
  the table (`_shown_not_written`). `tests/test_table_caption.py` (21 tests)
  covers the three packages, the optional short caption (the long one is what a
  reader sees), `\caption*`, two captions in one table, a caption shown inside a
  listing, a caption outside the environment not being lifted twice, and the
  end-to-end `draft` run. Nine mutations, `survivors: []`, `broken mutants: []`.

  *Not covered*: a real published paper using `\endfirsthead`/`\endhead`
  repetitions; the fixtures are written from the package documentation.
  `\captionof` inside a table (the `caption` package) is not handled.

- [x] **Three commands pasted the name they were pointing at into the sentence.**
  `\captionof{table}{We collected 154,391 examples.}` converted to
  `tableWe collected 154,391 examples.`, `\rotatebox{90}{...}` leaked `90`, and
  `\hyperref[sec:data]{...}` leaked `[sec:data]`. Each takes one argument that
  names something and one that is prose, and none was in `_SKIP_FIRST_ARGUMENT`,
  so each fell through to the unknown-command branch, which drops the command
  name and keeps every argument.
  *Who is blocked*: anyone whose manuscript uses `\captionof` - the caption
  package's spelling for a table set inside a paragraph, not an exotic input.
  `draft` on such a paper printed
  `0 claim block(s) proposed: 0 quoting the sentence verbatim` for a sentence
  the page holds word for word; the same sentence in a plain paragraph gave
  `1 claim block(s) proposed: 1 quoting the sentence verbatim` with
  `confidence: high`. `\nameref` and `\vref` were the mirror case: `\ref`
  under other names, missing from `_DROP_ARGUMENT`, so
  `see \nameref{sec:data} for details.` put the label key in the prose as a
  word.
  *Done when*: those three commands convert to their text argument alone, a
  verbatim citation inside them is proposed at `confidence: high`, and
  `\nameref`/`\vref` drop their key the way `\ref` already did.
  *Done - why it is now true*: `captionof`, `rotatebox` and `hyperref` are in
  `_SKIP_FIRST_ARGUMENT`; `nameref`, `vref` and `Vref` are in `_DROP_ARGUMENT`.
  `hyperref` spells its name in the optional argument in one form and the first
  braced argument in the other, so `_OPTIONAL_IS_THE_NAME` drops only the
  bracket when a bracket is there - skipping two arguments unconditionally ate
  the words, which is worse than the leak. `tests/test_captionof_argument.py`
  (21 tests) covers the conversion, the braced-form control, the end-to-end
  `draft` proposal, and a loop over every name in `_SKIP_FIRST_ARGUMENT` that
  fails if any command keeps a brace. Seven mutants, all red: the three new
  names back out together, `rotatebox` alone, `hyperref` alone, the
  optional-argument adjustment removed, `nameref`/`vref`/`Vref` back out of the
  drop table, the adjustment's bracket test removed, and that test made
  unconditional.
  *Not covered*: `\hyperref [label]{text}` with a space before the bracket is
  read as the braced form, which keeps its words but leaks the label;
  `\stackrel`, `\overset` and `\underbrace` leak their first argument too and
  were left alone, because they are math and `_plain_math` already decides what
  a reader sees.

- [x] **`report` printed the same bibliography line for two opposite facts.**
  `citevouch report` answered "what does the ledger say" and printed
  `- bibliography: 0 entries` for a project scanned with `--bib refs.bib`
  where that file held no readable entry, and the identical line for a
  project that never passed `--bib` at all. `Ledger.bibliographies` has
  held the file names since 0.22.33 - added so a recorded bibliography
  failure could reach the recorded pass - and `verify` reads it, but
  `report` never did.

  *Who was blocked*: anyone auditing a ledger. "Bibliographies were given,
  and nothing could be read out of them" and "no bibliography was given,
  so no reference was ever checked against one" lead to opposite next
  steps, and the report rendered them with one string.

  *Done when*: the line names the recorded files, and a run with no
  bibliography says so instead of implying an empty one.

  *Done - why it is now true*: `cli._bibliography_line(ledger)` prints
  `refs.bib (0 entries)` or `none recorded (0 entries)`; the JSON payload's
  `ledger` object gained `bibliographies`. Proved by
  `tests/test_report_names_bibliography.py` (10 tests), and by eight
  mutants that all go red - the line back to counting only, names dropped
  when nothing could be read, names never printed, `none recorded` replaced
  by a bare count, no clipping, the count left off, the JSON field removed,
  the JSON field written empty.

  *Not covered*: a ledger whose recorded bibliography has since been
  deleted (the line would still name it, and nothing asserts that text);
  a ledger written by a tool newer than `SUPPORTED_SCHEMA`.

- [x] **The recorded pass re-read the bibliography and then judged the stale mapping.**  Since 0.22.33 the recorded pass opens every bibliography the ledger names, so that a file nobody could read is not silently treated as a file nobody mentioned.  The parse findings came from that fresh read; the verdicts - which keys exist, which entries are unused, which entries are missing required fields - were still computed from `ledger.entries`, the mapping `scan` captured.  One run held two opinions about one file and the stale one spoke.
  *What was wrong*: with a project scanned against a bibliography holding `knuth2020` and then edited so the file holds only `lamport1994`,

  ```text
  $ citevouch check manuscript.md --bib refs.bib
  [high] bib-key-missing at manuscript.md:1 (c1): claim c1 cites 'knuth2020', which is not in the bibliography the ledger recorded
  $ citevouch check manuscript.md --use-recorded
  [info] quote-found at manuscript.md:1 (c1): quote found on page 1
  ```

  The mirror image is the more expensive half: an entry that lacked `publisher` and `year` kept its `bib-field-empty` complaint after the file had replaced it with a complete one, so the author was told about required fields of an entry that no longer existed.
  *Who was blocked*: every contributor, because `action.yml` runs `check --use-recorded`.  The green pull request and the red local run were the same tree, and the sentence the PR showed named an entry the file no longer held - which invites the author to add it back.
  *Done when*: the recorded pass and the live pass report the same verdict on a bibliography that changed after `scan`, and neither ever reports a `bib-key-missing` about a file the run could not read.
  *Done - why it is now true*: `src/citevouch/verify.py` now judges `verdict_entries`, which are the entries this run re-read; the recorded mapping survives in exactly two runs that opened no file at all - `fresh` (live `check`, where `scan` just wrote these entries) and a ledger written before `bibliographies` existed.  `field_findings`, `entry_keys`, the unused set and the `bib-key-missing` loop all read that one mapping, and the sentence says "the bibliography" rather than "the bibliography the ledger recorded" when the file was re-read.  Proved by `tests/test_bibliography_fresh_verdicts.py` (12 tests) and ten mutations, all red: verdicts back on `ledger.entries`, re-read entries discarded, the no-file case judged empty, unused/key/field all back on the recorded mapping, the sentence reverted, parse findings dropped, and the re-read disabled.
  *Not covered*: no real journal-exported `.bib`; every fixture is hand- written to the BibTeX subset this tool reads.  Two `--bib` files whose keys collide still merge into one mapping, and that case is untouched.

- [x] **Two `--bib` files that define one key silently overwrote each other.**  `parse_bib` reports a key defined twice *inside one file* (`bib-duplicate-key`, high).  Two files each defining it once produced no finding at all, because both merges were `dict.update`: `scan`'s loop over `--bib`, and the recorded pass's re-read of `Ledger.bibliographies`.
  *What was wrong*: with `a.bib` calling `knuth2020` a book and `b.bib` calling the same key a different article,

  ```text
  $ citevouch scan manuscript.md --bib a.bib --bib b.bib
  citevouch: wrote citevouch.lock.json (1 claim)      # exit 0, no finding
  ```

  The later file silently replaced the earlier one, so which work a claim rested on was decided by the order of the `--bib` flags - an accident of the command line, not a statement about the paper.
  *Who was blocked*: anyone with a bibliography split across files, which is the normal shape of a multi-project Zotero export.  `action.yml` runs `check --use-recorded`, which merged the re-read files the same way, so the pull request was green whichever entry won.
  *Done when*: a key defined in two different `--bib` files is reported on every verb that reads bibliographies, names both files, and does not change which entry the run judges.
  *Done - why it is now true*: `src/citevouch/bibtex.py` has `merge_entries(into, entries) -> list[Finding]`, which reports the clash as `bib-duplicate-key` (high) naming both `earlier.path` and `entry.path`, and still lets the later entry win.  `scan.py` calls it instead of `ledger.entries.update(...)`; `verify.py` calls it instead of `reread_entries.update(...)`.  Proved by `tests/test_bib_cross_file_keys.py` (14 tests): both orders, three files defining one key, `scan` / `check` / `verify`, and the silent cases - two files with different keys, one entry, one file naming a key twice (still one finding), and one file passed twice.  Nine mutations, all red; one survived the first round and the `--bib a.bib --bib a.bib` test is what killed it, which is why that case is pinned.
  *Not covered*: no real Zotero or JabRef export split across two files.  `citevouch draft --bib` reads the same files but prints none of their parse findings - not this one and not the older ones - so the finding reaches `scan`, `check` and `verify` only.  That silence predates this change and is left alone here.

- [x] **`draft --bib` dropped the bibliography parser's findings and then lied about the entry.**
  `draft` reads every `--bib` file for one reason - to answer "where is the
  local file for this key" - and threw away `parse_bib`'s findings, so a file
  it could only half read produced no output at all:

  ```text
  $ citevouch draft paper.md --root . -o claims.md --bib refs.bib
  citevouch: 0 claim block(s) proposed (0 verbatim), 1 citation(s) left as comments
  $ citevouch scan paper.md --root . --bib refs.bib
  [high] bib-unparsed-entry at refs.bib:1: an entry was never closed ...
  [high] bib-unreadable at refs.bib:1: not one entry could be read ...
  ```

  Because the entry never parsed, the key had no entry to answer with, and the
  comment written for it said the bibliography had no `file` field - about a
  `.bib` that has `file = {page.txt}` on line 5. That is the false sentence
  v0.19.63 fixed for the `scan` path, still standing in the command that reads
  the file to answer that exact question.
  *Who is blocked*: anyone whose `.bib` came out of a reference manager with
  one malformed entry. `draft` is the first command a new user runs against
  their own paper, and the sentence sends them looking for a field that is
  right there.
  *Done when*: `draft --bib` reports the same parse findings `scan` does, and
  a key the bibliography names without defining gets a sentence that says so.
  *Done - why it is now true*: `cmd_draft` keeps `parsed.findings`, prints them
  before its summary, merges entries through `merge_entries` (so a key defined
  in two `--bib` files is reported from here too), and passes `draft` a
  `bib_unreadable` set built by `draft._bib_keys_without_entries` - the keys a
  file names in an entry header while producing no entry for them. `_why_no_file`
  says "the bibliography could not be fully read, so no entry was parsed for
  'knuth2020'" for those and keeps the generic sentence for a readable
  bibliography that simply does not mention the key.
  `tests/test_draft_bib_findings.py` (14 tests); ten mutations, `survivors: []`
  (two needed a tighter test: one asserted the key was anywhere on the line when
  the comment prefix already carries it, and one needed a readable entry with no
  `file` field to show the set must exclude keys that parsed).
  *Not covered*: no real reference-manager export; a key regex that is
  deliberately loose and only ever runs on a file the parser already refused.

- [x] **The command `draft` told the author to run next failed on its own output.**
  `draft` ends by naming the `check` command that reads the file it just wrote.
  That sentence was built from the output path alone, so a run with `--root`
  printed an advice without it, and following the advice checked the current
  directory instead of the project:

  ```text
  $ citevouch draft proj/paper.md --root proj -o claims.md --bib proj/refs.bib
  citevouch: wrote claims.md; read it, then `citevouch check claims.md` to see what it got wrong
  $ citevouch check claims.md
  [high] source-missing at claims.md:11 (knuth2020): claim knuth2020 names
  source='knuth2020' but no entry in sources.toml ...
  ```

  The second command exits 1 with a false accusation about a claim `draft` had
  itself just quoted verbatim from a page it had read.
  *Who is blocked*: the first-time user this command exists for. `draft` is the
  command that turns a paper into checkable claims, so its last line is the
  only instruction many readers ever follow.
  *Done when*: the command printed in the output can be copied and run from the
  directory it was printed in, and does what the sentence says.
  *Done - why it is now true*: `cli._check_advice(output, root)` builds it from
  the values the run used - `--root` whenever the run had one and nothing for
  `--root .` - and `cli._shell_word` prints paths with forward slashes (a
  Windows backslash is a shell escape) and quotes anything with a space,
  including the `'` -> `'\''` case that would otherwise end the quote early.
  `tests/test_draft_advice_runs.py` (6 tests) extracts the command from the
  output and executes it, so the test fails on what a user would notice.
  Six mutations, `survivors: []` (one survived the first round: nothing escaped
  an apostrophe, which needed a filename with one in it to show).
  *Not covered*: only POSIX `sh` rules are honoured - the advice is split with
  `shlex` in the test, and `cmd.exe` quoting differs.

- [x] **An output flag could write over a file the run had just read.**
  `scan --ledger` accepted any path, and the ledger is the one file this tool is
  meant to write, so the flag looks like an ordinary destination. Measured, on a
  project holding one claim:

  ```text
  $ citevouch scan paper.md --root . --ledger paper.md
  citevouch: wrote paper.md (1 claim)                        ->  exit 0
  ```

  The manuscript was 97 bytes of Markdown and 753 bytes of JSON afterwards.
  `--ledger sources.toml` replaced the manifest and `--ledger page.txt` replaced
  the page the quote came from; every one of them exited 0 and said what it had
  written.

  `draft -o` had refused such outputs since v0.19.52, but its list came from the
  command line, so it missed the same class of file from the other end: `draft -o
  page.txt --force` wrote 511 bytes of proposals over the page `sources.toml`
  binds to `paper`, because no flag ever names that path.

  *Who is blocked*: anyone who mistypes a `--ledger` or `-o` in a directory full
  of filenames that look like ledgers. The run reports success, so nothing tells
  them until the next command cannot read the manuscript they just destroyed.

  *Done when*: an output path that resolves to any file the run read is refused
  before the write, with a message naming the file and what it is to the project.

  *Done — why it is now true*: both writers ask `cli._project_inputs`, built from
  what the run read rather than from its flags: the manuscript, both manifest
  names, every source the manifest or `--source` bound, every `--bib` file, and
  the ledger. The comparison is by resolved path; `scan --dry-run` is exempt
  because it writes nothing. `tests/test_ledger_overwrites_input.py` (13) asserts
  the bytes of every protected file, not only the exit code, and nine mutations
  of the guard are all red. One of them survived first — the comparison falling
  back to a textual one — because `Path` discards a leading `./`, so the test now
  names one file two ways with `..`.

  *Not covered*: a filesystem where two spellings of one path are two files (a
  case-insensitive checkout on a case-sensitive runner); a source bound by a
  manifest that lives outside `--root`.

- [x] **A manuscript could be its own source of evidence.**
  *Done 2026-11-09.*
  *What was wrong.* `sources.toml` says where a claim's proof lives; nothing
  asked whether the place it named was the manuscript being checked. On a
  project whose manifest maps `paper` to `paper.md`, with a sentence that
  exists nowhere except inside the claim block asserting it:

  ```text
  $ citevouch check paper.md --root .
  [info] quote-found at paper.md:5 (c1): quote found on page 1

  citevouch: 1 claim — 1 verified, 0 moved, 0 missing
  worst severity: info
  ```
  `1 verified` for a fabricated quote, because the quote was searched for on
  page 1 of the file that contains it. Three routes reached the same green: the
  manifest, `--source paper.md`, and a byte-for-byte copy under another name.
  *Who is blocked.* Everyone, silently: this is the one claim the tool exists
  to refuse, and it is the loudest possible false statement - certifying the
  author's own draft as external evidence. `action.yml` accepts `--source` too,
  so a pull request could go green on it.
  *Done when.* All three routes exit 1 with a `source-is-manuscript` finding at
  `high`, `scan` and `check --use-recorded` both report it, the ledger does not
  record the manuscript as a source, and a real page holding the same sentence
  still verifies.
  *Done - why it is now true.* New `src/citevouch/evidence.py` holds
  `is_the_manuscript()` (resolved path, then digest) and
  `source_is_manuscript_finding()`; `scan.py` calls it after `resolve_source`
  and skips the claim without recording `ledger.sources`; `verify.py` calls it
  in the recorded pass, which never reads the manifest at all. `CODES`,
  `SARIF_RULES` and both README tables gained `source-is-manuscript` (high).
  `tests/test_manuscript_is_not_a_source.py` (13). The mutation campaign's
  first round left two mutants alive - removing the scan-side digest, and
  searching the claim anyway - because `check` runs both passes and the other
  one caught it; `test_scan_alone_catches_a_copy` (runs `scan` on its own) and
  `test_the_ledger_does_not_record_the_manuscript_as_a_source` killed them,
  then all eight died.
  *Not covered.* A case-insensitive filesystem, where two spellings resolve to
  one file only sometimes; the digest comparison is what covers that and no
  test here can exercise both filesystems at once.

- [x] **`draft` proposed a claim block that `check` refuses on sight.**
  v0.22.47 taught `scan` and `verify` that a source may not be the manuscript
  itself, and left `draft` out. A `sources.toml` binding a key to the
  manuscript, or a bibliography entry whose `file` field names it, made
  `draft` write a block into `claims.md` and recommend pasting it back:

      ```claim id=knuth2020 source=knuth2020 page=1
      quote: |
        We collected precisely 987,654 examples under a blue moon \citep{knuth2020}.
      ```

  Pasting it back gave `[high] source-is-manuscript`. *Who is blocked*: an
  author who follows the advice the tool just printed, which is every author
  the command exists for. *Done when* `draft` asks the same question the
  other two readers ask, and the skip note names the file.
  *Done - why it is now true*: `src/citevouch/draft.py` calls
  `evidence.is_the_manuscript` between resolving the key and recording it as
  a needed source, and `src/citevouch/cli.py` passes the manuscript path and
  its digest. `tests/test_draft_source_is_manuscript.py` (10 tests) pins all
  three routes plus one test that builds the block the old code wrote and
  asserts `check` rejects it. Six mutants, `survivors: []` - one candidate
  was an equivalent mutant (the digest subsumes the path for every input
  reaching it) and is documented in the script rather than tested for.
  *Not covered*: a manuscript reached through a symlink whose target is the
  source page; `draft` also still prints no bibliography parse findings
  (that was v0.22.44's separate fix for `scan`, and `draft` shares it).

- [x] **A quotation that ran across two page breaks was reported missing.**
  The stitcher glued *pairs* of adjacent pages together, so a quote crossing
  one break was found and one crossing two was not. Measured on a source
  whose sentence starts on page 2 and ends on page 4:

      [high] quote-missing at manuscript.md:1 (c1): We collected a very
      large number of examples from the corpus and then filtered them by ha…
       — quote not found in page.txt

  The words are there, verbatim, in order. *Who is blocked*: every author
  quoting a long sentence from a paper that sets prose in a narrow column;
  two-page quotes were already handled, so the failure looked random.
  *Done when* a quote touching three or four pages is found, and every
  downstream answer agrees with the wider window.
  *Done - why it is now true*: `src/citevouch/matching.py` replaced
  `_page_pairs` with `_page_runs` (every run up to `MAX_STITCHED_PAGES = 4`),
  `Match.spanned` records every page a quote touches, and
  `src/citevouch/verify.py` reads that field in four places: the not-a-move
  check, the message, the numbers check, and the run ordering (length is the
  outer loop, so a shorter run always beats a longer one that merely
  contains the quote). `tests/test_cross_page_three.py` (19 tests) pins each;
  nine mutants, `survivors: []`. One mutant survived two rounds - "the
  numbers check reads only the ends" - because `_number_checks` returns
  early when no page it was given has any number, so the fixture needed a
  figure on an end *and* one in the middle.
  *Not covered*: a quote spanning more than four pages is still reported
  missing - the limit is a cost decision, pinned by a test on the constant
  but not fixtured; and no real PDF whose extractor splits a word mid-break.

- [x] **A quotation whose figures straddle a page break was called a fabrication.**
  The numbers tier -- the comparison that blanks out every figure and asks whether the
  remaining words are the page's -- read one page at a time.  The exact and canonical
  tiers had already been taught to stitch adjacent pages; this one had not.  Measured on
  a sentence printed across pages 2 to 4 with page 3 carrying a different total:

    ```
    [high] quote-missing at manuscript.md:1 (c1): We collected a very large number of
    examples from the corpus and then filtered the 154,39... — quote not found in page.txt
    ```

  With the right figure the same words were found across the same pages, so a typo was
  reported as a fabricated quotation -- about pages the author can open and read -- and
  the run answered "are these the source's figures?" with "is this the source's
  sentence?".

  *Who was blocked*: anyone quoting a sentence that runs over two page breaks.  Only
  that shape was wrong; a quote fitting one page, or one break, was reported correctly,
  which is why no earlier round caught it.

  *Done when*: a wrong figure on a middle page is reported as a wrong figure, and the
  sentence names the pages it looked at.

  *Done - why it is now true*: `src/citevouch/matching.py` tries single pages and then
  every run from `_page_runs`, both through one `_number_match` helper, the same order
  the exact tier uses so a quote that fits a page is still attributed to it.
  `_number_checks` is asked about `match.spanned`, so a figure printed on a middle page
  is not reported absent.  The sentence now says "pages 2, 3 and 4 ... do not contain
  that number" rather than joining them with " or ", which read as three alternatives.
  `tests/test_numbers_across_pages.py` (10 tests) pins the code, the wording, the
  single-page case, the `Match` fields and the recorded path; ten mutants are red once
  two survivors were re-aimed at a fixture with a page-level match competing against a
  run-level one.

  *Not covered*: no real PDF whose figures straddle a break -- the fixtures are text
  pages joined with a form feed.  `MAX_STITCHED_PAGES` is 4, so a quote spanning five
  pages is still reported missing; that is a cost decision, not a completeness claim.

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

- [x] **A word-processing document.** A `.docx` is a zip. Neither PDF reader
  reads it, so the plain-text fallback did - and decoded the zip into 120
  characters of valid-looking nonsense, which became page 1. The run then
  reported `[high] quote-missing ... quote not found in paper.docx`: a verdict
  about the author's quote when the fact was about the file format. *Done in
  v0.20.0:* `source-not-text` (medium) reads the file's own first bytes and
  names what the document is and how to convert it. The noise-ratio idea was
  measured and rejected - a PNG is only 1.6% control characters, so no
  threshold separates "prose with the odd NUL" from "image bytes". Two things
  make this more than a message change: a suffix the author stated (`.txt`) is
  still read as text even when it starts with `PK`, and the refusal sits above
  the cache, because an entry written before the check existed holds the zip
  spelled as characters and would answer for the file forever. Four mutations
  are red.

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
- [x] **`draft` quoted half of a sentence the source printed across two pages.**
  The matcher learned, in 0.22.49, to find a quotation running off the bottom of a
  page: `Match.spanned` now carries every page of the run.  `draft.propose_quote` kept
  asking the old question, `match.page` - the *first* page of the run - and looked for
  the author's sentence in that page's own text.  A sentence ending on the next page is
  not one of that page's sentences, so the verbatim branch missed and the proposal fell
  back to the medium-confidence path, which quotes whichever part of the sentence the
  page does print.  Measured on one sentence, one project, two layouts:

    ```
    whole on page 2:   1 quoting the sentence verbatim   confidence: high    page=2
    split 2 -> 3:      0 verbatim (1 claim block)        confidence: medium  page=3
                       quote: filtered them by hand before training the model on
                              the remaining portion.
    ```

  The half sentence is a true sentence of page 3, and it is not what the author wrote;
  the block was written into the file `draft` tells the author to copy from.

  *Who was blocked*: anyone whose sentence begins near the foot of one page and ends
  near the top of the next, which is the normal shape of a sentence in a two-column
  paper.  Nothing failed loudly - the author got a weaker claim with a truncated
  quotation and a comment saying a similar sentence was on the page.

  *Done when*: a sentence the source prints across a break is quoted whole, at high
  confidence, and the claim still names the page a reader starts on.

  *Done - why it is now true*: `propose_quote` builds `covering` from every page whose
  number is in `match.spanned`, joins them, and searches that for the verbatim
  sentence; the returned page stays `match.page`.  Stitching the whole document instead
  is the one way this branch can say "not verbatim" about a sentence the source prints
  exactly - a page boundary carries no reliable sentence break, so a page ending "see
  also" merges into the next page's opening and the real sentence stops being a
  sentence in the joined text.  `tests/test_draft_cross_page_quote.py` (9 tests) pins
  the cross-page quote, the single-page control, the two-page case, the page number and
  a dangling page before the run.  Seven mutants are all red, including
  `covering = pages`, which survived until the dangling-page fixture existed.

  *Not covered*: real PDFs whose extractor splits a word across a break, and sentences
  spanning more than `MAX_STITCHED_PAGES` (4) pages - beyond that the matcher itself
  reports the quote missing, so `draft` never reaches this branch.

- [x] **P1 - a sentence the browser never paints was verified as a quotation**

  *What was wrong.* The HTML reader dropped inert elements by tag name
  (`script`, `style`, `template`, `textarea`, `iframe`) and that list was the
  whole rule.  A browser has a second, larger vocabulary for "do not paint
  this" and none of it is a tag name.  Measured on a one-claim project whose
  only source held the sentence in each layout:

  - `<div style="display:none">We collected 40,688 examples from the corpus.</div>`
  - `<div style="visibility:hidden">` around the same sentence
  - `<p hidden>`
  - `<span aria-hidden="true">`
  - a `<title>` in `<head>`
  - a `<datalist>` `<option>`

  Every one answered `[info] quote-found … quote found on page 1` and exited 0.
  Every other HTML defect this reader has had turned a visible quote into
  `quote-missing` - annoying, but the author checks and finds the tool wrong.
  This one certified words nobody can see, which is the only thing the tool
  exists to prevent.

  *What it does now.* `_without_unpainted()` reads the opening tag instead of
  the tag name: `_attributes()` is a tokeniser, `_style_hides()` recognises
  `display: none` and `visibility: hidden|collapse`, `_paints_nothing()` adds
  the `hidden` attribute unless it is `until-found`, and `_end_of_element()`
  counts depth so a nested `<div>` goes with its parent while a sibling stays.

  *Done - why it is now true.* `tests/test_unpainted_html.py` (37 tests) covers
  the six layouts end to end (each must fail `check`), a nested element going
  with its parent, a sibling surviving, an unclosed element running to the end,
  a void element (`<img hidden>`) hiding only itself, and the four shapes that
  must keep verifying: `aria-hidden`, `<title>`, `<datalist>` and
  `hidden="until-found"`.  Thirteen mutations all go red - the ones that matter
  are "no normalisation of the style's spelling", "the attribute reader falls
  back to searching for the word", "the end of the element is the first closing
  tag", "an unclosed element ends where it started" and "the pass is not run at
  all".

  *The first fix was wrong in the same way twice.* Searching the tag for
  `\bhidden\b` dropped five elements nothing had hidden
  (`title="hidden"`, `data-hidden="true"`, `class="hidden"`, `id="hidden"`,
  `aria-label="hidden"`), and a lookbehind fixing `aria-hidden` still ate
  `title="hidden"`.  The question was "is `hidden` an attribute name here", and
  the answer is a tokeniser, not a better regex.

  *Not covered*: `color: white`, `font-size: 0`, `opacity: 0` and
  `position: absolute; left: -9999px` are all ways an author hides text and all
  also ordinary styling, so they are deliberately left in the page text -
  documented in `_style_hides`'s docstring, because the false `quote-missing`
  they would cause costs more.  Nor does this read a stylesheet: `<style>
  .gone { display: none }` is dropped by `_UNRENDERED_TAGS` as raw text, so a
  class-based hide is not resolved.  Measured: a page whose only source kept the
  sentence in `<p class="gone">` still verifies with the stylesheet present,
  because the class-to-rule mapping is not read.

- [x] **P1 - a small non-UTF-8 HTML page was read as mojibake and its quote reported missing**

  *What was wrong.* `encoding_problem()` in `src/citevouch/sources.py` refused a
  text source when `invalid_utf8_share(bytes) >= MAX_UNDECODABLE_SHARE` (0.25),
  and that share is measured over the whole file while an HTML header is ASCII.
  Measured on a one-claim project whose only source was a 239-byte GBK page with
  `<!DOCTYPE>`, `<meta http-equiv="Content-Type" content="text/html; charset=gbk">`,
  `<link>`, `<title>论文摘要</title>` and one body sentence:

  - `invalid_utf8_share = 0.172`, so it was **not** refused;
  - `_decode_text` decoded it with `errors="replace"` - a decoder that cannot
    fail - and the extracted text was `' ����ժҪ �����ռ� …'`;
  - end to end: `[high] quote-missing … 本文收集了六万八千个例句，全部来自语料库中的真实文本。
    — quote not found in page.html`, exit 1, about a sentence printed verbatim in
    that file;
  - the same page with one more sentence scores 0.254 and is refused correctly,
    so the defect only ever appeared on short documents.

  cp1252 French scores 0.176 and German 0.075, so the one obvious alternative -
  lower the threshold - would have started refusing files that read perfectly.
  The share was a guess standing in for a question the file answers directly.

  *What it does now.* `textnorm.declared_charset()` reads `<meta charset>`, the
  `<meta http-equiv ... content="...charset=...">` spelling and the XML
  declaration from the first 4 KiB, after stripping comments so a tutorial page
  that *shows* the tag declares nothing, and returns the name only when
  `codecs.lookup` knows it (so `gb2312`, `GBK` and `gbk` arrive as one spelling,
  and a misspelt name falls back to the old guess instead of raising).
  `textnorm.declared_reading()` returns the text only when those exact bytes
  decode with that codec without error.  `_decode_text` tries it as one more
  proof before the byte-share guess, and `sources.encoding_problem()` asks the
  same function - because a refusal that disagrees with the reader is the same
  mistake pointing the other way: a long GBK page scores 0.643 and would
  otherwise be refused as unreadable by a reader that now reads it fine.

  *Done - why it is now true.* `tests/test_declared_charset.py` (20 tests)
  covers the measured defect end to end (the GBK page verifies, `codes ==
  ["quote-found"]`, exit 0, where it used to be `quote-missing`/1), a fixture
  assertion that the byte share really was under the line, the same bytes with
  the declaration removed still refused as `source-encoding`, Big5 and
  Shift-JIS pages, five declaration spellings, the four things that are not
  declarations (no tag, inside a comment, an unknown codec name, past the
  window), the wrong-declaration direction (UTF-8 bytes labelled `gbk` still
  read as UTF-8; `declared_reading` returns `None`; `charset=utf-8` is left to
  the normal reader), and the two-reader agreement in both directions.
  `tests/test_one_reader.py` now names the two new helpers and pins their call
  sites, so a `declared_reading` used anywhere but inside the one reader fails
  that guard.  Nine mutations all go red - "the declaration is never read",
  "comments are not stripped", "the window is 1 KiB", "the whole file is
  searched", "an unknown codec name is returned anyway", "the declaration is
  believed without decoding cleanly", "a utf-8 declaration is acted on", "the
  reader ignores the declaration", "the refusal check ignores the declaration".
  The 1 KiB and whole-file mutations survived the first run because nothing
  pinned the window from either side; a 3 KiB-plus-header test and a
  past-the-first-kilobyte test were added until both died.

  *Not covered*: a document whose declaration is right but whose bytes are a
  mixture of two encodings (it fails the clean-decode test and falls back to the
  share); a `.txt` source, which has no declaration to read; and a `.bib`,
  deliberately left on the byte-share rule because a bibliography is mostly
  ASCII and a readable one must not be refused.

- [x] **P1 - a quotation that was never decoded was reported as a quotation the page does not have**

  **What was wrong.** A manuscript saved in GBK (what a Chinese Windows editor
  writes by default) is decoded by `textnorm._decode_text`, whose last line is
  `raw.decode("utf-8", errors="replace")`.  The fence line, the `quote:` label
  and every attribute are ASCII, so the block is still parsed; only the quoted
  words become U+FFFD.  Measured on a 111-byte GBK manuscript quoting a
  sentence its source prints verbatim on page 1:

      [high] quote-missing at manuscript.md:3 (c1): <replacement characters>
      -- quote not found in page.txt

  exit 1, after `scan` had already recorded the corrupted quote into
  `citevouch.lock.json`.  `check --use-recorded` - the command `action.yml`
  runs on every pull request - reported exactly the same thing.  `source-encoding`
  could not answer it: that check judges a *source* file, and this is the
  manuscript.  Two neighbours were silent in the same direction: `draft` said
  "no citations were found to propose them for (this command reads `[@key]` and
  `\cite{key}`)", pointing at the author's syntax when the syntax was correct,
  and `doctor` printed nine `[ok  ]` lines and exited 0 while the run it
  explains was accusing the author.

  **What it does now.** `textnorm.UNDECODED` names the character a decoder
  writes where it could not read a byte.  `verify` counts a claim whose quote
  holds one as **skipped, never missing**, reports `claim-not-decoded` (high)
  naming the file and the `iconv` line that fixes it, and does not search the
  page at all.  `doctor`'s `claims` check fails with the same reading and the
  same fix line.  `draft` says the file was never decoded, in the stderr line
  and in the proposals file, instead of blaming the citation syntax.
  `model.CODES`, `report.SARIF_RULES` and both README code tables carry the new
  code.

  **Why it is now true.** 17 tests in `tests/test_undecoded_quote.py`: the
  quote is not accused, the new code appears, the message names the file and
  `iconv`, the severity is `[high]`, the tally reads `1 claim — 0 verified, 0
  moved, 0 missing, 1 skipped`, and the recorded pass produces the identical
  code list.  Eleven mutations, all red: no guard, guard that refuses
  everything, missing skip count, missing finding, severity lowered, no
  `continue`, doctor ignoring the claims, draft counting zero, draft file
  keeping the old sentence, stderr keeping the old sentence, and a guard that
  also fires on U+FFFD in a *page*.

  Kept deliberately: a UTF-8 manuscript quoting a sentence the page does not
  print is still `quote-missing`; a page that legitimately holds U+FFFD does not
  trip the guard, because the guard is about the manuscript; and an eight-bit
  *source* file is still `source-encoding`, judged by
  `sources.encoding_problem`.

  **Not covered.** A GBK manuscript that holds **no** claim block still reports
  `no-claim-blocks` with no mention of the encoding - that sentence is already
  true ("this file has none"), it just does not say why, and adding the encoding
  reason to it is a separate change to the scan-level message.  `draft`'s
  "nothing on any page shares enough terms" line has the same shape.
- [x] **P1 - `draft` compared a sentence whose characters were never
  decoded, and blamed the page.**

  **What was wrong.** 0.22.54 taught `check` to refuse a quote made of
  replacement characters.  `draft` is a second reader of the same
  sentence and kept answering: on a GBK manuscript whose `[@paper]`
  survives the damage (whether it survives depends on byte alignment - a
  74-byte sentence swallows the `[` and the `@`), it proposed nothing and
  wrote

  ```
  <!-- line 1: paper - nothing on any page shares enough terms with the
       sentence (3 needed) -->
  ```

  Every word true except the subject: the comparison did run, and the
  words it compared were 96 replacement characters.  The source page,
  which prints the sentence verbatim, was never at fault.

  **What it does now.**  `draft` asks the *sentence*, not the file, before
  comparing it with any page, and the reason names the sentence, the
  characters that were its words, the manuscript, and the command:

  ```
  <!-- line 5: paper - the sentence this cites was never decoded: 67
       characters of it are replacement characters, so no page was searched
       for it - manuscript.md is not UTF-8. Convert it first, for example
       `iconv -f GBK -t utf-8 manuscript.md > utf8.md` -->
  ```

  **Why it is now true.**  `tests/test_undecoded_quote.py` grew
  `_cited()` (a manuscript whose citation survives, which is the only way
  into the branch) and `TestAFileCanBeHalfReadable` (one undamaged ASCII
  citation beside a destroyed Chinese one: the readable one is still
  proposed, the destroyed one is the only comment, and the summary line
  says `1 claim block(s) proposed ... 1 citation(s) left as comments`).
  Eight mutations were run and all die: no guard, counting the file
  instead of the sentence, an inverted condition, appending the reason
  without `continue`, dropping the count, dropping the file name,
  dropping the command.  A ninth idea was dropped rather than run because
  it is equivalent to the guard as written (recorded in the mutation
  script so the next round does not mistake it for a gap).

  Kept deliberately: a UTF-8 sentence that genuinely shares fewer than
  three terms with every page still gets the old reason, because for that
  file the page *is* the fact.

  **Not covered.**  A GBK manuscript with no claim block at all still
  reports `no-claim-blocks` without mentioning the encoding (the
  sentence is true, it just does not say why), and the same holds for
  `draft`'s `no citations were found` line when the citation's own `[`
  is eaten by a two-byte pair.  Both are scan-level messages; each needs
  its own change.

- [x] **P1 - a paper that quotes a replacement character was refused as a file that lost one**
  - **What was wrong.** The previous two releases taught three readers that a
    quotation holding U+FFFD was never decoded, and all three asked the text:
    `"\ufffd" in quote`. That is a different question from "did reading this
    file replace a byte?". A paper *about* text encodings prints the character
    on purpose. Measured on a lossless UTF-8 manuscript reading
    `Notepad wrote <U+FFFD> where the byte could not be decoded.`, with the
    source page printing the same sentence verbatim: `check` reported
    `[high] claim-not-decoded … manuscript.md cannot be read as UTF-8 without
    loss. Convert it first, for example \`iconv -f GBK -t utf-8 manuscript.md >
    utf8.md\``, `1 claim — 0 verified, 0 moved, 0 missing, 1 skipped`, exit 1;
    `doctor` reported `[FAIL] claims`; all three claim dialects agreed. Every
    word was false - the file decoded losslessly, nothing was lost, the advice
    would mangle it, and `find_in_pages` finds that quote on page 1 at tier
    `exact`. The guard was blocking the one comparison that would have
    succeeded.
  - **What it does now.** The decoder reports what the reading cost.
    `_decode_text_and_loss()` returns `(text, lost)`; `_decode_text()` is the
    text half. `read_text_and_loss()` / `read_text()` mirror that pair for
    files, `read_loses_bytes()` is the flag alone. `lost` is `True` exactly when
    a strict decode with the chosen codec raised. `verify`, `draft` and
    `doctor` require the flag **and** the character.
  - **Why it is now true.** `tests/test_quoted_replacement_character.py` has 15
    tests: the lossless case in all three dialects, the same case through the
    recorded pass, `draft` still proposing, `doctor` still passing, the GBK
    manuscript still refused by both `check` and `doctor`, a genuine miss still
    a miss, and one test per decoder branch - the BOM-less UTF-16 file the swap
    branch reads (it lost nothing), a declared-charset file (strict decode, no
    loss), and a truncated UTF-16 file (a trailing byte, so a loss - a case a
    replacement character can never reach). 12 mutations all red, including
    `_lost` always true, `_lost` always false, the flag never measured, one
    decoder branch reporting another branch's answer, and `read_text` decoding
    on its own again.
  - **Not covered.** `scan` still writes a decoded-as-mojibake quotation into
    the ledger without a word about the file, so an author who only runs
    `scan` sees a clean exit; and a manuscript with no claim blocks at all
    still reports `no-claim-blocks` without naming the encoding. Both need the
    scan-side report, which is a separate change.

- [x] **P1 - a manuscript whose byte count is even is read as UTF-16 and loses
  its claim fences**

  **What was wrong.** `textnorm._decode_text_and_loss` tried the sixteen-bit
  reading when `_noise(utf8_reading)` cleared two thresholds and
  `_noise(candidate) == 0`. A 114-byte GBK manuscript clears both: re-pairing
  its bytes produces clean-looking text in the same script, so the swap went
  through. Its two claim fences, its `quote:` keys and its `id=`/`source=`
  attributes are ASCII and were intact in the UTF-8 reading; the sixteen-bit
  reading erased every one of them. Measured on the built project:

  ```
  $ citevouch check manuscript.md
  [high] no-claim-blocks at manuscript.md: manuscript.md contains no claim
  blocks, so nothing was checked ... This file has none.
  ```
  `draft` on the same file said `0 claim block(s) proposed: no citations were
  found to propose them for (this command reads `[@key]` and `\cite{key}`)` -
  the author's citation style was correct - and `doctor` failed the `claims`
  check while blaming the claim blocks. A 113-byte twin of the same file, one
  byte shorter, was read correctly, so appending a single byte changed all three
  verdicts.

  **What it does now.** The swap is refused when it would shorten the longest
  run of printable ASCII (`_longest_printable_run` / `_keeps_the_structure` /
  `STRUCTURE_RUN = 8`). Claim fences, `quote:` keys and `[@key]` citations are
  such runs in every encoding an author saves them in, and re-pairing those
  bytes erases all of them. A genuine UTF-16-LE file never shows a run that
  long, because its letters sit between zero bytes. One shape stays undecidable
  and is written into the docstring rather than papered over: an 8-bit file of
  pure two-byte script, holding no ASCII at all, with an even byte count.

  **Why it is now true.** `tests/test_even_length_manuscript.py` (20 tests)
  pins both halves: the fences survive at both length parities, the two parities
  decode to the same text plus the appended byte, no other 8-bit family
  (big5 / shift_jis / cp1251 / cp1252) is swapped, and genuine UTF-16-LE
  manuscripts - Chinese, Russian, single-line, fenced - still decode. The
  end-to-end tests assert the even-length project reports `claim-not-decoded`
  and never `no-claim-blocks`. Ten mutations all go red: the veto removed, made
  always-refusing, made always-accepting, the threshold moved to 1 and to 40,
  the short-run escape dropped, the comparison ignoring the candidate, the run
  counter zeroed, the character class widened to all bytes, and the loss flag
  re-attached to the swap.

  **Not covered.** A manuscript that is not UTF-8 *and* writes no ASCII at all
  *and* has an even byte count is still ambiguous, and the reader picks UTF-16;
  the docstring says so. The `scan` pass still records a mojibake quotation in
  the ledger without complaining (the guards live in `check`/`draft`/`doctor`).

- [x] **P1 - `draft` read a citation the author was displaying as one they were making**
  - What was wrong: `draft` read citations from the raw manuscript, so a `[@key]`
    inside a fenced block, a code span, an HTML comment or an indented block - a
    specimen of the syntax - was reported as a real citation. On a manuscript whose
    page prints the sampled sentence word for word, with `ghost` a key that has no
    local file, all six shapes produced `line 2: ghost - no local file: not in
    sources.toml, no `file` field in the bibliography, and no file named after the
    key`. Two of the shapes did worse: ``` and `<!--` travelled into the
    sentence compared with the page, so an identical sentence stopped matching and
    the paragraph dropped from `1 claim block(s) proposed (1 verbatim)` to `0 claim
    block(s) proposed (0 verbatim)` at medium confidence.
  - What it does now: `src/citevouch/display.py` blanks every displayed region and
    keeps the text's length and its newlines exactly. `draft` masks once and reads
    both the citation sites and the sentences from the masked text, so displayed
    keys are not cited and display markers are not words. A `> ` blockquote is still
    prose, and a `[@ghost]` in an ordinary sentence is still reported missing.
  - Why it is now true: `tests/test_displayed_citations.py` has 28 tests - six
    displayed shapes produce no note and lose no verbatim match; the mask keeps its
    length and every newline offset; the fence rules are checked directly on the
    mask (wrong character, too few characters, a short line inside a long fence, a
    line with text after the run, an unclosed fence running to the end of the file,
    the closing line itself); and an indented list continuation stays prose. Eleven
    mutations were run against this file and all eleven are red. Two of them were
    only killed after the tests below were added, because the end-to-end fixtures
    happened to cover the same characters twice: `a fence closes on too few
    characters` needed a four-backtick fence with no other run of four in the file,
    and `the last line of a fenced block is left out` needed a closing run longer
    than the opening one so no code span could pair them.
  - Not covered: LaTeX `\verb`, `\lstinline` and `\mintinline`. `to_text` restores
    their literal spelling into the converted text, so `\verb|\citep{ghost}|` is
    still read as a real citation by `draft`. That is the same defect in a different
    module and is left as its own entry.

- [x] **P1 - a LaTeX command shown with `\verb` was read as a citation the author made**

  **What was wrong.** `latex.to_text` drops an inline-verbatim body before the
  citation patterns run and puts the characters back afterwards, because TeX prints
  them (`50\verb|%|` is a percent sign).  The restored characters come back in LaTeX
  spelling, and `draft` reads the converted text: `\verb|\citep{ghost2021}|` came
  back as `\citep{ghost2021}` and `citation_sites` recognised it.  Measured on a
  manuscript with the example beside a real `\citep{paper}`:
  `1 claim block(s) proposed (0 verbatim), 3 citation(s) left as comments`, and the
  comment `line 3: ghost2021 - no local file: not in sources.toml, no file field in
  the bibliography, and no file named after the key` - an author told their own
  example has a missing paper.  A specimen in a paragraph above a sentence also
  stopped that sentence matching, because the restored example text travelled into
  the sentence `draft` compared.

  **What it does now.** `latex.to_text_and_display()` returns the converted text plus
  the span of each restored body; `latex.to_text()` is its first half, so the two
  cannot drift.  `display.blank()` blanks exactly those spans, and `draft` masks
  them before it reads either the citations or the sentence.  The bodies go back
  **last**, after the whitespace passes - their markers hold no space and no newline,
  so no pass touched them and no pass moved them.  Measured after:
  `1 claim block(s) proposed (1 verbatim), 0 citation(s) left as comments`, one
  `paper` block at `confidence: high`, no `ghost2021` note.

  **Why it is now true.** `tests/test_latex_displayed_citations.py` (20 tests) covers
  all five inline-verbatim commands (`\verb`, `\verb*`, `\lstinline`,
  `\mintinline{tex}`, `\lstinline[language=TeX]`), the literal characters that must
  still reach the output (`50%`, visible backslashes inside a `\verb` body), the
  spans pointing at the bodies inside the returned string, the whitespace-collapsing
  case where a span could drift, and the prose that must keep its real citations.
  `tests/test_displayed_citations.py` grew four tests for `display.blank` taking
  spans that do not fit.  12 mutations, all red: 11 died on the new tests and the
  last (`display.blank` not clamping) only died after those four were added - a
  negative start wrapped around to the end of the string and blanked prose the
  author wrote, which no end-to-end fixture happened to exercise.

  **Not covered.** A body inside the very sentence that cites the real page still
  blanks a hole in that sentence, so the sentence stops matching word for word and
  falls back to the medium-confidence passage; Markdown inline code has the same
  behaviour.  Fixing it means comparing against the text with holes rather than
  against the printed characters, which is a different change.  A `\verb` body
  inside a claim block's `quote:` is likewise blanked in the claim text.


- [x] **P1 - the markdown report left out the claims it skipped**

  **What was wrong.** `render_text` and `render_json` both print
  `result.skipped`; the markdown summary row - the one `action.yml` puts in a
  pull-request comment, the surface a reviewer actually reads - printed
  `checked`, `verified`, `moved` and `missing` and stopped. Measured on a claim
  whose source file exists but holds no text:

  ```
  --format text      citevouch: 1 claim — 0 verified, 0 moved, 0 missing, 1 skipped
  --format json      {"checked": 1, ..., "skipped": 1}
  --format markdown  **1** claim · **0** verified · **0** moved · **0** missing
  ```

  The run exits 1 over that claim and the row accounts for none of it. Nothing
  in the row is false - those are real counts of real categories - but a reader
  adds up what is on the page, gets zero, and concludes the document holds
  nothing. A skipped claim was read and then deliberately not judged, which is
  the opposite of it not existing.

  **What it does now.** The row carries the fifth count when it is not zero,
  exactly as the text tally does, so a clean report keeps the row it has always
  had. `tests/test_markdown_summary_matches_the_others.py` asserts the four
  counts add up to `checked` - one assertion that catches both a missing
  category and a duplicated one.

  **Why it is now true.** 7 tests, 8 mutations, all red: never printing the
  clause, always printing it, printing `missing` twice, printing `verified` as
  skipped, gluing the clause to the `unrecorded` row instead, removing it from
  the text tally too, dropping `moved` from the markdown row, and counting
  blocks in a row that says claims. The last one survived the first round -
  it only dies once a test pins the two rows to their two different nouns.
  The demo red line is unchanged: `5 claims — 4 verified, 0 moved, 1 missing`,
  `worst severity: high`, exit 1.

  **Not covered.** The SARIF writer never carried a tally and still does not;
  it has a fixed shape and callers read `invocations` there instead. Nothing
  here makes a fifth renderer appear - if one does, it starts without the
  clause like this one did.

- [x] **P1 - a `\begin{...}` line's arguments were pasted into the sentence**

  **What was wrong.** `latex._convert` had a rule for commands that take
  arguments - `_SKIP_FIRST_ARGUMENT`, `_DROP_ALL_ARGUMENTS`,
  `_SKIP_ARGUMENT_COUNT` - and no rule at all for environments, which it
  treated as a name to drop and a body to keep. So the argument became the
  first word of the next sentence:

  ```
  \begin{spacing}{1.5}
  We collected 40,688 examples from the corpus ... \citep{paper}
  \end{spacing}
  ```

  converted to `'1.5
  We collected ...'`. `draft` glues a figure to the following line because
  there is no full stop between them, and proposed

      quote: |
        1.5 We collected 40,688 examples from the corpus of written English and then filtered them by hand.

  with `confidence: medium` where the same sentence outside the environment
  earns `high`. Pasted back, the block is `[high] quote-fuzzy` **and**
  `[high] number-absent-in-quote: the quote says 1.5 but page 1 of the source
  does not contain that number` - the tool asking the author about a number
  the author never typed, in a sentence the source prints verbatim.

  Measured leaks before the fix: `minipage`, `wrapfigure`, `wraptable`,
  `multicols`, `multicols*`, `subfigure`, `subtable`, `adjustbox`, `spacing`,
  `list`, `column`, `tcolorbox`, `figure`, `table`, `algorithm` and
  `thebibliography`.

  **What it does now.** Three tables say what a `begin` line consumes:
  `_ENVIRONMENT_ARGUMENTS` (counted braced groups), `_ENVIRONMENT_OPTIONAL`
  (a leading `[..]` placement or list style) and `_ENVIRONMENT_OVERLAY` (a
  beamer `<..>`). `_past_environment_arguments` applies them only to
  `begin`; `theorem`, `lemma`, `corollary`, `proposition`, `remark` and
  `proof` are deliberately absent from the optional set because their
  `[Main result]` is the author's own words.

  **Why it is now true.** 30 tests, 10 mutations, all red. Three of them
  survived the first round and each needed a test written for it: spaces
  between environment name and argument, an argument that never closes (the
  group must be abandoned, not the file), and `\end{...}` (which takes no
  arguments at all - a braced group after it is the author's). The
  space-skipping one only died once the test used *two* arguments with a
  space before the second. The demo red line is unchanged:
  `5 claims — 4 verified, 0 moved, 1 missing`, `worst severity: high`, exit 1.

  **Not covered.** The tables say how many groups to skip, not what is inside
  them, so an argument that is itself a macro (`{\linewidth}`, `{\colwidth}`)
  is skipped wholesale rather than expanded - which is what the prose wants,
  but it means a `\begin{minipage}{\foo{1.5}}` still leaves the body alone only because the
  group scan is balanced. Sectioning parameters (`titlesec`), keyval lists
  outside `adjustbox`, and counter names are the same family and are still
  unhandled.
- [x] **P1 - a citation that opens a sentence was read as a bare word**

  `solid` `src/citevouch/latex.py`.  `CITATION_NAMES` carried natbib's
  seven capitalised commands (`\Citet`, `\Citep`, `\Citealp` and four more) and
  **none** of biblatex's, while listing both families' lowercase ones.
  A capitalised citation command is not decoration: an author writes it when
  the citation opens a sentence, which is the first citation anyone reading
  the paper sees.

  Measured before the fix:

  ```text
  \autocite{paper}   ->  '[@paper]'        \Autocite{paper}   ->  'paper'
  \autocites{a}{b}   ->  '[@a; @b]'        \Autocites{a}{b}   ->  'ab'
  ```

  The key was pasted into the prose as a word, and `draft` then reported
  `0 claim block(s) proposed: no citations were found to propose them for`
  about a manuscript whose first sentence cites a paper.

  What it does now: both families appear in `CITATION_NAMES`, and their
  plurals in `MULTI_CITATION_NAMES`, each group spelled out rather than
  derived by upper-casing a lowercase name (`\Cite` is not natbib's and
  `\Nocite` is not biblatex's, so a derived table would claim two commands
  nobody writes).  `\Autocite{paper}` now converts to `[@paper]` and reaches a site.

  Why it is now true: `tests/test_citation_names.py` grows 16 tests - the two
  pinned name lists now carry the biblatex capitals, and a new
  `TestACitationThatOpensASentence` class checks that each of the seven
  singular and seven plural commands reaches a site, that the plural ones
  reach *every* source, that a sentence-initial citation proposes a block
  end to end, and that the capital and lowercase forms of seven commands
  give the same answer.  113 tests in the file, 3323 in the suite.
  Five mutations are caught (drop the whole biblatex group, keep only one
  name, drop the plural group, spell the plurals lowercase, drop the natbib
  group).  A sixth - flipping `key=len, reverse=True` to `False` - was
  measured equivalent over all 30 names x 3 call shapes and is recorded in
  the harness rather than counted as a survivor.

  Not covered: thirteen lowercase biblatex commands are still missing
  entirely - `footfullcite`, `citenum`, `citetitle`, `citedate`, `citeurl`,
  `citename`, `notecite`, `pnotecite`, `fnotecite`, `citefield`,
  `citealias`, `citepalias`, `citetext`.  All convert to a bare key and
  produce no site.  Listing them from a table rather than from observation
  is the same mistake this round fixed, so they need the same treatment:
  one at a time with an end-to-end case each.

- [x] **P1 - a bibliography message named a ledger that no run had written**

  **What was wrong.**  `verify` chose the noun in a `bib-key-missing` finding
  from one variable with two possible values: the file it had just re-read
  (`the bibliography`), or the file the ledger recorded (`the bibliography the
  ledger recorded`).  `check --bib` reaches the same line by a third path - it
  scans the manuscript and the bibliography to answer this one run and writes
  no ledger - and got the second sentence.  On a project that had never been
  scanned:

  ```text
  [high] bib-key-missing at manuscript.md:1 (c1): claim c1 cites
        'knuth2020', which is not in the bibliography the ledger recorded
  ```

  `citevouch.lock.json` did not exist before that command and did not exist
  after it.  The finding was right; the noun pointed at a document nobody had
  written, so an author who went looking for it would find nothing.

  **What it does now.**  Three cases, one per source: `the bibliography this
  run read` when `check --bib` scanned it, `the bibliography` when a recorded
  pass re-read the file, and `the bibliography the ledger recorded` only when
  the ledger is old enough to carry entries without the file that produced
  them.

  **Why it is now true.**  `tests/test_bib_message_names_the_file.py`, 5 tests:
  the fresh run's sentence, the recorded pass's sentence, the legacy ledger's
  sentence, the `source=`-without-`ref=` wording, and a deleted bibliography
  that must stay a `source-missing` rather than become a missing key.  The
  first test also asserts `(root / 'citevouch.lock.json').exists() is False`,
  so the premise of the complaint is pinned, not just its wording.  5
  mutations: four died (both branches answer with the ledger, both answer with
  the plain file, the fresh branch answers with the ledger, the fresh branch
  is unreachable).  One was measured equivalent - guarding the first branch
  with `and not fresh` changes nothing, because `reread_entries` is only
  filled inside `if not fresh:` - and is recorded as equivalent rather than as
  a survivor.

  **Not covered.**  The other two `bib-*` sentences (`bib-field-duplicate`,
  `bib-key-unused`) were not re-read for a third source; only the key-missing
  sentence was shown to have one.


- [x] **P1 - a bibliography that holds only macros was reported as unreadable prose**

  What was wrong: `parse_bib` ended with a single branch for "no entries came out", and it wrote the sentence for the worst reason - not one entry could be read, the file is probably in the wrong encoding, convert it.  Two very different files reach that branch.  With a shared `macros.bib` (two `@string definitions) beside `refs.bib` (every key the manuscript cites), which is what multiple `--bib` flags are for:

  ```
  $ citevouch check manuscript.md --root . --bib macros.bib --bib refs.bib
  [high] bib-unreadable at macros.bib:1: not one entry could be read from
         macros.bib, so every reference in the manuscript is unchecked
         against a bibliography that is effectively empty.  Often the file
         is not the encoding it claims: a UTF-16 save read as UTF-8 gives a
         replacement character and a NUL between every letter.
  exit 1
  ```

  The file is ASCII, it parsed completely, both macros came through, and no reference went unanswered.  The author is sent to change an encoding that is already right, at the severity reserved for findings a reader must not ignore.

  What it does now: the branch asks the question it can answer - is there text this parse could not account for?  A gap between entries, or an entry that never closes, is that answer and keeps `bib-unreadable`.  Definitions alone are not, and get a new `bib-no-entries` (low) that says what the file does hold (`2 definitions`) and points at `--bib macros.bib --bib refs.bib`.  A file with macros *and* stray prose stays loud and now says how many definitions did parse.  `bib-no-entries` is added to `CODES`, the SARIF rules and both README code tables.

  Why it is now true: `tests/test_bib_definitions_only.py` (9 tests) covers the two-flag set-up, a `@preamble`-only file, an `@comment`-only file, prose that is not BibTeX (still `bib-unreadable`), and macros plus stray prose (still loud, and now counted).  Eight mutations, all red: always blame the encoding, never blame it, definitions not counted, unparsed headers no longer counted, unclosed entries no longer counted, the count dropped from the sentence, the workaround dropped from the sentence, `bib-no-entries` reported as high.  The last two survived the first run and were killed by pinning `2 definitions` and `--bib macros.bib --bib refs.bib` in the test.

  Not covered: `draft --bib` uses the same `parse_bib`, so it now also reports `bib-no-entries` for a definitions-only file; no test pins that verb yet.  A file that holds definitions and an *unclosed* entry is still `bib-unreadable` (correct), but a file whose only content is `@comment` is reported low even though nothing in it was lost - that is the intended reading of the code, not an oversight.


- [x] **P1 - a `macros.bib` passed beside `refs.bib` did nothing, and the message
  said the opposite**

  **What was wrong.** `--bib` may be given more than once, and the shape that
  needs it is a shared macros file beside the entries that use its `@string`s.
  Each file was parsed alone, so `journal = acm` in `refs.bib` was reported as
  an undefined macro while the definition sat on line 1 of the other file, and
  the sentence named the one thing that was not true: "no `@string` defines
  them".  Measured for all three orders -- macros first, refs first, refs alone
  -- identical:

  ```text
  [medium] bib-macro-unknown at refs.bib:1: knuth1984: 1 undefined macro in 1
  field ('journal' uses 'acm'); no @string defines them, so each name was kept
  as literal text
  ```

  **What it does now.** The group of `--bib` files is parsed as one
  bibliography.  `bibtex.parse_bib_group` reads the group twice: the first pass
  collects every `@string`, the second parses each file against all of them,
  because which flag came first is not a fact about the bibliography.
  `parse_bib` grew a `known_strings` parameter for the second pass.  All three
  readers moved over together -- `scan`, `draft`, and the recorded pass in
  `verify`, which used to disagree with the run that wrote the ledger.

  **Why it is now true.** `tests/test_bib_macros_across_files.py` (9 tests) pins
  the group pass itself (`parse_bib` takes and returns the strings), both flag
  orders end to end, the recorded pass reading the same group, and `draft`.  The
  reverse direction is pinned too: a macro nobody defines is still
  `bib-macro-unknown` with the name quoted, a lone `refs.bib` still reports its
  macro undefined, and a definitions-only file is still `[low] bib-no-entries`
  at exit 0.  Nine mutations, all red: each reader falling back to parsing files
  alone, the group pass never collecting strings, keeping only the last file's
  strings, `parse_bib` ignoring what it was given, the second pass not being the
  one returned, an undefined macro going silent, and a definitions-only file
  losing its low severity.

  **Not covered.** A macros file named through a Zotero/biblatex config rather
  than on the command line is still not discovered; the group is exactly what
  the `--bib` flags name.

- [x] **P1 - two `--bib` files that define one macro differently picked a winner
  silently**

  **What was wrong.** The group of `--bib` files shares one `@string` table, and
  a repeated macro name was simply overwritten in flag order.  Measured with
  `a.bib` defining `j = "Journal A"` and `c.bib` defining `j = "Journal C"`,
  with `e.bib` using `j`:

  ```text
  a.bib c.bib e.bib -> journal = 'Journal C'   (no finding)
  c.bib a.bib e.bib -> journal = 'Journal A'   (no finding)
  ```

  So which work the entry named depended on the order of two flags, and nothing
  said so.  This landed the same round as the group parse itself, which is what
  made the conflict possible.

  **What it does now.** `bibtex.parse_bib_group` compares definitions as it
  collects them and reports `bib-macro-redefined` (high), naming the macro, both
  values and both files, instead of quietly keeping the last one.

  **Why it is now true.** `tests/test_bib_macro_redefined.py` (11 tests) pins
  the finding in both flag orders, the message naming both files and both
  values, a three-file disagreement naming all three, and the severity reaching
  `[high]` end to end.  The reverse direction is pinned too: an identical
  repeat in two files is not a conflict, one file redefining its own macro keeps
  its old "later wins" answer, and a single file with a repeated macro is
  unchanged.  Seven mutations, all red: never reporting, reporting identical
  repeats, dropping the conflicts instead of attaching them, a message with no
  file or no value, the severity dropping to medium, the conflict check keyed on
  the wrong thing, and the earlier side of the conflict reported as the later
  one.  Two survivors in the first pass were rewritten: one was an equivalent
  mutation (a no-op expression), the other (`known.clear()`) still detected the
  conflict, so both were replaced with mutations that actually change the
  finding.

  **Not covered.** A macro redefined inside one file still keeps "the later
  definition wins" and says nothing; that shape had an answer before `--bib`
  could be given twice, and changing it is a separate decision.

- [x] **P2 - two macros that disagree between the same two files were one
  finding**

  What was wrong: `bib-macro-redefined` (new in 0.22.66) wrote every conflict
  as `path=<the later file>, line=1` and attached them all with
  `parsed[0].findings.extend`. On `a.bib` defining `j = "Journal A"` and
  `n = "Note A"`, `b.bib` redefining both on lines 5 and 8, and `refs.bib`
  using both, the run produced two findings that were the same coordinate, and
  `cli._deconflict` keys on `(code, claim_id, path, line)`:

  ```text
  raw findings:          2  (both at b.bib line 1)
  after _deconflict:     1
  ```

  The author was told about `j`, fixed it, re-ran, and met `n` for the first
  time. Line 1 of a `.bib` is almost always a comment, so the coordinate also
  sent them to the wrong place.

  What it does now: `BibResult.string_lines` records the line each `@string`
  was written on, and the conflict carries the winning file's line:

  ```text
  [high] bib-macro-redefined at b.bib:5: @string 'j' is defined as
  'Journal A' in a.bib line 1 and as 'Journal B' in b.bib line 5; ...
  ```

  Each finding is attached to the result for the file that won it, so a caller
  that groups results by file gets the right answer.

  Why it is now true: `tests/test_bib_macro_redefined.py` grew seven tests -
  two conflicts are two findings, the deconflict pass keeps both, each points
  at the line that wrote it, the message names both lines, the check prints two
  lines, every finding is attached to its own file, and the earlier side names
  its own line. Eight mutations, all red: dropping the line back to 1, dropping
  the earlier line from the message, dropping the later line, attaching to the
  first result, attaching to the last, never recording the line, never reading
  it back, and recording 1 for the earlier side.

  Not covered: a single file that defines one macro twice still takes the last
  definition silently - that shape has no second file to blame and is recorded
  separately.

- [x] **P1 - a table claim whose page cell held a range was not read at all**

  `_TABLE_CLAIM` read the `page` column as `\d+|-|`, so a row whose
  author wrote `1-2` matched no claim at all - it was not a claim that had
  gone wrong, it was not a claim.  Measured on a one-page source whose
  quote is verbatim on page 1:

  ```
  | c1 | paper | 1   | <quote> | full sentence |
  | c2 | paper | 1-2 | <quote> | full sentence |
  ```

  gave `1 claim - 1 verified, 0 moved, 0 missing`, `worst severity:
  info`, exit 0, and no line anywhere mentioned the second row.  The range
  row on its own was worse: the file looked empty and the run said
  `[high] no-claim-blocks ... This file has none.`

  What it does now: the page cell admits a number or a run of numbers
  joined by a dash, including the en and em dashes a word processor
  substitutes.  Each of those still fails `int()`, so the row is read and
  the hint the tool cannot apply is what it complains about -
  `[medium] page-unreadable ... the hint is ignored and the quote will be
  located by search`, with the claim verified anyway.  That is the answer
  the fence dialect has given for the same value since it was written.

  Why it is now true: `tests/test_table_page_range.py` adds 13 tests -
  the range row is a claim, the range row alone is not an empty file, five
  spellings of a range are read, the hint is what gets refused and not the
  claim, a plain number still sets the page, the tally does not count a
  refused hint as a skip, and a header row and a separator row are still
  not claims.  Putting the old `\d+|-|` cell back turns 8 of them red.
  Six mutations of the new cell are all caught: the old alphabet, the dash
  dropped, the en and em dashes dropped, the interior space dropped,
  any-text, and digit-only.

  Not covered: `iv` and `iv-vii` still match no claim at all, so a table
  row with a roman-numeral page is still silently absent.  Roman numerals
  are not numbers this tool can compare, and widening the cell to reach
  them is the change that would break the header-row test.

- [x] **P2 - a results table with a numeric column reads as a claim row**

  What was wrong: any five-cell row whose third cell was a bare integer
  was a claim.  Measured on a manuscript holding a real results table:

  ```
  | model | setting | 84 | We report the mean over five seeds | note |
  |-------|---------|----|------------------------------------|------|
  | bert  | base    | 84 | 88 | 90 |
  ```

  `check` printed two `[high] source-missing` lines naming `source='setting'` and `source='base'`, exit 1.  Worse, when the header's prose
  cell happened to appear on the page it printed
  `[info] quote-found at manuscript.md:3 (model): quote found on page 1`
  - a column label certified as a verified quotation.

  What it does now: a row is a header when it is shaped like a table
  claim *and* the line under it is a GFM delimiter row (dashes with
  optional alignment colons, at most three spaces of indent, nothing else
  on the line).  Such a row is named with the new `claim-table-header`
  code (medium) and is not judged against any source.  Data rows under it
  are still read; a row with no delimiter under it is still a claim.

  Why it is now true: 20 tests in `tests/test_table_header_row.py` and 12
  mutations, all red.  Two mutants survived the first round and each was a
  real gap - `any row above a dash line counts` (the helper never asked
  whether the line was table-shaped) and `the header finding names no
  line` (the one test pinned the header at line 1, so a finding that
  always said "line 1" could not fail).  Each got a test and the round
  closed at 12/12.

  Not covered: the delimiter row must be *directly* under the header, so a
  table whose header and delimiter are separated by a blank line still
  reads its header as a claim - and that is deliberate, because Markdown
  does not make a table out of it either.  Tables wider or narrower than
  five cells are out of scope: the dialect only binds five.

- [x] **P1 - a heading or a horizontal rule under a one-line claim comment was read as the quote**

  What was wrong: `_continues_one_line_html` ends an already-closed
  `<!-- claim ... -->` block at a blank line or where the next construct
  starts.  The construct list held a fence, another comment and a table
  row.  A heading and a thematic break were not on it, so both joined the
  quote and the run reported

  ```
  <!-- claim: c1 source=paper page=1 -->
  ## Methods
  -> [high] quote-missing at manuscript.md:1 (c1): ## Methods — quote not found
  ```

  and, for `---`, the same sentence with `---` in place of `## Methods`.
  Both send the author to their PDF to look for a heading and a rule their
  source never printed, over a block that carries no quote at all.

  What it does now: two patterns join the list.

  ```
  _ATX_HEADING = re.compile(r"^[ \t]{0,3}#{1,6}(?:[ \t]|$)")
  _THEMATIC_BREAK = re.compile(r"^[ \t]{0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$")
  ```

  The indent cap and the required space after the hashes matter:
  `#hashtag` and `--- and then some words` are still prose, and `--` is
  still the quote.  A block left with no quote now reports
  `claim-uncheckable`, which names the author's own file.

  Why it is now true: 15 tests in
  `tests/test_one_line_comment_boundary.py`, and 10 mutations all red.
  The first mutation round left two alive - heading allows any indent,
  break needs only two characters - and each got a test of its own
  (`test_a_deeply_indented_hashtag_is_a_code_block`,
  `test_two_dashes_are_not_a_break`) before the round closed at 10/10.

  Not covered: the inventory is still not closed.  `</div>`, `<br>` and
  `![img](x.png)` after a one-line comment are still read as the quote.
  They are HTML blocks rather than Markdown block starters, so they need
  the same treatment from the other direction, and this fix did not do
  it.  The results-table item it pointed at is closed further down this file.

- [x] **P1 - a file whose only table row was the table's header checked nothing, and exited 0**

  Found by running an *old* shape through the *new* door: 0.22.70 added
  `claim-table-header` for a row above the `|---|` delimiter, and the code was
  fully tested - but nothing asked what the pre-existing rule would think of it.

  `ParseResult.nothing_to_check` (in `src/citevouch/manuscript.py`) decided
  whether a run checked anything with "no claims, and no finding whose code
  starts with `claim-`". The prefix was a shorthand for a property nobody had
  written down: every such code used to describe a block the author wrote and
  the parser could not use. A header row is not a block, so this manuscript:

  ```
  | model | setting | 84 | We report the mean over five seeds. | note |
  |-------|---------|----|------------------------------------|------|
  ```

  printed `[medium] claim-table-header ...`, `0 claims — 0 verified, 0 moved, 0
  missing` and **exited 0**, while an empty manuscript exited 1 with
  `no-claim-blocks`. Both checked nothing; the CI gate passed for one of them.

  The second reader of the same lines disagreed too. With the exit code fixed,
  `scan._no_claim_blocks_finding`'s near-miss list still pointed at the header
  row and said it was "inside a blockquote, a list item or an indent, where
  Markdown renders it as a code sample rather than a table" - about a row at the
  left margin.

  What it does now: `nothing_to_check` names `claim-table-header` as the one
  `claim-` code that does **not** explain a run, with the reason written beside
  it, and `scan` skips header rows in the near-miss list so both readers agree.

  Why it is now true: `tests/test_header_only_file.py` (10 tests) covers the
  header-only file exiting 1 for `check` and `scan`, the empty file still saying
  the same thing, a refused block still explaining itself without a second
  finding, the header finding no longer being read as an explanation, and the
  near-miss sentence no longer naming a construct that is not there (both when
  the header stands alone and when a data row follows). Five mutations, all red:
  every `claim-` code explaining the run, nothing explaining the run, everything
  explaining the run, `scan` pointing at the header, `scan` skipping every row.
  The fifth survived at first - my mutation runner only ran the new test file,
  and `tests/test_no_claims.py` was the suite that caught it; widening the runner
  to include it made all five red.

  Not covered: a header row separated from its delimiter by a blank line is not
  a table at all (documented in `_is_header_row`), so that row is still read as
  a claim.

- [x] **P1 - a table's delimiter row was read as a claim named `-`**

  What was wrong: GFM lets a delimiter cell be a single dash, so `|-|-|-|-|-|`
  is a legal delimiter row for a five-column table. It is also a five-cell row
  whose third cell is `-`, which is exactly what `_TABLE_CLAIM` asks for, so a
  correct table produced `[high] source-missing at manuscript.md:2 (-): claim -
  names source='-' but no entry in sources.toml` and `2 claims - 1 verified, 0
  moved, 1 missing`, exit 1. `_-_-_`, `--`, `:-`, `-:` and `:-:` were already
  fine: none of their cells is a bare `-`.

  What it does now: four readers refuse a delimiter row, each measured on its
  own - the claim reader in `parse_manuscript`; `_unread_findings`, which had
  been calling it a claim block "inside a blockquote, a list item or an indent"
  (three things it is not); `scan`'s near-miss list, which said the same thing
  from another command; and `_is_header_row`, which would have called a
  delimiter the header of the row below it.

  Why it is now true: `tests/test_delimiter_row.py` (11 tests) and 6 mutations,
  all red: no claim-reader refusal, no unread refusal, no scan refusal, every
  dashed row refused, every row skipped, and a delimiter allowed as a header.
  Two survived the first round. "Every row is skipped" was written against the
  wrong reader and became `scan: every row is skipped`. "A delimiter can be a
  header" looked equivalent - the claim reader refuses a delimiter before
  `_is_header_row` is asked - until two adjacent delimiter rows made the guard
  observable, which is now the test that pins it.

  Not covered: `_is_header_row` still assumes the delimiter immediately follows
  its header, so a blank line between the two makes the header a claim again.
  That is the open item noted above under the header-only fix.

- [x] **P1 - a table claim whose page cell said `p. 3` was deleted, not read**

  What was wrong: the table dialect reads the page cell with a pattern, so a
  value the pattern does not know never reaches `int()` - the row stops being a
  claim. A page hint is prose as often as it is a number, so
  `| c1 | paper | p. 3 | We collected 40,688 examples from the corpus. | note |`
  printed `[high] no-claim-blocks ... This file has none`, exit 1, over a file
  holding one claim whose quote the page prints verbatim. `1,2`, `pp. 3-4`,
  `page 5` and `pages 6-7` did the same.

  What it does now: the cell admits an optional `p`/`pp`/`page`/`pages` prefix
  with its full stop, then digits separated by space, comma, dash, en dash or em
  dash, or a bare dash for "no hint", or nothing. A cell holding any other
  letter is still not a page, which is what keeps a results table's third column
  from turning five-cell rows into claims - that was the previous defect, and
  both halves are real.

  Why it is now true: `tests/test_table_page_spellings.py`, 25 tests, and 10
  mutations, all red. One test asserts the fence and table dialects answer the
  same value the same way, which is the property that was missing: the fence
  dialect had parsed `p. 3`, refused it with `page-unreadable`, and verified the
  claim, for releases.

  Not covered: roman numerals. `iv` and `iv-vii` still match nothing, so a table
  claim with a roman page hint is still invisible - the same class of defect
  this item closed, left open because there is no rule here that both dialects
  would agree on.

- [x] **P2 - a roman-numeral page hint deletes a table claim row**

  What was wrong: `| c1 | paper | iv | We collected ... | note |` matched no
  claim at all. The file reported `no-claim-blocks ... This file has none` when
  that was its only row, and silently dropped the row when it had company. The
  fence dialect answered `page=iv` with `page-unreadable`, medium, and verified
  the quote anyway - so one dialect named an ignored hint and the other said the
  file was empty.

  What it does now: the page cell admits a roman numeral and lets `int()` refuse
  it, exactly the way it already refuses `p. 3` and `1,2`. The alphabet is i, v,
  x and l, each run has to be a canonical numeral, and a run joined by a dash, an
  en dash, an em dash or a comma is one hint - so `iv`, `IV`, `iv-vii`,
  `iv, vii`, `p. iv` and `pp. iv-vii` are all read, while `ill`, `mix`, `class`,
  `civic`, `live`, `x-ray`, `iv.` and a cell holding `m` or `c` stay words.

  Why it is now true: `tests/test_table_roman_page.py`, 42 tests, and 9
  mutations, all red - no roman branch, any letters, any run of i/v/x/l,
  lowercase only, no comma separator, one numeral never a run, m and c admitted,
  non-canonical numerals, branch unreachable. One test asserts the fence and
  table dialects return the same code for the same value, which is the property
  whose absence caused three defects in a row (numbers, then the prose around
  them, then numerals).

  Not covered: a page numbered in the hundreds in roman numerals. `m` and `c`
  are left out on purpose, because a table's third column is far more likely to
  say `class` or `done` than to be page `mcmxc`; that cell is still silently
  dropped, and it is the same shape as the defect this item closed.

- [x] **P1 - an HTML block under a one-line claim comment was read as the quote**

  What was wrong: the one-line comment dialect ends where the next construct
  starts, and that list held a blank line, a fence, another comment opener, a
  table row, an ATX heading and a thematic break.  HTML was missing, so a claim
  comment written directly above a closing tag was read with the tag as its
  quote.  Measured in a project whose page prints the quoted sentence:

      <!-- claim: c1 source=paper page=1 -->
      </div>
      -> [high] quote-missing at manuscript.md:1 (c1): </div> - quote not found
         (too short for a fuzzy comparison) in page.txt

  The same for `<div class="note">`, `<br>`, `<hr>`, `<table>`, `<details>` and
  an image line.  Each one sent the author to their PDF looking for a tag their
  source never printed, when the block holds no quote at all and the honest
  finding is `claim-uncheckable`.

  What it does now: the boundary rule is CommonMark's HTML block types - a
  block-level tag name opens a block whether or not prose follows it on the
  line, a complete tag alone on a line opens a block, and
  `<script>`/`<pre>`/`<style>`/`<textarea>` open a block.  A tag inside a
  sentence stays in the sentence: `a <b>bold</b> word` is prose, `<divs>` is not
  a tag name, and `5 < 7 and 8 > 2` is arithmetic.

  Why it is now true: `tests/test_html_block_boundary.py`, 46 tests, and 10
  mutations, all red.  Three of the ten survived the first suite and only died
  after fixtures with prose after the tag were added - the alone-on-a-line form
  and the block-level name list look identical until a line puts text after the
  tag.

  Not covered: treating every angle bracket as a boundary would chop a legitimate
  quote in half, so a tag that starts a line and is not in CommonMark's list
  stays content.  That is the same trade the whole dialect makes: erring short
  drops a quote, erring long invents one.

- [x] **P1 - an unknown field's value was searched as part of the quote, and the message said it was not**

  **What was wrong.**  A claim body is read as a YAML mapping: an indented line under `key: |` belongs to that key.  `_split_body` already cleared the collection target (`current = ""`) in the branch that reads a *known* attribute, and the branch that reads an unknown key was written from it without that line.  So the lines under an unknown key fell through to `if current:` and joined whatever field was still open - `quote:`, nearly always:

  ```claim id=c1 source=paper page=1
  quote: |
    We collected 40,688 examples from the corpus of written English.
  text: |
    我们收集了例句
  ```

  gave `claim.quote == 'We collected 40,688 examples from the corpus of written English.\n我们收集了例句'`, and then

      [medium] claim-field-unknown … it was neither applied nor searched
               as part of the quote
      [high]   quote-missing … — quote not found in page.txt

  Every word of the medium finding was false, and the high finding that followed accused the author of quoting a passage that is verbatim on the page.  The real problem - a misspelt field name - was in the output, one line above the accusation, saying the opposite of what had happened.

  **What it does now.**  The unknown-key branch clears `current` too, so a block scalar under a key this format does not have has no owner and its lines reach neither the quote nor the claim text.  The finding is unchanged and still names the line and the key; the quote is the passage the author wrote.

  **Why it is now true.**  `tests/test_unknown_field_value.py` (13 tests) pins six shapes: a block scalar under an unknown key stays out of the quote (fence and HTML dialects), a second unknown key does not adopt the first one's value, a known key after the unknown one still merges, the value becomes no claim text either, and - on a project - the run prints `quote-found` and not `quote-missing`, with the value absent from the reported quote.  A separate test pins the message itself (`neither applied nor searched as part of the quote`), so the promise and the behaviour are now checked in the same file.

  Five mutations die: keeping the owner, adopting the quote, adopting the claim text, not recording the key at all, and clearing the quote along with the owner.  A sixth - letting the unknown key collect its own lines - is equivalent by construction (`fields` is read only for `quote` and `claim`, and this key is neither) and is recorded as `EQUIVALENT` in the script rather than counted as caught.

  **Not covered.**  The body is read by hand, not by a YAML parser, so other shapes a real YAML parser accepts (flow mappings, anchors, folded `>` scalars with blank lines) are read the way this reader chooses and not the way YAML says; the tests pin the former.
- [x] **P1 - a source key written without quotes bound on one interpreter and made the manifest unreadable on another**

  **What was wrong.**  `sources.toml` has two readers.  On 3.11+ the file goes to `tomllib`; on 3.10, which has no `tomllib`, it goes to `sources._mini_toml`, a line-based subset that splits on `=` and strips.  The subset bound whatever key the author wrote: `王力2020`, `smith/2020`, `smith 2020`, `smith:2020`, `smith@2020`, `papér`.  TOML allows only `A-Z a-z 0-9 _ -` unquoted, so `tomllib` refused the whole file.

  Measured, `[sources]` + `<key> = "page.txt"`, both readers over the same bytes: on 3.10 the source bound and the manuscript verified; on 3.12 the manifest was reported unreadable and every claim in the manuscript lost its source at once, as `source-missing ... because the manifest could not be read`.  Same repository, nothing edited between the runs - the verdict depended on the interpreter that happened to be installed, and the failing one failed loudly about a file the author had not touched.

  **What it does now.**  `sources._bare_key_is_not_a_key` asks the question both readers can answer, and `_refuse_shapes_only_one_reader_follows` asks it before either reader runs, so the subset reaches the refusal `tomllib` earns.  The sentence carries the fix: `王力2020 is not a bare TOML key; quote it - "王力2020" - to bind one source under that name`.  A quoted key is legal TOML and binds, so the suggested spelling is the one that works.

  Two neighbouring shapes keep the sentences they already had, on purpose: a dotted key (`smith.2020` is legal TOML naming a nested table, and answering it with `quote it` would trade the right sentence for a near miss) and a quoted key this reader cannot spell (`"pa#ge"`).

  **Why it is now true.**  `tests/test_manifest_bare_keys.py` (55 tests) drives both readers over the same strings and compares outcomes: 8 bare keys both bind, 8 non-bare keys both refuse, and for every non-bare key the two refusals are the *same sentence* - not merely both refusals.  Five quoted names both bind and bind without their quotes.  Each offered spelling is then used for real, because a suggestion the same reader refuses is worse than none.  On a project, the 3.10 path is simulated by `monkeypatch`-style replacement of `_load_toml` and both paths are asserted to bind nothing and report the same `manifest_problem`.

  Eight mutations die: never asking the question, calling every key non-bare, calling no key non-bare, refusing quoted keys too, answering a dotted key with the quoting advice, widening the alphabet to any run of non-separators, dropping `quote it` from the message, and dropping the quoted form from it.  The message mutations only died after the test was made to assert the instruction as well as the spelling - naming the fix is not telling the author it is a fix.

  **Not covered.**  A real TOML parser is not run on 3.10 in CI; the agreement is pinned by driving the two entry points over the same bytes, which is what the readers do.  Keys that are TOML table headers (`[a.b]`) and multi-line keys are outside this reader by design and are refused with the sentence they already had.

- [x] **P1 - `--allow-stale` silenced two guards it never documented**

  **What was wrong.**  Three facts were reported under one code, `ledger-stale`: the ledger describes another document, the recorded manuscript is gone, and the text changed.  A single `if check_manuscript_hash and ledger.manuscript_sha256:` wrapped all three, so `--allow-stale` - documented in `README.md` as *the manuscript changed since the ledger was recorded* - also silenced the other two.  A ledger written for `a.md`, asked about `b.md`, exited 0 with `[info] quote-found at a.md:1 (c1)`; deleting `a.md` gave the same green line about a file that is not on disk.  The existence guard above it existed precisely because *deleting the thing under review must never be the way to make the check pass*, and the flag was a second door into the state it refuses.

  **What it does now.**  `src/citevouch/verify.py` states the three facts separately: an identity check (`recorded_name != manuscript_path.name`) and an existence check (`not manuscript_path.is_file()`) run outside the flag, and only the digest comparison (`manuscript_digest != ledger.manuscript_sha256`) is gated by `check_manuscript_hash`.  `--allow-stale` still tolerates a manuscript with new prose, which is what it is named for; a ledger about another document, a manuscript that is gone, and a path that is now a directory are `[high] ledger-stale` with or without it.  The existence check now also covers a ledger that recorded no `manuscript_sha256` - the hash is needed to answer *did the text change*, not *is the file here* - and uses `is_file` rather than `exists`, so a directory is named as a directory instead of raising `PermissionError` out of `sha256_file` and escaping as exit 1.

  **Why it is now true.**  `tests/test_allow_stale_scope.py` (15 tests) pins each fact in both directions: `verify` and `check --use-recorded` still exit 1 with the flag set for another document, a missing manuscript, and a directory; the tolerated case (a paragraph added) still exits 0 with `quote-found`; and a legacy ledger with no recorded hash is not let off by the flag.  Eleven mutations all go red: putting either guard back inside the flag, requiring a hash for the existence check, skipping the existence check, using `exists()` instead of `is_file()`, skipping the name check, comparing full paths rather than file names, ignoring the flag on the digest, never running the digest, letting the flag silence the recorded re-parse, and swapping the order of the two guards.

  **Not covered.**  Behaviour change worth naming: a repository that used `--allow-stale` to run a ledger against a **renamed** manuscript now gets `ledger-stale` instead of a verdict - that is the point of the fix, but it is a tightening, and the message names the two ways out (`citevouch scan` for this document, or point `--ledger` at the right project).  The flag's interaction with `--use-recorded` on the bibliography path is unchanged and stays as it was.

- [x] **P1 - a ledger about `sub/m.md` was accepted as the ledger for `m.md`**

  **What was wrong.**  `src/citevouch/verify.py` decided whether the
  ledger describes the document this run was asked about by comparing
  `Path(ledger.manuscript).name` against `manuscript_path.name`.  Two
  files in one project can share a name, so with a ledger recorded for
  `sub/m.md`, `verify m.md --root .` reported `[high] ledger-stale ...
  m.md changed since the ledger was written` (accusing the author of an
  edit that never happened) and `verify m.md --root . --allow-stale`
  reported `[info] quote-found at m.md:1 (c1)` and exited 0 (crediting
  `m.md` with a page `sub/m.md` printed, through the one branch
  `--allow-stale` is meant to answer).

  **What it does now.**  `_describes_the_same_file(recorded, root,
  manuscript_path)` compares paths spelled the way the ledger stores
  them: `recorded_path(root, manuscript_path)` - relative to the root,
  forward slashes - against the recorded string.  `./m.md`,
  `sub/../sub/m.md` and an absolute path still name the same document;
  `sub/m.md` and `m.md` do not.  The message now names both paths rather
  than both bare names.

  **Why it is now true.**  `tests/test_ledger_path_identity.py` (12 tests)
  pins both directions: the same name in another directory is refused by
  `verify` and by `check --use-recorded`, with and without
  `--allow-stale`, never prints `quote-found` for the other document, and
  never says `changed since the ledger was written`; the three equivalent
  spellings of the recorded document stay green; and a live `check`
  (which scans and verifies in one run) is never blocked by the guard.
  Six mutations all go red: comparing names, comparing the recorded
  string as given, skipping the comparison, treating an unrecorded name
  as different, never consulting the guard, and consulting it for a fresh
  scan.

  **Not covered.**  A manuscript outside `--root` is stored absolute by
  `recorded_path`, so the comparison there is string equality of two
  absolute paths; no test exercises it.  The earlier form of this fix
  compared resolved filesystem paths with a spelling fallback - two ways
  to answer one question - and made a fresh `check` call its own ledger a
  different document; that is why there is one comparison now.

- [x] **P1 - a manuscript outside `--root` was recorded with whatever spelling the author typed**

  **What was wrong.**  `recorded_path` (`src/citevouch/scan.py`) stores
  an input the way a ledger can carry it: a forward-slash path relative
  to the root. A file outside the root cannot be made relative, and the
  branch that handles that case returned the string the caller passed
  in. That reads like declining to guess, but every difference in the
  caller's spelling went straight into the ledger, and the identity
  guard compares stored strings. With the manuscript at `papers/m.md`,
  outside the project:

  ```
  scan C:\papers\m.md --root proj     -> 0, ledger records C:\papers\m.md
  verify C:\papers\m.md --root proj     -> 0, quote-found
  verify ..\papers\m.md --root proj     -> 1, ledger-stale
                            "ledger describes C:\papers\m.md, but this check
                             was asked about C:\proj\..\papers\m.md"
  ```

  One book, two spellings, called two books - inside the identity guard,
  the one place that comparison is supposed to get right. This is the
  gap v0.22.79's backlog entry listed under **Not covered**.

  **What it does now.**  The outside-root branch returns the resolved
  path, so a file the ledger cannot make relative still has exactly one
  ledger spelling. Paths inside the root are unchanged: still relative,
  still portable, and every spelling of one file still collapses to one
  string.

  **Why it is now true.**  `tests/test_ledger_path_identity.py`
  `TestAManuscriptOutsideTheRoot` (4 tests) reaches the same file by two
  spellings, one run each - a single spelling per test passes with the
  identity function and proves nothing - and a fifth test keeps a
  *different* outside document refused. Six mutations were all red,
  including "the caller's spelling is kept" (the original code), "an
  unresolved path is returned", "the relative branch is not canonical"
  and "nothing is made absolute".

  **Not covered.**  `Path.resolve()` on a case-insensitive filesystem
  (macOS) collapsing two files whose names differ only in case is not
  exercised here; the recorded form would then be identical, which is
  what the platform says anyway.

- [x] **The `draft` advice was a command Windows could not run**
  (`src/citevouch/cli.py` `_shell_word`).

  **What was wrong.** `draft` ends by naming the `check` that reads the
  file it just wrote, in backticks, because the author is meant to copy
  it. The output path was printed with forward slashes, but `--root` was
  printed as typed, and every Windows path is typed with backslashes:

  ```
  $ citevouch draft paper.md --root C:\work\proj -o claims.md
  citevouch: wrote claims.md; read it, then `citevouch check
  C:/work/proj/claims.md --root C:\work\proj`
  $ citevouch check C:/work/proj/claims.md --root C:\work\proj
  citevouch: --root C:workproj does not exist; ...
  ```

  The shell ate the separators before `citevouch` saw the argument, so
  copying the sentence - the one thing a backticked sentence asks for -
  exited 2 on the last line of the first screen `draft` prints.

  **What it does now.** `_shell_word` quotes a backslash as well as
  whitespace and the four characters a POSIX shell expands, so both
  halves of the advice go through the same rule:

  ```
  citevouch check C:/work/proj/claims.md --root 'C:\work\proj'
  ```

  **Why it is now true.** `tests/test_draft_advice_runs.py` gains
  `TestTheAdviceWhenTheRootIsAnAbsolutePath`: the sentence is split back
  with `shlex.split` and `--root` must equal the value the run was given;
  the whole sentence is run from a different directory and must exit 0
  with `1 claim - 1 verified`; and the rule is asserted directly. Four
  mutations, all red: no backslash trigger, `--root` printed without
  quoting, every value quoted, apostrophe not escaped.

  **Not covered.** Both tests parse the sentence with `shlex.split`,
  which is POSIX rules. A `cmd.exe` or PowerShell reader is not tested,
  so what is proven is that the value survives POSIX quoting, not that
  it survives every shell on the platform it is printed on.

- [x] **P1 - an indented field-shaped line inside `quote: |` cut the quote in half, and the
  half that remained verified**

  A mapping body writes `quote:` and its attributes at the left margin with the
  quotation below them, so every indented line in that body is quotation. All three
  readers in `_split_body` matched their key patterns with `^\s*`, and only the
  unknown-key reader also refused indented lines, so `page: 2` indented became an
  attribute while `Page: 2` indented stayed in the quote. A quote containing a line
  shaped like a field lost every line from there down.

  Measured, a block whose quote held a fabricated second sentence - separated from
  the real first sentence by an indented `source: our own dataset` - reported
  `[info] quote-found`, `1 claim - 1 verified`, exit 0, against a page that prints
  only the first sentence. Without the middle line the same block reported
  `[high] quote-missing`, exit 1. The reverse case: a page that prints
  `source: the Penn Treebank, released in 1999.` had its quote truncated there and
  reported `quote-found` for the surviving fragment.

  What it does now: the three readers share `_at_the_margin(raw, margin)`, and
  `margin` is the indent of the shallowest `quote:`/`claim:` line in the same body.
  A line deeper than that is quotation whatever it spells; a line at that indent is
  a key. A claim block nested two spaces deep in a list still reads its own keys.

  Why it is now true: `tests/test_indented_field_lines.py` covers nine key names at
  four indents, the unknown-key branch, a body that is itself indented, and the
  end-to-end verdict. Eight mutations, all red - margin forced to zero, margin
  unbounded, `_at_the_margin` always true, always false, ignoring the margin, and
  each of the three branches dropping its call.

  Not covered: a claim block indented with a tab. `_at_the_margin` counts
  characters, so a tab counts as one; the README documents spaces only.

- [x] **P1 - a field written with `=` inside a claim body was dropped above the
  quote and quoted below it**

  *What was wrong.* A claim body is a mapping and reads `key: value`; the
  opening line of the same block reads `key=value`. Each reader accepted only
  its own spelling, and a body line at the margin written with `=` matched no
  key pattern at all, so it fell through to the branch that appends to the open
  field - and with no field open, to a bare drop. Measured on a source whose
  quote is on page 2:

  ```
  page=2 above quote, correct page   -> [info] quote-found page 2, hint dropped
  page=2 above quote, WRONG page     -> [info] quote-found, exit 0, no finding
  page=2 below quote                 -> [high] quote-missing "…corpus. page=2"
  ```

  A misspelt separator either switched a check off without a word or accused
  the author of quoting a passage the source really prints.

  *What it does now.* The line is reported as `claim-field-unknown` (medium)
  and kept out of the quote, in both positions; it is never applied, because
  the author cannot tell from the key alone whether the key or the separator
  was wrong. The sentence names the separator that works (`write page: (not
  page=)`) for a name the body has, and for a name it does not have lists the
  names from the reader's own table - `number:` is a body key next to
  `numbers:`, and the message used to say "no such key" while listing it.

  *Why it is now true.* `tests/test_body_equals_fields.py` - 28 tests over ten
  spellings, both positions, the margin rule beside it, the comparison `a == b`
  that must not be read as a field, and four end-to-end verdicts. Ten mutations
  covering the reader, the margin, the field-clearing, both sentences and the
  rendered name list are all red. The first version of the fix had two patterns
  for the same line, both matching every candidate; deleting the redundant one
  is what let the mutations die.

  *Not covered.* A claim body nested inside a Markdown list item that also
  spells a field with `=` - the margin rule and the separator rule are tested
  separately, not in combination.
- [x] **P1 - a table row that left off its trailing pipe was never looked at**

  What was wrong: the table dialect's pattern required a closing `|` at the end of
  the row, while GitHub-flavoured Markdown says the pipes at the ends of a row
  may be left out. A row written the shorter way matched nothing, so its claim
  was never read. On its own the file came back as `no-claim-blocks`, described
  in the vocabulary of a fenced block; next to one good block the run printed
  `1 claim - 1 verified` with no finding naming the row, so the evidence was
  silently absent from the verdict.

  What it does now: the last cell ends at either a trailing pipe or the end of
  the line. That file reports `2 claims - 2 verified`. A row with a fourth
  column and no fifth is still refused, because an empty last cell and a table
  of a different shape cannot be told apart.

  Why it is now true: `tests/test_table_row_without_trailing_pipe.py` holds 25
  tests covering both spellings, the equal-claim comparison, the four-cell
  boundary, trailing whitespace, prose that contains pipes, the end-to-end
  verdicts, and the detector agreeing with the parser. Four mutations of the
  pattern all go red; the fifth (no space allowed before the trailing pipe) is
  equivalent, because `_claim_from` strips both cells either way.

  Not covered: a last cell that ends inside an escaped `\`|`; and the ambiguous four-cell shape is unread by design.

- [x] **P0 - a damaged text cell in the ledger was reported as a verdict about the author** (0.22.85)

  What was wrong: `Ledger.from_json` guarded every structural cell and read
  every textual one with `str(entry.get(key, ""))`. `str()` turns `null` into
  the four characters `None` and `5` into `"5"`, so a ledger edited by hand
  reached the verifier looking like a claim whose quote really is those
  characters. On a project whose page holds the quoted sentence, one damaged
  cell produced `[high] quote-missing at m.md:1 (c1): None - quote not found
  (too short for a fuzzy comparison) in page.txt` with exit 1 - and exit 1
  here means findings reached the threshold, which is a verdict about the
  manuscript. `id: null` printed `quote-found at m.md:1 (None)`, `path: null`
  printed `quote-found at None:1`, and `source: null` said `source 'None'
  cannot be found any more` about a source that never existed.

  What it does now: every text cell goes through `_text_cell`, which refuses
  a present non-string with exit 2 and names the cell and the type:
  `citevouch: ledger claims[0].quote must be a string, not NoneType`. An
  absent key keeps its old meaning, so a ledger written before a key existed
  still reads.

  Why it is now true: 80 tests in `tests/test_damaged_ledger_text_cells.py`
  cover 18 damaged cells across the three verbs that read a ledger plus
  `report`, and 12 mutations all go red - including one per text cell
  reverting to `str(entry.get(...))`.

  Not covered: a ledger damaged in a way that is still valid JSON with valid
  types but wrong content (a quote replaced by another string) cannot be told
  from an honest edit; only the type is checkable.

- [x] **P1 - the child-environment guard read one spelling and missed the
  name it was passed through** (0.22.85)

  What was wrong: the new test helper built `env = {"PYTHONPATH": ...}` and
  passed `env=env`. That replaces the whole environment; on Windows the child
  loses `SYSTEMROOT` and aborts in `_Py_HashRandomization_Init` before it can
  report anything. Three Linux and macOS cells passed, four assertions failed
  on Windows 3.10 - the fourth time this repository wrote this defect, and
  the first time `tests/test_child_env.py` did not catch it: it matched
  `env={...}` literals only.

  What it does now: the guard resolves a name to its bindings, a call to the
  values the function returns, and accepts any expression that mentions the
  environment. It stays permissive where control flow would be needed, which
  is the safe direction: a false negative keeps the build green on a real
  defect one indirection out, a false positive fails correct code.

  Why it is now true: two new tests pin both directions (a two-key literal
  behind a name is flagged; a helper that returns `{**os.environ, ...}` is
  not), and a reverse-validation run put the two-key literal back and
  confirmed the guard goes red before restoring it.

  Not covered: a name reassigned conditionally to both a good and a bad dict
  is treated as good (any binding inherits); modelling that would need flow
  analysis, and the guard is a lint, not a proof.

- [x] **P1 - the same attribute written twice decided the verdict, by line
  order** (0.22.86)

  What was wrong: `_attrs` (the opening line) and `_split_body` (the body)
  both stored `out[key] = value`, so writing one attribute twice kept the
  last value and dropped the first with no finding. On a quote printed on
  page 1 of `paper.txt` and nowhere in `alt.txt`, `source=paper source=alt`
  produced `[high] quote-missing` (an accusation about the author), and
  `source=alt source=paper` produced `[info] quote-found` (silence). The
  body had the same shape: `page: 2` then `page: 1` verified, and swapping
  the two lines produced `[medium] quote-moved`. A repeated `id:` silently
  renamed the claim in the report and in the ledger.

  What it does now: the first value is kept and every later value is named
  in a new `claim-field-repeated` (medium) finding, one finding per
  attribute, in both layers (opening line and body) and both dialects
  (fenced and comment). Two identical spellings say nothing, because nothing
  was lost. The alias pair keeps its own finding, and the documented rule
  that the opening line wins over the body is unchanged.

  Why it is now true: 22 tests cover both layers, both dialects, both line
  orders, the identical-value case, the alias pair and three end-to-end
  verdicts; eight mutations were run against the new code (each layer
  silent, each layer keeping the last value, identical values counted as a
  repeat, the alias pair reported as a repeat, a message naming only the
  dropped value, one finding per dropped value) and all eight went red.

  Not covered: a repeated attribute inside a claim block that is itself
  nested inside a list item; the margin rule and the repeat rule are each
  tested, the combination is not.
- [x] **P1 - a bibliography `file` field was read as one path, and only one (0.22.87)**

  What was wrong: `draft` looked in an entry's `file` field for the local
  copy of the cited paper, and read that field as a path - split on `:` and
  take the second piece. Three tools write the field and only two shapes
  were read. With `papers/page.txt` on disk,
  `file = {Full Text PDF:papers/page.txt:application/pdf}` (Zotero today)
  and `file = {papers/page.txt;papers/other.pdf}` (Mendeley) both produced
  `no local file: ... names 'Full Text PDF:papers/page.txt:application/pdf', and that file is not there`
  - a sentence naming a file nobody wrote, about a file that is right
  there. The colon split also turned `:C:\papers\page.txt:application/pdf`
  into `'C'`, because a drive letter is the second piece of a colon split.

  What it does now: `_bib_files` returns every candidate the field names,
  in the order the author's tool wrote them - `;` separates copies and
  attachments, and a `label:path:mime` or `path:mime` wrapper is unwrapped
  only when the tail actually looks like a MIME type, which is what leaves
  a legal `papers/a:b.txt` alone. `resolve` tries each candidate in turn,
  so an entry whose second attachment is the one on disk now resolves, and
  `_why_no_file` names every path it tried. `_bib_file` is kept as the
  first-candidate spelling so the callers that want one path stay readable.

  Why it is now true: 17 tests in `tests/test_bib_file_field.py` pin every
  shape (plain, unlabelled Zotero, labelled Zotero, a label with spaces, a
  Windows absolute path with and without the wrapper, Mendeley's two
  copies, two Zotero attachments, an empty field, and `papers/a:b.txt`
  staying whole). `TestTheSecondCandidateIsTried` and
  `TestTheSentenceNamesWhatItCouldNotFind` cover the two halves that only
  fail together: the resolver walks the list and the sentence prints it.
  Eight mutations, all red: no path read from the field; only the first
  candidate tried; only the first path named; `;` read as one path; the
  MIME test removed; the label never recognised; the empty leading piece
  kept; a colon in a name treated as a wrapper.

  Not covered: a `.bib` written by Zotero itself (the fixtures reproduce
  its shape by hand from the strings the tool documents); a `file` field
  whose label itself contains a colon.
- [x] **P1 - a page that printed `40, 688` was said not to contain `40,688` (0.22.88)**

What was wrong: a quote typing `40,688` against a page printing `40, 688`
printed both halves of a contradiction in one run - `[info] quote-found`
from the word matcher, which deletes whitespace before comparing, and
`[high] number-absent-in-quote` from the number reader, whose grouping
separator had to sit flush against its digits. The mirror case read a quote
typing `40, 688` as two numbers and reported both missing from a page that
printed the figure once.

What it does now: `CANON_PATTERN` lets a digit group be parted from its
separator, and the digits of a group be parted from each other, by the
spaces `canonical_number` already folds away. The group rule is untouched:
one to three digits on the left and exactly three on the right, so
`2019 2020 2021` stays three years, `1234 567` stays two numbers, `40, 6888`
is still not a group, and a newline is still not a parting.

Why it is now true: `tests/test_number_separated_by_space.py` pins eight
spellings of one figure (one token, one canonical value), pins the four
neighbours that must not widen (years, the two-number page range, the
four-digit left side, a group that would cut a run of four digits), pins the
newline boundary, and runs the whole thing end to end through `check` in
both directions - spaced page against tight quote, and tight page against
spaced quote - plus a real different number that must still be reported
absent. Nine mutations were run against `src/citevouch/textnorm.py`:
dropping either side of the separator's whitespace, dropping the bare space
branch, forbidding the left digits to part, forbidding the group to part,
widening the left side to four digits, dropping the digit-boundary assertion,
letting a newline part digits, and reverting `CANON_PATTERN` to
`REPORT_PATTERN`. All nine went red.

Not covered: `MASK_PATTERN`, which the match tiers use to blank numbers out,
still reads `40, 688` as two spans. That only makes the numbers tier mask
more than it must, never less, so it was left alone rather than risk the
tiers that already pass; a real PDF that splits a group across a line break
is also untested, because the pattern deliberately refuses to join across
one.
- [x] **P1 - an attribute written on the fence and again in the body silently dropped the body's value (0.22.89)**

  What was wrong: a claim block can name one attribute twice, once on the
  opening line (`source=paper`) and again in the body (`source: alt`).
  `_claim_from` merged the two with `merged.update(attrs)`, so the opening
  line won and the body's value vanished with no finding. Measured with a
  quote printed in `alt.txt` and nowhere in `paper.txt`, the block

      ```claim id=c1 source=paper page=1
      quote: |
        We collected 154,391 examples from the corpus.
      source: alt
      ```

  gave `[high] quote-missing at m.md:1 (c1): quote not found in paper.txt` -
  an accusation against an author who wrote the right source three lines
  below the fence - and the same block with the values swapped verified
  silently. Five attributes behaved this way: `source`, `page`, `id`,
  `marker`, `ref`.

  What it does now: the precedence rule is unchanged (the fence wins,
  because that is where the format is documented), and a new
  `claim-field-shadowed` (medium) finding names both values, which one was
  used, and the line carrying the one that was dropped. One finding per
  attribute, because findings on one line are deduplicated downstream and a
  loop would report the first and hide the rest. The snapshot of the opening
  line is taken before the merge, since after it the loser is unrecoverable.

  Why it is now true: `tests/test_cross_layer_attributes.py` (17 tests)
  covers all five attributes, both directions, the line number of the loser,
  the silent cases (equal values, body-only keys, fence-only keys, the `ref`
  `cite` alias pair keeping its own finding), and three end-to-end
  verdicts. Eleven mutations were run and ten were caught: the finding never
  produced, the snapshot moved after the merge, the equal values reported,
  the missing keys reported, the body winning, the line pinned to the
  fence,
  the message naming the winner as the loser, only one attribute reported,
  `places` never filled, and the alias pair pulled into the same-name rule.
  The eleventh (`x = dict(y)` -> `x = y`) is equivalent: `attrs = merged`
  rebinds a name and never writes into the dict the callee already holds.

  Not covered: a body attribute inside a list item's indented claim block,
  where the body line offset is measured against an indented fence; and the
  comment dialect's one-line form, which has no body lines to shadow
  anything.

- [x] **P1 - two findings about one attribute contradicted each other (0.22.90)**

  What was wrong: a claim writing one attribute on its opening line and
  again, twice, in its body produced two findings about the same value, and
  they disagreed. On a block with `source=paper` on the fence and
  `source: alt` then `source: other` in the body, `check` printed
  `claim-field-shadowed` saying `'alt' in the body ... was dropped` directly
  above `claim-field-repeated` saying `the first, 'alt', was kept`, while
  the ledger recorded a third answer, `paper`. Each finding was true of its
  own layer; read together they left the author to work out which sentence
  to believe.

  What it does now: `_repeated_fields` takes the opening line's values. When
  one of them is the name being repeated, the sentence says the fence writes
  it too, counts the fence among the writings, names the value that won, and
  lists every body value that lost. A body-only repeat keeps its old
  sentence, because nothing above it won.

  Why it is now true: `tests/test_two_findings_one_attribute.py` (9 tests)
  pins both shapes - the both-layers case (no `was kept`, `3 times`,
  `were all dropped`, the winner named, both losers named) and the body-only
  control that must not change - plus the two-attribute block (four findings
  on four lines, none of them claiming a body value survived) and one
  end-to-end `check`. Ten mutations were run and all ten were caught: the
  taken values ignored, the fence not counted, singular verb, singular noun,
  only the first loser named, the winner unnamed, the repeat pointing at the
  fence instead of its own line, names passed instead of values, one call
  site forgetting the values, and the unchanged shape silently reworded.

  Not covered: the comment dialect's one-line form, where every attribute is
  on the opening line and no body repeat exists; and the table dialect,
  which has no body lines to repeat.

- [x] **P1 - an attribute line was read as quote text whenever the body named no key (0.22.91)**

**What was wrong.** A claim body has four shapes: `quote:`/`claim:` keys, a
`>>` passage, two paragraphs, or one paragraph. The format's margin rule
says a line at the block's own indentation is a field line, so `page: 2`
under the fence means the same thing as `page=2` on it. It was implemented
inside the first shape's branch only, so the other three read the attribute
line as prose. Measured on a fence that had already said
`id=c1 source=paper page=1`, with the passage really on page 2:
`['page: 2', '', Q]` gave quote `page: 2`, claim `Q` and page 1, and then
`[high] quote-missing "page: 2"` - an accusation about a page the source
never printed. `[Q, '', 'page: 2']` gave quote `Q`, claim `page: 2`, exit 0:
the hint was dropped and printed back as the author's prose. All six
attribute names, both dialects.

**What it does now.** `_split_body` lifts the attribute lines out before the
shape is chosen, for every shape, on one rule. Only the six names the format
has are taken - `Note: ours.` and `Example: 1` stay in the quote, because a
reader that treats every colon as a field cuts quotations in half. A repeat
inside a keyless body keeps the first spelling and reports the rest through
`claim-field-repeated`; two identical values still say nothing. An attribute
line on its own now leaves a block with no passage, and `_claim_from` says
`carries no verbatim quote` instead of accusing the author of quoting their
own line.

**Why it is now true.** 25 tests in
`tests/test_attribute_line_without_a_key.py` cover the five keyless shapes,
the six names, the indent rule, the shadow/repeat findings and the
end-to-end verdict (including the third page of a three-page file, where the
wrong hint is now `quote-moved` at medium instead of `quote-missing` at
high). 13 mutations were aimed at the new branch: 11 turned the suite red,
and the two survivors were checked and found equivalent (the
`_ATTRIBUTE_KEY` pattern is case-sensitive, so `lower()` cannot change a key
that reached it; and a body of `[' ']` returns the same empty tuple through
the paragraph fallback). One older test in
`tests/test_attributes_in_the_body.py` asserted the old behaviour - that a
keyless body is all quote - and was rewritten to assert the quote survives
and the page is read.

**Not covered.** A margin line whose value is a YAML block scalar (`page: |`
plus an indented line) still takes only the inline value, which is exactly
what the mapping branch does with these six names. The `>>` shape with an
attribute line between two passages is lifted and the passages stay
adjacent, but no test pins that interleaving.


- [x] **P0 - a definition written in the body gave its template to the paper, and `draft` invented a citation from it (0.22.92)**

**What was wrong.** `latex._definition_end` decided how many brace groups a
definition takes with two membership tests, `_DOCUMENT_COMMAND` and
`_ENVIRONMENT_DEFINITION`. Every spelling that had a branch was read
correctly; every spelling that had no branch fell through to the
unknown-command rule, which keeps all the arguments because for most
commands the arguments are the prose. Eighteen definition spellings leaked
their templates into the paper, and `included_files` - which reads the raw
source - reported a template's `\input{ghost/sec}` as a file the paper pulls
in. The worst case was
`\NewDocumentEnvironment{aside}{m}{The corpus for the study of grammar has \citep{phantom2020}.}{}`,
which converted to
`asidemThe corpus for the study of grammar has [@phantom2020].`: the
template's citation became real, and `draft` proposed a claim block quoting
a page it had found by keyword overlap. Twenty settings commands were the
same bug from the other side, pasting font names and lengths into the
sentence.

**What it does now.** The shape is a number in one table,
`_DEFINITION_GROUPS` (name, then how many brace groups it takes), and
`_definition_end` reads it in a loop. `included_files` reads the same table,
so a template's `\input` is not a file. Twenty settings commands are in
`_DROP_ALL_ARGUMENTS`. Adding a spelling is now a key, not a branch.

**Why it is now true.** `tests/test_latex_definition_shapes.py` (67 tests)
covers every leaked spelling in both directions - the template is gone and
the sentence after it survives - plus the file list, the sixteen spellings
that already worked, and a `draft` call that asserts the template's citation
is not a citation. Twelve mutations ran red, including one fewer group and
one more group than the table says.

**Not covered.** A definition whose body holds a `%` comment before the
closing brace; `\NewDocumentEnvironment` with an optional argument count
before the specification; `\tcbset`, a tcolorbox settings command that was
not among the twenty measured. The mutation check also found two defects in
this fix itself - a conditional whose arms returned the same value, and a
star branch duplicating `_skip_optional_args` - both removed.

- [x] **P1 - one sentence on one page was reported both found and absent, because two readers read two different strings (0.22.93)**

**What was wrong.** A page printed the fullwidth `４０，６８８`; the quote typed
`40,688`. The matcher compares `fold`ed text, where NFKC has already turned
the fullwidth comma into `,`, so it saw one number and printed `[info]
quote-found`. `verify._page_numbers` scanned the *raw* page with
`CANON_PATTERN`, whose separator list has no fullwidth comma, so it read
`40` and `688` and printed `[high] number-absent-in-quote ... the quote says
40,688 but page 1 of the source does not contain that number`. One run, one
sentence, two opposite verdicts. The same split made `mask_numbers` write
two placeholders where the quote wrote one, so the numbers tier could not
line a fullwidth page up with an ASCII quote at all, and a quote typed in
the fullwidth form was read as two numbers.

**What it does now.** `textnorm.fold_number_forms` applies NFKC and drops
format characters, and nothing else; the page reader, the quote reader, the
report reader, the masker and the span reader all pass their text through it
first. NFKC is exactly the right amount - it turns `４` and `，` into `4` and
`,` because those are compatibility spellings of the same characters - and
it leaves whitespace and offsets alone, which the masker needs because a
collapsed line break would merge two numbers into one placeholder. It
deliberately does not translate Arabic-Indic or Devanagari digits: the first
version called `_ascii_digits` too, and the full suite caught that it broke
`numbers_in`'s promise to report a number the way the document spells it.

**Why it is now true.** `tests/test_fullwidth_digits.py` (22 tests) makes
the five readers agree on one number in both scripts, runs the sentence that
was called both found and absent through three page/quote combinations, and
pins what the shared reading must not change - a line break keeping two
numbers apart, offsets not moving, `2019 2020 2021` still three years, a
bare space still a thousands group, the quote reader still keeping the wide
separator rule that `numbers_in` refuses. Ten mutations ran red, including
each reader falling back to the raw text.

**Not covered.** A number split across a line break inside a run of pages; a
fullwidth number inside a table-dialect claim; circled or enclosed numerals,
which stay non-numbers by design. The measured perf cost is unchanged.


- [x] **P1 - a NUL in the page was counted as a blanked number, so the report named the wrong figure (0.22.94)**

What was wrong:

The matcher blanks every number out as `\x00` and compares the blanks; the
  numbers tier counts the blanks before a match to learn which number the
  page printed at that spot. PDF extraction keeps NUL bytes - six pages
  among the first 250 PDFs of one real corpus carry one - and a NUL anywhere
  before the match added one to the count, shifting every slot by one
  number. A page reading
  `A footnote says 9,800 somewhere.\x00We collected 9,801 examples from the corpus. Then 7 more.`
  was reported as printing `7` where the quote says `9,800`, in a manuscript
  quoting `We collected 9,800 examples from the corpus.` The page prints
  `9,801` in that very sentence, and the same page without the NUL reported
  `9,801`. Same page, same quote, one invisible character apart, two
  different accusations.

What it does now:

`matching._without_the_placeholder` removes the sentinel from the text
  before it is masked, so a blank is written only where a number was. Both
  `mask_numbers` and `number_spans` go through it, so the masker's count and
  the span reader's tokens stay in step, and `_numbers_under` lands on the
  number the page actually prints. Twenty tests pin the count, both ends of
  the end-to-end verdict, and the things that must not change: one blank per
  number, a fullwidth number is still one number, `2019 2020 2021` is still
  three years, and a bare space is still a thousands group at most once.

Why it is now true:

Seven mutations: leaving the artefact in place, both readers bypassing the
  helper, removing only the first artefact, removing only leading artefacts,
  and the masker forgetting the helper are all red. The seventh - removing
  the sentinel before rather than after the folding - survived, and that is
  a theorem rather than a gap: a full scan of 0x110000 found the NUL itself
  is the only character whose NFKC folding yields a NUL, so the two orders
  are the same function. Recorded as equivalent, not papered over with a
  test.

Not covered:

A NUL inside a number (`40\x00688`) is read as one number rather than two;
  that is the charitable direction and it is tested, but the corpus read did
  not contain the case. A NUL inside a claim block's own quote text is not
  covered: the manuscript reader drops control characters before this code
  sees them, so the tests only cover pages. No audit was made of other
  characters a page can supply that the masker treats as content; this fix
  removes the one the masker itself injects.


- [x] **P1 - `doctor` called a manuscript it could not use fine, and sent the reader to the wrong files (0.22.95)**

What was wrong:

A manuscript whose only claim block was read and refused - no `id=`, no
  `source=`, no quote - made `check` print `[high] claim-uncheckable`, count
  the block as unchecked, and exit 1, while the ledger held no claim at all.
  `doctor` on the same tree printed seven `[ok  ]` lines, exited 0, and
  closed with "Everything this tool needs is on this machine. If quotes are
  still reported missing, the source files are the place to look." The
  command a reader runs *because* the report looked empty was the one
  telling them nothing was wrong, and the last line pointed at source files
  for a defect in the manuscript. One branch had folded two opposite shapes
  together: a block nobody could reach (blockquote, list item, indent)
  produces no claim and no finding, but a block the parser read and refused
  is a decision.

What it does now:

The claims line fails, counts every refused block, names the line and the
  fault, and gives the attribute fix. The `sources` and `extraction` lines
  say "not checked, because the parser refused the blocks this file holds"
  instead of "no claim names a source" printed one line under a refusal.

Why it is now true:

`tests/test_doctor_refused_claim.py` covers three refusal shapes in the
  fence dialect and one in the comment dialect, each asserted for exit 1,
  for `[FAIL] claims`, for the message naming the command to run, and for
  the closing "machine is fine" sentence being absent. It also pins the two
  boundaries that must not move: a file holding one readable block beside a
  refused one still exits 0 with "1 of which the parser could read", and a
  fence out of reach still reports `no claim blocks` rather than "read and
  refused". 9 mutations of `src/citevouch/doctor.py`, all red: skipping the
  branch, reporting it ok, counting only the first refusal, counting a table
  header as a block, dropping the line number, dropping the fault text,
  dropping the command from the fix, leaving `sources` as it was, and
  narrowing the refusal set.

Not covered:

The table dialect's refused-row-plus-header shape was measured by hand but
  not enumerated. `scan` and `verify` still report the refusal through the
  finding alone, which is right - they name the block - and this entry only
  claims what `doctor` now says.



- [x] **P1 - `doctor --format sarif` filed a manuscript problem under `check-unavailable`, whose rule line blames the installation (0.22.96)**

What was wrong:

SARIF puts the code on the rule line GitHub prints above the message.
  `doctor.findings()` chose one constant for every failure it had found,
  `check-unavailable`, whose short description reads "This machine cannot run
  the checks at all." A project whose only claim block names no `source=`
  reaches GitHub as an installation problem while `check` says
  `claim-uncheckable` and exits 1; a manuscript holding no claim blocks
  arrives the same way, and so does a source file that is missing. The reader
  of the code-scanning tab was told to repair their machine and sent to look
  at the wrong file.

What it does now:

`Report` carries the code it should be filed under, defaulted to
  `check-unavailable` (only the interpreter, the PDF library and the
  PDF-to-text tool keep that default, because only they measure the machine).
  Two codes join it: `manuscript-unusable` when the manuscript is LaTeX, not a
  file, a directory, or unreadable - `check` exits 2 on all four - and
  `project-unusable` when the claim blocks, their sources, or the manifest
  stop the run. `doctor.findings()` reads the field instead of choosing a
  word, and `--format json` carries the code too, so a script can tell the
  three apart.

Why it is now true:

`tests/test_doctor_sarif_codes.py` runs `doctor --format sarif` over a
  refused block, an unbound source key, a manuscript of pure prose, a missing
  manifest, a manifest that does not parse, a `.tex` manuscript, an unreadable
  PNG source, and a stubbed-away PDF library, and asserts the ruleId of each.
  The three rule descriptions are asserted to name their own subject and not
  each other's, and the codes are asserted to be in `CODES` and `SARIF_RULES`.
  The two older tests that pinned the single constant now pin
  `manuscript-unusable`, plus a new one that stubs `_pypdf` and keeps
  `check-unavailable`. 13 mutations, 13 red: reverting `findings()` to the
  constant, mislabelling any one check, and changing the default each fail.

Not covered:

The rule lines are verified through the SARIF ruleId, not by reading the
  prose a code-scanning tab renders. A run holding a machine failure and
  several project failures at once is unmeasured: the test stubs the PDF
  library on an otherwise sound project. `scan` and `verify` were not touched;
  they never had this seam.

- [x] **P1 - the commands `doctor` printed did not run: a manuscript at `paper/m.md` got `citevouch draft m.md -o claims.md` (0.22.97)**

**What was wrong.** Each failed check ends with a sentence naming what to
  type, and that sentence is the whole point of the line. It was assembled
  from `target.name` - the file name alone - so the directory vanished, and
  the `--root` the run had been given was dropped the same way.
  `citevouch draft m.md -o claims.md` answers
  `citevouch: manuscript m.md does not exist`. The LaTeX branch did the
  same, and the GBK branch printed a bare `citevouch scan`, which is
  argparse text rather than a command. `draft` had already fixed exactly
  this for its own closing advice, four releases earlier, in
  `cli._check_advice`; the rule existed and the second caller had never
  heard of it.

**What it does now.** The rule lives in `citevouch.advice`: `shell_word`
  quotes a value for a shell, `root_words` yields `--root` when the root is
  not the default, and `citevouch_command` joins them after the program
  name. `doctor` 's four builders (`_draft_advice`, `_scan_advice`,
  `_check_advice`, and the `iconv` line for a miscoded file) and `cli` 's
  `_check_advice` all go through it, so one string cannot drift from the
  other. A run above the project prints
  `citevouch draft paper/m.md -o claims.md --root paper`; a run inside it
  keeps the short form.

**Why it is now true.** `tests/test_doctor_advice_runs.py` takes the
  command out of the output and runs it with `shlex.split`, from the
  directory above the project - the one place where printing the bare name
  and printing the real path give different answers. 14 tests cover the four
  branches, the `--root` form, the shell-quoting edge cases (space,
  backslash, apostrophe, empty) and the two commands `draft` prints. 12
  mutations: dropping the directory, dropping the root from each of the
  three builders, restoring the bare `citevouch scan`, printing backslashes,
  printing `--root .`, and three quoting relaxations - all red. Full suite
  4073 passed, 237 files formatted, demo red line unchanged.

**Not covered.** An absolute `--root` is quoted by the same branch but no
  test pins that spelling. Shells other than POSIX sh: the quoting is
  single-quote-with-escape, correct for sh/bash/zsh and PowerShell's
  argument parser, wrong for `cmd.exe`, which the tool never claims to
  support.

- [x] **P1 - one run named the manuscript twice, and the short name was the one that could not be resolved (0.22.98)**

  **What was wrong.** With `sources.toml` at the repository root and the
  manuscript in a directory - the layout `action.yml` documents -
  `check paper/m.md --root .` printed `[high] quote-missing at m.md:3`,
  while the ledger written by the same run recorded
  `manuscript: paper/m.md`. Every reader of the manuscript passed
  `Path.name` to the parser, so a finding lost the directory as soon as the
  project had one. GitHub code scanning resolves a SARIF `uri` against the
  repository root, where `m.md` does not exist, so the annotation was
  dropped and the pull request showed nothing.

  **What it does now.** `scan`, `verify` and `doctor` ask `recorded_path` -
  the function that already named the file for the ledger, the sources and
  the bibliography - and hand that one string to `parse_manuscript`, to
  `scan_unbound_markers`, to `_no_claim_blocks_finding`, to the two
  `ledger-stale` guards that fire before any parsing, and to the sentences
  that name the file inline. Sixteen call sites, one spelling.

  **Why it is now true.** A finding's `path` is now byte-identical to the
  ledger's `manuscript` for the same file, in text, JSON and SARIF, whether
  the manuscript is at the root, in a directory, or named by an absolute
  path; `--root paper` correctly yields `m.md`. Twenty tests cover the three
  verbs and the guards that run before parsing, and nine mutations (dropping
  the root, keeping the basename in one reader, skipping the stale guards)
  all go red. The docstring that defended the basename is rewritten: a
  root-relative path also reads the same in every checkout, and unlike a
  bare basename it names a file the reader can open.

  **Not covered.** A project on a different drive from the checkout, where
  `relative_to` raises and `recorded_path` keeps the absolute form - the
  unchanged fallback. `--root` pointing at a symlink on POSIX. Any future
  reader that builds a path without going through `parse_manuscript`.

- [x] **P1 - the four `convert it first` sentences named a file that was not where the reader stood (0.22.99)**

**What was wrong.** `source-not-text`, `source-encoding`, `source-no-text`
  and `claim-not-decoded` all told the author to convert a file and printed
  the command to do it with `path.name`. A source at `sources/paper.docx`
  produced `soffice --convert-to pdf paper.docx`; the reader is at the
  project root and that file is one directory down, so the command answers
  `Error: source file paper.docx does not exist`. The finding's own `path`
  field was correct in all four cases - only the prose was wrong, which is
  why every existing test stayed green: they asserted a substring of the
  sentence and never asked whether the file it named existed.

**What it does now.** The four sentences print the root-relative path the
  reader can open - the same spelling the ledger records - shell-quoted
  through `shell_path`, so a name with a space survives the shell as one
  argument. `recorded_path` moved from `scan.py` to `sources.py` so the
  sentence builders can reach it without an import cycle; the three builders
  take an optional `root` and spell the path themselves, and `root=None`
  keeps a bare unit-test path exactly as given. `draft` gained a
  `manuscript_name` argument because the path it compares for identity is
  not the path it should print.

**Why it is now true.** 11 tests in `tests/test_conversion_command_runs.py`,
  all run from the directory *above* the project, because that is the only
  place the two spellings differ: they take the command out of the output,
  split it with `shlex`, and stat every path word in it. Three of them go
  end to end through `check` and `draft` and read the file `draft` wrote,
  since that is where the author reads the note. 10 mutations (each
  `shell_path` reverted to `Path(...).name`, the root dropped, the quoting
  dropped, `draft` printing its identity path) are all red; 4104 tests and
  239 formatted files on the final tree; the demo still reports 4 verified,
  1 missing, exit 1.

**Not covered.** A source named with a Windows backslash is shell-quoted as
  a path, not translated; `-` and `--` leading words in a printed command
  are skipped by the test rather than proven safe; the `report` verb has no
  such sentence.
- [x] **P1 - the pre-commit hook read the ledger in its comment and not in its arguments (0.22.100)**

  **What was wrong.** `.pre-commit-hooks.yaml` said, in its own header, "It
  reads the committed ledger by default", and its description promised to
  fail "when a quote moved, went missing, or the source file is no longer
  the one the ledger recorded". It ran `citevouch check manuscript.md` with
  no `--use-recorded`, which scans afresh and never opens the ledger.
  Measured with a source replaced by another version of the same paper, the
  quoted sentence still in it: the hook exited 0 with `[info] quote-found`,
  while `citevouch check manuscript.md --use-recorded` reported
  `[medium] source-changed`. A ledger that was never committed was worse
  than silence: the hook printed a clean run where the recorded path exits 2
  saying there is no ledger at all. The default threshold was the second
  half - `quote-moved` and `source-changed` are both medium, so even on the
  recorded path the hook printed the two findings its description names and
  exited 0.

  **What it does now.** `args` is
  `["manuscript.md", "--use-recorded", "--fail-on", "medium"]`, with the
  measured comparison written next to it. The recording hook keeps no
  `--use-recorded`: `scan` is the command that writes a ledger, and telling
  it to trust one is the mirror image of the same mistake. Six new tests
  compose the command out of the YAML and run it against a project that
  should fail - a replaced source, a quote that moved, a ledger that was
  never committed - so the file is exercised as the thing pre-commit
  executes.

  **Why it is now true.** `tests/test_precommit.py` has 21 tests, six of
  them new; five mutations of the YAML are all red: dropping
  `--use-recorded`, keeping it but dropping `--fail-on`, putting the
  threshold back to the default, giving the recording hook `--use-recorded`,
  and removing the manuscript from `args`. Every mutation changes an exit
  code rather than a message, because the assertions are on return codes and
  finding codes.

  **Not covered.** pre-commit itself was not installed and run - the harness
  stands in for it by composing `entry` + `args` exactly as pre-commit would
  and executing it in bash. A repository that renames its manuscript away
  from `manuscript.md` still has to edit `args` by hand, and no test covers
  that edit. The `medium` threshold was chosen from the codes the
  description names, not measured against a corpus of real commits.
