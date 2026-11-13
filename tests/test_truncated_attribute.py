"""A value written in more than one word on the opening line of a claim block.

`_attrs` reads an unquoted value only up to the first space, and the words that
follow belong to no attribute at all: they are not appended to the quote, they
are not reported as an unknown field, and no other check looks at them.  So the
author writes a hint, the tool reads the first word of it, and the rest is
deleted in silence - the same silence `pgae=3` was fixed to refuse on this line.

Measured with a two-page source whose quote is printed on page 2 only:

    ```claim id=c1 source=paper page=1 to 2   -> [info] quote-found page 2, exit 0
    ```claim id=c1 source=paper page=1 and 2  -> [info] quote-found page 2, exit 0

The run answered a question about page 1 and never said that `to 2` was on the
line.  The body dialect reads the whole line (`page: 1 to 2` gives
`page-unreadable`), so this was an opening-line-only loss.

What this file also pins down: the fix must not turn a *quoted* value into a
finding about truncation (it is already reported, as `page-unreadable`), must
not speak about keys the format does not use (`note=one two three` is prose that
happens to contain an equals sign), and must not mistake a trailing comment for
a lost word.
"""

from __future__ import annotations

import contextlib
import io
from pathlib import Path

import pytest

from citevouch.cli import main
from citevouch.manuscript import parse_manuscript

B3 = "`" * 3
NL = chr(10)
QUOTE = "We collected 154,391 examples from the corpus."
# Page 1 says something else, so "which page was used" is visible in the output
# rather than inferred from the exit code.
PAGES = ["It was the second year of the project.", QUOTE]


def _project(root: Path, manuscript: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "page.txt").write_text(chr(12).join(PAGES) + chr(12), encoding="utf-8")
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8"
    )
    (root / "manuscript.md").write_text(manuscript, encoding="utf-8", newline="\n")
    return root


def _fenced(attrs: str) -> str:
    return (
        "# T"
        + NL
        + NL
        + f"{B3}claim {attrs}"
        + NL
        + "quote: |"
        + NL
        + "  "
        + QUOTE
        + NL
        + B3
        + NL
    )


def _commented(attrs: str) -> str:
    return (
        "# T"
        + NL
        + NL
        + f"<!-- claim {attrs}"
        + NL
        + "quote: |"
        + NL
        + "  "
        + QUOTE
        + NL
        + "-->"
        + NL
    )


def _any_dialect(attrs: str) -> str:
    return _fenced(attrs)


def _findings(text: str) -> list:
    return parse_manuscript(text, path="m.md").findings


def _codes(text: str) -> list[str]:
    return [finding.code for finding in _findings(text)]


def _truncated(text: str) -> list:
    return [finding for finding in _findings(text) if finding.code == "claim-field-truncated"]


