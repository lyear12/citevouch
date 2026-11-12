"""An attribute line is an attribute line in every shape a body can take.

`_split_body` reads four shapes, tried in order of explicitness::

    quote:/claim: keys;  a `>>` line;  first paragraph quote and second claim;
    everything as the quote.

The fix that first stopped attribute lines from being searched as quote text
only reached the first shape, because that is the shape that calls itself a
mapping.  The margin rule it enforced is about the margin, not about which
branch ran, so the other three shapes kept the defect.  Measured on a fence
that had already said `id=c1 source=paper page=1`, with the passage verbatim
on page 2 of the source::

    ["page: 2", "", Q]      -> quote "page: 2", claim Q, page still 1
                               [high] quote-missing "page: 2"
    ["page: 2", Q]          -> quote "page: 2\\nQ"          [high] quote-missing
    [Q, "", "page: 2"]      -> quote Q, claim "page: 2"     exit 0, silent
    [Q, "page: 2"]          -> quote "Q\\npage: 2"          [high] quote-missing
    ["page: 2", ">> Q"]     -> quote Q, claim "page: 2"     exit 0, silent
    ["page: 2"]             -> quote "page: 2"              an accusation

Every one of those is a statement about the author that the file does not
support: the page hint they wrote was applied in none of the six, and four of
them accused them of quoting words their source never printed.

The line that separates this from the opposite defect is the name, not the
shape.  Only the six names this format actually has are lifted out; a `Note:`
or `Example:` line is prose that happens to contain a colon, and lifting that
would cut a quotation in half.
"""

from __future__ import annotations

import json

import pytest

from citevouch.manuscript import _split_body, parse_manuscript

B3 = "`" * 3
NL = "\n"
QUOTE = "We collected 154,391 examples from the corpus."
SECOND = "It follows that the method works."
# Page 1 says nothing quotable; the passage is on page 2.
PAGE = "Nothing to see here.\f" + QUOTE + NL + SECOND + NL


def _fenced(body: str, attrs: str = "id=c1 source=paper") -> str:
    return f"# T{NL}{NL}{B3}claim {attrs}{NL}{body}{NL}{B3}{NL}"


def _commented(body: str, attrs: str = "id=c1 source=paper") -> str:
    return f"# T{NL}{NL}<!-- claim {attrs}{NL}{body}{NL}-->{NL}"


def _project(tmp_path, body: str, attrs: str = "id=c1 source=paper", page: str = PAGE):
    from citevouch.cli import main

    (tmp_path / "page.txt").write_text(page, encoding="utf-8", newline=NL)
    (tmp_path / "sources.toml").write_text(
        f'[sources]{NL}paper = "page.txt"{NL}', encoding="utf-8", newline=NL
    )
    (tmp_path / "m.md").write_text(_fenced(body, attrs), encoding="utf-8", newline=NL)
    return main


class TestTheMarginRuleHoldsInEveryShape:
    @pytest.mark.parametrize(
        "body",
        [
            ["page: 2", "", QUOTE],
            ["page: 2", QUOTE],
            [QUOTE, "", "page: 2"],
            [QUOTE, "page: 2"],
            ["page: 2", ">> " + QUOTE],
        ],
        ids=[
            "above a paragraph",
            "above with no blank line",
            "below a paragraph",
            "below with no blank line",
            "above the arrow",
        ],
    )
    def test_the_page_is_applied_and_not_quoted(self, body: list[str]) -> None:
        quote, _claim, attributes, _unknown = _split_body(body)
        assert attributes == {"page": "2"}
        assert quote == QUOTE, "the page line must not be searched as quote text"

    def test_an_attribute_on_its_own_leaves_nothing_to_quote(self) -> None:
        # Nothing is left once the line is read as what it is.  Saying so is
        # the point: the block carries no passage, and `_claim_from` says that
        # instead of accusing the author of quoting "page: 2".
        quote, claim, attributes, _unknown = _split_body(["page: 2"])
        assert (quote, claim, attributes) == ("", "", {"page": "2"})

    def test_the_dialect_does_not_matter(self) -> None:
        result = parse_manuscript(
            _commented(f"page: 2{NL}{QUOTE}", attrs="id=c1 source=paper"), path="m.md"
        )
        assert [(c.page, c.quote) for c in result.claims] == [(2, QUOTE)]
        assert "page: 2" not in result.claims[0].quote

    def test_a_line_deeper_than_the_bodys_margin_is_content(self) -> None:
        # The margin is the body's own least indent, the same way the mapping
        # branch takes it from the block's own keys.  A line written deeper
        # than that is continuation text, whatever it contains - the rule has
        # to be one rule, not two.
        quote, _claim, attributes, _unknown = _split_body(["  page: 2", "", QUOTE])
        assert attributes == {}
        assert quote == "page: 2"

    def test_the_margin_moves_with_a_block_that_is_indented(self) -> None:
        quote, _claim, attributes, _unknown = _split_body(["  page: 2", "", "  " + QUOTE])
        assert attributes == {"page": "2"}
        assert quote == QUOTE


