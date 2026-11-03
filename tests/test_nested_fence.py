"""A second ```claim fence inside an unfinished one used to vanish.

Two claim blocks written back to back, with the first one's closing fence
missing:

    Intro.

    ```claim id=c1 source=paper page=1
    quote: |
      the corpus holds 154,391 sentences
    ```claim id=c2 source=paper page=1
    quote: |
      a second sentence that is also on the page
    ```

The parser reads from the first opener to the first line that is exactly ```,
which here is the *second* block's closer - so the second block's opener and
quote are absorbed into the first block's quote.  Measured before this was
fixed, on a project where both sentences are on page 1:

    scan                   -> exit 0, "wrote citevouch.lock.json (1 claim)"
    check                  -> exit 1, [high] quote-missing at :3
                              "…sentences ```claim id=c2 sourc… - quote not in paper.txt"

`id=c2` appears nowhere in the report and nowhere in the ledger: the author
wrote two claims and one of them silently stopped existing.  The only line they
do get sends them to check the PDF against a quote they never wrote - it has a
fence line spliced into the middle of it.

Three backticks around ```claim lines are genuinely ambiguous (a sample of the
syntax looks the same as a forgotten closer), which is why this project reports
line 1 rather than guessing.  What it must not do is report nothing.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from citevouch.manuscript import parse_manuscript

PAGE = "The corpus holds 154,391 sentences.\nA second sentence that is also on the page.\n"
SOURCES = b'[sources]\npaper = "paper.txt"\n'
BAD = (
    "```claim id=c1 source=paper page=1\n"
    "quote: |\n"
    "  the corpus holds 154,391 sentences\n"
    "```claim id=c2 source=paper page=1\n"
    "quote: |\n"
    "  a second sentence that is also on the page\n"
    "```\n"
)
GOOD = (
    "```claim id=c1 source=paper page=1\n"
    "quote: |\n"
    "  the corpus holds 154,391 sentences\n"
    "```\n\n"
    "```claim id=c2 source=paper page=1\n"
    "quote: |\n"
    "  a second sentence that is also on the page\n"
    "```\n"
)


def _project(tmp_path: Path, body: str) -> Path:
    (tmp_path / "paper.txt").write_bytes(PAGE.encode())
    (tmp_path / "sources.toml").write_bytes(SOURCES)
    (tmp_path / "manuscript.md").write_bytes(("Intro.\n\n" + body).encode())
    return tmp_path


def _run(root: Path, *args: str) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, "-m", "citevouch", *args],
        cwd=root,
        env={
            **os.environ,
            "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.returncode, (result.stdout or "") + (result.stderr or "")


class TestTheParserSaysTheFenceIsMissing:
    def test_the_second_block_does_not_disappear_silently(self):
        result = parse_manuscript(BAD)
        codes = [finding.code for finding in result.findings]
        assert "claim-block-unclosed" in codes, result.findings
        finding = next(f for f in result.findings if f.code == "claim-block-unclosed")
        assert finding.line == 1
        assert "line 4" in finding.message

    def test_the_sentence_the_author_wrote_is_still_a_claim(self):
        """Splitting is the reading that loses nothing, so split."""
        result = parse_manuscript(BAD)
        assert [claim.id for claim in result.claims] == ["c1", "c2"]
        first = next(claim for claim in result.claims if claim.id == "c1")
        assert "```claim" not in first.quote

    def test_an_unclosed_block_at_the_end_is_still_reported_once(self):
        text = "```claim id=c1 source=a page=1\nquote: |\n  words\n"
        result = parse_manuscript(text)
        assert [f.code for f in result.findings] == ["claim-block-unclosed"]
        assert result.findings[0].line == 1

    def test_an_ordinary_unclosed_sentence_is_unchanged(self):
        """No nested opener: the existing message must not start claiming one."""
        text = "```claim id=c1 source=a page=1\nquote: |\n  words\n"
        result = parse_manuscript(text)
        assert "a second claim fence" not in result.findings[0].message


class TestTheCommand:
    def test_scan_is_not_green_about_the_block_it_never_read(self, tmp_path: Path):
        root = _project(tmp_path, BAD)
        code, text = _run(root, "scan", "manuscript.md")
        assert code == 1, text
        assert "claim-block-unclosed" in text

    def test_both_claims_reach_the_ledger(self, tmp_path: Path):
        root = _project(tmp_path, BAD)
        _run(root, "scan", "manuscript.md")
        ledger = (root / "citevouch.lock.json").read_text(encoding="utf-8")
        assert '"c2"' in ledger, ledger

    def test_the_quote_does_not_carry_a_fence_line(self, tmp_path: Path):
        root = _project(tmp_path, BAD)
        code, text = _run(root, "check", "manuscript.md")
        assert code == 1, text
        assert "```claim id=c2" not in text

    def test_a_properly_closed_pair_is_silent(self, tmp_path: Path):
        root = _project(tmp_path, GOOD)
        code, text = _run(root, "check", "manuscript.md")
        assert code == 0, text
        assert "claim-block-unclosed" not in text
