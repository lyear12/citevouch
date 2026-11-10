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

## [0.22.60] — 2026-11-10
### Fixed

* **The markdown report left out the claims it skipped.**

  `render_text` and `render_json` both carry `skipped`; the markdown summary
  row - the one `action.yml` puts in a pull-request comment - printed four
  counts and never that fifth one. Measured on a claim whose source file exists
  but holds no text, before this change:

  ```
  --format text      citevouch: 1 claim — 0 verified, 0 moved, 0 missing, 1 skipped
  --format json      {"checked": 1, ..., "skipped": 1}
  --format markdown  **1** claim · **0** verified · **0** moved · **0** missing
  ```

  The run exits 1 over that claim, and the row a reviewer reads accounts for
  none of it. The four numbers add up to the document minus everything this
  run declined to judge, so a red job looks like a report about a smaller
  paper. A skipped claim was read and then deliberately not judged - that is
  the opposite of it not existing, and the surface a reviewer trusts cannot be
  the one place that says it does not.

  The clause is conditional on `result.skipped`, exactly as the text tally is,
  so a clean report keeps the row it has always had: 6 tests, 6 mutations, all
  red.
## [0.22.59] — 2026-11-09
### Fixed

* **A citation the author was showing with `\verb` was one `draft` said they made.**

  TeX prints an inline-verbatim body literally, so the converter drops each body before the citation patterns run and puts the characters back afterwards - that is how `50\verb|%|` reaches the output as a percent sign. The restored characters come back in LaTeX spelling, and `draft` reads the converted text: `\verb|\citep{ghost2021}|` came back as `\citep{ghost2021}` and `citation_sites` recognised it. The author was told their own example key has no local file, and a specimen placed above a sentence also stopped that sentence matching, because the example text travelled into the sentence `draft` compared.

  Measured on a manuscript with the example beside a real `\citep{paper}`, before this change:

  ```
  citevouch: 1 claim block(s) proposed (0 verbatim), 3 citation(s) left as comments
  <!-- line 3: ghost2021 - no local file: not in sources.toml, no `file` field
       in the bibliography, and no file named after the key -->
  ```

  The Markdown half of this defect was fixed in 0.22.58 by blanking the display before anything reads it. This one cannot use that answer: the restored characters have to stay, because they are what the paper prints. The converter is the only code that knows where each body landed, so `latex.to_text_and_display()` now says where, and `display.blank()` blanks exactly those spans. `latex.to_text()` is that function's first half, so the two cannot drift.

  The bodies go back **last**, after the whitespace passes. Their markers hold no space and no newline, so no pass touched them and no pass moved them - measuring spans in one string and returning another is how this kind of fix goes wrong.

  What this does not fix: a body inside the sentence that cites the real page still blanks a hole in that sentence, so it falls back to the medium-confidence passage. Markdown inline code has the same behaviour and it is recorded in `docs/backlog.md` - the fix is to compare against text with holes rather than against the printed characters, which is a different change from this one.

  `tests/test_latex_displayed_citations.py` (20 tests) covers all five inline-verbatim commands, the literal characters that must survive, the spans pointing at the bodies in the returned string, and the prose that must keep its citations. 12 mutations, all red - one of them only after `blank()` got tests for spans that do not fit, because a negative start wrapped around to the end of the string and blanked prose the author wrote.
## [0.22.58] — 2026-11-09
### Fixed

