"""A group of `--bib` files is one bibliography, macros included.

`--bib` may be given more than once, and the shape it exists for is a shared
`macros.bib` beside a `refs.bib`.  Measured before this file existed, every
order reported the same thing:

    [medium] bib-macro-unknown at refs.bib:1: knuth1984: 1 undefined macro
    in 1 field ('journal' uses 'acm'); no @string defines them, so each name
    was kept as literal text

`macros.bib` held `@string{acm = "Association for Computing Machinery"}` on
line 1.  So the message named the one thing that was not true, and the shared
macros file - the whole reason `--bib` takes two flags - did nothing at all.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from citevouch.bibtex import parse_bib

NL = chr(10)
B3 = chr(96) * 3
SENTENCE = (
    "We collected 154,391 examples from the corpus of written English and "
    "then filtered them by hand."
)
PAGE = SENTENCE + NL
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
MACROS = '@string{acm = "Association for Computing Machinery"}' + NL
# The entry uses the macro.  This is what a shared macros file is for.
ENTRY = (
    NL.join(
        [
            "@article{knuth1984,",
            "  title = {T},",
            "  author = {A},",
            "  journal = acm,",
            "  year = {1984},",
            "}",
        ]
    )
    + NL
)
UNKNOWN = '@string{other = "Other"}' + NL


def _project(tmp_path: Path) -> Path:
    (tmp_path / "page.txt").write_text(PAGE, encoding="utf-8", newline=NL)
    (tmp_path / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    (tmp_path / "manuscript.md").write_text(MANUSCRIPT, encoding="utf-8", newline=NL)
    (tmp_path / "macros.bib").write_text(MACROS, encoding="utf-8", newline=NL)
    (tmp_path / "refs.bib").write_text(ENTRY, encoding="utf-8", newline=NL)
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
    # A finding line reads `[medium] bib-macro-unknown at refs.bib:1: ...`, so
    # the code is the token after the severity, not the severity itself.
    codes: list[str] = []
    for line in captured.splitlines():
        if not line.startswith("["):
            continue
        _, _, rest = line.partition("]")
        code = rest.strip().split(" ")[0]
        if code:
            codes.append(code)
    return codes


class TestTheMacroIsThePointOfTheSecondFlag:
    def test_parse_bib_takes_the_strings_it_was_given(self) -> None:
        result = parse_bib(ENTRY, "refs.bib", {"acm": "Association for Computing Machinery"})
        assert result.entries["knuth1984"].fields["journal"] == (
            "Association for Computing Machinery"
        )
        assert "bib-macro-unknown" not in [finding.code for finding in result.findings]

    def test_parse_bib_returns_the_strings_it_now_knows(self) -> None:
        first = parse_bib(MACROS, "macros.bib")
        second = parse_bib(ENTRY, "refs.bib", first.strings)
        assert second.strings["acm"] == "Association for Computing Machinery"

    def test_macros_first_resolves_the_macro(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        code, captured = _run(
            root,
            "check",
            "manuscript.md",
            "--root",
            str(root),
            "--bib",
            "macros.bib",
            "--bib",
            "refs.bib",
        )
        assert "bib-macro-unknown" not in _codes(captured)
        assert code == 0

    def test_refs_first_resolves_it_too(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        code, captured = _run(
            root,
            "check",
            "manuscript.md",
            "--root",
            str(root),
            "--bib",
            "refs.bib",
            "--bib",
            "macros.bib",
        )
        assert "bib-macro-unknown" not in _codes(captured)
        assert code == 0


class TestWhatMustStillBeReported:
    def test_a_macro_nobody_defined_is_still_unknown(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        (root / "macros.bib").write_text(UNKNOWN, encoding="utf-8", newline=NL)
        code, captured = _run(
            root,
            "check",
            "manuscript.md",
            "--root",
            str(root),
            "--bib",
            "macros.bib",
            "--bib",
            "refs.bib",
        )
        assert "bib-macro-unknown" in _codes(captured)
        assert "'acm'" in captured
        assert code == 0

    def test_refs_alone_still_says_the_macro_is_undefined(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _code, captured = _run(
            root, "check", "manuscript.md", "--root", str(root), "--bib", "refs.bib"
        )
        assert "bib-macro-unknown" in _codes(captured)

    def test_a_definitions_file_is_still_only_low(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        code, captured = _run(
            root,
            "check",
            "manuscript.md",
            "--root",
            str(root),
            "--bib",
            "macros.bib",
            "--bib",
            "refs.bib",
        )
        assert "bib-no-entries" in _codes(captured)
        assert code == 0

    def test_the_recorded_pass_reads_the_group_the_same_way(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _run(
            root,
            "scan",
            "manuscript.md",
            "--root",
            str(root),
            "--bib",
            "macros.bib",
            "--bib",
            "refs.bib",
        )
        code, captured = _run(
            root, "check", "manuscript.md", "--root", str(root), "--use-recorded"
        )
        assert "bib-macro-unknown" not in _codes(captured)
        assert code == 0


class TestTheDraftReaderToo:
    def test_draft_sees_the_macro_from_the_other_file(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        (root / "sources.toml").write_text(
            "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
        )
        code, captured = _run(
            root,
            "draft",
            "manuscript.md",
            "--root",
            str(root),
            "--bib",
            "macros.bib",
            "--bib",
            "refs.bib",
            "-o",
            "claims.md",
        )
        assert code == 0
        assert "bib-macro-unknown" not in _codes(captured)
