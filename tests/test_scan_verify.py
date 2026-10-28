"""End-to-end: scan builds a ledger, verify re-checks it, drift is caught.

These are the tests that describe the product.  Everything below builds real
files on disk because the tool's whole job is reading them.
"""

from __future__ import annotations

import json
from pathlib import Path

from citevouch.scan import ScanOptions, scan
from citevouch.verify import verify


def _write(project: Path, name: str, text: str) -> Path:
    path = project / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_clean_project_scans_and_verifies(project: Path, manuscript: Path):
    ledger, findings = scan(ScanOptions(manuscript=str(manuscript), root=str(project)))
    # scan records; the judgement about whether the quote is really there comes
    # from verify.  A scan that reported "found" would be doing two jobs.
    assert ledger.claims
    assert not [f for f in findings if f.severity == "high"]

    result = verify(ledger, ScanOptions(manuscript=str(manuscript), root=str(project)))
    assert result.ok
    assert result.verified == 1
    assert [f.code for f in result.findings] == ["quote-found"]


def test_scan_records_the_source_hash_and_page_count(project: Path, manuscript: Path):
    ledger, _ = scan(ScanOptions(manuscript=str(manuscript), root=str(project)))
    ref = ledger.sources["smith2026cxn"]
    assert ref.sha256
    assert ref.pages == 1
    assert ref.path.endswith("2026_smith_networks.txt")


def test_the_ledger_records_a_portable_path(project: Path, manuscript: Path):
    """A ledger that stores an absolute path is a ledger for one machine only.

    `papers/x.pdf`, forward-slashed, resolves after a clone on Linux; `C:\\...`
    does not, and a CI job that clones the repository would report every source
    as missing for a reason that has nothing to do with the evidence.
    """
    ledger, _ = scan(ScanOptions(manuscript=str(manuscript), root=str(project)))
    recorded = ledger.sources["smith2026cxn"].path
    assert not Path(recorded).is_absolute()
    assert "\\" not in recorded
    assert recorded == "papers/2026_smith_networks.txt"

    # And a relative record still resolves on the way back in.
    result = verify(ledger, ScanOptions(manuscript=str(manuscript), root=str(project)))
    assert result.verified == 1
    assert result.ok


def test_two_keys_for_one_file_are_filed_under_their_own_keys(project: Path, manuscript: Path):
    """The key inside a ledger entry must match the key the entry is filed under."""
    source = project / "papers" / "2026_smith_networks.txt"
    (project / "sources.toml").write_text(
        '[sources]\nsmith2026cxn = "papers/2026_smith_networks.txt"\n'
        'smith2026again = "papers/2026_smith_networks.txt"\n',
        encoding="utf-8",
    )
    manuscript.write_text(
        manuscript.read_text(encoding="utf-8")
        + "\n```claim id=c2 source=smith2026again\nquote: |\n  The inventory has 40,688 entries.\n```\n",
        encoding="utf-8",
    )
    ledger, _ = scan(ScanOptions(manuscript=str(manuscript), root=str(project)))
    assert source.exists()
    assert set(ledger.sources) == {"smith2026cxn", "smith2026again"}
    for key, ref in ledger.sources.items():
        assert ref.key == key, f"entry {key} claims to be {ref.key}"


def test_scan_records_the_manuscript_hash(project: Path, manuscript: Path):
    ledger, _ = scan(ScanOptions(manuscript=str(manuscript), root=str(project)))
    assert ledger.manuscript_sha256


def test_editing_the_manuscript_makes_the_ledger_stale(project: Path, manuscript: Path):
    ledger, _ = scan(ScanOptions(manuscript=str(manuscript), root=str(project)))
    manuscript.write_text(
        manuscript.read_text(encoding="utf-8") + "\nA new paragraph.\n",
        encoding="utf-8",
    )
    result = verify(ledger, ScanOptions(manuscript=str(manuscript), root=str(project)))
    assert [f.code for f in result.findings] == ["ledger-stale"]
    assert not result.ok
    assert result.skipped == len(ledger.claims)


