"""A key whose value is not a path is named, not dropped.

Before this, ``read_manifest`` kept only the entries whose value was a string
and said nothing about the rest.  The claim that named one of them was then
told, per claim::

    claim c1 names source='page' but no entry in sources.toml and no --source
    path resolves it; add it to sources.toml

about a ``sources.toml`` that said ``page = 5`` on the line the author was
reading.  Measured on eight shapes - an integer, a float, a boolean, an array,
an inline table, ``sources = 5``, ``sources = "page.txt"``, and an empty file -
all of them produced that one sentence.

The empty file is not this defect: a manifest with no entries really does have
no entry for the key, and "add it to sources.toml" is the right advice.  The
other seven are, and they split three ways:

* a value that is not a string (integer, float, boolean, array, inline table);
* a ``sources`` key that is not a table at all (``sources = 5``);
* the same, spelled as a string (``sources = "page.txt"``).

The first is a key that *is* named, so it goes into ``unusable`` and the
message quotes the manifest.  The last two are a manifest that cannot be read,
so they go into ``manifest_problem``.  Two buckets, because the author's next
move differs: edit the value under a key, versus replace the whole file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from citevouch import sources

MANUSCRIPT = "```claim id=c1 source=page page=1\nquote: |\n  alpha beta gamma\n```\n"
PAGE = "alpha beta gamma\n"

NOT_A_PATH = {
    "integer": "page = 5\n",
    "float": "page = 3.5\n",
    "boolean": "page = true\n",
    "array": 'page = ["a.txt"]\n',
    "inline table": 'page = { file = "a.txt" }\n',
}


def project(tmp_path: Path, manifest: str) -> Path:
    """A project whose manifest is the string given."""
    root = tmp_path / "p"
    root.mkdir()
    (root / "sources.toml").write_text(manifest, encoding="utf-8", newline="\n")
    (root / "a.txt").write_text(PAGE, encoding="utf-8", newline="\n")
    (root / "m.md").write_text(MANUSCRIPT, encoding="utf-8", newline="\n")
    return root


def run(root: Path, *extra: str) -> tuple[int, str]:
    """Run the verifier over the project, returning the exit code and output."""
    import contextlib
    import io

    from citevouch.cli import main

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        code = main(["check", "m.md", "--root", str(root), *extra])
    return code, buffer.getvalue()


class TestTheKeyIsNamed:
    """A key the manifest holds with a value that is not a path."""

    @pytest.mark.parametrize("shape", sorted(NOT_A_PATH))
    def test_the_key_reaches_the_unusable_bucket(self, tmp_path: Path, shape: str) -> None:
        root = project(tmp_path, f"[sources]\n{NOT_A_PATH[shape]}")
        table = sources.read_source_table(root)
        assert "page" in table.unusable, f"{shape} lost the key entirely"
        assert table.manifest_problem is None, shape

    @pytest.mark.parametrize("shape", sorted(NOT_A_PATH))
    def test_the_claim_is_not_told_there_is_no_entry(self, tmp_path: Path, shape: str) -> None:
        root = project(tmp_path, f"[sources]\n{NOT_A_PATH[shape]}")
        code, out = run(root)
        assert code == 1
        assert "no entry in sources.toml" not in out, shape
        assert "sources.toml binds 'page'" in out, shape

    def test_the_sentence_does_not_claim_to_know_the_value(self, tmp_path: Path) -> None:
        """The message says what shape the value has, not what it is.

        Quoting ``5`` back would be a second promise: the manifest is read by
        two parsers, and only one of them kept the value at all.
        """
        root = project(tmp_path, "[sources]\npage = 5\n")
        _, out = run(root)
        assert "page = 5" not in out
        assert "a number, a boolean, a list and a nested table are all not a file" in out

    @pytest.mark.parametrize("shape", sorted(NOT_A_PATH))
    def test_the_reason_is_the_same_on_both_readers(self, tmp_path: Path, shape: str) -> None:
        """3.10 has no tomllib, so the subset parser answers too.

        A reader that reported the key on one interpreter and nothing on the
        other would make the same manifest bind on 3.11 and lie on 3.10.
        """
        manifest = f"[sources]\n{NOT_A_PATH[shape]}"
        collected: list[str] = []
        sources._mini_toml(manifest, collected)
        assert "page" in collected, f"{shape} is dropped silently by the 3.10 reader"


class TestTheOtherKeysStillBind:
    """One bad value does not take the manifest with it."""

    def test_a_good_key_beside_a_bad_one_still_resolves(self, tmp_path: Path) -> None:
        root = project(tmp_path, '[sources]\npage = 5\nother = "a.txt"\n')
        table = sources.read_source_table(root)
        assert "other" in table.found
        assert Path(table.found["other"]).name == "a.txt"
        assert "page" in table.unusable

    def test_the_old_reading_of_a_boolean_manifest_is_unchanged(self, tmp_path: Path) -> None:
        """``load_manifest`` still returns just the paths.

        This shape is pinned in test_critic_round5 as well, from when the bug it
        fixed was a boolean discarding the whole manifest.  Both must hold.
        """
        root = project(tmp_path, '[sources]\np = "a.txt"\nenabled = true\n')
        assert sources.load_manifest(root) == {"p": "a.txt"}


class TestTheSourcesKeyMustBeATable:
    """``sources = 5`` is a manifest this tool cannot read, not a missing key."""

    @pytest.mark.parametrize(
        "manifest",
        ["sources = 5\n", 'sources = "page.txt"\n', "sources = true\n"],
    )
    def test_it_is_a_manifest_problem_not_an_absent_key(
        self, tmp_path: Path, manifest: str
    ) -> None:
        root = project(tmp_path, manifest)
        table = sources.read_source_table(root)
        assert table.manifest_problem is not None, manifest
        assert "not a table of keys to paths" in table.manifest_problem
        assert table.unusable == {}

    def test_the_claim_message_names_the_shape(self, tmp_path: Path) -> None:
        root = project(tmp_path, "sources = 5\n")
        code, out = run(root)
        assert code == 1
        assert "no entry in sources.toml" not in out
        assert "not a table of keys to paths" in out

    def test_the_subset_reader_refuses_it_too(self) -> None:
        """3.10 must not answer "no such section" to a file 3.11 rejects."""
        with pytest.raises(ValueError, match="not a table of keys to paths"):
            sources._mini_toml("sources = 5\n")


class TestAnEmptyManifestIsNotThisDefect:
    """An empty file really has no entry, and the old advice is right."""

    def test_it_still_says_there_is_no_entry(self, tmp_path: Path) -> None:
        root = project(tmp_path, "")
        code, out = run(root)
        assert code == 1
        assert "no entry in sources.toml" in out
        assert "something that is not a path" not in out


class TestTheJsonManifest:
    """``sources.json`` holds values too, and the same sentence applies."""

    def test_a_number_in_json_is_not_a_path(self, tmp_path: Path) -> None:
        root = tmp_path / "j"
        root.mkdir()
        (root / "sources.json").write_text(
            json.dumps({"sources": {"page": 5, "other": "a.txt"}}),
            encoding="utf-8",
            newline="\n",
        )
        (root / "a.txt").write_text(PAGE, encoding="utf-8", newline="\n")
        (root / "m.md").write_text(MANUSCRIPT, encoding="utf-8", newline="\n")
        table = sources.read_source_table(root)
        assert "page" in table.unusable
        assert "sources.json binds 'page'" in table.unusable["page"]
        assert "other" in table.found

    def test_a_root_that_is_not_an_object_is_named(self, tmp_path: Path) -> None:
        """A JSON manifest whose root is a list, a number, a string or a
        boolean is not a manifest.  Reading it as an empty one made every claim
        report `no entry in sources.json` about a file it was plainly looking
        at - the same wrong answer the TOML path had until 0.19.66."""
        shapes = {'["a.txt"]': "list", "5": "int", '"page"': "str", "true": "bool"}
        for body, label in shapes.items():
            root = tmp_path / label
            root.mkdir()
            (root / "sources.json").write_text(body, encoding="utf-8", newline="\n")
            table = sources.read_source_table(root)
            assert table.found == {}, body
            assert table.manifest_problem is not None, body
            assert "not an object mapping source keys to paths" in table.manifest_problem
            # The type is the part of the sentence that says what the file
            # holds; without it an author cannot tell a one-character typo from
            # a file that is not a manifest at all.
            assert label in table.manifest_problem

    def test_a_null_sources_key_is_named(self, tmp_path: Path) -> None:
        """`{"sources": null}` binds nothing and says nothing, so the advice
        every claim gets is "add it to sources.json" - which the author does,
        beside the key that is already wrong."""
        root = tmp_path / "n"
        root.mkdir()
        (root / "sources.json").write_text('{"sources": null}', encoding="utf-8", newline="\n")
        table = sources.read_source_table(root)
        assert table.found == {}
        assert table.manifest_problem is not None
        assert "null" in table.manifest_problem

    def test_an_empty_object_is_still_a_manifest(self, tmp_path: Path) -> None:
        """`{}` binds no sources and is not broken: a project mid-setup has one,
        and the message for a missing key is correct there."""
        root = tmp_path / "e"
        root.mkdir()
        (root / "sources.json").write_text("{}", encoding="utf-8", newline="\n")
        table = sources.read_source_table(root)
        assert table.found == {}
        assert table.manifest_problem is None
