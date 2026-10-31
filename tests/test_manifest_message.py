"""What the tool says when a manifest entry cannot be used.

The message used to be identical for four different situations: no manifest,
a manifest without that key, a manifest whose key points at a file that is not
there, and a manifest that could not be parsed at all.  Three of those four are
sentences about something the author already did right - they wrote the entry -
so the reader goes back to the manifest, finds their line, and concludes the
tool is broken.  A message about a path has to be true about that path.

`read_source_table` now keeps them, but the old `discover_sources` threw the unusable entries away (`if path.is_file()` with no
`else`), which is why the per-claim message could not tell the cases apart: by
the time it ran, the information was gone.  `read_source_table` keeps it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from citevouch.sources import read_manifest, read_source_table

ROOT = Path(__file__).resolve().parent.parent


def _project(tmp_path: Path, manifest: str | None) -> Path:
    (tmp_path / "note.txt").write_text("hello\n", encoding="utf-8")
    (tmp_path / "m.md").write_text(
        "```claim id=c1 source=p\nquote: hello\n```\n", encoding="utf-8"
    )
    if manifest is not None:
        (tmp_path / "sources.toml").write_text(manifest, encoding="utf-8")
    return tmp_path


def _check(project: Path, extra: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "PYTHONIOENCODING": "utf-8",
    }
    argv = [
        sys.executable,
        "-m",
        "citevouch",
        "check",
        "m.md",
        "--root",
        str(project),
        "--no-cache",
    ]
    for path in extra or []:
        argv.extend(["--source", path])
    return subprocess.run(
        argv,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=str(project),
        check=False,
    )


class TestTheTableKeepsWhatItCouldNotUse:
    def test_a_key_whose_file_is_gone_is_kept_as_unusable(self, tmp_path: Path) -> None:
        project = _project(tmp_path, '[sources]\np = "gone.txt"\n')
        table = read_source_table(project)
        assert table.found == {}
        assert "p" in table.unusable
        assert "does not exist" in table.unusable["p"]

    def test_a_key_whose_file_is_a_directory_says_so(self, tmp_path: Path) -> None:
        project = _project(tmp_path, '[sources]\np = "."\n')
        table = read_source_table(project)
        assert "p" in table.unusable
        assert "is a directory, not a file" in table.unusable["p"]

    def test_a_key_that_resolves_is_not_listed_as_unusable(self, tmp_path: Path) -> None:
        project = _project(tmp_path, '[sources]\np = "note.txt"\n')
        table = read_source_table(project)
        assert "p" in table.found
        assert table.unusable == {}

    def test_a_manifest_that_will_not_parse_reports_itself(self, tmp_path: Path) -> None:
        project = _project(tmp_path, '[sources\np = "note.txt"\n')
        table = read_source_table(project)
        assert table.found == {}
        assert table.manifest_problem is not None
        assert "sources.toml" in table.manifest_problem

    def test_no_manifest_is_not_a_problem(self, tmp_path: Path) -> None:
        project = _project(tmp_path, None)
        table = read_source_table(project)
        assert table.found == {}
        assert table.unusable == {}
        assert table.manifest_problem is None

    def test_the_table_keeps_the_bindings_and_keeps_the_failures(self, tmp_path: Path) -> None:
        project = _project(tmp_path, '[sources]\np = "note.txt"\nq = "gone.txt"\n')
        table = read_source_table(project)
        assert set(table.found) == {"p"}
        assert "q" in table.unusable

    def test_load_manifest_is_the_mapping_alone(self, tmp_path: Path) -> None:
        project = _project(tmp_path, '[sources]\np = "note.txt"\n')
        assert read_manifest(project) == ({"p": "note.txt"}, None)


class TestTheReportedSentenceIsTrue:
    def test_a_missing_file_is_not_called_a_missing_entry(self, tmp_path: Path) -> None:
        project = _project(tmp_path, '[sources]\np = "gone.txt"\n')
        result = _check(project)
        assert result.returncode == 1
        assert "no entry in sources.toml" not in result.stdout
        assert "sources.toml maps 'p' to 'gone.txt'" in result.stdout
        assert "does not exist" in result.stdout

    def test_a_directory_says_directory(self, tmp_path: Path) -> None:
        project = _project(tmp_path, '[sources]\np = "."\n')
        result = _check(project)
        assert result.returncode == 1
        assert "is a directory, not a file" in result.stdout

    def test_an_unreadable_manifest_is_named_as_the_cause(self, tmp_path: Path) -> None:
        project = _project(tmp_path, '[sources\np = "note.txt"\n')
        result = _check(project)
        assert result.returncode == 1
        assert "the manifest could not be read" in result.stdout
        assert "sources.toml could not be read as TOML" in result.stdout

    def test_no_manifest_still_says_add_it(self, tmp_path: Path) -> None:
        project = _project(tmp_path, None)
        result = _check(project)
        assert result.returncode == 1
        assert "no entry in sources.toml" in result.stdout
        assert "add it to sources.toml" in result.stdout

    def test_a_resolved_project_says_nothing_at_all(self, tmp_path: Path) -> None:
        project = _project(tmp_path, '[sources]\np = "note.txt"\n')
        result = _check(project)
        assert result.returncode == 0
        assert "source" not in result.stdout


class TestTheContradictionThatWasWrittenDown:
    """The pair that made this bug survive: same call, opposite conclusions."""

    def test_a_directory_in_the_manifest_is_kept_not_dropped(self, tmp_path: Path) -> None:
        project = _project(tmp_path, '[sources]\nother = "."\n')
        table = read_source_table(project)
        # The sibling test in test_critic_round3.py used to assert this path was
        # ignored, while the test above it asserted a --source directory must be
        # refused.  Both passed, because the manifest half threw the entry away
        # and the sentence written about it blamed the manifest for not having it.
        assert "other" in table.unusable
        assert "other" not in table.found

    def test_a_bad_source_flag_is_still_a_usage_error(self, tmp_path: Path) -> None:
        from citevouch.errors import UsageError

        project = _project(tmp_path, None)
        (project / "adir").mkdir()
        with pytest.raises(UsageError):
            read_source_table(project, [str(project / "adir")])


class TestBothReadersTellTheSameStory:
    """`scan` and `verify` read the same manifest; they used to describe it differently."""

    def _scan_and_verify(self, project: Path) -> tuple[str, str]:
        env = {
            **os.environ,
            "PYTHONPATH": str(ROOT / "src"),
            "PYTHONIOENCODING": "utf-8",
        }

        def run(verb: str) -> str:
            done = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "citevouch",
                    verb,
                    "m.md",
                    "--root",
                    str(project),
                    "--no-cache",
                ],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                cwd=str(project),
                check=False,
            )
            return done.stdout

        return run("scan"), run("verify")

    def test_an_unusable_entry_is_named_by_both(self, tmp_path: Path) -> None:
        project = _project(tmp_path, "[sources]" + chr(10) + 'p = "gone.txt"' + chr(10))
        scanned, verified = self._scan_and_verify(project)
        for out in (scanned, verified):
            assert "sources.toml maps 'p' to 'gone.txt'" in out
        # The old verify line: true about the file, silent about the entry the
        # author has to edit.
        assert "cannot be found any more" not in verified

    def test_an_unreadable_manifest_is_named_by_both(self, tmp_path: Path) -> None:
        project = _project(tmp_path, "[sources" + chr(10) + 'p = "note.txt"' + chr(10))
        scanned, verified = self._scan_and_verify(project)
        for out in (scanned, verified):
            assert "the manifest could not be read" in out

    def test_a_key_nobody_named_keeps_the_old_sentence(self, tmp_path: Path) -> None:
        project = _project(tmp_path, None)
        _, verified = self._scan_and_verify(project)
        assert "cannot be found any more" in verified

    def test_the_table_answers_only_what_it_knows(self, tmp_path: Path) -> None:
        from citevouch.sources import SourceTable, explain_unresolved

        empty = SourceTable()
        assert explain_unresolved("p", empty) is None
        bad = SourceTable(unusable={"p": "p is gone"}, manifest_problem="broke")
        assert explain_unresolved("p", bad) == "p is gone"
        assert explain_unresolved("q", bad) == "the manifest could not be read: broke"


class TestTheDraftProposalNamesTheCauseToo:
    """The third reader of the manifest, and it had the same generic sentence."""

    def _draft(self, project: Path) -> str:
        (project / "m.md").write_text(
            "Prior work trains on two corpora of real sentences [@smith2020]." + chr(10),
            encoding="utf-8",
        )
        (project / "refs.bib").write_text(
            "@article{smith2020," + chr(10) + "  title = {A Paper}" + chr(10) + "}" + chr(10),
            encoding="utf-8",
        )
        env = {
            **os.environ,
            "PYTHONPATH": str(ROOT / "src"),
            "PYTHONIOENCODING": "utf-8",
        }
        subprocess.run(
            [
                sys.executable,
                "-m",
                "citevouch",
                "draft",
                "m.md",
                "--root",
                str(project),
                "--bib",
                "refs.bib",
                "-o",
                "claims.md",
                "--force",
            ],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            cwd=str(project),
            check=False,
        )
        return (project / "claims.md").read_text(encoding="utf-8")

    def test_an_unusable_entry_is_not_described_as_absent(self, tmp_path: Path) -> None:
        project = _project(tmp_path, "[sources]" + chr(10) + 'smith2020 = "gone.txt"' + chr(10))
        out = self._draft(project)
        assert "sources.toml maps 'smith2020' to 'gone.txt'" in out
        # The generic sentence claims all three searches failed. Two of the
        # three are about this project and neither is what happened.
        assert "not in sources.toml, no `file` field" not in out

    def test_an_unreadable_manifest_is_named(self, tmp_path: Path) -> None:
        project = _project(tmp_path, "[sources" + chr(10) + 'smith2020 = "gone.txt"' + chr(10))
        out = self._draft(project)
        assert "the manifest could not be read" in out

    def test_a_key_nobody_named_keeps_the_generic_sentence(self, tmp_path: Path) -> None:
        project = _project(tmp_path, None)
        out = self._draft(project)
        assert "not in sources.toml, no `file` field" in out


class TestAKeyBoundTwiceIsRefusedInsteadOfResolved:
    """Two sources naming the same key used to resolve to whichever came last.

    The manifest branch overwrote what a --source flag had bound, so a caller
    who passed the flag to replace one stale entry got no error, no effect, and
    a finding saying the quote was not in the file they had just tried to stop
    using.  Refusing is not picking a winner; it is declining to rank two files
    the caller can see and the tool cannot.
    """

    def _project(self, tmp_path: Path) -> Path:
        (tmp_path / "m.md").write_text(
            "```claim id=c1 source=dup page=1"
            + chr(10)
            + "quote: alpha text here."
            + chr(10)
            + "```"
            + chr(10),
            encoding="utf-8",
        )
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        (tmp_path / "a" / "dup.txt").write_text("alpha text here." + chr(10), encoding="utf-8")
        (tmp_path / "b" / "dup.txt").write_text("beta text here." + chr(10), encoding="utf-8")
        return tmp_path

    def _manifest(self, project: Path, value: str) -> None:
        (project / "sources.toml").write_text(
            "[sources]" + chr(10) + "dup = " + chr(34) + value + chr(34) + chr(10),
            encoding="utf-8",
        )

    def test_the_flag_and_the_manifest_cannot_both_win(self, tmp_path: Path) -> None:
        project = self._project(tmp_path)
        self._manifest(project, "b/dup.txt")
        result = _check(project, extra=[str(project / "a" / "dup.txt")])
        assert result.returncode == 2
        assert "bound twice" in result.stderr
        assert "--source" in result.stderr
        assert "sources.toml" in result.stderr

    def test_two_flags_on_the_same_stem_are_refused(self, tmp_path: Path) -> None:
        project = self._project(tmp_path)
        result = _check(
            project,
            extra=[str(project / "a" / "dup.txt"), str(project / "b" / "dup.txt")],
        )
        assert result.returncode == 2
        assert "bound twice by --source" in result.stderr

    def test_the_same_file_named_twice_is_not_a_conflict(self, tmp_path: Path) -> None:
        project = self._project(tmp_path)
        same = str(project / "a" / "dup.txt")
        result = _check(project, extra=[same, same])
        assert result.returncode == 0
        assert "quote found" in result.stdout

    def test_the_manifest_naming_the_same_file_is_not_a_conflict(self, tmp_path: Path) -> None:
        project = self._project(tmp_path)
        self._manifest(project, "a/dup.txt")
        result = _check(project, extra=[str(project / "a" / "dup.txt")])
        assert result.returncode == 0
        assert "quote found" in result.stdout
