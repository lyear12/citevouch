"""A claim block that declares `marker=` must bind the mark line beside it.

`marker=` has been read from the opening line since the first commit, stored on
``Claim.marker``, written to the ledger, and read back from it - and used by
nothing.  Measured on this manuscript::

    【原文】PyFCG 3.3 installs cleanly.

    ```claim id=c1 source=a marker=【原文】
    quote: |
      PyFCG 3.3 installs cleanly.
    ```

``scan`` reported ``[low] claim-without-evidence at m.md:1: the 【原文】 mark
on this line has no claim block, so nothing ties it to a page in a local
source`` while the ledger for that same run recorded ``marker='【原文】'`` for
``c1``.  The document held the binding and the sentence said it did not.
"""

from __future__ import annotations

import pytest

from citevouch.manuscript import (
    _bound_mark_lines,
    _paragraph_above,
    parse_manuscript,
    scan_unbound_markers,
)
from citevouch.textnorm import read_text

NL = chr(10)
B3 = chr(96) * 3

MARK = "【原文】"
GUESS = "【推测】"


def _lines(text: str) -> list[int]:
    parsed = parse_manuscript(text)
    return [
        f.line for f in scan_unbound_markers(text, spans=parsed.spans, claims=parsed.claims)
    ]


def _block(cid: str, marker: str = MARK, body: str = "PyFCG 3.3 installs cleanly.") -> str:
    attributes = f" id={cid} source=a" + (f" marker={marker}" if marker else "")
    return B3 + "claim" + attributes + NL + "quote: |" + NL + f"  {body}" + NL + B3 + NL


class TestTheMarkBesideTheBlockIsBound:
    def test_the_mark_above_the_block_is_no_longer_unbound(self) -> None:
        text = f"{MARK}PyFCG 3.3 installs cleanly.{NL}{NL}" + _block("c1")
        assert _lines(text) == []

    def test_the_mark_below_the_block_is_no_longer_unbound(self) -> None:
        text = _block("c1") + f"{NL}{MARK}PyFCG 3.3 installs cleanly.{NL}"
        assert _lines(text) == []

    @pytest.mark.parametrize("blank", [1, 2, 3])
    def test_the_blank_lines_between_them_do_not_matter(self, blank: int) -> None:
        text = f"{MARK}PyFCG 3.3 installs cleanly.{NL}" + NL * blank + _block("c1")
        assert _lines(text) == []

    def test_a_claim_whose_marker_matches_the_line_above_a_paragraph_does_not_reach_it(
        self,
    ) -> None:
        # The mark heads a *different* paragraph, so the block beside it is not
        # its block.  Binding it anyway would hide a real unbound assertion.
        text = (
            f"{MARK}an uncited sentence.{NL}{NL}"
            "A paragraph of prose that is not marked." + NL + NL + _block("c1")
        )
        assert _lines(text) == [1]


class TestWhatMustStayReported:
    def test_a_block_with_no_marker_binds_nothing(self) -> None:
        text = f"{MARK}PyFCG 3.3 installs cleanly.{NL}{NL}" + _block("c1", marker="")
        assert _lines(text) == [1]

    def test_a_mark_the_block_does_not_name_stays_unbound(self) -> None:
        text = f"{GUESS}the gain is 3 points.{NL}{NL}" + _block("c1", marker=MARK)
        assert _lines(text) == [1]

    def test_a_mark_two_paragraphs_away_is_not_reached(self) -> None:
        text = f"{MARK}far above.{NL}{NL}another paragraph" + NL + NL + _block("c1")
        assert _lines(text) == [1]

    def test_a_second_mark_further_up_is_not_silenced(self) -> None:
        # Only the neighbouring mark is bound; the one above it is still an
        # assertion with no evidence, and it stays reported.
        text = f"{MARK}first unbound sentence.{NL}{NL}{MARK}second sentence.{NL}{NL}" + _block(
            "c1"
        )
        assert _lines(text) == [1]

    def test_two_marks_around_one_block_are_both_left_reported(self) -> None:
        # Ambiguous: either mark could be the one the block vouches for.
        # Silencing both would hide a genuine unbound assertion, so neither is
        # bound and both are reported.
        text = f"{MARK}above.{NL}{NL}" + _block("c1") + NL + f"{MARK}below.{NL}"
        assert _lines(text) == [1, 8]

    def test_two_blocks_bind_one_mark_each(self) -> None:
        text = (
            f"{MARK}first sentence.{NL}{NL}"
            + _block("c1")
            + NL
            + f"{GUESS}second sentence.{NL}{NL}"
            + _block("c2", marker=GUESS)
        )
        assert _lines(text) == []


