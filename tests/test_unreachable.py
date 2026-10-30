"""A path that cannot be reached is not a file that went missing.

Windows reports an unreachable share as ``ERROR_BAD_NETPATH`` (53) and an
absent path as ``ERROR_FILE_NOT_FOUND`` (3), and Python maps both to
``errno.ENOENT``.  So ``Path.exists()`` answers "no" to two different
questions and the difference has to come from the raw error.  These tests pin
the mapping down without needing a real share to be down, because a test that
needs a network outage to run is a test that never runs.
"""

from __future__ import annotations

import errno
from pathlib import Path

import pytest

from citevouch.errors import _WINERROR_UNREACHABLE, why_not_a_file
from citevouch.verify import _gone_sentence


def _oserror(errno_value: int, winerror: int | None = None) -> OSError:
    """An OSError carrying a specific ``winerror``, on any platform."""
    exc = OSError(errno_value, "synthetic")
    if winerror is not None:
        exc.winerror = winerror
    return exc


class TestTheTwoQuestionsStatsCannotTellApart:
    """``exists()`` is the wrong judge; the raw error is the right one."""

    def test_a_missing_file_is_called_missing(self, tmp_path: Path):
        assert why_not_a_file(tmp_path / "nope.md") == "does not exist"

    def test_a_directory_is_called_a_directory(self, tmp_path: Path):
        assert why_not_a_file(tmp_path) == "is a directory, not a file"

    def test_a_file_is_not_asked_about(self, tmp_path: Path):
        """The helper answers for paths that are *not* files; a file is a bug
        in the caller, not a sentence.  It still says something truthful."""
        target = tmp_path / "paper.md"
        target.write_text("x", encoding="utf-8")
        assert why_not_a_file(target) == "does not exist"


class TestTheWindowsNumbers:
    """Every ``winerror`` in the table names a location, not a file."""

    @pytest.mark.parametrize("winerror", sorted(_WINERROR_UNREACHABLE))
    def test_the_number_names_an_unreachable_location(self, winerror: int):
        answer = why_not_a_file(_Raising(_oserror(errno.ENOENT, winerror)))
        assert answer == (
            "cannot be reached (the network path is not available from here), "
            "which is not the same as missing"
        )

    def test_a_plain_missing_file_is_not_dragged_into_it(self):
        """``ERROR_FILE_NOT_FOUND`` is 3 and must stay missing."""
        answer = why_not_a_file(_Raising(_oserror(errno.ENOENT, 3)))
        assert answer == "does not exist"

    def test_the_table_is_not_silently_empty(self):
        """A mapping that matches nothing would make every test above vacuous."""
        assert len(_WINERROR_UNREACHABLE) >= 5


class TestThePosixNumbers:
    @pytest.mark.parametrize("name", ["ENETUNREACH", "EHOSTUNREACH", "ECONNREFUSED", "EIO"])
    def test_the_errno_names_an_unreachable_location(self, name: str):
        if not hasattr(errno, name):
            pytest.skip(f"this platform has no {name}")
        answer = why_not_a_file(_Raising(_oserror(getattr(errno, name))))
        assert answer == (
            "cannot be reached (the filesystem reports it is unavailable), "
            "which is not the same as missing"
        )

    def test_enoent_is_still_missing_on_posix(self):
        assert why_not_a_file(_Raising(_oserror(errno.ENOENT))) == "does not exist"


class _Raising:
    """A stand-in for a ``Path`` whose ``stat`` fails in a chosen way."""

    def __init__(self, exc: OSError) -> None:
        self._exc = exc

    def is_dir(self) -> bool:
        return False

    def __fspath__(self) -> str:
        raise AssertionError("the helper must not fall back to string paths")

    def __str__(self) -> str:
        return "<synthetic>"


_ORIGINAL_STAT = __import__("os").stat


@pytest.fixture(autouse=True)
def _stat_raises_for_the_stand_in(monkeypatch):
    import os

    def fake_stat(path, *args, **kwargs):
        if isinstance(path, _Raising):
            raise path._exc
        return _ORIGINAL_STAT(path, *args, **kwargs)

    monkeypatch.setattr(os, "stat", fake_stat)


