"""No message may predict an exit code it does not produce.

`doctor`'s claims line read:

    <file> holds no claim blocks, so every run will report 0 claims checked
    and exit 0

Every word of that was false by the time anyone read it.  `check`, `verify` and
`scan` all report `no-claim-blocks` (high) and exit 1 - that fix had shipped
three releases earlier, in 0.19.47, and the sentence describing the old
behaviour stayed behind in the message that announced the fix.  So the one line
of `doctor` that exists to explain a silent run told the reader the silence was
normal and green, which is precisely the outcome the whole change had removed.

A sentence about what another command will do decays the moment that command
changes, and nothing runs the sentence.  Two tests: the specific line, and a
mechanical one over every message the tool can print.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from citevouch import doctor
from citevouch.cli import main

SRC = Path(__file__).resolve().parent.parent / "src" / "citevouch"

#: What a string looks like when it promises a run is green.
#:
#: Only ``0``.  Predicting a failure is the safe direction - a reader told the
#: run fails goes and looks, and finds either the failure or a pleasant
#: surprise.  Predicting success is the direction that silences a reader, and a
#: message that says "exit 1" describes a rule that is written down next to it
#: (`--fail-on` is explained by the threshold the same sentence names).
GREEN_CLAIM = re.compile(r"\bexit[s]?\s+0\b", re.IGNORECASE)


def _messages(path: Path) -> list[tuple[int, str]]:
    """Every string constant in ``path`` that is not a docstring.

    Docstrings and comments quote history on purpose ("this used to exit 0"),
    and they are not shown to a reader at run time.  A message is a constant
    that reaches `Report`/`Finding`, so it is a plain string literal in an
    expression position - which is what filtering out module/class/function
    docstrings leaves.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docstrings.add(id(body[0].value))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docstrings:
                continue
            found.append((node.lineno, node.value))
    return found


class TestTheLineThatWasWrong:
    def _line(self, tmp_path: Path) -> str:
        (tmp_path / "manuscript.md").write_text("Just prose here.\n", encoding="utf-8")
        report = doctor._claim_blocks(tmp_path / "manuscript.md")
        return report.detail

    def test_it_does_not_promise_the_run_is_green(self, tmp_path: Path):
        """The sentence said `exit 0` about a run that exits 1."""
        detail = self._line(tmp_path)
        assert "exit 0" not in detail, detail
        assert not GREEN_CLAIM.search(detail), detail

    def test_it_says_what_actually_happens(self, tmp_path: Path):
        (tmp_path / "manuscript.md").write_text("Just prose here.\n", encoding="utf-8")
        assert main(["check", str(tmp_path / "manuscript.md")]) == 1
        detail = self._line(tmp_path)
        assert "no-claim-blocks" in detail, detail
        # Saying the run fails is the safe direction: a reader who is told so
        # goes and looks, and finds either the failure or a surprise.  The
        # detail is allowed to name it; it is not allowed to predict a clean one.
        assert "exits 1" in detail, detail

    def test_the_two_commands_tell_the_same_story(self, tmp_path: Path):
        """`check` names the code; `doctor` names the same code.

        Written as agreement, not as an expected sentence: the wording is free
        to change, the pair of claims is not.
        """
        (tmp_path / "manuscript.md").write_text("Just prose here.\n", encoding="utf-8")
        broken = doctor.problems(doctor.diagnose(root=tmp_path, manuscript="manuscript.md"))
        claims = next(report for report in broken if report.name == "claims")
        assert "no-claim-blocks" in claims.detail, claims.detail


class TestNoMessagePromisesAGreenRun:
    """A claim about another command's exit code is a claim nothing runs.

    Searching for this shape rather than for the one sentence that was wrong,
    because the sentence was written by someone fixing the behaviour it
    describes - the failure is in the shape, not in that author.
    """

    def test_no_user_facing_string_predicts_a_clean_exit(self):
        offenders: list[str] = []
        for path in sorted(SRC.glob("*.py")):
            for line, value in _messages(path):
                if GREEN_CLAIM.search(value):
                    offenders.append(f"{path.name}:{line}: {value[:90]}")
        assert offenders == [], chr(10).join(offenders)

    def test_the_scan_reaches_the_strings_a_reader_sees(self):
        """A guard that finds nothing because it looks nowhere is green.

        `exit 0` as a promise is rare on purpose, so the helpful assertion is
        that the scan actually walked the messages: `--fail-on`'s help is a
        string a reader sees, and it is in there.
        """
        seen = [value for path in sorted(SRC.glob("*.py")) for _, value in _messages(path)]
        assert any("--fail-on" in value or "lowest severity" in value for value in seen)
