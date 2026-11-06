"""A marker marks the line it starts; inside a sentence it is a word.

`scan_unbound_markers` asked `marker in line` and reported every line that
contained the characters, so `demo/manuscript.md:3` - which only *names* the
convention ("这份节选保留了原档的【原文】/【实测】/【推测】三级标记约定") - was
reported as a sentence that claims something without evidence.  The demo's own
output carried a false accusation; a reader who reached line 3 to fix it found
a remark about the notation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from citevouch.manuscript import parse_manuscript, scan_unbound_markers

REPO = Path(__file__).resolve().parents[1]
DEMO = REPO / "demo" / "manuscript.md"


def _lines(text: str) -> list[int]:
    return [
        finding.line
        for finding in scan_unbound_markers(text, spans=parse_manuscript(text).spans)
    ]


class TestAMarkerThatStartsItsLineCounts:
    """Every decorative prefix real manuscripts use, then the mark."""

    @pytest.mark.parametrize(
        "prefix",
        [
            "",
            "- ",
            "* ",
            "+ ",
            "> ",
            "> > ",
            "1. ",
            "2) ",
            "    ",
            "　",  # ideographic space, which CJK documents indent with
            "**",
            "__",
            "*",
        ],
    )
    def test_the_prefix_does_not_hide_the_mark(self, prefix: str) -> None:
        text = prefix + "【原文】PyFCG 3.3 installs cleanly.\n"
        assert _lines(text) == [1]

    def test_the_square_bracket_spelling_counts_too(self) -> None:
        assert _lines("[原文] PyFCG 3.3 installs cleanly.\n") == [1]

    @pytest.mark.parametrize(
        "marker", ["【原文】", "【实测】", "【推测】", "[原文]", "[实测]", "[推测]"]
    )
    def test_every_documented_mark_starts_a_line(self, marker: str) -> None:
        assert _lines(marker + "PyFCG 3.3 installs cleanly.\n") == [1]

    def test_a_later_line_counts_too(self) -> None:
        text = "A first paragraph.\n\n- 【推测】the gain is 3 points.\n"
        assert _lines(text) == [3]


class TestAMentionInsideProseIsNotAMark:
    """The demo's own line, and the other shapes a mention takes."""

    def test_the_demo_line_that_names_the_convention(self) -> None:
        text = "> 这份节选保留了原档的【原文】/【实测】/【推测】三级标记约定，只是把\n"
        assert _lines(text) == []

    @pytest.mark.parametrize(
        "text",
        [
            "We keep the 【原文】 convention in this section.\n",
            "The token `【原文】` is how you mark a line.\n",
            "<!-- 【原文】 the sentence you quote -->\n",
            "| 【原文】 | PyFCG 3.3 installs cleanly. |\n",
            "PyFCG 【原文】 installs cleanly.\n",
        ],
    )
    def test_a_mention_is_not_an_accusation(self, text: str) -> None:
        assert _lines(text) == []


class TestTheDemoNoLongerAccusesItsOwnRemark:
    def test_the_two_bare_claims_are_still_reported(self) -> None:
        text = DEMO.read_text(encoding="utf-8")
        assert _lines(text) == [52, 54]

    def test_line_three_is_not_reported(self) -> None:
        text = DEMO.read_text(encoding="utf-8")
        assert 3 not in _lines(text)


class TestTheCoveredSpansStillExist:
    """The spans exemption is unchanged - only the admission test moved."""

    def test_a_mark_at_the_start_of_a_quote_is_exempt_with_spans(self) -> None:
        text = "```claim id=c1 source=a\nquote: |\n  【原文】 quoted here\n```\n"
        assert len(scan_unbound_markers(text)) == 1
        assert scan_unbound_markers(text, spans=parse_manuscript(text).spans) == []

    def test_a_mark_inside_prose_beside_a_block_is_still_reported(self) -> None:
        text = (
            "【原文】a bare sentence.\n\n```claim id=c1 source=a\nquote: |\n  words here\n```\n"
        )
        assert _lines(text) == [1]
