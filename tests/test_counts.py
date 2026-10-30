"""A count written next to a word is a sentence, and sentences agree.

The tool prints sentences like "1 bibliography entry is cited by no claim" and
"3 characters at line 1 were between entries and were not read".  Those are
read by people, and a reader who sees "1 bibliography entries are cited" learns
something true about the author's attention to detail and something false about
the tool's.

The failure mode this guards is narrow and repeatable: a plural spelled inline
(`f"{n} entries"`) is correct for every count except the ones a test would
naturally pick.  Every existing test for these two findings asserted that the
*code* appeared, never what the sentence said, so both defects shipped.

The shared spellings live in `textnorm.count_of` / `word_for` / `verb_for` /
`is_are`.  `report.py` and `cli.py` had their own copies of the same three
rules; `bibtex.py` and `verify.py` had none and rolled the sentence by hand.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from citevouch.textnorm import count_of, is_are, verb_for, word_for

NL = chr(10)
ROOT = Path(__file__).resolve().parents[1]

TEXT = NL.join(
    [
        "A Study of Sentence Length",
        "=" * 28,
        "",
        "The corpus contains 154,391 sentences in total.",
        "",
    ]
)
CLAIM = NL.join(
    [
        "```claim id=c1 source=paper page=1",
        'quote: "The corpus contains 154,391 sentences in total."',
        "```",
        "",
    ]
)


def _run(project: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    """Run the real command, because the sentence is the product."""
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "PYTHONIOENCODING": "utf-8",
    }
    return subprocess.run(
        [sys.executable, "-m", "citevouch", *argv],
        cwd=str(project),
        env=env,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _project(tmp_path: Path, bib_text: str) -> Path:
    (tmp_path / "m.md").write_text(CLAIM, encoding="utf-8", newline=NL)
    (tmp_path / "paper.txt").write_text(TEXT, encoding="utf-8", newline=NL)
    (tmp_path / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "paper.txt"' + NL, encoding="utf-8", newline=NL
    )
    (tmp_path / "r.bib").write_text(bib_text, encoding="utf-8", newline=NL)
    return tmp_path


def _line(text: str, needle: str) -> str:
    for line in text.splitlines():
        if needle in line:
            return line
    raise AssertionError(f"no line mentioning {needle!r} in:\n{text}")


class TestTheSharedSpelling:
    """The helper itself, before anything is asked to use it."""

    def test_a_count_of_one_is_singular(self):
        assert count_of(1, "claim") == "1 claim"

    def test_zero_takes_the_plural(self):
        # "0 claims", not "0 claim": English puts zero with the plural, and a
        # ledger with no bibliography is the common case.
        assert count_of(0, "claim") == "0 claims"

    def test_an_irregular_plural_is_said_out_loud(self):
        assert count_of(1, "entry", "entries") == "1 entry"
        assert count_of(2, "entry", "entries") == "2 entries"

    def test_the_bare_word_and_the_verb_agree_with_it(self):
        assert word_for(1, "claim") == "claim"
        assert word_for(2, "claim") == "claims"
        assert verb_for(1) == "was"
        assert verb_for(2) == "were"
        assert is_are(1) == "is"
        assert is_are(2) == "are"


class TestTheVerifierAgreesWithItsCount:
    def test_one_unused_entry_is_singular(self, tmp_path: Path):
        project = _project(
            tmp_path, "@article{lonely, title={T}, author={A}, year={2019}}" + NL
        )
        done = _run(project, "check", "m.md", "--bib", "r.bib")
        line = _line(done.stdout + done.stderr, "bib-key-unused")
        assert "1 bibliography entry is cited by no claim" in line
        assert "entries" not in line
        assert " are " not in line

    def test_several_unused_entries_are_plural(self, tmp_path: Path):
        body = "".join(
            f"@article{{k{i}, title={{T}}, author={{A}}, year={{2019}}}}{NL}" for i in range(3)
        )
        project = _project(tmp_path, body)
        done = _run(project, "check", "m.md", "--bib", "r.bib")
        line = _line(done.stdout + done.stderr, "bib-key-unused")
        assert "3 bibliography entries are cited by no claim" in line


class TestTheBibliographyReaderAgreesWithItsCount:
    def test_one_stray_character_is_singular(self, tmp_path: Path):
        project = _project(
            tmp_path, "@article{a, title={T}, author={A}, year={2019}}" + NL + "x" + NL
        )
        done = _run(project, "check", "m.md", "--bib", "r.bib")
        line = _line(done.stdout + done.stderr, "bib-entry-header-unparsed")
        assert "1 character at line 1 was between entries" in line
        assert " was not read" in line
        # Both halves of the sentence have to agree.  The first version of this
        # fix changed only the first verb and left "and were not read", which
        # is how it was caught.
        assert "were" not in line
        assert "characters" not in line

    def test_several_stray_characters_are_plural(self, tmp_path: Path):
        project = _project(
            tmp_path, "@article{a, title={T}, author={A}, year={2019}}" + NL + "xyz" + NL
        )
        done = _run(project, "check", "m.md", "--bib", "r.bib")
        line = _line(done.stdout + done.stderr, "bib-entry-header-unparsed")
        assert "3 characters at line 1 were between entries" in line
        assert "were not read" in line

    def test_stray_text_between_two_entries_counts_the_same_way(self, tmp_path: Path):
        # The reader has two branches for this finding: text after the last
        # entry, and text between two entries.  Fixing one and testing it
        # leaves the other hand-rolled -- which is exactly what the first
        # attempt at this fix did, and the reverse verification said so.
        one = (
            "@article{a, title={T}, author={A}, year={2019}}"
            + NL
            + "x"
            + NL
            + "@article{b, title={T}, author={A}, year={2020}}"
            + NL
        )
        project = _project(tmp_path, one)
        done = _run(project, "check", "m.md", "--bib", "r.bib")
        line = _line(done.stdout + done.stderr, "bib-entry-header-unparsed")
        assert "1 character at line 1 was between entries" in line
        assert "was not read" in line
        assert "were" not in line
        assert "characters" not in line

    def test_text_between_two_entries_is_plural_for_several(self, tmp_path: Path):
        three = (
            "@article{a, title={T}, author={A}, year={2019}}"
            + NL
            + "xyz"
            + NL
            + "@article{b, title={T}, author={A}, year={2020}}"
            + NL
        )
        project = _project(tmp_path, three)
        done = _run(project, "check", "m.md", "--bib", "r.bib")
        line = _line(done.stdout + done.stderr, "bib-entry-header-unparsed")
        assert "3 characters at line 1 were between entries" in line
        assert "were not read" in line


class TestNobodyRollsItByHand:
    """A fifth copy of the rule would pass every test above."""

    @pytest.mark.parametrize(
        "module",
        ["bibtex.py", "cli.py", "report.py", "verify.py"],
    )
    def test_the_plural_rules_come_from_one_module(self, module: str):
        text = (ROOT / "src" / "citevouch" / module).read_text(encoding="utf-8")
        # `noun + "s"` and `noun}s`) are the two spellings of a hand-rolled
        # plural.  Neither may appear in a message-building module any more.
        assert 'noun + "s"' not in text, f"{module} spells a plural by hand"
        assert "{noun}s" not in text, f"{module} spells a plural by hand"
