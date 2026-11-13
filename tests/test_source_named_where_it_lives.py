"""Three sentences named a source by its file name, with the directory gone.

Every finding that says something about a *source file* - "quote not found in
<file>", "<file> has pages 1-N", "<file> is a different file than the one the
ledger recorded" - used ``Path(path).name``, which keeps the last segment and
drops everything in front of it.  A project that keeps its sources in a folder
therefore told its author to look at a file that is not where they are standing:

    $ citevouch check m.md            # sources.toml maps paper -> sources/paper.txt
    [high] quote-missing at m.md:1 (c1): ... - quote not found in paper.txt

The claim's own path in that same line became root-relative several rounds ago;
the *source* half of the sentence was left behind, and the ledger has always
spelled the file ``sources/paper.txt``.  Measured, before and after:

    ...quote not found in paper.txt        -> sources/paper.txt opens from here
    paper.txt has pages 1-2                -> sources/paper.txt has pages 1-2
    paper.txt is a different file ...      -> sources/paper.txt is a different file ...

The rule is the one ``recorded_path`` already answers for the manuscript, the
bibliography and the ledger: name a file the way the run resolved it - relative
to the root, forward slashes, shell-quoted when it has to survive being pasted
into a command.  A source at the project root still prints as ``paper.txt``,
because that *is* its root-relative spelling; the fix adds a directory only
where there is one.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

NL = chr(10)
FF = chr(12)
B3 = chr(96) * 3

ROOT = Path(__file__).resolve().parents[1]

QUOTE = "We collected 154,391 examples from the corpus."
ELSEWHERE = "Nothing of the kind appears on this page."
PAGE = "Intro." + FF + QUOTE + NL

MANIFEST = "[sources]" + NL + 'paper = "sources/paper.txt"' + NL


def _run(root: Path, *argv: str) -> tuple[int, str]:
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "PYTHONIOENCODING": "utf-8",
    }
    proc = subprocess.run(
        [sys.executable, "-m", "citevouch", *argv],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return proc.returncode, proc.stdout + proc.stderr


def _project(tmp_path: Path, page: str, *, attrs: str = "id=c1 source=paper") -> Path:
    root = tmp_path / "proj"
    (root / "sources").mkdir(parents=True, exist_ok=True)
    (root / "sources" / "paper.txt").write_text(page, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(MANIFEST, encoding="utf-8", newline=NL)
    body = B3 + "claim " + attrs + NL + "quote: |" + NL + "  " + QUOTE + NL + B3 + NL
    (root / "m.md").write_text(body, encoding="utf-8", newline=NL)
    return root


def _line_with(text: str, marker: str) -> str:
    for line in text.splitlines():
        if marker in line:
            return line
    raise AssertionError(f"no line mentions {marker!r}:{NL}{text}")


def _quoted_name(line: str) -> str:
    """The shell-quoted or bare path the sentence ends by naming."""
    found = re.search(r"'([^']+)'", line)
    if found:
        return found.group(1)
    tail = line.rsplit(" in ", 1)[-1].strip() if " in " in line else line.rsplit(" ", 1)[-1]
    return tail.rstrip(".,;")


def _page_name(line: str) -> str:
    """The path in front of ``has pages 1-N``.

    Asserting only that the line *contains* ``sources/paper.txt`` would pass
    for an absolute path too - the absolute spelling ends with the same
    segment.  The claim this file makes is narrower: the name is the root
    relative one, so it can be pasted into a command run from the root.
    """
    head = line.split(" has pages 1-", 1)[0]
    named = head.rsplit(" ", 1)[-1]
    return named.strip("'\"")


class TestTheFileNamedCanBeOpened:
    def test_the_quote_missing_sentence_names_the_whole_path(self, tmp_path):
        root = _project(tmp_path, ELSEWHERE + NL)
        code, out = _run(root, "check", "m.md")
        assert code == 1
        line = _line_with(out, "quote-missing")
        named = _quoted_name(line)
        assert named == "sources/paper.txt", line
        assert (root / named).is_file()

    def test_the_page_out_of_range_sentence_names_the_whole_path(self, tmp_path):
        root = _project(tmp_path, PAGE, attrs="id=c1 source=paper page=9")
        code, out = _run(root, "check", "m.md")
        assert code == 1
        line = _line_with(out, "page-out-of-range")
        assert _page_name(line) == "sources/paper.txt", line
        assert " has pages 1-" in line, line

    def test_the_source_changed_sentence_names_the_whole_path(self, tmp_path):
        root = _project(tmp_path, QUOTE + NL)
        code, _ = _run(root, "scan", "m.md")
        assert code == 0
        (root / "sources" / "paper.txt").write_text(
            "Preface. " + QUOTE + " Appendix." + NL, encoding="utf-8", newline=NL
        )
        code, out = _run(root, "check", "m.md", "--use-recorded")
        assert code == 0
        line = _line_with(out, "source-changed")
        assert "sources/paper.txt is a different file than the one" in line, line

    def test_scan_agrees_with_check_on_the_page_sentence(self, tmp_path):
        root = _project(tmp_path, PAGE, attrs="id=c1 source=paper page=9")
        code, out = _run(root, "scan", "m.md")
        assert code == 1
        line = _line_with(out, "page-out-of-range")
        assert _page_name(line) == "sources/paper.txt", line
        assert " has pages 1-" in line, line

    def test_the_recorded_pass_has_its_own_page_sentence(self, tmp_path):
        """`check --use-recorded` reaches the sentence from verify, not scan.

        `check` de-duplicates a finding that both halves of the run reach, and
        the *first* one wins - so the scan copy is the only one a plain
        `check` ever prints, and the verify copy could have gone back to
        `Path(path).name` with every test still green.  A recorded run never
        scans, which is how this sentence gets a run of its own.
        """
        root = _project(tmp_path, PAGE, attrs="id=c1 source=paper page=9")
        _run(root, "scan", "m.md")
        code, out = _run(root, "check", "m.md", "--use-recorded")
        assert code == 1
        line = _line_with(out, "page-out-of-range")
        assert _page_name(line) == "sources/paper.txt", line
        assert " has pages 1-" in line, line

    def test_the_sentence_is_relative_to_the_root_not_to_the_shell(self, tmp_path):
        """Run from the parent directory: the root spelling is still the one named.

        With ``--root .`` the root is ``Path(".")``, so joining it onto the
        recorded path is a no-op and a doubled join looks correct.  A run
        from outside the project gives the root a name, which is what tells
        the two apart.
        """
        _project(tmp_path, PAGE, attrs="id=c1 source=paper page=9")
        code, out = _run(tmp_path, "check", "proj/m.md", "--root", "proj")
        assert code == 1
        line = _line_with(out, "page-out-of-range")
        assert _page_name(line) == "sources/paper.txt", line
        assert " has pages 1-" in line, line

    def test_the_quote_sentence_is_relative_to_the_root_too(self, tmp_path):
        _project(tmp_path, ELSEWHERE + NL)
        code, out = _run(tmp_path, "check", "proj/m.md", "--root", "proj")
        assert code == 1
        line = _line_with(out, "quote-missing")
        assert _quoted_name(line) == "sources/paper.txt", line


class TestAFileAtTheProjectRootKeepsItsShortName:
    def test_the_root_is_the_spelling_when_the_file_is_there(self, tmp_path):
        root = tmp_path / "flat"
        root.mkdir()
        (root / "paper.txt").write_text(ELSEWHERE + NL, encoding="utf-8", newline=NL)
        (root / "sources.toml").write_text(
            "[sources]" + NL + 'paper = "paper.txt"' + NL, encoding="utf-8", newline=NL
        )
        (root / "m.md").write_text(
            B3
            + "claim id=c1 source=paper"
            + NL
            + "quote: |"
            + NL
            + "  "
            + QUOTE
            + NL
            + B3
            + NL,
            encoding="utf-8",
            newline=NL,
        )
        code, out = _run(root, "check", "m.md")
        assert code == 1
        line = _line_with(out, "quote-missing")
        assert "paper.txt" in line
        assert "sources/" not in line, line


class TestTheSentenceStillSaysWhatItSays:
    def test_the_quote_and_the_verdict_survive(self, tmp_path):
        root = _project(tmp_path, ELSEWHERE + NL)
        _, out = _run(root, "check", "m.md")
        line = _line_with(out, "quote-missing")
        assert QUOTE in line
        assert "quote-missing" in line

    def test_a_path_with_a_space_is_quoted_so_it_can_be_pasted(self, tmp_path):
        root = tmp_path / "spaced"
        (root / "my sources").mkdir(parents=True)
        (root / "my sources" / "paper one.txt").write_text(
            ELSEWHERE + NL, encoding="utf-8", newline=NL
        )
        (root / "sources.toml").write_text(
            "[sources]" + NL + 'paper = "my sources/paper one.txt"' + NL,
            encoding="utf-8",
            newline=NL,
        )
        (root / "m.md").write_text(
            B3
            + "claim id=c1 source=paper"
            + NL
            + "quote: |"
            + NL
            + "  "
            + QUOTE
            + NL
            + B3
            + NL,
            encoding="utf-8",
            newline=NL,
        )
        _, out = _run(root, "check", "m.md")
        line = _line_with(out, "quote-missing")
        assert "'my sources/paper one.txt'" in line, line
