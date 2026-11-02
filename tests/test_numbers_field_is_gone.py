"""A `numbers:` block used to empty the quote it was written next to.

`_FIELD_KEY` listed `numbers?` from the first commit, and nothing ever read the
field: `_claim_from` builds `Claim.numbers` with `numbers_in(quote)`.  So the
value was parsed, discarded, and the claim searched anyway - and because the
key also made the body look like a mapping, the `>>` and two-paragraph shapes
lost their quote entirely.

Measured before the fix: `['>> We collected 40,688 examples.', 'numbers: 1']`
came back as `('', '', {})` where the same body without the second line came
back as `('We collected 40,688 examples.', '', {})`.  The claim then failed with
`claim-uncheckable` ("carries no verbatim quote") for a block whose quote was
written correctly.

The key is gone rather than honoured: honouring it would mean deciding what a
hand-written number list means to a verifier that already derives the numbers
from the quote, and that is a format design change, not a fix.
"""

from __future__ import annotations

import contextlib
import io
from pathlib import Path

from citevouch.cli import main
from citevouch.manuscript import _split_body, parse_manuscript

B3 = "`" * 3
QUOTE = "We collected 40,688 examples."
CLAIM = "It holds 40,688 examples."


def _fenced(body: list[str], attrs: str = "id=c1 source=paper page=1") -> str:
    return "\n".join(["# T", "", f"{B3}claim {attrs}", *body, B3, ""])


class TestTheKeyNoLongerDividesTheBody:
    def test_a_numbers_line_does_not_swallow_an_arrow_quote(self) -> None:
        quote, _, _ = _split_body([f">> {QUOTE}", "numbers: 1"])
        assert quote == QUOTE, "the arrow shape must keep its quote"

    def test_a_numbers_line_does_not_swallow_a_two_paragraph_quote(self) -> None:
        quote, _, _ = _split_body([QUOTE, "", CLAIM, "numbers: 2"])
        assert quote == QUOTE

    def test_a_numbers_line_does_not_swallow_a_quoted_block(self) -> None:
        quote, _, _ = _split_body(["quote: |", f"  {QUOTE}", "numbers: |", "  99,999"])
        assert quote == QUOTE


class TestTheKeyIsNotSpecialAtAll:
    """With the key gone, its line is ordinary body text - visible, not dropped."""

    def test_the_line_lands_in_the_claim_text_of_the_arrow_shape(self) -> None:
        quote, claim, attributes = _split_body([f">> {QUOTE}", "numbers: 1"])
        assert quote == QUOTE
        assert claim == "numbers: 1", "an unread key must stay visible, not vanish"
        assert attributes == {}

    def test_the_line_lands_in_the_quote_of_a_keyless_body(self) -> None:
        quote, claim, _ = _split_body([QUOTE, "numbers: 1"])
        assert claim == ""
        assert "numbers: 1" in quote


class TestTheVerdictOnAProject:
    def test_a_block_that_wrote_a_numbers_line_is_still_verified(self, tmp_path: Path) -> None:
        root = tmp_path / "proj"
        root.mkdir()
        (root / "paper.txt").write_text(QUOTE + "\n", encoding="utf-8", newline="\n")
        (root / "sources.toml").write_text(
            '[sources]\npaper = "paper.txt"\n', encoding="utf-8", newline="\n"
        )
        (root / "m.md").write_text(
            _fenced([f">> {QUOTE}", "numbers: 1"]), encoding="utf-8", newline="\n"
        )
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["check", "m.md", "--root", str(root)])
        assert code == 0, out.getvalue()
        assert "claim-uncheckable" not in out.getvalue()
        assert "1 claim — 1 verified" in out.getvalue()


class TestTheDerivedNumbersAreStillTheQuotes:
    def test_the_numbers_come_from_the_quote_not_from_a_field(self) -> None:
        parsed = parse_manuscript(_fenced(["quote: |", f"  {QUOTE}"]))
        assert parsed.claims[0].numbers == ("40,688",)

    def test_a_claim_with_no_digits_has_no_numbers(self) -> None:
        parsed = parse_manuscript(_fenced(["quote: |", "  alpha beta gamma"]))
        assert parsed.claims[0].numbers == ()
