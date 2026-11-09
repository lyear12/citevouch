"""What a Markdown container does to the sentence `draft` is asked to propose.

A blockquote, a list item and a heading are three ways of *showing* a sentence.
The marker in front of the sentence is typography, not words: nobody reading the
rendered page sees a `>` between the author's words. `draft` read the raw line,
so the marker travelled into the `claim:` field it asks the author to paste, and
- worse - the same sentence then failed to match the source verbatim, because the
page does not contain a `>` either.

Measured before this file existed, one page holding

    We collected 154,391 examples from the corpus.

and a manuscript quoting it verbatim: plain gave `confidence: high` and one
proposal; the same sentence behind `> `, `- `, `* `, `+ `, `## ` or `1) ` gave
`0 claim block(s) proposed` and the comment "nothing on any page shares enough
terms with the sentence (3 needed)" - about a sentence the page shares four
terms with and prints word for word. A false reason attached to a real loss is
worse than no reason, because it sends the author to edit the sentence that was
right.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from citevouch.draft import statement_of

ROOT = Path(__file__).resolve().parents[1]
ENV = {
    **os.environ,
    "PYTHONPATH": str(ROOT / "src"),
    "PYTHONIOENCODING": "utf-8",
}

SENTENCE = "We collected 154,391 examples from the corpus."
PASSAGE = "The corpus we used contains 154,391 sentences in total."


def _project(tmp_path: Path, body: str, page: str = SENTENCE) -> Path:
    root = tmp_path / "project"
    root.mkdir(parents=True)
    (root / "page.txt").write_text(page + "\n", encoding="utf-8", newline="\n")
    (root / "sources.toml").write_text(
        '[sources]\npaper = "page.txt"\n', encoding="utf-8", newline="\n"
    )
    (root / "m.md").write_text(body, encoding="utf-8", newline="\n")
    return root


def _draft(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "citevouch", "draft", "m.md", "-o", "p.md"],
        cwd=root,
        env=ENV,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _proposals(root: Path) -> str:
    path = root / "p.md"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


class TestTheMarkerIsTypographyNotWords:
    @pytest.mark.parametrize(
        "written",
        [
            "> ",
            "- ",
            "* ",
            "+ ",
            "# ",
            "### ",
            "1) ",
            "   > ",
            "> > ",
            "> - ",
            "- > ",
        ],
    )
    def test_each_container_marker_is_dropped(self, written: str) -> None:
        assert statement_of(f"{written}{SENTENCE}") == SENTENCE

    def test_every_line_of_a_wrapped_quote_loses_its_own_marker(self) -> None:
        wrapped = "> The corpus we used contains\n> 154,391 sentences in total."
        assert statement_of(wrapped) == PASSAGE

    def test_a_list_item_continued_on_the_next_line(self) -> None:
        wrapped = "- The corpus we used contains\n  154,391 sentences in total."
        assert statement_of(wrapped) == PASSAGE

    def test_a_four_space_indent_is_a_code_block_and_keeps_its_bullet(self) -> None:
        # CommonMark reads four spaces as a code block, so what follows is a
        # quotation of Markdown rather than prose: the bullet is the sample.
        written = f"    - {SENTENCE}"
        assert statement_of(written) == f"- {SENTENCE}"

    @pytest.mark.parametrize(
        "written",
        [
            f"a > b, and {SENTENCE}",
            f"-- {SENTENCE}",
            f"#hashtag then {SENTENCE}",
            f"-3 degrees, and {SENTENCE}",
            f"2.5 million, and {SENTENCE}",
            f"x - y, and {SENTENCE}",
        ],
    )
    def test_a_marker_lookalike_inside_prose_is_left_alone(self, written: str) -> None:
        assert statement_of(written) == written


class TestTheProposalAfterTheFix:
    @pytest.mark.parametrize("written", ["> ", "- ", "* ", "+ ", "## ", "1) "])
    def test_a_verbatim_sentence_is_proposed_as_verbatim(
        self, tmp_path: Path, written: str
    ) -> None:
        root = _project(tmp_path, f"{written}{SENTENCE} [@paper]\n")
        assert _draft(root).returncode == 0
        text = _proposals(root)
        assert "1 claim block(s) proposed: 1 quoting the sentence verbatim" in text
        assert "confidence: high" in text
        assert f"claim: |\n  {SENTENCE}\n" in text

    def test_a_wrapped_blockquote_becomes_one_line(self, tmp_path: Path) -> None:
        body = "> The corpus we used contains\n> 154,391 sentences in total. [@paper]\n"
        root = _project(tmp_path, body, page=PASSAGE)
        assert _draft(root).returncode == 0
        text = _proposals(root)
        assert "confidence: high" in text
        claim = text.split("claim: |", 1)[1]
        assert f"\n  {PASSAGE}\n" in claim
        assert ">" not in claim

    def test_a_heading_is_proposed_without_its_hashes(self, tmp_path: Path) -> None:
        root = _project(tmp_path, f"## {PASSAGE} [@paper]\n", page=PASSAGE)
        assert _draft(root).returncode == 0
        text = _proposals(root)
        assert f"claim: |\n  {PASSAGE}\n" in text
        assert "claim: |\n  ##" not in text


class TestWhatWasAlreadyRight:
    def test_a_plain_paragraph_still_proposes_the_sentence(self, tmp_path: Path) -> None:
        root = _project(tmp_path, f"{SENTENCE} [@paper]\n")
        assert _draft(root).returncode == 0
        assert "confidence: high" in _proposals(root)

    def test_an_ordered_item_with_a_period_was_never_affected(self, tmp_path: Path) -> None:
        root = _project(tmp_path, f"1. {SENTENCE} [@paper]\n")
        assert _draft(root).returncode == 0
        assert "confidence: high" in _proposals(root)