class TestTheRecordedManuscriptThatIsNotAFile:
    """A directory named ``m.md`` passes ``exists()`` and then ``sha256_file``
    raises ``PermissionError``, which leaves ``main`` as a traceback with exit
    1 - and 1 is this tool's word for "the manuscript has findings".  The
    author then reads a crash as a verdict about their citations.
    """

    def _scanned(self, tmp_path: Path) -> Path:
        # Through the command, not the library function: `scan()` returns the
        # ledger and `cmd_scan` is what writes it, so a fixture that calls the
        # function records nothing and every later verb answers "no ledger".
        from citevouch.cli import main

        (tmp_path / "p.txt").write_text(
            "The corpus has 40,688 entries here.\n", encoding="utf-8", newline="\n"
        )
        (tmp_path / "sources.toml").write_text(
            '[sources]\np = "p.txt"\n', encoding="utf-8", newline="\n"
        )
        (tmp_path / "m.md").write_text(
            "```claim id=c1 source=p\n>> The corpus has 40,688 entries\n```\n",
            encoding="utf-8",
            newline="\n",
        )
        assert main(["scan", "m.md", "--root", str(tmp_path)]) == 0
        (tmp_path / "m.md").unlink()
        (tmp_path / "m.md").mkdir()
        return tmp_path

    def test_it_is_reported_and_not_raised(self, tmp_path: Path, capsys):
        from citevouch.cli import main

        root = self._scanned(tmp_path)
        code = main(["verify", "m.md", "--root", str(root)])
        captured = capsys.readouterr()
        assert code == 1
        assert "Traceback" not in captured.err
        assert "is now a directory" in captured.out

    def test_the_sentence_has_exactly_one_set_of_brackets(self, tmp_path: Path, capsys):
        """``cannot be opened (cannot be reached (the network path ...))`` is
        what a spliced fragment produces; a rewritten sentence does not nest."""

        gone = _gone_sentence(_Raising(_oserror(errno.ENOENT, 53)))
        assert gone.count("(") == 0
        assert "network path" in gone


def _stat_raises_for(monkeypatch, name: str, exc: OSError) -> None:
    """Make ``os.stat`` fail with ``exc`` for one path and behave elsewhere.

    The platform decides what an unreachable path looks like - Windows raises
    with ``winerror=53``, Linux has no such number - so a test that reaches a
    real dead host only runs on one of the three operating systems this project
    supports.  Supplying the error keeps the routing under test and the
    platform out of it.
    """
    import os

    import citevouch.errors as errors

    real_stat = os.stat

    def fake_stat(path, *args, **kwargs):
        try:
            text = os.fspath(path)
        except TypeError:
            text = None
        if text == name:
            raise exc
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(errors.os, "stat", fake_stat)


class TestTheCommandLineSaysIt:
    """The sentences are only worth writing if they reach the person running it."""

    def test_an_unreachable_manuscript_is_not_called_missing(
        self, tmp_path: Path, capsys, monkeypatch
    ):
        from citevouch.cli import main

        missing = str(tmp_path / "paper.md")
        _stat_raises_for(monkeypatch, missing, _oserror(errno.ENOENT, 53))
        code = main(["scan", missing, "--root", str(tmp_path)])
        err = capsys.readouterr().err
        assert code == 2
        assert "cannot be reached" in err
        assert "does not exist" not in err

    def test_an_unreachable_bib_is_not_called_missing(
        self, tmp_path: Path, capsys, monkeypatch
    ):
        from citevouch.cli import main

        (tmp_path / "m.md").write_text("no claim blocks here" + chr(10), encoding="utf-8")
        missing = str(tmp_path / "refs.bib")
        _stat_raises_for(monkeypatch, missing, _oserror(errno.ENOENT, 53))
        code = main(["draft", "m.md", "--root", str(tmp_path), "--bib", missing])
        err = capsys.readouterr().err
        assert code == 2
        assert "cannot be reached" in err
        assert "does not exist" not in err

    def test_an_ordinary_missing_manuscript_is_still_missing(self, tmp_path: Path, capsys):
        from citevouch.cli import main

        code = main(["scan", "nope.md", "--root", str(tmp_path)])
        err = capsys.readouterr().err
        assert code == 2
        assert "does not exist" in err
        assert "cannot be reached" not in err

    def test_a_directory_manuscript_is_called_a_directory(self, tmp_path: Path, capsys):
        from citevouch.cli import main

        (tmp_path / "adir").mkdir()
        code = main(["scan", "adir", "--root", str(tmp_path)])
        err = capsys.readouterr().err
        assert code == 2
        assert "is a directory, not a file" in err
