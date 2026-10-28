"""CLI contract: exit codes, formats, and what happens on bad input."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from citevouch.cli import main


def _project(tmp_path: Path) -> Path:
    (tmp_path / "papers").mkdir()
    (tmp_path / "papers" / "p.txt").write_text(
        "We train on two corpora.\nThe inventory has 40,688 entries.\n",
        encoding="utf-8",
    )
    (tmp_path / "sources.toml").write_text('[sources]\np = "papers/p.txt"\n', encoding="utf-8")
    (tmp_path / "refs.bib").write_text(
        "@article{paper, author={A}, title={T}, journal={J}, year={2026}}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.md").write_text(
        "```claim id=c1 source=p\nquote: |\n  We train on two corpora.\n```\n",
        encoding="utf-8",
    )
    return tmp_path


def test_scan_writes_a_ledger_and_exits_zero(tmp_path: Path, capsys):
    root = _project(tmp_path)
    code = main(["scan", "m.md", "--root", str(root)])
    assert code == 0
    ledger = json.loads((root / "citevouch.lock.json").read_text(encoding="utf-8"))
    assert ledger["claims"][0]["id"] == "c1"
    assert ledger["manuscript_sha256"]


def test_scan_is_stable_across_runs(tmp_path: Path):
    root = _project(tmp_path)
    main(["scan", "m.md", "--root", str(root)])
    first = (root / "citevouch.lock.json").read_text(encoding="utf-8")
    main(["scan", "m.md", "--root", str(root)])
    second = (root / "citevouch.lock.json").read_text(encoding="utf-8")
    # generated_at changes, everything else must not: a ledger that churns on
    # every run makes every commit look meaningful.
    a, b = json.loads(first), json.loads(second)
    for key in ("generated_at",):
        a.pop(key, None)
        b.pop(key, None)
    assert a == b


def test_verify_clean_project_exits_zero(tmp_path: Path):
    root = _project(tmp_path)
    main(["scan", "m.md", "--root", str(root)])
    assert main(["verify", "m.md", "--root", str(root)]) == 0


def test_verify_after_the_manuscript_changed_exits_one(tmp_path: Path, capsys):
    root = _project(tmp_path)
    main(["scan", "m.md", "--root", str(root)])
    (root / "m.md").write_text(
        "```claim id=c1 source=p\nquote: |\n  We train on two corpora.\n```\n\nmore prose\n",
        encoding="utf-8",
    )
    assert main(["verify", "m.md", "--root", str(root)]) == 1
    assert "ledger-stale" in capsys.readouterr().out


def test_allow_stale_downgrades_the_exit_code(tmp_path: Path):
    root = _project(tmp_path)
    main(["scan", "m.md", "--root", str(root)])
    (root / "m.md").write_text(
        (root / "m.md").read_text(encoding="utf-8") + "\nprose\n", encoding="utf-8"
    )
    assert main(["verify", "m.md", "--root", str(root), "--allow-stale"]) == 0


def test_check_without_a_ledger_works(tmp_path: Path):
    root = _project(tmp_path)
    assert main(["check", "m.md", "--root", str(root)]) == 0
    assert not (root / "citevouch.lock.json").exists()


def test_check_use_recorded_verifies_the_committed_ledger(tmp_path: Path):
    root = _project(tmp_path)
    main(["scan", "m.md", "--root", str(root)])
    assert main(["check", "m.md", "--root", str(root), "--use-recorded"]) == 0


def test_check_use_recorded_without_a_ledger_is_a_usage_error(tmp_path: Path, capsys):
    root = _project(tmp_path)
    assert main(["check", "m.md", "--root", str(root), "--use-recorded"]) == 2
    assert "no ledger" in capsys.readouterr().err


def test_missing_manuscript_is_a_usage_error(tmp_path: Path, capsys):
    root = _project(tmp_path)
    assert main(["scan", "nope.md", "--root", str(root)]) == 2
    assert "citevouch:" in capsys.readouterr().err


def test_corrupt_ledger_is_a_usage_error(tmp_path: Path, capsys):
    root = _project(tmp_path)
    (root / "citevouch.lock.json").write_text("{not json", encoding="utf-8")
    assert main(["verify", "m.md", "--root", str(root)]) == 2
    assert "not readable JSON" in capsys.readouterr().err


def test_json_format_is_parseable(tmp_path: Path, capsys):
    root = _project(tmp_path)
    main(["check", "m.md", "--root", str(root), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["findings"][0]["code"] == "quote-found"
    assert payload["worst"] == "info"


def test_sarif_format_has_the_required_shape(tmp_path: Path, capsys):
    root = _project(tmp_path)
    main(["check", "m.md", "--root", str(root), "--format", "sarif"])
    doc = json.loads(capsys.readouterr().out)
    assert doc["version"] == "2.1.0"
    run = doc["runs"][0]
    assert run["tool"]["driver"]["name"] == "citevouch"
    assert run["results"][0]["ruleId"] == "quote-found"


def test_markdown_format_has_a_heading(tmp_path: Path, capsys):
    root = _project(tmp_path)
    main(["check", "m.md", "--root", str(root), "--format", "markdown"])
    assert capsys.readouterr().out.startswith("## citevouch evidence report")


def test_quiet_hides_info_lines(tmp_path: Path, capsys):
    root = _project(tmp_path)
    main(["check", "m.md", "--root", str(root), "--quiet"])
    assert "quote-found" not in capsys.readouterr().out


def test_fail_on_medium_catches_a_changed_source_that_still_verifies(tmp_path: Path):
    root = _project(tmp_path)
    main(["scan", "m.md", "--root", str(root)])
    # Append to the source: the file changed (medium) but the quote is intact,
    # so the default --fail-on high must stay at 0 and --fail-on medium must not.
    (root / "papers" / "p.txt").write_text(
        "We train on two corpora.\nThe inventory has 40,688 entries.\nA new footnote.\n",
        encoding="utf-8",
    )
    assert main(["verify", "m.md", "--root", str(root), "--allow-stale"]) == 0
    assert (
        main(
            [
                "verify",
                "m.md",
                "--root",
                str(root),
                "--allow-stale",
                "--fail-on",
                "medium",
            ]
        )
        == 1
    )


def test_report_prints_a_table(tmp_path: Path, capsys):
    root = _project(tmp_path)
    main(["scan", "m.md", "--root", str(root)])
    capsys.readouterr()
    assert main(["report", "--root", str(root)]) == 0
    out = capsys.readouterr().out
    assert "| claim | source | page | quote |" in out
    assert "`c1`" in out


def test_version_flag_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "citevouch" in capsys.readouterr().out


def test_no_subcommand_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_a_console_that_cannot_encode_the_manuscript_still_reports(tmp_path: Path, monkeypatch):
    """A Windows console on a legacy codepage must not turn findings into a crash.

    The manifest here is Chinese, because that is how the author writes, and the
    finding quotes the marker back at them.  The output stream is cp1252, which
    cannot represent it.  The exit code is the contract a CI job reads, so the
    run has to finish with one.
    """
    root = _project(tmp_path)
    (root / "m.md").write_text(
        "```claim id=c1 source=p\nquote: |\n  We train on two corpora.\n```\n\n"
        "【原文】这句断言还没有绑定证据。\n",
        encoding="utf-8",
    )
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", stream)

    assert main(["check", "m.md", "--root", str(root)]) == 0
    stream.flush()
    payload = raw.getvalue()
    # Redirected output is UTF-8: whoever reads the redirect expects that, and a
    # Chinese finding re-encoded to the local codepage is unreadable to them.
    assert "【原文】".encode() in payload
    assert b"claim-without-evidence" in payload
