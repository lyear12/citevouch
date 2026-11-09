"""The opening line only understands ``key=value``, and a colon there is silent.

The body of a claim block writes fields with colons - ``quote: |``, ``id: c1`` -
so an author who writes the page hint one line up the same way is doing what the
format taught them. Measured on a two-page source where the quote is on page 1
and the block asks for page 9:

```text
```claim id=c1 source=paper page=9      -> [high] page-out-of-range
```claim id=c1 source=paper page: 9     -> [info] quote-found page 1, exit 0
```

The second block asked a question about page 9 and the answer came from page 1,
with no line saying the hint had been dropped. ``id: c1`` was worse: the bare
token became the claim's id, so every finding named ``(id:)`` - a name the
author never wrote - and the ledger recorded it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

NL = chr(10)

PAGE_ONE = "We collected 154,391 examples from the corpus." + NL
PAGE_TWO = "The second page says something entirely different." + NL
# A form feed is what pypdf and plain-text extraction agree on as a page break.
TWO_PAGES = PAGE_ONE + chr(12) + PAGE_TWO
MANIFEST = "[sources]" + NL + 'paper = "page.txt"' + NL
ENV = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}


def _project(tmp_path: Path, opening: str, quote: str = PAGE_ONE) -> Path:
    root = tmp_path / "proj"
    root.mkdir(parents=True)
    (root / "page.txt").write_text(TWO_PAGES, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(MANIFEST, encoding="utf-8", newline=NL)
    manuscript = f"```claim {opening}" + NL + "quote: |" + NL + quote + "```" + NL
    (root / "manuscript.md").write_text(manuscript, encoding="utf-8", newline=NL)
    return root


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "citevouch", *args, "--root", str(root)],
        capture_output=True,
        text=True,
        env=ENV,
    )


def _lines(proc: subprocess.CompletedProcess[str]) -> list[str]:
    return [line for line in proc.stdout.splitlines() if line.startswith("[")]


class TestAColonOnTheOpeningLineIsSaidOutLoud:
    def test_a_page_hint_with_a_colon_is_reported(self, tmp_path: Path):
        root = _project(tmp_path, "id=c1 source=paper page: 9")
        got = _run(root, "check", "manuscript.md")
        found = _lines(got)
        unknown = [line for line in found if "claim-field-unknown" in line]
        assert unknown, got.stdout
        # The sentence has to name both spellings, or the author cannot tell
        # whether the key was wrong or the separator was.
        assert "page:" in unknown[0], unknown
        assert "page=" in unknown[0], unknown

    def test_a_misspelt_key_with_a_colon_is_reported(self, tmp_path: Path):
        root = _project(tmp_path, "id=c1 source=paper pgae: 9")
        got = _run(root, "check", "manuscript.md")
        unknown = [line for line in _lines(got) if "claim-field-unknown" in line]
        assert unknown, got.stdout
        assert "pgae" in unknown[0], unknown
        # The sentence must name the spelling that would have worked, or the
        # author is told a key they never meant to write is wrong.
        assert "page=" in unknown[0], unknown

    def test_it_is_reported_on_the_scan_path_too(self, tmp_path: Path):
        """``scan`` writes the ledger, so a dropped hint must be named there."""
        root = _project(tmp_path, "id=c1 source=paper page: 9")
        got = _run(root, "scan", "manuscript.md")
        unknown = [line for line in _lines(got) if "claim-field-unknown" in line]
        assert unknown, got.stdout


class TestTheIdIsNotInvented:
    def test_a_colon_id_does_not_become_the_name(self, tmp_path: Path):
        """``id: c1`` used to make the claim's id the literal string ``id:``."""
        root = _project(tmp_path, "id: c1 source=paper page=1")
        got = _run(root, "check", "manuscript.md")
        out = got.stdout
        assert "id:" not in "".join(line for line in _lines(got) if "quote-found" in line), out
        # And the block is refused rather than verified, because no id was read.
        assert "claim-uncheckable" in out, out

    def test_the_missing_id_is_explained_by_the_colon_finding(self, tmp_path: Path):
        root = _project(tmp_path, "id: c1 source=paper page=1")
        got = _run(root, "check", "manuscript.md")
        out = got.stdout
        assert "claim-field-unknown" in out, out
        assert "id=" in out, out


class TestNothingElseIsDisturbed:
    def test_the_equals_spelling_still_reads_the_page(self, tmp_path: Path):
        """The control: the same hint with ``=`` still reaches the page check."""
        root = _project(tmp_path, "id=c1 source=paper page=9")
        got = _run(root, "check", "manuscript.md")
        assert "page-out-of-range" in got.stdout, got.stdout
        assert "claim-field-unknown" not in got.stdout, got.stdout

    def test_a_correct_block_stays_quiet(self, tmp_path: Path):
        root = _project(tmp_path, "id=c1 source=paper page=1")
        got = _run(root, "check", "manuscript.md")
        assert "claim-field-unknown" not in got.stdout, got.stdout
        assert "quote-found" in got.stdout, got.stdout

    @pytest.mark.parametrize("value", ["weird:name", "10:30", "a:b:c"])
    def test_a_colon_inside_a_value_is_not_a_field(self, tmp_path: Path, value: str):
        """``source=weird:name`` is one value, not a field called ``weird``."""
        root = _project(tmp_path, f"id=c1 source={value} page=1")
        got = _run(root, "check", "manuscript.md")
        assert "claim-field-unknown" not in got.stdout, got.stdout

    def test_a_quoted_value_keeps_its_colon(self, tmp_path: Path):
        """A value may contain ``page: 3``; that is text, not a field.

        The opening line is scanned for ``key:`` tokens, so a quoted value has
        to be blanked first - otherwise a correct block whose marker quotes a
        page reference is accused of writing a field with a colon.
        """
        root = _project(tmp_path, 'id=c1 source=paper page=1 marker="see page: 3"')
        got = _run(root, "check", "manuscript.md")
        assert "claim-field-unknown" not in got.stdout, got.stdout
        # The block itself is fine, so the run verifies it.
        assert "quote-found" in got.stdout, got.stdout

    def test_the_html_dialect_gets_the_same_sentence(self, tmp_path: Path):
        root = tmp_path / "proj"
        root.mkdir(parents=True)
        (root / "page.txt").write_text(TWO_PAGES, encoding="utf-8", newline=NL)
        (root / "sources.toml").write_text(MANIFEST, encoding="utf-8", newline=NL)
        manuscript = "<!-- claim: c1 source=paper page: 9 -->" + NL + ">> " + PAGE_ONE + NL
        (root / "manuscript.md").write_text(manuscript, encoding="utf-8", newline=NL)
        got = _run(root, "check", "manuscript.md")
        assert "claim-field-unknown" in got.stdout, got.stdout
