"""A citation shown as an example is not a citation the author is making.

Both Markdown and LaTeX have ways of *displaying* a passage instead of writing
it: a fenced block, a code span, an HTML comment, an indented block.  Neither
renders those words as prose, so a `[@key]` inside one is a specimen of the
syntax rather than a place the author cites that key.

Measured before this file existed, with `SAMPLE` printed word for word on the
page and `ghost` a key with no local file, `draft` wrote::

    <!-- line 2: ghost - no local file: not in sources.toml, no `file` field
         in the bibliography, and no file named after the key -->

-an author told their own example has a missing paper.  Two of the three shapes
also lost something worse: the same paragraph then came back with
``0 claim block(s) proposed (0 verbatim)`` and a medium-confidence passage,
because the display markers travelled into the sentence `draft` compared, so a
sentence the page prints word for word no longer matched it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from citevouch import display
from citevouch.cli import main

NL = chr(10)
B3 = chr(96) * 3

SAMPLE = (
    "We collected forty thousand examples from the corpus of written English "
    "and then filtered them by hand before training the model."
)


def _project(tmp_path: Path, manuscript: str) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    (root / "manuscript.md").write_text(manuscript, encoding="utf-8", newline=NL)
    (root / "page.txt").write_text(SAMPLE + NL, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    return root


def _draft(tmp_path: Path, manuscript: str) -> tuple[str, str]:
    root = _project(tmp_path, manuscript)
    code = main(["draft", str(root / "manuscript.md"), "--root", str(root)])
    return code, (root / "claims.md").read_text(encoding="utf-8")


def _notes(written: str) -> list[str]:
    return [line for line in written.splitlines() if line.startswith("<!-- line ")]


def _quote(written: str) -> str:
    lines = written.splitlines()
    for index, line in enumerate(lines):
        if line.strip().startswith("quote:"):
            body: list[str] = []
            for following in lines[index + 1 :]:
                if not following.startswith("  "):
                    break
                body.append(following.strip())
            return " ".join(body)
    return ""


class TestADisplayedCitationIsNotACitation:
    """Each shape displays a citation without making one."""

    @pytest.mark.parametrize(
        "shown",
        [
            B3 + "markdown" + NL + "Cite it as [@ghost] and stop." + NL + B3 + NL,
            "~~~" + NL + "Cite it as [@ghost] and stop." + NL + "~~~" + NL,
            "The syntax is `[@ghost]` and nothing else." + NL,
            "The syntax is ``a `[@ghost]` b`` and nothing else." + NL,
            "<!-- an example: [@ghost] -->" + NL,
            "    [" + NL + "    [@ghost]" + NL,
        ],
        ids=["fence", "tilde", "span", "double-span", "comment", "indented"],
    )
    def test_the_key_is_not_reported_missing(self, tmp_path: Path, shown: str) -> None:
        code, written = _draft(tmp_path, shown + NL + SAMPLE + " [@paper]." + NL)
        assert code == 0
        assert "ghost" not in written, written

    def test_the_prose_around_it_is_still_read(self, tmp_path: Path) -> None:
        shown = B3 + "markdown" + NL + "Cite it as [@ghost]." + NL + B3 + NL
        code, written = _draft(tmp_path, shown + NL + SAMPLE + " [@paper]." + NL)
        assert code == 0
        assert "```claim" in written
        assert _quote(written) == SAMPLE


class TestTheDisplayDoesNotBecomePartOfTheSentence:
    """The markers of a display are not words in the sentence underneath it."""

    @pytest.mark.parametrize(
        "above",
        [
            B3 + "markdown" + NL + "Cite it as [@ghost]." + NL + B3 + NL,
            "<!-- an example: [@ghost] -->" + NL,
            "The syntax is `[@ghost]` and that is all." + NL,
        ],
        ids=["fence", "comment", "span"],
    )
    def test_a_verbatim_sentence_stays_verbatim(self, tmp_path: Path, above: str) -> None:
        code, written = _draft(tmp_path, above + SAMPLE + " [@paper]." + NL)
        assert code == 0
        assert "1 claim block(s) proposed (1 verbatim)" not in written  # sanity: not stderr
        assert "confidence: high" in written, written
        assert _quote(written) == SAMPLE

    def test_without_the_display_it_is_verbatim_too(self, tmp_path: Path) -> None:
        code, written = _draft(tmp_path, SAMPLE + " [@paper]." + NL)
        assert code == 0
        assert "confidence: high" in written
        assert _quote(written) == SAMPLE


class TestWhatMustStillCount:
    """The display mask must not swallow prose that is really prose."""

    def test_a_blockquote_is_prose(self, tmp_path: Path) -> None:
        code, written = _draft(tmp_path, "> " + SAMPLE + " [@paper]." + NL)
        assert code == 0
        assert "```claim" in written


class TestTheDisplayRuleItself:
    """The rules that decide where a display starts and where it stops.

    ``mask`` is checked directly here: an end-to-end run can pass for the wrong
    reason when two neighbouring regions happen to cover the same characters.
    """

    def test_a_tilde_fence_is_not_closed_by_a_backtick_line(self) -> None:
        text = "~~~markdown" + NL + B3 + NL + "Cite it as [@ghost]." + NL + "~~~" + NL
        assert "[@ghost]" not in display.mask(text)

    def test_a_backtick_fence_is_not_closed_by_a_tilde_line(self) -> None:
        text = B3 + "markdown" + NL + "~~~" + NL + "Cite it as [@ghost]." + NL + B3 + NL
        assert "[@ghost]" not in display.mask(text)

    def test_a_long_fence_is_not_closed_by_a_short_one(self) -> None:
        text = (
            "````markdown" + NL + B3 + NL + "Cite it as [@ghost]." + NL + B3 + NL + "````" + NL
        )
        assert "[@ghost]" not in display.mask(text)

    def test_what_follows_a_short_fence_inside_a_long_one_is_still_displayed(self) -> None:
        # If the short line closed the long fence, the prose after it would be
        # read as the author's own words and its `[@real]` reported as missing.
        text = (
            "````markdown"
            + NL
            + B3
            + NL
            + "Cite it as [@ghost]."
            + NL
            + B3
            + NL
            + "And after it [@real]."
            + NL
            + "````"
            + NL
        )
        assert "[@real]" not in display.mask(text)

    def test_a_short_line_does_not_close_a_longer_fence_in_the_first_place(self) -> None:
        # Four backticks open, three appear later, and no other run of four
        # exists - so the two runs cannot pair as a code span either.  A fence
        # is closed by at least as many of its own characters, so this one is
        # still open and the prose after the short line is displayed.
        text = (
            "````markdown"
            + NL
            + "Cite it as [@ghost]."
            + NL
            + B3
            + NL
            + "And after it [@real]."
            + NL
        )
        assert "[@real]" not in display.mask(text)

    def test_the_closing_fence_line_is_displayed_whole(self) -> None:
        # The closing run is longer than the opening one, so no code span pairs
        # them: only the line rule can blank that last line.
        text = "````markdown" + NL + "Cite it as [@ghost]." + NL + "`````" + NL
        assert "`" not in display.mask(text)

    def test_the_closing_fence_is_part_of_the_display(self) -> None:
        text = B3 + NL + "x" + NL + B3 + NL
        assert "`" not in display.mask(text)

    def test_a_line_with_text_after_the_fence_does_not_close_it(self) -> None:
        # CommonMark: a closing fence carries nothing but spaces after it.  A
        # ```` ``` trailing ```` line is sample text, so the fence is still open
        # and everything after it is displayed - which is what `manuscript`
        # already does, and what this mask has to agree with.
        text = B3 + NL + "x" + NL + B3 + " trailing" + NL + "After [@ghost]." + NL
        assert "[@ghost]" not in display.mask(text)

    def test_an_indented_continuation_of_a_list_item_is_prose(self, tmp_path: Path) -> None:
        manuscript = "- A list item" + NL + "    " + SAMPLE + " [@paper]." + NL
        code, written = _draft(tmp_path, manuscript)
        assert code == 0
        assert "```claim" in written, written
        assert "paper - no local file" not in written


class TestTheMaskKeepsTheShapeOfTheFile:
    """A position in the masked text has to be the same position in the file.

    Every answer `draft` gives is quoted back with a line number, so the mask
    may change characters but never the length of the text and never where its
    line breaks are.
    """

    TEXT = (
        "Prose `[@ghost]` here."
        + NL
        + B3
        + "markdown"
        + NL
        + "A sample [@ghost2]."
        + NL
        + B3
        + NL
        + "<!-- [@ghost3] -->"
        + NL
        + NL
        + "    [@ghost4]"
        + NL
    )

    def test_the_length_is_unchanged(self) -> None:
        assert len(display.mask(self.TEXT)) == len(self.TEXT)

    def test_every_newline_stays_where_it_was(self) -> None:
        before = [index for index, char in enumerate(self.TEXT) if char == NL]
        after = [index for index, char in enumerate(display.mask(self.TEXT)) if char == NL]
        assert after == before

    def test_the_displayed_characters_are_gone_and_the_prose_is_not(self) -> None:
        masked = display.mask(self.TEXT)
        assert "ghost" not in masked
        assert masked.startswith("Prose ")


class TestWhatTheDisplayRuleHasToKnow:
    """The rule that closes a fence, and the rule that lets one stay open."""

    def test_a_tilde_fence_is_not_closed_by_backticks(self, tmp_path: Path) -> None:
        shown = (
            "~~~markdown" + NL + B3 + NL + "Cite it as [@ghost]." + NL + B3 + NL + "~~~" + NL
        )
        code, written = _draft(tmp_path, shown + NL + SAMPLE + " [@paper]." + NL)
        assert code == 0
        assert "ghost" not in written, written

    def test_a_backtick_fence_is_not_closed_by_tildes(self, tmp_path: Path) -> None:
        shown = (
            B3
            + "markdown"
            + NL
            + "~~~"
            + NL
            + "Cite it as [@ghost]."
            + NL
            + "~~~"
            + NL
            + B3
            + NL
        )
        code, written = _draft(tmp_path, shown + NL + SAMPLE + " [@paper]." + NL)
        assert code == 0
        assert "ghost" not in written, written

    def test_an_unclosed_fence_runs_to_the_end_of_the_file(self, tmp_path: Path) -> None:
        manuscript = (
            SAMPLE
            + " [@paper]."
            + NL
            + NL
            + B3
            + "markdown"
            + NL
            + "Cite it as [@ghost]."
            + NL
            + "And as [@ghost2]."
            + NL
        )
        code, written = _draft(tmp_path, manuscript)
        assert code == 0
        assert "ghost" not in written, written
        assert "```claim" in written


class TestARealCitationIsStillMissedWhenItIsMissing:
    """The point is to stop reading examples, not to stop reading citations."""

    def test_a_key_with_no_file_is_still_reported(self, tmp_path: Path) -> None:
        code, written = _draft(tmp_path, SAMPLE + " [@ghost]." + NL)
        assert code == 0
        assert "ghost" in written
