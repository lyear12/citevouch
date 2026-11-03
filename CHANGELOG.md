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

[Unreleased]: https://github.com/lyear12/citevouch/compare/v0.22.4...HEAD
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
