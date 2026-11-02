"""One manifest, one answer, whichever interpreter reads it.

`sources.toml` has two readers.  On 3.11+ `_load_toml` hands the file to
`tomllib`; on 3.10, which has no `tomllib`, it falls back to `_mini_toml`, a
line-based subset parser.  The CI matrix runs 3.10, 3.12 and 3.13, so the same
repository is served by both.

Measured before this was pinned, same file, both readers:

=========================  =========================  ======================
manifest                   tomllib                    subset
=========================  =========================  ======================
`sources = { page = .. }`  binds `page`               can see no table
`pa.ge = "a.txt"`          binds nothing at `pa.ge`   binds `pa.ge`
`page = "a"` twice         refuses the file           last one wins
`[sources]` twice          refuses the file           merges the halves
=========================  =========================  ======================

Every row is a project that is green on one interpreter and red on another for
a file nobody edited between the runs.  The subset parser must not grow into a
TOML parser to fix this; the fix is that both readers refuse the same files and
with the same sentence, and that the spellings which do work are the ones the
README describes.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest

from citevouch import sources

ACCEPTED = {
    "a plain table": '[sources]\npage = "a.txt"\n',
    "two keys": '[sources]\npage = "a.txt"\nother = "b.txt"\n',
    "a comment": '# the manifest\n\n[sources]\npage = "a.txt"  # trailing\n',
    "no sources table": '[other]\npage = "a.txt"\n',
    "an empty file": "",
    "a quoted colon key": '[sources]\n"knuth:2019" = "a.txt"\n',
    "a quoted dotted key": '[sources]\n"pa.ge" = "a.txt"\n',
    "a quoted key with a space": '[sources]\n"pa ge" = "a.txt"\n',
    "a non-ascii path": '[sources]\npage = "\u6587\u732e/a.txt"\n',
    "a backslash escape": '[sources]\npage = "a\\\\b.txt"\n',
    "another section": '[sources]\npage = "a.txt"\n[other]\npage = "b.txt"\n',
}

#: Read without complaint by both readers, but not into the same dict: a value
#: that is not a string is not a path, so the subset drops it from the table
#: and hands the key out separately, while tomllib keeps the raw value.  Both
#: then say the same thing about it - "this key is not bound to a file" - and
#: that is the only level at which one manifest has to have one answer.
NOT_A_PATH_VALUES = {
    "a non-string value": "[sources]\npage = 5\n",
    "a boolean value": "[sources]\npage = true\n",
    "a float value": "[sources]\npage = 3.5\n",
    "an array value": '[sources]\npage = ["a.txt"]\n',
}

REFUSED = {
    "an inline table": 'sources = { page = "a.txt" }\n',
    "a dotted key": '[sources]\npa.ge = "a.txt"\n',
    "a repeated key": '[sources]\npage = "a.txt"\npage = "b.txt"\n',
    "a reopened table": '[sources]\npage = "a.txt"\n[sources]\nother = "b.txt"\n',
    "a string at the root": 'sources = "page.txt"\n',
    "a number at the root": "sources = 5\n",
    "an array at the root": 'sources = ["a.txt"]\n',
    "a line that is not an assignment": '[sources]\npage = "a.txt"\nbogus\n',
}


def both_readers(manifest: str) -> list[tuple[str, object]]:
    """What each reader makes of `manifest`, as (outcome, value)."""
    out: list[tuple[str, object]] = []
    for reader in (sources._load_toml, sources._mini_toml):
        try:
            out.append(("read", reader(manifest)))
        except ValueError as exc:
            out.append(("refused", str(exc)))
    return out


class TestTheAcceptedSpellingsReadTheSame:
    @pytest.mark.parametrize("name", sorted(ACCEPTED))
    def test_both_readers_return_the_same_table(self, name: str) -> None:
        manifest = ACCEPTED[name]
        left, right = both_readers(manifest)
        assert left[0] == "read", f"{name}: tomllib refused an accepted manifest"
        assert right[0] == "read", f"{name}: the subset refused an accepted manifest"
        assert left[1] == right[1], f"{name}: two readings of one file"

    @pytest.mark.parametrize("name", sorted({**ACCEPTED, **NOT_A_PATH_VALUES}))
    def test_the_keys_that_bind_are_the_same(self, name: str, tmp_path: Path) -> None:
        """Not the same dict, the same bindings: the table is what callers see."""
        manifest = {**ACCEPTED, **NOT_A_PATH_VALUES}[name]
        root = tmp_path / name.replace(" ", "-")
        root.mkdir()
        (root / "sources.toml").write_text(manifest, encoding="utf-8", newline="\n")
        (root / "a.txt").write_text("alpha\n", encoding="utf-8", newline="\n")
        (root / "b.txt").write_text("beta\n", encoding="utf-8", newline="\n")
        real = sources.read_source_table(root)
        original = sources._load_toml
        sources._load_toml = lambda text, odd=None: sources._mini_toml(text, odd)
        try:
            mini = sources.read_source_table(root)
        finally:
            sources._load_toml = original
        assert sorted(real.found) == sorted(mini.found), name
        assert sorted(real.unusable) == sorted(mini.unusable), name
        assert bool(real.manifest_problem) == bool(mini.manifest_problem), name


class TestTheScanOnlyAsksAboutTheSourcesTable:
    """A manifest may carry tables nobody here reads, in any TOML they like.

    The first version of the pre-scan walked the whole file, so
    ``[other] pa.ge = "dir/x"`` - a nested table to both readers, binding no
    source to either - made the manifest unreadable.  Measured: `found={}` with
    `manifest_problem` naming a dotted key under a table this tool never reads.
    Both readers answer ``sources`` the same way for that file, which is the
    whole question, so the refusal would have been the regression.
    """

    UNRELATED: ClassVar[dict[str, str]] = {
        "a dotted key under another table": (
            '[sources]\npage = "a.txt"\n[other]\npa.ge = "dir/x"\n'
        ),
        "an inline table under another table": (
            '[sources]\npage = "a.txt"\n[other]\nsources = { a = "b" }\n'
        ),
        "a dotted key under no [sources] at all": 'pa.ge = "dir/x"\n',
        "a dotted key quoted under [sources]": '[sources]\n"pa.ge" = "a.txt"\n',
    }

    @pytest.mark.parametrize("name", sorted(UNRELATED))
    def test_the_manifest_is_read(self, name: str, tmp_path: Path) -> None:
        root = tmp_path / name.replace(" ", "-")
        root.mkdir()
        (root / "sources.toml").write_text(self.UNRELATED[name], encoding="utf-8", newline="\n")
        (root / "a.txt").write_text("alpha\n", encoding="utf-8", newline="\n")
        table = sources.read_source_table(root)
        assert not table.manifest_problem, name

    def test_the_source_it_does_bind_still_binds(self, tmp_path: Path) -> None:
        root = tmp_path / "p"
        root.mkdir()
        (root / "sources.toml").write_text(
            self.UNRELATED["a dotted key under another table"],
            encoding="utf-8",
            newline="\n",
        )
        (root / "a.txt").write_text("alpha\n", encoding="utf-8", newline="\n")
        table = sources.read_source_table(root)
        assert list(table.found) == ["page"]

    def test_root_inline_table_is_still_refused(self) -> None:
        left, right = both_readers(REFUSED["an inline table"])
        assert left[0] == "refused"
        assert right[0] == "refused"

    def test_dotted_key_under_sources_is_still_refused(self) -> None:
        left, right = both_readers(REFUSED["a dotted key"])
        assert left[0] == "refused"
        assert right[0] == "refused"


class TestTheRefusedSpellingsAreRefusedTwice:
    @pytest.mark.parametrize("name", sorted(REFUSED))
    def test_both_readers_refuse(self, name: str) -> None:
        left, right = both_readers(REFUSED[name])
        assert left[0] == "refused", f"{name}: tomllib read a manifest we refuse"
        assert right[0] == "refused", f"{name}: the subset read a manifest we refuse"

    @pytest.mark.parametrize(
        "name",
        ["an inline table", "a dotted key", "a repeated key", "a reopened table"],
    )
    def test_the_two_readers_say_the_same_sentence(self, name: str) -> None:
        """One refusal, one explanation.

        A reader that refuses in its own words tells the author their file is
        broken twice, differently, depending on which interpreter is installed.
        """
        left, right = both_readers(REFUSED[name])
        assert left[1] == right[1], f"{name}: {left[1]!r} vs {right[1]!r}"

    def test_the_inline_table_message_names_the_working_spelling(self) -> None:
        _, message = both_readers(REFUSED["an inline table"])[0]
        assert "[sources]" in message
        assert 'key = "path"' in message

    def test_the_dotted_key_message_offers_the_quoted_form(self) -> None:
        _, message = both_readers(REFUSED["a dotted key"])[0]
        assert "dotted key" in message
        assert '"pa.ge"' in message

    def test_the_repeated_key_message_names_the_key(self) -> None:
        _, message = both_readers(REFUSED["a repeated key"])[0]
        assert "'page'" in message
        assert "[sources]" in message


class TestTheClaimIsNotToldTheWrongThing:
    """The end-to-end sentence, because the parsed table is not the report."""

    def project(self, tmp_path: Path, manifest: str) -> Path:
        root = tmp_path / "p"
        root.mkdir()
        (root / "sources.toml").write_text(manifest, encoding="utf-8", newline="\n")
        (root / "a.txt").write_text("alpha beta gamma\n", encoding="utf-8", newline="\n")
        (root / "m.md").write_text(
            "```claim id=c1 source=page page=1\nquote: |\n  alpha beta gamma\n```\n",
            encoding="utf-8",
            newline="\n",
        )
        return root

    def run(self, root: Path) -> tuple[int, str]:
        import contextlib
        import io

        from citevouch.cli import main

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            code = main(["check", "m.md", "--root", str(root)])
        return code, buffer.getvalue()

    @pytest.mark.parametrize("name", sorted(REFUSED))
    def test_a_refused_manifest_is_reported_once_and_named(
        self, name: str, tmp_path: Path
    ) -> None:
        code, out = self.run(self.project(tmp_path, REFUSED[name]))
        assert code == 1, name
        assert "no entry in sources.toml" not in out, f"{name}: a false absence"
        assert "could not be read as TOML" in out, name

    def test_a_refused_manifest_names_what_to_change(self, tmp_path: Path) -> None:
        _, out = self.run(self.project(tmp_path, REFUSED["a dotted key"]))
        assert "dotted key" in out

    def test_the_accepted_spellings_still_verify(self, tmp_path: Path) -> None:
        root = self.project(tmp_path, '[sources]\npage = "a.txt"\n')
        code, out = self.run(root)
        assert code == 0, out
        assert "1 claim — 1 verified" in out
