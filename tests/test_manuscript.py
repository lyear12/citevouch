"""Manuscript parsing: three accepted dialects, and every malformed form."""

from __future__ import annotations

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
    assert result.findings[0].code == "claim-without-evidence"
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


def test_claim_inside_a_non_claim_fence_is_ignored():
    text = """
```markdown
```claim id=c1 source=a
quote: |
  nested
```
```
"""
    result = parse_manuscript(text)
    assert result.claims == []


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