class TestTheLineIsFoundInEveryDialect:
    def test_an_html_comment_block_binds_the_mark_above_it(self) -> None:
        text = (
            f"{MARK}PyFCG 3.3 installs cleanly.{NL}{NL}"
            "<!-- claim: c1 source=a marker="
            + MARK
            + " -->"
            + NL
            + "PyFCG 3.3 installs cleanly."
            + NL
            + ">> PyFCG 3.3 installs cleanly."
            + NL
        )
        assert _lines(text) == []

    def test_a_table_block_cannot_name_a_mark_and_says_so(self) -> None:
        # The table dialect is five fixed columns (`id | source | page | quote |
        # claim`) with no attribute grammar at all, so there is nowhere to write
        # `marker=`.  A mark beside a table row therefore stays unbound — that
        # is the honest answer, because the author really did not say which
        # block the mark vouches for.
        text = (
            f"{MARK}PyFCG 3.3 installs cleanly.{NL}{NL}"
            "| id | source | page | quote | claim |"
            + NL
            + "| --- | --- | --- | --- | --- |"
            + NL
            + "| c1 | a | 1 | PyFCG 3.3 installs cleanly. | the statement |"
            + NL
        )
        assert _lines(text) == [1]

    def test_a_table_row_holding_a_mark_is_not_a_binding(self) -> None:
        # A sixth column renders as an extra cell, not as an attribute.
        text = (
            f"{MARK}PyFCG 3.3 installs cleanly.{NL}{NL}"
            "| id | source | page | quote | claim | marker |"
            + NL
            + "| --- | --- | --- | --- | --- | --- |"
            + NL
            + "| c1 | a | 1 | PyFCG 3.3 installs cleanly. | the statement | "
            + MARK
            + " |"
            + NL
        )
        assert _lines(text) == [1]


class TestTheRulesThatKeepItNarrow:
    """Each of these pins one guard, because each guard can silence a finding."""

    def test_a_decorated_mark_line_still_binds(self) -> None:
        # The binding is decided by the same `_MARKER_DECORATION` the scan uses,
        # so `- 【原文】 …` and `> 【原文】 …` must bind exactly as a bare mark
        # does.  Reusing the stripper is the point: a second copy of "what may
        # stand in front of a sentence" is a second answer.
        for prefix in ("- ", "> ", "  "):
            text = f"{prefix}{MARK}PyFCG 3.3 installs cleanly.{NL}{NL}" + _block("c1")
            assert _lines(text) == [], prefix

    def test_a_mark_the_caller_did_not_ask_about_is_not_bound(self) -> None:
        # `markers` is the caller's list of marks this scan should report.  A
        # block naming a mark outside it vouches for something this run is not
        # talking about, so the binding must not be recorded for it.
        text = f"{GUESS}the gain is 3 points.{NL}{NL}" + _block("c1", marker=GUESS)
        parsed = parse_manuscript(text)
        bound = _bound_mark_lines(
            text.splitlines(), parsed.claims, parsed.spans, markers=(MARK,)
        )
        assert bound == set()

    def test_a_mark_two_blocks_both_name_is_bound_by_neither(self) -> None:
        # One mark between two blocks that both say `marker=【原文】`: either
        # could be the assertion it vouches for.  Binding it would silence a
        # real unbound sentence, so neither block claims it.
        text = _block("c1") + NL + f"{MARK}the mark both blocks name.{NL}{NL}" + _block("c2")
        assert _lines(text) == [6]

    def test_a_paragraph_search_does_not_cross_a_claim_block(self) -> None:
        # `_paragraph_above` promises a mark may head the paragraph *beside* a
        # block, not reach through one.  Walking past a covered line would let a
        # block bind a mark that belongs to whatever is on the far side.
        lines = [f"{MARK}far above.", "", B3 + "claim id=c1 source=a", B3]
        covered = {3, 4}
        assert _paragraph_above(lines, 5, covered) is None


class TestTheDemoIsUnchanged:
    def test_the_demo_still_reports_its_two_bare_marks(self) -> None:
        from pathlib import Path

        demo = Path(__file__).resolve().parents[1] / "demo" / "manuscript.md"
        assert _lines(read_text(demo)) == [52, 54]


class TestTheLedgerStillRecordsTheMarker:
    def test_the_attribute_is_still_parsed(self) -> None:
        text = f"{MARK}PyFCG 3.3 installs cleanly.{NL}{NL}" + _block("c1")
        parsed = parse_manuscript(text)
        assert [c.marker for c in parsed.claims] == [MARK]
