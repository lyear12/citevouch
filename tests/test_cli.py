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


def test_init_demo_writes_a_project_that_the_documented_next_command_accepts(tmp_path):
    # The first command in the README has to lead somewhere. init-demo once
    # stopped after writing the files, so `verify` - the command the README
    # shows next - failed with "no ledger". That reached the README, the
    # acceptance job and the release smoke test before a test existed here.
    target = tmp_path / "my-paper"
    assert main(["init-demo", str(target)]) == 0
    assert (target / "citevouch.lock.json").is_file(), "init-demo must record a ledger"

    # standing in the new directory, exactly as the README has the user do
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.chdir(target)
        assert main(["verify", "manuscript.md"]) == 0
    finally:
        monkeypatch.undo()


def test_init_demo_refuses_a_directory_that_already_has_something(tmp_path):
    target = tmp_path / "my-paper"
    target.mkdir()
    (target / "notes.txt").write_text("mine\n", encoding="utf-8")
    assert main(["init-demo", str(target)]) == 2
    assert (target / "notes.txt").read_text(encoding="utf-8") == "mine\n"
    assert not (target / "manuscript.md").exists()


def _write_ledger_with_schema(root: Path, schema: object) -> Path:
    path = root / "citevouch.lock.json"
    main(["scan", "m.md", "--root", str(root), "--quiet"])
    blob = json.loads(path.read_text(encoding="utf-8"))
    blob["schema"] = schema
    path.write_text(json.dumps(blob), encoding="utf-8")
    return path


def test_a_ledger_from_the_future_is_refused_not_guessed(tmp_path: Path, capsys):
    """A schema this code has never seen would half-parse: added or renamed
    fields come back empty, and "source-missing" on a half-read claim is a
    false verdict from the one tool that exists to avoid those. Refuse the
    file, exit 2, and name the fix."""
    root = _project(tmp_path)
    _write_ledger_with_schema(root, 2)
    assert main(["verify", "m.md", "--root", str(root)]) == 2
    err = capsys.readouterr().err
    assert "schema 2" in err
    assert "upgrade citevouch" in err


def test_a_ledger_without_a_schema_key_is_still_readable(tmp_path: Path):
    """Silence where there is nothing wrong: the default schema must not start
    refusing files written before the field meant anything."""
    root = _project(tmp_path)
    path = _write_ledger_with_schema(root, None)
    blob = json.loads(path.read_text(encoding="utf-8"))
    del blob["schema"]
    path.write_text(json.dumps(blob), encoding="utf-8")
    assert main(["verify", "m.md", "--root", str(root)]) == 0


def test_a_non_numeric_schema_is_a_usage_error(tmp_path: Path, capsys):
    root = _project(tmp_path)
    _write_ledger_with_schema(root, "two")
    assert main(["verify", "m.md", "--root", str(root)]) == 2
    assert "non-numeric schema" in capsys.readouterr().err


