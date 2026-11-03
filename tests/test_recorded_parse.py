"""A block the parser refused must not become invisible in CI.

`scan` refuses a claim block that has no `id=`, a claim id used twice, or a
fence that is never closed, and exits 1.  The ledger records the claims the
parser *accepted*, because a refused block has no evidence to record - so the
verification pass, which walks the ledger, never sees the block at all.

`action.yml` runs `check --use-recorded` on every pull request, which is the
verification pass and nothing else.  Measured before this was fixed:

    scan                       -> exit 1, [high] claim-uncheckable at :9
    check --use-recorded       -> exit 0, [info] quote-found at :3
    verify                     -> exit 0

An author who writes a second claim block without an `id=` and commits it gets a
green tick, and the only command that would have told them is one the CI job
does not run.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PAGE = (
    "The resulting grammar consists of a network of 40,688 constructions, of\n"
    "which 9,800 are frame-evoking constructions.\n"
)
GOOD = (
    "```claim id=c1 source=paper page=1\n"
    "quote: |\n"
    "  The resulting grammar consists of a network of 40,688 constructions, of\n"
    "  which 9,800 are frame-evoking constructions.\n"
    "```\n"
)
NO_ID = "```claim source=paper page=1\nquote: |\n  another sentence entirely\n```\n"
DUPLICATE = GOOD
UNCLOSED = GOOD + "\n```claim id=c2 source=paper page=1\nquote: |\n  tail\n"


def _project(tmp_path: Path, body: str) -> Path:
    (tmp_path / "paper.txt").write_bytes(PAGE.encode())
    (tmp_path / "sources.toml").write_bytes(b'[sources]\npaper = "paper.txt"\n')
    (tmp_path / "manuscript.md").write_bytes(("Intro.\n\n" + body).encode())
    return tmp_path


def _run(root: Path, *args: str) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, "-m", "citevouch", *args],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def _scan(root: Path) -> int:
    code, _ = _run(root, "scan", "manuscript.md")
    return code


class TestTheRecordedPathSeesTheRefusedBlock:
    @pytest.mark.parametrize(
        ("body", "code_expected"),
        [
            (GOOD + "\n" + NO_ID, "claim-uncheckable"),
            (GOOD + "\n" + DUPLICATE, "claim-uncheckable"),
        ],
    )
    def test_a_refused_block_is_not_a_green_build(self, tmp_path: Path, body, code_expected):
        root = _project(tmp_path, body)
        assert _scan(root) == 1, "the premise: scan refuses this manuscript"
        code, text = _run(root, "check", "manuscript.md", "--use-recorded")
        assert code == 1, f"check --use-recorded said the tree was fine:\n{text}"
        assert code_expected in text

    def test_the_unclosed_fence_survives_the_round_trip(self, tmp_path: Path):
        root = _project(tmp_path, UNCLOSED)
        _scan(root)
        code, text = _run(root, "check", "manuscript.md", "--use-recorded")
        assert code == 1
        assert "claim-block-unclosed" in text

    def test_verify_agrees_with_the_recorded_check(self, tmp_path: Path):
        root = _project(tmp_path, GOOD + "\n" + NO_ID)
        _scan(root)
        recorded = _run(root, "check", "manuscript.md", "--use-recorded")
        verified = _run(root, "verify", "manuscript.md")
        assert recorded[0] == verified[0], (
            "two commands that read the same ledger gave different exit codes:\n"
            f"check --use-recorded -> {recorded[0]}\n{recorded[1]}\n"
            f"verify               -> {verified[0]}\n{verified[1]}"
        )

    def test_every_refused_block_is_named_not_just_the_first(self, tmp_path: Path):
        """Two blocks without an `id=` are two mistakes, and each gets its line.

        A report that names the first one and stops reads as "fix this and you
        are done", so the second block keeps the silence the first one had -
        the failure this file exists for, one block later.
        """
        root = _project(tmp_path, GOOD + "\n" + NO_ID + "\n" + NO_ID)
        _scan(root)
        code, text = _run(root, "check", "manuscript.md", "--use-recorded")
        assert code == 1, text
        lines = [line for line in text.splitlines() if "claim-uncheckable" in line]
        assert len(lines) == 2, text


class TestNothingNewIsReported:
    def test_a_clean_project_is_still_green(self, tmp_path: Path):
        root = _project(tmp_path, GOOD)
        assert _scan(root) == 0
        code, text = _run(root, "check", "manuscript.md", "--use-recorded")
        assert code == 0, text
        assert "claim-uncheckable" not in text

    def test_the_live_check_does_not_say_it_twice(self, tmp_path: Path):
        root = _project(tmp_path, GOOD + "\n" + NO_ID)
        code, text = _run(root, "check", "manuscript.md")
        assert code == 1
        lines = [line for line in text.splitlines() if "claim-uncheckable" in line]
        assert len(lines) == 1, text

    def test_allow_stale_describes_only_the_recorded_text(self, tmp_path: Path):
        """`--allow-stale` says "do not compare", so do not describe a text either.

        The ledger no longer claims to be about the file on disk, and a finding
        about a paragraph the ledger never recorded would be a verdict about a
        document this run has not read.
        """
        root = _project(tmp_path, GOOD)
        assert _scan(root) == 0
        (root / "manuscript.md").write_bytes(("Intro.\n\n" + GOOD + "\n" + NO_ID).encode())
        code, text = _run(root, "check", "manuscript.md", "--use-recorded", "--allow-stale")
        assert code == 0, text
        assert "claim-uncheckable" not in text


class TestTheLedgerIsStillTheSourceOfTruth:
    def test_the_refusal_is_read_from_the_manuscript_not_invented(self, tmp_path: Path):
        """A hand-written ledger that records nothing must not silence the report."""
        root = _project(tmp_path, GOOD + "\n" + NO_ID)
        _scan(root)
        ledger_path = root / "citevouch.lock.json"
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        assert [claim["id"] for claim in ledger["claims"]] == ["c1"]
        code, text = _run(root, "check", "manuscript.md", "--use-recorded")
        assert code == 1
        assert "manuscript.md:9" in text
