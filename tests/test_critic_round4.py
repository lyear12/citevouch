"""F1, F5-F10: the last round of things the code said that were not true.

Each test here failed before its fix. A regression test that was already green
records a fix; it does not defend one.

F1   a directory recorded as a source died with `PermissionError`, and the
     traceback left the process at exit 1 - the code that means "there are
     findings", so CI could not tell a crash from a verdict.
F5   an unclosed ```claim fence silently ate every claim after it.
F6   `-` is the table dialect's spelling of "no page"; it was reported as a
     non-numeric page the author had typed.
F7   `report --format markdown` printed page 0 as an em dash.
F8   two codes were documented, given severities and SARIF rules, and never
     produced by anything.
F9   `sources.yaml` was advertised and skipped; the SourceRef docstring still
     promised a filename-stem fallback that had been removed.
F10  a near-miss suggestion could point at a file the tool cannot read.
"""

from __future__ import annotations

import json

from citevouch.cli import main
from citevouch.manuscript import parse_manuscript
from citevouch.model import CODES, Ledger
from citevouch.report import SARIF_RULES
from citevouch.sources import candidate_files, extract_pages, near_misses


def _project(tmp_path):
    (tmp_path / "papers").mkdir()
    (tmp_path / "papers" / "p.txt").write_text(
        "We train on two corpora.\n",
        encoding="utf-8",
    )
    (tmp_path / "sources.toml").write_text('[sources]\np = "papers/p.txt"\n', encoding="utf-8")
    (tmp_path / "m.md").write_text(
        "```claim id=c1 source=p page=1\nquote: |\n  We train on two corpora.\n```\n",
        encoding="utf-8",
    )
    return tmp_path


# --- F1: a directory is missing, not fatal ---------------------------------


def test_a_directory_recorded_as_a_source_is_a_finding_not_a_traceback(tmp_path, capsys):
    """`exists()` is true for a directory, and the next line reads bytes from it."""
    root = _project(tmp_path)
    (root / "adir").mkdir()
    ledger_path = root / "citevouch.lock.json"
    main(["scan", "m.md", "--root", str(root)])
    # Drop the manifest: otherwise the key still resolves through it and the
    # recorded path - the thing under test - is never consulted.
    (root / "sources.toml").unlink()
    blob = json.loads(ledger_path.read_text(encoding="utf-8"))
    blob["sources"]["p"]["path"] = "adir"
    ledger_path.write_text(json.dumps(blob), encoding="utf-8")

    code = main(["verify", "m.md", "--root", str(root)])

    captured = capsys.readouterr()
    assert "Traceback" not in captured.err, captured.err
    assert code == 1
    assert "source-missing" in captured.out


def test_extract_pages_names_a_directory_as_a_directory(tmp_path):
    """It is `source-missing`, and the sentence says which kind of missing."""
    (tmp_path / "adir").mkdir()
    pages, problem = extract_pages(tmp_path / "adir", tmp_path, use_cache=False)
    assert pages == []
    assert problem is not None
    assert problem.code == "source-missing"
    assert "is a directory, not a file" in problem.message


# --- F5: an unclosed fence is data loss, and it is reported ----------------


def test_an_unclosed_claim_fence_is_reported_instead_of_swallowing_the_rest():
    text = (
        "```claim id=c1 source=s page=1\n"
        "quote: |\n"
        "  first quote\n"
        "```claim id=c2 source=s page=1\n"
        "quote: |\n"
        "  second quote\n"
    )
    parsed = parse_manuscript(text, "m.md")
    codes = [f.code for f in parsed.findings]
    assert "claim-block-unclosed" in codes
    finding = next(f for f in parsed.findings if f.code == "claim-block-unclosed")
    assert finding.claim_id == "c1"
    assert "never closed" in finding.message
    assert finding.line == 1


def test_a_file_that_ends_without_closing_its_fence_says_so():
    text = "```claim id=c1 source=s page=1\nquote: |\n  first quote\n"
    parsed = parse_manuscript(text, "m.md")
    assert [f.code for f in parsed.findings] == ["claim-block-unclosed"]


def test_a_closed_fence_is_not_reported():
    text = (
        "```claim id=c1 source=s page=1\n"
        "quote: |\n"
        "  first quote\n"
        "```\n"
        "\n"
        "```claim id=c2 source=s page=1\n"
        "quote: |\n"
        "  second quote\n"
        "```\n"
    )
    parsed = parse_manuscript(text, "m.md")
    assert [c.id for c in parsed.claims] == ["c1", "c2"]
    assert parsed.findings == []