class TestTheTableIsATable:
    """`report` had no test at all, so it had two defects nobody had seen.

    Its rows escaped `|` in the quote and nowhere else, so a claim id holding a
    pipe ended the column and every row below it shifted.  And the summary line
    pluralised by appending an "s", which printed "0 entrys" on the demo - the
    one project in this repository - where anybody would have seen it.
    """

    MANUSCRIPT = "```claim id=c|1 source=s\nWe train on two corpora | and one pipe.\n```\n"

    def _project(self, root):
        root.mkdir(parents=True, exist_ok=True)
        (root / "sources.toml").write_text(
            '[sources]\ns = "s.txt"\n', encoding="utf-8", newline="\n"
        )
        (root / "s.txt").write_text(
            "We train on two corpora | and one pipe.\n", encoding="utf-8", newline="\n"
        )
        (root / "manuscript.md").write_text(self.MANUSCRIPT, encoding="utf-8", newline="\n")
        return root

    @staticmethod
    def _columns(line):
        """Count the separators, not the pipes.

        An escaped pipe is visible to `str.count` and is not a column edge,
        so counting raw pipes fails the very fix it should be checking.
        """
        unescaped = line.replace("\\\\", chr(0)).replace("\\|", chr(0))
        return unescaped.count("|")

    def _report(self, root, capsys):
        assert main(["scan", str(root / "manuscript.md"), "--root", str(root)]) == 0
        capsys.readouterr()
        assert main(["report", "--root", str(root)]) == 0
        return capsys.readouterr().out

    def test_a_pipe_inside_a_cell_does_not_add_a_column(self, tmp_path, capsys):
        out = self._report(self._project(tmp_path / "p"), capsys)
        rows = [ln for ln in out.split("\n") if ln.startswith("| ")]
        assert len({self._columns(ln) for ln in rows}) == 1, out

    def test_the_pipe_the_reader_sees_is_escaped(self, tmp_path, capsys):
        out = self._report(self._project(tmp_path / "p"), capsys)
        assert "c" + chr(92) + "|1" in out
        assert "corpora " + chr(92) + "| and" in out

    def test_an_empty_bibliography_is_not_called_entrys(self, tmp_path, capsys):
        out = self._report(self._project(tmp_path / "p"), capsys)
        assert "0 entries" in out
        assert "entrys" not in out

    def test_every_row_of_the_demo_has_the_same_shape(self, capsys):
        demo = Path(__file__).resolve().parent.parent / "demo"
        assert main(["report", "--root", str(demo)]) == 0
        out = capsys.readouterr().out
        assert "entrys" not in out
        rows = [ln for ln in out.split("\n") if ln.startswith("| ")]
        assert len({self._columns(ln) for ln in rows}) == 1, out


