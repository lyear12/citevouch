"""Manuscript parsing: three accepted dialects, and every malformed form."""

from __future__ import annotations

import pytest

from citevouch.manuscript import parse_manuscript, scan_unbound_markers


def test_fenced_block_is_parsed():
    text = """
```claim id=c1 source=smith2026 page=3
quote: |
  We train the model on two corpora.
claim: |
  The grammar is learned from two corpora.
```
"""
    result = parse_manuscript(text)
    assert len(result.claims) == 1
    claim = result.claims[0]
    assert claim.id == "c1"
    assert claim.source == "smith2026"
    assert claim.page == 3
    assert claim.quote == "We train the model on two corpora."
    assert claim.text == "The grammar is learned from two corpora."
    assert claim.quote_fingerprint


def test_html_comment_form_is_parsed():
    text = """
<!-- claim: c2 source=smith2026 page=4
The grammar is learned from two corpora.
>> We train the model on two corpora.
-->
"""
    result = parse_manuscript(text)
    assert len(result.claims) == 1
    assert result.claims[0].id == "c2"
    assert result.claims[0].quote == "We train the model on two corpora."
    assert result.claims[0].text == "The grammar is learned from two corpora."


def test_table_row_form_is_parsed():
    text = "| c3 | smith2026 | 5 | We train on two corpora. | The grammar is learned. |\n"
    result = parse_manuscript(text)
    assert len(result.claims) == 1
    assert result.claims[0].quote == "We train on two corpora."
    assert result.claims[0].page == 5


def test_header_row_of_a_table_is_not_a_claim():
    text = "| id | source | page | quote | claim |\n|---|---|---|---|---|\n"
    result = parse_manuscript(text)
    assert result.claims == []


def test_missing_id_is_reported():
    text = """
```claim source=smith2026
quote: |
  something
```
"""
    result = parse_manuscript(text)
    assert result.claims == []
    assert result.findings[0].code == "claim-uncheckable"
    assert "no id=" in result.findings[0].message


def test_missing_source_is_reported():
    text = """
```claim id=c1
quote: |
  something
```
"""
    result = parse_manuscript(text)
    assert result.claims == []
    assert "names no source" in result.findings[0].message


def test_missing_quote_is_reported():
    text = """
```claim id=c1 source=smith2026
claim: |
  only an assertion, no evidence
```
"""
    result = parse_manuscript(text)
    assert result.claims == []
    assert "no verbatim quote" in result.findings[0].message


def test_duplicate_id_keeps_the_first_and_reports():
    text = """
```claim id=c1 source=a
quote: |
  first quote here
```
```claim id=c1 source=b
quote: |
  second quote here
```
"""
    result = parse_manuscript(text)
    assert [c.quote for c in result.claims] == ["first quote here"]
    assert any("used twice" in f.message for f in result.findings)


def test_non_claim_fence_is_skipped_entirely():
    text = """
```python
claim = "this should not be parsed"
```
"""
    result = parse_manuscript(text)
    assert result.claims == []
    assert result.findings == []


def test_a_code_sample_wrapping_a_claim_with_four_backticks_stays_silent():
    """The safe way to document the syntax: wrap it in four backticks.

    A three-backtick sample around a ```claim line is *indistinguishable* from
    an author who forgot the sample's closing fence - in both, the ```claim is
    swallowed and ends at a line that was meant to end a claim. Since the two
    cannot be told apart from the text, the run says so (see the two tests
    below). Four backticks make the nesting explicit, and then there is nothing
    to guess: the outer fence does not close on the inner one.
    """
    text = """````markdown
```claim id=c1 source=a
quote: |
  nested
```
````
"""
    result = parse_manuscript(text)
    assert result.claims == []
    assert result.findings == []


def test_an_unclosed_code_fence_that_swallowed_a_claim_is_reported():
    """The failure this guard exists for: a missing closer turns the author's
    own claim into "code", and the run used to print 0 claims and exit 0."""
    text = """```python
code with no closing fence

```claim id=c1 source=a
quote: |
  the corpus holds 154,391 sentences
```
"""
    result = parse_manuscript(text)
    assert result.claims == []
    assert [f.code for f in result.findings] == ["claim-block-unclosed"]
    assert "opened on line 4" in result.findings[0].message
    assert result.findings[0].line == 1


def test_an_unclosed_html_claim_is_reported():
    text = """<!-- claim: c1 source=a
quote: |
  the corpus holds 154,391 sentences
"""
    result = parse_manuscript(text)
    assert [f.code for f in result.findings] == ["claim-block-unclosed"]
    assert result.findings[0].line == 1


def test_line_numbers_point_at_the_opening_delimiter():
    text = "\n\n\n```claim id=c1 source=a\nquote: |\n  words here\n```\n"
    result = parse_manuscript(text)
    assert result.claims[0].line == 4


def test_numbers_are_extracted_from_the_quote():
    text = """
```claim id=c1 source=a
quote: |
  It reports 40,688 constructions and 48.4% hapax.
```
"""
    result = parse_manuscript(text)
    assert result.claims[0].numbers == ("40,688", "48.4%")


