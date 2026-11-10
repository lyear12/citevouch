r"""An HTML block under a one-line claim comment is not its quote.

The one-line comment dialect has no terminator of its own, so its body ends
where the next construct starts.  An ATX heading and a thematic break were
added to that list; HTML was the third family and was still missing.  Measured
in a project whose page prints the quoted sentence:

    <!-- claim: c1 source=paper page=1 -->
    </div>
    -> [high] quote-missing at manuscript.md:1 (c1): </div> - quote not found
       (too short for a fuzzy comparison) in page.txt

The same for `<div class="note">`, `<br>`, `<hr>`, `<table>` and `<details>`.
Every one of them sends the author to their PDF looking for a tag their source
never printed, when the truth is that the block holds no quote at all and the
honest finding is `claim-uncheckable`.

The rule is CommonMark's, not "anything in angle brackets":

* a block-level tag name, opening or closing, starts a block (type 6);
* a complete tag alone on a line starts a block (type 7);
* `<script>`, `<pre>`, `<style>` and `<textarea>` start a block (type 1).

So `a <b>bold</b> word` is still prose, `<divs>` is not a tag name, and
`5 < 7 and 8 > 2` is still arithmetic.  That distinction is the whole point:
reading every angle bracket as a boundary would chop a legitimate quote in
half, which loses a quote instead of misreporting one.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from citevouch.manuscript import parse_manuscript

NL = chr(10)
QUOTE = "We collected 40,688 examples from the corpus."
PAGE = "Preface" + NL + QUOTE + NL
OPENER = "<!-- claim: c1 source=paper page=1 -->"
PYTHONPATH = str(Path(__file__).resolve().parents[1] / "src")


def parse(*lines: str):
    return parse_manuscript(NL.join(lines) + NL, path="manuscript.md")


def quote_of(*lines: str) -> list[str]:
    return [claim.quote for claim in parse(*lines).claims]


def codes(*lines: str) -> list[str]:
    return [finding.code for finding in parse(*lines).findings]


def _run(root: Path, *argv: str) -> tuple[int, str]:
    env = {**os.environ, "PYTHONPATH": PYTHONPATH, "PYTHONIOENCODING": "utf-8"}
    got = subprocess.run(
        [sys.executable, "-m", "citevouch", *argv],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    return got.returncode, (got.stdout or "") + (got.stderr or "")


def _project(root: Path, manuscript: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline=chr(10))
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL,
        encoding="utf-8",
        newline=chr(10),
    )
    (root / "manuscript.md").write_text(manuscript, encoding="utf-8", newline=chr(10))


class TestAnHtmlBlockIsNotTheQuote:
    @pytest.mark.parametrize(
        "line",
        [
            "</div>",
            '<div class="note">',
            "<br>",
            "<hr>",
            "<table>",
            "<details>",
            "</details>",
            "<p>",
            "  </div>",
            "<DIV>",
        ],
    )
    def test_a_block_level_tag_stops_the_quote(self, line):
        assert quote_of(OPENER, line) == [], line
        assert codes(OPENER, line) == ["claim-uncheckable"], line

    @pytest.mark.parametrize(
        "line",
        ["<span>", "</a>", "<img src=x>", '<a href="x">', "<custom-el>"],
    )
    def test_a_tag_alone_on_its_line_stops_the_quote(self, line):
        assert quote_of(OPENER, line) == [], line
        assert codes(OPENER, line) == ["claim-uncheckable"], line

    @pytest.mark.parametrize("line", ["<script>", "<pre>", "<style>", "<textarea>"])
    def test_a_raw_text_element_stops_the_quote(self, line):
        assert quote_of(OPENER, line) == [], line

    def test_the_indent_limit_is_three_spaces(self):
        # CommonMark matches an HTML block after at most three spaces.  Four
        # spaces is an indented code block, which is a different construct and
        # not one this dialect handles - so `</div>` at four spaces stays
        # content, and that is written down here rather than discovered later.
        assert quote_of(OPENER, "   </div>") == []
        assert quote_of(OPENER, "    </div>") == ["</div>"]


class TestWhatMustStillBeTheQuote:
    @pytest.mark.parametrize(
        "line",
        [
            "> " + QUOTE,
            QUOTE,
            "  " + QUOTE,
            "a <b>bold</b> word",
            "5 < 7 and 8 > 2",
            "<divs> is not a tag",
            "We cite <div> in passing",
        ],
    )
    def test_prose_and_inline_markup_stay_in_the_sentence(self, line):
        found = quote_of(OPENER, *line.split(NL))
        assert found, line

    def test_a_tag_line_ends_the_block_so_the_next_line_is_not_the_quote(self):
        # `<div>` alone is an HTML block, so it is a boundary - and the prose
        # after it belongs to the document, not to the claim comment above it.
        # That is the CommonMark reading and the one that cannot invent a quote.
        assert quote_of(OPENER, "<div>", QUOTE) == []


class TestABlockLevelTagWithTextAfterIt:
    """The half of the rule that "a tag alone on a line" cannot cover.

    A block-level tag opens a block even when prose follows it on the same
    line: `<div class="note">Some text.` is a block, not a sentence.  Without
    the name list, only the alone-on-a-line form matches, and every line here
    would be read as the quote.
    """

    @pytest.mark.parametrize(
        "line",
        [
            '<div class="note">Some text follows.',
            "<div>Some text follows.",
            "<p>Some text follows.",
            "</div> trailing words",
            "<table> <tr> <td>cell",
            "<details>Summary here",
        ],
    )
    def test_a_block_level_tag_opens_a_block_even_with_text_after_it(self, line):
        assert quote_of(OPENER, line) == [], line
        assert codes(OPENER, line) == ["claim-uncheckable"], line

    @pytest.mark.parametrize("name", ["div", "DIV", "Div", "dIv"])
    def test_the_name_authors_write_in_any_case(self, name):
        # `</DIV>` alone is matched by the alone-on-a-line form whatever its
        # case; the list has to be case insensitive too, or a tag with text
        # after it stops counting and the line becomes the quote.
        line = "<" + name + ">Some text follows."
        assert quote_of(OPENER, line) == [], line

    @pytest.mark.parametrize(
        "line",
        ["<divs>Some text follows.", "<dividend>Amount is 5", "<d>short"],
    )
    def test_a_name_the_list_does_not_carry_is_inline(self, line):
        found = quote_of(OPENER, line)
        assert found == [line], line

    def test_an_inline_tag_does_not_split_the_sentence(self):
        assert quote_of(OPENER, "See <b>this</b> line.") == ["See <b>this</b> line."]

    def test_the_marker_line_still_wins_over_what_follows(self):
        assert quote_of(OPENER, ">> " + QUOTE, "</div>") == [QUOTE]

    def test_a_divider_line_still_stops_the_quote(self):
        assert quote_of(OPENER, "## Methods") == []


class TestTheVerdictOnAProject:
    def test_the_tag_is_not_reported_missing_from_the_page(self, tmp_path):
        root = tmp_path / "proj"
        _project(root, "## Methods" + NL + NL + OPENER + NL + "</div>" + NL)
        code, report = _run(root, "check", "manuscript.md", "--root", str(root))
        assert "</div>" not in report
        assert "quote-missing" not in report
        assert "claim-uncheckable" in report
        assert code == 1

    def test_a_claim_with_a_real_quote_under_a_heading_still_verifies(self, tmp_path):
        root = tmp_path / "proj"
        _project(
            root,
            "## Methods" + NL + NL + OPENER + NL + ">> " + QUOTE + NL + "</div>" + NL,
        )
        code, report = _run(root, "check", "manuscript.md", "--root", str(root))
        assert "quote-found" in report
        assert "1 claim" in report
        assert code == 0
