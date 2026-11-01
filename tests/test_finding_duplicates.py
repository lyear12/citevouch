"""One fact, one line: the two check paths must not disagree about the count.

The fresh path scanned and then deduplicated.  The recorded path - the one
``action.yml`` runs on every pull request - skipped the deduplication, so the
same tree produced two lines for one conclusion there and one line locally.
A reviewer reading the two never sees them side by side, which is why this
survived: the only way to notice is to run both and compare the totals.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from citevouch.cli import main

PAGE = "We collected 40,688 examples in the corpus.\n"
MANUSCRIPT = """```claim id=c1 source=a page=1
quote: |
  We collected 40,688 examples in the corpus.
claim: |
  The corpus has 40,688 examples.
```
"""


def _project(tmp_path: Path, page: str = PAGE) -> Path:
    (tmp_path / "page.txt").write_text(page, encoding="utf-8")
    (tmp_path / "sources.toml").write_text('[sources]\na = "page.txt"\n', encoding="utf-8")
    (tmp_path / "m.md").write_text(MANUSCRIPT, encoding="utf-8")
    return tmp_path


def _codes(root: Path, *, recorded: bool) -> list[tuple[str, str]]:
    """Run one mode and return every (code, claim id) it printed."""
    argv = ["check", "m.md", "--root", str(root), "--format", "json"]
    if recorded:
        argv.append("--use-recorded")
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main(argv)
    return [
        (f["code"], f.get("claim_id") or "") for f in json.loads(buffer.getvalue())["findings"]
    ]


def test_a_missing_number_is_one_line_in_both_modes(tmp_path: Path):
    """The reported defect: two lines recorded, one line fresh."""
    root = _project(tmp_path)
    main(["scan", "m.md", "--root", str(root)])
    # The page keeps the words and changes the number, which is the shape the
    # `numbers` tier reports and the per-number check also reports.
    (root / "page.txt").write_text(
        "We collected 12 examples in the corpus.\n", encoding="utf-8"
    )

    fresh = _codes(root, recorded=False)
    recorded = _codes(root, recorded=True)

    absent = "number-absent-in-quote"
    assert fresh.count((absent, "c1")) == 1
    assert recorded.count((absent, "c1")) == 1, (
        "the recorded path printed the same number twice; before the fix this "
        f"was 2. Codes seen: {recorded}"
    )


def test_the_two_modes_agree_about_how_many_findings_there_are(tmp_path: Path):
    """Whatever the dedup key is, both paths must apply it the same way.

    This is the assertion that would have caught the original bug without
    knowing which code duplicated: it compares the two paths to each other
    rather than to a remembered number.
    """
    root = _project(tmp_path)
    main(["scan", "m.md", "--root", str(root)])
    (root / "page.txt").write_text(
        "We collected 12 examples in the corpus.\n", encoding="utf-8"
    )

    fresh = _codes(root, recorded=False)
    recorded = _codes(root, recorded=True)
    # The recorded path may add `source-changed`, which the fresh path cannot
    # know about because it reads the current file as the truth.  Nothing
    # else may differ.
    assert [c for c in recorded if c[0] != "source-changed"] == fresh


def test_the_duplicate_was_real_in_the_verifier(tmp_path: Path):
    """The dedup is not hiding a bug in the verifier: both lines come out of it."""
    from citevouch import scan as scan_module
    from citevouch import verify as verify_module

    root = _project(tmp_path)
    main(["scan", "m.md", "--root", str(root)])
    (root / "page.txt").write_text(
        "We collected 12 examples in the corpus.\n", encoding="utf-8"
    )

    args = _options_for(root)
    ledger, _ = scan_module.scan(args)
    result = verify_module.verify(ledger, args, check_manuscript_hash=False)
    absent = [f for f in result.findings if f.code == "number-absent-in-quote"]
    assert len(absent) == 2, (
        "expected the verifier to reach this conclusion twice before dedup; if "
        "it now reaches it once, the dedup may be unnecessary - check whether "
        f"the CLI test above still fails without it. Got: {[f.message for f in absent]}"
    )


def _options_for(root: Path):
    from citevouch import scan as scan_module

    return scan_module.ScanOptions(manuscript="m.md", root=str(root), sources=[], bib=[])


def test_the_path_is_part_of_what_makes_a_finding_duplicate(tmp_path: Path):
    """Two unreadable sources are two facts, not one fact twice.

    ``source-no-text`` carries no claim id - it is true of a *file*.  If the
    dedup key were (code, claim) it would keep the first unreadable source and
    drop the second, and the author would OCR ``a.pdf``, re-run, and meet
    ``b.pdf`` for the first time.  A key that looks tidier is a key that loses
    a file, which is why the path is in it.
    """
    from test_source_no_text import _blank_pdf

    _blank_pdf(tmp_path / "a.pdf", pages=1)
    _blank_pdf(tmp_path / "b.pdf", pages=1)
    (tmp_path / "sources.toml").write_text(
        '[sources]\na = "a.pdf"\nb = "b.pdf"\n', encoding="utf-8"
    )
    (tmp_path / "m.md").write_text(
        "```claim id=c1 source=a\nquote: |\n  This sentence is on no page at all.\n```\n"
        "\n```claim id=c2 source=b\nquote: |\n  This one is not either, not anywhere.\n```\n",
        encoding="utf-8",
    )

    codes = [code for code, _ in _codes(tmp_path, recorded=False)]
    assert codes.count("source-no-text") == 2, (
        "both unreadable sources must be named; a key without the path keeps "
        f"one and hides the other. Codes seen: {codes}"
    )


def _findings_for(argv: list[str]) -> list[tuple[str, str]]:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main(argv)
    return [
        (f["code"], f.get("claim_id") or "") for f in json.loads(buffer.getvalue())["findings"]
    ]


def test_every_verb_that_prints_findings_prints_each_fact_once(tmp_path: Path):
    """The pass belongs at the writer, not in each caller's branch.

    Fixing this one caller at a time is how it got to three: ``check``
    deduplicated, ``check --use-recorded`` did not, and ``verify`` - a verb
    this file's first version never ran - did not either.  A test naming two
    of the three callers would have passed while the third stayed broken, so
    this one enumerates the verbs instead of the branches.
    """
    root = _project(tmp_path)
    main(["scan", "m.md", "--root", str(root)])
    (root / "page.txt").write_text(
        "We collected 12 examples in the corpus.\n", encoding="utf-8"
    )

    verbs = {
        "verify": ["verify", "m.md", "--root", str(root), "--format", "json"],
        "check": ["check", "m.md", "--root", str(root), "--format", "json"],
        "check --use-recorded": [
            "check",
            "m.md",
            "--root",
            str(root),
            "--format",
            "json",
            "--use-recorded",
        ],
    }
    for name, argv in verbs.items():
        seen = _findings_for(argv)
        assert len(seen) == len(set(seen)), f"{name} printed a fact twice: {seen}"


def test_two_blocks_that_both_forgot_an_id_are_two_problems(tmp_path: Path):
    """Two findings that are not the same fact must not share a key.

    Both blocks below carry an empty claim id, so a key of
    (code, claim_id, path) collapsed them into one and the report named only
    line 1.  The author fixes line 1, re-runs, and meets line 8 for the first
    time - the report was describing the file one mistake at a time.
    """
    root = tmp_path
    body = (
        "```claim source=a page=1\n"
        "quote: |\n"
        "  We collected 40,688 examples.\n"
        "claim: |\n"
        "  A block with no id.\n"
        "```\n"
        "\n"
        "```claim source=a page=1\n"
        "quote: |\n"
        "  We collected 40,688 examples.\n"
        "claim: |\n"
        "  Another block with no id.\n"
        "```\n"
    )
    (root / "m.md").write_text(body, encoding="utf-8")
    (root / "page.txt").write_text("We collected 40,688 examples.\n", encoding="utf-8")
    (root / "sources.toml").write_text('[sources]\na = "page.txt"\n', encoding="utf-8")

    seen = _findings_for(["check", "m.md", "--root", str(root), "--format", "json"])
    uncheckable = [c for c in seen if c[0] == "claim-uncheckable"]
    assert len(uncheckable) == 2, (
        f"two id-less blocks reported as {len(uncheckable)} problem(s)"
    )

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main(["check", "m.md", "--root", str(root), "--format", "json"])
    lines = [
        f.get("line")
        for f in json.loads(buffer.getvalue())["findings"]
        if f["code"] == "claim-uncheckable"
    ]
    assert lines == [1, 8], f"the two findings named lines {lines}"