class TestNamesTheFormatDoesNotUseStayInTheQuote:
    @pytest.mark.parametrize(
        "line",
        ["Example: 1", "Note: ours.", "Case: the corpus", "numbers: 1", "Page: 1"],
        ids=["example", "note", "case", "numbers", "capital page"],
    )
    def test_a_prose_line_is_not_a_field(self, line: str) -> None:
        quote, claim, attributes, _unknown = _split_body([line, "", QUOTE])
        assert attributes == {}
        assert quote == line, "a word and a colon is not a statement about the claim"
        assert claim == QUOTE

    def test_an_unknown_field_in_a_mapping_is_still_reported(self) -> None:
        # The mapping branch has declared itself by writing `quote:`; there the
        # unknown line is reported rather than quoted.  That asymmetry is the
        # rule, not an oversight.
        result = _split_body(["quote: |", "  " + QUOTE, "Note: ours."])
        assert result[0] == QUOTE
        assert result[3] == [(3, "Note")]


class TestTheShapeStaysAParagraphShape:
    def test_a_body_that_names_no_field_is_unchanged(self) -> None:
        quote, claim, attributes, _unknown = _split_body([QUOTE, "", SECOND])
        assert (quote, claim, attributes) == (QUOTE, SECOND, {})

    def test_the_second_paragraph_is_not_a_field(self) -> None:
        # `page: 2` in the second paragraph is lifted out, which leaves the
        # second paragraph empty - so no claim text is invented from it.
        quote, claim, _attributes, _unknown = _split_body([QUOTE, "", "page: 2"])
        assert (quote, claim) == (QUOTE, "")


class TestWhatTheAuthorLosesIsSaid:
    def test_a_body_value_the_fence_overrides_is_named(self) -> None:
        result = parse_manuscript(
            _fenced(f"page: 2{NL}{QUOTE}", attrs="id=c1 source=paper page=1"), path="m.md"
        )
        codes = [finding.code for finding in result.findings]
        assert codes == ["claim-field-shadowed"]
        message = result.findings[0].message
        assert "'1' on the opening line" in message
        assert "'2' in the body" in message

    def test_the_finding_points_at_the_body_line(self) -> None:
        text = _fenced(f"page: 2{NL}{QUOTE}", attrs="id=c1 source=paper page=1")
        result = parse_manuscript(text, path="m.md")
        assert result.findings[0].line == 4
        assert text.splitlines()[3].strip() == "page: 2"

    def test_a_block_with_no_quote_left_says_that(self) -> None:
        result = parse_manuscript(_fenced("page: 2"), path="m.md")
        messages = [finding.message for finding in result.findings]
        assert any("carries no verbatim quote" in message for message in messages)
        assert not any(finding.code == "quote-missing" for finding in result.findings)

    def test_the_first_of_two_body_lines_is_the_one_kept(self) -> None:
        # Same decision the mapping shape makes, and the same one the opening
        # line makes: the first spelling wins and the rest are reported.  A
        # last-one-wins rule would make the verdict depend on line order.
        text = _fenced(f"page: 2{NL}page: 3{NL}{QUOTE}", attrs="id=c1 source=paper")
        result = parse_manuscript(text, path="m.md")
        assert [(c.page, c.quote) for c in result.claims] == [(2, QUOTE)]
        repeated = [f for f in result.findings if f.code == "claim-field-repeated"]
        assert len(repeated) == 1
        assert "'2'" in repeated[0].message
        assert "'3'" in repeated[0].message

    def test_the_same_value_twice_says_nothing(self) -> None:
        # Two lines saying the same thing are not a loss, so there is nothing
        # to report - and reporting it would train the author to ignore the one
        # code that means a value went missing.
        text = _fenced(f"page: 2{NL}page: 2{NL}{QUOTE}", attrs="id=c1 source=paper")
        result = parse_manuscript(text, path="m.md")
        assert [(c.page, c.quote) for c in result.claims] == [(2, QUOTE)]
        assert not [f for f in result.findings if f.code == "claim-field-repeated"]

    def test_a_quoted_value_is_unwrapped_like_the_opening_line(self) -> None:
        # `page: "2"` is the same statement as `page: 2`, and the same one as
        # `page="2"` on the fence.  The quote marks are spelling, not content:
        # left in, the hint reads as `"2"` and matches no page at all.
        quote, _claim, attributes, _unknown = _split_body(['page: "2"', "", QUOTE])
        assert attributes == {"page": "2"}
        assert quote == QUOTE


class TestTheVerdictOnAProject:
    def test_the_page_hint_is_used(self, tmp_path, capsys) -> None:
        main = _project(tmp_path, f"page: 2{NL}{QUOTE}")
        assert main(["check", "m.md", "--root", str(tmp_path)]) == 0
        out = capsys.readouterr().out
        assert "quote-found" in out
        assert "page 2" in out

    def test_a_wrong_page_hint_is_still_a_page_hint(self, tmp_path, capsys) -> None:
        # Page 3 exists and the passage is on page 2, so the honest verdict is
        # `quote-moved` - the hint was read, the passage was found, and the two
        # disagree.  Before the fix the quote was `QUOTE\npage: 3`, which found
        # nothing and accused the author of quoting words their source never
        # printed, at a severity that fails the build.
        page = PAGE + "\fYet another page of prose.\n"
        main = _project(tmp_path, f"{QUOTE}{NL}page: 3", page=page)
        assert main(["check", "m.md", "--root", str(tmp_path)]) == 0
        out = capsys.readouterr().out
        assert "quote-moved" in out
        assert "quote-missing" not in out
        assert "page: 3" not in out, "the author's own line must not be the quoted text"

        assert main(["scan", "m.md", "--root", str(tmp_path)]) == 0
        recorded = json.loads((tmp_path / "citevouch.lock.json").read_text(encoding="utf-8"))
        claim = recorded["claims"][0]
        assert claim["quote"] == QUOTE
        assert claim["page"] == 3
