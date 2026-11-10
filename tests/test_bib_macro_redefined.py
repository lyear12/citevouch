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
from citevouch.cli import _deconflict

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


# Two macros that disagree between the same two files are two things to fix.
# They were reported at line 1 of the winning file, which is the same
# coordinate `_deconflict` keys on, so only the first survived: the author
# fixed `j`, re-ran, and met `n` for the first time.
TWO_A = '@string{j = "Journal A"}' + NL + '@string{n = "Note A"}' + NL
TWO_B = NL * 4 + '@string{j = "Journal B"}' + NL + NL * 2 + '@string{n = "Note B"}' + NL
TWO_USE = (
    NL.join(
        [
            "@article{k1,",
            "  title = {T},",
            "  author = {A},",
            "  journal = j,",
            "  note = n,",
            "  year = {2020},",
            "}",
        ]
    )
    + NL
)


class TestEveryConflictGetsItsOwnCoordinate:
    def test_two_conflicts_are_two_findings(self) -> None:
        results = parse_bib_group([(TWO_A, "a.bib"), (TWO_B, "b.bib"), (TWO_USE, "refs.bib")])
        found = [
            finding
            for result in results
            for finding in result.findings
            if finding.code == "bib-macro-redefined"
        ]
        assert len(found) == 2, [finding.message for finding in found]

    def test_the_deconflict_pass_keeps_both(self) -> None:
        # The report downstream keeps one finding per (code, claim, path,
        # line).  Two conflicts on one coordinate is one line on screen and one
        # fix in the file, and the second one is then met on the next run.
        results = parse_bib_group([(TWO_A, "a.bib"), (TWO_B, "b.bib"), (TWO_USE, "refs.bib")])
        raw = [finding for result in results for finding in result.findings]
        kept = [f for f in _deconflict(raw) if f.code == "bib-macro-redefined"]
        assert len(kept) == 2, [f.message for f in kept]

    def test_each_finding_points_at_the_line_that_wrote_it(self) -> None:
        # The reader opens the file the finding names.  Line 1 of a `.bib` is
        # usually a comment, so pointing there sends them hunting.
        results = parse_bib_group([(TWO_A, "a.bib"), (TWO_B, "b.bib"), (TWO_USE, "refs.bib")])
        found = {
            finding.message.split("'")[1]: finding
            for result in results
            for finding in result.findings
            if finding.code == "bib-macro-redefined"
        }
        assert found["j"].line == 5, found["j"].line
        assert found["n"].line == 8, found["n"].line

    def test_the_message_names_the_line_each_side_wrote(self) -> None:
        results = parse_bib_group([(TWO_A, "a.bib"), (TWO_B, "b.bib"), (TWO_USE, "refs.bib")])
        message = next(
            finding.message
            for result in results
            for finding in result.findings
            if finding.code == "bib-macro-redefined" and "'j'" in finding.message
        )
        assert "a.bib line 1" in message and "b.bib line 5" in message

    def test_the_check_prints_both(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        (root / "a.bib").write_text(TWO_A, encoding="utf-8", newline=NL)
        (root / "b.bib").write_text(TWO_B, encoding="utf-8", newline=NL)
        (root / "e.bib").write_text(TWO_USE, encoding="utf-8", newline=NL)
        _code, captured = _run(
            root,
            "check",
            "manuscript.md",
            "--root",
            str(root),
            "--bib",
            "a.bib",
            "--bib",
            "b.bib",
            "--bib",
            "e.bib",
        )
        lines = [line for line in captured.splitlines() if "bib-macro-redefined" in line]
        assert len(lines) == 2, lines
        assert any("'j'" in line for line in lines)
        assert any("'n'" in line for line in lines)


class TestTheFindingHangsOffTheFileItNames:
    def test_every_finding_is_attached_to_its_own_file(self) -> None:
        # `scan`, `draft` and the recorded re-read all flatten these results
        # without reading the finding's own path, so a finding attached to the
        # wrong result is a finding filed under another file's name.  Nothing
        # breaks today; the next caller that groups by result gets a lie.
        results = parse_bib_group([(TWO_A, "a.bib"), (TWO_B, "b.bib"), (TWO_USE, "refs.bib")])
        names = ["a.bib", "b.bib", "refs.bib"]
        for result, path in zip(results, names, strict=True):
            for finding in result.findings:
                if finding.code == "bib-macro-redefined":
                    assert finding.path == path, (finding.path, path)

    def test_the_earlier_side_names_its_own_line(self) -> None:
        # `a.bib` writes `n` on line 2, not line 1.  Reporting line 1 sends the
        # reader to the comment at the top of the file.
        results = parse_bib_group([(TWO_A, "a.bib"), (TWO_B, "b.bib"), (TWO_USE, "refs.bib")])
        message = next(
            finding.message
            for result in results
            for finding in result.findings
            if finding.code == "bib-macro-redefined" and "'n'" in finding.message
        )
        assert "a.bib line 2" in message, message
        assert "b.bib line 8" in message, message