def test_allow_stale_lets_a_reviewer_ignore_the_hash(project: Path, manuscript: Path):
    ledger, _ = scan(ScanOptions(manuscript=str(manuscript), root=str(project)))
    manuscript.write_text(manuscript.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    result = verify(
        ledger,
        ScanOptions(manuscript=str(manuscript), root=str(project)),
        check_manuscript_hash=False,
    )
    assert not any(f.code == "ledger-stale" for f in result.findings)
    assert result.verified == 1


def test_changed_source_is_reported_as_drift(project: Path, manuscript: Path):
    ledger, _ = scan(ScanOptions(manuscript=str(manuscript), root=str(project)))
    source = project / "papers" / "2026_smith_networks.txt"
    source.write_text("1. Introduction\nWe train on one corpus now.\n", encoding="utf-8")
    result = verify(ledger, ScanOptions(manuscript=str(manuscript), root=str(project)))
    codes = {f.code for f in result.findings}
    # Both facts matter: the file changed, and the quote is gone because of it.
    assert "source-changed" in codes
    assert "quote-missing" in codes
    assert not result.ok


def test_quote_that_moved_pages_is_reported_not_waved_through(project: Path, manuscript: Path):
    source = project / "papers" / "2026_smith_networks.txt"
    source.write_text(
        "A new first page pushes everything down.\n\f\n"
        "We train the model on 154,391 sentences drawn from two corpora.\n"
        "The construction inventory totals 40,688 entries.\n",
        encoding="utf-8",
    )
    ledger, _findings = scan(ScanOptions(manuscript=str(manuscript), root=str(project)))
    assert ledger.claims
    result = verify(ledger, ScanOptions(manuscript=str(manuscript), root=str(project)))
    moved = [f for f in result.findings if f.code == "quote-moved"]
    assert moved, [f.code for f in result.findings]
    assert result.ok  # moving pages is a medium finding, not a blocker


def test_missing_source_file_is_reported(project: Path, manuscript: Path):
    ledger, _ = scan(ScanOptions(manuscript=str(manuscript), root=str(project)))
    (project / "papers" / "2026_smith_networks.txt").unlink()
    (project / "sources.toml").unlink()  # otherwise the manifest still names it
    result = verify(ledger, ScanOptions(manuscript=str(manuscript), root=str(project)))
    codes = {f.code for f in result.findings}
    assert codes & {"source-missing", "source-unreadable"}
    assert not result.ok


def test_page_hint_beyond_the_document_is_reported(project: Path):
    _write(project, "papers/tiny.txt", "one page only")
    _write(
        project,
        "sources.toml",
        '[sources]\ntiny = "papers/tiny.txt"\n',
    )
    manuscript = _write(
        project,
        "m.md",
        "```claim id=c1 source=tiny page=9\nquote: |\n  one page only\n```\n",
    )
    ledger, findings = scan(ScanOptions(manuscript=str(manuscript), root=str(project)))
    assert "page-out-of-range" in {f.code for f in findings}
    assert ledger.claims[0].page == 9


def test_unresolved_source_is_reported(project: Path):
    manuscript = _write(
        project,
        "m.md",
        "```claim id=c1 source=unknown2026\nquote: |\n  whatever text\n```\n",
    )
    _ledger, findings = scan(ScanOptions(manuscript=str(manuscript), root=str(project)))
    assert "source-missing" in {f.code for f in findings}


def test_bib_entries_are_loaded_into_the_ledger(project: Path, manuscript: Path):
    ledger, findings = scan(
        ScanOptions(
            manuscript=str(manuscript),
            root=str(project),
            bib=[str(project / "refs.bib")],
        )
    )
    assert "smith2026cxn" in ledger.entries
    assert "bib-key-unused" not in {f.code for f in findings}


def test_bib_key_used_by_a_claim_is_not_reported_unused(project: Path, manuscript: Path):
    ledger, _findings = scan(
        ScanOptions(
            manuscript=str(manuscript),
            root=str(project),
            bib=[str(project / "refs.bib")],
        )
    )
    result = verify(ledger, ScanOptions(manuscript=str(manuscript), root=str(project)))
    assert "bib-key-unused" not in {f.code for f in result.findings}


def test_unused_bib_entry_is_reported(project: Path, manuscript: Path):
    (project / "refs.bib").write_text(
        "@article{ghost2020, author={X}, title={Y}, journal={Z}, year={2020}}\n",
        encoding="utf-8",
    )
    ledger, _ = scan(
        ScanOptions(
            manuscript=str(manuscript),
            root=str(project),
            bib=[str(project / "refs.bib")],
        )
    )
    result = verify(ledger, ScanOptions(manuscript=str(manuscript), root=str(project)))
    assert "bib-key-unused" in {f.code for f in result.findings}


def test_claim_naming_an_unknown_bib_key_is_reported(project: Path):
    _write(project, "papers/p.txt", "some text here")
    _write(project, "sources.toml", '[sources]\np = "papers/p.txt"\n')
    _write(
        project,
        "refs.bib",
        "@article{real, author={A}, title={T}, journal={J}, year={2020}}\n",
    )
    manuscript = _write(
        project,
        "m.md",
        "```claim id=c1 source=p ref=phantom2020\nquote: |\n  some text here\n```\n",
    )
    ledger, _ = scan(
        ScanOptions(
            manuscript=str(manuscript),
            root=str(project),
            bib=[str(project / "refs.bib")],
        )
    )
    result = verify(ledger, ScanOptions(manuscript=str(manuscript), root=str(project)))
    assert "bib-key-missing" in {f.code for f in result.findings}


def test_ledger_round_trips_through_json(project: Path, manuscript: Path):
    ledger, _ = scan(ScanOptions(manuscript=str(manuscript), root=str(project)))
    payload = json.loads(json.dumps(ledger.to_json()))
    from citevouch.model import Ledger

    restored = Ledger.from_json(payload)
    assert restored.claims[0].id == ledger.claims[0].id
    assert restored.claims[0].quote_fingerprint == ledger.claims[0].quote_fingerprint
    assert restored.sources["smith2026cxn"].sha256 == ledger.sources["smith2026cxn"].sha256


def test_verify_against_a_ledger_built_from_json(project: Path, manuscript: Path):
    ledger, _ = scan(ScanOptions(manuscript=str(manuscript), root=str(project)))
    lock = project / "citevouch.lock.json"
    lock.write_text(json.dumps(ledger.to_json()), encoding="utf-8")
    from citevouch.model import Ledger

    restored = Ledger.from_json(json.loads(lock.read_text(encoding="utf-8")))
    result = verify(restored, ScanOptions(manuscript=str(manuscript), root=str(project)))
    assert result.ok
    assert result.verified == 1


def test_numbers_in_a_quote_that_are_absent_from_the_page_are_reported(project: Path):
    _write(project, "papers/p.txt", "We train on 154,391 corpora.")
    _write(project, "sources.toml", '[sources]\np = "papers/p.txt"\n')
    manuscript = _write(
        project,
        "m.md",
        "```claim id=c1 source=p\nquote: |\n  We train on 999,999 corpora.\n```\n",
    )
    ledger, _ = scan(ScanOptions(manuscript=str(manuscript), root=str(project)))
    result = verify(ledger, ScanOptions(manuscript=str(manuscript), root=str(project)))
    codes = {f.code for f in result.findings}
    # The words match apart from the number, so the number check is the one that
    # has to fire; a plain "quote missing" would hide which part is wrong.
    assert "number-absent-in-quote" in codes


def test_number_check_is_silent_when_the_page_has_the_number(project: Path):
    _write(project, "papers/p.txt", "It reports 40,688 constructions.")
    _write(project, "sources.toml", '[sources]\np = "papers/p.txt"\n')
    manuscript = _write(
        project,
        "m.md",
        "```claim id=c1 source=p\nquote: |\n  It reports 40,688 constructions.\n```\n",
    )
    _ledger, findings = scan(ScanOptions(manuscript=str(manuscript), root=str(project)))
    assert "number-absent-in-quote" not in {f.code for f in findings}


def test_scan_with_no_claims_is_clean(project: Path):
    manuscript = _write(project, "m.md", "Just prose, nothing to verify.\n")
    ledger, findings = scan(ScanOptions(manuscript=str(manuscript), root=str(project)))
    assert ledger.claims == []
    assert findings == []


def test_missing_manuscript_is_a_usage_error(project: Path):
    import pytest

    from citevouch.errors import UsageError

    with pytest.raises(UsageError):
        scan(ScanOptions(manuscript=str(project / "nope.md"), root=str(project)))


def test_the_manifest_subset_reads_sources_toml_without_tomllib(project: Path):
    # Python 3.10 has no tomllib, and sources.toml is what the README tells
    # people to write.  If the 3.10 fallback silently returned {}, every claim
    # would come back source-missing there and nowhere else - which is exactly
    # what CI caught once.  Exercise the fallback on whatever interpreter runs
    # the suite, so the next breakage shows up here and not only on 3.10.
    from citevouch.sources import _mini_toml

    text = (
        "# the sources manifest\n"
        "[sources]\n"
        'p = "papers/p.txt"  # trailing comment\n'
        "q = 'papers/q.txt'\n"
        'hash = "a#b.txt"\n'
    )
    assert _mini_toml(text) == {
        "sources": {
            "p": "papers/p.txt",
            "q": "papers/q.txt",
            "hash": "a#b.txt",
        }
    }

    try:
        import tomllib
    except ImportError:
        expected = None
    else:
        expected = tomllib.loads(text)
    if expected is not None:
        assert _mini_toml(text) == expected, "the 3.10 fallback drifted from tomllib"
