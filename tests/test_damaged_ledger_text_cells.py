"""A damaged text cell in the ledger must not become a verdict about the author.

``Ledger.from_json`` guarded every *structural* cell from the start (``claims``
must be a list, ``line`` must be a whole number, ``numbers`` must be strings)
and then read every *textual* one with ``str(entry.get(key, ""))``.  ``str()``
turns a ``null`` into the four characters ``None`` and a ``5`` into ``"5"``, so
a hand-edited or half-merged ledger arrived in the verifier looking like a
claim whose quote really is those characters:

    [high] quote-missing at m.md:1 (c1): None — quote not found (too short for
    a fuzzy comparison) in page.txt

Exit **1** means "findings reached the threshold" — a verdict on the
manuscript.  The page held the quoted sentence the whole time; the damaged
thing was the file.  ``docs`` and the module's own docstring say the one thing
that must not happen is a type problem escaping as exit 1, and this is that
thing wearing the clothes of a verdict.

The rule under test: a ledger text cell holds a string.  A key that is *absent*
keeps its existing meaning (the callers default it to ``""``); a key that is
present with something else is a damaged file, refused with exit 2 and a
message that names the cell.
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
B3 = chr(96) * 3
PAGE = "The corpus holds 40,688 examples of written English." + NL


def _manuscript() -> str:
    return NL.join(
        [
            B3 + "claim id=c1 source=paper page=1",
            "quote: |",
            "  The corpus holds 40,688 examples",
            B3,
            "",
        ]
    )


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    (tmp_path / "page.txt").write_text(PAGE, encoding="utf-8", newline=NL)
    (tmp_path / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    (tmp_path / "m.md").write_text(_manuscript(), encoding="utf-8", newline=NL)
    return tmp_path


def _base() -> dict:
    return {
        "schema": SUPPORTED_SCHEMA,
        "manuscript": "m.md",
        "manuscript_sha256": "",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "tool_version": "0.0.0",
        "sources": {"paper": {"key": "paper", "path": "page.txt", "sha256": "x", "pages": 1}},
        "entries": {},
        "claims": [
            {
                "id": "c1",
                "text": "",
                "source": "paper",
                "quote": "The corpus holds 40,688 examples",
                "page": 1,
                "path": "m.md",
                "line": 1,
                "marker": "",
                "ref": "",
                "numbers": ["40,688"],
                "quote_fingerprint": "",
            }
        ],
    }


#: One damaged entry per shape: where the cell lives in the blob, how to plant
#: it, and the words its message owes the reader.  Every one of these used to be
#: read as text instead.
DAMAGED: dict[str, tuple[tuple, callable]] = {
    "top-manuscript-null": (("manuscript",), lambda b: b.update(manuscript=None)),
    "top-manuscript-number": (("manuscript",), lambda b: b.update(manuscript=5)),
    "top-hash-list": (("manuscript_sha256",), lambda b: b.update(manuscript_sha256=["x"])),
    "source-key-null": (
        ("sources", "paper", "key"),
        lambda b: b["sources"]["paper"].update(key=None),
    ),
    "source-path-number": (
        ("sources", "paper", "path"),
        lambda b: b["sources"]["paper"].update(path=3),
    ),
    "claim-id-null": (("claims", 0, "id"), lambda b: b["claims"][0].update(id=None)),
    "claim-id-list": (("claims", 0, "id"), lambda b: b["claims"][0].update(id=["c1"])),
    "claim-quote-null": (("claims", 0, "quote"), lambda b: b["claims"][0].update(quote=None)),
    "claim-quote-number": (("claims", 0, "quote"), lambda b: b["claims"][0].update(quote=5)),
    "claim-quote-list": (("claims", 0, "quote"), lambda b: b["claims"][0].update(quote=["a"])),
    "claim-quote-object": (("claims", 0, "quote"), lambda b: b["claims"][0].update(quote={})),
    "claim-quote-true": (("claims", 0, "quote"), lambda b: b["claims"][0].update(quote=True)),
    "claim-text-null": (("claims", 0, "text"), lambda b: b["claims"][0].update(text=None)),
    "claim-source-null": (
        ("claims", 0, "source"),
        lambda b: b["claims"][0].update(source=None),
    ),
    "claim-source-number": (("claims", 0, "source"), lambda b: b["claims"][0].update(source=5)),
    "claim-path-null": (("claims", 0, "path"), lambda b: b["claims"][0].update(path=None)),
    "claim-marker-number": (("claims", 0, "marker"), lambda b: b["claims"][0].update(marker=7)),
    "claim-ref-number": (("claims", 0, "ref"), lambda b: b["claims"][0].update(ref=7)),
}


def _blob(name: str) -> dict:
    blob = _base()
    DAMAGED[name][1](blob)
    return blob


def _planted(blob: dict, path: tuple):
    node = blob
    for step in path:
        node = node[step]
    return node


def _where(path: tuple) -> str:
    """The cell name a message should carry, e.g. ``claims[0].quote``.

    A mapping key is written the way the reader of the JSON file writes it -
    quoted inside brackets - because that is the spelling the existing guard
    helpers already use (``sources['paper']``), and one message style for one
    family of messages is worth more than the shorter dotted spelling.
    """
    out = str(path[0])
    last = len(path) - 1
    for position, step in enumerate(path[1:], start=1):
        if position == last:
            out += f".{step}"
        elif isinstance(step, int):
            out += f"[{step}]"
        else:
            out += f"[{step!r}]"
    return out


class TestEveryDamagedTextCellIsRefused:
    @pytest.mark.parametrize("name", sorted(DAMAGED))
    def test_it_is_a_usage_error(self, name: str) -> None:
        with pytest.raises(UsageError):
            Ledger.from_json(_blob(name))

    @pytest.mark.parametrize("name", sorted(DAMAGED))
    def test_the_message_names_the_cell(self, name: str) -> None:
        path = DAMAGED[name][0]
        with pytest.raises(UsageError) as caught:
            Ledger.from_json(_blob(name))
        message = str(caught.value)
        assert _where(path) in message, message
        assert "must be a string" in message, message

    @pytest.mark.parametrize("name", sorted(DAMAGED))
    def test_the_message_names_the_type_it_found(self, name: str) -> None:
        blob = _blob(name)
        # The type is whatever the test planted; the message has to say which,
        # otherwise "the ledger is wrong" leaves the reader hunting by eye.
        expected = type(_planted(blob, DAMAGED[name][0])).__name__
        with pytest.raises(UsageError) as caught:
            Ledger.from_json(blob)
        assert expected in str(caught.value), str(caught.value)


class TestTheVerdictNeverReachesTheAuthor:
    """The point of the whole guard: no verdict-shaped sentence, and no exit 1."""

    @pytest.mark.parametrize("name", sorted(DAMAGED))
    def test_the_three_verbs_refuse_it(self, name: str, project: Path) -> None:
        (project / "citevouch.lock.json").write_text(
            json.dumps(_blob(name)), encoding="utf-8", newline=NL
        )
        for argv in (
            ["report", "--root", str(project)],
            ["check", "m.md", "--root", str(project), "--use-recorded"],
            ["verify", "m.md", "--root", str(project)],
        ):
            assert main(argv) == 2, (name, argv)

    @pytest.mark.parametrize("name", ["claim-quote-null", "claim-quote-number"])
    def test_it_does_not_accuse_the_author(self, name: str, project: Path) -> None:
        # Measured before the guard: ``[high] quote-missing … None — quote not
        # found … in page.txt``, exit 1.  The page has the sentence.
        (project / "citevouch.lock.json").write_text(
            json.dumps(_blob(name)), encoding="utf-8", newline=NL
        )
        done = _cli(project, "check", "m.md", "--use-recorded")
        assert done.returncode == 2, done.stdout
        assert "quote-missing" not in done.stdout, done.stdout
        assert "quote-found" not in done.stdout, done.stdout

    @pytest.mark.parametrize("name", ["claim-source-null", "claim-source-number"])
    def test_it_does_not_invent_a_vanished_source(self, name: str, project: Path) -> None:
        (project / "citevouch.lock.json").write_text(
            json.dumps(_blob(name)), encoding="utf-8", newline=NL
        )
        done = _cli(project, "check", "m.md", "--use-recorded")
        assert done.returncode == 2, done.stdout
        assert "source-missing" not in done.stdout, done.stdout

    def test_report_does_not_print_the_word_none_as_a_filename(self, project: Path) -> None:
        (project / "citevouch.lock.json").write_text(
            json.dumps(_blob("top-manuscript-null")), encoding="utf-8", newline=NL
        )
        done = _cli(project, "report")
        assert done.returncode == 2, done.stdout
        assert "— None" not in done.stdout, done.stdout


class TestTheShapesThatMustKeepWorking:
    def test_an_absent_key_is_still_absent(self) -> None:
        # Absent and null are not the same file: a ledger written before a key
        # existed has no key, and that keeps working.
        blob = _base()
        for key in ("marker", "ref", "quote_fingerprint", "text"):
            blob["claims"][0].pop(key)
        ledger = Ledger.from_json(blob)
        assert ledger.claims[0].marker == ""
        assert ledger.claims[0].ref == ""

    def test_the_whole_run_still_writes_a_ledger_it_can_read(self, project: Path) -> None:
        assert main(["scan", "m.md", "--root", str(project)]) == 0
        written = json.loads((project / "citevouch.lock.json").read_text("utf-8"))
        assert Ledger.from_json(written).to_json() == written

    def test_an_ordinary_ledger_still_verifies(self, project: Path) -> None:
        assert main(["scan", "m.md", "--root", str(project)]) == 0
        assert main(["check", "m.md", "--root", str(project), "--use-recorded"]) == 0


# --- helpers ---------------------------------------------------------------


def _cli(project: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    """Run one command in a fresh interpreter, so exit codes are real ones.

    ``**os.environ`` is not decoration: ``env=`` replaces the whole
    environment, and on Windows a child without ``SYSTEMROOT`` aborts in
    ``_Py_HashRandomization_Init`` before it can report anything.  The first
    version of this helper handed over a two-key dict, which passed on the
    three Linux and macOS cells and failed four assertions on Windows 3.10.
    """
    env = {
        **os.environ,
        "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
        "PYTHONIOENCODING": "utf-8",
    }
    return subprocess.run(
        [sys.executable, "-m", "citevouch", *argv, "--root", str(project)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=str(project),
    )


def _cleanup(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
