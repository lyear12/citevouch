# Demo sources

Two published papers, included unmodified as the test fixture for `demo/`. They are here so
that the example can be re-run byte-for-byte: `demo/citevouch.lock.json` pins their SHA-256, and
`verify` reports `source-changed` if either file is ever replaced.

| file | paper | licence |
| --- | --- | --- |
| `2026_VanEecke-Beuls_CoNLL2026_large-scale-CxG.pdf` | Paul Van Eecke and Katrien Beuls, *A Method for Learning Large-Scale Computational Construction Grammars from Semantically Annotated Corpora*, Proceedings of CoNLL 2026, pp. 213–226 | © 2026 Association for Computational Linguistics; distributed on the ACL Anthology, which publishes its proceedings open access |
| `2020_TayyarMadabushi-etal_CxGBERT.pdf` | Harish Tayyar Madabushi, Laurence Romain, and Dagmar Divjak, *CxGBERT: BERT meets Construction Grammar*, COLING 2020 | Creative Commons Attribution 4.0 International (stated on the paper itself) |

Both are redistributed here as a reproducible fixture, not as part of this project's content. If you
own the rights to either file and would rather it not be in this repository, open an issue and it will
be removed; the demo still runs, it just needs the two files dropped back in under `demo/papers/`.

## Why a real paper instead of a generated one

The tool's hard problems are all about real PDFs: ligatures, smart quotes, words hyphenated across a
line break, footnotes interleaved with body text, and page numbers that belong to the *proceedings*
rather than to the paper. A generated fixture contains none of that, passes, and proves nothing. The
fixture is therefore deliberately a real file whose extraction quirks are already known — page 6
really does hold the 40,688-construction sentence, and the FCG Editor sentence really is not in it.
