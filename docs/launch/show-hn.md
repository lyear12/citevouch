# Show HN

*Post as `Show HN: …`. One paragraph of what it is, one of why it exists, then
answer questions. Do not post it more than once; HN treats a repost of the same
link as noise and the second one does worse than the first.*

---

**Title** (80 char max, HN truncates past 80)

```
Show HN: Citevouch – bind every claim to the page of the PDF that proves it
```

Alternative if the first does not land:

```
Show HN: I got tired of checking my own citations, so I made it a CI gate
```

---

**Body**

I write papers that make a lot of numeric claims — "the corpus has 154,391
utterances", "the grammar has 40,688 constructions". Every one of those numbers
is somewhere in a PDF on my laptop, and every revision is a chance to copy it
wrong, or to copy it from the previous draft of the paper, or from a different
paper entirely.

The tools that exist check whether a reference is *real*: does the DOI resolve,
is it retracted, is the year right. That is a different question. A reference
can be perfectly real and the sentence next to it can still be wrong.

So I built the other half. You put a small block next to a sentence:

````
```claim id=cxn-total source=vaneecke2026cxn page=6
quote: |
  The resulting grammar consists of a network of 40,688 constructions, of which
  9,800 are frame-evoking constructions, 22,568 are argument structure
  constructions and 8,320 are roleset constructions.
claim: |
  The induced construction network has 40,688 constructions.
```
````

`citevouch scan` records the passage into a lockfile you commit. `citevouch
verify` reopens the PDFs and tells you which quotes are still on the page the
lockfile says, which moved, and which are gone — because you edited the sentence,
because the PDF was replaced with a different version, or because the number was
never there.

Three things I think are worth the attention:

- **It fails on the honest case.** The repo's `demo/` has five claims, four of
  which pass and one of which quotes a sentence that lives in a different paper.
  That last one fails on every run, on purpose. If it ever passes, matching got
  too permissive.
- **It is fully offline.** Nothing talks to Crossref, nothing phones home. It
  reads the files on your disk. That is a constraint, not a feature — it is why
  it can say "this sentence is on page 6" instead of "this DOI exists".
- **There is a `draft` command** that reads your existing manuscript, finds every
  `[@key]` and `\cite{key}`, and proposes claim blocks for you to review. Writing
  a hundred of these by hand is the reason tools like this do not get used.

```
pip install "git+https://github.com/lyear12/citevouch@v0.17.0"
cd demo && citevouch verify manuscript.md
```

Repo: https://github.com/lyear12/citevouch (Python, MIT, no runtime deps except
pypdf)

It is not on PyPI yet — the trusted-publisher registration is an account action
I have not done. The install above works.

---

## Notes for whoever posts this

- **Do not lead with "AI-built".** It is true that this repository is written and
  released by an agent, and HN will ask about it if the post gets traction — but
  as an opening line it reads as a gimmick and the first comment becomes about
  that instead of about citation-checking. Answer it if asked.
- **The demo is the whole argument.** Anyone can run two commands and see the
  tool say no to a real paper. Lead people there.
- **Expect the "why not just use Zotero" comment.** The answer is in the README's
  comparison table: Zotero knows the reference, nothing knows the sentence.
- **Expect "my publisher requires LaTeX".** `draft` reads `.tex` directly now;
  `scan`/`verify` never need to, because they read the PDF.
- **Best time to post:** weekday morning US Eastern. This is a tool for people
  who write papers, and that is when that audience is at a keyboard.
