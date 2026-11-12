"""Two findings on one attribute must not contradict each other.

A block may write one attribute on the opening line and again (twice) in the
body.  That produces two findings: ``claim-field-shadowed`` for the fence
winning, and ``claim-field-repeated`` for the body's own repeat.  Measured
before this file existed, on

    ```claim id=c1 source=paper page=1
    quote: |
      We collected 154,391 examples from the corpus.
    source: alt
    source: other
    ```

the first said ``'alt' in the body ... was dropped`` and the second said
``the first, 'alt', was kept`` - one screenful of output, two opposite
sentences about one value, and the ledger recorded a third value (``paper``).
The repeat finding described the body in isolation when the author reads the
block as a whole.
"""

from __future__ import annotations

import contextlib
import io

from citevouch.cli import main
from citevouch.manuscript import parse_manuscript

NL = chr(10)
B3 = chr(96) * 3
QUOTE = "We collected 154,391 examples from the corpus."

SHADOWED = "claim-field-shadowed"
REPEATED = "claim-field-repeated"


def _fence(opener: str, *body: str) -> str:
    return NL.join([B3 + "claim " + opener, *body, B3, ""])


def _messages(text: str, code: str) -> list[str]:
    parsed = parse_manuscript(text, "m.md")
    return [f.message for f in parsed.findings if f.code == code]


def _line(text: str, code: str) -> int:
    parsed = parse_manuscript(text, "m.md")
    return next(f.line for f in parsed.findings if f.code == code)


class TestTheTwoFindingsAgree:
    def test_the_repeat_does_not_call_the_dropped_value_kept(self) -> None:
        text = _fence(
            "id=c1 source=paper page=1",
            "quote: |",
            "  " + QUOTE,
            "source: alt",
            "source: other",
        )
        repeated = _messages(text, REPEATED)
        assert len(repeated) == 1
        message = repeated[0]
        # The body's first value lost too, and saying it "was kept" makes the
        # other finding on the same block read as a lie.
        assert "was kept" not in message
        assert "'alt'" in message
        assert "'other'" in message
        assert "'paper'" in message
        assert "opening line" in message

    def test_the_repeat_counts_the_opening_line_too(self) -> None:
        text = _fence(
            "id=c1 source=paper page=1",
            "quote: |",
            "  " + QUOTE,
            "source: alt",
            "source: other",
        )
        message = _messages(text, REPEATED)[0]
        # Two body spellings plus the one on the fence.
        assert "3 times" in message

    def test_it_says_every_body_value_was_dropped(self) -> None:
        text = _fence(
            "id=c1 source=paper page=1",
            "quote: |",
            "  " + QUOTE,
            "source: alt",
            "source: other",
        )
        message = _messages(text, REPEATED)[0]
        assert "were all dropped" in message
        assert "body values" in message

    def test_one_body_repeat_says_was_not_were(self) -> None:
        text = _fence(
            "id=c1 source=paper page=1",
            "quote: |",
            "  " + QUOTE,
            "source: alt",
        )
        # A single body spelling is only shadowed, never repeated, so this is
        # the control: the verb agreement code is not reached at all.
        assert _messages(text, REPEATED) == []
        assert len(_messages(text, SHADOWED)) == 1


class TestTheLayerWithNoFenceValueIsUnchanged:
    """A body-only repeat keeps its old sentence: nothing above it won."""

    def test_it_still_says_the_first_body_value_was_kept(self) -> None:
        text = _fence(
            "id=c1 page=1",
            "quote: |",
            "  " + QUOTE,
            "source: alt",
            "source: other",
        )
        message = _messages(text, REPEATED)[0]
        assert "the first, 'alt', was kept" in message
        assert "'other'" in message
        assert "was dropped" in message

    def test_the_shadowed_finding_is_absent(self) -> None:
        text = _fence(
            "id=c1 page=1",
            "quote: |",
            "  " + QUOTE,
            "source: alt",
            "source: other",
        )
        assert _messages(text, SHADOWED) == []


class TestBothLayersRepeated:
    def test_two_attributes_give_four_findings_that_do_not_disagree(self) -> None:
        text = _fence(
            "id=c1 source=paper page=1",
            "quote: |",
            "  " + QUOTE,
            "source: alt",
            "source: other",
            "page: 4",
            "page: 5",
        )
        parsed = parse_manuscript(text, "m.md")
        codes = [f.code for f in parsed.findings]
        assert codes.count(SHADOWED) == 2
        assert codes.count(REPEATED) == 2
        for message in _messages(text, REPEATED):
            # Neither repeat may claim a body value survived.
            assert "was kept" not in message

    def test_the_findings_point_at_the_lines_that_carry_the_losers(self) -> None:
        text = _fence(
            "id=c1 source=paper page=1",
            "quote: |",
            "  " + QUOTE,
            "source: alt",
            "source: other",
            "page: 4",
            "page: 5",
        )
        lines = sorted(f.line for f in parse_manuscript(text, "m.md").findings)
        assert lines == [4, 5, 6, 7]


class TestTheVerdictOnAProject:
    def test_check_reports_both_and_stays_green(self, tmp_path) -> None:
        root = tmp_path / "proj"
        root.mkdir()
        (root / "paper.txt").write_text(QUOTE + NL, encoding="utf-8", newline=chr(10))
        (root / "alt.txt").write_text("Elsewhere." + NL, encoding="utf-8", newline=chr(10))
        (root / "other.txt").write_text("Nowhere." + NL, encoding="utf-8", newline=chr(10))
        (root / "sources.toml").write_text(
            "[sources]"
            + NL
            + 'paper = "paper.txt"'
            + NL
            + 'alt = "alt.txt"'
            + NL
            + 'other = "other.txt"'
            + NL,
            encoding="utf-8",
            newline=chr(10),
        )
        (root / "m.md").write_text(
            _fence(
                "id=c1 source=paper page=1",
                "quote: |",
                "  " + QUOTE,
                "source: alt",
                "source: other",
            ),
            encoding="utf-8",
            newline=chr(10),
        )
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["check", "m.md", "--root", str(root)])
        printed = out.getvalue()
        assert code == 0
        assert SHADOWED in printed
        assert REPEATED in printed
        assert "was kept" not in printed
