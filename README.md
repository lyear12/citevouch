# citevouch

**English** · [简体中文](README.zh-CN.md)

**Bind every claim in your manuscript to the page of the PDF that proves it — and fail CI when that evidence drifts.**

`citevouch` is not another "does this DOI exist" checker. Plenty of those exist, and they answer a
different question. It answers the question you actually face the night before a deadline:

> This paragraph says 154,391 sentences. Is that number on page 6 of the PDF it cites, or did I
> copy it from an earlier draft of the paper — or from a different paper entirely?

![verify output](docs/img/verify.png)

You write a claim block next to each sentence you want checked. The block names a local PDF, a page,
and the verbatim passage. `citevouch scan` records that evidence into a commit-able lockfile;
`citevouch verify` re-reads the PDFs and tells you which evidence still holds, which moved, and
which is gone.

```text
$ cd demo && citevouch verify manuscript.md
[info] quote-found at manuscript.md:9 (cxn-total): quote found on page 6
[info] quote-found at manuscript.md:18 (corpus-size): quote found on page 6
[info] quote-found at manuscript.md:26 (hapax-share): quote found on page 7
[info] quote-found at manuscript.md:34 (avg-degree): quote found on page 14
[high] quote-missing at manuscript.md:43 (fcg-editor): The FCG Editor is an innovative environment for
  engineering computational construction gr… — no passage in the source is close to this quote in
  2020_TayyarMadabushi-etal_CxGBERT.pdf

citevouch: 5 claims — 4 verified, 0 moved, 1 missing
worst severity: high
```

That is this repository's own `demo/`, run as-is — not a mock-up. The fifth claim cites a sentence
that lives in a different paper, which is the failure the tool exists to catch. And here is the page
it is talking about — the highlighted sentence is what `quote-found on page 6` means:

![the page the quote is on](docs/img/page.png)

The images are generated from the demo by `tools/make_figures.py`, and `tests/test_figures.py`
fails if the text in the first one stops matching what the demo prints.

## Why this is different

| | what it checks | catches | misses |
|---|---|---|---|
| DOI / metadata checkers | the reference resolves in Crossref / OpenAlex | hallucinated references, retractions, wrong year | a real paper quoted wrong |
| reference managers | formatting, duplicates | - | everything semantic |
| **citevouch** | **this sentence ← that page of that file** | wrong numbers, drifted paraphrases, PDF swapped for a newer version, a quote that only ever existed in your head | whether the paper itself is good |

The two are complementary. A hallucinated citation passes every local-PDF check because there is no
local PDF. A real citation with a mangled number passes every DOI check because the DOI is fine.
Run both.

## What "drift" means

A claim verified in January is not verified in March. `citevouch` distinguishes the ways evidence
rots:

