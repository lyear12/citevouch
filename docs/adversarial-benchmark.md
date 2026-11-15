# What this tool is measured against, and what the measurement cannot say

The README says what `citevouch` checks. This page says how that claim is
measured, what the benchmark contains, and which of its numbers are facts about
the tool rather than facts about the PDFs it read.

The data lives in [`tests/fixtures/adversarial-cases.json`](../tests/fixtures/adversarial-cases.json)
and is read by [`tests/test_adversarial_benchmark.py`](../tests/test_adversarial_benchmark.py).
Every `expected` block in that file was produced by running the matcher, not
written by hand: the file records `measured_with` - `citevouch 0.28.0`, CPython
3.14.6, pypdf 6.16.1, dated 2026-11-15 - so a reader knows what machine the
numbers describe.

## Three axes, never one score

The single most expensive confusion in a citation checker is treating these as
one question. They are three, and only the first is computed.

| axis | the question | who answers it | in this benchmark |
| --- | --- | --- | --- |
| **Alignment** | is this quote on that page? | the matcher | `expected` block, re-measured on every test run |
| **Extraction** | did the reader produce the words at all? | the PDF reader | `source` cases read the two demo PDFs through the real extractor |
| **Support** | does the passage back the sentence? | a human | `human_support` label, never computed |

`human_support` is a label this project wrote down. It is not a verdict the
tool produces, and the benchmark exists partly to keep that sentence true.

## The case that proves the split is real

`paraphrase-faithful` is labelled `supported` and is **not on the page**:

- the page prints `The intervention did not improve accuracy in the controlled study.`
- the claim quotes `Accuracy did not improve under the intervention in that study.`

A reader would accept that as a faithful rendering. The matcher returns
`tier: none`, `found: false` - correctly, because the words are not there. So
the benchmark carries a case where the human axis says yes and the computed axis
says no, and neither is a bug. `paraphrase-faithful` has intent
`should_not_find` precisely because a tool that reported it as found would be
lying about what it did.

The mirror image is `cjk-exact`: the words are on the page, the support label is
`unknown` because nobody here has judged whether the quoted Chinese sentence
backs the claim it is attached to.

## What is in the primary set

Nineteen cases, each with a provenance record:

| family | cases |
| --- | --- |
| verbatim and near-verbatim hits | `exact-hit-en`, `whitespace-collapse`, `line-wrap-hyphen`, `wrapped-in-quotes` |
| layout | `cross-page-run`, `conll-extracted-lines`, `conll-sentence-as-printed` |
| CJK | `cjk-exact`, `cjk-negation-exact`, `cjk-negation-dropped` |
| adjacent and scoped sentences | `adjacent-sentence-second`, `entity-scope-narrow` |
| distant numbers | `number-wrong-in-quote`, `conll-wrong-number` |
| undecidable word boundaries | `squashed-boundary-lost` |
| absent text | `quote-absent`, `conll-absent-sentence` |
| the two axes disagreeing | `paraphrase-faithful` |
| a second real paper | `cxgbert-abstract` |

The `real-pdf` cases are read out of `demo/papers/`, the two published papers
this repository already ships, whose licences are recorded in
[`demo/papers/README.md`](../demo/papers/README.md). The rest are `authored`:
written here, containing no third-party text, so they can be redistributed with
the archive. The four cases in `held_out` are kept separate so the shape of the
primary set is not also the shape of the thing used to check it; they are
measured and recorded the same way.

## A measurement that disagrees with the design is recorded, not hidden

`conll-sentence-as-printed` is the one open disagreement, and it is written into
`known_gaps`:

> The reader breaks the sentence across four lines with hyphens, so the flattened
> form an author would retype matches at similarity 0.91 and lands in the `fuzzy`
> tier - reported as `quote-fuzzy` at high, with the claim counted missing. The
> demo passes because it quotes the reader's own line-broken text, which matches
> exactly. An author who retypes the printed sentence is told the quote is only
> approximate.

That is a real cost and this page does not talk it away. It also cannot be fixed
here: closing it means teaching the hyphen tier to absorb a whole sentence's
worth of line breaks, which is a matching change and needs its own accepted
design.

The test enforces the bookkeeping in both directions. A case whose `intent` and
`expected` disagree without a `known_gaps` entry fails, so a gap cannot be opened
quietly; and a `known_gaps` entry whose case now satisfies its intent fails, so a
gap cannot be closed quietly either. Closing the gap above requires deleting its
entry in the same commit that changes the matcher.

## What this benchmark does not cover

- **Extraction quality on files this repository does not own.** Two real papers
  is a corpus, not a survey. Both are two-column ACL-style PDFs with a modern
  reader; scans, right-to-left layouts, ligature-heavy typefaces and
  LaTeX-generated equations are not measured here. The `held_out` RTL case
  exercises the *matcher* on Hebrew text, not a real Hebrew PDF.
- **Support, at all.** There is no gold set of "this passage backs this
  sentence", so no number on this page is a precision or recall of that. The
  labels are one person's reading, written down so a disagreement can be argued
  with rather than guessed at.
- **Typical latency.** Nothing here is timed.
- **Whether the source is the file the author meant.** A hash says the bytes are
  the ones that were recorded; it does not say they are the right paper.

## How to re-measure

```sh
PYTHONPATH=src python -m pytest tests/test_adversarial_benchmark.py
```

The file is regenerated by the same case table that produced it, so a deliberate
change to the matcher is a two-line commit: the behaviour change, and the updated
`expected` blocks with an updated `measured_with`. A change that leaves the
fixture untouched fails the first test in the module.
