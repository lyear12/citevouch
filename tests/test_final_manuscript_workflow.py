"""The final-manuscript workflow, walked end to end against the real CLI.

``docs/final-manuscript.md`` describes what a writer does with this tool once
their Markdown is the version they mean to submit: draft proposals, read them,
copy the ones they accept into that manuscript, record, and then live with a CI
job that compares the manuscript with the record.  Until now that path was
described in prose and tested nowhere, which is how a workflow rots: each step
is covered by its own unit test, and the seams between them are covered by
nobody.

The seam that mattered, measured on v0.26.1 in a clean venv built from the
published wheel: after copying a reviewed block into ``final.md`` and running
``citevouch scan final.md``, the project is green.  Editing one unrelated
sentence then makes ``check --use-recorded`` exit 1 with ``ledger-stale`` --
correctly, because the ledger records the whole manuscript's digest -- and the
documented recovery is to scan again, after which it is green again.  Nothing in
the suite walked that loop, so nothing would have noticed if re-recording had
stopped clearing the finding.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
ENV = {**os.environ, "PYTHONPATH": str(SRC), "PYTHONIOENCODING": "utf-8"}

PAGE = (
    "We collected 40,688 examples from the corpus, of which 1,204 were held out "
    "for evaluation.\n"
)

MANUSCRIPT = """\
# Method

We collected 40,688 examples from the corpus [@paper].

# Discussion

