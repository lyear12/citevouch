"""A claim written as a mapping must be read as a mapping.

Measured before the fix, with the page reading
``We collected 40,688 examples in the corpus.``:

    ```claim id=c1 source=paper page=1
    quote: |
      We collected 40,688 examples in the corpus.
    ref: paper2026
    ```

came back as

    [high] quote-missing at m.md:3 (c1): We collected 40,688 examples in the
    corpus. ref: paper2026 - quote not found in page.txt

and the same block written as an HTML comment did too.  The passage is on the
page; what was searched for was the passage *plus* the author's own attribute
line, so the tool accused them of quoting something their PDF does not say.
Every part of this was silent: the quote simply came back longer, the claim
count was right, and only the verdict was wrong.

The two dialects shared the reader, so they shared the defect.  These tests
say so twice on purpose - a fix in one branch is how the other branch stays
broken.
"""

from __future__ import annotations

import pytest

from citevouch.manuscript import parse_manuscript

# Written as a name so the fences stay readable in this file's own prose.
B3 = "`" * 3
QUOTE = "We collected 40,688 examples in the corpus."
PAGE = f"{QUOTE}\n"


def _fenced(body: str, attrs: str = "id=c1 source=paper") -> str:
    return f"# T\n\n{B3}claim {attrs}\n{body}\n{B3}\n"


def _commented(body: str, attrs: str = "id=c1 source=paper") -> str:
    return f"# T\n\n<!-- claim {attrs}\n{body}\n-->\n"


class TestTheAttributesAreNotQuoteText:
    @pytest.mark.parametrize("ref", ["ref: paper2026", "cite: paper2026"])
    def test_a_reference_line_is_not_part_of_the_quote(self, ref: str) -> None:
        body = f"quote: |\n  {QUOTE}\n{ref}"
        result = parse_manuscript(_fenced(body))
        assert [claim.quote for claim in result.claims] == [QUOTE]

    def test_a_page_line_is_not_part_of_the_quote(self) -> None:
        body = f"quote: |\n  {QUOTE}\npage: 1"
        result = parse_manuscript(_fenced(body))
        assert [claim.quote for claim in result.claims] == [QUOTE]

    def test_an_unknown_key_still_is_part_of_the_quote(self) -> None:
        # The fix names the six keys a claim may carry.  Anything else is text
        # the author quoted, and dropping it silently would be a worse defect
        # than the one being fixed: a quote that grew is visible in a verdict,
        # a quote that shrank is visible nowhere.
        body = f"quote: |\n  {QUOTE}\nfootnote: hello"
        result = parse_manuscript(_fenced(body))
        assert [claim.quote for claim in result.claims] == [f"{QUOTE}\nfootnote: hello"]

    def test_the_html_dialect_reads_them_too(self) -> None:
        body = f"quote: |\n  {QUOTE}\nref: paper2026"
        result = parse_manuscript(_commented(body))
        assert [claim.quote for claim in result.claims] == [QUOTE]
        assert [claim.ref for claim in result.claims] == ["paper2026"]


class TestABlockCanCarryEveryAttributeInItsBody:
    def test_a_block_with_nothing_on_the_fence_line_is_read(self) -> None:
        body = f"id: c1\nsource: paper\npage: 1\nquote: |\n  {QUOTE}"
        result = parse_manuscript(_fenced(body, attrs=""))
        assert [(claim.id, claim.source, claim.page) for claim in result.claims] == [
            ("c1", "paper", 1)
        ]
        assert result.findings == []

    def test_the_fence_wins_when_both_name_the_same_key(self) -> None:
        # The documented place wins, because it is where a reader looks, and a
        # silent override from a less visible place is its own kind of lie.
        body = f"source: elsewhere\nquote: |\n  {QUOTE}"
        result = parse_manuscript(_fenced(body, attrs="id=c1 source=paper"))
        assert [claim.source for claim in result.claims] == ["paper"]

    def test_the_body_fills_in_what_the_fence_leaves_out(self) -> None:
        body = f"source: paper\nquote: |\n  {QUOTE}"
        result = parse_manuscript(_fenced(body, attrs="id=c1"))
        assert [(claim.id, claim.source) for claim in result.claims] == [("c1", "paper")]

    def test_a_body_attribute_between_two_quote_lines_is_not_quoted(self) -> None:
        body = f"quote: |\n  {QUOTE}\nref: paper2026\nclaim: |\n  The corpus was large."
        result = parse_manuscript(_fenced(body))
        assert [claim.quote for claim in result.claims] == [QUOTE]
        assert [claim.text for claim in result.claims] == ["The corpus was large."]


class TestTheShapesThatAreNotMappingsKeepTheirQuote:
    """A body with no ``quote:`` key is all quote, by the documented fallback.

    This is the regression the fix introduced and this file's own run caught:
    counting an ``id:``/``source:`` line as a "key" made a ``>>`` block look
    like a mapping, and the quote came back empty while the attribute line
    became the claim text - a silent loss, which is worse than the defect being
    fixed.  Both shapes below were quoted correctly before the fix and have to
    stay that way.
    """

    def test_the_arrow_shape_keeps_its_quote(self) -> None:
        body = f">> {QUOTE}\nsource: paper"
        result = parse_manuscript(_fenced(body, attrs="id=c1 source=paper"))
        assert [claim.quote for claim in result.claims] == [QUOTE]

    def test_a_body_with_no_keys_is_all_quote(self) -> None:
        body = f"{QUOTE}\npage: 1"
        result = parse_manuscript(_fenced(body))
        assert [claim.quote for claim in result.claims] == [f"{QUOTE}\npage: 1"]


class TestTheVerdictOnARealProject:
    def test_the_quote_is_found_when_the_page_holds_it(self, tmp_path) -> None:
        from citevouch.cli import main

        (tmp_path / "page.txt").write_text(PAGE, encoding="utf-8", newline="\n")
        (tmp_path / "sources.toml").write_text(
            '[sources]\npaper = "page.txt"\n', encoding="utf-8", newline="\n"
        )
        body = f"quote: |\n  {QUOTE}\nref: paper2026"
        (tmp_path / "m.md").write_text(_fenced(body), encoding="utf-8", newline="\n")
        assert main(["check", "m.md", "--root", str(tmp_path), "--quiet"]) == 0

    def test_the_html_dialect_is_found_too(self, tmp_path) -> None:
        from citevouch.cli import main

        (tmp_path / "page.txt").write_text(PAGE, encoding="utf-8", newline="\n")
        (tmp_path / "sources.toml").write_text(
            '[sources]\npaper = "page.txt"\n', encoding="utf-8", newline="\n"
        )
        body = f"quote: |\n  {QUOTE}\nref: paper2026"
        (tmp_path / "m.md").write_text(_commented(body), encoding="utf-8", newline="\n")
        assert main(["check", "m.md", "--root", str(tmp_path), "--quiet"]) == 0