| code | severity | meaning |
|---|---|---|
| `quote-found` | info | the passage is on the cited page |
| `quote-moved` | medium | the passage is in the document, on a different page (layout change) |
| `quote-fuzzy` | high | only an approximate match exists — never counted as verified |
| `quote-missing` | high | no passage close to this quote anywhere in the source |
| `number-absent-in-quote` | high | a number inside the quote is not on that page |
| `source-changed` | medium | the PDF is byte-different from the one the ledger recorded |
| `source-missing` | high | the PDF the claim names cannot be found |
| `source-unreadable` | high | the PDF exists but no text could be extracted |
| `source-no-text` | high | the PDF was read and held no text at all - it is a scan, and OCR is what it needs |
| `page-out-of-range` | high | the cited page is not a page of the document (below 1 or past its end) |
| `ledger-stale` | high | the manuscript changed since the ledger was recorded |
| `check-unavailable` | high | `doctor` found a check it cannot pass: no PDF library, an unsupported interpreter, a cache it cannot write |
| `bib-key-missing` | high | the claim cites a bibliography key that is not there |
| `bib-key-unused` | info | a bibliography entry no claim cites (reported as one aggregate line) |
| `bib-duplicate-key` | high | two entries share a key |
| `bib-unparsed-entry` | high | an entry never closes, so everything after it was not read |
| `bib-unreadable` | high | not one entry could be read, so no reference was checked against it |
| `bib-entry-header-unparsed` | medium | text between entries, or an `@` header that is not a usable entry |
| `bib-field-malformed` | medium | a field could not be read; later fields of the entry are still parsed |
| `bib-field-duplicate` | medium | one field given twice in an entry (names are case-insensitive); first kept |
| `bib-macro-unknown` | medium | a field uses a `@string` macro that is not defined yet |
| `bib-field-empty` | medium | a required field is empty or missing |
| `claim-without-evidence` | low | a 【原文】/【推测】-style marker with no claim block |
| `claim-block-unclosed` | high | a `` ```claim `` block never closes, so every claim after it was read as part of it |
| `claim-uncheckable` | high | a claim block cannot be looked up at all - no `source=`, no quote, no id, or an id used twice so the second block is dropped |
| `page-unreadable` | medium | a `page=` hint is not a number, so it is ignored and the quote is located by search |
| `no-claim-blocks` | high | the manuscript holds no claim blocks at all, so nothing in it was checked |

Exit code is `0` when nothing reaches `--fail-on` (default `high`), `1` when something does, `2` for
usage errors. That means a CI job needs no wrapper logic.

## Is this for you?

**Use it when**: you hold a pile of PDFs (or exported text) and a manuscript full of
"this sentence has a source, this number came from that paper" claims, and you want a machine to
re-check every one of them on every commit, before submission, before release — literature
reviews, system reviews, lecture notes, fact-checked long-form, AI-assisted drafts whose numbers
you have not personally re-verified.

**Skip it when**: your question is "does this paper exist, was it retracted" — that is what DOI
checkers like citegate do, and running both is the point. And if the references live only online
with no local file, there is nothing here to check against: the tool deliberately never goes to the
network; everything happens between files on your machine.

## Install

Not on PyPI yet — the release workflow publishes there once a trusted publisher is registered for
this repository, and reports whether it did. Until then, install from GitHub:

```bash
pip install "git+https://github.com/lyear12/citevouch@v0.19.23"
# or, from a clone:
pip install .
```

Requires Python 3.10+.

PDF text extraction uses [pypdf](https://pypi.org/project/pypdf/); if `pdftotext` (poppler) is on
`PATH` it is used as a second engine, and plain-text sources work with no dependency at all.

## Use it in 60 seconds

```bash
citevouch init-demo my-paper      # scaffold a project that already passes
cd my-paper
citevouch verify manuscript.md    # "1 claim — 1 verified"
```

`init-demo` writes the three files *and* records the ledger, so the project it hands you is already
in the state `verify` reads. When you replace the demo source with a real PDF, `citevouch scan`
records the new evidence, and `verify` is what you run after that — and in CI.

By hand, three files:

**`manuscript.md`** — the claim block goes right above the sentence it backs.

````markdown
```claim id=corpus-size source=vaneecke2026cxn ref=vaneecke2026learning page=6
quote: |
  Together, the combined corpus contains 154,391 utterances, annotated with a total of 440,528
  roleset instances.
claim: |
  训练语料合计 154,391 句 / 440,528 个角色集实例。