class TestAPathThatCannotBeWrittenIsAUsageError:
    """The exit code has to say "bad path", not "your manuscript failed".

    Every one of these used to escape ``main`` as an ``OSError`` traceback and
    exit 1 - and 1 is the code this tool reserves for "findings reached the
    --fail-on threshold". A CI job could not tell a mistyped ``--ledger`` from a
    paper whose quotes were wrong, which is exactly the confusion the whole exit
    contract exists to prevent. The read path already turned ``OSError`` into a
    usage error; these are the write paths, which did not.
    """

    def test_a_ledger_that_is_a_directory_is_refused(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        (root / "adir").mkdir()
        assert main(["scan", "m.md", "--root", str(root), "--ledger", "adir"]) == 2
        assert "is a directory" in capsys.readouterr().err

    def test_a_ledger_under_a_file_is_refused(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        assert main(["scan", "m.md", "--root", str(root), "--ledger", "m.md/x.json"]) == 2
        assert "is a file, not a directory" in capsys.readouterr().err

    def test_a_draft_output_under_a_file_is_refused(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        assert main(["draft", "m.md", "--root", str(root), "-o", "m.md/x.md"]) == 2
        assert "is a file, not a directory" in capsys.readouterr().err

    def test_no_traceback_reaches_the_caller(self, tmp_path: Path, capsys):
        """Exit 2 and a sentence, not a stack trace.

        A traceback is not merely ugly here: ``python -m citevouch`` would exit
        1 for it, and 1 is a verdict. The assertion is on the message shape
        because that is the part a caller pastes into a bug report.
        """
        root = _project(tmp_path)
        (root / "adir").mkdir()
        for argv in (
            ["scan", "m.md", "--root", str(root), "--ledger", "adir"],
            ["scan", "m.md", "--root", str(root), "--ledger", "m.md/x.json"],
            ["draft", "m.md", "--root", str(root), "-o", "m.md/x.md"],
        ):
            assert main(argv) == 2, argv
            err = capsys.readouterr().err
            assert "Traceback" not in err, argv
            assert err.startswith("citevouch: "), argv

    def test_the_directory_is_still_a_directory_afterwards(self, tmp_path: Path, capsys):
        """A refused write leaves the target alone and no staging file behind.

        ``scan`` stages the ledger as ``<name>.tmp`` and replaces it. The guard
        runs on the final name before the temporary file is created, so a
        refusal must leave no ``.tmp`` beside it. Asserted as those two facts
        rather than as a whole-directory listing: ``scan`` extracts pages before
        it writes anything, so the ``.citevouch`` cache directory is there
        either way and a listing assertion would be testing that instead.
        """
        root = _project(tmp_path)
        (root / "adir").mkdir()
        assert main(["scan", "m.md", "--root", str(root), "--ledger", "adir"]) == 2
        capsys.readouterr()
        assert (root / "adir").is_dir()
        assert not (root / "adir.tmp").exists()


class TestAMessageAboutAPathIsTrueAboutThatPath:
    """``is_file()`` judged the path; ``exists()`` wrote the sentence.

    A directory is not a file, so it cannot be a bib file - but it does exist,
    and the finding said it did not. The author then goes looking for a file
    that was never missing. ``sources.py`` already worded this distinction for
    source files; these were the places that did not.
    """

    def test_a_directory_bib_is_said_to_be_a_directory(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        (root / "adir").mkdir()
        assert main(["check", "m.md", "--root", str(root), "--bib", "adir"]) == 1
        out = capsys.readouterr().out
        assert "is a directory, not a file" in out
        assert "does not exist" not in out

    def test_a_missing_bib_is_still_said_to_be_missing(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        assert main(["check", "m.md", "--root", str(root), "--bib", "nope.bib"]) == 1
        out = capsys.readouterr().out
        assert "does not exist" in out
        assert "is a directory" not in out

    def test_draft_words_a_directory_bib_the_same_way(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        (root / "adir").mkdir()
        assert main(["draft", "m.md", "--root", str(root), "--bib", "adir"]) == 2
        assert "is a directory, not a file" in capsys.readouterr().err

    def test_a_bad_source_path_is_refused_rather_than_dropped(self, tmp_path: Path, capsys):
        """Silence here costs a false ``source-missing`` two steps later."""
        root = _project(tmp_path)
        (root / "adir").mkdir()
        assert main(["check", "m.md", "--root", str(root), "--source", "adir"]) == 2
        err = capsys.readouterr().err
        assert "is a directory, not a file" in err
        assert "Traceback" not in err


class TestTheReportAgreesWithTheExitCode:
    """A report is read by somebody who did not trust the exit code alone.

    `render_markdown` used to decide its two headings from severity: `high`
    under Blocking, everything else under Other.  The thing that actually
    fails a run is `--fail-on`, so at `--fail-on medium` the report put the
    only reason for a red build under Other.  The unit tests of the renderer
    pass `fail_on` directly, which means they would all still pass if `main`
    forgot to hand it over - so this goes through the command line.
    """

    def _project(self, root):
        root.mkdir(parents=True, exist_ok=True)
        (root / "s.txt").write_text(
            "A plain sentence with nothing special in it." + chr(10),
            encoding="utf-8",
            newline=chr(10),
        )
        (root / "sources.toml").write_text(
            "[sources]" + chr(10) + 's = "s.txt"' + chr(10), encoding="utf-8", newline=chr(10)
        )
        # A page hint that is not a number is a medium finding: the quote is
        # still located, the instruction was ignored.
        (root / "manuscript.md").write_text(
            "```claim id=c1 source=s page=banana"
            + chr(10)
            + ">> A plain sentence with nothing special in it."
            + chr(10)
            + "```"
            + chr(10),
            encoding="utf-8",
            newline=chr(10),
        )
        return root

    def test_the_blocking_section_follows_the_threshold(self, tmp_path: Path, capsys):
        root = self._project(tmp_path)
        for threshold, should_block in (("high", False), ("medium", True), ("info", True)):
            capsys.readouterr()
            code = main(
                [
                    "check",
                    "manuscript.md",
                    "--root",
                    str(root),
                    "--format",
                    "markdown",
                    "--fail-on",
                    threshold,
                ]
            )
            out = capsys.readouterr().out
            assert ("### Blocking" in out) is should_block, (threshold, out)
            assert (code == 1) is should_block, (threshold, code)
