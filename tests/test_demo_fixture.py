"""F4: both demo PDFs have to be load bearing.

The fixture shipped two papers and cited one. Replacing the uncited one with
40 bytes of garbage changed the demo's output by nothing, which made three
sentences false: `demo/papers/README.md` ("`source-changed` if either file is
replaced"), the Chinese README ("5 条断言取自两篇真实论文") and AGENTS.md ("a
real PDF pair").

The fix binds the fifth claim to the second paper, so both are cited and the
wrong-paper failure is a real one: the FCG Editor sentence is in neither.
These tests are the ones that would have caught the decoration.
"""

import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo"


def _demo_copy(tmp_path: Path) -> Path:
    target = tmp_path / "demo"
    shutil.copytree(DEMO, target, ignore=shutil.ignore_patterns(".citevouch"))
    return target


def test_every_demo_source_is_cited_by_a_claim() -> None:
    """A fixture file nobody references is a fixture file nobody would miss."""
    from citevouch.scan import ScanOptions, scan

    ledger, _findings = scan(ScanOptions(manuscript="manuscript.md", root=str(DEMO)))
    cited = {claim.source for claim in ledger.claims}
    declared = set(ledger.sources)
    assert declared == cited, f"declared but never cited: {declared - cited}"


def test_the_two_demo_claims_bind_to_different_files() -> None:
    from citevouch.scan import ScanOptions, scan

    ledger, _findings = scan(ScanOptions(manuscript="manuscript.md", root=str(DEMO)))
    paths = {ref.path for ref in ledger.sources.values()}
    assert len(ledger.sources) == 2
    assert len(paths) == 2, f"both source keys resolve to the same file: {paths}"


@pytest.mark.parametrize(
    "paper",
    [
        "2026_VanEecke-Beuls_CoNLL2026_large-scale-CxG.pdf",
        "2020_TayyarMadabushi-etal_CxGBERT.pdf",
    ],
)
def test_replacing_either_pdf_is_noticed(tmp_path: Path, paper: str) -> None:
    """The promise in `demo/papers/README.md`, executed instead of asserted."""
    from citevouch.cli import main

    demo = _demo_copy(tmp_path)
    target = demo / "papers" / paper
    assert target.is_file()
    target.write_bytes(b"%PDF-1.4\nnot the paper any more\n")

    # Exit 1 alone proves nothing here: `fcg-editor` fails on a clean checkout too,
    # so a test that only checks the code stays green even when the replaced file is
    # never read. The finding has to be about *this* file.
    import contextlib
    import io
    import json

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = main(
            ["verify", "manuscript.md", "--root", str(demo), "--no-cache", "--format", "json"]
        )
    assert code == 1
    payload = json.loads(buffer.getvalue())
    changed = [f for f in payload["findings"] if f["code"] == "source-changed"]
    assert changed, "replacing a cited PDF produced no source-changed finding"
    assert any(paper in f["message"] for f in changed), (
        f"source-changed does not mention {paper}: " + ", ".join(f["message"] for f in changed)
    )


def test_the_wrong_file_kind_is_named_before_it_is_skipped(tmp_path: Path) -> None:
    """`source-changed` must survive the unreadable-source skip.

    The skip exists so a PDF nobody can read does not produce a `quote-missing`
    verdict about the author's quote. It sat *in front of* the hash comparison,
    so replacing a cited PDF with a corrupt file reported `source-unreadable`
    and nothing else: the reader is told their PDF is broken, never that it is
    not the file the ledger read. Those are different repairs.
    """
    from citevouch.cli import main

    demo = _demo_copy(tmp_path)
    papers = demo / "papers"
    paper = sorted(papers.glob("*.pdf"))
    assert len(paper) == 2, f"expected the two-paper fixture, found {paper}"
    paper[1].write_bytes(b"%PDF-1.4\nthis replacement is not a document\n")

    import contextlib
    import io
    import json

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        main(["verify", "manuscript.md", "--root", str(demo), "--no-cache", "--format", "json"])
    payload = json.loads(buffer.getvalue())
    findings = payload["findings"]
    codes = [f["code"] for f in findings]

    # `quote-missing` for the deliberately-wrong `fcg-editor` claim is expected and
    # is not about the swapped file. What must not happen is a `quote-missing`
    # against the claim whose source was replaced - that would be a verdict about
    # the quote drawn from a file the tool could not read.
    broken_claims = {f["claim_id"] for f in findings if f["code"] == "source-changed"}
    assert broken_claims, f"the swap went unreported; findings were {codes}"
    assert "source-unreadable" in codes
    missing = {f["claim_id"] for f in findings if f["code"] == "quote-missing"}
    assert missing == {"fcg-editor"}, f"a broken file became evidence: {missing}"


def test_the_committed_ledger_is_one_this_version_would_write(tmp_path: Path) -> None:
    """A stale ledger means the fixture is rehearsing a program that is gone.

    `demo/citevouch.lock.json` sat at tool_version 0.5.0 through eleven releases.
    Nothing failed, because nothing compared the committed file to what `scan`
    writes today - so the demo was one schema change away from being a fixture
    that cannot be regenerated. The version is not pinned here: pinning it would
    break every release, since the auto-release bump cannot reach inside `demo/`.
    What is checked is that re-recording the demo's own manuscript reproduces the
    committed file except for the two fields that record *when* and *by what*.
    """
    import json

    from citevouch.cli import main

    demo = _demo_copy(tmp_path)
    committed = json.loads((demo / "citevouch.lock.json").read_text(encoding="utf-8"))

    import contextlib
    import io

    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        main(["scan", "manuscript.md", "--root", str(demo), "--no-cache"])

    fresh = json.loads((demo / "citevouch.lock.json").read_text(encoding="utf-8"))

    volatile = {"generated_at", "tool_version"}
    for key in committed:
        if key in volatile:
            continue
        assert fresh.get(key) == committed[key], (
            f"{key} differs between the committed ledger and a fresh scan of the "
            f"same manuscript, so the demo records evidence this version would "
            f"not write. Re-record it with `citevouch scan demo/manuscript.md "
            f"--root demo`."
        )
    assert committed["tool_version"], "the committed ledger records no tool_version"
    assert fresh["tool_version"] == __import__("citevouch").__version__
