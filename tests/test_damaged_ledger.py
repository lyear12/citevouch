"""A damaged lockfile is refused, not half-read and not crashed on.

``model.Ledger.from_json`` used to trust every field.  A lockfile edited by hand,
truncated by a bad merge, or written by a script that assumed yesterday's shape
raised ``AttributeError``, ``TypeError`` or ``ValueError`` straight out of
``main`` -- and a Python interpreter exits **1** on an uncaught exception, which
in this tool means "findings reached the threshold".  Eighteen damaged shapes
crashed across ``report``, ``verify`` and ``check --use-recorded``; every one of
them was indistinguishable from a verdict.

Two rules are under test here:

1. Every shape this code cannot read in full produces exit **2** with a message
   that names the section and the key (``ledger claims[0] must be an object``),
   never a traceback, and never exit 1.
2. A shape that is merely *absent* -- ``claims: []``, a missing ``tool_version``,
   a ``page`` written as ``"7"`` -- still works.  A guard that refuses files the
   writer produces would be worse than the crash it replaced.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from citevouch.cli import main
from citevouch.errors import UsageError
from citevouch.model import SUPPORTED_SCHEMA, Ledger

NL = chr(10)


def _manuscript() -> str:
    return NL.join(
        [
            "# t",
            "",
            "```claim id=c1 source=a page=1",
            "quote: |",
            "  alpha beta gamma delta epsilon",
            "claim: |",
            "  the claim text",
            "```",
            "",
        ]
    )


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    (tmp_path / "a.txt").write_text(
        "alpha beta gamma delta epsilon and more words here to be a page." + NL,
        encoding="utf-8",
    )
    (tmp_path / "sources.toml").write_text(
        "[sources]" + NL + 'a = "a.txt"' + NL, encoding="utf-8"
    )
    (tmp_path / "m.md").write_text(_manuscript(), encoding="utf-8")
    return tmp_path


def _base() -> dict:
    return {
        "schema": SUPPORTED_SCHEMA,
        "manuscript": "m.md",
        "manuscript_sha256": "",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "tool_version": "0.0.0",
        "sources": {"a": {"key": "a", "path": "a.txt", "sha256": "x", "pages": 1}},
        "entries": {},
        "claims": [
            {
                "id": "c1",
                "text": "the claim text",
                "source": "a",
                "quote": "alpha beta",
                "page": 1,
                "path": "m.md",
                "line": 3,
                "marker": "",
                "ref": "",
                "numbers": [],
                "quote_fingerprint": "",
            }
        ],
    }


def _with(**change) -> dict:
    blob = _base()
    blob.update(change)
    return blob


def _claim(**change) -> dict:
    blob = _base()
    blob["claims"] = [dict(blob["claims"][0], **change)]
    return blob


# --- the shapes that crashed ------------------------------------------------


CRASHING = {
    "claims-hold-null": _with(claims=[None]),
    "claims-hold-a-string": _with(claims=["x"]),
    "claims-hold-a-number": _with(claims=[5]),
    "claims-hold-a-list": _with(claims=[[]]),
    "claims-hold-one-good-and-one-null": _with(claims=[_base()["claims"][0], None]),
    "claims-is-a-number": _with(claims=5),
    "claims-is-null": _with(claims=None),
    "source-value-is-null": _with(sources={"a": None}),
    "source-value-is-a-string": _with(sources={"a": "x"}),
    "entry-value-is-null": _with(entries={"k": None}),
    "entry-value-is-a-list": _with(entries={"k": []}),
    "entry-fields-is-a-number": _with(
        entries={"k": {"key": "k", "type": "article", "fields": 5, "line": 3}}
    ),
    "claim-numbers-is-a-number": _claim(numbers=5),
    "claim-numbers-hold-a-number": _claim(numbers=[1]),
    "claim-line-is-a-word": _claim(line="x"),
    "claim-line-is-a-fraction": _claim(line=1.5),
    "source-pages-is-a-word": _with(
        sources={"a": {"key": "a", "path": "a.txt", "sha256": "x", "pages": "x"}}
    ),
    "source-pages-is-a-fraction": _with(
        sources={"a": {"key": "a", "path": "a.txt", "sha256": "x", "pages": 1.5}}
    ),
    "entry-line-is-a-word": _with(
        entries={"k": {"key": "k", "type": "article", "fields": {}, "line": "x"}}
    ),
    "schema-is-a-fraction": _with(schema=1.5),
}


class TestEveryDamagedShapeIsRefused:
    @pytest.mark.parametrize("name", sorted(CRASHING))
    def test_it_raises_a_usage_error_and_not_a_builtin(self, name: str) -> None:
        with pytest.raises(UsageError):
            Ledger.from_json(CRASHING[name])

    @pytest.mark.parametrize("name", sorted(CRASHING))
    def test_the_message_names_the_section(self, name: str) -> None:
        with pytest.raises(UsageError) as caught:
            Ledger.from_json(CRASHING[name])
        message = str(caught.value)
        # The reader is looking at a JSON file with a hundred keys in it.  A
        # message that only says "the ledger is wrong" leaves them to find the
        # one damaged key by eye.
        assert "ledger" in message
        assert any(
            word in message for word in ("claims", "sources", "entries", "schema", "fields")
        ), message

    @pytest.mark.parametrize("name", sorted(CRASHING))
    def test_the_cli_turns_it_into_exit_two(self, name: str, project: Path) -> None:
        # Exit 1 is reserved for "findings reached the threshold".  A crash that
        # exited 1 would read as a verdict against the manuscript.
        (project / "citevouch.lock.json").write_text(
            json.dumps(CRASHING[name]), encoding="utf-8"
        )
        assert main(["report", "--root", str(project)]) == 2

    @pytest.mark.parametrize("name", sorted(CRASHING))
    def test_the_three_verbs_that_read_a_ledger_all_refuse(
        self, name: str, project: Path
    ) -> None:
        (project / "citevouch.lock.json").write_text(
            json.dumps(CRASHING[name]), encoding="utf-8"
        )
        for argv in (
            ["report", "--root", str(project)],
            ["verify", "m.md", "--root", str(project)],
            ["check", "m.md", "--use-recorded", "--root", str(project)],
        ):
            assert main(argv) == 2, " ".join(argv)

    @pytest.mark.parametrize("name", sorted(CRASHING))
    def test_the_message_says_which_file_is_damaged(
        self, name: str, project: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # A project holds a manuscript, a bibliography, a sources manifest and
        # a lockfile.  "ledger claims[0] must be an object" without the path
        # leaves the reader to guess which file to open -- and the shape message
        # alone is not a filename.
        capsys.readouterr()
        (project / "citevouch.lock.json").write_text(
            json.dumps(CRASHING[name]), encoding="utf-8"
        )
        assert main(["report", "--root", str(project)]) == 2
        printed = capsys.readouterr().err
        assert "citevouch.lock.json" in printed, printed
        assert "ledger" in printed


class TestTheThreeVerbsDoNotCrashAtAll:
    """A crash is a bug whatever exit code it produces.

    The parametrised tests above assert exit 2 through ``main``, which catches
    ``UsageError``.  If a later change made one of these raise something else,
    ``main`` would not catch it and the test process would see a traceback --
    but only for the shapes that happen to be in the table.  This test runs the
    three verbs in a subprocess, so an uncaught exception surfaces as a
    non-zero exit with a traceback on stderr rather than as a Python exception
    inside pytest's own interpreter.
    """

    def test_no_shape_produces_a_traceback(self, project: Path) -> None:
        for name, blob in sorted(CRASHING.items()):
            (project / "citevouch.lock.json").write_text(json.dumps(blob), encoding="utf-8")
            for argv in (["report"], ["verify", "m.md"], ["check", "m.md", "--use-recorded"]):
                done = subprocess.run(
                    [sys.executable, "-m", "citevouch", *argv],
                    cwd=project,
                    capture_output=True,
                    text=True,
                    env={
                        **os.environ,
                        "PYTHONPATH": str(Path(__file__).resolve().parent.parent / "src"),
                        "PYTHONIOENCODING": "utf-8",
                    },
                )
                assert "Traceback (most recent call last)" not in done.stderr, (
                    name,
                    argv,
                    done.stderr,
                )
                assert done.returncode == 2, (name, argv, done.returncode, done.stdout)


# --- the shapes that must keep working -------------------------------------


WORKING = {
    "no-claims-yet": _with(claims=[]),
    "no-version-string": {k: v for k, v in _base().items() if k != "tool_version"},
    "page-written-as-a-string": _claim(page="7"),
    "page-missing": {
        **_base(),
        "claims": [{k: v for k, v in _base()["claims"][0].items() if k != "page"}],
    },
    "numbers-null": _claim(numbers=None),
    "numbers-missing": {
        **_base(),
        "claims": [{k: v for k, v in _base()["claims"][0].items() if k != "numbers"}],
    },
    "sources-empty": _with(sources={}),
    "entries-empty": _with(entries={}),
    "no-sources-key": {k: v for k, v in _base().items() if k != "sources"},
    "no-entries-key": {k: v for k, v in _base().items() if k != "entries"},
    "fields-empty": _with(
        entries={"k": {"key": "k", "type": "article", "fields": {}, "line": 3}}
    ),
    "fields-missing": _with(entries={"k": {"key": "k", "type": "article", "line": 3}}),
    "schema-as-a-string": _with(schema="1"),
}


class TestAnAbsentFieldIsNotADamagedOne:
    @pytest.mark.parametrize("name", sorted(WORKING))
    def test_it_reads(self, name: str) -> None:
        ledger = Ledger.from_json(WORKING[name])
        assert isinstance(ledger, Ledger)

    @pytest.mark.parametrize("name", sorted(WORKING))
    def test_the_verbs_do_not_call_it_damaged(self, name: str, project: Path) -> None:
        (project / "citevouch.lock.json").write_text(
            json.dumps(WORKING[name]), encoding="utf-8"
        )
        code = main(["report", "--root", str(project)])
        assert code == 0, (name, code)

    def test_a_ledger_this_tool_writes_reads_back_unchanged(
        self, project: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # The end of the argument: the strictness above must not refuse a file
        # the writer produced.  Round-tripping is the one test that keeps a
        # hand-built fixture from standing in for the real shape.
        capsys.readouterr()
        assert main(["scan", "m.md", "--root", str(project)]) == 0
        written = json.loads((project / "citevouch.lock.json").read_text("utf-8"))
        assert Ledger.from_json(written).to_json() == written


def test_the_whole_shipped_round_trip_survives_a_move(project: Path) -> None:
    """Copy the project elsewhere and read it there: nothing may depend on cwd."""
    assert main(["scan", "m.md", "--root", str(project)]) == 0
    other = project.parent / (project.name + "-moved")
    shutil.copytree(project, other)
    assert main(["report", "--root", str(other)]) == 0


#: Depth that makes ``json.loads`` give up.  Measured on CPython 3.14: 2000
#: nested arrays decode, 20000 raise ``RecursionError: Stack overflow``.  The
#: number is a property of the interpreter's stack, not of this project, so the
#: test asks the file to be *deep enough to try*, not for one exact depth.
DEEP = 20000


class TestANestDeepEnoughToBreakTheParser:
    """The same wrong exit code, arriving through the parser instead of a key.

    ``_read_ledger`` caught ``ValueError`` around ``json.loads`` because that is
    what malformed JSON raises -- and for a file of balanced brackets it raises
    something else entirely.  ``json`` is a recursive-descent parser, so nesting
    burns interpreter stack until ``RecursionError``, which is not a
    ``ValueError``: it escaped ``main`` and the interpreter exited 1.  Measured
    before the fix::

        RecursionError: Stack overflow (used 2912 kB) while decoding a JSON
        array from a unicode string

    A lockfile is an input.  Balanced brackets it cannot survive are the same
    problem as an unbalanced brace, and get the same answer.
    """

    @staticmethod
    def _write(project: Path, depth: int) -> None:
        (project / "citevouch.lock.json").write_text(
            "[" * depth + "]" * depth, encoding="utf-8"
        )

    def test_a_deeply_nested_ledger_is_refused(self, project: Path) -> None:
        self._write(project, DEEP)
        assert main(["report", "--root", str(project)]) == 2

    def test_the_message_says_what_the_parser_hit(self, project: Path) -> None:
        # "is not readable JSON" alone would also be true of a typo, and the
        # author would go looking for one.  This file is balanced.
        self._write(project, DEEP)
        with pytest.raises(UsageError) as caught:
            from citevouch.cli import _read_ledger

            _read_ledger(project / "citevouch.lock.json")
        assert "nests too deeply" in str(caught.value)

    def test_the_three_verbs_that_read_a_ledger_all_refuse(self, project: Path) -> None:
        self._write(project, DEEP)
        for argv in (
            ["report", "--root", str(project)],
            ["verify", "m.md", "--root", str(project)],
            ["check", "m.md", "--use-recorded", "--root", str(project)],
        ):
            assert main(argv) == 2, " ".join(argv)

    def test_no_traceback_is_printed(self, project: Path) -> None:
        self._write(project, DEEP)
        done = subprocess.run(
            [sys.executable, "-m", "citevouch", "report", "--root", str(project)],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).parents[1] / "src")},
            check=False,
        )
        assert "Traceback (most recent call last)" not in done.stderr
        assert done.returncode == 2, done.stderr

    def test_a_nest_the_parser_survives_is_still_only_not_a_ledger(self, project: Path) -> None:
        # The boundary of the fix: nesting that decodes is judged on what it
        # decodes to, which is a list, not this tool's object.
        self._write(project, 200)
        with pytest.raises(UsageError) as caught:
            from citevouch.cli import _read_ledger

            _read_ledger(project / "citevouch.lock.json")
        assert "not a citevouch ledger" in str(caught.value)
