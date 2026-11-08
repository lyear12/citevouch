"""The read side of the ledger must judge the path before it judges the bytes.

``report --ledger adir`` used to say ``ledger adir is not readable JSON:
[Errno 13] Permission denied: 'adir'`` - a sentence about what is inside the
file, offered about a path whose problem is that it is not a file at all.  The
write side of the same command family already had the right sentence
(``adir is a directory, not a file``), so one command said two different things
about one mistake depending on whether it was reading or writing.

Measured before the fix, with a project whose ledger path is a directory:

    report --ledger adir   -> rc=2  ledger adir is not readable JSON: [Errno 13]
                                     Permission denied: 'adir'
    scan  --ledger adir    -> rc=2  adir is a directory, not a file

and with a ledger path under a file:

    report --ledger manuscript.md/x.json
        -> rc=2  no ledger at manuscript.md\\x.json; run `citevouch scan` first
    scan  --ledger manuscript.md/x.json
        -> rc=2  cannot write manuscript.md\\x.json: manuscript.md is a file,
                 not a directory

Both read-side sentences send the author to the wrong place: the first to the
JSON parser (there is no JSON), the second to `scan` (which then refuses with a
third sentence).  The fix is one judgement of the path, made once, before any
byte is read.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from citevouch.cli import main
from citevouch.errors import UsageError

NL = chr(10)
PAGE = "We collected 154,391 examples from the corpus." + NL
MANIFEST = "[sources]" + NL + 'paper = "page.txt"' + NL
GOOD = (
    "```claim id=c1 source=paper page=1"
    + NL
    + "quote: |"
    + NL
    + "  We collected 154,391 examples from the corpus."
    + NL
    + "```"
    + NL
)


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(MANIFEST, encoding="utf-8", newline=NL)
    (root / "manuscript.md").write_text(GOOD, encoding="utf-8", newline=NL)
    return root


class TestTheReadSideSaysWhatTheWriteSideSays:
    """One mistake, one sentence - whichever verb met it."""

    def test_a_directory_is_named_a_directory(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        (root / "bad.json").mkdir()
        assert main(["report", "--ledger", "bad.json", "--root", str(root)]) == 2
        err = capsys.readouterr().err
        assert "is a directory, not a file" in err, err
        # The sentence must not blame the JSON parser for a path problem.
        assert "not readable JSON" not in err, err

    @pytest.mark.parametrize(
        "argv",
        [
            ["report", "--ledger", "bad.json"],
            ["verify", "manuscript.md", "--ledger", "bad.json"],
            ["check", "manuscript.md", "--use-recorded", "--ledger", "bad.json"],
        ],
        ids=["report", "verify", "check"],
    )
    def test_every_reading_verb_says_the_same_thing(self, tmp_path: Path, capsys, argv):
        root = _project(tmp_path)
        (root / "bad.json").mkdir()
        assert main([*argv, "--root", str(root)]) == 2
        err = capsys.readouterr().err
        assert "is a directory, not a file" in err, err

    def test_the_two_verbs_agree_on_the_sentence(self, tmp_path: Path, capsys):
        """The write side already said it; the read side now says the same."""
        root = _project(tmp_path)
        (root / "bad.json").mkdir()
        assert main(["scan", "manuscript.md", "--root", str(root), "--ledger", "bad.json"]) == 2
        written = capsys.readouterr().err
        assert main(["report", "--ledger", "bad.json", "--root", str(root)]) == 2
        read = capsys.readouterr().err
        assert "is a directory, not a file" in written, written
        assert "is a directory, not a file" in read, read
        # Both name the same path, so a reader cannot think they are two files.
        assert "bad.json" in written and "bad.json" in read

    def test_a_ledger_under_a_file_names_the_file_in_the_way(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        assert main(["report", "--ledger", "manuscript.md/x.json", "--root", str(root)]) == 2
        err = capsys.readouterr().err
        assert "is a file, not a directory" in err, err
        # And it must not claim there is simply no ledger: there is no place to
        # put one, which is a different sentence and a different fix.
        assert "no ledger at" not in err, err

    def test_the_reading_verb_does_not_talk_about_writing(self, tmp_path: Path, capsys):
        """``cannot write`` about a read is advice for the wrong end of the pipe.

        The shape sentence is shared with the write side, so sharing it too
        literally made ``report`` say ``cannot write …: manuscript.md is a file,
        not a directory`` - a sentence whose verb sends the author to look at
        output paths when the ledger they asked to read is unreachable.
        """
        root = _project(tmp_path)
        assert main(["report", "--ledger", "manuscript.md/x.json", "--root", str(root)]) == 2
        err = capsys.readouterr().err
        assert "cannot read" in err, err
        assert "cannot write" not in err, err

    def test_a_ledger_that_is_simply_absent_still_says_run_scan(self, tmp_path: Path, capsys):
        """The one shape the old sentence was right about, unchanged."""
        root = _project(tmp_path)
        assert main(["report", "--ledger", "gone.json", "--root", str(root)]) == 2
        err = capsys.readouterr().err
        assert "no ledger at" in err, err
        assert "citevouch scan" in err, err


class TestTheReaderIsTheOnePlaceThatJudgesIt:
    """``_read_ledger`` is the only reader, so the judgement lives there once."""

    def test_the_helper_refuses_a_directory(self, tmp_path: Path):
        from citevouch.cli import _read_ledger

        root = _project(tmp_path)
        (root / "bad.json").mkdir()
        with pytest.raises(UsageError) as caught:
            _read_ledger(root / "bad.json")
        assert "is a directory, not a file" in str(caught.value)

    def test_the_helper_refuses_a_path_under_a_file(self, tmp_path: Path):
        from citevouch.cli import _read_ledger

        root = _project(tmp_path)
        with pytest.raises(UsageError) as caught:
            _read_ledger(root / "manuscript.md" / "x.json")
        assert "is a file, not a directory" in str(caught.value)

    def test_a_written_ledger_is_still_read(self, tmp_path: Path):
        """The guard must not become a wall: the normal path still works."""
        from citevouch.cli import _read_ledger

        root = _project(tmp_path)
        assert main(["scan", "manuscript.md", "--root", str(root)]) == 0
        ledger = _read_ledger(root / "citevouch.lock.json")
        assert [claim.id for claim in ledger.claims] == ["c1"]


class TestNoTracebackForAnyShape:
    """Exit 2 and a sentence, never a stack trace and never exit 1."""

    @pytest.mark.parametrize(
        "argv",
        [
            ["report", "--ledger", "bad.json"],
            ["verify", "manuscript.md", "--ledger", "bad.json"],
            ["check", "manuscript.md", "--use-recorded", "--ledger", "bad.json"],
        ],
        ids=["report", "verify", "check"],
    )
    def test_the_subprocess_exit_code_is_two(self, tmp_path: Path, argv):
        root = _project(tmp_path)
        (root / "bad.json").mkdir()
        env = {**os.environ, "PYTHONPATH": str(Path.cwd() / "src")}
        proc = subprocess.run(
            [sys.executable, "-m", "citevouch", *argv, "--root", str(root)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            cwd=str(root),
            timeout=120,
        )
        assert proc.returncode == 2, proc.stdout + proc.stderr
        assert "Traceback" not in proc.stderr, proc.stderr