def test_unbound_marker_is_reported():
    text = "This sentence is marked 【原文】 but carries no claim block.\n"
    findings = scan_unbound_markers(text)
    assert len(findings) == 1
    assert findings[0].code == "claim-without-evidence"
    assert findings[0].line == 1


def test_bound_text_inside_a_claim_block_is_not_reported_as_unbound():
    text = "```claim id=c1 source=a\nquote: |\n  quoted 【原文】 here\n```\n"
    # Without spans the scan is line-based and cannot know better; with the
    # spans the parser produced, the documented claim is correctly exempt.
    assert len(scan_unbound_markers(text)) == 1
    parsed = parse_manuscript(text)
    assert scan_unbound_markers(text, spans=parsed.spans) == []


def test_custom_markers_are_respected():
    text = "A sentence marked [verified] here.\n"
    findings = scan_unbound_markers(text, markers=("[verified]",))
    assert len(findings) == 1


def test_empty_manuscript_yields_nothing():
    result = parse_manuscript("")
    assert result.claims == []
    assert result.findings == []


def test_a_four_backtick_fence_may_contain_a_claim_line_silently():
    """Four ticks nest unambiguously, so it is the documented safe form.

    Three ticks are genuinely ambiguous — a forgotten closer and a deliberate
    sample look the same — so the tool reports the loss. Four ticks are not:
    the outer fence closes only on a run of four, which cannot be this claim's
    own three. Guessing "forgot the fence" there would punish the one way to
    quote a fence correctly.
    """
    text = """````markdown
```claim id=c1 source=a
quote: |
  this is sample text, not a claim
```
````
"""
    result = parse_manuscript(text)
    assert result.claims == []
    assert result.findings == []


def test_two_blocks_that_are_broken_for_different_reasons_both_say_so():
    text = """
```claim id=c1 source=a
quote: |
  quote one
```
```claim id=c1 source=a
quote: |
  quote two
```
```claim source=a
quote: |
  quote three
```
"""
    result = parse_manuscript(text)
    codes = [f.code for f in result.findings]
    assert codes.count("claim-uncheckable") == 2
    assert [c.id for c in result.claims] == ["c1"]


def test_a_claim_that_cannot_be_checked_is_not_also_advice():
    """`claim-without-evidence` means "bind this marker"; it is not a verdict.

    The two used to share a code, so a malformed block and a stray marker in
    prose were equally quiet, and `--fail-on high` let the malformed one pass.
    """
    text = """
```claim id=c1 page=1
quote: |
  words
```
"""
    result = parse_manuscript(text)
    assert result.findings[0].code == "claim-uncheckable"
    assert result.findings[0].severity == "high"


class TestAnInlineQuoteIsTheValueAndNotTheMarks:
    """`quote: "the passage"` and `quote: the passage` are the same quote.

    Claims carry `key="value"` attributes, and the attribute reader has stripped
    those marks from the start.  The body reader never did.  So a writer who
    quoted the passage in the only place a YAML reader would quote it - the
    inline scalar - sent the two marks into the search as content, matched
    nothing, and got a `quote-missing` (high) verdict that accused their
    manuscript of a passage the PDF does contain.

    The same failure as a byte-order mark, an invisible directional mark, and a
    full-width digit: an encoding detail of the file read as a fact about the
    paper.  This one lived in the reader nobody had pointed at.
    """

    def _quote_of(self, body: str) -> str:
        nl = chr(10)
        text = "```claim id=c1 source=s" + nl + body + nl + "```" + nl
        result = parse_manuscript(text)
        assert result.claims, [f.code for f in result.findings]
        return result.claims[0].quote

    def test_a_double_quoted_value_loses_its_marks(self):
        assert self._quote_of('quote: "We train on two corpora."') == "We train on two corpora."

    def test_a_single_quoted_value_loses_its_marks(self):
        assert self._quote_of("quote: 'We train on two corpora.'") == "We train on two corpora."

    def test_a_bare_value_is_untouched(self):
        assert self._quote_of("quote: We train on two corpora.") == "We train on two corpora."

    def test_a_block_value_is_untouched(self):
        nl = chr(10)
        assert (
            self._quote_of("quote: |" + nl + "  We train on two corpora.")
            == "We train on two corpora."
        )

    @pytest.mark.parametrize("body", ['quote: "yes" or "no"', "quote: it's a test"])
    def test_marks_inside_the_value_are_content(self, body: str):
        """A value that only *starts* and ends with a mark is not a quoted scalar.

        `"yes" or "no"` begins and ends with a double quote.  A rule that only
        compared the two ends would eat one mark off each end and search for a
        passage nobody wrote - which is the failure this fix exists to prevent,
        reintroduced by a fix that was too eager.
        """
        expected = body.split("quote: ", 1)[1]
        assert self._quote_of(body) == expected

    def test_a_lone_mark_is_left_alone(self):
        assert self._quote_of('quote: "') == '"'
