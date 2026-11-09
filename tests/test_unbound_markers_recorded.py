"""The recorded pass has to report a credibility mark that no block covers.

``scan`` runs :func:`citevouch.manuscript.scan_unbound_markers` and says, for
every 【原文】 line that no claim block covers::

    [low] claim-without-evidence at manuscript.md:1: the 【原文】 mark on this
    line has no claim block, so nothing ties it to a page in a local source

``verify`` re-parses the manuscript when the recorded digest still matches, so
it has the spans and the claims that function needs - it simply never asked.
Measured on a manuscript holding a marked sentence followed by an unrelated
claim block::

    check                 -> 0, [low] claim-without-evidence at manuscript.md:1
    check --use-recorded  -> 0, [info] quote-found at manuscript.md:3 (c1)

``action.yml`` runs ``check --use-recorded``, so the author's marked sentence
never gets the advice on the pull request - and a mark with no block is
exactly the shape this tool exists to catch.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src")}

SENTENCE = "We collected 154,391 examples from the corpus."
PAGE = SENTENCE + "\nA second line with no numbers in it.\n"
MANIFEST = '[sources]\npaper = "page.txt"\n'
BOUND = "```claim id=c1 source=paper page=1\nquote: |\n  " + SENTENCE + "\n```\n"
MARKED = "【原文】 " + SENTENCE + "\n"
NAMING = (
    "```claim id=c1 source=paper page=1 marker=【原文】\nquote: |\n  " + SENTENCE + "\n```\n"
)


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "citevouch", *args, "--root", str(root)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env=ENV,
    )


def _project(tmp_path: Path, manuscript: str) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    (root / "page.txt").write_text(PAGE, encoding="utf-8")
    (root / "sources.toml").write_text(MANIFEST, encoding="utf-8")
    (root / "manuscript.md").write_text(manuscript, encoding="utf-8")
    return root


def _codes(proc: subprocess.CompletedProcess[str]) -> list[str]:
    return [
        line.split()[1]
        for line in (proc.stdout or "").splitlines()
        if line.startswith("[") and "]" in line and len(line.split()) > 1
    ]


def _recorded(root: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return _run(
        root,
        "check",
        "manuscript.md",
        "--use-recorded",
        "--ledger",
        "citevouch.lock.json",
        *extra,
    )


class TestTheRecordedPassReportsTheMark:
    def test_a_mark_with_no_block_is_reported(self, tmp_path: Path) -> None:
        root = _project(tmp_path, MARKED + "\n" + BOUND)
        assert _run(root, "scan", "manuscript.md").returncode == 0
        proc = _recorded(root)
        assert "claim-without-evidence" in _codes(proc), proc.stdout
        assert "【原文】" in proc.stdout

    def test_the_two_paths_agree_on_the_code(self, tmp_path: Path) -> None:
        root = _project(tmp_path, MARKED + "\n" + BOUND)
        _run(root, "scan", "manuscript.md")
        live = _run(root, "check", "manuscript.md")
        recorded = _recorded(root)
        assert "claim-without-evidence" in _codes(live)
        assert "claim-without-evidence" in _codes(recorded)

    def test_two_marks_are_both_named(self, tmp_path: Path) -> None:
        manuscript = MARKED + "\n" + "【推测】 " + SENTENCE + "\n\n" + BOUND
        root = _project(tmp_path, manuscript)
        _run(root, "scan", "manuscript.md")
        proc = _recorded(root)
        lines = [line for line in proc.stdout.splitlines() if "claim-without-evidence" in line]
        assert len(lines) == 2, proc.stdout
        assert "【原文】" in lines[0] or "【原文】" in lines[1]
        assert "【推测】" in lines[0] or "【推测】" in lines[1]

    def test_the_verify_verb_agrees_too(self, tmp_path: Path) -> None:
        root = _project(tmp_path, MARKED + "\n" + BOUND)
        _run(root, "scan", "manuscript.md")
        proc = _run(root, "verify", "manuscript.md")
        assert "claim-without-evidence" in _codes(proc), proc.stdout


class TestWhatMustStayQuiet:
    def test_a_block_that_names_the_mark_silences_it(self, tmp_path: Path) -> None:
        # The block says which mark it answers for, so the mark is bound.  Both
        # paths must agree; a mark directly above an unrelated block is *not*
        # bound, and both paths report it (see the class above).
        root = _project(tmp_path, MARKED + "\n" + NAMING)
        _run(root, "scan", "manuscript.md")
        assert "claim-without-evidence" not in _codes(_recorded(root))
        assert "claim-without-evidence" not in _codes(_run(root, "check", "manuscript.md"))

    def test_the_live_run_does_not_say_it_twice(self, tmp_path: Path) -> None:
        root = _project(tmp_path, MARKED + "\n\n" + BOUND)
        live = _run(root, "check", "manuscript.md")
        lines = [line for line in live.stdout.splitlines() if "claim-without-evidence" in line]
        assert len(lines) == 1, live.stdout

    def test_a_stale_ledger_says_nothing_about_marks(self, tmp_path: Path) -> None:
        root = _project(tmp_path, MARKED + "\n" + BOUND)
        _run(root, "scan", "manuscript.md")
        (root / "manuscript.md").write_text(
            MARKED + "\n" + BOUND + "\nA paragraph added after the scan.\n", encoding="utf-8"
        )
        proc = _recorded(root, "--allow-stale")
        assert "claim-without-evidence" not in _codes(proc), proc.stdout

    def test_a_document_without_marks_stays_quiet(self, tmp_path: Path) -> None:
        root = _project(tmp_path, BOUND)
        _run(root, "scan", "manuscript.md")
        proc = _recorded(root)
        assert "claim-without-evidence" not in _codes(proc)


class TestTheFindingIsTheScanners:
    @pytest.mark.parametrize("marker", ["【原文】", "【实测】", "【推测】", "[原文]"])
    def test_every_default_marker_reaches_the_recorded_pass(
        self, tmp_path: Path, marker: str
    ) -> None:
        root = _project(tmp_path, marker + " " + SENTENCE + "\n\n" + BOUND)
        _run(root, "scan", "manuscript.md")
        proc = _recorded(root)
        assert "claim-without-evidence" in _codes(proc), proc.stdout
        assert marker in proc.stdout

    def test_a_mark_inside_a_fence_is_not_reported(self, tmp_path: Path) -> None:
        manuscript = "```markdown\n" + MARKED + "```\n\n" + BOUND
        root = _project(tmp_path, manuscript)
        _run(root, "scan", "manuscript.md")
        proc = _recorded(root)
        assert "claim-without-evidence" not in _codes(proc), proc.stdout