* **`draft` read a citation the author was displaying as one they were making.**
  Markdown has four ways to show a passage instead of writing it - a fenced block,
  a code span, an HTML comment, an indented block - and a `[@key]` inside one is a
  specimen of the syntax, not a citation. Measured on a manuscript whose page prints
  the sampled sentence word for word, with `ghost` a key that has no local file, all
  six shapes made `draft` write `line 2: ghost - no local file: not in sources.toml`:
  the author told their own example has a missing paper. Two of the shapes lost more:
  the paragraph underneath came back as `0 claim block(s) proposed (0 verbatim)` with a
  medium-confidence passage, because ``` and `<!--` travelled into the sentence
  compared with the page.
  
  The new `src/citevouch/display.py` blanks every displayed region while keeping the
  text's length and its newlines exactly, so a position in it is the same position in
  the manuscript. A closing fence carries at least as many of its own character as
  opened it and nothing after them; a span closes on a run of exactly as many
  backticks; an unterminated fence or comment runs to the end of the file, which
  `manuscript` reports separately; and an indented block has to start a paragraph, or
  an indented continuation of a list item would be read as sample text and its prose
  would vanish. `draft` masks once and reads both citations and sentences from the
  masked text. A `> ` blockquote is still prose, and a `[@ghost]` in an ordinary
  sentence is still reported missing. 28 tests, 11 mutations, all red.
## [0.22.57] — 2026-11-09
### Fixed

* **A manuscript whose length happened to be even lost its claim fences.**
  The UTF-16 fallback in `textnorm._decode_text_and_loss` moved a file to the
  sixteen-bit reading whenever that reading had no replacement characters and
  the UTF-8 reading had enough of them.  A 114-byte GBK manuscript satisfied
  both: re-pairing its bytes produces clean-looking text in the same script, so
  the swap went through.  Its two claim fences, its `quote:` keys and its
  `id=`/`source=` attributes are ASCII and had survived the UTF-8 reading; the
  sixteen-bit reading made every one of them disappear.  `check` then said the
  manuscript held no claim blocks, `draft` said no citations had been written in
  the style it reads, and `doctor` blamed the claim blocks - three readings of
  one file, not one of them about the encoding.  A 113-byte twin of the same
  file, one byte shorter, was read correctly, so appending a single byte
  changed all three verdicts.

  The rule is now structure rather than cleanliness: the swap is refused when it
  would shorten the longest run of printable ASCII, because claim fences,
  `quote:` keys and `[@key]` citations are such runs in every encoding an
  author saves them in, and re-pairing those bytes erases all of them.  A
  genuine UTF-16-LE file never shows a run that long, since its letters sit
  between zero bytes.  One shape stays undecidable and is documented: an 8-bit
  file of pure two-byte script with no ASCII at all and an even number of bytes.

  `tests/test_even_length_manuscript.py` covers both halves, and ten mutations
  of the new rule - the veto removed, made constant, the threshold moved to one
  and to forty, the escape dropped, the counter zeroed, the class widened, and
  the loss flag re-attached to the swap - are all caught.
## [0.22.56] — 2026-11-09
### Fixed

* **A paper that quotes a replacement character was refused as a file that
  lost one.**
  Two releases ago the tool learned that a quotation holding U+FFFD was a
  quotation whose bytes were never decoded, and three readers - `check`,
  `draft` and `doctor` - asked that question of the text: is this character
  there? That is not the same question. U+FFFD says a byte *could* have been
  lost; only the decoder knows whether one *was*.

  A paper about text encodings prints one on purpose. Measured on a lossless
  UTF-8 manuscript reading `Notepad wrote <U+FFFD> where the byte could not be
  decoded.`, with its source page printing the same sentence verbatim:

  ```
  [high] claim-not-decoded at manuscript.md:3 (c1): 1 character of this quote
  were never decoded, so the quote was never searched - manuscript.md cannot be
  read as UTF-8 without loss. Convert it first, for example
  `iconv -f GBK -t utf-8 manuscript.md > utf8.md`
  citevouch: 1 claim - 0 verified, 0 moved, 0 missing, 1 skipped
  ```

  Every word of that is false. The file decodes losslessly, nothing was lost,
  the `iconv` advice would mangle it, and the quote is on page 1 - the matcher
  finds it at tier `exact`. `doctor` called the claims check failed. All three
  claim dialects agreed, so the wrong answer was not a parsing accident. A tool
  that refuses a correct quotation and sends the author to convert a healthy
  file is the failure mode this project exists to prevent, one step over from
  the one it fixed last.

  The decoder now reports what the reading cost. `_decode_text_and_loss()`
  returns the text and a flag; `_decode_text()` is the text half.
  `read_text_and_loss()` and `read_text()` mirror that pair for files, and
  `read_loses_bytes()` is the flag alone. The flag is `True` when the chosen
  reading had to replace a byte, which is exactly "a strict decode of these
  bytes with this codec raised". `check`, `draft` and `doctor` now require the
  flag **and** the character; a lossless file's U+FFFD is a character the
  author wrote, which is what a paper about encodings contains.

  Each branch of the decoder reports its own loss: the declared charset (read
  only after a strict decode succeeded) reports none, the UTF-16 swap reports
  none because a noise-free reading wrote no replacement character, and a
  truncated UTF-16 file reports the trailing byte it had to drop even though
  the text it produced is otherwise perfect.

  15 tests in `tests/test_quoted_replacement_character.py`, in all three claim
  dialects, plus the reverse cases: a GBK manuscript is still refused by
  `check` and by `doctor`, a genuine miss is still a miss, and a lossless file
  is still proposed for by `draft`. 12 mutations, all red - including the one
  that made the flag always `True`, the one that made it always `False`, and
  the four that gave one decoder branch another branch's answer.
## [0.22.55] — 2026-11-09
### Fixed

* **A sentence the file never decoded was compared with a page.**
  The previous release stopped `check` from accusing a quote whose
  characters were never decoded. `draft` was the other half, and it was
  still guessing: whether the ASCII `[@paper]` survives a GBK manuscript
  being read as UTF-8 depends on byte alignment (a 74-byte sentence
  swallows the `[` and the `@`; a longer one does not), so a manuscript
  could carry a citation `draft` found and a sentence it could not read.
  Measured on such a file, with the sentence printed verbatim on the
  source page:

  ```
  citevouch: 0 claim block(s) proposed (0 verbatim), 1 citation(s) left as comments
  <!-- line 1: paper - nothing on any page shares enough terms with the
       sentence (3 needed) -->
  ```

  Every word of that is true except the subject. The comparison really
  did find fewer than three shared terms - because the sentence it
  compared was 96 replacement characters - and the page was never at
  fault. A tool that sends an author to look at their source PDF for a
  fault in their own editor is the failure this project exists to avoid.

  The guard asks the sentence, not the file. A GBK manuscript can hold a
  perfectly readable ASCII sentence beside a destroyed Chinese one, and
  skipping both would be the same mistake with the sign flipped: measured
  on a mixed file, `text.count(UNDECODED)` skipped the citation whose
  sentence was never damaged. So the reason now names the sentence, the
  number of replacement characters that were its words, the manuscript
  that has to be converted, and the command that converts it:

  ```
  <!-- line 5: paper - the sentence this cites was never decoded: 67
       characters of it are replacement characters, so no page was searched
       for it - manuscript.md is not UTF-8. Convert it first, for example
       `iconv -f GBK -t utf-8 manuscript.md > utf8.md` -->
  ```

  `tests/test_undecoded_quote.py` grew a mixed-file project (one
  decodable citation, one destroyed) and four tests around it, and 8
  mutations die: no guard, counting the file instead of the sentence,
  inverting the condition, appending the reason without `continue`,
  dropping the count, dropping the file name, dropping the command.
## [0.22.54] — 2026-11-09
### Fixed

* **A quote nobody could read was reported as a quote the page does not have.**
  A manuscript saved in GBK - what a Chinese Windows editor writes by default -
  reaches `textnorm._decode_text`, which ends in
  `raw.decode("utf-8", errors="replace")`. A decoder that cannot fail has
  decided that every file is text. The fence line, the `quote:` label and the
  attributes are ASCII, so the claim block is still recognised, and only the
  quoted words become U+FFFD. Measured on a 111-byte GBK manuscript whose
  quoted sentence is printed verbatim on page 1 of its source:

  ```
  [high] quote-missing at manuscript.md:3 (c1): ���数据
  — quote not found in page.txt
  ```

  with exit 1, and the same byte stream recorded into `citevouch.lock.json`
  first, so the corrupted quote was also the evidence every later recorded run
  would check. `source-encoding` could not answer this: it judges a *source*
  file, and this is the manuscript. Nothing in the tool could: `doctor` printed
  nine `[ok  ]` lines and exited 0 while the run it explains was accusing the
  author.

  The bytes that were never decoded are known exactly - they are the positions
  where the decoder wrote a replacement character - so the claim says so
  instead of being searched. A claim whose quote holds one is counted as
  skipped, never as missing, and reported as `claim-not-decoded` (high) with
  the file and the `iconv` line that fixes it. `doctor`'s `claims` check fails
  with the same reading, and `draft` no longer answers a zero from such a file
  with "your citations were written in a form I do not read": it says the file
  was never decoded, in the stderr line and in the proposals file.

  What must still work, and does: a UTF-8 manuscript quoting a sentence the
  page does not print is still `quote-missing`; a page that legitimately holds
  U+FFFD is not the guard, because the guard is about the manuscript; and an
  eight-bit *source* file is still `source-encoding`, judged by
  `sources.encoding_problem` as before. A guard on one reader is not a guard on
  the format, and the two readers answer different nouns.

  17 tests, 11 mutations, all red.
## [0.22.53] — 2026-11-09
### Fixed

* **A page that names its own encoding was read as mojibake and its quote reported missing.** A source is refused as `source-encoding` when more than a quarter of its bytes cannot be UTF-8, and that share is measured over the whole file. An HTML header is ASCII, so it dilutes the share: measured on a one-claim project whose only source was a 239-byte GBK page carrying `<meta http-equiv="Content-Type" content="text/html; charset=gbk">`, `textnorm.invalid_utf8_share` scored 0.172 against the 0.25 line. The file slipped through the refusal, was decoded with `errors="replace"`, and its one Chinese sentence came back as

  ```
  [high] quote-missing at manuscript.md:1 (paper): 本文收集了六万八千个例句，全部来自语料库中的真实文本。 — quote not found in page.html
  ```

  with exit 1 - an accusation about a sentence printed verbatim in the file it was read from. The same page with one more sentence in it scores 0.254 and is refused correctly, which is why the defect only ever appeared on short documents.

  The tool now reads the encoding the document claims for itself - `<meta charset>`, the `http-equiv` spelling, and the XML declaration - and uses it, but only when the name is one Python knows *and* those bytes decode with it cleanly. Two things follow. A UTF-8 page labelled `gb2312` still reads as UTF-8, because the wrong declaration fails the second test; and a page with no declaration still gets the old byte-share judgement, so the defect is fixed without loosening the guard that caught it. Both are measured, and both have tests.

  Lowering the threshold was the alternative and it is wrong: a cp1252 French page scores 0.176 and reads perfectly, so the number is already as low as it can go. The share was never a bad guess about a file that could answer the question directly.

  `sources.encoding_problem` asks the same question as `textnorm._decode_text` and got the same answer, because a refusal that disagrees with the reader is the same mistake pointing the other way: measured, a longer GBK page scores 0.643 and would have been refused as unreadable by a reader that now reads it fine.

  20 tests, 9 mutations, all red.
## [0.22.52] — 2026-11-09
### Fixed

* **A sentence the browser never paints was verified as a quotation.** The HTML
  reader dropped inert elements by tag name (`script`, `style`, `template`,
  `textarea`, `iframe`) and that list was the whole rule. A browser can also be
  told to paint nothing about an element it does hold, and then the words are
  still in the file and still not on the page. Measured on a one-claim project
  whose only source held the sentence in each of these:

  - `<div style="display:none">We collected 40,688 examples from the corpus.</div>`
  - `<div style="visibility:hidden"></div>`
  - `<p hidden>`
  - `<span aria-hidden="true">`
  - a `<title>`
  - a `<datalist>` `<option>`

  Every one of them answered `[info] quote-found … quote found on page 1` and
  exited 0. The first three are the bug. The other three are the answer the tool
  should keep giving, because a reader can reach those words: an `aria-hidden`
  span is still painted for a sighted reader, a `<title>` is printed in the tab
  and the window bar, and a `<datalist>` option is painted when the list is
  opened. `hidden="until-found"` is the same case and is tested beside them - it
  is painted the moment the page is searched. Certifying words no reader can see
  is the one failure this tool cannot apologise for, and it does not care which
  mechanism hid them - exactly as it does not care whether the code was in a
  `<script>` or a `<template>`.

  The reader now reads the opening tag instead of the tag name: `_attributes()`
  is a real tokeniser (an attribute name starts where the previous value ends,
  and a value may be double-quoted, single-quoted or bare), `_style_hides()`
  says `display: none` or `visibility: hidden|collapse`, `_paints_nothing()`
  adds the `hidden` attribute when it is not `until-found`, and
  `_without_unpainted()` removes the whole element with a depth counter so a
  nested `<div>` goes with its parent and a sibling does not.

  The first attempt searched the tag for the word `hidden`. Measured against
  `title="hidden"`, `data-hidden="true"`, `class="hidden"`, `id="hidden"` and
  `aria-label="hidden"`, that dropped five elements nothing had hidden. The
  guard against it is not a narrower search but a tokeniser.

  37 tests, 13 mutations, all red.
## [0.22.51] — 2026-11-09
### Fixed

* **`draft` quoted half of a sentence the source printed across two pages.** The
  matcher learned to find a quotation that runs off the bottom of one page (0.22.49,
  `_page_runs` and `Match.spanned`), so the *match* covered every page of the run.
  `propose_quote` then looked the hit up by `match.page` alone -- the first page of the
  run -- and offered the verbatim branch only that page's own sentences.  A sentence
  that ends on the next page is not one of them, so the branch missed and the proposal
  fell back to the medium-confidence path, quoting whichever half of the sentence
  happened to fit on one page.  Measured on the same sentence in the same project:

    * whole on page 2: `1 quoting the sentence verbatim`, `confidence: high`,
      `page=2`, the complete sentence
    * split across pages 2 and 3: `1 claim block(s) proposed (0 verbatim)`,
      `confidence: medium`, `page=3`, and only
      `filtered them by hand before training the model on the remaining portion.`

  The verbatim search now reads the pages the match covers, and still names
  `match.page` - the page a reader starts on.  Stitching the whole document instead
  looks safer and is the one way this branch can be made to say "not verbatim" about a
  sentence the source prints exactly: page boundaries have no reliable sentence break,
  so a page ending `see also` merges into the next page's opening and the real sentence
  is no longer a sentence in the joined text.  Seven mutations of the new code are all
  red, including that one.
## [0.22.50] — 2026-11-09
### Fixed

* **A quotation whose figures run across three pages was called a fabrication.** The
  numbers tier -- the one that compares the words with every figure blanked out, so
  it can say "the words are the page's, the numbers are not" -- read one page at a
  time.  The exact and canonical tiers had already been taught to stitch adjacent
  pages; this one never was.  So a sentence that starts on page 2 and ends on page 4
  was found across the run when its figures were right, and reported
  `quote-missing` when a figure printed on page 3 disagreed:

    ```
    [high] quote-missing at manuscript.md:1 (c1): We collected a very large number of
    examples from the corpus and then filtered the 154,39... — quote not found in page.txt
    ```

  Page 3 printed `9,800`; the quote said `154,391`.  That is a typo, which this tool
  exists to name precisely, and it was reported as a fabricated quotation instead --
  the worst sentence available, about a passage the author can read on the pages they
  cited.  Worse, the run answered the harder question (are these the source's figures?)
  with the answer to the easier one (is this the source's sentence?).

  The tier now makes two passes: single pages first, then every run of adjacent pages,
  the same order the exact tier uses so a quote that fits on one page is still
  attributed to that page.  Both passes build their `Match` through one helper, because
  a second copy of the same twelve arguments is where the next wrong one would live.

  Two things had to follow it:

  * `_number_checks` is asked about every page of the run.  Reading only the first
    page would have reported a figure printed on page 3 as absent from the source.
  * The sentence names a run the way a reader names it.  It used to join the page
    numbers with `" or "`, so a three-page run read as *"page 2 or 3 or 4 of the source
    does not contain that number"* -- three pages offered as alternatives, when the
    finding means the number is on none of them.  It now says *"pages 2, 3 and 4 ...
    do not contain that number"*.

  `tests/test_numbers_across_pages.py` (10 tests) pins the code the run reports, the
  pages the sentence names, the single-page case (unchanged), the `Match` fields, and
  that `check --use-recorded` agrees with `check`.  Ten mutants, all red once two of
  them were re-aimed: the first campaign's "single-page pass always wins" and "the run
  pass only stitches two pages" both survived, because no fixture yet had a page-level
  match competing with a run-level match.
## [0.22.49] — 2026-11-09
### Fixed

* **A quotation that ran across two page breaks was reported missing.**
  The stitcher glued *pairs* of adjacent pages together, so a quote crossing one
  break was found and a quote crossing two was not.  Measured on a source whose
  sentence starts on page 2 and ends on page 4:

  ```text
  $ citevouch check manuscript.md --root .
  [high] quote-missing at manuscript.md:1 (c1): We collected a very large
  number of examples from the corpus and then filtered them by ha…
   — quote not found in page.txt
  ```

  The words are there, verbatim, in order.  A reader turning from page 2 to
  page 4 sees the sentence; only a program that reads two pages at a time
  cannot - and this tool's whole promise is that its sentences are true.

  `_page_pairs` became `_page_runs`, which stitches every run up to
  `MAX_STITCHED_PAGES` (4) instead of every pair, and `Match.spanned` records
  every page the quote touches rather than its two ends.  Four consequences are
  fixed with it: the "not a move" check now accepts the *middle* page of a run
  (a ledger saying 3 for a quote on 2-4 is right, and calling it a move would
  teach the author to edit a correct number); the message says "running onto
  pages 3 and 4"; the numbers check reads every page of the run, so a figure
  printed mid-run is no longer reported absent; and the run length is the outer
  loop, because a hint on an early page otherwise let a four-page run that
  merely *contained* the quote win over the three pages it occupies
  (`tests/test_cross_page_three.py`, 19 tests, nine mutants).
## [0.22.48] — 2026-11-09
### Fixed

* **`draft` proposed a claim block that `check` would refuse on sight.**
  v0.22.47 taught `scan` and `verify` that a source may not be the manuscript
  itself, and left `draft` out. So a `sources.toml` naming the manuscript, or a
  bibliography `file = {paper.md}` field, made `draft` write this into
  `claims.md` and tell the author to paste it back:

      ```claim id=knuth2020 source=knuth2020 page=1
      quote: |
        We collected precisely 987,654 examples under a blue moon \citep{knuth2020}.
      ```

  Pasting it back gave `[high] source-is-manuscript` - the tool produced, and
  recommended, the exact block its own next command rejects. A proposal the tool
  would refuse on sight is not a proposal; it is a trap with a citation in it.
  The three paths are now asked the same question the other two readers ask, and
  the skip note says which file is the problem and what to do about it
  (`tests/test_draft_source_is_manuscript.py`, 10 tests, six mutants).
## [0.22.47] — 2026-11-09
### Fixed

* **A manuscript could be its own source of evidence.** `sources.toml` is the
  file that says where a claim's proof lives, and it was never asked whether
  the place it named was the manuscript being checked. Measured on a project
  whose manifest maps `paper` to `paper.md`, with a sentence that exists
  nowhere except inside the claim block that asserts it:

  ```text
  $ citevouch check paper.md --root .
  [info] quote-found at paper.md:5 (c1): quote found on page 1

  citevouch: 1 claim — 1 verified, 0 moved, 0 missing
  worst severity: info
  ```

  The quote was searched for on page 1 of the file that contains it, so the
  tool certified its own input as independent evidence. It was not one route
  but three: the manifest, `--source paper.md`, and a byte-for-byte copy of the
  manuscript saved under another name all reached the same `quote-found`, while
  the same quote against a real page was correctly `quote-missing`. `scan` and
  the recorded pass now refuse a source that is the manuscript, by resolved
  path or by digest, and report the new `source-is-manuscript` code at `high` —
  the run fails instead of passing. The rule is about the file, not the text:
  a different file that happens to hold the same sentence still verifies, which
  is the ordinary case and is covered by a test.
## [0.22.46] — 2026-11-09
### Fixed

* **`scan --ledger` could write the ledger over the manuscript, the manifest or
  a source page.** The ledger is the one file this tool is meant to write, so
  the flag looks like an ordinary destination and nothing about it looks
  dangerous. Measured, on a project holding one claim:

  ```text
  $ citevouch scan paper.md --root . --ledger paper.md
  citevouch: wrote paper.md (1 claim)                          ->  exit 0
  ```

  The manuscript was 97 bytes of Markdown and 753 bytes of JSON afterwards.
  `--ledger sources.toml` replaced the manifest and `--ledger page.txt`
  replaced the page the quote came from; every one of them exited 0 and said
  what it had written, so the run reported success while deleting the evidence
  it had just recorded.

  `draft -o` had refused outputs like these since v0.19.52, but its list was
  built from the command line, so it missed the same class of file from the
  other end: `draft -o page.txt --force` wrote 511 bytes of proposals over the
  page `sources.toml` binds to `paper`, because that path is never typed on the
  command line.

  Both writers now ask one list, `cli._project_inputs`, built from what the run
  actually read rather than from its flags: the manuscript, both manifest
  names, every source the manifest or `--source` bound, every `--bib` file, and
  the ledger. The comparison is by resolved path, and the sentence names the
  file *and* what it is to the project — an author who typed only `--ledger
  page.txt` has never seen the manifest line that binds it, so echoing the path
  back leaves them asking where it came from. `scan --dry-run` is not refused,
  because it writes nothing.

  Proved by `tests/test_ledger_overwrites_input.py` (13), which asserts the
  bytes of every protected file rather than only the exit code, and by nine
  mutations of the guard — one of them survived until a test spelled one file
  two ways with `..`, because `Path` discards a leading `./` and the original
  spelling test could not tell a resolved comparison from a textual one.
## [0.22.45] — 2026-11-09
### Fixed

* **The command `draft` told the author to run next failed on its own output.** `draft` ends by naming the `check` command that reads the file it just wrote. That sentence was built from the output path alone, so a run with a `--root` printed an advice without it:

  ```text
  $ citevouch draft proj/paper.md --root proj -o claims.md --bib proj/refs.bib
  citevouch: wrote claims.md; read it, then `citevouch check claims.md` to see what it got wrong
  $ citevouch check claims.md
  [high] source-missing at claims.md:11 (knuth2020): claim knuth2020 names source='knuth2020' but no entry in sources.toml ...
  ```

  The second command ran against the current directory instead of the project and accused a claim `draft` had itself just quoted verbatim from a page it had read. `draft` is the first command a new user runs, so the last thing it said was a false accusation about its own work.

  The advice is now built by `cli._check_advice(output, root)` from the values the run actually used: it carries `--root` whenever the run did (and omits it for `--root .`, where there is nothing to add), prints the path with forward slashes because a Windows backslash is an escape in a shell, and quotes any argument that needs it through `cli._shell_word` - including the `'` → `'\''` case, since an apostrophe in a filename would otherwise end the quote early. `tests/test_draft_advice_runs.py` (6 tests) walks the command out of the output and runs it, so the test fails on the same thing a user would. Six mutations, `survivors: []`.
## [0.22.44] — 2026-11-09
### Fixed

* **`draft --bib` threw away everything the bibliography parser said.** `draft` read every `--bib` file for one reason - to answer "where is the local file for this key" - and the file it was answering for could be one the parser had only half read. An unclosed entry, a binary file or a duplicate key produced no output at all:

  ```text
  $ citevouch draft paper.md --root . -o claims.md --bib refs.bib
  citevouch: 0 claim block(s) proposed (0 verbatim), 1 citation(s) left as comments
  ```

  and because the entry never parsed, the key had no entry to answer with, so the comment written for it said the bibliography had no `file` field - about a `.bib` that has one on line 5:

  ```text
  <!-- line 1: knuth2020 - no local file: not in sources.toml, no `file` field in the bibliography, and no file named after the key -->
  ```

  `scan` on the same project reported `bib-unparsed-entry` and `bib-unreadable`; the command whose whole job is to tell the author what it could not look at said nothing. This is the false sentence v0.19.63 fixed for the `scan` path, still standing in the command that reads the file to answer that exact question.

  `cmd_draft` now keeps the parse findings, prints them before its summary, merges entries through `merge_entries` (so a key defined in two `--bib` files is reported here too), and passes `draft` a set of keys the bibliography *named* without producing an entry for. `_why_no_file` says "the bibliography could not be fully read, so no entry was parsed for 'knuth2020'" for those, and keeps the generic sentence for a readable bibliography that simply does not mention the key. `tests/test_draft_bib_findings.py` (14 tests); ten mutations, `survivors: []`.
## [0.22.43] — 2026-11-09
### Fixed

* **Two `--bib` files that define one key silently overwrote each other.**  `parse_bib` reports a key defined twice *inside one file* (`bib-duplicate-key`, high). Two files each defining it once produced no finding at all, because `scan` merged them with `dict.update`: the later file replaced the earlier one, so which work a claim rested on was decided by the order of the `--bib` flags.

  ```text
  $ citevouch scan manuscript.md --bib a.bib --bib b.bib
  citevouch: wrote citevouch.lock.json (1 claim)      # exit 0, no finding
  ```

  `a.bib` called `knuth2020` a book and `b.bib` called the same key a different article; the ledger kept whichever file came last on the command line, and the run was green either way. The `check --use-recorded` path that `action.yml` runs had the same silence, because it merged the re-read files the same way.

  Both merges now go through `bibtex.merge_entries`, which reports the clash as `bib-duplicate-key` (high) and names **both** files and the key. The later entry still wins, so reporting the clash does not change the verdict: the fix must not decide the answer instead of the evidence. The same file named twice is not a clash - both passes read the same bytes.

  `tests/test_bib_cross_file_keys.py` (14 tests) covers both orders, three files defining one key, the recorded and live passes, and the cases that must stay silent: two files with different keys, one entry, one file naming a key twice (still one finding), and one file passed twice. Nine mutations, all red - including one that replaced the newly added test, which is how the `--bib a.bib --bib a.bib` case got pinned.

  *Not covered*: `citevouch draft --bib` reads the same files but never prints their parse findings at all - not this one, and not the ones that already existed - so the clause above applies to `scan`, `check` and `verify` only. That silence is older than this change and is left alone here.
## [0.22.42] — 2026-11-09
### Fixed

- **The recorded pass re-read the bibliography and then judged the copy it remembered.** Since 0.22.33 the recorded pass opens every bibliography the ledger names, so that a file nobody could read is not silently treated as a file nobody mentioned. The parse findings came from that fresh read; the *verdicts* - which keys exist, which entries are unused, which entries are missing required fields - were still computed from `ledger.entries`, the mapping captured when `scan` ran. One run therefore held two opinions about one file, and the stale one was the one that spoke. Measured on a project scanned with a bibliography holding `knuth2020`, then edited so the file holds only `lamport1994`:

  ```text
  $ citevouch check manuscript.md --bib refs.bib
  [high] bib-key-missing at manuscript.md:1 (c1): claim c1 cites 'knuth2020', which is not in the bibliography the ledger recorded
  $ citevouch check manuscript.md --use-recorded
  [info] quote-found at manuscript.md:1 (c1): quote found on page 1
  ```

  The mirror image held for fields: an entry that lacked `publisher` and `year` kept its `bib-field-empty` complaint after the file had replaced it with a complete one, so the author was told about required fields of an entry that no longer existed. `action.yml` runs `check --use-recorded`, so that was the sentence a pull request showed.

  The verdicts now come from the entries this run actually read. A file that is missing or unreadable simply yields nothing, so nothing in it is judged: the `source-missing` or `bib-unreadable` finding says why, and a key missing from a file nobody could read is not a missing key. Only two runs still read the recorded mapping, and neither of them opened a file: `scan` already put what it read into the ledger this same run (`fresh`), and a ledger written before the field existed names no file at all. `tests/test_bibliography_fresh_verdicts.py` (10 tests) pins both directions: the recorded pass now agrees with the live one on a replaced bibliography, never reports the two contradictory verdicts together, and stays silent when the bibliography itself could not be read.
## [0.22.41] — 2026-11-09
### Fixed

* **`report` printed the same bibliography line for two opposite facts.**
  A project scanned with `--bib refs.bib` where that file held no readable
  entry and a project that never passed `--bib` at all both printed
  `- bibliography: 0 entries`. The ledger has recorded the file name since
  0.22.33 (`Ledger.bibliographies`); the command whose whole job is "what
  does the ledger say" simply never read that field. The two runs, before:

  ```text
  $ citevouch scan manuscript.md --root . --bib refs.bib   # refs.bib is binary
  [high] bib-unreadable at refs.bib:1: not one entry could be read from refs.bib
  citevouch: wrote citevouch.lock.json (1 claim)
  $ citevouch report --root .
  - bibliography: 0 entries

  $ citevouch scan manuscript.md --root .        # no --bib at all
  citevouch: wrote citevouch.lock.json (1 claim)
  $ citevouch report --root .
  - bibliography: 0 entries
  ```

  The line now names the files and then their size - `refs.bib (0 entries)`
  against `none recorded (0 entries)` - so the report distinguishes a
  bibliography that was given and could not be read from one that was never
  given. A ledger written before the field existed says `none recorded`,
  which is what it means rather than a claim about the project. The JSON
  payload's `ledger` object gained the same list, for the readers that never
  see the table.

  Proved by `tests/test_report_names_bibliography.py` (10), and by eight
  mutants that all go red: the line back to counting only, names dropped
  when nothing could be read, names never printed, `none recorded` replaced
  by a bare count, no clipping, the count left off, the JSON field removed,
  the JSON field written empty.
## [0.22.40] — 2026-11-09
### Fixed

* **Three commands pasted the name they were pointing at into the sentence.**
  `\captionof{table}{We collected 154,391 examples.}` converted to
  `tableWe collected 154,391 examples.` - the float type glued to the first
  word - and `draft` then compared a sentence the author never wrote against
  the page. A citation that is verbatim in the source came back as
  `0 claim block(s) proposed: 0 quoting the sentence verbatim`:

  ```text
  # plain paragraph in the .tex
  1 claim block(s) proposed: 1 quoting the sentence verbatim
  <!-- confidence: high - the manuscript's sentence appears verbatim in the source -->

  # the same sentence inside \captionof{table}{...}
  0 claim block(s) proposed: 0 quoting the sentence verbatim
  ```

  `\rotatebox{90}{...}` leaked `90`, and `\hyperref[sec:data]{...}` leaked
  `[sec:data]`. All three take one argument that names something and one that
  is prose; none of them was in `_SKIP_FIRST_ARGUMENT`, so they fell through to
  the unknown-command branch, which drops the command name and keeps every
  argument. `\captionof` is the caption package's way of titling a float that
  is not a float - the normal spelling for a table set inside a paragraph - so
  this was not an exotic input.

  `\nameref` and `\vref` were the mirror image: they are `\ref` with a
  different name, `\ref`'s argument is already dropped, and these two were not
  in that set, so `see \nameref{sec:data} for details.` put the label key in
  the prose as a word.

  *Not covered*: the `\hyperref` adjustment keys off a `[` before the first
  braced argument, so a paper that writes `\hyperref [label]{text}` with a space
  before the bracket is read as the braced form. The braced form keeps its
  words, so the failure is a leaked `[label]`, not lost text. `\stackrel`,
  `\overset` and `\underbrace` leak their first argument too, but all three
  are math and read by `_plain_math`, which keeps the digits a reader sees; left
  alone deliberately.
## [0.22.39] — 2026-11-09
### Fixed

* **A long table's caption was dropped along with its cells.**
  `table` keeps its caption *outside* the grid, so dropping `tabular` always
  left the caption alone. `longtable`, `xltabular` and `longtabu` are the other
  way round - they break across pages and repeat the caption in a running head,
  so `\caption` is written *inside* the environment. Dropping the body dropped a
  sentence the author wrote and a reader sees, and with it the citation printed
  under the table.

  Measured before the fix, `draft` on a paper whose longtable caption cites
  `knuth2020` in plain sight:

  ```text
  citevouch: 0 claim block(s) proposed: no citations were found to propose them for
             (this command reads `[@key]` and `\cite{key}`)
  ```

  The cells are still dropped - they are data, and a key labelling a row is not
  a citation of the paper's argument. The caption is prose, so it is converted
  and appended after the (dropped) table. A `\caption` that appears inside a
  `verbatim`/`lstlisting` block nested in the table is not lifted: that one is a
  demonstration of the syntax, not a caption of this table.

  `tests/test_table_caption.py` (21 tests) covers the three packages, the
  optional short caption (the long one is what a reader sees), `\caption*`, two
  captions in one table, a caption printed inside a listing, a caption outside
  the environment not being lifted twice, and the end-to-end `draft` run that
  used to say no citations were found. Nine mutations, `survivors: []`.
## [0.22.38] — 2026-11-09
### Fixed

* **A table was read as prose unless the author happened to use `tabular`.**
  `_DROP_ENVIRONMENT` named `tabular` and `tabular*` and nothing else, so the
  package that draws the table decided whether the tool read it. `tabularx`,
  `xltabular`, `tabulary`, `longtable`, `tabu`, `longtabu` and `supertabular`
  were not on the list: their column specification leaked into the text as a
  word and every cell was read as a sentence.

  Measured before the fix, converting one `tabularx` table:

  ```text
  \begin{tabularx}{\linewidth}{lX}
  Baseline \citep{knuth2020} & 90,000 \\

  to_text -> 'lX
              Baseline [@knuth2020] & 90,000'
  ```

  `draft` then reported `0 claim block(s) proposed (0 verbatim), 1 citation(s)
  left as comments` and blamed the page for not containing

  ```text
  <!-- line 9: knuth2020 - nothing on any page shares enough terms with the sentence (3 needed) -->
  ```

  - a sentence that is a row of a table, assembled out of a column spec and two
  ampersands. The same table written with `tabular` was dropped whole and the
  run truthfully said no citations were found. One paper, one table, two
  verdicts, chosen by a package name.

  All seven are now dropped like `tabular` was. `tests/test_table_environments.py`
  (44 tests) pins the cells, the column spec, the citation in a cell, a table
  nested in the same environment, an unclosed table, the includes inside one,
  and - just as important - that `array` and the `matrix` family and the
  display-math environments keep their numbers, because a formula's numbers are
  what a reader sees. Ten mutations, `survivors: []`.
## [0.22.37] — 2026-11-09
### Fixed

* **A bibliography was recorded two ways in one ledger.**
  `sources.toml`'s paths and the ledger's own `bibliographies` list are
  recorded relative to `--root` with forward slashes, so a ledger written on
  Windows resolves on the Linux job that runs the same commit. The bibliography
  *entries* were not: they were handed the path exactly as the shell spelled
  it, so one project produced two ledgers depending on which directory the
  command was typed in:

  ```text
  scan proj/manuscript.md --root proj --bib proj/sub/refs.bib
    entries['knuth2020'].path = 'proj\sub\refs.bib'
    bibliographies            = ['sub/refs.bib']
  cd proj && scan manuscript.md --root . --bib sub/refs.bib
    entries['knuth2020'].path = 'sub\refs.bib'
  ```

  Whichever shell ran, the other one read a path it had not written, and every
  finding built on that entry named it back in the author's spelling. The
  recorded path is now computed in one place (`scan.recorded_path`, renamed
  from `_ledger_path` because two modules need it and a private name collides
  with the CLI's own flag resolver), and all four call sites that hand a
  bibliography to the parser use it: the recording pass, the live `check
  --bib`, `verify`'s re-read, and `draft --bib`.

  One reader had to move with it: `draft` resolved a bib entry's `file` field
  against `entry.path`'s folder, which only worked because that path used to
  be relative to the shell. It is now joined to the root, which is what the
  ledger's paths have always meant.

  A path outside `--root` still keeps its absolute form — there is no honest
  relative spelling for it, and inventing one would move a finding onto some
  other file.
## [0.22.36] — 2026-11-09
### Fixed

* **A `--quiet` run that failed handed GitHub code scanning an empty document, and no reason.**
  `--quiet` shortens the *display*: info and low findings are held back, and a
  run can still fail because of them. Three of the four writers said so in
  words - the text writer and the Markdown writer print "N findings at or above
  `--fail-on X` were hidden by `--quiet`; that is why this run failed", and the
  JSON writer at least exposes `hidden` and `worst`. The SARIF writer, which is
  the one CI actually uploads, was never asked. Measured on a project holding
  one low `claim-without-evidence` and one info `quote-found`:

  ```text
  --format text     1 finding at or above --fail-on low was hidden by --quiet ...
  --format markdown **1** finding at or above `--fail-on low` was hidden ...
  --format json     findings: [], hidden: 2, worst: low
  --format sarif    results: [], no "invocations" key at all
  ```

  All four exited 1. The last line is the failure: code scanning received a
  document that says a successful analysis found nothing, while the job was
  red for a reason no reader of that document could see. A gate whose red has
  no explanation is the same defect as a green tick over an unchecked claim.

  `render_sarif` now takes the whole run and the threshold, and when
  `--quiet` held back a finding that reaches `--fail-on`, it writes
  `runs[0].invocations[0]` with `executionSuccessful: false` and one
  `toolExecutionNotifications` message naming the count and the threshold.
  `results` is untouched, so `--quiet` still means what it meant. Runs that
  never hid a failing finding get no `invocations` key at all, so their bytes
  do not change.

  `render_json` gained the two keys a reader was previously left to infer -
  `failing_hidden` and `fail_on` - and both are written only when non-zero.
  Writing them exposed a second defect in the same function: it computed
  `hidden` by subtracting two lengths, so a run holding the same finding
  object twice reported one *hidden* finding over a payload that listed it.
  Both writers now subtract by identity.

  Covered by `tests/test_sarif_quiet.py` (23 tests) and proven by 13 mutations,
  every one of which turns the suite red.
## [0.22.35] — 2026-11-09
### Fixed

* **A Markdown container marker travelled into the `claim:` text `draft` proposes.**
  A blockquote (`> `), a bullet (`- `, `* `, `+ `), a heading (`## `) and a
  parenthesised ordinal (`1) `) are ways of *showing* a sentence; the marker is
  typography, and no reader of the rendered page sees it. `draft` read the raw
  line, so the marker was copied into the `claim:` field the author is told to
  paste, and the sentence then failed to match its own source verbatim - the
  page has no `>` either. Measured on one page holding
  `We collected 154,391 examples from the corpus.` quoted word for word in the
  manuscript:

  ```text
  plain paragraph   -> confidence: high    1 proposal
  > / - / * / + / # -> 0 claim block(s) proposed
  ```

  and the comment left in the proposal blamed the author's sentence: "nothing
  on any page shares enough terms with the sentence (3 needed)" - about a
  sentence the page shares four terms with and prints word for word. A false
  reason attached to a real loss is worse than silence, because it sends the
  author to rewrite the sentence that was already right. `statement_of` now
  drops the container prefix from every line (a wrapped blockquote loses one
  marker per line), which fixes both the proposal and the confidence in one
  place. Marker lookalikes stay: `-- x`, `-3 degrees`, `2.5 million`,
  `#hashtag`, `a > b`, and a four-space indent, which CommonMark reads as a
  code block.
## [0.22.34] — 2026-11-09
### Fixed

* **A credibility mark with no claim block was invisible on the CI path.**
  `scan` asks `scan_unbound_markers` about every 【原文】 line no claim block
  covers, and says so. `verify` - which is all `check --use-recorded` does, and
  all `action.yml` runs on a pull request - re-parses the manuscript to
  re-derive the blocks the parser refused, and then never asked about the
  marks. A manuscript holding a marked sentence and an unrelated claim block
  therefore produced:

  ```text
  check                 -> [low] claim-without-evidence at manuscript.md:1
  check --use-recorded  -> [info] quote-found at manuscript.md:3 (c1)
  ```

  A mark without a block is the single most common way a manuscript looks
  verified while nothing on that line can be checked, so the one path that
  never reported it was the one path that runs on every pull request. The
  recorded pass now asks the same function with the same spans and claims, so
  a mark a block covers stays quiet for exactly the reason `scan` keeps it
  quiet, and a mark it does not cover is reported once.
* **The demo's own output changes with this fix.**
  Its two unbound marks at `demo/manuscript.md:52` and `:54` now appear in
  `verify`'s output, so both README examples show them and `docs/img/` was
  regenerated. The red line is unchanged: `5 claims — 4 verified, 0 moved, 1
  missing`, worst `high`, exit 1. Covered by
  `tests/test_unbound_markers_recorded.py` (13 tests) and four mutations, all
  red.
## [0.22.33] — 2026-11-09

## [0.22.33] — 2026-11-09
### Fixed

* **A bibliography nobody could read was silent on the recorded path.**
  `scan --bib` reports `bib-unreadable`, `bib-unparsed-entry` and
  `bib-entry-header-unparsed`; the ledger stores only the *entries* a
  bibliography yielded, so a file that yielded none recorded as the same empty
  mapping as a project that named no bibliography. `check --use-recorded` -
  which `action.yml` runs on every pull request - then saw an empty mapping and
  said nothing:

      scan                  -> 1, [high] bib-unreadable
      check --use-recorded  -> 0, [info] quote-found

  A binary `refs.bib`, an entry left unclosed, a path that is no longer there:
  all three were findings only the one command that nobody runs in CI produced.
  The ledger now records the bibliography files it read (`bibliographies`), and
  the recorded pass re-reads them and reports their findings, exactly as it
  re-parses the manuscript when the recorded digest matches. A deleted
  bibliography is reported as `source-missing` by name. `--allow-stale` does not
  silence it: that flag says the ledger describes an older draft of the
  manuscript, and it says nothing about the bibliography being gone - the same
  reason `source-missing` and `source-changed` already run under it. The live
  `check` still names each failure once, because `fresh` is the one case where
  `scan` returned the findings a line earlier. Ledgers written before this key
  existed read as "no bibliography named", so an existing project keeps its
  current verdict until it runs `scan --bib` again.
  Proved by `tests/test_bibliography_recorded.py` (17), and by nine mutations -
  including "scan records only the files it could parse" and "the recorded pass
  re-reads only when the manuscript digest matches" - each of which turns the
  suite red.
## [0.22.32] — 2026-11-09
### Fixed

* **A table claim row with an empty cell made the file look empty.**

  The table dialect is five cells wide: `| id | source | page | quote | claim |`.
  `_TABLE_CLAIM` required a character in the `id` cell and a digit-or-`-` in the
  `page` cell, so a row with either one left blank matched nothing at all.  The
  row then belonged to no claim and to no span, and a one-row manuscript was
  reported as holding no claim block whatsoever.  Measured on a one-page source
  whose quote is verbatim on page 1:

  ```
  | c1 | paper |  | <quote> | ok |   ->  [high] no-claim-blocks at m.md:
  |  | paper | 1 | <quote> | ok |        m.md contains no claim blocks, so
                                        nothing was checked: ... This file
                                        has none.                        exit 1
  ```

  Both rows plainly hold a claim.  The quietest shape was worse: a blank-`page`
  row followed by a good row gave `1 claim - 1 verified, 0 moved, 0 missing`,
  exit 0, and not one line mentioned the row the parser had walked past.

  An empty cell is not a syntax error - it is a claim the author has not
  finished, and both omissions already had an honest answer in `_claim_from`:

  * a blank `id` gives `claim-uncheckable: claim block has no id= attribute`,
    the same sentence the fence dialect gives;
  * a blank `page` means "no page hint", which is what `-` already meant.

  `_TABLE_CLAIM` now allows both cells to be empty, so the row is read and the
  finding names the line.  A header row (`| id | source | page | ... |`) is
  still not a claim: its `page` cell holds the word `page`.

  `tests/test_table_blank_cells.py` (11 tests) covers the four shapes, the
  parser directly, and the wrapped-row detector.  Five mutants, no survivors:
  the id cell required again, the page cell required again, a blank id filled
  with a placeholder, a blank page turned into page 0, and the wrapped-row
  detector retyping the table shape instead of deriving it from
  `_TABLE_CLAIM.pattern` (that last one survived until the wrapped-row test
  existed, which is why it is in the file).

* **The test for that fix passed here and failed on all three Windows jobs.**

  `tests/test_table_blank_cells.py` runs the command in a child process and
  compared its output against a summary line containing an em dash. It did not
  pin an encoding on either end, so the child wrote with the Windows code page
  and the parent decoded with the locale: `EF BF BD` on one side of the
  comparison and `E2 80 94` on the other. This machine's locale and code page
  both happen to be UTF-8, so the assertion held locally; on
  `windows-latest` (3.10, 3.12 and 3.13) it failed with
  `assert '1 claim � 1 verified' in '... citevouch: 1 claim — 1 verified ...'`
  and the release was skipped.

  The child now gets `PYTHONIOENCODING=utf-8` and the parent decodes with
  `encoding="utf-8"`. The product code was never wrong - only the test that
  watched it was reading a byte sequence it had assumed was text.
## [0.22.31] — 2026-11-09
### Fixed

* **A colon on a claim block's opening line was parsed away in silence.**

  The body of a claim block writes its fields as a mapping - `quote: |`, `id: c1` -
  and the opening line only understands `key=value`. An author who wrote the
  page hint one line up the same way was doing what the format taught them.

  Measured on a two-page source whose quote is on page 1, asking for page 9:

  ```text
  ```claim id=c1 source=paper page=9     -> [high] page-out-of-range
  ```claim id=c1 source=paper page: 9    -> [info] quote-found page 1, exit 0
  ```

  The second block asked a question about page 9 and the answer came from page 1,
  with no line saying the hint had been dropped. `id: c1` was worse: the bare
  token became the claim's name, so every finding in the run read `(id:)` - a
  name the author never wrote - and the ledger recorded it.

  Now the opening line reports a `key:` spelling as `claim-field-unknown`,
  naming the attribute and the `=` spelling that would have worked. It still
  does **not** apply the key: deciding whether `page: 9` is a hint or a note is
  a format decision, and a wrong guess is worse than the silence this replaces.
  A colon inside a quoted value is not a field, and a colon inside a bare value
  (`source=weird:name`) is still one value, not one either.

  Covered by `tests/test_opening_line_colons.py` (12 tests) across both dialects
  and both verbs; eight mutations of the new code all go red.
## [0.22.30] — 2026-11-08
### Fixed

* **A bad `--ledger` path was reported as a problem inside the file.**

  The four verbs that read a ledger asked the JSON parser first and the path
  second, so a path that could not be a file at all came back as a parse
  error:

  ```text
  $ citevouch report --ledger adir
  citevouch: ledger adir is not readable JSON: [Errno 13] Permission denied: 'adir'
  ```

  Nothing is wrong with the JSON: `adir` is a directory. The sentence sends
  the author to the parser, where there is nothing to find. A ledger under a
  file was worse - it said the ledger was simply absent:

  ```text
  $ citevouch report --ledger manuscript.md/x.json
  citevouch: no ledger at manuscript.md\x.json; run `citevouch scan` first
  ```

  That advice fails too, with a third sentence: `scan` cannot write there
  either, because its parent is a file.

  The write side already had the right wording (`adir is a directory, not a
  file`), so the same mistake produced two different sentences depending on
  which direction touched it. Both sides now ask one helper,
  `_unusable_target`, and the read side asks it before the existence test.
  One mistake, one sentence, whichever verb met it.

  Only the wording changed: every shape still exits 2, a missing ledger still
  says `no ledger at ...; run `citevouch scan` first`, and a real syntax
  error still names the line the parser stopped on.

  Covered by `tests/test_ledger_path_shapes.py` (13 tests: the read side
  saying what the write side says, all three reading verbs agreeing, the
  path-under-a-file case naming the file, the two shapes that were already
  correct staying correct, and the helper being the single place the
  judgement lives).
## [0.22.29] — 2026-11-08
### Fixed

* **A code sample in the manuscript was counted as a claim block the run could not check.**

  A fenced ```` ```python ```` block, a `~~~` fence and a four-backtick fence all made the summary line claim one more block than the file held. Measured on a manuscript with one real claim and one Python sample:

  ```text
  citevouch: 1 claim — 1 verified, 0 moved, 0 missing
  2 claim blocks — 1 of which this run could not check
  worst severity: info
  ```

  There was one block. The same manuscript in `citevouch doctor` read `2 claim blocks, 1 of which the parser could read; the next command names the rest` - and no command named anything, because the "unread" block was a sample that was never meant to be read.

  The cause is two questions sharing one list. `ParseResult.spans` answers "which line ranges may not be searched for prose", so it must be wide: a sample that shows a claim block must not have its own body reported as an unread claim. Counting blocks is a different question with a narrower answer, so `ParseResult` now carries `claim_spans` beside `spans`, and the summary line and `doctor` both count `claim_spans`.

* **`tools/format_check.sh` exited 1 on this machine without printing anything.**

  The fourth gate printed no output and failed, while the same file list passed under `ruff` directly. `set -eu` plus the idiom `[ "$status" -eq 123 ] && status=1` terminated the script in the `sh` shipped with this shell before the summary line was written; the same script is green under Git Bash and on CI. The behaviour changed with nothing but the wording of the comments above that line, so it was not a logic bug to reason about - it was an environment property to measure. The line is now an `if`, which says the same thing and does not depend on how a shell treats a failing `&&` in the middle of a `set -e` script.
## [0.22.28] — 2026-11-07
### Fixed

* **The summary line counted the claims the ledger held, not the blocks the manuscript held.**

  `citevouch: N claims — V verified, M moved, X missing` is the last line of every run, and it was built from `ledger.claims`. The ledger records only the blocks the parser *accepted*: a block with no `source=` is refused, so it reaches neither `verified` nor `missing` nor `skipped`, and the sentence describes a smaller document than the one just read. Measured on a manuscript holding one accepted claim and one block with no `source=`:

  ```text
  [high] claim-uncheckable at manuscript.md:6 (c2): claim c2 names no source=; the quote cannot be looked up
  [info] quote-found at manuscript.md:1 (c1): quote found on page 1
  citevouch: 1 claim — 1 verified, 0 moved, 0 missing
  worst severity: high
  ```

  Two blocks were in the file. The run was red, so nothing was hidden from the exit code; what was hidden is how much of the manuscript the numbers described.

  The line now carries a second sentence only when there is a gap to report:

  ```text
  citevouch: 1 claim — 1 verified, 0 moved, 0 missing
  2 claim blocks — 1 of which this run could not check
  worst severity: high
  ```

  `--format json` gains `summary.blocks` and `summary.unrecorded`, and `--format markdown` gains the same clause, because those are the two formats a dashboard or a pasted report reads.

  The count is one subtraction in `src/citevouch/verify.py`: every span the parser could see, minus every claim it could record (`_unrecorded`). An unclosed fence is deliberately *not* counted there — it still yields a claim, so it is checked like any other, and saying "1 block, 1 not checked" for it would be false in the other direction.

  The live `check` builds its ledger from the text on disk and then verifies with `check_manuscript_hash=False`, so it never re-parsed; `verify()` gained a `fresh=` argument that takes the count from a parse of that same text without re-adding the findings `scan` already returned. `tests/test_tally_counts_blocks.py` (14 tests) covers the text line, the JSON summary, the Markdown report, the quiet cases, and the demo. Nine mutants — none counted, all spans counted, clause never printed, `blocks` returning `checked`, the fresh pass not counting, the JSON fields dropped, the Markdown clause dropped, the live check not fresh, the plural dropped — all go red.
## [0.22.27] — 2026-11-06
### Fixed

* **A claim block's `marker=` said which mark vouches for it, and the scan never read it.**

  `marker=` has been parsed from the opening line since the first commit, stored on
  `Claim.marker`, written to the ledger and read back from it - and used by nothing.  A
  manuscript that wrote the binding got both halves of the contradiction in one run:

      【原文】PyFCG 3.3 installs cleanly.

      ```claim id=c1 source=a marker=【原文】
      quote: |
        PyFCG 3.3 installs cleanly.
      ```

  The ledger recorded `marker='【原文】'` for `c1`, and `scan` printed
  `[low] claim-without-evidence at m.md:1: the 【原文】 mark on this line has no claim
  block, so nothing ties it to a page in a local source` in the same run.  Two
  guards keep the binding from silencing a real finding: the mark has to head the
  *neighbouring* paragraph (not somewhere further up the page, and not across
  another block), and it has to be wanted by exactly one block - two marks either
  side of one block are two readings of the same sentence, and guessing would hide
  which one the author meant.

  The table dialect has five fixed columns and no attribute grammar, so a table
  row cannot write `marker=`; a mark beside a table row stays unbound, which is
  the honest answer.

  `tests/test_marker_attribute.py` (21 tests).  Nine mutations, all red: binding
  nothing, ignoring the caller's marker list, accepting any nearby mark, keeping
  only the paragraph above, only the paragraph below, binding a mark two blocks
  both want, letting the paragraph search cross a block, dropping the `bound`
  check in the scan, and matching without setting aside the Markdown that may
  precede a sentence.
## [0.22.26] — 2026-11-06
### Fixed
**A sentence that only *described* the credibility notation was reported as an unbound claim.**

`scan_unbound_markers` asked whether a marker's characters appeared anywhere in a line, and reported the line if they did. The demo's own manuscript carries the convention's introduction at line 3:

```
> 这份节选保留了原档的【原文】/【实测】/【推测】三级标记约定，只是把
```

`citevouch scan demo/manuscript.md` accused that sentence of making a claim with no evidence on the page. The advice the finding earns — bind a claim block to it — is advice to annotate a glossary.

* The convention is a *prefix*: a line that opens with a mark vouches for what follows.
* The scan now sets aside the Markdown that may stand in front of a sentence — indentation (including the ideographic space), `>`, bullets, ordered-list numbers, emphasis — and then asks whether the mark opens the line.
* On the demo, the two real marks stay reported and the remark does not:

```
[low] claim-without-evidence at manuscript.md:52: the 【原文】 mark on this line has no claim block, ...
[low] claim-without-evidence at manuscript.md:54: the 【推测】 mark on this line has no claim block, ...
```

* `tests/test_marker_position.py` (31 tests) covers thirteen kinds of prefix, the six documented marks, five ways a line merely *mentions* the notation (mid-sentence, inline code, HTML comment, table cell, after a name), and the demo itself.
* Six mutants, all red: the containment test restored, no decoration set aside, whitespace only, nothing set aside, containment after the decoration, and the spans exemption removed.

A mark that trails its sentence is now a miss rather than a finding. That is the same direction the rest of this file has taken when a guess would accuse a reader: silence costs a nudge, a false accusation costs the reader's trust in line 3.
## [0.22.25] — 2026-11-06
### Fixed
**A misspelt attribute on a claim block's fence line was parsed, stored and never read.**

`_attrs` reads every `key=value` token on the opening line into a dict, and `_claim_from` then looks up six names. A seventh token was kept and never consulted, so the claim it was meant to steer ran without it and every line of output was written as if it had. On a project that prints the same sentence on page 1 and on page 3:

```
```claim id=c1 source=paper page=3   -> quote-found page 3
```claim id=c1 source=paper pgae=3   -> quote-found page 1, exit 0, no finding
```

The author asked for page 3 and was answered from page 1, silently. The body path has refused this since the `Page: 1` fix: a left-margin line that reads like a field but names no known key is reported as `claim-field-unknown`. The fence line - where the format is documented and where most people write their attributes - had no such guard.

The same report now covers both places, under two conditions that both earn their place:

* **a near miss**, one edit away from a key this format has, including a transposition (`pgae` costs one, not two, because swapped letters are the typo the fingers actually make), so some other tool's `data-x=` is left alone;* **the right spelling is absent** - a block writing both `page=3` and an unrelated `pgae=1` has lost nothing, and silence there is correct.

The misspelt key is still dropped rather than applied: guessing which key an author meant is a format decision, not a reader's call. `tests/test_opening_line_fields.py` (35 tests) covers both dialects, both edit shapes, the quiet cases and the severity contract; seven mutations, `survivors: none`.
## [0.22.24] — 2026-11-05
### Fixed
**A manuscript saved with CRLF and the same manuscript saved with LF drafted differently.**

Windows editors write `\r\n`, and this tool's `read_text` kept the carriage
returns. `draft` finds the paragraph around a citation by searching for
`\n\n`; a CRLF file contains `\r\n\r\n`, so the search found nothing and the
whole manuscript became one paragraph. Two files differing only in how the
editor saved them produced different drafts:

```
-  We collected 154,391 examples from the corpus, and we evaluated them on 9,800 rolesets.
+  ## Methods We collected 154,391 examples from the corpus, and we evaluated them on 9,800 rolesets.
```

The heading (or, lower down, a list) was glued onto the sentence, so `draft`
offered the author a sentence nobody wrote, for pasting into the manuscript,
and its confidence fell from `high` to `medium` because the heading's words
diluted the terms it shared with the page. A `.tex` file was unaffected -
`latex.to_text` rebuilds the text itself - which is why the fix belongs in
the reader and not in `draft`.

* `read_text` now flattens `\r\n` and lone `\r` to `\n` after decoding, so
  every path that reads through it - manuscripts, bibliographies, text
  sources, JSON - sees one text. Nothing is written back; the author's file
  keeps its line endings.
* `tests/test_line_endings.py` (14 tests) pins the reader, the draft text,
  the verdicts, a CRLF page and a CRLF bibliography, and the LaTeX path.
* `tests/test_one_reader.py` (3 tests) walks the package with `ast` and
  fails if any module outside `textnorm` starts decoding bytes into text.
  Five mutants: keep the `\r`s, drop lone-`\r` handling, replace `\r`
  before the pair, delete the break instead of flattening, write the
  normalised text back - all red, no survivors.
## [0.22.23] — 2026-11-05
### Fixed
**A listing that showed \input made `draft` name a file the paper never reads.**

`included_files` reads the raw source, and the raw source contains the listing
that *demonstrates* the syntax. A name written inside a literal environment is an
example, and it was reported as an include:

```
\begin{lstlisting}
\input{chapters/intro}
\end{lstlisting}
```
produced
```
<!-- This document pulls text in from chapters/intro, which `citevouch draft`
does not read: any citation in those files is missing from the blocks below. -->
```

That sentence is false about that document, and it is printed in the one comment
the tool tells an author to read. The same for `verbatim`, `verbatim*`, `minted`,
`filecontents` and the `comment` package's environment. It also hid a real
include: the body of a listing that quoted `%` used to be treated as a comment
start, so a genuine `\input` after it could be dropped.

* `included_files` now starts from the document with every literal body blanked, so a name shown there is not reported and a name outside one still is;
* `comment` is in the set here and stays out of `_VERBATIM_ENVIRONMENT`: that set answers "is a `%` here a character", where a `%` inside a `comment` environment starts a real comment, while this one answers "is a command here executed";
* `alltt`, `tabular` and `tikzpicture` are deliberately outside the set - TeX executes what is inside them, and a test pins each name from the other side;
* an unclosed literal environment blanks the rest of the document, which is what TeX did to it too.

Note for authors: nothing to redo. The warning in a generated `claims.md` changes
for a `.tex` that shows `\input` in a listing - it stops naming a file that was
never read. Tests: `tests/test_literal_environment_includes.py` (24 tests, both
halves: the six literal environments are blanked and the three executed ones are
not). Six mutations ran red, `survivors: none`.
## [0.22.22] — 2026-11-05
### Fixed
**Five note commands still put their words inside the sentence that cited them.**

`\footnote`, `\footnotetext` and `\marginpar` were moved out of the sentence they hang on
when it was measured that keeping them inline produces words no paper contains. The list
that decides this was three names long, and the same defect was live under the rest of the
family. Measured on the tree before this release, with a note in the middle of a sentence:

```
The method works\thanks{We thank the annotators.}, and we show it.
  -> 'The method worksWe thank the annotators., and we show it.'
The method works\tnotetext{See the appendix.}, and we show it.
  -> 'The method worksSee the appendix., and we show it.'
```

The same for `\marginnote`, `\sidenote` and `\endnote`. `worksWe` is in no paper; `draft`
reads sentences out of the converted text, so a proposal built on that string is a claim
about a sentence nobody wrote. `\thanks` is the one that matters most in practice: every
funded paper has one, and it is written mid-sentence inside `\author`.

* the five now separate like the three before them, and each note keeps its own words in a block of its own, so a citation inside a note still counts;
* `\thanks*`, the starred spelling the kernel also accepts, is the same note and is now handled the same way;
* nothing else moved: `\textbf`, `\emph`, `\textsc` and the rest of the inline wrappers still keep their argument where it was written, which a test pins from the other side.

Note for authors: nothing to redo. The converted text of a `.tex` source changes, so
`draft` proposals from a document that used these commands will read differently - better,
because the note's words are no longer spliced into the middle of the sentence. Fixes
`tests/test_latex_more_notes.py` (45 tests, both halves: the five are notes, and `\textbf`,
`\emph`, `\textsc` stay inline). Eight mutations ran red, one per name plus the declaration,
the star handling and the whole branch.
## [0.22.21] — 2026-11-05
### Fixed

**The UTF-16 fallback turned a GBK manuscript into rubbish, and the tool then said the manuscript was empty.**

`textnorm._decode_text` has a fallback for files saved as UTF-16 without a byte-order mark: if the UTF-8 reading is noisier than `max(4, len // 50)`, try UTF-16-LE and keep it when it scores less noise.  A manuscript is mostly ASCII - its claim fences, its `quote:` keys and its attribute syntax all are - so a GBK or Big5 manuscript is noisy as UTF-8 in proportion to how much prose it holds and no more.  The fallback saw that noise, found a UTF-16 reading that scored lower, and took it.  The whole file became `'탑뾾쫎...'`: fences, keys and prose together.  The search that followed found no claim blocks in a manuscript that had them:

    [high] no-claim-blocks at manuscript.md:2: manuscript.md contains no claim
    blocks, so nothing was checked: a claim block opens with three backticks, the
    word `claim`, then `id=` and `source=`. This file has none.

That is a high finding that tells the author their manuscript is empty, when the fact is that the tool chose the wrong reading of it.  Worse than the mojibake it was trying to fix: `raw.decode("utf-8", errors="replace")` had kept every fence and turned only the Chinese lines into replacement characters, so the block was still there to be found.

Two conditions now have to hold, and both are facts about the two file families rather than tuning:

* **the UTF-16 reading has to score zero noise.**  Byte pairs that came from a real character cannot decode to a control or a replacement character, so every genuine UTF-16-LE document measures zero.  An 8-bit file read that way nearly always scores something - zero in only 42 of 600 random short samples across GBK, Big5, Shift-JIS and cp1251 - and never once it held ASCII as well, which is exactly the manuscript case.
* **the noise has to be at least a tenth of the file.**  A stray byte in a long UTF-8 paper scores one or two noise characters and must not move the reading; every genuine UTF-16-LE CJK document measured between 0.17 and 0.41.

Neither half survives alone.  A long UTF-8 paper with cp1252 bytes pasted in reads *clean* as UTF-16 and is saved only by the share test; a GBK manuscript has both a large share and a non-zero UTF-16 score and is saved only by the clean test.  Together they kept all twelve adversarial 8-bit files on the UTF-8 reading - GBK, Big5 and Shift-JIS manuscripts at three lengths each, plus Russian in GBK - and moved all twelve genuine UTF-16-LE files, in single-script and mixed-script shapes.

An 8-bit file with no ASCII in it at all is still ambiguous, and it is reported rather than guessed: it reaches the `source-encoding` guard, which says the words were never searched.  Big-endian without a mark stays undecidable for the reason it always was - swapping a Han character's bytes yields another Han character - and the rule does not pretend otherwise.

`tests/test_mojibake_fallback.py` (15 tests) pins the rule from both sides, including one test per half so that deleting either condition fails a test named after it.  Six mutations were run against it and every one went red: the share test dropped, loosened to a fiftieth, the clean test dropped, loosened to "any improvement", the fallback disabled, the fallback forced.
## [0.22.20] — 2026-11-05
### Fixed

**A source saved in a desktop encoding was read as mojibake, and the quote was then reported missing.**

`textnorm._decode_text` ends in ```raw.decode("utf-8", errors="replace")```.  That line is why the tool never crashes on a file it cannot read, and also why it lies about one: a page saved in GBK decoded to 54 characters of valid-looking mojibake holding **one** replacement character, and the plausibility check that would have caught it needs ```max(4, len // 50)``` - four.  Big5 gave 2, Shift-JIS 3, a cp1252 em dash 1.  No desktop encoding ever reached it, so the mojibake was searched, found to contain nothing, and the run answered the author's quote with:

    [high] quote-missing at manuscript.md:1 (c1): 我们收集了 40,688 个例句，并检验它们的分布。
    — quote not found in page.txt

A verdict about their sentence, when the fact was about the file's encoding.  Reproduced with four encodings (GBK, Big5, Shift-JIS, latin-1) on a page whose quote is verbatim on it; UTF-8 and UTF-16 were correct all along.

Lowering the noise threshold cannot fix this - the same score protects text that legitimately holds a stray byte.  What separates the two cases is that a *mixture* fails strict UTF-8: valid UTF-8 is UTF-8, and a file that is not stays unreadable however it is measured.  New `textnorm.invalid_utf8_share` reports the fraction of bytes that fit no UTF-8 sequence at all, and `sources.encoding_problem` refuses a text-suffixed source above 0.25 - measured: GBK page 0.62, Big5 0.58, Shift-JIS 0.57 against cp1252 French 0.085 and one stray byte 0.024.

New code `source-encoding` (high, next to `source-no-text`: both are cases where the author believes a source was searched and it was not).  Two deliberate exemptions, each a measurement rather than a preference:

* a file that names its own encoding (a byte-order mark, or the NUL pattern a UTF-16 save leaves) is never refused - a UTF-16 page of Chinese scores 0.33, past the line, and is perfectly readable; the guard asks `textnorm.proven_codec` first, and that helper is now the one list both readers share;
* a bibliography is not judged at all, because a Chinese `.bib` is mostly ASCII: a GBK one scores 0.11-0.24 where a GBK page scores 0.62, and a line low enough to catch it would be cleared by a cp1252 French page (0.085) by a hair.  Two files that close cannot be told apart by this number, and refusing a file the author can read is the same class of error as accusing their quote.

`tests/test_source_encoding.py` (20 tests) covers the four encodings, the two exemptions and the cache.  Reverse validation: six mutants, `survivors: []` - and the first round had **two** survivors ("a file that names its own encoding is refused anyway", "every suffix is judged, PDFs included") because no test fed a file that is readable *and* past the line; the demo PDF is 0.33 on this scale.  One existing test was found to be checking nothing: `test_the_demo_pdf_is_not_affected` looked for `demo/page.txt`, which is not a file, and returned early.
## [0.22.19] — 2026-11-04
### Fixed

- **Two spellings of one attribute, both written, and neither said so.**
  `ref=` and `cite=` name the same bibliography entry; the lookup reads
  `ref` and falls back to `cite`.  Writing both with different values was
  silent in *both* directions, and the two directions were different defects.
  Measured with `refs.bib` holding `knuth2020` and a quote verbatim on page 1:

  ```
  ref=phantom cite=knuth2020   ->  exit 1
      [high] bib-key-missing at m.md:1 (c1): claim c1 cites 'phantom',
      which is not in the bibliography the ledger recorded
  cite=phantom ref=knuth2020   ->  exit 0, no finding at all
  ```

  One direction accused the author on the strength of a string they may have
  meant to delete; the other dropped that string without a word.  Both left
  the manuscript saying something no run had applied - the same shape as the
  misspelt `Page: 1` body field fixed in 0.22.14, one attribute over.

  A conflicting pair is now `claim-field-conflict` (medium): the run still
  verifies the quote, but it names both values and says which one was used and
  which was dropped.  The values are unaffected - the fallback still reads
  `ref` first, so nothing that worked stops working.  `tests/test_field_conflict.py`
  (15 tests) pins the parser and the command; six mutations are red, including
  one that only removed the attribution from the sentence and survived the
  first round.
## [0.22.18] — 2026-11-04
### Fixed

- **`bib-key-missing` handed the author a bibliography key they never wrote.**
  `source` names a local document; `ref` names a bibliography entry.  A claim
  that writes only `source=paper` was looked up under `paper`, and when the
  bibliography had no such entry the finding said

      [high] bib-key-missing at manuscript.md:1 (c1): claim c1 cites 'paper',
      which is not in the bibliography the ledger recorded

  Nothing in that manuscript cites `paper` - it *names* it, as the file the
  quote came from.  The verdict is right (a bibliography is present and this
  claim names nothing in it) and stays `high`, but the sentence invites the
  wrong repair: adding `paper` to `refs.bib` puts a PDF's file name in the
  bibliography, while the one-line fix is `ref=<key>`.  The fallback that makes
  the lookup possible still decides *what is checked*; it no longer decides
  what the message calls it.  Measured on a project whose claim writes
  `source=paper` and no `ref=`: before, the sentence above; after, `claim c1
  names no ref=, so it was looked up as 'paper' - the name of its source file -
  and the bibliography the ledger recorded has no such entry. Write ref=<key>
  for the entry this quote comes from`.  A claim that does write `ref=phantom`
  still reads `cites 'phantom'`, and a project that names its PDF and its entry
  the same way is still green without a `ref=`.
  `tests/test_bib_key_namespace.py` (7 tests) pins both halves at once.  Five
  mutations, `survivors: []`: the fallback branch speaking in the `ref` voice,
  the advice losing the attribute name, the sentence dropping the name it
  looked up, an empty `ref` counting as a written one, and the fallback
  removed.
## [0.22.17] — 2026-11-04
### Fixed

- **A ledger written by any earlier build made the verifier accuse a
  *verbatim* quote of a number the page does not contain.** 0.22.16 taught the
  tool that `40 688` written with a grouping space is one number, and started
  storing `Claim.numbers` that way — but `Ledger.from_json` kept whatever the
  file held, and a ledger committed before 0.22.16 records `["40", "688"]` for
  that same quote.  Verifying such a ledger compared the two stale tokens
  against a page this build reads as `40688` and reported

      [high] number-absent-in-quote ... the quote says 40 and 688 but page 1
      of the source does not contain those numbers

  about a quote that is *character for character* the page.  `action.yml` runs
  `check --use-recorded`, so this was the CI verdict for every repository that
  upgraded — an accusation, at high, caused by a formatting change inside the
  tool.  Documenting "re-run `scan` after upgrading" is not a repair when the
  upgrade itself is what turns a green build red.

  `Claim.numbers` is derived data: `textnorm.quote_numbers` is its only
  producer and the quote it describes sits in the same JSON object.  So
  `Ledger.from_json` now re-derives it from that quote and only shape-checks
  the stored list — a stale value can only be older than the quote, never
  better informed than it.  This is deliberately not leniency: a re-typed
  number is still absent from the page and still `high`, because the
  comparison now starts from the text the author actually wrote.  A value of
  the wrong shape (`numbers: 5`, `numbers: ["x", 1]`) is still a damaged
  ledger and still exits 2 — no writer ever produced that shape, as opposed to
  a shape an older writer produced.
## [0.22.16] — 2026-11-04
### Fixed

- **The same number, written with a grouping space, got three different
  verdicts from three functions that each had their own rule.** A page printing
  `40 688` and a claim typing `40,688` came back `number-absent-in-quote` — an
  accusation that the source does not contain a figure the reader can see
  printed on it. A page printing `40` + a non-breaking space + `688` came back
  exit 0 with `0 verified, 0 moved, 1 missing` and **no finding at all**: the
  run said a claim had not been checked and never said why. A page printing
  `40` + a thin space + `688` came back `quote-fuzzy` at "similarity 1.00"
  *plus* the same false number accusation. All three pages fold to the same
  text — `fold` already declares every one of those spaces the same character —
  so the disagreement was entirely inside the tool.

  The cause was three tables. `REPORT_PATTERN` (what a manuscript asserts)
  refuses a bare space between digit triples, because "2019 2020 2021" is three
  years and not twenty million. `MASK_PATTERN` (what the numbers tier blanks
  out) accepts a space and a non-breaking space but not the other spacing
  characters. And `canonical_number` (what a value is compared by) stripped
  only those same two. Nothing owned the question "are these two spellings the
  same value", so each layer answered it differently and the layers disagreed
  about which layer's answer applied.

  Fixed by giving that question one owner: `CANON_PATTERN`, used by the
  canonical tier, by the page-side number collection and by the claim's
  recorded numbers. A space counts there only as a *thousands group* — one to
  three digits, then exactly three — so the year rule above still holds
  (`numbers_in("2019 2020 2021")` is unchanged, and a new test pins it).
  `canonical_number` now strips every spacing character `fold` treats as a
  space. Measured after the fix: all nine spellings of `40,688` verify against
  all nine, and a genuinely different figure (page `40 688`, quote `80,688`)
  still exits 1.

  Note for existing projects: the ledger records the numbers `scan` read, so a
  ledger written before this release keeps the old split of `40 688` into two
  numbers until `scan` is re-run.
## [0.22.15] — 2026-11-04
### Fixed

- **A release recovery that found the release treated "exists" as "published",
  so a draft stayed a draft while every step reported success.** `gh release
  create` attaches assets by creating a *draft* release, uploading to it, and
  then publishing it — three API calls. v0.22.14 died between the first and the
  third: the create call answered `HTTP 502: Server Error`, and the draft
  existed anyway. The `Re-attach artefacts if the release already existed` step
  asks only `gh release view "$tag"`, which answers "yes" for a draft; it
  uploaded the wheel and the sdist, exited zero, and the run was green with the
  release invisible to anyone reading the repo. That is worse than a red run,
  because nothing in the log said a word about it — the release was published
  by hand minutes later, which is exactly the human step this project exists to
  not need.

  The recovery now finishes the job the create step was doing: after attaching
  the assets (in that order — publishing an empty release is worse), it reads
  `isDraft` from the API and calls `gh release edit "$tag" --draft=false` when
  the answer is true, then reads `isDraft` again and fails the run if it is
  still true. The last word comes from the API rather than from the step that
  just succeeded at something else.

  `tests/test_release_recovery.py` (7 tests) runs the real shell body of the
  step against a `gh` stub whose *existence* and *draftness* are separate
  state, so a body that publishes nothing cannot pass by saying it did. It
  asserts the published-release path is left alone, that the assets are
  attached before the publish, and that a release that stays a draft exits 1.
  Five mutations, `survivors: []`: no publish, no final check, publish before
  upload, re-publish a published release, and dropping the `if:` that gates the
  whole recovery on the create step's failure.
## [0.22.14] — 2026-11-04
### Fixed

- **A misspelt field name in a claim body either switched a check off in silence
  or accused the author of quoting a page their source never printed.** The
  body reader recognises a fixed set of keys (`quote`, `claim`, `numbers`, and
  the attributes `id`, `source`, `ref`, `cite`, `page`, `marker`). A line that
  was shaped like a field but named anything else took one of two paths, and
  neither one said anything. Measured on a project whose quote really is on
  page 2, with the page hint misspelt:

  - `Page: 1` **above** `quote:` — the hint was dropped, the claim was located
    by search, and the run printed `[info] quote-found` and exited 0. Writing
    `page: 1` correctly on the same project prints `[medium] quote-moved …
    the quote is on page 2, the ledger says 1`. So a typo in a field name
    turned a check off, and nothing anywhere said so.
  - `Page: 1` **below** `quote:` — the line was appended to the quote, so the
    passage searched for ended in `Page: 1`, matched nothing, and the run
    printed `[high] quote-missing … The resulting grammar consists of a
    network of 40,688 constructions. Page: 1 — quote not found in page.txt` and
    exited 1. That is the tool's most serious sentence — the author quoted
    something their source does not contain — printed because the author
    capitalised a key.

  In a `quote: |` block a line at the left margin is a sibling key, never
  continuation text, so the reading that loses nothing is to say both facts:
  this is a field, and it is not one this format has. Both dialects (the fence
  and the `<!-- claim -->` comment) now report `claim-field-unknown` (medium)
  naming the line and the key, and keep the line out of the quote. Indented
  lines are still continuation text, and a correctly spelt key is still
  silent. Severity is medium because the quote is still located and compared —
  what is lost is the instruction the field carried, which is the same loss as
  `page-unreadable`.

  The positive tests are in `tests/test_unknown_fields.py` (20 tests): the line
  number reported is the line the editor shows, five misspellings are each
  named, two unknown keys are two findings, an indented `Page: 1 is what the
  source says` still joins the quote, `numbers:` is still a known key, and the
  end-to-end runs assert both that `quote-missing` is gone and that `--fail-on
  medium` still turns the run red. Six mutations, `survivors: []`.

### Fixed

- **A starred definition deleted the rest of the document, and the xparse commands
  left their macro body in the prose.** Three defects in one function,
  `latex._definition_end`, each measured before the fix (`B` is a backslash):

  1. A definition written with a star — `B + "newcommand*{..."` — put a `*`
     where the code expected an opening brace. `_group_end` answered `-1`, and
     the fallthrough translated that into `len(text)`, so the definition
     consumed the whole rest of the file. Measured on `"A. " + B +
     "newcommand*{" + B + "x}{y} The grammar is large."`: the converted text was
     `'A.'` — 32 characters gone, and no finding said so. Six spellings take the
     star this way: `newcommand`, `renewcommand`, `providecommand`,
     `DeclareRobustCommand`, `newenvironment`, `renewenvironment`. Deleting
     prose is the one failure an author cannot see, which is why the star is now
     skipped and, more generally, why a definition that cannot be read to its
     end now stops where it started reading instead of running to the end of the
     file.
  2. The xparse commands `DeclareDocumentCommand`, `NewDocumentCommand`,
     `RenewDocumentCommand` and `ProvideDocumentCommand` take **three** groups:
     the name, the argument specification and the body. The generic path
     consumed two, so the body stayed in the prose. Measured:
     `B + "NewDocumentCommand{B + "seecite}{m}{see B + "citep{#1}}` contributed
     the words `see [@#1]` to the text, and `draft.citation_sites` reported a
     citation to the key `#1` — a source the paper never cites, offered to the
     author to paste into a claim block.
  3. A definition with no readable group at all — `B + "newcommand The grammar
     is large."`, `B + "newtheorem ..."`, `B + "def ..."` — took the same
     `len(text)` exit and deleted what followed.

  The etoolbox `...x` spellings (`newcommandx`, `renewcommandx`,
  `providecommandx`) are **not** the xparse shape: they take a name, an optional
  count, an optional default and then the body, so they stay on the generic
  path. A group that follows an etoolbox definition belongs to the page and is
  kept; the same group after an xparse definition is the body and is dropped.
  Both directions are pinned by tests.
## [0.22.12] — 2026-11-03
### Fixed

- **29 conditional commands from `etoolbox` and LaTeX2e were not in any table, so
  their test arguments were pasted into the sentence and their two branches were
  glued into a word that is in neither.** Measured before the fix (`B` is a
  backslash):

  ```
  to_text("X " + B + "ifboolexpr{test}{Yes words}{No words} Y")              -> 'X testYes wordsNo words Y'
  to_text("X " + B + "ifnumcomp{1}{=}{2}{Yes words}{No words} Y")            -> 'X 1=2Yes wordsNo words Y'
  to_text("X " + B + "ifdef" + B + "foo{Yes words}{No words} Y")             -> 'X Yes wordsNo words Y'
  to_text("X " + B + "IfFileExists{sec/intro}{Yes words}{No words} Y")       -> 'X sec/introYes wordsNo words Y'
  ```

  `Yes wordsNo words` is a token in neither branch, and it is the sentence
  `draft` offers the author to paste into a `claim:` block. All four now read
  `'X Yes words No words Y'`.

  The table changed shape, because the fact it was missing is a number: how many
  brace groups hold the *test* before the two branches. `_BRANCH_COMMAND` is now
  `dict[str, int]` (`\ifnumcomp` takes three test groups, `\ifstrequal` two,
  `\iftoggle` one) instead of a `frozenset` of names, and `_BRANCH_BARE_TEST`
  names the seven `\ifdef...` commands whose test is a bare control sequence
  (`\ifdef\foo{yes}{no}`) rather than a group. A separate `BACKSLASH` constant
  exists because that character had been spelled as a literal inside three
  different comparisons and mismatched a quoting layer twice.

  `tests/test_latex_branch_commands.py` walks the table (23 group tests, 8 bare
  tests), and asserts the table and the test's own lists name the same commands —
  a name added to one and not the other is a name nobody checked. Six mutations,
  all red: table back to `ifthenelse` only, bare-test set emptied, every command
  counted as one group, branches joined flush again, the bare token not stepped
  over, and the test always consuming exactly one group.
## [0.22.11] — 2026-11-03
### Fixed

- **The two branches of `\ifthenelse` were written flush against each other, so they
  formed words that are in neither branch.** `\ifthenelse{test}{yes}{no}` is not
  decidable here, and both branches are text the author wrote, so the
  converter keeps both. It kept them touching:

  ```text
  A. \ifthenelse{1=2}{We report five}{We report these} results.
  ```

  came out as `A. We report fiveWe report these results.`: `fiveWe` is a token
  that appears in neither branch, and it is in the sentence that
  `draft` offers the author to paste into a claim block. Two citation
  branches were joined the same way and came out as `[@no][@yes]`.
  Each branch is a whole piece of prose and at most one of them is ever
  typeset, so they are now joined by one space.
## [0.22.10] — 2026-11-03
### Fixed

- **A space between a command and its argument did not count, so the
  argument was read as prose.** TeX does not care whether an argument
  touches its command: `\\input {sec/intro}` and
  `\\input{sec/intro}` are the same command. Only the touching
  spelling was understood. Measured across the six tables that say what
  a command's arguments are, against the 104 command names whose
  arguments must not reach the prose: **85 of them pasted the argument
  into the sentence when one space stood between.**
  `\\input {sec/intro}` came out as
  `... examples. sec/intro The end.`, so a file path was read as two words
  of the paper - and because the part it named was never read, every
  citation inside that part was missing too.

  The same gap hit the tables that keep an argument, split one off, or
  count them: `\\textcolor {blue}{blue}` became `blueblue`,
  `\\setcounter {page}{3}` left `page` and `3` in the sentence,
  and `\\footnote {note}` was read as the words `note}` in the body.

  The fix holds whitespace **pending** and spends it only when a brace
  group actually follows, so `\\footnotemark[1]` - bracket
  argument, no brace argument - still consumes its bracket and does not
  then eat the space after it (`Text continues.` would otherwise become
  `Textcontinues.`), and a switch such as
  `\\bfseries We collected` still keeps the space that separates
  its two words. `\\input sec/intro` (plain TeX, no braces) still
  reports the file and still keeps the path out of the prose.

  `tests/test_space_before_brace.py` (22 tests) pins all three
  directions; six mutations, none survived.
## [0.22.9] — 2026-11-03
### Fixed

- **A pipe written the only correct way inside a table cell was read as a cell boundary.**
  GFM defines exactly one escape inside a table cell: a backslash before the pipe
  separator. The table dialect matched each column with `[^|]+?`, which stops at any
  pipe, so an author who escaped correctly had their quote cut at the backslash and the
  remainder of it installed as the `text` column:

  > | c1 | paper | 1 | a\|b | t |

  parsed as quote `a\` and text `b`. Written the way Markdown says is wrong -
  the pipe left bare - the same row parsed as quote `a` and text `b`, i.e. the correct
  spelling was the one that lost data.

  End to end on a project whose page carries a literal pipe in the sentence, the
  correctly escaped row was reported `[high] quote-fuzzy ... similarity 1.00` and exited
  1, and the same row unescaped verified and exited 0.

  The columns are now matched with `_CELL = r"(?:[^|\\]|\\.)*?"`
  and the cell text loses the escape through `_unescape_pipe`, which undoes `\|`
  and nothing else - every other backslash stays as written, because a quote may hold
  one (a Windows path, an escaped character in a borrowed sentence) and rewriting it
  would be editing the author's text rather than reading it. `source`, `quote` and
  `text` all go through it.

- **A table row with a blank column was reported as a file with no claim blocks.**
  The same cell pattern required at least one character, so `| c1 | paper | 1 | q | |`
  and `| c1 | paper | 1 | | short |` matched no dialect at all, and a manuscript whose
  only table row was one of those came back as `[high] no-claim-blocks ... This file has
  none` - over a file that had one. An empty column is not a parse failure; it is a
  claim the author has not finished, and the parser already has a finding for that, so
  an empty quote or source now comes back as `[high] claim-uncheckable` naming the claim
  and saying what is missing, while an empty `text` column simply verifies.
## [0.22.8] — 2026-11-03
### Fixed

- **A file whose only claim blocks were wrapped told its author that it had none.** With no
  accepted claim, `scan` builds one `no-claim-blocks` finding to explain why nothing was
  checked. That explanation looks for the nearest claim-shaped line using `_CLAIMISH`, whose
  `^\s*` prefix stops dead at a `>` or a `- `, so a manuscript holding only blockquoted or
  listed blocks matched nothing and the message ended, over a file whose first line was the
  block, with:

  > a claim block opens with three backticks, the word `claim`, then `id=` and `source=`. This
  > file has none.

  Measured on three files, one per dialect, each holding exactly one wrapped block and nothing
  else: all three said "This file has none", with `line 0` - the code base's "no line at all".
  The parser's own `_WRAPPED` table already knew those lines; the zero-claim path was written
  before that table existed.

  The same path also called every indented block a fence. `_CLAIMISH` *can* see an indent, so
  an indented `<!-- claim` line reached the near-miss branch and was told that "an indented
  fence is a code sample in Markdown" - about a line with no fence on it.

  Both are fixed: the wrapped blocks are now found through `_unread_opener`, each dialect is
  described with its own reason (the same `_UNREAD_REASON` sentences `claim-block-unread`
  uses), the count is the number of wrapped blocks in the file, the finding carries the line
  the reader can open, and the indent sentence names the construct that was actually written.
  A file holding several blocks written the same way is now counted rather than described one
  at a time.
## [0.22.7] — 2026-11-03
### Fixed

- **The skipped-block finding covered one dialect and left the other two silent.** The
  `claim-block-unread` detector added in 0.22.5 looked for a claim fence, then for the
  container prefixes that put it out of reach, and reported what it found. The format has
  three openers - a fence, an `<!-- claim` comment and a table row - and only the first was
  in that pattern, so on a project holding one good fenced block plus one wrapped block,
  measured shape by shape with `sources.toml` mapping `paper = "page.txt"`:

  | wrapped block | `scan` | `check` | ledger | findings |
  | --- | --- | --- | --- | --- |
  | fence, indented | 1 | 1 | `['c1']` | `claim-block-unread` |
  | comment, indented | 0 | 0 | `['c1']` | none |
  | comment, blockquoted | 0 | 0 | `['c1']` | none |
  | table, indented | 0 | 0 | `['c1']` | none |
  | table, blockquoted | 0 | 0 | `['c1']` | none |

  The second block's id was in no finding and in no ledger row for four of the five, and
  `check` called those runs a verification. Each dialect now has its own entry in one table
  (`_WRAPPED`), the table opener is `_TABLE_CLAIM.pattern[1:]` rather than a retyped copy of
  it so the parser and the detector cannot disagree about what a claim row is, and the
  finding names the construct it actually found: a fence, a `<!-- claim` opener or a table
  row, because "move it to the left margin" is only the whole fix for one of the three.
  `doctor`'s `claims` count follows for free - it counts the fences this finding names.
## [0.22.6] — 2026-11-03
### Fixed

- **`doctor` counted a manuscript by the blocks it managed to read.** The `claims` check
  prints how many claim blocks the file holds, and it counted `parsed.spans` (the blocks the
  parser consumed) plus `parsed.claims` (the ones it accepted). Neither counts a block the
  parser walked past because a blockquote, a list item or an indent put the fence out of
  reach, so a file holding two fences was reported as `1 claim block` - measured on a project
  with one good block and one blockquoted block, where `doctor --manuscript manuscript.md
  --root .` printed `[ok  ] claims      1 claim block` and exited 0 while `check` printed
  `[high] claim-block-unread at manuscript.md:8 (c2)` and exited 1. The count now includes
  the fences `claim-block-unread` named, so the same file reads `2 claim blocks, 1 of which
  the parser could read; the next command names the rest`. The check stays green and
  `doctor` still exits 0: a block it could not read is a finding with its own line number,
  and that division of labour is the same one the refused-block case has always had - which
  is also why the defect was invisible until the count was compared against the file.
## [0.22.5] — 2026-11-03
### Fixed

- **A claim block inside a blockquote, a list item or an indent was skipped without a word.**
  Markdown renders such a fence as a code sample, so the parser is right not to read it - but it
  is wrong to say nothing, because a manuscript holding one good block and one wrapped block
  reported `1 claim — 1 verified, 0 moved, 0 missing` and exited 0. Measured before the fix, on a
  project whose `page.txt` holds the sentence both blocks quote: `scan` wrote
  `citevouch.lock.json (1 claim)` and exited 0, `check` printed `1 claim — 1 verified, 0 moved,
  0 missing` with `worst severity: info`, `doctor` showed two green ticks, and the second block's
  id appeared in no finding and in no ledger row. The same held for a bullet (`- ```claim`), an
  ordinal (`1. ```claim`) and a bare two-space indent. The near-miss sentence `scan` already had
  names the indented shape correctly, but it only runs for a file that produced *zero* claims, so
  one good block anywhere in the manuscript switched it off - partial recognition, which is the
  shape that reads like a total. There is a new code, `claim-block-unread` (high), reported per
  line with the claim id on it, saying the fence is not at the left margin and will not be
  checked until it is. A file with no claims at all still gets `no-claim-blocks` and not both, and
  a fence inside a code sample is still silent, because sample text is not a claim the parser
  failed to read.
## [0.22.4] — 2026-11-03
### Fixed

- **The format gate counted files it never judged, and could be green having judged nothing.** `tools/format_check.sh` counted every tracked `*.py`, `*.md` and `*.toml`, then handed all three extensions to `ruff format --check` - and ruff has no TOML formatter, so it silently declined those files and printed `2 files already formatted` where the script counted 3. The number this repository quotes in every commit message was therefore a count of the tracked set, not of the judged set, and it drifted by exactly the number of tracked TOML files: a backlog commit quoted `147` while `ruff` reported `146`, which is how the lint job caught it. The gap had been written down in `tests/test_format_check.py` as `declined = 2` with a comment explaining it instead of a guard removing it. Measured on a tree holding one unrelated tracked `*.toml`: the script printed `3 files already formatted` and exited 0 while ruff had judged two files. Two more holes in the same script: a tree whose only tracked file is a `*.toml` printed nothing and exited **0**, so a gate that judged zero files reported success; and a staged file deleted from disk stays in `git ls-files`, ruff cannot read it, and the old code exited on ruff's status without ever comparing its summary to the count, so the quoted number could be one too many. The script now counts and hands over the same two extensions, refuses an empty file list, and - on the green path - refuses both an absent summary line (`ruff reported no summary line, so it judged nothing; N file(s) were handed to it`, exit 2) and a summary that disagrees with the count (`ruff judged N of the M file(s) handed to it; the count cannot be quoted`,
  exit 2). That sentence then failed on the macOS runners only, because BSD
  `wc -l` pads its answer to a fixed width and GNU does not, so the count
  reached the message as `       2`; the padding is stripped with `tr -d ' '`
  and a test reads the script for it, since a Linux run cannot see the
  padding and a macOS run cannot see its absence.
## [0.22.3] — 2026-11-03
### Fixed

- **Three citation commands nobody could see.** Natbib's capitalised forms
  open a sentence, so they are the first citation a reader meets: `\Citet`,
  `\Citep`, `\Citeauthor`, `\Citeyear`, `\Citealp`, `\Citealt` and
  `\Citeyearpar` were on neither name list, so `\Citet{knuth1984}` reached the
  page as the bare word `knuth1984` and `draft` reported that a manuscript
  citing on its first sentence cited nothing. A space or a tab between the
  command and its brace - legal TeX, and what a reflowed line produces - was
  equally invisible: `\citep[p.~3] {knuth}` gave no site at all and `to_text`
  kept `[p. 3] knuth` as prose. And `draft.py` typed the name list a second
  time instead of reading `latex.py`'s, so it had already fallen behind:
  `\citeyearpar{k}` became a `[@k]` marker in the text `draft` was reading and
  `draft` still said there were no citations, with the marker in front of it.
  Both readers now build their patterns from one exported table
  (`CITATION_NAMES`, `MULTI_CITATION_NAMES`, and the shared `_GAP`), so a third
  copy cannot drift again. A newline is deliberately *not* in the gap: between
  a command and its mandatory argument a newline is where a missing brace finds
  the next paragraph's brace group, and reading one paragraph's text as
  another's citation is the silent wrong answer this module exists to avoid.
## [0.22.2]

## [0.22.2] — 2026-11-03
### Fixed

- **A `.docx` saved as `paper.txt` was read as text, and the run then accused
  the author's quote.** The known-suffix list is exempt from the byte sniff
  because the suffix is the author stating the format - true, but the file
  saved under the wrong name is exactly the case where the statement and the
  file disagree. Measured: a two-entry zip copied to `real.txt` produced 196
  characters of mojibake with 47 replacement characters and C0 controls,
  `problem` was `None`, and `citevouch check` answered a quote the document
  contains with `[high] quote-missing ... quote not found in real.txt`.
  The judgement is now made on the text that came out, not the bytes that
  went in: the same noise score `textnorm._decode_text` already uses to
  decide an encoding was wrong, confirmed by the file's own header. A note
  that merely begins `PK` still reads, because its noise is 2 in 73
  characters rather than 47 in 196. The cache-hit path judges too - a cache
  holds pages, not a verdict - and a PDF is exempt, because its bytes were
  already checked against the header and its readers are entitled to leave a
  control character in otherwise good text.
## [0.22.1] — 2026-11-03
### Fixed

- **A PDF named `paper.txt` was decoded as text, and the run then accused
  the quote.** The suffix is the author's statement about the format, and
  this tool reads what it is told to read. But a PDF has its own reader
  here, and using it on a file that *is* a PDF is strictly more capable
  than decoding the same bytes as UTF-8. Measured: the demo paper copied
  to `real.txt` extracted as 4 pages / 206,870 characters of mojibake, and
  a claim quoting the paper's own sentence came back
  `[high] quote-missing ... no passage in the source is close to this
  quote in real.txt`, exit 1 — a sentence about the author's quote when
  the fact was about the file's name.

  `extract_pages` now reads the first five bytes of any file whose suffix
  is not `.pdf`, and switches to the PDF readers when they spell `%PDF-`.
  The cache entry is stored under the reader that actually ran, so the
  mojibake an earlier version cached as `plain` is not handed back.

  The one file this can hurt is text whose first bytes spell the PDF
  header; it gets `source-unreadable` instead of a false `quote-missing`,
  which is the right direction — a refusal makes the author look, a false
  accusation makes them doubt their own quote.
## [0.22.0] — 2026-11-03
### Removed

- **Four module-level functions nothing called, each with a docstring
  describing a feature this tool does not have.** `verify.doi_index` was
  documented as the map for "the optional Crossref cross-check" — there is no
  Crossref cross-check, and `AGENTS.md` says one would belong in a separate
  optional command rather than inside `scan`/`verify`/`check`. `verify.rebuild`
  claimed to be the wrapper "so the CLI has one call per verb"; the CLI imports
  `verify` directly. `verify.summarize` was a second copy of the sentence a run
  prints, unreachable while `report.py` writes the real one.
  `sources._odd_bindings` pluralised a manifest's bad keys into one sentence;
  the live code writes that sentence per key. Measured with an AST scan of
  `src/`, `tests/` and `tools/`: all four names appear nowhere. `verify.py` line
  coverage went from 90% to 96%, and no test had to change — which is the point
  and the problem: nothing was running them.

### Added

- `tests/test_no_dead_functions.py` resolves each package function against every
  name the repository actually references, per module, so `draft.summarize` is
  not mistaken for a use of `verify.summarize`. Six mutations are killed,
  including re-adding each of the four functions under clean source.
## [0.21.5] — 2026-11-03
### Fixed

- **A `sources.toml` whose keys sit at the top level is now named as a
  problem instead of read as an empty manifest.** The JSON reader takes its
  mapping at the top level (`{"page": "a.txt"}` is the documented form), so
  ``paper = "page.txt"`` written straight into `sources.toml` with no
  `[sources]` header looks like a manifest to the one format and like nothing
  at all to the other.  Measured on that project: `check` printed
  `[high] source-missing … no entry in sources.toml and no --source path
  resolves it; add it to sources.toml` about a key that was in the file, three
  lines above the header the message asked for, and `doctor` printed
  `[ok  ] manifest sources.toml (19 bytes), 0 sources, every one of them
  present on this machine` and exited 0.  Both readers now refuse the file with
  one sentence naming the keys and the two ways to fix it.  The refusal is
  written on the text in the shared pre-scan rather than against the parsed
  mapping, because the subset parser used on 3.10 files those keys under a
  bucket named `""` — a check written on the mapping would refuse on 3.11 and
  stay silent on 3.10.  A key literally called `sources` and a dotted name are
  excluded: both already have their own, more precise, sentence.
## [0.21.4] — 2026-11-03
### Fixed

- **Two claim blocks that share one closing fence are no longer read as one.**
  With the first block's closer missing, the body scan ran from the first
  opener to the *second* block's closer, swallowing the second opener and its
  quote into the first block.  Measured on a two-block manuscript: `scan`
  exited **0** and wrote a ledger holding `['c1']`, while `check` exited 1 with
  `[high] quote-missing at manuscript.md:3 (c1): … ```` ```claim id=c2 sourc ````
  — a quote the author never wrote.  `id=c2` was in no finding and in no ledger
  row: the author wrote two claims and one stopped existing.  The scan now stops
  at a nested opener, both blocks become claims, and the missing fence is
  reported as `claim-block-unclosed` naming the line where the second fence
  begins.
## [0.21.3] — 2026-11-03
### Fixed

- **A claim block the parser refused no longer disappears from the CI path.**
  The ledger records the claims the parser *accepted*, because a refused block
  has no evidence to record - so the verification pass, which walks the ledger,
  never learned the block existed.  `action.yml` runs `check --use-recorded` on
  every pull request, which is that pass and nothing else.  Measured on a
  manuscript holding one accepted claim and a second block missing its `id=`:
  `scan` exited 1 with `[high] claim-uncheckable at manuscript.md:9`, while
  `check --use-recorded` and `verify` both exited 0 with a green
  `[info] quote-found`.  A contributor who pastes a second claim block and
  forgets its `id=` got a tick.  `verify` now re-parses the manuscript when the
  ledger's digest proves it describes this exact text, and reports the parser's
  own findings; with `--allow-stale` it stays silent, because a finding about a
  paragraph the ledger never recorded would be a verdict about a document this
  run has not read.
## [0.21.2] — 2026-11-03
### Fixed

- **A quote printed inside a CDATA section is no longer reported missing.**
  `<![CDATA[ ... ]]>` is how a feed, a JATS article and an OAI-PMH record carry
  prose, and the tag stripper read the whole section as one tag - `<` followed
  by `!` is exactly what a doctype looks like - so the words were replaced by a
  space and the delimiters took their place on the page.  Measured: a source
  `We collected <![CDATA[9,800]]> rolesets.` extracted as `We collected
  rolesets.`, and the claim quoting the sentence came back `[high]
  quote-missing` with the source file named.  `sources._without_cdata` now
  unwraps the section before tag removal, keeps an unterminated section's text
  (a truncated save should lose the delimiters, not the document), and the body
  is still stripped of tags afterwards so an Atom `type="html"` fragment does
  not hand `<p>` to the page.
## [0.21.1] — 2026-11-03
### Fixed

- **A quote that exists only inside a `<template>`, `<textarea>` or `<iframe>`
  is no longer certified as found.**  The HTML reader dropped the bodies of
  `<script>`, `<style>` and comments, and those three were not on the list, so
  a sentence that lives only in an inert template was read as page text and
  came back `[info] quote-found` with exit 0 — a verified claim about words no
  reader can see on that page.  This is the same failure the `<script>` fix
  addressed, one element name short.  `<noscript>` and `<svg>` stay in the page
  text on purpose: `<noscript>` content *is* shown when scripting is off, and
  an `<svg>` may carry real `<text>`, so removing either would turn a quote a
  reader can see into `quote-missing`.
## [0.21.0] — 2026-11-03
### Added

- **`doctor` now opens the sources instead of only counting them.** Every other
  check was green — the manifest was found, the keys were bound, the files
  existed — while `check` on the same tree reported `source-unreadable`,
  `source-no-text` or `source-not-text` and exited 1. `doctor` is the command a
  worried user runs *instead of* the one that fails, so answering "the files are
  there" to a question about their contents is worse than not answering. The new
  `extraction` report reads every source a claim names, through the same cache,
  and names the first few files it cannot read along with the step that fixes
  each one. It stands aside when a key is unbound or the manifest will not parse,
  so one problem is still reported by the one check that owns it.
## [0.20.2] — 2026-11-03
### Fixed

- **An empty `.txt` was told to run OCR on it.** `source-no-text` was written for
  a scanned PDF, and its one message ended with `ocrmypdf <file> out.pdf`. The
  same code answers for every format, so an empty or whitespace-only `.txt`,
  `.md` or `.xml`, and markup whose words are all inside tags, all got that
  sentence — advice that cannot work on any of them: a text file has no text
  layer, and OCR does not untag a document. Each format now gets its own reason,
  and the suffix travels from the extractor to the sentence on both the
  extraction and the cache-hit path.
## [0.20.1] — 2026-11-03
### Fixed

- **Code is not prose: a quote that exists only inside a `<script>` was
  verified.** The HTML reader removed a `<script>`/`<style>` body only when the
  end tag was spelled exactly `</script>`; HTML also allows `</script >` and
  `</script\n>`, so a formatter that writes either spelling left the whole body
  in the page text and a sentence living only in JavaScript came back
  `[info] quote-found` — the one outcome this tool cannot apologise for. The
  same two ways of giving up also dropped nothing at all for a truncated
  `<script>` or an unterminated `<!--`, so everything after the footnote a
  writer never closed was read as prose. Unterminated now means "to the end of
  the file", which is what a browser does with a raw-text element too.
## [0.20.0] — 2026-11-03
### Added

- **`source-not-text`: a file the tool cannot read is no longer read as text.**
  A source with a suffix this tool does not know (`.docx`, `.odt`, `.epub`,
  `.doc`, `.png`, `.rtf`) fell through both PDF readers and then fell back to
  plain text, which decoded the zip into a hundred characters of valid-looking
  nonsense and returned it as page 1. The run then reported
  `[high] quote-missing ... quote not found in paper.docx` — a verdict about
  the author's quote, when the fact was about the file format. The new code
  reads the file's own first bytes and says what the document is and how to
  convert it (`soffice --convert-to pdf paper.docx`). Medium severity: reading
  it as text wasted a step, it did not corrupt anything.

### Fixed

- **The refusal is decided above the cache.** A cache entry written before the
  check existed holds the zip bytes spelled as characters; a lookup first would
  hand that text back forever, so the diagnosis would appear once and then
  never again. `tests/test_opaque_formats.py` poisons an entry by hand and
  asserts the verdict still wins.
## [0.19.88] — 2026-11-03
### Fixed

- **`doctor` promised a green run for a project that fails.** Its claims line
  read `holds no claim blocks, so every run will report 0 claims checked and
  exit 0`. Every word of that is false: `check`, `verify` and `scan` all report
  `no-claim-blocks` (high) and exit 1. The sentence was written in 0.19.47 by
  the commit that added the check — it describes the behaviour that change had
  just removed — so it was wrong from its first release. The line now says what
  happens: `every run reports no-claim-blocks and exits 1: nothing in this
  project is ever checked`. A test scans every non-docstring string in
  `src/citevouch/` for a promise of `exit 0`, because the next such sentence
  will not be in the same place.
## [0.19.87] — 2026-11-03
### Fixed

- **`draft` read a Pandoc citation as a bare key or not at all.** The
  bracket form was required to hold keys separated by semicolons, so
  every citation carrying a locator or a prefix was invisible:
  `[@a, p. 3]`, `[see @a]`, `[-@a, ch. 2]` and `[@a, p. 3; @b, p. 4]`
  all matched nothing. Pandoc's grammar is
  `[prefix @key suffix; @key2 suffix2]`, and a page number is how a
  large share of real Markdown citations are written, so `draft`
  answered "no citations were found" to manuscripts that cite in
  every paragraph. The bracket body and the key now both require a
  boundary before the `@`, so an address such as `[contact me at
  x@y.com]` is still not a citation, and nothing is deleted from a
  sentence that holds no citation at all.
- **`draft` put the raw command in the sentence it asked the author to
  paste.** The plural citation commands one parser had just learned
  were never stripped by the other: a sentence ending `\cites{a}{b}`
  became `claim: | ... \cites{a}{b}.` - a sentence no human wrote, in
  the one field this command exists to propose.
## [0.19.86] — 2026-11-03
### Fixed

- The plural citation commands are read, in both the converter and the
  bibliography scan.  `\cites{a}{b}`, `\parencites`, `\textcites`,
  `\autocites`, `\footcites`, `\smartcites`, `\supercites` and
  `\fullcites` take one brace group per source, which the citation pattern
  could not match: it stopped at `cite`, and the `s` that follows is neither
  `*` nor `[` nor `{`.  The command then fell through to the generic rule
  for an unknown command - drop the name, keep the arguments - so every key
  was left in the prose as a bare word and `citation_sites` reported a
  manuscript that cites three sources at once as citing none.
  `\fullcite`, `\parencite`, `\textcite`, `\autocite`, `\footcite`,
  `\smartcite` and `\supercite` were missing from the same pattern
  altogether, so a biblatex manuscript produced no proposals at all.
  Measured: `\cites{a}{b}` went from `'ab'` with no site to `[@a; @b]`
  with two; the seven singular names went from no site each to one.
## [0.19.85] — 2026-11-03
### Fixed

- A quote the author wrapped in quotation marks is now recognised as the
  quote it is.  The marks are how a manuscript introduces somebody else's
  words, and they are not on the page unless the page quoted somebody too,
  so a sentence copied out of the source and put in quotes matched no tier
  and came back as `quote-fuzzy` at high severity - with a message that
  contradicted itself: "the source has a similar passage but not these
  words verbatim (closest passage, page 1, similarity 1.00)".  Measured on
  a page holding the sentence bare: `tier='fuzzy' similarity=1.000` before,
  `tier='exact'` after.  Eleven bracket pairs are peeled - `"` `'` and the
  curly, corner, white-corner, book-title, angle, lenticular, tortoise and
  halfwidth CJK forms - but only when the pair matches and there is
  something between the marks.  The retry is only accepted when it finds
  the quote: a weaker verdict about text the author did not write is not an
  improvement on the verdict about the text they did.
## [0.19.84] — 2026-11-02
### Fixed

- The fuzzy tier can now compare Chinese.  It counts the units it compares,
  and it counted whitespace chunks: Chinese has no spaces, so a 40-character
  quote was one token, below `MIN_FUZZY_TOKENS`, and the tier answered
  "quote not found (too short for a fuzzy comparison)" about a sentence whose
  every character had just been compared.  A quote that differs from the page
  by a character or two was therefore reported as absent, at high severity,
  instead of as a near match.  A CJK character is now one token and a Latin
  word is still one token; the closest-passage excerpt joins characters
  without spaces so it reads as the prose the author wrote.  Measured on 60
  sentences of this project's own Chinese: one changed character scores at
  least 0.667 and 95% at least 0.857, while two unrelated sentences score at
  most 0.333.
## [0.19.83] — 2026-11-02
### Fixed

- A control word followed directly by Chinese text no longer eats the
  sentence.  `str.isalpha()` is true for CJK characters, and Chinese prose has
  no spaces, so `\noindent构式语法认为...` was read as a single control word
  named `noindent` plus the whole sentence - and the sentence was dropped with
  the name.  Measured on a four-line `ctexart` document, every line of prose
  disappeared and what survived was the closing punctuation.  The damage is
  silent: `draft` proposes nothing for a manuscript full of sentences, and
  `check` reports a clean run over text that was never read.  Control words are
  now scanned as a backslash followed by ASCII letters, which is what TeX
  itself does, in all five places that scan one - the converter, the
  conditional reader, and the file-inclusion reader.
## [0.19.82] — 2026-11-02
### Fixed

- The Chinese LaTeX stacks no longer paste font names and point sizes into the
  prose.  `\zihao`, `\CJKfamily`, `\CJK`, `\chinese`, `\fontsize`,
  `\linespread`, `\setCJKmainfont` and the `\ctexset`/`\CTEXsetup` family all
  name a font, a size or a registry code, and the converter's fallthrough - drop
  the command, keep what it wraps - kept the argument.  On a `ctexart`
  manuscript `{\zihao{5} 相关研究 ...}` became `5 相关研究 ...`, so `draft`
  proposed a claim whose text opens with the point size; `\ctexset{...}` left
  `section/format=` and `\CTEXsetup[format=...]{section}` left both the bracket
  and the word.  Fifteen commands are now in the table that drops every argument.
## [0.19.81] — 2026-11-02
### Fixed

- A citation removed from Chinese prose no longer leaves a space inside the
  sentence.  `statement_of` closes the gap a marker leaves before a closing
  mark, and the first version of that line listed the five Latin marks only:
  `相关研究指出词汇与构式之间存在互动关系 [@page]。` became
  `相关研究指出词汇与构式之间存在互动关系 。`, which is not how the sentence
  is written and not how it will be quoted back at the source.  The marks are
  now one set, `_NO_SPACE_BEFORE`, covering the CJK stops, the small marks, the
  ellipsis and the closing brackets as well as the Latin five, and the space
  between two words is still left alone.
## [0.19.80] — 2026-11-02
### Fixed

- Chinese, Japanese and Korean prose is split into sentences, and a passage is
  measured in words instead of characters.  A full stop in those scripts is not
  followed by a space, and the splitter required one, so a whole paragraph came
  back as a single run: `_sentences_of("第一句话。第二句话。第三句话。")` returned
  one sentence, not three.  That run then exceeded the passage ceiling, so
  `draft` refused it and reported `nothing on any page shares enough terms with
  the sentence (3 needed)` about a paragraph that shared eighteen of them.  The
  same paragraph was written into `claim:` as the claim text, so a proposal
  built on it was built on words the author never wrote as one sentence.  The
  splitter now breaks after CJK terminal punctuation without consuming anything,
  so a closing bracket stays with the sentence it closes.  The floor and the
  ceiling are now counted in words - a run of letters, or one CJK character -
  because a character is a letter in English and a syllable in Chinese: measured
  on this repository's own prose, the old character window 40..400 kept 37% of
  Chinese sentences where the word window 7..70 keeps 86%, and keeps 84% of
  English sentences either way.
## [0.19.79] — 2026-11-02
### Fixed

- A footnote is no longer spliced into the sentence it hangs on.
  `The method works\footnote{See \citep{fn} for the proof.}, and we ...`
  converted to `The method worksSee [@fn] for the proof., and we ...`, so
  `draft` proposed a claim whose text contains the word `worksSee` - a string
  that appears in no paper.  `\footnotetext` and `\marginpar` did the same.
  The bodies now move to the end of the converted text as their own block, so
  the main sentence survives whole, the note keeps the author's words, and a
  citation inside a note still counts as a citation.  Emitting the note as a
  paragraph where it was written was tried first and rejected: it broke the
  main sentence at whatever punctuation followed
  (`'The method works\n\nSee [@fn] ...\n\n, and we show it.'`).
## [0.19.78] — 2026-11-02
### Fixed

- Text TeX never reads is no longer converted.  `\iffalse ... \fi`
  is how a LaTeX author comments out a paragraph, and it was being read as
  prose: `\iffalse \citep{hidden} \input{ghost/sec} \fi`
  measured as `[@hidden]` in the converted text and `ghost/sec` in the
  include list.  So `draft` proposed a claim for a citation the author had
  turned off, and the author was told a file was missing that the paper
  never reads.  A `\else` inside such a branch is live text and is kept;
  `\if0` is treated as `\iffalse`; nesting is counted, so two dead
  blocks in a row are two dead blocks.
- A live conditional no longer leaves its own marker in the sentence.
  `\iftrue \citep{shown} \fi` keeps the body, which the
  unknown-command fallthrough already did, but the fallthrough also dropped
  nothing else - `\ifdefined\foo \citep{shown} \fi` pasted
  `ifdefined` into the words.  An unterminated conditional follows TeX: a
  dead body takes the rest of the file, a live one is converted to the end.
- `\ifthenelse{test}{yes}{no}` keeps both branches and drops the test.
  The test used to be glued to the first branch
  (`\ifthenelse{1=2}{\citep{no}}{\citep{yes}}` measured as
  `1=2[@no][@yes]`), the same defect as the counter arguments fixed in
  0.19.77 - a fragment no reader of the paper ever sees, at the front of a
  sentence that `draft` then proposes as the claim text.

  The conditionals that take operands before their body (`\ifnum`,
  `\ifdim`, `\ifodd`, `\ifx`, `\ifcat`, `\ifcase`) are
  counted for nesting and otherwise left alone, so their operand is still a
  word in the sentence.  Dropping operands is a token-level scan rather than
  a table of command names, and a half fix that cut the body without reading
  the operand would drop real text.  `tests/test_latex_conditionals.py`
  records that limitation as a test rather than leaving it to be discovered.
## [0.19.77] — 2026-11-02
### Fixed

- A command that names a counter, a length, a style or a registry key no
  longer pastes that name into the sentence around it.  `\setcounter{page}{3}`
  used to convert to `3`, glued to the next word: a paper whose section
  began with that line had a sentence starting `3We collected 40,688
  examples`, and `draft` proposed exactly that as the claim text - a number
  the author never typed, in a block the ledger then records.  Twenty-eight
  commands were falling through to "keep whatever it wraps" and now drop
  their arguments whole: the counter and length commands
  (`\setcounter`, `\addtocounter`, `\stepcounter`,
  `\refstepcounter`, `\setlength`, `\addtolength`,
  `\settowidth`, `\newcounter`), the page-style and running-head
  commands (`\pagestyle`, `\thispagestyle`,
  `\pagenumbering`, `\markboth`, `\markright`,
  `\addcontentsline`), the silent-spacer `\phantom` family,
  `\rule`, `\index`, `\glossary`, `\citeindextype`,
  `\pdfbookmark`, `\definelabel`, `\usetikzlibrary`,
  `\graphicspath`, `\selectlanguage`, `\footnotemark`,
  and `\DeclareMathOperator`.
- `\multicolumn{2}{c}{text}` kept only its span, so the alignment `c`
  was glued to the cell: measured as `cwide text`.  Its text is the third
  argument, and the two before it are dropped.
- `\texorpdfstring{TeX text}{PDF text}` said the words twice, once in the
  form no reader sees.  Only the first argument stays.
- `\newcommandx`, `\renewcommandx`, `\providecommandx`
  and the xparse `\NewDocumentCommand` family were not recognised as
  definitions, so `\newcommandx{\x}[1]{Body #1}` measured as
  `[1]Body #1` - the parameter count and the body back in the prose, which is
  the defect 0.19.76 fixed for the older spellings.
## [0.19.76] — 2026-11-02
### Fixed

- A macro definition's body was read as a sentence. `\newcommand`, `\renewcommand`, `\providecommand`,
  `\DeclareRobustCommand`, `\def`, `\gdef`, `\edef`, `\xdef`, `\newenvironment`,
  `\renewenvironment` and `\newtheorem` were handled as "drop one argument", so everything
  after the name - the parameter count, the optional default, and the body -
  stayed in the stream. Two consequences, in opposite directions. A body that
  names a key put that key into the text: `\newcommand{\knuthcite}{\citep{knuth}}` turned
  a paper that never cites Knuth into one that does, and `draft` proposed a
  `sources.toml` line for it. A body that names a parameter lost a real
  citation: `\newcommand{\seecite}[1]{see \citep{#1} for details}`
  recorded a citation to the key `#1` while every `\seecite{knuth}` became a bare word,
  so a paper that cites once per paragraph was told it cites nothing.
  `included_files` had the same hole from the other side: a body holding
  `\input{#1}` was reported as a file named `#1`.

  The three shapes are read by `_definition_end`: a braced name followed by an
  optional count, an optional default and a body; the low-level
  `\def\name#1{body}` form whose name is not in braces; and
  `\newtheorem{name}{Printed}[within]`, whose argument order matches neither of the others.
  `_without_definitions` runs the same cut over the raw source, so a checker
  that reads it without converting first gets the same answer. Measured before
  the fix: 26 new tests, five mutations of the new code, all five red.
## [0.19.75] — 2026-11-02
### Fixed

- Seven more file-inclusion commands pasted their path into the sentence and
  reported nothing: `\subfile{sec/intro}` became `sec/intro` in the converted
  text while `included_files` returned `[]`, and the same held for `\import`,
  `\subimport`, `\includestandalone`, `\includepdf`, `\lstinputlisting` and
  `\verbatiminput`. Each was in neither `_KEEP_ARGUMENT` nor `_DROP_ARGUMENT`,
  so it fell through to "drop the command name, keep everything after it" - the
  same fallthrough that produced `blueblue` for `\textcolor`. Two things went
  wrong at once: the sentence `draft` proposes a claim for carried a file path,
  and the note telling the author which parts of the paper were not read was
  empty, so a paper split across seven files looked as if it had been read
  whole. `_INCLUDE_ARGUMENTS` now records each command and how many arguments
  name the file (`\import` and `\subimport` take two, and their names are
  concatenated), the converter drops the arguments whole, and `included_files`
  reports them in source order alongside the three forms it already knew.
  `tests/test_latex_more_includes.py` covers all seven commands, optional
  arguments, the verbatim and comment forms that must stay invisible, and one
  end-to-end `draft` run; four mutations - leave the name in the prose, never
  report the file, report only the first argument of a two-argument command,
  drop only the command name - are all red.
## [0.19.74] — 2026-11-02
### Fixed

- Ten LaTeX commands that take a non-prose argument and then the text kept the
  first argument in the output, because they were in neither `_KEEP_ARGUMENT`
  nor `_DROP_ARGUMENT` and fell through to "keep whatever this wraps, drop the
  name": `\textcolor{red}{small}` became `redsmall`,
  `\href{https://x}{this paper}` became `https://xthis paper`,
  `\scalebox{2}{big}` became `2big`, `\parbox{3cm}{boxed}` became `3cmboxed`,
  `\hyperlink{target}{linked}` became `targetlinked`, and the same for
  `\colorbox`, `\resizebox`, `\fcolorbox`, `\makebox` and `\framebox` (the last
  two also kept their `[width]`). That text is what `draft` puts in the claim it
  asks the author to paste, so the proposal was built on a sentence the paper
  does not contain. A new `_SKIP_FIRST_ARGUMENT` set skips the non-prose
  arguments - one for most, two for `\fcolorbox` and `\resizebox` - and converts
  the last one as ordinary prose, so `\textcolor{blue}{\textbf{blue}}` still
  yields `blue` rather than `\textbf{blue}`.
## [0.19.73] — 2026-11-02
### Fixed

- `\input` has two spellings and the converter knew one. Plain TeX writes
  `\input sec/intro`, LaTeX writes `\input{sec/intro}`; only the braced form was
  dropped from the prose and named in the "this document pulls text in from"
  note. The bare form did both wrong at once: the file name stayed glued into
  the sentence (`We show this in sec_intro and continue the argument here.`),
  which is the sentence `draft` proposes a claim for, *and*
  `included_files()` returned `[]`, so a paper split across files got a clean
  zero that named neither the missing half nor the stray word. Measured on a
  two-line `.tex`: before, `to_text` returned `'We show this in sec_intro and
  continue the argument here.'` with `included_files() == []`; after, the
  sentence reads `'We show this in and continue the argument here.'` and the
  note names `sec/intro`. A bare name runs to the next whitespace, as it does
  in TeX, so `\input third/three.tex` keeps its extension.
## [0.19.72] — 2026-11-02
### Fixed

- A test compared two ledgers byte for byte, and a ledger records when it was
  written: the comparison was green only while both `scan` runs landed inside
  the same second. The sdist job failed on it at 2026-11-02T14:54:18Z with
  `1 failed, 1529 passed, 7 skipped` and a diff of two ledgers that looked
  identical. The comparison now drops `generated_at`, and two new tests keep
  that honest - one proves the normaliser removes only the clock, one proves an
  unmodified `scan` still stamps a time. Mutating the normaliser and mutating
  `scan`'s timestamp both turn them red.
## [0.19.71] — 2026-11-02
### Fixed

- `Claim`'s docstring said the ledger stores the quote's fingerprint "so a later
  verification run can tell 'the quote is gone' from 'the quote moved'". No code
  reads `quote_fingerprint` back: `quote-moved` is decided from the page numbers
  the current run found, and the digest is a record that keeps the passage out
  of two places. The note now says that, and names the property that actually
  matters - `--allow-stale` lets a changed manuscript be checked, so an edited
  quote has to be compared against the source like any other. Measured before
  the change: editing a quote to something weaker under
  `--use-recorded --allow-stale` gave `quote-found` for the new text, because
  the check reads the manuscript, not the digest.
- Three tests keep that sentence honest: one reads the docstring, one asserts
  only the parser computes a fingerprint, and one fails if any module outside
  `model.py` mentions the field without writing it - which is what a comparison
  would look like.
## [0.19.70] — 2026-11-02
### Fixed

- A `sources.json` whose root is not an object - `[]`, `5`, `"page"`, `true` -
  was read as an empty manifest with no problem reported, so every claim was
  told `no entry in sources.json` about a file it was plainly looking at. That
  is the same wrong answer 0.19.66 fixed for the TOML path, still live on the
  JSON one; the message now names the type the file holds.
- `{"sources": null}` was read the same way, and the advice every claim gets -
  `add it to sources.json` - is followed by adding a second key beside the one
  that is wrong. The null key is now named.
- The message is asserted to carry the type (`holds list`, `holds int`), not
  only the shape, because the type is the part an author can act on: without it
  the sentence reads like a spelling rule rather than a diagnosis.
## [0.19.69] — 2026-11-02
### Fixed

- A `sources.toml` that the two manifest readers disagreed about is now refused
  by both, with one sentence. The pair was `_load_toml` (tomllib, 3.11+) and
  `_mini_toml` (the line-based subset, 3.10), and five spellings fell between
  them: a value written across lines (tomllib joins the body, the subset raises
  on the first line and drops the whole manifest), a line ending in a comma
  (tomllib refuses the file, the subset binds the key), a quoted key holding
  `=`, `#`, a bracket or a quote (tomllib binds it, the subset silently dropped
  the line), two assignments on one line (`a=b = "x.pdf"`, tomllib refuses,
  the subset binds `a`), and an inline table or dotted key at the root, which
  the previous release already refused. The CI matrix runs 3.10, 3.12 and 3.13,
  so the same project could bind on one interpreter and report `source-missing`
  on another. Measured after the fix: nine shapes checked at the
  `read_source_table` level, zero differing answers.
- The pre-scan asks only the questions that change what `sources` means. It
  refuses an inline table at the root and a dotted key under `[sources]`, and
  now an inline table is excluded from the two-assignment check as well -
  `x = { y = 1 }` holds its second `=` inside a value this reader cannot
  follow, binds no source either way, and refusing it would reject a manifest
  both readers answer the same way.
## [0.19.68] — 2026-11-02
## [0.19.68] — 2026-11-02
### Fixed

- The pre-scan that makes both `sources.toml` readers refuse the same spellings
  walked the whole file, so a dotted key under a table this tool never reads -
  `[other]` then `pa.ge = "dir/x"` - made the manifest unreadable:
  `found={}` with `manifest_problem` naming a key in an unrelated table.  Both
  readers agree about that file, which is the whole question, so the refusal
  was rejecting a manifest that answers the same question the same way.  The
  scan now asks only about the places that can change what `sources` means: an
  inline table at the root, and a dotted key under `[sources]`.  An inline
  table inside another table is left alone for the same reason.
## [0.19.67] — 2026-11-02
### Fixed

- `sources.toml` has two readers: `tomllib` on 3.11+, and the line-based subset
  on 3.10.  Four spellings were legal TOML that the two read differently, so
  the same file bound one way on one interpreter and another way on the other,
  and CI runs 3.10, 3.12 and 3.13:

  | manifest | `tomllib` | subset |
  |---|---|---|
  | `sources = { page = "a.txt" }` | binds `page` | sees no table |
  | `pa.ge = "a.txt"` | binds nothing at `pa.ge` | binds `pa.ge` |
  | `page = "a"` twice | refuses the file | last one wins |
  | `[sources]` twice | refuses the file | merges the halves |

  Both readers now run one pre-scan and refuse those four with the same
  sentence, so no interpreter reads a manifest as something the other does not.
  The refusal lives before the split because a check written inside the subset
  can only ever speak for the subset.  The spellings that do work are the ones
  the README already describes, and the messages name them: `[sources]` with one
  `key = "path"` line, and a quoted key - `"pa.ge"` - when the dot is part of
  the name.
## [0.19.66] — 2026-11-02
### Fixed

- A `sources.toml` entry whose value was not a path was dropped in silence, and
  the claim that named it was told there was no such entry.  `page = 5`
  produced `claim c1 names source='page' but no entry in sources.toml and no
  --source path resolves it; add it to sources.toml` about the line the author
  was reading.  Eight shapes did this: an integer, a float, a boolean, an array,
  an inline table, `sources = 5`, `sources = "page.txt"`, and an empty file.
  The first five are keys the manifest holds, so they now reach `unusable` and
  their message quotes the manifest that binds them; the two `sources = ...`
  shapes are a manifest that cannot be read at all, so they reach
  `manifest_problem`; the empty file keeps the old advice, because a file with
  no entries really does have no entry.  The 3.10 subset reader answers the same
  way as `tomllib`, so one manifest cannot bind on 3.12 and lie on 3.10.
## [0.19.65] — 2026-11-02
### Fixed

- `doctor` printed the reader's errno as a second problem when the manuscript
  could not be read.  A missing `manuscript.md` produced
  `[ok  ] sources  could not be read to check them: [Errno 2] No such file or
  directory: 'p\manuscript.md'` one line below the `manuscript` check that had
  already said the file does not exist, and a directory produced `[Errno 13]
  Permission denied` — a sentence that sends the reader to look at permissions
  on a path whose actual problem is that it is a directory.  The `sources`
  check now says `not checked, because the manuscript could not be read` and
  leaves the cause to the check that owns it, the same way the `manifest` check
  already hands its failure to the `manifest` line.
## [0.19.64] — 2026-11-02
### Fixed

- `--source` resolved its path by a different rule than the other six path
  flags. Every one of them accepts a path that already works and only falls
  back to `--root` for the rest, which is what makes
  `citevouch check paper/m.md --root paper` mean the same as `cd paper &&
  citevouch check m.md`. `--source` joined the root unconditionally, so with
  the project in `paper/` and the command typed from one level above,
  `--bib paper/refs.bib` worked and `--source paper/page.txt` exited 2 with
  `source paper\paper\page.txt does not exist` - about a file that is there.
  An author who has just learned one spelling from the error message gets the
  other spelling wrong, so all seven now share
  `sources._resolve` (which `scan._resolve` re-exports, so the existing call
  sites and tests keep working).
- The same split ran through `draft`'s output guard, which names the inputs a
  `-o` must not overwrite. It computed those names with its own
  root-joining rule while `read_source_table` used the shared one, so
  `draft --source paper/page.txt -o page.txt --force` protected
  `paper/paper/page.txt` - not a file - and wrote proposals over
  `paper/page.txt`, the source the run had just read a quote out of. The
  guard now names the same files the reader opens.
## [0.19.63] — 2026-11-02
### Fixed

- `draft` opened a source with the path it was about to write into
  `sources.toml`, which is relative to the project root, and `extract_pages`
  reads what it is given against the process directory.  From one level above
  the project the two differ, so a project that produced one proposal from
  inside produced none from outside: `citevouch draft paper/m.md --root paper
  --bib paper/refs.bib` wrote `0 claim block(s) proposed` and explained every
  citation with `source file page.txt does not exist` about a file sitting in
  `paper/page.txt`.  Nothing about the project differed between the two runs
  except the working directory.  The call site now opens `_resolve(root, path)`,
  the one rule the other five commands already share, and still records the
  root-relative `path` in the proposal.
- `draft` said `no `file` field in the bibliography` about a `.bib` whose entry
  had a `file` field naming a file that was not there.  `_why_no_file` only
  knew the two reasons `sources.toml` can give, so every other failure fell
  through to a summary that is false in the one case an author can see at once:
  the field is on the screen.  It now answers from the bibliography entry when
  there is one, naming the path it points at, and keeps the old summary for the
  three-way case that really has all three causes.  A Zotero `:path:mime`
  wrapper is unwrapped first, because that is the form the field is stored in.
## [0.19.62] — 2026-11-02
### Fixed

- `doctor` re-rooted a relative `--manuscript` path that already worked, so it
  disagreed with every other verb about which file it was reading.  From the
  directory above the project, `citevouch check paper/m.md --root paper`
  verified and exited 0 while `citevouch doctor --root paper --manuscript
  paper/m.md` reported `paper\paper\m.md does not exist` and exited 1.  The fix
  line printed with that failure recommends `paper/manuscript.md` — the exact
  shape that had just been rejoined — so following the advice reproduced the
  failure.  `doctor` now resolves paths through `scan._resolve`, the helper
  `scan`, `verify`, `check` and `draft` already share: a path that exists as
  typed is never re-rooted.  Seven tests, three mutations all red.
## [0.19.61] — 2026-11-02
### Fixed

- A `numbers:` line under a claim used to **throw the quote away**.  The key was
  in the set that decides "is this body a mapping at all", and nothing ever
  read its value (`_claim_from` derives `Claim.numbers` from the quote), so a
  correctly written `>> the quote` next to `numbers: 1` came back as an empty
  quote and `claim-uncheckable` — silent data loss for a block that had done
  nothing wrong.  Measured: `['>> We collected 40,688 examples.', 'numbers: 1']`
  returned `('', '', {})` where the same body without the second line returned
  `('We collected 40,688 examples.', '', {})`.  The set that decides the shape
  is now exactly `quote` and `claim`; inside a mapping a `numbers:` line is
  still consumed as a sibling key, because in YAML terms it really does end the
  value above it.  Nine tests, five mutations all red.
## [0.19.60] — 2026-11-02
### Fixed

- pypdf reports a damaged file twice: it logs (`invalid pdf header`, `EOF
  marker not found` through `pypdf._reader`) **and** it raises.  The raise was
  already caught and turned into a `source-unreadable` finding that says the
  same thing with more detail, so the log lines were a worse copy of a fact the
  reader was about to get — printed on stderr, next to a run that exits 1,
  where `--format json` consumers and CI logs have to filter them out by hand.
  Measured: one unreadable source printed **four** lines of pypdf's warnings
  around the single line this tool wrote.  A `_quiet_pypdf()` context manager
  now lowers the `pypdf` logger for the two reads that expect trouble (the
  extraction and the diagnosis) and restores it in `finally`.  Six tests, and
  five mutations all red — the first draft of those tests counted stderr text
  and **two mutations survived**, because pytest installs a log handler on the
  root logger and `redirect_stderr` never sees a record at all.
## [0.19.59] — 2026-11-02
### Fixed

- The body-attribute fix above had a regression of its own, caught before it
  left the branch by running the new file's tests against the shipped code:
  counting an `id:`/`source:` line as a "key" made a `>>` block (or any body
  with no `quote:` key) look like a mapping, so the quote came back **empty**
  and the attribute line became the claim text.  That is silent data loss, and
  it is worse than the defect being fixed: a quote that grew shows up in a
  verdict, and a quote that vanished shows up nowhere.  The mapping branch is
  now entered only by the two keys a body is actually divided by (`quote:`,
  `claim:`, `number:`); attribute lines are read *inside* it.  Two tests hold
  the shapes that must not move, one per fallback, and both fail against the
  broken version.
## [0.19.58] — 2026-11-02
### Fixed

- A claim block written as a mapping - its attributes one per line under the
  fence, `id:` / `source:` / `page:` / `ref:` - had those lines appended to the
  quote.  The words were then searched as if the author had quoted
  `source: paper` out of their PDF, and the verdict was `quote-missing`
  (high): an accusation against a passage that is on the page.  Measured
  before this, with the page reading "We collected 40,688 examples in the
  corpus." and the block carrying one `ref: paper2026` line:
  `[high] quote-missing at m.md:3 (c1): We collected 40,688 examples in the
  corpus. ref: paper2026 - quote not found in page.txt`.  Both dialects had it
  (the ` ```claim ` fence and the `<!-- claim ... -->` comment), because they
  share one body reader, so a fix in one branch would have left the other
  broken.  The six keys a claim may carry are now read from the body and
  merged under the opening line, which wins when both name the same key: the
  fence is where the format is documented.  Any other key is still quote text
  - a quote that grew is visible in a verdict, and a quote that silently
  shrank is visible nowhere.  Five mutations, five red, none survived.
## [0.19.57] — 2026-11-02
### Fixed

- `doctor` gained the check it was missing: whether the source keys the
  *manuscript* names are bound at all.  The `manifest` check asks whether each
  key in `sources.toml` maps to a file that is on disk; the `claims` check asks
  whether the manuscript holds blocks.  Both can pass while every block names a
  key nobody binds, and that is the one failure `doctor` exists to explain.
  Measured before this: a project whose `sources.toml` binds `other =
  "other.txt"` and whose only claim names `source=paper` got seven `[ok  ]`
  lines, exit **0**, and the closing sentence "Everything this tool needs is on
  this machine. If quotes are still reported missing, the source files are the
  place to look." — while `check` on the same project printed `[high]
  source-missing ... claim c1 names source='paper' but no entry in
  sources.toml` and exited 1.  The reader is sent to look at source files that
  are all present, correctly spelled, and simply filed under a different name.
  The new line names each unbound key and the files nearest it on disk, and it
  leaves three states to the lines that already own them: a manifest that will
  not parse, a key whose file is missing, and a manuscript that names no keys at
  all.  This is the fifth instance of one shape (0.19.44 through 0.19.47 were
  the others), so the test file compares `doctor` against `check` on the same
  projects instead of remembering what each one prints.  Seven mutations, all
  red; one of them survived the first pass and was killed by a test built from
  the shape it needed.
## [0.19.56] — 2026-11-02
### Fixed

- `--bib` is refused by the two commands that do not read a bibliography,
  instead of being accepted and ignored.  `scan` parses each `.bib` and records
  its entries into the ledger; `verify` and `check --use-recorded` check the
  manuscript's keys against `ledger.entries` and never open a `.bib`.  Both
  accepted the flag anyway, so `check m.md --use-recorded --bib nowhere.bib`
  and `verify m.md --bib nowhere.bib` exited **0** for a path that does not
  exist — and `action.yml` always passes `--use-recorded`, so on a pull request
  the flag was pure decoration whose whole purpose was to make the run able to
  fail.  Validating the path would only catch typos (a correct path is still
  not read), so the command is refused and both working alternatives are named
  in the message.  Six mutations, all red.
## [0.19.55] — 2026-11-02
### Fixed

- A damaged `.citevouch/cache/<sha>.json` is now a cache miss instead of a
  crash.  The extraction cache trusted the shapes it read, so a scratch file
  holding `{"pages": 5}`, `{"pages": [null]}`, a page whose `number` was `"x"`,
  or a JSON root that was a list all reached the interpreter and exited **1** -
  the code that means "findings at or above `--fail-on`" - with a traceback
  (`TypeError: 'int' object is not iterable`, `AttributeError: 'NoneType'
  object has no attribute 'get'`, `ValueError: invalid literal for int()`).
  A cache can be recomputed from the bytes it describes, so an unrecognised
  shape is dropped and the file re-extracted; a *recognised* shape is still
  used, which is why the fix is not "stop caching" - there are tests that fail
  if the cache stops being read.  Eight mutations, all red, including one that
  only a raw-JSON root fixture could kill.
## [0.19.54] — 2026-11-02
### Fixed

- A `source-unreadable` finding no longer tells you to install a reader you
  already have.  Four different problems - a truncated download, a file saved
  with the wrong extension, an empty file, and a machine with no PDF reader -
  all produced the same sentence, `install pypdf (pip install pypdf) or
  pdftotext and try again`, on machines where `citevouch doctor` had just
  reported `[ok  ] pypdf 6.16.1`.  The readers already knew: pypdf raises
  `PdfStreamError: Stream has ended unexpectedly` or `EmptyFileError: Cannot
  read an empty file`, and poppler prints `invalid pdf header` or `EOF marker
  not found`.  Those sentences were discarded one frame above the message that
  needed them, because the extractors have to return `None` and nothing else so
  that a corrupt PDF stays a finding rather than a crash.  The message now asks
  both readers once more, on the failure path only, and quotes them.  Six
  mutations, all of them fatal; the sixth was survived by the first version of
  the tests, because a message holding one true sentence is still not the old
  false one - the fix now has a test that drives `pdftotext` directly rather
  than relying on whatever this machine has installed.
## [0.19.53] — 2026-11-02
### Fixed

- **A mistyped `--root` was accepted, and every verb then answered a question about a directory that was not the project.** In a project at `proj/`, `scan proj/m.md --root nowhere` **created** `nowhere/` and wrote a ledger into it - `citevouch: wrote nowhere\citevouch.lock.json (1 claim)` - leaving a phantom project on disk that the next run would not even look at; `doctor --root nowhere` made `nowhere/.citevouch/cache` in order to test it; `draft ... --root nowhere` wrote its proposals there. The worst one is `check`, because it is wrong rather than merely untidy: the manuscript still resolved (a path that exists as given is never re-rooted) so the run looked like it had read the project, and then reported `[high] source-missing ... no entry in sources.toml` - a sentence about the one thing the author had already got right, with that manifest sitting next to the manuscript the whole time. None of it was repairable downstream: by the time a message is being written the run has already answered a question about the wrong directory. `main()` now calls `_project_root(args.root)` once, before any verb, which refuses a root that is not a directory with exit 2 and a sentence naming the usual fix ("drop `--root`: that is the default"). A root that is a **file** says "is a file, not a directory" and not "does not exist" - and a root that is an unreachable share keeps `why_not_a_file`'s unreachable sentence, which is the distinction that function exists for. `init-demo` has no `--root` and is untouched. Four mutations, all red: the guard never being called, a missing root being allowed through, a file root being reported as missing, and the message dropping the default-root advice.
## [0.19.52] — 2026-11-02
### Fixed

- **`draft -o` could write proposals over a file the project is read from, and `--force` made it easy.** The command guarded its output against the manuscript and against nothing else, so `-o sources.toml --force` reported success - `citevouch: wrote sources.toml; read it, then citevouch check sources.toml` - and left the project unable to resolve a single claim: `check` answered `[high] source-missing ... the manifest could not be read: sources.toml could not be read as TOML (Invalid statement (at line 1, column 1))` for every claim in it, where the same manuscript had been `1 claim - 1 verified` a moment before, and `doctor` failed its manifest check. `-o citevouch.lock.json --force` did the same to the ledger, after which `verify` said `ledger citevouch.lock.json is not readable JSON: Expecting value: line 1 column 1 (char 0)` - the recorded evidence for the whole manuscript, gone. `-o refs.bib --force` alongside `--bib refs.bib`, and `-o papers/p2.txt --force` alongside `--source papers/p2.txt`, both wrote through as well. `cmd_draft` now calls `_refuse_an_output_that_is_an_input`, which compares the resolved output against every file the run actually reads: both manifest names, each `--bib` file, each `--source` file, and the ledger. Both manifest names rather than the one that exists, because writing `sources.json` beside a live `sources.toml` overwrote nothing and still broke the project - a project holding both is refused rather than guessed between, so every claim went from verified to `[high] source-missing ... both sources.toml and sources.json exist, and only one of them is read`. `--force` does not reach the guard: it exists to replace a proposal the author already looked at, not to promise that any path is safe. Three mutations, all red - the guard not being called at all, only the manifest that already exists being protected, and the ledger dropped from the list.
## [0.19.51] — 2026-11-02
### Fixed

- **`draft` proposed a block whose id the manuscript already used, so the block the author pasted was the one `check` ignored.** The command names each proposal after its citation key and tells the author to read the file and copy the blocks in. A manuscript that already holds `id=paper` and one more sentence citing `[@paper]` therefore got a proposal labelled `paper` too, and appending it - the only thing the tool tells you to do - produced `[high] claim-uncheckable at merged.md:12 (paper): claim id 'paper' is used twice (first at line 3); the ledger cannot track both, so the second is ignored`. The ignored one is the newest block in the file. `draft()` now takes `taken_ids`, and `cmd_draft` fills it from `parse_manuscript(text)` so the ids the file already holds seed the set `_claim_id` de-duplicates against; the second proposal for one key becomes `paper-2`, then `paper-3`, and a manuscript with no blocks still gets the plain key. Four mutations, all red - one ignoring `taken_ids`, one letting it *replace* the de-duplication (which would make two citations of one key collide with each other instead), one passing `None` from the command, and one reading only the first existing id, which a one-block fixture cannot see.
## [0.19.50] — 2026-11-02
### Fixed

- **`doctor` described a file with two claim blocks as a file with one.** `_claim_blocks` counted `len(parsed.claims)`, which holds the blocks the parser *accepted*; a manuscript with one good block and one that forgot `id=` reported `[ok  ] claims      1 claim block`. The blocks the parser saw live in `parsed.spans` and there were two, so the check said something false about the file - in the one check whose whole purpose is to stop false statements, and in the module whose docstring explains that a refused block "has its own finding ... `doctor` exists to explain silence, not to pre-empt a message the next command will print". Both counts are defensible: `check` on that file prints `[high] claim-uncheckable` at the refused line and `1 claim - 1 verified`, and one of those numbers is a description of the file while the other is a description of the run. `doctor` now reports `2 claim blocks, 1 of which the parser could read; the next command names the rest`, and keeps the terse `2 claim blocks` for a file where nothing was refused, because a clean project should not be told about a split it does not have. Five tests, three mutations all red - one of them restoring exactly the shipped line, one dropping the "N of which" half (a count with no explanation of the gap is a riddle), and one that extends the long sentence to every file.
## [0.19.49] — 2026-11-02
### Fixed

- **A lockfile with balanced brackets could still crash the reader, because `json.loads` is a recursive-descent parser.** The guard added in 0.19.48 catches the damaged *shapes* a lockfile can hold, and `_read_ledger` already caught `ValueError` for malformed JSON - but a file of twenty thousand nested brackets is not malformed, it is too deep: the decoder burns interpreter stack until `RecursionError: Stack overflow (used 2912 kB) while decoding a JSON array from a unicode string`. `RecursionError` is not a `ValueError`, so it escaped `main` and the interpreter exited **1**, which in this tool means "findings reached the threshold" - the same false verdict as the twenty crashes before it, arriving through the parser instead of through a key. Nothing this tool writes nests more than four deep, so a nest the parser cannot survive gets the answer a syntax error gets: `UsageError`, exit 2, and a message saying the file nests too deeply. Five tests, including one that asks the *interpreter* whether it survived (2000 nested arrays decode, 20000 do not) rather than pinning one depth on every Python this runs on, and a subprocess test that asserts no traceback reaches stderr. Two mutations, both red - but only after the first run reported both red for the wrong reason: the mutant harness called `pytest` in a subprocess without an importable pytest, and read "no module named pytest" as a passing red. A guard is only verified by the run that was actually measuring it.
## [0.19.48] — 2026-11-02
### Fixed

- **A damaged lockfile crashed the three verbs that read it, and a crash exits 1.** `Ledger.from_json` trusted every field: `raw.get(...)` on each list element, `int(...)` on each count. A lockfile edited by hand, truncated by a bad merge, or written against yesterday's shape therefore raised `AttributeError`, `TypeError` or `ValueError` straight out of `main` - and because an uncaught exception makes the interpreter exit **1**, those crashes were indistinguishable from "findings reached the threshold". Twenty damaged shapes were run through `report`, `verify` and `check --use-recorded`; all twenty crashed all three. `cli._read_ledger` already refuses a ledger whose *schema number* is too new ("Reading a future ledger with today's parser would half-parse it ... `source-missing` on a half-read claim is the false verdict this tool exists to avoid"), and that reasoning was never applied to the file's own shape. It is now: `_object`, `_section`, `_whole` and `_texts` refuse what this code cannot read in full and name the section and the key (`ledger claims[0] must be an object, not NoneType`), `_read_ledger` prefixes the path so the reader knows which file to open, and every one of them is a `UsageError`, which is exit 2. `claims: null` is refused rather than read as an empty ledger, and `fields: []` is refused rather than falling back to `{}` - a half-read entry reports `bib-field-missing` about a title that is in the file. Nine mutations; eight red, and the ninth is an equivalent mutant (the type guard makes the old coercion unreachable). A guard that refuses a file the *writer* produces would be worse than the crash it replaced, so the suite also round-trips a real `scan` output through `from_json` and asserts the two are equal.
## [0.19.47] — 2026-11-02
### Fixed

- **`doctor` passed a manuscript that holds no claim blocks, which is the same silence it was written to explain.** A file with no blocks produces `0 claims - 0 verified, 0 moved, 0 missing` with `worst severity: info` and exit 0 - a green run of a check that never happened. `check` reports `no-claim-blocks` (high) and exits 1, and `verify` does the same for a ledger that recorded none; `doctor` printed `[ok  ] manuscript  manuscript.md (76 bytes)`, closed with `Everything this tool needs is on this machine.` and exited 0. This is the fourth version of one shape in this file: the manuscript line asked whether a path is a file, and "is a file" is not a question about whether the run will find anything. It now carries a seventh check, `claims`, that parses the manuscript and reports `5 claim blocks`, or `none that the parser could read; the next command names why` for a block the parser refused (that case already has its own finding naming the line), or fails with the `citevouch draft` step for a file with nothing to propose from. The condition itself is now `ParseResult.nothing_to_check` - one property, not the same expression typed out in three modules, which is exactly how the third reader came to be written without it. Six mutations, all red; two survived the first run and both were real gaps - a manuscript fixture with exactly one block cannot fail a test about counting, and my own mutation anchored on the wrong `ok=False` (there are two). One README example and the fixture's `# t` manuscript had to change with it, which is the same lesson as the last three rounds.
## [0.19.46] — 2026-11-02 — 2026-11-02
### Fixed

- **`doctor` passed a `.tex` manuscript with a clean bill of health, about the one file `check` refuses outright.** `check paper.tex` exits 2 and says claim blocks live in Markdown, not in a `.tex` file - scanning one would record zero claims and report a clean run for a manuscript nothing checked. `doctor --manuscript paper.tex` printed `[ok  ] manuscript  paper.tex (69 bytes)`, closed with `Everything this tool needs is on this machine.` and exited 0. So the command that exists to explain "why did it find nothing" was silent about the one input that guarantees there is nothing to find, and a reader doing the sensible thing - check the machine before trusting the report - got an all-clear on a file the next command would not read. `doctor` now asks `latex.looks_like_latex`, the same predicate the scanner uses, and gives the same reason plus the `citevouch draft` step that does work on a `.tex` source. One of the four mutations for this - "every file is now called LaTeX" - was caught by the demo README test rather than by the new ones, which is what that test is for.
## [0.19.45] — 2026-11-02
### Fixed

- **`doctor` called a directory `does not exist`, which is the one thing it is not.** The manuscript check was `if target.is_file(): ... else: "does not exist"`, so `--manuscript adir` on an existing directory reported a path the reader can see in their file manager as absent - and `citevouch check` on that same path said `is a directory, not a file`. Two commands, two stories about one path, and the wrong one came from the command whose job is to explain the other. `doctor` now asks `errors.why_not_a_file`, the same function the rest of the tool uses, so a directory, an unreachable share and a genuinely missing file are three different sentences with three different next steps; the directory gets its own fix line naming the manuscript inside it rather than the generic "`--root` is the project directory" advice.
## [0.19.44] — 2026-11-02
### Fixed

- **`doctor` checked that `sources.toml` exists and never that the files it names do, so it printed `[ok  ] manifest` and `Everything this tool needs is on this machine.` about projects where every claim was about to fail.** The check stopped at `candidate.is_file()`: a manifest that would not parse, one that mapped every key to a path that is not on this disk, one that named a directory, and two manifests side by side all printed the same `[ok  ] manifest sources.toml (N bytes)` and exited 0 - and the very next command printed, per claim, `[high] source-missing`, which is the exact failure `doctor` exists to explain. A file's size is not a fact about whether it points anywhere. `doctor` now reads the manifest through the same `read_source_table` the rest of the tool uses and reports three different answers, because they need different work from the reader: no manifest at all stays ok (passing `--source` is supported), a manifest that will not parse is a syntax problem in one file, and a manifest naming absent files is a path problem in this project, with the missing keys named and a fix that says to re-run `scan` because the recorded ledger still holds the old paths.
- **The `doctor` test fixture was itself a project that could not run.** It wrote a `sources.toml` naming `a.txt` and never wrote `a.txt`, so three tests that assert an ok report were passing only because the check did not look at the manifest.

## [0.19.43] — 2026-11-02
### Fixed

- **`draft` could not tell "you have no citations" from "none of your citations had a local PDF", and printed the same thing for both.** The two zeros are not the same zero: one is a fact about the machine, the other is a fact about the reading, and the second one is usually the tool's fault - a citation written `(Van Eecke 2026)` instead of `[@vaneecke2026]` is invisible to the parser. Measured before this: a manuscript with no markers and a manuscript whose one marker pointed at a missing file produced the same stderr summary (`0 claim block(s) proposed (0 verbatim), 0 citation(s) left as comments`), the same exit 0 and almost the same five-line file, and then the same advice - *read it, then* `citevouch check <file>` *to see what it got wrong* - about a file that held nothing to read. `draft` now records that it found no citations at all, says which two forms it reads (`[@key]` and `\cite{key}`), names an example of what it does not, and replaces the advice with a sentence about the real problem, in the summary, in the prose and in the file the author commits.
## [0.19.42] — 2026-11-02
### Fixed

- **The new `claim-number-differs` rule accused 38.5% of correct claims, and it was my own rule from the release before.** The rule shipped with a single test: is the claim's number one keystroke from a number in its quote? Two different years are almost always one keystroke apart (`2010`/`2011`, `1995`/`1999`), and so are two small ordinals (`1`/`2`, `3`/`4`), which is why a passage that restates a quote and names a second study looked exactly like a mistyped count. Measured against adjacent real sentences from 100 published papers: **67 of 174 pairs flagged, every one of them correct text**. Reporting a right claim is worse than missing a wrong one - it teaches the author to stop reading the report, after which the tool is worth nothing. Three guards now stand between a pair and a report, each judged on the two numbers actually being compared rather than on the sentence as a whole: neither may be a plausible calendar year (`1500`-`2100`), at least one must be written the way a copied quantity is written (separator, decimal, percent), and the claim's number must not be printed anywhere on the cited page - an author who writes `10,000` that appears further down the page read it somewhere. After the fix the same 788 adjacent pairs produce **zero** flags, while `40,688` mistyped as `80,688` still exits 1.
## [0.19.41] — 2026-11-02
### Fixed

- **A claim could restate its own quote with a different digit and verify.** `claim.numbers` holds the numbers inside the *quote*, because those are what the cited page has to contain; nothing in the run ever compared the claim's own sentence against them. Measured before this: a page reading `We collected 40,688 examples` quoted exactly, with the claim restating it as `80,688`, gave `[info] quote-found`, `worst severity: info` and **exit 0** - the one error the author most wants a machine to find, passing the gate built to find it. The new `claim-number-differs` (`high`) reports a claim number that is one keystroke from a number in its own quote, at the point where the quote has been confirmed to be the page's text; a number that is merely different is not reported, so a year the author supplied (`2020`) or a total they derived (`4,068` next to `40,688`) stays quiet. The message quotes the spelling the page prints, not the canonical form the comparison uses.
## [0.19.40] — 2026-11-02
### Fixed

- **`draft` proposed a quote for the sentence after the one the author cited.** When the marker is typed after the full stop - `usage. [@p]`, which Pandoc accepts and which is how a citation added at the end of a thought comes out - the splitter put the marker at the start of the next run of text, so the cited sentence came back as the *following* sentence, or as `[@p].` when there was nothing after it. `draft` then looked for a passage matching a sentence the author never cited and backed it with that paper's file: a wrong claim attributed to a real source, which is the one thing this tool exists to prevent. Measured over the 71 usable papers in the construction-grammar corpus, this shape produced a proposal for 0 of them before the fix and 46 of 46 after it. The rule now reads the text between a run's start and the marker: when that prefix holds no words the marker trails the sentence before it, and a paragraph containing nothing but markers looks back one paragraph.
## [0.19.39] — 2026-11-02
### Fixed

- **A quote copied out of a reader was reported missing whenever the page broke a hyphenated word.** A PDF line that ends mid-word is extracted as `exam-` + newline + `ples`, and `normalize` has always joined that pair back into `examples`, which is why quoting the page as you read it worked. Copying the same passage out of Acrobat, Word or a browser produces a different string: the reader keeps the hyphen glyph and puts a space where the line break was, so `exam- ples` arrives with one space in the middle of each broken word. Nothing joined that shape, so a correct quote from a rendered page was run against `quote-missing` - measured over 20 real papers, 120 quotes and four reader readings, this shape accounted for 11 of the 12 misses. The new `pasted` tier folds line breaks to `- ` and compares that reading against the quote; it counts as found, and, like the `hyphen` tier, it only moves the line-break spelling, so `re-cover` on a page still does not satisfy a quote reading `recover`. After the fix the same corpus misses 8 of 160, and all eight are image-only PDFs with no text layer - a different defect.
## [0.19.38] — 2026-11-02
### Fixed

- **A number that is on the page, in another sentence, was reported as a number the page does not contain.** The `numbers` tier finds a quote by matching the text with every number blanked out, so it already knows which of the page's numbers sit where the quote's numbers sit — and it threw that away. The verifier then asked a weaker question, "does 9,800 appear anywhere on page 1?", and for a quote that borrowed a number from the next sentence the answer is yes, so the run fell back to the summary and printed `the words match page 1 but the numbers do not; the quote records 9,800` — about a number printed four lines further down the same page. An author who turned the page, saw 9,800 and stopped trusting the tool would have been right to. `Match.page_numbers` now records the numbers the page actually prints under the quote's blank positions, and a quote whose numbers are the page's own but in the wrong places is reported under a new code, `number-not-in-passage`, at `high`: `the quote says 9,800 where page 1 prints 40,688; that number is on the page, but not in this passage`. `number-absent-in-quote` keeps its meaning, which is now the only thing it ever truthfully said: the page has no such number at all.
## [0.19.37] — 2026-11-01
### Fixed

- **A claim with two wrong numbers reported one of them.** The same shape as the four bibliography sites fixed in 0.19.34-0.19.36, in the verifier this time: `_number_checks` produced one finding per absent number and every one of them carried the claim's line, so the duplicate pass kept the first. Measured before this: a claim whose quote names two numbers the page does not contain gave `raw: 2, dedup: 1`, and the surviving line named only the first. All absent numbers are now one finding that names each of them.
- **The vaguer of two sentences about one claim was the one that survived.** The `numbers` tier appended a summary ("the words match page 1 but the numbers do not; the quote records ...") before the specific per-number findings, so the duplicate pass kept the summary and the author was never told which number was wrong. The specific findings now come first and the summary is a fallback for the case where there is nothing specific to say.
## [0.19.36] — 2026-11-01
### Fixed

- **An entry missing four required fields reported one of them.** The fourth
  site with the shape fixed three times already: `field_findings` produced one
  finding per missing field, every one of them carrying the entry's opening
  line, so the duplicate pass kept `author` and hid `title`, `journal` and
  `year`. Measured before this: two entries missing four fields each gave
  `raw: 8, dedup: 2`. The author filled in one, ran again, and met the next
  one - four runs to learn four fields. Missing fields are now one finding per
  entry naming all of them. Present-but-empty fields join that same message as
  a second clause rather than a second finding: they share the entry's code
  and line, so a separate finding was dropped by the same duplicate pass that
  hid the others.
## [0.19.35] — 2026-11-01
### Fixed

- **The third reporting site with the same shape: `bib-field-malformed`.** The
  previous commit left this one alone and said it was unreachable. It is not:
  an entry with a bad field, a readable field, and another bad field produces
  two fragments, and they share the entry's line, so the duplicate pass kept
  the first and hid the second. Two fragments are now one finding naming both,
  and the two branches that append a fragment (nothing to resume at, and
  resumed at the next field) land in the same list rather than reporting
  separately. A filter that could never reject anything was removed rather
  than left in as reassurance.

- **The same aggregation bug, one code over: `bib-macro-unknown`.** The previous
  entry fixed this shape for `bib-field-duplicate` and stopped there, so a
  field using two undefined macros still reported only the first, and two
  fields each using one reported only the first field - both because findings
  for one entry share its line and the duplicate pass keeps one per line. Now
  one finding per entry names every field and every macro, with counts that
  deduplicate repeated names (`jalpha # jalpha` is one undefined macro, not
  two). Nothing that used to be reported stopped being reported.
## [0.19.34] — 2026-11-01
### Fixed

- **One entry with three doubled fields reported one of them.** `parse_bib`
  reports every finding for an entry at the line the entry opens on, and the
  duplicate pass keys on `(code, claim, path, line)`. Three findings about
  `title`, `year` and `author` in the same entry therefore collapsed to the
  first: an author fixed `title`, re-ran, and met `year` for the first time -
  a report that has to be run three times to be read once. `bib-field-duplicate`
  now reports the set, the way `bib-key-unused` already did, naming every
  doubled field in one finding per entry. Nothing that used to be reported
  stopped being reported; what changed is that it all arrives at once.
## [0.19.33] — 2026-11-01
### Fixed

- **The deduplication key was missing the line, so two mistakes reported as
  one.** Moving the pass into `_render` in 0.19.32 made it apply to `scan` as
  well, and `scan` is where findings for blocks the parser could not turn into
  claims are born. Two claim blocks that both forgot `id=` share the empty
  claim id, so a key of `(code, claim_id, path)` called them the same finding:
  a manuscript with two of them was reported as having one, and fixing line 1
  made line 8 vanish from the report while staying in the file. The key is now
  `(code, claim_id, path, line)`. A genuine duplicate - the numbers tier and
  the per-number check naming the same number on the same claim - still
  collapses, because both carry the line of the claim they are about.
## [0.19.32] — 2026-11-01
### Fixed

- **The deduplication moved to the writer, where every verb reaches it.** 0.19.31
  gave `check` and `check --use-recorded` a shared pass and left `verify` printing
  the verifier's duplicates, because the fix was applied one call site at a time
  and there were three. `verify` is the verb a developer runs locally, so the same
  project reported two `number-absent-in-quote` lines for one claim there and one
  through `check`. The pass now lives in `_render`, which all three verbs call,
  and the new test enumerates the verbs instead of the branches - a test naming
  two of three callers would have stayed green while the third stayed broken.
## [0.19.31] — 2026-11-01
### Fixed

- **`check --use-recorded` reported one finding twice, and `check` did not.**
  The fresh path deduplicated its findings before printing them; the recorded
  path - the one `action.yml` runs on every pull request - never applied that
  pass, so the same tree produced two lines for one conclusion in CI and one
  line locally, and nobody sees those two outputs side by side. The duplicate
  was real: a quote whose words match a page but whose numbers do not is
  reported by the tier that matched the words and again by the check that walks
  the numbers, which is two sentences about the same number. The deduplication
  is now one function both paths call, and a new test compares the two paths to
  *each other* rather than to a remembered count - the assertion that would
  have caught this without already knowing which code duplicated.
## [0.19.30] — 2026-11-01
### Fixed

- **The `hyphen` tier shipped in 0.19.29 certified words the page never
  printed.** It removed hyphens from the *quote* and searched a page whose
  hyphens `normalize` had already removed, so every hyphen was gone from both
  sides and `re-cover` matched a page reading `recover`, `re-sign` matched
  `resign`, `re-form` matched `reform`, `co-op` matched `coop`. Those are real
  pairs of real words, and the tier was certifying claims the source does not
  support - the failure this project treats as the worst it can produce. The
  tier now reads the page's line-break hyphen the other way: `fold_keeping_hyphen`
  keeps it, the quote keeps whatever the author wrote, and the two are compared
  as they stand. Neither side is ever stripped, so the tier can only compare
  like with like and cannot manufacture a word. The original defect is still
  fixed - a quote reading `high-dimensional` against a page that broke
  `high-\ndimensional` at the line end is found - and all six pairs above are
  now refused.
## [0.19.29] — 2026-11-01
### Fixed

- **A compound word broken at a line end made a correct quote unfindable.**
  A page that sets `high-dimensional` with the break between the two halves
  extracts as `high-\ndimensional`. Normalisation reads that hyphen as
  typeset hyphenation and joins it, giving `highdimensional` — right for
  `pro-\cessing`, wrong for `high-dimensional`, and the extracted bytes are
  identical in both cases. An author quoting the page as it is printed writes
  `high-dimensional`, which matched no tier: a sentence that is on the page was
  reported `quote-missing` at high severity. On this project's own 20-page
  sample of real linguistics PDFs the shape occurs 312 times. A new `hyphen`
  tier compares the quote in both spellings against the page as the extractor
  settled it; it counts as found, and it is one-directional — the page is never
  stripped of hard hyphens, so a page reading `re-cover the sofa` still cannot
  satisfy a quote reading `recover the sofa`.
## [0.19.28] — 2026-11-01
### Fixed

- **A quote that stopped in the middle of a number was certified as found.**
  Against a page reading `The value is 40.688 in the table.`, a claim quoting
  `The value is 40.` came back `exact`, `similarity 1.0`, verified — the number
  in the claim is a truncation of the one on the page, and the tool called it
  proven. Five shapes did this: ending just before the decimal separator
  (`40.`), ending without it (`40`), ending on a thousands comma (`40,`),
  cutting a version number (`We used Python 3.` against `3.10.2`), and cutting
  a bare integer (`The value is 406` against `40688`). The word-boundary rule
  could not see any of them, because the character a number is cut at is the
  separator itself, and a separator is not a word character. Every tier that
  may certify a quote now refuses a match whose span lands strictly inside a
  number (`_cuts_a_number`); a match that ends exactly where the number ends,
  or stops before it begins, is untouched. A miss sends the author to look at
  the page; a false pass does not.
## [0.19.27] — 2026-11-01
### Fixed

- **The same number written the European way was reported as a different
  number.** `40.688` on the page and `40,688` in the quote are one number, and
  `40 688` is a third spelling of it. The tool read the dots as decimal points
  and the commas as thousands separators, so two of the three spellings never
  met: `check` exited 1 with `[high] number-absent-in-quote`, telling an author
  that the number they had just copied off the page was not on the page. The
  reading of a number is now one function used by both sides. `,` and `.` are
  grouping marks when they sit between exactly three digits and the number does
  not start `0` (`1.234.567`, `1,234,567`, `1.000,5`), and a decimal point
  otherwise (`48.4`, `0.688`, `1.0005`); the pattern that finds numbers reads
  `1.234.567` as one number instead of `1.234` and `567`. The verifier gained a
  fifth matching tier, `canonical`, tried after the literal comparisons and
  before the one that reports mismatched numbers: it compares the two texts
  with every number rewritten in one spelling, so a quote that differs from the
  page only in its thousands separators is now `quote-found` rather than
  `number-absent-in-quote`. Everything else stays where it was: `41,000` against
  `40,688` is still `number-absent-in-quote`, a number the page spells with a
  bare space is still not silently equal to one the quote groups, and the
  search that straddles a page break is unchanged.
## [0.19.26] — 2026-11-01
### Fixed

- **A LaTeX paper that shows its citation syntax was read as making those
  citations.**
  `\verb|\citep{a1}|` is how a paper *illustrates* what a cite command looks
  like, and TeX prints it literally; the tool turned it into `[@a1]`, a citation
  the author never wrote. `\verb*`, `\lstinline` (with or without options) and
  `\mintinline{tex}` behaved the same way. Two larger failures had the same
  cause. `50\verb|%| of it \citep{real2020}` lost everything after the `%`,
  because the `%` was read as the start of a comment - including the real
  citation. And `%` inside a `verbatim`-family environment ate the
  `\end{verbatim}` itself, so `to_text` returned an empty document and every
  citation after that point disappeared. `included_files` had the same gap: a
  `\verb|\input{sec/ghost}|` was reported as a file the tool could not read.
  Verbatim bodies are now masked before comments are stripped and hidden from
  the citation pattern and the converter, then restored as the literal
  characters TeX prints, so a `%` in `50\verb|%|` still reaches the output as a
  percent sign. The `verbatim` environment's own docstring had described this
  as a known limitation that "costs nothing unless the swallowed line is the
  `\end{verbatim}` itself" - which is exactly the case that happened.
## [0.19.25] — 2026-10-31
### Fixed

- **The `no-claim-blocks` message quoted a line that satisfied the rule it
  had just described.**
  An indented fence is a Markdown code sample and not a claim block, so the
  near-miss detector found it and the generic branch explained that claim
  fences are three backticks followed by the word `claim` - then printed the
  offending line, which is exactly that. The reader is told their block is
  wrong in a sentence their block satisfies. It now names the indent, says
  that an indented fence is a code sample in Markdown, and says where to put
  it instead. A block at the left margin still gets the generic sentence,
  because there it is true.
## [0.19.24] — 2026-10-31
### Fixed

- **The pre-commit hooks could not run.**
  `.pre-commit-hooks.yaml` named `entry: citevouch check` and said
  `pass_filenames: false`, and pre-commit does exactly what that says: it
  runs the command with no argument. `check` takes the manuscript as a
  positional one, so every commit was refused with
  `the following arguments are required: manuscript` and exit 2, without a
  single claim being read - a gate that fails for a reason that has nothing
  to do with the manuscript. The hooks now name `args: [manuscript.md]`,
  which is the file the check is about, and still pass no filenames: `files:`
  matches every Markdown file in the repository, README included, and
  `check` takes exactly one. The suite did not catch this because its helper
  appended `manuscript.md` itself - it ran the command it wished the hook
  ran. That helper now composes the command out of `entry`, `args` and
  `pass_filenames`, so a hook that cannot run is a hook whose tests fail.
## [0.19.23] — 2026-10-31
### Fixed

- **A claim id holding a backtick broke the `report` table.**
  The id column wrapped the id in backticks *after* escaping it, so an id
  containing one closed the code span early: the cell rendered as
  `<code>c</code>1` and the row came out one cell short of its header. A
  code span closes on the first run of backticks as long as its opening
  run, so the delimiter has to be chosen by looking at the content. The
  result is still escaped as a cell, because pipes and newlines break the
  table however the span is delimited. The rule is tested against the
  string rather than through a Markdown renderer, since no renderer is a
  dependency of this package.
## [0.19.22] — 2026-10-31
### Fixed

- **The advice from `no-claim-blocks` did not carry `--root`.**
  `check m.md --root paper` reads `paper/m.md` and printed
  `citevouch draft m.md -o claims.md`; pasted back, that resolved `m.md`
  against the working directory and answered `manuscript m.md does not
  exist`, exit 2 - with the correct file one directory away. A path only
  means what it meant alongside the root it was resolved against, so the
  advice now repeats `--root` whenever the caller named one. The default
  is still printed as nothing, because `--root .` in advice is noise; that
  sentence is pinned by tests and by the README.
## [0.19.21] — 2026-10-31
### Fixed

- **The command `no-claim-blocks` printed could not be run.** Two faults in one
  sentence. It named the manuscript by *basename* - correct for the finding's
  `path`, wrong for something a reader pastes into a shell - so checking
  `paper/m.md` from the project root printed `citevouch draft m.md`, which
  answers `manuscript m.md does not exist` and exit 2. And it always suggested
  `-o claims.md`, so a `claims.md` that still had no blocks was told to run
  `draft claims.md -o claims.md`, which `draft` refuses by design because the
  output would land on the manuscript it was reading. The advice now carries
  the path the reader typed and picks an output name that differs from it; the
  finding's own `path` stays the basename, so the same project still reads the
  same from any directory.
## [0.19.20] — 2026-10-31
### Fixed

- **Two `sources` manifests on disk was a ranking nobody stated.** A project that
  kept a `sources.json` beside its live `sources.toml` was resolved against
  whichever name came first in `MANIFEST_NAMES`, and the other file was
  invisible in every message - including the one telling the author to add an
  entry they had already added to the file that lost. `read_manifest` now
  refuses when both exist: it names both files and asks the author to delete or
  merge, because which manifest is authoritative is a fact the checkout knows
  and the tool does not. One manifest alone is still read exactly as before.
- **A project keeping its keys in `sources.json` was told to edit
  `sources.toml`.** The per-claim sentence hard-coded `sources.toml` in both
  halves - "no entry in sources.toml" and "add it to sources.toml" - so the
  reader was sent to a file that is not in their checkout, and the likeliest
  repair (create it) is what produces the two-manifest refusal above.
  `SourceTable` now carries `manifest_name`, and the sentence uses it; a
  project with no manifest at all still hears about `sources.toml`, because
  that is the file the README teaches you to make.
## [0.19.19] — 2026-10-31
### Fixed

- **A source key bound twice resolved to whichever binding came last, quietly.**
  A `--source` flag and a `sources.toml` entry that named the same key pointed the
  claim at the manifest's file, so a caller who passed the flag to stop using one
  stale entry got no error, no effect, and a finding saying the quote was not in
  the file they had just tried to replace. Two `--source` flags whose files share a
  stem behaved the same way, resolving to the second one. `read_source_table` now
  refuses both with a usage error naming the key and the two paths, and stays
  silent when they resolve to the same file.
## [0.19.18] — 2026-10-31
### Fixed

- An attribute left empty took the next attribute as its value.  `claim id=c1 source= page=1` read as `source="page=1"`, so a block with a half-filled `source=` was bound to a key nobody wrote and the report complained about `sources.toml` for a typo in the block.  The attribute reader now splits the two spellings: with no space after `=` the token is the value outright, so `source=a=b` still says `a=b`; with a space, a following `something=` is the next attribute, so `source= page=1` is an empty source and earns `claim-uncheckable`.  Three mutations are red, and each one only fails the tests about its own half.
## [0.19.17] — 2026-10-31
### Fixed

- **`draft` names the cause instead of reciting all three candidates.** A key
  whose `sources.toml` line was present but pointed at a moved file was
  reported as `no local file: not in sources.toml, no 'file' field in the
  bibliography, and no file named after the key`. That sentence claims three
  searches came up empty, and the first one is about a line the author is
  looking at. `draft` now asks the same `sources.explain_unresolved` that
  `scan` and `verify` use, so all three readers of the manifest say the same
  thing about the same project. A key nobody named keeps the old sentence,
  because there the three-way summary is accurate.
## [0.19.16] — 2026-10-31
### Fixed

- **`scan` and `verify` now describe a broken manifest the same way.** The
  release above taught `scan` to name the entry it could not use; `verify` was
  still reporting `source 'p' cannot be found any more` for the same project
  and the same claim. That sentence is true about the file and silent about the
  entry the author has to edit, so the reader who runs `verify` - which is the
  half a reader runs - got the older, weaker message. Both now build it from
  `sources.explain_unresolved`, which is one function for one fact. A key
  nobody named keeps the old sentence, because there is nothing better to say.
## [0.19.15] — 2026-10-31
### Fixed

- **A manifest entry whose file is not usable is no longer called a missing
  entry.** `sources.toml` naming `p = "gone.txt"` made every claim that used
  `p` report `claim c1 names source='p' but no entry in sources.toml ... add it
  to sources.toml` - a sentence about the one thing the author had got right,
  which sent them back to a file that already had their line in it. The cause
  was `discover_sources` throwing the entry away (`if path.is_file():` with no
  `else`) before the message was written, so "no manifest", "no such key",
  "key names a file that is not there" and "manifest will not parse" all
  arrived as the same empty mapping. Those last two now travel with the
  sentence that explains them (`read_source_table` / `SourceTable`), and the
  reader is told what is actually wrong: `sources.toml maps 'p' to
  'gone.txt', but 'gone.txt' does not exist`, `'.' is a directory, not a
  file`, or `the manifest could not be read: sources.toml could not be read
  as TOML (...)`. Two tests in `tests/test_critic_round3.py` had written down
  opposite conclusions about the same judgement - a directory passed to
  `--source` is refused, a directory named in the manifest is ignored - and
  the ignored half is what hid this: ignoring was never visible, so nobody
  could see it was happening. The manifest half now keeps the key as
  unusable rather than dropping it.
## [0.19.14] — 2026-10-30
### Fixed

- **`doctor` reports a machine problem under its own code, not a source
  code.** Every failing check - an interpreter older than the package supports,
  no PDF library, a cache directory nobody can write to, a project missing the
  files it says it has - was emitted as `source-unreadable`, on the theory that
  one vocabulary per problem beats two. But SARIF is what a reader sees in the
  code-scanning tab, and the rule line above each result comes from the code,
  not the message, so a read-only cache directory was displayed under "A source
  file could not be read." The message was always right; the word above it was
  borrowed from a neighbouring problem. There is now a `check-unavailable` code
  (`high`), documented in both READMEs and in the SARIF rule table. The same
  commit corrects the docstring on `doctor.findings()`, which claimed to exist
  for `--format json` - that branch carries every check, passing or not, and
  never calls it.
## [0.19.13] — 2026-10-30
### Fixed

- **`draft` names the files it could not read, instead of reporting a clean
  zero.** A paper that keeps its chapters in `\input{sec/intro}` files
  - which is the shape of every Overleaf project and most real papers -
  holds its citations in the parts, and `draft` reads one file. Run on such a
  paper it proposed `0 claim block(s)` and exited 0, which reads as "this
  manuscript has no citations" rather than "I never opened the half that
  does". The proposals file now says which files the document pulls in and
  that any citation in them is missing from the blocks below.
  The includes are still not followed: that is a design change, and it is
  not made here.
## [0.19.12] — 2026-10-30
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

[Unreleased]: https://github.com/lyear12/citevouch/compare/v0.22.60...HEAD
[0.22.60]: https://github.com/lyear12/citevouch/releases/tag/v0.22.60
[0.22.59]: https://github.com/lyear12/citevouch/releases/tag/v0.22.59
[0.22.58]: https://github.com/lyear12/citevouch/releases/tag/v0.22.58
[0.22.57]: https://github.com/lyear12/citevouch/releases/tag/v0.22.57
[0.22.56]: https://github.com/lyear12/citevouch/releases/tag/v0.22.56
[0.22.55]: https://github.com/lyear12/citevouch/releases/tag/v0.22.55
[0.22.54]: https://github.com/lyear12/citevouch/releases/tag/v0.22.54
[0.22.53]: https://github.com/lyear12/citevouch/releases/tag/v0.22.53
[0.22.52]: https://github.com/lyear12/citevouch/releases/tag/v0.22.52
[0.22.51]: https://github.com/lyear12/citevouch/releases/tag/v0.22.51
[0.22.50]: https://github.com/lyear12/citevouch/releases/tag/v0.22.50
[0.22.49]: https://github.com/lyear12/citevouch/releases/tag/v0.22.49
[0.22.48]: https://github.com/lyear12/citevouch/releases/tag/v0.22.48
[0.22.47]: https://github.com/lyear12/citevouch/releases/tag/v0.22.47
[0.22.46]: https://github.com/lyear12/citevouch/releases/tag/v0.22.46
[0.22.45]: https://github.com/lyear12/citevouch/releases/tag/v0.22.45
[0.22.44]: https://github.com/lyear12/citevouch/releases/tag/v0.22.44
[0.22.43]: https://github.com/lyear12/citevouch/releases/tag/v0.22.43
[0.22.42]: https://github.com/lyear12/citevouch/releases/tag/v0.22.42
[0.22.41]: https://github.com/lyear12/citevouch/releases/tag/v0.22.41
[0.22.40]: https://github.com/lyear12/citevouch/releases/tag/v0.22.40
[0.22.39]: https://github.com/lyear12/citevouch/releases/tag/v0.22.39
[0.22.38]: https://github.com/lyear12/citevouch/releases/tag/v0.22.38
[0.22.37]: https://github.com/lyear12/citevouch/releases/tag/v0.22.37
[0.22.36]: https://github.com/lyear12/citevouch/releases/tag/v0.22.36
[0.22.35]: https://github.com/lyear12/citevouch/releases/tag/v0.22.35
[0.22.34]: https://github.com/lyear12/citevouch/releases/tag/v0.22.34
[0.22.33]: https://github.com/lyear12/citevouch/releases/tag/v0.22.33
[0.22.33]: https://github.com/lyear12/citevouch/releases/tag/v0.22.33
[0.22.32]: https://github.com/lyear12/citevouch/releases/tag/v0.22.32
[0.22.31]: https://github.com/lyear12/citevouch/releases/tag/v0.22.31
[0.22.30]: https://github.com/lyear12/citevouch/releases/tag/v0.22.30
[0.22.29]: https://github.com/lyear12/citevouch/releases/tag/v0.22.29
[0.22.28]: https://github.com/lyear12/citevouch/releases/tag/v0.22.28
[0.22.27]: https://github.com/lyear12/citevouch/releases/tag/v0.22.27
[0.22.26]: https://github.com/lyear12/citevouch/releases/tag/v0.22.26
[0.22.25]: https://github.com/lyear12/citevouch/releases/tag/v0.22.25
[0.22.24]: https://github.com/lyear12/citevouch/releases/tag/v0.22.24
[0.22.23]: https://github.com/lyear12/citevouch/releases/tag/v0.22.23
[0.22.22]: https://github.com/lyear12/citevouch/releases/tag/v0.22.22
[0.22.21]: https://github.com/lyear12/citevouch/releases/tag/v0.22.21
[0.22.20]: https://github.com/lyear12/citevouch/releases/tag/v0.22.20
[0.22.19]: https://github.com/lyear12/citevouch/releases/tag/v0.22.19
[0.22.18]: https://github.com/lyear12/citevouch/releases/tag/v0.22.18
[0.22.17]: https://github.com/lyear12/citevouch/releases/tag/v0.22.17
[0.22.16]: https://github.com/lyear12/citevouch/releases/tag/v0.22.16
[0.22.15]: https://github.com/lyear12/citevouch/releases/tag/v0.22.15
[0.22.14]: https://github.com/lyear12/citevouch/releases/tag/v0.22.14
[0.22.12]: https://github.com/lyear12/citevouch/releases/tag/v0.22.12
[0.22.11]: https://github.com/lyear12/citevouch/releases/tag/v0.22.11
[0.22.10]: https://github.com/lyear12/citevouch/releases/tag/v0.22.10
[0.22.9]: https://github.com/lyear12/citevouch/releases/tag/v0.22.9
[0.22.8]: https://github.com/lyear12/citevouch/releases/tag/v0.22.8
[0.22.7]: https://github.com/lyear12/citevouch/releases/tag/v0.22.7
[0.22.6]: https://github.com/lyear12/citevouch/releases/tag/v0.22.6
[0.22.5]: https://github.com/lyear12/citevouch/releases/tag/v0.22.5
[0.22.4]: https://github.com/lyear12/citevouch/releases/tag/v0.22.4
[0.22.3]: https://github.com/lyear12/citevouch/releases/tag/v0.22.3
[0.22.2]: https://github.com/lyear12/citevouch/releases/tag/v0.22.2
[0.22.2]: https://github.com/lyear12/citevouch/releases/tag/v0.22.2
[0.22.1]: https://github.com/lyear12/citevouch/releases/tag/v0.22.1
[0.22.0]: https://github.com/lyear12/citevouch/releases/tag/v0.22.0
[0.21.5]: https://github.com/lyear12/citevouch/releases/tag/v0.21.5
[0.21.4]: https://github.com/lyear12/citevouch/releases/tag/v0.21.4
[0.21.3]: https://github.com/lyear12/citevouch/releases/tag/v0.21.3
[0.21.2]: https://github.com/lyear12/citevouch/releases/tag/v0.21.2
[0.21.1]: https://github.com/lyear12/citevouch/releases/tag/v0.21.1
[0.21.0]: https://github.com/lyear12/citevouch/releases/tag/v0.21.0
[0.20.2]: https://github.com/lyear12/citevouch/releases/tag/v0.20.2
[0.20.1]: https://github.com/lyear12/citevouch/releases/tag/v0.20.1
[0.20.0]: https://github.com/lyear12/citevouch/releases/tag/v0.20.0
[0.19.88]: https://github.com/lyear12/citevouch/releases/tag/v0.19.88
[0.19.87]: https://github.com/lyear12/citevouch/releases/tag/v0.19.87
[0.19.86]: https://github.com/lyear12/citevouch/releases/tag/v0.19.86
[0.19.85]: https://github.com/lyear12/citevouch/releases/tag/v0.19.85
[0.19.84]: https://github.com/lyear12/citevouch/releases/tag/v0.19.84
[0.19.83]: https://github.com/lyear12/citevouch/releases/tag/v0.19.83
[0.19.82]: https://github.com/lyear12/citevouch/releases/tag/v0.19.82
[0.19.81]: https://github.com/lyear12/citevouch/releases/tag/v0.19.81
[0.19.80]: https://github.com/lyear12/citevouch/releases/tag/v0.19.80
[0.19.79]: https://github.com/lyear12/citevouch/releases/tag/v0.19.79
[0.19.78]: https://github.com/lyear12/citevouch/releases/tag/v0.19.78
[0.19.77]: https://github.com/lyear12/citevouch/releases/tag/v0.19.77
[0.19.76]: https://github.com/lyear12/citevouch/releases/tag/v0.19.76
[0.19.75]: https://github.com/lyear12/citevouch/releases/tag/v0.19.75
[0.19.74]: https://github.com/lyear12/citevouch/releases/tag/v0.19.74
[0.19.73]: https://github.com/lyear12/citevouch/releases/tag/v0.19.73
[0.19.72]: https://github.com/lyear12/citevouch/releases/tag/v0.19.72
[0.19.71]: https://github.com/lyear12/citevouch/releases/tag/v0.19.71
[0.19.70]: https://github.com/lyear12/citevouch/releases/tag/v0.19.70
[0.19.69]: https://github.com/lyear12/citevouch/releases/tag/v0.19.69
[0.19.68]: https://github.com/lyear12/citevouch/releases/tag/v0.19.68
[0.19.68]: https://github.com/lyear12/citevouch/releases/tag/v0.19.68
[0.19.67]: https://github.com/lyear12/citevouch/releases/tag/v0.19.67
[0.19.66]: https://github.com/lyear12/citevouch/releases/tag/v0.19.66
[0.19.65]: https://github.com/lyear12/citevouch/releases/tag/v0.19.65
[0.19.64]: https://github.com/lyear12/citevouch/releases/tag/v0.19.64
[0.19.63]: https://github.com/lyear12/citevouch/releases/tag/v0.19.63
[0.19.62]: https://github.com/lyear12/citevouch/releases/tag/v0.19.62
[0.19.61]: https://github.com/lyear12/citevouch/releases/tag/v0.19.61
[0.19.60]: https://github.com/lyear12/citevouch/releases/tag/v0.19.60
[0.19.59]: https://github.com/lyear12/citevouch/releases/tag/v0.19.59
[0.19.58]: https://github.com/lyear12/citevouch/releases/tag/v0.19.58
[0.19.57]: https://github.com/lyear12/citevouch/releases/tag/v0.19.57
[0.19.56]: https://github.com/lyear12/citevouch/releases/tag/v0.19.56
[0.19.55]: https://github.com/lyear12/citevouch/releases/tag/v0.19.55
[0.19.54]: https://github.com/lyear12/citevouch/releases/tag/v0.19.54
[0.19.53]: https://github.com/lyear12/citevouch/releases/tag/v0.19.53
[0.19.52]: https://github.com/lyear12/citevouch/releases/tag/v0.19.52
[0.19.51]: https://github.com/lyear12/citevouch/releases/tag/v0.19.51
[0.19.50]: https://github.com/lyear12/citevouch/releases/tag/v0.19.50
[0.19.49]: https://github.com/lyear12/citevouch/releases/tag/v0.19.49
[0.19.48]: https://github.com/lyear12/citevouch/releases/tag/v0.19.48
[0.19.47]: https://github.com/lyear12/citevouch/releases/tag/v0.19.47
[0.19.46]: https://github.com/lyear12/citevouch/releases/tag/v0.19.46
[0.19.45]: https://github.com/lyear12/citevouch/releases/tag/v0.19.45
[0.19.44]: https://github.com/lyear12/citevouch/releases/tag/v0.19.44
[0.19.43]: https://github.com/lyear12/citevouch/releases/tag/v0.19.43
[0.19.42]: https://github.com/lyear12/citevouch/releases/tag/v0.19.42
[0.19.41]: https://github.com/lyear12/citevouch/releases/tag/v0.19.41
[0.19.40]: https://github.com/lyear12/citevouch/releases/tag/v0.19.40
[0.19.39]: https://github.com/lyear12/citevouch/releases/tag/v0.19.39
[0.19.38]: https://github.com/lyear12/citevouch/releases/tag/v0.19.38
[0.19.37]: https://github.com/lyear12/citevouch/releases/tag/v0.19.37
[0.19.36]: https://github.com/lyear12/citevouch/releases/tag/v0.19.36
[0.19.35]: https://github.com/lyear12/citevouch/releases/tag/v0.19.35
[0.19.34]: https://github.com/lyear12/citevouch/releases/tag/v0.19.34
[0.19.33]: https://github.com/lyear12/citevouch/releases/tag/v0.19.33
[0.19.32]: https://github.com/lyear12/citevouch/releases/tag/v0.19.32
[0.19.31]: https://github.com/lyear12/citevouch/releases/tag/v0.19.31
[0.19.30]: https://github.com/lyear12/citevouch/releases/tag/v0.19.30
[0.19.29]: https://github.com/lyear12/citevouch/releases/tag/v0.19.29
[0.19.28]: https://github.com/lyear12/citevouch/releases/tag/v0.19.28
[0.19.27]: https://github.com/lyear12/citevouch/releases/tag/v0.19.27
[0.19.26]: https://github.com/lyear12/citevouch/releases/tag/v0.19.26
[0.19.25]: https://github.com/lyear12/citevouch/releases/tag/v0.19.25
[0.19.24]: https://github.com/lyear12/citevouch/releases/tag/v0.19.24
[0.19.23]: https://github.com/lyear12/citevouch/releases/tag/v0.19.23
[0.19.22]: https://github.com/lyear12/citevouch/releases/tag/v0.19.22
[0.19.21]: https://github.com/lyear12/citevouch/releases/tag/v0.19.21
[0.19.20]: https://github.com/lyear12/citevouch/releases/tag/v0.19.20
[0.19.19]: https://github.com/lyear12/citevouch/releases/tag/v0.19.19
[0.19.18]: https://github.com/lyear12/citevouch/releases/tag/v0.19.18
[0.19.17]: https://github.com/lyear12/citevouch/releases/tag/v0.19.17
[0.19.16]: https://github.com/lyear12/citevouch/releases/tag/v0.19.16
[0.19.15]: https://github.com/lyear12/citevouch/releases/tag/v0.19.15
[0.19.14]: https://github.com/lyear12/citevouch/releases/tag/v0.19.14
[0.19.13]: https://github.com/lyear12/citevouch/releases/tag/v0.19.13
[0.19.12]: https://github.com/lyear12/citevouch/releases/tag/v0.19.12
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