It matters.
"""


def _citevouch(root: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "citevouch", *argv],
        cwd=root,
        env=ENV,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _verdict(root: Path, *argv: str) -> tuple[int, dict, list[str]]:
    result = _citevouch(root, *argv, "--format", "json")
    payload: dict = {}
    if result.stdout.strip().startswith("{"):
        payload = json.loads(result.stdout)
    return (
        result.returncode,
        payload.get("summary", {}),
        [finding["code"] for finding in payload.get("findings", [])],
    )


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "paper"
    project.mkdir()
    (project / "page.txt").write_text(PAGE, encoding="utf-8", newline="\n")
    (project / "sources.toml").write_text(
        '[sources]\npaper = "page.txt"\n', encoding="utf-8", newline="\n"
    )
    (project / "final.md").write_text(MANUSCRIPT, encoding="utf-8", newline="\n")
    return project


def _proposed_block(proposals: Path) -> str:
    text = proposals.read_text(encoding="utf-8")
    start = text.find("```claim")
    assert start >= 0, "draft proposed nothing, so nothing downstream can be walked"
    end = text.find("\n```", start) + 4
    return text[start:end]


def _ledger(project: Path) -> dict:
    return json.loads((project / "citevouch.lock.json").read_text(encoding="utf-8"))


class TestTheWriterWalksItInOrder:
    def test_draft_review_copy_record_and_gate(self, tmp_path: Path) -> None:
        project = _project(tmp_path)

        drafted = _citevouch(project, "draft", "final.md")
        assert drafted.returncode == 0, drafted.stdout + drafted.stderr
        proposals = project / "claims.md"
        assert proposals.is_file(), "draft wrote no proposals file"

        # The writer reads the proposal, decides it is right, and copies it into
        # the manuscript they intend to submit.  This is the only human step.
        (project / "final.md").write_text(
            "# Method\n\n" + _proposed_block(proposals) + "\n\n# Discussion\n\nIt matters.\n",
            encoding="utf-8",
            newline="\n",
        )

        code, summary, codes = _verdict(project, "check", "final.md")
        assert code == 0 and summary["verified"] == 1 and codes == ["quote-found"]

        recorded = _citevouch(project, "scan", "final.md")
        assert recorded.returncode == 0, recorded.stdout + recorded.stderr
        assert _ledger(project)["manuscript"] == "final.md"

        code, summary, codes = _verdict(
            project, "check", "final.md", "--use-recorded", "--fail-on", "medium"
        )
        assert code == 0 and summary["verified"] == 1 and codes == ["quote-found"]

    def test_an_unrelated_prose_edit_is_re_answered_by_re_recording(
        self, tmp_path: Path
    ) -> None:
        project = _project(tmp_path)
        _citevouch(project, "draft", "final.md")
        (project / "final.md").write_text(
            "# Method\n\n"
            + _proposed_block(project / "claims.md")
            + "\n\n# Discussion\n\nIt matters.\n",
            encoding="utf-8",
            newline="\n",
        )
        _citevouch(project, "scan", "final.md")

        edited = (
            (project / "final.md")
            .read_text(encoding="utf-8")
            .replace("It matters.", "The results matter.")
        )
        (project / "final.md").write_text(edited, encoding="utf-8", newline="\n")

        code, summary, codes = _verdict(
            project, "check", "final.md", "--use-recorded", "--fail-on", "medium"
        )
        assert code == 1 and codes == ["ledger-stale"], (
            "a prose edit must be caught by the recorded gate, and it must be the "
            "only thing reported: the claim itself did not change"
        )
        assert summary["verified"] == 0
        assert summary["skipped"] == 1

        again = _citevouch(project, "scan", "final.md")
        assert again.returncode == 0
        code, summary, codes = _verdict(
            project, "check", "final.md", "--use-recorded", "--fail-on", "medium"
        )
        assert code == 0 and summary["verified"] == 1, (
            "re-recording is the documented recovery and has to clear the finding"
        )

    def test_the_page_hint_and_the_source_are_answered_differently(
        self, tmp_path: Path
    ) -> None:
        project = _project(tmp_path)
        _citevouch(project, "draft", "final.md")
        reviewed = (
            "# Method\n\n"
            + _proposed_block(project / "claims.md")
            + "\n\n# Discussion\n\nIt matters.\n"
        )
        (project / "final.md").write_text(reviewed, encoding="utf-8", newline="\n")
        _citevouch(project, "scan", "final.md")

        (project / "final.md").write_text(
            reviewed.replace("page=1", "page=3"), encoding="utf-8", newline="\n"
        )
        code, _, codes = _verdict(project, "check", "final.md")
        assert code == 1 and "page-out-of-range" in codes, (
            "asking for a page the one-page source does not have must be said, "
            "not silently answered from page 1"
        )

        (project / "final.md").write_text(reviewed, encoding="utf-8", newline="\n")
        _citevouch(project, "scan", "final.md")
        (project / "page.txt").write_text(
            PAGE.replace("1,204", "1,205"), encoding="utf-8", newline="\n"
        )
        code, summary, codes = _verdict(
            project, "check", "final.md", "--use-recorded", "--fail-on", "medium"
        )
        assert code == 1
        assert "source-changed" in codes, (
            "the source is compared with the digest in the ledger, which is the "
            "only way a recorded run can notice the page changed"
        )
        assert summary["missing"] == 1


class TestTheProposalsFileIsNotTheManuscript:
    def test_reviewing_proposals_needs_no_ledger_of_their_own(self, tmp_path: Path) -> None:
        """``check`` on the proposals file answers without touching the record."""
        project = _project(tmp_path)
        _citevouch(project, "draft", "final.md")
        assert not (project / "citevouch.lock.json").exists()

        code, summary, codes = _verdict(project, "check", "claims.md")
        assert code == 0 and summary["verified"] == 1 and codes == ["quote-found"]
        assert not (project / "citevouch.lock.json").exists(), (
            "check must not write the project's ledger; only scan records"
        )

    def test_recording_proposals_needs_a_ledger_of_their_own(self, tmp_path: Path) -> None:
        """A proposals ledger goes beside the project ledger, never over it.

        The alternative is measured in docs/final-manuscript.md: ``scan`` writes
        whatever document it was pointed at into the ledger it is given, so
        scanning the proposals file with the default ledger replaces the record
        of the manuscript the project is actually about.
        """
        project = _project(tmp_path)
        (project / "final.md").write_text(
            "# Method\n\n"
            + _proposed_block(
                _draft_into(project),
            )
            + "\n\n# Discussion\n\nIt matters.\n",
            encoding="utf-8",
            newline="\n",
        )
        _citevouch(project, "scan", "final.md")
        assert _ledger(project)["manuscript"] == "final.md"

        separate = _citevouch(project, "scan", "claims.md", "--ledger", "claims.lock.json")
        assert separate.returncode == 0, separate.stdout + separate.stderr
        assert _ledger(project)["manuscript"] == "final.md", (
            "the project's ledger still describes the manuscript"
        )
        claims_ledger = json.loads((project / "claims.lock.json").read_text(encoding="utf-8"))
        assert claims_ledger["manuscript"] == "claims.md"


def _draft_into(project: Path) -> Path:
    result = _citevouch(project, "draft", "final.md")
    assert result.returncode == 0, result.stdout + result.stderr
    return project / "claims.md"
