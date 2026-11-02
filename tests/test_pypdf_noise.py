"""pypdf's warnings about a broken file must not reach the reader's console.

pypdf reports a damaged file twice: it logs (``pypdf._reader`` warns
``invalid pdf header: b'not a'`` and ``EOF marker not found``) and then it
raises.  The raise is caught and turned into a finding that says the same thing
with more detail, so the log lines are a worse copy of a fact the author is
already getting - delivered on stderr, next to a run that exits 1.

Measured before the fix: one unreadable source in a project put four lines of
pypdf's warnings around the single line citevouch wrote.

The assertions here count *log records*, not stderr text.  Redirecting stderr
does not see them: logging resolves its stream from a handler, and pytest
installs one on the root logger, so a test that reads ``sys.stderr`` passes
whether or not the code under test logs anything.  Both mutations that removed
the silencing survived exactly that way in the first draft of this file.
"""

from __future__ import annotations

import contextlib
import io
import logging
from pathlib import Path

import pytest

from citevouch import sources
from citevouch.cli import main

B3 = "`" * 3
NOT_A_PDF = b"not a pdf at all, just text\n"


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "papers").mkdir(parents=True)
    (root / "papers" / "broken.pdf").write_bytes(NOT_A_PDF)
    (root / "sources.toml").write_text(
        '[sources]\npaper = "papers/broken.pdf"\n', encoding="utf-8", newline="\n"
    )
    (root / "m.md").write_text(
        f"# T\n\n{B3}claim id=c1 source=paper page=1\n"
        "quote: |\n  alpha beta gamma delta\n"
        f"{B3}\n",
        encoding="utf-8",
        newline="\n",
    )
    return root


def _run(root: Path, *extra: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(["check", "m.md", "--root", str(root), "--no-cache", *extra])
        except SystemExit as exc:  # pragma: no cover - main returns, it does not exit
            code = exc.code if isinstance(exc.code, int) else 1
    return code, out.getvalue(), err.getvalue()


@contextlib.contextmanager
def _record_pypdf():
    """Collect every log record pypdf would emit, at any level."""
    records: list[str] = []

    class Collect(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record.getMessage())

    handler = Collect()
    pypdf_logger = logging.getLogger("pypdf")
    pypdf_logger.addHandler(handler)
    previous = pypdf_logger.level
    # A handler only sees what the level lets through; a caller who wants these
    # messages would have configured exactly this, and the code under test is
    # supposed to silence its own reads on top of it.
    pypdf_logger.setLevel(logging.DEBUG)
    try:
        yield records
    finally:
        pypdf_logger.removeHandler(handler)
        pypdf_logger.setLevel(previous)


class TestTheWarningIsSuppressed:
    def test_a_broken_pdf_logs_nothing_through_pypdf(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        with _record_pypdf() as records:
            code, _, _ = _run(root)
        assert code == 1, "an unreadable source is a high finding, so the run fails"
        assert records == [], f"pypdf's own warnings leaked: {records!r}"

    def test_the_verdict_still_says_what_is_wrong(self, tmp_path: Path) -> None:
        _, out, _ = _run(_project(tmp_path))
        assert "source-unreadable" in out
        assert "not a document this tool can open" in out

    def test_the_message_reader_does_not_log_either(self, tmp_path: Path) -> None:
        """The second read - the one that asks each reader why - is silenced too."""
        broken = _project(tmp_path) / "papers" / "broken.pdf"
        with _record_pypdf() as records:
            sources._why_both_refused(broken)
        assert records == [], f"the diagnosis itself logged: {records!r}"


class TestTheSilencingIsScoped:
    """The suppression belongs to the read that expects trouble, not the process."""

    def test_the_logger_level_is_restored(self, tmp_path: Path) -> None:
        logger = logging.getLogger("pypdf")
        logger.setLevel(logging.NOTSET)
        _run(_project(tmp_path))
        assert logger.level == logging.NOTSET, "the level must not stay lowered after the read"

    def test_it_is_restored_even_when_the_read_raises(self) -> None:
        logger = logging.getLogger("pypdf")
        # Establish the level the test compares against, instead of reading it:
        # a previous test that left ERROR behind would make "restored" and
        # "never restored" the same observation.
        logger.setLevel(logging.NOTSET)
        with pytest.raises(RuntimeError):
            with sources._quiet_pypdf():
                assert logger.level == logging.ERROR
                raise RuntimeError("boom")
        assert logger.level == logging.NOTSET, "the level stayed at ERROR after a raise"

    def test_a_warning_outside_our_read_still_reaches_the_handler(self) -> None:
        """The suppression is scoped to the read; pypdf is not muted globally."""
        with _record_pypdf() as records:
            logging.getLogger("pypdf._reader").warning("something else went wrong")
        assert records == ["something else went wrong"]
