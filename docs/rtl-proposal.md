# Two right-to-left pipelines, measured again, and three bounded answers

**Status: a proposal waiting for one Owner decision.**

**Nothing in this document changes how the tool behaves.** No extractor was added,
no matching path was altered, and `src/` was not touched.

## Why this exists

An author writing Arabic or Hebrew can receive a finding that says their quote is
not in a page where it is printed. That is the one failure this project treats as
worst, because a tool that accuses a correct quotation teaches its user to ignore
it. The earlier note in `docs/backlog.md` described two producers and two defects.
Both were rebuilt and re-measured on 2026-11-15; two of its conclusions no longer
hold, and one new fact does.

## What was measured, and how

| Item | Value |
| --- | --- |
| Page text | `נטען כי המשתתפים קיבלו 40,688 דוגמאות במילון.` (the same sentence as the earlier note) |
| Producer A | `pymupdf` 1.26.7 `insert_htmlbox` with HarfBuzz shaping - what a browser print-to-PDF does |
| Producer B | LibreOffice 26 headless, `--convert-to pdf` from an HTML file with `dir='rtl'` |
| Reader under test | `pypdf` 6.16.1 - the only reader this project has for `.pdf` |
| Command | `citevouch check m.md --root . --format json --no-cache`, one claim block, quote = the sentence |

## Result A - pymupdf: the letters are reversed in place

`pypdf` returns

```
ןעטנ  יכ  םיפתתשמה  ולביק 40,688 תואמגוד  ןולימב .
```

- **Five of six Hebrew words are exact character-for-character reverses**, in the
  original word order: `נטען`→`ןעטנ`, `כי`→`יכ`, `המשתתפים`→`םיפתתשמה`,
  `קיבלו`→`ולביק`, `דוגמאות`→`תואמגוד`.
- The sixth is the reverse **minus its full stop**, which has been moved to the end
  of the line as ` .`: `במילון.`→`ןולימב`.
- `40,688` is untouched, and the Latin line on the same page reads correctly, so
  the damage is specific to the bidi run.
- `pymupdf.get_text()` on the same bytes returns the correct logical order.

**What the shipped tool says.** A correct Hebrew quote gets
`[high] quote-missing`, `0 verified`, `1 missing`, **exit 1**. The words the author
quoted are on the page; every letter is in the wrong order, so nothing matches. A
quote copied from what `pypdf` returned is `quote-found` at `exact` - which proves
the matcher is fine and the input is not.

## Result B - LibreOffice: the words are right and the spaces are missing

`pypdf` returns

```
    נטעןכיהמשתתפיםקיבלו 40,688  דוגמאותבמילון .
```

No reversal. The correct letter forms in the correct order. But spaces between
Hebrew words are gone (`נטען כי` → `נטעןכי`, `דוגמאות במילון` → `דוגמאותבמילון`),
and the full stop is again detached at the end.

**What the shipped tool says.** A correct Hebrew quote gets
`[high] quote-word-boundaries-unclear`, `0 verified`, `1 skipped`, **exit 1** -
that is, the third answer CV-001 introduced for exactly this situation, not an
accusation. `textnorm.squash(page)` does equal `textnorm.squash(quote)`, so the
`pasted`/`squashed` tiers locate it, and the run says it cannot decide rather than
saying the words are absent.

### Where this diverges from the 2026-11-01 note

| The earlier note said | Measured 2026-11-15 |
| --- | --- |
| Producer A: "each Hebrew word as its own reversal, word order preserved" | True for five of six; the sixth loses its full stop, so a whole-sentence reversal is not the same string |
| Producer B: "drops the space between a Hebrew word and an adjacent number" | Not reproduced: the space before `40,688` survived (there are two spaces after it). What this build loses is the spaces between Hebrew words |
| "An author who quotes just the number gets `[high] number-absent-in-quote` and `quote-missing`" | Not reproduced on either file: quoting `40,688` alone is `quote-found`, `1 verified`, **exit 0** on both producers |
| "Producer B ... goes to the `squashed` tier ... so the quote is found" | Half right: squash-equal is the finding, but the run reports `quote-word-boundaries-unclear` and `skipped`, never `verified` - CV-001 changed this on 2026-11-14 |
| "What is still open is what the finding says when a page is RTL" | Still open, and now narrower: it is one producer and one severity, not two of each |

