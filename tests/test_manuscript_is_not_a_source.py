"""A source may not be the manuscript it is supposed to prove.

The only evidence this tool has for a quote is the text of another file. When
that file is the manuscript itself, the claim block that asserts a sentence is
also the page that contains it: the quote is "found", the claim is "verified",
and the sentence may have been invented for the occasion.

Measured before the fix - a sentence that exists nowhere on earth, with the
manifest naming the manuscript:

    manifest -> manuscript     rc=0  [info] quote-found ... quote found on page 1
    manifest -> copy of it     rc=0  [info] quote-found ... quote found on page 1
    --source manuscript        rc=0  [info] quote-found ... quote found on page 1
    control: real source       rc=1  [high] quote-missing

The third line is the one that matters: `--source` was checked against
`source.toml` for a *typo* and resolved to a file, and no pass asked whether
the file it had just opened was the file being checked.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"}

# Appears nowhere except inside the claim block that asserts it.
FABRICATED = "We collected precisely 987,654 examples under a blue moon."
PAGE = "A page that is not the manuscript.\n"

PAPER = f"""\
# A paper

Some prose that is not a quote.

```claim id=c1 source=paper page=1
quote: |
  {FABRICATED}
```
"""


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "citevouch", *args],
        cwd=root,
        env=ENV,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _codes(proc: subprocess.CompletedProcess[str]) -> list[str]:
    out = []
    for line in (proc.stdout + proc.stderr).splitlines():
        if line.startswith("[") and "] " in line:
            out.append(line.split("] ", 1)[1].split(" ", 1)[0].rstrip(":"))
    return out


def _project(tmp_path: Path, manifest: str, extra: dict[str, str] | None = None) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "paper.md").write_text(PAPER, encoding="utf-8", newline="\n")
    (root / "sources.toml").write_text(manifest, encoding="utf-8", newline="\n")
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline="\n")
    for name, body in (extra or {}).items():
        (root / name).write_text(body, encoding="utf-8", newline="\n")
    return root


class TestTheManuscriptIsNotEvidence:
    def test_the_manifest_may_not_name_the_manuscript(self, tmp_path: Path) -> None:
        root = _project(tmp_path, '[sources]\npaper = "paper.md"\n')
        proc = _run(root, "check", "paper.md", "--root", ".")
        assert proc.returncode == 1, (proc.stdout, proc.stderr)
        assert "quote-found" not in _codes(proc)
        assert "source-is-manuscript" in _codes(proc)

    def test_the_message_says_which_key_did_it(self, tmp_path: Path) -> None:
        root = _project(tmp_path, '[sources]\npaper = "paper.md"\n')
        proc = _run(root, "check", "paper.md", "--root", ".")
        text = proc.stdout + proc.stderr
        assert "'paper'" in text
        assert "paper.md" in text

    def test_scan_reports_it_too(self, tmp_path: Path) -> None:
        root = _project(tmp_path, '[sources]\npaper = "paper.md"\n')
        proc = _run(root, "scan", "paper.md", "--root", ".")
        assert proc.returncode == 1
        assert "source-is-manuscript" in _codes(proc)

    def test_the_recorded_pass_reports_it_too(self, tmp_path: Path) -> None:
        root = _project(tmp_path, '[sources]\npaper = "paper.md"\n')
        _run(root, "scan", "paper.md", "--root", ".")
        proc = _run(root, "check", "paper.md", "--root", ".", "--use-recorded")
        assert proc.returncode == 1
        assert "source-is-manuscript" in _codes(proc)

    def test_scan_alone_catches_a_copy(self, tmp_path: Path) -> None:
        # `check` runs `scan` and then `verify`, and both now guard.  That made
        # the scan-side guard invisible to the test above: removing its digest
        # left the run red anyway, because the verifier caught the claim on the
        # way past.  A project whose only pass is `scan` is the case that
        # separates them, and `scan` is what writes the ledger everyone else
        # reads.
        root = _project(
            tmp_path,
            '[sources]\npaper = "copy.md"\n',
            {"copy.md": PAPER},
        )
        proc = _run(root, "scan", "paper.md", "--root", ".")
        assert proc.returncode == 1, (proc.stdout, proc.stderr)
        assert "source-is-manuscript" in _codes(proc)

    def test_the_ledger_does_not_record_the_manuscript_as_a_source(
        self, tmp_path: Path
    ) -> None:
        # Reporting the problem and then recording the bad binding anyway would
        # leave the next `check --use-recorded` with a source it must refuse
        # again, and a reader of the ledger wondering which of the two rows is
        # the truth.
        import json

        root = _project(tmp_path, '[sources]\npaper = "paper.md"\n')
        _run(root, "scan", "paper.md", "--root", ".")
        blob = json.loads((root / "citevouch.lock.json").read_text(encoding="utf-8"))
        assert blob["sources"] == {}, blob["sources"]

    def test_a_copy_of_the_manuscript_is_not_evidence_either(self, tmp_path: Path) -> None:
        root = _project(
            tmp_path,
            '[sources]\npaper = "copy.md"\n',
            {"copy.md": PAPER},
        )
        proc = _run(root, "check", "paper.md", "--root", ".")
        assert proc.returncode == 1
        assert "quote-found" not in _codes(proc)


class TestTheControlStillWorks:
    def test_a_real_source_still_finds_its_quote(self, tmp_path: Path) -> None:
        body = "We collected 154,391 examples from the corpus.\n"
        paper = (
            "# A paper\n\n"
            "```claim id=c1 source=paper page=1\n"
            "quote: |\n"
            "  We collected 154,391 examples from the corpus.\n"
            "```\n"
        )
        root = tmp_path / "proj"
        root.mkdir()
        (root / "paper.md").write_text(paper, encoding="utf-8", newline="\n")
        (root / "page.txt").write_text(body, encoding="utf-8", newline="\n")
        (root / "sources.toml").write_text(
            '[sources]\npaper = "page.txt"\n', encoding="utf-8", newline="\n"
        )
        proc = _run(root, "check", "paper.md", "--root", ".")
        assert proc.returncode == 0, (proc.stdout, proc.stderr)
        assert "quote-found" in _codes(proc)

    def test_a_quote_missing_from_a_real_source_is_still_missing(self, tmp_path: Path) -> None:
        root = _project(tmp_path, '[sources]\npaper = "page.txt"\n')
        proc = _run(root, "check", "paper.md", "--root", ".")
        assert proc.returncode == 1
        assert "quote-missing" in _codes(proc)


class TestTheSourceIsStillAllowedToMentionTheManuscript:
    def test_a_source_may_be_a_different_file_with_the_same_words(self, tmp_path: Path) -> None:
        # Same sentence on a real page: this is the ordinary case and it must
        # keep verifying - the rule is about the *file*, not about the text.
        body = FABRICATED + "\n"
        root = tmp_path / "proj"
        root.mkdir()
        (root / "paper.md").write_text(PAPER, encoding="utf-8", newline="\n")
        (root / "page.txt").write_text(body, encoding="utf-8", newline="\n")
        (root / "sources.toml").write_text(
            '[sources]\npaper = "page.txt"\n', encoding="utf-8", newline="\n"
        )
        proc = _run(root, "check", "paper.md", "--root", ".")
        assert proc.returncode == 0, (proc.stdout, proc.stderr)
        assert "quote-found" in _codes(proc)


class TestTheSourceFlagIsJudgedTheSameWay:
    def test_source_pointing_at_the_manuscript_is_refused(self, tmp_path: Path) -> None:
        root = _project(tmp_path, "")
        proc = _run(root, "check", "paper.md", "--root", ".", "--source", "paper.md")
        assert proc.returncode != 0
        assert "quote-found" not in _codes(proc)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
