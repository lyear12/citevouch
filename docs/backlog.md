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
