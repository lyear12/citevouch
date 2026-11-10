"""A bibliography of definitions is not a bibliography that failed to read.

Measured before this file existed, with a two-file set-up that the multiple
``--bib`` support exists to make possible -- shared ``macros.bib`` next to
``refs.bib``::

    $ citevouch check manuscript.md --root . --bib macros.bib --bib refs.bib
    [high] bib-unreadable at macros.bib:1: not one entry could be read from
           macros.bib, so every reference in the manuscript is unchecked
           against a bibliography that is effectively empty.  Often the file
           is not the encoding it claims: a UTF-16 save read as UTF-8 gives a
           replacement character and a NUL between every letter.
    exit 1

Every word of that is false.  The file is ASCII, it parsed completely, the
reader kept both macros, and ``refs.bib`` answered every key in the
manuscript.  The author is sent to inspect an encoding that is correct, and
the run fails at ``high`` -- the severity this project reserves for things a
reader must not ignore.
"""

from __future__ import annotations

from pathlib import Path

from citevouch.cli import main

NL = chr(10)
B3 = chr(96) * 3

PAGE = (
    "We collected 154,391 examples from the corpus of written English and then filtered them by hand."
    + NL
)
SENTENCE = PAGE.strip()
MANUSCRIPT = (
    B3
    + "claim id=c1 source=paper ref=knuth1984 page=1"
    + NL
    + "quote: |"
    + NL
    + "  "
    + SENTENCE
    + NL
    + B3
    + NL
)

ENTRY = (
    NL.join(
        [
            "@article{knuth1984,",
            "  title = {The Art of Computer Programming},",
            "  author = {Knuth, Donald},",
            "  journal = {CS},",
            "  year = {1984},",
            "}",
        ]
    )
    + NL
)

MACROS = (
    NL.join(
        [
            "@string{acl = {Association for Computational Linguistics}}",
            "@string{emnlp = {Empirical Methods in Natural Language Processing}}",
        ]
    )
    + NL
)

PREAMBLE = '@preamble{ "' + chr(92) + "newcommand{" + chr(92) + 'noopsort}[1]{}" }' + NL
BARE_COMMENT = "@comment{ this file only holds a note about the others }" + NL


def _project(tmp_path: Path) -> Path:
    (tmp_path / "page.txt").write_text(PAGE, encoding="utf-8", newline=NL)
    (tmp_path / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    (tmp_path / "manuscript.md").write_text(MANUSCRIPT, encoding="utf-8", newline=NL)
    return tmp_path


class TestADefinitionsFileIsNotAnUnreadableOne:
    def test_a_macros_file_beside_the_entries_is_not_a_failure(
        self, tmp_path: Path, capsys
    ) -> None:
        project = _project(tmp_path)
        (project / "macros.bib").write_text(MACROS, encoding="utf-8", newline=NL)
        (project / "refs.bib").write_text(ENTRY, encoding="utf-8", newline=NL)

        code = main(
            [
                "check",
                "manuscript.md",
                "--root",
                str(project),
                "--bib",
                "macros.bib",
                "--bib",
                "refs.bib",
            ]
        )
        out = capsys.readouterr().out

        assert code == 0, out
        assert "bib-unreadable" not in out, out
        assert "quote-found" in out, out

    def test_the_macros_file_is_not_accused_of_a_bad_encoding(
        self, tmp_path: Path, capsys
    ) -> None:
        project = _project(tmp_path)
        (project / "macros.bib").write_text(MACROS, encoding="utf-8", newline=NL)

        main(["check", "manuscript.md", "--root", str(project), "--bib", "macros.bib"])
        out = capsys.readouterr().out

        assert "UTF-16" not in out, out
        assert "not one entry could be read" not in out, out

    def test_the_run_says_what_the_file_actually_holds(self, tmp_path: Path, capsys) -> None:
        project = _project(tmp_path)
        (project / "macros.bib").write_text(MACROS, encoding="utf-8", newline=NL)

        code = main(["check", "manuscript.md", "--root", str(project), "--bib", "macros.bib"])
        out = capsys.readouterr().out

        assert code == 0, out
        assert "bib-no-entries" in out, out
        assert "macros.bib" in out, out
        # A definitions file is a real file, so the note is below the default
        # failure threshold instead of stopping the build.
        assert "[low]" in out, out
        # The sentence has to say what the file does hold - "no entries" is
        # only half a fact when the reader can see two definitions in it -
        # and it has to say what to do about it, which is not "convert this
        # file" but "pass it beside the one holding the entries".
        assert "2 definitions" in out, out
        assert "--bib macros.bib --bib refs.bib" in out, out


class TestADefinitionsFileOfAnyKindIsRead:
    def test_a_preamble_only_file(self, tmp_path: Path, capsys) -> None:
        project = _project(tmp_path)
        (project / "pre.bib").write_text(PREAMBLE, encoding="utf-8", newline=NL)

        code = main(["check", "manuscript.md", "--root", str(project), "--bib", "pre.bib"])
        out = capsys.readouterr().out

        assert code == 0, out
        assert "bib-unreadable" not in out, out
        assert "bib-no-entries" in out, out

    def test_a_comment_only_file(self, tmp_path: Path, capsys) -> None:
        project = _project(tmp_path)
        (project / "note.bib").write_text(BARE_COMMENT, encoding="utf-8", newline=NL)

        code = main(["check", "manuscript.md", "--root", str(project), "--bib", "note.bib"])
        out = capsys.readouterr().out

        assert code == 0, out
        assert "bib-unreadable" not in out, out


class TestWhatIsStillUnreadable:
    def test_prose_that_is_not_bibtex_still_fails(self, tmp_path: Path, capsys) -> None:
        project = _project(tmp_path)
        (project / "refs.bib").write_text("this is not bibtex at all" + NL, encoding="utf-8")

        code = main(["check", "manuscript.md", "--root", str(project), "--bib", "refs.bib"])
        out = capsys.readouterr().out

        assert code == 1, out
        assert "bib-unreadable" in out, out
        assert "bib-no-entries" not in out, out

    def test_a_definitions_file_with_stray_prose_names_the_prose(
        self, tmp_path: Path, capsys
    ) -> None:
        project = _project(tmp_path)
        (project / "mixed.bib").write_text(
            MACROS + "these are only the macros, the entries are in refs.bib" + NL,
            encoding="utf-8",
        )

        code = main(["check", "manuscript.md", "--root", str(project), "--bib", "mixed.bib"])
        out = capsys.readouterr().out

        # Prose nobody read is a real failure, so this one stays loud.  What
        # must not happen is the file being called unreadable *and* the
        # encoding blamed while the macros in it parsed fine.
        assert code == 1, out
        assert "bib-entry-header-unparsed" in out, out
        assert "bib-unreadable" in out, out
        assert "2 definitions did parse" in out, out
