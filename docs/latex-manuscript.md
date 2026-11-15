# When the final manuscript is LaTeX

`citevouch draft` accepts a `.tex` file. `citevouch scan`, `check` and `verify` do not: claim
blocks live in Markdown, and a `.tex` file cannot hold one in a way the parser reads. This page is
the walk from a `.tex` manuscript to a gating CI job, and the one place where that walk does not
close.

Everything below was run against `paper.tex` in a scratch project with one 40,688-example page in
`sources.toml`. The commands and exit codes are the ones this version prints.

## 1. Propose from the `.tex`

```bash
citevouch draft paper.tex --bib refs.bib -o claims.md
```

Measured on a document whose section said `We collected 40,688 examples from the corpus \citep{paper}.`:

```
citevouch: 1 claim block(s) proposed (1 verbatim), 0 citation(s) left as comments
citevouch: wrote claims.md; read it, then `citevouch check claims.md` to see what it got wrong
```

The prose was converted, the citation became a marker, and the block quotes the page verbatim.

## 2. Read the proposals

`claims.md` is a proposal file, not a manuscript. Read the `medium` entries, fix what the converter
mangled, and delete the blocks you do not want. Nothing here has been checked yet.

## 3. Put the blocks in a Markdown file, and keep it next to the `.tex`

This is the step that has no automatic answer. The blocks cannot go into `paper.tex`:

```
$ citevouch scan paper.tex
citevouch: manuscript paper.tex is LaTeX, and citevouch reads claim blocks - which live in
Markdown, not in a .tex file. Propose them first: `citevouch draft paper.tex -o claims.md`,
then check claims.md. Scanning the .tex would record zero claims and report a clean run for
a manuscript nothing checked.
$ echo $?
2
```

So the blocks live in a second file — call it `evidence.md` — holding the accepted blocks and
nothing else:

````markdown
# Evidence for paper.tex

```claim id=corpus source=paper page=1
quote: |
  We collected 40,688 examples from the corpus.
claim: |
  We collected 40,688 examples from the corpus.
```
````

## 4. Record the evidence

```bash
citevouch scan evidence.md
```

```
$ citevouch scan evidence.md; echo $?
citevouch: wrote citevouch.lock.json (1 claim)
0
```

The ledger's `manuscript` field is `evidence.md`. That is the whole point of this page and the whole
of its limitation: **the ledger's subject is the Markdown file, not the `.tex` file.**

## 5. Gate the pull request

```bash
citevouch check evidence.md --use-recorded --fail-on medium
```

Measured, on the same project:

| what changed | command | exit | findings |
| --- | --- | --- | --- |
| nothing | `check evidence.md --use-recorded --fail-on medium` | 0 | `quote-found` |
| the quote in `evidence.md` | same | 1 | `ledger-stale` (high), 0 verified, 1 skipped |
| the page text under the quote | same | 1 | `source-changed` (medium) and `quote-fuzzy` (medium) |
| **the number in `paper.tex`** | same | **0** | `quote-found`, verified 1 |

## The limitation, stated exactly

The last row is the one to read. Changing `40,688` to `91,234` inside `paper.tex` left the gate at
exit 0 with one verified claim, because nothing in the ledger names `paper.tex`. The gate protects
the file it is pointed at. It cannot see the manuscript the evidence was collected for, and no flag
makes it: `--allow-stale` relaxes the ledger's binding to *its own* subject, not to a second file
the tool has never been told about.

That leaves two honest options, and this version implements neither:

- keep the link manual — the reviewer is told that `evidence.md` mirrors `paper.tex`, and that
  editing the `.tex` is exactly the case CI will not catch;
- give `evidence.md` a claim per sentence whose words also appear in the `.tex`, and gate on the
  pair — but the converter is not a TeX parser, so a sentence it mangles stops being comparable and
  the check quietly loses the sentence rather than failing.

Both are written down as an open question in [review-state-proposal.md](review-state-proposal.md),
which is about binding a *review* to content; binding a *manuscript* to content is the same shape of
problem and needs the same decision.

## What the converter reads, and what it does not

- It reads **one file**. `\input{sec/method}`, `\subfile`, `\import` and the rest are listed by
  `included_files`, and `draft` prints a comment naming them, but the text of those files is never
  read. Measured: a document whose only `\citep` sat in an `\input`ed file got
  `0 claim block(s) proposed: no citations were found to propose them for`.
- `%` comments, `thebibliography`, verbatim and listing environments, macro bodies and TeX
  conditionals are dropped or resolved as TeX would; a section title becomes its own paragraph.
- A macro that expands to prose is invisible: the converter sees the call, not the expansion.
- A mangled sentence usually stops being proposed at all, which is a weaker proposal rather than a
  wrong one. Where it does propose, the passage is genuinely verbatim from the page but may not be
  the passage you meant — those are `medium`, and a proposal is not a verdict.

## What this page does not claim

It makes no claim that gating `evidence.md` covers `paper.tex`. The measured row above says the
opposite, and the two options that would close it are decisions, not implementation details. It does
not claim the converter understands TeX. And it is not a review: it cannot tell you whether the
passage backs the sentence.