The earlier note was not wrong when it was written. Producer B's behaviour depends
on the LibreOffice build and on the exact markup; the number-only case was measured
before the whitespace-free tier stopped certifying quotes. Recording the divergence
is the point: a proposal built on a four-day-old measurement would ask the Owner to
decide about a defect that has since changed shape.

## Can an RTL page be recognised from the text the tool already has?

Yes, cheaply, and that is what makes a narrow answer possible. Counting letters in
Unicode right-to-left ranges:

| Text | Share of letters that are RTL |
| --- | --- |
| Producer A page | **0.50** |
| Producer B page | **0.50** |
| Hebrew sentence alone | 1.00 |
| Arabic sentence alone | 1.00 |
| `The study (נטען) reports 40,688 examples.` | 0.15 |
| `2020_TayyarMadabushi-etal_CxGBERT.pdf` (real paper) | **0.00** |
| `2026_VanEecke-Beuls_CoNLL2026_large-scale-CxG.pdf` (real paper) | **0.00** |
| Latin sentence | 0.00 |

A threshold of 0.30 separates everything measured here. **This is one page per
producer and three controls, not a corpus**; it is enough to show the signal exists
and not enough to fix a number. A page carrying a short Hebrew citation inside a
long English paper would score low and would *not* be flagged - which is correct
for the "reversed letters" defect, because there the whole run is RTL.

## The three answers, with what each promises

### A. Say the page may be right-to-left, and stop accusing

When a quote fails to match **and** the source page is substantially RTL, replace
`quote-missing` with a finding that says the page is right-to-left, that the
reader may have reversed or joined the words, and that the author should read the
page. Exit code follows the existing severity table; no new exit path.

- Promises: the tool never tells an RTL author their quote is absent when the page
  is RTL. That is the whole of the accusation problem.
- Does not promise: that the quote verifies. Anything RTL becomes "check by hand",
  including quotes that would have matched.
- Cost: one detector, one new code, one README/CHANGELOG row, tests. No dependency,
  no schema change, no change to matching. Producer B already lands here, so this
  mostly aligns the wording across the two producers.
- Risk: a page that is mostly RTL but whose quote genuinely is absent now gets the
  softer finding. That is a real loss of one signal, and it is the price of never
  making the false accusation.

### B. Read the page a second way when the first reading looks RTL

If the page scores above the threshold, extract it again with an extractor that
emits logical order (`pymupdf`) and match against that. Requires a new dependency
in `src/`, which this project forbids without a decision, and which `AGENTS.md`
names as exactly this kind of case.

- Promises: correct first-producer quotes verify normally.
- Does not promise anything for producer B, where the words are in logical order
  already and the spaces are what is missing.
- Cost: a dependency, an install story, a cache key that distinguishes the reader
  (`extractor` is already recorded per entry), and two readers to keep honest - the
  failure mode `_why_both_refused` exists to prevent.

### C. Do nothing and document it

Keep the extraction, state in the README that right-to-left manuscripts are not
supported, and let `quote-missing` mean what it says.

- Promises: nothing new.
- Cost: the false accusation stays, in the one case the project says it cares most
  about. Cheapest in engineering and worst for the author.

## What this proposal will not do

- It will not add a `pymupdf` dependency to `src/` before the Owner chooses.
- It will not un-reverse text heuristically. A reversed word and a genuinely
  different word are the same string to any check that has only the page; guessing
  would certify and refuse at random, and a palindromic or mixed-script quote makes
  it worse.
- It will not claim the 0.30 threshold is right. It separates what was measured
  here; a corpus is a different task.

## The decision

**Question (one, for the Owner): do we make right-to-left pages honest about what
the reader did to them (A), add a second reader to the tool (B), or leave the
behaviour alone and document it (C)?**

- **Answer A** - recommended if the tool is to stay dependency-free: a page is
  flagged as possibly reordered rather than certified or accused, no new package,
  and the two producers finally say the same kind of thing.
- **Answer B** - correct for producer A's quotes and no help for producer B; needs an
  explicit decision to add a package to `src/`.
- **Answer C** - honest and cheap, at the cost of the false accusation.

The acceptance for this task is the Owner's answer, recorded here and in
`docs/iteration-state.json`, followed by a separate bounded implementation task.
A timeout is not an answer. `src/` stays untouched until then.