def _run(root: Path, *args: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main([*args, "manuscript.md", "--root", str(root)])
    return code, out.getvalue()


class TestTheLostWordsAreNamed:
    @pytest.mark.parametrize(
        ("attrs", "kept", "lost"),
        [
            ("id=c1 source=paper page=1 to 2", "1", "to 2"),
            ("id=c1 source=paper page=1 and 2", "1", "and 2"),
            ("id=c1 source=paper source=paper extra", "paper", "extra"),
            ("id=c1 source=paper ref=knuth2020 et al", "knuth2020", "et al"),
            ("id=c1 source=paper marker=see above", "see", "above"),
        ],
    )
    def test_the_value_and_the_words_it_lost_are_both_named(
        self, attrs: str, kept: str, lost: str
    ) -> None:
        found = _truncated(_any_dialect(attrs))
        assert len(found) == 1
        message = found[0].message
        assert f"read as {kept!r}" in message
        assert f"{lost!r}, which belongs to no attribute" in message
        assert f"{lost!r} was dropped" in message

    def test_the_advice_names_a_spelling_that_keeps_the_words(self) -> None:
        message = _truncated(_any_dialect("id=c1 source=paper page=1 to 2"))[0].message
        assert 'page="1 to 2"' in message

    def test_the_finding_points_at_the_line_that_holds_it(self) -> None:
        text = "# T" + NL + NL + f"{B3}claim id=c1 source=paper page=1 to 2" + NL
        text += "quote: |" + NL + "  " + QUOTE + NL + B3 + NL
        found = _truncated(text)
        assert [finding.line for finding in found] == [3]
        assert text.splitlines()[2].strip().startswith("```claim id=c1")

    def test_one_key_with_a_tail_is_reported_once(self) -> None:
        # `page` is written twice; only the first spelling has a tail, and the
        # second one has its own finding (`claim-field-repeated`).  Two
        # truncation findings for one key would be two sentences about one
        # mistake.
        found = _truncated(_any_dialect("id=c1 source=paper page=1 x page=2 y"))
        assert [f.message.split(" and then ")[1].split(",")[0] for f in found] == ["'x'"]

    def test_a_second_attribute_after_the_value_is_not_a_lost_word(self) -> None:
        # `ref=knuth2020` follows `page=1`; the words in between are the value's
        # tail, and the attribute after it still has to be read.
        parsed = parse_manuscript(
            _any_dialect("id=c1 source=paper page=1 ref=knuth2020"),
            path="m.md",
        )
        assert parsed.claims[0].page == 1
        assert parsed.claims[0].ref == "knuth2020"
        assert [f.code for f in parsed.findings] == []


class TestWhatMustStaySilent:
    def test_a_quoted_value_is_already_reported_and_is_not_reported_twice(self) -> None:
        codes = _codes(_any_dialect('id=c1 source=paper page="1 to 2"'))
        assert "page-unreadable" in codes
        assert "claim-field-truncated" not in codes

    def test_a_key_the_format_does_not_use_is_prose(self) -> None:
        assert _codes(_any_dialect("id=c1 source=paper note=one two three")) == []

    def test_a_trailing_comment_is_not_a_lost_word(self) -> None:
        assert _codes(_any_dialect("id=c1 source=paper page=1 # page two")) == []

    def test_a_tail_that_is_not_a_word_is_left_to_the_page_hint(self) -> None:
        # `page=p.` keeps `p.` and leaves `1`: that is not a lost word, and
        # `page-unreadable` already says the hint could not be applied.
        codes = _codes(_any_dialect("id=c1 source=paper page=p. 1"))
        assert "page-unreadable" in codes
        assert "claim-field-truncated" not in codes

    def test_a_misspelt_key_is_still_the_unknown_field_finding(self) -> None:
        codes = _codes(_any_dialect("id=c1 source=paper page: 9"))
        assert codes == ["claim-field-unknown"]

    def test_trailing_spaces_are_not_a_lost_word(self) -> None:
        assert _codes(_any_dialect("id=c1 source=paper   ")) == []


class TestTheDialectsAgree:
    @pytest.mark.parametrize("attrs", ["id=c1 source=paper page=1 to 2", "id=c1 source=paper"])
    def test_the_comment_dialect_reports_what_the_fence_reports(self, attrs: str) -> None:
        fence = [(f.code, f.message) for f in _findings(_fenced(attrs))]
        comment = [(f.code, f.message) for f in _findings(_commented(attrs))]
        assert fence == comment


class TestTheVerdictOnAProject:
    def test_the_page_the_run_used_is_still_reported_honestly(self, tmp_path: Path) -> None:
        # The quote is on page 2; the hint was read as page 1.  The run finds
        # the quote (search starts at the hint and walks on), and now it also
        # says that the hint it used was not the hint that was written.
        root = _project(tmp_path, _fenced("id=c1 source=paper page=1 to 2"))
        code, out = _run(root, "check")
        assert code == 0
        assert "quote-moved" in out
        assert "quote is on page 2, the ledger says 1" in out
        assert "claim-field-truncated" in out
        assert "to 2" in out

    def test_the_threshold_can_turn_it_into_a_failure(self, tmp_path: Path) -> None:
        root = _project(tmp_path, _fenced("id=c1 source=paper page=1 to 2"))
        assert _run(root, "check")[0] == 0
        code, out = _run(root, "check", "--fail-on", "medium")
        assert code == 1
        assert "claim-field-truncated" in out

    def test_a_clean_claim_says_nothing(self, tmp_path: Path) -> None:
        root = _project(tmp_path, _fenced("id=c1 source=paper page=2"))
        code, out = _run(root, "check")
        assert code == 0
        assert "claim-field-truncated" not in out