```
````

**`sources.toml`** — maps the name you use to a file.

```toml
[sources]
vaneecke2026cxn = "papers/2026_VanEecke-Beuls_CoNLL2026_large-scale-CxG.pdf"
```

**`refs.bib`** — optional. When present, `source`/`ref` keys are checked against it.

```bash
citevouch scan   manuscript.md --root . --bib refs.bib   # writes citevouch.lock.json
citevouch verify manuscript.md --root .                  # re-checks the PDFs
citevouch check  manuscript.md --root . --format markdown # PR comment
```

Commit `citevouch.lock.json`. It is the memory that makes drift detectable: without it, `verify`
can only say "found", never "moved".

The [demo/](demo/) directory is a complete, runnable real project: five claims taken from two
published papers, one of them deliberately backed by the wrong paper so the tool must refuse it —
that refusal is the repository's standing regression test, not a defect. Point CI at it and see
what a red evidence gate looks like.

### When it says every quote is missing

Run `citevouch doctor` before you believe it.

```text
$ citevouch doctor --root demo
[ok  ] python      3.12
[ok  ] pypdf       6.16.1 (reads PDFs in-process)
[ok  ] pdftotext   not on PATH (not needed; pypdf is installed)
[ok  ] cache       demo/.citevouch/cache is writable
[ok  ] manuscript  demo/manuscript.md (2154 bytes)
[ok  ] manifest    demo/sources.toml (148 bytes)

Everything this tool needs is on this machine. If quotes are still reported missing, the source files are the place to look.
```

(That is a machine with `pypdf` from pip and no poppler; with `pdftotext` installed the third line
prints its path instead, shortened in the middle. Windows prints backslashes.)

The failure that sends people away from this tool is not an error message. It is a run that
finishes and reports every quote missing, because the PDF could not be read at all — and nothing in
that output says so. `doctor` is the command that is allowed to be reassuring: it checks that an
extractor exists, that the cache is writable, that the interpreter is new enough, and that the files
the project names are actually there. It exits `1` when something is broken, and it is the one
place where `1` means "your machine", not "your manuscript".

### Start from a manuscript, not from an empty file

Writing the first twenty claim blocks by hand is where this tool loses people. `draft` reads your
manuscript, finds every citation, and writes a proposal file under `--root` (`-o` is resolved
against the root like every other path this tool takes, and it refuses to write over the
manuscript it is reading):

```bash
citevouch draft manuscript.md --root . -o claims.md
```

```text
citevouch: 1 claim block(s) proposed (0 verbatim), 2 citation(s) left as comments
```

Each proposal is a real sentence from the most relevant page of the file that citation resolves to,
with the page it came from, so `scan` and `verify` accept it immediately:

```markdown
<!-- confidence: medium - the best sentence on the most relevant page (4 shared terms); read it before trusting the claim -->
```claim id=vaneecke2026cxn source=vaneecke2026cxn page=5
quote: |
  When more links are later added to the grammar network as more training examples are processed,
  the same tell.01 construction can be reused in combination with other frame-evoking or argument
  structure constructions to process utterances such as “Ah, why should you come out if you were
  told not to?
claim: |
  Construction grammar treats a grammar as a network of constructions, and this network is learned
  from data rather than written by hand.
```
```

Three things it will not do, and says so in the file instead: it never edits your manuscript, never
proposes a sentence it did not read from the page, and never invents a citation. Keys with no local
file come back as comments explaining what to add; a citation whose best passage is already proposed
for an earlier one comes back as a comment too, rather than the same quote twice. `high` confidence
means your own sentence appears verbatim in the source — that case needs no judgement. `medium`
means a real sentence on the right page that you still have to read.

To bind keys the bibliography already knows about, pass `--bib refs.bib`. A Zotero `file` field is
used when the key is not in `sources.toml`, and the file prints the `[sources]` line to paste.

### If your manuscript is LaTeX

Pass the `.tex` file. It is converted before anything reads it, so the command is the same one:

```bash
citevouch draft paper.tex --bib refs.bib -o claims.md
```

`\citep{a, b}`, `\citet`, `\textcite` and the other citation commands become the same markers the
Markdown path uses, `%` comments and `thebibliography` are dropped, and a section title becomes its
own paragraph so it does not get glued onto the sentence below it. Notes that came from `[p.~3]`
are dropped, because the page number always comes from the PDF, never from your source.

This is a converter, not a TeX parser: a macro that generates text, an `\input`, or an environment
whose body is not prose will be read as prose or skipped. That costs a weaker proposal, never a
false pass — the quote in a `claim` block always comes from the PDF, so a mangled sentence cannot
make a citation look verified. `scan` and `verify` never see LaTeX; only this command does.

### Three claim dialects

Fenced blocks (above), HTML comments, and table rows. Pick whichever survives your editor.

```markdown
<!-- claim: c2 source=smith2026cxn page=4 -->
>> The corpus contains 154,391 utterances.