# --- F6: `-` is a legal way to say "no page" ------------------------------


def test_a_dash_page_in_the_table_dialect_means_no_page_not_a_mistake():
    table = (
        "| id | source | page | quote | claim |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| c3 | s | - | some words of evidence | a claim |\n"
    )
    parsed = parse_manuscript(table, "m.md")
    assert [c.id for c in parsed.claims] == ["c3"]
    assert parsed.claims[0].page is None
    assert parsed.findings == []


# --- F7: page 0 is a number ------------------------------------------------


def test_report_prints_page_zero_instead_of_an_em_dash(tmp_path, capsys):
    root = _project(tmp_path)
    ledger = Ledger(manuscript="m.md", manuscript_sha256="x", generated_at="2026-01-01")
    ledger_path = root / "citevouch.lock.json"
    ledger_path.write_text(json.dumps(ledger.to_json()), encoding="utf-8")
    blob = json.loads(ledger_path.read_text(encoding="utf-8"))
    blob["claims"] = [
        {
            "id": "c1",
            "text": "t",
            "source": "p",
            "quote": "q",
            "page": 0,
        }
    ]
    ledger_path.write_text(json.dumps(blob), encoding="utf-8")

    assert main(["report", "--root", str(root)]) == 0
    out = capsys.readouterr().out
    assert "| `c1` | p | 0 |" in out, out
    # The cell, not the whole page: the title line contains an em dash of its own.
    row = next(line for line in out.splitlines() if line.startswith("| `c1`"))
    assert "—" not in row, row


# --- F8: a code nobody produces is a promise nobody keeps -----------------


def test_the_code_tables_agree_in_both_directions():
    assert set(CODES) - set(SARIF_RULES) == set()
    assert set(SARIF_RULES) - set(CODES) == set()


def test_every_code_is_produced_somewhere():
    """A code with no producer is documentation for a finding that cannot happen."""
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / "src" / "citevouch"
    # Leave out the two files that only *declare* codes: a code that exists in
    # both tables and nowhere else is the exact defect this test is for.
    producers = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(src.glob("*.py"))
        if path.name not in {"model.py", "report.py"}
    )
    missing = [code for code in CODES if f'"{code}"' not in producers]
    assert not missing, f"declared but never raised: {missing}"


# --- F9: do not advertise a manifest format we skip -----------------------


def test_a_yaml_manifest_is_not_advertised():
    from citevouch.sources import MANIFEST_NAMES

    assert MANIFEST_NAMES == ("sources.toml", "sources.json")


def test_the_source_docstring_does_not_promise_a_stem_fallback():
    from citevouch.model import SourceRef

    doc = SourceRef.__doc__ or ""
    assert "filename stem" not in doc
    assert "manifest" in doc


# --- F10: a suggestion has to be a file the tool could read ---------------


def test_near_misses_do_not_offer_a_readme(tmp_path):
    (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")
    (tmp_path / "papers").mkdir()
    (tmp_path / "papers" / "2026_vaneecke_cxn.pdf").write_bytes(b"%PDF-1.4\n")
    candidates = candidate_files(tmp_path)
    offered = near_misses("readme", candidates)
    assert "README.md" not in offered
    assert offered == []


# --- the ledger is a lockfile, so it is written the way it is committed ----


def test_the_ledger_is_written_with_lf_endings_on_every_platform(tmp_path):
    """`Path.write_text` translated \n to \r\n on Windows.

    A tool that reads and writes the same file has to write the bytes it means
    to read. On Windows the old writer produced CRLF, git normalised it back to
    LF on commit, and every scan after a fresh clone produced a diff of nothing
    but line endings - for a file whose whole purpose is to be read in a diff.
    """
    root = _project(tmp_path)
    assert main(["scan", "m.md", "--root", str(root)]) == 0
    raw = (root / "citevouch.lock.json").read_bytes()
    assert b"\r\n" not in raw, "the ledger carries CRLF"
    assert raw.endswith(b"\n")


def test_init_demo_writes_files_with_lf_endings(tmp_path):
    target = tmp_path / "demo"
    assert main(["init-demo", str(target)]) == 0
    for name in ("manuscript.md", "sources.toml", "demo_source.txt", "citevouch.lock.json"):
        raw = (target / name).read_bytes()
        assert b"\r\n" not in raw, f"{name} carries CRLF"
