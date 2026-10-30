# citevouch

**English** · [简体中文](README.zh-CN.md)

**Bind every claim in your manuscript to the page of the PDF that proves it — and fail CI when that evidence drifts.**

`citevouch` is not another "does this DOI exist" checker. Plenty of those exist, and they answer a
different question. It answers the question you actually face the night before a deadline:

> This paragraph says 154,391 sentences. Is that number on page 6 of the PDF it cites, or did I
> copy it from an earlier draft of the paper — or from a different paper entirely?

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
that lives in a different paper, which is the failure the tool exists to catch.

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
| `page-out-of-range` | high | the cited page is not a page of the document (below 1 or past its end) |
| `ledger-stale` | high | the manuscript changed since the ledger was recorded |
| `bib-key-missing` | high | the claim cites a bibliography key that is not there |
| `bib-key-unused` | info | a bibliography entry no claim cites (reported as one aggregate line) |
| `bib-duplicate-key` | high | two entries share a key |
| `bib-unparsed-entry` | high | an entry never closes, so everything after it was not read |
| `bib-entry-header-unparsed` | medium | text between entries, or an `@` header that is not a usable entry |
| `bib-field-malformed` | medium | a field could not be read; later fields of the entry are still parsed |
| `bib-field-duplicate` | medium | one field given twice in an entry (names are case-insensitive); first kept |
| `bib-macro-unknown` | medium | a field uses a `@string` macro that is not defined yet |
| `bib-field-empty` | medium | a required field is empty or missing |
| `claim-without-evidence` | low | a 【原文】/【推测】-style marker with no claim block |
| `claim-block-unclosed` | high | a `` ```claim `` block never closes, so every claim after it was read as part of it |
| `claim-uncheckable` | high | a claim block cannot be looked up at all - no `source=`, no quote, no id, or an id used twice so the second block is dropped |
| `page-unreadable` | medium | a `page=` hint is not a number, so it is ignored and the quote is located by search |

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
pip install "git+https://github.com/lyear12/citevouch@v0.10.3"
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

```yaml
- uses: actions/setup-python@v5
  with: { python-version: "3.12" }
- run: pip install "git+https://github.com/lyear12/citevouch@v0.10.3"
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
