"""A check that cannot run must not quote a second vocabulary for one cause.

`doctor` reports seven checks in a fixed order.  When the manuscript is missing
or is a directory, the `manuscript` check fails and says so in the terms the
author can act on ("does not exist", "is a directory, not a file").  The
`sources` check then tried to read the same path and printed:

    [ok  ] sources  could not be read to check them: [Errno 2] No such file or directory: 'p\\manuscript.md'

for a file that had just been reported missing one line above, and

    [ok  ] sources  could not be read to check them: [Errno 13] Permission denied: 'p\\adir'

for a directory.  Two things are wrong with that line and only the second is
cosmetic: it names an errno where the command had already named a cause, and
`Permission denied` about a directory is a sentence a reader will chase - they
will look at the permissions on `adir` - when the actual cause is that it is a
directory at all.  The `manifest` check already had the honest form for this
state ("not checked, because the manifest could not be read"), written for the
same reason: a check should own one noun and stay quiet about the rest.
"""

from __future__ import annotations

from pathlib import Path

from citevouch.cli import main

MANIFEST = '[sources]\npage = "page.txt"\n'


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "p"
    root.mkdir()
    (root / "sources.toml").write_text(MANIFEST, encoding="utf-8", newline="\n")
    (root / "page.txt").write_text("alpha beta gamma\n", encoding="utf-8", newline="\n")
    return root


def _line_for(out: str, name: str) -> str:
    for line in out.splitlines():
        if line.startswith("[") and f"] {name} " in line:
            return line
    raise AssertionError(f"no {name!r} line in:\n{out}")


class TestTheManuscriptFailureIsReportedOnce:
    def test_a_missing_manuscript_does_not_borrow_the_reader_s_errno(
        self, tmp_path: Path, capsys
    ) -> None:
        project = _project(tmp_path)
        main(["doctor", "--root", str(project)])
        out = capsys.readouterr().out
        sources = _line_for(out, "sources")
        assert "Errno" not in sources, sources
        assert "Permission denied" not in sources, sources

    def test_a_directory_manuscript_is_not_called_a_permission_problem(
        self, tmp_path: Path, capsys
    ) -> None:
        project = _project(tmp_path)
        (project / "adir").mkdir()
        main(["doctor", "--root", str(project), "--manuscript", str(project / "adir")])
        out = capsys.readouterr().out
        sources = _line_for(out, "sources")
        assert "Permission denied" not in sources, sources
        assert "Errno" not in sources, sources
        assert "adir" not in sources, sources

    def test_the_sources_line_says_why_it_stopped(self, tmp_path: Path, capsys) -> None:
        project = _project(tmp_path)
        main(["doctor", "--root", str(project)])
        out = capsys.readouterr().out
        sources = _line_for(out, "sources")
        assert "not checked" in sources, sources
        assert "manuscript" in sources, sources

    def test_the_manuscript_line_still_names_the_cause(self, tmp_path: Path, capsys) -> None:
        """Quieting the second line must not quiet the first one."""
        project = _project(tmp_path)
        main(["doctor", "--root", str(project)])
        out = capsys.readouterr().out
        manuscript = _line_for(out, "manuscript")
        assert "does not exist" in manuscript, manuscript

    def test_a_readable_manuscript_is_still_checked(self, tmp_path: Path, capsys) -> None:
        """The check must still run in the case it exists for."""
        project = _project(tmp_path)
        (project / "manuscript.md").write_text(
            "```claim id=c1 source=page page=1\n"
            "quote: |\n"
            "  alpha beta gamma\n"
            "claim: |\n"
            "  alpha beta gamma\n"
            "```\n",
            encoding="utf-8",
            newline="\n",
        )
        code = main(["doctor", "--root", str(project)])
        out = capsys.readouterr().out
        assert code == 0, out
        sources = _line_for(out, "sources")
        assert "each" not in sources or "bound" in sources, sources
        assert "1 source key" in sources, sources

    def test_the_failure_count_does_not_double_count_one_cause(
        self, tmp_path: Path, capsys
    ) -> None:
        """One missing file is one broken check, not two.

        `problems()` counts the failing lines, and the summary reads
        "N of 7 checks failed".  A second failing line for the same cause would
        inflate that number and send the reader looking for a second problem.
        """
        project = _project(tmp_path)
        code = main(["doctor", "--root", str(project)])
        out = capsys.readouterr().out
        assert code == 1
        assert "1 of 7 checks failed" in out, out
