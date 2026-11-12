"""A file whose one block was refused: does `doctor` say the machine is fine?

``doctor`` exists to explain a report that looks empty.  A manuscript holding a
single claim block that the parser *read and refused* - no ``id=``, no
``source=``, no quote - produced seven ``[ok  ]`` lines and exit 0, ending with
"Everything this tool needs is on this machine.  If quotes are still reported
missing, the source files are the place to look."  ``check`` on the same tree
printed ``[high] claim-uncheckable`` and exited 1, and the ledger held no claim
at all.  The reader who ran ``doctor`` *because* the report looked empty was the
one being told nothing was wrong, and the sentence at the bottom sent them to
look at source files for a defect that is in the manuscript.

The boundary this file pins down is the one the module already drew: ``doctor``
fails when the run would be vacuous - nothing in the project is ever checked -
and stays green when some block was checked and some other block was refused,
because that refusal has its own line number and its own severity.  Both halves
are asserted here, so a future fix cannot quietly widen the first into the
second.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from citevouch import doctor

B3 = "`" * 3
NL = "\n"
QUOTE = "We collected 40,688 examples from the corpus."
OTHER = "The held-out set of 9,800 rolesets is described elsewhere."
PAGE = "Nothing to see here.\f" + QUOTE + NL + OTHER + NL
MANIFEST = '[sources]\npaper = "page.txt"\n'
FIXED = "`citevouch check` names each block"

# The three ways a block is refused after the parser has read it.  Each one
# leaves `parsed.claims` empty, so the ledger gets no claim, and each one is a
# high-severity finding in `check`.
REFUSALS = {
    "no-source": B3 + "claim id=c1" + NL + "quote: |" + NL + "  " + QUOTE + NL + B3 + NL,
    "no-id": B3 + "claim source=paper" + NL + "quote: |" + NL + "  " + QUOTE + NL + B3 + NL,
    "no-quote": B3 + "claim id=c1 source=paper" + NL + "claim: see above" + NL + B3 + NL,
}
# The same refusal in the HTML-comment dialect: one attribute table, two
# spellings, and the fix must not be written for only one of them.
COMMENTED = "<!-- claim id=c1" + NL + "quote: |" + NL + "  " + QUOTE + NL + "-->" + NL


def _project(tmp_path: Path, body: str) -> Path:
    root = tmp_path / "proj"
    root.mkdir(parents=True, exist_ok=True)
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(MANIFEST, encoding="utf-8", newline=NL)
    (root / "m.md").write_text(body, encoding="utf-8", newline=NL)
    return root


def _run(root: Path, *argv: str) -> tuple[int, str]:
    env = {
        **__import__("os").environ,
        "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
        "PYTHONIOENCODING": "utf-8",
    }
    done = subprocess.run(
        [sys.executable, "-m", "citevouch", *argv],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return done.returncode, done.stdout + done.stderr


class TestTheVerdictIsNotGreenerThanTheCommandItExplains:
    @pytest.mark.parametrize("name", sorted(REFUSALS))
    def test_doctor_exits_one(self, tmp_path: Path, name: str):
        root = _project(tmp_path, REFUSALS[name])
        code, out = _run(root, "doctor", "--root", ".", "--manuscript", "m.md")
        assert code == 1, out

    @pytest.mark.parametrize("name", sorted(REFUSALS))
    def test_it_does_not_say_the_machine_is_fine(self, tmp_path: Path, name: str):
        root = _project(tmp_path, REFUSALS[name])
        _code, out = _run(root, "doctor", "--root", ".", "--manuscript", "m.md")
        assert "Everything this tool needs is on this machine" not in out

    @pytest.mark.parametrize("name", sorted(REFUSALS))
    def test_the_claims_line_is_the_one_that_breaks(self, tmp_path: Path, name: str):
        root = _project(tmp_path, REFUSALS[name])
        _code, out = _run(root, "doctor", "--root", ".", "--manuscript", "m.md")
        assert "[FAIL] claims" in out, out
        assert "read and refused" in out, out
        assert FIXED in out, out

    def test_the_comment_dialect_is_refused_the_same_way(self, tmp_path: Path):
        root = _project(tmp_path, COMMENTED)
        code, out = _run(root, "doctor", "--root", ".", "--manuscript", "m.md")
        assert code == 1, out
        assert "[FAIL] claims" in out, out
        assert "read and refused" in out, out

    def test_check_agrees(self, tmp_path: Path):
        """The two commands must not disagree about whether this is a problem."""
        root = _project(tmp_path, REFUSALS["no-source"])
        check_code, check_out = _run(root, "check", "m.md", "--root", ".")
        doctor_code, doctor_out = _run(root, "doctor", "--root", ".", "--manuscript", "m.md")
        assert check_code == 1, check_out
        assert doctor_code == 1, doctor_out
        assert "claim-uncheckable" in check_out, check_out


class TestTheLinesBelowItDoNotContradictIt:
    @pytest.mark.parametrize("name", sorted(REFUSALS))
    def test_sources_and_extraction_point_at_the_refusal(self, tmp_path: Path, name: str):
        """They may not say "no claim names a source" one line under a refusal.

        That sentence is true of a file holding no block.  Printed beside
        ``[FAIL] claims ... read and refused`` it tells the reader there is no
        claim and, one line up, that there are claims the tool would not take.
        """
        root = _project(tmp_path, REFUSALS[name])
        reports = doctor.diagnose(root=root, manuscript="m.md")
        for line in ("sources", "extraction"):
            report = next(item for item in reports if item.name == line)
            assert report.ok, report.detail
            assert report.detail == (
                "not checked, because the parser refused the blocks this file holds"
            ), report.detail

    def test_a_file_without_any_block_keeps_the_old_sentence(self, tmp_path: Path):
        """The other shape still gets the sentence it was written for."""
        root = _project(tmp_path, "Just prose, no blocks at all." + NL)
        reports = doctor.diagnose(root=root, manuscript="m.md")
        for line in ("sources", "extraction"):
            report = next(item for item in reports if item.name == line)
            assert report.detail == "no claim names a source", report.detail


class TestTheBoundaryThisFixMustNotCross:
    def test_one_readable_block_is_enough_to_stay_green(self, tmp_path: Path):
        """A mixed file is the documented silence, and it must survive.

        ``tests/test_skipped_claim_blocks.py`` records the decision: a block the
        parser refused beside one it read is named in the count ("1 of which the
        parser could read; the next command names the rest") and ``doctor``
        stays green, because the run is not vacuous - one claim *is* checked.
        Widening this fix to cover that case would make ``doctor`` disagree with
        its own recorded design.
        """
        good = (
            B3
            + "claim id=c1 source=paper page=2"
            + NL
            + "quote: |"
            + NL
            + "  "
            + QUOTE
            + NL
            + B3
            + NL
        )
        root = _project(tmp_path, good + NL + REFUSALS["no-source"])
        code, out = _run(root, "doctor", "--root", ".", "--manuscript", "m.md")
        assert code == 0, out
        assert "1 of which the parser could read" in out, out

    def test_a_block_nobody_could_reach_is_still_the_other_failure(self, tmp_path: Path):
        """An unreachable fence produces no claim and no finding.

        It lands in the ``nothing_to_check`` branch with an empty file, so it is
        reported as ``no claim blocks`` - the same failure ``check`` exits 1 for.
        The new branch must not be reachable from it, or one block out of reach
        would be described as "read and refused", which is the opposite of what
        happened.
        """
        unreached = (
            "> "
            + B3
            + "claim id=c1 source=paper"
            + NL
            + "> quote: |"
            + NL
            + ">   "
            + QUOTE
            + NL
            + "> "
            + B3
            + NL
        )
        root = _project(tmp_path, unreached)
        code, out = _run(root, "doctor", "--root", ".", "--manuscript", "m.md")
        assert code == 1, out
        assert "no claim blocks" in out, out
        assert "read and refused" not in out, out


class TestWhatTheMessageMustName:
    def test_every_refused_block_is_counted(self, tmp_path: Path):
        """Two refusals are two blocks, not the first one.

        The count is the only place the reader learns how much work the fix is,
        and a file with three bad blocks takes three edits, not one.
        """
        two = REFUSALS["no-source"] + NL + REFUSALS["no-id"]
        root = _project(tmp_path, two)
        reports = doctor.diagnose(root=root, manuscript="m.md")
        report = next(item for item in reports if item.name == "claims")
        assert not report.ok
        assert report.detail.startswith("2 claim blocks"), report.detail

    def test_the_line_of_the_first_refusal_is_named(self, tmp_path: Path):
        """`check` names a line; a diagnosis that says "somewhere" is not one."""
        body = NL + NL + REFUSALS["no-source"]
        root = _project(tmp_path, body)
        reports = doctor.diagnose(root=root, manuscript="m.md")
        report = next(item for item in reports if item.name == "claims")
        assert "line 3" in report.detail, report.detail
        assert "no source=" in report.detail, report.detail

    def test_a_shape_like_header_is_not_counted_as_a_refused_block(self, tmp_path: Path):
        """A header row is not a block, even when a refusal sits under it.

        ``claim-table-header`` is deliberately excluded from the count in
        ``ParseResult.nothing_to_check`` for the same reason: a header row names
        nothing and holds no quotation, so counting it here would report two
        refused blocks for a file holding one, and would point the reader at the
        header's line instead of the block they have to fix.
        """
        shaped = (
            "| c1 | paper | 2 | "
            + QUOTE
            + " | see above |"
            + NL
            + "| --- | --- | --- | --- | --- |"
            + NL
        )
        root = _project(tmp_path, shaped + NL + REFUSALS["no-source"])
        reports = doctor.diagnose(root=root, manuscript="m.md")
        report = next(item for item in reports if item.name == "claims")
        assert not report.ok
        assert report.detail.startswith("1 claim block"), report.detail
        assert "line 4" in report.detail, report.detail


class TestTheRepositoryDemoStillDiagnosesClean:
    def test_the_demo_has_no_broken_check(self):
        """The demo is the one manuscript every release runs `doctor` against."""
        demo = Path(__file__).resolve().parent.parent / "demo"
        reports = doctor.diagnose(root=demo, manuscript="manuscript.md")
        assert doctor.problems(reports) == []
