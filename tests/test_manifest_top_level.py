"""A manifest is one file, and the two readers must answer it the same way.

``sources.json`` takes its mapping at the top level: ``{"page": "a.txt"}``.
``sources.toml`` takes it inside a ``[sources]`` table.  A TOML file that puts
its keys at the top level and never writes a table header is therefore the one
shape the two formats disagree about - and until this file existed, that
disagreement was answered silently.

Measured before the fix, on a project whose only claim names ``paper`` and
whose ``sources.toml`` holds ``paper = "page.txt"`` at the top level:

    check  -> [high] source-missing ... "no entry in sources.toml and no
              --source path resolves it; add it to sources.toml"
    doctor -> [ok  ] manifest sources.toml (19 bytes), 0 sources, every one of
              them present on this machine

The author is told to add an entry that is in the file, three lines above the
header the message asks for, and the command whose whole job is to explain that
message calls the file fine.  ``0 sources, ok`` is the shape this module exists
to stop: a file with content reported as a file with none.

The refusal lives in the pre-scan on the *text*, not in the parsed dict, and
that placement is the part worth keeping: the subset parser on 3.10 files
top-level keys under a bucket named ``""``, so a check written against the
parsed mapping would refuse on 3.11 and stay silent on 3.10 - a manifest read
one way by whichever interpreter happens to be installed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from citevouch import sources

NL = chr(10)

FLAT = 'title = "Sources"' + NL + 'paper = "page.txt"' + NL

QUOTE = ["The resulting grammar consists of a network of 40,688 constructions."]

CLAIM = [
    "```claim id=c1 source=paper page=1",
    "quote: |",
    "  The resulting grammar consists of a network of 40,688 constructions.",
    "```",
]


def _project(tmp_path: Path, manifest: str) -> Path:
    root = tmp_path / "p"
    root.mkdir()
    (root / "sources.toml").write_text(manifest, encoding="utf-8", newline=NL)
    # `paper.txt`, not `page.txt`: `--source` binds a file to a key named after
    # its stem, so the rescue test has to name the file the claim asks for or it
    # is testing a different project.
    (root / "paper.txt").write_text(NL.join(QUOTE), encoding="utf-8", newline=NL)
    (root / "manuscript.md").write_text(NL.join(CLAIM), encoding="utf-8", newline=NL)
    return root


def _run(root: Path, *args: str) -> tuple[int, str]:
    import contextlib
    import io

    from citevouch.cli import main

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        code = main([*args, "--root", str(root)])
    return code, buffer.getvalue()


def _both_readers(manifest: str) -> list[tuple[str, object]]:
    out: list[tuple[str, object]] = []
    for reader in (sources._load_toml, sources._mini_toml):
        try:
            out.append(("read", reader(manifest)))
        except ValueError as exc:
            out.append(("refused", str(exc)))
    return out


class TestBothReadersRefuseIt:
    def test_the_two_readers_give_the_same_sentence(self) -> None:
        left, right = _both_readers(FLAT)
        assert left[0] == "refused"
        assert right[0] == "refused"
        assert left[1] == right[1]

    def test_the_sentence_names_the_keys(self) -> None:
        _, message = _both_readers(FLAT)[0]
        assert "'paper'" in message
        assert "'title'" in message

    def test_the_sentence_offers_the_working_spelling(self) -> None:
        """The advice, not just the word.

        `"[sources]" in message` is not this assertion: the same message says
        "no [sources] table" further up, so a mutation that deleted the
        instruction left the token behind and the test passed.  What the
        author needs is the command: add the header, or switch format.
        """
        _, message = _both_readers(FLAT)[0]
        assert "add the header above them" in message
        assert "move them to sources.json" in message

    def test_the_count_is_the_number_of_stray_keys(self) -> None:
        """`len(seen)` and `len(stray)` are the same number here, and must not be.

        FLAT has two top-level keys and both are stray, so a count taken over
        `seen` instead of `stray` printed 2 as well.  This manifest separates
        them: `page` is a dotted name, so it is seen and not stray.
        """
        manifest = 'title = "S"' + NL + 'page.x = "a.txt"' + NL
        left, right = _both_readers(manifest)
        assert left[0] == "refused"
        assert right[0] == "refused"
        assert "1 key at the top level" in left[1], left[1]
        assert "'title'" in left[1]
        assert "page.x" not in left[1]


class TestWhatIsStillRead:
    """The refusal has to be narrow, or it rejects working projects."""

    @pytest.mark.parametrize(
        "name,manifest",
        [
            ("empty", ""),
            ("comment only", "# nothing yet" + NL),
            ("a table", "[sources]" + NL + 'page = "a.txt"' + NL),
            ("another table", "[other]" + NL + 'page = "a.txt"' + NL),
            (
                "a root key beside a table",
                'title = "S"' + NL + "[sources]" + NL + 'page = "a.txt"' + NL,
            ),
            (
                "a root key with a nested table",
                'title = "S"' + NL + "[other]" + NL + 'x = "y"' + NL,
            ),
        ],
    )
    def test_both_readers_still_read_it(self, name: str, manifest: str) -> None:
        left, right = _both_readers(manifest)
        assert left[0] == "read", f"{name}: tomllib refused a working manifest"
        assert right[0] == "read", f"{name}: the subset refused a working manifest"

    def test_the_table_still_binds(self, tmp_path: Path) -> None:
        root = _project(
            tmp_path, 'title = "S"' + NL + "[sources]" + NL + 'paper = "paper.txt"' + NL
        )
        table = sources.read_source_table(root)
        assert not table.manifest_problem
        assert list(table.found) == ["paper"]


class TestTheClaimIsToldTheTruth:
    def test_check_names_the_top_level_keys(self, tmp_path: Path) -> None:
        code, output = _run(_project(tmp_path, FLAT), "check", "manuscript.md")
        assert code == 1
        assert "because the manifest could not be read" in output
        assert "[sources]" in output
        assert "no entry in sources.toml" not in output

    def test_doctor_does_not_call_the_file_fine(self, tmp_path: Path) -> None:
        root = _project(tmp_path, FLAT)
        code, output = _run(root, "doctor", "--manuscript", "manuscript.md")
        assert code == 1
        line = next(line for line in output.splitlines() if line.startswith("[FAIL] manifest"))
        assert "cannot be used" in line
        assert "0 sources" not in output

    def test_source_still_rescues_it(self, tmp_path: Path) -> None:
        root = _project(tmp_path, FLAT)
        code, output = _run(root, "check", "manuscript.md", "--source", "paper.txt")
        assert code == 0, output
        assert "quote-found" in output

    def test_a_working_table_is_untouched(self, tmp_path: Path) -> None:
        root = _project(tmp_path, "[sources]" + NL + 'paper = "paper.txt"' + NL)
        code, output = _run(root, "check", "manuscript.md")
        assert code == 0, output
