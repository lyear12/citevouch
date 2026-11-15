"""CV-017: a reproducible three-stage performance measurement for citevouch.

Usage::

    PYTHONPATH=src python tools/benchmark.py            # human-readable table
    PYTHONPATH=src python tools/benchmark.py --json      # machine-readable

The tool measures three stages separately, because they scale with different
things and are fixed by different changes:

* extraction  - a property of the PDF reader; scales with file size and page count
* normalisation - a property of the text; scales with characters
* matching    - a property of the matcher; scales with pages AND quote length

Every sample is a median over ``--repeat`` runs, and every report carries the
machine, the tool version, the reader, the cache state, the claim count and the
page count, so a number without that context never leaves this file.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import citevouch  # noqa: E402
from citevouch import matching, sources, textnorm  # noqa: E402

DEMO = REPO / "demo"
PAPERS = DEMO / "papers"
PARAGRAPH = (
    "The corpus contains a large number of annotated construction entries, and "
    "each entry records a form, a meaning and a set of attested instances. "
)
# Deliberately absent from every fixture, so every matching tier runs.  A quote
# that hits is measured by the tier that found it, which is not the same cost.
ABSENT = "This sentence does not appear in the paper, and it is long enough to be searched for."
# Two manuscript shapes, because they cost very different amounts: a claim that
# is on the page stops at the tier that found it, and a claim that is not runs
# every tier against every page.  Reporting only the second would overstate a
# typical run; reporting only the first would hide the worst case.
HIT_CLAIM = "records a form, a meaning and a set of attested instances"
MISS_CLAIM = "The corpus contains a large number of annotated construction entries."


def _reader_name() -> str:
    try:
        import pypdf
    except ImportError:
        return "pdftotext"
    return f"pypdf-{pypdf.__version__}"


def _timed(fn: Callable[[], Any], repeat: int) -> tuple[Any, dict[str, float]]:
    samples: list[float] = []
    value: Any = None
    for _ in range(repeat):
        start = time.perf_counter()
        value = fn()
        samples.append((time.perf_counter() - start) * 1000.0)
    return value, {
        "repeat": repeat,
        "min_ms": round(min(samples), 2),
        "median_ms": round(statistics.median(samples), 2),
        "max_ms": round(max(samples), 2),
    }


def _pages_of(count: int) -> list[sources.PageText]:
    return [sources.PageText(number=i + 1, text=PARAGRAPH * 5) for i in range(count)]


def benchmark(*, repeat: int, warm_repeat: int) -> dict[str, Any]:
    pdf = sorted(PAPERS.glob("*.pdf"))[0]
    (pages, problem), extraction_cold = _timed(
        lambda: sources.extract_pages(pdf, DEMO, use_cache=False), repeat
    )
    if problem is not None:
        raise SystemExit(f"the extraction fixture is unreadable: {problem}")
    _, extraction_warm = _timed(
        lambda: sources.extract_pages(pdf, DEMO, use_cache=True), warm_repeat
    )

    body = "\n".join(page.text for page in pages)
    _, normalisation = _timed(lambda: textnorm.fold(body), warm_repeat)

    hit = body.find("The resulting grammar consists of a network of")
    verbatim = body[hit : hit + 200].replace("\n", " ")

    _, match_verbatim = _timed(lambda: matching.find_in_pages(verbatim, pages), repeat)
    _, match_absent = _timed(lambda: matching.find_in_pages(ABSENT, pages), repeat)
    _, match_long = _timed(lambda: matching.find_in_pages(body.strip()[:8000], pages), repeat)

    repeated = "We collected forty thousand examples from the corpus.\n" * 2000
    repeated_pages = [sources.PageText(number=1, text=repeated)]
    _, match_repetitive = _timed(
        lambda: matching.find_in_pages("examples from the corpus", repeated_pages), repeat
    )

    page_scaling: list[dict[str, Any]] = []
    for count in (1, 8, 32, 128):
        book = _pages_of(count)
        _, timing = _timed(lambda b=book: matching.find_in_pages(ABSENT, b), repeat)
        page_scaling.append({"pages": count, "chars": count * len(PARAGRAPH) * 5, **timing})

    quote_scaling: list[dict[str, Any]] = []
    for chars in (40, 160, 640):
        quote = ("not in this paper " * 200)[:chars]
        _, timing = _timed(lambda q=quote: matching.find_in_pages(q, pages), repeat)
        quote_scaling.append({"quote_chars": chars, **timing})

    manuscript_pages = _pages_of(100)

    def run(claims: list[str]) -> None:
        for claim in claims:
            matching.find_in_pages(claim, manuscript_pages)

    _, manuscript_hit = _timed(lambda: run([HIT_CLAIM] * 30), repeat)
    _, manuscript_miss = _timed(lambda: run([MISS_CLAIM] * 30), repeat)

    return {
        "schema": 1,
        "measured_with": {
            "citevouch": citevouch.__version__,
            "python": platform.python_version(),
            "machine": platform.platform(),
            "reader": _reader_name(),
            "cache": "cold for the first extraction sample, warm for the rest",
        },
        "fixtures": {
            "pdf": pdf.name,
            "pdf_bytes": pdf.stat().st_size,
            "pdf_pages": len(pages),
            "pdf_chars": len(body),
            "synth_page_chars": len(PARAGRAPH) * 5,
            "manuscript_pages": len(manuscript_pages),
            "manuscript_claims": 30,
        },
        "stages": {
            "extraction_cold": extraction_cold,
            "extraction_warm": extraction_warm,
            "normalisation": normalisation,
            "matching": {
                "verbatim_200": match_verbatim,
                "absent_85": match_absent,
                "long_8000": match_long,
                "repetitive_108k": match_repetitive,
            },
        },
        "scaling": {"pages": page_scaling, "quote": quote_scaling},
        "manuscript": {"claims_on_the_page": manuscript_hit, "claims_absent": manuscript_miss},
    }


def _line(label: str, stats: dict[str, float]) -> str:
    return (
        f"  {label:<34} median {stats['median_ms']:9.2f} ms"
        f"  (min {stats['min_ms']:8.2f}  max {stats['max_ms']:8.2f}, n={stats['repeat']})"
    )


def report(data: dict[str, Any]) -> str:
    measured = data["measured_with"]
    fixtures = data["fixtures"]
    stages = data["stages"]
    lines = [
        f"citevouch {measured['citevouch']}  python {measured['python']}  reader {measured['reader']}",
        f"machine: {measured['machine']}",
        f"fixture: {fixtures['pdf']} ({fixtures['pdf_bytes']} bytes, "
        f"{fixtures['pdf_pages']} pages, {fixtures['pdf_chars']} chars)",
        "",
        "stage 1 - extraction",
        _line("cold (no cache)", stages["extraction_cold"]),
        _line("warm (cache hit)", stages["extraction_warm"]),
        "",
        "stage 2 - normalisation",
        _line("fold the whole document", stages["normalisation"]),
        "",
        "stage 3 - matching",
    ]
    for name, stats in stages["matching"].items():
        lines.append(_line(name.replace("_", " "), stats))
    lines += ["", "page scaling (absent quote, every tier runs):"]
    for row in data["scaling"]["pages"]:
        per_page = row["median_ms"] / row["pages"]
        lines.append(
            f"  pages={row['pages']:4d} chars={row['chars']:7d}  "
            f"median {row['median_ms']:9.2f} ms  ({per_page:.2f} ms/page)"
        )
    lines += ["", "quote-length scaling (absent quote, 14 real pages):"]
    for row in data["scaling"]["quote"]:
        lines.append(
            f"  quote={row['quote_chars']:4d} chars  median {row['median_ms']:9.2f} ms"
        )
    lines += [
        "",
        f"a manuscript: {fixtures['manuscript_claims']} claims x "
        f"{fixtures['manuscript_pages']} pages ({fixtures['synth_page_chars']} chars/page)",
        _line("claims on the page", data["manuscript"]["claims_on_the_page"]),
        _line("claims absent (every tier runs)", data["manuscript"]["claims_absent"]),
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repeat", type=int, default=3, help="samples per measurement (default 3)"
    )
    parser.add_argument("--warm-repeat", type=int, default=5, help="samples for cheap stages")
    parser.add_argument("--json", action="store_true", help="print JSON instead of a table")
    parser.add_argument("--out", type=Path, default=None, help="also write the JSON here")
    args = parser.parse_args(argv)
    data = benchmark(repeat=args.repeat, warm_repeat=args.warm_repeat)
    if args.out is not None:
        args.out.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(data, indent=2, sort_keys=True) if args.json else report(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
