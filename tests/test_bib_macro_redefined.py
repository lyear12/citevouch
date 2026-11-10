"""Two files that define one macro differently have to say so.

Giving `--bib` twice made a group, and the group shares one `@string` table.
Measured before this file existed, on `a.bib` defining `j = "Journal A"` and
`c.bib` defining `j = "Journal C"`, with `e.bib` using `j`:

    a.bib c.bib e.bib -> journal = 'Journal C'   (no finding)
    c.bib a.bib e.bib -> journal = 'Journal A'   (no finding)

So which work the entry names depended on the order of two flags, and nothing
said so.  `bib-duplicate-key` already refuses that shape for entries; a macro is
the same fact written one level up.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from citevouch.bibtex import parse_bib, parse_bib_group

NL = chr(10)
B3 = chr(96) * 3
SENTENCE = (
    "We collected 154,391 examples from the corpus of written English and "
    "then filtered them by hand."
)
MANUSCRIPT = (
    B3
    + "claim id=c1 source=paper ref=k1 page=1"
    + NL
    + "quote: |"
    + NL
    + "  "
    + SENTENCE
    + NL
    + B3
    + NL
)
A = '@string{j = "Journal A"}' + NL
C = '@string{j = "Journal C"}' + NL
USE = (
    NL.join(
        [
            "@article{k1,",
            "  title = {T},",
            "  author = {A},",
            "  journal = j,",
            "  year = {2020},",
            "}",
        ]
    )
    + NL
)


def _project(tmp_path: Path) -> Path:
    (tmp_path / "page.txt").write_text(SENTENCE + NL, encoding="utf-8", newline=NL)
    (tmp_path / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    (tmp_path / "manuscript.md").write_text(MANUSCRIPT, encoding="utf-8", newline=NL)
    (tmp_path / "a.bib").write_text(A, encoding="utf-8", newline=NL)
    (tmp_path / "c.bib").write_text(C, encoding="utf-8", newline=NL)
    (tmp_path / "e.bib").write_text(USE, encoding="utf-8", newline=NL)
    return tmp_path


def _run(root: Path, *argv: str) -> tuple[int, str]:
    env = {
        **os.environ,
        "PYTHONPATH": str(Path.cwd() / "src"),
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


def _codes(captured: str) -> list[str]:
    codes: list[str] = []
    for line in captured.splitlines():
        if not line.startswith("["):
            continue
        _, _, rest = line.partition("]")
        code = rest.strip().split(" ")[0]
        if code:
            codes.append(code)
    return codes


class TestTheGroupRefusesToPickOneSilently:
    def test_the_redefinition_is_reported(self) -> None:
        results = parse_bib_group([(A, "a.bib"), (C, "c.bib"), (USE, "e.bib")])
        codes = [finding.code for result in results for finding in result.findings]
        assert "bib-macro-redefined" in codes

    def test_the_message_names_both_files_and_the_macro(self) -> None:
        results = parse_bib_group([(A, "a.bib"), (C, "c.bib"), (USE, "e.bib")])
        messages = [
            finding.message
            for result in results
            for finding in result.findings
            if finding.code == "bib-macro-redefined"
        ]
        assert messages, "no redefinition finding"
        assert "a.bib" in messages[0] and "c.bib" in messages[0]
        assert "'j'" in messages[0]

    def test_the_message_quotes_both_values(self) -> None:
        # The reader has to be able to tell which definition to delete; a
        # message that names both files but neither value leaves them guessing.
        results = parse_bib_group([(A, "a.bib"), (C, "c.bib"), (USE, "e.bib")])
        message = next(
            finding.message
            for result in results
            for finding in result.findings
            if finding.code == "bib-macro-redefined"
        )
        assert "'Journal A'" in message and "'Journal C'" in message

    def test_three_files_all_disagreeing_all_get_named(self) -> None:
        # `known.clear()`-style bugs keep only the last comparison alive; three
        # disagreeing definitions is the smallest shape that shows a lost one.
        results = parse_bib_group(
            [(A, "a.bib"), (C, "c.bib"), ('@string{j = "Journal D"}' + NL, "d.bib")]
        )
        messages = [
            finding.message
            for result in results
            for finding in result.findings
            if finding.code == "bib-macro-redefined"
        ]
        assert len(messages) == 2, messages
        named = " ".join(messages)
        assert "a.bib" in named and "c.bib" in named and "d.bib" in named

    def test_the_other_order_reports_it_too(self) -> None:
        results = parse_bib_group([(C, "c.bib"), (A, "a.bib"), (USE, "e.bib")])
        codes = [finding.code for result in results for finding in result.findings]
        assert "bib-macro-redefined" in codes

    def test_it_is_high_because_the_work_is_ambiguous(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _code, captured = _run(
            root,
            "check",
            "manuscript.md",
            "--root",
            str(root),
            "--bib",
            "a.bib",
            "--bib",
            "c.bib",
            "--bib",
            "e.bib",
        )
        line = next(line for line in captured.splitlines() if "bib-macro-redefined" in line)
        assert line.startswith("[high]")


class TestWhatMustNotBeReported:
    def test_one_definition_read_twice_is_not_a_redefinition(self) -> None:
        results = parse_bib_group([(A, "a.bib"), (A, "a.bib")])
        codes = [finding.code for result in results for finding in result.findings]
        assert "bib-macro-redefined" not in codes

    def test_the_same_definition_in_two_files_is_the_same_definition(self) -> None:
        results = parse_bib_group([(A, "a.bib"), (A, "b.bib")])
        codes = [finding.code for result in results for finding in result.findings]
        assert "bib-macro-redefined" not in codes

    def test_one_file_alone_is_unchanged(self) -> None:
        results = parse_bib_group([(C, "c.bib"), (USE, "e.bib")])
        codes = [finding.code for result in results for finding in result.findings]
        assert "bib-macro-redefined" not in codes

    def test_a_macro_redefined_inside_one_file_is_still_the_old_behaviour(self) -> None:
        # `@string` twice in one file is a file disagreeing with itself; this
        # change is about the group, and one file's own repeat already had an
        # answer (the later definition wins) before `--bib` took two flags.
        text = A + C
        result = parse_bib(text, "both.bib")
        assert result.strings["j"] == "Journal C"
        assert "bib-macro-redefined" not in [f.code for f in result.findings]

    def test_the_entry_itself_still_parses(self) -> None:
        results = parse_bib_group([(A, "a.bib"), (C, "c.bib"), (USE, "e.bib")])
        entries = [r for r in results if r.entries]
        assert entries and entries[0].entries["k1"].fields["journal"] in (
            "Journal A",
            "Journal C",
        )
