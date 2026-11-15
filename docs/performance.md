# What this tool costs, measured on one machine

Numbers on this page were measured by `tools/benchmark.py` on **this machine** -
Windows-11-10.0.26300-SP0, CPython 3.14.6, pypdf-6.16.1, citevouch 0.29.0 -
against `demo/papers/2020_TayyarMadabushi-etal_CxGBERT.pdf` (243961 bytes, 13 pages,
52058 characters). Every figure is a median over the stated number of
runs, and the run repeats are reported because a single timing is an anecdote.

A timing is a fact about a machine and a version, not a property of the tool. If
these numbers are reproduced on another machine and differ, both machines are
right about themselves; nothing here is a specification.

## The three stages, measured apart

They scale with different things. Extraction scales with the file, normalisation
with characters, matching with pages *and* quote length.

| measurement | median ms | min ms | max ms | runs |
| --- | --- | --- | --- | --- |
| cold extraction (no cache) | 259.97 | 226.70 | 405.62 | 3 |
| warm extraction (cache hit) | 10.51 | 10.12 | 11.25 | 5 |
| normalise the whole document | 9.85 | 9.66 | 10.24 | 5 |
| match a 200-character verbatim quote | 0.01 | 0.00 | 0.02 | 3 |
| match an 85-character absent quote | 209.74 | 209.53 | 228.15 | 3 |
| match an 8000-character quote | 125.34 | 122.29 | 126.20 | 3 |
| match on a repetitive 108 KB page | 1.92 | 1.79 | 1.99 | 3 |
| 30 claims, on the page, 100 pages | 1.78 | 1.77 | 1.86 | 3 |
| 30 claims, absent, 100 pages | 2770.16 | 2753.57 | 2777.46 | 3 |

Two rows deserve their own sentence, because they are the two ways a citation
checker can be slow or fast for the wrong reason.

**A cache hit is not a small win; it is the whole cost of reading the PDF.** Cold
extraction of this paper costs about twenty times a warm one. That is what the
cache in `.citevouch/` exists for, and it is why a project that checks in its
cache runs its gate in a fraction of a second.

**A claim that is on the page is not a little cheaper than one that is not; it is
two orders of magnitude cheaper.** The hit above is one claim whose text is on
the page - it stops at the tier that found it. The absent row runs every tier
against every page. A manuscript of claims that all hit costs milliseconds; a
manuscript of claims that all miss costs seconds. Reporting only one of those two
numbers would misrepresent the tool in one direction or the other, so both are
measured.

## How cost scales

Page count, with an absent quote (every tier runs, so this is the worst case):

| pages | characters | median ms | ms per page |
| --- | --- | --- | --- |
| 1 | 720 | 1.84 | 1.84 |
| 8 | 5760 | 18.31 | 2.29 |
| 32 | 23040 | 78.52 | 2.45 |
| 128 | 92160 | 311.72 | 2.44 |

Per-page cost stays roughly flat, which is the shape the implementation claims:
pages are scanned independently and the tiers are tried per page. A quadratic
regression would show up here as a rising per-page column.

Quote length, against the real 14-page paper:

| quote characters | median ms |
| --- | --- |
| 40 | 131.41 |
| 160 | 231.61 |
| 640 | 719.39 |

Quote length matters as much as page count. A long quote is compared against a
longer window, so the comparison itself grows. This is why the harness never
promises "typical latency": there is no typical quote.

## What these numbers are not

- **Not a measurement of your paper.** The 100-page, 30-claim manuscript is
  synthetic: five copies per page of one 600-character paragraph. Real papers have
  figures, equations, tables and footnotes, and the extraction cost per page is
  not uniform. The ceiling that a test enforces on this fixture is a tripwire for a
  complexity regression, not a service level.
- **Not a promise about a cold machine.** Every matching number here runs against
  pages already in memory. A full cold run pays extraction first, then matching, and
  the extraction number above is what that costs for a file this size.
- **Not a claim that nothing is slow.** Nothing in this project times out a
  verification. There is no deadline in `src/citevouch/` and no way to make the
  tool give up and report a verdict it did not reach - a timeout that changed a
  verdict would be worse than slow. The only deadlines in the package are the 180
  second limits on the external `pdftotext` subprocess, which exist so a hung
  child cannot hang the tool.
- **Not a comparison.** There is no baseline against an earlier version recorded
  here, so this page cannot show a regression; it shows a shape. If a change is
  suspected of being slow, re-run the tool before and after on the same machine.

## Re-measuring

```sh
PYTHONPATH=src python tools/benchmark.py            # the table above
PYTHONPATH=src python tools/benchmark.py --json     # the same data
PYTHONPATH=src python tools/benchmark.py --out perf.json --repeat 7
```

`tests/test_performance_budget.py` runs the tool on every suite run and asserts
the *shape* - that a cache hit beats a cold read, that a hit beats a miss, that
per-page cost stays flat, that a longer quote is slower - inside thresholds loose
enough that a slow CI machine cannot fail them. It does not assert any
millisecond figure from this page; if it did, every runner upgrade would fail the
build.