| id | source | page | quote | claim |
|----|--------|------|-------|-------|
| c3 | smith2026cxn | 7 | almost half (48.4%) occur only once | 48.4% 是 hapax |
```

If you keep a sample of the syntax inside your manuscript — a tutorial chapter, a README of your
own — fence it with **four** backticks (`` ```` ``), not three. A three-backtick sample that contains
a ```claim line is indistinguishable from a claim block that forgot its closing fence, and the tool
reports it rather than guessing (`claim-block-unclosed`, high). Four backticks say "this is a
sample" unambiguously.

### CI

The shortest form is the action. It installs the tag it is pinned to and runs the gate:

```yaml
- uses: lyear12/citevouch@v0.19.23
  with:
    manuscript: manuscript.md
```

It runs `check --use-recorded`, which reads the ledger out of the repository instead of re-deriving
it — so **commit `citevouch.lock.json` first** (see [Use it in 60 seconds](#use-it-in-60-seconds)).
On a repository that has never been scanned the job exits 2 with `no ledger at
citevouch.lock.json; run \`citevouch scan\` first`. That is a setup error, not a verdict about the
manuscript, which is why the action stops on it rather than reporting a green job for a check that
never ran.

It writes a SARIF file and exposes its path as the `sarif` output, so adding a code-scanning upload
is one more step:

```yaml
- uses: lyear12/citevouch@v0.19.23
  id: citevouch
  with:
    manuscript: manuscript.md
    fail-on: high
- uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: ${{ steps.citevouch.outputs.sarif }}
```

If you would rather not use an action, three lines do the same job:

```yaml
- uses: actions/setup-python@v5
  with: { python-version: "3.12" }
- run: pip install "git+https://github.com/lyear12/citevouch@v0.19.23"
- run: citevouch check manuscript.md --root . --use-recorded --format sarif > citevouch.sarif
```

Once PyPI publication is set up, the first line shortens to `pip install citevouch`; pinning the tag
is the safer form for a gate anyway, because a floating install can change the verdict under you.

`--use-recorded` verifies the committed ledger instead of re-deriving it, so the job fails only when
the PDFs or the manuscript moved underneath the evidence — which is exactly what you want a gate to
watch. Upload the SARIF to code scanning and findings appear inline on the PR.

## Design notes

- **The quote is the anchor, not the page number.** Page numbers are a hint. A PDF re-flowed by a
  different tool keeps its text and loses its pagination; matching on text survives that, matching on
  page numbers does not.
- **Fuzzy matches never count as verified.** A paraphrase is not a quote. Fuzzy matching exists to
  say "something is there, look at it", and it is reported as `quote-fuzzy` (high) precisely so it
  cannot be mistaken for a pass: the threshold that fails the run is the same one that fails a
  quote that is not there at all.
- **The manuscript hash is checked before anything else.** If the manuscript changed at all, every
  claim is `skipped` and one `ledger-stale` finding is emitted — better one honest failure than
  thirty confusing ones.
- **One finding per class, not per occurrence,** where the class is rare enough to hide in. Thirty-
  seven unused bibliography entries are one line; one missing quote is its own line.
- **No network.** Everything is local files. A verification run in an offline exam room behaves
  identically to one in CI.

## Status

Pre-1.0. Versioned as [docs/maintenance.md](docs/maintenance.md) spells it: patch releases carry
fixes, minor releases carry capability, and the ledger's `schema` field — still `1`, unchanged since
the first commit — is what gates reading an old ledger. A ledger written by one version verifies
under the next; when a release does change the shape, it bumps that field and says so here, and
`verify` refuses a schema it cannot read instead of guessing at it.

## License

MIT. See [LICENSE](LICENSE).
