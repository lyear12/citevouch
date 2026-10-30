# Figures

Both images are generated, not drawn. Regenerate them with:

```sh
PYTHONPATH=src python tools/make_figures.py
```

That needs `pymupdf` and `Pillow`, which are a figure tool's dependencies and not
the tool's — nothing under `src/citevouch` imports either of them.

## verify.png

`citevouch verify manuscript.md`, run inside `demo/`, with the real output
rendered into a terminal frame. Every line in it is what the command printed,
including the deliberate `[high]` on the `fcg-editor` claim.

`verify.txt` next to it holds the same lines as plain text. It exists because a
PNG cannot be compared by a test but a sidecar can: `tests/test_figures.py` runs
the demo again and fails if the output no longer matches, so the picture cannot
quietly become a picture of software that no longer exists.

## page.png

Page 6 of `demo/papers/2026_VanEecke-Beuls_CoNLL2026_large-scale-CxG.pdf`, with
`The resulting grammar consists` and `40,688` highlighted. It is the page that
the first line of `verify.png` is talking about, which is the whole point of the
tool: not "the reference exists" but "this sentence is on this page".

It is a short excerpt of one paragraph, not a whole page and not a whole paper,
picked because it is the paragraph the highlighted sentence lives in.

## Licence

The paper is ©2026 the Association for Computational Linguistics, from the
Proceedings of the 30th Conference on Computational Natural Language Learning
(pages 213–226), and ACL Anthology is open access. The excerpt is reproduced
here as the minimal illustration of what the tool checks, with the neighbouring
context left intact so the sentence is not misrepresented. If a rights holder
prefers it gone, it will be removed and the figure redrawn from a document this
project owns.
