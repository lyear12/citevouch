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
