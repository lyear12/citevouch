"""An unknown field's block-scalar value was read as part of the quote.

Measured before the fix, on a claim whose quote is verbatim on page 1:

    quote: |
      We collected 40,688 examples from the corpus of written English.
    text: |
      我们收集了例句

came back as

    claim.quote == 'We collected 40,688 examples from the corpus of written English.'
                    '\\n我们收集了例句'
    [medium] claim-field-unknown … it was neither applied nor searched as part
             of the quote
    [high]   quote-missing … We collected …English. 我们收集了例句
             — quote not found in page.txt

The finding said the value never reached the quote, and the same run searched
it.  Two facts in one output, and the one the author reads first is false.

The cause is a missing `current = ""`: the known-attribute branch two lines
above clears the collection target, the unknown-key branch did not, so the
indented line after it fell through to `if current:` and joined whatever field
was open - `quote:`, nearly always.

A block scalar's lines belong to the key above them.  When the key is not one
this format has, the lines have no owner, and `fields.setdefault(current, [])`
is the only thing that can adopt them.  Clearing `current` is what makes the
sentence in the finding true.
"""

from __future__ import annotations

import contextlib
import io
from pathlib import Path

from citevouch.cli import main
from citevouch.manuscript import parse_manuscript

NL = chr(10)
B3 = chr(96) * 3
QUOTE = "We collected 40,688 examples from the corpus of written English."
PAGE = "Preface" + NL + QUOTE + NL
CLAIM = "我们的主张"


def _fenced(body: str, attrs: str = "id=c1 source=paper page=1") -> str:
    return B3 + "claim " + attrs + NL + body + NL + B3 + NL


def _commented(body: str, attrs: str = "id=c1 source=paper page=1") -> str:
    return "<!-- claim " + attrs + NL + body + NL + "-->" + NL


def _quotes(text: str) -> list[str]:
    return [claim.quote for claim in parse_manuscript(text).claims]


def _codes(text: str) -> list[str]:
    return [finding.code for finding in parse_manuscript(text).findings]


def _project(tmp_path: Path, manuscript: str) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    (root / "m.md").write_text(manuscript, encoding="utf-8", newline=NL)
    return root


def _run(root: Path, *args: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main([*args, "m.md", "--root", str(root)])
    return code, out.getvalue()


class TestTheValueHasNoOwner:
    def test_a_block_scalar_under_an_unknown_key_stays_out_of_the_quote(self) -> None:
        body = "quote: |" + NL + "  " + QUOTE + NL + "text: |" + NL + "  " + CLAIM
        assert _quotes(_fenced(body)) == [QUOTE]

    def test_the_line_is_still_named(self) -> None:
        body = "quote: |" + NL + "  " + QUOTE + NL + "text: |" + NL + "  " + CLAIM
        assert _codes(_fenced(body)) == ["claim-field-unknown"]

    def test_the_message_promises_what_the_run_does(self) -> None:
        body = "quote: |" + NL + "  " + QUOTE + NL + "text: |" + NL + "  " + CLAIM
        message = parse_manuscript(_fenced(body)).findings[0].message
        assert "neither applied nor searched as part of the quote" in message, (
            "the promise this file holds the code to"
        )

    def test_the_html_dialect_reads_it_the_same_way(self) -> None:
        body = "quote: |" + NL + "  " + QUOTE + NL + "text: |" + NL + "  " + CLAIM
        assert _quotes(_commented(body)) == [QUOTE]

    def test_a_second_unknown_field_does_not_pick_up_the_first_one_s_value(self) -> None:
        body = (
            "quote: |"
            + NL
            + "  "
            + QUOTE
            + NL
            + "text: |"
            + NL
            + "  "
            + CLAIM
            + NL
            + "notes: |"
            + NL
            + "  another line"
        )
        assert _quotes(_fenced(body)) == [QUOTE]
        assert _codes(_fenced(body)) == ["claim-field-unknown", "claim-field-unknown"]

    def test_a_known_key_after_the_unknown_one_still_works(self) -> None:
        body = (
            "quote: |" + NL + "  " + QUOTE + NL + "text: |" + NL + "  " + CLAIM + NL + "page: 1"
        )
        result = parse_manuscript(_fenced(body))
        assert [claim.quote for claim in result.claims] == [QUOTE]
        assert [claim.page for claim in result.claims] == [1]

    def test_the_value_does_not_become_a_claim_either(self) -> None:
        body = "quote: |" + NL + "  " + QUOTE + NL + "text: |" + NL + "  " + CLAIM
        result = parse_manuscript(_fenced(body))
        assert [claim.text for claim in result.claims] == [""]


class TestWhatMustStillWork:
    def test_an_indented_line_under_the_quote_is_continuation(self) -> None:
        body = "quote: |" + NL + "  " + QUOTE + NL + "  " + CLAIM
        assert _quotes(_fenced(body)) == [QUOTE + NL + CLAIM]

    def test_an_unknown_key_with_an_inline_value_is_unchanged(self) -> None:
        body = "quote: |" + NL + "  " + QUOTE + NL + "text: " + CLAIM
        assert _quotes(_fenced(body)) == [QUOTE]
        assert _codes(_fenced(body)) == ["claim-field-unknown"]

    def test_an_unknown_key_above_the_quote_does_not_eat_it(self) -> None:
        body = "text: |" + NL + "  " + CLAIM + NL + "quote: |" + NL + "  " + QUOTE
        assert _quotes(_fenced(body)) == [QUOTE]
        assert _codes(_fenced(body)) == ["claim-field-unknown"]

    def test_a_known_attribute_still_takes_its_indented_value_nowhere(self) -> None:
        body = "quote: |" + NL + "  " + QUOTE + NL + "page: 1"
        assert _codes(_fenced(body)) == []


class TestTheVerdictOnAProject:
    def test_the_run_does_not_accuse_the_quote(self, tmp_path: Path) -> None:
        body = "quote: |" + NL + "  " + QUOTE + NL + "text: |" + NL + "  " + CLAIM
        root = _project(tmp_path, _fenced(body))
        code, output = _run(root, "check")
        assert "quote-missing" not in output, (
            "the quote is on page 1; only the field name was wrong"
        )
        assert "quote-found" in output
        assert "claim-field-unknown" in output
        assert code == 0

    def test_the_message_is_now_true(self, tmp_path: Path) -> None:
        body = "quote: |" + NL + "  " + QUOTE + NL + "text: |" + NL + "  " + CLAIM
        root = _project(tmp_path, _fenced(body))
        _code, output = _run(root, "check")
        assert CLAIM not in output, (
            "the finding says the value was not searched as part of the quote, "
            "so the value must not appear in the quote the run reports"
        )
